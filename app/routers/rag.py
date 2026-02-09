"""RAG (Retrieval-Augmented Generation) API Router.

Provides endpoints for RAG search operations used by RAG Agent V2.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user_optional
from app.models.user import User
from app.services.rag.rag_service import RAGService, SearchResult
from app.services.rag.document_metadata import format_citation

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RAG"])


class RAGSearchRequest(BaseModel):
    """RAG search request schema."""

    query: str = Field(..., min_length=1, max_length=2000, description="Search query")
    user_id: str = Field(..., description="User ID (email) for access control")
    project_id: Optional[str] = Field(None, description="Filter by project")
    document_ids: Optional[list[str]] = Field(None, description="Filter by document IDs")
    top_k: int = Field(10, ge=1, le=50, description="Number of results")
    min_score: float = Field(0.0, ge=0.0, le=1.0, description="Minimum relevance score")
    use_reranking: bool = Field(True, description="Enable enhanced reranking")


class RAGSearchResponse(BaseModel):
    """RAG search response schema."""

    results: list[dict[str, Any]]
    total_count: int
    query: str
    reranking_metadata: dict[str, Any] = Field(default_factory=dict)


class RAGHealthResponse(BaseModel):
    """RAG health check response."""

    elasticsearch: bool
    index_exists: bool
    image_index_exists: bool
    embedding_model: str
    reranking_enabled: bool


@router.post("/search", response_model=RAGSearchResponse)
async def rag_search(
    request: RAGSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Perform RAG search with hybrid keyword + vector search.

    This endpoint is designed for RAG Agent V2 integration.

    Features:
    - Hybrid search (BM25 + vector similarity)
    - Document ID filtering for file-specific search
    - Enhanced reranking with multi-factor scoring
    - Access control based on user_id

    Returns search results with metadata and reranking information.
    """
    try:
        rag_service = RAGService()

        # Use current_user if authenticated, otherwise use provided user_id
        user_id = current_user.email if current_user else request.user_id

        if request.use_reranking:
            results, reranking_metadata = await rag_service.search_with_reranking(
                query=request.query,
                user_id=user_id,
                project_id=request.project_id,
                document_ids=request.document_ids,
                top_k=request.top_k,
                min_score=request.min_score,
            )
        else:
            results = await rag_service.search(
                query=request.query,
                user_id=user_id,
                project_id=request.project_id,
                document_ids=request.document_ids,
                top_k=request.top_k,
                min_score=request.min_score,
                use_reranking=False,
            )
            reranking_metadata = {"reranking_applied": False}

        # Convert SearchResult objects to dicts
        results_dicts = [
            {
                "content": r.content,
                "metadata": r.metadata,
                "score": r.score,
                "chunk_id": r.chunk_id,
            }
            for r in results
        ]

        logger.info(
            f"RAG search completed: query='{request.query[:50]}...', "
            f"results={len(results)}, user={user_id}"
        )

        return RAGSearchResponse(
            results=results_dicts,
            total_count=len(results),
            query=request.query,
            reranking_metadata=reranking_metadata,
        )

    except Exception as e:
        logger.error(f"RAG search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/search/evaluate")
