"""RAG (Retrieval-Augmented Generation) service package.

Enhanced with:
- Reranking system for improved search quality
- Image processing for PDF documents
- Paper metadata extraction
"""

from app.services.rag.embedding_service import EmbeddingService, get_embedding_service
from app.services.rag.elasticsearch_client import ElasticsearchClient, get_elasticsearch_client
from app.services.rag.document_processor import DocumentProcessor
from app.services.rag.rag_service import RAGService, SearchResult, SearchEvaluation

# Reranking module
from app.services.rag.rerank import (
    EnhancedReRanker,
    DocumentScorer,
    ScoreNormalizer,
    detect_query_type,
)

# Paper metadata extraction
from app.services.rag.paper_metadata import (
    extract_paper_metadata,
    PaperMetadata,
)

__all__ = [
    # Core services
    "EmbeddingService",
    "get_embedding_service",
    "ElasticsearchClient",
    "get_elasticsearch_client",
    "DocumentProcessor",
    "RAGService",
    "SearchResult",
    "SearchEvaluation",
    # Reranking
    "EnhancedReRanker",
    "DocumentScorer",
    "ScoreNormalizer",
    "detect_query_type",
    # Paper metadata
    "extract_paper_metadata",
    "PaperMetadata",
]
