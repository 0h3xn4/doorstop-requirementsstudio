"""ReqIF 1.x export and import: structure, determinism, lossless round trip, foreign files, safety."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import pytest

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.exporters.itemsio import apply_import, export_items_csv, plan_import, read_csv
from rvs_core.exporters.reqif import export_reqif, read_reqif
from rvs_core.matrices import Provenance

PROV = Provenance("0.1.0", "3.2", "Minimal example", "working copy", datetime(2026, 1, 2, 3, 4, 5), "alice")
NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
XHTML = "http://www.w3.org/1999/xhtml"
Q = f"{{{NS}}}"
NCNAME = re.compile(r"^[A-Za-z_][\w.\-]*$")


def _export(root: Path, documents: tuple[str, ...] = ()) -> bytes:
    cfg, _ = load_project_config(root)
    return export_reqif(cfg, DoorstopProject.open(root).items(), PROV, documents)


def _tree(data: bytes) -> ET.Element:
    return ET.fromstring(data)


# export structure ------------------------------------------------------------------------------------------------------
def test_export_is_a_well_formed_reqif_document(minimal_project: Path):
    data = _export(minimal_project)
    assert data.startswith(b"<?xml version='1.0' encoding='utf-8'?>")
    root = _tree(data)
    assert root.tag == Q + "REQ-IF"
    header = root.find(f"{Q}THE-HEADER/{Q}REQ-IF-HEADER")
    assert header is not None
    assert header.findtext(f"{Q}REQ-IF-VERSION") == "1.0"
    assert header.findtext(f"{Q}TITLE") == "Minimal example"
    assert header.findtext(f"{Q}CREATION-TIME") == "2026-01-02T03:04:05"
    content = root.find(f"{Q}CORE-CONTENT/{Q}REQ-IF-CONTENT")
    assert content is not None
    assert [c.tag for c in content] == [Q + t for t in ("DATATYPES", "SPEC-TYPES", "SPEC-OBJECTS", "SPEC-RELATIONS", "SPECIFICATIONS")]  # fmt: skip


def test_one_specification_per_document_and_one_object_per_item(minimal_project: Path):
    root = _tree(_export(minimal_project))
    specs = root.findall(f".//{Q}SPECIFICATION")
    assert [s.get("LONG-NAME") for s in specs] == ["SYS", "EPS", "VER"]
    objects = root.findall(f".//{Q}SPEC-OBJECT")
    assert len(objects) == 10
    foreign = {v.get("THE-VALUE") for v in root.iter(Q + "ATTRIBUTE-VALUE-STRING") if v.find(f"{Q}DEFINITION/{Q}ATTRIBUTE-DEFINITION-STRING-REF").text == "RVS-AD-ForeignID"}  # fmt: skip
    assert "SYS-0001" in foreign and "VER-0001" in foreign
    hierarchies = root.findall(f".//{Q}SPEC-HIERARCHY")
    assert len(hierarchies) == 10  # every item appears exactly once in a specification


def test_relations_carry_parent_and_typed_links(minimal_project: Path):
    root = _tree(_export(minimal_project))
    types = {t.get("IDENTIFIER"): t.get("LONG-NAME") for t in root.iter(Q + "SPEC-RELATION-TYPE")}
    assert set(types.values()) == {"parent", "satisfies", "verifies", "refines", "conflicts-with"}
    rel_types = [types[r.find(f"{Q}TYPE/{Q}SPEC-RELATION-TYPE-REF").text] for r in root.iter(Q + "SPEC-RELATION")]
    assert rel_types.count("parent") == 3  # the three EPS items link to SYS
    assert "verifies" in rel_types


def test_enumerations_use_the_project_vocabulary(minimal_project: Path):
    root = _tree(_export(minimal_project))
    enums = {e.get("LONG-NAME"): [v.get("LONG-NAME") for v in e.iter(Q + "ENUM-VALUE")] for e in root.iter(Q + "DATATYPE-DEFINITION-ENUMERATION")}  # fmt: skip
    assert enums["status"] == ["draft", "reviewed", "approved", "baselined", "obsolete"]


def test_statement_is_xhtml_and_lossless_markdown(minimal_project: Path):
    root = _tree(_export(minimal_project))
    divs = list(root.iter(f"{{{XHTML}}}div"))
    assert divs and any("shall" in "".join(d.itertext()) for d in divs)
    md = [v.get("THE-VALUE") for v in root.iter(Q + "ATTRIBUTE-VALUE-STRING") if v.find(f"{Q}DEFINITION/{Q}ATTRIBUTE-DEFINITION-STRING-REF").text == "RVS-AD-Markdown"]  # fmt: skip
    assert any("shall" in (m or "") for m in md)


def test_all_references_resolve_and_identifiers_are_unique_names(minimal_project: Path):
    root = _tree(_export(minimal_project))
    ids = [e.get("IDENTIFIER") for e in root.iter() if e.get("IDENTIFIER")]
    assert len(ids) == len(set(ids)) and all(NCNAME.match(i) for i in ids)
    refs = [e.text for e in root.iter() if e.tag.endswith("-REF")]
    assert refs and all(r in set(ids) for r in refs)
    assert all(
        e.get("LAST-CHANGE") == "2026-01-02T03:04:05"
        for e in root.iter()
        if e.get("IDENTIFIER") and not e.tag.endswith("HEADER")
    )


def test_export_is_deterministic(minimal_project: Path):
    assert _export(minimal_project) == _export(minimal_project)


def test_document_subset_drops_dangling_relations(minimal_project: Path):
    root = _tree(_export(minimal_project, ("EPS",)))
    assert [s.get("LONG-NAME") for s in root.iter(Q + "SPECIFICATION")] == ["EPS"]
    assert len(list(root.iter(Q + "SPEC-OBJECT"))) == 3
    assert not list(root.iter(Q + "SPEC-RELATION"))  # their parents are in SYS, which was not exported


# round trips -----------------------------------------------------------------------------------------------------------
def _csv_rows(root: Path) -> list[dict[str, str]]:
    cfg, _ = load_project_config(root)
    return read_csv(export_items_csv(cfg, DoorstopProject.open(root).items(), PROV))


def test_reimporting_an_export_changes_nothing(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    read = read_reqif(_export(minimal_project), cfg, items)
    plan = plan_import(cfg, items, read.rows)
    assert not plan.errors, [e.message for e in plan.errors]
    assert {r.action for r in plan.results} == {"unchanged"}


def test_export_then_import_into_a_fresh_project_reproduces_the_items(tmp_path: Path, minimal_project: Path):
    from rvs_core.examples.minimal import DOCS
    from rvs_core.project import create_project

    data = _export(minimal_project)
    fresh = tmp_path / "fresh"
    create_project(fresh, "Minimal example", DOCS)
    cfg, _ = load_project_config(fresh)
    read = read_reqif(data, cfg, DoorstopProject.open(fresh).items())
    plan = plan_import(cfg, DoorstopProject.open(fresh).items(), read.rows)
    assert not plan.errors, [e.message for e in plan.errors]
    apply_import(fresh, plan, user="alice", why="")
    assert _csv_rows(fresh) == _csv_rows(minimal_project)


def test_satellite_round_trip_is_lossless(tmp_path: Path):
    import shutil

    from conftest import EXAMPLES
    from rvs_core.project import create_project

    src = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "satellite300", src, ignore=shutil.ignore_patterns(".rvs-cache"))
    cfg, _ = load_project_config(src)
    data = _export(src)
    fresh = tmp_path / "fresh"
    create_project(fresh, cfg.project.name, cfg.project.documents)
    fcfg, _ = load_project_config(fresh)
    read = read_reqif(data, fcfg, [])
    plan = plan_import(fcfg, [], read.rows)
    assert not plan.errors, [e.message for e in plan.errors][:5]
    apply_import(fresh, plan, user="x", why="")
    assert _csv_rows(fresh) == _csv_rows(src)


# foreign files ----------------------------------------------------------------------------------------------------------
FOREIGN = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd" xmlns:xhtml="http://www.w3.org/1999/xhtml">
 <THE-HEADER><REQ-IF-HEADER IDENTIFIER="h"><CREATION-TIME>2020-01-01T00:00:00Z</CREATION-TIME><REQ-IF-VERSION>1.0</REQ-IF-VERSION><TITLE>Customer</TITLE></REQ-IF-HEADER></THE-HEADER>
 <CORE-CONTENT><REQ-IF-CONTENT>
  <DATATYPES>
   <DATATYPE-DEFINITION-STRING IDENTIFIER="dt-s" LONG-NAME="String" MAX-LENGTH="255"/>
   <DATATYPE-DEFINITION-XHTML IDENTIFIER="dt-x" LONG-NAME="XHTML"/>
   <DATATYPE-DEFINITION-ENUMERATION IDENTIFIER="dt-e" LONG-NAME="Prio"><SPECIFIED-VALUES>
     <ENUM-VALUE IDENTIFIER="ev-h" LONG-NAME="high"/><ENUM-VALUE IDENTIFIER="ev-l" LONG-NAME="low"/></SPECIFIED-VALUES></DATATYPE-DEFINITION-ENUMERATION>
  </DATATYPES>
  <SPEC-TYPES>
   <SPEC-OBJECT-TYPE IDENTIFIER="sot" LONG-NAME="Requirement"><SPEC-ATTRIBUTES>
     <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="ad-name" LONG-NAME="ReqIF.Name"><TYPE><DATATYPE-DEFINITION-STRING-REF>dt-s</DATATYPE-DEFINITION-STRING-REF></TYPE></ATTRIBUTE-DEFINITION-STRING>
     <ATTRIBUTE-DEFINITION-XHTML IDENTIFIER="ad-text" LONG-NAME="ReqIF.Text"><TYPE><DATATYPE-DEFINITION-XHTML-REF>dt-x</DATATYPE-DEFINITION-XHTML-REF></TYPE></ATTRIBUTE-DEFINITION-XHTML>
     <ATTRIBUTE-DEFINITION-ENUMERATION IDENTIFIER="ad-prio" LONG-NAME="Priority"><TYPE><DATATYPE-DEFINITION-ENUMERATION-REF>dt-e</DATATYPE-DEFINITION-ENUMERATION-REF></TYPE></ATTRIBUTE-DEFINITION-ENUMERATION>
     <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="ad-cust" LONG-NAME="Customer Ref"><TYPE><DATATYPE-DEFINITION-STRING-REF>dt-s</DATATYPE-DEFINITION-STRING-REF></TYPE></ATTRIBUTE-DEFINITION-STRING>
   </SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>
   <SPEC-RELATION-TYPE IDENTIFIER="rt-parent" LONG-NAME="parent"/>
   <SPEC-RELATION-TYPE IDENTIFIER="rt-other" LONG-NAME="Satisfies in DOORS"/>
   <SPECIFICATION-TYPE IDENTIFIER="st" LONG-NAME="Spec"/>
  </SPEC-TYPES>
  <SPEC-OBJECTS>
   <SPEC-OBJECT IDENTIFIER="o1"><TYPE><SPEC-OBJECT-TYPE-REF>sot</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="Power"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>ad-name</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
     <ATTRIBUTE-VALUE-XHTML><DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>ad-text</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION><THE-VALUE><xhtml:div><xhtml:p>The spacecraft <xhtml:b>shall</xhtml:b> have power.</xhtml:p><xhtml:ul><xhtml:li>one</xhtml:li><xhtml:li>two</xhtml:li></xhtml:ul></xhtml:div></THE-VALUE></ATTRIBUTE-VALUE-XHTML>
     <ATTRIBUTE-VALUE-ENUMERATION><DEFINITION><ATTRIBUTE-DEFINITION-ENUMERATION-REF>ad-prio</ATTRIBUTE-DEFINITION-ENUMERATION-REF></DEFINITION><VALUES><ENUM-VALUE-REF>ev-h</ENUM-VALUE-REF></VALUES></ATTRIBUTE-VALUE-ENUMERATION>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="C-17"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>ad-cust</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
   </VALUES></SPEC-OBJECT>
   <SPEC-OBJECT IDENTIFIER="o2"><TYPE><SPEC-OBJECT-TYPE-REF>sot</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="Battery"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>ad-name</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
     <ATTRIBUTE-VALUE-XHTML><DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>ad-text</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION><THE-VALUE><xhtml:div>The battery shall store energy.</xhtml:div></THE-VALUE></ATTRIBUTE-VALUE-XHTML>
   </VALUES></SPEC-OBJECT>
   <SPEC-OBJECT IDENTIFIER="o3"><TYPE><SPEC-OBJECT-TYPE-REF>sot</SPEC-OBJECT-TYPE-REF></TYPE><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="Charger"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>ad-name</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
     <ATTRIBUTE-VALUE-XHTML><DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>ad-text</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION><THE-VALUE><xhtml:div>The charger shall charge.</xhtml:div></THE-VALUE></ATTRIBUTE-VALUE-XHTML>
   </VALUES></SPEC-OBJECT>
  </SPEC-OBJECTS>
  <SPEC-RELATIONS>
   <SPEC-RELATION IDENTIFIER="r1"><TYPE><SPEC-RELATION-TYPE-REF>rt-parent</SPEC-RELATION-TYPE-REF></TYPE><SOURCE><SPEC-OBJECT-REF>o2</SPEC-OBJECT-REF></SOURCE><TARGET><SPEC-OBJECT-REF>o1</SPEC-OBJECT-REF></TARGET></SPEC-RELATION>
   <SPEC-RELATION IDENTIFIER="r2"><TYPE><SPEC-RELATION-TYPE-REF>rt-other</SPEC-RELATION-TYPE-REF></TYPE><SOURCE><SPEC-OBJECT-REF>o3</SPEC-OBJECT-REF></SOURCE><TARGET><SPEC-OBJECT-REF>o1</SPEC-OBJECT-REF></TARGET></SPEC-RELATION>
  </SPEC-RELATIONS>
  <SPECIFICATIONS><SPECIFICATION IDENTIFIER="s1" LONG-NAME="Customer spec"><TYPE><SPECIFICATION-TYPE-REF>st</SPECIFICATION-TYPE-REF></TYPE><CHILDREN>
    <SPEC-HIERARCHY IDENTIFIER="h1"><OBJECT><SPEC-OBJECT-REF>o1</SPEC-OBJECT-REF></OBJECT><CHILDREN>
      <SPEC-HIERARCHY IDENTIFIER="h2"><OBJECT><SPEC-OBJECT-REF>o2</SPEC-OBJECT-REF></OBJECT></SPEC-HIERARCHY>
      <SPEC-HIERARCHY IDENTIFIER="h3"><OBJECT><SPEC-OBJECT-REF>o3</SPEC-OBJECT-REF></OBJECT></SPEC-HIERARCHY>
    </CHILDREN></SPEC-HIERARCHY>
  </CHILDREN></SPECIFICATION></SPECIFICATIONS>
 </REQ-IF-CONTENT></CORE-CONTENT>
</REQ-IF>
"""


