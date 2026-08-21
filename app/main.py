"""FastAPI application factory.

Bootstraps the agent registry idempotently during startup (in-memory runtime
agents built from persisted agent records), registers routers, and attaches
global exception handlers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents.factory import ensure_company_agents
from app.agents.registry import AgentRegistry
from app.api import agents, audit_logs, departments, health, objectives, tasks, workflows
from app.api.errors import register_exception_handlers
from app.core.config import settings
from app.core.database import async_session_factory, create_all
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    # Development/test convenience: create tables before bootstrapping.
    # Production will use Alembic migrations instead.
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

    # Routers are mounted under the configured API prefix.
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(departments.router, prefix=settings.api_prefix)
    app.include_router(agents.router, prefix=settings.api_prefix)
    app.include_router(tasks.router, prefix=settings.api_prefix)
    app.include_router(objectives.router, prefix=settings.api_prefix)
    app.include_router(workflows.router, prefix=settings.api_prefix)
    app.include_router(audit_logs.router, prefix=settings.api_prefix)

    return app


app = create_app()