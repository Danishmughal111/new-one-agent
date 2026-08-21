"""Agent system: base abstraction, registry, and concrete company agents."""

from app.agents.base import (
    AgentContext,
    AgentExecutionResult,
    BaseAgent,
)
from app.agents.registry import AgentRegistry, default_registry
from app.agents.executive.ceo import CEOAgent
from app.agents.executive.coo import COOAgent
from app.agents.executive.chief_of_staff import ChiefOfStaffAgent
from app.agents.quality.qa import QAAgent
from app.agents.security.security_agent import SecurityAgent
from app.agents.worker import WorkerAgent

__all__ = [
    "AgentContext",
    "AgentExecutionResult",
    "AgentRegistry",
    "BaseAgent",
    "CEOAgent",
    "COOAgent",
    "ChiefOfStaffAgent",
    "QAAgent",
    "SecurityAgent",
    "WorkerAgent",
    "default_registry",
]