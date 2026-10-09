from collections import defaultdict
from pathlib import Path

import pytest

from conftest import EXAMPLES
from rvs_core.adapter import DoorstopProject
from rvs_core.examples.satellite import SEEDED_DEFECTS, build_satellite_project
from rvs_core.validate import validate_project


@pytest.fixture(scope="module")
def sat(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("sat") / "satellite"
    build_satellite_project(root)
    return root


def test_size_and_structure(sat: Path):
    proj = DoorstopProject.open(sat)
    reqs = [i for i in proj.items() if i.document != "VER"]
    assert 290 <= len(reqs) <= 310
    assert {d.prefix for d in proj.documents()} == {
        "MIS",
        "SYS",
        "EPS",
        "OBC",
        "AOCS",
        "TTC",
        "STR",
        "THM",
        "PLD",
        "VER",
    }


def test_rule_engine_finds_exactly_the_seeded_defects(sat: Path):
    report = validate_project(sat)
    found: dict[str, list[str]] = defaultdict(list)
    for f in report.findings:
        if f.code.startswith("RVS-RULE-"):
            found[f.code].append(f.uid)
    assert {k: sorted(v) for k, v in found.items()} == SEEDED_DEFECTS
    assert report.exit_code == 1  # seeded errors


def test_no_config_or_schema_findings(sat: Path):
    codes = {f.code for f in validate_project(sat).findings}
    assert not [c for c in codes if c.startswith(("RVS-ATTR", "RVS-DOC", "RVS-SCHEMA"))], codes


def test_committed_copy_matches_generator(sat: Path):
    def snap(root: Path) -> dict[str, bytes]:
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    assert snap(EXAMPLES / "satellite300") == snap(sat)
