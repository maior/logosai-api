"""Analytics models for logosus schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Float, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.logosus.base import LogosusBase

if TYPE_CHECKING:
    from app.models.logosus.user import User


class UsageStats(LogosusBase):
    """General API usage statistics - aggregated daily."""

    __tablename__ = "usage_stats"
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

    # API calls
    api_calls: Mapped[int] = mapped_column(Integer, default=0)
    api_errors: Mapped[int] = mapped_column(Integer, default=0)

    # Chat usage
    chat_messages: Mapped[int] = mapped_column(Integer, default=0)
    conversations_created: Mapped[int] = mapped_column(Integer, default=0)

    # Token usage
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)

    # Agent usage (JSON: agent_name -> count)
    agent_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example: {"internet_agent": 10, "analysis_agent": 5}

    # Model usage (JSON: model_name -> count)
    model_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example: {"gpt-4": 20, "claude-3": 15}

    # Endpoint usage (JSON: endpoint -> count)
    endpoint_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Example: {"/api/v1/chat/stream": 50, "/api/v1/rag/search": 30}

    # Performance
    avg_response_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<UsageStats {self.user_id[:8]}... {self.date.date()}>"


# Note: Forward references resolved by SQLAlchemy using string names in relationships
