"""Image processing service for RAG system."""

import io
import logging
from typing import Any, Optional

from PIL import Image

from app.config import settings
from app.services.rag.embedding_service import get_embedding_service
from app.services.rag.image.extractor import (
    extract_images_from_pdf,
    extract_images_with_fitz,
    resize_image,
)

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Process and index images from PDF documents.

    Features:
    - Extract images from PDFs
    - Generate caption embeddings
    - Index to Elasticsearch
    """

    def __init__(self, es_client: Optional[Any] = None):
        """
        Initialize image processor.

        Args:
            es_client: Optional Elasticsearch client
        """
        self._es_client = es_client
        self._embedding_service = None

    @property
    def embedding_service(self):
        """Get embedding service (lazy init)."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    @property
    def es_client(self):
        """Get Elasticsearch client (lazy init)."""
        if self._es_client is None:
            from app.services.rag.elasticsearch_client import get_elasticsearch_client

            self._es_client = get_elasticsearch_client()
        return self._es_client

    async def process_pdf_images(
        self,
        pdf_path: str,
        user_email: str,
        file_name: str,
        project_id: str,
        use_fitz: bool = True,
    ) -> dict[str, Any]:
        """
        Extract and process images from a PDF.

        Args:
            pdf_path: Path to the PDF file
            user_email: User email
            file_name: Original file name
            project_id: Project ID
            use_fitz: Use PyMuPDF for better extraction

        Returns:
            Processing statistics
        """
        try:
            # Extract images
            if use_fitz:
                images = extract_images_with_fitz(
                    pdf_path=pdf_path,
                    user_email=user_email,
                    file_name=file_name,
                    project_id=project_id,
                )
            else:
                images = extract_images_from_pdf(
                    pdf_path=pdf_path,
                    user_email=user_email,
                    file_name=file_name,
                    project_id=project_id,
                )

            if not images:
                logger.info(f"No images found in {file_name}")
                return {"images_found": 0, "images_indexed": 0}

            # Generate embeddings for captions
            for img_doc in images:
                caption = img_doc.get("caption", "")
                if caption and caption != "No caption found":
                    img_doc["vector"] = self.embedding_service.encode(caption)

            # Index to Elasticsearch
            indexed_count = await self._index_images(images)

            logger.info(
                f"Processed {len(images)} images from {file_name}, "
                f"indexed {indexed_count}"
            )

            return {
                "images_found": len(images),
                "images_indexed": indexed_count,
                "file_name": file_name,
            }

        except Exception as e:
            logger.error(f"Error processing PDF images: {e}")
            return {"error": str(e), "images_found": 0, "images_indexed": 0}

    async def _index_images(
        self,
        images: list[dict[str, Any]],
    ) -> int:
        """
        Index images to Elasticsearch.

        Args:
            images: List of image documents

        Returns:
            Number of indexed images
        """
        try:
            # Ensure index exists
            await self._ensure_image_index()

            index_name = settings.elasticsearch_index_images

            indexed = 0
            for img_doc in images:
                try:
                    await self.es_client.client.index(
                        index=index_name,
                        body=img_doc,
                    )
                    indexed += 1
                except Exception as e:
                    logger.warning(f"Failed to index image: {e}")

            # Refresh index
            await self.es_client.client.indices.refresh(index=index_name)

            return indexed

        except Exception as e:
            logger.error(f"Error indexing images: {e}")
            return 0

    async def _ensure_image_index(self) -> None:
        """Create image index if it doesn't exist."""
        try:
            index_name = settings.elasticsearch_index_images

            if await self.es_client.client.indices.exists(index=index_name):
                return

            index_body = {
                "settings": {
                    "index": {
                        "number_of_shards": 1,
                        "number_of_replicas": 1,
                    }
                },
                "mappings": {
                    "properties": {
                        "image_id": {"type": "keyword"},
                        "page_num": {"type": "integer"},
                        "file_name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "image_data": {"type": "binary"},
                        "caption": {"type": "text"},
                        "vector": {
                            "type": "dense_vector",
                            "dims": 768,
                            "index": True,
                            "similarity": "cosine",
                        },
                        "timestamp": {"type": "date"},
                        "user_email": {"type": "keyword"},
                        "project_id": {"type": "keyword"},
                    }
                },
            }

            await self.es_client.client.indices.create(
                index=index_name,
                body=index_body,
            )
            logger.info(f"Created image index: {index_name}")

        except Exception as e:
            logger.error(f"Error creating image index: {e}")

    async def search_images(
        self,
        query: str,
        user_email: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search for images by caption.

        Args:
            query: Search query
            user_email: User email for filtering
            project_id: Optional project ID filter
            top_k: Number of results

        Returns:
            List of matching images
        """
        try:
            query_embedding = self.embedding_service.encode(query)
            index_name = settings.elasticsearch_index_images

            # Build filter
            filter_conditions = [{"term": {"user_email": user_email}}]
            if project_id:
                filter_conditions.append({"term": {"project_id": project_id}})

            # Search query
            search_query = {
                "query": {
                    "bool": {
                        "filter": filter_conditions,
                        "should": [
                            {"match": {"caption": query}},
                            {
                                "script_score": {
                                    "query": {"match_all": {}},
                                    "script": {
                                        "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                                        "params": {"query_vector": query_embedding},
                                    },
                                }
                            },
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "size": top_k,
                "_source": ["image_id", "caption", "page_num", "file_name", "timestamp"],
            }

            response = await self.es_client.client.search(
                index=index_name,
                body=search_query,
            )

            results = []
            for hit in response["hits"]["hits"]:
                result = hit["_source"]
                result["score"] = hit["_score"]
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Image search error: {e}")
            return []

    async def get_image_by_id(
        self,
        image_id: str,
        user_email: str,
    ) -> Optional[dict[str, Any]]:
        """
        Get image by ID.

        Args:
            image_id: Image ID
            user_email: User email for filtering

        Returns:
            Image document or None
        """
        try:
            index_name = settings.elasticsearch_index_images

            search_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"image_id": image_id}},
                            {"term": {"user_email": user_email}},
                        ]
                    }
                },
                "size": 1,
            }

            response = await self.es_client.client.search(
                index=index_name,
                body=search_query,
            )

            if response["hits"]["hits"]:
                return response["hits"]["hits"][0]["_source"]

            return None

        except Exception as e:
            logger.error(f"Error getting image: {e}")
            return None

    async def delete_images_by_file(
        self,
        file_name: str,
        user_email: str,
    ) -> int:
        """
        Delete all images for a file.

        Args:
            file_name: File name
            user_email: User email

        Returns:
            Number of deleted images
        """
        try:
            index_name = settings.elasticsearch_index_images

            response = await self.es_client.client.delete_by_query(
                index=index_name,
                body={
                    "query": {
                        "bool": {
                            "must": [
                                {"match": {"file_name.keyword": file_name}},
                                {"term": {"user_email": user_email}},
                            ]
                        }
                    }
                },
            )

            deleted = response.get("deleted", 0)
            logger.info(f"Deleted {deleted} images for {file_name}")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting images: {e}")
            return 0
