"""Document-aware chunkers, one module per source type.

    syllabus.py          -> Syllabus PDFs
    instruction_plan.py  -> Instruction Plan (IP) PDFs
    benefits.py          -> benefits_clean.md

Shared structures and helpers live in ``chunk.py``.
"""

from .benefits import chunk_benefits
from .chunk import Chunk, assign_chunk_indices, truncate_text
from .instruction_plan import chunk_ip
from .syllabus import chunk_syllabus

__all__ = [
    "Chunk",
    "assign_chunk_indices",
    "chunk_benefits",
    "chunk_ip",
    "chunk_syllabus",
    "truncate_text",
]
