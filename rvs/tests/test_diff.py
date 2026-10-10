import io
from datetime import datetime
from pathlib import Path

import pytest

from rvs_core.adapter import DoorstopProject
from rvs_core.authoring import EditService
from rvs_core.changecontrol.baselines import create_baseline
from rvs_core.changecontrol.diff import diff_snapshots, load_snapshot, text_segments
from rvs_core.matrices import Provenance

PROV = Provenance("0.1.0", "3.2", "Minimal example", "PDR vs working copy", datetime(2026, 1, 2, 3, 4, 5), "alice")


# word-level segments -----------------------------------------------------------------------------------
def test_text_segments_mark_inserted_and_deleted_words():
    segs = text_segments("The system shall provide power.", "The system shall provide regulated power.")
    assert [(op, t) for op, t in segs if op != "equal"] == [("insert", "regulated ")]
    assert "".join(t for op, t in segs if op != "insert") == "The system shall provide power."
    assert "".join(t for op, t in segs if op != "delete") == "The system shall provide regulated power."


def test_text_segments_for_replacements_and_identical_text():
    segs = text_segments("mass 50 kg", "mass 60 kg")
    assert [(op, t) for op, t in segs if op != "equal"] == [("delete", "50"), ("insert", "60")]
    assert text_segments("same", "same") == [("equal", "same")]
    assert text_segments("", "new") == [("insert", "new")]
    assert text_segments("old", "") == [("delete", "old")]


# snapshots and diffs ---------------------------------------------------------------------------------------
def test_working_copy_vs_baseline(git_project: Path):
    create_baseline(git_project, "PDR", "d", user="alice")
    svc = EditService(git_project, user="bob")
    svc.update_item(
        "SYS-0001", text="The spacecraft shall provide regulated power.", attrs={"owner": "power"}, why="clarify"
    )
    svc.create_item(
        "EPS", "The EPS shall be new.", attrs={"title": "New", "type": "functional"}, parents=["SYS-0001"], why="x"
    )
    base, work = load_snapshot(git_project, "PDR"), load_snapshot(git_project, None)
    diff = diff_snapshots(base, work)
    assert (diff.added, diff.removed, diff.changed) == (1, 0, 1)
    changed = next(c for c in diff.changes if c.kind == "changed")
    assert changed.uid == "SYS-0001" and {f.name for f in changed.fields} == {"text", "owner"}
    text = next(f for f in changed.fields if f.name == "text")
    assert (
        ("insert", "regulated") in text.segments
        and ("delete", "electrical") in text.segments
        and text.before.startswith("The spacecraft shall provide electrical")
    )
    added = next(c for c in diff.changes if c.kind == "added")
    assert added.uid == "EPS-0004" and added.after is not None and added.before is None
    assert diff.left == "PDR" and diff.right == "working copy"


def test_removed_items_and_documents(git_project: Path):
    import shutil

    create_baseline(git_project, "PDR", "d", user="alice")
    (git_project / "EPS" / "EPS-0003.yml").unlink()
    shutil.rmtree(git_project / "VER")
    diff = diff_snapshots(load_snapshot(git_project, "PDR"), load_snapshot(git_project, None))
    assert {c.uid for c in diff.changes if c.kind == "removed"} == {"EPS-0003", "VER-0001", "VER-0002", "VER-0003"}
    assert diff.removed == 4


def test_baseline_vs_baseline_and_unchanged_items_are_not_listed(git_project: Path):
    create_baseline(git_project, "A", "d", user="alice")
    EditService(git_project, user="bob").update_item("SYS-0002", attrs={"title": "Eclipse operation (rev B)"}, why="x")
    create_baseline(git_project, "B", "d", user="alice")
    diff = diff_snapshots(load_snapshot(git_project, "A"), load_snapshot(git_project, "B"))
    assert [(c.uid, c.kind) for c in diff.changes] == [("SYS-0002", "changed")] and diff.changed == 1
    same = diff_snapshots(load_snapshot(git_project, "B"), load_snapshot(git_project, "B"))
    assert same.changes == () and (same.added, same.removed, same.changed) == (0, 0, 0)


def test_reviews_stamps_and_links_stamps_are_not_changes(git_project: Path):
    create_baseline(git_project, "A", "d", user="alice")
    proj = DoorstopProject.open(git_project)
    proj.review_item("SYS-0001")
    proj.clear_suspect("EPS-0001")
    assert diff_snapshots(load_snapshot(git_project, "A"), load_snapshot(git_project, None)).changes == ()


