"""Marketplace endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.core.deps import CurrentUser, DBSession, OptionalUser
from app.models.marketplace import AgentStatus
from app.schemas.marketplace import (
    AgentCreate,
    AgentDetailResponse,
    AgentListResponse,
    AgentResponse,
    AgentSearchRequest,
    AgentStatsResponse,
    AgentUpdate,
    CategoryListResponse,
    CategoryResponse,
    PurchaseCreate,
    PurchaseListResponse,
    PurchaseResponse,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpdate,
)
from app.services.marketplace_service import MarketplaceService, MarketplaceServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Agent Endpoints ==============

@router.get("/agents", response_model=AgentListResponse)
async def list_agents(
    db: DBSession,
    query: Optional[str] = Query(None, max_length=200),
    category: Optional[str] = None,
    pricing_type: Optional[str] = None,
    is_free: Optional[bool] = None,
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    sort_by: str = Query("popular", regex="^(popular|newest|rating|price_asc|price_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    List and search marketplace agents.

    Supports filtering by category, pricing, rating, and text search.
    Sort options: popular, newest, rating, price_asc, price_desc
    """
    service = MarketplaceService(db)

    request = AgentSearchRequest(
        query=query,
        category=category,
        pricing_type=pricing_type,
        is_free=is_free,
        min_rating=min_rating,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

    agents, total = await service.search_agents(request)
    total_pages = (total + page_size - 1) // page_size

    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/agents/featured", response_model=list[AgentResponse])
async def get_featured_agents(
    db: DBSession,
    limit: int = Query(10, ge=1, le=50),
):
    """Get featured agents."""
    service = MarketplaceService(db)
    agents = await service.get_featured_agents(limit)
    return [AgentResponse.model_validate(a) for a in agents]


@router.get("/agents/categories", response_model=CategoryListResponse)
async def get_categories(db: DBSession):
    """Get all categories with agent counts."""
    service = MarketplaceService(db)
    categories = await service.get_categories()
    return CategoryListResponse(
        categories=[CategoryResponse(**c) for c in categories]
    )


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    current_user: CurrentUser,
    db: DBSession,
    data: AgentCreate,
):
    """
    Create a new agent listing.

    The agent will be created in DRAFT status.
    Use the publish endpoint to make it public.

    Requires authentication.
    """
    service = MarketplaceService(db)

    try:
        agent = await service.create_agent(
            creator_email=current_user.email,
            data=data,
        )
        await db.commit()
        return AgentResponse.model_validate(agent)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/agents/my", response_model=AgentListResponse)
async def get_my_agents(
    current_user: CurrentUser,
    db: DBSession,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get current user's agent listings.

    Optionally filter by status.
    Requires authentication.
    """
    service = MarketplaceService(db)

    agent_status = None
    if status_filter:
        try:
            agent_status = AgentStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid values: {[s.value for s in AgentStatus]}",
            )

    skip = (page - 1) * page_size
    agents, total = await service.get_user_agents(
        user_email=current_user.email,
        status=agent_status,
        skip=skip,
        limit=page_size,
    )
    total_pages = (total + page_size - 1) // page_size

    return AgentListResponse(
        agents=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/agents/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(
    agent_id: str,
    db: DBSession,
    current_user: OptionalUser,
):
    """
    Get agent details.

    Returns additional info like creator details and purchase status.
    """
    service = MarketplaceService(db)
    agent = await service.get_agent_with_creator(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Check if user has purchased
    is_purchased = False
    if current_user:
        purchase = await service.check_purchase(agent_id, current_user.email)
        is_purchased = purchase is not None

    response = AgentDetailResponse.model_validate(agent)
    response.creator_name = agent.creator.name if agent.creator else None
    response.creator_picture = agent.creator.picture_url if agent.creator else None
    response.is_purchased = is_purchased

    return response


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
    data: AgentUpdate,
):
    """
    Update an agent listing.

    Requires authentication and ownership.
    """
    service = MarketplaceService(db)
    agent = await service.get_agent_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.creator_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this agent",
        )

    try:
        agent = await service.update_agent(agent, data)
        await db.commit()
        return AgentResponse.model_validate(agent)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Delete an agent listing.

    Requires authentication and ownership.
    """
    service = MarketplaceService(db)
    agent = await service.get_agent_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.creator_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this agent",
        )

    await service.delete_agent(agent)
    await db.commit()


