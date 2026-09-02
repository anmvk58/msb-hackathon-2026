from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.local_runtime import LocalAgentRuntime
from app.agent.state import AgentLifecycle, LLMRecommendationDecision
from app.database import get_db
from app.main import app
from app.models import AgentActionLog, AgentRecommendation, Budget


AS_OF = date(2026, 9, 1)


class CountingLLM:
    model = "counting-test-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate_structured(self, **_: object) -> LLMRecommendationDecision:
        self.calls += 1
        return LLMRecommendationDecision(
            summary="Grounded recommendation",
            recommended_option_id="A",
            reasoning_summary="Deterministic test decision",
        )


def _recommend(runtime: LocalAgentRuntime, session: Session):
    return runtime.run(
        session,
        customer_id="C001",
        message="Tài chính tháng này của tôi thế nào?",
        as_of=AS_OF,
    )


def test_agent_run_returns_recommendation_id(session: Session) -> None:
    state = _recommend(LocalAgentRuntime(), session)
    assert state.recommendation_id is not None
    stored = session.get(AgentRecommendation, state.recommendation_id)
    assert stored is not None
    assert stored.recommendation_data["candidate_plan"]["candidate_options"]
    assert stored.recommendation_data["recommendation"]["options"]


def test_select_option_does_not_call_llm_again(session: Session) -> None:
    llm = CountingLLM()
    runtime = LocalAgentRuntime(llm_client=llm)
    recommendation = _recommend(runtime, session)
    runtime.select(session, recommendation_id=recommendation.recommendation_id, option_id="A")
    assert llm.calls == 1


def test_select_option_does_not_rerun_financial_tools(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = _recommend(runtime, session)
    before = session.scalar(
        select(func.count()).select_from(AgentActionLog).where(
            AgentActionLog.action_type == "TOOL_CALL"
        )
    )
    runtime.select(session, recommendation_id=recommendation.recommendation_id, option_id="A")
    after = session.scalar(
        select(func.count()).select_from(AgentActionLog).where(
            AgentActionLog.action_type == "TOOL_CALL"
        )
    )
    assert after == before


def test_select_unknown_option_rejected(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = _recommend(runtime, session)
    try:
        runtime.select(
            session, recommendation_id=recommendation.recommendation_id, option_id="UNKNOWN"
        )
    except ValueError as error:
        assert "Unknown recommendation option" in str(error)
    else:
        raise AssertionError("Unknown option was accepted")


def test_select_expired_recommendation_rejected(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = _recommend(runtime, session)
    stored = session.get(AgentRecommendation, recommendation.recommendation_id)
    stored.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()
    try:
        runtime.select(session, recommendation_id=recommendation.recommendation_id, option_id="A")
    except ValueError as error:
        assert "expired" in str(error)
    else:
        raise AssertionError("Expired recommendation was accepted")


def test_action_log_contains_recommendation_id(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = _recommend(runtime, session)
    waiting = runtime.select(
        session, recommendation_id=recommendation.recommendation_id, option_id="A"
    )
    log = session.get(AgentActionLog, waiting.action_id)
    assert log.recommendation_id == recommendation.recommendation_id
    assert log.signal_id is not None


def test_confirmation_uses_previously_persisted_tool_parameters(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = _recommend(runtime, session)
    waiting = runtime.select(
        session, recommendation_id=recommendation.recommendation_id, option_id="A"
    )
    log = session.get(AgentActionLog, waiting.action_id)
    persisted_arguments = dict(log.tool_input)
    executed = runtime.confirm(session, action_id=waiting.action_id, confirmed=True)
    budget = session.scalar(select(Budget).where(Budget.customer_id == "C001"))
    assert executed.state == AgentLifecycle.MONITORING
    assert budget.amount == int(persisted_arguments["amount"])


def test_client_cannot_modify_action_parameters_during_select(session: Session) -> None:
    runtime = app.dependency_overrides

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        recommendation = client.post(
            "/api/agent/run",
            json={"customer_id": "C001", "message": "Radar", "as_of": "2026-09-01"},
        )
        response = client.post(
            "/api/agent/select",
            json={
                "recommendation_id": recommendation.json()["recommendation_id"],
                "option_id": "A",
                "parameters": {"amount": "1"},
            },
        )
    runtime.clear()
    assert response.status_code == 422


def test_create_budget_transitions_to_monitoring_after_execute(session: Session) -> None:
    runtime = LocalAgentRuntime()
    recommendation = _recommend(runtime, session)
    waiting = runtime.select(
        session, recommendation_id=recommendation.recommendation_id, option_id="A"
    )
    executed = runtime.confirm(session, action_id=waiting.action_id, confirmed=True)
    assert executed.state == AgentLifecycle.MONITORING
