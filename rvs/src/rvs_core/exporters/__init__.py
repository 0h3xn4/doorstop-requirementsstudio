"""Output formats. Tables (matrices): csv, json, xlsx, html, docx, pdf. Documents (specifications): html, docx, pdf.

ReqIF is deferred (decision D04); a new format is added by extending these two dispatch functions."""

from rvs_core.exporters.builders import matrix_doc
from rvs_core.exporters.docx_out import render_docx
from rvs_core.exporters.html_out import render_html
from rvs_core.exporters.model import Doc
from rvs_core.exporters.pdf_out import render_pdf
from rvs_core.exporters.xlsx_out import render_xlsx
from rvs_core.matrices.render import to_csv, to_json
from rvs_core.matrices.table import MatrixTable

TABLE_FORMATS = ("csv", "json", "xlsx", "html", "docx", "pdf")
DOC_FORMATS = ("html", "docx", "pdf")
BINARY_FORMATS = ("xlsx", "docx", "pdf")


def render_doc(doc: Doc, fmt: str) -> bytes:
    if fmt == "html":
        return render_html(doc)
    if fmt == "docx":
        return render_docx(doc)
    if fmt == "pdf":
        return render_pdf(doc)
    raise ValueError(f"Documents can be exported as {', '.join(DOC_FORMATS)}, not '{fmt}'.")


def render_table(table: MatrixTable, fmt: str) -> bytes:
    if fmt == "csv":
        return to_csv(table).encode("utf-8")
    if fmt == "json":
        return to_json(table).encode("utf-8")
    if fmt == "xlsx":
        return render_xlsx(table)
    if fmt in DOC_FORMATS:
        return render_doc(matrix_doc(table), fmt)
    raise ValueError(f"Tables can be exported as {', '.join(TABLE_FORMATS)}, not '{fmt}'.")


__all__ = ["BINARY_FORMATS", "DOC_FORMATS", "TABLE_FORMATS", "render_doc", "render_table"]
