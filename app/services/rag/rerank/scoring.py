"""Scoring functions for reranking."""

import logging
from typing import Any

import numpy as np
from scipy.spatial.distance import cosine

from app.services.rag.rerank.config import DOC_QUALITY_PARAMS

logger = logging.getLogger(__name__)


class DocumentScorer:
    """Calculate various document scores for reranking."""

    def __init__(self):
        self.quality_params = DOC_QUALITY_PARAMS

    def calculate_vector_similarity(
        self,
        doc_embedding: list[float],
        query_embedding: list[float],
    ) -> float:
        """
        Calculate vector similarity between document and query.

        Args:
            doc_embedding: Document embedding vector
            query_embedding: Query embedding vector

        Returns:
            Cosine similarity score (0-1)
        """
        try:
            if not doc_embedding or not query_embedding:
                return 0.0

            doc_vec = np.array(doc_embedding)
            query_vec = np.array(query_embedding)

            if np.all(doc_vec == 0) or np.all(query_vec == 0):
                return 0.0

            similarity = 1 - cosine(doc_vec, query_vec)
            return max(0.0, min(1.0, similarity))

        except Exception as e:
            logger.error(f"Vector similarity calculation error: {e}")
            return 0.0

    def calculate_document_quality(self, doc: dict[str, Any]) -> float:
        """
        Calculate document quality score.

        Args:
            doc: Document dict with content and metadata

        Returns:
            Quality score (0-1)
        """
        try:
            # Length score
            content_length = len(doc.get("content", ""))
            length_score = self._calculate_length_score(content_length)

            # Structure score (headings, paragraphs, etc.)
            structure_score = self._calculate_structure_score(doc)

            # Freshness score
            freshness_score = doc.get("freshness_score", 0.5)

            # Weighted average
            quality_score = (
                length_score * 0.4 + structure_score * 0.3 + freshness_score * 0.3
            )

            return quality_score

        except Exception as e:
            logger.error(f"Document quality calculation error: {e}")
            return 0.5

    def _calculate_length_score(self, length: int) -> float:
        """Calculate score based on document length."""
        try:
            if length < self.quality_params["min_length"]:
                return length / self.quality_params["min_length"]
            elif length <= self.quality_params["optimal_length"]:
                return 1.0
            else:
                decay = max(
                    0,
                    1
                    - (length - self.quality_params["optimal_length"])
                    / (
                        self.quality_params["max_length"]
                        - self.quality_params["optimal_length"]
                    ),
                )
                return max(0.5, decay)

        except Exception as e:
            logger.error(f"Length score calculation error: {e}")
            return 0.5

    def _calculate_structure_score(self, doc: dict[str, Any]) -> float:
        """Calculate score based on document structure."""
        try:
            structure_elements = {
                "has_title": 0.3,
                "has_headers": 0.3,
                "has_paragraphs": 0.2,
                "has_lists": 0.1,
                "has_code_blocks": 0.1,
            }

            score = 0.0
            content = doc.get("content", "")

            if doc.get("title") or doc.get("metadata", {}).get("title"):
                score += structure_elements["has_title"]
            if "##" in content or "#" in content:
                score += structure_elements["has_headers"]
            if "\n\n" in content:
                score += structure_elements["has_paragraphs"]
            if "- " in content or "* " in content:
                score += structure_elements["has_lists"]
            if "```" in content:
                score += structure_elements["has_code_blocks"]

            return score

        except Exception as e:
            logger.error(f"Structure score calculation error: {e}")
            return 0.5

    def calculate_freshness_score(
        self,
        doc: dict[str, Any],
        max_age_days: int = 365,
    ) -> float:
        """
        Calculate document freshness score.

        Args:
            doc: Document with created_at metadata
            max_age_days: Maximum age in days for scoring

        Returns:
            Freshness score (0-1)
        """
        try:
            from datetime import datetime, timezone

            metadata = doc.get("metadata", {})
            created_at = metadata.get("created_at") or metadata.get("reg_date")

            if not created_at:
                return 0.5

            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

            now = datetime.now(timezone.utc)
            age_days = (now - created_at).days

            if age_days <= 0:
                return 1.0
            elif age_days >= max_age_days:
                return 0.1

            return 1.0 - (age_days / max_age_days) * 0.9

        except Exception as e:
            logger.error(f"Freshness score calculation error: {e}")
            return 0.5

    def calculate_relevance_score(
        self,
        doc: dict[str, Any],
        query: str,
        query_embedding: list[float],
    ) -> float:
        """
        Calculate combined relevance score.

        Args:
            doc: Document with content and embeddings
            query: Search query
            query_embedding: Query embedding vector

        Returns:
            Relevance score (0-1)
        """
        try:
            # Vector similarity
            doc_embedding = doc.get("vector", doc.get("embedding", []))
            vector_score = self.calculate_vector_similarity(doc_embedding, query_embedding)

            # Keyword matching
            content = doc.get("content", "").lower()
            query_words = set(query.lower().split())
            matching_words = sum(1 for word in query_words if word in content)
            keyword_score = min(1.0, matching_words / max(len(query_words), 1))

            # Combined score
            return vector_score * 0.7 + keyword_score * 0.3

        except Exception as e:
            logger.error(f"Relevance score calculation error: {e}")
            return 0.0
