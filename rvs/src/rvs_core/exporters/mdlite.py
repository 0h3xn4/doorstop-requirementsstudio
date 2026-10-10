"""A deliberately small Markdown subset for requirement statements: paragraphs, bullet/numbered lists and
**bold**, *italic*, `code`. Everything else is literal text; raw HTML is never interpreted."""

import re
from dataclasses import dataclass

Span = tuple[str, str]  # (text, style) with style in "", "b", "i", "code"
Spans = tuple[Span, ...]

_INLINE = re.compile(
    r"(\*\*(?P<b>[^*\n]+?)\*\*|(?<![\w*])\*(?P<i>[^*\s](?:[^*\n]*?[^*\s])?)\*(?![\w*])|`(?P<c>[^`\n]+)`)"
)
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBER = re.compile(r"^\s*\d+[.)]\s+(.*)$")


@dataclass(frozen=True)
class Para:
    spans: Spans


@dataclass(frozen=True)
class Bullets:
    items: tuple[Spans, ...]
    ordered: bool = False


def inline(text: str) -> Spans:
    spans: list[Span] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            spans.append((text[pos : m.start()], ""))
        if m.group("b") is not None:
            spans.append((m.group("b"), "b"))
        elif m.group("i") is not None:
            spans.append((m.group("i"), "i"))
        else:
            spans.append((m.group("c"), "code"))
        pos = m.end()
    if pos < len(text):
        spans.append((text[pos:], ""))
    return tuple(spans)


def plain(spans: Spans) -> str:
    return "".join(t for t, _ in spans)


def parse(text: str) -> list[Para | Bullets]:
    blocks: list[Para | Bullets] = []
    lines = text.replace("\r\n", "\n").split("\n")
    para: list[str] = []
    items: list[Spans] = []
    ordered = False

    def flush_para() -> None:
        if para:
            blocks.append(Para(inline(" ".join(s.strip() for s in para))))
            para.clear()

    def flush_list() -> None:
        nonlocal ordered
        if items:
            blocks.append(Bullets(tuple(items), ordered))
            items.clear()
            ordered = False

    for line in lines:
        if not line.strip():
            flush_para()
            flush_list()
            continue
        b, n = _BULLET.match(line), _NUMBER.match(line)
        if b or n:
            flush_para()
            if items and ordered != bool(n):
                flush_list()
            ordered = bool(n)
            items.append(inline((n or b).group(1).strip()))  # type: ignore[union-attr]
        elif items and line.startswith((" ", "\t")):
            items[-1] = inline(plain(items[-1]) + " " + line.strip())  # continuation of a list item
        else:
            flush_list()
            para.append(line)
    flush_para()
    flush_list()
    return blocks
