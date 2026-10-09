"""Regenerate examples/ (run after changing the generator; a test compares the committed copy)."""

import shutil
from pathlib import Path

from rvs_core.examples.minimal import build_minimal_project
from rvs_core.examples.satellite import build_satellite_project

examples = Path(__file__).resolve().parents[1] / "examples"
for name, build in (("minimal10", build_minimal_project), ("satellite300", build_satellite_project)):
    shutil.rmtree(examples / name, ignore_errors=True)
    build(examples / name)
    print(f"wrote {examples / name}")
