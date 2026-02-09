"""User service for database operations.

Uses logosus schema for user management (logos_api independent).
Users are identified by UUID but looked up by email.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.logosus.user import User, APIKey
from app.schemas.user import UserCreate


class UserService:
    """Service for user-related database operations.

    Uses logosus schema where:
    - id (UUID) is the primary key
    - email is a unique index for lookups
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by UUID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email (primary lookup method)."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=user_data.email,
            name=user_data.name,
            picture=user_data.picture_url,
            provider="email",
            subscription_tier="free",
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_last_login(self, user: User) -> User:
        """Update user's last login timestamp."""
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def create_or_update_google_user(
        self,
        google_id: str,
        email: str,
        name: str,
        picture_url: Optional[str] = None,
    ) -> User:
        """Create or update user from Google OAuth.

        Pattern:
        1. Check if user exists by email
        2. If exists, update last_login_at and profile info
        3. If not, create new user with Google provider
        """
        # Try to find by email
        user = await self.get_by_email(email)

        if user:
            # Update existing user
            user.name = name
            user.picture = picture_url
            user.provider_id = google_id
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(user)
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                picture=picture_url,
                provider="google",
                provider_id=google_id,
                is_active=True,
                is_verified=True,  # Google verified
                subscription_tier="free",
                last_login_at=datetime.now(timezone.utc),
            )
            self.db.add(user)
            await self.db.flush()
            await self.db.refresh(user)

        return user

    async def update_profile(
        self,
        user: User,
        name: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> User:
        """Update user profile."""
        if name is not None:
            user.name = name
        if picture is not None:
            user.picture = picture
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def deactivate(self, user: User) -> User:
        """Deactivate user account."""
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def activate(self, user: User) -> User:
        """Activate user account."""
        user.is_active = True
        await self.db.flush()
        await self.db.refresh(user)
        return user

    # API Key management
    async def create_api_key(
        self,
        user: User,
        name: str,
        scopes: Optional[list[str]] = None,
    ) -> tuple[str, APIKey]:
        """Create a new API key for user.

        Returns:
            Tuple of (full_key, api_key_record)
            Note: full_key is only returned once and should be shown to user
        """
        import json
        full_key, prefix, key_hash = APIKey.generate_key()

        api_key = APIKey(
            user_id=user.id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=json.dumps(scopes) if scopes else None,
            is_active=True,
        )
        self.db.add(api_key)
        await self.db.flush()
        await self.db.refresh(api_key)

        return full_key, api_key

    async def get_api_keys(self, user: User) -> list[APIKey]:
        """Get all API keys for user."""
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.user_id == user.id,
                APIKey.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def revoke_api_key(self, api_key: APIKey) -> None:
        """Revoke an API key."""
        api_key.is_active = False
        await self.db.flush()
