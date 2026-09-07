from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.state import ActionDraft, AgentLifecycle, RecommendationOption


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"customer_id": "C001", "message": "Phân tích tài chính và đề xuất hành động phù hợp", "as_of": "2026-09-02"}]})

    customer_id: str = Field(description="Mã khách hàng; dữ liệu demo có C001 đến C004", examples=["C001"])
    message: str = Field(min_length=1, max_length=2000, description="Yêu cầu bằng ngôn ngữ tự nhiên gửi tới Agent")
    as_of: date | None = Field(default=None, description="Ngày phân tích; bỏ trống để dùng ngày hiện tại")


class AgentSelectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"recommendation_id": "R-EXAMPLE", "option_id": "A"}]})

    recommendation_id: str = Field(description="ID nhận được từ /api/agent/run")
    option_id: str = Field(description="Mã phương án trong recommendations, ví dụ A hoặc B")


class AgentConfirmRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"action_id": "A-EXAMPLE", "confirmed": True}]})

    action_id: str = Field(description="ID action nhận được từ /api/agent/select")
    confirmed: bool = Field(description="true để thực thi, false để từ chối")


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
