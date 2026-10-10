"""Text cleaning: generic whitespace/page-furniture helpers + IP boilerplate."""

from .instruction_plan import (
    clean_chunk_text,
    has_ip_boilerplate,
    is_boilerplate,
    strip_ip_boilerplate,
)
from .text import (
    collapse_whitespace,
    is_page_furniture,
    normalize_text,
    normalize_whitespace,
    strip_page_furniture,
)

__all__ = [
    "clean_chunk_text",
    "collapse_whitespace",
    "has_ip_boilerplate",
    "is_boilerplate",
    "is_page_furniture",
    "normalize_text",
    "normalize_whitespace",
    "strip_ip_boilerplate",
    "strip_page_furniture",
]