"""Database/service integration tests (SQLite)."""

import pytest

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.schemas.agent import AgentCreate
from app.schemas.department import DepartmentCreate
from app.schemas.objective import ObjectiveCreate
from app.schemas.task import TaskCreate, TaskStatusTransition
from app.services.agent_service import AgentService
from app.services.audit_service import AuditService
from app.services.department_service import DepartmentService
from app.services.objective_service import ObjectiveService
from app.services.task_service import TaskService


async def test_department_creation_and_list(session) -> None:
    svc = DepartmentService(session)
    dept = await svc.create(DepartmentCreate(name="Executive"))
    assert dept.id
    listed = await svc.list()
    assert any(d.id == dept.id for d in listed)


async def test_department_duplicate_name_rejected(session) -> None:
    svc = DepartmentService(session)
    await svc.create(DepartmentCreate(name="Executive"))
    with pytest.raises(ValidationError):
        await svc.create(DepartmentCreate(name="Executive"))


async def test_agent_creation(session, department) -> None:
    svc = AgentService(session)
    agent = await svc.create(
        AgentCreate(name="CEO", role="ceo", department_id=department.id, permissions=["system.read"])
    )
    assert agent.role == "ceo"
    fetched = await svc.get(agent.id)
    assert fetched.name == "CEO"


async def test_agent_unknown_permission_rejected(session, department) -> None:
    svc = AgentService(session)
    with pytest.raises(ValidationError):
        await svc.create(
            AgentCreate(name="Bad", role="x", department_id=department.id, permissions=["secret.read"])
        )


async def test_task_creation(session, coo_agent) -> None:
    svc = TaskService(session)
    task = await svc.create(TaskCreate(title="Research", created_by_agent_id=coo_agent.id))
    assert task.status == "PENDING"


async def test_task_assignment(session, coo_agent, worker_agent) -> None:
    svc = TaskService(session)
    task = await svc.create(TaskCreate(title="Research", created_by_agent_id=coo_agent.id))
    assigned = await svc.assign(task.id, worker_agent.id, changed_by_agent_id=coo_agent.id)
    assert assigned.assigned_agent_id == worker_agent.id


async def test_task_assignment_permission_denied(session, worker_agent) -> None:
    svc = TaskService(session)
    task = await svc.create(TaskCreate(title="Research"))
    with pytest.raises(PermissionDeniedError):
        await svc.assign(task.id, worker_agent.id, changed_by_agent_id=worker_agent.id)


async def test_task_history_created(session, coo_agent, task) -> None:
    svc = TaskService(session)
    history = await svc.get_history(task.id)
    assert [h.new_status for h in history] == ["PENDING"]


async def test_objective_creation_and_persistence(session) -> None:
    svc = ObjectiveService(session)
    obj = await svc.create(ObjectiveCreate(title="Objective A"))
    assert obj.status == "PENDING"
    fetched = await svc.get(obj.id)
    assert fetched.title == "Objective A"


async def test_audit_logging(session, department) -> None:
    # department.create audited by DepartmentService
    audit = AuditService(session)
    logs = await audit.list(limit=100)
    assert any(l.action == "department.create" for l in logs)


async def test_task_not_found(session) -> None:
    svc = TaskService(session)
    with pytest.raises(NotFoundError):
        await svc.get("does-not-exist")