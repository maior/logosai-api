"""Document management endpoints - uses user_files table from logos_server."""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status

from app.core.deps import CurrentUser, DBSession
from app.services.document_service import DocumentService, DocumentServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


async def _process_file_async(
    file_id: str,
    user_email: str,
    project_id: str,
    db_url: str,
):
    """
    Async implementation of RAG processing.

    Uses synchronous Elasticsearch client for background tasks to avoid
    aiohttp event loop issues with asyncio.timeout() in Python 3.11+.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from elasticsearch import Elasticsearch
    from app.services.rag.document_processor import DocumentProcessor
    from app.services.rag.embedding_service import get_embedding_service
    from app.config import settings
    import uuid

    engine = None
    sync_es = None
    logger.info(f"Background async processing started for file {file_id}")
    try:
        engine = create_async_engine(db_url)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            service = DocumentService(session)
            user_file = await service.get_by_id_and_user(file_id, user_email)

            if not user_file:
                logger.warning(f"File not found for background processing: {file_id}")
                return

            logger.info(f"User file found: {user_file.file_name}, processing...")

            # Use synchronous ES client for background processing
            sync_es = Elasticsearch([settings.elasticsearch_url])
            logger.info(f"Sync ES client created for {settings.elasticsearch_url}")

            # Build file path
            from pathlib import Path
            upload_dir = Path("uploads")
            file_path = upload_dir / user_file.project_id / user_file.file_name

            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return

            try:
                # Process document
                processor = DocumentProcessor()
                chunks = await processor.process_file(
                    file_path=str(file_path),
                    file_name=user_file.file_name,
                    user_id=user_email,
                    document_id=file_id,
                    project_id=project_id,
                )
                logger.info(f"Document processed: {len(chunks) if chunks else 0} chunks generated")

                if not chunks:
                    logger.warning(f"No chunks generated for file {file_id}")
                    return

                # Get embedding service
                embedding_service = get_embedding_service()

                # Index using synchronous ES client
                indexed_count = 0
                for chunk in chunks:
                    try:
                        embedding = embedding_service.encode(chunk.page_content)

                        doc_body = {
                            "content": chunk.page_content,
                            "embedding": embedding,
                            "metadata": chunk.metadata,
                        }

                        sync_es.index(
                            index=settings.elasticsearch_index_docs,
                            id=str(uuid.uuid4()),
                            document=doc_body,
                        )
                        indexed_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to index chunk: {e}")

                # Refresh index
                sync_es.indices.refresh(index=settings.elasticsearch_index_docs)

                logger.info(
                    f"Background RAG processing completed for file {file_id}: "
                    f"indexed {indexed_count}/{len(chunks)} chunks"
                )

            except Exception as e:
                logger.error(f"Background RAG processing failed for {file_id}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Background task error for file {file_id}: {e}", exc_info=True)
    finally:
        if sync_es:
            try:
                sync_es.close()
            except Exception:
                pass
        if engine:
            await engine.dispose()


def process_file_background(
    file_id: str,
    user_email: str,
    project_id: str,
    db_url: str,
):
    """
    Background task wrapper - runs async function in new event loop.
    FastAPI BackgroundTasks doesn't properly await async functions,
    so we need to run them in a new event loop.
    """
    import threading

    logger.info(f"Background task started for file {file_id} in thread {threading.current_thread().name}")

    try:
        # Create new event loop for background task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _process_file_async(file_id, user_email, project_id, db_url)
            )
        finally:
            loop.close()
        logger.info(f"Background task completed for file {file_id}")
    except Exception as e:
        logger.error(f"Background task wrapper error for {file_id}: {e}", exc_info=True)


@router.get("/")
async def list_files(
    current_user: CurrentUser,
    db: DBSession,
    project_id: Optional[str] = Query(None, description="Filter by project"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """
    List files for current user.

    Optionally filter by project.
    Requires authentication.
    """
    service = DocumentService(db)

    files, total = await service.list_by_user(
        user_email=current_user.email,
        project_id=project_id,
        skip=skip,
        limit=limit,
    )

    return {
        "files": [
            {
                "file_id": f.file_id,
                "project_id": f.project_id,
                "project_name": f.project_name,
                "file_name": f.file_name,
                "file_size": f.file_size,
                "file_type": f.file_type,
                "upload_at": f.upload_at.isoformat() if f.upload_at else None,
            }
            for f in files
        ],
        "total": total,
    }


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    current_user: CurrentUser,
    db: DBSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    project_id: str = Form(..., description="Project ID (required)"),
    project_name: Optional[str] = Form(None, description="Project name"),
    auto_process: bool = Form(True, description="Automatically process for RAG indexing"),
):
    """
    Upload a file.

    Supported formats: PDF, TXT, MD, DOCX, CSV, JSON
    Maximum file size: 50MB

    Requires authentication.
    """
    from app.config import settings

    service = DocumentService(db)

    try:
        user_file = await service.upload(
            user_email=current_user.email,
            file=file,
            project_id=project_id,
            project_name=project_name,
        )
        await db.commit()

        # Queue background RAG processing
        if auto_process:
            logger.info(f"Adding background task for file {user_file.file_id}")
            background_tasks.add_task(
                process_file_background,
                file_id=user_file.file_id,
                user_email=current_user.email,
                project_id=project_id,
                db_url=settings.database_url,
            )
            message = "File uploaded. RAG processing started in background."
        else:
            message = "File uploaded. Use /process endpoint to index for RAG."

        return {
            "file": {
                "file_id": user_file.file_id,
                "project_id": user_file.project_id,
                "file_name": user_file.file_name,
                "file_size": user_file.file_size,
                "file_type": user_file.file_type,
                "upload_at": user_file.upload_at.isoformat() if user_file.upload_at else None,
            },
            "message": message,
        }
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get file details.

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    user_file = await service.get_by_id_and_user(
        file_id=file_id,
        user_email=current_user.email,
    )

    if not user_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return {
        "file_id": user_file.file_id,
        "project_id": user_file.project_id,
        "project_name": user_file.project_name,
        "user_email": user_file.user_email,
        "file_name": user_file.file_name,
        "file_size": user_file.file_size,
        "file_type": user_file.file_type,
        "upload_at": user_file.upload_at.isoformat() if user_file.upload_at else None,
    }


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Delete a file (soft delete).

    Requires authentication and ownership.
    """
    service = DocumentService(db)
    user_file = await service.get_by_id_and_user(
        file_id=file_id,
        user_email=current_user.email,
    )

    if not user_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    await service.delete(user_file)
    await db.commit()


