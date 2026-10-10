"""PDF via ReportLab with the bundled IBM Plex fonts (embedded). Deterministic: ReportLab's invariant mode."""

import io
from importlib import resources
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, ListFlowable, ListItem, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus import Paragraph as RLParagraph

from rvs_core.exporters.mdlite import Bullets, Spans, parse
from rvs_core.exporters.model import DiffEntry, Doc, Entry, Heading, Paragraph, TableBlock

SANS, BOLD, ITALIC, MONO = "IBMPlexSans", "IBMPlexSans-SemiBold", "IBMPlexSans-Italic", "IBMPlexMono"
_GAP_FILL = {"unverified-approved": "#FFD7D9", "orphan": "#FFD7D9", "unverified": "#FCF4D6", "childless": "#FCF4D6"}
_registered = False


def _register_fonts() -> None:
    global _registered
    if _registered:
        return
    for name, file in (
        (SANS, "IBMPlexSans-Regular"),
        (BOLD, "IBMPlexSans-SemiBold"),
        (ITALIC, "IBMPlexSans-Italic"),
        (MONO, "IBMPlexMono-Regular"),
    ):
        path = resources.files("rvs_core.exporters").joinpath(f"fonts/{file}.ttf")
        pdfmetrics.registerFont(TTFont(name, io.BytesIO(path.read_bytes())))
    pdfmetrics.registerFontFamily(SANS, normal=SANS, bold=BOLD, italic=ITALIC, boldItalic=BOLD)
    _registered = True


CELL_LIMIT = 1500  # a cell taller than a page cannot be split by ReportLab


def _fit_cell(value: str) -> str:
    return value if len(value) <= CELL_LIMIT else value[:CELL_LIMIT] + " … [cut: see the CSV or XLSX export]"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _markup(spans: Spans) -> str:
    out = []
    for text, style in spans:
        e = _esc(text)
        out.append({"b": f"<b>{e}</b>", "i": f"<i>{e}</i>", "code": f'<font name="{MONO}">{e}</font>'}.get(style, e))
    return "".join(out)


LONG_TEXT = (
    4000  # characters; a longer statement is laid out in pieces (one huge paragraph made ReportLab's cost cubic)
)


def _chunks(text: str, size: int = LONG_TEXT) -> list[str]:
    """``text`` cut into pieces of at most ``size`` characters at line ends (or, for one enormous line, at spaces)."""
    if len(text) <= size:
        return [text]
    pieces: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > size:
            cut = line.rfind(" ", 0, size)
            cut = cut if cut > 0 else size
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:cut])
            line = line[cut:].lstrip(" ")
        if current and len(current) + len(line) + 1 > size:
            pieces.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        pieces.append(current)
    return pieces


