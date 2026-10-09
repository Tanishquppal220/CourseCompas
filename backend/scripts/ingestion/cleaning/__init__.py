"""Text cleaning: generic whitespace helpers + IP-specific boilerplate filters."""

from .instruction_plan import (
    clean_chunk_text,
    is_boilerplate,
    looks_like_page_furniture,
    strip_footer,
)
from .text import collapse_whitespace, normalize_whitespace

__all__ = [
    "clean_chunk_text",
    "collapse_whitespace",
    "is_boilerplate",
    "looks_like_page_furniture",
    "normalize_whitespace",
    "strip_footer",
]
