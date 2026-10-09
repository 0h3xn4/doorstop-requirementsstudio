"""Regenerate examples/ (run after changing the generator; a test compares the committed copy)."""

import shutil
from pathlib import Path

from rvs_core.examples.minimal import build_minimal_project

target = Path(__file__).resolve().parents[1] / "examples" / "minimal10"
shutil.rmtree(target, ignore_errors=True)
build_minimal_project(target)
print(f"wrote {target}")
