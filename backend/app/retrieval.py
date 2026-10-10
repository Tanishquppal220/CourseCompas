import re
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.embeddings import embed_query
from app.models import BenefitChunk, CourseDocumentChunk
from app.reranker import rerank_documents

COURSE_DOC_TYPES = (
    "Syllabus",
    "IP",
)

# Calibrated hybrid multiplier (FTS cover density weight relative to cosine similarity base)
HYBRID_ALPHA = 1.2

FTS_STOP_PATTERNS = [
    r"\b(what\s+is|what\s+are|what\s+topics\s+are\s+covered\s+in|topics\s+covered\s+in|what\s+topics\s+are)\b",
    r"\b(can\s+you\s+show\s+me|show\s+me\s+the|tell\s+me\s+about|can\s+you\s+tell\s+me)\b",
    r"\b(how\s+does|how\s+can|how\s+do\s+i|what\s+happens\s+if\s+i|can\s+an)\b",
    r"\b(difference\s+between|list\s+of|breakdown\s+of|overview\s+of)\b",
    r"\b(topics|covered|syllabus|details|guidelines|requirement|requirements)\b",
]


def clean_query_for_fts(query: str) -> tuple[str, str | None]:
    """Distills conversational natural language queries into content keywords for FTS."""
    text_clean = query

    # Extract course code (e.g. CSE205, INT108)
    course_match = re.search(r"\b([A-Za-z]{3}\d{3})\b", text_clean)
    extracted_code = course_match.group(1).upper() if course_match else None

    # Remove conversational filler patterns
    for pat in FTS_STOP_PATTERNS:
        text_clean = re.sub(pat, " ", text_clean, flags=re.IGNORECASE)

    # Clean punctuation
    text_clean = re.sub(r"[?!.,;:\"'(){}\[\]]", " ", text_clean)

    tokens = [
        t
        for t in text_clean.split()
        if len(t) > 1
        and t.lower()
        not in {
            "the",
            "in",
            "and",
            "or",
            "to",
            "for",
            "of",
            "on",
            "at",
            "by",
            "an",
            "is",
            "if",
            "my",
        }
    ]

    cleaned_query = " ".join(tokens)
    return (cleaned_query if cleaned_query else query), extracted_code


def _source_label(doc_type: str, document_name: str | None) -> str:
    name = document_name or "unknown"
    return f"{doc_type}/{name}"


