import subprocess
import sys
from pathlib import Path

from conftest import EXAMPLES
from rvs_core.examples.minimal import build_minimal_project


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts and ".rvs-cache" not in p.parts
    }


def test_committed_minimal_example_matches_generator(tmp_path: Path):
    build_minimal_project(tmp_path / "m")
    assert _snapshot(EXAMPLES / "minimal10") == _snapshot(tmp_path / "m")


def test_minimal_example_has_ten_items(minimal_project: Path):
    from rvs_core.adapter import DoorstopProject

    assert len(DoorstopProject.open(minimal_project).items()) == 10


def test_plain_doorstop_cli_validates_the_reference_project(minimal_project: Path):
    """Spec: a project folder must stay a valid Doorstop tree (CI runs Doorstop's own validation)."""
    subprocess.run(["git", "init", "-q"], cwd=minimal_project, check=True)  # Doorstop's CLI needs a working copy
    out = subprocess.run(
        [sys.executable, "-c", "import sys; from doorstop.cli.main import main; sys.exit(main())"],
        cwd=minimal_project, capture_output=True, text=True, check=False, timeout=120,
    )  # fmt: skip
    assert out.returncode == 0, out.stdout + out.stderr
