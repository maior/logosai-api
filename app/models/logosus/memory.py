"""User memory models for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase, TimestampMixin

if TYPE_CHECKING:
    from app.models.logosus.user import User
    from app.models.logosus.conversation import Conversation


class UserMemory(LogosusBase, TimestampMixin):
    """User memory for personalized AI responses.

    Stores facts, preferences, context, and instructions extracted
    from conversations. Used to inject user context into LLM prompts.
    """

    __tablename__ = "user_memories"
    __table_args__ = (
        {"schema": "logosus"},
    )

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

    # Memory content
    memory_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )  # 'fact', 'preference', 'context', 'instruction'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
    )  # 'language', 'work', 'hobby', 'domain', etc.

    # Scoring
    importance: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0 ~ 1.0

    # Source tracking
    source_conversation_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.conversations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Usage tracking
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Extra metadata
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memories")
    source_conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation",
    )

    def __repr__(self) -> str:
        preview = self.content[:40] + "..." if len(self.content) > 40 else self.content
        return f"<UserMemory [{self.memory_type}] '{preview}'>"
