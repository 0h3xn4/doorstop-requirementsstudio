"""Self-contained HTML: inline CSS, bundled fonts as data URIs, no scripts, no external references."""

import base64
import html
from functools import cache
from importlib import resources

from rvs_core.exporters.mdlite import Bullets, Spans, parse
from rvs_core.exporters.model import DiffEntry, Doc, Entry, Heading, Paragraph, TableBlock

_FONTS = (
    ("IBM Plex Sans", "normal", "400", "IBMPlexSans-Regular"),
    ("IBM Plex Sans", "normal", "600", "IBMPlexSans-SemiBold"),
    ("IBM Plex Sans", "italic", "400", "IBMPlexSans-Italic"),
    ("IBM Plex Mono", "normal", "400", "IBMPlexMono-Regular"),
)


@cache
def _font_css() -> str:
    rules = []
    for family, style, weight, name in _FONTS:
        raw = resources.files("rvs_core.exporters").joinpath(f"fonts/{name}.subset.woff").read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        rules.append(
            f'@font-face{{font-family:"{family}";font-style:{style};font-weight:{weight};'
            f'src:url(data:font/woff;base64,{b64}) format("woff");}}'
        )
    return "\n".join(rules)


_CSS = """
body{font-family:"IBM Plex Sans",sans-serif;font-size:14px;color:#161616;background:#fff;margin:0;padding:24px 32px;line-height:1.45}
header.titleblock{border-bottom:2px solid #161616;margin-bottom:24px;padding-bottom:12px}
h1{font-size:24px;margin:0 0 8px} h2{font-size:18px;margin:28px 0 8px} h3{font-size:15px;margin:0 0 4px}
.prov{color:#525252;font-size:12px;margin:0} .notes{background:#f4f4f4;border-left:4px solid #f1c21b;padding:8px 12px;margin:12px 0}
table{border-collapse:collapse;width:100%;font-size:13px;margin:12px 0} th{background:#f4f4f4;text-align:left;border-bottom:1px solid #8d8d8d}
th,td{padding:6px 8px;border-bottom:1px solid #e0e0e0;vertical-align:top}
tr.gap-unverified td,tr.gap-childless td{background:#fcf4d6} tr.gap-orphan td,tr.gap-unverified-approved td{background:#ffd7d9}
section.req{border-top:1px solid #e0e0e0;padding:10px 0} .fields{color:#525252;font-size:12px;margin:4px 0}
.fields b{color:#161616;font-weight:600} code{font-family:"IBM Plex Mono",monospace;background:#f4f4f4;padding:0 3px}
ins{background:#defbe6;color:#0e6027;text-decoration:none} del{background:#fff1f1;color:#a2191f}
.kind{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:#525252;margin-left:8px}
@media print{body{padding:0}header.titleblock{page-break-after:avoid}section.req{page-break-inside:avoid}}
"""


def _spans(spans: Spans) -> str:
    out = []
    for text, style in spans:
        esc = html.escape(text)
        out.append(
            {"b": f"<strong>{esc}</strong>", "i": f"<em>{esc}</em>", "code": f"<code>{esc}</code>"}.get(style, esc)
        )
    return "".join(out)


def _markdown(text: str) -> str:
    parts = []
    for block in parse(text):
        if isinstance(block, Bullets):
            tag = "ol" if block.ordered else "ul"
            parts.append(f"<{tag}>" + "".join(f"<li>{_spans(i)}</li>" for i in block.items) + f"</{tag}>")
        else:
            parts.append(f"<p>{_spans(block.spans)}</p>")
    return "\n".join(parts)


def _table(t: TableBlock) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in t.columns)
    rows = []
    for n, row in enumerate(t.rows):
        flag = t.flags[n] if n < len(t.flags) else None
        cls = f' class="gap-{html.escape(flag)}"' if flag else ""
        rows.append(f"<tr{cls}>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>\n" + "\n".join(rows) + "\n</tbody></table>"


def render_html(doc: Doc) -> bytes:
    body: list[str] = []
    for block in doc.blocks:
        if isinstance(block, Heading):
            tag = f"h{min(block.level + 1, 4)}"
            body.append(f"<{tag}>{html.escape(block.text)}</{tag}>")
        elif isinstance(block, Paragraph):
            body.append(_markdown(block.text))
        elif isinstance(block, TableBlock):
            body.append(_table(block))
        elif isinstance(block, DiffEntry):
            rows = "".join(
                f'<p class="fields"><b>{html.escape(f.name)}:</b> '
                + "".join(
                    {"insert": f"<ins>{html.escape(t)}</ins>", "delete": f"<del>{html.escape(t)}</del>"}.get(
                        op, html.escape(t)
                    )
                    for op, t in f.segments
                )
                + "</p>"
                for f in block.fields
            )
            title = f" &mdash; {html.escape(block.title)}" if block.title else ""
            body.append(
                f'<section class="req" id="{html.escape(block.uid)}"><h3>{html.escape(block.uid)}{title}'
                f'<span class="kind">{html.escape(block.kind)}</span></h3>{rows}</section>'
            )
        elif isinstance(block, Entry):
            fields = " &middot; ".join(f"<b>{html.escape(k)}:</b> {html.escape(v)}" for k, v in block.fields)
            title = f" &mdash; {html.escape(block.title)}" if block.title else ""
            rationale = (
                f'<p class="fields"><b>Rationale:</b> {html.escape(block.rationale)}</p>' if block.rationale else ""
            )
            body.append(
                f'<section class="req" id="{html.escape(block.uid)}"><h3>{html.escape(block.uid)}{title}</h3>'
                f'{_markdown(block.text)}<p class="fields">{fields}</p>{rationale}</section>'
            )
    prov = "".join(f'<p class="prov">{html.escape(line)}</p>' for line in doc.provenance.lines())
    notes = "".join(f'<p class="notes">{html.escape(n)}</p>' for n in doc.notes)
    page = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(doc.title)}</title>"
        f'<meta name="generator" content="rvs {html.escape(doc.provenance.tool_version)}">'
        f"<style>{_font_css()}{_CSS}</style></head><body>"
        f'<header class="titleblock"><h1>{html.escape(doc.title)}</h1>{prov}</header>{notes}'
        f"<main>\n{chr(10).join(body)}\n</main></body></html>\n"
    )
    return page.encode("utf-8")
