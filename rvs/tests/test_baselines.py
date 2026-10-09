import hashlib
from pathlib import Path

import pytest
import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.authoring import EditService, ReasonRequiredError, read_history
from rvs_core.changecontrol.baselines import (
    BaselineError,
    OpenChangeRequestsError,
    baselined_uids,
    create_baseline,
    item_digest,
    list_baselines,
    verify_baseline,
)
from rvs_core.changecontrol.changes import ChangeRequestStore
from rvs_core.config import load_project_config
from rvs_core.validate import validate_project
from rvs_core.vcs.git import GitError, GitRepo


def _approve(root: Path, uid: str) -> None:
    DoorstopProject.open(root).update_item(uid, attrs={"status": "approved"})


def test_create_baseline_writes_manifest_commits_and_tags(git_project: Path):
    b = create_baseline(git_project, "PDR", "Preliminary design review", user="alice")
    assert b.name == "PDR" and b.created_by == "alice" and b.items == 10
    manifest = yaml.safe_load((git_project / "baselines" / "PDR.yaml").read_text())
    assert (
        manifest["rvs_schema_version"] == 1
        and manifest["name"] == "PDR"
        and manifest["description"] == "Preliminary design review"
    )
    assert set(manifest["items"]) == {i.uid for i in DoorstopProject.open(git_project).items()}
    assert all(len(v) == 64 for v in manifest["items"].values())
    repo = GitRepo.discover(git_project)
    tag = repo.tag("rvs/baseline/PDR")
    assert tag is not None and tag.commit == b.commit and "Preliminary design review" in tag.message
    committed = repo.read_tree(tag.commit, git_project)
    assert "baselines/PDR.yaml" in committed and "SYS/SYS-0001.yml" in committed and "rvs-project.yaml" in committed
    assert not any(p.startswith(".rvs-cache") for p in committed)


def test_manifest_is_deterministic_for_identical_content(git_project: Path, tmp_path: Path):
    create_baseline(git_project, "A", "d", user="alice")
    first = (git_project / "baselines" / "A.yaml").read_bytes()
    # item digests do not depend on stamps, paths or time
    items = {i.uid: item_digest(i) for i in DoorstopProject.open(git_project).items()}
    assert yaml.safe_load(first)["items"] == items


def test_item_digest_changes_with_content_not_with_irrelevant_fields(git_project: Path):
    proj = DoorstopProject.open(git_project)
    before = item_digest(proj.get_item("SYS-0001"))
    proj.update_item("SYS-0001", attrs={"owner": "someone else"})
    assert item_digest(proj.get_item("SYS-0001")) != before
    proj.update_item("SYS-0001", attrs={"owner": "systems"})
    assert item_digest(proj.get_item("SYS-0001")) == before
    proj.review_item("SYS-0001")  # reviewed stamp is not content
    assert item_digest(proj.get_item("SYS-0001")) == before


def test_name_validation_and_immutability(git_project: Path):
    for bad in ("", "has space", "a/b", "..", "x" * 80):
        with pytest.raises(BaselineError, match="name"):
            create_baseline(git_project, bad, "d", user="a")
    create_baseline(git_project, "PDR", "d", user="a")
    with pytest.raises(BaselineError, match="already exists"):
        create_baseline(git_project, "PDR", "again", user="a")


def test_requires_a_git_repository_unless_asked_to_create_one(minimal_project: Path):
    with pytest.raises(GitError, match="Git repository"):
        create_baseline(minimal_project, "PDR", "d", user="a")
    b = create_baseline(minimal_project, "PDR", "d", user="a", init_git=True)
    assert b.commit and GitRepo.discover(minimal_project).tag("rvs/baseline/PDR")


def test_project_inside_a_larger_repository_uses_a_scoped_tag(tmp_path: Path):
    from rvs_core.examples.minimal import build_minimal_project

    repo_root = tmp_path / "repo"
    GitRepo.init(repo_root)
    proj = repo_root / "reqs" / "sat"
    build_minimal_project(proj)
    (repo_root / "README.md").write_text("not part of the baseline")
    b = create_baseline(proj, "PDR", "d", user="a")
    repo = GitRepo.discover(proj)
    assert b.tag == "rvs/baseline/reqs/sat/PDR" and repo.tag(b.tag) is not None
    assert "README.md" not in repo.read_tree(b.commit, repo.root)
    assert [x.name for x in list_baselines(proj)] == ["PDR"]


def test_list_baselines_sorted_by_creation_with_details(git_project: Path):
    create_baseline(git_project, "SRR", "first", user="alice")
    EditService(git_project, user="a").update_item("SYS-0001", attrs={"owner": "z"}, why="x")
    create_baseline(git_project, "PDR", "second", user="bob")
    found = list_baselines(git_project)
    assert [b.name for b in found] == ["SRR", "PDR"]  # creation order, not alphabetical
    assert found[1].created_by == "bob" and found[1].description == "second" and found[1].commit != found[0].commit


