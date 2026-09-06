from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.embeddings import embed_query
from app.models import BenefitChunk, CourseDocumentChunk

COURSE_DOC_TYPES = (
    "Syllabus",
    "IP",
)


def _source_label(doc_type: str, document_name: Optional[str]) -> str:
    name = document_name or "unknown"
    return f"{doc_type}/{name}"


def _course_search(
    db: Session,
    query_vector: list,
    k: int,
    course_code: Optional[str],
    doc_types: Optional[List[str]],
    chunk_types: Optional[List[str]],
) -> List[Dict[str, Any]]:
    distance = CourseDocumentChunk.embedding.cosine_distance(query_vector)
    q = db.query(
        CourseDocumentChunk,
        (1 - distance).label("score"),
    )

    if course_code:
        q = q.filter(CourseDocumentChunk.course_code == course_code.upper())
    if doc_types:
        q = q.filter(CourseDocumentChunk.doc_type.in_(doc_types))
    if chunk_types:
        q = q.filter(CourseDocumentChunk.chunk_type.in_(chunk_types))

    rows = q.order_by(distance).limit(k).all()

    return [
        {
            "id": chunk.id,
            "source": _source_label(chunk.doc_type, chunk.document_name),
            "course_code": chunk.course_code,
            "document_name": chunk.document_name,
            "doc_type": chunk.doc_type,
            "chunk_type": chunk.chunk_type,
            "section_title": chunk.section_title,
            "content": chunk.content,
            "score": round(float(score), 4),
        }
        for chunk, score in rows
    ]


def _benefit_search(
    db: Session,
    query_vector: list,
    k: int,
) -> List[Dict[str, Any]]:
    distance = BenefitChunk.embedding.cosine_distance(query_vector)
    q = db.query(
        BenefitChunk,
        (1 - distance).label("score"),
    )

    rows = q.order_by(distance).limit(k).all()

    return [
        {
            "id": chunk.id,
            "source": _source_label("Benefits", chunk.document_name),
            "course_code": None,
            "document_name": chunk.document_name,
            "doc_type": "Benefits",
            "chunk_type": chunk.chunk_type,
            "section_title": chunk.section_title,
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
    chunk_types: Optional[List[str]] = None,
    prefer_doc_type: Optional[str] = None,
    prefer_syllabus: bool = False,
) -> List[Dict[str, Any]]:
    query_vector = embed_query(query)

    if source_filter:
        source_results = _course_search(
            db, query_vector, k, course_code, doc_types, chunk_types
        )
        source_results = [r for r in source_results if source_filter in r["source"]]
        return source_results

    if prefer_syllabus:
        prefer_doc_type = "Syllabus"

    if prefer_doc_type is None:
        return _course_search(db, query_vector, k, course_code, doc_types, chunk_types)

    primary_cap = max(1, k - 2)
    preferred = _course_search(db, query_vector, k, course_code, [prefer_doc_type], chunk_types)
    primary = preferred[:primary_cap]
    seen = {r["id"] for r in primary}

    other_types = list(COURSE_DOC_TYPES)
    other_types = [t for t in other_types if t != prefer_doc_type]
    if doc_types:
        other_types = [t for t in other_types if t in doc_types]

    remaining_slots = k - len(primary)
    if remaining_slots > 0 and other_types:
        for r in _course_search(
            db, query_vector, remaining_slots, course_code, other_types, chunk_types
        ):
            if r["id"] not in seen:
                primary.append(r)
                seen.add(r["id"])

    return primary[:k]


def search_benefits(
    db: Session,
    query: str,
    k: int = 5,
    chunk_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    query_vector = embed_query(query)
    results = _benefit_search(db, query_vector, k)
    if chunk_types:
        results = [r for r in results if r["chunk_type"] in chunk_types]
    return results[:k]