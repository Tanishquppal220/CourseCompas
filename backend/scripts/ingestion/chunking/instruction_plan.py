"""Chunker for Instruction Plan (IP) PDFs.

IP PDFs are 20+ page lecture-by-lecture tables. This module reconstructs
per-lecture chunks from the tables plus course overview, outcomes,
textbook/reference, and schedule chunks.

Tables are classified **once** into a typed kind (``TableKind``) by
:func:`classify_tables`; the chunk-building passes then dispatch on those kinds
instead of re-scanning every table's cells for each pattern.
"""

import re
from dataclasses import dataclass, field

from ..cleaning import clean_chunk_text, normalize_whitespace
from .chunk import (
    CO_RE,
    COURSE_CODE_RE,
    Chunk,
    collect_cleaned_text_items,
    truncate_text,
)
from .metadata import (
    IpCourseOutcomeMeta,
    IpCourseOverviewMeta,
    IpLectureMeta,
    IpReferenceMeta,
    IpTableRowMeta,
)

WEEK_RE = re.compile(r"\bWeek\s*(\d+)", re.IGNORECASE)
LECTURE_RE = re.compile(r"\bLecture\s*(\d+)", re.IGNORECASE)
REF_CODE_RE = re.compile(r"^(T|R)\s?-\s?\d+", re.IGNORECASE)
SINGLE_LABEL_RE = re.compile(r"^(Week|Lecture)$", re.IGNORECASE)
SPILL_WORDS = {"spill", "spill over", "over"}


class TableKind:
    """The semantic kind a single IP table is classified as."""

    OVERVIEW = "overview"
    BOOKS = "books"
    LECTURE = "lecture"
    SCHEDULE = "schedule"
    OTHER = "other"


@dataclass
class TableClaims:
    """The kinds each table was claimed by, in one classification pass."""

    kinds: list[set[str]] = field(default_factory=list)

    def has(self, index: int, kind: str) -> bool:
        return kind in self.kinds[index]


def join_table(table) -> str:
    """Serialize one table's cells into the string pattern checks run on."""
    return " ".join(" ".join(r) for r in table.rows)


def classify_tables(tables) -> TableClaims:
    """Classify every IP table once into its typed kind(s).

    Mirrors the historical claim order (overview-first-wins, then books,
    then lecture, then schedule) so a table still belongs to at most the same
    kinds it would have been consumed by in the old four-pass loop.
    """
    joineds = [join_table(table) for table in tables]
    kinds: list[set[str]] = [set() for _ in tables]

    # Course overview: only the first table with code + weightage.
    for ti, joined in enumerate(joineds):
        if "Course Weightage" in joined and COURSE_CODE_RE.search(joined):
            kinds[ti].add(TableKind.OVERVIEW)
            break

    # Textbook / reference tables.
    for ti, joined in enumerate(joineds):
        if _is_book_table(joined):
            kinds[ti].add(TableKind.BOOKS)

    # Lecture-plan tables (skip tables already claimed above).
    claimed = {ti for ti, ks in enumerate(kinds) if ks}
    for ti, joined in enumerate(joineds):
        if ti in claimed:
            continue
        if WEEK_RE.search(joined) or LECTURE_RE.search(joined):
            kinds[ti].add(TableKind.LECTURE)

    # Schedule / distribution tables (LTP weeks), still unclaimed.
    claimed = {ti for ti, ks in enumerate(kinds) if ks}
    for ti, joined in enumerate(joineds):
        if ti in claimed:
            continue
        if "week" in joined.lower() and "mte" in joined.lower():
            kinds[ti].add(TableKind.SCHEDULE)

    return TableClaims(kinds=kinds)


def _is_book_table(joined: str) -> bool:
    """True if a joined table looks like a textbook/reference table."""
    lower_joined = joined.lower()
    has_book_code = bool(re.search(r"\b[TR]\s?-\s?\d+\b", joined))
    return (
        "textbook" in lower_joined
        or "reference books" in lower_joined
        or (
            has_book_code
            and " by " in lower_joined
            and not WEEK_RE.search(joined)
            and not LECTURE_RE.search(joined)
        )
    )


