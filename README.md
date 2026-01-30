# LogosAI API

FastAPI 기반의 LogosAI 백엔드 서버입니다. 온톨로지 기반 멀티 에이전트 AI 시스템을 위한 RESTful API를 제공합니다.

> **상태**: ✅ Production Ready (2026-01-30)
> ACP 서버 통합 완료, 전체 채팅 플로우 검증 완료

## 주요 기능

- **인증 시스템**: Google OAuth + JWT 토큰 기반 인증
- **프로젝트 관리**: 프로젝트 CRUD, 아카이브, 공유
- **세션 관리**: 대화 세션 및 메시지 히스토리
- **실시간 채팅**: SSE 스트리밍 기반 AI 응답 ✅ (ACP 서버 통합 완료)
- **문서 관리**: 파일 업로드 및 RAG 검색
- **마켓플레이스**: 에이전트 등록/검색/구매

## 기술 스택

| 분류 | 기술 |
|------|------|
| Framework | FastAPI 0.109+ |
| Database | PostgreSQL + SQLAlchemy 2.0 (async) |
| Auth | JWT (python-jose) + Google OAuth |
| Validation | Pydantic v2 |
| Streaming | SSE (sse-starlette) |
| Migration | Alembic |

## 빠른 시작

### 요구사항

- Python 3.11+
- PostgreSQL 14+
- pip

### 설치

```bash
# 저장소 클론
git clone https://github.com/maior/logosai-api.git
cd logosai-api

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -e .

# 개발 의존성 설치 (선택)
pip install -e ".[dev]"
```

### 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
vim .env
```

필수 환경 변수:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/logosai

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-in-production

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# ACP Server (에이전트 실행 서버)
ACP_SERVER_URL=http://localhost:8888
```

### 데이터베이스 마이그레이션

```bash
# 마이그레이션 실행
alembic upgrade head
```

### 서버 실행

```bash
# 개발 서버 실행 (자동 리로드)
uvicorn app.main:app --reload --port 8090

# 프로덕션 실행
uvicorn app.main:app --host 0.0.0.0 --port 8090 --workers 4
```

서버 실행 후:
- API 문서: http://localhost:8090/docs
- ReDoc: http://localhost:8090/redoc
- Health Check: http://localhost:8090/health

## API 구조

### 인증 (Authentication)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/auth/login/google` | Google OAuth 로그인 |
| POST | `/api/v1/auth/refresh` | 토큰 갱신 |
| POST | `/api/v1/auth/logout` | 로그아웃 |

### 사용자 (Users)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/users/me` | 현재 사용자 정보 |
| PUT | `/api/v1/users/me` | 프로필 수정 |
| GET | `/api/v1/users/me/subscription` | 구독 정보 |
| PUT | `/api/v1/users/me/api-keys` | API 키 설정 |

### 프로젝트 (Projects)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/projects/` | 프로젝트 목록 |
| POST | `/api/v1/projects/` | 프로젝트 생성 |
| GET | `/api/v1/projects/{id}` | 프로젝트 조회 |
| PUT | `/api/v1/projects/{id}` | 프로젝트 수정 |
| DELETE | `/api/v1/projects/{id}` | 프로젝트 삭제 |
| POST | `/api/v1/projects/{id}/archive` | 아카이브 |

### 세션 (Sessions)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/sessions/` | 세션 목록 |
| POST | `/api/v1/sessions/` | 세션 생성 |
| GET | `/api/v1/sessions/{id}` | 세션 조회 |
| DELETE | `/api/v1/sessions/{id}` | 세션 삭제 |
| GET | `/api/v1/sessions/{id}/messages` | 메시지 목록 |

### 채팅 (Chat)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/chat/` | 채팅 (동기) |
| POST | `/api/v1/chat/stream` | 채팅 (SSE 스트리밍) |
| GET | `/api/v1/chat/health` | 서비스 상태 |

