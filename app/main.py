"""FastAPI application factory.

Bootstraps the agent registry idempotently during startup (in-memory runtime
agents built from persisted agent records), registers routers, and attaches
global exception handlers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.factory import ensure_company_agents
from app.agents.registry import AgentRegistry
from app.api import activity, agents, audit_logs, blogger_auth, departments, health, objectives, tasks, trendera, workflows
from app.api.errors import register_exception_handlers
from app.core.config import settings
from app.core.database import async_session_factory, create_all
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    # Local development uses SQLite; create its schema on startup so the app
    # runs without external tooling. PostgreSQL/production schemas are managed
    # by Alembic (``alembic upgrade head``) and intentionally NOT touched here.
    if settings.database_url.startswith("sqlite"):
        await create_all()

    # Idempotent agent bootstrap: ensures persisted agent records then builds
    # a single in-memory registry shared by all requests.
    registry = AgentRegistry()
    async with async_session_factory() as session:
        await ensure_company_agents(session, registry)
    app.state.agent_registry = registry

    yield


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    register_exception_handlers(app)

    # CORS: allow the TrendEra frontend (Vite dev server) to reach this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers are mounted under the configured API prefix.
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(departments.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(tasks.router, prefix=settings.api_prefix)
    app.include_router(objectives.router, prefix=settings.api_prefix)
    app.include_router(workflows.router, prefix=settings.api_prefix)
    app.include_router(audit_logs.router, prefix=settings.api_prefix)
    app.include_router(trendera.router, prefix=settings.api_prefix)
    app.include_router(blogger_auth.router, prefix=settings.api_prefix)
    app.include_router(activity.router, prefix=settings.api_prefix)

    return app


app = create_app()