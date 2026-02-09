"""
Agent Registry Service

DB-backed dynamic agent registry that replaces hardcoded DEFAULT_AGENTS
in ontology/orchestrator/agent_registry.py.

Provides:
- CRUD operations for agents and ACP servers
- ACP server sync (discovers agents from ACP /jsonrpc endpoint)
- Bridge to ontology AgentRegistry (loads DB agents into in-memory registry)
- Seed defaults on first run for backward compatibility
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import aiohttp
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.logosus.agent import ACPServer, RegisteredAgent

logger = logging.getLogger(__name__)


# Default agents to seed if DB is empty (backward compatibility with hardcoded list)
# These match the 12 agents from ontology/orchestrator/agent_registry.py DEFAULT_AGENTS
SEED_AGENTS = [
    {
        "agent_id": "internet_agent",
        "name": "인터넷 검색 에이전트",
        "description": "웹 검색을 수행하여 실시간 정보를 수집합니다. 주가, 환율, 뉴스 등 최신 데이터를 인터넷에서 검색합니다.",
        "capabilities": ["web_search", "real_time_data", "news_search", "price_lookup"],
        "tags": ["검색", "실시간", "인터넷", "데이터수집"],
        "display_name": "Internet Search",
        "display_name_ko": "인터넷 검색",
        "icon": "🌐",
        "color": "#3b82f6",
        "priority": 5,
    },
    {
        "agent_id": "weather_agent",
        "name": "날씨 정보 에이전트",
        "description": "실시간 날씨 정보를 제공하는 전문 에이전트입니다. 현재 날씨, 기온, 습도, 미세먼지, 주간 예보를 조회합니다.",
        "capabilities": ["weather_forecast", "real_time_weather", "air_quality", "weekly_forecast"],
        "tags": ["날씨", "기온", "미세먼지", "예보", "weather"],
        "display_name": "Weather",
        "display_name_ko": "날씨 정보",
        "icon": "🌤️",
        "color": "#06b6d4",
        "priority": 10,
    },
    {
        "agent_id": "analysis_agent",
        "name": "데이터 분석 에이전트",
        "description": "수집된 데이터를 분석하고 인사이트를 추출합니다. 수치, 트렌드, 비교 분석을 수행합니다.",
        "capabilities": ["data_analysis", "trend_analysis", "comparison", "insight_extraction"],
        "tags": ["분석", "데이터", "통계", "인사이트"],
        "display_name": "Data Analysis",
        "display_name_ko": "데이터 분석",
        "icon": "📊",
        "color": "#8b5cf6",
        "priority": 20,
    },
    {
        "agent_id": "shopping_agent",
        "name": "쇼핑 검색 에이전트",
        "description": "상품 검색, 가격 비교, 쇼핑 추천을 수행합니다. 네이버 쇼핑, 쿠팡 등에서 상품을 찾습니다.",
        "capabilities": ["product_search", "price_comparison", "shopping_recommendation"],
        "tags": ["쇼핑", "상품", "가격", "구매", "shopping"],
        "display_name": "Shopping",
        "display_name_ko": "쇼핑 검색",
        "icon": "🛒",
        "color": "#f97316",
        "priority": 30,
    },
    {
        "agent_id": "code_generation_agent",
        "name": "코드 생성 에이전트",
        "description": "프로그래밍 코드를 생성하고 분석합니다. Python, JavaScript 등 다양한 언어를 지원합니다.",
        "capabilities": ["code_generation", "code_analysis", "debugging", "refactoring"],
        "tags": ["코드", "프로그래밍", "개발", "코딩", "code"],
        "display_name": "Code Generation",
        "display_name_ko": "코드 생성",
        "icon": "💻",
        "color": "#10b981",
        "priority": 25,
    },
    {
        "agent_id": "llm_search_agent",
        "name": "LLM 검색 에이전트",
        "description": "LLM 지식 기반의 일반 질의응답을 수행합니다. 상식, 학문, 기술 등 광범위한 질문에 응답합니다.",
        "capabilities": ["general_qa", "knowledge_search", "academic_research"],
        "tags": ["검색", "질문", "지식", "학문", "일반"],
        "display_name": "LLM Search",
        "display_name_ko": "LLM 검색",
        "icon": "🔍",
        "color": "#6366f1",
        "priority": 15,
    },
    {
        "agent_id": "calculator_agent",
        "name": "계산기 에이전트",
        "description": "수학 계산, 단위 변환, 통계 계산을 수행합니다.",
        "capabilities": ["math_calculation", "unit_conversion", "statistics"],
        "tags": ["계산", "수학", "단위변환", "통계"],
        "display_name": "Calculator",
        "display_name_ko": "계산기",
        "icon": "🧮",
        "color": "#ef4444",
        "priority": 35,
    },
    {
        "agent_id": "scheduler_agent",
        "name": "일정 관리 에이전트",
        "description": "일정 조회, 생성, 수정을 수행합니다. 캘린더 시스템에 접근하여 일정을 관리합니다.",
        "capabilities": ["schedule_management", "calendar_access", "reminder"],
        "tags": ["일정", "스케줄", "캘린더", "약속"],
        "display_name": "Scheduler",
        "display_name_ko": "일정 관리",
        "icon": "📅",
        "color": "#f59e0b",
        "priority": 40,
    },
    {
        "agent_id": "samsung_gateway_agent",
        "name": "삼성 게이트웨이 에이전트",
        "description": "삼성전자 관련 전문 정보를 처리합니다. 삼성 제품, 서비스, 기업 정보를 전문적으로 다룹니다.",
        "capabilities": ["samsung_products", "samsung_services", "corporate_info"],
        "tags": ["삼성", "Samsung", "반도체", "갤럭시"],
        "display_name": "Samsung Gateway",
        "display_name_ko": "삼성 게이트웨이",
        "icon": "📱",
        "color": "#1428a0",
        "priority": 45,
    },
    {
        "agent_id": "data_visualization_agent",
        "name": "데이터 시각화 에이전트",
        "description": "데이터를 차트, 그래프, 대시보드로 시각화합니다.",
        "capabilities": ["chart_generation", "graph_visualization", "dashboard_creation"],
        "tags": ["시각화", "차트", "그래프", "대시보드"],
        "display_name": "Data Visualization",
        "display_name_ko": "데이터 시각화",
        "icon": "📈",
        "color": "#14b8a6",
        "priority": 50,
    },
    {
        "agent_id": "rag_search_agent",
        "name": "RAG 검색 에이전트",
        "description": "업로드된 문서를 기반으로 검색하고 답변합니다. PDF, 워드 등 문서를 분석합니다.",
        "capabilities": ["document_search", "rag_retrieval", "document_analysis"],
        "tags": ["문서", "RAG", "검색", "PDF"],
        "display_name": "RAG Search",
        "display_name_ko": "RAG 검색",
        "icon": "📄",
        "color": "#a855f7",
        "priority": 55,
    },
    {
        "agent_id": "currency_exchange_agent",
        "name": "환율 변환 에이전트",
        "description": "실시간 환율 정보를 제공하고 통화 변환을 수행합니다. USD, EUR, JPY, CNY, GBP 등 30개 이상의 통화를 지원합니다.",
        "capabilities": ["exchange_rate", "currency_conversion", "real_time_rate", "rate_history", "multi_currency"],
        "tags": ["환율", "통화", "달러", "엔화", "유로", "exchange", "currency", "USD", "EUR", "JPY"],
        "display_name": "Currency Exchange",
        "display_name_ko": "환율 변환",
        "icon": "💱",
        "color": "#f59e0b",
        "priority": 50,
    },
]


class AgentRegistryService:
    """DB-backed agent registry service.

    Manages agents and ACP servers in the database, and provides
    a bridge to load them into the ontology AgentRegistry at runtime.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # --- ACP Server CRUD ---

    async def ensure_default_acp_server(self) -> ACPServer:
        """Ensure the default ACP server exists in DB. Creates if not found."""
        result = await self.db.execute(
            select(ACPServer).where(ACPServer.is_default == True)
        )
        server = result.scalar_one_or_none()

        if server:
            # Update URL if changed in config
            if server.url != settings.acp_server_url:
                server.url = settings.acp_server_url
                server.updated_at = datetime.now(timezone.utc)
            return server

        # Create default server
        server = ACPServer(
            id=str(uuid4()),
            name="Local ACP Server",
            url=settings.acp_server_url,
            is_active=True,
            is_default=True,
            health_status="unknown",
            description="Default local ACP server",
        )
        self.db.add(server)
        await self.db.flush()
        logger.info(f"📦 Created default ACP server: {server.url}")
        return server

    async def get_acp_server(self, server_id: str) -> Optional[ACPServer]:
        """Get ACP server by ID."""
        result = await self.db.execute(
            select(ACPServer).where(ACPServer.id == server_id)
        )
        return result.scalar_one_or_none()

    async def get_all_acp_servers(self) -> list[ACPServer]:
        """Get all ACP servers with agent counts."""
        result = await self.db.execute(
            select(ACPServer)
            .options(selectinload(ACPServer.agents))
            .order_by(ACPServer.is_default.desc(), ACPServer.name)
        )
        return list(result.scalars().all())

    async def create_acp_server(self, data: dict) -> ACPServer:
        """Create a new ACP server."""
        server = ACPServer(
            id=str(uuid4()),
            name=data["name"],
            url=data["url"],
            is_active=data.get("is_active", True),
            is_default=data.get("is_default", False),
            description=data.get("description"),
            metadata_json=data.get("metadata"),
        )
        self.db.add(server)
        await self.db.flush()
        return server

    # --- Agent CRUD ---

    async def get_all_agents(self) -> list[RegisteredAgent]:
        """Get all registered agents with ACP server info."""
        result = await self.db.execute(
            select(RegisteredAgent)
            .options(selectinload(RegisteredAgent.acp_server))
            .where(RegisteredAgent.is_available == True)
            .order_by(RegisteredAgent.priority, RegisteredAgent.agent_id)
        )
        return list(result.scalars().all())

    async def get_agent_by_id(self, agent_id: str) -> Optional[RegisteredAgent]:
        """Get agent by agent_id."""
        result = await self.db.execute(
            select(RegisteredAgent)
            .options(selectinload(RegisteredAgent.acp_server))
            .where(RegisteredAgent.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    async def upsert_agent(self, data: dict, acp_server_id: str) -> RegisteredAgent:
        """Create or update an agent."""
        agent_id = data["agent_id"]

        result = await self.db.execute(
            select(RegisteredAgent).where(RegisteredAgent.agent_id == agent_id)
        )
        agent = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if agent:
            # Update existing
            agent.name = data.get("name", agent.name)
            agent.description = data.get("description", agent.description)
            agent.capabilities = data.get("capabilities", agent.capabilities)
            agent.tags = data.get("tags", agent.tags)
            agent.input_type = data.get("input_type", agent.input_type)
            agent.output_type = data.get("output_type", agent.output_type)
            agent.display_name = data.get("display_name", agent.display_name)
            agent.display_name_ko = data.get("display_name_ko", agent.display_name_ko)
            agent.icon = data.get("icon", agent.icon)
            agent.color = data.get("color", agent.color)
            agent.priority = data.get("priority", agent.priority)
            agent.is_available = True
            agent.last_seen_at = now
            agent.acp_server_id = acp_server_id
            agent.updated_at = now
            return agent

        # Create new
        agent = RegisteredAgent(
            id=str(uuid4()),
            agent_id=agent_id,
            acp_server_id=acp_server_id,
            name=data.get("name", agent_id),
            description=data.get("description"),
            capabilities=data.get("capabilities", []),
            tags=data.get("tags", []),
            input_type=data.get("input_type", "query"),
            output_type=data.get("output_type", "text"),
            display_name=data.get("display_name"),
            display_name_ko=data.get("display_name_ko"),
            icon=data.get("icon"),
            color=data.get("color"),
            priority=data.get("priority", 50),
            is_available=True,
            last_seen_at=now,
            source=data.get("source", "acp_sync"),
        )
        self.db.add(agent)
        await self.db.flush()
        return agent

    async def create_agent(self, data: dict) -> RegisteredAgent:
        """Manually register an agent."""
        acp_server_id = data.get("acp_server_id")
        if not acp_server_id:
            server = await self.ensure_default_acp_server()
            acp_server_id = server.id

        data["source"] = "manual"
        return await self.upsert_agent(data, acp_server_id)

    # --- Sync from ACP ---

    async def sync_from_acp(
        self, acp_server_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Sync agents from an ACP server.

        Discovers agents via JSON-RPC list_agents endpoint and upserts them to DB.
        Agents not seen in this sync are deactivated.
        """
        # Resolve ACP server
        if acp_server_id:
            server = await self.get_acp_server(acp_server_id)
            if not server:
                raise ValueError(f"ACP server not found: {acp_server_id}")
        else:
            server = await self.ensure_default_acp_server()

        # Fetch agents from ACP
        acp_agents = await self._fetch_agents_from_acp(server.url)

        added = 0
        updated = 0

        # Get existing agents for this server
        result = await self.db.execute(
            select(RegisteredAgent).where(
                RegisteredAgent.acp_server_id == server.id
            )
        )
        existing = {a.agent_id: a for a in result.scalars().all()}
        seen_ids = set()

        for acp_agent in acp_agents:
            agent_id = acp_agent.get("agent_id", acp_agent.get("name", ""))
            if not agent_id:
                continue

            seen_ids.add(agent_id)

            was_existing = agent_id in existing
            await self.upsert_agent(
                {
                    "agent_id": agent_id,
                    "name": acp_agent.get("name", agent_id),
                    "description": acp_agent.get("description", ""),
                    "capabilities": acp_agent.get("capabilities", []),
                    "tags": acp_agent.get("tags", []),
                    "source": "acp_sync",
                },
                acp_server_id=server.id,
            )

            if was_existing:
                updated += 1
            else:
                added += 1

        # Deactivate agents not seen in this sync
        deactivated = 0
        for agent_id, agent in existing.items():
            if agent_id not in seen_ids:
                agent.is_available = False
                deactivated += 1

        # Update server health
        server.health_status = "healthy"
        server.last_health_check = datetime.now(timezone.utc)

        await self.db.flush()

        total = len(seen_ids)
        logger.info(
            f"📦 ACP sync complete: {added} added, {updated} updated, "
            f"{deactivated} deactivated, {total} total"
        )

        return {
            "added": added,
            "updated": updated,
            "deactivated": deactivated,
            "total": total,
            "acp_server_name": server.name,
            "acp_server_url": server.url,
        }

    async def _fetch_agents_from_acp(self, acp_url: str) -> list[dict]:
        """Fetch agent list from ACP server via JSON-RPC."""
        rpc_payload = {
            "jsonrpc": "2.0",
            "method": "list_agents",
            "params": {},
            "id": 1,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{acp_url}/jsonrpc",
                    json=rpc_payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = data.get("result", data)
                        agents = result.get("agents", [])
                        logger.info(f"📡 Fetched {len(agents)} agents from {acp_url}")
                        return agents
                    else:
                        logger.warning(
                            f"ACP server returned {response.status}: {acp_url}"
                        )
                        return []
        except Exception as e:
            logger.error(f"Failed to fetch agents from ACP: {e}")
            return []

    # --- Seed defaults ---

    async def seed_defaults_if_empty(self) -> int:
        """Seed default agents if DB is empty.

        This provides backward compatibility with the hardcoded DEFAULT_AGENTS
        from ontology/orchestrator/agent_registry.py.
        """
        result = await self.db.execute(
            select(func.count(RegisteredAgent.id))
        )
        count = result.scalar_one()

        if count > 0:
            logger.info(f"📦 DB has {count} agents, skipping seed")
            return 0

        # Ensure default ACP server
        server = await self.ensure_default_acp_server()

        # Seed default agents
        for agent_data in SEED_AGENTS:
            agent_data_copy = {**agent_data, "source": "seed"}
            await self.upsert_agent(agent_data_copy, acp_server_id=server.id)

        await self.db.flush()
        logger.info(f"📦 Seeded {len(SEED_AGENTS)} default agents")
        return len(SEED_AGENTS)

    # --- Ontology Bridge ---

    async def load_into_ontology_registry(self, registry: Any) -> int:
        """Load all DB agents into the ontology AgentRegistry.

        This is the key bridge: DB agents → in-memory ontology registry
        that the QueryPlanner uses for agent selection.
        """
        agents = await self.get_all_agents()

        if not agents:
            logger.warning("No agents in DB to load into ontology registry")
            return 0

        # Import here to avoid circular imports
        try:
            from ontology.orchestrator.models import AgentRegistryEntry, AgentSchema
        except ImportError:
            logger.error("Cannot import ontology models")
            return 0

        loaded = 0
        for agent in agents:
            try:
                entry = AgentRegistryEntry(
                    agent_id=agent.agent_id,
                    name=agent.name,
                    description=agent.description or "",
                    capabilities=agent.capabilities or [],
                    tags=agent.tags or [],
                    schema=AgentSchema(
                        input_type=agent.input_type or "query",
                        output_type=agent.output_type or "text",
                    ),
                    display_name=agent.display_name,
                    display_name_ko=agent.display_name_ko,
                    icon=agent.icon,
                    color=agent.color,
                    priority=agent.priority,
                )
                registry.register_agent(entry)
                loaded += 1
            except Exception as e:
                logger.debug(f"Failed to load agent {agent.agent_id}: {e}")

        logger.info(f"📦 Loaded {loaded} agents from DB into ontology registry")
        return loaded

    async def get_agent_count(self) -> int:
        """Get total number of available agents."""
        result = await self.db.execute(
            select(func.count(RegisteredAgent.id)).where(
                RegisteredAgent.is_available == True
            )
        )
        return result.scalar_one()
