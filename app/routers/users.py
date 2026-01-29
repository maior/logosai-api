"""User management endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.deps import CurrentUser, DBSession
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


class UserSubscription(BaseModel):
    """User subscription information."""
    plan_type: str  # free, pro, premium
    status: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ApiKeyRequest(BaseModel):
    """API key configuration request."""
    provider: str  # openai, anthropic, google
    api_key: str
    model_name: Optional[str] = None


class ApiKeyResponse(BaseModel):
    """API key response (masked)."""
    provider: str
    api_key_masked: str
    model_name: Optional[str] = None
    is_valid: bool


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUser):
    """
    Get current user profile.

    Requires authentication.
    """
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    current_user: CurrentUser,
    db: DBSession,
    update_data: UserUpdate,
):
    """
    Update current user profile.

    Requires authentication.
    """
    # Update user fields
    if update_data.name is not None:
        current_user.name = update_data.name
    if update_data.picture_url is not None:
        current_user.picture_url = update_data.picture_url

    await db.commit()
    await db.refresh(current_user)

    return UserResponse.model_validate(current_user)


@router.get("/me/subscription", response_model=UserSubscription)
async def get_subscription(current_user: CurrentUser):
    """
    Get current user's subscription information.

    Requires authentication.
    """
    return UserSubscription(
        plan_type=current_user.subscription_type,
        status="active" if current_user.is_active else "inactive",
        start_date=current_user.created_at.isoformat() if current_user.created_at else None,
        end_date=(
            current_user.subscription_expires_at.isoformat()
            if current_user.subscription_expires_at
            else None
        ),
    )


@router.get("/me/api-keys", response_model=list[ApiKeyResponse])
async def get_api_keys(current_user: CurrentUser):
    """
    Get user's configured API keys (masked).

    Requires authentication.

    Note: API keys are stored separately. This is a placeholder.
    """
    # TODO: Implement API key storage model
    return []


@router.put("/me/api-keys", response_model=ApiKeyResponse)
async def set_api_key(
    current_user: CurrentUser,
    request: ApiKeyRequest,
):
    """
    Set or update an API key.

    Requires authentication.
    """
    # TODO: Implement API key storage
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key storage not implemented yet"
    )


@router.delete("/me/api-keys/{provider}")
async def delete_api_key(
    current_user: CurrentUser,
    provider: str,
):
    """
    Delete an API key.

    Requires authentication.
    """
    # TODO: Implement API key deletion
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="API key deletion not implemented yet"
    )
