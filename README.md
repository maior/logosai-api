# LogosAI API

A FastAPI-based backend server for LogosAI. Provides RESTful APIs for the ontology-driven multi-agent AI system.

> **Status**: ✅ Production Ready (2026-01-30)
> ACP server integration complete, full chat flow verified

## Key Features

- **Authentication**: Google OAuth + JWT token-based authentication
- **Project Management**: Project CRUD, archiving, and sharing
- **Session Management**: Conversation sessions and message history
- **Real-time Chat**: SSE streaming-based AI responses ✅ (ACP server integration complete)
- **Document Management**: File upload and RAG search
- **Marketplace**: Agent registration, search, and purchase

## Tech Stack

| Category | Technology |
|----------|------------|
| Framework | FastAPI 0.109+ |
| Database | PostgreSQL + SQLAlchemy 2.0 (async) |
| Auth | JWT (python-jose) + Google OAuth |
| Validation | Pydantic v2 |
| Streaming | SSE (sse-starlette) |
| Migration | Alembic |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/maior/logosai-api.git
cd logosai-api

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Install dev dependencies (optional)
pip install -e ".[dev]"
```

### Configuration

```bash
# Create .env file
cp .env.example .env

# Edit .env file
vim .env
```

Required environment variables:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/logosai

# JWT
JWT_SECRET_KEY=your-super-secret-key-change-in-production

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# ACP Server (Agent execution server)
ACP_SERVER_URL=http://localhost:8888
```

### Database Migration

```bash
# Run migrations
alembic upgrade head
```

### Running the Server

```bash
# Development server (with auto-reload)
uvicorn app.main:app --reload --port 8090

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8090 --workers 4
```

Once the server is running:
- API Docs: http://localhost:8090/docs
- ReDoc: http://localhost:8090/redoc
- Health Check: http://localhost:8090/health

## API Reference

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/login/google` | Google OAuth login |
| POST | `/api/v1/auth/refresh` | Refresh token |
| POST | `/api/v1/auth/logout` | Logout |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users/me` | Get current user info |
| PUT | `/api/v1/users/me` | Update profile |
| GET | `/api/v1/users/me/subscription` | Get subscription info |
| PUT | `/api/v1/users/me/api-keys` | Configure API keys |

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/projects/` | List projects |
| POST | `/api/v1/projects/` | Create project |
| GET | `/api/v1/projects/{id}` | Get project |
| PUT | `/api/v1/projects/{id}` | Update project |
| DELETE | `/api/v1/projects/{id}` | Delete project |
| POST | `/api/v1/projects/{id}/archive` | Archive project |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/sessions/` | List sessions |
| POST | `/api/v1/sessions/` | Create session |
| GET | `/api/v1/sessions/{id}` | Get session |
| DELETE | `/api/v1/sessions/{id}` | Delete session |
| GET | `/api/v1/sessions/{id}/messages` | List messages |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/` | Chat (synchronous) |
| POST | `/api/v1/chat/stream` | Chat (SSE streaming) |
| GET | `/api/v1/chat/health` | Service health |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/documents/` | List documents |
| POST | `/api/v1/documents/upload` | Upload document |
| GET | `/api/v1/documents/{id}` | Get document |
| PUT | `/api/v1/documents/{id}` | Update document |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| POST | `/api/v1/documents/search` | RAG search |
| POST | `/api/v1/documents/{id}/reprocess` | Reprocess document |
| GET | `/api/v1/documents/{id}/content` | Get document content |

Supported file formats: PDF, TXT, Markdown, DOCX, CSV, JSON (max 50MB)

### Marketplace

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/marketplace/agents` | Search/filter agents |
| GET | `/api/v1/marketplace/agents/featured` | Featured agents |
| GET | `/api/v1/marketplace/agents/categories` | List categories |
| POST | `/api/v1/marketplace/agents` | Register agent |
| GET | `/api/v1/marketplace/agents/my` | My agents |
| GET | `/api/v1/marketplace/agents/{id}` | Agent details |
| PUT | `/api/v1/marketplace/agents/{id}` | Update agent |
| DELETE | `/api/v1/marketplace/agents/{id}` | Delete agent |
| POST | `/api/v1/marketplace/agents/{id}/publish` | Publish agent |
| POST | `/api/v1/marketplace/agents/{id}/unpublish` | Unpublish agent |
| GET | `/api/v1/marketplace/agents/{id}/stats` | Agent statistics |
| GET | `/api/v1/marketplace/agents/{id}/reviews` | List reviews |
| POST | `/api/v1/marketplace/agents/{id}/reviews` | Write review |
| PUT | `/api/v1/marketplace/agents/{id}/reviews` | Update review |
| DELETE | `/api/v1/marketplace/agents/{id}/reviews` | Delete review |
| POST | `/api/v1/marketplace/agents/{id}/purchase` | Purchase agent |
| GET | `/api/v1/marketplace/purchases` | Purchase history |

Pricing types: free, one_time, subscription, usage_based

## ACP Server Integration Architecture

logos_api integrates with an ACP (Agent Communication Protocol) server to provide a multi-agent AI system.

> **Important**: The ACP server must be running for the chat feature to work.

### End-to-End Flow

```
Frontend (logos_web)
    |
    v POST /api/v1/chat/stream
