import sys
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(backend_dir))  # Add backend directory to sys.path for imports

from app.database import SessionLocal, engine
from app.models import Base, BenefitChunk
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DATA_FILE = "benefits_clean.md"



def extract_chunks_from_markdown(md_path: Path) -> list[dict[str, Any]]:
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    chunks = []
    
    current_section = "Academic Benefits"
    current_overview = ""
    table_index = 0

    for block in blocks:
        
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines or not lines[0].startswith("|"):
            continue

        table_index += 1
        
        # 1. Detect section title from first row
        first_row = [c for c in lines[0].split("|")[1:-1]]
        non_empty = [c for c in first_row if c]
        if non_empty and len(non_empty) == 1 and not lines[0].startswith("| ---"):
            title_candidate = non_empty[0]
            if not any(k in title_candidate.lower() for k in ["category", "stipend", "sr. no", "types of", "proofs"]):
                current_section = title_candidate

        # 2. Extract overview paragraph, column headers, and footer notes
        headers = []
        header_idx = -1
        description_text = ""
        footer_notes = []

        for r_idx, line in enumerate(lines):
            cells = [c for c in line.split("|")[1:-1]]
            meaningful = [c for c in cells if c]
            
            if len(meaningful) == 1 and len(meaningful[0]) > 60:
                description_text = meaningful[0]
            elif any(k in " ".join(meaningful).lower() for k in ["category", "stipend", "sr. no", "types of projects"]):
                header_idx = r_idx
                headers = cells
                break

        if current_overview and not description_text:
            description_text = current_overview

        # 3. Add high-level Policy Overview & Eligibility Rules chunk
        if description_text:
            policy_chunk = f"Section: {current_section}\nType: Policy Overview & Eligibility Rules\nDetails: {description_text}"
            chunks.append({
                "section_title": current_section,
                "chunk_type": "policy_overview",
                "table_index": table_index,
                "content": policy_chunk,
                "metadata": {
                    "section": current_section,
                    "table_index": table_index,
                    "type": "policy_overview"
                }
            })

        # 4. Parse tabular rows with backward & forward fill
        if header_idx != -1 and header_idx + 1 < len(lines):
            headers = [h if h else f"Field_{h_i+1}" for h_i, h in enumerate(headers)]
            
            # Identify benefit column for backward fill
            benefit_col_name = None
            for h in headers:
                if any(k in h.lower() for k in ["benefit", "academic benefit"]):
                    benefit_col_name = h
                    break

            raw_rows = []
            for data_line in lines[header_idx + 1:]:
                if data_line.startswith("| ---"):
                    continue
                cells = [c for c in data_line.split("|")[1:-1]]
                meaningful = [c for c in cells if c]
                if not meaningful:
                    continue

                # Check if this is a footer note row
                if len(meaningful) == 1 and len(meaningful[0]) > 40:
                    footer_notes.append(meaningful[0])
                    continue

                raw_rows.append(cells)

            # Backward fill shared benefits across grouped rows
            if benefit_col_name:
                b_idx = headers.index(benefit_col_name)
                next_benefit = ""
                for r in reversed(raw_rows):
                    if b_idx < len(r) and r[b_idx]:
                        next_benefit = r[b_idx]
                    elif b_idx < len(r) and not r[b_idx] and next_benefit:
                        r[b_idx] = next_benefit

            # Forward fill hierarchical columns (Stipend, Duration, Category, Types)
            last_values = {}
            for cells in raw_rows:
                row_dict = {}
                for col_idx, (h, val) in enumerate(zip(headers, cells)):
                    if val:
                        last_values[h] = val
                        row_dict[h] = val
                    else:
                        if h in last_values and any(k in h.lower() for k in ["stipend", "duration", "category", "types", "achievement"]):
                            row_dict[h] = last_values[h]

                # Format clean, context-rich chunk representation
                context_lines = [f"Section: {current_section}"]
                for k, v in row_dict.items():
                    context_lines.append(f"{k}: {v}")

                if description_text and len(row_dict) > 1:
                    context_lines.append(f"(General Policy: {description_text[:120]}...)")

                content_str = "\n".join(context_lines)
                chunks.append({
                    "section_title": current_section,
                    "chunk_type": "criteria_row",
                    "table_index": table_index,
                    "content": content_str,
                    "metadata": {
                        "section": current_section,
                        "table_index": table_index,
                        "fields": row_dict
                    }
                })

        # 5. Add footer notes / special condition chunks
        for note in footer_notes:
            chunks.append({
                "section_title": current_section,
                "chunk_type": "special_note",
                "table_index": table_index,
                "content": f"Section: {current_section}\nSpecial Policy Note: {note}",
                "metadata": {
                    "section": current_section,
                    "table_index": table_index,
                    "type": "special_policy_note"
                }
            })


    return chunks 
def run_ingestion():
    """
    1. Extract structured text & table chunks from Markdown
    2. Generate embeddings for each chunk using a local model
    3. Store chunks and embeddings in PostgreSQL with vector extension
    4. Create an index for vector similarity search
    """
    md_path = backend_dir / "data" / DATA_FILE
    if not md_path.exists():
        print(f"Error: {md_path} does not exist!")
        return


    chunks = extract_chunks_from_markdown(md_path)

    embedder = SentenceTransformer(MODEL_NAME)

    contents = [c["content"] for c in chunks]
    embeddings = embedder.encode(contents, show_progress_bar=True, normalize_embeddings=True)

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        deleted = session.query(BenefitChunk).delete()
        if deleted:
            print(f"Cleared {deleted} previous benefit chunk records.")
        session.commit()

        print(f"5. Inserting {len(chunks)} benefit chunks into database ...")
        for chunk, emb in zip(chunks, embeddings):
            record = BenefitChunk(
                document_name=md_path.name,
                section_title=chunk["section_title"],
                page_number=chunk["table_index"],  # Use table index as reference page
                chunk_type=chunk["chunk_type"],
                content=chunk["content"],
                chunk_metadata=chunk["metadata"],
                embedding=emb.tolist()
            )
            session.add(record)
        session.commit()

        print("6. Creating HNSW index for vector similarity search ...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_benefit_chunks_embedding_hnsw 
                ON benefit_chunks 
                USING hnsw (embedding vector_cosine_ops);
            """))
            conn.commit()

        print("=== INGESTION COMPLETED SUCCESSFULLY! ===")
        total_rows = session.query(BenefitChunk).count()
        print(f"Verified rows in benefit_chunks table: {total_rows}")

    except Exception as e:
        session.rollback()
        print(f"Ingestion failed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    # run_ingestion()
    run_ingestion()
