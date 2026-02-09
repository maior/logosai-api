# CLAUDE.md - logos_api Development Guidelines

logos_api FastAPI 서버 개발 가이드입니다.

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | logos_api |
| **기술 스택** | FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL |
| **포트** | 8090 |
| **상태** | ✅ Production Ready (Ontology + ACP 통합 완료) |

## ⚠️ 중요: Django와 독립적

**logos_api는 Django(logos_server)와 연동하지 않습니다.**

- logos_api는 독립적인 FastAPI 백엔드 서버
- 온톨로지 시스템(`ontology/`)을 직접 import하여 사용
- ACP Server와 직접 통신
- Django 서버(8080)와 별개로 작동

```
❌ 잘못된 이해:
   logos_api → Django → ACP Server

✅ 올바른 아키텍처:
   logos_api → Ontology System → ACP Server
        ↓
   독립적인 FastAPI 서버
```

## 서비스 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                     logos_api Service Architecture                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   Frontend (Website:8000)                                            │
│        │                                                             │
│        ▼ HTTP/SSE                                                    │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    logos_api (8090)                          │   │
│   │   FastAPI Backend                                            │   │
│   │   ├── app/services/chat_service.py                           │   │
│   │   ├── app/services/orchestrator_service.py  ⭐ 핵심          │   │
│   │   └── app/services/acp_client.py                             │   │
│   └────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│                            ▼ Direct Import                           │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              Ontology System (ontology/)                     │   │
│   │   ├── core/unified_query_processor.py                        │   │
│   │   ├── core/hybrid_agent_selector.py  ⭐ NEW                  │   │
│   │   ├── core/agent_sync_service.py     ⭐ NEW                  │   │
│   │   ├── orchestrator/workflow_orchestrator.py                  │   │
│   │   └── engines/knowledge_graph_clean.py                       │   │
│   └────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│                            ▼ HTTP SSE                                │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │              ACP Server (8888)                               │   │
│   │   logosai/logosai/examples/standalone_acp_server.py          │   │
│   │   └── agents/ (61+ 에이전트)                                 │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   Database: PostgreSQL                                               │
│   - logosus schema (logos_api 독립, UUID PK)                         │
│     ├── users (UUID id, email unique index)                          │
│     ├── conversations (채팅 세션)                                    │
│     ├── messages                                                     │
│     ├── documents (RAG)                                              │
│     └── analytics                                                    │
│   - logosai schema (logos_server 공유, Marketplace)                  │
│                                                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 핵심 파일

| 파일 | 설명 |
|------|------|
| `app/main.py` | FastAPI 앱 엔트리포인트 |
| `app/config.py` | 환경 설정 (Pydantic Settings) |
| `app/database.py` | SQLAlchemy async 설정 |
| `app/services/orchestrator_service.py` | **⭐ 온톨로지 오케스트레이터 통합** |
| `app/services/chat_service.py` | 채팅 서비스 (SSE 스트리밍) |
| `app/services/acp_client.py` | ACP 서버 클라이언트 |
| `app/routers/chat.py` | 채팅 API 라우터 |
| `app/models/` | SQLAlchemy 모델 |
| `app/models/logosus/` | **⭐ logosus 스키마 모델 (NEW)** |
| `app/services/conversation_service.py` | **⭐ 채팅 대화 서비스 (NEW)** |
| `app/services/user_service.py` | 사용자 서비스 (logosus 기반) |
| `app/services/agent_registry_service.py` | **⭐ DB 기반 에이전트 레지스트리 (NEW)** |
| `app/routers/agents.py` | 에이전트 관리 REST API (NEW) |
| `app/models/logosus/agent.py` | ACPServer + RegisteredAgent 모델 (NEW) |
| `app/schemas/agent.py` | 에이전트 Pydantic 스키마 (NEW) |
| `app/middleware/response_normalizer.py` | 응답 포맷 정규화 (JSON+Markdown 혼재 처리 포함) |
| `app/middleware/response_middleware.py` | SSE 이벤트 래퍼 |
| `app/models/logosus/memory.py` | **⭐ UserMemory 모델 (NEW)** |
| `app/schemas/memory.py` | 메모리 Pydantic 스키마 (NEW) |
| `app/services/memory_service.py` | **⭐ 메모리 서비스 (스마트 활용 포함) (NEW)** |
| `app/routers/memory.py` | 메모리 CRUD REST API (NEW) |

## 온톨로지 시스템 통합

