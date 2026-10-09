"""Make chunk page_number nullable.

Revision ID: 0003_page_number_nullable
Revises: 0002_add_full_text_search
Create Date: 2026-10-10

``page_number`` previously meant different things per chunker (a real page, a
hardcoded 1 or 2, or a table index) and was ``NOT NULL``. It now means a real
source page number, or ``NULL`` when the source has no pages (the benefits
markdown).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_page_number_nullable"
down_revision: str | Sequence[str] | None = "0002_add_full_text_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("course_doc_chunks", "benefit_chunks")


def upgrade() -> None:
    """Allow page_number to be NULL where the source has no pages."""
    for table in TABLES:
        op.alter_column(
            table, "page_number", existing_type=sa.Integer(), nullable=True
        )


def downgrade() -> None:
    """Restore the NOT NULL constraint (fails if NULL rows are present)."""
    for table in TABLES:
        op.alter_column(
            table, "page_number", existing_type=sa.Integer(), nullable=False
        )
