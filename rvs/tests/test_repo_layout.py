"""RVS lives in a folder of a clone of Doorstop itself; Doorstop's own commands and tests run at the clone's root."""

from pathlib import Path

import pytest

RVS = Path(__file__).resolve().parents[1]
CLONE = RVS.parent


def test_rvs_folder_is_invisible_to_doorstop_run_at_the_clone_root():
    """Without ``rvs/.doorstop.skip-all`` the example projects (several root documents named SYS, MIS, ...) make plain
    ``doorstop`` fail with "multiple root documents" and break the upstream test suite."""
    if not (CLONE / "doorstop" / "core" / "builder.py").is_file():
        pytest.skip("not inside the Doorstop clone (for example an unpacked sdist)")
    assert (RVS / ".doorstop.skip-all").is_file()
    from doorstop.core import builder

    prefixes = {str(d.prefix) for d in builder.build(root=str(CLONE))}
    assert not prefixes & {"SYS", "MIS", "EPS", "VER", "PLD"}
