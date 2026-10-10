"""CLI entrypoint for the CourseCompass ingestion pipeline.

Parses authenticated course documents (Syllabus + IP PDFs) and the academic
benefits markdown into semantic chunks, embeds them, and persists them into
`course_doc_chunks` / `benefit_chunks`.

The implementation lives in the ``ingestion/`` package; this file only wires up
the import path so the pipeline runs with:

    uv run python scripts/ingest.py --courses CSE273 CSE101
    uv run python scripts/ingest.py                 # everything, incremental
    uv run python scripts/ingest.py --workers 2     # half the first-run time
    uv run python scripts/ingest.py --benefits-only
    uv run python scripts/ingest.py --force-rebuild # recompute all, skipping the DB already-present check

See ``ingestion/README.md`` for the stage-by-stage map.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from ingestion.cli import main

if __name__ == "__main__":
    main()