### 문서 (Documents)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/documents/` | 문서 목록 |
| POST | `/api/v1/documents/upload` | 문서 업로드 |
| GET | `/api/v1/documents/{id}` | 문서 조회 |
| PUT | `/api/v1/documents/{id}` | 문서 수정 |
| DELETE | `/api/v1/documents/{id}` | 문서 삭제 |
| POST | `/api/v1/documents/search` | RAG 검색 |
| POST | `/api/v1/documents/{id}/reprocess` | 문서 재처리 |
| GET | `/api/v1/documents/{id}/content` | 문서 내용 조회 |

지원 파일 형식: PDF, TXT, Markdown, DOCX, CSV, JSON (최대 50MB)

### 마켓플레이스 (Marketplace)

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/marketplace/agents` | 에이전트 검색/필터 |
| GET | `/api/v1/marketplace/agents/featured` | 추천 에이전트 |
| GET | `/api/v1/marketplace/agents/categories` | 카테고리 목록 |
| POST | `/api/v1/marketplace/agents` | 에이전트 등록 |
| GET | `/api/v1/marketplace/agents/my` | 내 에이전트 |
| GET | `/api/v1/marketplace/agents/{id}` | 에이전트 상세 |
| PUT | `/api/v1/marketplace/agents/{id}` | 에이전트 수정 |
| DELETE | `/api/v1/marketplace/agents/{id}` | 에이전트 삭제 |
| POST | `/api/v1/marketplace/agents/{id}/publish` | 에이전트 게시 |
| POST | `/api/v1/marketplace/agents/{id}/unpublish` | 게시 취소 |
| GET | `/api/v1/marketplace/agents/{id}/stats` | 통계 조회 |
| GET | `/api/v1/marketplace/agents/{id}/reviews` | 리뷰 목록 |
| POST | `/api/v1/marketplace/agents/{id}/reviews` | 리뷰 작성 |
| PUT | `/api/v1/marketplace/agents/{id}/reviews` | 리뷰 수정 |
| DELETE | `/api/v1/marketplace/agents/{id}/reviews` | 리뷰 삭제 |
| POST | `/api/v1/marketplace/agents/{id}/purchase` | 에이전트 구매 |
| GET | `/api/v1/marketplace/purchases` | 구매 내역 |

가격 유형: 무료(free), 일회성(one_time), 구독(subscription), 사용량 기반(usage_based)

## ACP 서버 통합 아키텍처

logos_api는 ACP(Agent Communication Protocol) 서버와 통합되어 멀티 에이전트 AI 시스템을 제공합니다.

### 전체 플로우

```
Frontend (Website)
    │
    ▼ POST /api/v1/chat/stream
┌─────────────────────────────────────────────┐
│              logos_api (8090)               │
├─────────────────────────────────────────────┤
│ 1. JWT 인증 → 사용자 조회                   │
│ 2. 세션 생성/조회                           │
│ 3. 사용자 메시지 저장 (role: user)          │
│ 4. ACP 서버로 스트리밍 요청                 │
└─────────────────┬───────────────────────────┘
                  │ SSE Stream
                  ▼
┌─────────────────────────────────────────────┐
│              ACP Server (8888)              │
├─────────────────────────────────────────────┤
│ 5. 쿼리 분석 (LLM: gemini-2.5-flash-lite)  │
│ 6. 에이전트 선택 (자동)                     │
│ 7. 에이전트 실행                            │
│ 8. 결과 통합 (LLM)                          │
│ 9. final_result 이벤트 전송                 │
└─────────────────┬───────────────────────────┘
                  │ SSE Events
                  ▼
┌─────────────────────────────────────────────┐
│              logos_api (8090)               │
├─────────────────────────────────────────────┤
│ 10. Assistant 메시지 저장 (role: assistant) │
│ 11. message_saved 이벤트 전송               │
└─────────────────┬───────────────────────────┘
                  │ SSE Response
                  ▼
