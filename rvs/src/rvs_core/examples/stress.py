"""Reference project 3: a stress project (default 5,000 items) for performance tests. Deterministic, fictional."""

from pathlib import Path

import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.config.model import DocumentDecl
from rvs_core.project import create_project

SUBSYSTEMS = ("EPS", "OBC", "AOCS", "TTC", "STR", "THM", "PLD")
DOCS = (
    DocumentDecl("SYS", "requirements", "System"),
    *(DocumentDecl(p, "requirements", f"{p} subsystem", parent="SYS") for p in SUBSYSTEMS),
    DocumentDecl("VER", "verification", "Verification", parent="SYS"),
)
TYPES = ("functional", "performance", "interface", "design")
STATUS = ("draft", "reviewed", "draft", "draft")


def build_stress_project(root: Path, total: int = 5000) -> DoorstopProject:
    """``total`` items: 10 % system, 60 % subsystem requirements (7 documents), 30 % verification items."""
    proj = create_project(root, "Stress project (fictional data)", DOCS)
    acronyms = [{"acronym": a, "expansion": a} for a in ("EPS", "OBC", "AOCS", "TTC", "STR", "THM", "PLD", "SYS")]
    glossary = {"rvs_schema_version": 1, "terms": [], "acronyms": acronyms}
    (root / "config" / "glossary.yaml").write_text(
        yaml.safe_dump(glossary, sort_keys=True), encoding="utf-8", newline="\n"
    )
    n_sys = total // 10
    n_ver = (total * 3) // 10
    n_sub = total - n_sys - n_ver
    sys_uids = []
    for n in range(n_sys):
        attrs = _attrs(n, "system")
        sys_uids.append(
            proj.add_item("SYS", f"The system shall meet performance figure {n}.", attrs=attrs, level=f"1.{n + 1}").uid
        )
    sub_uids: list[str] = []
    per = {p: n_sub // len(SUBSYSTEMS) + (1 if i < n_sub % len(SUBSYSTEMS) else 0) for i, p in enumerate(SUBSYSTEMS)}
    for prefix, count in per.items():
        for n in range(count):
            item = proj.add_item(
                prefix, f"The {prefix} shall satisfy figure {n}.", attrs=_attrs(n, "subsystem"), level=f"1.{n + 1}"
            )
            proj.link(item.uid, sys_uids[(len(sub_uids)) % len(sys_uids)])
            sub_uids.append(item.uid)
    for n in range(n_ver):
        target = sub_uids[(n * 2) % len(sub_uids)]
        proj.add_item(
            "VER",
            f"Verify {target}.",
            attrs={
                "title": f"Verify {target}", "proc_id": f"V-{n}", "verify_method": "test",
                "verify_level": "subsystem", "v_status": ("planned", "passed", "failed", "in-progress")[n % 4],
                "link_verifies": [target],
            },
            level=f"1.{n + 1}",
            derived=True,
        )  # fmt: skip
    return proj


def _attrs(n: int, level: str) -> dict[str, str]:
    return {
        "title": f"Requirement {n}", "type": TYPES[n % 4], "verify_method": "test", "verify_level": level,
        "owner": "team", "priority": ("high", "medium", "low")[n % 3], "status": STATUS[n % 4],
    }  # fmt: skip
