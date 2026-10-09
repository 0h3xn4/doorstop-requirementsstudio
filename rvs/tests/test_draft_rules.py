from pathlib import Path

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.rules.draft import check_draft


def _check(root: Path, **kw):  # type: ignore[no-untyped-def]
    cfg, _ = load_project_config(root)
    items = DoorstopProject.open(root).items()
    docs = DoorstopProject.open(root).documents()
    return check_draft(cfg, items, docs, **kw)


def test_a_good_draft_has_no_findings(minimal_project: Path):
    found = _check(minimal_project, document="EPS", text="The EPS shall regulate the bus voltage.",
                   attrs={"title": "Reg", "type": "functional", "verify_method": "test"}, parents=["SYS-0001"])  # fmt: skip
    assert found == []


def test_bad_drafts_report_the_rules_that_apply(minimal_project: Path):
    found = _check(minimal_project, document="EPS", text="The OBC provides adequate power.", attrs={"title": "x", "type": "functional"}, parents=[])  # fmt: skip
    codes = {f.code for f in found}
    assert {
        "RVS-RULE-SHALL-PRESENT",
        "RVS-RULE-VAGUE-WORDS",
        "RVS-RULE-HAS-PARENT",
        "RVS-RULE-VERIFY-METHOD-SET",
        "RVS-RULE-UNDEFINED-ACRONYM",
    } <= codes
    assert all(f.uid == "(new)" for f in found)


def test_drafts_do_not_touch_the_project(minimal_project: Path):
    before = {p: p.read_bytes() for p in minimal_project.rglob("*.yml")}
    _check(minimal_project, document="EPS", text="x", attrs={}, parents=[])
    assert {p: p.read_bytes() for p in minimal_project.rglob("*.yml")} == before
    assert len(DoorstopProject.open(minimal_project).items()) == 10


def test_root_document_drafts_need_no_parent(minimal_project: Path):
    found = _check(minimal_project, document="SYS", text="The system shall exist.", attrs={"title": "t", "type": "functional", "verify_method": "test"}, parents=[])  # fmt: skip
    assert "RVS-RULE-HAS-PARENT" not in {f.code for f in found}
