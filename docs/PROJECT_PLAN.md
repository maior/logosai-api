# LogosAPI Project Plan

> FastAPI 기반 새로운 백엔드 서버 구축 계획

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | logos_api |
| **목표** | Django logos_server를 대체하는 FastAPI 서버 |
| **예상 기간** | 4주 |
| **우선순위** | 핵심 기능 먼저, 부가 기능 나중에 |

---

## Phase 1: 프로젝트 기반 구축 (Day 1-3)

### 목표
- FastAPI 프로젝트 구조 완성
- 데이터베이스 연결
- 기본 인증 시스템

### 태스크

#### Day 1: 프로젝트 초기화 ✅
- [x] 폴더 구조 생성
- [x] 분석 문서 작성
- [x] pyproject.toml 설정
- [x] .env 설정
- [x] FastAPI 앱 기본 구조

#### Day 2: 데이터베이스 설정 ✅
- [x] SQLAlchemy async 설정
- [x] Base 모델 정의
- [x] Alembic 마이그레이션 설정
- [x] User 모델 생성

#### Day 3: 인증 시스템 ✅
- [x] JWT 토큰 생성/검증
- [x] Google OAuth 연동
- [x] 의존성 주입 (get_current_user)
- [x] 인증 테스트

### 산출물
- 실행 가능한 FastAPI 서버
- DB 연결 완료
- 인증 시스템 작동

---

## Phase 2: Users & Projects API (Day 4-7)

### 목표
- 사용자 관리 API 완성
- 프로젝트 관리 API 완성

### 태스크

#### Day 4-5: Users API ✅
- [x] User 스키마 정의 (email as PK)
- [x] UserService 구현 (get_by_email)
- [x] Users 라우터 구현
  - POST /users/load → POST /auth/login/google
  - GET /users/me
  - PUT /users/api-keys
  - GET /users/subscription
- [x] 테스트 작성

#### Day 6-7: Projects API ✅
- [x] Project 스키마 정의 (owner_email FK)
- [x] ProjectService 구현
- [x] Projects 라우터 구현
  - POST /projects
  - GET /projects
  - DELETE /projects/{id}
  - POST /projects/{id}/archive
- [x] 테스트 작성

### 산출물
- ✅ Users API 완성
- ✅ Projects API 완성
- ✅ 테스트 통과

---

## Phase 3: Sessions & Chat API (Day 8-14)

### 목표
- 세션 관리 API 완성
- 채팅 API 완성
- SSE 스트리밍 구현

### 태스크

#### Day 8-9: Sessions API ✅
- [x] Session 스키마 정의 (user_email FK)
- [x] SessionService 구현
- [x] Sessions 라우터 구현
  - POST /sessions
  - GET /sessions
  - GET /sessions/{id}/messages
  - DELETE /sessions/{id}

#### Day 10-12: Chat & Streaming ✅
- [x] SSE 스트리밍 구현
- [x] ACP Server 연동
- [x] 온톨로지 시스템 연동
- [x] Chat 라우터 구현
  - POST /chat (일반 응답)
  - POST /chat/stream (SSE 스트리밍)
  - 86% 이벤트 커버리지

#### Day 13-14: 테스트 & 최적화 ✅
- [x] 통합 테스트
- [x] JSON 형식 테스트 (4/4 PASS)
- [x] RAG 직접 테스트 (3/3 PASS)

### 산출물
- ✅ Sessions API 완성
- ✅ 실시간 스트리밍 채팅 작동
- ✅ Frontend 연동 테스트 완료

---

## Phase 4: Documents & Marketplace (Day 15-21)

### 목표
- 문서 관리 API
- 마켓플레이스 API

### 태스크

#### Day 15-17: Documents API ✅
- [x] Document 스키마 정의
- [x] PDF 업로드/처리
- [x] Elasticsearch 연동 (RAG)
- [x] Documents 라우터 구현
  - POST /documents/upload
  - GET /documents
  - POST /documents/search
  - DELETE /documents/{id}
- [x] RAG 고급 기능: Reranking, Image Processing, Paper Metadata

#### Day 18-21: Marketplace API ✅
- [x] Agent 스키마 정의 (creator_email FK)
- [x] MarketplaceService 구현
- [x] Marketplace 라우터 구현
  - GET/POST /marketplace/agents
  - GET/PUT/DELETE /marketplace/agents/{id}
  - POST /marketplace/agents/{id}/publish
  - GET/POST /marketplace/agents/{id}/reviews
  - POST /marketplace/agents/{id}/purchase
- [x] 테스트

### 산출물
- ✅ Documents API 완성
- ✅ Marketplace API 완성

---

## Phase 5: 마무리 & 배포 준비 (Day 22-28)

### 목표
- 전체 테스트
- 문서화
- 배포 준비

### 태스크
- [ ] E2E 테스트
- [ ] API 문서 검토
- [ ] 성능 최적화
- [ ] Docker 설정
- [ ] CI/CD 파이프라인
- [ ] Frontend 전환 테스트

---

## API 설계 (RESTful)

### 기존 Django vs 새로운 FastAPI

| 기존 (Django) | 새로운 (FastAPI) | 변경 사항 |
|---------------|------------------|-----------|
| POST /loaduser | POST /auth/login | RESTful 명명 |
| POST /userinfo | GET /users/me | GET 사용 |
| POST /projectlist | GET /projects | GET 사용 |
| POST /projectcreate | POST /projects | 단순화 |
| POST /sessionlist | GET /sessions | GET 사용 |
| POST /sessionchatview | GET /sessions/{id}/messages | 경로 파라미터 |
| POST /stream/multi-agent | POST /chat/stream | SSE 유지 |