def chunk_ip(text_items, tables) -> list[Chunk]:
    """Chunk a parsed Instruction Plan into lecture/reference/overview chunks."""
    chunks: list[Chunk] = []
    claims = classify_tables(tables)

    # ---- Course overview table: the one with course code + weightage ----
    for ti, table in enumerate(tables):
        if not claims.has(ti, TableKind.OVERVIEW):
            continue
        chunks.append(
            Chunk(
                doc_type="IP",
                page=table.page,
                section_title="Course Overview",
                chunk_type="course_overview",
                content=overview_from_course_table(table),
                metadata=IpCourseOverviewMeta(),
            )
        )
        break

    # ---- Course outcomes from text items ----
    for page, text in collect_cleaned_text_items(text_items):
        matches = list(CO_RE.finditer(clean_chunk_text(text)))
        for m in matches:
            co_num = int(m.group(1))
            chunks.append(
                Chunk(
                    doc_type="IP",
                    page=page,
                    section_title="Course Outcomes",
                    chunk_type="course_outcome",
                    content=f"CO{co_num} :: {normalize_whitespace(m.group(2))}",
                    metadata=IpCourseOutcomeMeta(co_num=co_num),
                )
            )

    # ---- Textbook / Reference tables ----
    for ti, table in enumerate(tables):
        if not claims.has(ti, TableKind.BOOKS):
            continue
        for pg, row in iter_book_rows(table):
            code, title, author, publisher = row
            section_title = f"{code} {title}"
            chunks.append(
                Chunk(
                    doc_type="IP",
                    page=pg,
                    section_title=truncate_text(section_title, 120),
                    chunk_type="reference",
                    content=f"{code}: {title} by {author}, {publisher}".strip().rstrip(
                        ","
                    ),
                    metadata=IpReferenceMeta(ref_code=code),
                )
            )

    # ---- Lecture-plan tables ----
    carried_week = None
    for ti, table in enumerate(tables):
        if not claims.has(ti, TableKind.LECTURE):
            continue

        current: dict | None = None
        for row in table.rows:
            meaningful = [c for c in row if c.strip()]
            if not meaningful:
                continue
            classified = classify_lecture_cells(meaningful)
            if classified["week"] is not None:
                carried_week = classified["week"]

            if classified["lecture"] is not None:
                if current is not None:
                    append_lecture_chunk(chunks, current)
                current = {
                    "week": carried_week,
                    "lecture": classified["lecture"],
                    "topic": classified["topic"],
                    "refs": classified["refs"],
                    "desc": classified["desc"],
                    "outcomes": classified["outcomes"],
                    "pedagog": classified["pedagog"],
                    "page": table.page,
                }
                if classified["week"] is not None:
                    carried_week = classified["week"]
            else:
                # Continuation row for the current lecture.
                if current is not None:
                    if classified["topic"] and not current["topic"]:
                        current["topic"] = classified["topic"]
                    current["desc"].extend(classified["desc"])
                    current["outcomes"].extend(classified["outcomes"])
                    if classified["outcomes"] and not current["outcomes"]:
                        current["outcomes"] = classified["outcomes"]
        if current is not None:
            append_lecture_chunk(chunks, current)

    # ---- Schedule / distribution tables (LTP weeks) ----
    for ti, table in enumerate(tables):
        if not claims.has(ti, TableKind.SCHEDULE):
            continue
        row_text = "; ".join(" | ".join(r) for r in table.rows if any(r))
        chunks.append(
            Chunk(
                doc_type="IP",
                page=table.page,
                section_title="LTP Week Distribution",
                chunk_type="table_row",
                content=row_text,
                metadata=IpTableRowMeta(),
            )
        )

    chunks.sort(key=lambda c: (c.page == 0, c.page, c.chunk_type != "course_overview"))
    return chunks


def merge_label_cells(cells: list) -> list:
    """Fold adjacent ('Lecture', '2') / ('Week', '1') cells into one."""
    merged = []
    for i, cell in enumerate(cells):
        if (
            SINGLE_LABEL_RE.match(cell.strip())
            and i + 1 < len(cells)
            and cells[i + 1].strip().isdigit()
        ):
            merged.append(f"{cell.strip()} {cells[i + 1].strip()}")
            continue
        if (
            i > 0
            and SINGLE_LABEL_RE.match(cells[i - 1].strip())
            and cell.strip().isdigit()
        ):
            continue
        merged.append(cell)
    return merged


def clean_table_cells(cells: list) -> list:
    """Merge label cells and drop blank / spill-over cells."""
    cells = merge_label_cells(cells)
    cleaned = []
    for cell in cells:
        cell = cell.strip()
        if not cell:
            continue
        lowered = cell.lower()
        if lowered in SPILL_WORDS or "spill over" in lowered:
            continue
        cleaned.append(cell)
    return cleaned


