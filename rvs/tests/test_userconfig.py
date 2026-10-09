import json
from pathlib import Path

import pytest

from rvs_core import userconfig


def test_config_dir_honours_the_override_and_platform_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("RVS_CONFIG_DIR", str(tmp_path / "x"))
    assert userconfig.config_dir() == tmp_path / "x"
    monkeypatch.delenv("RVS_CONFIG_DIR")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr("sys.platform", "linux")
    assert userconfig.config_dir() == tmp_path / "xdg" / "rvs"
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    assert userconfig.config_dir() == tmp_path / "appdata" / "rvs"


def test_settings_round_trip_and_defaults():
    assert userconfig.load()["mode"] == "guided"  # first run: guided
    userconfig.save({"mode": "expert"})
    assert userconfig.load()["mode"] == "expert"


def test_corrupt_or_unwritable_settings_never_raise(monkeypatch: pytest.MonkeyPatch):
    userconfig.save({"mode": "expert"})
    (userconfig.config_dir() / "settings.json").write_text("{ not json")
    assert userconfig.load()["mode"] == "guided"
    monkeypatch.setenv("RVS_CONFIG_DIR", "/proc/definitely/not/writable")
    userconfig.save({"mode": "expert"})  # silently ignored


def test_settings_hold_no_project_content():
    userconfig.add_recent(Path("/work/projects/sat"))
    data = json.loads((userconfig.config_dir() / "settings.json").read_text())
    assert set(data) <= {"mode", "recent", "shortcuts", "geometry"}


def test_recent_projects_are_deduplicated_most_recent_first_and_limited():
    for n in range(12):
        userconfig.add_recent(Path(f"/p/{n}"))
    userconfig.add_recent(Path("/p/5"))
    recent = userconfig.recent_projects()
    assert recent[0] == Path("/p/5") and len(recent) == 8 and len(set(recent)) == 8


def test_shortcut_overrides_are_stored_per_action():
    userconfig.set_shortcut("export", "Ctrl+Shift+E")
    assert userconfig.load()["shortcuts"] == {"export": "Ctrl+Shift+E"}
