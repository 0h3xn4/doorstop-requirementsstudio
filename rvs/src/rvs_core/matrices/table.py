"""A rendered matrix: plain strings, one flag per row. GUI, CLI and the M4 exporters all render this."""

from dataclasses import dataclass, field

from rvs_core.matrices.provenance import Provenance


@dataclass(frozen=True)
class MatrixTable:
    title: str
    columns: list[str]
    rows: list[list[str]]
    flags: list[str | None]  # per row: None or a gap code (childless, orphan, unverified, unverified-approved)
    provenance: Provenance
    notes: tuple[str, ...] = field(default_factory=tuple)
