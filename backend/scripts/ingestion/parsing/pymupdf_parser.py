"""PyMuPDF + pymupdf4llm parser backend (default, fast)."""

import re
from pathlib import Path

from .models import ParsedPdf, ParsedTable, cell_to_text


def strip_markdown_tables(block: str) -> str:
    """Remove markdown table lines from ``block``, keeping surrounding prose.

    pymupdf4llm renders tables as markdown, but the same tables are extracted
    separately into ``ParsedPdf.tables``. Dropping the markdown rows here stops
    every table from being stored (and embedded) twice.
    """
    kept = [line for line in block.splitlines() if not line.strip().startswith("|")]
    return "\n".join(kept).strip()


def parse_pdf_with_pymupdf(pdf_path: Path) -> ParsedPdf:
    """Parse a PDF with PyMuPDF for tables and pymupdf4llm for text."""
    import pymupdf
    import pymupdf4llm

    parsed = ParsedPdf(source=str(pdf_path))

    doc = pymupdf.open(pdf_path)

    try:
        text_items = []

        for page_number, page in enumerate(doc, start=1):
            # -------------------------------------------------------------
            # 1. DETECT TABLES
            # -------------------------------------------------------------
            try:
                table_finder = page.find_tables()

                for table in table_finder.tables:
                    rows = []

                    for row in table.extract():
                        clean_row = [cell_to_text(cell) for cell in row]

                        # Remove trailing empty columns.
                        while clean_row and clean_row[-1] == "":
                            clean_row.pop()

                        # Ignore completely empty rows.
                        if any(clean_row):
                            rows.append(clean_row)

                    if not rows:
                        continue

                    parsed.tables.append(
                        ParsedTable(
                            page=page_number,
                            rows=rows,
                            n_rows=len(rows),
                            n_cols=max(len(row) for row in rows),
                        )
                    )

            except Exception as exc:  # noqa: BLE001
                print(
                    f"[parse] table extraction warning "
                    f"{pdf_path.name} page {page_number}: {exc}",
                    flush=True,
                )

        # -------------------------------------------------------------
        # 2. EXTRACT TEXT BLOCKS WITH pymupdf4llm
        # -------------------------------------------------------------
        try:
            chunks = pymupdf4llm.to_markdown(doc, use_layout=True, page_chunks=True)
            for chunk in chunks:
                page_num = chunk.get("metadata", {}).get("page", 0) + 1
                text = chunk.get("text", "")

                # Split markdown into paragraph-like blocks.
                blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
                for i, block in enumerate(blocks):
                    # Drop table markdown; those tables live in parsed.tables.
                    block = strip_markdown_tables(block)
                    if not block:
                        continue

                    # Strip markdown formatting for the chunkers (headers, bold, italic).
                    clean_block = re.sub(r"^#+\s*", "", block, flags=re.MULTILINE)
                    clean_block = clean_block.replace("**", "").replace("__", "")

                    text_items.append(
                        {
                            "page": page_num,
                            "top": i,  # preserve relative order
                            "text": clean_block,
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            print(
                f"[parse] text extraction warning {pdf_path.name}: {exc}",
                flush=True,
            )

        parsed.text_items = text_items

        return parsed

    finally:
        doc.close()
