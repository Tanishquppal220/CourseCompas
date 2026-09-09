"""Central reranker configuration for CourseCompass using BGE-Reranker."""

import logging
import os
from functools import lru_cache
from typing import Any

import torch
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

RERANKER_MODEL = "BAAI/bge-reranker-base"


@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    """Load and cache the BGE CrossEncoder reranker model."""
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    return CrossEncoder(RERANKER_MODEL)


def rerank_documents(
    query: str,
    documents: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rerank candidate documents based on cross-encoder query-passage relevance score."""
    if not documents:
        return []

    if len(documents) <= 1:
        return documents[:top_k]

    try:
        reranker = get_reranker()
        pairs = [[query, doc.get("content", "")] for doc in documents]
        scores = reranker.predict(pairs)

        for doc, score in zip(documents, scores, strict=False):
            doc["rerank_score"] = round(float(score), 4)

        ranked = sorted(
            documents, key=lambda x: x.get("rerank_score", 0.0), reverse=True
        )
        return ranked[:top_k]
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"Reranking failed ({e}), falling back to initial ranking order."
        )
        return documents[:top_k]