+---------------------------------------------+
|              logos_api (8090)                |
+---------------------------------------------+
| 1. JWT authentication -> User lookup         |
| 2. Session creation/retrieval                |
| 3. Save user message (role: user)            |
| 4. Stream request to ACP server              |
+-----------------------+---------------------+
                        | SSE Stream
                        v
+---------------------------------------------+
|              ACP Server (8888)              |
+---------------------------------------------+
| 5. Query analysis (LLM)                     |
| 6. Agent selection (automatic)               |
| 7. Agent execution                           |
| 8. Result integration (LLM)                  |
| 9. Send final_result event                   |
+-----------------------+---------------------+
                        | SSE Events
                        v
+---------------------------------------------+
|              logos_api (8090)                |
+---------------------------------------------+
| 10. Save assistant message (role: assistant) |
| 11. Send message_saved event                 |
+-----------------------+---------------------+
                        | SSE Response
                        v
Frontend (logos_web) <- Real-time UI update
```

### Service Configuration

| Service | Port | Description |
|---------|------|-------------|
| logos_api | 8090 | FastAPI backend (this project) |
| ACP Server | 8888 | Agent execution server ([logosai-framework](https://github.com/maior/logosai-framework)) |
| logos_web | 8010 | Next.js frontend ([logosai-web](https://github.com/maior/logosai-web)) |

### ACP Server Setup (Required)

The ACP server is required for chat functionality. Use the `SimpleACPServer` from [logosai-framework](https://github.com/maior/logosai-framework).

#### Quick Start

```bash
pip install logosai
```

```python
# my_acp_server.py
from logosai import SimpleAgent, AgentResponse
from logosai.acp import SimpleACPServer

class HelloAgent(SimpleAgent):
    agent_name = "Hello Agent"
    agent_description = "A simple greeting agent"

    async def handle(self, query, context=None):
        return AgentResponse.success(content={"answer": f"Hello! Here is the response to '{query}'."})

server = SimpleACPServer(port=8888)
server.add(HelloAgent())
server.run()
```

```bash
# Run the ACP server
python my_acp_server.py

