import os
import time
from pathlib import Path

import pytest

from rvs_core.vcs.git import GitError, GitRepo


def test_discover_fails_with_a_helpful_message_outside_a_repository(tmp_path: Path):
    with pytest.raises(GitError, match="not inside a Git repository"):
        GitRepo.discover(tmp_path)


def test_init_commit_tag_and_read_back(tmp_path: Path):
    proj = tmp_path / "proj"
    (proj / "SYS").mkdir(parents=True)
    (proj / "SYS" / "a.yml").write_text("x: 1\n")
    repo = GitRepo.init(proj)
    c1 = repo.commit_directory(proj, "first", "alice")
    assert c1 and repo.head() == c1
    (proj / "SYS" / "a.yml").write_text("x: 2\n")
    (proj / "new.yml").write_text("n\n")
    c2 = repo.commit_directory(proj, "second", "alice")
    assert c2 != c1
    repo.create_tag("rvs/baseline/v1", "a message", "alice", c2)
    info = repo.tag("rvs/baseline/v1")
    assert info is not None and info.commit == c2 and info.tagger.startswith("alice") and "a message" in info.message
    assert abs(info.time - time.time()) < 60
    assert repo.read_tree(c2, proj) == {"SYS/a.yml": b"x: 2\n", "new.yml": b"n\n"}
    assert repo.read_tree(c1, proj) == {"SYS/a.yml": b"x: 1\n"}


def test_commit_directory_records_deletions_and_skips_the_cache_folder(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.yml").write_text("1")
    (proj / "b.yml").write_text("2")
    (proj / ".rvs-cache").mkdir()
    (proj / ".rvs-cache" / "x.json").write_text("{}")
    repo = GitRepo.init(proj)
    repo.commit_directory(proj, "one", "a")
    (proj / "b.yml").unlink()
    c = repo.commit_directory(proj, "two", "a")
    assert sorted(repo.read_tree(c, proj)) == ["a.yml"]


def test_commit_directory_with_no_changes_returns_the_current_head(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "a.yml").write_text("1")
    repo = GitRepo.init(proj)
    c = repo.commit_directory(proj, "one", "a")
    assert repo.commit_directory(proj, "again", "a") == c


def test_only_the_project_directory_is_committed_when_it_is_inside_a_larger_repository(tmp_path: Path):
    repo = GitRepo.init(tmp_path)
    proj = tmp_path / "sub" / "proj"
    proj.mkdir(parents=True)
    (proj / "a.yml").write_text("1")
    (tmp_path / "unrelated.txt").write_text("keep out")
    found = GitRepo.discover(proj)
    c = found.commit_directory(proj, "msg", "a")
    assert found.read_tree(c, proj) == {"a.yml": b"1"}
    assert found.root == repo.root
    assert found.relative(proj) == "sub/proj"
    entries = found.read_tree(c, tmp_path)
    assert "unrelated.txt" not in entries


def test_commit_is_never_signed_even_when_the_user_configures_signing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # A global `commit.gpgsign=true` with an unavailable signer must not break (or hang) a baseline.
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[commit]\n\tgpgsign = true\n[gpg]\n\tformat = ssh\n[user]\n\tname = Zed\n\temail = z@example.com\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("HOME", str(tmp_path))
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "a.yml").write_text("1")
    repo = GitRepo.init(proj)
    assert repo.commit_directory(proj, "m", None)


def test_author_comes_from_the_given_user_then_git_config_then_login(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("HOME", str(tmp_path))
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "a.yml").write_text("1")
    repo = GitRepo.init(proj)
    c = repo.commit_directory(proj, "m", "carol")
    assert repo.commit_author(c).startswith("carol <")


def test_tags_listing_is_sorted_and_prefix_filtered(tmp_path: Path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "a.yml").write_text("1")
    repo = GitRepo.init(proj)
    c = repo.commit_directory(proj, "m", "a")
    for name in ("rvs/baseline/b", "rvs/baseline/a", "other/x"):
        repo.create_tag(name, "m", "a", c)
    assert [t.name for t in repo.tags("rvs/baseline/")] == ["rvs/baseline/a", "rvs/baseline/b"]
    with pytest.raises(GitError, match="already exists"):
        repo.create_tag("rvs/baseline/a", "again", "a", c)
