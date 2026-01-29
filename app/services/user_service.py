"""User service for database operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate


class UserService:
    """Service for user-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_google_id(self, google_id: str) -> Optional[User]:
        """Get user by Google ID."""
        result = await self.db.execute(
            select(User).where(User.google_id == google_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=user_data.email,
            name=user_data.name,
            picture_url=user_data.picture_url,
            google_id=user_data.google_id,
            hashed_password=(
                hash_password(user_data.password)
                if user_data.password
                else None
            ),
            is_verified=True if user_data.google_id else False,
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
        """Create or update user from Google OAuth."""
        # Try to find by google_id first
        user = await self.get_by_google_id(google_id)

        if user:
            # Update existing user
            user.name = name
            user.picture_url = picture_url
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(user)
            return user

        # Try to find by email (link existing account)
        user = await self.get_by_email(email)

        if user:
            # Link Google account to existing user
            user.google_id = google_id
            user.name = name
            user.picture_url = picture_url
            user.is_verified = True
            user.last_login_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(user)
            return user

        # Create new user
        user_data = UserCreate(
            email=email,
            name=name,
            picture_url=picture_url,
            google_id=google_id,
        )
        return await self.create(user_data)
