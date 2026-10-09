"""Filesystem locations used by the ingestion pipeline.

Single source of truth for where raw source documents live, so no other
module has to rebuild these paths.
"""

from pathlib import Path

# scripts/ingestion/paths.py -> scripts -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BACKEND_DIR / "data"
SYLLABUS_DIR = DATA_DIR / "Syllabus"
IP_DIR = DATA_DIR / "IP"
BENEFITS_MD = DATA_DIR / "benefits_clean.md"
