"""Regressions for defects found in exporters, importers and the CLI by the review pass."""

import io
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from openpyxl import Workbook

from rvs_cli.main import main
from rvs_core import csvsafe
from rvs_core.adapter import DoorstopProject
from rvs_core.authoring import EditService
from rvs_core.changecontrol.baselines import create_baseline
from rvs_core.config import load_project_config
from rvs_core.exporters.itemsio import (
    apply_import,
    export_items_csv,
    export_items_xlsx,
    plan_import,
    read_csv,
    read_xlsx,
)
from rvs_core.exporters.reqif import export_reqif, read_reqif
from rvs_core.matrices import Provenance

PROV = Provenance("0.1.0", "3.2", "P", "working copy", datetime(2026, 1, 2, 3, 4, 5), "alice")


def _plan(root: Path, rows: list[dict[str, str]], **kw):  # type: ignore[no-untyped-def]
    cfg, _ = load_project_config(root)
    return plan_import(cfg, DoorstopProject.open(root).items(), rows, root=root, **kw)


def _row(n: int = 1, **fields: str) -> dict[str, str]:
    return {"_row": str(n), **fields}


# import planning --------------------------------------------------------------------------------------------------------------
def test_a_baselined_item_without_a_reason_is_a_plan_error_and_nothing_is_written(git_project: Path):
    create_baseline(git_project, "B1", "first", user="a")
    before = (git_project / "SYS" / "SYS-0003.yml").read_bytes()
    rows = [
        _row(2, id="SYS-0100", title="New", text="The x shall y.", type="functional"),
        _row(3, id="SYS-0003", text="The spacecraft shall differ."),
    ]
    plan = _plan(git_project, rows)
    assert [r.action for r in plan.results] == ["create", "error"] and "baseline" in plan.results[1].message
    report = apply_import(git_project, plan, user="a", why="")
    assert report.applied is False and not (git_project / "SYS" / "SYS-0100.yml").exists()
    assert (git_project / "SYS" / "SYS-0003.yml").read_bytes() == before
    with_reason = _plan(git_project, rows, why="customer change")
    assert not with_reason.errors


def test_ids_must_be_written_in_full_and_new_ids_must_be_above_the_highest(minimal_project: Path):
    plan = _plan(minimal_project, [_row(2, id="SYS-2", title="x"), _row(3, id="SYS-0002", title="Power renamed")])
    assert plan.results[0].action == "error" and "SYS-0002" in plan.results[0].message
    assert plan.results[1].action == "update"
    high = _plan(minimal_project, [_row(2, id="SYS-0010", text="The x shall y.", title="t", type="functional")])
    assert high.results[0].action == "create"
    report = apply_import(minimal_project, high, user="a", why="")
    assert report.created_uids == ("SYS-0010",)
    low = _plan(minimal_project, [_row(2, id="SYS-0007", text="The x shall y.", title="t", type="functional")])
    assert low.results[0].action == "error" and "not above the highest" in low.results[0].message


def test_skip_errors_never_creates_a_child_of_a_rejected_parent(minimal_project: Path):
    rows = [
        _row(2, id="SYS-0100", text="The x shall y.", title="t", type="functional", status="nonsense"),
        _row(3, id="EPS-0100", text="The y shall z.", title="u", type="functional", parents="SYS-0100"),
    ]
    plan = _plan(minimal_project, rows)
    assert [r.action for r in plan.results] == ["error", "error"]
    report = apply_import(minimal_project, plan, user="a", why="", skip_errors=True)
    assert report.created == 0 and not (minimal_project / "EPS" / "EPS-0100.yml").exists()


def test_each_row_is_planned_with_its_own_columns(minimal_project: Path):
    rows = [
        _row(2, id="SYS-0001", text="The spacecraft shall be changed.", title="One"),
        {"_row": "2", "_sheet": "EPS", "id": "EPS-0001", "title": "Only a title"},
    ]
    plan = _plan(minimal_project, rows)
    assert sorted(plan.results[1].changes) == ["title"]  # the missing text column does not blank the statement


def test_control_characters_in_an_import_are_a_row_error(minimal_project: Path):
    plan = _plan(minimal_project, [_row(2, id="SYS-0001", text="The spacecraft shall\x0bbreak.")])
    assert plan.results[0].action == "error" and "control character" in plan.results[0].message


def test_dates_must_exist(minimal_project: Path):
    plan = _plan(
        minimal_project,
        [_row(2, id="VER-0001", executed_on="2026-13-45"), _row(3, id="VER-0002", executed_on="2026-02-03")],
    )
    assert plan.results[0].action == "error" and plan.results[1].action == "update"


