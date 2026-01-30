# CLAUDE.md - logos_api Development Guidelines

logos_api FastAPI 서버 개발 가이드입니다.

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | logos_api |
| **기술 스택** | FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL |
| **포트** | 8090 |
| **상태** | ✅ Production Ready (ACP 통합 완료) |

## 서비스 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                     logos_api Service Architecture                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Frontend (Website:3000)                                           │
│        │                                                            │
│        ▼ HTTP/SSE                                                   │
│   ┌─────────────────┐                                               │
│   │ logos_api (8090)│  FastAPI Backend                              │
│   │   app/          │                                               │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼ HTTP SSE (/stream/multi)                               │
│   ┌─────────────────┐                                               │
│   │ ACP Server(8888)│  Agent Execution Runtime                      │
│   │ logosai/        │                                               │
│   └─────────────────┘                                               │
│                                                                     │
│   Database: PostgreSQL (logosai schema)                             │
│   - logosai.users (email as PK)                                     │
│   - logosai.sessions                                                │
│   - logosai.messages                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 핵심 파일

| 파일 | 설명 |
|------|------|
| `app/main.py` | FastAPI 앱 엔트리포인트 |
| `app/config.py` | 환경 설정 (Pydantic Settings) |
| `app/database.py` | SQLAlchemy async 설정 |
| `app/services/acp_client.py` | ACP 서버 클라이언트 |
| `app/services/chat_service.py` | 채팅 서비스 (SSE 스트리밍) |
| `app/routers/chat.py` | 채팅 API 라우터 |
| `app/models/` | SQLAlchemy 모델 |

## 서버 시작

```bash
# 가상환경 활성화
source ../.venv/bin/activate

# 개발 서버 시작
uvicorn app.main:app --reload --port 8090

# ACP 서버도 필요 (별도 터미널)
cd ../logosai/logosai/examples
python standalone_acp_server.py --enable-auto-agent-selection
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
initialization → ontology_init → multi_agent_init → query_analysis_started
    → intent_analysis (x3) → agent_scoring → agent_query_generated
    → analysis_complete → agents_selected → agent_started → agent_completed
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

## 관련 문서

- [README.md](./README.md) - 프로젝트 소개 및 API 문서
- [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) - 개발 계획 및 진행 상황
- [docs/ANALYSIS.md](./docs/ANALYSIS.md) - 시스템 분석 문서
- [../CLAUDE.md](../CLAUDE.md) - 메인 프로젝트 가이드

---

*최종 업데이트: 2026-01-30*
