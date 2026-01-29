# LogosAI Server Migration Analysis

> Django `logos_server` → FastAPI `logos_api` 마이그레이션을 위한 분석 문서

## 1. 현재 시스템 개요

### 1.1 규모
| 항목 | 수치 |
|------|------|
| 총 Python 파일 | ~380개 |
| 총 코드 라인 | ~142,000줄 |
| Django 앱 | 6개 |
| API 엔드포인트 | ~50개 |
| DB 모델 | ~40개 |

### 1.2 Django 앱 구조
```
logos_server/
├── app_users/      # 사용자 관리 (15 files)
├── app_project/    # 프로젝트 관리 (14 files)
├── app_chatting/   # 채팅 & RAG (150 files)
├── app_agent/      # 에이전트 오케스트레이션 (148 files)
├── app_market/     # 마켓플레이스 (22 files)
└── app_pdf/        # PDF 처리 (6 files)
```

---

## 2. API 엔드포인트 분석

### 2.1 Users API (`/app_users/`)

| Endpoint | Method | 설명 | 우선순위 |
|----------|--------|------|---------|
| `/loaduser` | POST | 사용자 로드/생성 | 🔴 필수 |
| `/userinfo` | POST | 사용자 정보 조회 | 🔴 필수 |
| `/userapikey` | POST | API 키 관리 | 🔴 필수 |
| `/usersubscription` | POST | 구독 정보 | 🟡 중요 |
| `/userusageoption` | POST | 사용 옵션 설정 | 🟡 중요 |
| `/searchusage` | POST | 검색 사용량 기록 | 🟢 선택 |

**비즈니스 로직:**
- Google OAuth 연동
- 구독 플랜: free, pro, premium
- API 키 암호화 저장

### 2.2 Projects API (`/app_project/`)

| Endpoint | Method | 설명 | 우선순위 |
|----------|--------|------|---------|
| `/projectcreate` | POST | 프로젝트 생성 | 🔴 필수 |
| `/projectlist` | POST | 프로젝트 목록 | 🔴 필수 |
| `/projectdelete` | POST | 프로젝트 삭제 | 🔴 필수 |
| `/projectshare` | POST | 프로젝트 공유 | 🟡 중요 |
| `/projectshareuser` | POST | 공유 사용자 관리 | 🟡 중요 |
| `/projectpublicstatus` | POST | 공개 상태 변경 | 🟢 선택 |

**비즈니스 로직:**
- 프로젝트별 세션 관리
- 사용자 간 프로젝트 공유
- 공개/비공개 설정

### 2.3 Chat & Sessions API (`/app_chatting/`)

| Endpoint | Method | 설명 | 우선순위 |
|----------|--------|------|---------|
| `/sessioncreate` | POST | 세션 생성 | 🔴 필수 |
| `/sessionlist` | POST | 세션 목록 | 🔴 필수 |
| `/sessionchatview` | POST | 채팅 히스토리 조회 | 🔴 필수 |
| `/sessionchatupdate` | POST | 채팅 업데이트 | 🔴 필수 |
| `/sessiondelete` | POST | 세션 삭제 | 🔴 필수 |
| `/chatting` | POST | 채팅 요청 | 🔴 핵심 |
| `/chatsavedmessages` | POST | 저장된 메시지 | 🟡 중요 |
| `/memories` | POST | 메모리 관리 | 🟡 중요 |
| `/websearch` | POST | 웹 검색 | 🟡 중요 |
| `/summarize` | POST | 요약 | 🟡 중요 |
| `/shoppingsearch` | POST | 쇼핑 검색 | 🟢 선택 |

### 2.4 Documents API (`/app_chatting/`)

| Endpoint | Method | 설명 | 우선순위 |
|----------|--------|------|---------|
| `/pdfupload` | POST | PDF 업로드 | 🟡 중요 |
| `/pdffilelist` | POST | PDF 목록 | 🟡 중요 |
| `/pdfdelete` | POST | PDF 삭제 | 🟡 중요 |
| `/esinitialize` | POST | Elasticsearch 초기화 | 🟢 선택 |

