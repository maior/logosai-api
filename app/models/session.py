"""Session model for SQLAlchemy."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Session(Base):
    """Session model for chat conversations.

    Note: This is a new table for logos_api in the logosai schema.
    Uses user_email to reference logosai.users.email.
    """

    __tablename__ = "sessions"
    __table_args__ = {"schema": "logosai"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Foreign keys - uses email to reference users (logos_server uses email as primary key)
    user_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("logosai.users.email", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Project ID (no FK constraint since projects table may not exist)
    project_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
    )

    # Metadata
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions", foreign_keys=[user_email])

    # Compatibility property
    @property
    def user_id(self) -> str:
        """Return user_email for compatibility."""
        return self.user_email
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, title={self.title})>"


# Import for type hints
from app.models.user import User
from app.models.project import Project
from app.models.message import Message
