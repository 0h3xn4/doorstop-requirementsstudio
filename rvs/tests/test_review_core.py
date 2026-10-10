"""Regressions for defects found in the core by the review pass (data integrity, malformed hand-edited files)."""

import os
import shutil
import time
from pathlib import Path

import pytest
import yaml

from conftest import EXAMPLES
from rvs_core.adapter import DoorstopProject
from rvs_core.authoring import EditService, read_history
from rvs_core.validate import validate_project


def _aged(root: Path) -> None:
    old = time.time() - 600
    for p in root.rglob("*.yml"):
        os.utime(p, (old, old))


# links ------------------------------------------------------------------------------------------------------------------
def test_adding_a_parent_does_not_clear_a_link_that_is_already_suspect(minimal_project: Path):
    svc = EditService(minimal_project)
    svc.update_item("SYS-0001", text="The spacecraft shall have changed power needs.")
    proj = DoorstopProject.open(minimal_project)
    assert "SYS-0001" in proj.suspect_links("EPS-0002")
    svc.set_parents("EPS-0002", ["SYS-0001", "SYS-0003"])
    again = DoorstopProject.open(minimal_project)
    assert again.suspect_links("EPS-0002") == ("SYS-0001",)  # SYS-0003 is new and fresh; SYS-0001 stays unreviewed


# malformed hand edits ------------------------------------------------------------------------------------------------------
def _patch(root: Path, rel: str, **fields: object) -> None:
    path = root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(fields)
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


@pytest.mark.parametrize(
    "fields",
    [
        {"text": 5},
        {"text": ["a", "b"]},
        {"level": "abc"},
        {"links": 5},
        {"header": 3},
        {"status": ["draft"]},
        {"status": {"a": 1}},
        {"link_verifies": 5},
        {"link_satisfies": "SYS-0001"},
        {"owner": {"x": 1}},
        {"references": "abc"},
    ],
)
def test_validate_reports_instead_of_raising_on_odd_item_content(minimal_project: Path, fields: dict[str, object]):
    _patch(minimal_project, "EPS/EPS-0002.yml", **fields)
    report = validate_project(minimal_project, doorstop=False)  # must not raise
    assert report.findings and report.exit_code in (0, 1, 3)


def test_an_impossible_date_is_a_finding_not_a_crash(minimal_project: Path):
    path = minimal_project / "VER" / "VER-0001.yml"
    path.write_text(path.read_text(encoding="utf-8") + "executed_on: 2024-02-30\n", encoding="utf-8")
    report = validate_project(minimal_project, doorstop=False)
    assert report.exit_code in (1, 3) and any(f.severity.value == "error" for f in report.findings)


def test_a_quoted_impossible_date_is_a_type_error(minimal_project: Path):
    _patch(minimal_project, "VER/VER-0001.yml", executed_on="2020-13-45")
    report = validate_project(minimal_project, doorstop=False)
    assert any(f.code == "RVS-ATTR-TYPE" and "executed_on" in f.message for f in report.findings)


def test_the_safety_net_names_the_error_type_only(minimal_project: Path, monkeypatch):  # type: ignore[no-untyped-def]
    import rvs_core.validate as v

    def boom(*_a: object, **_k: object) -> None:
        raise KeyError("secret requirement text")

    monkeypatch.setattr(v, "run_rules", boom)
    report = validate_project(minimal_project, doorstop=False)
    assert report.exit_code == 3 and report.findings[0].code == "RVS-VALIDATION-FAILED"
    assert "KeyError" in report.findings[0].message and "secret" not in report.findings[0].message


def test_stray_and_misnamed_item_files_are_errors(minimal_project: Path):
    shutil.copy(minimal_project / "SYS" / "SYS-0001.yml", minimal_project / "SYS" / "SYS-0001 copy.yml")
    shutil.copy(minimal_project / "SYS" / "SYS-0002.yml", minimal_project / "SYS" / "EPS-0099.yml")
    report = validate_project(minimal_project, doorstop=False)
    names = [f for f in report.findings if f.code == "RVS-ITEM-NAME"]
    assert len(names) == 2 and report.exit_code == 1


def test_config_that_is_not_utf8_is_reported(minimal_project: Path):
    (minimal_project / "config" / "vocab.yaml").write_bytes("values: {type: [caf\xe9]}\n".encode("latin-1"))
    report = validate_project(minimal_project, doorstop=False)
    assert (
        report.exit_code == 3 and report.findings[0].code == "RVS-CONFIG-YAML" and "UTF-8" in report.findings[0].message
    )


def test_empty_rule_parameters_do_not_crash(minimal_project: Path):
    rules = minimal_project / "config" / "rules.yaml"
    data = yaml.safe_load(rules.read_text(encoding="utf-8"))
    for rule in data["rules"]:
        rule["params"] = {k: None for k in rule.get("params", {})} or {"words": None, "terms": None}
    rules.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert validate_project(minimal_project, doorstop=False).exit_code in (0, 1)


