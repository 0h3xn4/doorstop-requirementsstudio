from pathlib import Path

import pytest
import yaml

from rvs_core.authoring import EditService, read_history
from rvs_core.changecontrol.changes import ChangeRequestError, ChangeRequestStore
from rvs_core.config import load_project_config
from rvs_core.validate import validate_project


def _store(root: Path) -> ChangeRequestStore:
    cfg, _ = load_project_config(root)
    return ChangeRequestStore(root, cfg)


def test_config_defines_statuses_and_which_block_a_baseline(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    assert "open" in cfg.changes.statuses and "deferred" in cfg.changes.statuses
    assert set(cfg.changes.open_statuses) <= set(cfg.changes.statuses) and "deferred" not in cfg.changes.open_statuses
    assert cfg.changes.promote == {"approved": "baselined"}


def test_create_assigns_sequential_ids_and_writes_a_deterministic_file(minimal_project: Path):
    store = _store(minimal_project)
    a = store.create("Change the bus", "Move to 28 V", "alice", ["EPS-0001"])
    b = store.create("Second", "", "bob", [])
    assert (a.id, b.id) == ("CR-0001", "CR-0002") and a.status == "open"
    text = (minimal_project / "changes" / "CR-0001.yaml").read_text()
    data = yaml.safe_load(text)
    assert data["rvs_schema_version"] == 1 and data["items"] == ["EPS-0001"] and data["raised_by"] == "alice"
    assert [r.id for r in store.list()] == ["CR-0001", "CR-0002"]


def test_status_change_is_logged_and_validated(minimal_project: Path):
    store = _store(minimal_project)
    cr = store.create("T", "", "alice", [])
    updated = store.set_status(cr.id, "in-review", "bob", "looks fine")
    assert updated.status == "in-review"
    assert (
        updated.log[-1]["who"] == "bob"
        and updated.log[-1]["status"] == "in-review"
        and updated.log[-1]["note"] == "looks fine"
    )
    with pytest.raises(ChangeRequestError, match="finished"):
        store.set_status(cr.id, "finished", "bob", "")
    with pytest.raises(ChangeRequestError, match="CR-0099"):
        store.get("CR-0099")


def test_deferral_needs_a_reason(minimal_project: Path):
    store = _store(minimal_project)
    cr = store.create("T", "", "alice", [])
    with pytest.raises(ChangeRequestError, match="reason"):
        store.defer(cr.id, "", "bob")
    assert store.defer(cr.id, "after PDR", "bob").status == "deferred"


def test_update_fields_and_items(minimal_project: Path):
    store = _store(minimal_project)
    cr = store.create("T", "d", "alice", ["SYS-0001"])
    updated = store.update(cr.id, title="New title", description="New", items=["SYS-0001", "SYS-0002"], who="bob")
    assert (updated.title, updated.description, updated.items) == ("New title", "New", ("SYS-0001", "SYS-0002"))


def test_open_change_requests(minimal_project: Path):
    store = _store(minimal_project)
    a, b = store.create("A", "", "x", []), store.create("B", "", "x", [])
    store.set_status(b.id, "closed", "x", "")
    assert [c.id for c in store.open_requests()] == [a.id]


def test_edits_can_be_attributed_to_a_change_request(minimal_project: Path):
    store = _store(minimal_project)
    cr = store.create("T", "", "alice", ["SYS-0001"])
    svc = EditService(minimal_project, user="alice", change_request=cr.id)
    svc.update_item("SYS-0002", attrs={"owner": "z"}, why="because")
    assert read_history(minimal_project, "SYS-0002")[-1]["cr"] == cr.id
    assert store.edited_items(cr.id) == ["SYS-0002"]


def test_edits_cannot_be_attributed_to_a_closed_or_unknown_change_request(minimal_project: Path):
    store = _store(minimal_project)
    cr = store.create("T", "", "alice", [])
    store.set_status(cr.id, "closed", "alice", "")
    with pytest.raises(ValueError, match="closed"):
        EditService(minimal_project, user="a", change_request=cr.id).update_item("SYS-0001", attrs={"owner": "x"})
    with pytest.raises(ValueError, match="CR-0099"):
        EditService(minimal_project, user="a", change_request="CR-0099")


def test_validate_reports_bad_status_and_unknown_items(minimal_project: Path):
    store = _store(minimal_project)
    cr = store.create("T", "", "alice", ["SYS-0099"])
    path = minimal_project / "changes" / f"{cr.id}.yaml"
    data = yaml.safe_load(path.read_text())
    data["status"] = "finished"
    path.write_text(yaml.safe_dump(data))
    codes = {f.code: f for f in validate_project(minimal_project, doorstop=False).findings}
    assert codes["RVS-CR-STATUS"].location == f"changes/{cr.id}.yaml" and "finished" in codes["RVS-CR-STATUS"].message
    assert "RVS-CR-ITEM" in codes and "SYS-0099" in codes["RVS-CR-ITEM"].message


def test_newer_change_request_schema_is_refused(minimal_project: Path):
    cr = _store(minimal_project).create("T", "", "alice", [])
    path = minimal_project / "changes" / f"{cr.id}.yaml"
    data = yaml.safe_load(path.read_text())
    data["rvs_schema_version"] = 9
    path.write_text(yaml.safe_dump(data))
    report = validate_project(minimal_project, doorstop=False)
    assert report.exit_code == 3 and "RVS-SCHEMA-NEWER" in {f.code for f in report.findings}


def test_change_request_files_do_not_disturb_validation(minimal_project: Path):
    _store(minimal_project).create("T", "", "alice", ["SYS-0001"])
    assert validate_project(minimal_project, doorstop=False).exit_code == 0
