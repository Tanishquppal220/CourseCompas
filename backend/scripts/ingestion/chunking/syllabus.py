"""Chunker for Syllabus PDFs (2-3 page, highly templated documents).

Turns a syllabus into course-overview, course-outcome, practical, reference,
and per-unit topic chunks.
"""

import re

from ..cleaning import normalize_whitespace
from .chunk import (
    CO_RE,
    Chunk,
    assign_chunk_indices,
    collect_cleaned_text_items,
    truncate_text,
)

UNIT_MARKER_RE = re.compile(r"^Unit\s+([IVX]+)$")
PRACTICAL_RE = re.compile(r"^\d{2}\.[^\d]")
TOPIC_SPLIT_RE = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9 &/()\-',.]{2,90}?)\s*[:：]\s*(.+)$", re.DOTALL
)

ROMAN = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
}


def chunk_syllabus(text_items) -> list[Chunk]:
    """Chunk a parsed Syllabus PDF into semantic pieces."""
    chunks: list[Chunk] = []
    current_unit: int | None = None
    unit_buf: list[tuple] = []  # (page, topic_title, content)
    outcomes_buf: list[tuple] = []  # (page, text)
    practicals: list[tuple] = []  # (page, text)
    ref_items: list[tuple] = []  # (page, text)
    in_refs = False
    overview_parts: list[tuple] = []

    for page, text in collect_cleaned_text_items(text_items):
        lowered = text.lower()

        if in_refs:
            ref_items.append((page, text))
            continue

        # LTP line.
        if re.search(r"\bCredits\b", text) and re.search(r"\bL\s*:", text):
            overview_parts.append((page, "LTP", text))
            continue

        # Unit markers flip state and flush the previous unit's topic chunks.
        m = UNIT_MARKER_RE.match(text)
        if m:
            flush_unit_chunks(chunks, current_unit, unit_buf)
            current_unit = ROMAN.get(m.group(1), None)
            unit_buf = []
            continue

        # Practicals: "01. Write a program ..."
        if PRACTICAL_RE.match(text) or re.match(r"^•\s*\d{2}\.", text):
            practicals.append((page, text))
            continue
        if "list of practical" in lowered:
            continue

        # Text books / references enter references mode.
        if (
            text.startswith(("Text Books", "References"))
            or "text books:" in text[:40].lower()
        ):
            in_refs = True
            ref_items.append((page, text))
            continue

        # Course outcomes block.
        if "course outcomes" in lowered[:40] or re.search(r"CO\d+\s*::", text):
            outcomes_buf.append((page, text))
            continue

        # Regular content associates with the current unit, if any.
        if current_unit is not None:
            unit_buf.append((page, text))
        else:
            # Content before any unit marker (intro blurb).
            if "course outcomes" in lowered or "through this course" in lowered:
                outcomes_buf.append((page, text))
            else:
                overview_parts.append((page, "Overview", text))

    flush_unit_chunks(chunks, current_unit, unit_buf)

    # Course overview chunk.
    if overview_parts:
        content_parts = []
        for _pg, _label, text in overview_parts:
            content_parts.extend([text])
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=overview_parts[0][0],
                section_title="Course Overview",
                chunk_type="course_overview",
                content="\n".join(content_parts),
                metadata={"document_kind": "syllabus"},
            )
        )

    # Course outcomes chunks.
    outcomes_page = outcomes_buf[0][0] if outcomes_buf else None
    co_buf = "\n".join(text for _page, text in outcomes_buf)
    co_buf = re.sub(
        r"\s*Through this course students should be able to\s*$",
        "",
        co_buf,
        flags=re.IGNORECASE,
    )
    co_buf = re.sub(r"^Course Outcomes\s*:", "", co_buf, flags=re.IGNORECASE).strip()
    if co_buf:
        matched = list(CO_RE.finditer(co_buf))
        if matched:
            for m in matched:
                co_num = int(m.group(1))
                content = f"CO{co_num} :: {normalize_whitespace(m.group(2))}"
                chunks.append(
                    Chunk(
                        doc_type="Syllabus",
                        page=outcomes_page,
                        section_title="Course Outcomes",
                        chunk_type="course_outcome",
                        content=content,
                        metadata={"document_kind": "syllabus", "co_num": co_num},
                    )
                )
        else:
            chunks.append(
                Chunk(
                    doc_type="Syllabus",
                    page=outcomes_page,
                    section_title="Course Outcomes",
                    chunk_type="course_outcome",
                    content=f"Course Outcomes\n{co_buf}",
                    metadata={"document_kind": "syllabus"},
                )
            )

    # Practical chunks.
    for idx, (page, text) in enumerate(practicals, start=1):
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=page,
                section_title="List of Practicals",
                chunk_type="practical",
                content=text,
                metadata={"document_kind": "syllabus", "practical_no": idx},
            )
        )

    # References chunk.
    if ref_items:
        ref_text = "\n".join(text for _page, text in ref_items)
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=ref_items[0][0],
                section_title="Text Books & References",
                chunk_type="references",
                content=clean_reference_text(ref_text),
                metadata={"document_kind": "syllabus"},
            )
        )

    chunks.sort(
        key=lambda c: (c.page if c.page is not None else 0, c.chunk_type != "course_outcome")
    )
    return assign_chunk_indices(chunks)


def clean_reference_text(text: str) -> str:
    """Strip footer noise and tidy lines inside a references block."""
    text = re.sub(
        r"\b(Session\s+\d{4}\s*-\s*\d{2}|Page\s*:?\s*\d+/\d+)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[ \t]{2,}", " ", text)
    return "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())


def flush_unit_chunks(
    chunks: list[Chunk], unit_num: int | None, unit_buf: list[tuple]
) -> None:
    """Emit one chunk per buffered line of a unit, then clear the buffer."""
    if unit_num is None or not unit_buf:
        return
    unit_label = to_roman_numeral(unit_num)
    for page, text in unit_buf:
        m = TOPIC_SPLIT_RE.match(text)
        if m:
            topic_title = m.group(1).strip()
            body = normalize_whitespace(m.group(2))
            content = f"Unit {unit_label}\n{topic_title} : {body}"
            section_title = topic_title
        else:
            content = f"Unit {unit_label}\n{text}"
            section_title = truncate_text(text, 60)
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=page,
                section_title=section_title,
                chunk_type="unit",
                content=content,
                metadata={
                    "document_kind": "syllabus",
                    "unit": unit_num,
                    "unit_label": unit_label,
                },
            )
        )


def to_roman_numeral(n: int) -> str:
    """Return the Roman numeral string for ``n`` (falls back to ``str(n)``)."""
    for rom, val in ROMAN.items():
        if val == n:
            return rom
    return str(n)
