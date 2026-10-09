"""Chunker for Syllabus PDFs (2-3 page, highly templated documents).

Turns a syllabus into course-overview, course-outcome, practical, reference,
and per-unit topic chunks.

Two phases: :func:`classify_syllabus` first sorts every text item into typed
sections (overview / outcomes / practicals / references / units), then small
builders (:func:`build_overview_chunk`, :func:`build_outcome_chunks`, ...)
emit the chunks from those sections.
"""

import re
from dataclasses import dataclass, field

from ..cleaning import normalize_whitespace
from .chunk import (
    CO_RE,
    Chunk,
    collect_cleaned_text_items,
    truncate_text,
)
from .metadata import (
    SyllabusCourseOutcomeMeta,
    SyllabusCourseOverviewMeta,
    SyllabusOutcomeBlobMeta,
    SyllabusPracticalMeta,
    SyllabusReferencesMeta,
    SyllabusUnitMeta,
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


@dataclass
class SyllabusSections:
    """The typed sections a syllabus is classified into before chunking."""

    overview: list = field(default_factory=list)  # (page, text)
    outcomes: list = field(default_factory=list)  # (page, text)
    practicals: list = field(default_factory=list)  # (page, text)
    references: list = field(default_factory=list)  # (page, text)
    # unit_no -> [(page, text)] in first-appearance order.
    units: dict = field(default_factory=dict)


def chunk_syllabus(text_items) -> list[Chunk]:
    """Chunk a parsed Syllabus PDF into semantic pieces."""
    sections = classify_syllabus(text_items)

    chunks: list[Chunk] = []

    # Construction order matters: the final sort is stable and does not
    # distinguish unit/overview/practical/reference chunks (only course
    # outcomes sort ahead of everything else). Emit in the same order the
    # original state machine did: units first, then overview, outcomes,
    # practicals, references.
    chunks.extend(build_unit_chunks(sections))

    overview = build_overview_chunk(sections)
    if overview is not None:
        chunks.append(overview)

    chunks.extend(build_outcome_chunks(sections))
    chunks.extend(build_practical_chunks(sections))

    references = build_reference_chunk(sections)
    if references is not None:
        chunks.append(references)

    chunks.sort(
        key=lambda c: (c.page if c.page is not None else 0, c.chunk_type != "course_outcome")
    )
    return chunks


def classify_syllabus(text_items) -> SyllabusSections:
    """Sort every text item into its section, preserving per-section order."""
    sections = SyllabusSections()
    current_unit: int | None = None
    unit_buf: list = []  # (page, text) pending for the current unit
    in_refs = False

    for page, text in collect_cleaned_text_items(text_items):
        lowered = text.lower()

        # Once references start, everything after belongs to them (sticky).
        if in_refs:
            sections.references.append((page, text))
            continue

        # LTP line.
        if re.search(r"\bCredits\b", text) and re.search(r"\bL\s*:", text):
            sections.overview.append((page, text))
            continue

        # Unit markers flip state and flush the previous unit's topic lines.
        m = UNIT_MARKER_RE.match(text)
        if m:
            store_unit(sections, current_unit, unit_buf)
            current_unit = ROMAN.get(m.group(1), None)
            unit_buf = []
            continue

        # Practicals: "01. Write a program ..."
        if PRACTICAL_RE.match(text) or re.match(r"^•\s*\d{2}\.", text):
            sections.practicals.append((page, text))
            continue
        if "list of practical" in lowered:
            continue

        # Text books / references enter references mode.
        if (
            text.startswith(("Text Books", "References"))
            or "text books:" in text[:40].lower()
        ):
            in_refs = True
            sections.references.append((page, text))
            continue

        # Course outcomes block.
        if "course outcomes" in lowered[:40] or re.search(r"CO\d+\s*::", text):
            sections.outcomes.append((page, text))
            continue

        # Regular content associates with the current unit, if any.
        if current_unit is not None:
            unit_buf.append((page, text))
        else:
            # Content before any unit marker (intro blurb).
            if "course outcomes" in lowered or "through this course" in lowered:
                sections.outcomes.append((page, text))
            else:
                sections.overview.append((page, text))

    store_unit(sections, current_unit, unit_buf)
    return sections


def store_unit(sections: SyllabusSections, unit_num: int | None, unit_buf: list) -> None:
    """Fold a finished unit buffer into ``sections.units`` (in first-seen order)."""
    if unit_num is not None and unit_buf:
        sections.units.setdefault(unit_num, []).extend(unit_buf)


def build_overview_chunk(sections: SyllabusSections) -> Chunk | None:
    """Emit the course-overview chunk from the pre-unit blurb + LTP line."""
    if not sections.overview:
        return None
    content_parts = [text for _page, text in sections.overview]
    return Chunk(
        doc_type="Syllabus",
        page=sections.overview[0][0],
        section_title="Course Overview",
        chunk_type="course_overview",
        content="\n".join(content_parts),
        metadata=SyllabusCourseOverviewMeta(),
    )


def build_outcome_chunks(sections: SyllabusSections) -> list[Chunk]:
    """Emit one chunk per course outcome (or one blob when no CO markers)."""
    if not sections.outcomes:
        return []

    chunks: list[Chunk] = []
    outcomes_page = sections.outcomes[0][0]
    co_buf = "\n".join(text for _page, text in sections.outcomes)
    co_buf = re.sub(
        r"\s*Through this course students should be able to\s*$",
        "",
        co_buf,
        flags=re.IGNORECASE,
    )
    co_buf = re.sub(r"^Course Outcomes\s*:", "", co_buf, flags=re.IGNORECASE).strip()

    if not co_buf:
        return chunks

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
                    metadata=SyllabusCourseOutcomeMeta(co_num=co_num),
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
                metadata=SyllabusOutcomeBlobMeta(),
            )
        )
    return chunks


def build_practical_chunks(sections: SyllabusSections) -> list[Chunk]:
    """Emit one chunk per practical, numbered in reading order."""
    chunks: list[Chunk] = []
    for idx, (page, text) in enumerate(sections.practicals, start=1):
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=page,
                section_title="List of Practicals",
                chunk_type="practical",
                content=text,
                metadata=SyllabusPracticalMeta(practical_no=idx),
            )
        )
    return chunks


def build_reference_chunk(sections: SyllabusSections) -> Chunk | None:
    """Emit the single references chunk (if any reference items were seen)."""
    if not sections.references:
        return None
    ref_text = "\n".join(text for _page, text in sections.references)
    return Chunk(
        doc_type="Syllabus",
        page=sections.references[0][0],
        section_title="Text Books & References",
        chunk_type="references",
        content=clean_reference_text(ref_text),
        metadata=SyllabusReferencesMeta(),
    )


def build_unit_chunks(sections: SyllabusSections) -> list[Chunk]:
    """Emit one chunk per buffered line of every unit."""
    chunks: list[Chunk] = []
    for unit_num, unit_buf in sections.units.items():
        flush_unit_chunks(chunks, unit_num, unit_buf)
    return chunks


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
    chunks: list[Chunk], unit_num: int | None, unit_buf: list
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
                metadata=SyllabusUnitMeta(unit=unit_num, unit_label=unit_label),
            )
        )


def to_roman_numeral(n: int) -> str:
    """Return the Roman numeral string for ``n`` (falls back to ``str(n)``)."""
    for rom, val in ROMAN.items():
        if val == n:
            return rom
    return str(n)