@router.post("/search")
async def search_files(
    current_user: CurrentUser,
    db: DBSession,
    query: str = Form(..., description="Search query"),
    project_id: Optional[str] = Form(None, description="Filter by project"),
    top_k: int = Form(5, ge=1, le=20, description="Number of results"),
):
    """
    Search files using RAG (Retrieval-Augmented Generation).

    Returns website-compatible format:
    {
        "msg": "success",
        "code": 0,
        "data": {
            "query": "...",
            "results": [...],
            "references": [...],
            "pdf_names": [...],
            ...
        }
    }

    Uses hybrid search: keyword + vector similarity with reranking.
    Requires authentication.
    """
    service = DocumentService(db)

    try:
        # Already returns website-compatible format
        results = await service.search(
            user_email=current_user.email,
            query=query,
            project_id=project_id,
            top_k=top_k,
        )
        return results
    except DocumentServiceError as e:
        return {
            "msg": "error",
            "code": 400,
            "data": {
                "query": query,
                "results": [],
                "error": str(e),
            },
        }


@router.post("/{file_id}/process")
async def process_file(
    file_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Process a file for RAG indexing.

    Extracts text, creates chunks with embeddings, and indexes to Elasticsearch.
    Requires authentication and ownership.
    """
    service = DocumentService(db)
    user_file = await service.get_by_id_and_user(
        file_id=file_id,
        user_email=current_user.email,
    )

    if not user_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    try:
        stats = await service.process_for_rag(user_file)
        return {
            "file_id": file_id,
            "message": "File processed successfully",
            "stats": stats,
        }
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{file_id}/content")
async def get_file_content(
    file_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get file content as text.

    Supports: PDF, TXT, MD, DOCX, CSV, JSON
    Requires authentication and ownership.
    """
    service = DocumentService(db)
    user_file = await service.get_by_id_and_user(
        file_id=file_id,
        user_email=current_user.email,
    )

    if not user_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    try:
        content = await service.get_content(user_file)
        return {
            "file_id": file_id,
            "file_name": user_file.file_name,
            "content": content,
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

    Returns Elasticsearch connection status.
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
