"""Database schema and vector-index management for ingestion."""

from sqlalchemy import text

from app.database import engine
from app.models import Base

from .console import log

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
    """Create the pgvector extension and all ORM tables if missing."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)


def create_hnsw_indexes() -> None:
    """Create the HNSW vector indexes used by retrieval."""
    with engine.begin() as conn:
        for table, ddl in HNSW_INDEX_SQL.items():
            conn.execute(text(ddl))
            log(f"  hnsw index ready on {table}")
