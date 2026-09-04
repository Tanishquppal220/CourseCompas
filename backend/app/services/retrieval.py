from typing import List, Optional, Dict, Any
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from sqlalchemy import text
try:
    from app.models import BenefitChunk
except ImportError:
    from backend.app.models import BenefitChunk


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)

def search_benefits(
    db: Session,
    query: str,
    limit: int = 5,
    section_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Perform semantic vector similarity search against benefit_chunks using cosine distance (<=>).
    """
    embedder = get_embedder()
    # Generate query embedding and normalize
    query_vector = embedder.encode(query, normalize_embeddings=True).tolist()
    
    # Base query calculating cosine similarity (1 - cosine distance)
    # Cosine distance operator in pgvector is <=>
    distance_expr = BenefitChunk.embedding.cosine_distance(query_vector)
    
    q = db.query(
        BenefitChunk,
        (1 - distance_expr).label("similarity_score")
    )
    
    if section_filter:
        q = q.filter(BenefitChunk.section_title.ilike(f"%{section_filter}%"))
        
    results = q.order_by(distance_expr).limit(limit).all()
    
    formatted_results = []
    for chunk, similarity in results:
        formatted_results.append({
            "id": chunk.id,
            "document_name": chunk.document_name,
            "section_title": chunk.section_title,
            "page_number": chunk.page_number,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "metadata": chunk.chunk_metadata,
            "similarity_score": round(float(similarity), 4)
        })
        
    return formatted_results


def search_course_docs(
    db: Session,
    query: str,
    course_code: Optional[str] = None,
    limit: int = 4
) -> List[Dict[str, Any]]:
    """
    Perform semantic vector similarity search against course_doc_chunks.
    """
    # Import locally to avoid circular imports if any
    try:
        from app.models import CourseDocumentChunk
    except ImportError:
        from backend.app.models import CourseDocumentChunk

    embedder = get_embedder()
    query_vector = embedder.encode(query, normalize_embeddings=True).tolist()
    
    distance_expr = CourseDocumentChunk.embedding.cosine_distance(query_vector)
    
    q = db.query(
        CourseDocumentChunk,
        (1 - distance_expr).label("similarity_score")
    )
    
    if course_code:
        q = q.filter(CourseDocumentChunk.course_code.ilike(f"%{course_code}%"))
        
    results = q.order_by(distance_expr).limit(limit).all()
    
    formatted_results = []
    for chunk, similarity in results:
        formatted_results.append({
            "id": chunk.id,
            "course_code": chunk.course_code,
            "doc_type": chunk.doc_type,
            "page_number": chunk.page_number,
            "content": chunk.content,
            "similarity_score": round(float(similarity), 4)
        })
        
    return formatted_results


def search_schema(
    db: Session,
    query: str,
    limit: int = 5,
    section_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Perform semantic vector similarity search against schema_chunks using cosine distance.
    """
    try:
        from app.models import SchemaChunk
    except ImportError:
        from backend.app.models import SchemaChunk

    embedder = get_embedder()
    query_vector = embedder.encode(query, normalize_embeddings=True).tolist()
    
    distance_expr = SchemaChunk.embedding.cosine_distance(query_vector)
    
    q = db.query(
        SchemaChunk,
        (1 - distance_expr).label("similarity_score")
    )
    
    if section_filter:
        q = q.filter(SchemaChunk.section_title.ilike(f"%{section_filter}%"))
        
    results = q.order_by(distance_expr).limit(limit).all()
    
    formatted_results = []
    for chunk, similarity in results:
        formatted_results.append({
            "id": chunk.id,
            "document_name": chunk.document_name,
            "section_title": chunk.section_title,
            "chunk_type": chunk.chunk_type,
            "content": chunk.content,
            "metadata": chunk.chunk_metadata,
            "similarity_score": round(float(similarity), 4)
        })
        
    return formatted_results
