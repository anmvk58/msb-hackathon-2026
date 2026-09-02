from datetime import date, datetime, timedelta
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.candidates import CandidateActionGenerator
from app.agent.runtime import AgentRuntime
from app.agent.state import (
    ActionDraft,
    AgentLifecycle,
    LLMRecommendationDecision,
    RadarState,
    RecommendationResult,
    assemble_recommendation,
)
from app.llm import LLMClient, MockLLMClient
from app.llm.prompts import FINANCIAL_RADAR_SYSTEM_PROMPT
from app.models import AgentActionLog, RadarSignal, SignalStatus, SignalType
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
        self.candidate_generator = CandidateActionGenerator()

    def trace_tool(
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
        snapshot = self.trace_tool(
            session, customer_id=customer_id, tool_name="get_financial_snapshot",
            arguments={"customer_id": customer_id}
        )
        state.snapshot = _json(snapshot)
        state.transition(AgentLifecycle.CONTEXT_READY)

        forecast = self.trace_tool(
            session, customer_id=customer_id, tool_name="forecast_cashflow",
            arguments={"customer_id": customer_id, "as_of": as_of.isoformat(), "forecast_until": (as_of + timedelta(days=14)).isoformat()}
        )
        anomaly = self.trace_tool(
            session, customer_id=customer_id, tool_name="detect_spending_anomaly",
            arguments={"customer_id": customer_id, "as_of": as_of.isoformat()}
        )
        recurring = self.trace_tool(
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
                goal = self.trace_tool(
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
        candidate = self.candidate_generator.generate(
            session, customer_id=customer_id, as_of=as_of,
            primary_type=primary_type, analysis=analysis
        )
        decision = self.llm.generate_structured(
            system_prompt=FINANCIAL_RADAR_SYSTEM_PROMPT,
            user_prompt=message,
            response_model=LLMRecommendationDecision,
            context={
                "candidate_plan": candidate.model_dump(mode="json"),
                "financial_analysis": analysis,
            },
        )
        state.recommendation = assemble_recommendation(candidate, decision)
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
