"""Message model for SQLAlchemy."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
import enum


class MessageRole(str, enum.Enum):
    """Message role types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(Base):
    """Message model for chat messages."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Foreign key
    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Extra data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    agent_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role})>"


# Import for type hints
from app.models.session import Session
