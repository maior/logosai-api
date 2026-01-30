"""RAG (Retrieval-Augmented Generation) service.

Enhanced with reranking and image processing support.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from app.config import settings
from app.services.rag.document_processor import DocumentProcessor
from app.services.rag.elasticsearch_client import ElasticsearchClient, get_elasticsearch_client
from app.services.rag.embedding_service import EmbeddingService, get_embedding_service
from app.services.rag.rerank import EnhancedReRanker, detect_query_type

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Search result with content and metadata."""

    content: str
    metadata: dict[str, Any]
    score: float
    chunk_id: str


@dataclass
class SearchEvaluation:
    """Evaluation metrics for search results."""

    result_quality: float
    context_relevance: float
    clarity_score: float
    diversity_score: float
    coverage_score: float


class RAGService:
    """
    Main RAG service combining embedding, indexing, and search.

    Features:
    - Document processing and indexing
    - Hybrid search (keyword + vector)
    - Enhanced reranking with multi-factor scoring
    - Image processing and search
    - Result evaluation and ranking
    """

    def __init__(
        self,
        es_client: Optional[ElasticsearchClient] = None,
        embedding_service: Optional[EmbeddingService] = None,
        enable_reranking: bool = True,
    ):
        self.es_client = es_client or get_elasticsearch_client()
        self.embedding_service = embedding_service or get_embedding_service()
        self.document_processor = DocumentProcessor()
        self.enable_reranking = enable_reranking

        # Initialize reranker
        self._reranker: Optional[EnhancedReRanker] = None

        # Search parameters
        self.relevance_threshold = 0.75
        self.min_diversity_score = 0.3
        self.max_results = 10

    @property
    def reranker(self) -> EnhancedReRanker:
        """Get reranker (lazy initialization)."""
        if self._reranker is None:
            self._reranker = EnhancedReRanker()
        return self._reranker

    async def index_document(
        self,
        file_path: str,
        file_name: str,
        user_id: str,
        document_id: str,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process and index a document for RAG.

        Args:
            file_path: Path to the file
            file_name: Original file name
            user_id: Owner user ID
            document_id: Document ID in database
            project_id: Optional project ID

        Returns:
            Indexing statistics
        """
        # Process document into chunks
        chunks = await self.document_processor.process_file(
            file_path=file_path,
            file_name=file_name,
            user_id=user_id,
            document_id=document_id,
            project_id=project_id,
        )

        # Index to Elasticsearch
        indexed_count = await self.es_client.index_documents(
            documents=chunks,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
        )

        # Get chunk statistics
        stats = self.document_processor.get_chunk_stats(chunks)
        stats["indexed_count"] = indexed_count

        logger.info(f"Indexed document {document_id}: {indexed_count} chunks")
        return stats

    async def index_document_content(
        self,
        content: bytes,
        file_name: str,
        user_id: str,
        document_id: str,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Process and index document from content bytes.

        Args:
            content: File content as bytes
            file_name: Original file name
            user_id: Owner user ID
            document_id: Document ID
            project_id: Optional project ID

        Returns:
            Indexing statistics
        """
        # Process document into chunks
        chunks = await self.document_processor.process_file_content(
            content=content,
            file_name=file_name,
            user_id=user_id,
            document_id=document_id,
            project_id=project_id,
        )

        # Index to Elasticsearch
        indexed_count = await self.es_client.index_documents(
            documents=chunks,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
        )

        stats = self.document_processor.get_chunk_stats(chunks)
        stats["indexed_count"] = indexed_count

        return stats

    async def search(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
        use_reranking: Optional[bool] = None,
    ) -> list[SearchResult]:
        """
        Search for relevant documents with optional reranking.

        Args:
            query: Search query
            user_id: User ID for access control
            project_id: Optional project ID filter
            document_ids: Optional document IDs filter
            top_k: Number of results
            min_score: Minimum relevance score
            use_reranking: Override reranking setting

        Returns:
            List of search results
        """
        # Fetch more results for reranking
        fetch_k = top_k * 3 if (use_reranking or self.enable_reranking) else top_k

        results = await self.es_client.hybrid_search(
            query=query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=fetch_k,
            min_score=min_score,
        )

        # Apply reranking if enabled
        should_rerank = use_reranking if use_reranking is not None else self.enable_reranking
        if should_rerank and results:
            results = await self._apply_reranking(query, results, top_k)
        else:
            results = results[:top_k]

        return [
            SearchResult(
                content=r["content"],
                metadata=r["metadata"],
                score=r.get("final_score", r["score"]),
                chunk_id=r["chunk_id"],
            )
            for r in results
        ]

    async def _apply_reranking(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """
        Apply enhanced reranking to search results.

        Args:
            query: Search query
            results: Raw search results
            top_k: Number of final results

        Returns:
            Reranked results
        """
        try:
            # Detect query type
            query_type = detect_query_type(query)

            # Apply reranking
            reranked = await self.reranker.rerank(
                query=query,
                search_results=results,
                query_type=query_type,
                top_k=top_k,
            )

            logger.info(
                f"Reranking applied: {len(results)} -> {len(reranked)} results, "
                f"query_type={query_type}"
            )

            return reranked

        except Exception as e:
            logger.warning(f"Reranking failed, using original results: {e}")
            return results[:top_k]

    async def search_with_reranking(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> tuple[list[SearchResult], dict[str, Any]]:
        """
        Search with reranking and return detailed scores.

        Args:
            query: Search query
            user_id: User ID for access control
            project_id: Optional project ID filter
            document_ids: Optional document IDs filter
            top_k: Number of results
            min_score: Minimum relevance score

        Returns:
            Tuple of (results, reranking_metadata)
        """
        # Fetch more results for reranking
        results = await self.es_client.hybrid_search(
            query=query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=top_k * 3,
            min_score=min_score,
        )

        if not results:
            return [], {"reranking_applied": False}

        # Get query embedding for reranking
        query_embedding = self.embedding_service.encode(query)
        query_type = detect_query_type(query)

        # Apply reranking with full scoring
        reranked = self.reranker.rerank_search_results(
            search_results=results,
            query_embedding=query_embedding,
            query_type=query_type,
        )

        # Get top_k results
        top_results = reranked[:top_k]

        search_results = [
            SearchResult(
                content=r["content"],
                metadata=r["metadata"],
                score=r.get("final_score", r["score"]),
                chunk_id=r["chunk_id"],
            )
            for r in top_results
        ]

        # Prepare metadata
        reranking_metadata = {
            "reranking_applied": True,
            "query_type": query_type,
            "original_count": len(results),
            "reranked_count": len(top_results),
            "score_breakdown": [
                {
                    "chunk_id": r["chunk_id"],
                    "final_score": r.get("final_score", 0),
                    "component_scores": r.get("component_scores", {}),
                }
                for r in top_results
            ],
        }

        return search_results, reranking_metadata

    async def search_with_evaluation(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> tuple[list[SearchResult], SearchEvaluation]:
        """
        Search with result quality evaluation.

        Returns:
            Tuple of (results, evaluation metrics)
        """
        results = await self.search(
            query=query,
            user_id=user_id,
            project_id=project_id,
            document_ids=document_ids,
            top_k=top_k,
        )

        evaluation = self._evaluate_results(query, results)
        return results, evaluation

    def _evaluate_results(
        self,
        query: str,
        results: list[SearchResult],
    ) -> SearchEvaluation:
        """Evaluate search result quality."""
        if not results:
            return SearchEvaluation(
                result_quality=0.0,
                context_relevance=0.0,
                clarity_score=0.0,
                diversity_score=0.0,
                coverage_score=0.0,
            )

        # Result quality (average relevance score)
        result_quality = sum(r.score for r in results) / len(results)

        # Context relevance (embedding similarity)
        query_embedding = self.embedding_service.encode(query)
        similarities = []
        embeddings = []

        for result in results:
            result_embedding = self.embedding_service.encode(result.content)
            embeddings.append(result_embedding)
            sim = self.embedding_service.cosine_similarity(query_embedding, result_embedding)
            similarities.append(sim)

        context_relevance = sum(similarities) / len(similarities)

        # Query clarity
        clarity_score = self._calculate_clarity(query)

        # Result diversity
        diversity_score = self._calculate_diversity(embeddings)

        # Coverage score
        coverage_score = self._calculate_coverage(embeddings)

        return SearchEvaluation(
            result_quality=result_quality,
            context_relevance=context_relevance,
            clarity_score=clarity_score,
            diversity_score=diversity_score,
            coverage_score=coverage_score,
        )

    def _calculate_clarity(self, query: str) -> float:
        """Calculate query clarity score."""
        words = query.split()
        if not words:
            return 0.0

        # Length-based score
        length_score = min(len(words) / 10.0, 1.0) if len(words) < 20 else 20.0 / len(words)

        # Special character penalty
        special_chars = sum(1 for c in query if not c.isalnum() and not c.isspace())
        clarity_penalty = max(0, 1 - (special_chars / max(len(query), 1)))

        return (length_score + clarity_penalty) / 2

    def _calculate_diversity(self, embeddings: list[list[float]]) -> float:
        """Calculate result diversity score."""
        if len(embeddings) < 2:
            return 0.0

        # Calculate pairwise similarities
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = self.embedding_service.cosine_similarity(embeddings[i], embeddings[j])
                similarities.append(sim)

        # Diversity = 1 - average similarity
        avg_similarity = sum(similarities) / len(similarities)
        return 1.0 - avg_similarity

    def _calculate_coverage(self, embeddings: list[list[float]]) -> float:
        """Calculate result coverage score (embedding space spread)."""
        if not embeddings:
            return 0.0

        embeddings_array = np.array(embeddings)
        std_dev = np.std(embeddings_array, axis=0)
        coverage = min(np.mean(std_dev) * 5, 1.0)

        return float(coverage)

    async def delete_document(self, document_id: str, user_id: str) -> int:
        """
        Delete all chunks for a document.

        Returns number of deleted chunks.
        """
        return await self.es_client.delete_by_document_id(document_id, user_id)

    async def search_images(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for images by caption.

        Args:
            query: Search query
            user_id: User ID for filtering
            project_id: Optional project ID filter
            top_k: Number of results

        Returns:
            List of image results
        """
        try:
            from app.services.rag.image.processor import ImageProcessor

            image_processor = ImageProcessor(es_client=self.es_client)
            return await image_processor.search_images(
                query=query,
                user_email=user_id,
                project_id=project_id,
                top_k=top_k,
            )
        except ImportError:
            logger.warning("Image processor not available")
            return []
        except Exception as e:
            logger.error(f"Image search error: {e}")
            return []

    async def index_pdf_with_images(
        self,
        file_path: str,
        file_name: str,
        user_id: str,
        document_id: str,
        project_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Index a PDF document including text and images.

        Args:
            file_path: Path to the file
            file_name: Original file name
            user_id: Owner user ID
            document_id: Document ID in database
            project_id: Optional project ID

        Returns:
            Combined indexing statistics
        """
        # Process PDF with images
        result = await self.document_processor.process_pdf_with_images(
            file_path=file_path,
            file_name=file_name,
            user_id=user_id,
            document_id=document_id,
            project_id=project_id,
        )

        chunks = result["chunks"]
        stats = result["stats"]

        # Index text chunks to Elasticsearch
        indexed_count = await self.es_client.index_documents(
            documents=chunks,
            user_id=user_id,
            project_id=project_id,
            document_id=document_id,
        )

        stats["indexed_count"] = indexed_count
        logger.info(
            f"Indexed PDF {document_id}: {indexed_count} text chunks, "
            f"{stats.get('images_indexed', 0)} images"
        )

        return stats

    async def health_check(self) -> dict[str, Any]:
        """Check RAG system health."""
        es_healthy = await self.es_client.health_check()
        index_exists = await self.es_client.index_exists()
        image_index_exists = await self.es_client.index_exists(
            settings.elasticsearch_index_images
        )

        return {
            "elasticsearch": es_healthy,
            "index_exists": index_exists,
            "image_index_exists": image_index_exists,
            "embedding_model": settings.embedding_model_name,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "reranking_enabled": self.enable_reranking,
        }
