from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.state import ActionDraft, AgentLifecycle, RecommendationOption


class AgentRunRequest(BaseModel):
    customer_id: str
    message: str = Field(min_length=1, max_length=2000)
    as_of: date | None = None


class AgentSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    option_id: str


class AgentConfirmRequest(BaseModel):
    action_id: str
    confirmed: bool


class ConfirmationView(BaseModel):
    required: bool
    status: str


class AgentResponse(BaseModel):
    message: str
    state: AgentLifecycle
    customer_id: str
    signals: list[dict[str, Any]] = Field(default_factory=list)
    analysis: dict[str, Any] | None = None
    recommendations: list[RecommendationOption] = Field(default_factory=list)
    recommended_option_id: str | None = None
    recommendation_id: str | None = None
    action_id: str | None = None
    action: ActionDraft | None = None
    confirmation: ConfirmationView
    execution_result: dict[str, Any] | None = None
    error: str | None = None


def response_from_state(state: "RadarState") -> AgentResponse:
    from app.agent.state import RadarState

    if not isinstance(state, RadarState):
        raise TypeError("state must be RadarState")
    recommendation = state.recommendation
    if state.state == AgentLifecycle.WAITING_CONFIRMATION:
        message = "Tôi đã chuẩn bị hành động. Vui lòng xác nhận trước khi thực thi."
    elif state.state in {AgentLifecycle.EXECUTED, AgentLifecycle.MONITORING}:
        message = "Hành động đã được thực thi thành công."
    elif recommendation:
        message = recommendation.summary
    else:
        message = state.error or "Financial Radar completed."
    return AgentResponse(
        message=message,
        state=state.state,
        customer_id=state.customer_id,
        signals=state.signals,
        analysis=state.financial_analysis,
        recommendations=recommendation.options if recommendation else [],
        recommended_option_id=recommendation.recommended_option_id if recommendation else None,
        recommendation_id=state.recommendation_id,
        action_id=state.action_id,
        action=state.action_draft,
        confirmation=ConfirmationView(
            required=bool(state.policy_result and state.policy_result.confirmation_required),
            status=state.confirmation_status,
        ),
        execution_result=state.execution_result,
        error=state.error,
    )
