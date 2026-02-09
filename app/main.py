"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db, close_db
from app.services.acp_client import close_acp_client
from app.services.orchestrator_service import close_orchestrator_service

# Import routers
from app.routers import auth, users, projects, sessions, chat, health, documents, marketplace, rag, agents, memory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📊 Environment: {settings.environment}")
    print(f"🔗 Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")

    # Initialize database
    # await init_db()  # Uncomment when models are ready

    # Initialize agent registry (seed defaults + attempt ACP sync)
    try:
        from app.database import get_db_context
        from app.services.agent_registry_service import AgentRegistryService

        async with get_db_context() as db:
            service = AgentRegistryService(db)
            await service.ensure_default_acp_server()
            seeded = await service.seed_defaults_if_empty()
            if seeded:
                print(f"📦 Seeded {seeded} default agents")

            # Attempt ACP sync (non-blocking - server may not be running)
            try:
                result = await service.sync_from_acp()
                print(f"📦 ACP sync: {result['added']} added, {result['updated']} updated, {result['total']} total")
            except Exception as sync_err:
                print(f"⚠️ ACP sync skipped: {sync_err}")
    except Exception as e:
        print(f"⚠️ Agent registry init skipped: {e}")

    yield

    # Shutdown
    print("👋 Shutting down...")
    await close_orchestrator_service()
    await close_acp_client()
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="LogosAI Backend API Server - FastAPI Version",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add Session middleware (required for OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["Projects"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(marketplace.router, prefix="/api/v1/marketplace", tags=["Marketplace"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["RAG"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
app.include_router(memory.router, prefix="/api/v1/memories", tags=["Memories"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers,
    )
