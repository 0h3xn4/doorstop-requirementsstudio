"""Tests for behaviour that mutation probes in the full audit showed to be unprotected: each test fails when the guarded
line is removed or inverted. Grouped by area; the ID in the docstring is the audit's mutation ID."""

import io
import os
import re
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.authoring import EditService, read_history
from rvs_core.changecontrol.baselines import BaselineError, create_baseline, item_digest, snapshot_dir, verify_baseline
from rvs_core.changecontrol.changes import ChangeRequestError, ChangeRequestStore
from rvs_core.config import load_project_config
from rvs_core.matrices import VcmFilter, build_traceability, build_vcm
from rvs_core.matrices.provenance import Provenance
from rvs_core.rules import build_context, run_rules
from rvs_core.schema.versioning import SchemaVersionError, migrate
from rvs_core.trace import LinkGraph
from rvs_core.trace.coverage import coverage
from rvs_core.validate import validate_project
from rvs_core.vcs.git import GitRepo

PROV = Provenance("0", "3.2", "P", "working copy", datetime(2026, 1, 2, 3, 4, 5), "alice")


def _codes(root: Path) -> list[str]:
    return [f.code for f in validate_project(root, doorstop=False).findings]


def _ctx(root: Path) -> tuple[Any, list[Any], Any]:
    cfg, _ = load_project_config(root)
    items = DoorstopProject.open(root).items()
    return cfg, items, LinkGraph.build(cfg, items)


# baselines ----------------------------------------------------------------------------------------------------------------------------
def test_B03_B14_deferrals_need_a_reason_and_an_open_request(git_project: Path):
    cfg, _ = load_project_config(git_project)
    cr = ChangeRequestStore(git_project, cfg).create("c", "", "a")
    with pytest.raises(BaselineError, match="needs a reason"):
        create_baseline(git_project, "X1", "x", user="a", defer={cr.id: "  "})
    with pytest.raises(BaselineError, match="not an open change request"):
        create_baseline(git_project, "X1", "x", user="a", defer={"CR-0099": "why"})


@pytest.mark.parametrize("name", ["a..b", "v1.", "v1.lock"])
def test_B13_names_git_cannot_hold_say_why(git_project: Path, name: str):
    with pytest.raises(BaselineError, match="Git does not allow"):
        create_baseline(git_project, name, "x", user="a")


def test_B08_the_statement_is_part_of_an_items_digest(minimal_project: Path):
    item = DoorstopProject.open(minimal_project).get_item("SYS-0001")
    assert item_digest(item) != item_digest(replace(item, text=item.text + " Changed."))
    assert item_digest(item) == item_digest(
        replace(item, text=item.text + "\n\n")
    )  # trailing blank space is not content


