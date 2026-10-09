"""Public PDF parsing entrypoints.

``batch_parse`` is the one the pipeline calls; it checks the on-disk cache and
then parses uncached PDFs with the PyMuPDF backend.
"""

import time
from collections.abc import Iterable
from pathlib import Path

from .cache import load_cached, save_parsed_cache
from .models import ParsedPdf
from .pymupdf_parser import parse_pdf_with_pymupdf


def parse_pdf(pdf_path: Path, use_cache: bool = True) -> ParsedPdf:
    """Parse a single PDF."""
    results = batch_parse([pdf_path], use_cache=use_cache, verbose=False)

    if not results:
        raise RuntimeError(f"Failed to parse PDF: {pdf_path}")

    return results[0][1]


def batch_parse(
    pdf_paths: Iterable[Path],
    use_cache: bool = True,
    verbose: bool = True,
) -> list[tuple[Path, ParsedPdf]]:
    """Parse many PDFs, returning ``(resolved_path, parsed)`` pairs.

    Cached parses are returned first; only uncached PDFs hit the backend.
    """
    pdf_paths = [Path(path).resolve() for path in pdf_paths]

    results = []
    pending = []

    # -----------------------------------------------------------------
    # CACHE CHECK
    # -----------------------------------------------------------------
    for pdf_path in pdf_paths:
        cached = load_cached(pdf_path) if use_cache else None

        if cached is not None:
            results.append((pdf_path, cached))
        else:
            pending.append(pdf_path)

    if not pending:
        return results

    # -----------------------------------------------------------------
    # PARSE (PyMuPDF)
    # -----------------------------------------------------------------
    started = time.time()

    for index, pdf_path in enumerate(pending, start=1):
        try:
            parsed = parse_pdf_with_pymupdf(pdf_path)

            save_parsed_cache(pdf_path, parsed)

            results.append((pdf_path, parsed))

            if verbose:
                elapsed = time.time() - started

                print(
                    f"[parse:pymupdf] {pdf_path.name} "
                    f"({index}/{len(pending)}) "
                    f"t+{elapsed:.1f}s",
                    flush=True,
                )

        except Exception as exc:  # noqa: BLE001
            print(
                f"[parse:pymupdf] FAILED {pdf_path.name}: {exc}",
                flush=True,
            )

    return results