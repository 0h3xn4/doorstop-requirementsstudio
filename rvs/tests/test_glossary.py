from pathlib import Path

import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.glossary import find_acronyms
from rvs_core.rules import build_context, run_rules


def test_find_acronyms_basic():
    text = "The EPS shall power the OBC and TT&C units. See EPS-0001 and SYS-0002 for 28 V."
    found = [(a.text, a.defined) for a in find_acronyms(text, known={"EPS"})]
    assert ("EPS", True) in found
    assert ("OBC", False) in found and ("TT&C", False) in found
    assert all(t not in {"SYS", "V"} for t, _ in found)  # UID prefixes and single letters are ignored
    assert len([1 for t, _ in found if t == "EPS"]) == 1  # "EPS-0001" is an ID, not an acronym use


def test_find_acronyms_positions_are_exact():
    text = "Use the OBC now."
    (hit,) = find_acronyms(text, known=set())
    assert text[hit.start : hit.end] == "OBC"


def test_min_length_and_ignore():
    hits = find_acronyms("AB and ABC and XYZ", known=set(), min_length=3, ignore={"XYZ"})
    assert [h.text for h in hits] == ["ABC"]


def test_undefined_acronym_rule(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    proj.update_item("SYS-0001", text="The spacecraft shall power the OBC.")
    cfg, _ = load_project_config(minimal_project)
    findings = [f for f in run_rules(build_context(cfg, proj.items(), proj.documents())) if f.uid == "SYS-0001"]
    f = next(x for x in findings if x.code == "RVS-RULE-UNDEFINED-ACRONYM")
    assert "OBC" in f.message and "glossary" in f.hint.lower()


def test_defining_the_acronym_in_the_glossary_clears_the_finding(minimal_project: Path):
    proj = DoorstopProject.open(minimal_project)
    proj.update_item("SYS-0001", text="The spacecraft shall power the OBC.")
    path = minimal_project / "config" / "glossary.yaml"
    data = yaml.safe_load(path.read_text())
    data["acronyms"].append({"acronym": "OBC", "expansion": "On-Board Computer"})
    path.write_text(yaml.safe_dump(data))
    cfg, _ = load_project_config(minimal_project)
    codes = {f.code for f in run_rules(build_context(cfg, proj.items(), proj.documents())) if f.uid == "SYS-0001"}
    assert "RVS-RULE-UNDEFINED-ACRONYM" not in codes
