from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.state import AgentLifecycle, RadarState
from app.policy import PolicyEngine
from app.tools import build_tool_registry
from app.tools.contracts import ConfirmationPolicy
from app.tools.schemas import CreateBudgetInput


def test_registry_exposes_exact_mvp_tools() -> None:
    registry = build_tool_registry()
    names = {item.name for item in registry.metadata()}
    assert names == {
        "get_financial_snapshot",
        "detect_spending_anomaly",
        "detect_upcoming_recurring",
        "forecast_cashflow",
        "simulate_goal_scenarios",
        "create_budget",
        "create_reminder",
        "update_goal",
    }


def test_tool_uses_financial_engine(session: Session) -> None:
    output = build_tool_registry().execute(
        session,
        "forecast_cashflow",
        {
            "customer_id": "C001",
            "as_of": "2026-09-01",
            "forecast_until": "2026-09-15",
        },
    )
    assert output.forecast_balance == Decimal("1366667")


def test_create_budget_requires_confirmation() -> None:
    registry = build_tool_registry()
    decision = PolicyEngine(registry).evaluate("create_budget")
    assert decision.allowed is True
    assert decision.confirmation_required is True
    assert decision.confirmation_policy == ConfirmationPolicy.REQUIRED


def test_create_budget_server_side_validation() -> None:
    with pytest.raises(ValidationError):
        CreateBudgetInput(
            customer_id="C001",
            category="SALARY",
            amount=4_000_000,
            alert_threshold=Decimal("1.2"),
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )


def test_state_machine_rejects_confirmation_bypass() -> None:
    state = RadarState(customer_id="C001")
    with pytest.raises(ValueError, match="Invalid agent transition"):
        state.transition(AgentLifecycle.EXECUTING)


def test_state_machine_valid_prepare_flow() -> None:
    state = RadarState(customer_id="C001")
    for lifecycle in (
        AgentLifecycle.CONTEXT_READY,
        AgentLifecycle.SIGNAL_DETECTED,
        AgentLifecycle.ANALYSIS_READY,
        AgentLifecycle.RECOMMENDATION_READY,
        AgentLifecycle.ACTION_PREPARED,
        AgentLifecycle.WAITING_CONFIRMATION,
        AgentLifecycle.EXECUTING,
        AgentLifecycle.EXECUTED,
    ):
        state.transition(lifecycle)
    assert state.state == AgentLifecycle.EXECUTED

