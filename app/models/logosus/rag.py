"""RAG-related models for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase

if TYPE_CHECKING:
    from app.models.logosus.user import User
    from app.models.logosus.project import Project
    from app.models.logosus.conversation import Conversation


class SearchHistory(LogosusBase):
    """Search query history for analytics and improvement."""

    __tablename__ = "search_history"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.conversations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Query info
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(50), default="default")
    # Types: factual, comparative, exploratory, procedural, default

    # Search parameters
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    min_score: Mapped[float] = mapped_column(Float, default=0.0)
    include_images: Mapped[bool] = mapped_column(default=False)

    # Results summary
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    top_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Reranking info
    reranking_applied: Mapped[bool] = mapped_column(default=False)

    # Document sources (JSON array of document IDs)
    source_documents: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Performance
    search_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # User feedback
    was_helpful: Mapped[Optional[bool]] = mapped_column(nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    project: Mapped[Optional["Project"]] = relationship("Project")

    def __repr__(self) -> str:
        query_preview = self.query[:30] + "..." if len(self.query) > 30 else self.query
        return f"<SearchHistory '{query_preview}'>"


class RAGUsage(LogosusBase):
    """RAG usage statistics - aggregated daily."""

    __tablename__ = "rag_usage"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Period
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Document stats
    documents_uploaded: Mapped[int] = mapped_column(Integer, default=0)
    documents_indexed: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    storage_bytes: Mapped[int] = mapped_column(Integer, default=0)

    # Search stats
    search_count: Mapped[int] = mapped_column(Integer, default=0)
    image_search_count: Mapped[int] = mapped_column(Integer, default=0)

    # Token usage (embeddings)
    embedding_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Performance
    avg_search_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_result_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<RAGUsage {self.user_id[:8]}... {self.date.date()}>"


# Note: Forward references resolved by SQLAlchemy using string names in relationships
