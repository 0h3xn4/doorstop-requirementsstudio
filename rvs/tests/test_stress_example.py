from pathlib import Path

import pytest

from rvs_core.adapter import DoorstopProject
from rvs_core.examples.stress import build_stress_project
from rvs_core.validate import validate_project


def test_small_stress_project_is_valid_and_deterministic(tmp_path: Path):
    build_stress_project(tmp_path / "a", total=60)
    build_stress_project(tmp_path / "b", total=60)
    items = DoorstopProject.open(tmp_path / "a").items()
    assert len(items) == 60

    def snap(r: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(r)): p.read_bytes()
            for p in sorted(r.rglob("*"))
            if p.is_file() and ".rvs-cache" not in p.parts
        }

    assert snap(tmp_path / "a") == snap(tmp_path / "b")
    report = validate_project(tmp_path / "a", doorstop=False)
    assert not [f for f in report.findings if f.code.startswith(("RVS-ATTR", "RVS-DOC", "RVS-LINK", "RVS-SCHEMA"))], [
        f.format() for f in report.findings
    ][:5]


@pytest.mark.parametrize("total", [10, 100])
def test_requested_size_is_respected(tmp_path: Path, total: int):
    build_stress_project(tmp_path / "p", total=total)
    assert len(DoorstopProject.open(tmp_path / "p").items()) == total
