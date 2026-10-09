"""Rule engine. Each rule id in rules.yaml maps to one checker; severity, enabling and parameters come from the file."""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rvs_core.adapter import DocumentInfo, ItemData
from rvs_core.config import ProjectConfig
from rvs_core.findings import Finding, Severity
from rvs_core.glossary import find_acronyms


@dataclass(frozen=True)
class RuleContext:
    cfg: ProjectConfig
    items: Mapping[str, ItemData]
    docs: Mapping[str, DocumentInfo]
    root_prefix: str
    verified_by: Mapping[str, tuple[str, ...]]  # item uid -> verification items (or itself) that verify it

    def kind(self, item: ItemData) -> str:
        decl = self.cfg.project.document(item.document)
        return decl.kind if decl else ""


def build_context(cfg: ProjectConfig, items: Sequence[ItemData], docs: Sequence[DocumentInfo]) -> RuleContext:
    by_uid = {i.uid: i for i in items}
    verified: dict[str, list[str]] = {}
    for item in items:
        for target in item.attrs.get("link_verifies") or []:
            verified.setdefault(str(target), []).append(item.uid)  # VER item verifies target
        if item.attrs.get("link_verifies"):
            verified.setdefault(item.uid, []).append(item.uid)  # a requirement can carry its own verifies links
    root = next((d.prefix for d in docs if d.parent is None), "")
    return RuleContext(cfg, by_uid, {d.prefix: d for d in docs}, root, {k: tuple(v) for k, v in verified.items()})


@dataclass(frozen=True)
class _Rule:
    id: str
    severity: Severity
    params: Mapping[str, Any]
    description: str


Check = Callable[[RuleContext, ItemData, _Rule], Iterable[tuple[str, str]]]  # yields (message, hint)


def _applies_to_requirement(ctx: RuleContext, item: ItemData) -> bool:
    return ctx.kind(item) == "requirements" and item.normative and item.active


def _word(keyword: str) -> re.Pattern[str]:
    return re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.IGNORECASE)


def _shall_present(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    kw = str(rule.params.get("keyword", "shall"))
    if _applies_to_requirement(ctx, item) and not _word(kw).search(item.text):
        yield (
            f"{item.uid} does not contain '{kw}', so it is not stated as a requirement.",
            f"Rewrite it as 'The <system> {kw} <do something>'.",
        )


def _single_statement(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    kw = str(rule.params.get("keyword", "shall"))
    limit = int(rule.params.get("max", 1))
    n = len(_word(kw).findall(item.text))
    if _applies_to_requirement(ctx, item) and n > limit:
        yield (
            f"{item.uid} uses '{kw}' {n} times, so it probably states more than one requirement.",
            "Split it into one requirement per statement.",
        )


def _vague_words(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    if not _applies_to_requirement(ctx, item):
        return
    for word in rule.params.get("words", []):
        if _word(str(word)).search(item.text):
            yield (
                f"{item.uid} uses the vague wording '{word}'.",
                "Replace it with a measurable value or a precise condition.",
            )


def _no_implementation(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    if not (_applies_to_requirement(ctx, item) and item.attrs.get("type") == "functional"):
        return
    for term in rule.params.get("terms", []):
        if _word(str(term)).search(item.text):
            yield (
                f"{item.uid} is a functional requirement but mentions the implementation term '{term}'.",
                "State what the system must do, not how; move design choices to a design requirement.",
            )


def _verify_method_set(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    if _applies_to_requirement(ctx, item) and not item.attrs.get("verify_method"):
        yield (f"{item.uid} has no verification method.", "Choose test, analysis, inspection or review of design.")


def _has_parent(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    if _applies_to_requirement(ctx, item) and item.document != ctx.root_prefix and not item.derived and not item.links:
        yield (
            f"{item.uid} has no parent requirement.",
            "Link it to the requirement it derives from, or mark it as derived if it has no parent.",
        )


def _verified_when_approved(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    statuses = set(rule.params.get("statuses", ["approved"]))
    if _applies_to_requirement(ctx, item) and item.attrs.get("status") in statuses and item.uid not in ctx.verified_by:
        yield (
            f"{item.uid} is {item.attrs.get('status')} but nothing verifies it.",
            "Link a verification item to it, or set the status back to draft or reviewed.",
        )


def _undefined_acronym(ctx: RuleContext, item: ItemData, rule: _Rule) -> Iterable[tuple[str, str]]:
    if not item.active:
        return
    known = set(ctx.cfg.glossary.acronyms)
    seen: set[str] = set()
    parts = [item.text, str(item.attrs.get("title") or ""), str(item.attrs.get("rationale") or "")]
    for part in parts:
        for hit in find_acronyms(
            part, known, min_length=int(rule.params.get("min_length", 2)), ignore=set(rule.params.get("ignore", []))
        ):
            if not hit.defined and hit.text not in seen:
                seen.add(hit.text)
                yield (
                    f"{item.uid} uses the acronym '{hit.text}', which is not in the glossary.",
                    "Add it to config/glossary.yaml with its expansion.",
                )


CHECKS: dict[str, Check] = {
    "shall-present": _shall_present,
    "single-statement": _single_statement,
    "vague-words": _vague_words,
    "no-implementation": _no_implementation,
    "verify-method-set": _verify_method_set,
    "has-parent": _has_parent,
    "verified-when-approved": _verified_when_approved,
    "undefined-acronym": _undefined_acronym,
}


def run_rules(ctx: RuleContext, items: Iterable[ItemData] | None = None) -> list[Finding]:
    """Run every enabled rule on ``items`` (default: all items). Output order is deterministic."""
    targets = sorted(items if items is not None else ctx.items.values(), key=lambda i: i.uid)
    findings: list[Finding] = []
    for raw in ctx.cfg.rules["rules"]:
        rid = raw["id"]
        if not raw["enabled"]:
            continue
        check = CHECKS.get(rid)
        if check is None:
            findings.append(
                Finding(
                    "RVS-RULE-UNKNOWN",
                    Severity.ERROR,
                    f"config/rules.yaml enables rule '{rid}', which this version of RVS does not provide.",
                    f"Remove it or set enabled: false. Available rules: {', '.join(sorted(CHECKS))}.",
                    "config/rules.yaml",
                )
            )
            continue
        rule = _Rule(rid, Severity(raw["severity"]), raw.get("params", {}), raw.get("description", ""))
        code = "RVS-RULE-" + rid.upper()
        for item in targets:
            findings.extend(
                Finding(code, rule.severity, message, hint, item.path, item.uid)
                for message, hint in check(ctx, item, rule)
            )
    return findings