### 2.5 Agent API (`/app_agent/`)

| Endpoint | Method | 설명 | 우선순위 |
|----------|--------|------|---------|
| `/stream/multi-agent` | POST | SSE 스트리밍 | 🔴 핵심 |
| `/dbagent` | POST | 에이전트 실행 | 🔴 핵심 |
| `/taskagent` | POST | 태스크 에이전트 | 🟡 중요 |
| `/dashboard` | GET/POST | 대시보드 데이터 | 🟡 중요 |
| `/dbcontest` | POST | DB 연결 테스트 | 🟢 선택 |

**핵심 로직:**
- 온톨로지 기반 에이전트 선택
- SSE 실시간 스트리밍
- ACP Server (8888) 연동

### 2.6 Marketplace API (`/app_market/`)

| Endpoint | Method | 설명 | 우선순위 |
|----------|--------|------|---------|
| `/agentlist` | POST | 에이전트 목록 | 🟡 중요 |
| `/agentdetail` | POST | 에이전트 상세 | 🟡 중요 |
| `/agentinstall` | POST | 에이전트 설치 | 🟡 중요 |
| `/installedagents` | POST | 설치된 에이전트 | 🟡 중요 |
| `/registeragent` | POST | 에이전트 등록 | 🟡 중요 |
| `/deleteagent` | POST | 에이전트 삭제 | 🟡 중요 |
| `/categorylist` | POST | 카테고리 목록 | 🟢 선택 |
| `/agentreviews` | POST | 리뷰 관리 | 🟢 선택 |
| `/createtoken` | POST | 토큰 생성 | 🟢 선택 |
| `/checktoken` | POST | 토큰 검증 | 🟢 선택 |
| `/tokenlist` | POST | 토큰 목록 | 🟢 선택 |
| `/revoketoken` | POST | 토큰 취소 | 🟢 선택 |

---

## 3. 데이터베이스 스키마

### 3.1 Core Tables

```sql
-- Users
users (
    id, email, name, picture_url,
    created_at, updated_at
)

-- Subscriptions
user_subscriptions (
    id, user_id, plan_type, status,
    subscription_id, order_id,
    payment_provider, start_date, end_date
)

-- API Keys
user_api_keys (
    id, user_id, provider, api_key_encrypted,
    model_name, project_id
)

-- Projects
projects (
    id, user_id, name, description,
    is_public, created_at
)

-- Project Shares
project_shares (
    id, project_id, shared_user_id,
    share_type, status
)

-- Sessions
sessions (
    id, project_id, user_id, title,
    created_at, last_modified
)

-- Messages
messages (
    id, session_id, role, content,
    metadata, created_at
)

-- Memories
memories (
    id, user_id, project_id, content,
    embedding, created_at
)
```

### 3.2 Marketplace Tables

```sql
-- Agents
agents (
    id, name, description, author_id,
    category_id, version, icon_url,
    is_published, created_at
)

-- Agent Installs
agent_installs (
    id, agent_id, user_id, installed_at
)

-- Agent Reviews
agent_reviews (
    id, agent_id, user_id, rating,
    comment, created_at
)

-- Categories
categories (
    id, name, description, icon
)

-- API Tokens
api_tokens (
    id, user_id, token_hash, name,
    scopes, expires_at, created_at
)
```

---

## 4. 외부 서비스 연동

| 서비스 | 용도 | 필수 여부 |
|--------|------|----------|
| **PostgreSQL** | 메인 데이터베이스 | 🔴 필수 |
| **ACP Server (8888)** | 에이전트 실행 | 🔴 필수 |
| **OpenAI API** | LLM 처리 | 🔴 필수 |
| **Google OAuth** | 인증 | 🔴 필수 |
| **Milvus** | 벡터 DB | 🟡 중요 |
| **Elasticsearch** | 문서 검색 | 🟡 중요 |
| **Redis** | 캐싱 | 🟢 선택 |

---

## 5. 핵심 비즈니스 로직

### 5.1 인증 플로우
```
Google OAuth → LoadUser → Session 생성 → JWT 발급
```