# Verify
curl http://localhost:8888/jsonrpc -d '{"jsonrpc":"2.0","method":"list_agents","id":1}'
```

#### Using the Sample Server

```bash
git clone https://github.com/maior/logosai-framework.git
cd logosai-framework/samples
pip install logosai
python sample_acp_server.py  # Runs on port 8888
```

For detailed agent development instructions, see the [logosai-framework README](https://github.com/maior/logosai-framework#4-run-a-multi-agent-server).

## SSE Streaming Events

The `POST /api/v1/chat/stream` endpoint streams the following events:

### Event List

| Event | Description | Stage |
|-------|-------------|-------|
| `initialization` | System initialization, session creation | 1 |
| `ontology_init` | Ontology query analysis started | 2 |
| `multi_agent_init` | Multi-agent processing started | 3 |
| `query_analysis_started` | LLM query analysis started | 4 |
| `intent_analysis` | User intent analysis | 5 |
| `agent_scoring` | Agent scoring and selection | 6 |
| `agent_query_generated` | Per-agent query generation | 7 |
| `analysis_complete` | Query analysis complete | 8 |
| `agents_selected` | Agent selection complete | 9 |
| `agent_started` | Agent execution started | 10 |
| `agent_completed` | Agent execution completed | 11 |
| `integration_started` | Result integration started | 12 |
| `integration_completed` | Result integration completed | 13 |
| `final_result` | Final result | 14 |
| `message_saved` | Message saved to database | 15 |
| `error` | Error occurred | - |

### Client Example

```javascript
// Connect to SSE stream via POST request
const response = await fetch('/api/v1/chat/stream', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream'
  },
  body: JSON.stringify({
    query: 'Calculate 1+1',
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
  // Parse SSE events
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

### EventSource Example

```javascript
// Note: EventSource only supports GET; use fetch for POST requests
const eventSource = new EventSource('/api/v1/chat/stream');

eventSource.addEventListener('agents_selected', (e) => {
  const data = JSON.parse(e.data);
  console.log('Selected agents:', data.agents);
});

eventSource.addEventListener('final_result', (e) => {
  const data = JSON.parse(e.data);
  console.log('Final result:', data.data.result);
});

eventSource.addEventListener('message_saved', (e) => {
  const data = JSON.parse(e.data);
  console.log('Saved message ID:', data.message_id);
});

eventSource.addEventListener('error', (e) => {
  console.error('Error:', e);
});
```

## Database Schema

### User Table (logosai.users)

> **Important**: The `email` field is used as the primary key for backward compatibility with `logos_server` (not the UUID `id`).

```sql
-- logosai.users table schema
CREATE TABLE logosai.users (
    email VARCHAR(255) PRIMARY KEY,  -- email is PK
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

### Foreign Key References

All tables reference users via the `email` field:

```python
# Project model example
owner_email: Mapped[str] = mapped_column(
    String(255),
    ForeignKey("logosai.users.email", ondelete="CASCADE"),
)

# Session model example
user_email: Mapped[str] = mapped_column(
    String(255),
    ForeignKey("logosai.users.email", ondelete="CASCADE"),
)
```

### Compatibility Properties

Each model provides an `id` property for API compatibility:

```python
# User model
@property
def id(self) -> str:
    return self.email  # Returns email as id

# Project model
@property
def owner_id(self) -> str:
    return self.owner_email  # Compatibility property
```

## Project Structure

```
logos_api/
├── alembic/                 # DB migrations
│   └── versions/            # Migration scripts
├── app/
│   ├── core/                # Core modules
│   │   ├── deps.py          # FastAPI dependencies
│   │   ├── exceptions.py    # Custom exceptions
│   │   └── security.py      # JWT authentication
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # User, UserHistory, SubscriptionPlan
│   │   ├── project.py       # Project (owner_email FK)
│   │   ├── session.py       # Session (user_email FK)
│   │   ├── message.py
│   │   ├── document.py
│   │   └── marketplace.py   # MarketplaceAgent, AgentReview, AgentPurchase
│   ├── routers/             # API routers
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── projects.py
│   │   ├── sessions.py
│   │   ├── chat.py
│   │   ├── documents.py
│   │   └── marketplace.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── session.py
│   │   ├── chat.py
│   │   ├── document.py
│   │   └── marketplace.py
│   ├── services/            # Business logic
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── project_service.py
│   │   ├── session_service.py
│   │   ├── chat_service.py
│   │   ├── acp_client.py
│   │   ├── document_service.py
│   │   ├── marketplace_service.py
│   │   └── rag/             # RAG services
│   │       ├── rag_service.py
│   │       ├── elasticsearch_client.py
│   │       ├── embedding_service.py
│   │       ├── document_processor.py
│   │       ├── paper_metadata.py
│   │       ├── rerank/      # Reranking system
│   │       └── image/       # Image processing
│   ├── config.py            # Configuration
│   ├── database.py          # DB connection
│   └── main.py              # App entrypoint
├── docs/                    # Documentation
├── tests/                   # Tests
├── .env.example             # Environment variables example
├── alembic.ini              # Alembic configuration
├── pyproject.toml           # Project configuration
└── README.md
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html
```

### Code Formatting

```bash
# Black formatting
black app/

# Ruff linting
ruff check app/

# Type checking
mypy app/
```

### Creating Migrations

```bash
# Auto-generate (requires DB connection)
alembic revision --autogenerate -m "Add new table"

# Manual creation
alembic revision -m "Custom migration"
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection URL |
| `JWT_SECRET_KEY` | Yes | - | JWT signing key |
| `JWT_ALGORITHM` | | HS256 | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | | 1440 | Access token expiry (minutes) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | | 7 | Refresh token expiry (days) |
| `GOOGLE_CLIENT_ID` | | - | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | | - | Google OAuth secret |
| `ACP_SERVER_URL` | | http://localhost:8888 | ACP server URL |
| `CORS_ORIGINS` | | ["http://localhost:3000"] | Allowed CORS origins |
| `DEBUG` | | false | Debug mode |
| `ENVIRONMENT` | | development | Environment (development/staging/production) |

## License

MIT License

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Related Projects

| Project | Description | Repository |
|---------|-------------|------------|
| **logosai-framework** | Python SDK + Agent Runtime | [github.com/maior/logosai-framework](https://github.com/maior/logosai-framework) |
| **logosai-ontology** | Ontology-based multi-agent orchestration | [github.com/maior/logosai-ontology](https://github.com/maior/logosai-ontology) |
| **logosai-web** | Next.js frontend | [github.com/maior/logosai-web](https://github.com/maior/logosai-web) |
