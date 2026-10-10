import json
from pathlib import Path

from rvs_cli.main import main


def _run(capsys, *argv: str) -> tuple[int, str]:  # type: ignore[no-untyped-def]
    capsys.readouterr()
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_cr_lifecycle(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    p = str(minimal_project)
    code, out = _run(capsys, "cr", "new", p, "Change the bus", "-d", "28 V", "--item", "EPS-0001", "--user", "alice")
    assert code == 0 and "CR-0001" in out
    code, out = _run(capsys, "cr", "list", p)
    assert code == 0 and "CR-0001" in out and "open" in out and "Change the bus" in out
    code, out = _run(capsys, "cr", "status", p, "CR-0001", "in-review", "--note", "ok", "--user", "bob")
    assert code == 0 and "in-review" in out
    code, out = _run(capsys, "cr", "show", p, "CR-0001")
    assert code == 0 and "EPS-0001" in out and "bob" in out and "in-review" in out
    assert main(["cr", "status", p, "CR-0001", "finished"]) == 2
    assert main(["cr", "show", p, "CR-0099"]) == 2
    assert main(["cr", "defer", p, "CR-0001", "--reason", ""]) == 2
    assert main(["cr", "defer", p, "CR-0001", "--reason", "after PDR"]) == 0


def test_baseline_create_list_verify(git_project: Path, capsys):  # type: ignore[no-untyped-def]
    p = str(git_project)
    code, out = _run(capsys, "baseline", "create", p, "PDR", "-m", "Preliminary design review", "--user", "alice")
    assert code == 0 and "PDR" in out and "10 items" in out
    code, out = _run(capsys, "baseline", "list", p)
    assert code == 0 and "PDR" in out and "alice" in out and "Preliminary design review" in out
    code, out = _run(capsys, "baseline", "list", p, "--format", "json")
    data = json.loads(out)
    assert data[0]["name"] == "PDR" and len(data[0]["commit"]) == 40
    code, out = _run(capsys, "baseline", "verify", p, "PDR")
    assert code == 0 and "intact" in out
    path = git_project / "baselines" / "PDR.yaml"
    path.write_text(path.read_text() + "# tampered\n")
    code, out = _run(capsys, "baseline", "verify", p, "PDR")
    assert code == 1 and "RVS-BASELINE-MODIFIED" in out


def test_baseline_blocked_by_open_change_requests_then_deferred(git_project: Path, capsys):  # type: ignore[no-untyped-def]
    p = str(git_project)
    main(["cr", "new", p, "Open one", "--user", "a"])
    code, out = _run(capsys, "baseline", "create", p, "PDR", "-m", "d")
    assert code == 1 and "CR-0001" in out and "defer" in out.lower()
    code, out = _run(capsys, "baseline", "create", p, "PDR", "-m", "d", "--defer", "CR-0001=after PDR")
    assert code == 0 and "deferred" in out.lower()


def test_baseline_without_git_explains_and_init_git_fixes_it(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    p = str(minimal_project)
    capsys.readouterr()
    assert main(["baseline", "create", p, "PDR", "-m", "d"]) == 2
    assert "Git repository" in capsys.readouterr().err
    assert main(["baseline", "create", p, "PDR", "-m", "d", "--init-git"]) == 0


def test_baseline_name_errors_exit_two(git_project: Path):
    assert main(["baseline", "create", str(git_project), "bad name", "-m", "d"]) == 2
    assert main(["baseline", "verify", str(git_project), "NOPE"]) == 2


def test_diff_between_baseline_and_working_copy(git_project: Path, capsys, tmp_path: Path):  # type: ignore[no-untyped-def]
    from rvs_core.authoring import EditService

    p = str(git_project)
    main(["baseline", "create", p, "PDR", "-m", "d", "--user", "alice"])
    EditService(git_project, user="bob").update_item(
        "SYS-0001", text="The spacecraft shall provide regulated power to all payloads.", why="x"
    )
    code, out = _run(capsys, "diff", p, "PDR", "working")
    assert code == 0 and "1 changed" in out and "SYS-0001" in out and "[-electrical-]" in out and "{+regulated+}" in out
    code, out = _run(capsys, "diff", p, "PDR", "PDR")
    assert code == 0 and "0 changed" in out
    code, out = _run(capsys, "diff", p, "PDR", "working", "--format", "json")
    data = json.loads(out)
    assert data["summary"] == {"added": 0, "removed": 0, "changed": 1} and data["changes"][0]["uid"] == "SYS-0001"
    for fmt in ("html", "docx", "pdf", "csv"):
        target = tmp_path / f"d.{fmt}"
        assert (
            main(["diff", p, "PDR", "working", "--format", fmt, "-o", str(target)]) == 0 and target.stat().st_size > 50
        )
    assert main(["diff", p, "PDR", "working", "--document", "EPS"]) == 0
    assert main(["diff", p, "NOPE", "working"]) == 2


def test_export_from_a_baseline_carries_its_name(git_project: Path, tmp_path: Path):
    from rvs_core.authoring import EditService

    p = str(git_project)
    main(["baseline", "create", p, "PDR", "-m", "d", "--user", "alice"])
    EditService(git_project, user="bob").update_item("SYS-0001", attrs={"title": "Changed after PDR"}, why="x")
    out = tmp_path / "vcm.csv"
    assert main(["export", p, "--vcm", "--baseline", "PDR", "-o", str(out)]) == 0
    text = out.read_text("utf-8")
    assert "Baseline: PDR" in text and "Changed after PDR" not in text and "Payload power" in text
    now = tmp_path / "now.csv"
    assert main(["export", p, "--vcm", "-o", str(now)]) == 0
    assert "Changed after PDR" in now.read_text("utf-8") and "latest baseline: PDR" in now.read_text("utf-8")


def test_import_can_be_attributed_to_a_change_request(git_project: Path, tmp_path: Path):
    from rvs_core.authoring import read_history

    p = str(git_project)
    main(["cr", "new", p, "Retitle", "--user", "a"])
    csv_file = tmp_path / "items.csv"
    main(["export", p, "--items", "-o", str(csv_file)])
    csv_file.write_text(csv_file.read_text("utf-8-sig").replace("Payload power", "Payload power v2"), encoding="utf-8")
    assert main(["import", p, str(csv_file), "--cr", "CR-0001", "--reason", "r", "--user", "bob"]) == 0
    assert read_history(git_project, "SYS-0001")[-1]["cr"] == "CR-0001"
    assert main(["import", p, str(csv_file), "--cr", "CR-0099"]) == 2
