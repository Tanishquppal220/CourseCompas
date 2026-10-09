"""Parser backend selection and cache location.

The backend is chosen with the ``PARSER_BACKEND`` environment variable:

    PARSER_BACKEND=pymupdf   # default, fast
    PARSER_BACKEND=docling   # original implementation

Both backends return the same :class:`~ingestion.parsing.models.ParsedPdf`
structure, so the rest of the pipeline does not need to change.
"""

import os
from pathlib import Path

from ..paths import BACKEND_DIR

PARSER_BACKEND = os.getenv("PARSER_BACKEND", "pymupdf").lower()

if PARSER_BACKEND not in {"pymupdf", "docling"}:
    raise ValueError(
        f"Unknown PARSER_BACKEND={PARSER_BACKEND!r}. Use 'pymupdf' or 'docling'."
    )

# Separate cache directories matter: a PyMuPDF cache must never be confused
# with a Docling cache.
CACHE_DIR = Path(
    os.getenv(
        "PDF_PARSE_CACHE_DIR",
        BACKEND_DIR / ".cache" / PARSER_BACKEND,
    )
)
