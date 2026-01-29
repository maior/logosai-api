"""Marketplace schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============== Agent Schemas ==============

class AgentBase(BaseModel):
    """Base agent schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=10)
    short_description: Optional[str] = Field(None, max_length=500)
    category: str = Field(..., max_length=100)
    tags: Optional[list[str]] = None
    agent_type: str = Field(..., max_length=100)


class AgentCreate(AgentBase):
    """Schema for creating an agent listing."""
    pricing_type: str = Field(default="free")
    price: Optional[Decimal] = Field(default=0, ge=0)
    currency: str = Field(default="USD", max_length=3)
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    screenshots: Optional[list[str]] = None
    agent_config: Optional[dict[str, Any]] = None
    capabilities: Optional[list[str]] = None
    requirements: Optional[dict[str, Any]] = None
    version: str = Field(default="1.0.0", max_length=50)


class AgentUpdate(BaseModel):
    """Schema for updating an agent listing."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    short_description: Optional[str] = Field(None, max_length=500)
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[list[str]] = None
    pricing_type: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    screenshots: Optional[list[str]] = None
    agent_config: Optional[dict[str, Any]] = None
    capabilities: Optional[list[str]] = None
    requirements: Optional[dict[str, Any]] = None
    version: Optional[str] = Field(None, max_length=50)
    changelog: Optional[str] = None


class AgentResponse(AgentBase):
    """Schema for agent response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    creator_id: str
    status: str
    pricing_type: str
    price: Optional[Decimal] = None
    currency: str
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    screenshots: Optional[list[str]] = None
    agent_config: Optional[dict[str, Any]] = None
    capabilities: Optional[list[str]] = None
    requirements: Optional[dict[str, Any]] = None
    version: str
    changelog: Optional[str] = None
    download_count: int
    rating_average: Optional[Decimal] = None
    rating_count: int
    review_count: int
    is_featured: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class AgentListResponse(BaseModel):
    """Schema for agent list response."""
    agents: list[AgentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AgentDetailResponse(AgentResponse):
    """Schema for agent detail response with creator info."""
    creator_name: Optional[str] = None
    creator_picture: Optional[str] = None
    is_purchased: bool = False


# ============== Review Schemas ==============

class ReviewBase(BaseModel):
    """Base review schema."""
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


class ReviewCreate(ReviewBase):
    """Schema for creating a review."""
    pass


class ReviewUpdate(BaseModel):
    """Schema for updating a review."""
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


class ReviewResponse(ReviewBase):
    """Schema for review response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    user_id: str
    is_verified_purchase: bool
    helpful_count: int
    created_at: datetime
    updated_at: datetime
    # User info (joined)
    user_name: Optional[str] = None
    user_picture: Optional[str] = None


class ReviewListResponse(BaseModel):
    """Schema for review list response."""
    reviews: list[ReviewResponse]
    total: int
    average_rating: Optional[float] = None
    rating_distribution: dict[int, int] = {}


# ============== Purchase Schemas ==============

class PurchaseCreate(BaseModel):
    """Schema for creating a purchase."""
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None


class PurchaseResponse(BaseModel):
    """Schema for purchase response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    user_id: str
    pricing_type: str
    amount_paid: Decimal
    currency: str
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime


class PurchaseListResponse(BaseModel):
    """Schema for purchase list response."""
    purchases: list[PurchaseResponse]
    total: int


# ============== Search/Filter Schemas ==============

class AgentSearchRequest(BaseModel):
    """Schema for agent search request."""
    query: Optional[str] = Field(None, max_length=200)
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    pricing_type: Optional[str] = None
    min_rating: Optional[float] = Field(None, ge=0, le=5)
    is_free: Optional[bool] = None
    sort_by: str = Field(default="popular")  # popular, newest, rating, price_asc, price_desc
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class CategoryResponse(BaseModel):
    """Schema for category response."""
    name: str
    slug: str
    count: int
    icon: Optional[str] = None


class CategoryListResponse(BaseModel):
    """Schema for category list response."""
    categories: list[CategoryResponse]


# ============== Stats Schemas ==============

class AgentStatsResponse(BaseModel):
    """Schema for agent statistics."""
    total_downloads: int
    total_revenue: Decimal
    average_rating: Optional[float] = None
    total_reviews: int
    active_subscriptions: int
    downloads_this_month: int
    revenue_this_month: Decimal
