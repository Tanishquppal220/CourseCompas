"""
PDF parser abstraction for CourseCompass.

Supported backends:

    PARSER_BACKEND=pymupdf   # default, fast
    PARSER_BACKEND=docling   # original implementation

Both backends return the same ParsedPdf structure, so the rest of the
ingestion pipeline does not need to change.

Switch backend with:

    PARSER_BACKEND=pymupdf uv run python scripts/ingest.py

or:

    PARSER_BACKEND=docling uv run python scripts/ingest.py
"""

import hashlib
import logging
import os
import pickle
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

logging.disable(logging.WARNING)


# =============================================================================
# CONFIGURATION
# =============================================================================

PARSER_BACKEND = os.getenv("PARSER_BACKEND", "pymupdf").lower()

if PARSER_BACKEND not in {"pymupdf", "docling"}:
    raise ValueError(
        f"Unknown PARSER_BACKEND={PARSER_BACKEND!r}. Use 'pymupdf' or 'docling'."
    )


BACKEND_DIR = Path(__file__).resolve().parent.parent

# Separate cache directories are important.
# A PyMuPDF cache must never be confused with a Docling cache.
CACHE_DIR = Path(
    os.getenv(
        "PDF_PARSE_CACHE_DIR",
        BACKEND_DIR / ".cache" / PARSER_BACKEND,
    )
)


# =============================================================================
# COMMON DATA STRUCTURES
# =============================================================================


@dataclass
class ParsedTable:
    page: int
    rows: list
    n_rows: int
    n_cols: int


@dataclass
class ParsedPdf:
    source: str
    text_items: list = field(default_factory=list)
    tables: list = field(default_factory=list)


# =============================================================================
# COMMON HELPERS
# =============================================================================


def _cell_str(value) -> str:
    """Convert a table cell into a clean string."""
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in ("nan", "none", "nat"):
        return ""

    return text


def _cache_file(pdf_path: Path) -> Path:
    """
    Generate a cache file based on:

    - file path
    - modification time
    - file size
    - parser backend
    """

    cache_key = (
        f"{PARSER_BACKEND}|"
        f"{pdf_path}|"
        f"{pdf_path.stat().st_mtime_ns}|"
        f"{pdf_path.stat().st_size}"
    )

    digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]

    return CACHE_DIR / f"{pdf_path.stem}_{digest}.pkl"


def load_cached(pdf_path: Path) -> Optional[ParsedPdf]:
    """Return cached parsed PDF if available."""

    pdf_path = pdf_path.resolve()
    cache_file = _cache_file(pdf_path)

    if not cache_file.exists():
        return None

    try:
        with open(cache_file, "rb") as fh:
            return pickle.load(fh)

    except Exception:
        # Corrupt/incompatible cache → ignore it and re-parse.
        return None


def _save_cache(pdf_path: Path, parsed: ParsedPdf) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_file = _cache_file(pdf_path)

    with open(cache_file, "wb") as fh:
        pickle.dump(
            parsed,
            fh,
            protocol=pickle.HIGHEST_PROTOCOL,
        )


# =============================================================================
# PYMuPDF BACKEND
# =============================================================================


def _rect_overlap_ratio(rect1, rect2) -> float:
    """
    Return overlap ratio relative to rect1.

    Used to determine whether a text block belongs to a detected table.
    """

    intersection = rect1 & rect2

    if intersection.is_empty:
        return 0.0

    area1 = rect1.get_area()

    if area1 <= 0:
        return 0.0

    return intersection.get_area() / area1


def _parse_with_pymupdf(pdf_path: Path) -> ParsedPdf:
    """
    Parse a PDF using PyMuPDF and pymupdf4llm.
    """

    import pymupdf
    import pymupdf4llm

    parsed = ParsedPdf(source=str(pdf_path))

    doc = pymupdf.open(pdf_path)

    try:
        text_items = []

        for page_number, page in enumerate(doc, start=1):
            # -------------------------------------------------------------
            # 1. DETECT TABLES
            # -------------------------------------------------------------

            try:
                table_finder = page.find_tables()

                for table in table_finder.tables:
                    rows = []

                    for row in table.extract():
                        clean_row = [_cell_str(cell) for cell in row]

                        # Remove trailing empty columns.
                        while clean_row and clean_row[-1] == "":
                            clean_row.pop()

                        # Ignore completely empty rows.
                        if any(clean_row):
                            rows.append(clean_row)

                    if not rows:
                        continue

                    parsed.tables.append(
                        ParsedTable(
                            page=page_number,
                            rows=rows,
                            n_rows=len(rows),
                            n_cols=max(len(row) for row in rows),
                        )
                    )

            except Exception as exc:
                print(
                    f"[parse] table extraction warning "
                    f"{pdf_path.name} page {page_number}: {exc}",
                    flush=True,
                )

        # -------------------------------------------------------------
        # 2. EXTRACT TEXT BLOCKS WITH pymupdf4llm
        # -------------------------------------------------------------
        try:
            chunks = pymupdf4llm.to_markdown(doc, use_layout=True, page_chunks=True)
            for chunk in chunks:
                page_num = chunk.get("metadata", {}).get("page", 0) + 1
                text = chunk.get("text", "")
                
                # Split markdown into paragraph-like blocks
                blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
                for i, block in enumerate(blocks):
                    import re
                    # Remove markdown formatting for chunkers (headers, bold, italic)
                    clean_block = re.sub(r'^#+\s*', '', block, flags=re.MULTILINE)
                    clean_block = clean_block.replace('**', '').replace('__', '')
                    
                    text_items.append({
                        "page": page_num,
                        "top": i,  # preserve relative order
                        "text": clean_block,
                    })
        except Exception as exc:
            print(
                f"[parse] text extraction warning "
                f"{pdf_path.name}: {exc}",
                flush=True,
            )

        parsed.text_items = text_items

        return parsed

    finally:
        doc.close()


