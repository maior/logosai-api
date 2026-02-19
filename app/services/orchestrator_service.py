"""
Orchestrator Service for logos_api

Django의 멀티 에이전트 스트리밍과 동일한 기능을 FastAPI에서 제공합니다.
ontology 모듈의 WorkflowOrchestrator를 사용하여:
- 쿼리 분석 (UnifiedQueryProcessor)
- 워크플로우 계획 생성 (QueryPlanner)
- 에이전트 실행 (ExecutionEngine)
- 데이터 변환 (DataTransformer)
- SSE 스트리밍 (ProgressStreamer)
"""

import asyncio
import logging
import sys
import os
from typing import Any, AsyncGenerator, Optional, List, Dict
from datetime import datetime, timezone

# Add ontology to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ontology'))

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy imports for ontology modules
_orchestrator_available = False
_imports_attempted = False


def _ensure_imports():
    """Lazy import ontology modules."""
    global _orchestrator_available, _imports_attempted

    if _imports_attempted:
        return _orchestrator_available

    _imports_attempted = True

    try:
        global WorkflowOrchestrator, QueryPlanner, DataTransformer
        global ExecutionEngine, AgentRegistry, ProgressStreamer
        global UnifiedQueryProcessor, get_unified_query_processor
        global ProgressEventType, ExecutionPlan
        global KnowledgeGraphEngine, VisualizationManager

        from ontology.orchestrator import (
            WorkflowOrchestrator,
            QueryPlanner,
            DataTransformer,
            ExecutionEngine,
            AgentRegistry,
            ProgressStreamer,
            ProgressEventType,
            ExecutionPlan,
        )
        from ontology.core.unified_query_processor import (
            UnifiedQueryProcessor,
            get_unified_query_processor,
        )
        from ontology.engines.knowledge_graph_clean import KnowledgeGraphEngine, get_knowledge_graph_engine
        from ontology.system.visualization_manager import VisualizationManager

        _orchestrator_available = True
        logger.info("✅ Ontology orchestrator modules loaded successfully")

    except ImportError as e:
        logger.warning(f"⚠️ Ontology modules not available: {e}")
        _orchestrator_available = False

    return _orchestrator_available


