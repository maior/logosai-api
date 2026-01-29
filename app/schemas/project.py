"""Project schemas for request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """Base project schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""
    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)
    is_public: Optional[bool] = None
    is_archived: Optional[bool] = None


class ProjectResponse(ProjectBase):
    """Schema for project response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    is_public: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Schema for project list response."""
    projects: list[ProjectResponse]
    total: int


class ProjectShareRequest(BaseModel):
    """Schema for sharing a project."""
    user_email: str
    permission: str = Field(default="read", pattern=r'^(read|write|admin)$')
