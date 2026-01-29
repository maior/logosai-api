"""Document schemas for request/response validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    """Base document schema."""
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None


class DocumentCreate(DocumentBase):
    """Schema for creating a document (metadata only, file uploaded separately)."""
    project_id: Optional[str] = None


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    project_id: Optional[str] = None


class DocumentResponse(DocumentBase):
    """Schema for document response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    project_id: Optional[str] = None

    # File info
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    document_type: str

    # Processing status
    status: str
    error_message: Optional[str] = None

    # Content metadata
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    language: Optional[str] = None

    # Vector store info
    chunk_count: Optional[int] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Schema for document list response."""
    documents: list[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    """Schema for upload response."""
    document: DocumentResponse
    message: str


class DocumentSearchRequest(BaseModel):
    """Schema for RAG search request."""
    query: str = Field(..., min_length=1, max_length=1000)
    project_id: Optional[str] = None
    document_ids: Optional[list[str]] = None
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class DocumentChunk(BaseModel):
    """Schema for document chunk in search results."""
    document_id: str
    document_title: Optional[str] = None
    content: str
    page_number: Optional[int] = None
    score: float
    metadata: Optional[dict[str, Any]] = None


class DocumentSearchResponse(BaseModel):
    """Schema for RAG search response."""
    query: str
    results: list[DocumentChunk]
    total_results: int


class DocumentProcessingStatus(BaseModel):
    """Schema for document processing status."""
    document_id: str
    status: str
    progress: int = Field(ge=0, le=100)
    message: Optional[str] = None
    error: Optional[str] = None
