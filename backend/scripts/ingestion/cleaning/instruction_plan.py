"""Instruction Plan (IP) boilerplate: the disclaimer repeated on every IP page.

The generic per-item pipeline (page furniture + whitespace) lives in
``cleaning.text``; this module layers the IP-specific disclaimer phrases on
top and re-exports the composed per-item cleaners the chunkers call through
``chunking.chunk.collect_cleaned_text_items``.
"""

import re

from .text import (
    collapse_whitespace,
    is_page_furniture,
    normalize_whitespace,
    strip_page_furniture,
)

# Repeated disclaimer that appears at the bottom of every IP page.
IP_BOILERPLATE_PHRASES = (
    "an instruction plan is only a tentative plan",
    "the teacher may make some changes in his/her teaching plan",
    "updated on the contemporary issues related to the course",
    "the students are advised to use syllabus for preparation of all examinations",
)

# The large multi-line disclaimer block, removed so entire chunks are not dropped.
IP_DISCLAIMER_RE = re.compile(
    r"An instruction plan is only a tentative plan.*?mentioned in the instruction plan\.?",
    re.IGNORECASE | re.DOTALL,
)


def lower_matches_phrase(lowered: str, phrases) -> bool:
    """True if any phrase occurs in the already-lowercased text."""
    return any(phrase in lowered for phrase in phrases)


def has_ip_boilerplate(text: str) -> bool:
    """True if an instruction-plan boilerplate phrase occurs in ``text``."""
    lowered = normalize_whitespace(text).lower()
    return bool(lowered) and lower_matches_phrase(lowered, IP_BOILERPLATE_PHRASES)


def strip_ip_boilerplate(text: str) -> str:
    """Remove the large instruction-plan disclaimer block."""
    return IP_DISCLAIMER_RE.sub("", text)


# Composed per-item cleaners (page furniture + IP boilerplate + whitespace).
# ``collect_cleaned_text_items`` calls these with both steps on by default.
def clean_chunk_text(text: str) -> str:
    """Normalize + strip page furniture and IP boilerplate for a chunk's content."""
    text = strip_page_furniture(text)
    text = strip_ip_boilerplate(text)
    return collapse_whitespace(text).strip()


def is_boilerplate(text: str) -> bool:
    """True if text is repeated boilerplate / junk, not useful for retrieval."""
    lowered = normalize_whitespace(text).lower()
    if not lowered:
        return True
    if lower_matches_phrase(lowered, IP_BOILERPLATE_PHRASES):
        return True
    return is_page_furniture(text)