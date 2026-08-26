"""CompanyWorkflow integration tests (SQLite)."""

from app.agents.base import AgentContext
from app.agents.executive.ceo import CEOAgent
from app.agents.executive.coo import COOAgent
from app.agents.quality.qa import QAAgent
from app.agents.worker import WorkerAgent
from app.agents.factory import ensure_company_agents
from app.agents.registry import AgentRegistry
from app.orchestration.company_workflow import CompanyWorkflow
from app.schemas.objective import ObjectiveCreate
from app.schemas.task import TaskCreate, TaskStatusTransition, TaskUpdate
from app.services.agent_service import AgentService
from app.services.objective_service import ObjectiveService
from app.services.task_service import TaskService


async def _bootstrap_workflow(session):
    """Build a full workflow using idempotent company-agent bootstrap."""
    registry = AgentRegistry()
    agents = await ensure_company_agents(session, registry)
    task_service = TaskService(session)
    workflow = CompanyWorkflow(
        ceo=agents["ceo"],
        coo=agents["coo"],
        worker=agents["worker"],
        qa=agents["qa"],
        task_service=task_service,
    )
    return task_service, agents, workflow


async def test_company_workflow_success(session) -> None:
    task_service, agents, workflow = await _bootstrap_workflow(session)
    result = await workflow.run("Increase TrendEra affiliate revenue")
    assert result.ok is True
    assert result.final_status == "COMPLETED"
    assert len(result.tasks) == 3
    assert all(t["status"] == "COMPLETED" for t in result.tasks)


async def test_company_workflow_rejection_path(session) -> None:
    """An invalid task result must be rejected -> REVISION_REQUIRED via QA."""
    task_service, agents, workflow = await _bootstrap_workflow(session)

    task = await task_service.create(
        TaskCreate(title="Bad result task", created_by_agent_id=agents["coo"].agent_id)
    )
    await task_service.assign(
        task.id, agents["worker"].agent_id, changed_by_agent_id=agents["coo"].agent_id
    )
    await task_service.transition(
        task.id, TaskStatusTransition(target_status="QUEUED", changed_by_agent_id=agents["coo"].agent_id)
    )
    await task_service.transition(
        task.id, TaskStatusTransition(target_status="IN_PROGRESS", changed_by_agent_id=agents["worker"].agent_id)
    )
    # Invalid result (missing "output").
    await task_service.update(task.id, TaskUpdate(result={"simulated": True}))
    await task_service.transition(
        task.id, TaskStatusTransition(target_status="REVIEW", changed_by_agent_id=agents["worker"].agent_id)
    )

    qa_result = await agents["qa"].execute(AgentContext(task_id=task.id))
    assert qa_result.ok is False
    assert qa_result.data["decision"] == "REJECTED"
    assert (await task_service.get(task.id)).status == "REVISION_REQUIRED"


async def test_completed_objective_status(session) -> None:
    task_service, agents, workflow = await _bootstrap_workflow(session)
    objective_service = ObjectiveService(session)
    objective = await objective_service.create(
        ObjectiveCreate(title="Increase TrendEra affiliate revenue")
    )
    updated, result = await objective_service.run(objective.id, workflow)
    assert result.ok is True
    assert updated.status == "COMPLETED"