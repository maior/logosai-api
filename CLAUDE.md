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
│   Database: PostgreSQL (logosai schema)                              │
│   - logosai.users (email as PK)                                      │
│   - logosai.sessions                                                 │
│   - logosai.messages                                                 │
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

## 데이터베이스 주의사항

### 스키마: `logosai`
모든 테이블은 `logosai` 스키마에 위치합니다:
```python
__table_args__ = {"schema": "logosai"}
```

### 사용자 참조: `email` (not UUID)
```python
# ✅ 올바름
user_email: Mapped[str] = mapped_column(
    ForeignKey("logosai.users.email"),
)

# ❌ 잘못됨 - users 테이블에 id 컬럼 없음
user_id: Mapped[str] = mapped_column(
    ForeignKey("logosai.users.id"),
)
```

### Message 모델 - role 필드
```python
# ✅ 올바름 - String으로 저장
role: Mapped[str] = mapped_column(String(50))

# _save_message에서 enum → string 변환
role=role.value  # MessageRole.USER → 'user'
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
initialization → ontology_init → agents_loading → agents_available
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

# 채팅 스트리밍 테스트
curl -X POST "http://localhost:8090/api/v1/chat/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "1+1 계산해줘"}'

# 세션 조회
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8090/api/v1/sessions/{session_id}"

# 메시지 히스토리
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8090/api/v1/sessions/{session_id}/messages"
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

*최종 업데이트: 2026-01-31*
