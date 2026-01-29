"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.auth import (
    GoogleLoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter()


@router.post("/login/google", response_model=LoginResponse)
async def google_login(
    request: GoogleLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Login with Google OAuth.

    - Verifies Google ID token
    - Creates or updates user in database
    - Returns JWT tokens and user info
    """
    # Verify Google token
    google_info = await AuthService.verify_google_token(request.credential)

    if not google_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google credential",
        )

    # Create or update user
    user_service = UserService(db)
    user = await user_service.create_or_update_google_user(
        google_id=google_info.sub,
        email=google_info.email,
        name=google_info.name,
        picture_url=google_info.picture,
    )

    # Commit the transaction
    await db.commit()

    # Create tokens
    tokens = AuthService.create_tokens(user.id, user.email)

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=tokens,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token.

    - Verifies refresh token
    - Returns new access token
    """
    payload = AuthService.verify_refresh_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Create new access token
    tokens = AuthService.create_access_token_from_refresh(payload)

    # Include original refresh token in response
    tokens.refresh_token = request.refresh_token

    return tokens


@router.post("/logout")
async def logout():
    """
    Logout user.

    Note: JWT tokens are stateless, so logout is handled client-side
    by removing the tokens. This endpoint is provided for completeness.
    """
    return {"message": "Logged out successfully"}