async def rag_search_with_evaluation(
    request: RAGSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Perform RAG search with result quality evaluation.

    Returns search results plus evaluation metrics:
    - result_quality: Average relevance score
    - context_relevance: Semantic similarity to query
    - clarity_score: Query clarity assessment
    - diversity_score: Result diversity
    - coverage_score: Topic coverage
    """
    try:
        rag_service = RAGService()
        user_id = current_user.email if current_user else request.user_id

        results, evaluation = await rag_service.search_with_evaluation(
            query=request.query,
            user_id=user_id,
            project_id=request.project_id,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )

        results_dicts = [
            {
                "content": r.content,
                "metadata": r.metadata,
                "score": r.score,
                "chunk_id": r.chunk_id,
            }
            for r in results
        ]

        return {
            "results": results_dicts,
            "total_count": len(results),
            "query": request.query,
            "evaluation": {
                "result_quality": evaluation.result_quality,
                "context_relevance": evaluation.context_relevance,
                "clarity_score": evaluation.clarity_score,
                "diversity_score": evaluation.diversity_score,
                "coverage_score": evaluation.coverage_score,
            },
        }

    except Exception as e:
        logger.error(f"RAG search with evaluation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.get("/health", response_model=RAGHealthResponse)
async def rag_health():
    """
    Check RAG system health.

    Returns status of:
    - Elasticsearch connection
    - Document index
    - Image index
    - Embedding model
    - Reranking status
    """
    try:
        rag_service = RAGService()
        health = await rag_service.health_check()

        return RAGHealthResponse(
            elasticsearch=health.get("elasticsearch", False),
            index_exists=health.get("index_exists", False),
            image_index_exists=health.get("image_index_exists", False),
            embedding_model=health.get("embedding_model", "unknown"),
            reranking_enabled=health.get("reranking_enabled", False),
        )

    except Exception as e:
        logger.error(f"RAG health check error: {e}")
        return RAGHealthResponse(
            elasticsearch=False,
            index_exists=False,
            image_index_exists=False,
            embedding_model="error",
            reranking_enabled=False,
        )


@router.post("/index")
async def index_document(
    document_id: str,
    user_id: str,
    file_path: str,
    file_name: str,
    project_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Index a document for RAG search.

    This endpoint is for manual document indexing.
    For automatic indexing, use the document upload endpoint.
    """
    try:
        rag_service = RAGService()
        actual_user_id = current_user.email if current_user else user_id

        stats = await rag_service.index_document(
            file_path=file_path,
            file_name=file_name,
            user_id=actual_user_id,
            document_id=document_id,
            project_id=project_id,
        )

        return {
            "success": True,
            "document_id": document_id,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Document indexing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {str(e)}",
        )


@router.delete("/document/{document_id}")
async def delete_document_index(
    document_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Delete document chunks from the index.
    """
    try:
        rag_service = RAGService()
        actual_user_id = current_user.email if current_user else user_id

        deleted_count = await rag_service.delete_document(
            document_id=document_id,
            user_id=actual_user_id,
        )

        return {
            "success": True,
            "document_id": document_id,
            "deleted_chunks": deleted_count,
        }

    except Exception as e:
        logger.error(f"Document deletion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deletion failed: {str(e)}",
        )


class UnifiedSearchRequest(BaseModel):
    """Unified search request for text and images."""

    query: str = Field(..., min_length=1, max_length=2000, description="Search query")
    user_id: str = Field(..., description="User ID (email) for access control")
    project_id: Optional[str] = Field(None, description="Filter by project")
    document_ids: Optional[list[str]] = Field(None, description="Filter by document IDs")
    top_k: int = Field(5, ge=1, le=20, description="Number of results per type")
    include_images: bool = Field(True, description="Include image search results")
    use_reranking: bool = Field(True, description="Enable enhanced reranking")


class Reference(BaseModel):
    """Reference information for citation."""

    ref_id: str = Field(..., description="Reference ID (e.g., ref-1)")
    type: str = Field(..., description="Reference type: text or image")
    doc_type: Optional[str] = Field(None, description="Document type (paper, legal, meeting, etc.)")
    file_name: str = Field(..., description="Source file name")
    page: Optional[int] = Field(None, description="Page number")
    title: Optional[str] = Field(None, description="Document title")
    authors: Optional[str] = Field(None, description="Authors")
    organization: Optional[str] = Field(None, description="Organization/Company")
    caption: Optional[str] = Field(None, description="Image caption (for images)")
    chunk_index: Optional[int] = Field(None, description="Chunk index within document")
    citation: str = Field(..., description="Formatted citation string")


@router.post("/search/unified")
async def unified_search(
    request: UnifiedSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Unified RAG search for text and images with references.

    Returns:
    - text_results: Matching text chunks with content and metadata
    - image_results: Matching images with captions
    - references: Formatted citation information for all results

    Use references to cite sources in LLM responses:
    - "According to [ref-1], emotional RAG improves..."
    - "As shown in [ref-img-1], the architecture..."
    """
    try:
        rag_service = RAGService()
        user_id = current_user.email if current_user else request.user_id

        # Text search
        if request.use_reranking:
            text_results, reranking_metadata = await rag_service.search_with_reranking(
                query=request.query,
                user_id=user_id,
                project_id=request.project_id,
                document_ids=request.document_ids,
                top_k=request.top_k,
            )
        else:
            text_results = await rag_service.search(
                query=request.query,
                user_id=user_id,
                project_id=request.project_id,
                document_ids=request.document_ids,
                top_k=request.top_k,
                use_reranking=False,
            )
            reranking_metadata = {"reranking_applied": False}

        # Image search (optional)
        image_results = []
        if request.include_images:
            image_results = await rag_service.search_images(
                query=request.query,
                user_id=user_id,
                project_id=request.project_id,
                top_k=request.top_k,
            )

        # Build references list
        references = []
        seen_refs = set()  # Deduplicate by file_name + page

        # Text references
        for i, result in enumerate(text_results):
            meta = result.metadata
            ref_key = f"{meta.get('file_name', '')}_{meta.get('page', '')}_{meta.get('chunk_index', i)}"

            if ref_key not in seen_refs:
                seen_refs.add(ref_key)

                # Use format_citation for document-type-aware citation
                doc_type = meta.get("doc_type", "general")
                citation = format_citation(meta, ref_id=f"ref-{len(references) + 1}")

                # Add page info if not already in citation
                page = meta.get("page")
                if page and f"p.{page}" not in citation and f"p. {page}" not in citation:
                    citation += f", p.{page}"

                references.append(
                    Reference(
                        ref_id=f"ref-{len(references) + 1}",
                        type="text",
                        doc_type=doc_type,
                        file_name=meta.get("file_name", "Unknown"),
                        page=page,
                        title=meta.get("title"),
                        authors=meta.get("authors"),
                        organization=meta.get("organization"),
                        chunk_index=meta.get("chunk_index"),
                        citation=citation,
                    )
                )

        # Image references
        for i, img in enumerate(image_results):
            ref_key = f"img_{img.get('file_name', '')}_{img.get('page_num', i)}"

            if ref_key not in seen_refs:
                seen_refs.add(ref_key)

                file_name = img.get("file_name", "Unknown")
                page = img.get("page_num")
                caption = img.get("caption", "")

                # Extract figure number from caption if available
                fig_num = ""
                if caption and "Fig." in caption:
                    fig_num = caption.split(":")[0].strip()

                citation = f"{fig_num}" if fig_num else f"Image from {file_name}"
                if page:
                    citation += f", p.{page}"

                references.append(
                    Reference(
                        ref_id=f"ref-img-{i + 1}",
                        type="image",
                        file_name=file_name,
                        page=page,
                        caption=caption[:200] if caption else None,
                        citation=citation,
                    )
                )

        # Convert results to dicts
        text_results_dicts = [
            {
                "content": r.content,
                "metadata": r.metadata,
                "score": r.score,
                "chunk_id": r.chunk_id,
                "ref_id": f"ref-{i + 1}",  # Link to reference
            }
            for i, r in enumerate(text_results)
        ]

        image_results_dicts = [
            {
                **img,
                "ref_id": f"ref-img-{i + 1}",  # Link to reference
            }
            for i, img in enumerate(image_results)
        ]

        logger.info(
            f"Unified search: query='{request.query[:50]}...', "
            f"text={len(text_results)}, images={len(image_results)}, refs={len(references)}"
        )

        return {
            "query": request.query,
            "text_results": text_results_dicts,
            "image_results": image_results_dicts,
            "references": [ref.model_dump() for ref in references],
            "total_count": {
                "text": len(text_results),
                "images": len(image_results),
                "references": len(references),
            },
            "reranking_metadata": reranking_metadata,
        }

    except Exception as e:
        logger.error(f"Unified search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.post("/search/images")
async def search_images(
    query: str,
    user_id: str,
    project_id: Optional[str] = None,
    top_k: int = 5,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Search for images by caption.

    Returns images with captions, page numbers, and file information.
    """
    try:
        rag_service = RAGService()
        actual_user_id = current_user.email if current_user else user_id

        results = await rag_service.search_images(
            query=query,
            user_id=actual_user_id,
            project_id=project_id,
            top_k=top_k,
        )

        # Add references for images
        references = []
        for i, img in enumerate(results):
            file_name = img.get("file_name", "Unknown")
            page = img.get("page_num")
            caption = img.get("caption", "")

            fig_num = ""
            if caption and "Fig." in caption:
                fig_num = caption.split(":")[0].strip()

            citation = f"{fig_num}" if fig_num else f"Image from {file_name}"
            if page:
                citation += f", p.{page}"

            references.append({
                "ref_id": f"ref-img-{i + 1}",
                "type": "image",
                "file_name": file_name,
                "page": page,
                "caption": caption[:200] if caption else None,
                "citation": citation,
            })

        return {
            "query": query,
            "results": results,
            "references": references,
            "total_count": len(results),
        }

    except Exception as e:
        logger.error(f"Image search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image search failed: {str(e)}",
        )
