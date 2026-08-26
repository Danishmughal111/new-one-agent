"""Shared pytest fixtures.

Sets an isolated SQLite database URL BEFORE importing application code so the
cached ``Settings`` picks it up, then recreates a clean schema before each
test. Tests never depend on a live PostgreSQL instance or external APIs.
"""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEBUG"] = "false"
# Force the deterministic mock LLM so no test can ever hit the live DeepSeek
# API (even when a .env DEEPSEEK_API_KEY is present). Env vars override .env.
os.environ["DEEPSEEK_API_KEY"] = ""

import httpx
import pytest
import pytest_asyncio

from app.core.database import async_session_factory, create_all, drop_all
from app.main import create_app
from app.schemas.agent import AgentCreate
from app.schemas.department import DepartmentCreate
from app.schemas.objective import ObjectiveCreate
from app.schemas.task import TaskCreate
from app.services.agent_service import AgentService
from app.services.department_service import DepartmentService
from app.services.objective_service import ObjectiveService
from app.services.task_service import TaskService


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Ensure a clean, isolated schema before every test."""
    await drop_all()
    await create_all()
    yield
    await drop_all()


@pytest_asyncio.fixture
async def session():
    """Yield an async DB session bound to the test SQLite database."""
    async with async_session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client():
    """Yield a FastAPI test client with the application lifespan executed."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest_asyncio.fixture
async def department(session):
    """Create and return a department through the service."""
    return await DepartmentService(session).create(DepartmentCreate(name="Executive"))


@pytest_asyncio.fixture
async def worker_agent(session, department):
    """Create and return a worker agent (agent.execute permission)."""
    return await AgentService(session).create(
        AgentCreate(
            name="Worker Agent",
            role="worker",
            department_id=department.id,
            permissions=["agent.execute"],
        )
    )


@pytest_asyncio.fixture
async def coo_agent(session, department):
    """Create and return a COO agent (task.create + task.assign)."""
    return await AgentService(session).create(
        AgentCreate(
            name="COO Agent",
            role="coo",
            department_id=department.id,
            permissions=["task.create", "task.assign"],
        )
    )


@pytest_asyncio.fixture
async def qa_agent(session, department):
    """Create and return a QA agent (review/approve/reject)."""
    return await AgentService(session).create(
        AgentCreate(
            name="QA Agent",
            role="qa",
            department_id=department.id,
            permissions=["task.review", "task.approve", "task.reject"],
        )
    )


@pytest_asyncio.fixture
async def task(session, coo_agent):
    """Create and return a plain PENDING task created by the COO agent."""
    return await TaskService(session).create(
        TaskCreate(title="Test task", created_by_agent_id=coo_agent.id)
    )


@pytest_asyncio.fixture
async def objective(session):
    """Create and return a persisted objective."""
    return await ObjectiveService(session).create(
        ObjectiveCreate(title="Increase TrendEra affiliate revenue")
    )