def test_string_lists_with_commas_and_semicolons_round_trip(minimal_project: Path):
    DoorstopProject.open(minimal_project).update_item(
        "VER-0002", attrs={"nonconformances": ["NCR-1, rev A", "NCR-2; open", "plain\\back"]}
    )
    cfg, _ = load_project_config(minimal_project)
    rows = read_csv(export_items_csv(cfg, DoorstopProject.open(minimal_project).items(), PROV))
    plan = _plan(minimal_project, rows)
    assert not plan.errors and {r.action for r in plan.results} == {"unchanged"}


# files ---------------------------------------------------------------------------------------------------------------------------
def test_csv_cells_that_excel_would_run_are_protected_and_still_round_trip(minimal_project: Path):
    tricky = ["=cmd|' /C calc'!A0", "+1", "-1 item", "@SUM(1)", "'=quoted", "''-x", "plain"]
    for value in tricky:
        assert csvsafe.unprotect(csvsafe.protect(value)) == value, value
        assert not csvsafe.protect(value).startswith(("=", "+", "-", "@"))
    DoorstopProject.open(minimal_project).update_item("SYS-0001", attrs={"title": '=HYPERLINK("http://evil","x")'})
    cfg, _ = load_project_config(minimal_project)
    data = export_items_csv(cfg, DoorstopProject.open(minimal_project).items(), PROV)
    assert b",=HYPERLINK" not in data and b"'=HYPERLINK" in data
    plan = _plan(minimal_project, read_csv(data))
    assert {r.action for r in plan.results} == {"unchanged"}


def test_matrix_csv_is_protected_too(minimal_project: Path):
    from rvs_core.exporters.export_request import ExportRequest, build_output
    from rvs_core.validate import validate_project

    DoorstopProject.open(minimal_project).update_item("SYS-0001", attrs={"title": "=1+1"})
    report = validate_project(minimal_project, doorstop=False)
    data = build_output(ExportRequest("vcm", "csv"), report.config, report.items, report.graph, PROV)  # type: ignore[arg-type]
    assert b",=1+1" not in data and b"'=1+1" in data


def test_a_row_with_too_many_cells_is_reported():
    rows = read_csv(b"id,title\nSYS-0002,Eclipse, operation\nSYS-0003,ok\n")
    assert "more cell" in rows[0]["_error"] and "_error" not in rows[1]


def test_a_huge_field_is_readable_again():
    big = "x" * 300_000
    rows = read_csv(f'id,text\nSYS-0001,"{big}"\n'.encode())
    assert len(rows[0]["text"]) == 300_000


def test_xlsx_refuses_cells_it_cannot_hold_instead_of_cutting_them(minimal_project: Path):
    DoorstopProject.open(minimal_project).update_item("SYS-0001", text="The spacecraft shall " + "word " * 10_000 + ".")
    cfg, _ = load_project_config(minimal_project)
    with pytest.raises(ValueError, match="32,767"):
        export_items_xlsx(cfg, DoorstopProject.open(minimal_project).items(), PROV)


def test_a_sparse_workbook_is_read_quickly_and_a_non_workbook_is_refused():
    wb = Workbook()
    ws = wb.active
    ws.append(["id", "title"])
    ws.append(["SYS-0001", "x"])
    ws["XFD1048576"] = "far away"
    buf = io.BytesIO()
    wb.save(buf)
    rows = read_xlsx(buf.getvalue())
    assert rows[0]["id"] == "SYS-0001" and len(rows) <= 2
    with pytest.raises(ValueError, match="not an Excel"):
        read_xlsx(b"PK nope")


def test_xlsx_with_control_characters_still_exports(minimal_project: Path):
    path = minimal_project / "SYS" / "SYS-0001.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["text"] = "The spacecraft shall\x0b stay.\n"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    assert export_items_xlsx(cfg, items, PROV)[:2] == b"PK"


# ReqIF --------------------------------------------------------------------------------------------------------------------------------
def test_reqif_with_control_characters_stays_well_formed_and_readable(minimal_project: Path):
    import xml.etree.ElementTree as ET

    path = minimal_project / "SYS" / "SYS-0001.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["text"] = "The spacecraft shall\x0b stay.\n"
    data["title"] = "T\x0c"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    xml = export_reqif(cfg, items, PROV)
    ET.fromstring(xml)  # noqa: S314
    assert read_reqif(xml, cfg, items).rows