### OrchestratorService

`app/services/orchestrator_service.py`에서 온톨로지 시스템을 직접 import하여 사용:

```python
from ontology.orchestrator import (
    WorkflowOrchestrator,
    QueryPlanner,
    ExecutionEngine,
    AgentRegistry,
)
from ontology.core.unified_query_processor import UnifiedQueryProcessor

# 온톨로지 시스템으로 쿼리 분석 및 워크플로우 실행
orchestrator = WorkflowOrchestrator(
    agent_executor=self._execute_agent_via_acp,
    registry=self._registry,
)
```

### 하이브리드 에이전트 선택 (NEW)

Knowledge Graph + LLM 하이브리드 방식으로 에이전트 선택:

```python
from ontology.core.hybrid_agent_selector import get_hybrid_selector

selector = get_hybrid_selector()
agent, metadata = await selector.select_agent(
    query="삼성전자 주가 알려줘",
    available_agents=["internet_agent", "analysis_agent"],
    agents_info=agents_info
)

# 학습 루프 - 성공 시 피드백 저장
await selector.store_feedback(query, agent, success=True)
```

### 에이전트 동기화 (NEW)

ACP Server 에이전트를 Knowledge Graph에 자동 동기화:

```python
from ontology.core.agent_sync_service import initialize_agent_sync

# 서버 시작 시 전체 동기화
result = await initialize_agent_sync()
# {"total_agents": 61, "added": 54, "updated": 7}
```

### DB 기반 Dynamic Agent Registry (NEW 2026-02-06)

DB를 source of truth로 에이전트를 관리하고 ontology AgentRegistry에 동적 로드:

```python
from app.services.agent_registry_service import AgentRegistryService

service = AgentRegistryService(db)

# 서버 시작 시 자동 실행 (main.py lifespan)
await service.ensure_default_acp_server()    # 기본 ACP 서버 등록
await service.seed_defaults_if_empty()       # DEFAULT_AGENTS 시드
await service.sync_from_acp(server_id)       # ACP에서 실제 에이전트 동기화
await service.load_into_ontology_registry()  # DB → ontology in-memory 로드
```

**DB 모델**:
- `ACPServer`: ACP 서버 접속 정보 (url, health_status, is_active)
- `RegisteredAgent`: 에이전트 메타데이터 (agent_id, capabilities, tags, priority)

**REST API**:
- `GET /api/v1/agents/` - 전체 에이전트 목록
- `GET /api/v1/agents/{agent_id}` - 특정 에이전트 조회
- `POST /api/v1/agents/sync` - ACP 동기화 트리거
- `GET /api/v1/agents/servers/` - ACP 서버 목록

### 응답 포맷 자동 보정 (NEW 2026-02-06)

logos_web 프론트엔드가 기대하는 정규 포맷으로 SSE 응답 자동 보정:

```python
from app.middleware.response_middleware import normalized_event_generator

# chat.py에서 스트리밍 응답 래핑
raw_stream = service.stream_chat(query, email)
normalized = normalized_event_generator(raw_stream)
return EventSourceResponse(event_generator(normalized))
```

**자동 수정 항목**:
- 이중 중첩 `data.data.result` → `data.result` 평탄화
- agent_results에서 answer 자동 추출
- JSON 코드블록 마커 제거 (JSON+Markdown 혼재 시 Markdown만 추출)
- 에러 → 한국어 사용자 친화적 메시지

### User Memory System (NEW 2026-02-08)

사용자별 메모리를 저장하고 채팅 시 자동으로 활용:

```python
from app.services.memory_service import MemoryService

service = MemoryService(db)

# 메모리 CRUD
memory = await service.create_memory(user_id, content, memory_type, importance)
memories = await service.get_user_memories(user_id)

# 채팅 컨텍스트용 메모리 로드 (스마트 활용)
context_str = await service.load_memories_for_context(user_id)
# → 타입별 그룹화 + 차별화된 활용 가이드
```

**메모리 타입별 활용 원칙**:
| 타입 | 가이드 | 예시 |
|------|--------|------|
| `instruction` | 항상 적용 | "항상 한국어로 답변해줘" |
| `preference` | 명시적으로 다른 것을 요청하지 않는 한 적용 | "파이썬 선호" |
| `fact` | 쿼리와 관련 있을 때만 활용 | "성균관대 컴공 전공" |
| `context` | 관련 있을 때만 참고 | "졸업 프로젝트 진행 중" |

