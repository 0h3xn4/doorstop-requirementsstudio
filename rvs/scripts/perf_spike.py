"""M1 spike: build a 5,000-item project, then time open / read-all / validate. Usage: perf_spike.py [dir]."""

import sys
import tempfile
import time
from pathlib import Path

from rvs_core.adapter import DoorstopProject
from rvs_core.config.model import DocumentDecl
from rvs_core.project import create_project
from rvs_core.validate import validate_project

DOCS = (
    DocumentDecl("SYS", "requirements", "System"),
    DocumentDecl("SUB", "requirements", "Subsystem", parent="SYS"),
    DocumentDecl("VER", "verification", "Verification", parent="SYS"),
)
N = 5000


def build(root: Path) -> None:
    proj = create_project(root, "Stress", DOCS)
    per = {"SYS": 500, "SUB": 3500, "VER": 1000}
    for prefix, count in per.items():
        for n in range(count):
            attrs = {"title": f"Item {n}", "type": "functional", "verify_method": "test", "verify_level": "system"}
            if prefix == "VER":
                attrs = {"title": f"Proc {n}", "verify_method": "test", "verify_level": "system", "v_status": "planned"}
            proj.add_item(
                prefix, f"The system shall do thing {n}.", attrs=attrs, level=f"1.{n + 1}", derived=prefix == "VER"
            )


def timed(label: str, fn):  # type: ignore[no-untyped-def]
    t = time.perf_counter()
    out = fn()
    print(f"{label:28} {time.perf_counter() - t:6.2f} s")
    return out


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp())
    root = base / "stress5000"
    if not root.exists():
        timed(f"build {N} items", lambda: build(root))
    proj = timed("open tree", lambda: DoorstopProject.open(root))
    items = timed("read all items", lambda: proj.items())
    print(f"{len(items)} items")
    timed("rvs validate (full)", lambda: validate_project(root))
