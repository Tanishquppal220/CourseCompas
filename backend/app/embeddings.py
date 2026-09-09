"""Central embedding configuration for CourseCompass."""

import os
from functools import lru_cache

import torch
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
BATCH_SIZE = 64


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    """Load the embedding model once and cache it."""
    # Use all CPU cores for the CPU-bound encode step.
    torch.set_num_threads(max(1, os.cpu_count() or 1))
    return SentenceTransformer(MODEL_NAME, trust_remote_code=True)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into normalized 512-dim vectors."""
    embedder = get_embedder()
    embeddings = embedder.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    # Matryoshka dimension selection: keep the first EMBEDDING_DIM components.
    return [emb[:EMBEDDING_DIM].tolist() for emb in embeddings]


def embed_query(query: str) -> list[float]:
    """Embed a single user query into a normalized 512-dim vector."""
    embedder = get_embedder()
    embedding = embedder.encode(
        query,
        normalize_embeddings=True,
    )
    return embedding[:EMBEDDING_DIM].tolist()
