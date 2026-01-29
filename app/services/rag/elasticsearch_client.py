"""Elasticsearch client for RAG system."""

import logging
from functools import lru_cache
from typing import Any, Optional

from elasticsearch import AsyncElasticsearch
from langchain_core.documents import Document as LangchainDocument
from langchain_elasticsearch import ElasticsearchStore

from app.config import settings
from app.services.rag.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """
    Async Elasticsearch client for document storage and retrieval.

    Provides both low-level ES operations and LangChain integration.
    """

    _instance: Optional["ElasticsearchClient"] = None
    _es_client: Optional[AsyncElasticsearch] = None

    def __new__(cls) -> "ElasticsearchClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._store: Optional[ElasticsearchStore] = None
        self._initialized = True

    @property
    def client(self) -> AsyncElasticsearch:
        """Get async Elasticsearch client."""
        if self._es_client is None:
            self._es_client = AsyncElasticsearch([settings.elasticsearch_url])
        return self._es_client

    @property
    def store(self) -> ElasticsearchStore:
        """Get LangChain ElasticsearchStore for document operations."""
        if self._store is None:
            embedding_service = get_embedding_service()
            self._store = ElasticsearchStore(
                embedding=embedding_service.model,
                es_url=settings.elasticsearch_url,
                index_name=settings.elasticsearch_index_docs,
            )
        return self._store

    async def close(self):
        """Close Elasticsearch connections."""
        if self._es_client:
            await self._es_client.close()
            self._es_client = None
        if self._store:
            self._store = None
        logger.info("Elasticsearch connections closed")

    async def health_check(self) -> bool:
        """Check Elasticsearch connection health."""
        try:
            info = await self.client.info()
            logger.info(f"Elasticsearch connected: {info['cluster_name']}")
            return True
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False

    async def index_exists(self, index_name: Optional[str] = None) -> bool:
        """Check if index exists."""
        idx = index_name or settings.elasticsearch_index_docs
        return await self.client.indices.exists(index=idx)

    async def create_index(self, index_name: Optional[str] = None) -> bool:
        """
        Create document index with proper mappings.

        Returns True if created, False if already exists.
        """
        idx = index_name or settings.elasticsearch_index_docs

        if await self.index_exists(idx):
            logger.info(f"Index {idx} already exists")
            return False

        index_body = {
            "settings": {
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                }
            },
            "mappings": {
                "properties": {
                    "text": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                    },
                    "vector": {
                        "type": "dense_vector",
                        "dims": 768,
                        "index": True,
                        "similarity": "cosine",
                        "index_options": {
                            "type": "int8_hnsw",
                            "m": 16,
                            "ef_construction": 100,
                        },
                    },
                    "metadata": {
                        "properties": {
                            "user_id": {"type": "keyword"},
                            "project_id": {"type": "keyword"},
                            "document_id": {"type": "keyword"},
                            "file_name": {
                                "type": "text",
                                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                            },
                            "file_type": {"type": "keyword"},
                            "page": {"type": "integer"},
                            "chunk_index": {"type": "integer"},
                            "title": {"type": "text"},
                            "created_at": {"type": "date"},
                        }
                    },
                }
            },
        }

        await self.client.indices.create(index=idx, body=index_body)
        logger.info(f"Index {idx} created")
        return True

    async def index_documents(
        self,
        documents: list[LangchainDocument],
        user_id: str,
        project_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> int:
        """
        Index documents to Elasticsearch.

        Args:
            documents: List of LangChain documents with content and metadata
            user_id: User ID for access control
            project_id: Optional project ID
            document_id: Optional document ID

        Returns:
            Number of indexed documents
        """
        # Ensure index exists
        await self.create_index()

        # Add user context to metadata
        for doc in documents:
            doc.metadata["user_id"] = user_id
            if project_id:
                doc.metadata["project_id"] = project_id
            if document_id:
                doc.metadata["document_id"] = document_id

        # Use LangChain store for indexing (handles embeddings automatically)
        embedding_service = get_embedding_service()
        try:
            ElasticsearchStore.from_documents(
                documents,
                embedding_service.model,
                es_url=settings.elasticsearch_url,
                index_name=settings.elasticsearch_index_docs,
            )
            logger.info(f"Indexed {len(documents)} documents")
            return len(documents)
        except Exception as e:
            # If index exists, use add_documents
            if "resource_already_exists_exception" in str(e).lower():
                self.store.add_documents(documents)
                logger.info(f"Added {len(documents)} documents to existing index")
                return len(documents)
            raise

    async def hybrid_search(
        self,
        query: str,
        user_id: str,
        project_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """
        Perform hybrid search (keyword + vector).

        Args:
            query: Search query
            user_id: User ID for access control
            project_id: Optional project ID filter
            document_ids: Optional document ID filter
            top_k: Number of results to return
            min_score: Minimum relevance score threshold

        Returns:
            List of search results with content, metadata, and scores
        """
        embedding_service = get_embedding_service()
        query_vector = embedding_service.encode(query)

        # Build filter conditions
        filter_conditions = [{"term": {"metadata.user_id": user_id}}]

        if project_id:
            filter_conditions.append({"term": {"metadata.project_id": project_id}})

        if document_ids:
            filter_conditions.append({"terms": {"metadata.document_id": document_ids}})

        # Hybrid search query
        search_query = {
            "query": {
                "bool": {
                    "filter": filter_conditions,
                    "should": [
                        # Keyword search with boosting
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["text^2", "metadata.title", "metadata.file_name"],
                                "type": "most_fields",
                                "tie_breaker": 0.3,
                            }
                        },
                        # Vector search
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {
                                    "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                                    "params": {"query_vector": query_vector},
                                },
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            "size": top_k,
            "_source": ["text", "metadata"],
        }

        response = await self.client.search(
            index=settings.elasticsearch_index_docs,
            body=search_query,
        )

        results = []
        for hit in response["hits"]["hits"]:
            score = hit["_score"]
            if score < min_score:
                continue

            results.append(
                {
                    "content": hit["_source"].get("text", ""),
                    "metadata": hit["_source"].get("metadata", {}),
                    "score": score,
                    "chunk_id": hit["_id"],
                }
            )

        return results

    async def delete_by_document_id(self, document_id: str, user_id: str) -> int:
        """
        Delete all chunks for a document.

        Returns number of deleted documents.
        """
        response = await self.client.delete_by_query(
            index=settings.elasticsearch_index_docs,
            body={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"metadata.document_id": document_id}},
                            {"term": {"metadata.user_id": user_id}},
                        ]
                    }
                }
            },
        )
        deleted = response.get("deleted", 0)
        logger.info(f"Deleted {deleted} chunks for document {document_id}")
        return deleted

    async def delete_by_user_id(self, user_id: str) -> int:
        """Delete all documents for a user."""
        response = await self.client.delete_by_query(
            index=settings.elasticsearch_index_docs,
            body={"query": {"term": {"metadata.user_id": user_id}}},
        )
        deleted = response.get("deleted", 0)
        logger.info(f"Deleted {deleted} chunks for user {user_id}")
        return deleted


@lru_cache
def get_elasticsearch_client() -> ElasticsearchClient:
    """Get cached Elasticsearch client instance."""
    return ElasticsearchClient()
