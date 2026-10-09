"""Project templates that ship with the tool: a document tree and a short description. Nothing here comes from a
standard; they are neutral starting points the project then owns (its files and config/ are copies)."""

from dataclasses import dataclass
from pathlib import Path

from rvs_core.adapter import DoorstopProject
from rvs_core.config.model import DocumentDecl
from rvs_core.project import create_project
from rvs_core.vcs.git import GitRepo

_R, _V = "requirements", "verification"


@dataclass(frozen=True)
class ProjectTemplate:
    key: str
    title: str
    description: str
    documents: tuple[DocumentDecl, ...]


TEMPLATES: dict[str, ProjectTemplate] = {
    t.key: t
    for t in (
        ProjectTemplate(
            "minimal",
            "Minimal",
            "A system specification, one subsystem specification and a verification plan.",
            (
                DocumentDecl("SYS", _R, "System requirements"),
                DocumentDecl("SUB", _R, "Subsystem requirements", parent="SYS"),
                DocumentDecl("VER", _V, "Verification plan", parent="SYS"),
            ),
        ),
        ProjectTemplate(
            "satellite",
            "Small satellite",
            "Mission and system requirements, seven subsystem specifications (EPS, OBC, AOCS, TT&C, structure, thermal, payload) and a verification plan.",
            (
                DocumentDecl("MIS", _R, "Mission requirements"),
                DocumentDecl("SYS", _R, "System requirements", parent="MIS"),
                DocumentDecl("EPS", _R, "Electrical power subsystem", parent="SYS"),
                DocumentDecl("OBC", _R, "On-board computer", parent="SYS"),
                DocumentDecl("AOCS", _R, "Attitude and orbit control", parent="SYS"),
                DocumentDecl("TTC", _R, "Telemetry, tracking and command", parent="SYS"),
                DocumentDecl("STR", _R, "Structure", parent="SYS"),
                DocumentDecl("THM", _R, "Thermal control", parent="SYS"),
                DocumentDecl("PLD", _R, "Payload", parent="SYS"),
                DocumentDecl("VER", _V, "Verification plan", parent="SYS"),
            ),
        ),
        ProjectTemplate(
            "software",
            "Software product",
            "System requirements, a software requirements specification, interface requirements and a test specification.",
            (
                DocumentDecl("SYS", _R, "System requirements"),
                DocumentDecl("SRS", _R, "Software requirements", parent="SYS"),
                DocumentDecl("ICD", _R, "Interface requirements", parent="SYS"),
                DocumentDecl("TST", _V, "Test specification", parent="SYS"),
            ),
        ),
    )
}


def create_from_template(root: Path, name: str, template: str, *, git: bool = False) -> DoorstopProject:
    if template not in TEMPLATES:
        raise ValueError(f"The template '{template}' does not exist. Available: {', '.join(sorted(TEMPLATES))}.")
    root = Path(root)
    if (root / "rvs-project.yaml").exists():
        raise ValueError(f"{root} already contains an RVS project. Choose an empty folder.")
    if not name.strip():
        raise ValueError("The project needs a name.")
    project = create_project(root, name.strip(), TEMPLATES[template].documents)
    if git:
        GitRepo.init(root)
    return project
