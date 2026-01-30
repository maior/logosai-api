"""Marketplace service for agent listing operations."""

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.marketplace import (
    AgentPurchase,
    AgentReview,
    AgentStatus,
    MarketplaceAgent,
    PricingType,
)
from app.models.user import User
from app.schemas.marketplace import (
    AgentCreate,
    AgentSearchRequest,
    AgentUpdate,
    PurchaseCreate,
    ReviewCreate,
    ReviewUpdate,
)

logger = logging.getLogger(__name__)


class MarketplaceServiceError(Exception):
    """Marketplace service error."""
    pass


class MarketplaceService:
    """Service for marketplace operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============== Agent Operations ==============

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
        return f"{slug}-{uuid4().hex[:8]}"

    async def create_agent(
        self,
        creator_email: str,
        data: AgentCreate,
    ) -> MarketplaceAgent:
        """Create a new agent listing."""
        # Validate pricing
        pricing_type = PricingType(data.pricing_type)
        if pricing_type != PricingType.FREE and (data.price is None or data.price <= 0):
            raise MarketplaceServiceError("Price is required for paid agents")

        agent = MarketplaceAgent(
            creator_email=creator_email,
            name=data.name,
            slug=self._generate_slug(data.name),
            description=data.description,
            short_description=data.short_description,
            category=data.category,
            tags=data.tags,
            agent_type=data.agent_type,
            pricing_type=pricing_type,
            price=data.price or Decimal(0),
            currency=data.currency,
            icon_url=data.icon_url,
            banner_url=data.banner_url,
            screenshots=data.screenshots,
            agent_config=data.agent_config,
            capabilities=data.capabilities,
            requirements=data.requirements,
            version=data.version,
            status=AgentStatus.DRAFT,
        )

        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)

        logger.info(f"Agent {agent.id} created by user {creator_email}")
        return agent

    async def get_agent_by_id(self, agent_id: str) -> Optional[MarketplaceAgent]:
        """Get agent by ID."""
        result = await self.db.execute(
            select(MarketplaceAgent).where(MarketplaceAgent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_agent_by_slug(self, slug: str) -> Optional[MarketplaceAgent]:
        """Get agent by slug."""
        result = await self.db.execute(
            select(MarketplaceAgent).where(MarketplaceAgent.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_agent_with_creator(self, agent_id: str) -> Optional[MarketplaceAgent]:
        """Get agent with creator info."""
        result = await self.db.execute(
            select(MarketplaceAgent)
            .options(selectinload(MarketplaceAgent.creator))
            .where(MarketplaceAgent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def update_agent(
        self,
        agent: MarketplaceAgent,
        data: AgentUpdate,
    ) -> MarketplaceAgent:
        """Update agent listing."""
        update_data = data.model_dump(exclude_unset=True)

        # Handle pricing type change
        if "pricing_type" in update_data:
            update_data["pricing_type"] = PricingType(update_data["pricing_type"])

        for field, value in update_data.items():
            setattr(agent, field, value)

        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def delete_agent(self, agent: MarketplaceAgent) -> None:
        """Delete agent listing."""
        await self.db.delete(agent)
        await self.db.flush()

    async def publish_agent(self, agent: MarketplaceAgent) -> MarketplaceAgent:
        """Publish agent (submit for review or direct publish)."""
        if agent.status not in [AgentStatus.DRAFT, AgentStatus.REJECTED]:
            raise MarketplaceServiceError("Agent cannot be published from current status")

        # For now, direct publish (skip review)
        agent.status = AgentStatus.PUBLISHED
        agent.published_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def unpublish_agent(self, agent: MarketplaceAgent) -> MarketplaceAgent:
        """Unpublish agent (back to draft)."""
        if agent.status != AgentStatus.PUBLISHED:
            raise MarketplaceServiceError("Only published agents can be unpublished")

        agent.status = AgentStatus.DRAFT
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def search_agents(
        self,
        request: AgentSearchRequest,
        user_id: Optional[str] = None,
    ) -> tuple[list[MarketplaceAgent], int]:
        """Search and filter agents."""
        query = select(MarketplaceAgent).where(
            MarketplaceAgent.status == AgentStatus.PUBLISHED
        )

        # Text search
        if request.query:
            search_term = f"%{request.query}%"
            query = query.where(
                or_(
                    MarketplaceAgent.name.ilike(search_term),
                    MarketplaceAgent.description.ilike(search_term),
                    MarketplaceAgent.short_description.ilike(search_term),
                )
            )

        # Category filter
        if request.category:
            query = query.where(MarketplaceAgent.category == request.category)

        # Tags filter
        if request.tags:
            query = query.where(MarketplaceAgent.tags.overlap(request.tags))

        # Pricing filter
        if request.pricing_type:
            query = query.where(
                MarketplaceAgent.pricing_type == PricingType(request.pricing_type)
            )

        if request.is_free is not None:
            if request.is_free:
                query = query.where(MarketplaceAgent.pricing_type == PricingType.FREE)
            else:
                query = query.where(MarketplaceAgent.pricing_type != PricingType.FREE)

        # Rating filter
        if request.min_rating is not None:
            query = query.where(
                or_(
                    MarketplaceAgent.rating_average >= request.min_rating,
                    MarketplaceAgent.rating_average.is_(None),
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Sorting
        sort_options = {
            "popular": MarketplaceAgent.download_count.desc(),
            "newest": MarketplaceAgent.published_at.desc(),
            "rating": MarketplaceAgent.rating_average.desc().nullslast(),
            "price_asc": MarketplaceAgent.price.asc(),
            "price_desc": MarketplaceAgent.price.desc(),
        }
        sort_order = sort_options.get(request.sort_by, sort_options["popular"])
        query = query.order_by(sort_order)

        # Pagination
        offset = (request.page - 1) * request.page_size
        query = query.offset(offset).limit(request.page_size)

        result = await self.db.execute(query)
        agents = list(result.scalars().all())

        return agents, total

    async def get_user_agents(
        self,
        user_email: str,
        status: Optional[AgentStatus] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[MarketplaceAgent], int]:
        """Get agents created by user."""
        query = select(MarketplaceAgent).where(MarketplaceAgent.creator_email == user_email)

        if status:
            query = query.where(MarketplaceAgent.status == status)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Paginate
        query = query.order_by(MarketplaceAgent.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.db.execute(query)
        agents = list(result.scalars().all())

        return agents, total

    async def get_featured_agents(self, limit: int = 10) -> list[MarketplaceAgent]:
        """Get featured agents."""
        result = await self.db.execute(
            select(MarketplaceAgent)
            .where(
                MarketplaceAgent.status == AgentStatus.PUBLISHED,
                MarketplaceAgent.is_featured == True,
            )
            .order_by(MarketplaceAgent.download_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_categories(self) -> list[dict[str, Any]]:
        """Get all categories with counts."""
        result = await self.db.execute(
            select(
                MarketplaceAgent.category,
                func.count(MarketplaceAgent.id).label("count"),
            )
            .where(MarketplaceAgent.status == AgentStatus.PUBLISHED)
            .group_by(MarketplaceAgent.category)
            .order_by(desc("count"))
        )

        categories = []
        for row in result.all():
            categories.append({
                "name": row.category,
                "slug": row.category.lower().replace(" ", "-"),
                "count": row.count,
            })

        return categories

    # ============== Review Operations ==============

    async def create_review(
        self,
        agent_id: str,
        user_email: str,
        data: ReviewCreate,
    ) -> AgentReview:
        """Create a review for an agent."""
        # Check if user already reviewed
        existing = await self.db.execute(
            select(AgentReview).where(
                AgentReview.agent_id == agent_id,
                AgentReview.user_email == user_email,
            )
        )
        if existing.scalar_one_or_none():
            raise MarketplaceServiceError("You have already reviewed this agent")

        # Check if user has purchased
        purchase = await self.db.execute(
            select(AgentPurchase).where(
                AgentPurchase.agent_id == agent_id,
                AgentPurchase.user_email == user_email,
            )
        )
        is_verified = purchase.scalar_one_or_none() is not None

        review = AgentReview(
            agent_id=agent_id,
            user_email=user_email,
            rating=data.rating,
            title=data.title,
            content=data.content,
            is_verified_purchase=is_verified,
        )

        self.db.add(review)
        await self.db.flush()

        # Update agent rating stats
        await self._update_agent_rating_stats(agent_id)

        await self.db.refresh(review)
        return review

    async def get_reviews(
        self,
        agent_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AgentReview], int, Optional[float], dict[int, int]]:
        """Get reviews for an agent with stats."""
        # Get reviews
        query = (
            select(AgentReview)
            .options(selectinload(AgentReview.user))
            .where(
                AgentReview.agent_id == agent_id,
                AgentReview.is_hidden == False,
            )
            .order_by(AgentReview.created_at.desc())
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        reviews = list(result.scalars().all())

        # Get average rating
        avg_result = await self.db.execute(
            select(func.avg(AgentReview.rating)).where(
                AgentReview.agent_id == agent_id,
                AgentReview.is_hidden == False,
            )
        )
        avg_rating = avg_result.scalar()

        # Get rating distribution
        dist_result = await self.db.execute(
            select(
                AgentReview.rating,
                func.count(AgentReview.id),
            )
            .where(
                AgentReview.agent_id == agent_id,
                AgentReview.is_hidden == False,
            )
            .group_by(AgentReview.rating)
        )
        distribution = {i: 0 for i in range(1, 6)}
        for row in dist_result.all():
            distribution[row[0]] = row[1]

        return reviews, total, float(avg_rating) if avg_rating else None, distribution

    async def update_review(
        self,
        review: AgentReview,
        data: ReviewUpdate,
    ) -> AgentReview:
        """Update a review."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(review, field, value)

        await self.db.flush()

        # Update agent rating stats
        await self._update_agent_rating_stats(review.agent_id)

        await self.db.refresh(review)
        return review

    async def delete_review(self, review: AgentReview) -> None:
        """Delete a review."""
        agent_id = review.agent_id
        await self.db.delete(review)
        await self.db.flush()

        # Update agent rating stats
        await self._update_agent_rating_stats(agent_id)

    async def get_user_review(
        self,
        agent_id: str,
        user_email: str,
    ) -> Optional[AgentReview]:
        """Get user's review for an agent."""
        result = await self.db.execute(
            select(AgentReview).where(
                AgentReview.agent_id == agent_id,
                AgentReview.user_email == user_email,
            )
        )
        return result.scalar_one_or_none()

    async def _update_agent_rating_stats(self, agent_id: str) -> None:
        """Update agent's rating statistics."""
        result = await self.db.execute(
            select(
                func.avg(AgentReview.rating),
                func.count(AgentReview.id),
            ).where(
                AgentReview.agent_id == agent_id,
                AgentReview.is_hidden == False,
            )
        )
        row = result.one()
        avg_rating, review_count = row

        await self.db.execute(
            MarketplaceAgent.__table__.update()
            .where(MarketplaceAgent.id == agent_id)
            .values(
                rating_average=avg_rating,
                rating_count=review_count,
                review_count=review_count,
            )
        )

    # ============== Purchase Operations ==============

    async def purchase_agent(
        self,
        agent_id: str,
        user_email: str,
        data: PurchaseCreate,
    ) -> AgentPurchase:
        """Purchase or subscribe to an agent."""
        # Get agent
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            raise MarketplaceServiceError("Agent not found")

        if agent.status != AgentStatus.PUBLISHED:
            raise MarketplaceServiceError("Agent is not available for purchase")

        # Check if already purchased (for non-subscription)
        if agent.pricing_type != PricingType.SUBSCRIPTION:
            existing = await self.db.execute(
                select(AgentPurchase).where(
                    AgentPurchase.agent_id == agent_id,
                    AgentPurchase.user_email == user_email,
                )
            )
            if existing.scalar_one_or_none():
                raise MarketplaceServiceError("You have already purchased this agent")

        purchase = AgentPurchase(
            agent_id=agent_id,
            user_email=user_email,
            pricing_type=agent.pricing_type,
            amount_paid=agent.price or Decimal(0),
            currency=agent.currency,
            transaction_id=data.transaction_id,
            payment_method=data.payment_method,
            is_active=True,
        )

        self.db.add(purchase)

        # Update download count
        agent.download_count += 1

        await self.db.flush()
        await self.db.refresh(purchase)

        logger.info(f"User {user_email} purchased agent {agent_id}")
        return purchase

    async def get_user_purchases(
        self,
        user_email: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[AgentPurchase], int]:
        """Get user's purchases."""
        query = (
            select(AgentPurchase)
            .options(selectinload(AgentPurchase.agent))
            .where(AgentPurchase.user_email == user_email)
            .order_by(AgentPurchase.created_at.desc())
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query) or 0

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        purchases = list(result.scalars().all())

        return purchases, total

    async def check_purchase(
        self,
        agent_id: str,
        user_email: str,
    ) -> Optional[AgentPurchase]:
        """Check if user has purchased an agent."""
        result = await self.db.execute(
            select(AgentPurchase).where(
                AgentPurchase.agent_id == agent_id,
                AgentPurchase.user_email == user_email,
                AgentPurchase.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    async def get_agent_stats(
        self,
        agent_id: str,
        creator_email: str,
    ) -> dict[str, Any]:
        """Get statistics for an agent (creator only)."""
        agent = await self.get_agent_by_id(agent_id)
        if not agent or agent.creator_email != creator_email:
            raise MarketplaceServiceError("Agent not found or access denied")

        # Get purchase stats
        purchase_stats = await self.db.execute(
            select(
                func.count(AgentPurchase.id),
                func.sum(AgentPurchase.amount_paid),
            ).where(AgentPurchase.agent_id == agent_id)
        )
        row = purchase_stats.one()
        total_purchases, total_revenue = row

        # Get active subscriptions
        active_subs = await self.db.scalar(
            select(func.count(AgentPurchase.id)).where(
                AgentPurchase.agent_id == agent_id,
                AgentPurchase.pricing_type == PricingType.SUBSCRIPTION,
                AgentPurchase.is_active == True,
            )
        ) or 0

        return {
            "total_downloads": agent.download_count,
            "total_revenue": total_revenue or Decimal(0),
            "average_rating": float(agent.rating_average) if agent.rating_average else None,
            "total_reviews": agent.review_count,
            "active_subscriptions": active_subs,
            "downloads_this_month": 0,  # TODO: Implement
            "revenue_this_month": Decimal(0),  # TODO: Implement
        }
