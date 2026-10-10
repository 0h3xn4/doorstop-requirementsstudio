from pathlib import Path

from rvs_core.examples.minimal import build_minimal_project


def _snapshot(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_regeneration_is_byte_identical(tmp_path: Path):
    build_minimal_project(tmp_path / "a")
    build_minimal_project(tmp_path / "b")
    assert _snapshot(tmp_path / "a") == _snapshot(tmp_path / "b")


def test_no_timestamps_in_generated_files(tmp_path: Path):
    import re

    build_minimal_project(tmp_path / "a")
    stamp = re.compile(r"\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d")
    for name, data in _snapshot(tmp_path / "a").items():
        assert not stamp.search(data.decode("utf-8")), name
