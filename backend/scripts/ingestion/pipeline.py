"""End-to-end ingestion pipeline: parse -> chunk -> embed -> store.

Reading order of a run:

    1. ``ensure_tables``            schema: extension + tables + migrations
    2. ``plan_course_docs``         decide which (course, doc_type) need work
    3. ``run_course_ingest``        parse/chunk in a pool, embed, persist
    4. ``ingest_benefits``          same for benefits_clean.md
    5. ``create_hnsw_indexes``      build the vector indexes

The pipeline is incremental by default: a (course_code, doc_type) whose chunks
already exist is skipped, so re-runs only reprocess what is missing. Within a
run each document is idempotent (delete-then-insert). Use ``--force-rebuild``
to recompute everything from scratch.

Parsing is CPU-bound per page, so ``--workers N`` runs parsing/chunking in up
to N processes with dynamic scheduling. Embedding and persistence always run
in the single main process, so exactly one copy of the embedding model is
loaded no matter how many workers are used.
"""

import logging
import time
from concurrent.futures import ProcessPoolExecutor

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.embeddings import embed_texts
from app.models import BenefitChunk, CourseDocumentChunk

from .chunking import chunk_benefits, chunk_ip, chunk_syllabus
from .console import log
from .database import HNSW_INDEX_SQL, create_hnsw_indexes, ensure_tables
from .parsing import batch_parse
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


def parse_and_chunk_one(task):
    """Parse one PDF (cache-aware) and chunk it; runs in a worker process.

    Returns ``(code, doc_type, document_name, chunks | None)`` where ``None``
    means the PDF failed to parse. The worker never embeds or touches the
    database, so worker processes stay small and no embedding model copy is
    loaded per worker. Each file is handled by exactly one worker, so the
    per-file parse cache never sees concurrent writers.
    """
    code, doc_type, doc_name, pdf = task
    parsed = None
    for _path, doc in batch_parse([pdf], use_cache=True, verbose=False):
        parsed = doc
    if parsed is None:
        return code, doc_type, doc_name, None
    return code, doc_type, doc_name, chunk_parsed_document(parsed, doc_type)


def persist_document_chunks(db, result, continue_on_error: bool = False) -> int:
    """Embed and persist one document's chunks; runs in the main process.

    ``result`` is a ``(code, doc_type, document_name, chunks | None)`` tuple
    from :func:`parse_and_chunk_one`. The embedding model is loaded here via
    the process-local ``lru_cache``, keeping it to a single copy per run.
    """
    code, doc_type, doc_name, chunks = result
    if chunks is None:
        logger.error("%s %s: parse failed", code, doc_type)
        if not continue_on_error:
            raise RuntimeError(f"Failed to parse {doc_name}")
        return 0
    if not chunks:
        log(f"  {code} {doc_type}: no chunks, skipped")
        return 0

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
            "chunk_index": i,
            "chunk_type": c.chunk_type,
            "content": c.content,
            "metadata": c.metadata.to_dict() if c.metadata else {},
            "embedding": vec,
        }
        for i, (c, vec) in enumerate(zip(chunks, embeddings))
    ]

    db.query(CourseDocumentChunk).filter_by(
        course_code=code, doc_type=doc_type
    ).delete()
    try:
        db.bulk_insert_mappings(CourseDocumentChunk, rows)
        db.commit()
        log(f"  {code} {doc_type}: {len(rows)} chunks in {time.time() - t0:.0f}s")
        return len(rows)
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
    return 0


def run_course_ingest(tasks: list, workers: int, continue_on_error: bool = False) -> int:
    """Ingest the task list, parsing in a process pool when ``workers > 1``.

    Parsing (and chunking) is CPU-bound, so it runs in up to ``workers``
    processes with dynamic scheduling (no round-robin split, so heavy IP docs
    cannot cluster on one worker). Embedding and persistence always run in
    this single main process, holding one embedding-model copy.
    """
    if not tasks:
        return 0

    db = SessionLocal()
    total = 0
    try:
        if workers <= 1 or len(tasks) == 1:
            for task in tasks:
                total += persist_document_chunks(
                    db,
                    parse_and_chunk_one(task),
                    continue_on_error=continue_on_error,
                )
        else:
            log(f"  parsing {len(tasks)} docs across {workers} processes")
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for result in pool.map(parse_and_chunk_one, tasks):
                    total += persist_document_chunks(
                        db, result, continue_on_error=continue_on_error
                    )
    finally:
        db.close()
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
            "document_name": "benefits_clean.md",
            "section_title": c.section_title,
            "page_number": c.page,
            "chunk_index": i,
            "chunk_type": c.chunk_type,
            "content": c.content,
            "metadata": c.metadata.to_dict() if c.metadata else {},
            "embedding": vec,
        }
        for i, (c, vec) in enumerate(zip(chunks, embeddings))
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
    ensure_tables() # 
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