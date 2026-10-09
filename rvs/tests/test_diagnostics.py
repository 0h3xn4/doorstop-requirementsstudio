import sys
from pathlib import Path

from rvs_cli.main import main
from rvs_core import diagnostics


def test_crash_report_has_frames_but_never_messages_or_values():
    secret = "TOP-SECRET requirement text SYS-0042"

    def boom() -> None:
        local_value = secret  # noqa: F841 - must never appear in the report
        raise ValueError(f"cannot save {secret}")

    try:
        boom()
    except ValueError:
        report = diagnostics.crash_report(*sys.exc_info())
    assert "ValueError" in report and "boom" in report and "test_diagnostics.py" in report
    assert "TOP-SECRET" not in report and "SYS-0042" not in report and "cannot save" not in report
    assert "rvs " in report  # tool version


def test_crash_report_is_written_to_the_user_folder_not_the_project(tmp_path: Path):
    try:
        raise RuntimeError("x")
    except RuntimeError:
        path = diagnostics.save_crash_report(*sys.exc_info())
    assert path is not None and path.parent.name == "crash" and path.read_text().startswith("RVS crash report")


def test_selftest_passes_and_lists_every_check(capsys):  # type: ignore[no-untyped-def]
    results = diagnostics.selftest()
    names = {r.name for r in results}
    assert {
        "configuration defaults and schemas",
        "fonts",
        "DOCX export",
        "PDF export",
        "XLSX export",
        "baseline (Git)",
        "offline guard",
    } <= names
    assert all(r.ok for r in results), [r for r in results if not r.ok]
    assert main(["selftest"]) == 0
    out = capsys.readouterr().out
    assert "PDF export" in out and "all checks passed" in out.lower()


def test_selftest_leaves_nothing_behind(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    diagnostics.selftest()
    assert list(tmp_path.iterdir()) == []


def test_manifest_verification(tmp_path: Path):
    (tmp_path / "a.txt").write_text("alpha")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("beta")
    diagnostics.write_manifest(tmp_path)
    assert diagnostics.verify_manifest(tmp_path) == []
    (tmp_path / "a.txt").write_text("ALPHA")
    (tmp_path / "sub" / "b.txt").unlink()
    (tmp_path / "extra.txt").write_text("new")
    problems = diagnostics.verify_manifest(tmp_path)
    assert any("a.txt" in p and "changed" in p for p in problems)
    assert any("b.txt" in p and "missing" in p for p in problems)
    assert any("extra.txt" in p and "unexpected" in p for p in problems)
    assert main(["selftest", "--manifest", str(tmp_path)]) == 1
