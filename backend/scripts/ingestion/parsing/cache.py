"""On-disk cache for parsed PDFs.

The cache key includes the file path, modification time, size, and
``CACHE_VERSION``, so bumping the version ignores caches written by an older
parse schema.
"""

import hashlib
import logging
import pickle
import sys
from pathlib import Path

from . import models
from .config import CACHE_DIR
from .models import ParsedPdf

logger = logging.getLogger(__name__)

# Bump when the shape or content of ParsedPdf changes, so stale caches are
# ignored instead of feeding the chunkers outdated data.
CACHE_VERSION = 3

# Failures that mean "this cache file is unusable" (corrupt, moved module, or
# unreadable). Anything else (e.g. a bug in a dataclass) should surface instead
# of being silently swallowed.
_CACHE_LOAD_ERRORS = (
    pickle.UnpicklingError,
    EOFError,
    AttributeError,
    ImportError,
    ModuleNotFoundError,
    OSError,
)


def cache_path_for(pdf_path: Path) -> Path:
    """Return the cache file that belongs to ``pdf_path``."""
    cache_key = (
        f"v{CACHE_VERSION}|"
        f"{pdf_path}|"
        f"{pdf_path.stat().st_mtime_ns}|"
        f"{pdf_path.stat().st_size}"
    )

    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]

    return CACHE_DIR / f"{pdf_path.stem}_{digest}.pkl"


def load_cached(pdf_path: Path) -> ParsedPdf | None:
    """Return the cached parse of ``pdf_path``, or ``None`` if unusable/missing."""
    pdf_path = pdf_path.resolve()
    cache_file = cache_path_for(pdf_path)

    if not cache_file.exists():
        return None

    # Backward compatibility: caches written before the parser was split into
    # this package pickle `parse_pdf.ParsedPdf`. Alias that old module name to
    # the new models module so existing caches keep loading instead of forcing
    # an expensive full re-parse.
    sys.modules.setdefault("parse_pdf", models)

    try:
        with open(cache_file, "rb") as fh:
            parsed = pickle.load(fh)
    except _CACHE_LOAD_ERRORS as exc:
        logger.warning(
            "Ignoring unreadable parse cache %s (%s); re-parsing.",
            cache_file.name,
            exc,
        )
        return None

    if not isinstance(parsed, ParsedPdf):
        logger.warning(
            "Ignoring parse cache %s with unexpected type %s; re-parsing.",
            cache_file.name,
            type(parsed).__name__,
        )
        return None

    return parsed


def save_parsed_cache(pdf_path: Path, parsed: ParsedPdf) -> None:
    """Write ``parsed`` to the on-disk cache for ``pdf_path``."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_file = cache_path_for(pdf_path)

    with open(cache_file, "wb") as fh:
        pickle.dump(parsed, fh, protocol=pickle.HIGHEST_PROTOCOL)