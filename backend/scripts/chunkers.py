"""Semantic chunkers for CourseCompass documents.

Three chunkers, one per source shape:

  * Syllabus PDFs  (2-3 page highly templated documents)  -> course unit/topic,
    course outcome, practical, references, overview chunks.
  * IP PDFs        (20+ page lecture-by-lecture tables)   -> per-lecture chunks
    reconstructed from Docling table cells, plus course overview, outcomes,
    textbook/reference, and schedule chunks.
  * benefits_clean.md                                     -> policy overview,
    criteria-row, and special-note chunks.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from cleaners import clean_chunk_text, is_boilerplate, normalize_whitespace

COURSE_CODE_RE = re.compile(r"\b([A-Z]{3}\d{3})\b")
UNIT_MARKER_RE = re.compile(r"^Unit\s+([IVX]+)$")
PRACTICAL_RE = re.compile(r"^\d{2}\.[^\d]")
REF_CONT_RE = re.compile(r"^\d\s*\.\s")
TOPIC_SPLIT_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 &/()\-',.]{2,90}?)\s*[:：]\s*(.+)$", re.DOTALL)
CO_RE = re.compile(r"CO(\d+)\s*::\s*(.+?)(?=CO\d+\s*::|$)", re.DOTALL)

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
         "VII": 7, "VIII": 8, "IX": 9, "X": 10}


@dataclass
class Chunk:
    doc_type: str
    page: int
    section_title: str
    chunk_type: str
    content: str
    metadata: dict = field(default_factory=dict)


def _truncate(text: str, limit: int = 200) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _collect_text_items(text_items):
    """Yield cleaned, non-boilerplate text items in reading order."""
    for item in text_items:
        text = clean_chunk_text(item.get("text", ""))
        if not text or is_boilerplate(text):
            continue
        yield item.get("page", 0), text


# ---------------------------------------------------------------------------
# Syllabus
# ---------------------------------------------------------------------------


def chunk_syllabus(text_items) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_unit: int | None = None
    unit_buf: list[tuple] = []          # (page, topic_title, content)
    outcomes_buf: list[str] = []
    practicals: list[tuple] = []        # (page, text)
    ref_items: list[str] = []
    in_refs = False
    overview_parts: list[tuple] = []

    for page, text in _collect_text_items(text_items):
        lowered = text.lower()

        if in_refs:
            ref_items.append(text)
            continue

        # Course header line: "CSE273:FOUNDATIONS OF MACHINE LEARNING"
        if not courses_ok() and COURSE_CODE_RE.match(text) and ":" in text:
            overview_parts.append((page, "Course", text))
            continue
        # LTP line
        if re.search(r"\bCredits\b", text) and re.search(r"\bL\s*:", text):
            overview_parts.append((page, "LTP", text))
            continue

        # Unit markers flip state and flush previous unit's topic chunks.
        m = UNIT_MARKER_RE.match(text)
        if m:
            _flush_unit(chunks, current_unit, unit_buf)
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
        if text.startswith(("Text Books", "References")) or "text books:" in text[:40].lower():
            in_refs = True
            ref_items.append(text)
            continue

        # Course outcomes block.
        if "course outcomes" in lowered[:40] or re.search(r"CO\d+\s*::", text):
            outcomes_buf.append(text)
            continue

        # Regular content associates with the current unit, if any.
        if current_unit is not None:
            unit_buf.append((page, text))
        else:
            # Content before any unit marker (intro blurb).
            if "course outcomes" in lowered or "through this course" in lowered:
                outcomes_buf.append(text)
            else:
                overview_parts.append((page, "Overview", text))

    _flush_unit(chunks, current_unit, unit_buf)

    # Course overview chunk.
    if overview_parts:
        content_parts = []
        for _pg, label, text in overview_parts:
            content_parts.extend([text])
        ov_chunk = Chunk(
            doc_type="Syllabus",
            page=overview_parts[0][0],
            section_title="Course Overview",
            chunk_type="course_overview",
            content="\n".join(content_parts),
            metadata={"document_kind": "syllabus"},
        )
        chunks.append(ov_chunk)

    # Course outcomes chunks.
    co_buf = "\n".join(outcomes_buf)
    co_buf = re.sub(r"\s*Through this course students should be able to\s*$", "", co_buf, flags=re.IGNORECASE)
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
                        page=1,
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
                    page=1,
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
        ref_text = "\n".join(ref_items)
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=2,
                section_title="Text Books & References",
                chunk_type="references",
                content=_clean_refs(ref_text),
                metadata={"document_kind": "syllabus"},
            )
        )

    chunks.sort(key=lambda c: (c.page, c.chunk_type != "course_outcome"))
    for i, c in enumerate(chunks):
        c.metadata["chunk_index"] = i
    return chunks


def _clean_refs(text: str) -> str:
    text = re.sub(r"\b(Session\s+\d{4}\s*-\s*\d{2}|Page\s*:?\s*\d+/\d+)\b",
                  "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())


def _flush_unit(chunks: list[Chunk], unit_num: int | None, unit_buf: list[tuple]):
    if unit_num is None or not unit_buf:
        return
    unit_label = _roman(unit_num)
    for page, text in unit_buf:
        m = TOPIC_SPLIT_RE.match(text)
        if m:
            topic_title = m.group(1).strip()
            body = normalize_whitespace(m.group(2))
            content = f"Unit {unit_label}\n{topic_title} : {body}"
            section_title = topic_title
        else:
            content = f"Unit {unit_label}\n{text}"
            section_title = _truncate(text, 60)
        chunks.append(
            Chunk(
                doc_type="Syllabus",
                page=page,
                section_title=section_title,
                chunk_type="unit",
                content=content,
                metadata={"document_kind": "syllabus", "unit": unit_num,
                          "unit_label": unit_label},
            )
        )


def _roman(n: int) -> str:
    for rom, val in ROMAN.items():
        if val == n:
            return rom
    return str(n)


def courses_ok() -> bool:
    return True


# ---------------------------------------------------------------------------
# Instruction Plan (IP)
# ---------------------------------------------------------------------------

_WEEK_RE = re.compile(r"\bWeek\s*(\d+)", re.IGNORECASE)
_LECTURE_RE = re.compile(r"\bLecture\s*(\d+)", re.IGNORECASE)
_REF_CODE_RE = re.compile(r"^(T|R)\s?-\s?\d+", re.IGNORECASE)
_REF_CELL_RE = re.compile(r"\b(T|R)\d*\s*[-,]?\s*\d*\b", re.IGNORECASE)
_SINGLE_LABEL_RE = re.compile(r"^(Week|Lecture)$", re.IGNORECASE)
_SPILL_WORDS = {"spill", "spill over", "over"}


def _merge_label_cells(cells: list) -> list:
    """Fold adjacent ('Lecture', '2') / ('Week', '1') cells into one."""
    merged = []
    for i, cell in enumerate(cells):
        if (_SINGLE_LABEL_RE.match(cell.strip())
                and i + 1 < len(cells)
                and cells[i + 1].strip().isdigit()):
            merged.append(f"{cell.strip()} {cells[i + 1].strip()}")
            continue
        if i > 0 and _SINGLE_LABEL_RE.match(cells[i - 1].strip()) and cell.strip().isdigit():
            continue
        merged.append(cell)
    return merged


def _clean_cells(cells: list) -> list:
    cells = _merge_label_cells(cells)
    cleaned = []
    for cell in cells:
        cell = cell.strip()
        if not cell:
            continue
        lowered = cell.lower()
        if lowered in _SPILL_WORDS or "spill over" in lowered:
            continue
        cleaned.append(cell)
    return cleaned


def _classify_lecture_cells(cells) -> dict:
    out = {"week": None, "lecture": None, "topic": "", "refs": [],
           "desc": [], "outcomes": [], "pedagog": []}
    cleaned = _clean_cells(cells)
    for i, cell in enumerate(cleaned):
        lowered = cell.lower()

        m = _WEEK_RE.search(cell)
        if m and len(cell) < 30:
            out["week"] = int(m.group(1))
        if i == 0 and cell.isdigit() and not m:
            out["week"] = int(cell)
        m = _LECTURE_RE.search(cell)
        if m and len(cell) < 30:
            out["lecture"] = int(m.group(1))
            continue

        if _REF_CODE_RE.match(cell):
            out["refs"].append(cell)
            continue
        if re.fullmatch(r"[TRRifetories0-9\s\-/]+", cell) and len(cell) < 12:
            continue

        if (re.search(r"\bL\d+\s*:", cell) or "lecture-0" in lowered
                or "this lecture" in lowered or "this module" in lowered):
            out["desc"].append(cell)
            continue
        if ("students would be able" in lowered
                or "understand the" in lowered or "understand how" in lowered
                or ("understanding" in lowered and "able" in lowered)
                or "will be able to" in lowered):
            out["outcomes"].append(cell)
            continue
        if ("presentation" in lowered or "demonstration" in lowered
                or "programming hands-on" in lowered or "case study" in lowered):
            out["pedagog"].append(cell)
            continue

        # Default: longest leftover cell is the broad topic.
        if len(cell) >= len(out["topic"]):
            out["topic"] = cell

    out["refs"] = " ".join(out["refs"])
    return out


def _format_lecture(row: dict) -> str:
    parts = []
    if row["week"] is not None:
        parts.append(f"Week: {row['week']}")
    if row["lecture"] is not None and "lecture" not in (row.get("_skip_lecture") or []):
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


def chunk_ip(text_items, tables) -> list[Chunk]:
    chunks: list[Chunk] = []
    handled_tables = set()

    # ---- Course overview table: the one with course code + weightage ----
    for ti, table in enumerate(tables):
        joined = " ".join(" ".join(r) for r in table.rows)
        if "Course Weightage" in joined and COURSE_CODE_RE.search(joined):
            handled_tables.add(ti)
            overview_content = _overview_from_table(table)
            chunks.append(
                Chunk(
                    doc_type="IP",
                    page=table.page,
                    section_title="Course Overview",
                    chunk_type="course_overview",
                    content=overview_content,
                    metadata={"document_kind": "ip"},
                )
            )
            break

    # ---- Course outcomes from text items ----
    for page, text in _collect_text_items(text_items):
        matches = list(CO_RE.finditer(clean_chunk_text(text)))
        if matches:
            for m in matches:
                co_num = int(m.group(1))
                chunks.append(
                    Chunk(
                        doc_type="IP",
                        page=page,
                        section_title="Course Outcomes",
                        chunk_type="course_outcome",
                        content=f"CO{co_num} :: {normalize_whitespace(m.group(2))}",
                        metadata={"document_kind": "ip", "co_num": co_num},
                    )
                )

    # ---- Textbook / Reference tables ----
    for ti, table in enumerate(tables):
        joined = " ".join(" ".join(r) for r in table.rows)
        lower_joined = joined.lower()
        has_book_code = bool(re.search(r"\b[TR]\s?-\s?\d+\b", joined))
        is_book_table = (
            "textbook" in lower_joined
            or "reference books" in lower_joined
            or (
                has_book_code
                and " by " in lower_joined
                and not _WEEK_RE.search(joined)
                and not _LECTURE_RE.search(joined)
            )
        )
        if is_book_table:
            handled_tables.add(ti)
            for pg, row in _iter_book_rows(table):
                code, title, author, publisher = row
                section_title = f"{code} {title}"
                chunks.append(
                    Chunk(
                        doc_type="IP",
                        page=pg,
                        section_title=_truncate(section_title, 120),
                        chunk_type="reference",
                        content=f"{code}: {title} by {author}, {publisher}".strip().rstrip(","),
                        metadata={"document_kind": "ip", "ref_code": code},
                    )
                )

    # ---- Lecture-plan tables ----
    carried_week = None
    for ti, table in enumerate(tables):
        if ti in handled_tables:
            continue
        joined = " ".join(" ".join(r) for r in table.rows)
        if not (_WEEK_RE.search(joined) or _LECTURE_RE.search(joined)):
            continue
        handled_tables.add(ti)

        current: dict | None = None
        for row in table.rows:
            meaningful = [c for c in row if c.strip()]
            if not meaningful:
                continue
            classified = _classify_lecture_cells(meaningful)
            if classified["week"] is not None:
                carried_week = classified["week"]

            if classified["lecture"] is not None:
                if current is not None:
                    _append_lecture_chunk(chunks, current)
                current = {"week": carried_week, "lecture": classified["lecture"],
                           "topic": classified["topic"], "refs": classified["refs"],
                           "desc": classified["desc"], "outcomes": classified["outcomes"],
                           "pedagog": classified["pedagog"], "page": table.page}
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
            _append_lecture_chunk(chunks, current)

    # ---- Schedule / distribution tables (LTP weeks) ----
    for ti, table in enumerate(tables):
        if ti in handled_tables:
            continue
        joined = " ".join(" ".join(r) for r in table.rows)
        if "week" in joined.lower() and "mte" in joined.lower():
            handled_tables.add(ti)
            row_text = "; ".join(" | ".join(r) for r in table.rows if any(r))
            chunks.append(
                Chunk(
                    doc_type="IP",
                    page=table.page,
                    section_title="LTP Week Distribution",
                    chunk_type="table_row",
                    content=row_text,
                    metadata={"document_kind": "ip"},
                )
            )

    chunks.sort(key=lambda c: (c.page == 0, c.page, c.chunk_type != "course_overview"))
    return chunks


def _append_lecture_chunk(chunks: list[Chunk], row: dict):
    if not row or row["lecture"] is None:
        return
    content = _format_lecture(row)
    if not content.strip():
        return
    section_title = _truncate(row["topic"], 160) if row["topic"] else f"Lecture {row['lecture']}"
    chunks.append(
        Chunk(
            doc_type="IP",
            page=row["page"],
            section_title=section_title,
            chunk_type="lecture",
            content=content,
            metadata={
                "document_kind": "ip",
                "week": row.get("week"),
                "lecture": row["lecture"],
            },
        )
    )


def _iter_book_rows(table):
    """Yield (ref_code, title, author, publisher) for a Text/Reference table."""
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


def _overview_from_table(table) -> str:
    """Serialize the IP course header table into a readable block."""
    seen = []
    for row in table.rows:
        cells = [c.strip() for c in row if c.strip()]
        if not cells:
            continue
        seen.append(" | ".join(cells))
    return "\n".join(seen)


# ---------------------------------------------------------------------------
# Benefits markdown
# ---------------------------------------------------------------------------


SECTION_BLOCK_WORDS = {"category", "stipend", "sr. no", "types of projects", "achievement level"}


def chunk_benefits(md_path: Path) -> list[Chunk]:
    content = md_path.read_text(encoding="utf-8")
    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]

    chunks: list[Chunk] = []
    current_section = "Academic Benefits"
    current_overview = ""
    table_index = 0

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines or not lines[0].startswith("|"):
            continue

        table_index += 1

        # Detect section title from first row.
        first_row = [c.strip() for c in lines[0].split("|")[1:-1]]
        non_empty = [c for c in first_row if c]
        if non_empty and len(non_empty) == 1 and not lines[0].startswith("| ---"):
            title_candidate = non_empty[0]
            if not any(k in title_candidate.lower() for k in SECTION_BLOCK_WORDS):
                current_section = title_candidate

        # Extract overview paragraph, column headers, and footer notes.
        headers = []
        header_idx = -1
        description_text = ""
        footer_notes = []

        for r_idx, line in enumerate(lines):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            meaningful = [c for c in cells if c]

            if len(meaningful) == 1 and len(meaningful[0]) > 60:
                description_text = meaningful[0]
            elif any(k in " ".join(meaningful).lower() for k in SECTION_BLOCK_WORDS):
                header_idx = r_idx
                headers = cells
                break

        if current_overview and not description_text:
            description_text = current_overview

        # Policy overview & eligibility rules chunk.
        if description_text:
            chunks.append(
                Chunk(
                    doc_type="Benefits",
                    page=table_index,
                    section_title=current_section,
                    chunk_type="policy_overview",
                    content=f"Section: {current_section}\n"
                            f"Type: Policy Overview & Eligibility Rules\n"
                            f"Details: {description_text}",
                    metadata={"section": current_section, "table_index": table_index,
                              "type": "policy_overview"},
                )
            )

        # Tabular rows with backward & forward fill.
        if header_idx != -1 and header_idx + 1 < len(lines):
            headers = [h if h else f"Field_{i+1}" for i, h in enumerate(headers)]

            benefit_col_name = None
            for h in headers:
                if any(k in h.lower() for k in ["benefit", "academic benefit"]):
                    benefit_col_name = h
                    break

            raw_rows = []
            for data_line in lines[header_idx + 1:]:
                if data_line.startswith("| ---"):
                    continue
                cells = [c.strip() for c in data_line.split("|")[1:-1]]
                meaningful = [c for c in cells if c]
                if not meaningful:
                    continue
                if len(meaningful) == 1 and len(meaningful[0]) > 40:
                    footer_notes.append(meaningful[0])
                    continue
                raw_rows.append(cells)

            if benefit_col_name:
                b_idx = headers.index(benefit_col_name)
                next_benefit = ""
                for r in reversed(raw_rows):
                    if b_idx < len(r) and r[b_idx]:
                        next_benefit = r[b_idx]
                    elif b_idx < len(r) and not r[b_idx] and next_benefit:
                        r[b_idx] = next_benefit

            last_values = {}
            for cells in raw_rows:
                row_dict = {}
                for col_idx, (h, val) in enumerate(zip(headers, cells)):
                    if val:
                        last_values[h] = val
                        row_dict[h] = val
                    elif h in last_values and any(
                        k in h.lower() for k in ["stipend", "duration", "category", "types", "achievement"]
                    ):
                        row_dict[h] = last_values[h]

                if len(row_dict) < 1:
                    continue
                context_lines = [f"Section: {current_section}"]
                for k, v in row_dict.items():
                    context_lines.append(f"{k}: {v}")
                if description_text and len(row_dict) > 1:
                    context_lines.append(f"(General Policy: {description_text[:120]}...)")

                chunks.append(
                    Chunk(
                        doc_type="Benefits",
                        page=table_index,
                        section_title=current_section,
                        chunk_type="criteria_row",
                        content="\n".join(context_lines),
                        metadata={"section": current_section, "table_index": table_index,
                                  "fields": row_dict},
                    )
                )

        # Special note chunks.
        for note in footer_notes:
            chunks.append(
                Chunk(
                    doc_type="Benefits",
                    page=table_index,
                    section_title=current_section,
                    chunk_type="special_note",
                    content=f"Section: {current_section}\nSpecial Policy Note: {note}",
                    metadata={"section": current_section, "table_index": table_index,
                              "type": "special_policy_note"},
                )
            )

    for i, c in enumerate(chunks):
        c.metadata["chunk_index"] = i
    return chunks