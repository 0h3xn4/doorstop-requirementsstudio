"""Regressions for defects found in change control and the Git facade by the review pass."""

import hashlib
import json
import os
import stat
import subprocess
import threading
import time
from pathlib import Path

import pytest
from dulwich.objects import Blob, Commit, Tag, Tree
from dulwich.repo import Repo

from rvs_core.authoring import EditService, read_history
from rvs_core.changecontrol.baselines import (
    BaselineError,
    create_baseline,
    list_baselines,
    snapshot_dir,
    verify_baseline,
)
from rvs_core.changecontrol.changes import ChangeRequestError, ChangeRequestStore
from rvs_core.config import load_project_config
from rvs_core.validate import validate_project
from rvs_core.vcs.git import GitError, GitRepo


def _git(root: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }
    return subprocess.run(["git", *args], cwd=root, env=env, capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


# snapshot extraction ----------------------------------------------------------------------------------------------------------------
def _craft_tag(repo_root: Path, tag_name: str, entry: bytes, content: bytes = b"owned\n") -> None:
    """A tagged commit whose tree holds one entry with a hostile name next to the real tree of HEAD."""
    repo = Repo(str(repo_root))
    blob = Blob.from_string(content)
    repo.object_store.add_object(blob)
    head = repo[repo.head()]
    assert isinstance(head, Commit)
    tree = Tree()
    tree.add(entry, 0o100644, blob.id)
    repo.object_store.add_object(tree)
    commit = Commit()
    commit.tree, commit.parents = tree.id, []
    commit.author = commit.committer = b"x <x@x>"
    commit.author_time = commit.commit_time = 1
    commit.author_timezone = commit.commit_timezone = 0
    commit.message = b"evil"
    repo.object_store.add_object(commit)
    tag = Tag()
    tag.name, tag.message, tag.tagger = tag_name.encode(), b"evil", b"x <x@x>"
    tag.tag_time, tag.tag_timezone, tag.object = 1, 0, (Commit, commit.id)
    repo.object_store.add_object(tag)
    repo.refs[f"refs/tags/{tag_name}".encode()] = tag.id
    repo.close()


@pytest.mark.parametrize("entry", [b"..", b"../escape.txt", b"a\\..\\b", b".git"])
def test_hostile_tree_entries_are_refused_not_written(git_project: Path, tmp_path: Path, entry: bytes):
    create_baseline(git_project, "T1", "first", user="a")
    repo = GitRepo.discover(git_project)
    tag = repo.tag("rvs/baseline/T1")
    assert tag is not None
    outside = tmp_path / "escape.txt"
    # rewrite the tag so it points at a commit with a crafted tree; the manifest digest in the message stays valid
    repo.close()
    _craft_tag(git_project, "rvs/baseline/T2", entry)
    (git_project / "baselines" / "T2.yaml").write_text((git_project / "baselines" / "T1.yaml").read_text())
    with pytest.raises((BaselineError, GitError)):
        snapshot_dir(git_project, "T2")
    assert not outside.exists() and not (git_project.parent / "escape.txt").exists()


# baseline creation --------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ["a..b", "v1.lock", "v1.", "working", "x.lock.y"[:0] + "WORKING"])
def test_names_git_cannot_hold_are_refused_before_anything_is_written(git_project: Path, name: str):
    before = (git_project / "SYS" / "SYS-0001.yml").read_bytes()
    with pytest.raises(BaselineError):
        create_baseline(git_project, name, "x", user="a")
    assert not (git_project / "baselines").exists() or not list((git_project / "baselines").glob("*.yaml"))
    assert (git_project / "SYS" / "SYS-0001.yml").read_bytes() == before


def test_a_failing_commit_hook_does_not_run_or_break_baselines(git_project: Path):
    hook = git_project / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
    baseline = create_baseline(git_project, "H1", "x", user="a")
    assert baseline.commit and verify_baseline(git_project, "H1") == []


def test_a_failure_after_the_first_write_is_rolled_back(git_project: Path, monkeypatch):  # type: ignore[no-untyped-def]
    import rvs_core.changecontrol.baselines as bl

    EditService(git_project).update_item("SYS-0001", attrs={"status": "approved"})
    original = (git_project / "SYS" / "SYS-0001.yml").read_bytes()

    def fail(*_a: object, **_k: object) -> None:
        raise GitError("simulated tag failure")

    monkeypatch.setattr(GitRepo, "create_tag", fail)
    with pytest.raises(GitError):
        bl.create_baseline(git_project, "R1", "x", user="a")
    monkeypatch.undo()
    assert (git_project / "SYS" / "SYS-0001.yml").read_bytes() == original  # still "approved", not "baselined"
    assert not (git_project / "baselines" / "R1.yaml").exists()
    assert create_baseline(git_project, "R1", "x", user="a").name == "R1"  # the name is not burned


def test_unrelated_staged_and_ignored_files_stay_out_of_the_baseline_commit(tmp_path: Path):
    from rvs_core.examples.minimal import build_minimal_project

    repo_root = tmp_path / "repo"
    project = repo_root / "proj"
    build_minimal_project(project)
    (repo_root / ".gitignore").write_text("*.env\n")
    _git(repo_root, "init", "-q")
    (repo_root / "other.txt").write_text("staged by the user, not committed\n")
    _git(repo_root, "add", "other.txt", ".gitignore")
    (project / "secret.env").write_text("TOKEN=1\n")
    create_baseline(project, "D1", "x", user="a")
    files = _git(repo_root, "ls-tree", "-r", "--name-only", "HEAD").split()
    assert "other.txt" not in files and "proj/secret.env" not in files and "proj/SYS/SYS-0001.yml" in files
    assert "other.txt" in _git(repo_root, "diff", "--cached", "--name-only")  # still staged, untouched


def test_submodules_and_nested_repositories_are_not_flattened(tmp_path: Path):
    from rvs_core.examples.minimal import build_minimal_project

    repo_root = tmp_path / "repo"
    project = repo_root / "proj"
    build_minimal_project(project)
    _git(repo_root.parent, "init", "-q", str(repo_root))
    nested = project / "ext"
    nested.mkdir()
    _git(nested, "init", "-q")
    (nested / "lib.txt").write_text("library\n")
    create_baseline(project, "S1", "x", user="a")
    files = _git(repo_root, "ls-tree", "-r", "--name-only", "HEAD").split()
    assert not any(f.startswith("proj/ext") for f in files)


def test_baseline_names_that_sanitise_alike_get_different_tags(tmp_path: Path):
    from rvs_core.examples.minimal import build_minimal_project

    repo_root = tmp_path / "repo"
    _git(tmp_path, "init", "-q", str(repo_root))
    for folder in ("a b", "a_b"):
        build_minimal_project(repo_root / folder)
        create_baseline(repo_root / folder, "X", "x", user="a")  # the second must not collide with the first
    assert len([t for t in _git(repo_root, "tag").split() if t.endswith("/X")]) == 2


def test_a_moved_project_still_finds_its_baselines(tmp_path: Path):
    from rvs_core.examples.minimal import build_minimal_project

    repo_root = tmp_path / "repo"
    _git(tmp_path, "init", "-q", str(repo_root))
    build_minimal_project(repo_root / "proj")
    create_baseline(repo_root / "proj", "M1", "x", user="a")
    _git(repo_root, "mv", "proj", "renamed")
    assert [b.name for b in list_baselines(repo_root / "renamed")] == ["M1"]
    assert verify_baseline(repo_root / "renamed", "M1") == []


def test_crlf_checkouts_and_digest_lookalikes_do_not_fake_tampering(git_project: Path):
    create_baseline(git_project, "C1", "see manifest-sha256: " + "a" * 64, user="a")
    assert verify_baseline(git_project, "C1") == []
    manifest = git_project / "baselines" / "C1.yaml"
    manifest.write_bytes(manifest.read_bytes().replace(b"\n", b"\r\n"))  # what autocrlf does on Windows
    assert verify_baseline(git_project, "C1", deep=False) == []


def test_a_deleted_manifest_with_a_surviving_tag_is_an_error(git_project: Path):
    create_baseline(git_project, "N1", "x", user="a")
    (git_project / "baselines" / "N1.yaml").unlink()
    report = validate_project(git_project, doorstop=False)
    assert any(f.code == "RVS-BASELINE-NOMANIFEST" for f in report.findings) and report.exit_code == 1


def test_latest_baseline_orders_by_instant_not_by_text(git_project: Path):
    import yaml

    create_baseline(git_project, "A1", "x", user="a")
    create_baseline(git_project, "B1", "x", user="a")
    for name, created in (("A1", "2026-01-01T09:00:00.000000+09:00"), ("B1", "2026-01-01T08:30:00.000000+00:00")):
        path = git_project / "baselines" / f"{name}.yaml"
        data = yaml.safe_load(path.read_text())
        data["created"] = created
        path.write_text(yaml.safe_dump(data))
    assert [b.name for b in list_baselines(git_project)] == ["A1", "B1"]  # 00:00Z is earlier than 08:30Z


# change requests -----------------------------------------------------------------------------------------------------------------------
def test_concurrent_change_request_creation_never_loses_one(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    ids: list[str] = []

    def worker() -> None:
        store = ChangeRequestStore(minimal_project, cfg)
        for n in range(8):
            ids.append(store.create(f"CR {n}", "", "a").id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(ids) == len(set(ids)) == 32
    assert len(ChangeRequestStore(minimal_project, cfg).list()) == 32


def test_a_change_request_with_a_status_the_config_does_not_define_blocks_baselines(git_project: Path):
    cfg, _ = load_project_config(git_project)
    store = ChangeRequestStore(git_project, cfg)
    cr = store.create("Typo", "", "a")
    path = git_project / "changes" / f"{cr.id}.yaml"
    path.write_text(path.read_text().replace(f"status: {cr.status}", "status: Open"))
    from rvs_core.changecontrol.baselines import OpenChangeRequestsError

    with pytest.raises(OpenChangeRequestsError):
        create_baseline(git_project, "G1", "x", user="a")


def test_change_request_ids_cannot_escape_the_changes_folder(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    store = ChangeRequestStore(minimal_project, cfg)
    for bad in ("../x", "CR-0001/../../x", "x"):
        with pytest.raises(ChangeRequestError):
            store.get(bad)


def test_one_bad_history_file_does_not_break_the_change_request_views(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    store = ChangeRequestStore(minimal_project, cfg)
    cr = store.create("T", "", "a")
    EditService(minimal_project, change_request=cr.id).update_item("SYS-0001", text="The spacecraft shall be edited.")
    bad = minimal_project / "history" / "SYS" / "SYS-0002.jsonl"
    bad.write_bytes(b'{"cr": "CR-0001"}\n\xff\xfe<<<<<<< HEAD\n{"truncated')
    assert store.edited_items(cr.id) == ["SYS-0001"] or "SYS-0001" in store.edited_items(cr.id)
    assert read_history(minimal_project, "SYS-0002") is not None


# diff ---------------------------------------------------------------------------------------------------------------------------------------
def test_diffing_very_long_statements_stays_fast():
    from rvs_core.changecontrol.diff import text_segments

    before = " ".join(f"word{n}" for n in range(8000))
    after = before.replace("word4000", "changed", 1)
    started = time.perf_counter()
    segments = text_segments(before, after)
    assert time.perf_counter() - started < 5
    assert any(op == "insert" and "changed" in text for op, text in segments)
    assert hashlib and json  # keep imports used
