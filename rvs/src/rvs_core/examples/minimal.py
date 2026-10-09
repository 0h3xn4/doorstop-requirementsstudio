"""The minimal 10-item reference project (3 documents: SYS <- EPS, SYS <- VER)."""

from pathlib import Path

from rvs_core.adapter import DoorstopProject
from rvs_core.config.model import DocumentDecl
from rvs_core.project import create_project

DOCS = (
    DocumentDecl("SYS", "requirements", "System requirements"),
    DocumentDecl("EPS", "requirements", "Electrical power subsystem requirements", parent="SYS"),
    DocumentDecl("VER", "verification", "Verification plan", parent="SYS"),
)


def _req(title: str, rtype: str, method: str, level: str, status: str = "draft") -> dict[str, str]:
    return {
        "title": title,
        "type": rtype,
        "status": status,
        "verify_method": method,
        "verify_level": level,
        "owner": "systems",
        "priority": "high",
    }


def build_minimal_project(root: Path) -> DoorstopProject:
    proj = create_project(root, "Minimal example", DOCS)
    # SYS: three requirements and one heading (created last so its UID is SYS-0004)
    sys1 = proj.add_item(
        "SYS",
        "The spacecraft shall provide electrical power to all payloads.",
        attrs=_req("Payload power", "functional", "analysis", "system"),
        level="1.1",
    )
    sys2 = proj.add_item(
        "SYS",
        "The spacecraft shall operate in sunlight and eclipse.",
        attrs=_req("Eclipse operation", "operational", "test", "system"),
        level="1.2",
    )
    sys3 = proj.add_item(
        "SYS",
        "The spacecraft mass shall not exceed 50 kg.",
        attrs=_req("Mass budget", "performance", "inspection", "system"),
        level="1.3",
    )
    proj.add_item(
        "SYS",
        "Requirements derived from the mission statement.",
        attrs={"title": "Mission-derived"},
        level="1.0",
        normative=False,
        header="System requirements",
    )
    # EPS: three requirements, each with a Doorstop parent link
    eps = [
        (
            "The battery shall store at least the energy needed for one eclipse.",
            "Battery capacity",
            "design",
            "analysis",
            sys2,
        ),
        (
            "The solar array shall generate power in sunlight for all payloads.",
            "Array output",
            "performance",
            "test",
            sys1,
        ),
        ("The EPS mass shall not exceed 8 kg.", "EPS mass", "performance", "inspection", sys3),
    ]
    eps_items = []
    for n, (text, title, rtype, method, parent) in enumerate(eps, start=1):
        item = proj.add_item("EPS", text, attrs=_req(title, rtype, method, "subsystem"), level=f"1.{n}")
        proj.link(item.uid, parent.uid)
        eps_items.append(item)
    # VER: three derived verification items, typed `verifies` links are RVS attributes
    ver = [
        ("Eclipse power analysis", "analysis", "system", eps_items[0], "VER-EPS-A-001"),
        ("Array output test", "test", "subsystem", eps_items[1], "VER-EPS-T-001"),
        ("EPS mass inspection", "inspection", "subsystem", eps_items[2], "VER-EPS-I-001"),
    ]
    for n, (title, method, level, target, proc) in enumerate(ver, start=1):
        proj.add_item(
            "VER",
            f"Verify {target.uid}: {title.lower()}.",
            attrs={
                "title": title,
                "proc_id": proc,
                "verify_method": method,
                "verify_level": level,
                "v_status": "planned",
                "link_verifies": [target.uid],
            },
            level=f"1.{n}",
            derived=True,
        )
    return proj
