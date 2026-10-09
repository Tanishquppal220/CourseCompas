"""End-to-end ingestion pipeline: parse -> chunk -> embed -> store.

Reading order of a run:

    1. ``ensure_tables``            create tables + pgvector extension
    2. ``plan_course_docs``         decide which (course, doc_type) need work
    3. ``run_course_ingest``        parse PDFs, chunk, embed, persist
    4. ``ingest_benefits``          same for benefits_clean.md
    5. ``create_hnsw_indexes``      build the vector indexes

The pipeline is incremental by default: a (course_code, doc_type) whose chunks
already exist is skipped, so re-runs only reprocess what is missing. Within a
run each document is idempotent (delete-then-insert). Use ``--force-rebuild``
to recompute everything from scratch.

Docling parsing is CPU-bound per page and (measured on this machine) cannot be
sped up with Docling's threaded options. Use ``--workers N`` to run N
independent processes, each handling its own share of files. Each worker loads
its own models, so watch RAM: ~3GB per worker for Docling plus ~3GB for the
embedder.
"""

import logging
import time
from concurrent.futures import ProcessPoolExecutor
from functools import partial

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.embeddings import embed_texts
from app.models import BenefitChunk, CourseDocumentChunk

from .chunking import assign_chunk_indices, chunk_benefits, chunk_ip, chunk_syllabus
from .console import log
from .database import HNSW_INDEX_SQL, create_hnsw_indexes, ensure_tables
from .parsing import batch_parse
from .parsing.config import PARSER_BACKEND
from .paths import BENEFITS_MD, IP_DIR, SYLLABUS_DIR

logger = logging.getLogger(__name__)


def count_document_chunks(db, code: str, doc_type: str) -> int:
    """Return how many chunks are already stored for a (course, doc_type)."""
    return (
        db.query(CourseDocumentChunk)
        .filter_by(course_code=code, doc_type=doc_type)
        .count()
    )


def plan_course_docs(db, codes: list, force_rebuild: bool) -> list:
    """Return (code, doc_type, document_name, pdf_path) for docs needing work."""
    tasks = []
    for code in codes:
        for doc_type, pdf in (
            ("Syllabus", SYLLABUS_DIR / f"{code}.pdf"),
            ("IP", IP_DIR / f"{code}.pdf"),
        ):
            if not pdf.exists():
                continue
            if force_rebuild or count_document_chunks(db, code, doc_type) == 0:
                tasks.append((code, doc_type, pdf.name, pdf))
    return tasks


def chunk_parsed_document(parsed, doc_type: str):
    """Dispatch a parsed document to the chunker for its type."""
    if doc_type == "Syllabus":
        return chunk_syllabus(parsed.text_items)
    return chunk_ip(parsed.text_items, parsed.tables)


def ingest_course_docs(db, tasks: list, continue_on_error: bool = False) -> int:
    """Parse (if needed), chunk, embed, and persist one batch of doc sets.

    On failure the transaction is rolled back and the error is logged with a
    full traceback. The run aborts unless ``continue_on_error`` is set.
    """
    if not tasks:
        return 0

    paths = sorted({t[3] for t in tasks})
    log(f"  parsing {len(paths)} uncached PDFs ({PARSER_BACKEND})")
    parsed_map = {
        p: parsed for p, parsed in batch_parse(paths, use_cache=True, verbose=True)
    }

    by_code = {}
    for code, doc_type, doc_name, pdf in tasks:
        by_code.setdefault(code, []).append((doc_type, doc_name, pdf))

    total = 0
    for code, docsets in sorted(by_code.items()):
        for doc_type, doc_name, pdf in docsets:
            parsed = parsed_map.get(pdf.resolve())
            if parsed is None:
                logger.error("%s %s: parse failed", code, doc_type)
                if not continue_on_error:
                    raise RuntimeError(f"Failed to parse {pdf}")
                continue
            chunks = assign_chunk_indices(chunk_parsed_document(parsed, doc_type))
            if not chunks:
                log(f"  {code} {doc_type}: no chunks, skipped")
                continue

            t0 = time.time()
            texts = [c.content for c in chunks]
            embeddings = embed_texts(texts)
            rows = [
                {
                    "course_code": code,
                    "document_name": doc_name,
                    "doc_type": doc_type,
                    "section_title": c.section_title,
                    "page_number": c.page,
                    "chunk_index": c.metadata.get("chunk_index", 0),
                    "chunk_type": c.chunk_type,
                    "content": c.content,
                    "metadata": c.metadata,
                    "embedding": vec,
                }
                for c, vec in zip(chunks, embeddings)
            ]

            db.query(CourseDocumentChunk).filter_by(
                course_code=code, doc_type=doc_type
            ).delete()
            try:
                db.bulk_insert_mappings(CourseDocumentChunk, rows)
                db.commit()
                total += len(rows)
                log(
                    f"  {code} {doc_type}: {len(rows)} chunks in {time.time() - t0:.0f}s"
                )
            except IntegrityError:
                db.rollback()
                logger.exception("%s %s: failed to persist chunks", code, doc_type)
                if not continue_on_error:
                    raise
            except Exception:
                db.rollback()
                logger.exception("%s %s: ingestion error", code, doc_type)
                if not continue_on_error:
                    raise
    return total


