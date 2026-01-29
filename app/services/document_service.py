"""Document service for file management and RAG operations."""

import logging
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import Document, DocumentStatus, DocumentType
from app.schemas.document import DocumentUpdate, DocumentSearchRequest

logger = logging.getLogger(__name__)

# File storage configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default
ALLOWED_EXTENSIONS = {
    ".pdf": (DocumentType.PDF, "application/pdf"),
    ".txt": (DocumentType.TXT, "text/plain"),
    ".md": (DocumentType.MD, "text/markdown"),
    ".docx": (DocumentType.DOCX, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ".csv": (DocumentType.CSV, "text/csv"),
    ".json": (DocumentType.JSON, "application/json"),
}


class DocumentServiceError(Exception):
    """Document service error."""
    pass


class DocumentService:
    """Service for document-related operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, document_id: str) -> Optional[Document]:
        """Get document by ID."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self,
        document_id: str,
        user_id: str,
    ) -> Optional[Document]:
        """Get document by ID and user."""
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id,
                Document.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Document], int]:
        """List documents by user."""
        query = select(Document).where(Document.user_id == user_id)

        if project_id:
            query = query.where(Document.project_id == project_id)

        if status:
            query = query.where(Document.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(Document.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def upload(
        self,
        user_id: str,
        file: UploadFile,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Document:
        """
        Upload a document file.

        Args:
            user_id: User ID
            file: Uploaded file
            project_id: Optional project ID
            title: Optional title
            description: Optional description

        Returns:
            Created document

        Raises:
            DocumentServiceError: If upload fails
        """
        # Validate file
        if not file.filename:
            raise DocumentServiceError("Filename is required")

        # Get file extension
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise DocumentServiceError(
                f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS.keys())}"
            )

        # Get document type and expected mime type
        doc_type, expected_mime = ALLOWED_EXTENSIONS[ext]

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Check file size
        if file_size > MAX_FILE_SIZE:
            raise DocumentServiceError(
                f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Generate unique filename
        file_hash = hashlib.sha256(content).hexdigest()[:16]
        unique_filename = f"{uuid4().hex}_{file_hash}{ext}"

        # Create upload directory
        user_upload_dir = UPLOAD_DIR / user_id
        user_upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = user_upload_dir / unique_filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create document record
        document = Document(
            user_id=user_id,
            project_id=project_id,
            filename=unique_filename,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=file.content_type or expected_mime,
            document_type=doc_type,
            status=DocumentStatus.PENDING,
            title=title or Path(file.filename).stem,
            description=description,
        )

        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)

        # Queue for processing (async task)
        # TODO: Integrate with background task queue
        logger.info(f"Document {document.id} uploaded, queued for processing")

        return document

    async def update(
        self,
        document: Document,
        update_data: DocumentUpdate,
    ) -> Document:
        """Update document metadata."""
        data = update_data.model_dump(exclude_unset=True)

        for field, value in data.items():
            setattr(document, field, value)

        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def delete(self, document: Document) -> None:
        """Delete document and its file."""
        # Delete file
        try:
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete file {document.file_path}: {e}")

        # Delete from database
        await self.db.delete(document)
        await self.db.flush()

    async def update_status(
        self,
        document: Document,
        status: DocumentStatus,
        error_message: Optional[str] = None,
        **kwargs: Any,
    ) -> Document:
        """Update document processing status."""
        document.status = status
        document.error_message = error_message

        if status == DocumentStatus.COMPLETED:
            document.processed_at = datetime.now(timezone.utc)

        # Update additional fields
        for field, value in kwargs.items():
            if hasattr(document, field):
                setattr(document, field, value)

        await self.db.flush()
        await self.db.refresh(document)
        return document

    async def search(
        self,
        user_id: str,
        request: DocumentSearchRequest,
    ) -> dict[str, Any]:
        """
        Search documents using RAG.

        Note: This is a placeholder. Actual implementation requires:
        - Vector store integration (e.g., Milvus, Pinecone)
        - Document chunking and embedding

        Args:
            user_id: User ID
            request: Search request

        Returns:
            Search results
        """
        # Build base query for accessible documents
        query = select(Document).where(
            Document.user_id == user_id,
            Document.status == DocumentStatus.COMPLETED,
        )

        if request.project_id:
            query = query.where(Document.project_id == request.project_id)

        if request.document_ids:
            query = query.where(Document.id.in_(request.document_ids))

        result = await self.db.execute(query)
        documents = list(result.scalars().all())

        # TODO: Implement actual vector search
        # For now, return empty results with structure
        return {
            "query": request.query,
            "results": [],
            "total_results": 0,
        }

    async def get_content(self, document: Document) -> str:
        """
        Get document content as text.

        Note: This is a placeholder. Actual implementation requires:
        - PDF text extraction
        - DOCX parsing
        - etc.
        """
        file_path = Path(document.file_path)

        if not file_path.exists():
            raise DocumentServiceError("Document file not found")

        # Simple text file reading
        if document.document_type in [DocumentType.TXT, DocumentType.MD, DocumentType.CSV]:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                return await f.read()

        # TODO: Implement PDF, DOCX extraction
        raise DocumentServiceError(
            f"Content extraction not implemented for {document.document_type}"
        )
