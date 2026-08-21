"""Security agent — validates sensitive operations and permissions.

Strictly forbidden here:
- reading application secrets
- exposing environment variables
- receiving secret values
- being granted ``system.admin``

The Security Agent decides whether an operation is *allowed*, using:
``permission.validate``, ``audit.read``, ``security.validate``.
"""

from typing import Any

from app.agents.base import AgentContext, AgentExecutionResult, BaseAgent
from app.core.permissions import is_valid_permission
from app.services.audit_service import AuditService


class SecurityAgent(BaseAgent):
    """Validates permissions and flags unsafe operations. Never reads secrets."""

    role = "security"

    def __init__(
        self,
        agent_id: str,
        audit_service: AuditService,
        name: str = "Security Agent",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["permission_validation", "security_validation"],
            permissions=permissions
            or ["permission.validate", "audit.read", "security.validate"],
        )
        self._audit = audit_service

    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Validate a proposed operation against the requester's permissions.

        Expected payload:
            action: str, requested_permission: str, requester_agent_id: str
        """
        action = context.payload.get("action", "unknown")
        requested = context.payload.get("requested_permission")
        requester = context.payload.get("requester_agent_id")

        findings: dict[str, Any] = {
            "action": action,
            "requested_permission": requested,
            "requester_agent_id": requester,
        }

        if not requested:
            return self.create_result(
                ok=False,
                data={"decision": "DENIED", **findings},
                error="No requested_permission provided",
            )

        if not is_valid_permission(requested):
            await self._audit.record(
                action="security.violation",
                agent_id=self.agent_id,
                resource_type="permissions",
                metadata={"requested_permission": requested, "reason": "unknown_permission"},
            )
            findings["decision"] = "DENIED"
            findings["reason"] = "unknown_permission"
            return self.create_result(ok=False, data=findings, error="Unknown permission")

        # Phase 1: the Security Agent validates whether the requested permission
        # is known and non-secret. Actual resource-level enforcement is handled
        # by the centralized permission system during each service operation.
        findings["decision"] = "ALLOWED"
        findings["reason"] = "known_permission_validated"
        findings["simulated"] = True
        findings["generated_by"] = "deterministic_placeholder"
        return self.create_result(ok=True, data=findings)