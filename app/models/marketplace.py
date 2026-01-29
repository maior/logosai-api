"""Marketplace models for SQLAlchemy."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentStatus(str, enum.Enum):
    """Agent listing status."""
    DRAFT = "draft"
    PENDING = "pending"  # Pending review
    PUBLISHED = "published"
    REJECTED = "rejected"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class PricingType(str, enum.Enum):
    """Agent pricing type."""
    FREE = "free"
    ONE_TIME = "one_time"
    SUBSCRIPTION = "subscription"
    USAGE_BASED = "usage_based"


class MarketplaceAgent(Base):
    """Marketplace agent listing model."""

    __tablename__ = "marketplace_agents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Creator/Publisher
    creator_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Status
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus),
        nullable=False,
        default=AgentStatus.DRAFT,
    )

    # Categorization
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(String(50)), nullable=True)

    # Pricing
    pricing_type: Mapped[PricingType] = mapped_column(
        Enum(PricingType),
        nullable=False,
        default=PricingType.FREE,
    )
    price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        default=0,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Media
    icon_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    screenshots: Mapped[Optional[list]] = mapped_column(ARRAY(String(500)), nullable=True)

    # Agent configuration
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    capabilities: Mapped[Optional[list]] = mapped_column(ARRAY(String(100)), nullable=True)
    requirements: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Version info
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stats (denormalized for performance)
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rating_average: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Visibility
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="marketplace_agents")
    reviews: Mapped[list["AgentReview"]] = relationship(
        "AgentReview",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    purchases: Mapped[list["AgentPurchase"]] = relationship(
        "AgentPurchase",
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MarketplaceAgent(id={self.id}, name={self.name})>"


class AgentReview(Base):
    """Agent review model."""

    __tablename__ = "agent_reviews"
    __table_args__ = (
        UniqueConstraint("agent_id", "user_id", name="uq_agent_user_review"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # References
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("marketplace_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Review content
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Moderation
    is_verified_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Helpfulness
    helpful_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
    agent: Mapped["MarketplaceAgent"] = relationship("MarketplaceAgent", back_populates="reviews")
    user: Mapped["User"] = relationship("User", back_populates="agent_reviews")

    def __repr__(self) -> str:
        return f"<AgentReview(id={self.id}, rating={self.rating})>"


class AgentPurchase(Base):
    """Agent purchase/subscription model."""

    __tablename__ = "agent_purchases"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # References
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("marketplace_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Purchase info
    pricing_type: Mapped[PricingType] = mapped_column(
        Enum(PricingType),
        nullable=False,
    )
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=0,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Subscription specific
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Transaction
    transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    agent: Mapped["MarketplaceAgent"] = relationship("MarketplaceAgent", back_populates="purchases")
    user: Mapped["User"] = relationship("User", back_populates="agent_purchases")

    def __repr__(self) -> str:
        return f"<AgentPurchase(id={self.id}, agent_id={self.agent_id})>"


# Import for type hints
from app.models.user import User
