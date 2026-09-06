import sys
from pathlib import Path

import pymupdf4llm


def main(pdf_path: str):
    pdf_path = Path(pdf_path)

    print(f"Processing: {pdf_path.name}")
    print("=" * 80)

    markdown = pymupdf4llm.to_markdown(
        str(pdf_path),
        use_layout=True,
    )

    print(markdown[:15000])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run test_layout.py <file.pdf>")
        sys.exit(1)

    main(sys.argv[1])
