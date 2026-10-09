import csv
import io
import json
import subprocess
import sys
from pathlib import Path

from rvs_cli.main import main


def _run(capsys, *argv: str) -> tuple[int, str]:  # type: ignore[no-untyped-def]
    code = main(list(argv))
    return code, capsys.readouterr().out


def _csv_rows(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    rows = list(csv.reader(io.StringIO("\n".join(lines))))
    return rows[0], rows[1:]


def test_vcm_csv_with_provenance_header(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    code, out = _run(capsys, "export", str(minimal_project), "--vcm")
    assert code == 0
    comments = [ln for ln in out.splitlines() if ln.startswith("#")]
    assert any("Project: Minimal example" in c for c in comments) and any("Generated:" in c for c in comments)
    assert any("TODO-STANDARD" in c for c in comments)
    header, rows = _csv_rows(out)
    assert header[0] == "Requirement" and len(rows) == 6
    assert rows[3][:2] == ["EPS-0001", "Battery capacity"]


def test_vcm_filters_on_the_command_line(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    _, out = _run(capsys, "export", str(minimal_project), "--vcm", "--document", "EPS", "--method", "analysis")
    _, rows = _csv_rows(out)
    assert [r[0] for r in rows] == ["EPS-0001"]
    _, out = _run(capsys, "export", str(minimal_project), "--vcm", "--only-gaps")
    _, rows = _csv_rows(out)
    assert {r[0] for r in rows} == {"SYS-0001", "SYS-0002", "SYS-0003"}


def test_vcm_json(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    code, out = _run(capsys, "export", str(minimal_project), "--vcm", "--format", "json")
    data = json.loads(out)
    assert code == 0 and data["title"] == "Verification control matrix"
    assert len(data["rows"]) == 6 and data["provenance"]["project"] == "Minimal example"
    assert data["provenance"]["user"] and data["notes"]


def test_trace_matrix(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    code, out = _run(capsys, "export", str(minimal_project), "--trace", "SYS:EPS")
    header, rows = _csv_rows(out)
    assert code == 0 and "Linked items" in header
    assert {r[0]: r[2] for r in rows}["SYS-0002"] == "EPS-0001"
    _, out = _run(capsys, "export", str(minimal_project), "--trace", "EPS:SYS:up")
    _, rows = _csv_rows(out)
    assert {r[0]: r[2] for r in rows}["EPS-0001"] == "SYS-0002"


def test_coverage_and_impact(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    code, out = _run(capsys, "export", str(minimal_project), "--coverage")
    header, rows = _csv_rows(out)
    assert code == 0 and header[:3] == ["Document", "Title", "Items"] and [r[0] for r in rows] == ["SYS", "EPS", "VER"]
    code, out = _run(capsys, "export", str(minimal_project), "--impact", "SYS-0002")
    header, rows = _csv_rows(out)
    assert [r[0] for r in rows] == ["EPS-0001", "VER-0001"] and header[:3] == ["Item", "Depth", "Via"]


def test_output_file(minimal_project: Path, tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    target = tmp_path / "vcm.csv"
    code, out = _run(capsys, "export", str(minimal_project), "--vcm", "--output", str(target))
    assert code == 0 and out == "" and target.read_text(encoding="utf-8").startswith("# ")


def test_friendly_errors_exit_two_without_traceback(minimal_project: Path):
    for args in (["--trace", "NOPE:SYS"], ["--impact", "SYS-9999"], ["--trace", "SYS"]):
        out = subprocess.run(
            [sys.executable, "-m", "rvs_cli", "export", str(minimal_project), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        assert out.returncode == 2 and "Traceback" not in out.stderr and out.stderr.strip()


def test_export_of_unloadable_project_exits_three(tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    code, _ = _run(capsys, "export", str(tmp_path), "--vcm")
    assert code == 3
