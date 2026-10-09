"""Command-line interface for the ingestion pipeline."""

import argparse
import logging

from .pipeline import run_ingestion


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for ``scripts/ingest.py``."""
    parser = argparse.ArgumentParser(description="Ingest CourseCompass docs")
    parser.add_argument(
        "--courses",
        nargs="*",
        default=None,
        help="course codes to ingest (default: all)",
    )
    parser.add_argument("--benefits-only", action="store_true")
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="recompute everything even if chunks already exist in the DB",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore the on-disk parse cache and re-parse PDFs",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="processes to run parsing/embedding in (default 1; each uses "
        "~3GB RAM plus ~3GB for the embedder, so use 2 only on machines "
        "with plenty of free memory)",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="keep going after a document fails (default: abort on first error)",
    )
    return parser


def main() -> None:
    """Parse CLI arguments and run the ingestion pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    args = build_argument_parser().parse_args()
    run_ingestion(
        courses=args.courses,
        benefits_only=args.benefits_only,
        force_rebuild=args.force_rebuild,
        force=args.force,
        workers=args.workers,
        continue_on_error=args.continue_on_error,
    )
