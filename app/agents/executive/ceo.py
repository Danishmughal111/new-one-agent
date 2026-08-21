"""CEO agent — deterministic strategic decomposition.

Converts a high-level human objective into structured strategic objectives.
The CEO NEVER directly creates or assigns database tasks — that is the COO's
responsibility via the service layer.
"""

from typing import Any

from app.agents.base import AgentContext, AgentExecutionResult, BaseAgent

# Simple deterministic keyword -> (departments, actions) mapping. Phase 1 has
# no LLM; this is clearly-marked placeholder logic.
_STRATEGY_RULES: dict[str, dict[str, Any]] = {
    "affiliate": {
        "priority": "high",
        "recommended_departments": ["TrendEra", "Marketing"],
        "actions": [
            "Research high-demand affiliate products",
            "Analyze existing content performance",
            "Identify new content opportunities",
        ],
    },
    "automation": {
        "priority": "high",
        "recommended_departments": ["AI Automation"],
        "actions": [
            "Document client automation requirements",
            "Design n8n workflow architecture",
            "Prototype local AI agent workflow",
        ],
    },
    "content": {
        "priority": "medium",
        "recommended_departments": ["TrendEra", "Content"],
        "actions": [
            "Audit existing content inventory",
            "Identify content gaps",
            "Draft new content briefs",
        ],
    },
    "seo": {
        "priority": "medium",
        "recommended_departments": ["TrendEra", "SEO"],
        "actions": [
            "Perform keyword gap analysis",
            "Optimize underperforming pages",
            "Build internal linking plan",
        ],
    },
}

_DEFAULT_ACTIONS = [
    "Break objective into concrete work streams",
    "Identify required departments and capabilities",
    "Delegate to the COO for task planning",
]


class CEOAgent(BaseAgent):
    """Receives objectives and produces strategic directions."""

    role = "ceo"

    def __init__(
        self,
        agent_id: str,
        name: str = "CEO Agent",
        capabilities: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities or ["strategic_decomposition", "objective_delegation"],
            permissions=permissions or ["system.read"],
        )

    async def execute(self, context: AgentContext) -> AgentExecutionResult:
        """Decompose the human objective into structured strategic objectives."""
        objective_text = context.payload.get("objective", "").strip()
        if not objective_text:
            return self.create_result(ok=False, error="Empty objective provided")

        strategy = self._derive_strategy(objective_text)
        strategy["generated_by"] = "deterministic_placeholder"
        strategy["simulated"] = True
        strategy["objective"] = objective_text

        self.logger.info("CEO produced strategic objectives for '%s'", objective_text[:80])
        return self.create_result(ok=True, data=strategy)

    def _derive_strategy(self, objective_text: str) -> dict[str, Any]:
        """Deterministically map an objective to a strategic plan."""
        lowered = objective_text.lower()
        matched = next(
            (rule for keyword, rule in _STRATEGY_RULES.items() if keyword in lowered),
            None,
        )
        if matched is None:
            return {
                "objective_type": "strategic",
                "priority": "medium",
                "recommended_departments": ["TrendEra", "AI Automation"],
                "actions": list(_DEFAULT_ACTIONS),
            }
        return {
            "objective_type": "strategic",
            "priority": matched["priority"],
            "recommended_departments": list(matched["recommended_departments"]),
            "actions": list(matched["actions"]),
        }