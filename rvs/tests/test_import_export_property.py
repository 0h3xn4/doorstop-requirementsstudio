"""Property tests (spec): export -> import is lossless and changes nothing; regeneration is byte-identical."""

import tempfile
from datetime import datetime
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rvs_core.adapter import DoorstopProject
from rvs_core.config import load_project_config
from rvs_core.config.model import DocumentDecl
from rvs_core.exporters.itemsio import (
    apply_import,
    export_items_csv,
    export_items_xlsx,
    plan_import,
    read_csv,
    read_xlsx,
)
from rvs_core.matrices import Provenance
from rvs_core.project import create_project

PROV = Provenance("0.1.0", "3.2", "P", "working copy", datetime(2026, 1, 2, 3, 4, 5), "alice")
DOCS = (DocumentDecl("SYS", "requirements", "System"), DocumentDecl("EPS", "requirements", "EPS", parent="SYS"))

_word = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\x85  "), min_size=1, max_size=30
).filter(lambda s: s.strip() == s)
_tricky = st.sampled_from(
    [
        "yes",
        "no",
        "null",
        "~",
        "1.0",
        "0x1F",
        ": x",
        "# c",
        "- a",
        "a,b",
        'say "hi"',
        "=1+1",
        "+1",
        "-1",
        "@x",
        "é☃",
        "2024-01-01",
        "a;b",
    ]
)
_value = st.one_of(_word, _tricky)
_multiline = st.lists(_value, min_size=1, max_size=3).map("\n".join)


@st.composite
def projects(draw):  # type: ignore[no-untyped-def]
    n_sys = draw(st.integers(1, 3))
    n_eps = draw(st.integers(0, 3))
    sys_items = [
        {"text": draw(_multiline), "title": draw(_value), "owner": draw(_value), "rationale": draw(_multiline)}
        for _ in range(n_sys)
    ]
    eps_items = [
        {
            "text": draw(_multiline), "title": draw(_value), "source": draw(_value),
            "parents": sorted(draw(st.sets(st.integers(1, n_sys), min_size=1, max_size=n_sys))),
            "sat": sorted(draw(st.sets(st.integers(1, n_sys), max_size=n_sys))),
        }
        for _ in range(n_eps)
    ]  # fmt: skip
    return sys_items, eps_items


def _build(root: Path, spec) -> DoorstopProject:  # type: ignore[no-untyped-def]
    sys_items, eps_items = spec
    proj = create_project(root, "P", DOCS)
    for it in sys_items:
        proj.add_item(
            "SYS",
            it["text"],
            attrs={"title": it["title"], "type": "functional", "owner": it["owner"], "rationale": it["rationale"]},
        )
    for it in eps_items:
        item = proj.add_item("EPS", it["text"], attrs={"title": it["title"], "type": "design", "source": it["source"],
                                                       "link_satisfies": [f"SYS-{n:04d}" for n in it["sat"]]})  # fmt: skip
        for n in it["parents"]:
            proj.link(item.uid, f"SYS-{n:04d}")
    return proj


def _files(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".rvs-cache" not in p.parts and "history" not in p.parts
    }


def _export(root: Path, fmt: str) -> bytes:
    cfg, _ = load_project_config(root)
    items = DoorstopProject.open(root).items()
    return export_items_csv(cfg, items, PROV) if fmt == "csv" else export_items_xlsx(cfg, items, PROV)


def _read(data: bytes, fmt: str):  # type: ignore[no-untyped-def]
    return read_csv(data) if fmt == "csv" else read_xlsx(data)


def _plan(root: Path, rows):  # type: ignore[no-untyped-def]
    cfg, _ = load_project_config(root)
    return plan_import(cfg, DoorstopProject.open(root).items(), rows)


COMMON = dict(max_examples=12, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@settings(**COMMON)
@given(spec=projects(), fmt=st.sampled_from(["csv", "xlsx"]))
def test_reimporting_an_export_changes_nothing(spec, fmt: str):  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "p"
        _build(root, spec)
        before = _files(root)
        plan = _plan(root, _read(_export(root, fmt), fmt))
        assert not plan.errors, [e.message for e in plan.errors]
        assert {r.action for r in plan.results} == {"unchanged"}
        apply_import(root, plan, user="a", why="")
        assert _files(root) == before


@settings(**COMMON)
@given(spec=projects(), fmt=st.sampled_from(["csv", "xlsx"]))
def test_import_into_an_empty_project_reproduces_the_export(spec, fmt: str):  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a", Path(d) / "b"
        _build(a, spec)
        exported = _export(a, fmt)
        create_project(b, "P", DOCS)
        plan = _plan(b, _read(exported, fmt))
        assert not plan.errors, [e.message for e in plan.errors]
        apply_import(b, plan, user="a", why="")
        assert _read(_export(b, fmt), fmt) == _read(exported, fmt)


@settings(**COMMON)
@given(spec=projects())
def test_exports_are_byte_identical_when_regenerated(spec):  # type: ignore[no-untyped-def]
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "p"
        _build(root, spec)
        for fmt in ("csv", "xlsx"):
            assert _export(root, fmt) == _export(root, fmt)
