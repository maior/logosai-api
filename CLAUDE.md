# CLAUDE.md - logos_api Development Guidelines

Development guide for the logos_api FastAPI server.

## Project Overview

| Item | Details |
|------|---------|
| **Project Name** | logos_api |
| **Tech Stack** | FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL |
| **Port** | 8090 |
| **Status** | ✅ Production Ready (Ontology + ACP integration complete) |

## ⚠️ Important: Independent from Django

**logos_api does NOT depend on Django (logos_server).**

- logos_api is a standalone FastAPI backend server
- It directly imports and uses the ontology system (`ontology/`)
- It communicates directly with the ACP Server
- It operates independently from the Django server (8080)

```
❌ Incorrect understanding:
   logos_api → Django → ACP Server

✅ Correct architecture:
   logos_api → Ontology System → ACP Server
        ↓
   Standalone FastAPI Server
```

## Service Architecture

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
│   │   ├── app/services/orchestrator_service.py  ⭐ Core          │   │
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
│   │   └── agents/ (61+ agents)                                   │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│   Database: PostgreSQL                                               │
│   - logosus schema (logos_api independent, UUID PK)                  │
│     ├── users (UUID id, email unique index)                          │
│     ├── conversations (chat sessions)                                │
│     ├── messages                                                     │
│     ├── documents (RAG)                                              │
│     └── analytics                                                    │
│   - logosai schema (shared with logos_server, Marketplace)           │
│                                                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Core Files

| File | Description |
|------|-------------|
| `app/main.py` | FastAPI app entry point |
| `app/config.py` | Environment settings (Pydantic Settings) |
| `app/database.py` | SQLAlchemy async configuration |
| `app/services/orchestrator_service.py` | **⭐ Ontology orchestrator integration** |
| `app/services/chat_service.py` | Chat service (SSE streaming) |
| `app/services/acp_client.py` | ACP server client |
| `app/routers/chat.py` | Chat API router |
| `app/models/` | SQLAlchemy models |
| `app/models/logosus/` | **⭐ logosus schema models (NEW)** |
| `app/services/conversation_service.py` | **⭐ Chat conversation service (NEW)** |
| `app/services/user_service.py` | User service (logosus-based) |
| `app/services/agent_registry_service.py` | **⭐ DB-based agent registry (NEW)** |
| `app/routers/agents.py` | Agent management REST API (NEW) |
| `app/models/logosus/agent.py` | ACPServer + RegisteredAgent models (NEW) |
| `app/schemas/agent.py` | Agent Pydantic schemas (NEW) |
| `app/middleware/response_normalizer.py` | Response format normalization (includes JSON+Markdown mixed content handling) |
| `app/middleware/response_middleware.py` | SSE event wrapper |
| `app/models/logosus/memory.py` | **⭐ UserMemory model (NEW)** |
| `app/schemas/memory.py` | Memory Pydantic schemas (NEW) |
| `app/services/memory_service.py` | **⭐ Memory service (with smart utilization) (NEW)** |
| `app/routers/memory.py` | Memory CRUD REST API (NEW) |

## Ontology System Integration

### OrchestratorService

`app/services/orchestrator_service.py` directly imports and uses the ontology system:

```python
from ontology.orchestrator import (
    WorkflowOrchestrator,
    QueryPlanner,
    ExecutionEngine,
    AgentRegistry,
)
from ontology.core.unified_query_processor import UnifiedQueryProcessor

# Query analysis and workflow execution via the ontology system
orchestrator = WorkflowOrchestrator(
    agent_executor=self._execute_agent_via_acp,
    registry=self._registry,
)
```

### Hybrid Agent Selection (NEW)

Agent selection using a Knowledge Graph + LLM hybrid approach:

```python
from ontology.core.hybrid_agent_selector import get_hybrid_selector

selector = get_hybrid_selector()
agent, metadata = await selector.select_agent(
    query="Show me Samsung stock price",
    available_agents=["internet_agent", "analysis_agent"],
    agents_info=agents_info
)

# Learning loop - store feedback on success
await selector.store_feedback(query, agent, success=True)
```

### Agent Synchronization (NEW)

Automatically sync ACP Server agents to the Knowledge Graph:

```python
from ontology.core.agent_sync_service import initialize_agent_sync

# Full sync on server startup
result = await initialize_agent_sync()
# {"total_agents": 61, "added": 54, "updated": 7}
```

### DB-Based Dynamic Agent Registry (NEW 2026-02-06)

Manages agents with the database as the source of truth and dynamically loads them into the ontology AgentRegistry:

