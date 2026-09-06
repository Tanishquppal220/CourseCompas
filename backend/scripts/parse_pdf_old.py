"""Docling-based PDF parser with on-disk cache.

Parses a PDF into:
  * `text_items` — non-table text items in per-page reading order
    (sorted by page number, then vertical position top-to-bottom).
  * `tables`     — detected tables as 2D grids of cell strings.

Performance is tuned for CPU-only machines (no GPU assumed):

  * A single `DocumentConverter` is reused for every PDF so pipeline/ONNX
    setup happens once per process, not once per file.
  * The serial `PdfPipelineOptions` is used: measurements on this machine
    show Docling's threaded pipeline and document-level concurrency offer no
    wall-clock gain (per-page model inference is the bottleneck) while using
    substantially more memory. For multi-file speed use process-level
    parallelism (`ingest.py --workers`).
  * `batch_parse()` feeds all uncached PDFs through one `convert_all` pass.

The heavy Docling conversion is cached to `.cache/docling/<hash>.pkl` so
iterating on chunker logic does not re-run the slow layout/table models.
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

from docling_core.types.doc.document import TableItem  # noqa: E402

DOCLING_CACHE_DIR = Path(
    os.getenv("DOCLING_CACHE_DIR", Path(__file__).resolve().parent.parent / ".cache" / "docling")
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(_BACKEND_DIR))


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


def _cell_str(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in ("nan", "none", "nat"):
        return ""
    return text


@lru_cache(maxsize=1)
def _get_converter():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = False
    opts.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    return converter


def _cache_file(pdf_path: Path) -> Path:
    cache_key = f"{pdf_path}-{pdf_path.stat().st_mtime_ns}-{pdf_path.stat().st_size}"
    cache_digest = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:24]
    return DOCLING_CACHE_DIR / f"{pdf_path.stem}_{cache_digest}.pkl"


def _table_to_rows(table_item, doc) -> list:
    df = table_item.export_to_dataframe(doc=doc)
    rows = []
    for record in df.to_dict(orient="records"):
        row = [_cell_str(v) for v in record.values()]
        while row and row[-1] == "":
            row.pop()
        rows.append(row)
    return rows


def _from_document(pdf_path: Path, doc) -> ParsedPdf:
    parsed = ParsedPdf(source=str(pdf_path))
    text_items = []

    for item, _level in doc.iterate_items():
        if isinstance(item, TableItem):
            page = item.prov[0].page_no if item.prov else 0
            rows = _table_to_rows(item, doc)
            if not rows:
                continue
            parsed.tables.append(
                ParsedTable(
                    page=page,
                    rows=rows,
                    n_rows=len(rows),
                    n_cols=max(len(r) for r in rows),
                )
            )
            continue

        text = getattr(item, "text", None)
        if not text or not text.strip():
            continue
        page = item.prov[0].page_no if item.prov else 0
        top = item.prov[0].bbox.t if item.prov else 0.0
        text_items.append({"page": page, "top": top, "text": text.strip()})

    text_items.sort(key=lambda t: (t["page"], -t["top"]))
    parsed.text_items = text_items
    return parsed


def load_cached(pdf_path: Path) -> Optional[ParsedPdf]:
    """Return the cached parse for a PDF if present, else None."""
    pdf_path = pdf_path.resolve()
    cache_file = _cache_file(pdf_path)
    if cache_file.exists():
        with open(cache_file, "rb") as fh:
            return pickle.load(fh)
    return None


def parse_pdf(pdf_path: Path, use_cache: bool = True) -> ParsedPdf:
    """Parse a single PDF, returning a cached result when available."""
    cached = load_cached(pdf_path) if use_cache else None
    if cached is not None:
        return cached
    return next(batch_parse([pdf_path], use_cache=use_cache))[1]


def batch_parse(
    pdf_paths: Iterable[Path],
    use_cache: bool = True,
    verbose: bool = True,
) -> list:
    """Parse many PDFs in one threaded convert_all pass, writing pkl caches.

    Returns a list of (pdf_path, ParsedPdf) for every successfully parsed
    file. Already-cached files are skipped (they are NOT re-listed).
    """
    DOCLING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    converter = _get_converter()
    results = []
    pending = []
    for p in pdf_paths:
        p = p.resolve()
        cached = load_cached(p) if use_cache else None
        if cached is not None:
            results.append((p, cached))
        else:
            pending.append(p)

    if not pending:
        return results

    started = time.time()
    processed = 0
    for result in converter.convert_all(pending, raises_on_error=False):
        processed += 1
        src = result.input.file
        src_path = Path(src) if isinstance(src, (str, Path)) else Path(str(src))
        if result.status.value != "success" or result.document is None:
            print(f"[parse] FAILED {src_path.name}", flush=True)
            continue
        parsed = _from_document(src_path, result.document)
        cache_file = _cache_file(src_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "wb") as fh:
            pickle.dump(parsed, fh, protocol=pickle.HIGHEST_PROTOCOL)
        results.append((src_path, parsed))
        if verbose:
            elapsed = time.time() - started
            print(
                f"[parse] {src_path.name} ({processed}/{len(pending)}) "
                f"t+{elapsed:.0f}s",
                flush=True,
            )

    return results