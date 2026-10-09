import tempfile
from pathlib import Path

import pytest

from rvs_core.adapter import DoorstopProject, ProjectError

FINGERPRINT = ["title", "type", "verify_method", "verify_level"]


def _make(root: Path) -> DoorstopProject:
    proj = DoorstopProject.create(root)
    proj.create_document("SYS", defaults={"status": "draft"}, fingerprint=FINGERPRINT)
    proj.create_document("EPS", parent="SYS", defaults={"status": "draft"}, fingerprint=FINGERPRINT)
    return proj


def test_create_and_reopen_documents(tmp_path: Path):
    _make(tmp_path / "p")
    proj = DoorstopProject.open(tmp_path / "p")
    docs = {d.prefix: d for d in proj.documents()}
    assert set(docs) == {"SYS", "EPS"}
    assert docs["EPS"].parent == "SYS" and docs["SYS"].parent is None
    assert docs["SYS"].sep == "-" and docs["SYS"].digits == 4
    assert docs["SYS"].fingerprint == tuple(sorted(FINGERPRINT))
    assert docs["SYS"].defaults == {"status": "draft"}


def test_extended_attributes_round_trip(tmp_path: Path):
    proj = _make(tmp_path / "p")
    item = proj.add_item(
        "SYS", "The system shall do X.", attrs={"title": "X", "type": "functional", "rvs_schema_version": 1}
    )
    again = DoorstopProject.open(tmp_path / "p").get_item(item.uid)
    assert again.text.strip() == "The system shall do X."
    assert again.attrs["title"] == "X" and again.attrs["status"] == "draft"  # default applied
    assert again.attrs["rvs_schema_version"] == 1
    assert item.uid == "SYS-0001"


def test_status_change_does_not_make_links_suspect_but_fingerprint_attr_does(tmp_path: Path):
    proj = _make(tmp_path / "p")
    parent = proj.add_item("SYS", "Parent shall X.", attrs={"title": "P", "type": "functional"})
    child = proj.add_item("EPS", "Child shall Y.", attrs={"title": "C"})
    proj.link(child.uid, parent.uid)
    assert proj.suspect_links(child.uid) == ()

    proj.update_item(parent.uid, attrs={"status": "approved"})
    assert proj.suspect_links(child.uid) == ()

    proj.update_item(parent.uid, attrs={"title": "P changed"})
    assert proj.suspect_links(child.uid) == (parent.uid,)

    proj.clear_suspect(child.uid)
    assert proj.suspect_links(child.uid) == ()


def test_review_uses_doorstop_review_api(tmp_path: Path):
    proj = _make(tmp_path / "p")
    it = proj.add_item("SYS", "Shall.", attrs={"title": "T"})
    assert it.reviewed is False
    proj.review_item(it.uid)
    assert proj.get_item(it.uid).reviewed is True
    proj.update_item(it.uid, text="Changed shall.")
    assert proj.get_item(it.uid).reviewed is False


def test_items_sorted_deterministically(tmp_path: Path):
    proj = _make(tmp_path / "p")
    for n in range(12):
        proj.add_item("SYS", f"Req {n} shall.", attrs={"title": str(n)})
    uids = [i.uid for i in proj.items("SYS")]
    assert uids == sorted(uids)


def test_unknown_item_and_document_raise_project_error(tmp_path: Path):
    proj = _make(tmp_path / "p")
    with pytest.raises(ProjectError, match="SYS-9999"):
        proj.get_item("SYS-9999")
    with pytest.raises(ProjectError, match="NOPE"):
        proj.add_item("NOPE", "x")


def test_open_missing_folder_is_a_project_error(tmp_path: Path):
    with pytest.raises(ProjectError, match="does not exist"):
        DoorstopProject.open(tmp_path / "nope")


def test_no_temp_files_used_outside_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def boom(*a: object, **k: object) -> None:
        raise AssertionError("temp file used")

    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile", "TemporaryDirectory"):
        monkeypatch.setattr(tempfile, name, boom)
    proj = _make(tmp_path / "p")
    proj.add_item("SYS", "Shall.", attrs={"title": "T"})
    list(DoorstopProject.open(tmp_path / "p").issues())


def test_doorstop_issues_are_returned_as_data(tmp_path: Path):
    proj = _make(tmp_path / "p")
    parent = proj.add_item("SYS", "Parent shall.", attrs={"title": "P"})
    child = proj.add_item("EPS", "Child shall.", attrs={"title": "C"})
    proj.link(child.uid, parent.uid)
    proj.update_item(parent.uid, attrs={"title": "changed"})
    issues = list(proj.issues())
    assert any(i.level == "warning" and child.uid in i.message and "suspect" in i.message.lower() for i in issues)


def test_item_and_document_hooks_are_called(tmp_path: Path):
    proj = _make(tmp_path / "p")
    proj.add_item("SYS", "Shall.", attrs={"title": "T"})
    seen_items: list[str] = []
    seen_docs: list[str] = []
    list(
        proj.issues(
            item_check=lambda it, doc: seen_items.append(it.uid) or [],
            doc_check=lambda d: seen_docs.append(d.prefix) or [],
        )
    )
    assert seen_items == ["SYS-0001"] and sorted(seen_docs) == ["EPS", "SYS"]
