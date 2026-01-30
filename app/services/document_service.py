"""Document service for file management and RAG operations.

Matches logos_server's user_files table structure.
"""

import logging
import os
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import aiofiles
from fastapi import UploadFile
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.document import UserFile
from app.services.rag import RAGService

logger = logging.getLogger(__name__)

# File storage configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv", ".json"}


class DocumentServiceError(Exception):
    """Document service error."""
    pass


class DocumentService:
    """Service for document-related operations using user_files table."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._rag_service: Optional[RAGService] = None

    @property
    def rag_service(self) -> RAGService:
        """Get RAG service (lazy initialization)."""
        if self._rag_service is None:
            self._rag_service = RAGService()
        return self._rag_service

    async def get_by_id(self, file_id: str) -> Optional[UserFile]:
        """Get file by ID."""
        result = await self.db.execute(
            select(UserFile).where(
                UserFile.file_id == file_id,
                UserFile.is_deleted != True,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_and_user(
        self,
        file_id: str,
        user_email: str,
    ) -> Optional[UserFile]:
        """Get file by ID and user email."""
        result = await self.db.execute(
            select(UserFile).where(
                UserFile.file_id == file_id,
                UserFile.user_email == user_email,
                UserFile.is_deleted != True,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_email: str,
        project_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[UserFile], int]:
        """List files by user email."""
        conditions = [
            UserFile.user_email == user_email,
            UserFile.is_deleted != True,
        ]

        if project_id:
            conditions.append(UserFile.project_id == project_id)

        query = select(UserFile).where(and_(*conditions))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = query.order_by(UserFile.upload_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        files = list(result.scalars().all())

        return files, total

    async def upload(
        self,
        user_email: str,
        file: UploadFile,
        project_id: str,
        project_name: Optional[str] = None,
    ) -> UserFile:
        """
        Upload a document file.

        Args:
            user_email: User email
            file: Uploaded file
            project_id: Project ID (required)
            project_name: Optional project name

        Returns:
            Created UserFile record

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
                f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Read file content
        content = await file.read()
        file_size = len(content)

        # Check file size
        if file_size > MAX_FILE_SIZE:
            raise DocumentServiceError(
                f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Determine file type
        file_type = ext.lstrip(".")

        # Generate file ID
        file_id = str(uuid4())

        # Create upload directory
        project_upload_dir = UPLOAD_DIR / project_id
        project_upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file (use original filename)
        file_path = project_upload_dir / file.filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create file record
        user_file = UserFile(
            file_id=file_id,
            project_id=project_id,
            project_name=project_name,
            user_email=user_email,
            file_name=file.filename,
            file_size=file_size,
            file_type=file_type,
            is_deleted=False,
        )

        self.db.add(user_file)
        await self.db.flush()
        await self.db.refresh(user_file)

        logger.info(f"File {file_id} uploaded: {file.filename}")

        return user_file

    async def upload_base64(
        self,
        user_email: str,
        file_name: str,
        file_content_base64: str,
        project_id: str,
        project_name: Optional[str] = None,
    ) -> UserFile:
        """
        Upload a document from base64 content (logos_server compatible).

        Args:
            user_email: User email
            file_name: Original filename
            file_content_base64: Base64 encoded file content
            project_id: Project ID
            project_name: Optional project name

        Returns:
            Created UserFile record
        """
        # Decode base64
        try:
            content = base64.b64decode(file_content_base64)
        except Exception as e:
            raise DocumentServiceError(f"Invalid base64 content: {e}")

        # Get file extension
        ext = Path(file_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise DocumentServiceError(
                f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            raise DocumentServiceError(
                f"File too large. Maximum: {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        file_type = ext.lstrip(".")
        file_id = str(uuid4())

        # Create upload directory
        project_upload_dir = UPLOAD_DIR / project_id
        project_upload_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = project_upload_dir / file_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # Create file record
        user_file = UserFile(
            file_id=file_id,
            project_id=project_id,
            project_name=project_name,
            user_email=user_email,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            is_deleted=False,
        )

        self.db.add(user_file)
        await self.db.flush()
        await self.db.refresh(user_file)

        logger.info(f"File {file_id} uploaded (base64): {file_name}")

        return user_file

    async def delete(self, user_file: UserFile) -> None:
        """Soft delete file (mark as deleted)."""
        user_file.is_deleted = True
        user_file.deletion_date = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(user_file)

        logger.info(f"File {user_file.file_id} marked as deleted")

    async def hard_delete(self, user_file: UserFile) -> None:
        """Permanently delete file and its record."""
        # Delete from RAG index
        try:
            await self.delete_from_rag(user_file)
        except Exception as e:
            logger.warning(f"Failed to delete RAG data for {user_file.file_id}: {e}")

        # Delete physical file
        try:
            file_path = UPLOAD_DIR / user_file.project_id / user_file.file_name
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete file: {e}")

        # Delete from database
        await self.db.delete(user_file)
        await self.db.flush()

    async def process_for_rag(
        self,
        user_file: UserFile,
        include_images: bool = True,
    ) -> dict[str, Any]:
        """
        Process file for RAG indexing.

        Args:
            user_file: File to process
            include_images: Whether to process images (for PDFs)

        Returns:
            Processing statistics
        """
        file_path = UPLOAD_DIR / user_file.project_id / user_file.file_name

        if not file_path.exists():
            raise DocumentServiceError(f"File not found: {file_path}")

        try:
            # Use enhanced PDF processing for PDF files
            if user_file.file_type == "pdf" and include_images:
                stats = await self.rag_service.index_pdf_with_images(
                    file_path=str(file_path),
                    file_name=user_file.file_name,
                    user_id=user_file.user_email,
                    document_id=user_file.file_id,
                    project_id=user_file.project_id,
                )
            else:
                stats = await self.rag_service.index_document(
                    file_path=str(file_path),
                    file_name=user_file.file_name,
                    user_id=user_file.user_email,
                    document_id=user_file.file_id,
                    project_id=user_file.project_id,
                )

            logger.info(f"File {user_file.file_id} indexed to RAG: {stats}")
            return stats

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process file {user_file.file_id}: {error_msg}")
            raise DocumentServiceError(f"RAG processing failed: {error_msg}")

    async def search(
        self,
        user_email: str,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> dict[str, Any]:
        """
        Search documents using RAG hybrid search.

        Args:
            user_email: User email
            query: Search query
            project_id: Optional project ID filter
            top_k: Number of results
            min_score: Minimum relevance score

        Returns:
            Search results in website-compatible format
        """
        from uuid import uuid4

        try:
            results = await self.rag_service.search(
                query=query,
                user_id=user_email,
                project_id=project_id,
                top_k=top_k,
                min_score=min_score,
            )

            chunks = []
            references = []
            pdf_names = set()

            for r in results:
                metadata = r.metadata or {}
                file_name = metadata.get("file_name", "")

                chunks.append({
                    "file_id": metadata.get("document_id", ""),
                    "file_name": file_name,
                    "content": r.content,
                    "page": metadata.get("page"),
                    "score": r.score,
                    "metadata": metadata,
                })

                # Collect references and pdf names for website compatibility
                if r.content:
                    references.append(r.content[:200] + "..." if len(r.content) > 200 else r.content)
                if file_name and file_name.endswith(".pdf"):
                    pdf_names.add(file_name)

            # Return website-compatible format
            return {
                "msg": "success",
                "code": 0,
                "data": {
                    "query": query,
                    "results": chunks,
                    "total_results": len(chunks),
                    "references": references,
                    "pdf_names": list(pdf_names),
                    "usage_id": str(uuid4()),
                },
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                "msg": "error",
                "code": 500,
                "data": {
                    "query": query,
                    "results": [],
                    "total_results": 0,
                    "references": [],
                    "pdf_names": [],
                    "error": str(e),
                },
            }

    async def get_content(self, user_file: UserFile) -> str:
        """Get file content as text."""
        file_path = UPLOAD_DIR / user_file.project_id / user_file.file_name

        if not file_path.exists():
            raise DocumentServiceError("File not found")

        try:
            processor = self.rag_service.document_processor
            chunks = await processor.process_file(
                file_path=str(file_path),
                file_name=user_file.file_name,
                user_id=user_file.user_email,
                document_id=user_file.file_id,
                project_id=user_file.project_id,
            )

            content = "\n\n".join(chunk.page_content for chunk in chunks)
            return content

        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            raise DocumentServiceError(f"Failed to extract content: {str(e)}")

    async def delete_from_rag(self, user_file: UserFile) -> int:
        """Delete file chunks from RAG index."""
        try:
            deleted = await self.rag_service.delete_document(
                document_id=user_file.file_id,
                user_id=user_file.user_email,
            )
            logger.info(f"Deleted {deleted} chunks for file {user_file.file_id}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete RAG data: {e}")
            return 0

    async def check_rag_health(self) -> dict[str, Any]:
        """Check RAG system health status."""
        return await self.rag_service.health_check()
