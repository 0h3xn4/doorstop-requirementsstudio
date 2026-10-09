"""Property tests: arbitrary text/attribute values survive write -> reopen unchanged, and writing is deterministic."""

import tempfile
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rvs_core.adapter import DoorstopProject

# YAML-hostile on purpose: booleans, nulls, numbers, colons, hashes, leading/trailing spaces, unicode.
text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters="\x85  "), min_size=1, max_size=60
).filter(lambda s: s.strip() == s and s != "")
tricky = st.sampled_from(
    ["yes", "no", "null", "~", "1.0", "0x1F", ": x", "# c", "- a", "a: b", "'q'", '"d"', "é☃", "2024-01-01"]
)
values = st.one_of(text, tricky)


def _build(root: Path, title: str, body: str, owner: str) -> DoorstopProject:
    proj = DoorstopProject.create(root)
    proj.create_document("SYS", fingerprint=["title"])
    proj.add_item("SYS", f"The system shall {body}.", attrs={"title": title, "owner": owner})
    return proj


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(title=values, body=values, owner=values)
def test_attributes_and_text_round_trip(title: str, body: str, owner: str):
    with tempfile.TemporaryDirectory() as d:
        _build(Path(d) / "p", title, body, owner)
        item = DoorstopProject.open(Path(d) / "p").get_item("SYS-0001")
        assert item.attrs["title"] == title
        assert item.attrs["owner"] == owner
        assert item.text.strip() == f"The system shall {body}."


@settings(max_examples=25, deadline=None)
@given(title=values, body=values, owner=values)
def test_writing_same_content_twice_is_byte_identical(title: str, body: str, owner: str):
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a", Path(d) / "b"
        _build(a, title, body, owner)
        _build(b, title, body, owner)
        files = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        assert files == sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
        assert all((a / f).read_bytes() == (b / f).read_bytes() for f in files)