# =============================================================================
# DOCLING BACKEND
#
# This is your original implementation, kept here so you can switch back
# without changing any other project files.
# =============================================================================


@lru_cache(maxsize=1)
def _get_docling_converter():

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        ThreadedPdfPipelineOptions,
    )
    from docling.document_converter import (
        DocumentConverter,
        PdfFormatOption,
    )

    opts = ThreadedPdfPipelineOptions()

    opts.do_ocr = False
    opts.do_table_structure = True

    opts.layout_batch_size = 2
    opts.table_batch_size = 2

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )

    return converter


def _docling_table_to_rows(table_item, doc) -> list:

    df = table_item.export_to_dataframe(doc=doc)

    rows = []

    for record in df.to_dict(orient="records"):
        row = [_cell_str(value) for value in record.values()]

        while row and row[-1] == "":
            row.pop()

        if any(row):
            rows.append(row)

    return rows


def _parse_docling_document(
    pdf_path: Path,
    doc,
) -> ParsedPdf:

    from docling_core.types.doc.document import TableItem

    parsed = ParsedPdf(source=str(pdf_path))

    text_items = []

    for item, _level in doc.iterate_items():
        # -------------------------------------------------------------
        # TABLE
        # -------------------------------------------------------------

        if isinstance(item, TableItem):
            page = item.prov[0].page_no if item.prov else 0

            rows = _docling_table_to_rows(
                item,
                doc,
            )

            if not rows:
                continue

            parsed.tables.append(
                ParsedTable(
                    page=page,
                    rows=rows,
                    n_rows=len(rows),
                    n_cols=max(len(row) for row in rows),
                )
            )

            continue

        # -------------------------------------------------------------
        # NORMAL TEXT
        # -------------------------------------------------------------

        text = getattr(item, "text", None)

        if not text or not text.strip():
            continue

        page = item.prov[0].page_no if item.prov else 0

        top = item.prov[0].bbox.t if item.prov else 0.0

        text_items.append(
            {
                "page": page,
                "top": top,
                "text": text.strip(),
            }
        )

    # Preserve your original Docling ordering behavior.
    text_items.sort(
        key=lambda item: (
            item["page"],
            -item["top"],
        )
    )

    parsed.text_items = text_items

    return parsed


def _parse_many_with_docling(
    pdf_paths: list[Path],
    verbose: bool,
) -> list[tuple[Path, ParsedPdf]]:

    converter = _get_docling_converter()

    results = []

    started = time.time()
    processed = 0

    for result in converter.convert_all(
        pdf_paths,
        raises_on_error=False,
    ):
        processed += 1

        src = result.input.file

        src_path = (
            Path(src) if isinstance(src, (str, Path)) else Path(str(src))
        ).resolve()

        if result.status.value != "success" or result.document is None:
            print(
                f"[parse] FAILED {src_path.name}",
                flush=True,
            )
            continue

        parsed = _parse_docling_document(
            src_path,
            result.document,
        )

        _save_cache(
            src_path,
            parsed,
        )

        results.append(
            (
                src_path,
                parsed,
            )
        )

        if verbose:
            elapsed = time.time() - started

            print(
                f"[parse] {src_path.name} "
                f"({processed}/{len(pdf_paths)}) "
                f"t+{elapsed:.0f}s",
                flush=True,
            )

    return results


# =============================================================================
# PUBLIC API
#
# Everything below has the same interface as your original parse_pdf.py
# =============================================================================


def parse_pdf(
    pdf_path: Path,
    use_cache: bool = True,
) -> ParsedPdf:
    """
    Parse one PDF.

    Public API intentionally unchanged.
    """

    results = batch_parse(
        [pdf_path],
        use_cache=use_cache,
        verbose=False,
    )

    if not results:
        raise RuntimeError(f"Failed to parse PDF: {pdf_path}")

    return results[0][1]


def batch_parse(
    pdf_paths: Iterable[Path],
    use_cache: bool = True,
    verbose: bool = True,
) -> list[tuple[Path, ParsedPdf]]:
    """
    Parse multiple PDFs.

    Public API intentionally unchanged so ingest.py does not need changes.
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
            results.append(
                (
                    pdf_path,
                    cached,
                )
            )
        else:
            pending.append(pdf_path)

    if not pending:
        return results

    # -----------------------------------------------------------------
    # PYMuPDF
    # -----------------------------------------------------------------

    if PARSER_BACKEND == "pymupdf":
        started = time.time()

        for index, pdf_path in enumerate(
            pending,
            start=1,
        ):
            try:
                parsed = _parse_with_pymupdf(pdf_path)

                _save_cache(
                    pdf_path,
                    parsed,
                )

                results.append(
                    (
                        pdf_path,
                        parsed,
                    )
                )

                if verbose:
                    elapsed = time.time() - started

                    print(
                        f"[parse:pymupdf] {pdf_path.name} "
                        f"({index}/{len(pending)}) "
                        f"t+{elapsed:.1f}s",
                        flush=True,
                    )

            except Exception as exc:
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
            print(
                f"[parse] using Docling for {len(pending)} PDFs",
                flush=True,
            )

        results.extend(
            _parse_many_with_docling(
                pending,
                verbose=verbose,
            )
        )

        return results

    # Should never happen because we validate PARSER_BACKEND above.
    raise RuntimeError(f"Unsupported parser backend: {PARSER_BACKEND}")