def _course_search(
    db: Session,
    query_text: str,
    query_vector: list,
    k: int,
    course_code: str | None,
    doc_types: list[str] | None,
    chunk_types: list[str] | None,
) -> list[dict[str, Any]]:
    # 1. Distill natural language into content keywords for FTS and detect course codes
    cleaned_text, detected_code = clean_query_for_fts(query_text)
    effective_code = course_code or detected_code

    tsquery = func.websearch_to_tsquery("english", cleaned_text)

    # 2. Vector distance
    distance = CourseDocumentChunk.embedding.cosine_distance(query_vector)

    # 3. Hybrid scoring: normalized cosine similarity + calibrated cover-density rank
    hybrid_score = (1.0 - distance) + (
        func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery), 0.0)
        * HYBRID_ALPHA
    )

    q = db.query(
        CourseDocumentChunk,
        hybrid_score.label("score"),
    )

    if effective_code:
        q = q.filter(CourseDocumentChunk.course_code == effective_code.upper())
    if doc_types:
        q = q.filter(CourseDocumentChunk.doc_type.in_(doc_types))
    if chunk_types:
        q = q.filter(CourseDocumentChunk.chunk_type.in_(chunk_types))

    # Also require that it matches EITHER semantically (distance < 0.6) OR keyword matches
    # This prevents returning entirely irrelevant results just to fill 'k'
    q = q.filter(or_(distance < 0.6, CourseDocumentChunk.fts.op("@@")(tsquery)))

    rows = q.order_by(hybrid_score.desc()).limit(k).all()

    # Fallback: if effective_code filter was inferred (not explicitly requested) and gave 0 results,
    # re-run without the code constraint to prevent empty candidate lists
    if not rows and detected_code and not course_code:
        q_relaxed = db.query(
            CourseDocumentChunk,
            hybrid_score.label("score"),
        )
        if doc_types:
            q_relaxed = q_relaxed.filter(CourseDocumentChunk.doc_type.in_(doc_types))
        if chunk_types:
            q_relaxed = q_relaxed.filter(
                CourseDocumentChunk.chunk_type.in_(chunk_types)
            )
        q_relaxed = q_relaxed.filter(
            or_(distance < 0.6, CourseDocumentChunk.fts.op("@@")(tsquery))
        )
        rows = q_relaxed.order_by(hybrid_score.desc()).limit(k).all()

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
    query_text: str,
    query_vector: list,
    k: int,
) -> list[dict[str, Any]]:
    cleaned_text, _ = clean_query_for_fts(query_text)
    tsquery = func.websearch_to_tsquery("english", cleaned_text)
    distance = BenefitChunk.embedding.cosine_distance(query_vector)

    hybrid_score = (1.0 - distance) + (
        func.coalesce(func.ts_rank_cd(BenefitChunk.fts, tsquery), 0.0) * HYBRID_ALPHA
    )

    q = db.query(
        BenefitChunk,
        hybrid_score.label("score"),
    )

    q = q.filter(or_(distance < 0.6, BenefitChunk.fts.op("@@")(tsquery)))
    rows = q.order_by(hybrid_score.desc()).limit(k).all()

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
    course_code: str | None = None,
    source_filter: str | None = None,
    doc_types: list[str] | None = None,
    chunk_types: list[str] | None = None,
    prefer_doc_type: str | None = None,
    prefer_syllabus: bool = False,
    rerank: bool = True,
) -> list[dict[str, Any]]:
    query_vector = embed_query(query)
    candidate_k = max(8, k * 2) if rerank else k

    if source_filter:
        source_results = _course_search(
            db, query, query_vector, candidate_k, course_code, doc_types, chunk_types
        )
        source_results = [r for r in source_results if source_filter in r["source"]]
        if rerank and len(source_results) > 1:
            return rerank_documents(query, source_results, top_k=k)
        return source_results[:k]

    if prefer_syllabus:
        prefer_doc_type = "Syllabus"

    if prefer_doc_type is None:
        candidates = _course_search(
            db, query, query_vector, candidate_k, course_code, doc_types, chunk_types
        )
        if rerank and len(candidates) > 1:
            return rerank_documents(query, candidates, top_k=k)
        return candidates[:k]

    primary_cap = max(1, candidate_k - 4)
    preferred = _course_search(
        db,
        query,
        query_vector,
        candidate_k,
        course_code,
        [prefer_doc_type],
        chunk_types,
    )
    primary = preferred[:primary_cap]
    seen = {r["id"] for r in primary}

    other_types = list(COURSE_DOC_TYPES)
    other_types = [t for t in other_types if t != prefer_doc_type]
    if doc_types:
        other_types = [t for t in other_types if t in doc_types]

    remaining_slots = candidate_k - len(primary)
    if remaining_slots > 0 and other_types:
        for r in _course_search(
            db,
            query,
            query_vector,
            remaining_slots,
            course_code,
            other_types,
            chunk_types,
        ):
            if r["id"] not in seen:
                primary.append(r)
                seen.add(r["id"])

    candidates = primary[:candidate_k]
    if rerank and len(candidates) > 1:
        return rerank_documents(query, candidates, top_k=k)
    return candidates[:k]


def search_benefits(
    db: Session,
    query: str,
    k: int = 5,
    chunk_types: list[str] | None = None,
    rerank: bool = True,
) -> list[dict[str, Any]]:
    query_vector = embed_query(query)
    candidate_k = max(8, k * 2) if rerank else k
    results = _benefit_search(db, query, query_vector, candidate_k)
    if chunk_types:
        results = [r for r in results if r["chunk_type"] in chunk_types]
    if rerank and len(results) > 1:
        return rerank_documents(query, results, top_k=k)
    return results[:k]
