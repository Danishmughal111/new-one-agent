"""FastAPI dependency injection.

All dependencies are per-request (except the shared agent runtime which is
bootstrapped idempotently in the application lifespan). No global mutable
service state is used; services are constructed from the request session.
"""

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.agents.registry import AgentRegistry
from app.core.database import get_db
from app.orchestration.company_workflow import CompanyWorkflow
from app.services.agent_service import AgentService
from app.services.audit_service import AuditService
from app.services.department_service import DepartmentService
from app.services.objective_service import ObjectiveService
from app.services.task_service import TaskService
from app.services.workflow_service import WorkflowService


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the lifetime of a request."""
    async for session in get_db():
        yield session


def get_agent_registry(request: Request) -> AgentRegistry:
    """Return the shared, idempotently-bootstrapped agent registry."""
    return request.app.state.agent_registry


def get_department_service(session: AsyncSession = Depends(get_session)) -> DepartmentService:
    return DepartmentService(session)


def get_agent_service(session: AsyncSession = Depends(get_session)) -> AgentService:
    return AgentService(session)


def get_task_service(session: AsyncSession = Depends(get_session)) -> TaskService:
    return TaskService(session)


def get_workflow_service(session: AsyncSession = Depends(get_session)) -> WorkflowService:
    return WorkflowService(session)


def get_audit_service(session: AsyncSession = Depends(get_session)) -> AuditService:
    return AuditService(session)


def get_objective_service(session: AsyncSession = Depends(get_session)) -> ObjectiveService:
    return ObjectiveService(session)


def get_company_workflow(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CompanyWorkflow:
    """Build a CompanyWorkflow from the shared registry + a request TaskService."""
    registry: AgentRegistry = request.app.state.agent_registry
    ceo: BaseAgent = registry.get_by_role("ceo")
    coo: BaseAgent = registry.get_by_role("coo")
    worker: BaseAgent = registry.get_by_role("worker")
    qa: BaseAgent = registry.get_by_role("qa")
    return CompanyWorkflow(
        ceo=ceo,
        coo=coo,
        worker=worker,
        qa=qa,
        task_service=TaskService(session),
    )
