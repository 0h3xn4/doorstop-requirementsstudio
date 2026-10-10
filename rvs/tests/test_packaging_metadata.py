"""Runtime install set must not contain dev/release tooling (spec rule 8)."""

import tomllib
from pathlib import Path

PYPROJECT = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
DEV_ONLY = {"pytest", "pytest-qt", "hypothesis", "mypy", "ruff", "pyinstaller", "cyclonedx-bom",
            "pip-licenses", "pip-audit", "import-linter", "lxml", "build"}  # fmt: skip


def _name(req: str) -> str:
    for ch in "<>=!~[; ":
        req = req.split(ch)[0]
    return req.lower()


def test_runtime_dependencies_exclude_dev_tooling():
    runtime = {_name(r) for r in PYPROJECT["project"]["dependencies"]}
    assert not runtime & DEV_ONLY


def test_dev_extra_has_tooling_and_sbom():
    dev = {_name(r) for r in PYPROJECT["project"]["optional-dependencies"]["dev"]}
    assert {"pytest", "mypy", "ruff", "pyinstaller", "cyclonedx-bom", "pip-licenses", "pip-audit"} <= dev


def test_runtime_dependencies_pinned_and_doorstop_exact():
    deps = PYPROJECT["project"]["dependencies"]
    assert "doorstop==3.2" in deps
    assert all("==" in d or "~=" in d for d in deps), deps


def test_supported_python_range_declared():
    assert PYPROJECT["project"]["requires-python"] == ">=3.11,<3.14"
