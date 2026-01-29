"""Authentication schemas."""

from typing import Optional

from pydantic import BaseModel, EmailStr


class GoogleLoginRequest(BaseModel):
    """Google OAuth login request."""
    credential: str  # Google ID token


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # User ID
    email: EmailStr
    exp: int
    type: str  # "access" or "refresh"


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class LoginResponse(BaseModel):
    """Complete login response."""
    user: "UserResponse"
    tokens: TokenResponse


# Import here to avoid circular imports
from app.schemas.user import UserResponse
LoginResponse.model_rebuild()
