import re
from pathlib import Path

# def clean_cell(cell: str) -> str:
#     if not cell:
#         return " "
#     text_val = (
#         cell.replace("\\*", "")
#         .replace("\\-", "")
#         .replace("\\_", "")
#         .replace("\\.", "")
#         .replace("**", "")
#         .replace("*", "")
#         .replace("_", "")
#         .strip()
#     )
#     return text_val


# def main():
#     file_path = Path(__file__).resolve().parent.parent / "data" / "benifits.md"
#     with open(file_path, "r", encoding="utf-8") as f:
#         content = f.readlines()
#         # print(content[0:1])
#         new_list = [
#             (" |".join([clean_cell(cell) for cell in line.split("|")])) + "\n"
#             for line in content
#         ]
#         for line in new_list:
#             print(line, end="")


def clean_text(text: str) -> str:
    """Clean text without changing Markdown structure."""

    # Replace non-breaking spaces
    text = text.replace("\xa0", " ")

    # Remove unnecessary escaping but preserve Markdown syntax
    text = re.sub(r"\\([*_\-.])", r"\1", text)

    # Normalize multiple spaces
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def is_table_separator(line: str) -> bool:
    """
    Detect lines like:
    | --- | --- | --- |
    | :--- | ---: | :---: |
    """

    stripped = line.strip()

    if not stripped.startswith("|"):
        return False

    cells = stripped.strip("|").split("|")

    if not cells:
        return False

    return all(re.fullmatch(r"\s*:?-{3,}:?\s*", cell) is not None for cell in cells)


def clean_table_row(line: str) -> str:
    """
    Clean table cell content while preserving the exact
    number of columns and Markdown table structure.
    """

    # Preserve leading/trailing pipe structure
    stripped = line.strip()

    cells = stripped.split("|")

    cleaned_cells = []

    for cell in cells:
        cleaned_cells.append(clean_text(cell))

    # IMPORTANT:
    # Join with "|" without removing empty cells.
    return "|".join(cleaned_cells)


def clean_markdown(content: str) -> str:
    cleaned_lines = []

    for line in content.splitlines():
        # Preserve blank lines
        if not line.strip():
            cleaned_lines.append("")
            continue

        # Preserve Markdown table separator exactly
        if is_table_separator(line):
            cleaned_lines.append(line.strip())
            continue

        # Markdown table row
        if line.strip().startswith("|"):
            cleaned_lines.append(clean_table_row(line))
            continue

        # Normal text / headings
        cleaned_lines.append(clean_text(line))

    return "\n".join(cleaned_lines) + "\n"


def main():
    base_path = Path(__file__).resolve().parent.parent

    input_path = base_path / "data" / "benefits.md"

    output_path = base_path / "data" / "benefits_clean.md"

    content = input_path.read_text(encoding="utf-8")

    cleaned_content = clean_markdown(content)

    output_path.write_text(cleaned_content, encoding="utf-8")

    print(f"Cleaned Markdown saved to: {output_path}")


if __name__ == "__main__":
    main()