@router.post("/agents/{agent_id}/publish", response_model=AgentResponse)
async def publish_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Publish an agent to make it publicly available.

    Requires authentication and ownership.
    """
    service = MarketplaceService(db)
    agent = await service.get_agent_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.creator_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to publish this agent",
        )

    try:
        agent = await service.publish_agent(agent)
        await db.commit()
        return AgentResponse.model_validate(agent)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/agents/{agent_id}/unpublish", response_model=AgentResponse)
async def unpublish_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Unpublish an agent (back to draft).

    Requires authentication and ownership.
    """
    service = MarketplaceService(db)
    agent = await service.get_agent_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    if agent.creator_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to unpublish this agent",
        )

    try:
        agent = await service.unpublish_agent(agent)
        await db.commit()
        return AgentResponse.model_validate(agent)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/agents/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_stats(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get statistics for an agent.

    Requires authentication and ownership.
    """
    service = MarketplaceService(db)

    try:
        stats = await service.get_agent_stats(agent_id, current_user.email)
        return AgentStatsResponse(**stats)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


# ============== Review Endpoints ==============

@router.get("/agents/{agent_id}/reviews", response_model=ReviewListResponse)
async def get_agent_reviews(
    agent_id: str,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Get reviews for an agent."""
    service = MarketplaceService(db)

    # Verify agent exists
    agent = await service.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    skip = (page - 1) * page_size
    reviews, total, avg_rating, distribution = await service.get_reviews(
        agent_id, skip, page_size
    )

    # Build review responses with user info
    review_responses = []
    for review in reviews:
        response = ReviewResponse.model_validate(review)
        if review.user:
            response.user_name = review.user.name
            response.user_picture = review.user.picture_url
        review_responses.append(response)

    return ReviewListResponse(
        reviews=review_responses,
        total=total,
        average_rating=avg_rating,
        rating_distribution=distribution,
    )


@router.post("/agents/{agent_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
    data: ReviewCreate,
):
    """
    Create a review for an agent.

    Requires authentication.
    One review per user per agent.
    """
    service = MarketplaceService(db)

    # Verify agent exists
    agent = await service.get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    try:
        review = await service.create_review(
            agent_id=agent_id,
            user_email=current_user.email,
            data=data,
        )
        await db.commit()
        return ReviewResponse.model_validate(review)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/agents/{agent_id}/reviews", response_model=ReviewResponse)
async def update_my_review(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
    data: ReviewUpdate,
):
    """
    Update current user's review for an agent.

    Requires authentication.
    """
    service = MarketplaceService(db)

    review = await service.get_user_review(agent_id, current_user.email)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    review = await service.update_review(review, data)
    await db.commit()
    return ReviewResponse.model_validate(review)


@router.delete("/agents/{agent_id}/reviews", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_review(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Delete current user's review for an agent.

    Requires authentication.
    """
    service = MarketplaceService(db)

    review = await service.get_user_review(agent_id, current_user.email)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )

    await service.delete_review(review)
    await db.commit()


# ============== Purchase Endpoints ==============

@router.post("/agents/{agent_id}/purchase", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def purchase_agent(
    agent_id: str,
    current_user: CurrentUser,
    db: DBSession,
    data: PurchaseCreate,
):
    """
    Purchase or subscribe to an agent.

    For free agents, this just adds it to user's library.
    Requires authentication.
    """
    service = MarketplaceService(db)

    try:
        purchase = await service.purchase_agent(
            agent_id=agent_id,
            user_email=current_user.email,
            data=data,
        )
        await db.commit()
        return PurchaseResponse.model_validate(purchase)
    except MarketplaceServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/purchases", response_model=PurchaseListResponse)
async def get_my_purchases(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Get current user's purchased agents.

    Requires authentication.
    """
    service = MarketplaceService(db)

    skip = (page - 1) * page_size
    purchases, total = await service.get_user_purchases(
        user_email=current_user.email,
        skip=skip,
        limit=page_size,
    )

    return PurchaseListResponse(
        purchases=[PurchaseResponse.model_validate(p) for p in purchases],
        total=total,
    )
