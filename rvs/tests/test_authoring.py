import json
from pathlib import Path

import pytest

from rvs_core.authoring import EditService, ReasonRequiredError, history_path, read_history


def test_update_records_who_when_why_and_changed_fields(minimal_project: Path):
    svc = EditService(minimal_project, user="alice")
    svc.update_item("SYS-0001", text="The spacecraft shall provide power.", attrs={"owner": "power"}, why="clarify")
    (entry,) = read_history(minimal_project, "SYS-0001")
    assert entry["who"] == "alice" and entry["why"] == "clarify"
    assert entry["when"].startswith("20") and "T" in entry["when"]
    assert entry["fields"] == ["owner", "text"]
    assert entry["action"] == "update"
    assert "provide power" not in json.dumps(entry)  # names only, never content


def test_history_is_append_only_per_item_file(minimal_project: Path):
    svc = EditService(minimal_project, user="alice")
    svc.update_item("SYS-0001", attrs={"owner": "a"}, why="one")
    svc.update_item("SYS-0001", attrs={"owner": "b"}, why="two")
    svc.update_item("SYS-0002", attrs={"owner": "b"}, why="other item")
    assert [e["why"] for e in read_history(minimal_project, "SYS-0001")] == ["one", "two"]
    assert history_path(minimal_project, "SYS-0001").parent == history_path(minimal_project, "SYS-0002").parent
    assert history_path(minimal_project, "SYS-0001") != history_path(minimal_project, "SYS-0002")


def test_reason_is_mandatory_for_baselined_items(minimal_project: Path):
    svc = EditService(minimal_project, user="alice")
    svc.update_item("SYS-0001", attrs={"status": "baselined"}, why="")
    with pytest.raises(ReasonRequiredError, match="SYS-0001"):
        svc.update_item("SYS-0001", attrs={"owner": "x"}, why="  ")
    assert read_history(minimal_project, "SYS-0001")[-1]["fields"] == ["status"]
    svc.update_item("SYS-0001", attrs={"owner": "x"}, why="customer request")


def test_failed_edit_leaves_item_untouched(minimal_project: Path):
    svc = EditService(minimal_project, user="alice")
    svc.update_item("SYS-0001", attrs={"status": "baselined"}, why="")
    before = (minimal_project / "SYS" / "SYS-0001.yml").read_bytes()
    with pytest.raises(ReasonRequiredError):
        svc.update_item("SYS-0001", text="The spacecraft shall do something else.", why="")
    assert (minimal_project / "SYS" / "SYS-0001.yml").read_bytes() == before


def test_create_item_sets_defaults_and_records_history(minimal_project: Path):
    svc = EditService(minimal_project, user="bob")
    item = svc.create_item(
        "EPS",
        "The EPS shall do a thing.",
        attrs={"title": "Thing", "type": "functional"},
        parents=["SYS-0001"],
        why="new need",
    )
    assert item.uid == "EPS-0004" and item.attrs["status"] == "draft" and item.links == ("SYS-0001",)
    (entry,) = read_history(minimal_project, "EPS-0004")
    assert entry["action"] == "create" and entry["who"] == "bob"


def test_parent_must_exist_and_be_in_the_parent_document(minimal_project: Path):
    svc = EditService(minimal_project, user="bob")
    with pytest.raises(ValueError, match="SYS-0099"):
        svc.create_item("EPS", "The EPS shall x.", attrs={"title": "x"}, parents=["SYS-0099"])
    with pytest.raises(ValueError, match="parent document"):
        svc.create_item("EPS", "The EPS shall x.", attrs={"title": "x"}, parents=["VER-0001"])


def test_set_parents_replaces_links(minimal_project: Path):
    svc = EditService(minimal_project, user="bob")
    svc.set_parents("EPS-0001", ["SYS-0001"], why="re-allocated")
    from rvs_core.adapter import DoorstopProject

    assert DoorstopProject.open(minimal_project).get_item("EPS-0001").links == ("SYS-0001",)


def test_who_defaults_to_os_user(minimal_project: Path):
    svc = EditService(minimal_project)
    svc.update_item("SYS-0001", attrs={"owner": "z"}, why="x")
    assert read_history(minimal_project, "SYS-0001")[0]["who"]


def test_history_files_do_not_break_validation(minimal_project: Path):
    from rvs_core.validate import validate_project

    EditService(minimal_project, user="a").update_item("SYS-0001", attrs={"owner": "z"}, why="x")
    assert validate_project(minimal_project).exit_code == 0