### 5.2 채팅 플로우
```
사용자 쿼리
→ 온톨로지 분석
→ 에이전트 선택
→ ACP Server 호출
→ SSE 스트리밍 응답
```

### 5.3 문서 처리 플로우
```
PDF 업로드
→ 텍스트 추출
→ 청킹
→ 임베딩 생성
→ Milvus 저장
→ RAG 검색 가능
```

---

## 6. 마이그레이션 전략

### 6.1 Phase 1: 기반 구축 (Week 1)
- [ ] FastAPI 프로젝트 구조 생성
- [ ] DB 연결 (SQLAlchemy async)
- [ ] 기본 모델 정의
- [ ] JWT 인증 구현

### 6.2 Phase 2: 사용자 & 프로젝트 (Week 1-2)
- [ ] Users API 구현
- [ ] Projects API 구현
- [ ] Sessions API 구현
- [ ] 테스트 작성

### 6.3 Phase 3: 채팅 & 에이전트 (Week 2-3)
- [ ] SSE 스트리밍 구현
- [ ] 온톨로지 연동
- [ ] ACP Server 연동
- [ ] 채팅 API 구현

### 6.4 Phase 4: 부가 기능 (Week 3-4)
- [ ] Documents API
- [ ] Marketplace API
- [ ] 검색 기능
- [ ] 전체 테스트

---

## 7. 새로운 아키텍처 설계

### 7.1 프로젝트 구조
```
logos_api/
├── app/
│   ├── main.py                 # FastAPI 앱 진입점
│   ├── config.py               # 설정 관리
│   ├── database.py             # DB 연결
│   │
│   ├── models/                 # SQLAlchemy 모델
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── session.py
│   │   ├── message.py
│   │   └── agent.py
│   │
│   ├── schemas/                # Pydantic 스키마
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── session.py
│   │   └── agent.py
│   │
│   ├── routers/                # API 라우터
│   │   ├── __init__.py
│   │   ├── auth.py             # 인증
│   │   ├── users.py            # 사용자
│   │   ├── projects.py         # 프로젝트
│   │   ├── sessions.py         # 세션
│   │   ├── chat.py             # 채팅
│   │   ├── streaming.py        # SSE 스트리밍
│   │   ├── documents.py        # 문서
│   │   └── marketplace.py      # 마켓플레이스
│   │
│   ├── services/               # 비즈니스 로직
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── project_service.py
│   │   ├── chat_service.py
│   │   ├── agent_service.py
│   │   └── document_service.py
│   │
│   └── core/                   # 핵심 모듈
│       ├── __init__.py
│       ├── security.py         # JWT, 암호화
│       ├── dependencies.py     # 의존성 주입
│       ├── exceptions.py       # 커스텀 예외
│       └── middleware.py       # 미들웨어
│
├── tests/
│   ├── conftest.py
│   ├── test_users.py
│   ├── test_projects.py
│   └── test_chat.py
│
├── alembic/                    # DB 마이그레이션
│   ├── versions/
│   └── env.py
│
├── pyproject.toml
├── .env.example
└── README.md
```

### 7.2 기술 스택
| 카테고리 | 기술 |
|----------|------|
| **Framework** | FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Validation** | Pydantic v2 |
| **Auth** | python-jose (JWT) |
| **DB Migration** | Alembic |
| **Testing** | pytest-asyncio |
| **Server** | Uvicorn |

### 7.3 설계 원칙
1. **비동기 우선**: 모든 I/O 작업은 async/await
2. **의존성 주입**: FastAPI Depends 활용
3. **계층 분리**: Router → Service → Repository
4. **타입 안전성**: Pydantic 모델로 모든 입출력 검증
5. **자동 문서화**: OpenAPI (Swagger) 자동 생성

---

## 8. 다음 단계

1. **프로젝트 초기화**: `pyproject.toml`, 기본 구조 생성
2. **DB 설정**: SQLAlchemy async 설정, 모델 정의
3. **Auth 구현**: JWT 인증 시스템
4. **Users API**: 첫 번째 API 구현 및 테스트

---

*작성일: 2026-01-29*
*버전: 1.0*
