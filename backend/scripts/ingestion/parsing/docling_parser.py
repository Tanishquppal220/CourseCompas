"""Docling parser backend (the original implementation, kept switchable).

Enable it with ``PARSER_BACKEND=docling``.
"""

import time
from functools import lru_cache
from pathlib import Path

from .cache import save_parsed_cache
from .models import ParsedPdf, ParsedTable, cell_to_text


@lru_cache(maxsize=1)
def get_docling_converter():
    """Build (once) the shared Docling document converter."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = ThreadedPdfPipelineOptions()

    opts.do_ocr = False
    opts.do_table_structure = True

    opts.layout_batch_size = 2
    opts.table_batch_size = 2

    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )


def docling_table_to_rows(table_item, doc) -> list:
    """Convert a Docling table item into rows of clean cell strings."""
    df = table_item.export_to_dataframe(doc=doc)

    rows = []

    for record in df.to_dict(orient="records"):
        row = [cell_to_text(value) for value in record.values()]

        while row and row[-1] == "":
            row.pop()

        if any(row):
            rows.append(row)

    return rows


def parse_docling_document(pdf_path: Path, doc) -> ParsedPdf:
    """Convert one Docling document object into a :class:`ParsedPdf`."""
    from docling_core.types.doc.document import TableItem

    parsed = ParsedPdf(source=str(pdf_path))

    text_items = []

    for item, _level in doc.iterate_items():
        # -------------------------------------------------------------
        # TABLE
        # -------------------------------------------------------------
        if isinstance(item, TableItem):
            page = item.prov[0].page_no if item.prov else 0

            rows = docling_table_to_rows(item, doc)

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

    # Preserve the original Docling ordering behavior.
    text_items.sort(key=lambda item: (item["page"], -item["top"]))

    parsed.text_items = text_items

    return parsed


def parse_pdfs_with_docling(
    pdf_paths: list[Path],
    verbose: bool,
) -> list[tuple[Path, ParsedPdf]]:
    """Parse a batch of PDFs with Docling, caching each successful result."""
    converter = get_docling_converter()

    results = []

    started = time.time()
    processed = 0

    for result in converter.convert_all(pdf_paths, raises_on_error=False):
        processed += 1

        src = result.input.file

        src_path = (
            Path(src) if isinstance(src, (str, Path)) else Path(str(src))
        ).resolve()

        if result.status.value != "success" or result.document is None:
            print(f"[parse] FAILED {src_path.name}", flush=True)
            continue

        parsed = parse_docling_document(src_path, result.document)

        save_parsed_cache(src_path, parsed)

        results.append((src_path, parsed))

        if verbose:
            elapsed = time.time() - started

            print(
                f"[parse] {src_path.name} "
                f"({processed}/{len(pdf_paths)}) "
                f"t+{elapsed:.0f}s",
                flush=True,
            )

    return results
