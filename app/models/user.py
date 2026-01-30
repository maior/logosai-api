"""User model for SQLAlchemy.

Matches logos_server's logosai.users table schema.
Uses email as primary identifier (not UUID id).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """User model matching logos_server's logosai.users table.

    Schema (actual database columns):
    - email (PK): User's email address
    - name: User's display name
    - picture_url: Profile picture URL
    - created_at: Account creation timestamp
    - last_login_at: Last login timestamp
    - is_active: Whether user is active
    - subscription_type: Plan type (free, pro, enterprise)
    - updated_at: Last update timestamp
    - order_id: Order ID for subscription
    """

    __tablename__ = "users"
    __table_args__ = {"schema": "logosai"}

    # Email is the primary key (matches logos_server)
    email: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False),  # timestamp without time zone in DB
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    # User status
    is_active: Mapped[Optional[bool]] = mapped_column(default=True, nullable=True)

    # Subscription
    subscription_type: Mapped[Optional[str]] = mapped_column(String(50), default="free", nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships (bidirectional with Project, Session, and Marketplace models)
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="[Project.owner_email]",
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[Session.user_email]",
    )
    marketplace_agents: Mapped[list["MarketplaceAgent"]] = relationship(
        "MarketplaceAgent",
        back_populates="creator",
        cascade="all, delete-orphan",
        foreign_keys="[MarketplaceAgent.creator_email]",
    )
    agent_reviews: Mapped[list["AgentReview"]] = relationship(
        "AgentReview",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[AgentReview.user_email]",
    )
    agent_purchases: Mapped[list["AgentPurchase"]] = relationship(
        "AgentPurchase",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[AgentPurchase.user_email]",
    )

    # Computed properties for compatibility
    @property
    def id(self) -> str:
        """Return email as id for compatibility."""
        return self.email

    @property
    def is_verified(self) -> bool:
        """Always verified (logos_server doesn't have this field)."""
        return True

    def __repr__(self) -> str:
        return f"<User(email={self.email})>"


class UserHistory(Base):
    """User login history matching logos_server's logosai.user_history table."""

    __tablename__ = "user_history"
    __table_args__ = {"schema": "logosai"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False)
    access_type: Mapped[str] = mapped_column(String(50), nullable=False)  # login, logout
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # success, failure
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True,
    )


class SubscriptionPlan(Base):
    """Subscription plans matching logos_server's logosai.subscription_plans table."""

    __tablename__ = "subscription_plans"
    __table_args__ = {"schema": "logosai"}

    plan_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    max_files: Mapped[int] = mapped_column(default=10)
    monthly_search_limit: Mapped[int] = mapped_column(default=100)
    storage_limit: Mapped[int] = mapped_column(default=1024)  # MB
