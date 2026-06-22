"""
Embedding service using BGE-M3 via sentence-transformers.
Generates dense vectors for document chunks and queries.
"""

import hashlib
import re

import numpy as np
from sentence_transformers import SentenceTransformer
from structlog import get_logger

from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

_model: SentenceTransformer | None = None
_LOCAL_HASH_MODELS = {"local-hash", "hash", "deterministic"}


def _uses_local_hash_embeddings() -> bool:
    """Return True when the service should use offline deterministic embeddings."""
    return settings.embedding_model.strip().lower() in _LOCAL_HASH_MODELS


def _hash_embedding(text: str) -> list[float]:
    """
    Produce a deterministic local embedding for development/demo use.

    This is intentionally lightweight and offline. Production should use a real
    embedding model such as BAAI/bge-m3.
    """
    dim = settings.embedding_dimension
    vector = np.zeros(dim, dtype=np.float32)
    tokens = re.findall(r"[a-z0-9]+", text.lower())

    if not tokens:
        tokens = [text.strip().lower() or "empty"]

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        index = int.from_bytes(digest[:8], "big") % dim
        sign = 1.0 if digest[8] % 2 == 0 else -1.0
        weight = 1.0 + (len(token) % 7) / 10.0
        vector[index] += sign * weight

    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        vector[0] = 1.0
        return vector.tolist()

    return (vector / norm).tolist()


def _get_model() -> SentenceTransformer:
    """
    Lazy-load the embedding model.

    @returns Loaded SentenceTransformer model
    """
    global _model
    if _model is None:
        logger.info("embedding_model_loading", model=settings.embedding_model)
        _model = SentenceTransformer(
            settings.embedding_model,
            trust_remote_code=True,
        )
        logger.info(
            "embedding_model_loaded",
            model=settings.embedding_model,
            dimension=_model.get_sentence_embedding_dimension(),
        )
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    @param texts: List of text strings to embed
    @returns List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    if _uses_local_hash_embeddings():
        logger.info(
            "embedding_local_hash_batch",
            count=len(texts),
            dimension=settings.embedding_dimension,
        )
        return [_hash_embedding(text) for text in texts]

    model = _get_model()
    batch_size = settings.embedding_batch_size

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings = model.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        if isinstance(embeddings, np.ndarray):
            all_embeddings.extend(embeddings.tolist())
        else:
            all_embeddings.extend([e.tolist() for e in embeddings])

        logger.debug(
            "embedding_batch_complete",
            batch_start=i,
            batch_size=len(batch),
        )

    return all_embeddings


def embed_query(query: str) -> list[float]:
    """
    Generate embedding for a single query.
    Adds 'Represent this sentence for searching relevant passages: '
    prefix for BGE-M3 query encoding.

    @param query: Query text
    @returns Embedding vector
    """
    if _uses_local_hash_embeddings():
        return _hash_embedding(query)

    model = _get_model()
    instruction = "Represent this sentence for searching relevant passages: "
    embedding = model.encode(
        instruction + query,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if isinstance(embedding, np.ndarray):
        return embedding.tolist()
    return list(embedding)
