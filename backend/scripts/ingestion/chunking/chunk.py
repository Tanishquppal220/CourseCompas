"""The ``Chunk`` structure plus helpers shared by every chunker."""

import re
from dataclasses import dataclass, field

from ..cleaning import (
    collapse_whitespace,
    has_ip_boilerplate,
    is_page_furniture,
    strip_ip_boilerplate,
    strip_page_furniture,
)
from .metadata import ChunkMeta

# Shared document patterns (used by both the Syllabus and IP chunkers).
COURSE_CODE_RE = re.compile(r"\b([A-Z]{3}\d{3})\b")
CO_RE = re.compile(r"CO(\d+)\s*::\s*(.+?)(?=CO\d+\s*::|$)", re.DOTALL)


@dataclass
class Chunk:
    """One retrievable unit of text produced from a source document.

    ``page`` is the real 1-based source page number, or ``None`` when the
    source has no pages (e.g. the benefits markdown). Any non-page location
    information (table index, section) belongs in ``metadata``.

    ``metadata`` is a per-(doc_type, chunk_type) :class:`ChunkMeta` dataclass
    (see ``metadata.py``); the pipeline serializes it with ``.to_dict()``.
    ``chunk_index`` is owned by the pipeline, not the chunkers.
    """

    doc_type: str
    page: int | None
    section_title: str
    chunk_type: str
    content: str
    metadata: ChunkMeta | None = field(default=None)


def truncate_text(text: str, limit: int = 200) -> str:
    """Shorten ``text`` to ``limit`` characters, adding an ellipsis."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def collect_cleaned_text_items(
    text_items, *, strip_footers: bool = True, drop_boilerplate: bool = True
):
    """Yield ``(page, cleaned_text)`` for non-boilerplate items in reading order.

    Cleaning is an explicit, opt-in pipeline:

    * ``strip_footers`` -- remove generic page furniture (session/page footer
      lines) and filter items that are pure page furniture.
    * ``drop_boilerplate`` -- remove instruction-plan disclaimer text and
      filter items that consist entirely of IP boilerplate phrases.

    Both default to True, preserving the historical behavior shared by the
    Syllabus and IP chunkers; a per-source caller can opt out of a step.
    """
    for item in text_items:
        text = item.get("text", "")
        if strip_footers:
            text = strip_page_furniture(text)
        if drop_boilerplate:
            text = strip_ip_boilerplate(text)
        text = collapse_whitespace(text).strip()
        if not text:
            continue
        if drop_boilerplate and has_ip_boilerplate(text):
            continue
        if strip_footers and is_page_furniture(text):
            continue
        yield item.get("page", 0), text