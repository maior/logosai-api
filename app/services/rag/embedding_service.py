"""Embedding service for RAG system."""

import logging
from functools import lru_cache
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid loading at startup
_embeddings = None


def _get_embeddings():
    """Lazily load HuggingFace embeddings model."""
    global _embeddings
    if _embeddings is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        logger.info(f"Loading embedding model: {settings.embedding_model_name}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model_name,
            model_kwargs={"device": settings.embedding_device},
            encode_kwargs={"normalize_embeddings": False},
        )
        logger.info("Embedding model loaded successfully")
    return _embeddings


class EmbeddingService:
    """
    Singleton service for text embedding generation.

    Uses HuggingFace embeddings (jhgan/ko-sroberta-nli by default).
    Optimized for Korean text.
    """

    _instance: Optional["EmbeddingService"] = None

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._model = None
        self._initialized = True

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            self._model = _get_embeddings()
        return self._model

    def encode(self, text: str) -> list[float]:
        """
        Encode a single text into embedding vector.

        Args:
            text: Input text to encode

        Returns:
            Embedding vector as list of floats
        """
        try:
            return self.model.embed_query(text)
        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            raise

    def encode_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Encode multiple texts into embedding vectors.

        Args:
            texts: List of texts to encode

        Returns:
            List of embedding vectors
        """
        try:
            return self.model.embed_documents(texts)
        except Exception as e:
            logger.error(f"Documents encoding failed: {e}")
            raise

    def cosine_similarity(
        self,
        embedding1: list[float] | np.ndarray,
        embedding2: list[float] | np.ndarray,
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (0-1)
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


@lru_cache
def get_embedding_service() -> EmbeddingService:
    """Get cached embedding service instance."""
    return EmbeddingService()
