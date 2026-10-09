"""Check a requirement that does not exist yet (the guided wizard shows these findings while the user types)."""

from collections.abc import Mapping, Sequence
from typing import Any

from rvs_core.adapter import DocumentInfo, ItemData
from rvs_core.config import ProjectConfig
from rvs_core.findings import Finding
from rvs_core.rules.engine import build_context, run_rules

DRAFT_UID = "(new)"


def check_draft(
    cfg: ProjectConfig,
    items: Sequence[ItemData],
    docs: Sequence[DocumentInfo],
    *,
    document: str,
    text: str,
    attrs: Mapping[str, Any],
    parents: Sequence[str],
) -> list[Finding]:
    """Rule findings for a draft; the project itself is not touched."""
    decl = cfg.project.document(document)
    defaults = dict(cfg.templates.kinds[decl.kind].defaults) if decl else {}
    draft = ItemData(
        uid=DRAFT_UID, document=document, level="", text=text, header="", normative=True, derived=False, active=True,
        reviewed=False, ref="", links=tuple(parents), attrs={**defaults, **{k: v for k, v in attrs.items() if v not in (None, "")}},
        path="",
    )  # fmt: skip
    ctx = build_context(cfg, [*items, draft], docs)
    return run_rules(ctx, [draft])
