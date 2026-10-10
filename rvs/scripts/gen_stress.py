"""Generate the 5,000-item stress project (about a minute): gen_stress.py <target-dir> [total-items]."""

import sys
from pathlib import Path

from rvs_core.examples.stress import build_stress_project

target = Path(sys.argv[1])
build_stress_project(target, int(sys.argv[2]) if len(sys.argv) > 2 else 5000)
print(f"wrote {target}")
