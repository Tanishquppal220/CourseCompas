import sys
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(backend_dir))  # Add backend directory to sys.path for imports

from app.database import SessionLocal, engine
from app.models import Base, SchemaChunk
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DATA_FILE = "Schema.md"


def extract_chunks_from_markdown(md_path: Path) -> list[dict[str, Any]]:
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
    chunks = []
    
    current_section = "General Information"
    
    for block in blocks:
        if not block.startswith("|"):
            # Could be a title or section description
            if block.isupper() or "**" in block:
                current_section = block.replace("*", "").strip()
                chunks.append({
                    "section_title": current_section,
                    "chunk_type": "section_header",
                    "content": f"Section: {current_section}",
                    "metadata": {"section": current_section, "type": "header"}
                })
            else:
                chunks.append({
                    "section_title": current_section,
                    "chunk_type": "text",
                    "content": f"Section: {current_section}\nDetails: {block}",
                    "metadata": {"section": current_section, "type": "text"}
                })
            continue

        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
            
        # Parse table
        headers = []
        for i, line in enumerate(lines):
            if "---" in line:
                if i > 0:
                    headers = [c.strip().replace("*", "") for c in lines[i-1].split("|")[1:-1]]
                continue
                
            if "---" not in line and headers:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if not cells:
                    continue
                row_dict = {}
                for idx, (h, val) in enumerate(zip(headers, cells)):
                    if idx < len(headers):
                        h = headers[idx]
                        if val and h:
                            row_dict[h] = val
                
                if row_dict:
                    context_lines = [f"Section: {current_section}"]
                    for k, v in row_dict.items():
                        context_lines.append(f"{k}: {v}")
                    content_str = "\n".join(context_lines)
                    chunks.append({
                        "section_title": current_section,
                        "chunk_type": "table_row",
                        "content": content_str,
                        "metadata": {"section": current_section, "fields": row_dict}
                    })
    return chunks

def run_ingestion():
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
        deleted = session.query(SchemaChunk).delete()
        if deleted:
            print(f"Cleared {deleted} previous schema chunk records.")
        session.commit()

        print(f"Inserting {len(chunks)} schema chunks into database ...")
        for chunk, emb in zip(chunks, embeddings):
            record = SchemaChunk(
                document_name=md_path.name,
                section_title=chunk["section_title"],
                chunk_type=chunk["chunk_type"],
                content=chunk["content"],
                chunk_metadata=chunk["metadata"],
                embedding=emb.tolist()
            )
            session.add(record)
        session.commit()

        print("Creating HNSW index for vector similarity search ...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_schema_chunks_embedding_hnsw 
                ON schema_chunks 
                USING hnsw (embedding vector_cosine_ops);
            """))
            conn.commit()

        print("=== INGESTION COMPLETED SUCCESSFULLY! ===")
        total_rows = session.query(SchemaChunk).count()
        print(f"Verified rows in schema_chunks table: {total_rows}")

    except Exception as e:
        session.rollback()
        print(f"Ingestion failed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_ingestion()
