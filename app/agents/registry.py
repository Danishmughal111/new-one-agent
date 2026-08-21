"""Dynamic agent registry.

The registry is used ONLY for discovery and execution lookup — it is NOT a
communication bus. Agents never talk to each other through it.

Agents are registered by role and optionally by capability. Duplicate
registration raises to prevent silent shadowing.
"""

from app.core.exceptions import ValidationError
from app.core.logging import get_logger

logger = get_logger("agents.registry")


class AgentRegistry:
    """Holds runtime agent instances and supports discovery queries."""

    def __init__(self) -> None:
        # role -> agent instance
        self._by_role: dict[str, object] = {}
        # capability -> set of agent ids
        self._by_capability: dict[str, set[str]] = {}
        # agent_id -> agent instance
        self._by_id: dict[str, object] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, agent: object) -> None:
        """Register an agent, rejecting duplicates by role or id.

        ``agent`` must expose ``agent_id``, ``role``, and ``capabilities``
        (the ``BaseAgent`` contract). Type is kept as ``object`` to avoid a
        hard import cycle in case plugins live outside this package.
        """
        agent_id: str = getattr(agent, "agent_id")
        role: str = getattr(agent, "role")
        capabilities: list[str] = getattr(agent, "capabilities", [])

        if role in self._by_role:
            raise ValidationError(f"Agent with role '{role}' is already registered")
        if agent_id in self._by_id:
            raise ValidationError(f"Agent with id '{agent_id}' is already registered")

        self._by_role[role] = agent
        self._by_id[agent_id] = agent
        for capability in capabilities:
            self._by_capability.setdefault(capability, set()).add(agent_id)

        logger.info("Registered agent role=%s id=%s", role, agent_id)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get(self, agent_id: str) -> object | None:
        """Retrieve an agent by id, or None."""
        return self._by_id.get(agent_id)

    def get_by_role(self, role: str) -> object | None:
        """Retrieve an agent by role, or None."""
        return self._by_role.get(role)

    def get_by_capability(self, capability: str) -> list[object]:
        """Retrieve all agents advertising a capability."""
        ids = self._by_capability.get(capability, set())
        return [self._by_id[a] for a in ids if a in self._by_id]

    def list_roles(self) -> list[str]:
        """List registered roles (sorted)."""
        return sorted(self._by_role.keys())

    def __len__(self) -> int:
        return len(self._by_id)


# Convenience singleton (optional); inject this into the workflow.
default_registry = AgentRegistry()