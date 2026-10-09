"""CLI entrypoint for seeding the relational curriculum database.

The implementation lives in the ``seeding/`` package (data, loaders, routine).

    uv run python scripts/seed.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from seeding.load_curriculum import run

if __name__ == "__main__":
    run()
