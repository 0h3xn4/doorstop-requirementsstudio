"""CSV/XLSX item import and export: unchanged round trip, planning, errors, history, fresh-project creation."""

import io
from datetime import datetime
from pathlib import Path

import pytest

from rvs_core.adapter import DoorstopProject
from rvs_core.authoring import read_history
from rvs_core.config import load_project_config
from rvs_core.exporters.itemsio import (
    apply_import,
    export_items_csv,
    export_items_xlsx,
    item_columns,
    plan_import,
    read_csv,
    read_xlsx,
)
from rvs_core.matrices import Provenance

PROV = Provenance("0.1.0", "3.2", "Minimal example", "working copy", datetime(2026, 1, 2, 3, 4, 5), "alice")


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".rvs-cache" not in p.parts and "history" not in p.parts
    }


def _export_csv(root: Path) -> bytes:
    cfg, _ = load_project_config(root)
    return export_items_csv(cfg, DoorstopProject.open(root).items(), PROV)


def _plan(root: Path, rows: list[dict[str, str]], why: str = ""):  # type: ignore[no-untyped-def]
    cfg, _ = load_project_config(root)
    return plan_import(cfg, DoorstopProject.open(root).items(), rows, why=why)


def _csv_with(root: Path, edit) -> list[dict[str, str]]:  # type: ignore[no-untyped-def]
    rows = read_csv(_export_csv(root))
    edit(rows)
    return rows


def _row(rows: list[dict[str, str]], uid: str) -> dict[str, str]:
    return next(r for r in rows if r["id"] == uid)


