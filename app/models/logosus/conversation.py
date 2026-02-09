"""Conversation and Message models for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase, TimestampMixin

if TYPE_CHECKING:
    from app.models.logosus.user import User
    from app.models.logosus.project import Project


class Conversation(LogosusBase, TimestampMixin):
    """Conversation/Chat session."""

    __tablename__ = "conversations"
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

    # Metadata
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100), default="gpt-4")

    # Settings (JSON)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Stats
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id[:8]}... '{self.title or 'Untitled'}'>"


class Message(LogosusBase):
    """Individual message in a conversation."""

    __tablename__ = "messages"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    conversation_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Message content
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_input: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_output: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Agent info (if processed by agent)
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # RAG references (if used)
    references: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # Feedback
    feedback_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # -1 to 1
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    # Alias properties for API compatibility
    @property
    def session_id(self) -> str:
        """Alias for conversation_id for API backward compatibility."""
        return self.conversation_id

    @property
    def agent_type(self) -> Optional[str]:
        """Alias for agent_name for API backward compatibility."""
        return self.agent_name

    @property
    def tokens_used(self) -> Optional[int]:
        """Combined tokens for API compatibility."""
        if self.tokens_input is not None or self.tokens_output is not None:
            return (self.tokens_input or 0) + (self.tokens_output or 0)
        return None

    @property
    def extra_data(self) -> Optional[dict]:
        """Alias for agent_metadata for API compatibility."""
        return self.agent_metadata

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message {self.role}: '{content_preview}'>"


# Note: Forward references resolved by SQLAlchemy using string names in relationships