**SSE 이벤트**: 메모리가 로드되면 `memory_context` 이벤트 emit (initialization 전):
```json
{"event": "memory_context", "data": {"memory_count": 3, "message": "사용자 메모리 3건 로드됨"}}
```

**REST API**:
- `GET /api/v1/memories/` — 내 메모리 목록
- `POST /api/v1/memories/` — 메모리 생성 (201)
- `DELETE /api/v1/memories/{id}` — 메모리 삭제 (204, soft delete)

**배경 추출**: 채팅 후 `asyncio.create_task()`로 메모리 자동 추출 (Gemini gemini-2.5-flash-lite)

### 응답 포맷 가이드라인 (NEW 2026-02-08)

QueryPlanner 프롬프트에 쿼리 유형별 응답 포맷 지시가 포함됨:

| 쿼리 유형 | 포맷 지시 |
|-----------|----------|
| 검색/리서치 | `##` 소제목 + bullet point + 출처 |
| 계산/단순 답변 | 핵심 답변 먼저, 부연 최소 |
| 비교/분석 | Markdown 표 또는 항목별 비교 |
| 코드/기술 | 코드블록 + 단계별 설명 |

**핵심**: wall-of-text 금지 → 구조화된 Markdown 사용

## 서버 시작

⚠️ **항상 scripts/ 폴더의 스크립트 사용** (로그, PID 관리)

```bash
# ✅ 올바름 - 스크립트 사용
cd /Users/maior/Development/skku/Logos

./scripts/start_logos_api.sh       # logos_api 시작 (8090)
./scripts/start_agent_server.sh    # ACP 서버 시작 (8888)
./scripts/status.sh                # 상태 확인

# ❌ 잘못됨 - 직접 명령어 실행
uvicorn app.main:app --reload --port 8090  # 스크립트 사용!
```

## 데이터베이스 스키마

### 듀얼 스키마 구조 (NEW 2026-02)

logos_api는 두 개의 PostgreSQL 스키마를 사용합니다:

| 스키마 | 용도 | PK | 특징 |
|--------|------|-----|------|
| **logosus** | logos_api 독립 데이터 | UUID | 새로운 기능, RAG, Analytics |
| **logosai** | logos_server 공유 | email/int | Marketplace |

### logosus 스키마 (Primary - logos_api 독립)

```
logosus/
├── users          # UUID PK, email unique index
├── api_keys       # 프로그래매틱 접근용
├── sessions       # 인증 세션 (로그인)
├── conversations  # 채팅 세션 ⭐
├── messages       # 채팅 메시지
├── projects       # 프로젝트
├── documents      # RAG 문서
├── document_chunks
├── acp_servers    # ACP 서버 정보
├── registered_agents # 에이전트 레지스트리
├── user_memories  # 사용자 메모리 ⭐ NEW
├── search_history # RAG 검색 히스토리
├── rag_usage      # RAG 사용 통계
└── usage_stats    # API 사용 통계
```

```python
# logosus 모델 사용 예시
from app.models.logosus.user import User
from app.models.logosus.conversation import Conversation, Message

# User는 UUID id 사용
user.id  # '550e8400-e29b-41d4-a716-446655440000'
user.email  # 'user@example.com' (unique index)

# Conversation은 user_id (UUID)로 참조
conversation.user_id  # User의 UUID
```

### logosai 스키마 (Shared - Marketplace Only)

```python
# Marketplace 모델만 logosai 스키마 사용
from app.models.marketplace import MarketplaceAgent, AgentReview, AgentPurchase
```

### 주요 변경사항 (Migration from logosai)

```python
# ❌ 이전 (logosai - deprecated for core features)
user_email: Mapped[str] = mapped_column(
    ForeignKey("logosai.users.email"),
)

# ✅ 현재 (logosus)
user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False),
    ForeignKey("logosus.users.id", ondelete="CASCADE"),
)
```

### 모델 Import 가이드

```python
# 핵심 모델 (logosus)
from app.models import User, Conversation, Message, Document, Project

# Marketplace 모델 (logosai)
from app.models import MarketplaceAgent, AgentReview, AgentPurchase

# 레거시 모델 (deprecated - backward compatibility only)
from app.models import LegacyUser, LegacySession, LegacyMessage
```

### Message 모델 - role 필드
```python
# ✅ 올바름 - String으로 저장
role: Mapped[str] = mapped_column(String(20))

# 값: "user", "assistant", "system"
```

