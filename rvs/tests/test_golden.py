"""Golden-file tests: every output type on the reference projects (spec: minimal 10 items, satellite ~300).

Regenerate after an intentional change:  PYTHONPATH=tests python scripts/gen_goldens.py  (then review the diff)."""

import hashlib
import json
import sys

import pytest

from golden_support import GOLDEN, outputs_for


@pytest.fixture(scope="module")
def minimal_outputs() -> dict[str, bytes]:
    return outputs_for("minimal10")


@pytest.fixture(scope="module")
def satellite_outputs() -> dict[str, bytes]:
    return outputs_for("satellite300")


# PDF streams are zlib-compressed, so their bytes can differ between platforms; goldens come from Linux.
PORTABLE = ("csv", "json", "html", "xlsx", "docx")


def _comparable(name: str) -> bool:
    return sys.platform == "linux" or name.rsplit(".", 1)[1] in PORTABLE


def _check(name: str, outputs: dict[str, bytes]) -> None:
    manifest = json.loads((GOLDEN / name / "manifest.json").read_text(encoding="utf-8"))
    assert sorted(outputs) == sorted(manifest)
    differing = [n for n, data in outputs.items() if _comparable(n) and hashlib.sha256(data).hexdigest() != manifest[n]]
    assert not differing, f"outputs changed: {differing} (regenerate with scripts/gen_goldens.py if intended)"


def test_minimal10_outputs_match_golden_hashes(minimal_outputs: dict[str, bytes]):
    _check("minimal10", minimal_outputs)


def test_minimal10_text_outputs_match_golden_files(minimal_outputs: dict[str, bytes]):
    stored = sorted(
        p for p in (GOLDEN / "minimal10").iterdir() if p.suffix in (".csv", ".json") and p.name != "manifest.json"
    )
    assert len(stored) == 9
    for path in stored:
        assert minimal_outputs[path.name] == path.read_bytes(), path.name


def test_satellite300_outputs_match_golden_hashes(satellite_outputs: dict[str, bytes]):
    _check("satellite300", satellite_outputs)


def test_every_output_type_is_covered(minimal_outputs: dict[str, bytes]):
    kinds = {n.rsplit(".", 1)[1] for n in minimal_outputs}
    assert kinds == {"csv", "json", "xlsx", "html", "docx", "pdf", "reqif"}
    assert {n.split(".")[0].split("-")[0] for n in minimal_outputs} == {
        "vcm",
        "trace",
        "coverage",
        "impact",
        "items",
        "project",
        "spec",
    }