```python
from app.services.agent_registry_service import AgentRegistryService

service = AgentRegistryService(db)

# Automatically executed on server startup (main.py lifespan)
await service.ensure_default_acp_server()    # Register default ACP server
await service.seed_defaults_if_empty()       # Seed DEFAULT_AGENTS
await service.sync_from_acp(server_id)       # Sync actual agents from ACP
await service.load_into_ontology_registry()  # Load DB → ontology in-memory
```

**DB Models**:
- `ACPServer`: ACP server connection info (url, health_status, is_active)
- `RegisteredAgent`: Agent metadata (agent_id, capabilities, tags, priority)

**REST API**:
- `GET /api/v1/agents/` - List all agents
- `GET /api/v1/agents/{agent_id}` - Get specific agent
- `POST /api/v1/agents/sync` - Trigger ACP sync
- `GET /api/v1/agents/servers/` - List ACP servers

### Response Format Auto-Correction (NEW 2026-02-06)

Automatically normalizes SSE responses to the canonical format expected by the logos_web frontend:

```python
from app.middleware.response_middleware import normalized_event_generator

# Wrap streaming response in chat.py
raw_stream = service.stream_chat(query, email)
normalized = normalized_event_generator(raw_stream)
return EventSourceResponse(event_generator(normalized))
```

**Auto-correction items**:
- Double-nested `data.data.result` flattened to `data.result`
- Automatic answer extraction from agent_results
- JSON codeblock marker removal (extracts Markdown only when JSON+Markdown are mixed)
- Errors converted to user-friendly messages

### User Memory System (NEW 2026-02-08)

Stores per-user memories and automatically utilizes them during chat:

```python
from app.services.memory_service import MemoryService

service = MemoryService(db)

# Memory CRUD
memory = await service.create_memory(user_id, content, memory_type, importance)
memories = await service.get_user_memories(user_id)

# Load memories for chat context (smart utilization)
context_str = await service.load_memories_for_context(user_id)
# → Grouped by type + differentiated utilization guidelines
```

**Memory utilization principles by type**:
| Type | Guideline | Example |
|------|-----------|---------|
| `instruction` | Always apply | "Always respond in Korean" |
| `preference` | Apply unless user explicitly requests otherwise | "Prefers Python" |
| `fact` | Use only when relevant to the query | "CS major at Sungkyunkwan University" |
| `context` | Reference only when relevant | "Working on graduation project" |

**SSE Event**: When memories are loaded, a `memory_context` event is emitted (before initialization):
```json
{"event": "memory_context", "data": {"memory_count": 3, "message": "Loaded 3 user memories"}}
```

**REST API**:
- `GET /api/v1/memories/` - List my memories
- `POST /api/v1/memories/` - Create memory (201)
- `DELETE /api/v1/memories/{id}` - Delete memory (204, soft delete)

**Background extraction**: After chat, memories are automatically extracted via `asyncio.create_task()` (using Gemini gemini-2.5-flash-lite)

### Response Format Guidelines (NEW 2026-02-08)

The QueryPlanner prompt includes response format instructions tailored to query type:

| Query Type | Format Instruction |
|------------|-------------------|
| Search/Research | `##` subheadings + bullet points + sources |
| Calculation/Simple answer | Core answer first, minimal elaboration |
| Comparison/Analysis | Markdown table or item-by-item comparison |
| Code/Technical | Code blocks + step-by-step explanation |

**Key principle**: No wall-of-text - use structured Markdown

## Server Startup

⚠️ **Always use scripts from the scripts/ folder** (for log and PID management)

```bash
# ✅ Correct - use scripts
cd /Users/maior/Development/skku/Logos

./scripts/start_logos_api.sh       # Start logos_api (8090)
./scripts/start_agent_server.sh    # Start ACP server (8888)
./scripts/status.sh                # Check status

# ❌ Incorrect - running commands directly
uvicorn app.main:app --reload --port 8090  # Use scripts instead!
```

## Database Schema

### Dual Schema Structure (NEW 2026-02)

logos_api uses two PostgreSQL schemas:

| Schema | Purpose | PK | Characteristics |
|--------|---------|-----|-----------------|
| **logosus** | logos_api independent data | UUID | New features, RAG, Analytics |
| **logosai** | Shared with logos_server | email/int | Marketplace |

### logosus Schema (Primary - logos_api independent)

```
logosus/
├── users          # UUID PK, email unique index
├── api_keys       # For programmatic access
├── sessions       # Auth sessions (login)
├── conversations  # Chat sessions ⭐
├── messages       # Chat messages
├── projects       # Projects
├── documents      # RAG documents
├── document_chunks
├── acp_servers    # ACP server info
├── registered_agents # Agent registry
├── user_memories  # User memories ⭐ NEW
├── search_history # RAG search history
├── rag_usage      # RAG usage statistics
└── usage_stats    # API usage statistics
```

