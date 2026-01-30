"""Core reranking implementation."""

import logging
import time
from typing import Any, Optional

import numpy as np

from app.services.rag.rerank.config import (
    DEFAULT_WEIGHTS,
    FINAL_SCORE_WEIGHTS,
    QUERY_TYPE_WEIGHTS,
)
from app.services.rag.rerank.scoring import DocumentScorer
from app.services.rag.rerank.normalizer import ScoreNormalizer
from app.services.rag.rerank.utils import detect_query_type, log_reranking_stats
from app.services.rag.rerank.metrics import RerankingMetrics
from app.services.rag.rerank.analyzer import SearchBehaviorAnalyzer

logger = logging.getLogger(__name__)


class EnhancedReRanker:
    """
    Enhanced reranking system for RAG search results.

    Features:
    - Multi-factor scoring (vector, text, quality, freshness)
    - Query type detection and weight adjustment
    - Search behavior analysis
    - Performance metrics tracking
    """

    def __init__(self):
        self.scorer = DocumentScorer()
        self.normalizer = ScoreNormalizer()
        self.weights = DEFAULT_WEIGHTS.copy()
        self.metrics = RerankingMetrics()
        self.analyzer = SearchBehaviorAnalyzer()

    def rerank_search_results(
        self,
        search_results: list[dict[str, Any]],
        query_embedding: list[float],
        query_type: Optional[str] = None,
        search_params: Optional[dict[str, Any]] = None,
        search_behavior: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Rerank search results with enhanced scoring.

        Args:
            search_results: List of search results from Elasticsearch
            query_embedding: Query embedding vector
            query_type: Type of query (technical, conceptual, default)
            search_params: Optional search parameters
            search_behavior: Optional search behavior data

        Returns:
            Reranked list of search results
        """
        try:
            if not search_results or not query_embedding:
                logger.warning("Empty search results or query embedding")
                return search_results

            # Adjust weights based on query type
            self._adjust_weights(query_type)

            # Apply search params
            if search_params:
                self._apply_search_params(search_params)

            # Adjust weights based on search behavior
            if search_behavior:
                self._adjust_weights_by_behavior(search_behavior)

            scored_results = []
            bm25_scores = [doc.get("_score", doc.get("score", 0)) for doc in search_results]

            for doc in search_results:
                try:
                    # Calculate base scores
                    scores = self._calculate_base_scores(doc, query_embedding, bm25_scores)

                    # Calculate quality score
                    quality_score = self.scorer.calculate_document_quality(doc)

                    # Calculate freshness score
                    freshness_score = self.scorer.calculate_freshness_score(doc)

                    # Calculate final score
                    final_score = self._calculate_final_score(
                        scores,
                        quality_score,
                        freshness_score,
                        search_params,
                    )

                    scored_doc = {
                        **doc,
                        "final_score": final_score,
                        "component_scores": {
                            **scores,
                            "quality_score": quality_score,
                            "freshness_score": freshness_score,
                        },
                    }
                    scored_results.append(scored_doc)

                except Exception as e:
                    logger.error(f"Error processing document: {e}")
                    continue

            # Sort by final score
            ranked_results = sorted(
                scored_results,
                key=lambda x: x.get("final_score", 0),
                reverse=True,
            )

            # Log statistics
            log_reranking_stats(ranked_results)

            return ranked_results

        except Exception as e:
            logger.error(f"Reranking error: {e}")
            return search_results

    async def rerank(
        self,
        query: str,
        search_results: list[dict[str, Any]],
        query_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Async reranking with score calculation.

        Args:
            query: Search query
            search_results: List of search results
            query_type: Optional query type
            top_k: Number of results to return

        Returns:
            Reranked and filtered results
        """
        try:
            start_time = time.time()

            if not search_results:
                return []

            # Detect query type if not provided
            if not query_type:
                query_type = detect_query_type(query)

            # Calculate scores for each result
            scored_results = []
            for result in search_results:
                scores = await self.metrics.calculate_scores(
                    query=query,
                    document=result,
                    query_type=query_type,
                )

                result["rerank_scores"] = scores
                result["final_score"] = self.calculate_final_score_from_metrics(scores)
                scored_results.append(result)

            # Sort by final score
            scored_results = sorted(
                scored_results,
                key=lambda x: x["final_score"],
                reverse=True,
            )

            # Add metadata
            for result in scored_results[:top_k]:
                result["rerank_metadata"] = {
                    "query_type": query_type,
                    "rerank_time": time.time() - start_time,
                }

            logger.info(
                f"Reranking completed in {time.time() - start_time:.3f}s, "
                f"returned {min(top_k, len(scored_results))} results"
            )

            return scored_results[:top_k]

        except Exception as e:
            logger.error(f"Reranking error: {str(e)}")
            return search_results[:top_k] if search_results else []

    def _adjust_weights(self, query_type: Optional[str]) -> None:
        """Adjust weights based on query type."""
        if query_type and query_type in QUERY_TYPE_WEIGHTS:
            self.weights.update(QUERY_TYPE_WEIGHTS[query_type])

    def _apply_search_params(self, search_params: dict[str, Any]) -> None:
        """Apply search parameters to weights."""
        if "similarity_threshold" in search_params:
            self.weights["vector_weight"] *= search_params["similarity_threshold"]
        if "context_weight" in search_params:
            self.weights["context_weight"] = search_params["context_weight"]
        if "time_weight" in search_params:
            self.weights["freshness_weight"] = search_params["time_weight"]
        if "reference_weight" in search_params:
            self.weights["reference_weight"] = search_params["reference_weight"]

    def _adjust_weights_by_behavior(self, search_behavior: dict[str, Any]) -> None:
        """Adjust weights based on search behavior."""
        adjustments = self.analyzer.get_weight_adjustments(search_behavior)
        for key, multiplier in adjustments.items():
            if key in self.weights:
                self.weights[key] *= multiplier

    def _calculate_base_scores(
        self,
        doc: dict[str, Any],
        query_embedding: list[float],
        bm25_scores: list[float],
    ) -> dict[str, float]:
        """Calculate base scores for a document."""
        # Normalize BM25 score
        doc_score = doc.get("_score", doc.get("score", 0))
        bm25_score = self.normalizer.normalize_score(
            doc_score,
            min(bm25_scores) if bm25_scores else 0,
            max(bm25_scores) if bm25_scores else 1,
        )

        # Calculate vector similarity
        doc_vector = doc.get("vector", doc.get("embedding", []))
        vector_score = self.scorer.calculate_vector_similarity(
            doc_vector,
            query_embedding,
        )

        return {
            "bm25_score": bm25_score,
            "vector_score": vector_score,
        }

    def _calculate_final_score(
        self,
        scores: dict[str, float],
        quality_score: float,
        freshness_score: float,
        search_params: Optional[dict[str, Any]] = None,
    ) -> float:
        """Calculate final combined score."""
        try:
            # Combine scores with weights
            final_score = (
                scores.get("bm25_score", 0) * self.weights.get("text_weight", 0.4)
                + scores.get("vector_score", 0) * self.weights.get("vector_weight", 0.6)
                + quality_score * self.weights.get("quality_weight", 0.2)
                + freshness_score * self.weights.get("freshness_weight", 0.1)
            )

            # Normalize to 0-1 range
            return min(1.0, max(0.0, final_score))

        except Exception as e:
            logger.error(f"Final score calculation error: {e}")
            return 0.0

    def calculate_final_score_from_metrics(
        self,
        scores: dict[str, float],
    ) -> float:
        """Calculate final score from metric scores."""
        try:
            final_score = sum(
                scores.get(metric, 0) * weight
                for metric, weight in FINAL_SCORE_WEIGHTS.items()
            )
            return final_score

        except Exception as e:
            logger.error(f"Final score calculation error: {e}")
            return 0.0

    async def analyze_performance(
        self,
        query: str,
        selected_results: list[dict[str, Any]],
        response_time: float,
    ) -> dict[str, Any]:
        """
        Analyze reranking performance.

        Args:
            query: Search query
            selected_results: Selected results after reranking
            response_time: Total response time

        Returns:
            Performance metrics dictionary
        """
        try:
            performance_metrics = {
                "query_type": detect_query_type(query),
                "result_count": len(selected_results),
                "response_time": response_time,
                "avg_relevance": np.mean(
                    [
                        r.get("rerank_scores", {}).get("relevance", 0)
                        for r in selected_results
                    ]
                )
                if selected_results
                else 0,
            }

            return performance_metrics

        except Exception as e:
            logger.error(f"Performance analysis error: {str(e)}")
            return {}
