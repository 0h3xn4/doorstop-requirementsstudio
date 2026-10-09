"""Every quality rule: a violating and a conforming item (spec: each check traceable to a rule in configuration)."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.findings import Severity
from rvs_core.rules import build_context, run_rules


@pytest.fixture
def proj(minimal_project: Path) -> DoorstopProject:
    return DoorstopProject.open(minimal_project)


def _codes(root: Path, uid: str | None = None) -> set[str]:
    cfg, _ = load_project_config(root)
    proj = DoorstopProject.open(root)
    ctx = build_context(cfg, proj.items(), proj.documents())
    return {f.code for f in run_rules(ctx) if uid is None or f.uid == uid}


def _edit(root: Path, uid: str, text: str | None = None, **attrs: Any) -> None:
    proj = DoorstopProject.open(root)
    proj.update_item(uid, text=text, attrs=attrs or None)


def test_minimal_project_is_clean(minimal_project: Path):
    assert _codes(minimal_project) == set()


# shall-present -------------------------------------------------------------
def test_shall_present_violation(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", text="The spacecraft provides power.")
    assert "RVS-RULE-SHALL-PRESENT" in _codes(minimal_project, "SYS-0001")


def test_shall_present_ok_case_insensitive_and_word_boundary(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", text="The spacecraft SHALL provide power.")
    assert "RVS-RULE-SHALL-PRESENT" not in _codes(minimal_project, "SYS-0001")
    _edit(minimal_project, "SYS-0001", text="The spacecraft marshall provide power.")
    assert "RVS-RULE-SHALL-PRESENT" in _codes(minimal_project, "SYS-0001")


def test_shall_not_checked_on_headings_or_verification_items(minimal_project: Path):
    assert "RVS-RULE-SHALL-PRESENT" not in _codes(minimal_project, "SYS-0004")  # non-normative heading
    assert "RVS-RULE-SHALL-PRESENT" not in _codes(minimal_project, "VER-0001")  # verification kind


# single-statement ------------------------------------------------------------
def test_single_statement(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", text="The spacecraft shall do A. The spacecraft shall do B.")
    assert "RVS-RULE-SINGLE-STATEMENT" in _codes(minimal_project, "SYS-0001")
    _edit(minimal_project, "SYS-0001", text="The spacecraft shall do A and B.")
    assert "RVS-RULE-SINGLE-STATEMENT" not in _codes(minimal_project, "SYS-0001")


# vague-words -----------------------------------------------------------------
@pytest.mark.parametrize("phrase", ["adequate", "As Appropriate", "user-friendly"])
def test_vague_words_found(minimal_project: Path, phrase: str):
    _edit(minimal_project, "SYS-0001", text=f"The spacecraft shall provide {phrase} power.")
    assert "RVS-RULE-VAGUE-WORDS" in _codes(minimal_project, "SYS-0001")


def test_vague_words_need_whole_word_match(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", text="The spacecraft shall provide inadequately-named power.")
    assert "RVS-RULE-VAGUE-WORDS" not in _codes(minimal_project, "SYS-0001")


def test_vague_word_list_comes_from_configuration(minimal_project: Path):
    path = minimal_project / "config" / "rules.yaml"
    data = yaml.safe_load(path.read_text())
    for r in data["rules"]:
        if r["id"] == "vague-words":
            r["params"]["words"] = ["robust"]
    path.write_text(yaml.safe_dump(data))
    _edit(minimal_project, "SYS-0001", text="The spacecraft shall provide robust power.")
    assert "RVS-RULE-VAGUE-WORDS" in _codes(minimal_project, "SYS-0001")
    _edit(minimal_project, "SYS-0001", text="The spacecraft shall provide adequate power.")
    assert "RVS-RULE-VAGUE-WORDS" not in _codes(minimal_project, "SYS-0001")


# no-implementation -------------------------------------------------------------
def _set_terms(root: Path, terms: list[str]) -> None:
    path = root / "config" / "rules.yaml"
    data = yaml.safe_load(path.read_text())
    for r in data["rules"]:
        if r["id"] == "no-implementation":
            r["params"]["terms"] = terms
    path.write_text(yaml.safe_dump(data))


def test_no_implementation_only_for_functional(minimal_project: Path):
    _set_terms(minimal_project, ["FPGA"])
    _edit(minimal_project, "SYS-0001", text="The spacecraft shall use an FPGA to provide power.")  # functional
    assert "RVS-RULE-NO-IMPLEMENTATION" in _codes(minimal_project, "SYS-0001")
    _edit(minimal_project, "SYS-0003", text="The spacecraft shall use an FPGA to stay light.")  # performance
    assert "RVS-RULE-NO-IMPLEMENTATION" not in _codes(minimal_project, "SYS-0003")


def test_no_implementation_with_no_terms_is_silent(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    proj = DoorstopProject.open(minimal_project)
    findings = run_rules(build_context(cfg, proj.items(), proj.documents()))
    assert findings == []  # clean project: placeholders alone are reported by `validate`, not per item


# verify-method-set -------------------------------------------------------------
def test_verify_method_set(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", verify_method="")
    assert "RVS-RULE-VERIFY-METHOD-SET" in _codes(minimal_project, "SYS-0001")
    _edit(minimal_project, "SYS-0001", verify_method="test")
    assert "RVS-RULE-VERIFY-METHOD-SET" not in _codes(minimal_project, "SYS-0001")


# has-parent ---------------------------------------------------------------------
def test_has_parent(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    item = proj.add_item("EPS", "The EPS shall be orphaned.", attrs={"title": "Orphan", "type": "functional"})
    assert "RVS-RULE-HAS-PARENT" in _codes(minimal_project, item.uid)
    proj.link(item.uid, "SYS-0001")
    assert "RVS-RULE-HAS-PARENT" not in _codes(minimal_project, item.uid)


def test_has_parent_exempt_for_root_document_and_derived_items(minimal_project: Path):
    assert "RVS-RULE-HAS-PARENT" not in _codes(minimal_project, "SYS-0001")  # root document
    proj = DoorstopProject.open(minimal_project)
    item = proj.add_item("EPS", "The EPS shall be derived.", attrs={"title": "D", "type": "functional"}, derived=True)
    assert "RVS-RULE-HAS-PARENT" not in _codes(minimal_project, item.uid)


# verified-when-approved --------------------------------------------------------------
def test_verified_when_approved(minimal_project: Path):
    _edit(minimal_project, "EPS-0001", status="approved")  # VER-0001 verifies EPS-0001
    assert "RVS-RULE-VERIFIED-WHEN-APPROVED" not in _codes(minimal_project, "EPS-0001")
    _edit(minimal_project, "SYS-0001", status="approved")  # nothing verifies it
    f = [x for x in _findings(minimal_project) if x.uid == "SYS-0001" and x.code == "RVS-RULE-VERIFIED-WHEN-APPROVED"]
    assert f and f[0].severity is Severity.ERROR
    _edit(minimal_project, "SYS-0001", status="draft")
    assert "RVS-RULE-VERIFIED-WHEN-APPROVED" not in _codes(minimal_project, "SYS-0001")


def test_verified_via_own_verifies_link(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", status="approved", link_verifies=["VER-0001"])
    assert "RVS-RULE-VERIFIED-WHEN-APPROVED" not in _codes(minimal_project, "SYS-0001")


def _findings(root: Path):  # type: ignore[no-untyped-def]
    cfg, _ = load_project_config(root)
    proj = DoorstopProject.open(root)
    return run_rules(build_context(cfg, proj.items(), proj.documents()))


# configuration controls ---------------------------------------------------------------
def test_disabled_rule_is_skipped_and_severity_is_configurable(minimal_project: Path):
    path = minimal_project / "config" / "rules.yaml"
    data = yaml.safe_load(path.read_text())
    for r in data["rules"]:
        if r["id"] == "shall-present":
            r["enabled"] = False
        if r["id"] == "verify-method-set":
            r["severity"] = "info"
    path.write_text(yaml.safe_dump(data))
    _edit(minimal_project, "SYS-0001", text="Power is provided.", verify_method="")
    found = {f.code: f for f in _findings(minimal_project) if f.uid == "SYS-0001"}
    assert "RVS-RULE-SHALL-PRESENT" not in found
    assert found["RVS-RULE-VERIFY-METHOD-SET"].severity is Severity.INFO


def test_unknown_rule_id_in_configuration_is_reported(minimal_project: Path):
    path = minimal_project / "config" / "rules.yaml"
    data = yaml.safe_load(path.read_text())
    data["rules"].append({"id": "made-up", "severity": "error", "enabled": True})
    path.write_text(yaml.safe_dump(data))
    f = [x for x in _findings(minimal_project) if x.code == "RVS-RULE-UNKNOWN"]
    assert f and "made-up" in f[0].message


def test_findings_are_plain_language_with_hint_and_location(minimal_project: Path):
    _edit(minimal_project, "SYS-0001", text="Power is provided.")
    f = next(x for x in _findings(minimal_project) if x.code == "RVS-RULE-SHALL-PRESENT")
    assert f.uid == "SYS-0001" and f.location.endswith("SYS-0001.yml")
    assert "shall" in f.message and f.hint


def test_rules_run_inside_validate(minimal_project: Path):
    from rvs_core.validate import validate_project

    _edit(minimal_project, "SYS-0001", text="Power is provided.")
    report = validate_project(minimal_project)
    assert "RVS-RULE-SHALL-PRESENT" in {f.code for f in report.findings}
    assert report.exit_code == 1