```python
# Example usage of logosus models
from app.models.logosus.user import User
from app.models.logosus.conversation import Conversation, Message

# User uses UUID id
user.id  # '550e8400-e29b-41d4-a716-446655440000'
user.email  # 'user@example.com' (unique index)

# Conversation references user_id (UUID)
conversation.user_id  # User's UUID
```

### logosai Schema (Shared - Marketplace Only)

```python
# Only Marketplace models use the logosai schema
from app.models.marketplace import MarketplaceAgent, AgentReview, AgentPurchase
```

### Key Changes (Migration from logosai)

```python
# ❌ Previous (logosai - deprecated for core features)
user_email: Mapped[str] = mapped_column(
    ForeignKey("logosai.users.email"),
)

# ✅ Current (logosus)
user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False),
    ForeignKey("logosus.users.id", ondelete="CASCADE"),
)
```

### Model Import Guide

```python
# Core models (logosus)
from app.models import User, Conversation, Message, Document, Project

# Marketplace models (logosai)
from app.models import MarketplaceAgent, AgentReview, AgentPurchase

# Legacy models (deprecated - backward compatibility only)
from app.models import LegacyUser, LegacySession, LegacyMessage
```

### Message Model - role Field
```python
# ✅ Correct - stored as String
role: Mapped[str] = mapped_column(String(20))

# Values: "user", "assistant", "system"
```

## ACP Client Notes

### Endpoints
```python
# ✅ Correct
f"{base_url}/stream/multi"

# ❌ Incorrect
f"{base_url}/api/v1/stream"
```

### Parameter Names
```python
# ✅ Correct
payload = {
    "sessionid": session_id,  # lowercase 's'
}

# ❌ Incorrect
payload = {
    "session_id": session_id,  # underscore not allowed
}
```

### Parsing the final_result Event
The ACP server's final_result has a triple-nested structure:
```python
# event.data structure:
# {
#     "event": "final_result",
#     "data": {
#         "code": 0,
#         "data": {
#             "result": "actual response",
#             "agent_results": [...]
#         }
#     }
# }

data = event.get("data", {})
level1 = data.get("data", data)
level2 = level1.get("data", level1)
final_content = level2.get("result", "")
```

## SSE Event Flow

```
[memory_context] → initialization → ontology_init → agents_loading → agents_available
    → planning_start → planning_complete → stage_started
    → agent_started → agent_completed → stage_completed
    → integration_started → integration_completed → final_result → message_saved
```

## Test Commands

```bash
# Health check
curl http://localhost:8090/health

# Generate JWT token (Python)
python -c "
from datetime import datetime, timedelta, timezone
from jose import jwt
expire = datetime.now(timezone.utc) + timedelta(hours=24)
payload = {'sub': 'test@example.com', 'exp': expire, 'type': 'access'}
print(jwt.encode(payload, 'your-super-secret-key-change-this-in-production', algorithm='HS256'))
"

# Chat streaming test (JWT auth)
curl -X POST "http://localhost:8090/api/v1/chat/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Calculate 1+1"}'

# Chat streaming test (email auth - OAuth users)
curl -X POST "http://localhost:8090/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"query": "Calculate 1+1", "email": "test@example.com"}'

# List sessions (email auth)
curl -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/"

# Create session (email auth)
curl -X POST "http://localhost:8090/api/v1/sessions/" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: test@example.com" \
  -d '{"title": "New Session"}'

# Get session (email auth)
curl -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/{session_id}"

# Message history (email auth)
curl -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/{session_id}/messages"

# Delete session (email auth)
curl -X DELETE -H "X-User-Email: test@example.com" \
  "http://localhost:8090/api/v1/sessions/{session_id}"
```

## ⚠️ Mandatory E2E Test Rules (MANDATORY)

**Absolute rule**: E2E tests must be performed after implementation. No implementation is considered complete without testing.

### Test Sequence

| # | Step | Method | Verification |
|---|------|--------|-------------|
| 1 | API Health Check | `curl http://localhost:8090/health` | `{"status":"healthy"}` |
| 2 | API Unit Test | `curl` or Python script | Each endpoint responds correctly |
| 3 | SSE Streaming Test | SSE event parsing script | Event flow + final_result structure |
| 4 | Frontend Extraction Simulation | Python E2E test | Compatible with logos_web streaming.ts logic |
| 5 | logos_web Browser Verification | `http://localhost:8010` | Actual UI renders correctly |

