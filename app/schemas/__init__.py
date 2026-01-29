"""Pydantic schemas package."""

from app.schemas.auth import (
    GoogleLoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenResponse,
    TokenPayload,
)
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserInDB,
)
from app.schemas.project import (
    ProjectBase,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectShareRequest,
    ProjectUpdate,
)
from app.schemas.session import (
    MessageBase,
    MessageCreate,
    MessageListResponse,
    MessageResponse,
    SessionBase,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)

__all__ = [
    # Auth schemas
    "GoogleLoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    "TokenResponse",
    "TokenPayload",
    # User schemas
    "UserBase",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    "UserInDB",
    # Project schemas
    "ProjectBase",
    "ProjectCreate",
    "ProjectListResponse",
    "ProjectResponse",
    "ProjectShareRequest",
    "ProjectUpdate",
    # Session schemas
    "SessionBase",
    "SessionCreate",
    "SessionListResponse",
    "SessionResponse",
    "SessionUpdate",
    # Message schemas
    "MessageBase",
    "MessageCreate",
    "MessageListResponse",
    "MessageResponse",
]
