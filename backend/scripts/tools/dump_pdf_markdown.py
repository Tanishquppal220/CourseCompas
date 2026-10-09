"""Dump the raw markdown that pymupdf4llm extracts from a PDF.

Scratch/inspection utility (not part of the ingestion pipeline):

    uv run python scripts/tools/dump_pdf_markdown.py <file.pdf>
"""

import sys
from pathlib import Path

import pymupdf4llm


def dump_pdf_markdown(pdf_path: Path) -> None:
    """Print the first 15000 characters of the PDF's markdown extraction."""
    print(f"Processing: {pdf_path.name}")
    print("=" * 80)

    markdown = pymupdf4llm.to_markdown(str(pdf_path), use_layout=True)

    print(markdown[:15000])


def main(argv: list[str]) -> int:
    """CLI entrypoint."""
    if len(argv) != 2:
        print("Usage: uv run python scripts/tools/dump_pdf_markdown.py <file.pdf>")
        return 1

    dump_pdf_markdown(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