def test_approved_items_are_promoted_to_baselined_and_recorded(git_project: Path):
    _approve(git_project, "SYS-0001")
    b = create_baseline(git_project, "PDR", "d", user="alice")
    proj = DoorstopProject.open(git_project)
    assert (
        proj.get_item("SYS-0001").attrs["status"] == "baselined"
        and proj.get_item("SYS-0002").attrs["status"] == "draft"
    )
    entry = read_history(git_project, "SYS-0001")[-1]
    assert entry["action"] == "baseline" and entry["fields"] == ["status"] and "PDR" in entry["why"]
    committed = GitRepo.discover(git_project).read_tree(b.commit, git_project)
    assert b"status: baselined" in committed["SYS/SYS-0001.yml"]  # the baseline contains the promoted state


def test_baselined_items_need_a_reason_for_every_edit(git_project: Path):
    create_baseline(git_project, "PDR", "d", user="alice")
    assert "SYS-0001" in baselined_uids(git_project)
    svc = EditService(git_project, user="bob")
    with pytest.raises(ReasonRequiredError, match="baseline"):
        svc.update_item("SYS-0001", attrs={"owner": "x"}, why="")
    svc.update_item("SYS-0001", attrs={"owner": "x"}, why="customer request")
    # an item created after the baseline is not baselined
    new = svc.create_item(
        "EPS", "The EPS shall be new.", attrs={"title": "N", "type": "functional"}, parents=["SYS-0001"]
    )
    svc.update_item(new.uid, attrs={"owner": "free"}, why="")


def test_open_change_requests_block_a_baseline_until_deferred(git_project: Path):
    cfg, _ = load_project_config(git_project)
    store = ChangeRequestStore(git_project, cfg)
    a = store.create("Open one", "", "alice", [])
    b = store.create("Open two", "", "alice", [])
    store.set_status(b.id, "closed", "alice", "")
    with pytest.raises(OpenChangeRequestsError) as exc:
        create_baseline(git_project, "PDR", "d", user="alice")
    assert [c.id for c in exc.value.open_requests] == [a.id] and a.id in str(exc.value)
    assert not (git_project / "baselines").exists()  # nothing was written
    with pytest.raises(BaselineError, match="reason"):
        create_baseline(git_project, "PDR", "d", user="alice", defer={a.id: ""})
    result = create_baseline(git_project, "PDR", "d", user="alice", defer={a.id: "after PDR"})
    assert result.deferred == (a.id,) and store.get(a.id).status == "deferred"
    manifest = yaml.safe_load((git_project / "baselines" / "PDR.yaml").read_text())
    assert manifest["deferred_change_requests"] == [a.id]
    # a deferred request no longer blocks the next baseline
    assert create_baseline(git_project, "CDR", "d", user="alice").name == "CDR"


def test_deferring_something_that_is_not_open_is_an_error(git_project: Path):
    with pytest.raises(BaselineError, match="CR-0042"):
        create_baseline(git_project, "PDR", "d", user="a", defer={"CR-0042": "x"})


def test_verify_detects_a_modified_manifest_and_a_tampered_tree(git_project: Path):
    create_baseline(git_project, "PDR", "d", user="alice")
    assert verify_baseline(git_project, "PDR") == []
    path = git_project / "baselines" / "PDR.yaml"
    path.write_text(path.read_text().replace("name: PDR", "name: PDR-edited"))
    findings = verify_baseline(git_project, "PDR")
    assert [f.code for f in findings] == ["RVS-BASELINE-MODIFIED"] and "PDR" in findings[0].message
    codes = {f.code for f in validate_project(git_project, doorstop=False).findings}
    assert "RVS-BASELINE-MODIFIED" in codes  # validate reports it too


def test_verify_unknown_baseline(git_project: Path):
    with pytest.raises(BaselineError, match="NOPE"):
        verify_baseline(git_project, "NOPE")


def test_validate_does_not_complain_about_baselines_normally(git_project: Path):
    create_baseline(git_project, "PDR", "d", user="alice")
    report = validate_project(git_project, doorstop=False)
    assert report.exit_code == 0, [f.format() for f in report.findings]


def test_manifest_digest_matches_the_tag_message(git_project: Path):
    b = create_baseline(git_project, "PDR", "d", user="alice")
    tag = GitRepo.discover(git_project).tag("rvs/baseline/PDR")
    assert tag is not None
    digest = hashlib.sha256((git_project / "baselines" / "PDR.yaml").read_bytes()).hexdigest()
    assert digest in tag.message and b.manifest_sha256 == digest


def test_project_path_with_spaces_and_dot_folders_still_gets_a_valid_tag(tmp_path: Path):
    from rvs_core.examples.minimal import build_minimal_project

    repo_root = tmp_path / "repo"
    GitRepo.init(repo_root)
    proj = repo_root / ".hidden dir" / "my project (v2)"
    build_minimal_project(proj)
    b = create_baseline(proj, "PDR", "d", user="a")
    assert b.tag == "rvs/baseline/hidden_dir/my_project__v2_/PDR"
    assert GitRepo.discover(proj).tag(b.tag) is not None and verify_baseline(proj, "PDR") == []
