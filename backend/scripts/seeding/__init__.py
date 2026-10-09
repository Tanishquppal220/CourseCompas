"""Relational curriculum seeding (terms, courses, baskets, slots).

    curriculum_data.py    -> the raw data (no DB access)
    loaders.py            -> idempotent get-or-create helpers
    load_curriculum.py    -> load_all() + run() entrypoint

Entrypoint: ``uv run python scripts/seed.py``.
"""

from .load_curriculum import load_all, run
from .loaders import (
    get_or_create_area,
    get_or_create_basket,
    get_or_create_course,
    get_or_create_lookup,
    get_or_create_slot,
    get_or_create_term,
)

__all__ = [
    "get_or_create_area",
    "get_or_create_basket",
    "get_or_create_course",
    "get_or_create_lookup",
    "get_or_create_slot",
    "get_or_create_term",
    "load_all",
    "run",
]
