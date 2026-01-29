"""Authentication service for handling login logic."""

import httpx
from typing import Optional

from app.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.schemas.auth import TokenResponse
from app.schemas.user import UserResponse


class GoogleTokenInfo:
    """Google token information."""

    def __init__(
        self,
        sub: str,  # Google user ID
        email: str,
        name: str,
        picture: Optional[str] = None,
        email_verified: bool = False,
    ):
        self.sub = sub
        self.email = email
        self.name = name
        self.picture = picture
        self.email_verified = email_verified


class AuthService:
    """Service for authentication operations."""

    @staticmethod
    async def verify_google_token(credential: str) -> Optional[GoogleTokenInfo]:
        """
        Verify Google ID token and extract user info.

        Args:
            credential: Google ID token from frontend

        Returns:
            GoogleTokenInfo if valid, None otherwise
        """
        try:
            # Verify token with Google
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
                )

                if response.status_code != 200:
                    return None

                data = response.json()

                # Verify audience (client ID)
                if data.get("aud") != settings.google_client_id:
                    # In development, allow any audience
                    if settings.environment != "development":
                        return None

                return GoogleTokenInfo(
                    sub=data["sub"],
                    email=data["email"],
                    name=data.get("name", data["email"].split("@")[0]),
                    picture=data.get("picture"),
                    email_verified=data.get("email_verified", False),
                )
        except Exception:
            return None

    @staticmethod
    def create_tokens(user_id: str, email: str) -> TokenResponse:
        """
        Create access and refresh tokens for a user.

        Args:
            user_id: User's ID
            email: User's email

        Returns:
            TokenResponse with both tokens
        """
        token_data = {"sub": user_id, "email": email}

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    @staticmethod
    def verify_refresh_token(token: str) -> Optional[dict]:
        """
        Verify refresh token and return payload.

        Args:
            token: Refresh token

        Returns:
            Token payload if valid, None otherwise
        """
        payload = verify_token(token)

        if not payload:
            return None

        # Check token type
        if payload.get("type") != "refresh":
            return None

        return payload

    @staticmethod
    def create_access_token_from_refresh(payload: dict) -> TokenResponse:
        """
        Create new access token from refresh token payload.

        Args:
            payload: Verified refresh token payload

        Returns:
            TokenResponse with new access token (same refresh token)
        """
        token_data = {
            "sub": payload["sub"],
            "email": payload["email"],
        }

        access_token = create_access_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token="",  # Don't return refresh token on refresh
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