Frontend (Website) ← 실시간 UI 업데이트
```

### 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| logos_api | 8090 | FastAPI 백엔드 (이 프로젝트) |
| ACP Server | 8888 | 에이전트 실행 서버 (`logosai/logosai/examples/standalone_acp_server.py`) |
| Website | 3000 | Next.js 프론트엔드 |

### ACP 서버 시작

```bash
# ACP 서버 실행 (자동 에이전트 선택 활성화)
cd logosai/logosai/examples
python standalone_acp_server.py --enable-auto-agent-selection
```

## SSE 스트리밍 이벤트

`POST /api/v1/chat/stream` 엔드포인트는 다음 이벤트를 스트리밍합니다:

### 이벤트 목록

| 이벤트 | 설명 | 단계 |
|--------|------|------|
| `initialization` | 시스템 초기화, 세션 생성 | 1 |
| `ontology_init` | 온톨로지 쿼리 분석 시작 | 2 |
| `multi_agent_init` | 멀티 에이전트 처리 시작 | 3 |
| `query_analysis_started` | LLM 쿼리 분석 시작 | 4 |
| `intent_analysis` | 사용자 의도 분석 | 5 |
| `agent_scoring` | 에이전트 점수화 및 선택 | 6 |
| `agent_query_generated` | 에이전트별 쿼리 생성 | 7 |
| `analysis_complete` | 쿼리 분석 완료 | 8 |
| `agents_selected` | 에이전트 선택 완료 | 9 |
| `agent_started` | 에이전트 실행 시작 | 10 |
| `agent_completed` | 에이전트 실행 완료 | 11 |
| `integration_started` | 결과 통합 시작 | 12 |
| `integration_completed` | 결과 통합 완료 | 13 |
| `final_result` | 최종 결과 | 14 |
| `message_saved` | 메시지 DB 저장 완료 | 15 |
| `error` | 에러 발생 | - |

### 클라이언트 예시

```javascript
// POST 요청으로 SSE 스트림 연결
const response = await fetch('/api/v1/chat/stream', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream'
  },
  body: JSON.stringify({
    query: '1+1 계산해줘',
    session_id: null,
    project_id: null
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  // SSE 이벤트 파싱
  const lines = text.split('\n');
  for (const line of lines) {
    if (line.startsWith('event:')) {
      const eventType = line.substring(6).trim();
      console.log('Event:', eventType);
    } else if (line.startsWith('data:')) {
      const data = JSON.parse(line.substring(5).trim());
      console.log('Data:', data);
    }
  }
}
```

### EventSource 사용 예시

```javascript
// 참고: EventSource는 GET만 지원하므로 POST 필요시 fetch 사용 권장
const eventSource = new EventSource('/api/v1/chat/stream');

eventSource.addEventListener('agents_selected', (e) => {
  const data = JSON.parse(e.data);
  console.log('선택된 에이전트:', data.agents);
});

eventSource.addEventListener('final_result', (e) => {
  const data = JSON.parse(e.data);
  console.log('최종 결과:', data.data.result);
});

eventSource.addEventListener('message_saved', (e) => {
  const data = JSON.parse(e.data);
  console.log('저장된 메시지 ID:', data.message_id);
});

eventSource.addEventListener('error', (e) => {
  console.error('에러:', e);
});
```

## 데이터베이스 스키마

### User 테이블 (logosai.users)

> **중요**: `logos_server`와의 호환성을 위해 `email`을 기본 키로 사용합니다 (UUID `id` 아님).

```sql
-- logosai.users 테이블 스키마
CREATE TABLE logosai.users (
    email VARCHAR(255) PRIMARY KEY,  -- email이 PK
    name VARCHAR(255) NOT NULL,
    picture_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    subscription_type VARCHAR(50) DEFAULT 'free',
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    order_id VARCHAR(255)
);
```

### 외래 키 참조

모든 테이블에서 사용자 참조 시 `email`을 사용합니다:

```python
# Project 모델 예시
owner_email: Mapped[str] = mapped_column(
    String(255),
    ForeignKey("logosai.users.email", ondelete="CASCADE"),
)

# Session 모델 예시
user_email: Mapped[str] = mapped_column(
    String(255),
    ForeignKey("logosai.users.email", ondelete="CASCADE"),
)
```

### 호환성 속성

API 호환성을 위해 각 모델에 `id` 속성이 있습니다:

```python
# User 모델
@property
def id(self) -> str:
    return self.email  # email을 id로 반환

# Project 모델
@property
def owner_id(self) -> str:
    return self.owner_email  # 호환성 속성
```

## 프로젝트 구조

```
logos_api/
├── alembic/                 # DB 마이그레이션
│   └── versions/            # 마이그레이션 스크립트
├── app/
│   ├── core/                # 핵심 모듈
│   │   ├── deps.py          # FastAPI 의존성
│   │   ├── exceptions.py    # 커스텀 예외
│   │   └── security.py      # JWT 인증
│   ├── models/              # SQLAlchemy 모델
│   │   ├── user.py          # User, UserHistory, SubscriptionPlan
│   │   ├── project.py       # Project (owner_email FK)
│   │   ├── session.py       # Session (user_email FK)
│   │   ├── message.py
│   │   ├── document.py
│   │   └── marketplace.py   # MarketplaceAgent, AgentReview, AgentPurchase
│   ├── routers/             # API 라우터
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── projects.py
│   │   ├── sessions.py
│   │   ├── chat.py
│   │   ├── documents.py
│   │   └── marketplace.py
│   ├── schemas/             # Pydantic 스키마
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── session.py
│   │   ├── chat.py
│   │   ├── document.py
│   │   └── marketplace.py
│   ├── services/            # 비즈니스 로직
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── project_service.py
│   │   ├── session_service.py
│   │   ├── chat_service.py
│   │   ├── acp_client.py
│   │   ├── document_service.py
│   │   ├── marketplace_service.py
│   │   └── rag/             # RAG 서비스
│   │       ├── rag_service.py
│   │       ├── elasticsearch_client.py
│   │       ├── embedding_service.py
│   │       ├── document_processor.py
│   │       ├── paper_metadata.py
│   │       ├── rerank/      # 리랭킹 시스템
│   │       └── image/       # 이미지 처리
│   ├── config.py            # 설정
│   ├── database.py          # DB 연결
│   └── main.py              # 앱 엔트리포인트
├── docs/                    # 문서
├── tests/                   # 테스트
├── .env.example             # 환경 변수 예시
├── alembic.ini              # Alembic 설정
├── pyproject.toml           # 프로젝트 설정
└── README.md
```

## 개발

### 테스트 실행

```bash
# 전체 테스트
pytest

# 커버리지 포함
pytest --cov=app --cov-report=html
```

### 코드 포맷팅

```bash
# Black 포맷팅
black app/

# Ruff 린트
ruff check app/

# 타입 체크
mypy app/
```

### 마이그레이션 생성

```bash
# 자동 생성 (DB 연결 필요)
alembic revision --autogenerate -m "Add new table"

# 수동 생성
alembic revision -m "Custom migration"
```

## 환경 변수

| 변수명 | 필수 | 기본값 | 설명 |
|--------|------|--------|------|
| `DATABASE_URL` | ✓ | - | PostgreSQL 연결 URL |
| `JWT_SECRET_KEY` | ✓ | - | JWT 서명 키 |
| `JWT_ALGORITHM` | | HS256 | JWT 알고리즘 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | | 1440 | 액세스 토큰 만료 (분) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | | 7 | 리프레시 토큰 만료 (일) |
| `GOOGLE_CLIENT_ID` | | - | Google OAuth 클라이언트 ID |
| `GOOGLE_CLIENT_SECRET` | | - | Google OAuth 시크릿 |
| `ACP_SERVER_URL` | | http://localhost:8888 | ACP 서버 URL |
| `CORS_ORIGINS` | | ["http://localhost:3000"] | CORS 허용 오리진 |
| `DEBUG` | | false | 디버그 모드 |
| `ENVIRONMENT` | | development | 환경 (development/staging/production) |

## 라이선스

MIT License

## 기여

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 관련 프로젝트

- [LogosAI Server](https://github.com/maior/logosai-server) - Django 백엔드 (레거시)
- [LogosAI Ontology](https://github.com/maior/logosai-ontology) - 온톨로지 시스템
- [LogosAI SDK](https://github.com/maior/logosai) - Python SDK
