"""Per-user preferences (mode, recent projects, shortcut overrides). Never project content; never raises."""

import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {"mode": "guided", "recent": [], "shortcuts": {}, "geometry": "", "theme": "light"}
MAX_RECENT = 8


def config_dir() -> Path:
    override = os.environ.get("RVS_CONFIG_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "rvs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "rvs"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "rvs"


def _path() -> Path:
    return config_dir() / "settings.json"


def load() -> dict[str, Any]:
    data = dict(DEFAULTS)
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update({k: v for k, v in raw.items() if k in DEFAULTS})
    except (OSError, ValueError, RecursionError):
        pass
    if data["mode"] not in ("guided", "expert"):
        data["mode"] = "guided"
    if data["theme"] not in ("light", "dark", "system"):
        data["theme"] = "light"
    if not isinstance(data["geometry"], str) or not data["geometry"].isascii():
        data["geometry"] = ""
    shortcuts = data["shortcuts"]
    data["shortcuts"] = (
        {k: v for k, v in shortcuts.items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(shortcuts, dict)
        else {}
    )
    recent = data["recent"]
    data["recent"] = [p for p in recent if isinstance(p, str) and p] if isinstance(recent, list) else []
    return data


def save(data: dict[str, Any]) -> None:
    try:
        folder = config_dir()
        folder.mkdir(parents=True, exist_ok=True)
        merged = {k: v for k, v in {**DEFAULTS, **data}.items() if k in DEFAULTS}
        _path().write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
    except OSError:
        pass  # preferences are a convenience


def update(**changes: Any) -> None:
    save({**load(), **changes})


def add_recent(project: Path) -> None:
    recent = [str(project)] + [p for p in load()["recent"] if p != str(project)]
    update(recent=recent[:MAX_RECENT])


def recent_projects() -> list[Path]:
    return [Path(p) for p in load()["recent"]]


def set_shortcut(action: str, key: str) -> None:
    shortcuts = dict(load()["shortcuts"])
    shortcuts[action] = key
    update(shortcuts=shortcuts)
