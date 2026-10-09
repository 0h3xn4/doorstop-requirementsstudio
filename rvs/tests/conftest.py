import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    from rvs_core.examples.minimal import build_minimal_project

    root = tmp_path / "minimal"
    build_minimal_project(root)
    return root


@pytest.fixture
def git_project(minimal_project: Path) -> Path:
    """The minimal project inside its own Git repository (no commits yet)."""
    from rvs_core.vcs.git import GitRepo

    GitRepo.init(minimal_project)
    return minimal_project
