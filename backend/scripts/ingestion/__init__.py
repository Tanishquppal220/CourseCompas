"""CourseCompass document ingestion pipeline.

Read a run from top to bottom:

    cli.py            -> parse command-line flags
    pipeline.py       -> ORCHESTRATION: parse -> chunk -> embed -> store
    database.py       -> tables + HNSW vector indexes
    parsing/          -> PDF -> ParsedPdf (PyMuPDF or Docling backend)
    cleaning/         -> whitespace + IP boilerplate/footer removal
    chunking/         -> ParsedPdf -> Chunk (one module per document type)

Entrypoint: ``uv run python scripts/ingest.py``.
"""

from .chunking import Chunk, chunk_benefits, chunk_ip, chunk_syllabus
from .parsing import ParsedPdf, batch_parse, parse_pdf
from .pipeline import run_ingestion

__all__ = [
    "Chunk",
    "ParsedPdf",
    "batch_parse",
    "chunk_benefits",
    "chunk_ip",
    "chunk_syllabus",
    "parse_pdf",
    "run_ingestion",
]