def test_parents_links_and_flags_are_compared(git_project: Path):
    create_baseline(git_project, "A", "d", user="alice")
    svc = EditService(git_project, user="bob")
    svc.set_parents("EPS-0001", ["SYS-0001"], why="x")
    svc.update_item("EPS-0002", attrs={"link_satisfies": ["SYS-0001"]}, why="x")
    DoorstopProject.open(git_project).update_item("EPS-0003", normative=False)
    diff = diff_snapshots(load_snapshot(git_project, "A"), load_snapshot(git_project, None))
    by = {c.uid: {f.name for f in c.fields} for c in diff.changes}
    assert by == {"EPS-0001": {"parents"}, "EPS-0002": {"link_satisfies"}, "EPS-0003": {"normative"}}


def test_diff_can_be_limited_to_a_document_or_item(git_project: Path):
    create_baseline(git_project, "A", "d", user="alice")
    svc = EditService(git_project, user="bob")
    svc.update_item("SYS-0001", attrs={"owner": "a"}, why="x")
    svc.update_item("EPS-0001", attrs={"owner": "b"}, why="x")
    diff = diff_snapshots(load_snapshot(git_project, "A"), load_snapshot(git_project, None))
    assert {c.uid for c in diff.for_document("EPS")} == {"EPS-0001"}
    assert diff.for_item("SYS-0001") is not None and diff.for_item("SYS-0002") is None


def test_snapshot_uses_the_configuration_of_that_time(git_project: Path):
    create_baseline(git_project, "A", "d", user="alice")
    (git_project / "config" / "vocab.yaml").write_text(
        (git_project / "config" / "vocab.yaml").read_text().replace("obsolete", "retired")
    )
    old = load_snapshot(git_project, "A")
    assert "obsolete" in old.cfg.vocab.values("status") and "retired" in load_snapshot(
        git_project, None
    ).cfg.vocab.values("status")


def test_unknown_baseline(git_project: Path):
    from rvs_core.changecontrol.baselines import BaselineError

    with pytest.raises(BaselineError, match="NOPE"):
        load_snapshot(git_project, "NOPE")


def test_extracted_snapshots_live_inside_the_project_and_are_reused(git_project: Path):
    create_baseline(git_project, "A", "d", user="alice")
    s1 = load_snapshot(git_project, "A")
    s2 = load_snapshot(git_project, "A")
    assert s1.items == s2.items
    assert (git_project / ".rvs-cache" / "snapshots").is_dir()
    committed = GitCheck.names(git_project)
    assert not any(".rvs-cache" in n for n in committed)


class GitCheck:
    @staticmethod
    def names(root: Path) -> list[str]:
        from rvs_core.vcs.git import GitRepo

        repo = GitRepo.discover(root)
        head = repo.head()
        assert head
        return list(repo.read_tree(head, root))


# rendering ----------------------------------------------------------------------------------------------------
def _diff(git_project: Path):  # type: ignore[no-untyped-def]
    create_baseline(git_project, "PDR", "d", user="alice")
    svc = EditService(git_project, user="bob")
    svc.update_item("SYS-0001", text="The spacecraft shall provide regulated <power> & more.", why="x")
    svc.update_item("EPS-0002", attrs={"status": "approved"}, why="x")
    return diff_snapshots(load_snapshot(git_project, "PDR"), load_snapshot(git_project, None))


def test_diff_document_renders_in_html_docx_and_pdf(git_project: Path):
    from rvs_core.changecontrol.diff import diff_doc
    from rvs_core.exporters import render_doc

    doc = diff_doc(_diff(git_project), PROV)
    html = render_doc(doc, "html").decode("utf-8")
    assert "<ins>regulated" in html and "<del>" in html and "&lt;power&gt;" in html and "<script" not in html
    assert "SYS-0001" in html and "EPS-0002" in html and "Changed: 2" in html
    from docx import Document

    paragraphs = "\n".join(p.text for p in Document(io.BytesIO(render_doc(doc, "docx"))).paragraphs)
    assert "SYS-0001" in paragraphs
    from pypdf import PdfReader

    text = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(render_doc(doc, "pdf"))).pages)
    assert "SYS-0001" in text and "regulated" in text


def test_diff_table_summarises_changes(git_project: Path):
    from rvs_core.changecontrol.diff import diff_table

    t = diff_table(_diff(git_project), PROV)
    assert t.columns == ["Item", "Change", "Title", "Fields"]
    assert {r[0]: (r[1], r[3]) for r in t.rows} == {"EPS-0002": ("changed", "status"), "SYS-0001": ("changed", "text")}
