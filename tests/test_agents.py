"""Agent unit/integration tests (registry + concrete agents)."""

import pytest

from app.agents.base import AgentContext
from app.agents.executive.ceo import CEOAgent
from app.agents.executive.coo import COOAgent
from app.agents.quality.qa import QAAgent
from app.agents.registry import AgentRegistry
from app.agents.security.security_agent import SecurityAgent
from app.core.exceptions import ValidationError
from app.schemas.agent import AgentCreate
from app.schemas.task import TaskCreate, TaskStatusTransition, TaskUpdate
from app.services.agent_service import AgentService
from app.services.audit_service import AuditService
from app.services.task_service import TaskService


def test_agent_registry_registers_and_looks_up() -> None:
    registry = AgentRegistry()
    ceo = CEOAgent(agent_id="ceo-1", permissions=["system.read"])
    registry.register(ceo)
    assert registry.get("ceo-1") is ceo
    assert registry.get_by_role("ceo") is ceo
    assert "ceo" in registry.list_roles()


def test_agent_registry_duplicate_rejected() -> None:
    registry = AgentRegistry()
    registry.register(CEOAgent(agent_id="ceo-1", permissions=["system.read"]))
    with pytest.raises(ValidationError):
        registry.register(CEOAgent(agent_id="ceo-1", permissions=["system.read"]))


async def test_ceo_deterministic_output() -> None:
    ceo = CEOAgent(agent_id="ceo-1", permissions=["system.read"])
    result = await ceo.execute(
        AgentContext(payload={"objective": "Increase TrendEra affiliate revenue"})
    )
    assert result.ok is True
    assert result.data["objective_type"] == "strategic"
    assert "TrendEra" in result.data["recommended_departments"]
    assert result.data["simulated"] is True


async def test_coo_generates_and_assigns_tasks(session, department) -> None:
    agent_service = AgentService(session)
    coo = await agent_service.create(
        AgentCreate(
            name="COO", role="coo", department_id=department.id,
            permissions=["task.create", "task.assign"],
        )
    )
    worker = await agent_service.create(
        AgentCreate(
            name="Worker", role="worker", department_id=department.id,
            permissions=["agent.execute"],
        )
    )
    task_service = TaskService(session)
    coo_agent = COOAgent(
        agent_id=coo.id,
        task_service=task_service,
        agent_service=agent_service,
        permissions=["task.create", "task.assign"],
    )
    result = await coo_agent.execute(
        AgentContext(
            payload={
                "objective": "Test objective",
                "actions": ["Action A", "Action B"],
                "priority": "high",
                "worker_agent_id": worker.id,
            }
        )
    )
    assert result.ok is True
    assert len(result.data["created_tasks"]) == 2


async def test_qa_approval(session, department) -> None:
    qa = await AgentService(session).create(
        AgentCreate(
            name="QA", role="qa", department_id=department.id,
            permissions=["task.review", "task.approve", "task.reject"],
        )
    )
    task_service = TaskService(session)
    task = await task_service.create(TaskCreate(title="Task"))
    await task_service.transition(task.id, TaskStatusTransition(target_status="QUEUED"))
    await task_service.transition(task.id, TaskStatusTransition(target_status="IN_PROGRESS"))
    await task_service.update(task.id, TaskUpdate(result={"output": "done"}))
    await task_service.transition(task.id, TaskStatusTransition(target_status="REVIEW"))

    qa_agent = QAAgent(
        agent_id=qa.id,
        task_service=task_service,
        permissions=["task.review", "task.approve", "task.reject"],
    )
    result = await qa_agent.execute(AgentContext(task_id=task.id))
    assert result.ok is True
    assert result.data["decision"] == "APPROVED"
    assert (await task_service.get(task.id)).status == "COMPLETED"


async def test_qa_rejection_invalid_result(session, department) -> None:
    qa = await AgentService(session).create(
        AgentCreate(
            name="QA", role="qa", department_id=department.id,
            permissions=["task.review", "task.approve", "task.reject"],
        )
    )
    task_service = TaskService(session)
    task = await task_service.create(TaskCreate(title="Task"))
    await task_service.transition(task.id, TaskStatusTransition(target_status="QUEUED"))
    await task_service.transition(task.id, TaskStatusTransition(target_status="IN_PROGRESS"))
    # invalid result: missing "output"
    await task_service.update(task.id, TaskUpdate(result={"simulated": True}))
    await task_service.transition(task.id, TaskStatusTransition(target_status="REVIEW"))

    qa_agent = QAAgent(
        agent_id=qa.id,
        task_service=task_service,
        permissions=["task.review", "task.approve", "task.reject"],
    )
    result = await qa_agent.execute(AgentContext(task_id=task.id))
    assert result.ok is False
    assert result.data["decision"] == "REJECTED"
    assert (await task_service.get(task.id)).status == "REVISION_REQUIRED"


async def test_security_agent_permission_validation(session) -> None:
    audit = AuditService(session)
    security = SecurityAgent(agent_id="sec-1", audit_service=audit)

    allowed = await security.execute(
        AgentContext(payload={"requested_permission": "task.create"})
    )
    assert allowed.ok is True

    denied = await security.execute(
        AgentContext(payload={"requested_permission": "secret.read"})
    )
    assert denied.ok is False
    assert denied.data["decision"] == "DENIED"