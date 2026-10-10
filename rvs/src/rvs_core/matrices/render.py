"""Text renderings of a MatrixTable shared by the CLI and the GUI (CSV and JSON; the other formats render the same table)."""

import csv
import io
import json

from rvs_core import csvsafe
from rvs_core.matrices.table import MatrixTable


def to_json(table: MatrixTable) -> str:
    return (
        json.dumps(
            {
                "title": table.title,
                "columns": table.columns,
                "rows": table.rows,
                "flags": table.flags,
                "notes": list(table.notes),
                "provenance": table.provenance.to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


def to_csv(table: MatrixTable) -> str:
    """Provenance and notes first as '#' comment lines, then the header row and the data rows."""
    buf = io.StringIO()
    buf.write(f"# {table.title}\n")
    for line in (*table.provenance.lines(), *table.notes):
        buf.write(f"# {line}\n")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(table.columns)
    writer.writerows([csvsafe.protect(c) for c in row] for row in table.rows)  # no formula injection in Excel
    return buf.getvalue()


def render(table: MatrixTable, fmt: str) -> str:
    return to_json(table) if fmt == "json" else to_csv(table)