def render_pdf(doc: Doc) -> bytes:
    _register_fonts()
    page = landscape(A4) if doc.landscape else A4
    margin = 15 * mm
    width = page[0] - 2 * margin
    base = ParagraphStyle("base", fontName=SANS, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=base, fontSize=8, leading=10.5, textColor=colors.HexColor("#525252"))
    cell = ParagraphStyle("cell", parent=base, fontSize=8, leading=10)
    cell_head = ParagraphStyle("cellh", parent=cell, fontName=BOLD)
    title = ParagraphStyle("title", parent=base, fontName=BOLD, fontSize=20, leading=24, spaceAfter=6)
    h = {1: ParagraphStyle("h1", parent=base, fontName=BOLD, fontSize=15, leading=19, spaceBefore=14, spaceAfter=6),
         2: ParagraphStyle("h2", parent=base, fontName=BOLD, fontSize=12, leading=16, spaceBefore=10, spaceAfter=4),
         3: ParagraphStyle("h3", parent=base, fontName=BOLD, fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=2)}  # fmt: skip
    note = ParagraphStyle(
        "note", parent=base, fontName=ITALIC, fontSize=8.5, backColor=colors.HexColor("#F4F4F4"), borderPadding=4
    )

    story: list[Any] = [RLParagraph(_esc(doc.title), title)]
    story += [RLParagraph(_esc(line), small) for line in doc.provenance.lines()]
    story += [Spacer(1, 4 * mm)]
    story += [RLParagraph(_esc(n), note) for n in doc.notes]

    def markdown(text: str) -> list[Any]:
        flow: list[Any] = []
        for chunk in _chunks(text):
            flow += _markdown_flow(chunk)
        return flow

    def _markdown_flow(text: str) -> list[Any]:
        flow: list[Any] = []
        for block in parse(text):
            if isinstance(block, Bullets):
                items = [ListItem(RLParagraph(_markup(i), base)) for i in block.items]
                flow.append(
                    ListFlowable(
                        items, bulletType="1" if block.ordered else "bullet", bulletFontName=SANS, leftIndent=14
                    )
                )
            else:
                flow.append(RLParagraph(_markup(block.spans), base))
        return flow

    def table(t: TableBlock) -> Table:
        lens = [max([len(c)] + [len(r[i]) for r in t.rows[:200]]) for i, c in enumerate(t.columns)]
        weights = [min(max(n, 6), 40) for n in lens]
        widths = [width * w / sum(weights) for w in weights]
        data = [[RLParagraph(_esc(c), cell_head) for c in t.columns]]
        data += [[RLParagraph(_esc(_fit_cell(v)), cell) for v in row] for row in t.rows]
        style = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4F4F4")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6C6C6")),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]  # fmt: skip
        for n, flag in enumerate(t.flags):
            if flag:
                style.append(("BACKGROUND", (0, n + 1), (-1, n + 1), colors.HexColor(_GAP_FILL.get(flag, "#FCF4D6"))))
        tbl = Table(data, colWidths=widths, repeatRows=1)
        tbl.setStyle(TableStyle(style))
        return tbl

    for block in doc.blocks:
        if isinstance(block, Heading):
            story.append(RLParagraph(_esc(block.text), h[min(block.level, 3)]))
        elif isinstance(block, Paragraph):
            story += markdown(block.text)
        elif isinstance(block, TableBlock):
            story.append(table(block))
        elif isinstance(block, DiffEntry):
            diff_parts = [
                RLParagraph(
                    _esc(
                        f"{block.uid} — {block.title} ({block.kind})" if block.title else f"{block.uid} ({block.kind})"
                    ),
                    h[3],
                )
            ]
            for field in block.fields:
                marked = "".join(
                    {
                        "insert": f'<font color="#198038"><u>{_esc(t)}</u></font>',
                        "delete": f'<font color="#da1e28"><strike>{_esc(t)}</strike></font>',
                    }.get(op, _esc(t))
                    for op, t in field.segments
                )
                diff_parts.append(RLParagraph(f"<b>{_esc(field.name)}:</b> {marked}", base))
            story.append(KeepTogether(diff_parts))
        elif isinstance(block, Entry):
            head = f"{block.uid} — {block.title}" if block.title else block.uid
            parts: list[Any] = [RLParagraph(_esc(head), h[3]), *markdown(block.text)]
            if block.fields:
                parts.append(RLParagraph(" · ".join(f"<b>{_esc(k)}:</b> {_esc(v)}" for k, v in block.fields), small))
            if block.rationale:
                parts.append(RLParagraph(f"<b>Rationale:</b> {_esc(block.rationale)}", small))
            if len(block.text) > LONG_TEXT:
                story += (
                    parts  # a block that cannot fit one page anyway; KeepTogether would re-lay it out again and again
                )
            else:
                story.append(KeepTogether(parts))

    def decorate(canvas, d) -> None:  # type: ignore[no-untyped-def]
        canvas.saveState()
        canvas.setFont(SANS, 7.5)
        canvas.setFillColor(colors.HexColor("#525252"))
        p = doc.provenance
        canvas.drawString(
            margin,
            page[1] - 9 * mm,
            f"{p.project} · {p.baseline} · {p.generated.strftime('%Y-%m-%d %H:%M:%S')} · {p.user}",
        )
        canvas.drawCentredString(page[0] / 2, 8 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    buf = io.BytesIO()
    template = SimpleDocTemplate(
        buf, pagesize=page, leftMargin=margin, rightMargin=margin, topMargin=18 * mm, bottomMargin=16 * mm,
        title=doc.title, author=doc.provenance.user, subject=doc.provenance.project,
        creator=f"rvs {doc.provenance.tool_version}", invariant=1,
    )  # fmt: skip
    template.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
