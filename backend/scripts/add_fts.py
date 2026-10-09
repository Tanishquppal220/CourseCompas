"""CLI entrypoint: add full-text search (tsvector + GIN) to the chunk tables.

The implementation is now an Alembic migration
(``alembic/versions/0002_add_full_text_search.py``); this wrapper applies just
that revision so the historical command keeps working:

    uv run python scripts/add_fts.py

For general schema changes use Alembic directly, e.g. ``uv run alembic upgrade
head``.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config

from alembic import command


def main() -> None:
    """Apply the full-text-search Alembic revision."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "0002_add_full_text_search")


if __name__ == "__main__":
    main()