# what EditService accepts ----------------------------------------------------------------------------------------------------
def test_unstorable_characters_are_refused_and_the_item_stays_editable(minimal_project: Path):
    svc = EditService(minimal_project)
    for bad in ("bad \ud800 paste", "soft\x0bbreak", "nul\x00"):
        with pytest.raises(ValueError, match="control character"):
            svc.update_item("SYS-0001", text=f"The spacecraft shall {bad}.")
    with pytest.raises(ValueError, match="control character"):
        svc.update_item("SYS-0001", attrs={"owner": "a\x0bb"})
    with pytest.raises(ValueError, match="control character"):
        svc.create_item("SYS", "The spacecraft shall exist.\x1f", attrs={"title": "t", "type": "functional"})
    svc.update_item("SYS-0001", text="The spacecraft shall still be editable.")
    assert validate_project(minimal_project, doorstop=False).exit_code == 0


def test_doorstops_own_fields_and_unknown_names_cannot_be_written_as_attributes(minimal_project: Path):
    svc = EditService(minimal_project)
    for name in ("links", "level", "active", "normative", "text", "bogus"):
        with pytest.raises(ValueError, match="not a field"):
            svc.update_item("EPS-0001", attrs={name: "x"})
    assert DoorstopProject.open(minimal_project).get_item("EPS-0001").links == ("SYS-0002",)


def test_creating_in_an_unknown_document_is_a_plain_error(minimal_project: Path):
    with pytest.raises(ValueError, match="does not exist"):
        EditService(minimal_project).create_item("NOPE", "The x shall y.", attrs={"title": "t", "type": "functional"})


def test_a_failing_history_write_leaves_the_item_unchanged(minimal_project: Path):
    (minimal_project / "history").mkdir(exist_ok=True)
    (minimal_project / "history" / "SYS").write_text("a file where the folder should be")
    before = (minimal_project / "SYS" / "SYS-0001.yml").read_bytes()
    with pytest.raises(OSError):
        EditService(minimal_project).update_item("SYS-0001", text="The spacecraft shall change.")
    assert (minimal_project / "SYS" / "SYS-0001.yml").read_bytes() == before


def test_history_survives_a_damaged_line(minimal_project: Path):
    svc = EditService(minimal_project, user="a")
    svc.update_item("SYS-0001", text="The spacecraft shall be first.")
    path = minimal_project / "history" / "SYS" / "SYS-0001.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"action": "upd')  # a partial line, no newline
    svc.update_item("SYS-0001", text="The spacecraft shall be second.")
    entries = read_history(minimal_project, "SYS-0001")
    assert [e["action"] for e in entries] == ["update", "update"]
    path.write_bytes(path.read_bytes() + b"\xff\xfe junk\n<<<<<<< HEAD\n")
    assert len(read_history(minimal_project, "SYS-0001")) == 2


# cache, templates, numbering, impact, rules ---------------------------------------------------------------------------------------
def test_cached_paths_follow_a_moved_document_folder(tmp_path: Path):
    root = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "minimal10", root, ignore=shutil.ignore_patterns(".rvs-cache"))
    _aged(root)
    DoorstopProject.open(root).items()  # fills the cache
    before = {i.uid: i.path for i in DoorstopProject.open(root).items()}
    assert before["SYS-0001"] == "SYS/SYS-0001.yml"
    (root / "docs").mkdir()
    shutil.move(str(root / "SYS"), str(root / "docs" / "SYS"))
    moved = {i.uid: i.path for i in DoorstopProject.open(root).items()}
    assert moved["SYS-0001"] == "docs/SYS/SYS-0001.yml"


def test_a_template_is_never_written_into_a_used_folder(tmp_path: Path):
    from rvs_core.project_templates import create_from_template

    folder = tmp_path / "used"
    (folder / "config").mkdir(parents=True)
    (folder / "config" / "rules.yaml").write_text("mine: true\n")
    with pytest.raises(ValueError, match="not empty"):
        create_from_template(folder, "P", "minimal")
    assert (folder / "config" / "rules.yaml").read_text() == "mine: true\n" and not (
        folder / "rvs-project.yaml"
    ).exists()
    create_from_template(tmp_path / "fresh", "P", "minimal", git=True)  # an empty or new folder is fine


def test_only_the_dash_separator_is_accepted(minimal_project: Path):
    path = minimal_project / "config" / "numbering.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace('sep: "-"', 'sep: "_"'), encoding="utf-8")
    report = validate_project(minimal_project, doorstop=False)
    assert report.exit_code == 3 and report.findings[0].code == "RVS-CONFIG-INVALID"


def test_impact_lists_an_item_at_its_shallowest_depth():
    from rvs_core.config import load_project_config
    from rvs_core.trace import LinkGraph, impact
    from rvs_core.trace.graph import Edge

    graph = LinkGraph(
        [Edge("A", "R", "refines"), Edge("C", "R", "refines"), Edge("B", "A", "refines"), Edge("X", "B", "refines"), Edge("X", "C", "refines")],
        [], frozenset(), {"R", "A", "B", "C", "X"},
    )  # fmt: skip
    depth = {n.uid: n.depth for n in impact(graph, "R").root.children} | {
        n.uid: n.depth for n in impact(graph, "R").flat()
    }
    assert depth["X"] == 2 and load_project_config


def test_vague_phrases_match_across_line_breaks_and_extra_spaces():
    from rvs_core.rules.engine import _word

    pattern = _word("as appropriate")
    assert pattern.search("do it as\nappropriate") and pattern.search("do it as   appropriate")
    assert not pattern.search("do it as inappropriate")
