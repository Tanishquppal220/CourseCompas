"""Baseline: schema as it existed before Alembic was adopted.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-10

The CourseCompass schema predates Alembic and has always been created by
``Base.metadata.create_all`` (see ``scripts/ingestion/database.py``). This
revision is intentionally empty: it exists only so existing databases can be
stamped into Alembic's history with::

    uv run alembic stamp 0001_baseline

after which the later revisions apply incrementally.
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op: the baseline schema already exists."""


def downgrade() -> None:
    """No-op: dropping the baseline would drop the whole schema."""
