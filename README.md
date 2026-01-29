# LogosAI API

FastAPI 기반의 LogosAI 백엔드 서버입니다. 온톨로지 기반 멀티 에이전트 AI 시스템을 위한 RESTful API를 제공합니다.

## 주요 기능

- **인증 시스템**: Google OAuth + JWT 토큰 기반 인증
- **프로젝트 관리**: 프로젝트 CRUD, 아카이브, 공유
- **세션 관리**: 대화 세션 및 메시지 히스토리
- **실시간 채팅**: SSE 스트리밍 기반 AI 응답
- **문서 관리**: PDF 업로드 및 RAG 검색 (예정)
- **마켓플레이스**: 에이전트 설치/관리 (예정)

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

### 문서 (Documents) - 예정

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/documents/` | 문서 목록 |
| POST | `/api/v1/documents/upload` | 문서 업로드 |
| DELETE | `/api/v1/documents/{id}` | 문서 삭제 |
| POST | `/api/v1/documents/search` | RAG 검색 |

## SSE 스트리밍 이벤트

`POST /api/v1/chat/stream` 엔드포인트는 다음 이벤트를 스트리밍합니다:

```javascript
// 클라이언트 예시
const eventSource = new EventSource('/api/v1/chat/stream');

eventSource.addEventListener('ontology_init', (e) => {
  // 온톨로지 분석 시작
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('agents_selected', (e) => {
  // 에이전트 선택 완료
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('workflow_plan_created', (e) => {
  // 워크플로우 계획 생성
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('agent_started', (e) => {
  // 에이전트 실행 시작
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('agent_progress', (e) => {
  // 에이전트 진행 상황
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('agent_completed', (e) => {
  // 에이전트 완료
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('final_result', (e) => {
  // 최종 결과
  console.log(JSON.parse(e.data));
});

eventSource.addEventListener('error', (e) => {
  // 에러 발생
  console.error(JSON.parse(e.data));
});
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
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── session.py
│   │   └── message.py
│   ├── routers/             # API 라우터
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── projects.py
│   │   ├── sessions.py
│   │   └── chat.py
│   ├── schemas/             # Pydantic 스키마
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── session.py
│   │   └── chat.py
│   ├── services/            # 비즈니스 로직
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── project_service.py
│   │   ├── session_service.py
│   │   ├── chat_service.py
│   │   └── acp_client.py
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
