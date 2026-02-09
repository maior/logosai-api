"""Session model for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase, TimestampMixin

if TYPE_CHECKING:
    from app.models.logosus.user import User


class Session(LogosusBase, TimestampMixin):
    """User session for authentication."""

    __tablename__ = "sessions"
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

    # Token info
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Device/Client info
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 compatible
    device_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User")

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self) -> str:
        return f"<Session {self.id[:8]}... user={self.user_id[:8]}...>"


# Note: Forward references resolved by SQLAlchemy using string names in relationships
