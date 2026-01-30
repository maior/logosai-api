"""Authentication endpoints."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth

from app.database import get_db
from app.config import settings
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

# OAuth client setup
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


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


# ============================================================
# OAuth Callback 방식 (NextAuth 스타일)
# ============================================================

@router.get("/google")
async def google_oauth_start(
    request: Request,
    redirect_uri: Optional[str] = Query(None, description="Callback redirect URI"),
):
    """
    Start Google OAuth flow.

    Redirects to Google login page.
    After login, Google will redirect to /callback/google
    """
    # Use provided redirect_uri or default
    callback_url = redirect_uri or str(request.url_for('google_oauth_callback'))

    # Store callback URL in session for later use
    request.session['redirect_uri'] = redirect_uri or '/'

    return await oauth.google.authorize_redirect(request, callback_url)


@router.get("/callback/google")
async def google_oauth_callback(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Google OAuth callback handler.

    - Exchanges authorization code for tokens
    - Creates or updates user
    - Returns JWT tokens or redirects with tokens
    """
    try:
        # Get token from Google
        token = await oauth.google.authorize_access_token(request)

        # Get user info from token
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user info from Google",
            )

        # Create or update user
        user_service = UserService(db)
        user = await user_service.create_or_update_google_user(
            google_id=user_info['sub'],
            email=user_info['email'],
            name=user_info.get('name', user_info['email'].split('@')[0]),
            picture_url=user_info.get('picture'),
        )

        await db.commit()

        # Create JWT tokens
        tokens = AuthService.create_tokens(str(user.id), user.email)

        # Get redirect URI from session
        redirect_uri = request.session.pop('redirect_uri', '/')

        # If redirect_uri is a full URL, redirect with tokens as query params
        if redirect_uri.startswith('http'):
            redirect_url = f"{redirect_uri}?access_token={tokens.access_token}&refresh_token={tokens.refresh_token}"
            return RedirectResponse(url=redirect_url)

        # Otherwise return JSON response
        return LoginResponse(
            user=UserResponse.model_validate(user),
            tokens=tokens,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OAuth callback failed: {str(e)}",
        )