class OrchestratorService:
    """
    멀티 에이전트 워크플로우 오케스트레이션 서비스.

    Django의 multi_agent_streaming.py와 동일한 기능을 제공합니다.
    """

    def __init__(
        self,
        acp_base_url: Optional[str] = None,
    ):
        self.acp_base_url = acp_base_url or settings.acp_server_url
        self._orchestrator: Optional[Any] = None
        self._query_processor: Optional[Any] = None
        self._registry: Optional[Any] = None
        self._knowledge_graph: Optional[Any] = None
        self._visualization_manager: Optional[Any] = None
        self._initialized = False

    async def initialize(self) -> bool:
        """오케스트레이터 초기화."""
        if self._initialized:
            return True

        if not _ensure_imports():
            logger.warning("Orchestrator not available - falling back to direct ACP")
            return False

        try:
            # Agent Registry 초기화
            self._registry = AgentRegistry()

            # DB에서 에이전트 로드 (Dynamic Agent Registry)
            await self._load_agents_from_db()

            # UnifiedQueryProcessor 초기화
            self._query_processor = get_unified_query_processor()

            # WorkflowOrchestrator 초기화 (agent_executor 함수 전달)
            self._orchestrator = WorkflowOrchestrator(
                agent_executor=self._execute_agent_via_acp,
                registry=self._registry,
                enable_validation=True,
                enable_streaming=True,
            )

            # KnowledgeGraphEngine 및 VisualizationManager 초기화 (shared singleton)
            try:
                self._knowledge_graph = get_knowledge_graph_engine()
                self._visualization_manager = VisualizationManager(self._knowledge_graph)
                logger.info("✅ KnowledgeGraphEngine initialized (shared singleton) + VisualizationManager")
            except Exception as kg_error:
                logger.warning(f"⚠️ Knowledge graph initialization failed: {kg_error}")
                self._knowledge_graph = None
                self._visualization_manager = None

            self._initialized = True
            logger.info("✅ OrchestratorService initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize OrchestratorService: {e}")
            return False

    async def _load_agents_from_db(self) -> int:
        """DB에서 에이전트를 로드하여 ontology AgentRegistry에 등록.

        하드코딩된 DEFAULT_AGENTS 대신 DB에서 동적으로 로드합니다.
        DB가 비어있으면 DEFAULT_AGENTS가 이미 시드된 상태이므로 그것을 로드합니다.
        """
        try:
            from app.database import get_db_context
            from app.services.agent_registry_service import AgentRegistryService

            async with get_db_context() as db:
                service = AgentRegistryService(db)
                loaded = await service.load_into_ontology_registry(self._registry)
                if loaded > 0:
                    logger.info(f"📦 Loaded {loaded} agents from DB into ontology registry")
                else:
                    logger.warning("⚠️ No agents loaded from DB, using DEFAULT_AGENTS")
                return loaded
        except Exception as e:
            logger.warning(f"⚠️ DB agent loading failed, using DEFAULT_AGENTS: {e}")
            return 0

    async def _execute_agent_via_acp(
        self,
        agent_id: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        ACP 서버를 통해 에이전트를 실행합니다.

        WorkflowOrchestrator의 ExecutionEngine이 이 함수를 호출합니다.
        """
        import aiohttp
        import json

        payload = {
            "query": query,
            "agent_id": agent_id,
            "context": context or {},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.acp_base_url}/stream",  # 단일 에이전트 엔드포인트
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"ACP agent execution failed: {error_text}")
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}: {error_text[:200]}",
                            "agent_id": agent_id,
                        }

                    # SSE 응답 파싱
                    result = None
                    byte_buffer = b""  # 바이트 버퍼 (불완전한 UTF-8 바이트 저장)
                    text_buffer = ""   # 텍스트 버퍼 (파싱되지 않은 SSE 이벤트 저장)

                    async for chunk in response.content.iter_any():
                        byte_buffer += chunk

                        # 바이트 버퍼를 안전하게 디코딩 (멀티바이트 문자 처리)
                        decoded_text = ""
                        try:
                            decoded_text = byte_buffer.decode("utf-8")
                            byte_buffer = b""  # 성공 시 바이트 버퍼 초기화
                        except UnicodeDecodeError:
                            # 불완전한 UTF-8 시퀀스가 있으면 마지막 몇 바이트를 남겨둠
                            # UTF-8 멀티바이트 문자는 최대 4바이트
                            for i in range(1, min(4, len(byte_buffer) + 1)):
                                try:
                                    decoded_text = byte_buffer[:-i].decode("utf-8")
                                    byte_buffer = byte_buffer[-i:]  # 남은 바이트 유지
                                    break
                                except UnicodeDecodeError:
                                    continue
                            else:
                                # 모든 시도 실패 시 에러 무시하고 디코딩
                                decoded_text = byte_buffer.decode("utf-8", errors="replace")
                                byte_buffer = b""

                        # 디코딩된 텍스트를 텍스트 버퍼에 추가
                        text_buffer += decoded_text

                        # SSE 이벤트 파싱
                        while "\n\n" in text_buffer:
                            event_str, text_buffer = text_buffer.split("\n\n", 1)
                            for line in event_str.split("\n"):
                                if line.startswith("data:"):
                                    try:
                                        data = json.loads(line[5:].strip())
                                        event_type = data.get("event", data.get("type", ""))

                                        # final_result 또는 complete 이벤트에서 결과 추출
                                        if event_type in ("final_result", "complete", "result"):
                                            result = data.get("data", data)
                                    except json.JSONDecodeError:
                                        pass

                    if result:
                        return {
                            "success": True,
                            "data": result,
                            "agent_id": agent_id,
                        }
                    else:
                        return {
                            "success": False,
                            "error": "No result received",
                            "agent_id": agent_id,
                        }

        except Exception as e:
            logger.error(f"Agent execution error ({agent_id}): {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_id": agent_id,
            }

    async def load_agents_from_acp(self) -> List[Dict[str, Any]]:
        """ACP 서버에서 사용 가능한 에이전트 목록을 로드합니다.

        ACP에서 받은 에이전트를 DB에 저장하고 ontology registry에도 등록합니다.
        """
        import aiohttp
        import json

        try:
            # ACP 서버는 JSON-RPC 형식 사용
            rpc_payload = {
                "jsonrpc": "2.0",
                "method": "list_agents",
                "params": {},
                "id": 1,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.acp_base_url}/jsonrpc",
                    json=rpc_payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # JSON-RPC 응답에서 result 추출
                        result = data.get("result", data)
                        agents = result.get("agents", [])

                        # DB에 에이전트 동기화 저장
                        try:
                            from app.database import get_db_context
                            from app.services.agent_registry_service import AgentRegistryService

                            async with get_db_context() as db:
                                service = AgentRegistryService(db)
                                sync_result = await service.sync_from_acp()
                                logger.info(
                                    f"📦 DB sync: +{sync_result['added']}, "
                                    f"~{sync_result['updated']}, total={sync_result['total']}"
                                )
                                # DB에서 다시 로드하여 ontology registry 업데이트
                                if self._registry and _orchestrator_available:
                                    await service.load_into_ontology_registry(self._registry)
                        except Exception as db_err:
                            logger.debug(f"DB sync skipped: {db_err}")
                            # Fallback: 직접 registry에 등록
                            if self._registry and _orchestrator_available:
                                self._register_agents_to_registry(agents)

                        logger.info(f"📦 Loaded {len(agents)} agents from ACP server")
                        return agents
                    else:
                        logger.warning(f"Failed to load agents: HTTP {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Error loading agents from ACP: {e}")
            return []

    def _register_agents_to_registry(self, agents: List[Dict[str, Any]]) -> None:
        """Fallback: 에이전트를 ontology registry에 직접 등록 (DB 없이)."""
        if not _orchestrator_available:
            return

        from ontology.orchestrator.models import AgentRegistryEntry, AgentSchema

        for agent in agents:
            try:
                entry = AgentRegistryEntry(
                    agent_id=agent.get("agent_id", agent.get("name", "")),
                    name=agent.get("name", ""),
                    description=agent.get("description", ""),
                    capabilities=agent.get("capabilities", []),
                    tags=agent.get("tags", []),
                    schema=AgentSchema(
                        input_type="query",
                        output_type="text",
                    ),
                )
                self._registry.register_agent(entry)
            except Exception as e:
                logger.debug(f"Agent registration skipped: {e}")

    async def stream_with_orchestrator(
        self,
        query: str,
        user_email: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        WorkflowOrchestrator를 사용한 멀티 에이전트 스트리밍.

        Django의 _stream_with_orchestrator()와 동일한 기능:
        - UnifiedQueryProcessor로 쿼리 분석
        - WorkflowOrchestrator로 워크플로우 계획 생성 및 실행
        - DataTransformer로 에이전트 간 데이터 변환
        - SSE 이벤트 스트리밍
        """
        # 초기화 확인
        if not await self.initialize():
            async for event in self._fallback_stream(query, user_email, session_id, project_id, context):
                yield event
            return

        # 에이전트 로드
        yield {
            "event": "ontology_init",
            "data": {
                "message": "온톨로지 시스템으로 쿼리 분석 중...",
                "stage": "ontology_initialization",
                "progress": 10,
            },
        }

        agents = await self.load_agents_from_acp()

        yield {
            "event": "agents_loading",
            "data": {
                "message": "📂 설치된 에이전트 목록 조회 중...",
                "stage": "agents_loading",
                "progress": 12,
            },
        }

        if not agents:
            yield {
                "event": "error",
                "data": {
                    "error_code": "NO_AGENTS",
                    "message": "사용 가능한 에이전트가 없습니다.",
                },
            }
            return

        yield {
            "event": "log",
            "data": {
                "level": "success",
                "message": f"📦 {len(agents)}개 에이전트 로드 완료",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        # 🆕 사용 가능한 에이전트 목록 스트리밍 (UI에서 워크플로우 시각화용)
        yield {
            "event": "agents_available",
            "data": {
                "message": f"사용 가능한 에이전트 {len(agents)}개",
                "message_ko": f"사용 가능한 에이전트 {len(agents)}개",
                "agents": [
                    {
                        "agent_id": a.get("agent_id", a.get("name", "")),
                        "agent_name": a.get("name", a.get("agent_id", "")),
                        "description": a.get("description", ""),
                        "capabilities": a.get("capabilities", []),
                        "tags": a.get("tags", []),
                        "icon": self._get_agent_icon(a.get("agent_id", a.get("name", ""))),
                    }
                    for a in agents
                ],
                "progress": 15,
            },
        }

        # 에이전트를 레지스트리에 등록 (이미 load_agents_from_acp에서 등록됨)
        # DB sync 실패 시 fallback으로 직접 등록
        if self._registry and _orchestrator_available:
            self._register_agents_to_registry(agents)

        # 컨텍스트 구성
        execution_context = {
            "user_email": user_email,
            "session_id": session_id,
            "project_id": project_id,
            **(context or {}),
        }

        # WorkflowOrchestrator로 실행 (내부적으로 QueryPlanner가 LLM 분석 수행)
        # 🆕 실행된 에이전트 결과 수집 (Knowledge Graph 시각화용)
        executed_agents: List[Dict[str, Any]] = []
        selected_agents_from_plan: List[Dict[str, Any]] = []

        try:
            async for event in self._orchestrator.run_streaming(
                query=query,
                context=execution_context,
            ):
                # ProgressEvent를 SSE 형식으로 변환
                converted = self._convert_orchestrator_event(event)

                # 🆕 planning_complete 이벤트 강화 (선택된 에이전트 상세 정보 추가)
                if converted.get("event") == "planning_complete":
                    converted = self._enhance_planning_complete(converted, agents)
                    # 🆕 선택된 에이전트 정보 저장 (KG 시각화용)
                    selected_agents_from_plan = converted.get("data", {}).get("selected_agents", [])

                    # v3.0: Emit ML selection metadata for dashboard
                    try:
                        from ontology.core.hybrid_agent_selector import get_hybrid_selector
                        _sel = get_hybrid_selector()
                        if hasattr(_sel, '_selection_history') and _sel._selection_history:
                            _latest = _sel._selection_history[-1]
                            yield {
                                "event": "ml_selection",
                                "data": {
                                    "method": _latest.get("method", "unknown"),
                                    "confidence": _latest.get("confidence", 0),
                                    "value_estimate": _latest.get("value_estimate", 0),
                                    "elapsed_ms": _latest.get("elapsed_ms", 0),
                                    "selected_agent": _latest.get("selected_agent", ""),
                                    "gnn_rl_enabled": _sel._gnn_rl_enabled,
                                    "total_selections": _sel.stats.get("total_selections", 0),
                                    "message": f"ML: {_latest.get('method', 'unknown')} (conf: {_latest.get('confidence', 0):.0%})",
                                },
                            }
                    except Exception:
                        pass  # Non-critical, skip silently

                # 🆕 agent_complete 이벤트에서 실행 결과 수집
                if converted.get("event") == "agent_complete":
                    agent_data = converted.get("data", {})
                    agent_id = agent_data.get("agent_id", "")
                    if agent_id:
                        full_result = agent_data.get("data", {}).get("full_result", {})
                        executed_agents.append({
                            "agent_id": agent_id,
                            "agent_name": agent_data.get("agent_name", agent_id),
                            "result": full_result.get("data", {}).get("result", {}) if isinstance(full_result, dict) else full_result,
                            "execution_time": agent_data.get("elapsed_time_ms", 0) / 1000 if agent_data.get("elapsed_time_ms") else 0,
                            "confidence": 0.9,
                        })

                # 🆕 workflow_complete 이벤트에 수집된 에이전트 정보 주입
                if converted.get("event") == "final_result":
                    # agent_results가 비어있으면 수집된 데이터로 대체
                    inner_data = converted.get("data", {}).get("data", {})
                    if not inner_data.get("agent_results") and executed_agents:
                        inner_data["agent_results"] = executed_agents
                    # 🆕 KG 시각화 데이터 재생성 (실제 에이전트 기반)
                    if executed_agents or selected_agents_from_plan:
                        agents_for_kg = executed_agents if executed_agents else [
                            {"agent_id": a.get("agent_id"), "agent_name": a.get("agent_name"), "result": {}, "execution_time": 0, "confidence": 0.9}
                            for a in selected_agents_from_plan
                        ]
                        inner_data["knowledge_graph_visualization"] = self._create_kg_visualization_from_workflow(
                            query=query,
                            agent_results=agents_for_kg,
                            workflow_id=inner_data.get("metadata", {}).get("workflow_id", ""),
                        )
                        logger.info(f"📊 Re-generated KG visualization with {len(agents_for_kg)} actual agents")

                yield converted

        except Exception as e:
            logger.error(f"Orchestrator execution failed: {e}")
            yield {
                "event": "error",
                "data": {
                    "error_code": "EXECUTION_FAILED",
                    "message": f"워크플로우 실행 실패: {str(e)}",
                },
            }

    def _convert_orchestrator_event(self, event: Any) -> Dict[str, Any]:
        """Orchestrator 이벤트를 SSE 형식으로 변환."""
        if isinstance(event, dict):
            # dict인 경우에도 agent_id 보장
            return self._ensure_agent_info(event)

        # ProgressEvent 객체인 경우 - workflow_complete를 final_result로 변환
        if hasattr(event, "type"):
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

            # workflow_complete → final_result 변환
            if event_type == "workflow_complete":
                return self._convert_to_final_result(event)

        # ProgressEvent 객체인 경우 - to_dict() 메서드 사용
        if hasattr(event, "to_dict"):
            event_dict = event.to_dict()

            # agent_id와 agent_name 추출 (None 방지)
            agent_id = event_dict.get("agent_id") or ""
            display_name = event_dict.get("display_name") or agent_id

            # data 필드에서 추가 정보 추출
            event_data = event_dict.get("data") or {}

            result = {
                "event": event_dict.get("type", "unknown"),
                "data": {
                    "message": event_dict.get("message", ""),
                    "message_ko": event_dict.get("message_ko", ""),
                    "agent_id": agent_id,
                    "agent_name": display_name,  # agent_name 추가
                    "stage_id": event_dict.get("stage_id"),
                    "workflow_id": event_dict.get("workflow_id"),
                    "status": event_dict.get("status"),
                    "progress": event_dict.get("progress_percent"),
                    "data": event_data,
                    "error": event_dict.get("error"),
                    "elapsed_time_ms": event_dict.get("elapsed_time_ms"),
                    "display_name": display_name,
                    "icon": event_dict.get("icon"),
                },
            }
            return result

        # ProgressEvent 속성 직접 접근
        if hasattr(event, "type") and hasattr(event, "message"):
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)

            # agent_id와 display_name 추출 (None 방지)
            agent_id = getattr(event, "agent_id", None) or ""
            display_name = getattr(event, "display_name", None) or agent_id

            return {
                "event": event_type,
                "data": {
                    "message": event.message,
                    "message_ko": getattr(event, "message_ko", ""),
                    "agent_id": agent_id,
                    "agent_name": display_name,  # agent_name 추가
                    "stage_id": getattr(event, "stage_id", None),
                    "workflow_id": getattr(event, "workflow_id", None),
                    "status": getattr(event, "status", None),
                    "progress": getattr(event, "progress_percent", None),
                    "data": getattr(event, "data", None),
                    "error": getattr(event, "error", None),
                    "display_name": display_name,
                },
            }

        return {
            "event": "unknown",
            "data": {"raw": str(event)},
        }

    def _ensure_agent_info(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """이벤트에 agent_id/agent_name이 항상 포함되도록 보장하고 event 타입 추론."""
        # 🆕 event 필드가 없으면 message/stage 기반으로 추론
        if "event" not in event:
            event["event"] = self._infer_event_type(event)

        if "data" in event and isinstance(event["data"], dict):
            data = event["data"]
            # agent_id가 없거나 None이면 빈 문자열로 대체
            if not data.get("agent_id"):
                data["agent_id"] = ""
            # agent_name이 없으면 agent_id 또는 display_name 사용
            if not data.get("agent_name"):
                data["agent_name"] = data.get("display_name") or data.get("agent_id") or ""
        return event

    def _infer_event_type(self, event: Dict[str, Any]) -> str:
        """메시지/데이터 기반으로 이벤트 타입 추론."""
        message = event.get("message", "").lower()
        stage = event.get("stage", "").lower()
        data = event.get("data", {})

        # Planning events
        if "execution plan created" in message or "실행 계획 생성 완료" in message:
            return "planning_complete"
        if "execution plan" in message and "creating" in message:
            return "planning_start"
        if "execution plan validated" in message or "검증 완료" in message:
            return "plan_validated"

        # Stage events (agents 포함 여부로 판단)
        if isinstance(data, dict) and "stages" in data:
            return "planning_complete"

        # Agent events
        if "agent" in message and "started" in message:
            return "agent_started"
        if "agent" in message and ("completed" in message or "complete" in message):
            return "agent_completed"

        # Stage-based mapping
        stage_map = {
            "initialization": "initialization",
            "ontology_initialization": "ontology_init",
            "agents_loading": "agents_loading",
        }
        if stage in stage_map:
            return stage_map[stage]

        # Agents available
        if "agents" in event and isinstance(event.get("agents"), list) and len(event.get("agents", [])) > 5:
            return "agents_available"

        # Workflow events
        if "workflow" in message and "start" in message:
            return "workflow_start"
        if "workflow" in message and ("complete" in message or "completed" in message):
            return "workflow_complete"

        # Default based on stage
        if stage:
            return stage

        return "progress"

    def _convert_to_final_result(self, event: Any) -> Dict[str, Any]:
        """workflow_complete 이벤트를 final_result로 변환.

        프론트엔드(logos_web)가 기대하는 final_result 형식:
        {
            "event": "final_result",
            "data": {
                "code": 0,
                "data": {
                    "result": "최종 응답 내용",
                    "agent_results": [...],
                    "metadata": {...},
                    "knowledge_graph_visualization": {...}
                }
            }
        }
        """
        # event.data에서 final_output 추출
        event_data = getattr(event, "data", {}) or {}
        final_output = event_data.get("final_output", {})

        result_content = ""
        agent_results = []

        # final_output이 WorkflowResult 객체인 경우 처리
        if hasattr(final_output, "final_output"):
            result_content = self._extract_answer_from_output(final_output.final_output)

            # stages에서 agent_results 추출
            if hasattr(final_output, "stages"):
                for stage in final_output.stages:
                    if hasattr(stage, "agent_outputs"):
                        for agent_id, output in stage.agent_outputs.items():
                            agent_results.append({
                                "agent_id": agent_id,
                                "agent_name": agent_id,
                                "result": {"content": self._extract_answer_from_output(output)},
                                "execution_time": getattr(stage, "execution_time_ms", 0) / 1000,
                                "confidence": 0.9,
                            })
        elif isinstance(final_output, list):
            # Handle "combine" aggregation type - final_output is a list of all agent results
            # Structure: [{"agent_id": "...", "stage_id": ..., "data": {...}}, ...]
            agent_results = []
            result_parts = []
            for item in final_output:
                if isinstance(item, dict):
                    agent_id = item.get("agent_id", "unknown")
                    stage_id = item.get("stage_id", 0)
                    data = item.get("data", {})

                    # Extract answer from nested data structure
                    answer = self._extract_answer_from_output(data)

                    agent_results.append({
                        "agent_id": agent_id,
                        "agent_name": agent_id,
                        "stage_id": stage_id,
                        "result": {"content": answer},
                        "data": data,
                        "execution_time": 0,
                        "confidence": 0.9,
                    })

                    if answer:
                        result_parts.append(answer)

            # Combine all results into a single result content
            result_content = "\n\n---\n\n".join(result_parts) if result_parts else ""
            logger.info(f"📊 Combined {len(agent_results)} agent results from list aggregation")
        elif isinstance(final_output, dict):
            result_content = self._extract_answer_from_output(final_output)
            agent_results = final_output.get("agent_results", [])
        elif isinstance(final_output, str):
            result_content = final_output
        else:
            result_content = str(final_output) if final_output else ""

        # Knowledge Graph 시각화 데이터 생성 - 실제 워크플로우 결과 기반
        kg_visualization = None
        workflow_id = getattr(event, "workflow_id", "")
        query = getattr(event, "query", "") or ""

        # 이벤트 데이터에서 쿼리 추출 시도
        if not query:
            event_data = getattr(event, "data", {})
            if isinstance(event_data, dict):
                query = event_data.get("query", event_data.get("data", {}).get("query", ""))

        try:
            if agent_results:
                # ✅ 실제 워크플로우 결과 기반 동적 시각화 생성
                kg_visualization = self._create_kg_visualization_from_workflow(
                    query=query or "User Query",
                    agent_results=agent_results,
                    workflow_id=workflow_id,
                )
                logger.info(f"📊 Dynamic workflow visualization generated: {len(kg_visualization.get('nodes', []))} nodes, {len(kg_visualization.get('edges', []))} edges")
            elif self._visualization_manager:
                # 폴백: 정적 시각화 (agent_results가 없는 경우에만)
                kg_visualization = self._visualization_manager.get_knowledge_graph_visualization(max_nodes=50)
                logger.debug(f"📊 Static knowledge graph visualization: {len(kg_visualization.get('nodes', []))} nodes")
        except Exception as kg_error:
            logger.warning(f"⚠️ Knowledge graph visualization failed: {kg_error}")
            kg_visualization = None

        return {
            "event": "final_result",
            "data": {
                "code": 0,
                "data": {
                    "result": result_content,
                    "agent_results": agent_results,
                    "metadata": {
                        "elapsed_time_ms": getattr(event, "elapsed_time_ms", 0),
                        "workflow_id": workflow_id,
                    },
                    "knowledge_graph_visualization": kg_visualization,
                },
            },
        }

    def _extract_answer_from_output(self, output: Any) -> str:
        """중첩된 ACP 응답에서 answer/result 추출.

        ACP 응답 구조:
        {'success': True, 'data': {'result': {'answer': '...', 'reasoning': '...'}}}
        또는
        {'answer': '...'}
        또는
        코드 생성: {'response_type': 'advanced_code_generation_result', 'content': '...', 'code': '...'}
        또는
        문자열
        """
        if isinstance(output, str):
            return output

        if not isinstance(output, dict):
            return str(output) if output else ""

        # 중첩 구조 탐색: success.data.result.answer 또는 data.result.answer
        current = output

        # success > data > result 경로 따라가기
        for key in ["data", "result"]:
            if isinstance(current, dict) and key in current:
                current = current[key]

        # 최종적으로 answer, result, content, code 중 추출
        if isinstance(current, dict):
            # 코드 생성 응답 처리 (code 필드가 있으면 코드 포함)
            if "code" in current and current.get("response_type", "").endswith("code_generation_result"):
                content = current.get("content", "")
                code = current.get("code", "")
                language = current.get("language", "python")
                if code:
                    return f"{content}\n\n```{language}\n{code}\n```"
                return content

            if "answer" in current:
                return current["answer"]
            if "result" in current:
                result = current["result"]
                if isinstance(result, str):
                    return result
                if isinstance(result, dict) and "answer" in result:
                    return result["answer"]
            if "content" in current:
                return current["content"]
            # 🆕 analysis_agent의 summary 필드 처리
            if "summary" in current:
                return current["summary"]
            # 🆕 message 필드 처리 (일부 에이전트 응답 형식)
            if "message" in current and isinstance(current["message"], str):
                return current["message"]
            # 없으면 전체를 문자열로
            return str(current)

        return str(current) if current else ""

    def _get_agent_icon(self, agent_id: str) -> str:
        """에이전트 ID에 따른 아이콘 반환."""
        icons = {
            "internet_agent": "🌐",
            "analysis_agent": "📊",
            "data_visualization_agent": "📈",
            "visualization_agent": "📈",
            "samsung_gateway_agent": "📱",
            "llm_search_agent": "🔍",
            "shopping_agent": "🛒",
            "code_generation_agent": "💻",
            "weather_agent": "🌤️",
            "scheduler_agent": "📅",
            "calculator_agent": "🧮",
            "restaurant_finder_agent": "🍽️",
        }
        return icons.get(agent_id, "🤖")

    def _create_kg_visualization_from_workflow(
        self,
        query: str,
        agent_results: List[Dict[str, Any]],
        workflow_id: str = "",
    ) -> Dict[str, Any]:
        """실제 워크플로우 결과를 기반으로 Knowledge Graph 시각화 데이터 생성.

        Args:
            query: 사용자 쿼리
            agent_results: 실행된 에이전트 결과 목록
            workflow_id: 워크플로우 ID

        Returns:
            Neo4j 스타일 시각화 데이터 (nodes, edges, metadata)
        """
        nodes = []
        edges = []

        # 1. Query 노드 생성 (중앙 노드)
        query_node_id = f"query_{hash(query) % 10000}"
        query_display = query[:30] + "..." if len(query) > 30 else query
        nodes.append({
            "id": query_node_id,
            "type": "task",
            "label": query_display,
            "full_label": query,
            "properties": {
                "type": "user_query",
                "workflow_id": workflow_id,
            },
        })

        # 2. Workflow 노드 생성
        workflow_node_id = f"workflow_{workflow_id or 'current'}"
        nodes.append({
            "id": workflow_node_id,
            "type": "workflow",
            "label": f"Workflow",
            "properties": {
                "agent_count": len(agent_results),
                "status": "completed",
            },
        })

        # Query → Workflow 연결
        edges.append({
            "source": query_node_id,
            "target": workflow_node_id,
            "type": "TRIGGERS",
            "label": "triggers",
        })

        # 3. Agent 노드 생성 (실제 실행된 에이전트들)
        prev_agent_id = workflow_node_id
        for idx, agent_result in enumerate(agent_results):
            agent_id = agent_result.get("agent_id", f"agent_{idx}")
            agent_name = agent_result.get("agent_name", agent_id)
            execution_time = agent_result.get("execution_time", 0)
            confidence = agent_result.get("confidence", 0.9)

            # Agent 노드 추가
            agent_node_id = f"agent_{agent_id}_{idx}"
            nodes.append({
                "id": agent_node_id,
                "type": "agent",
                "label": agent_name,
                "properties": {
                    "agent_id": agent_id,
                    "icon": self._get_agent_icon(agent_id),
                    "execution_time": f"{execution_time:.2f}s" if isinstance(execution_time, (int, float)) else str(execution_time),
                    "confidence": confidence,
                    "order": idx + 1,
                    "status": "completed",
                },
            })

            # Workflow → Agent 연결 (첫 번째 에이전트)
            if idx == 0:
                edges.append({
                    "source": workflow_node_id,
                    "target": agent_node_id,
                    "type": "EXECUTES",
                    "label": "executes",
                })
            else:
                # 이전 에이전트 → 현재 에이전트 연결 (순차 실행)
                edges.append({
                    "source": prev_agent_id,
                    "target": agent_node_id,
                    "type": "THEN",
                    "label": f"step {idx + 1}",
                })

            prev_agent_id = agent_node_id

            # 4. Result 노드 생성 (각 에이전트의 결과)
            result_data = agent_result.get("result", {})
            if result_data:
                result_node_id = f"result_{agent_id}_{idx}"
                result_content = ""
                if isinstance(result_data, dict):
                    result_content = result_data.get("content", result_data.get("answer", ""))[:50]
                elif isinstance(result_data, str):
                    result_content = result_data[:50]

                if result_content:
                    nodes.append({
                        "id": result_node_id,
                        "type": "result",
                        "label": result_content + "..." if len(str(result_content)) > 50 else result_content,
                        "properties": {
                            "agent_id": agent_id,
                            "status": "success",
                        },
                    })

                    # Agent → Result 연결
                    edges.append({
                        "source": agent_node_id,
                        "target": result_node_id,
                        "type": "PRODUCES",
                        "label": "produces",
                    })

        # 5. Domain/Capability 노드 추가 (에이전트 기능 기반)
        domain_mapping = {
            "weather_agent": ("weather", "날씨 정보"),
            "internet_agent": ("web", "웹 검색"),
            "analysis_agent": ("analysis", "데이터 분석"),
            "shopping_agent": ("commerce", "쇼핑"),
            "calculator_agent": ("math", "수학 계산"),
            "scheduler_agent": ("calendar", "일정 관리"),
            "code_generation_agent": ("coding", "코드 생성"),
            "llm_search_agent": ("search", "LLM 검색"),
        }

        added_domains = set()
        for idx, agent_result in enumerate(agent_results):
            agent_id = agent_result.get("agent_id", "")
            if agent_id in domain_mapping and agent_id not in added_domains:
                domain_key, domain_label = domain_mapping[agent_id]
                domain_node_id = f"domain_{domain_key}"

                nodes.append({
                    "id": domain_node_id,
                    "type": "domain",
                    "label": domain_label,
                    "properties": {
                        "domain": domain_key,
                    },
                })

                # Agent → Domain 연결
                agent_node_id = f"agent_{agent_id}_{idx}"
                edges.append({
                    "source": agent_node_id,
                    "target": domain_node_id,
                    "type": "BELONGS_TO",
                    "label": "belongs to",
                })

                added_domains.add(agent_id)

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "workflow_id": workflow_id,
                "query": query,
                "agent_count": len(agent_results),
                "generated_at": "dynamic",
            },
        }

    def _enhance_planning_complete(
        self,
        event: Dict[str, Any],
        available_agents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """planning_complete 이벤트를 강화하여 워크플로우 정보 추가."""
        data = event.get("data", {})
        inner_data = data.get("data", {})

        # stages 정보 추출
        stages = inner_data.get("stages", data.get("stages", []))

        # 선택된 에이전트 ID 추출
        selected_agent_ids = set()
        for stage in stages:
            for agent_id in stage.get("agents", []):
                selected_agent_ids.add(agent_id)

        # 에이전트 상세 정보 매핑
        agents_map = {
            a.get("agent_id", a.get("name", "")): a
            for a in available_agents
        }

        # 선택된 에이전트 상세 정보
        selected_agents_detail = []
        for stage_idx, stage in enumerate(stages):
            for agent_id in stage.get("agents", []):
                agent_info = agents_map.get(agent_id, {})
                selected_agents_detail.append({
                    "agent_id": agent_id,
                    "agent_name": agent_info.get("name", agent_id),
                    "description": agent_info.get("description", ""),
                    "stage": stage_idx + 1,
                    "execution_type": stage.get("execution_type", "sequential"),
                    "icon": self._get_agent_icon(agent_id),
                    "purpose": f"Stage {stage_idx + 1}에서 실행",
                    "order": stage_idx + 1,
                })

        # 워크플로우 시각화 문자열 생성
        workflow_visualization = self._create_workflow_visualization(stages)

        # 이벤트 데이터 강화
        event["data"]["selected_agents"] = selected_agents_detail
        event["data"]["workflow_visualization"] = workflow_visualization
        event["data"]["total_stages"] = len(stages)
        event["data"]["total_agents"] = len(selected_agent_ids)

        # agents_selected 호환 형식 추가 (data 내부)
        agents_list = [
            {
                "agent_id": a["agent_id"],
                "agent_name": a["agent_name"],
                "purpose": a["purpose"],
                "order": a["order"],
                "status": "pending",
                "icon": a["icon"],
            }
            for a in selected_agents_detail
        ]
        event["data"]["agents"] = agents_list

        # 🆕 최상위 레벨에도 추가 (프론트엔드 호환성)
        event["agents"] = agents_list
        event["selected_agents"] = selected_agents_detail
        event["workflow_visualization"] = workflow_visualization
        event["total_stages"] = len(stages)
        event["total_agents"] = len(selected_agent_ids)

        return event

    def _create_workflow_visualization(self, stages: List[Dict[str, Any]]) -> str:
        """워크플로우 시각화 문자열 생성."""
        if not stages:
            return ""

        parts = []
        for i, stage in enumerate(stages):
            agents = stage.get("agents", [])
            exec_type = stage.get("execution_type", "sequential")

            if len(agents) == 1:
                parts.append(f"{self._get_agent_icon(agents[0])} {agents[0]}")
            elif exec_type == "parallel":
                agent_strs = [f"{self._get_agent_icon(a)} {a}" for a in agents]
                parts.append(f"[{' || '.join(agent_strs)}]")
            else:
                agent_strs = [f"{self._get_agent_icon(a)} {a}" for a in agents]
                parts.append(f"({' → '.join(agent_strs)})")

        return " → ".join(parts)

    async def _fallback_stream(
        self,
        query: str,
        user_email: str,
        session_id: Optional[str] = None,
        project_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Orchestrator 사용 불가 시 직접 ACP 서버 호출.

        주의: DataTransformer가 작동하지 않으므로 멀티 에이전트 간 데이터 전달 불가.
        """
        import aiohttp

        yield {
            "event": "warning",
            "data": {
                "message": "⚠️ Orchestrator 사용 불가 - 직접 ACP 호출 모드",
            },
        }

        payload = {
            "query": query,
            "email": user_email,
            "sessionid": session_id,
            "project_id": project_id,
            "context": context or {},
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.acp_base_url}/stream/multi",
                    json=payload,
                    headers={"Accept": "text/event-stream"},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    if response.status != 200:
                        yield {
                            "event": "error",
                            "data": {
                                "error_code": "ACP_ERROR",
                                "message": f"ACP 서버 오류: {response.status}",
                            },
                        }
                        return

                    buffer = ""
                    async for chunk in response.content.iter_any():
                        buffer += chunk.decode("utf-8")

                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            event = self._parse_sse_event(event_str)
                            if event:
                                yield event

        except Exception as e:
            yield {
                "event": "error",
                "data": {
                    "error_code": "CONNECTION_ERROR",
                    "message": f"ACP 서버 연결 실패: {str(e)}",
                },
            }

    def _parse_sse_event(self, event_str: str) -> Optional[Dict[str, Any]]:
        """SSE 이벤트 문자열 파싱."""
        import json

        event_type = "message"
        data = ""

        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()

        if data:
            try:
                return {
                    "event": event_type,
                    "data": json.loads(data),
                }
            except json.JSONDecodeError:
                return {
                    "event": event_type,
                    "data": {"message": data},
                }

        return None


# Global instance
_orchestrator_service: Optional[OrchestratorService] = None


def get_orchestrator_service() -> OrchestratorService:
    """Get global OrchestratorService instance."""
    global _orchestrator_service
    if _orchestrator_service is None:
        _orchestrator_service = OrchestratorService()
    return _orchestrator_service


async def close_orchestrator_service() -> None:
    """Close global OrchestratorService — saves KG, stats, and ML models."""
    global _orchestrator_service

    # 1. Save KG checkpoint
    try:
        from ontology.engines.knowledge_graph_clean import get_knowledge_graph_engine
        kg = get_knowledge_graph_engine()
        kg.save_to_disk()
    except Exception as e:
        logger.warning(f"⚠️ KG checkpoint save on shutdown failed: {e}")

    # 2. Save HybridAgentSelector stats
    try:
        from ontology.core.hybrid_agent_selector import get_hybrid_selector
        selector = get_hybrid_selector()
        selector.save_stats()
    except Exception as e:
        logger.warning(f"⚠️ Selector stats save on shutdown failed: {e}")

    # 3. Save GNN+RL ML models
    try:
        from ontology.core.hybrid_agent_selector import get_hybrid_selector
        selector = get_hybrid_selector()
        if selector._intelligent_selector is not None:
            selector._intelligent_selector.save_models()
            logger.info("💾 GNN+RL models saved on shutdown")
    except Exception as e:
        logger.warning(f"⚠️ GNN+RL model save on shutdown failed: {e}")

    if _orchestrator_service:
        logger.info("👋 OrchestratorService shutdown complete (checkpoints saved)")
        _orchestrator_service = None