def ingest_task_batch(tasks: list, continue_on_error: bool = False) -> int:
    """Worker entrypoint: opens its own DB session and ingests its share."""
    db = SessionLocal()
    try:
        return ingest_course_docs(db, tasks, continue_on_error=continue_on_error)
    finally:
        db.close()


def run_course_ingest(tasks: list, workers: int, continue_on_error: bool = False) -> int:
    """Ingest the task list, optionally across multiple worker processes."""
    if not tasks:
        return 0
    if workers <= 1 or len(tasks) == 1:
        return ingest_task_batch(tasks, continue_on_error=continue_on_error)
    job_splits = [t for t in [tasks[i::workers] for i in range(workers)] if t]
    log(f"  running {len(job_splits)} ingestion processes")
    total = 0
    with ProcessPoolExecutor(max_workers=len(job_splits)) as pool:
        worker = partial(ingest_task_batch, continue_on_error=continue_on_error)
        for count in pool.map(worker, job_splits):
            total += count
    return total


def ingest_benefits(db, force_rebuild: bool, continue_on_error: bool = False) -> int:
    """Chunk, embed, and persist the academic benefits markdown."""
    if not BENEFITS_MD.exists():
        log("  benefits_clean.md not found, skipping benefits")
        return 0
    if not force_rebuild and db.query(BenefitChunk).count() > 0:
        log("  benefits: already present, skipping")
        return 0
    chunks = chunk_benefits(BENEFITS_MD)
    t0 = time.time()
    embeddings = embed_texts([c.content for c in chunks])
    rows = [
        {
            "document_name": "Academic Benefits.pdf",
            "section_title": c.section_title,
            "page_number": c.page,
            "chunk_index": c.metadata.get("chunk_index", 0),
            "chunk_type": c.chunk_type,
            "content": c.content,
            "metadata": c.metadata,
            "embedding": vec,
        }
        for c, vec in zip(chunks, embeddings)
    ]
    db.query(BenefitChunk).delete()
    try:
        db.bulk_insert_mappings(BenefitChunk, rows)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("benefits: failed to persist chunks")
        if not continue_on_error:
            raise
        return 0
    log(f"  benefits: {len(rows)} chunks in {time.time() - t0:.0f}s")
    return len(rows)


def available_courses() -> list:
    """Return every course code that has a Syllabus or IP PDF."""
    codes = {p.stem for p in SYLLABUS_DIR.glob("*.pdf")}
    codes |= {p.stem for p in IP_DIR.glob("*.pdf")}
    return sorted(codes)


def run_ingestion(
    courses: list | None = None,
    benefits_only: bool = False,
    force_rebuild: bool = False,
    force: bool = False,
    workers: int = 1,
    continue_on_error: bool = False,
) -> None:
    """Run the full pipeline (parse -> chunk -> embed -> store -> index)."""
    ensure_tables()
    db = SessionLocal()
    started = time.time()
    try:
        if benefits_only:
            ingest_benefits(db, force_rebuild, continue_on_error=continue_on_error)
        else:
            codes = courses or available_courses()
            tasks = plan_course_docs(db, codes, force_rebuild or force)
            log(f"targeting {len(codes)} courses; {len(tasks)} doc(s) need work")
            run_course_ingest(tasks, workers, continue_on_error=continue_on_error)
            ingest_benefits(db, force_rebuild, continue_on_error=continue_on_error)
        create_hnsw_indexes()
    finally:
        db.close()

    for table in HNSW_INDEX_SQL:
        with engine.connect() as conn:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        log(f"{table}: total rows = {n}")
    log(f"total time: {time.time() - started:.0f}s")