def test_a_partial_reqif_export_does_not_clear_links_on_reimport(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    partial = export_reqif(cfg, items, PROV, ("EPS",))
    plan = plan_import(cfg, items, read_reqif(partial, cfg, items).rows)
    assert not plan.errors and {r.action for r in plan.results} == {"unchanged"}


def test_utf16_doctype_is_refused(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    xml = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY a "aaaa">]><REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"/>'
    with pytest.raises(ValueError, match="DOCTYPE"):
        read_reqif(xml.encode("utf-16"), cfg, [], document="SYS")


def test_script_links_in_statements_do_not_reach_other_tools(minimal_project: Path):
    DoorstopProject.open(minimal_project).update_item(
        "SYS-0001", text="The spacecraft shall obey [click](javascript:alert(1)) and [docs](https://example.org/a)."
    )
    cfg, _ = load_project_config(minimal_project)
    xml = export_reqif(cfg, DoorstopProject.open(minimal_project).items(), PROV).decode()
    import xml.etree.ElementTree as ET

    links = [a.get("href") for a in ET.fromstring(xml).iter("{http://www.w3.org/1999/xhtml}a")]  # noqa: S314
    assert links == [None, "https://example.org/a"]  # the script link lost its target; the lossless Markdown copy stays


def test_very_deep_hierarchies_are_refused_with_a_message(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    depth = 150
    nodes = (
        "".join(
            f'<SPEC-HIERARCHY IDENTIFIER="h{i}"><OBJECT><SPEC-OBJECT-REF>o</SPEC-OBJECT-REF></OBJECT><CHILDREN>'
            for i in range(depth)
        )
        + "</CHILDREN></SPEC-HIERARCHY>" * depth
    )
    xml = f'<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"><CORE-CONTENT><REQ-IF-CONTENT><SPEC-OBJECTS><SPEC-OBJECT IDENTIFIER="o"/></SPEC-OBJECTS><SPECIFICATIONS><SPECIFICATION IDENTIFIER="s" LONG-NAME="SYS"><CHILDREN>{nodes}</CHILDREN></SPECIFICATION></SPECIFICATIONS></REQ-IF-CONTENT></CORE-CONTENT></REQ-IF>'
    with pytest.raises(ValueError, match="nested"):
        read_reqif(xml.encode(), cfg, [])


# documents ------------------------------------------------------------------------------------------------------------------------------
def test_pdf_matrix_with_a_page_tall_cell_still_exports(minimal_project: Path):
    from rvs_core.exporters.export_request import ExportRequest, build_output
    from rvs_core.validate import validate_project

    DoorstopProject.open(minimal_project).update_item("SYS-0001", attrs={"title": "word " * 700})
    report = validate_project(minimal_project, doorstop=False)
    data = build_output(ExportRequest("vcm", "pdf"), report.config, report.items, report.graph, PROV)  # type: ignore[arg-type]
    assert data.startswith(b"%PDF")


def test_literal_asterisks_in_statements_survive_markdown_lite():
    from rvs_core.exporters.mdlite import inline

    spans = inline("The tool shall read *.txt and *.csv files, and *emphasis* works.")
    assert "".join(t for t, _s in spans).count("*") == 2 and ("emphasis", "i") in spans


# CLI -----------------------------------------------------------------------------------------------------------------------------------
def test_cli_reports_unwritable_output_and_unknown_documents_as_messages(minimal_project: Path, tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    assert main(["export", str(minimal_project), "--vcm", "-o", str(tmp_path / "missing" / "x.csv")]) == 2
    assert "rvs:" in capsys.readouterr().err
    assert main(["export", str(minimal_project), "--vcm", "--document", "NOPE"]) == 2
    assert main(["export", str(minimal_project), "--reqif", "--document", "NOPE"]) == 2
    assert main(["export", str(minimal_project), "--vcm", "-o", str(tmp_path)]) == 2  # a directory
    capsys.readouterr()
    assert main(["guide", "-o", str(tmp_path / "no" / "dir" / "g.html")]) == 2


def test_cli_import_failures_are_messages_not_tracebacks(git_project: Path, tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    create_baseline(git_project, "B1", "first", user="a")
    csv_file = tmp_path / "t.csv"
    csv_file.write_text("id,text\nSYS-0003,The spacecraft shall differ.\n", encoding="utf-8")
    assert main(["import", str(git_project), str(csv_file), "--dry-run"]) == 1  # a plan error, like any other
    assert "baseline" in capsys.readouterr().out
    assert main(["import", str(git_project), str(csv_file), "--reason", "customer change"]) == 0
    reqif = tmp_path / "x.reqif"
    assert main(["export", str(git_project), "--reqif", "-o", str(reqif)]) == 0
    assert main(["import", str(git_project), str(reqif), "--map", "nonsense"]) == 2


def test_init_refuses_to_nest_a_project_inside_a_project(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    assert main(["init", str(minimal_project / "sub"), "--name", "X"]) == 2
    assert "already an RVS project" in capsys.readouterr().err
    assert not (minimal_project / "sub").exists()
    existing_file = minimal_project.parent / "afile"
    existing_file.write_text("x")
    assert main(["init", str(existing_file), "--name", "X"]) == 2


def test_stdout_text_survives_a_legacy_console_encoding(minimal_project: Path, monkeypatch, capfdbinary):  # type: ignore[no-untyped-def]
    assert main(["export", str(minimal_project), "--items"]) == 0
    out = capfdbinary.readouterr().out
    assert out.startswith(b"\xef\xbb\xbf")  # the UTF-8 BOM arrives intact, whatever the console encoding is
    assert EditService  # imported for the flows above
