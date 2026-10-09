# Ingestion pipeline

This folder turns raw source documents into embedded, retrievable chunks.
Read this file top to bottom to know **what runs when**.

## Run it

```bash
uv run python scripts/ingest.py --courses CSE273 CSE101
uv run python scripts/ingest.py                 # everything, incremental
uv run python scripts/ingest.py --workers 2     # half the first-run time
uv run python scripts/ingest.py --benefits-only
uv run python scripts/ingest.py --force-rebuild # recompute all + ignore DB cache
uv run python scripts/ingest.py --force         # ignore the on-disk parse cache
uv run python scripts/ingest.py --continue-on-error  # keep going after a failure
```

By default the pipeline aborts on the first failed document (with a full
traceback in the logs); `--continue-on-error` restores best-effort batch mode.

Schema changes live outside this folder, in `backend/alembic/` (see
`alembic/versions/`). Run `uv run alembic upgrade head` from `backend/`.

`scripts/ingest.py` is only a thin entrypoint; everything real lives here.

## Stage order (walk the folders in this order)

| # | File / folder | What it does |
|---|---|---|
| 1 | `cli.py` | Parses CLI flags. |
| 2 | `pipeline.py` | Orchestrator. `run_ingestion()` = **parse → chunk → embed → store → index**. Also holds incremental change detection. |
| 3 | `database.py` | Creates tables + pgvector extension, builds HNSW vector indexes. |
| 4 | `parsing/` | PDFs → `ParsedPdf`. |
| 5 | `cleaning/` | Whitespace + IP footer/boilerplate removal. |
| 6 | `chunking/` | `ParsedPdf` → `Chunk` objects, **one module per document type**. |

## Folder guides

### `parsing/`
| File | Role |
|---|---|
| `models.py` | `ParsedPdf`, `ParsedTable`, `cell_to_text`. |
| `config.py` | `PARSER_BACKEND` (`pymupdf` default, or `docling`) + cache dir. |
| `cache.py` | On-disk parse cache (keyed by path, mtime, size, backend, and `CACHE_VERSION`). |
| `pymupdf_parser.py` | PyMuPDF + pymupdf4llm backend. Table markdown is dropped from text items (tables are stored once, in `parsed.tables`). |
| `docling_parser.py` | Docling backend (original implementation). |
| `parser.py` | Public `batch_parse` / `parse_pdf`; dispatches to the backend. |

### `cleaning/`
| File | Role |
|---|---|
| `text.py` | Generic `collapse_whitespace`, `normalize_whitespace`. |
| `instruction_plan.py` | IP footer patterns, boilerplate phrases, `clean_chunk_text`. |

### `chunking/`
| File | Role |
|---|---|
| `chunk.py` | `Chunk` dataclass + shared helpers (`truncate_text`, `collect_cleaned_text_items`, `assign_chunk_indices`). |
| `syllabus.py` | `chunk_syllabus` — Syllabus PDFs. |
| `instruction_plan.py` | `chunk_ip` — Instruction Plan PDFs. |
| `benefits.py` | `chunk_benefits` — `benefits_clean.md`. |

`Chunk.page` is always the real source page number, or `None` when the source
has no pages (the benefits markdown). Non-page location data (e.g. a table
index) goes in `Chunk.metadata`, not in `page`.

## Where things are stored

| Source | Chunker | Target table |
|---|---|---|
| `data/Syllabus/<CODE>.pdf` | `chunk_syllabus` | `course_doc_chunks` (doc_type `Syllabus`) |
| `data/IP/<CODE>.pdf` | `chunk_ip` | `course_doc_chunks` (doc_type `IP`) |
| `data/benefits_clean.md` | `chunk_benefits` | `benefit_chunks` |
