import argparse
import re
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal, engine
from app.models import Base, DocumentChunk
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pdfplumber import open as open_pdf
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

DATA_DIR = backend_dir / "data"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
COURSE_CODE_RE = re.compile(r"^([A-Z]{3}\d{3})")

SUPPORTED_EXTENSIONS = {".pdf", ".md"}

FOOTER_RE = re.compile(
    r"An instruction plan is only a tentative plan\..*?instruction plan\.\s*",
    re.DOTALL,
)


def doc_type_from(rel: Path) -> str:
    if str(rel).startswith("Syllabus/"):
        return "Syllabus"
    if str(rel).startswith("IP/"):
        return "IP"
    return "Markdown"


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        with open_pdf(path) as pdf:
            pages = []
            for page in pdf.pages:
                text_content = page.extract_text() or ""
                text_content = FOOTER_RE.sub("", text_content)
                pages.append(text_content)
            return "\n\n".join(pages)
    return path.read_text(encoding="utf-8", errors="replace")


def context_prefix(rel: Path, course_code: str | None) -> str:
    doc_type = doc_type_from(rel)
    if doc_type in {"Syllabus", "IP"} and course_code:
        return f"Course: {course_code} | Document: {doc_type}\n"
    return ""


def iter_source_files():
    for sub in sorted(DATA_DIR.rglob("*")):
        if sub.is_file() and sub.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield sub, sub.relative_to(DATA_DIR)


def run_ingestion(rebuild: bool = False):
    documents = []
    for path, rel in iter_source_files():
        text_content = extract_text(path)
        if not text_content.strip():
            print(f"  skipped empty: {rel}")
            continue
        documents.append(
            {
                "source": str(rel),
                "course_code": course_code_from(rel.name),
                "doc_type": doc_type_from(rel),
                "prefix": context_prefix(rel, course_code_from(rel.name)),
                "text": text_content,
            }
        )

    print(f"Loaded {len(documents)} documents")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    for doc in documents:
        for piece in splitter.split_text(doc["text"]):
            chunks.append(
                {
                    "source": doc["source"],
                    "course_code": doc["course_code"],
                    "doc_type": doc["doc_type"],
                    "content": doc["prefix"] + piece,
                }
            )

    print(f"Split into {len(chunks)} chunks")

    embedder = SentenceTransformer(MODEL_NAME)
    embeddings = embedder.encode(
        [c["content"] for c in chunks],
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        if rebuild:
            conn.execute(text("DROP TABLE IF EXISTS document_chunks CASCADE;"))
        conn.commit()

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        if rebuild:
            deleted = session.query(DocumentChunk).delete()
            print(f"Cleared {deleted} previous chunks")
            session.commit()

        for chunk, emb in zip(chunks, embeddings):
            session.add(
                DocumentChunk(
                    source=chunk["source"],
                    course_code=chunk["course_code"],
                    doc_type=chunk["doc_type"],
                    content=chunk["content"],
                    embedding=emb.tolist(),
                )
            )
        session.commit()

        with engine.connect() as conn:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw "
                    "ON document_chunks USING hnsw (embedding vector_cosine_ops);"
                )
            )
            conn.commit()

        total = session.query(DocumentChunk).count()
        print(f"=== INGESTION COMPLETED: {total} chunks ===")


def course_code_from(filename: str) -> str | None:
    match = COURSE_CODE_RE.match(filename)
    return match.group(1) if match else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Embed all files in backend/data")
    parser.add_argument("--rebuild", action="store_true", help="Clear existing chunks first")
    args = parser.parse_args()
    run_ingestion(rebuild=args.rebuild)