## ACP 클라이언트 주의사항

### 엔드포인트
```python
# ✅ 올바름
f"{base_url}/stream/multi"

# ❌ 잘못됨
f"{base_url}/api/v1/stream"
```

### 파라미터 이름
```python
# ✅ 올바름
payload = {
    "sessionid": session_id,  # 's' 소문자
}

# ❌ 잘못됨
payload = {
    "session_id": session_id,  # underscore 사용 불가
}
```

### final_result 이벤트 파싱
ACP 서버의 final_result는 3중 중첩 구조:
```python
# event.data 구조:
# {
#     "event": "final_result",
#     "data": {
#         "code": 0,
#         "data": {
#             "result": "실제 응답",
#             "agent_results": [...]
#         }
#     }
# }

data = event.get("data", {})
level1 = data.get("data", data)
level2 = level1.get("data", level1)
final_content = level2.get("result", "")
```

## SSE 이벤트 플로우

```
[memory_context] → initialization → ontology_init → agents_loading → agents_available
    → planning_start → planning_complete → stage_started
    → agent_started → agent_completed → stage_completed
    → integration_started → integration_completed → final_result → message_saved
```

## 테스트 명령어

```bash
# Health check
curl http://localhost:8090/health

# JWT 토큰 생성 (Python)
python -c "
from datetime import datetime, timedelta, timezone
from jose import jwt
expire = datetime.now(timezone.utc) + timedelta(hours=24)
payload = {'sub': 'test@example.com', 'exp': expire, 'type': 'access'}
print(jwt.encode(payload, 'your-super-secret-key-change-this-in-production', algorithm='HS256'))
"

# 채팅 스트리밍 테스트 (JWT 인증)
curl -X POST "http://localhost:8090/api/v1/chat/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "1+1 계산해줘"}'

# 채팅 스트리밍 테스트 (이메일 인증 - OAuth 사용자)
curl -X POST "http://localhost:8090/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "1+1 계산해줘", "email": "test@example.com"}'

# 세션 목록 조회 (이메일 인증)
curl -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/"

# 세션 생성 (이메일 인증)
curl -X POST "http://localhost:8090/api/v1/sessions/" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: test@example.com" \
  -d '{"title": "New Session"}'

# 세션 조회 (이메일 인증)
curl -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/{session_id}"

# 메시지 히스토리 (이메일 인증)
curl -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/{session_id}/messages"

# 세션 삭제 (이메일 인증)
curl -X DELETE -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/{session_id}"
```

## ⚠️ 필수 E2E 테스트 규칙 (MANDATORY)

**절대 원칙**: 구현 후 반드시 E2E 테스트를 수행한다. 테스트 없이 구현 완료로 간주하지 않는다.

### 테스트 순서

| # | 단계 | 방법 | 확인 항목 |
|---|------|------|----------|
| 1 | API Health Check | `curl http://localhost:8090/health` | `{"status":"healthy"}` |
| 2 | API 단위 테스트 | `curl` 또는 Python 스크립트 | 각 엔드포인트 정상 응답 |
| 3 | SSE 스트리밍 테스트 | SSE 이벤트 파싱 스크립트 | 이벤트 흐름 + final_result 구조 |
| 4 | 프론트엔드 추출 시뮬레이션 | Python E2E 테스트 | logos_web streaming.ts 로직과 호환 |
| 5 | logos_web 브라우저 확인 | `http://localhost:8010` | 실제 UI 렌더링 정상 |

### 프론트엔드 호환성 E2E 테스트

logos_api의 SSE 응답이 logos_web의 `streaming.ts` 추출 로직과 호환되는지 반드시 확인:

```python
# E2E 테스트 핵심: logos_web의 streaming.ts 추출 로직을 Python으로 시뮬레이션
# 1. logos_api에 실제 쿼리 전송 (SSE)
# 2. final_result 이벤트 수신
# 3. streaming.ts의 extractCleanResponse() 로직으로 answer 추출 시도
# 4. "No response received."가 아닌 실제 답변이 추출되는지 확인

async def test_query(query: str, expected_agent: str):
    # SSE 스트림 수신
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, json=payload) as resp:
            # 이벤트 파싱 (event: / data: / blank line)
            # final_result 이벤트에서 data 추출
            # simulate_frontend_final_result(data) 로 검증
            pass

# 필수 테스트 쿼리 (최소 3개)
tests = [
    ("1+1은 얼마야?", "calculator_agent"),      # 단순 계산
    ("달러 환율 알려줘", "currency_exchange_agent"), # 외부 API
    ("서울 날씨 알려줘", "weather_agent"),          # 실시간 데이터
]
```

