"""End-to-end ingestion pipeline for CourseCompass.

Parses authenticated course documents (Syllabus + IP PDFs) and the academic
benefits markdown into semantic chunks, embeds them with
Qwen3-Embedding-0.6B, and persists into `course_doc_chunks` /
`benefit_chunks`.

The pipeline is incremental by default: a (course_code, doc_type) whose
chunks already exist in the database is skipped, so re-runs and interrupted
runs only reprocess what is missing. Use `--force-rebuild` to recompute from
scratch. Within a run each doc is idempotent (delete-then-insert).

Docling parsing is CPU-bound per page and (measured on this machine) cannot
be sped up with Docling's threaded/parallel options. Use `--workers N` to
halve the first-run parse time by running N independent processes, each
handling its own share of files (each worker loads its own models, so watch
RAM: ~3GB per worker for Docling plus ~3GB for the embedder).

Usage:
  uv run python scripts/ingest.py --courses CSE273 CSE101
  uv run python scripts/ingest.py                 # everything, incremental
  uv run python scripts/ingest.py --workers 2     # half the first-run time
  uv run python scripts/ingest.py --benefits-only
  uv run python scripts/ingest.py --force-rebuild # recompute all + ignore cache
"""
import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from chunkers import chunk_benefits, chunk_ip, chunk_syllabus
from parse_pdf import batch_parse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.embeddings import embed_texts
from app.models import Base, BenefitChunk, CourseDocumentChunk

DATA_DIR = backend_dir / "data"
SYLLABUS_DIR = DATA_DIR / "Syllabus"
IP_DIR = DATA_DIR / "IP"
BENEFITS_MD = DATA_DIR / "benefits_clean.md"

HNSW_INDEX_SQL = {
    "course_doc_chunks": (
        "CREATE INDEX IF NOT EXISTS ix_course_doc_chunks_embedding "
        "ON course_doc_chunks USING hnsw (embedding vector_cosine_ops)"
    ),
    "benefit_chunks": (
        "CREATE INDEX IF NOT EXISTS ix_benefit_chunks_embedding "
        "ON benefit_chunks USING hnsw (embedding vector_cosine_ops)"
    ),
}


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_tables() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)


def create_hnsw_indexes() -> None:
    with engine.begin() as conn:
        for table, ddl in HNSW_INDEX_SQL.items():
            conn.execute(text(ddl))
            log(f"  hnsw index ready on {table}")


def _assign_indices(chunks) -> list:
    for i, c in enumerate(chunks):
        c.metadata["chunk_index"] = i
    return chunks


def _doc_row_count(db, code: str, doc_type: str) -> int:
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
            if force_rebuild or _doc_row_count(db, code, doc_type) == 0:
                tasks.append((code, doc_type, pdf.name, pdf))
    return tasks


def _chunk_for(parsed, doc_type):
    if doc_type == "Syllabus":
        return chunk_syllabus(parsed.text_items)
    return chunk_ip(parsed.text_items, parsed.tables)


def ingest_course_docs(db, tasks: list) -> int:
    """Parse (if needed), chunk, embed, and persist one batch of doc sets."""
    if not tasks:
        return 0

    paths = sorted({t[3] for t in tasks})
    log(f"  parsing {len(paths)} uncached PDFs (Docling)")
    parsed_map = {p: parsed for p, parsed in batch_parse(paths, use_cache=True, verbose=True)}

    by_code = {}
    for code, doc_type, doc_name, pdf in tasks:
        by_code.setdefault(code, []).append((doc_type, doc_name, pdf))

    total = 0
    for code, docsets in sorted(by_code.items()):
        for doc_type, doc_name, pdf in docsets:
            parsed = parsed_map.get(pdf.resolve())
            if parsed is None:
                log(f"  {code} {doc_type}: parse failed, skipped")
                continue
            chunks = _assign_indices(_chunk_for(parsed, doc_type))
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
                log(f"  {code} {doc_type}: {len(rows)} chunks in {time.time()-t0:.0f}s")
            except IntegrityError:
                db.rollback()
                log(f"  {code} {doc_type}: SKIPPED (FK violation / unknown course)")
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                log(f"  {code} {doc_type}: ERROR {exc}")
    return total


def _run_task_batch(tasks: list) -> int:
    """Worker entrypoint: opens its own DB session and ingests its share."""
    db = SessionLocal()
    try:
        return ingest_course_docs(db, tasks)
    finally:
        db.close()


def run_course_ingest(tasks: list, workers: int) -> int:
    if not tasks:
        return 0
    if workers <= 1 or len(tasks) == 1:
        return _run_task_batch(tasks)
    job_splits = [t for t in [tasks[i::workers] for i in range(workers)] if t]
    log(f"  running {len(job_splits)} ingestion processes")
    total = 0
    with ProcessPoolExecutor(max_workers=len(job_splits)) as pool:
        for count in pool.map(_run_task_batch, job_splits):
            total += count
    return total


def ingest_benefits(db, force_rebuild: bool) -> int:
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
    db.bulk_insert_mappings(BenefitChunk, rows)
    db.commit()
    log(f"  benefits: {len(rows)} chunks in {time.time()-t0:.0f}s")
    return len(rows)


def available_courses() -> list:
    codes = {p.stem for p in SYLLABUS_DIR.glob("*.pdf")}
    codes |= {p.stem for p in IP_DIR.glob("*.pdf")}
    return sorted(codes)


def main():
    parser = argparse.ArgumentParser(description="Ingest CourseCompass docs")
    parser.add_argument(
        "--courses",
        nargs="*",
        default=None,
        help="course codes to ingest (default: all)",
    )
    parser.add_argument("--benefits-only", action="store_true")
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="recompute everything even if chunks already exist in the DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore the docling on-disk cache and re-parse PDFs",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="processes to run parsing/embedding in (default 1; each uses "
        "~3GB RAM plus ~3GB for the embedder, so use 2 only on machines "
        "with plenty of free memory)",
    )
    args = parser.parse_args()

    ensure_tables()
    db = SessionLocal()
    started = time.time()
    try:
        if args.benefits_only:
            ingest_benefits(db, args.force_rebuild)
        else:
            codes = args.courses or available_courses()
            tasks = plan_course_docs(db, codes, args.force_rebuild or args.force)
            log(f"targeting {len(codes)} courses; {len(tasks)} doc(s) need work")
            run_course_ingest(tasks, args.workers)
            ingest_benefits(db, args.force_rebuild)
        create_hnsw_indexes()
    finally:
        db.close()

    for table in HNSW_INDEX_SQL:
        with engine.connect() as conn:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            log(f"{table}: total rows = {n}")
    log(f"total time: {time.time()-started:.0f}s")


if __name__ == "__main__":
    main()