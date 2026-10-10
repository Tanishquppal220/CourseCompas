"""Filesystem locations used by the ingestion pipeline.

Single source of truth for where raw source documents live, so no other
module has to rebuild these paths.

``BENEFITS_MD`` is a hand-cleaned copy of ``docs/BENEFITS_AND_POLICIES.md``:
its content was manually restructured into the ``|``-table markdown the
benefits chunker expects. Regenerating it is a manual step (tracked in git
via ``.gitignore``'s ``!data/benefits_clean.md`` exception).
"""

from pathlib import Path

# scripts/ingestion/paths.py -> scripts -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BACKEND_DIR / "data"
SYLLABUS_DIR = DATA_DIR / "Syllabus"
IP_DIR = DATA_DIR / "IP"
BENEFITS_MD = DATA_DIR / "benefits_clean.md"
