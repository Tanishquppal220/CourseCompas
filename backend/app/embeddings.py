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
    embedder = SentenceTransformer(MODEL_NAME, trust_remote_code=True)

    # The stored vector columns are sized for EMBEDDING_DIM, so the model must
    # produce exactly that many dimensions. Fail loudly instead of silently
    # writing vectors the database cannot store.
    model_dim = embedder.get_sentence_embedding_dimension()
    if model_dim != EMBEDDING_DIM:
        raise ValueError(
            f"{MODEL_NAME} emits {model_dim}-dim vectors but EMBEDDING_DIM="
            f"{EMBEDDING_DIM}. Update EMBEDDING_DIM (and the DB schema) to match."
        )

    return embedder


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into normalized ``EMBEDDING_DIM`` vectors."""
    embedder = get_embedder()
    embeddings = embedder.encode(
        texts,
        batch_size=BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """Embed a single user query into a normalized ``EMBEDDING_DIM`` vector."""
    embedder = get_embedder()
    embedding = embedder.encode(
        query,
        normalize_embeddings=True,
    )
    return embedding.tolist()
