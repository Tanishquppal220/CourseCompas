"""Chunker for the academic benefits markdown (``benefits_clean.md``).

Produces policy-overview, criteria-row, and special-note chunks.
"""

from pathlib import Path

from .chunk import Chunk
from .metadata import (
    BenefitsCriteriaRowMeta,
    BenefitsPolicyOverviewMeta,
    BenefitsSpecialNoteMeta,
)

SECTION_BLOCK_WORDS = {
    "category",
    "stipend",
    "sr. no",
    "types of projects",
    "achievement level",
}


def chunk_benefits(md_path: Path) -> list[Chunk]:
    """Read the benefits markdown and split it into semantic chunks."""
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
                    page=None,
                    section_title=current_section,
                    chunk_type="policy_overview",
                    content=f"Section: {current_section}\n"
                    f"Type: Policy Overview & Eligibility Rules\n"
                    f"Details: {description_text}",
                    metadata=BenefitsPolicyOverviewMeta(
                        section=current_section,
                        table_index=table_index,
                    ),
                )
            )

        # Tabular rows with backward & forward fill.
        if header_idx != -1 and header_idx + 1 < len(lines):
            headers = [h if h else f"Field_{i + 1}" for i, h in enumerate(headers)]

            benefit_col_name = None
            for h in headers:
                if any(k in h.lower() for k in ["benefit", "academic benefit"]):
                    benefit_col_name = h
                    break

            raw_rows = []
            for data_line in lines[header_idx + 1 :]:
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
                for h, val in zip(headers, cells):
                    if val:
                        last_values[h] = val
                        row_dict[h] = val
                    elif h in last_values and any(
                        k in h.lower()
                        for k in [
                            "stipend",
                            "duration",
                            "category",
                            "types",
                            "achievement",
                        ]
                    ):
                        row_dict[h] = last_values[h]

                if len(row_dict) < 1:
                    continue
                context_lines = [f"Section: {current_section}"]
                for k, v in row_dict.items():
                    context_lines.append(f"{k}: {v}")
                if description_text and len(row_dict) > 1:
                    context_lines.append(
                        f"(General Policy: {description_text[:120]}...)"
                    )

                chunks.append(
                    Chunk(
                        doc_type="Benefits",
                        page=None,
                        section_title=current_section,
                        chunk_type="criteria_row",
                        content="\n".join(context_lines),
                        metadata=BenefitsCriteriaRowMeta(
                            section=current_section,
                            table_index=table_index,
                            fields=row_dict,
                        ),
                    )
                )

        # Special note chunks.
        for note in footer_notes:
            chunks.append(
                Chunk(
                    doc_type="Benefits",
                    page=None,
                    section_title=current_section,
                    chunk_type="special_note",
                    content=f"Section: {current_section}\nSpecial Policy Note: {note}",
                    metadata=BenefitsSpecialNoteMeta(
                        section=current_section,
                        table_index=table_index,
                    ),
                )
            )

    return chunks
