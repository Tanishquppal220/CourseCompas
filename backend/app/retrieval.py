from functools import lru_cache
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from app.models import DocumentChunk

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def _search(
    db: Session,
    query_vector: list,
    k: int,
    course_code: Optional[str],
    doc_types: Optional[List[str]],
) -> List[Dict[str, Any]]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    q = db.query(
        DocumentChunk,
        (1 - distance).label("score"),
    )

    if course_code:
        q = q.filter(DocumentChunk.course_code == course_code.upper())
    if doc_types:
        q = q.filter(DocumentChunk.doc_type.in_(doc_types))

    rows = q.order_by(distance).limit(k).all()

    return [
        {
            "id": chunk.id,
            "source": chunk.source,
            "course_code": chunk.course_code,
            "doc_type": chunk.doc_type,
            "content": chunk.content,
            "score": round(float(score), 4),
        }
        for chunk, score in rows
    ]


def search_documents(
    db: Session,
    query: str,
    k: int = 5,
    course_code: Optional[str] = None,
    source_filter: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    prefer_syllabus: bool = False,
) -> List[Dict[str, Any]]:
    query_vector = get_embedder().encode(query, normalize_embeddings=True).tolist()

    if source_filter:
        source_results = _search(db, query_vector, k, course_code, doc_types)
        source_results = [r for r in source_results if source_filter in r["source"]]
        return source_results

    if not prefer_syllabus:
        return _search(db, query_vector, k, course_code, doc_types)

    syllabus_rows = _search(db, query_vector, k, course_code, ["Syllabus"])
    seen = {r["id"] for r in syllabus_rows}

    remaining_slots = k - len(syllabus_rows)
    if remaining_slots > 0:
        other_types = ["IP"] if doc_types is None else [
            t for t in doc_types if t != "Syllabus"
        ]
        if other_types:
            for r in _search(
                db, query_vector, remaining_slots, course_code, other_types
            ):
                if r["id"] not in seen:
                    syllabus_rows.append(r)
                    seen.add(r["id"])

    return syllabus_rows[:k]