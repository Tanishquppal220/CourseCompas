"""Instruction Plan (IP) cleaning: footer stripping and boilerplate removal.

IP PDFs repeat a disclaimer and a session/page footer on every page; these
helpers remove that noise before chunking.
"""

import re

from .text import collapse_whitespace, normalize_whitespace

# Repeated disclaimer that appears at the bottom of every IP page.
IP_BOILERPLATE_PHRASES = (
    "an instruction plan is only a tentative plan",
    "the teacher may make some changes in his/her teaching plan",
    "updated on the contemporary issues related to the course",
    "the students are advised to use syllabus for preparation of all examinations",
)

# Footer / page furniture patterns.
FOOTER_PATTERNS = (
    re.compile(r"\bSession\s+\d{4}\s*-\s*\d{2}\b", re.IGNORECASE),
    re.compile(r"\bPage\s*:\s*\d+\s*/\s*\d+\b"),
    re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
)


def strip_footer(text: str) -> str:
    """Remove session/page-number footer lines."""
    out = []
    for line in text.splitlines():
        if any(p.search(line) for p in FOOTER_PATTERNS):
            continue
        out.append(line)
    return "\n".join(out)


def lower_matches_phrase(lowered: str, phrases) -> bool:
    """True if any phrase occurs in the already-lowercased text."""
    return any(phrase in lowered for phrase in phrases)


def looks_like_page_furniture(text: str) -> bool:
    """True for footers, bare page numbers, and other page furniture."""
    stripped = normalize_whitespace(text)
    if any(p.search(text) for p in FOOTER_PATTERNS):
        return True
    if len(stripped) < 4:
        return True
    if stripped.isdigit():
        return True
    return bool(re.fullmatch(r"\d+", stripped))


def is_boilerplate(text: str) -> bool:
    """True if text is repeated boilerplate / junk, not useful for retrieval."""
    lowered = normalize_whitespace(text).lower()
    if not lowered:
        return True
    if lower_matches_phrase(lowered, IP_BOILERPLATE_PHRASES):
        return True
    return looks_like_page_furniture(text)


def clean_chunk_text(text: str) -> str:
    """Normalize + strip footers for a chunk's content."""
    text = strip_footer(text)

    # Remove the large instruction-plan boilerplate so entire blocks are not dropped.
    text = re.sub(
        r"An instruction plan is only a tentative plan.*?mentioned in the instruction plan\.?",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    return collapse_whitespace(text).strip()
