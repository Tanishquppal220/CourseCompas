"""Generic whitespace normalization shared by all document types."""

import re


def collapse_whitespace(text: str) -> str:
    """Collapse runs of whitespace inside lines and drop empty inter-line space."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def normalize_whitespace(text: str) -> str:
    """Collapse ALL whitespace (including newlines) into single spaces."""
    return re.sub(r"\s+", " ", text).strip()
