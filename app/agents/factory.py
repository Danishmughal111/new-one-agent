"""Factory for instantiating and registering the default company agents.

Performs the heavy lifting of:
- ensuring departments exist (via ``DepartmentService``)
- ensuring agent records exist (via ``AgentService``)
- building runtime agent instances with the agents' real DB ids
- registering them into an ``AgentRegistry``

No DB queries are written here directly — everything flows through services.
Runtime agent ids MUST match the persisted agent records so that service-level
permission lookups (which resolve an actor by id) work correctly.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.agents.executive.ceo import CEOAgent
from app.agents.executive.chief_of_staff import ChiefOfStaffAgent
from app.agents.executive.coo import COOAgent
from app.agents.quality.qa import QAAgent
from app.agents.registry import AgentRegistry
from app.agents.security.security_agent import SecurityAgent
from app.agents.worker import WorkerAgent
from app.core.logging import get_logger
from app.models.agent import Agent
from app.schemas.agent import AgentCreate
from app.schemas.department import DepartmentCreate
from app.services.agent_service import AgentService
from app.services.audit_service import AuditService
from app.services.department_service import DepartmentService
from app.services.task_service import TaskService

logger = get_logger("agents.factory")

# role -> (name, permissions, capabilities) for the Phase 1 agents.
_AGENT_SPECS = {
    "ceo": {
        "name": "CEO Agent",
        "permissions": ["system.read"],
        "capabilities": ["strategic_decomposition", "objective_delegation"],
    },
    "coo": {
        "name": "COO Agent",
        "permissions": ["task.create", "task.assign"],
        "capabilities": ["task_planning", "task_delegation"],
    },
    "chief_of_staff": {
        "name": "Chief of Staff Agent",
        "permissions": ["system.read"],
        "capabilities": ["monitoring", "operational_reporting"],
    },
    "qa": {
        "name": "QA Agent",
        "permissions": ["task.review", "task.approve", "task.reject"],
        "capabilities": ["quality_review"],
    },
    "security": {
        "name": "Security Agent",
        "permissions": ["permission.validate", "audit.read", "security.validate"],
        "capabilities": ["permission_validation", "security_validation"],
    },
    "worker": {
        "name": "Worker Agent",
        "permissions": ["agent.execute"],
        "capabilities": ["deterministic_execution"],
    },
}


async def _ensure_departments(
    department_service: DepartmentService,
) -> dict[str, str]:
    """Create (if missing) core departments and return name -> id."""
    names = ["Executive", "TrendEra", "AI Automation"]
    existing = await department_service.list(limit=1000)
    by_name = {d.name: d.id for d in existing}

    for name in names:
        if name not in by_name:
            created = await department_service.create(DepartmentCreate(name=name))
            by_name[name] = created.id
    return {name: by_name[name] for name in names}


def _build_agents(
    registry: AgentRegistry,
    task_service: TaskService,
    agent_service: AgentService,
    audit_service: AuditService,
    records: dict[str, Agent],
) -> dict[str, BaseAgent]:
    """Instantiate and register agents using their real DB ids."""
    ceo = CEOAgent(
        agent_id=records["ceo"].id,
        permissions=list(records["ceo"].permissions),
    )
    coo = COOAgent(
        agent_id=records["coo"].id,
        task_service=task_service,
        agent_service=agent_service,
        permissions=list(records["coo"].permissions),
    )
    chief = ChiefOfStaffAgent(
        agent_id=records["chief_of_staff"].id,
        task_service=task_service,
        permissions=list(records["chief_of_staff"].permissions),
    )
    qa = QAAgent(
        agent_id=records["qa"].id,
        task_service=task_service,
        permissions=list(records["qa"].permissions),
    )
    security = SecurityAgent(
        agent_id=records["security"].id,
        audit_service=audit_service,
        permissions=list(records["security"].permissions),
    )
    worker = WorkerAgent(
        agent_id=records["worker"].id,
        task_service=task_service,
        permissions=list(records["worker"].permissions),
    )

    for agent in (ceo, coo, chief, qa, security, worker):
        registry.register(agent)

    return {
        "ceo": ceo,
        "coo": coo,
        "chief_of_staff": chief,
        "qa": qa,
        "security": security,
        "worker": worker,
    }


async def ensure_company_agents(
    session: AsyncSession,
    registry: AgentRegistry,
) -> dict[str, BaseAgent]:
    """Ensure agent DB records exist, then build + register runtime agents.

    Idempotent: repeated calls on a fresh registry are safe. If any well-known
    agent record already exists (matched by role), it is reused rather than
    duplicated.
    """
    task_service = TaskService(session)
    agent_service = AgentService(session)
    audit_service = AuditService(session)
    department_service = DepartmentService(session)

    departments = await _ensure_departments(department_service)
    executive_dept = departments["Executive"]
    trendera_dept = departments["TrendEra"]

    existing_agents = await agent_service.list(limit=1000)
    by_role = {a.role: a for a in existing_agents}

    records: dict[str, Agent] = {}
    for role, spec in _AGENT_SPECS.items():
        if role in by_role:
            records[role] = by_role[role]
            continue
        department_id = trendera_dept if role == "worker" else executive_dept
        records[role] = await agent_service.create(
            AgentCreate(
                name=spec["name"],
                role=role,
                department_id=department_id,
                permissions=spec["permissions"],
                capabilities=spec["capabilities"],
            )
        )

    logger.info("Company agents ready: roles=%s", sorted(records.keys()))
    return _build_agents(
        registry=registry,
        task_service=task_service,
        agent_service=agent_service,
        audit_service=audit_service,
        records=records,
    )