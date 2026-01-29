"""Document management endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.core.deps import CurrentUser, DBSession
from app.models.document import DocumentStatus
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentUpdate,
    DocumentUploadResponse,
)
from app.services.document_service import DocumentService, DocumentServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    current_user: CurrentUser,
    db: DBSession,
    project_id: Optional[str] = Query(None, description="Filter by project"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    List documents for current user.

    Optionally filter by project and/or status.
    Requires authentication.
    """
    service = DocumentService(db)

    # Parse status filter
    doc_status = None
    if status_filter:
        try:
            doc_status = DocumentStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid values: {[s.value for s in DocumentStatus]}",
            )

    documents, total = await service.list_by_user(
        user_id=current_user.id,
        project_id=project_id,
        status=doc_status,
        skip=skip,
        limit=limit,
    )

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(..., description="Document file to upload"),
    project_id: Optional[str] = Form(None, description="Project ID"),
    title: Optional[str] = Form(None, description="Document title"),
    description: Optional[str] = Form(None, description="Document description"),
):
    """
    Upload a document.

    Supported formats: PDF, TXT, MD, DOCX, CSV, JSON
    Maximum file size: 50MB

    Requires authentication.
    """
    service = DocumentService(db)

    try:
        document = await service.upload(
            user_id=current_user.id,
            file=file,
            project_id=project_id,
            title=title,
            description=description,
        )
        await db.commit()

        return DocumentUploadResponse(
            document=DocumentResponse.model_validate(document),
            message="Document uploaded successfully. Processing will begin shortly.",
        )
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get document details.

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    document = await service.get_by_id_and_user(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentResponse.model_validate(document)


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    current_user: CurrentUser,
    db: DBSession,
    update_data: DocumentUpdate,
):
    """
    Update document metadata.

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    document = await service.get_by_id_and_user(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    document = await service.update(document, update_data)
    await db.commit()

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Delete a document.

    This will also delete the file from storage.
    Requires authentication and ownership.
    """
    service = DocumentService(db)
    document = await service.get_by_id_and_user(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    await service.delete(document)
    await db.commit()


@router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    current_user: CurrentUser,
    db: DBSession,
    request: DocumentSearchRequest,
):
    """
    Search documents using RAG (Retrieval-Augmented Generation).

    Uses hybrid search combining:
    - Keyword search (multi-field matching with boosting)
    - Vector search (cosine similarity with Korean-optimized embeddings)

    Returns relevant chunks with their source documents and relevance scores.
    Requires authentication.
    """
    service = DocumentService(db)

    try:
        results = await service.search(
            user_id=current_user.id,
            request=request,
        )
        return DocumentSearchResponse(**results)
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{document_id}/process", response_model=DocumentResponse)
async def process_document(
    document_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Process a document for RAG indexing.

    Extracts text, creates chunks with embeddings, and indexes to Elasticsearch.
    This operation may take several seconds depending on document size.

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    document = await service.get_by_id_and_user(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.status == DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document already processed. Use /reprocess to re-index.",
        )

    try:
        await service.process_for_rag(document)
        await db.commit()
        await db.refresh(document)
        return DocumentResponse.model_validate(document)
    except DocumentServiceError as e:
        await db.commit()  # Save failed status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    document_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Reprocess a document for RAG re-indexing.

    Deletes existing index entries and re-processes the document.
    Useful for documents that need re-indexing after updates.

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    document = await service.get_by_id_and_user(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        # Delete existing RAG entries
        await service.delete_from_rag(document)

        # Reprocess
        await service.process_for_rag(document)
        await db.commit()
        await db.refresh(document)

        return DocumentResponse.model_validate(document)
    except DocumentServiceError as e:
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get document content as text.

    Supports: PDF, TXT, MD, DOCX, CSV, JSON
    Uses the document processor for text extraction.

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    document = await service.get_by_id_and_user(
        document_id=document_id,
        user_id=current_user.id,
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    try:
        content = await service.get_content(document)
        return {
            "document_id": document_id,
            "content": content,
            "content_type": "text/plain",
        }
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/rag/health")
async def check_rag_health(
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Check RAG system health.

    Returns Elasticsearch connection status and index information.
    Requires authentication.
    """
    service = DocumentService(db)

    try:
        health = await service.check_rag_health()
        return {
            "status": "healthy" if health.get("elasticsearch") else "unhealthy",
            "details": health,
        }
    except Exception as e:
        return {
            "status": "error",
            "details": {"error": str(e)},
        }
