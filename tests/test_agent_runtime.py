from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.local_runtime import LocalAgentRuntime
from app.agent.state import AgentLifecycle
from app.models import AgentActionLog, Budget


AS_OF = date(2026, 9, 1)


def test_agent_run_returns_grounded_recommendation(session: Session) -> None:
    state = LocalAgentRuntime().run(
        session,
        customer_id="C001",
        message="Tài chính tháng này của tôi thế nào?",
        as_of=AS_OF,
    )
    assert state.state == AgentLifecycle.RECOMMENDATION_READY
    assert state.financial_analysis["forecast_balance"] == "1366667"
    assert state.recommendation is not None
    assert state.recommendation.recommended_option_id == "A"
    assert state.recommendation.options[0].parameters["amount"] == "4000000"


def test_action_not_executed_before_confirmation(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = runtime.run(
        session,
        customer_id="C001",
        message="Tạo ngân sách theo phương án A",
        as_of=AS_OF,
    )
    state = runtime.select(
        session, recommendation_id=recommendation.recommendation_id, option_id="A"
    )
    assert state.state == AgentLifecycle.WAITING_CONFIRMATION
    assert state.action_id is not None
    assert session.scalar(
        select(func.count()).select_from(Budget).where(Budget.customer_id == "C001")
    ) == 0
    log = session.get(AgentActionLog, state.action_id)
    assert log is not None
    assert log.action_status == "PREPARED"
    assert log.tool_output is None


def test_action_log_created_after_execution(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = runtime.run(
        session,
        customer_id="C001",
        message="Tạo ngân sách theo phương án A",
        as_of=AS_OF,
    )
    waiting = runtime.select(
        session, recommendation_id=recommendation.recommendation_id, option_id="A"
    )
    executed = runtime.confirm(session, action_id=waiting.action_id, confirmed=True)
    assert executed.state == AgentLifecycle.MONITORING
    assert executed.execution_result["status"] == "SUCCESS"
    budget = session.scalar(select(Budget).where(Budget.customer_id == "C001"))
    assert budget is not None
    assert budget.amount == Decimal("4000000")
    log = session.get(AgentActionLog, waiting.action_id)
    assert log.action_status == "SUCCESS"
    assert log.confirmation_status == "CONFIRMED"
    assert log.tool_output["budget_id"] == budget.budget_id
    assert log.latency_ms is not None


def test_declined_action_is_never_executed(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = runtime.run(
        session,
        customer_id="C001",
        message="Tạo ngân sách theo phương án A",
        as_of=AS_OF,
    )
    waiting = runtime.select(
        session, recommendation_id=recommendation.recommendation_id, option_id="A"
    )
    declined = runtime.confirm(session, action_id=waiting.action_id, confirmed=False)
    assert declined.state == AgentLifecycle.FAILED
    assert session.scalar(
        select(func.count()).select_from(Budget).where(Budget.customer_id == "C001")
    ) == 0


def test_all_agent_tool_calls_are_traced(session: Session) -> None:
    LocalAgentRuntime().run(
        session,
        customer_id="C002",
        message="Có chi tiêu nào bất thường không?",
        as_of=AS_OF,
    )
    traced_tools = set(
        session.scalars(
            select(AgentActionLog.tool_name).where(
                AgentActionLog.action_type == "TOOL_CALL",
                AgentActionLog.customer_id == "C002",
            )
        ).all()
    )
    assert traced_tools == {
        "get_financial_snapshot",
        "forecast_cashflow",
        "detect_spending_anomaly",
        "detect_upcoming_recurring",
    }