def classify_lecture_cells(cells) -> dict:
    """Split a lecture row's cells into week/lecture/topic/refs/desc/outcomes."""
    out = {
        "week": None,
        "lecture": None,
        "topic": "",
        "refs": [],
        "desc": [],
        "outcomes": [],
        "pedagog": [],
    }
    cleaned = clean_table_cells(cells)
    for i, cell in enumerate(cleaned):
        lowered = cell.lower()

        m = WEEK_RE.search(cell)
        if m and len(cell) < 30:
            out["week"] = int(m.group(1))
        if i == 0 and cell.isdigit() and not m:
            out["week"] = int(cell)
        m = LECTURE_RE.search(cell)
        if m and len(cell) < 30:
            out["lecture"] = int(m.group(1))
            continue

        if REF_CODE_RE.match(cell):
            out["refs"].append(cell)
            continue
        if re.fullmatch(r"[TRRifetories0-9\s\-/]+", cell) and len(cell) < 12:
            continue

        if (
            re.search(r"\bL\d+\s*:", cell)
            or "lecture-0" in lowered
            or "this lecture" in lowered
            or "this module" in lowered
        ):
            out["desc"].append(cell)
            continue
        if (
            "students would be able" in lowered
            or "understand the" in lowered
            or "understand how" in lowered
            or ("understanding" in lowered and "able" in lowered)
            or "will be able to" in lowered
        ):
            out["outcomes"].append(cell)
            continue
        if (
            "presentation" in lowered
            or "demonstration" in lowered
            or "programming hands-on" in lowered
            or "case study" in lowered
        ):
            out["pedagog"].append(cell)
            continue

        # Default: longest leftover cell is the broad topic.
        if len(cell) >= len(out["topic"]):
            out["topic"] = cell

    out["refs"] = " ".join(out["refs"])
    return out


def format_lecture_row(row: dict) -> str:
    """Render a classified lecture row as a readable multi-line block."""
    parts = []
    if row["week"] is not None:
        parts.append(f"Week: {row['week']}")
    if row["lecture"] is not None:
        parts.append(f"Lecture: {row['lecture']}")
    if row["topic"]:
        parts.append(f"Broad Topic: {row['topic']}")
    if row["refs"]:
        parts.append(f"Text/References: {row['refs']}")
    if row["desc"]:
        parts.append(f"Lecture Description: {' '.join(row['desc'])}")
    if row["outcomes"]:
        parts.append(f"Learning Outcomes: {' '.join(row['outcomes'])}")
    if row["pedagog"]:
        parts.append(f"Pedagogical Tool: {' '.join(row['pedagog'])}")
    return "\n".join(parts)


def append_lecture_chunk(chunks: list[Chunk], row: dict) -> None:
    """Append the chunk for one completed lecture row."""
    if not row or row["lecture"] is None:
        return
    content = format_lecture_row(row)
    if not content.strip():
        return
    section_title = (
        truncate_text(row["topic"], 160) if row["topic"] else f"Lecture {row['lecture']}"
    )
    chunks.append(
        Chunk(
            doc_type="IP",
            page=row["page"],
            section_title=section_title,
            chunk_type="lecture",
            content=content,
            metadata=IpLectureMeta(week=row.get("week"), lecture=row["lecture"]),
        )
    )


def iter_book_rows(table):
    """Yield ``(page, (ref_code, title, author, publisher))`` for a book table."""
    for row in table.rows:
        cells = [c.strip() for c in row if c.strip()]
        if not cells:
            continue
        m = re.search(r"^([TR])\s?-\s?(\d+)$", cells[0], re.IGNORECASE)
        if not m:
            continue
        code = f"{m.group(1).upper()}-{m.group(2)}"
        rest = cells[1:]
        if not rest:
            continue
        title = rest[0]
        author = rest[1] if len(rest) > 1 else ""
        publisher = rest[2] if len(rest) > 2 else ""
        yield table.page, (code, title, author, publisher)


def overview_from_course_table(table) -> str:
    """Serialize the IP course header table into a readable block."""
    seen = []
    for row in table.rows:
        cells = [c.strip() for c in row if c.strip()]
        if not cells:
            continue
        seen.append(" | ".join(cells))
    return "\n".join(seen)