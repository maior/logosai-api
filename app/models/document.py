"""Document model for SQLAlchemy - matches logos_server user_files table."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, String, BigInteger, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserFile(Base):
    """UserFile model - maps to existing user_files table from logos_server."""

    __tablename__ = "user_files"

    file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    project_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    project_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    user_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )

    file_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    upload_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    is_deleted: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )

    deletion_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<UserFile(file_id={self.file_id}, file_name={self.file_name})>"


# Alias for backward compatibility
Document = UserFile
