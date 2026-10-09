"""Add full-text search (generated tsvector + GIN) to the chunk tables.

Revision ID: 0002_add_full_text_search
Revises: 0001_baseline
Create Date: 2026-10-10

Replaces the ad-hoc ``scripts/add_fts.py`` script. Idempotent (``IF NOT
EXISTS``), so it is safe to run against databases where the columns were
already added by hand.
"""

from collections.abc import Sequence

from alembic import op
from app.models import FTS_EXPRESSION

# revision identifiers, used by Alembic.
revision: str = "0002_add_full_text_search"
down_revision: str | Sequence[str] | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table name, GIN index name) pairs sharing the same generated column.
FTS_TABLES = (
    ("course_doc_chunks", "ix_course_doc_chunks_fts"),
    ("benefit_chunks", "ix_benefit_chunks_fts"),
)


def upgrade() -> None:
    """Add generated tsvector columns and GIN indexes for hybrid search."""
    for table, index_name in FTS_TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN IF NOT EXISTS fts tsvector "
            f"GENERATED ALWAYS AS ({FTS_EXPRESSION}) STORED"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table} USING GIN (fts)"
        )


def downgrade() -> None:
    """Drop the GIN indexes and generated tsvector columns."""
    for table, index_name in FTS_TABLES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS fts")