def test_foreign_file_gets_new_ids_levels_titles_and_parents(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    read = read_reqif(FOREIGN.encode(), cfg, items, document="SYS", mapping={"Customer Ref": "source"})
    rows = {r["title"]: r for r in read.rows}
    assert [r["id"] for r in read.rows] == ["SYS-0005", "SYS-0006", "SYS-0007"]  # next free numbers, hierarchy order
    assert [r["level"] for r in read.rows] == ["1", "1.1", "1.2"]
    assert rows["Battery"]["parents"] == ""  # SYS is the root document: parents are only valid for child documents
    assert rows["Power"]["priority"] == "high" and rows["Power"]["source"] == "C-17"
    assert (
        "shall" in rows["Power"]["text"] and "- one" in rows["Power"]["text"] and "**shall**" in rows["Power"]["text"]
    )
    assert any("Satisfies in DOORS" in n for n in read.notes)  # unknown relation type reported, not imported


def test_foreign_parent_relations_become_parent_links_in_a_child_document(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    text = FOREIGN.replace("<SOURCE><SPEC-OBJECT-REF>o2", "<SOURCE><SPEC-OBJECT-REF>o2")  # same file, imported as EPS
    read = read_reqif(text.encode(), cfg, items, document="EPS")
    ids = [r["id"] for r in read.rows]
    assert ids == ["EPS-0004", "EPS-0005", "EPS-0006"]
    assert read.rows[1]["parents"] == ""  # parent is inside the same document: EPS items cannot parent each other
    assert any("same document" in n for n in read.notes)


def test_unmapped_attributes_are_reported_not_fatal(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    read = read_reqif(FOREIGN.encode(), cfg, [], document="SYS")
    assert read.unmapped == ["Customer Ref"]
    plan = plan_import(cfg, [], read.rows)
    assert not plan.errors, [e.message for e in plan.errors]


def test_specification_name_selects_the_document(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    with pytest.raises(ValueError, match="document"):
        read_reqif(FOREIGN.encode(), cfg, [])  # 'Customer spec' is no document and none was given
    renamed = FOREIGN.replace('LONG-NAME="Customer spec"', 'LONG-NAME="sys"')
    assert all(r["document"] == "SYS" for r in read_reqif(renamed.encode(), cfg, []).rows)


# safety and errors ------------------------------------------------------------------------------------------------------
def test_entity_declarations_are_refused(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><REQ-IF xmlns="%s"/>' % NS.encode()
    with pytest.raises(ValueError, match="DOCTYPE"):
        read_reqif(bomb, cfg, [], document="SYS")


@pytest.mark.parametrize("data", [b"", b"not xml at all", b"<html/>", b'<REQ-IF xmlns="%s"/>' % NS.encode()])
def test_bad_files_give_plain_messages(minimal_project: Path, data: bytes):
    cfg, _ = load_project_config(minimal_project)
    with pytest.raises(ValueError, match="ReqIF"):
        read_reqif(data, cfg, [], document="SYS")


def test_markup_in_statements_cannot_break_the_file(minimal_project: Path):
    DoorstopProject.open(minimal_project).update_item(
        "SYS-0001", text='The <b>unclosed & "odd" tag shall <script>x</script> stay text.'
    )
    root = _tree(_export(minimal_project))  # still well formed
    cfg, _ = load_project_config(minimal_project)
    items = DoorstopProject.open(minimal_project).items()
    plan = plan_import(cfg, items, read_reqif(_export(minimal_project), cfg, items).rows)
    assert {r.action for r in plan.results} == {"unchanged"} and root is not None


# CLI and GUI --------------------------------------------------------------------------------------------------------------
def test_cli_exports_and_dry_run_imports_reqif(minimal_project: Path, tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    from rvs_cli.main import main

    out = tmp_path / "all.reqif"
    assert main(["export", str(minimal_project), "--reqif", "-o", str(out)]) == 0
    assert out.read_bytes().startswith(b"<?xml")
    capsys.readouterr()
    assert main(["import", str(minimal_project), str(out), "--dry-run"]) == 0
    assert "0 to create, 0 to update, 10 unchanged, 0 errors" in capsys.readouterr().out
    only = tmp_path / "eps.reqif"
    assert main(["export", str(minimal_project), "--reqif", "--document", "EPS", "-o", str(only)]) == 0
    assert len(list(_tree(only.read_bytes()).iter(Q + "SPEC-OBJECT"))) == 3


def test_cli_imports_a_foreign_file_with_a_document_and_a_mapping(minimal_project: Path, tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    from rvs_cli.main import main

    foreign = tmp_path / "customer.reqif"
    foreign.write_text(FOREIGN, encoding="utf-8")
    assert main(["import", str(minimal_project), str(foreign), "--dry-run"]) == 2  # no document to import into
    assert "document" in capsys.readouterr().err
    assert (
        main(["import", str(minimal_project), str(foreign), "--document", "SYS", "--map", "Customer Ref=source"]) == 0
    )
    out = capsys.readouterr().out
    assert "3 created" in out or "create" in out
    cfg, _ = load_project_config(minimal_project)
    items = {i.uid: i for i in DoorstopProject.open(minimal_project).items()}
    assert items["SYS-0005"].attrs["title"] == "Power" and items["SYS-0005"].attrs["source"] == "C-17"
    assert main(["import", str(minimal_project), str(foreign), "--document", "SYS", "--map", "Customer Ref=nope"]) == 2


def test_gui_exports_reqif_and_imports_it_back(qtbot, minimal_project: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    from rvs_core.exporters.export_request import ExportRequest
    from rvs_gui.app import create_main_window
    from rvs_gui.export_dialog import ExportDialog

    win = create_main_window()
    qtbot.addWidget(win)
    win.show()
    assert win.open_project(minimal_project)
    dlg = ExportDialog(win.session, win)
    qtbot.addWidget(dlg)
    dlg.set_kind("reqif")
    assert [dlg.format.itemText(i) for i in range(dlg.format.count())] == ["reqif"] and dlg.document.isVisibleTo(dlg)
    assert dlg.request() == ExportRequest("reqif", "reqif")
    target = tmp_path / "out.reqif"
    with qtbot.waitSignal(win.export_done, timeout=30000):
        win.export_to(dlg.request(), target)
    rows = win.read_import_file(target)
    assert rows is not None and len(rows) == 10
    bad = tmp_path / "bad.reqif"
    bad.write_text("<nope/>")
    assert win.read_import_file(bad) is None and win.notification.kind == "error"