### 테스트 체크리스트

구현 완료 전 반드시 확인:

- [ ] API 엔드포인트 정상 응답 (200 OK)
- [ ] SSE 이벤트 플로우 정상 (initialization → ... → final_result)
- [ ] final_result 데이터에서 answer 추출 가능
- [ ] logos_web streaming.ts 호환 (extractCleanResponse 시뮬레이션 통과)
- [ ] 에러 응답도 사용자 친화적 메시지로 변환됨
- [ ] 서버 로그에 에러 없음 (`tail -f logs/logos_api.log`)

### Agent Registry 테스트 (DB 기반)

```bash
# 에이전트 목록 확인
curl http://localhost:8090/api/v1/agents/ | python -m json.tool | head -20

# 특정 에이전트 확인
curl http://localhost:8090/api/v1/agents/currency_exchange_agent

# ACP 동기화
curl -X POST http://localhost:8090/api/v1/agents/sync

# ACP 서버 목록
curl http://localhost:8090/api/v1/agents/servers/
```

## 로그 확인

```bash
# logos_api 로그
tail -f logs/logos_api.log

# ACP 서버 로그
tail -f ../logosai/logs/acp_server.log
```

## 핵심 개발 원칙

### 하드코딩 금지 (No Hardcoding)

**절대 원칙**: 에이전트 선택, 쿼리 분류, 도메인 매칭에서 **하드코딩된 키워드 매칭을 사용하지 않는다**.

```python
# ❌ 금지: 하드코딩된 키워드 매칭
if "날씨" in query:
    agent = "weather_agent"
elif "쇼핑" in query:
    agent = "shopping_agent"

# ❌ 금지: 특정 에이전트 이름 하드코딩
DEFAULT_AGENT = "internet_agent"  # 폴백으로 internet_agent 지정

# ✅ 권장: 하이브리드 선택기 사용
from ontology.core.hybrid_agent_selector import get_hybrid_selector
selector = get_hybrid_selector()
agent, metadata = await selector.select_agent(query, available_agents, agents_info)
```

**이유**:
- 새 에이전트 추가 시 코드 수정 불필요
- LLM이 의미론적으로 쿼리와 에이전트 매칭
- Knowledge Graph 학습으로 시간이 지날수록 정확도 향상
- 다국어 자동 지원, 유지보수성 향상

**상세 가이드**: [ontology/CLAUDE.md](../ontology/CLAUDE.md) 참조

---

## 일반적인 문제 해결

### 1. `messagerole` enum 에러
```
type "messagerole" does not exist
```
**해결**: Message 모델의 role 필드를 `Enum` → `String(50)`으로 변경

### 2. ACP 서버 연결 실패
```
ACP health check failed
```
**해결**: ACP 서버 실행 확인
```bash
lsof -i :8888  # 포트 확인
python standalone_acp_server.py --enable-auto-agent-selection
```

### 3. 자동 에이전트 선택 비활성화 에러
```
자동 에이전트 선택이 비활성화되어 있습니다
```
**해결**: ACP 서버 시작 시 `--enable-auto-agent-selection` 플래그 추가

### 4. JWT 토큰 에러
```
Invalid or expired token
```
**해결**: `.env`의 `JWT_SECRET_KEY`와 토큰 생성 시 사용한 키가 일치하는지 확인

### 5. Ontology 모듈 import 에러
```
Ontology modules not available
```
**해결**: Python path에 ontology 디렉토리 추가 확인
```python
import sys
sys.path.insert(0, '/path/to/Logos')
sys.path.insert(0, '/path/to/Logos/ontology')
```

## 관련 문서

- [README.md](./README.md) - 프로젝트 소개 및 API 문서
- [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) - 개발 계획 및 진행 상황
- [docs/ANALYSIS.md](./docs/ANALYSIS.md) - 시스템 분석 문서
- [../ontology/CLAUDE.md](../ontology/CLAUDE.md) - 온톨로지 시스템 가이드
- [../CLAUDE.md](../CLAUDE.md) - 메인 프로젝트 가이드

---

*최종 업데이트: 2026-02-08 (User Memory System, 메모리 UI 인디케이터, 응답 포맷 가이드라인, JSON+Markdown 혼재 처리)*
