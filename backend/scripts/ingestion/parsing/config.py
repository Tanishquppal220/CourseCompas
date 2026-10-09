"""Parse configuration: where the on-disk parse cache lives.

The cache directory can be overridden with ``PDF_PARSE_CACHE_DIR``. PDFs are
always parsed with the PyMuPDF backend, so only one cache layout exists.
"""

import os
from pathlib import Path

from ..paths import BACKEND_DIR

CACHE_DIR = Path(
    os.getenv(
        "PDF_PARSE_CACHE_DIR",
        BACKEND_DIR / ".cache" / "pymupdf",
    )
)