# export -----------------------------------------------------------------------------------------
def test_columns_cover_core_fields_and_attributes(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    cols = item_columns(cfg)
    assert cols[:10] == [
        "id",
        "document",
        "level",
        "normative",
        "derived",
        "active",
        "header",
        "ref",
        "text",
        "parents",
    ]
    assert {
        "title",
        "type",
        "status",
        "verify_method",
        "link_satisfies",
        "link_verifies",
        "v_status",
        "proc_id",
    } <= set(cols)
    assert "rvs_schema_version" not in cols and len(cols) == len(set(cols))


def test_csv_export_has_provenance_comments_bom_and_all_items(minimal_project: Path):
    data = _export_csv(minimal_project)
    assert data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8-sig")
    assert text.startswith("# ") and "Project: Minimal example" in text
    rows = read_csv(data)
    assert [r["id"] for r in rows][:4] == ["SYS-0004", "SYS-0001", "SYS-0002", "SYS-0003"] and len(
        rows
    ) == 10  # document order
    assert _row(rows, "EPS-0001")["parents"] == "SYS-0002" and _row(rows, "SYS-0004")["normative"] == "no"


def test_xlsx_export_has_a_sheet_per_document(minimal_project: Path):
    from openpyxl import load_workbook

    cfg, _ = load_project_config(minimal_project)
    data = export_items_xlsx(cfg, DoorstopProject.open(minimal_project).items(), PROV)
    wb = load_workbook(io.BytesIO(data))
    assert wb.sheetnames == ["SYS", "EPS", "VER", "Provenance"]
    assert [c.value for c in wb["EPS"][1]][0] == "id" and wb["EPS"].max_row == 4


# unchanged round trip -------------------------------------------------------------------------------
def test_unchanged_csv_round_trip_changes_nothing(minimal_project: Path):
    before = _snapshot(minimal_project)
    plan = _plan(minimal_project, read_csv(_export_csv(minimal_project)))
    assert {r.action for r in plan.results} == {"unchanged"} and not plan.errors
    apply_import(minimal_project, plan, user="alice", why="re-import")
    assert _snapshot(minimal_project) == before


def test_unchanged_xlsx_round_trip_changes_nothing(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    data = export_items_xlsx(cfg, DoorstopProject.open(minimal_project).items(), PROV)
    before = _snapshot(minimal_project)
    plan = _plan(minimal_project, read_xlsx(data))
    assert {r.action for r in plan.results} == {"unchanged"}
    apply_import(minimal_project, plan, user="alice", why="")
    assert _snapshot(minimal_project) == before


def test_comments_crlf_and_excel_style_numbers_are_tolerated(minimal_project: Path):
    text = _export_csv(minimal_project).decode("utf-8-sig").replace("\n", "\r\n").encode("utf-8")
    plan = _plan(minimal_project, read_csv(text))
    assert {r.action for r in plan.results} == {"unchanged"}


# updates --------------------------------------------------------------------------------------------------
def test_changed_cell_updates_only_that_item_and_field(minimal_project: Path):
    rows = _csv_with(minimal_project, lambda rs: _row(rs, "SYS-0002").update(title="Eclipse operation (rev)"))
    plan = _plan(minimal_project, rows)
    changed = [r for r in plan.results if r.action != "unchanged"]
    assert [(r.uid, r.action, r.changes) for r in changed] == [("SYS-0002", "update", ("title",))]
    before = _snapshot(minimal_project)
    report = apply_import(minimal_project, plan, user="alice", why="rename")
    assert (report.created, report.updated, report.unchanged) == (0, 1, 9)
    after = _snapshot(minimal_project)
    assert [k.replace("\\", "/") for k in after if after[k] != before.get(k)] == ["SYS/SYS-0002.yml"]
    assert DoorstopProject.open(minimal_project).get_item("SYS-0002").attrs["title"] == "Eclipse operation (rev)"
    entry = read_history(minimal_project, "SYS-0002")[-1]
    assert entry["action"] == "import" and entry["why"] == "rename" and entry["fields"] == ["title"]


def test_subset_of_columns_only_touches_those_columns(minimal_project: Path):
    csv = b"id,title\nSYS-0001,Only the title\n"
    plan = _plan(minimal_project, read_csv(csv))
    assert [(r.uid, r.changes) for r in plan.results] == [("SYS-0001", ("title",))]


def test_text_comparison_ignores_surrounding_whitespace_and_line_endings(minimal_project: Path):
    rows = _csv_with(
        minimal_project, lambda rs: _row(rs, "SYS-0001").update(text="  " + _row(rs, "SYS-0001")["text"] + "\r\n")
    )
    assert {r.action for r in _plan(minimal_project, rows).results} == {"unchanged"}


def test_blank_cell_clears_an_existing_value_on_update(minimal_project: Path):
    rows = _csv_with(minimal_project, lambda rs: _row(rs, "SYS-0001").update(owner=""))
    plan = _plan(minimal_project, rows)
    assert [(r.uid, r.changes) for r in plan.results if r.action == "update"] == [("SYS-0001", ("owner",))]
    apply_import(minimal_project, plan, user="a", why="")
    assert not DoorstopProject.open(minimal_project).get_item("SYS-0001").attrs["owner"]


def test_parents_typed_links_flags_and_level_are_imported(minimal_project: Path):
    def edit(rs: list[dict[str, str]]) -> None:
        r = _row(rs, "EPS-0001")
        r.update(parents="SYS-0001, SYS-0002", link_satisfies="SYS-0003", normative="no", level="1.5")

    plan = _plan(minimal_project, _csv_with(minimal_project, edit))
    (r,) = [x for x in plan.results if x.action == "update"]
    assert set(r.changes) == {"parents", "link_satisfies", "normative", "level"}
    apply_import(minimal_project, plan, user="a", why="")
    item = DoorstopProject.open(minimal_project).get_item("EPS-0001")
    assert item.links == ("SYS-0001", "SYS-0002") and item.attrs["link_satisfies"] == ["SYS-0003"]
    assert not item.normative and item.level == "1.5"


def test_changed_parents_are_not_suspect_after_import(minimal_project: Path):
    rows = _csv_with(minimal_project, lambda rs: _row(rs, "EPS-0001").update(parents="SYS-0001"))
    apply_import(minimal_project, _plan(minimal_project, rows), user="a", why="")
    assert DoorstopProject.open(minimal_project).suspect_links("EPS-0001") == ()


# creation ----------------------------------------------------------------------------------------------------
def test_new_rows_are_created_with_defaults(minimal_project: Path):
    rows = read_csv(
        b"id,document,title,text,type,parents\n,EPS,New thing,The EPS shall do a new thing.,functional,SYS-0001\n"
    )
    plan = _plan(minimal_project, rows)
    assert [(r.action, r.uid) for r in plan.results] == [("create", "")]
    report = apply_import(minimal_project, plan, user="bob", why="import")
    item = DoorstopProject.open(minimal_project).get_item("EPS-0004")
    assert report.created == 1 and item.attrs["status"] == "draft" and item.links == ("SYS-0001",)
    assert item.attrs["rvs_schema_version"] == 1
    assert read_history(minimal_project, "EPS-0004")[0]["action"] == "import"


def test_explicit_new_id_is_honoured_and_parents_may_point_at_new_rows(minimal_project: Path):
    csv = (
        b"id,document,title,text,type,parents\n"
        b"SYS-0010,SYS,New sys,The system shall exist.,functional,\n"
        b"EPS-0010,EPS,New eps,The EPS shall exist.,functional,SYS-0010\n"
    )
    plan = _plan(minimal_project, read_csv(csv))
    assert not plan.errors
    apply_import(minimal_project, plan, user="bob", why="")
    proj = DoorstopProject.open(minimal_project)
    assert proj.get_item("EPS-0010").links == ("SYS-0010",)


# errors ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("csv", "needle"),
    [
        ("id,document,title\n,NOPE,x\n", "NOPE"),
        ("id,title,bogus\nSYS-0001,x,1\n", "bogus"),
        ("id,status\nSYS-0001,finished\n", "finished"),
        ("id,parents\nEPS-0001,SYS-0099\n", "SYS-0099"),
        ("id,parents\nEPS-0001,VER-0001\n", "parent document"),
        ("id,parents\nSYS-0001,SYS-0002\n", "root document"),
        ("id,normative\nSYS-0001,maybe\n", "maybe"),
        ("id,level\nSYS-0001,one\n", "one"),
        ("id\nSYS-0001\nSYS-0001\n", "twice"),
        ("id,document\nEPS-0001,SYS\n", "belongs"),
        ("id,document,text\n,,x\n", "document"),
        ("id,link_satisfies\nEPS-0001,not-an-id\n", "not-an-id"),
        ("id,executed_on\nVER-0001,yesterday\n", "yesterday"),
    ],
)
def test_row_errors_are_reported_with_row_number_and_plain_language(minimal_project: Path, csv: str, needle: str):
    plan = _plan(minimal_project, read_csv(csv.encode()))
    errors = plan.errors
    assert errors and needle in errors[0].message and errors[0].row >= 1
    assert errors[0].action == "error"


def test_errors_abort_the_whole_import_unless_skipped(minimal_project: Path):
    rows = _csv_with(
        minimal_project,
        lambda rs: (_row(rs, "SYS-0001").update(title="Good"), _row(rs, "SYS-0002").update(status="finished")),
    )
    plan = _plan(minimal_project, rows)
    before = _snapshot(minimal_project)
    report = apply_import(minimal_project, plan, user="a", why="")
    assert report.applied is False and _snapshot(minimal_project) == before
    report = apply_import(minimal_project, plan, user="a", why="", skip_errors=True)
    assert report.applied and report.updated == 1 and report.errors == 1
    assert DoorstopProject.open(minimal_project).get_item("SYS-0001").attrs["title"] == "Good"


def test_baselined_items_need_a_reason(minimal_project: Path):
    DoorstopProject.open(minimal_project).update_item("SYS-0001", attrs={"status": "baselined"})
    rows = _csv_with(minimal_project, lambda rs: _row(rs, "SYS-0001").update(title="Changed"))
    plan = _plan(minimal_project, rows, why="")
    assert plan.errors and "reason" in plan.errors[0].message
    assert not _plan(minimal_project, rows, why="customer change").errors


def test_dry_run_is_just_planning(minimal_project: Path):
    before = _snapshot(minimal_project)
    _plan(minimal_project, _csv_with(minimal_project, lambda rs: _row(rs, "SYS-0001").update(title="X")))
    assert _snapshot(minimal_project) == before


# lossless into an empty project -------------------------------------------------------------------------------------
def test_export_then_import_into_a_fresh_project_reproduces_the_export(tmp_path: Path, minimal_project: Path):
    from rvs_core.examples.minimal import DOCS
    from rvs_core.project import create_project

    original = _export_csv(minimal_project)
    fresh = tmp_path / "fresh"
    create_project(fresh, "Minimal example", DOCS)
    plan = _plan(fresh, read_csv(original))
    assert not plan.errors, [e.message for e in plan.errors]
    apply_import(fresh, plan, user="alice", why="")

    def rows(data: bytes) -> list[dict[str, str]]:
        return read_csv(data)

    assert rows(_export_csv(fresh)) == rows(original)
