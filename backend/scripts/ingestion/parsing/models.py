"""Data structures shared by every PDF parser backend."""

from dataclasses import dataclass, field


@dataclass
class ParsedTable:
    """A table lifted out of one PDF page."""

    page: int
    rows: list
    n_rows: int
    n_cols: int


@dataclass
class ParsedPdf:
    """The normalized result of parsing one PDF."""

    source: str
    text_items: list = field(default_factory=list)
    tables: list = field(default_factory=list)


def cell_to_text(value) -> str:
    """Convert a raw table cell into a clean string."""
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in ("nan", "none", "nat"):
        return ""

    return text
