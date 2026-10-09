"""Baseline manifests (``baselines/<name>.yaml``): small, import-light helpers shared by authoring and baselines."""

from pathlib import Path
from typing import Any

import yaml

BASELINES_DIR = "baselines"


def manifest_path(root: Path, name: str) -> Path:
    return root / BASELINES_DIR / f"{name}.yaml"


def manifest_names(root: Path) -> list[str]:
    folder = root / BASELINES_DIR
    return sorted(p.stem for p in folder.glob("*.yaml")) if folder.is_dir() else []


def read_manifest(root: Path, name: str) -> dict[str, Any]:
    data = yaml.safe_load(manifest_path(root, name).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def baselined_uids(root: Path) -> set[str]:
    """Every item that is part of at least one baseline."""
    uids: set[str] = set()
    for name in manifest_names(root):
        uids.update(str(u) for u in read_manifest(root, name).get("items", {}))
    return uids
