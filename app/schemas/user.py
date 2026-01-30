"""User schemas for request/response validation.

Matches logos_server's logosai.users table schema.
Uses email as primary identifier.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    """Base user schema matching logos_server."""
    email: EmailStr
    name: str
    picture_url: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user.

    Matches logos_server's INSERT INTO logosai.users pattern.
    No password or google_id columns in logos_server.
    """
    pass


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    name: Optional[str] = None
    picture_url: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response.

    Matches logos_server's logosai.users table columns.
    Uses email as id for compatibility.
    """
    model_config = ConfigDict(from_attributes=True)

    # email is the id in logos_server
    subscription_type: Optional[str] = "free"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    is_active: Optional[bool] = True
    order_id: Optional[str] = None

    # Computed properties for API compatibility
    @property
    def id(self) -> str:
        """Return email as id."""
        return self.email

    @property
    def is_verified(self) -> bool:
        """Always verified."""
        return True


class UserInDB(UserResponse):
    """Schema for user in database.

    Same as UserResponse since logos_server doesn't have
    password or other sensitive fields in the users table.
    """
    pass
