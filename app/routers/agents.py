"""Agent and ACP Server management endpoints.

Provides REST API for:
- Listing registered agents
- Triggering ACP sync
- Manual agent registration
- ACP server management
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import DBSession
from app.schemas.agent import (
    ACPServerCreate,
    ACPServerResponse,
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    SyncRequest,
    SyncResponse,
)
from app.services.agent_registry_service import AgentRegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=AgentListResponse)
async def list_agents(db: DBSession) -> dict[str, Any]:
    """List all registered agents.

    Returns all available agents from the database, including
    their ACP server connection information.
    """
    service = AgentRegistryService(db)
    agents = await service.get_all_agents()

    return {
        "agents": [
            {
                **agent.to_registry_dict(),
                "id": agent.id,
                "acp_server_id": agent.acp_server_id,
                "is_available": agent.is_available,
                "average_execution_time_ms": agent.average_execution_time_ms,
                "success_rate": agent.success_rate,
                "last_seen_at": agent.last_seen_at,
                "source": agent.source,
                "created_at": agent.created_at,
                "updated_at": agent.updated_at,
                "acp_server_name": agent.acp_server.name if agent.acp_server else None,
                "acp_server_url": agent.acp_server.url if agent.acp_server else None,
            }
            for agent in agents
        ],
        "total": len(agents),
    }


@router.get("/{agent_id}")
async def get_agent(agent_id: str, db: DBSession) -> dict[str, Any]:
    """Get a specific agent by agent_id."""
    service = AgentRegistryService(db)
    agent = await service.get_agent_by_id(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    return {
        **agent.to_registry_dict(),
        "id": agent.id,
        "acp_server_id": agent.acp_server_id,
        "is_available": agent.is_available,
        "average_execution_time_ms": agent.average_execution_time_ms,
        "success_rate": agent.success_rate,
        "last_seen_at": agent.last_seen_at,
        "source": agent.source,
        "created_at": agent.created_at,
        "updated_at": agent.updated_at,
        "acp_server_name": agent.acp_server.name if agent.acp_server else None,
        "acp_server_url": agent.acp_server.url if agent.acp_server else None,
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def register_agent(request: AgentCreate, db: DBSession) -> dict[str, Any]:
    """Manually register an agent."""
    service = AgentRegistryService(db)

    try:
        agent = await service.create_agent(request.model_dump())
        await db.commit()
        return {
            "msg": "success",
            "agent_id": agent.agent_id,
            "id": agent.id,
        }
    except Exception as e:
        logger.error(f"Failed to register agent: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/sync", response_model=SyncResponse)
async def sync_agents(
    request: SyncRequest = SyncRequest(),
    db: DBSession = None,
) -> dict[str, Any]:
    """Trigger ACP server sync.

    Discovers agents from the ACP server and syncs them to the database.
    Agents not found in the ACP server are deactivated.
    """
    service = AgentRegistryService(db)

    try:
        result = await service.sync_from_acp(request.acp_server_id)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


# --- ACP Server Management ---


@router.get("/servers/", response_model=list[ACPServerResponse])
async def list_acp_servers(db: DBSession) -> list[dict[str, Any]]:
    """List all ACP servers."""
    service = AgentRegistryService(db)
    servers = await service.get_all_acp_servers()

    result = []
    for server in servers:
        agent_count = 0
        if server.agents:
            agent_count = len([a for a in server.agents if a.is_available])

        result.append({
            "id": server.id,
            "name": server.name,
            "url": server.url,
            "is_active": server.is_active,
            "is_default": server.is_default,
            "health_status": server.health_status,
            "last_health_check": server.last_health_check,
            "description": server.description,
            "metadata": server.metadata_json,
            "agent_count": agent_count,
            "created_at": server.created_at,
            "updated_at": server.updated_at,
        })

    return result


@router.post("/servers/", status_code=status.HTTP_201_CREATED)
async def create_acp_server(
    request: ACPServerCreate, db: DBSession
) -> dict[str, Any]:
    """Register a new ACP server."""
    service = AgentRegistryService(db)

    try:
        server = await service.create_acp_server(request.model_dump())
        await db.commit()
        return {
            "msg": "success",
            "id": server.id,
            "name": server.name,
            "url": server.url,
        }
    except Exception as e:
        logger.error(f"Failed to create ACP server: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
