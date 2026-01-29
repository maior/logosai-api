"""User schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    name: str
    picture_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: Optional[str] = None
    google_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    name: Optional[str] = None
    picture_url: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    is_verified: bool
    subscription_type: str
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UserInDB(UserResponse):
    """Schema for user in database (includes sensitive fields)."""
    hashed_password: Optional[str] = None
    google_id: Optional[str] = None