### 새로운 API 구조

```
/api/v1
├── /auth
│   ├── POST /login          # Google OAuth 로그인
│   ├── POST /refresh        # 토큰 갱신
│   └── POST /logout         # 로그아웃
│
├── /users
│   ├── GET /me              # 현재 사용자 정보
│   ├── PUT /me              # 사용자 정보 수정
│   ├── GET /me/subscription # 구독 정보
│   └── PUT /me/api-keys     # API 키 설정
│
├── /projects
│   ├── GET /                # 프로젝트 목록
│   ├── POST /               # 프로젝트 생성
│   ├── GET /{id}            # 프로젝트 상세
│   ├── PUT /{id}            # 프로젝트 수정
│   ├── DELETE /{id}         # 프로젝트 삭제
│   └── POST /{id}/share     # 프로젝트 공유
│
├── /sessions
│   ├── GET /                # 세션 목록
│   ├── POST /               # 세션 생성
│   ├── GET /{id}            # 세션 상세
│   ├── DELETE /{id}         # 세션 삭제
│   └── GET /{id}/messages   # 메시지 목록
│
├── /chat
│   ├── POST /               # 채팅 (일반)
│   └── POST /stream         # 채팅 (SSE 스트리밍)
│
├── /documents
│   ├── GET /                # 문서 목록
│   ├── POST /upload         # 문서 업로드
│   ├── DELETE /{id}         # 문서 삭제
│   └── POST /search         # 문서 검색 (RAG)
│
└── /marketplace
    ├── GET /agents          # 에이전트 목록
    ├── GET /agents/{id}     # 에이전트 상세
    ├── POST /agents/{id}/install    # 설치
    ├── DELETE /agents/{id}/install  # 제거
    └── GET /agents/installed        # 설치된 목록
```

---

## 기술 결정

### 1. 비동기 DB
```python
# SQLAlchemy 2.0 async
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

engine = create_async_engine("postgresql+asyncpg://...")
```

### 2. Pydantic v2
```python
from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    email: str = Field(..., description="User email")
    name: str = Field(..., min_length=1)
```

### 3. JWT 인증
```python
from jose import jwt

def create_access_token(data: dict) -> str:
    return jwt.encode(data, SECRET_KEY, algorithm="HS256")
```

### 4. SSE 스트리밍
```python
from sse_starlette.sse import EventSourceResponse

async def stream_chat():
    async def event_generator():
        async for chunk in process_chat():
            yield {"event": "message", "data": chunk}
    return EventSourceResponse(event_generator())
```

---

## 성공 기준

### Phase 1 완료 기준 ✅
- [x] FastAPI 서버 실행 (http://localhost:8090)
- [x] DB 연결 설정 (PostgreSQL async)
- [x] JWT 인증 작동
- [x] Swagger 문서 자동 생성 (/docs)

### Phase 2 완료 기준 ✅
- [x] 사용자 로그인/로그아웃
- [x] 프로젝트 CRUD
- [x] 기존 Django와 동일한 기능

### Phase 3 완료 기준 ✅
- [x] 세션 관리 완성
- [x] SSE 스트리밍 작동 (86% 이벤트 커버리지)
- [x] Frontend 연동 성공

### Phase 4 완료 기준 ✅
- [x] Documents API 완성
- [x] Marketplace API 완성
- [x] RAG 검색 기능 작동

### 전체 완료 기준
- [x] 모든 API 테스트 통과
- [x] Frontend에서 정상 작동 (JSON 형식 호환)
- [x] 성능: Django 대비 동등 이상
- [x] 문서화 완료

---

## 리스크 & 대응

| 리스크 | 대응 방안 |
|--------|----------|
| 온톨로지 시스템 연동 복잡 | 기존 코드 모듈화하여 재사용 |
| ACP Server 연동 | HTTP/SSE 클라이언트로 단순화 |
| DB 마이그레이션 | 기존 데이터 호환 스크립트 |
| Frontend 수정 | API 경로만 변경, 응답 형식 유지 |

---

## 다음 액션

1. ✅ 분석 문서 작성
2. ✅ 프로젝트 계획 작성
3. ✅ pyproject.toml 생성
4. ✅ FastAPI 기본 앱 구조 생성
5. ✅ 데이터베이스 설정
6. ✅ User 모델 및 인증 시스템 구현
7. ✅ Alembic 마이그레이션 준비
8. ✅ PostgreSQL 연결 (email as PK)
9. ✅ Projects API 구현
10. ✅ Sessions API 구현
11. ✅ Chat API 및 SSE 스트리밍 구현
12. ✅ Documents API 구현
13. ✅ Marketplace API 구현
14. ✅ RAG 시스템 포팅 (Elasticsearch, Reranking, Image)
15. ✅ JSON 형식 Website 호환성 확인

---

## 주요 변경 사항 (2026-01-30)

### 데이터베이스 스키마 변경
- `logosai.users` 테이블: `email`이 기본 키 (UUID `id` 아님)
- 모든 외래 키가 `email` 참조로 변경:
  - `Project.owner_email` → `logosai.users.email`
  - `Session.user_email` → `logosai.users.email`
  - `MarketplaceAgent.creator_email` → `logosai.users.email`
  - `AgentReview.user_email` → `logosai.users.email`
  - `AgentPurchase.user_email` → `logosai.users.email`

### API 호환성
- 호환성 속성 추가 (`id` → `email` 반환)
- Website JSON 형식 완전 호환 (`msg/code/data` 래퍼)
- SSE 이벤트 86% 커버리지

---

*작성일: 2026-01-29*
*최종 업데이트: 2026-01-30*
*버전: 2.0*
