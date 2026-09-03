import sys
from pathlib import Path
from typing import Any

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal, engine
from app.models import Base, CourseDocumentChunk

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def extract_chunks_from_pdf(pdf_path: Path, doc_type: str, course_code: str) -> list[dict[str, Any]]:
    chunks = []
    
    # Text splitter optimized for general documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text_content = page.extract_text()
                if not text_content:
                    continue
                
                # Split page text into smaller chunks
                page_chunks = text_splitter.split_text(text_content)
                
                for idx, chunk_text in enumerate(page_chunks):
                    # Add context prefix so the embedding captures what this chunk is about
                    contextualized_text = f"Course: {course_code} | Document: {doc_type} | Page: {page_num}\n\n{chunk_text}"
                    
                    chunks.append({
                        "course_code": course_code,
                        "doc_type": doc_type,
                        "page_number": page_num,
                        "chunk_index": idx,
                        "content": contextualized_text
                    })
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        
    return chunks

def run_ingestion():
    print("1. Initializing...")
    embedder = SentenceTransformer(MODEL_NAME)
    
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    Base.metadata.create_all(engine)
    session = SessionLocal()
    
    all_chunks = []
    
    data_dir = backend_dir / "data"
    COURSES_TO_PROCESS = [file.name.strip(".pdf") for file in (data_dir / "Syllabus").glob("*.pdf")]
    print(f"2. Processing target courses: {COURSES_TO_PROCESS}")
    for course_code in COURSES_TO_PROCESS:
        for doc_type, subdir in [("Syllabus", "Syllabus"), ("IP", "IP")]:
            pdf_path = data_dir / subdir / f"{course_code}.pdf"
            if pdf_path.exists():
                print(f"  - Extracting {doc_type} for {course_code}...")
                extracted = extract_chunks_from_pdf(pdf_path, doc_type, course_code)
                all_chunks.extend(extracted)
            else:
                print(f"  - WARNING: Missing {doc_type} for {course_code} at {pdf_path}")
                
    if not all_chunks:
        print("No chunks extracted. Exiting.")
        return
        
    print(f"3. Generating embeddings for {len(all_chunks)} chunks...")
    contents = [c["content"] for c in all_chunks]
    embeddings = embedder.encode(contents, show_progress_bar=True, normalize_embeddings=True)
    
    try:
        # Clear old chunks for these specific courses to avoid duplicates on re-runs
        deleted = session.query(CourseDocumentChunk).filter(
            CourseDocumentChunk.course_code.in_(COURSES_TO_PROCESS)
        ).delete(synchronize_session=False)
        print(f"Cleared {deleted} previous chunks for these courses.")
        session.commit()

        print(f"4. Inserting {len(all_chunks)} new chunks into database...")
        for chunk, emb in zip(all_chunks, embeddings):
            record = CourseDocumentChunk(
                course_code=chunk["course_code"],
                doc_type=chunk["doc_type"],
                page_number=chunk["page_number"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                embedding=emb.tolist()
            )
            session.add(record)
        session.commit()

        print("5. Creating HNSW index for vector similarity search...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_course_doc_chunks_embedding_hnsw 
                ON course_doc_chunks 
                USING hnsw (embedding vector_cosine_ops);
            """))
            conn.commit()

        print("=== INGESTION COMPLETED SUCCESSFULLY! ===")
        total_rows = session.query(CourseDocumentChunk).count()
        print(f"Verified rows in course_doc_chunks table: {total_rows}")

    except Exception as e:
        session.rollback()
        print(f"Ingestion failed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_ingestion()