def test_B06_a_snapshot_path_that_leaves_the_folder_is_refused(git_project: Path, monkeypatch):  # type: ignore[no-untyped-def]
    create_baseline(git_project, "S1", "x", user="a")
    monkeypatch.setattr(GitRepo, "read_tree", lambda *_a, **_k: {"../escape.txt": b"x"})
    with pytest.raises(BaselineError, match="leaves the snapshot folder"):
        snapshot_dir(git_project, "S1")
    assert not (git_project.parent / "escape.txt").exists()


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need a privilege on Windows")
def test_B07_a_symlinked_snapshot_cache_is_refused(git_project: Path, tmp_path: Path):
    create_baseline(git_project, "S2", "x", user="a")
    cache = git_project / ".rvs-cache"
    cache.mkdir(exist_ok=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (cache / "snapshots").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(BaselineError, match="symbolic link"):
        snapshot_dir(git_project, "S2")
    assert list(elsewhere.iterdir()) == []


def test_B16_a_tagged_tree_that_differs_from_its_manifest_is_corrupt(git_project: Path, monkeypatch):  # type: ignore[no-untyped-def]
    from rvs_core.changecontrol import diff

    create_baseline(git_project, "V1", "x", user="a")
    real = diff.load_snapshot

    def tampered(root: Path, name: str):  # type: ignore[no-untyped-def]
        snap = real(root, name)
        first = sorted(snap.items)[0]
        snap.items[first] = replace(snap.items[first], text="something else entirely")
        return snap

    monkeypatch.setattr(diff, "load_snapshot", tampered)
    assert [f.code for f in verify_baseline(git_project, "V1")] == ["RVS-BASELINE-CORRUPT"]


def test_B17_B18_a_missing_tag_is_reported_and_blocks_snapshots(git_project: Path):
    create_baseline(git_project, "N1", "x", user="a")
    repo = GitRepo.discover(git_project)
    del repo._refs[b"refs/tags/rvs/baseline/N1"]
    assert [f.code for f in verify_baseline(git_project, "N1")] == ["RVS-BASELINE-NOTAG"]
    with pytest.raises(BaselineError, match="tag of baseline 'N1' is missing"):
        snapshot_dir(git_project, "N1")


def test_K03_an_approved_change_request_blocks_a_baseline(git_project: Path):
    cfg, _ = load_project_config(git_project)
    store = ChangeRequestStore(git_project, cfg)
    cr = store.create("c", "", "a")
    store.set_status(cr.id, "approved", "a")
    with pytest.raises(BaselineError, match="change requests are open"):
        create_baseline(git_project, "K1", "x", user="a")


def test_D04_D05_stored_files_have_sorted_keys(git_project: Path):
    cfg, _ = load_project_config(git_project)
    store = ChangeRequestStore(git_project, cfg)
    store.set_status(store.create("c", "d", "a").id, "closed", "a")
    create_baseline(git_project, "D1", "x", user="a")
    for rel in ("changes/CR-0001.yaml", "baselines/D1.yaml"):
        keys = list(yaml.safe_load((git_project / rel).read_text()))
        assert keys == sorted(keys), rel


# change requests -----------------------------------------------------------------------------------------------------------------------
def test_C02_C05_C08_change_request_numbers_ids_and_titles(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    store = ChangeRequestStore(minimal_project, cfg)
    store.create("one", "", "a")
    store.create("two", "", "a")
    (minimal_project / "changes" / "CR-0001.yaml").unlink()
    assert store.create("three", "", "a").id == "CR-0003"  # the highest number plus one, not the count plus one
    with pytest.raises(ChangeRequestError, match="not a change request ID"):
        store.get("../../etc/passwd")
    with pytest.raises(ChangeRequestError, match="needs a title"):
        store.create("   ", "", "a")


# editing -------------------------------------------------------------------------------------------------------------------------------
def test_A10_A15_A16_changes_that_change_nothing_leave_no_history(minimal_project: Path):
    svc = EditService(minimal_project, user="u")
    before = len(read_history(minimal_project, "SYS-0001"))
    owner = DoorstopProject.open(minimal_project).get_item("SYS-0001").attrs.get("owner")
    svc.update_item("SYS-0001", attrs={"owner": owner})
    parents = DoorstopProject.open(minimal_project).get_item("SYS-0001").links
    svc.set_parents("SYS-0001", list(parents))
    svc.clear_suspect("SYS-0001")
    assert len(read_history(minimal_project, "SYS-0001")) == before


def test_A14_history_entries_carry_the_current_time(minimal_project: Path):
    EditService(minimal_project, user="u").update_item("SYS-0001", attrs={"owner": "someone new"})
    when = datetime.fromisoformat(read_history(minimal_project, "SYS-0001")[-1]["when"])
    assert abs(datetime.now().astimezone() - when) < timedelta(minutes=2)


# rules, matrices, validation ---------------------------------------------------------------------------------------------------------
def test_R07_V11_V18_inactive_items_are_ignored_by_rules_matrices_and_coverage(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    target = next(i for i in items if i.document == "SYS" and i.normative)
    gone = [
        replace(i, active=False, text="This is vague and has no keyword.") if i.uid == target.uid else i for i in items
    ]
    ctx = build_context(cfg, gone, DoorstopProject.open(minimal_project).documents())
    assert not [f for f in run_rules(ctx) if f.uid == target.uid]
    vcm = build_vcm(cfg, gone, LinkGraph.build(cfg, gone), VcmFilter(), provenance=PROV)
    assert target.uid not in {r[0] for r in vcm.rows}
    sys_row = next(r for r in coverage(cfg, gone, LinkGraph.build(cfg, gone)) if r.prefix == "SYS")
    assert sys_row.total == sum(1 for i in items if i.document == "SYS" and i.normative) - 1


def test_V16_derived_items_are_not_orphans(minimal_project: Path):
    cfg, items, graph = _ctx(minimal_project)
    child = next(i for i in items if i.document == "SYS" and i.normative and not i.links)
    items2 = [replace(i, derived=True) if i.uid == child.uid else i for i in items]
    t = (
        build_traceability(cfg, items2, LinkGraph.build(cfg, items2), "SYS", "MIS", "up", provenance=PROV)
        if any(d.prefix == "MIS" for d in cfg.project.documents)
        else build_traceability(cfg, items2, LinkGraph.build(cfg, items2), "EPS", "SYS", "up", provenance=PROV)
    )
    flagged = {r[0]: f for r, f in zip(t.rows, t.flags, strict=True)}
    assert flagged.get(child.uid) != "orphan"


def test_V04_V05_V23_required_and_typed_attributes_are_checked(minimal_project: Path):
    path = minimal_project / "VER" / "VER-0001.yml"
    data = yaml.safe_load(path.read_text())
    data.pop("verify_level", None)
    data["iterations"] = True
    data["nonconformances"] = [1, 2]
    path.write_text(yaml.safe_dump(data, sort_keys=True))
    codes = _codes(minimal_project)
    assert "RVS-ATTR-REQUIRED" in codes
    assert "RVS-ATTR-TYPE" in codes


def test_V25_V26_V27_document_and_project_problems(minimal_project: Path, tmp_path: Path):
    assert validate_project(tmp_path / "nowhere").exit_code == 3
    config = minimal_project / "EPS" / ".doorstop.yml"
    text = config.read_text()
    config.write_text(re.sub(r"parent: \w+", "parent: VER", text) if "parent:" in text else text + "  parent: VER\n")
    assert "RVS-DOC-PARENT" in _codes(minimal_project)


def test_V26_a_document_that_is_not_yaml_is_reported(minimal_project: Path):
    config = minimal_project / "VER" / ".doorstop.yml"
    config.write_text(config.read_text().replace("itemformat: yaml", "itemformat: markdown"))
    assert "RVS-DOC-FORMAT" in _codes(minimal_project)


def test_V19_V20_schema_versions():
    with pytest.raises(SchemaVersionError) as newer:
        migrate("item", {"rvs_schema_version": 2}, path="x.yml")  # one above the current version is already too new
    assert newer.value.code == "RVS-SCHEMA-NEWER"
    with pytest.raises(SchemaVersionError) as missing:
        migrate("item", {}, path="x.yml")
    assert missing.value.code == "RVS-SCHEMA-MISSING"


def test_K11_a_verification_item_needs_a_level(minimal_project: Path):
    cfg, _ = load_project_config(minimal_project)
    template = cfg.templates.kinds["verification"]
    assert next(a for a in template.attributes if a.name == "verify_level").required


# import / export -----------------------------------------------------------------------------------------------------------------------
def _plan(root: Path, rows: list[dict[str, str]]):  # type: ignore[no-untyped-def]
    from rvs_core.exporters.itemsio import plan_import

    cfg, items, _ = _ctx(root)
    return plan_import(cfg, items, rows, root=root)


def test_I03_a_new_item_must_be_numbered_above_the_highest(minimal_project: Path):
    from rvs_core.exporters.itemsio import plan_import

    cfg, items, _ = _ctx(minimal_project)
    numbers = sorted(int(i.uid.rsplit("-", 1)[1]) for i in items if i.document == "VER")
    gap = numbers[-2]  # absent from the list below, so a row for it looks new, but it is not above the highest
    listed = [i for i in items if i.uid != f"VER-{gap:04d}"]
    plan = plan_import(cfg, listed, [{"id": f"VER-{gap:04d}", "document": "VER", "text": "x", "_row": "2"}])
    assert plan.errors and "not above the highest" in plan.errors[0].message
    top = numbers[-1]
    ok = plan_import(cfg, items, [{"id": f"VER-{top + 1:04d}", "document": "VER", "text": "x", "_row": "2"}])
    assert not ok.errors


def test_I10_I22_unknown_columns_and_foreign_attributes_are_errors(minimal_project: Path):
    plan = _plan(minimal_project, [{"id": "SYS-0001", "not_a_column": "x", "_row": "2"}])
    assert plan.errors and "Unknown column" in plan.errors[0].message
    plan = _plan(minimal_project, [{"id": "SYS-0001", "document": "SYS", "proc_id": "P-1", "_row": "2"}])
    assert plan.errors, "a verification attribute on a requirement must be refused"


def test_I12_I19_dates_and_parent_ids_are_checked(minimal_project: Path):
    plan = _plan(minimal_project, [{"id": "VER-0001", "document": "VER", "executed_on": "yesterday", "_row": "2"}])
    assert plan.errors and "YYYY-MM-DD" in plan.errors[0].message
    plan = _plan(minimal_project, [{"id": "SYS-0001", "document": "SYS", "parents": "not an id", "_row": "2"}])
    assert plan.errors and "not an item ID" in plan.errors[0].message


def test_I09_every_reason_is_checked_before_the_first_write(git_project: Path):
    from rvs_core.authoring import ReasonRequiredError
    from rvs_core.exporters.itemsio import apply_import, plan_import

    create_baseline(git_project, "I1", "x", user="a")
    cfg, items, _ = _ctx(git_project)
    rows = [
        {"id": "SYS-0001", "document": "SYS", "text": "The spacecraft shall change one.", "_row": "2"},
        {"id": "SYS-0002", "document": "SYS", "text": "The spacecraft shall change two.", "_row": "3"},
    ]
    plan = plan_import(
        cfg, items, rows
    )  # planned without the baseline knowledge, so the reason check happens at apply time
    before = (git_project / "SYS" / "SYS-0001.yml").read_bytes()
    with pytest.raises(ReasonRequiredError):
        apply_import(git_project, plan, user="a", why="")
    assert (git_project / "SYS" / "SYS-0001.yml").read_bytes() == before


def test_I21_S16_spreadsheet_limits(monkeypatch):  # type: ignore[no-untyped-def]
    from openpyxl import Workbook

    from rvs_core.exporters import itemsio

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["id", "text"])
    for n in range(10):
        ws.append([f"SYS-{n + 1:04d}", "t"])
    buf = io.BytesIO()
    wb.save(buf)
    monkeypatch.setattr(itemsio, "MAX_XLSX_ROWS", 5)
    with pytest.raises(ValueError, match="more than"):
        itemsio.read_xlsx(buf.getvalue())
    monkeypatch.setattr(itemsio, "MAX_XLSX_ROWS", 200_000)
    monkeypatch.setattr(itemsio, "MAX_XLSX_BYTES", 100)
    with pytest.raises(ValueError, match="expands"):
        itemsio.read_xlsx(buf.getvalue())


# escaping ------------------------------------------------------------------------------------------------------------------------------
def test_S07_S08_html_escapes_titles_and_cells():
    from rvs_core.exporters.html_out import render_html
    from rvs_core.exporters.model import Doc, TableBlock

    doc = Doc(
        "<script>alert(1)</script>", PROV, [TableBlock(["<b>col</b>"], [["<img src=x onerror=alert(2)>"]], [None])]
    )
    out = render_html(doc).decode()
    assert "<script>alert" not in out and "<img src=x" not in out and "&lt;script&gt;" in out


def test_S09_pdf_markup_is_escaped():
    from rvs_core.exporters import pdf_out

    assert pdf_out._esc("<b>&</b>") == "&lt;b&gt;&amp;&lt;/b&gt;"


# environment ---------------------------------------------------------------------------------------------------------------------------
def test_S20_a_crash_report_hides_folder_names(tmp_path: Path):
    from rvs_core.diagnostics import crash_report

    folder = tmp_path / "secret-customer-project"
    folder.mkdir()
    module = folder / "mod.py"
    module.write_text("def boom():\n    raise RuntimeError('x')\n")
    namespace: dict[str, Any] = {}
    exec(compile(module.read_text(), str(module), "exec"), namespace)  # noqa: S102
    try:
        namespace["boom"]()
    except RuntimeError as exc:
        text = crash_report(type(exc), exc, exc.__traceback__)
    assert "secret-customer-project" not in text and "mod.py" in text


def test_G06_commit_identities_cannot_inject_headers(git_project: Path):
    repo = GitRepo.discover(git_project)
    who = repo._identity("evil <x@y>\nparent abc").decode()
    assert "\n" not in who and who.count("<") == 1 and who.count(">") == 1


def test_O14_O15_cache_version_and_doorstop_skip_marker(minimal_project: Path):
    from rvs_core.adapter import cache as cachemod

    DoorstopProject.open(minimal_project).items()
    time.sleep(2.2)
    for p in (minimal_project / "SYS").glob("*.yml"):
        os.utime(p, (1, 1))
    DoorstopProject.open(minimal_project).items()
    folder = minimal_project / ".rvs-cache"
    assert (folder / ".doorstop.skip-all").is_file() and (folder / ".gitignore").read_text() == "*\n"
    import json

    raw = json.loads((folder / "SYS.json").read_text())
    raw.pop("sig")
    raw["v"] = cachemod.CACHE_VERSION - 1
    raw["items"] = {}
    cache = cachemod.ItemCache(minimal_project)
    (folder / "SYS.json").write_text(
        json.dumps({**raw, "sig": cachemod.sign(json.dumps(raw, sort_keys=True, ensure_ascii=False))})
    )
    config = cachemod.stat_key(minimal_project / "SYS" / ".doorstop.yml")
    assert cache.load("SYS", config) == {}


# command line ----------------------------------------------------------------------------------------------------------------------------
def test_L03_L05_L06_import_and_export_argument_checks(minimal_project: Path, tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    import rvs_cli.main as cli

    assert cli.main(["export", str(minimal_project), "--vcm", "--format", "xlsx"]) == 2
    note = tmp_path / "items.txt"
    note.write_text("id,text\n")
    assert cli.main(["import", str(minimal_project), str(note)]) == 2
    bad = tmp_path / "bad.csv"
    bad.write_text("id,document,text\nSYS-0001,SYS,Changed text shall hold.\nNOPE-1,NOPE,x\n")
    assert cli.main(["import", str(minimal_project), str(bad), "--dry-run"]) == 1
    assert cli.main(["import", str(minimal_project), str(bad), "--skip-errors"]) == 1
    capsys.readouterr()


def test_an_unterminated_csv_quote_is_an_error_not_silent_data_loss():
    from rvs_core.exporters.itemsio import read_csv

    good = b'id,text\nSYS-0001,"fine"\nSYS-0002,5" pipe\n'
    assert [r["id"] for r in read_csv(good)] == ["SYS-0001", "SYS-0002"]
    with pytest.raises(ValueError, match="damaged"):
        read_csv(b'id,text\nSYS-0001,"never closed\nSYS-0002,second\nSYS-0003,third\n')
