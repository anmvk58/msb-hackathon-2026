from pydantic import BaseModel

from app.tools.contracts import ConfirmationPolicy, RiskLevel
from app.tools.registry import ToolRegistry


class PolicyDecision(BaseModel):
    allowed: bool
    risk_level: RiskLevel
    confirmation_required: bool
    confirmation_policy: ConfirmationPolicy
    reason: str


class PolicyEngine:
    """Deterministic action policy. It cannot be overridden by an LLM."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def evaluate(self, tool_name: str) -> PolicyDecision:
        tool = self.registry.get(tool_name)
        if tool.risk_level == RiskLevel.HIGH:
            return PolicyDecision(
                allowed=False,
                risk_level=tool.risk_level,
                confirmation_required=True,
                confirmation_policy=ConfirmationPolicy.AUTHENTICATED,
                reason="High-risk financial transactions are outside the MVP.",
            )
        required = tool.confirmation_policy in {
            ConfirmationPolicy.REQUIRED,
            ConfirmationPolicy.EXPLICIT,
            ConfirmationPolicy.AUTHENTICATED,
        }
        return PolicyDecision(
            allowed=True,
            risk_level=tool.risk_level,
            confirmation_required=required,
            confirmation_policy=tool.confirmation_policy,
            reason=(
                "Explicit customer confirmation is required before execution."
                if required
                else "Read-only or pre-authorized low-risk operation."
            ),
        )

