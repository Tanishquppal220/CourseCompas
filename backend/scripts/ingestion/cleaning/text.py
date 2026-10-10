"""Generic text normalization shared by all document types.

Whitespace handling and page-furniture (footer) detection/removal live here.
Anything specific to a single source document (e.g. the instruction-plan
disclaimer) lives in ``cleaning.instruction_plan`` and is applied opt-in by
the chunkers.
"""

import re

# Page furniture repeated on every page of the source PDFs.
FOOTER_PATTERNS = (
    re.compile(r"\bSession\s+\d{4}\s*-\s*\d{2}\b", re.IGNORECASE),
    re.compile(r"\bPage\s*:\s*\d+\s*/\s*\d+\b"),
    re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
)


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace inside lines and drop empty inter-line space."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def normalize_whitespace(text: str) -> str:
    """Collapse ALL whitespace (including newlines) into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_text(text: str, *, preserve_newlines: bool = True) -> str:
    """Unified whitespace normalization.

    ``preserve_newlines=True`` keeps line structure (see
    :func:`collapse_whitespace`); ``False`` flattens the text into a single
    line (see :func:`normalize_whitespace`).
    """
    return collapse_whitespace(text) if preserve_newlines else normalize_whitespace(text)


def strip_page_furniture(text: str) -> str:
    """Remove session/page-number footer lines."""
    out = []
    for line in text.splitlines():
        if any(p.search(line) for p in FOOTER_PATTERNS):
            continue
        out.append(line)
    return "\n".join(out)


def is_page_furniture(text: str) -> bool:
    """True for footers, bare page numbers, and other page furniture."""
    stripped = normalize_whitespace(text)
    if any(p.search(text) for p in FOOTER_PATTERNS):
        return True
    if len(stripped) < 4:
        return True
    if stripped.isdigit():
        return True
    return bool(re.fullmatch(r"\d+", stripped))