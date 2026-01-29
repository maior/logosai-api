"""Document processor for chunking and parsing files."""

import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiofiles
from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Process documents for RAG indexing.

    Supports: PDF, TXT, Markdown, DOCX, CSV
    Performs: Loading, text extraction, chunking
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv", ".json"}

    def __init__(
        self,
        chunk_size: int = settings.chunk_size,
        chunk_overlap: int = settings.chunk_overlap,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )

    async def process_file(
        self,
        file_path: str,
        file_name: str,
        user_id: str,
        document_id: str,
        project_id: Optional[str] = None,
    ) -> list[LangchainDocument]:
        """
        Process a file and return chunked documents.

        Args:
            file_path: Path to the file
            file_name: Original file name
            user_id: Owner user ID
            document_id: Document ID in database
            project_id: Optional project ID

        Returns:
            List of LangChain documents with content and metadata
        """
        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        # Load document based on type
        documents = await self._load_document(file_path, ext)

        if not documents:
            raise ValueError(f"Failed to load documents from {file_name}")

        # Check for empty content
        if all(not doc.page_content.strip() for doc in documents):
            raise ValueError(f"Document appears to be empty: {file_name}")

        # Split into chunks
        chunks = self.text_splitter.split_documents(documents)

        # Add metadata
        file_metadata = {
            "file_name": file_name,
            "file_type": ext[1:],  # Remove dot
            "document_id": document_id,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if project_id:
            file_metadata["project_id"] = project_id

        for i, chunk in enumerate(chunks):
            chunk.metadata.update(file_metadata)
            chunk.metadata["chunk_index"] = i
            chunk.metadata["page"] = chunk.metadata.get("page", 0) + 1

        logger.info(f"Processed {file_name}: {len(chunks)} chunks created")
        return chunks

    async def process_file_content(
        self,
        content: bytes,
        file_name: str,
        user_id: str,
        document_id: str,
        project_id: Optional[str] = None,
    ) -> list[LangchainDocument]:
        """
        Process file content from bytes.

        Args:
            content: File content as bytes
            file_name: Original file name
            user_id: Owner user ID
            document_id: Document ID
            project_id: Optional project ID

        Returns:
            List of chunked LangChain documents
        """
        ext = Path(file_name).suffix.lower()

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            return await self.process_file(
                file_path=temp_path,
                file_name=file_name,
                user_id=user_id,
                document_id=document_id,
                project_id=project_id,
            )
        finally:
            # Clean up temp file
            os.unlink(temp_path)

    async def _load_document(
        self,
        file_path: str,
        ext: str,
    ) -> list[LangchainDocument]:
        """Load document based on file type."""
        try:
            if ext == ".pdf":
                return await self._load_pdf(file_path)
            elif ext in {".txt", ".md"}:
                return await self._load_text(file_path)
            elif ext == ".docx":
                return await self._load_docx(file_path)
            elif ext == ".csv":
                return await self._load_csv(file_path)
            elif ext == ".json":
                return await self._load_json(file_path)
            else:
                raise ValueError(f"Unsupported extension: {ext}")
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            raise

    async def _load_pdf(self, file_path: str) -> list[LangchainDocument]:
        """Load PDF document using PyMuPDF."""
        import fitz  # PyMuPDF

        documents = []
        doc = fitz.open(file_path)

        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                documents.append(
                    LangchainDocument(
                        page_content=text,
                        metadata={"page": page_num, "source": file_path},
                    )
                )

        doc.close()
        return documents

    async def _load_text(self, file_path: str) -> list[LangchainDocument]:
        """Load text or markdown file."""
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        return [
            LangchainDocument(
                page_content=content,
                metadata={"source": file_path},
            )
        ]

    async def _load_docx(self, file_path: str) -> list[LangchainDocument]:
        """Load DOCX document."""
        from docx import Document as DocxDocument

        doc = DocxDocument(file_path)
        full_text = []

        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text)

        content = "\n\n".join(full_text)

        return [
            LangchainDocument(
                page_content=content,
                metadata={"source": file_path},
            )
        ]

    async def _load_csv(self, file_path: str) -> list[LangchainDocument]:
        """Load CSV file."""
        import csv

        documents = []

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        reader = csv.DictReader(content.splitlines())
        for i, row in enumerate(reader):
            # Convert row to text
            text = " | ".join(f"{k}: {v}" for k, v in row.items() if v)
            if text.strip():
                documents.append(
                    LangchainDocument(
                        page_content=text,
                        metadata={"source": file_path, "row": i},
                    )
                )

        return documents

    async def _load_json(self, file_path: str) -> list[LangchainDocument]:
        """Load JSON file."""
        import json

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        data = json.loads(content)

        # Convert to text representation
        if isinstance(data, list):
            documents = []
            for i, item in enumerate(data):
                text = json.dumps(item, ensure_ascii=False, indent=2)
                documents.append(
                    LangchainDocument(
                        page_content=text,
                        metadata={"source": file_path, "index": i},
                    )
                )
            return documents
        else:
            text = json.dumps(data, ensure_ascii=False, indent=2)
            return [
                LangchainDocument(
                    page_content=text,
                    metadata={"source": file_path},
                )
            ]

    def get_chunk_stats(self, documents: list[LangchainDocument]) -> dict[str, Any]:
        """Get statistics about chunked documents."""
        if not documents:
            return {"chunk_count": 0, "total_chars": 0, "avg_chunk_size": 0}

        total_chars = sum(len(doc.page_content) for doc in documents)
        return {
            "chunk_count": len(documents),
            "total_chars": total_chars,
            "avg_chunk_size": total_chars // len(documents),
            "min_chunk_size": min(len(doc.page_content) for doc in documents),
            "max_chunk_size": max(len(doc.page_content) for doc in documents),
        }
