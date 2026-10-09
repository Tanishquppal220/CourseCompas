"""Public PDF parsing entrypoints.

``batch_parse`` is the one the pipeline calls; it checks the on-disk cache and
then dispatches to the PyMuPDF or Docling backend based on ``PARSER_BACKEND``.
"""

import time
from collections.abc import Iterable
from pathlib import Path

from .cache import load_cached, save_parsed_cache
from .config import PARSER_BACKEND
from .docling_parser import parse_pdfs_with_docling
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
    # PYMuPDF
    # -----------------------------------------------------------------
    if PARSER_BACKEND == "pymupdf":
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

    # -----------------------------------------------------------------
    # DOCLING
    # -----------------------------------------------------------------
    if PARSER_BACKEND == "docling":
        if verbose:
            print(f"[parse] using Docling for {len(pending)} PDFs", flush=True)

        results.extend(parse_pdfs_with_docling(pending, verbose=verbose))

        return results

    # Should never happen because config validates PARSER_BACKEND at import.
    raise RuntimeError(f"Unsupported parser backend: {PARSER_BACKEND}")
