"""Project model for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase, TimestampMixin

if TYPE_CHECKING:
    from app.models.logosus.user import User
    from app.models.logosus.document import Document
    from app.models.logosus.conversation import Conversation


class Project(LogosusBase, TimestampMixin):
    """Project/Workspace for organizing documents and conversations."""

    __tablename__ = "projects"
    __table_args__ = {"schema": "logosus"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    owner_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("logosus.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Emoji or icon name
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Hex color

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    # Settings (JSON)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example settings:
    # {
    #     "default_model": "gpt-4",
    #     "rag_enabled": true,
    #     "allowed_file_types": ["pdf", "txt", "md"]
    # }

    # Stats
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    conversation_count: Mapped[int] = mapped_column(Integer, default=0)
    total_storage_bytes: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="projects")
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="project",
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"


# Note: Forward references resolved by SQLAlchemy using string names in relationships
