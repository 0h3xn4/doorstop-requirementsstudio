"""Create a project: rvs-project.yaml, config/*.yaml (copied from packaged defaults) and the Doorstop tree."""

from collections.abc import Sequence
from importlib import resources
from pathlib import Path

import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.config import CONFIG_NAMES, PROJECT_FILE, load_project_config
from rvs_core.config.model import DocumentDecl
from rvs_core.schema.versioning import CURRENT_VERSION


def create_project(root: Path, name: str, documents: Sequence[DocumentDecl]) -> DoorstopProject:
    """Write project files and create all documents (parents first). Output is deterministic."""
    root.mkdir(parents=True, exist_ok=True)
    project = {
        "rvs_schema_version": CURRENT_VERSION,
        "name": name,
        "documents": [
            {"prefix": d.prefix, "kind": d.kind, "title": d.title, **({"parent": d.parent} if d.parent else {})}
            for d in documents
        ],
    }
    (root / PROJECT_FILE).write_text(
        yaml.safe_dump(project, sort_keys=True, allow_unicode=True), encoding="utf-8", newline="\n"
    )
    config_dir = root / "config"
    config_dir.mkdir(exist_ok=True)
    for cfg_name in CONFIG_NAMES:
        text = resources.files("rvs_core.config").joinpath(f"defaults/{cfg_name}.yaml").read_text(encoding="utf-8")
        (config_dir / f"{cfg_name}.yaml").write_text(text, encoding="utf-8", newline="\n")

    cfg, _ = load_project_config(root)
    proj = DoorstopProject.create(root)
    created: set[str] = set()
    remaining = list(documents)
    while remaining:
        for d in list(remaining):
            if d.parent is None or d.parent in created:
                tpl = cfg.templates.kinds[d.kind]
                proj.create_document(
                    d.prefix,
                    parent=d.parent,
                    sep=cfg.numbering.sep_for(d.prefix),
                    digits=cfg.numbering.digits_for(d.prefix),
                    defaults=tpl.defaults,
                    fingerprint=tpl.fingerprint,
                )
                created.add(d.prefix)
                remaining.remove(d)
    return proj
