"""Database schema and vector-index management for ingestion."""

from sqlalchemy import text

from app.database import engine, upgrade_schema

from .console import log

# HNSW vector indexes are operational, not structural: they are recreated
# idempotently (IF NOT EXISTS) at the end of every ingest, so they stay out of
# the Alembic migration history on purpose (see app.database.upgrade_schema for
# the single schema-entry point).
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


def ensure_tables() -> None:
    """Bring the schema up to date: extension, ORM tables, Alembic migrations."""
    upgrade_schema()


def create_hnsw_indexes() -> None:
    """Create the HNSW vector indexes used by retrieval."""
    with engine.begin() as conn:
        for table, ddl in HNSW_INDEX_SQL.items():
            conn.execute(text(ddl))
            log(f"  hnsw index ready on {table}")