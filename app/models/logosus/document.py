"""Document and DocumentChunk models for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase, TimestampMixin

if TYPE_CHECKING:
    from app.models.logosus.project import Project
    from app.models.logosus.user import User


class Document(LogosusBase, TimestampMixin):
    """Document metadata and RAG indexing status."""

    __tablename__ = "documents"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File info
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, txt, md, docx, etc.
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # bytes
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # Storage path
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Document type detection (from document_metadata.py)
    doc_type: Mapped[str] = mapped_column(String(50), default="general")
    # Types: paper, corporate, presentation, meeting, legal, insurance, report, manual, general

    # Extracted metadata (JSON)
    doc_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #     "title": "...",
    #     "authors": "...",
    #     "organization": "...",
    #     "product_name": "...",  # for insurance
    #     "meeting_date": "...",  # for meeting minutes
    #     "language": "ko"
    # }

    # RAG indexing status
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    index_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Processing stats
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Elasticsearch index info
    es_index: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="documents")
    user: Mapped["User"] = relationship("User")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document {self.file_name} ({self.doc_type})>"


class DocumentChunk(LogosusBase):
    """Document chunk information - linked to Elasticsearch."""

    __tablename__ = "document_chunks"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Chunk info
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Content (stored for quick access, also in ES)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 for dedup

    # Character positions in original document
    start_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Elasticsearch reference
    es_chunk_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk {self.document_id[:8]}... #{self.chunk_index}>"


# Note: Forward references resolved by SQLAlchemy using string names in relationships
