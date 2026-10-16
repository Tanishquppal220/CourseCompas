"""Interactive Single-PDF Pipeline Stage Inspector.

Visualizes and inspects every transformation phase of the CourseCompass
ingestion pipeline for a single document (Syllabus or Instruction Plan):

    Stage 1: Raw File & Cache Inode Metadata
    Stage 2: PyMuPDF Extraction (ParsedPdf & ParsedTable)
    Stage 3: Text Cleaning & Boilerplate Stripping (Before vs. After Diff)
    Stage 4: Semantic Classification (Units/Outcomes or TableKind)
    Stage 5: Semantic Chunk Emission (Chunk objects, metadata, & content)
    Stage 6: Embedding Verification (Optional via --embed)

Usage:
    uv run python scripts/tools/inspect_pipeline.py data/Syllabus/CSE205.pdf
    uv run python scripts/tools/inspect_pipeline.py data/IP/CSE205.pdf --step
    uv run python scripts/tools/inspect_pipeline.py CSE205 --type ip --export
    uv run python scripts/tools/inspect_pipeline.py data/IP/CSE205.pdf --stage cleaning
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

# Ensure backend root and scripts are on sys.path for cache unpickling
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = BACKEND_DIR / "scripts"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Backward-compatibility alias for cached pkl files
import ingestion.parsing.models
sys.modules["scripts.ingestion.parsing.models"] = ingestion.parsing.models

# Ingestion imports
from scripts.ingestion.paths import SYLLABUS_DIR, IP_DIR
from scripts.ingestion.parsing.cache import cache_path_for, load_cached
from scripts.ingestion.parsing.parser import parse_pdf
from scripts.ingestion.cleaning.text import (
    strip_page_furniture,
    collapse_whitespace,
    is_page_furniture,
)
from scripts.ingestion.cleaning.instruction_plan import (
    strip_ip_boilerplate,
    clean_chunk_text,
    is_boilerplate,
)
from scripts.ingestion.chunking.chunk import collect_cleaned_text_items, Chunk
from scripts.ingestion.chunking.syllabus import classify_syllabus, chunk_syllabus
from scripts.ingestion.chunking.instruction_plan import classify_tables, chunk_ip, TableKind


# ANSI Terminal Colors
class Colors:
    CYAN = "\033[1;36m"
    GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[1;31m"
    MAGENTA = "\033[1;35m"
    BLUE = "\033[1;34m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def header(title: str) -> None:
    print(f"\n{Colors.CYAN}{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}{Colors.RESET}")


def subheader(title: str) -> None:
    print(f"\n{Colors.YELLOW}--- {title} ---{Colors.RESET}")


def pause_if_step(step_mode: bool) -> None:
    if step_mode:
        print(f"\n{Colors.DIM}[Press Enter to continue to next stage...]{Colors.RESET}", end="")
        input()


def resolve_pdf_path(target: str, doc_type: str | None) -> tuple[Path, str]:
    path_candidate = Path(target)
    if path_candidate.is_file():
        # Inferred from path
        if "syllabus" in str(path_candidate).lower():
            inferred_type = "Syllabus"
        elif "ip" in str(path_candidate).lower():
            inferred_type = "IP"
        else:
            inferred_type = doc_type.capitalize() if doc_type else "Syllabus"
        return path_candidate.resolve(), inferred_type

    # Otherwise treated as course code, e.g. "CSE205"
    code = target.upper()
    req_type = (doc_type or "syllabus").lower()
    if req_type == "syllabus":
        resolved = SYLLABUS_DIR / f"{code}.pdf"
        actual_type = "Syllabus"
    else:
        resolved = IP_DIR / f"{code}.pdf"
        actual_type = "IP"

    if not resolved.is_file():
        print(f"{Colors.RED}Error: PDF not found at {resolved}{Colors.RESET}")
        sys.exit(1)

    return resolved.resolve(), actual_type


def stage_1_raw_info(pdf_path: Path, doc_type: str) -> dict:
    header("STAGE 1: Raw File & Cache Inode Metadata")
    stat = pdf_path.stat()
    cache_file = cache_path_for(pdf_path)
    is_cached = cache_file.exists()

    info = {
        "file_name": pdf_path.name,
        "full_path": str(pdf_path),
        "doc_type": doc_type,
        "size_kb": round(stat.st_size / 1024, 2),
        "modified_time_ns": stat.st_mtime_ns,
        "cache_file": str(cache_file),
        "cache_exists": is_cached,
    }

    print(f"{Colors.BOLD}File Name:{Colors.RESET}       {info['file_name']}")
    print(f"{Colors.BOLD}Document Type:{Colors.RESET}   {info['doc_type']}")
    print(f"{Colors.BOLD}File Size:{Colors.RESET}       {info['size_kb']} KB")
    print(f"{Colors.BOLD}Cache File:{Colors.RESET}      {cache_file.name}")
    status_color = Colors.GREEN if is_cached else Colors.RED
    status_str = "CACHED (Fast resolution)" if is_cached else "NOT CACHED (Will parse with PyMuPDF)"
    print(f"{Colors.BOLD}Cache Status:{Colors.RESET}    {status_color}{status_str}{Colors.RESET}")

    return info


def _extract_page(item: any) -> int:
    if isinstance(item, dict):
        return item.get("page", 1)
    if isinstance(item, (list, tuple)) and len(item) > 0:
        return item[0]
    return 1


def _extract_text(item: any) -> str:
    if isinstance(item, dict):
        return item.get("text", "")
    if isinstance(item, (list, tuple)) and len(item) > 1:
        return str(item[1])
    return str(item)


def stage_2_parsed_pdf(pdf_path: Path, use_cache: bool = True) -> tuple[any, dict]:
    header("STAGE 2: PyMuPDF Document Extraction (ParsedPdf)")

    t0 = time.perf_counter()
    parsed = parse_pdf(pdf_path, use_cache=use_cache)
    duration_ms = round((time.perf_counter() - t0) * 1000, 2)

    total_text_items = len(parsed.text_items)
    total_tables = len(parsed.tables)
    pages = sorted(list({_extract_page(item) for item in parsed.text_items} | {t.page for t in parsed.tables}))

    print(f"{Colors.BOLD}Extraction Time:{Colors.RESET}   {duration_ms} ms")
    print(f"{Colors.BOLD}Total Pages:{Colors.RESET}       {len(pages)} (Page range: {min(pages) if pages else 0} - {max(pages) if pages else 0})")
    print(f"{Colors.BOLD}Raw Text Blocks:{Colors.RESET}   {total_text_items}")
    print(f"{Colors.BOLD}Extracted Tables:{Colors.RESET}  {total_tables}")

    subheader("Sample Raw Text Block (Page 1)")
    if parsed.text_items:
        first_item = parsed.text_items[0]
        first_text = _extract_text(first_item)
        preview_lines = first_text.strip().splitlines()[:6]
        for line in preview_lines:
            print(f"  {Colors.DIM}|{Colors.RESET} {line}")
        if len(first_text.strip().splitlines()) > 6:
            print(f"  {Colors.DIM}| ... ({len(first_text.strip().splitlines()) - 6} more lines){Colors.RESET}")
    else:
        print("  (No text blocks extracted)")

    if parsed.tables:
        subheader(f"Sample Table 1 (Page {parsed.tables[0].page})")
        t = parsed.tables[0]
        print(f"  Grid Dimensions: {len(t.rows)} rows x {max((len(r) for r in t.rows), default=0)} cols")
        for r_idx, row in enumerate(t.rows[:4]):
            truncated_cells = [c.replace('\n', ' ')[:25] for c in row[:5]]
            print(f"  Row {r_idx}: {' | '.join(truncated_cells)}")
        if len(t.rows) > 4:
            print(f"  ... ({len(t.rows) - 4} more rows)")

    stats = {
        "duration_ms": duration_ms,
        "total_pages": len(pages),
        "total_text_blocks": total_text_items,
        "total_tables": total_tables,
    }
    return parsed, stats


def stage_3_cleaning(parsed: any) -> tuple[list[tuple[int, str]], dict]:
    header("STAGE 3: Text Cleaning, Page Furniture & Boilerplate Removal")

    raw_items = parsed.text_items
    cleaned_items = list(collect_cleaned_text_items(raw_items, drop_boilerplate=True, strip_footers=True))

    dropped_count = len(raw_items) - len(cleaned_items)
    print(f"{Colors.BOLD}Raw Text Blocks In:{Colors.RESET}    {len(raw_items)}")
    print(f"{Colors.BOLD}Cleaned Blocks Out:{Colors.RESET}   {len(cleaned_items)}")
    print(f"{Colors.BOLD}Noise Blocks Dropped:{Colors.RESET} {Colors.GREEN if dropped_count else Colors.DIM}{dropped_count}{Colors.RESET}")

    subheader("Cleaning Before-and-After Inspection")
    found_stripped = False
    for item in raw_items:
        p = _extract_page(item)
        raw = _extract_text(item)
        cleaned = clean_chunk_text(raw)
        if len(raw) - len(cleaned) > 20 or is_boilerplate(raw):
            print(f"{Colors.BOLD}Page {p} Noise Detected & Stripped:{Colors.RESET}")
            for raw_line in raw.splitlines():
                raw_line_s = raw_line.strip()
                if raw_line_s and (is_page_furniture(raw_line_s) or any(bp in raw_line_s for bp in ["tentative plan", "changes in his/her teaching plan"])):
                    print(f"  {Colors.RED}- [STRIPPED]: {raw_line_s[:100]}{Colors.RESET}")
            found_stripped = True
            break

    if not found_stripped:
        print(f"  {Colors.DIM}(No boilerplate paragraphs detected in sample blocks){Colors.RESET}")

    stats = {
        "raw_count": len(raw_items),
        "cleaned_count": len(cleaned_items),
        "dropped_count": dropped_count,
    }
    return cleaned_items, stats


def stage_4_classification(parsed: any, doc_type: str) -> dict:
    header(f"STAGE 4: Semantic Classification ({doc_type})")
    data = {}

    if doc_type == "Syllabus":
        sections = classify_syllabus(parsed.text_items)
        data["overview_blocks"] = len(sections.overview)
        data["outcomes_blocks"] = len(sections.outcomes)
        data["practicals_blocks"] = len(sections.practicals)
        data["references_blocks"] = len(sections.references)
        data["units_found"] = sorted(list(sections.units.keys()))

        print(f"{Colors.BOLD}Course Overview Blocks:{Colors.RESET} {data['overview_blocks']}")
        print(f"{Colors.BOLD}Course Outcomes Blocks:{Colors.RESET} {data['outcomes_blocks']}")
        print(f"{Colors.BOLD}Practicals Blocks:{Colors.RESET}      {data['practicals_blocks']}")
        print(f"{Colors.BOLD}References Blocks:{Colors.RESET}      {data['references_blocks']}")
        print(f"{Colors.BOLD}Units Identified:{Colors.RESET}       {Colors.GREEN}{', '.join(f'Unit {u}' for u in data['units_found'])}{Colors.RESET}")

        if sections.units:
            first_unit = data['units_found'][0]
            subheader(f"Sample Unit {first_unit} First Block")
            unit_text = sections.units[first_unit][0][1]
            for ln in unit_text.splitlines()[:5]:
                print(f"  {Colors.CYAN}|{Colors.RESET} {ln}")

    else:  # IP
        claims = classify_tables(parsed.tables)
        counts = {
            TableKind.OVERVIEW: 0,
            TableKind.BOOKS: 0,
            TableKind.LECTURE: 0,
            TableKind.SCHEDULE: 0,
            TableKind.OTHER: 0,
        }
        for kinds in claims.kinds:
            if not kinds:
                counts[TableKind.OTHER] += 1
            for k in kinds:
                counts[k] = counts.get(k, 0) + 1

        data["table_kind_counts"] = counts
        print(f"{Colors.BOLD}Overview Tables (Weightages):{Colors.RESET} {counts[TableKind.OVERVIEW]}")
        print(f"{Colors.BOLD}Textbook/Reference Tables:{Colors.RESET}    {counts[TableKind.BOOKS]}")
        print(f"{Colors.BOLD}Lecture Plan Tables:{Colors.RESET}          {counts[TableKind.LECTURE]}")
        print(f"{Colors.BOLD}LTP Schedule Tables:{Colors.RESET}          {counts[TableKind.SCHEDULE]}")

    return data


def stage_5_chunks(parsed: any, doc_type: str, limit: int = 5) -> list[Chunk]:
    header("STAGE 5: Final Semantic Chunk Emission")

    if doc_type == "Syllabus":
        chunks = chunk_syllabus(parsed.text_items)
    else:
        chunks = chunk_ip(parsed.text_items, parsed.tables)

    for idx, c in enumerate(chunks):
        c.chunk_index = idx

    print(f"{Colors.BOLD}Total Chunks Emitted:{Colors.RESET} {Colors.GREEN}{len(chunks)}{Colors.RESET}")

    # Taxonomy breakdown
    type_counts: dict[str, int] = {}
    for c in chunks:
        type_counts[c.chunk_type] = type_counts.get(c.chunk_type, 0) + 1

    print(f"\n{Colors.BOLD}Chunk Taxonomy Breakdown:{Colors.RESET}")
    for c_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {Colors.CYAN}{c_type:<18}{Colors.RESET}: {count}")

    display_limit = len(chunks) if limit <= 0 else min(limit, len(chunks))
    subheader(f"Inspecting First {display_limit} Chunks")

    for i in range(display_limit):
        c = chunks[i]
        meta_json = json.dumps(c.metadata, default=str)
        print(f"\n{Colors.MAGENTA}┌── Chunk #{c.chunk_index} [{c.doc_type} / {c.chunk_type}] (Page {c.page}){Colors.RESET}")
        print(f"{Colors.MAGENTA}│{Colors.RESET} {Colors.BOLD}Section Title:{Colors.RESET} {c.section_title or 'N/A'}")
        print(f"{Colors.MAGENTA}│{Colors.RESET} {Colors.BOLD}Metadata:{Colors.RESET}      {Colors.YELLOW}{meta_json}{Colors.RESET}")
        print(f"{Colors.MAGENTA}│{Colors.RESET} {Colors.BOLD}Content Length:{Colors.RESET} {len(c.content)} chars")
        print(f"{Colors.MAGENTA}│{Colors.RESET} {Colors.BOLD}Content Preview:{Colors.RESET}")
        for ln in c.content.strip().splitlines()[:4]:
            print(f"{Colors.MAGENTA}│{Colors.RESET}   {ln}")
        if len(c.content.strip().splitlines()) > 4:
            print(f"{Colors.MAGENTA}│{Colors.RESET}   {Colors.DIM}... ({len(c.content.strip().splitlines()) - 4} more lines){Colors.RESET}")
        print(f"{Colors.MAGENTA}└──{'─' * 70}{Colors.RESET}")

    return chunks


def stage_6_embedding(chunks: list[Chunk]) -> None:
    header("STAGE 6: Dense Embedding Vector Verification")
    if not chunks:
        print("No chunks to embed.")
        return

    print("Loading SentenceTransformer model 'BAAI/bge-small-en-v1.5'...")
    from app.embeddings import embed_texts

    sample_chunk = chunks[0]
    t0 = time.perf_counter()
    vectors = embed_texts([sample_chunk.content])
    ms = round((time.perf_counter() - t0) * 1000, 2)

    vec = vectors[0]
    print(f"{Colors.BOLD}Embedded Chunk #{sample_chunk.chunk_index}:{Colors.RESET} [{sample_chunk.doc_type}/{sample_chunk.chunk_type}] in {ms} ms")
    print(f"{Colors.BOLD}Vector Dimensions:{Colors.RESET} {Colors.GREEN}{len(vec)}{Colors.RESET}")
    print(f"{Colors.BOLD}First 5 Floats:{Colors.RESET}    {[round(x, 5) for x in vec[:5]]}")

    # Check L2 normalization
    import math
    norm = math.sqrt(sum(x * x for x in vec))
    print(f"{Colors.BOLD}L2 Unit Norm:{Colors.RESET}      {norm:.6f} (Expected: 1.000000)")


from dataclasses import is_dataclass, asdict


def _serialize_meta(obj: any) -> any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if is_dataclass(obj):
        return asdict(obj)
    return str(obj)


def export_dumps(export_dir: Path, raw_info: dict, parsed: any, cleaned_items: list, chunks: list[Chunk]) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    header(f"EXPORT: Saving Intermediate Artifacts to {export_dir}")

    # 1. Info
    (export_dir / "01_raw_info.json").write_text(json.dumps(raw_info, indent=2), encoding="utf-8")

    # 2. Parsed summary
    parsed_summary = {
        "text_items_count": len(parsed.text_items),
        "tables_count": len(parsed.tables),
        "sample_table": parsed.tables[0].rows if parsed.tables else [],
    }
    (export_dir / "02_parsed_summary.json").write_text(json.dumps(parsed_summary, indent=2), encoding="utf-8")

    # 3. Cleaned items text dump
    cleaned_text = "\n\n---\n\n".join(f"[Page {p}]\n{txt}" for p, txt in cleaned_items)
    (export_dir / "03_cleaned_text.md").write_text(cleaned_text, encoding="utf-8")

    # 4. Chunks json
    chunks_data = [
        {
            "chunk_index": c.chunk_index,
            "doc_type": c.doc_type,
            "chunk_type": c.chunk_type,
            "page": c.page,
            "section_title": c.section_title,
            "metadata": _serialize_meta(c.metadata) if c.metadata is not None else {},
            "content": c.content,
        }
        for c in chunks
    ]
    (export_dir / "05_chunks.json").write_text(json.dumps(chunks_data, indent=2, default=_serialize_meta), encoding="utf-8")

    # 5. Chunks readable markdown
    chunks_md = []
    for c in chunks:
        meta_dict = _serialize_meta(c.metadata) if c.metadata is not None else {}
        chunks_md.append(
            f"## Chunk #{c.chunk_index} — `{c.chunk_type}` (Page {c.page})\n"
            f"**Section Title:** {c.section_title or 'N/A'}  \n"
            f"**Metadata:** `{json.dumps(meta_dict)}`  \n\n"
            f"```markdown\n{c.content}\n```\n"
        )
    (export_dir / "05_chunks_readable.md").write_text("\n".join(chunks_md), encoding="utf-8")

    print(f"{Colors.GREEN}Successfully exported 5 stage files to {export_dir}:{Colors.RESET}")
    print(f"  - 01_raw_info.json")
    print(f"  - 02_parsed_summary.json")
    print(f"  - 03_cleaned_text.md")
    print(f"  - 05_chunks.json")
    print(f"  - 05_chunks_readable.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="Step-by-step pipeline inspector for a single PDF.")
    parser.add_argument("target", help="Path to PDF or course code (e.g. data/Syllabus/CSE205.pdf or CSE205)")
    parser.add_argument("--type", "-t", choices=["syllabus", "ip"], help="Document type shortcut when target is a course code")
    parser.add_argument("--stage", "-s", choices=["raw", "parsed", "cleaning", "classified", "chunks", "all"], default="all", help="Target stage to inspect")
    parser.add_argument("--step", action="store_true", help="Pause for Enter after each stage")
    parser.add_argument("--no-cache", action="store_true", help="Bypass on-disk parse cache")
    parser.add_argument("--embed", action="store_true", help="Run Stage 6: generate vector embedding for chunk 0")
    parser.add_argument("--limit", type=int, default=5, help="Number of chunks to print preview for (default 5, use 0 for all)")
    parser.add_argument("--export", action="store_true", help="Export readable stage dumps to scratch/inspection_<doc>/")
    args = parser.parse_args()

    pdf_path, doc_type = resolve_pdf_path(args.target, args.type)

    target_stage = args.stage

    # Stage 1
    raw_info = stage_1_raw_info(pdf_path, doc_type)
    if target_stage == "raw":
        return 0
    pause_if_step(args.step)

    # Stage 2
    parsed, _ = stage_2_parsed_pdf(pdf_path, use_cache=not args.no_cache)
    if target_stage == "parsed":
        return 0
    pause_if_step(args.step)

    # Stage 3
    cleaned_items, _ = stage_3_cleaning(parsed)
    if target_stage == "cleaning":
        return 0
    pause_if_step(args.step)

    # Stage 4
    stage_4_classification(parsed, doc_type)
    if target_stage == "classified":
        return 0
    pause_if_step(args.step)

    # Stage 5
    chunks = stage_5_chunks(parsed, doc_type, limit=args.limit)
    if target_stage == "chunks":
        return 0
    pause_if_step(args.step)

    # Stage 6
    if args.embed:
        stage_6_embedding(chunks)

    # Export
    if args.export:
        export_folder = BACKEND_DIR / "scratch" / f"inspection_{pdf_path.stem}_{doc_type}"
        export_dumps(export_folder, raw_info, parsed, cleaned_items, chunks)

    header("PIPELINE INSPECTION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
