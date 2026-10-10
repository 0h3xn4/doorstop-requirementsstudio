import json
import subprocess
import sys
from pathlib import Path

import yaml

from rvs_cli.main import main


def test_validate_ok_exit_zero(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    assert main(["validate", str(minimal_project)]) == 0
    assert "0 errors" in capsys.readouterr().out


def test_validate_reports_errors_exit_one(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text().replace("status: draft", "status: finished"))
    assert main(["validate", str(minimal_project)]) == 1
    out = capsys.readouterr().out
    assert "SYS-0001" in out and "finished" in out


def test_validate_json_output(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    assert main(["validate", str(minimal_project), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["exit_code"] == 0 and isinstance(data["findings"], list)
    assert {"code", "severity", "message", "hint", "location", "uid"} <= set(data["findings"][0])


def test_strict_turns_warnings_into_failure(minimal_project: Path):
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text() + "mystery: 1\n")
    assert main(["validate", str(minimal_project)]) == 0
    assert main(["validate", str(minimal_project), "--strict"]) == 1


def test_newer_schema_exit_three_without_traceback(minimal_project: Path):
    p = minimal_project / "rvs-project.yaml"
    data = yaml.safe_load(p.read_text())
    data["rvs_schema_version"] = 99
    p.write_text(yaml.safe_dump(data))
    out = subprocess.run([sys.executable, "-m", "rvs_cli", "validate", str(minimal_project)],
                         capture_output=True, text=True, check=False)  # fmt: skip
    assert out.returncode == 3
    assert "Traceback" not in out.stdout + out.stderr


def test_validate_does_not_log_item_content(minimal_project: Path, caplog):  # type: ignore[no-untyped-def]
    import logging

    caplog.set_level(logging.DEBUG)
    main(["validate", str(minimal_project)])
    secret = "shall"  # every requirement statement contains it
    assert secret not in caplog.text