### Frontend Compatibility E2E Test

You must verify that logos_api's SSE responses are compatible with logos_web's `streaming.ts` extraction logic:

```python
# E2E test core: Simulate logos_web's streaming.ts extraction logic in Python
# 1. Send actual query to logos_api (SSE)
# 2. Receive final_result event
# 3. Attempt answer extraction using streaming.ts extractCleanResponse() logic
# 4. Verify that an actual answer is extracted (not "No response received.")

async def test_query(query: str, expected_agent: str):
    # Receive SSE stream
    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, json=payload) as resp:
            # Parse events (event: / data: / blank line)
            # Extract data from final_result event
            # Validate with simulate_frontend_final_result(data)
            pass

# Required test queries (minimum 3)
tests = [
    ("What is 1+1?", "calculator_agent"),              # Simple calculation
    ("USD to KRW exchange rate", "currency_exchange_agent"), # External API
    ("Weather in Seoul", "weather_agent"),              # Real-time data
]
```

### Test Checklist

Must verify before marking implementation as complete:

- [ ] API endpoints respond correctly (200 OK)
- [ ] SSE event flow is correct (initialization → ... → final_result)
- [ ] Answer can be extracted from final_result data
- [ ] Compatible with logos_web streaming.ts (extractCleanResponse simulation passes)
- [ ] Error responses are converted to user-friendly messages
- [ ] No errors in server logs (`tail -f logs/logos_api.log`)

### Agent Registry Test (DB-based)

```bash
# Check agent list
curl http://localhost:8090/api/v1/agents/ | python -m json.tool | head -20

# Check specific agent
curl http://localhost:8090/api/v1/agents/currency_exchange_agent

# ACP sync
curl -X POST http://localhost:8090/api/v1/agents/sync

# ACP server list
curl http://localhost:8090/api/v1/agents/servers/
```

## Log Inspection

```bash
# logos_api logs
tail -f logs/logos_api.log

# ACP server logs
tail -f ../logosai/logs/acp_server.log
```

## Core Development Principles

### No Hardcoding

**Absolute rule**: Never use **hardcoded keyword matching** for agent selection, query classification, or domain matching.

```python
# ❌ Forbidden: hardcoded keyword matching
if "weather" in query:
    agent = "weather_agent"
elif "shopping" in query:
    agent = "shopping_agent"

# ❌ Forbidden: hardcoded specific agent names
DEFAULT_AGENT = "internet_agent"  # Hardcoding internet_agent as fallback

# ✅ Recommended: use hybrid selector
from ontology.core.hybrid_agent_selector import get_hybrid_selector
selector = get_hybrid_selector()
agent, metadata = await selector.select_agent(query, available_agents, agents_info)
```

**Rationale**:
- No code changes needed when adding new agents
- LLM semantically matches queries to agents
- Knowledge Graph learning improves accuracy over time
- Automatic multilingual support and improved maintainability

**Detailed guide**: See [ontology/CLAUDE.md](../ontology/CLAUDE.md)

---

## Common Troubleshooting

### 1. `messagerole` Enum Error
```
type "messagerole" does not exist
```
**Solution**: Change the Message model's role field from `Enum` to `String(50)`

### 2. ACP Server Connection Failure
```
ACP health check failed
```
**Solution**: Verify the ACP server is running
```bash
lsof -i :8888  # Check port
python standalone_acp_server.py --enable-auto-agent-selection
```

### 3. Auto Agent Selection Disabled Error
```
Auto agent selection is disabled
```
**Solution**: Add the `--enable-auto-agent-selection` flag when starting the ACP server

### 4. JWT Token Error
```
Invalid or expired token
```
**Solution**: Verify that the `JWT_SECRET_KEY` in `.env` matches the key used to generate the token

### 5. Ontology Module Import Error
```
Ontology modules not available
```
**Solution**: Verify the ontology directory is in the Python path
```python
import sys
sys.path.insert(0, '/path/to/Logos')
sys.path.insert(0, '/path/to/Logos/ontology')
```

## Related Documentation

- [README.md](./README.md) - Project introduction and API documentation
- [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) - Development plan and progress
- [docs/ANALYSIS.md](./docs/ANALYSIS.md) - System analysis documentation
- [../ontology/CLAUDE.md](../ontology/CLAUDE.md) - Ontology system guide
- [../CLAUDE.md](../CLAUDE.md) - Main project guide

---

*Last updated: 2026-02-08 (User Memory System, memory UI indicator, response format guidelines, JSON+Markdown mixed content handling)*
