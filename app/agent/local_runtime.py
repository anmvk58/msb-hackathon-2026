from datetime import date, datetime, time
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.runtime import AgentRuntime
from app.agent.state import (
    ActionDraft,
    AgentLifecycle,
    RadarState,
    RecommendationResult,
)
from app.financial_engine import calculate_budget_guardrail
from app.llm import LLMClient, MockLLMClient
from app.llm.prompts import FINANCIAL_RADAR_SYSTEM_PROMPT
from app.models import AgentActionLog, Category, RadarSignal, SignalStatus, SignalType
from app.policy import PolicyEngine
from app.tools import ToolRegistry, build_tool_registry


def _json(value: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class LocalAgentRuntime(AgentRuntime):
    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.registry = registry or build_tool_registry()
        self.policy = PolicyEngine(self.registry)
        self.llm = llm_client or MockLLMClient()

    def _trace_tool(
        self,
        session: Session,
        *,
        customer_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        signal_id: str | None = None,
    ) -> BaseModel:
        started = perf_counter()
        try:
            output = self.registry.execute(session, tool_name, arguments)
        except Exception as error:
            elapsed = round((perf_counter() - started) * 1000)
            session.add(
                AgentActionLog(
                    action_id=f"T-{uuid4().hex[:16].upper()}",
                    customer_id=customer_id,
                    signal_id=signal_id,
                    action_type="TOOL_CALL",
                    tool_name=tool_name,
                    tool_input=arguments,
                    policy_result=_json(self.policy.evaluate(tool_name)),
                    confirmation_required=False,
                    confirmation_status="NOT_REQUIRED",
                    tool_output={"error": str(error)},
                    action_status="FAILED",
                    latency_ms=elapsed,
                )
            )
            session.commit()
            raise
        elapsed = round((perf_counter() - started) * 1000)
        session.add(
            AgentActionLog(
                action_id=f"T-{uuid4().hex[:16].upper()}",
                customer_id=customer_id,
                signal_id=signal_id,
                action_type="TOOL_CALL",
                tool_name=tool_name,
                tool_input=arguments,
                policy_result=_json(self.policy.evaluate(tool_name)),
                confirmation_required=False,
                confirmation_status="NOT_REQUIRED",
                tool_output=_json(output),
                action_status="SUCCESS",
                latency_ms=elapsed,
            )
        )
        session.commit()
        return output

    def _upsert_signal(
        self,
        session: Session,
        *,
        customer_id: str,
        signal_type: SignalType,
        severity: str,
        data: dict[str, Any],
    ) -> RadarSignal:
        signal = session.scalars(
            select(RadarSignal)
            .where(
                RadarSignal.customer_id == customer_id,
                RadarSignal.signal_type == signal_type,
                RadarSignal.status.in_([SignalStatus.NEW, SignalStatus.SHOWN, SignalStatus.ACTION_PROPOSED]),
            )
            .order_by(RadarSignal.created_at.desc())
        ).first()
        if signal is None:
            signal = RadarSignal(
                signal_id=f"S-{uuid4().hex[:16].upper()}",
                customer_id=customer_id,
                signal_type=signal_type,
                severity=severity,
                signal_data=data,
                status=SignalStatus.NEW,
                created_at=datetime.utcnow(),
            )
            session.add(signal)
        else:
            signal.severity = severity
            signal.signal_data = data
        session.commit()
        return signal

    def _recommendation_candidate(
        self,
        session: Session,
        *,
        customer_id: str,
        as_of: date,
        primary_type: SignalType,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        if primary_type == SignalType.CASHFLOW_RISK:
            guardrail = calculate_budget_guardrail(session, customer_id, Category.SHOPPING)
            return {
                "problem": "Dòng tiền dự kiến xuống dưới mức an toàn",
                "severity": analysis["risk_level"],
                "summary": (
                    f"Số dư dự báo là {_vnd(analysis['forecast_balance'])} VND, thấp hơn "
                    f"mức an toàn {_vnd(analysis['safe_balance'])} VND."
                ),
                "evidence": [
                    {
                        "source": "forecast_cashflow",
                        "metric": "forecast_balance",
                        "value": analysis["forecast_balance"],
                        "context": {"gap": analysis["gap"], "confidence": analysis["confidence"]},
                    },
                    *[
                        {
                            "source": "forecast_cashflow",
                            "metric": driver["type"],
                            "value": driver["impact"],
                            "context": driver["evidence"],
                        }
                        for driver in analysis["drivers"]
                    ],
                ],
                "options": [
                    {
                        "option_id": "A",
                        "title": "Tạo ngân sách mua sắm",
                        "description": "Đặt giới hạn SHOPPING và cảnh báo ở mức 80%.",
                        "action_type": "create_budget",
                        "parameters": {
                            "customer_id": customer_id,
                            "category": "SHOPPING",
                            "amount": str(guardrail.recommended_amount),
                            "alert_threshold": "0.8",
                            "start_date": as_of.isoformat(),
                            "end_date": as_of.replace(day=28).isoformat(),
                        },
                        "expected_impact": "Giảm tốc độ chi tiêu tùy ý trong tháng.",
                    },
                    {
                        "option_id": "B",
                        "title": "Tạo nhắc nhở trước khoản định kỳ",
                        "description": "Nhắc kiểm tra số dư trước ngày đến hạn.",
                        "action_type": "create_reminder",
                        "parameters": {
                            "customer_id": customer_id,
                            "title": "Kiểm tra số dư trước khoản định kỳ",
                            "remind_at": datetime.combine(as_of, time(9)).isoformat(),
                            "message": "Kiểm tra số dư và chi tiêu tùy ý trước khoản định kỳ sắp tới.",
                        },
                        "expected_impact": "Giúp chủ động điều chỉnh trước ngày thanh toán.",
                    },
                ],
                "recommended_option_id": "A",
                "reasoning_summary": "Option A trực tiếp xử lý driver chi tiêu tùy ý và tuân thủ policy confirmation.",
            }
        if primary_type == SignalType.SPENDING_ANOMALY:
            anomaly = analysis["anomalies"][0]
            guardrail = calculate_budget_guardrail(session, customer_id, anomaly["category"])
            return {
                "problem": "Chi tiêu theo danh mục tăng bất thường",
                "severity": "MEDIUM",
                "summary": f"Chi tiêu {anomaly['category']} tăng {DecimalString.percent(anomaly['change_pct'])} so với baseline.",
                "evidence": [{"source": "detect_spending_anomaly", "metric": "change_pct", "value": anomaly["change_pct"], "context": anomaly}],
                "options": [{
                    "option_id": "A", "title": "Tạo ngân sách danh mục", "description": "Áp dụng guardrail theo thu nhập.",
                    "action_type": "create_budget",
                    "parameters": {"customer_id": customer_id, "category": anomaly["category"], "amount": str(guardrail.recommended_amount), "alert_threshold": "0.8", "start_date": as_of.isoformat(), "end_date": as_of.replace(day=28).isoformat()},
                    "expected_impact": "Hạn chế chi vượt baseline trong phần còn lại của tháng."
                }],
                "recommended_option_id": "A", "reasoning_summary": "Guardrail được Financial Engine suy ra từ thu nhập, không do LLM tính."
            }
        if primary_type == SignalType.GOAL_DRIFT:
            scenarios = analysis["scenarios"]
            options = []
            for index, scenario in enumerate(scenarios):
                parameters = {"customer_id": customer_id, "goal_id": analysis["goal_id"]}
                if scenario["action_type"] == "INCREASE_CONTRIBUTION":
                    parameters["monthly_contribution"] = scenario["monthly_contribution"]
                else:
                    parameters["target_date"] = scenario["target_date"]
                options.append({
                    "option_id": chr(ord("A") + index),
                    "title": "Tăng đóng góp" if index == 0 else "Gia hạn mục tiêu",
                    "description": "Áp dụng kịch bản deterministic từ Financial Engine.",
                    "action_type": "update_goal", "parameters": parameters,
                    "expected_impact": "Đưa lộ trình mục tiêu về trạng thái khả thi."
                })
            return {
                "problem": "Mục tiêu tiết kiệm đang chậm tiến độ", "severity": "MEDIUM",
                "summary": f"Tiến độ thực tế thấp hơn kỳ vọng {_vnd(abs(int(analysis['gap_analysis']['gap'])))} VND.",
                "evidence": [{"source": "simulate_goal_scenarios", "metric": "goal_gap", "value": analysis["gap_analysis"]["gap"], "context": analysis["gap_analysis"]}],
                "options": options, "recommended_option_id": "A",
                "reasoning_summary": "Kịch bản tăng đóng góp giữ nguyên deadline hiện tại."
            }
        event = analysis["events"][0]
        return {
            "problem": "Khoản thanh toán định kỳ sắp đến", "severity": "MEDIUM",
            "summary": f"{event['name']} trị giá {_vnd(event['expected_amount'])} VND sẽ đến hạn sau {event['days_until']} ngày.",
            "evidence": [{"source": "detect_upcoming_recurring", "metric": "expected_amount", "value": event["expected_amount"], "context": event}],
            "options": [{
                "option_id": "A", "title": "Tạo nhắc nhở", "description": "Nhắc kiểm tra số dư trước hạn.",
                "action_type": "create_reminder",
                "parameters": {"customer_id": customer_id, "title": f"Chuẩn bị {event['name']}", "remind_at": datetime.combine(as_of, time(9)).isoformat(), "message": f"Khoản {event['name']} sắp đến hạn."},
                "expected_impact": "Giảm nguy cơ bỏ lỡ khoản định kỳ."
            }],
            "recommended_option_id": "A", "reasoning_summary": "Nhắc nhở là hành động low-risk phù hợp evidence."
        }

    def _prepare_or_execute(
        self,
        session: Session,
        state: RadarState,
        selected_option_id: str,
    ) -> RadarState:
        if state.recommendation is None:
            raise ValueError("Recommendation is required before action preparation")
        option = next(
            (item for item in state.recommendation.options if item.option_id == selected_option_id),
            None,
        )
        if option is None:
            raise ValueError(f"Unknown recommendation option: {selected_option_id}")
        validated = self.registry.validate_input(option.action_type, option.parameters)
        state.selected_action = selected_option_id
        state.action_draft = ActionDraft(tool=option.action_type, arguments=validated.model_dump(mode="json"))
        state.transition(AgentLifecycle.ACTION_PREPARED)
        decision = self.policy.evaluate(option.action_type)
        state.policy_result = decision
        if not decision.allowed:
            state.error = decision.reason
            state.transition(AgentLifecycle.FAILED)
            return state
        action_id = f"A-{uuid4().hex[:16].upper()}"
        state.action_id = action_id
        signal_id = state.signals[0]["signal_id"] if state.signals else None
        log = AgentActionLog(
            action_id=action_id,
            customer_id=state.customer_id,
            signal_id=signal_id,
            action_type=option.action_type,
            tool_name=option.action_type,
            tool_input=state.action_draft.arguments,
            policy_result=_json(decision),
            confirmation_required=decision.confirmation_required,
            confirmation_status="PENDING" if decision.confirmation_required else "NOT_REQUIRED",
            tool_output=None,
            action_status="PREPARED",
            latency_ms=None,
        )
        session.add(log)
        if signal_id:
            signal = session.get(RadarSignal, signal_id)
            if signal:
                signal.status = SignalStatus.ACTION_PROPOSED
        session.commit()
        if decision.confirmation_required:
            state.confirmation_status = "PENDING"
            state.transition(AgentLifecycle.WAITING_CONFIRMATION)
            return state
        return self._execute_prepared(session, state, log)

    def _execute_prepared(
        self, session: Session, state: RadarState, log: AgentActionLog
    ) -> RadarState:
        state.transition(AgentLifecycle.EXECUTING)
        started = perf_counter()
        try:
            output = self.registry.execute(session, log.tool_name, log.tool_input)
        except Exception as error:
            log.action_status = "FAILED"
            log.tool_output = {"error": str(error)}
            log.latency_ms = round((perf_counter() - started) * 1000)
            state.error = str(error)
            state.transition(AgentLifecycle.FAILED)
            session.commit()
            return state
        log.action_status = "SUCCESS"
        log.tool_output = _json(output)
        log.latency_ms = round((perf_counter() - started) * 1000)
        state.execution_result = log.tool_output
        state.transition(AgentLifecycle.EXECUTED)
        if log.signal_id:
            signal = session.get(RadarSignal, log.signal_id)
            if signal:
                signal.status = SignalStatus.ACTIONED
        session.commit()
        return state

    def run(
        self,
        session: Session,
        *,
        customer_id: str,
        message: str,
        as_of: object,
        selected_option_id: str | None = None,
    ) -> RadarState:
        if not isinstance(as_of, date):
            raise TypeError("as_of must be a date")
        state = RadarState(customer_id=customer_id, user_message=message)
        snapshot = self._trace_tool(
            session, customer_id=customer_id, tool_name="get_financial_snapshot",
            arguments={"customer_id": customer_id}
        )
        state.snapshot = _json(snapshot)
        state.transition(AgentLifecycle.CONTEXT_READY)

        forecast = self._trace_tool(
            session, customer_id=customer_id, tool_name="forecast_cashflow",
            arguments={"customer_id": customer_id, "as_of": as_of.isoformat(), "forecast_until": (as_of + timedelta(days=14)).isoformat()}
        )
        anomaly = self._trace_tool(
            session, customer_id=customer_id, tool_name="detect_spending_anomaly",
            arguments={"customer_id": customer_id, "as_of": as_of.isoformat()}
        )
        recurring = self._trace_tool(
            session, customer_id=customer_id, tool_name="detect_upcoming_recurring",
            arguments={"customer_id": customer_id, "as_of": as_of.isoformat(), "window_days": 14}
        )

        primary_type: SignalType | None = None
        analysis: dict[str, Any]
        if forecast.risk_level == "HIGH":
            primary_type = SignalType.CASHFLOW_RISK
            analysis = _json(forecast)
            severity = "HIGH"
        elif anomaly.anomalies:
            primary_type = SignalType.SPENDING_ANOMALY
            analysis = _json(anomaly)
            severity = "MEDIUM"
        else:
            try:
                goal = self._trace_tool(
                    session, customer_id=customer_id, tool_name="simulate_goal_scenarios",
                    arguments={"customer_id": customer_id, "as_of": as_of.isoformat()}
                )
            except ValueError:
                goal = None
            if goal and goal.gap_analysis.is_drifting:
                primary_type = SignalType.GOAL_DRIFT
                analysis = _json(goal)
                severity = "MEDIUM"
            elif recurring.events:
                primary_type = SignalType.UPCOMING_RECURRING
                analysis = _json(recurring)
                severity = "MEDIUM"
            else:
                state.financial_analysis = _json(forecast)
                state.transition(AgentLifecycle.RECOMMENDATION_READY)
                return state

        signal = self._upsert_signal(
            session, customer_id=customer_id, signal_type=primary_type,
            severity=severity, data=analysis
        )
        state.signals = [{
            "signal_id": signal.signal_id, "signal_type": signal.signal_type.value,
            "severity": signal.severity, "status": signal.status.value,
            "signal_data": signal.signal_data,
        }]
        state.trigger_type = primary_type.value
        state.transition(AgentLifecycle.SIGNAL_DETECTED)
        state.financial_analysis = analysis
        state.transition(AgentLifecycle.ANALYSIS_READY)
        candidate = self._recommendation_candidate(
            session, customer_id=customer_id, as_of=as_of,
            primary_type=primary_type, analysis=analysis
        )
        state.recommendation = self.llm.generate_structured(
            system_prompt=FINANCIAL_RADAR_SYSTEM_PROMPT,
            user_prompt=message,
            response_model=RecommendationResult,
            context={"grounded_candidate": candidate, "financial_analysis": analysis},
        )
        signal.status = SignalStatus.SHOWN
        session.commit()
        state.transition(AgentLifecycle.RECOMMENDATION_READY)
        if selected_option_id:
            return self._prepare_or_execute(session, state, selected_option_id)
        return state

    def confirm(self, session: Session, *, action_id: str, confirmed: bool) -> RadarState:
        log = session.get(AgentActionLog, action_id)
        if log is None or log.action_type == "TOOL_CALL":
            raise ValueError(f"Unknown action_id: {action_id}")
        state = RadarState(
            customer_id=log.customer_id,
            state=AgentLifecycle.WAITING_CONFIRMATION,
            action_id=log.action_id,
            action_draft=ActionDraft(tool=log.tool_name, arguments=log.tool_input),
            policy_result=self.policy.evaluate(log.tool_name),
            confirmation_status=log.confirmation_status,
        )
        if log.action_status != "PREPARED" or log.confirmation_status != "PENDING":
            raise ValueError("Action is not awaiting confirmation")
        if not confirmed:
            log.confirmation_status = "DECLINED"
            log.action_status = "CANCELLED"
            state.confirmation_status = "DECLINED"
            state.error = "Customer declined the prepared action."
            state.transition(AgentLifecycle.FAILED)
            session.commit()
            return state
        log.confirmation_status = "CONFIRMED"
        state.confirmation_status = "CONFIRMED"
        session.commit()
        return self._execute_prepared(session, state, log)

    def prepare_action(
        self,
        session: Session,
        *,
        customer_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> RadarState:
        """Prepare a direct API action through the same policy/state path."""
        validated = self.registry.validate_input(tool_name, arguments)
        state = RadarState(customer_id=customer_id, user_message="Direct action request")
        state.transition(AgentLifecycle.CONTEXT_READY)
        state.recommendation = RecommendationResult.model_validate(
            {
                "problem": "Direct customer action request",
                "severity": self.registry.get(tool_name).risk_level.value,
                "summary": "Action validated and sent through policy enforcement.",
                "evidence": [
                    {
                        "source": "customer_request",
                        "metric": "validated_input",
                        "value": True,
                    }
                ],
                "options": [
                    {
                        "option_id": "DIRECT",
                        "title": tool_name,
                        "description": "Validated direct action request.",
                        "action_type": tool_name,
                        "parameters": validated.model_dump(mode="json"),
                        "expected_impact": "Apply the explicitly requested business action.",
                    }
                ],
                "recommended_option_id": "DIRECT",
                "reasoning_summary": "No LLM decision; initiated explicitly by the customer.",
            }
        )
        state.transition(AgentLifecycle.RECOMMENDATION_READY)
        return self._prepare_or_execute(session, state, "DIRECT")


class DecimalString:
    @staticmethod
    def percent(value: str | int | float) -> str:
        from decimal import Decimal

        return f"{Decimal(str(value)) * 100:.0f}%"


def _vnd(value: object) -> str:
    from decimal import Decimal

    return f"{int(Decimal(str(value))):,}"


from datetime import timedelta  # kept after class declarations for compact imports
