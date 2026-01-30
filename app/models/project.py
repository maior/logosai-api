"""Project model for SQLAlchemy."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    """Project model for organizing user work.

    Note: This table doesn't exist in logos_server (logosai schema).
    It's a new table for logos_api to manage project organization.
    Uses owner_email to reference logosai.users.email.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Owner - references users by email (logos_server uses email as primary key)
    owner_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("logosai.users.email", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Settings
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

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

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="projects", foreign_keys=[owner_email])
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    # Note: user_files uses project_id as varchar, not foreign key

    # Compatibility property
    @property
    def owner_id(self) -> str:
        """Return owner_email for compatibility."""
        return self.owner_email

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"


# Import for type hints
from app.models.user import User
from app.models.session import Session
