"""Format-neutral document model: builders produce a Doc, the HTML/DOCX/PDF renderers draw it."""

from dataclasses import dataclass, field

from rvs_core.matrices.provenance import Provenance


@dataclass(frozen=True)
class Heading:
    level: int  # 1..3
    text: str


@dataclass(frozen=True)
class Paragraph:
    text: str  # Markdown subset (see mdlite)


@dataclass(frozen=True)
class TableBlock:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    flags: tuple[str | None, ...] = ()  # gap code per row, or empty


@dataclass(frozen=True)
class Entry:
    """One requirement or verification item in a specification document."""

    uid: str
    title: str
    text: str  # Markdown subset
    fields: tuple[tuple[str, str], ...] = ()
    rationale: str = ""


Block = Heading | Paragraph | TableBlock | Entry


@dataclass(frozen=True)
class Doc:
    title: str
    provenance: Provenance
    blocks: tuple[Block, ...] = ()
    notes: tuple[str, ...] = field(default_factory=tuple)
    landscape: bool = False

    @property
    def subtitle(self) -> str:
        return self.provenance.project
