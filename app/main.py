from datetime import date
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.factory import build_agent_runtime
from app.agent.schemas import (
    AgentConfirmRequest,
    AgentResponse,
    AgentRunRequest,
    AgentSelectRequest,
    response_from_state,
)
from app.config import get_settings
from app.database import create_schema, get_db
from app.llm import (
    LLMAuthenticationError,
    LLMRequestError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)
from app.models import AgentActionLog, Customer, RadarSignal
from app.schemas import AgentActionLogRead, RadarSignalRead
from app.tools import build_tool_registry
from app.tools.contracts import ToolExecutionError
from app.tools.schemas import (
    CashflowInput,
    CreateBudgetInput,
    CreateReminderInput,
    FinancialSnapshotInput,
    GoalSimulationInput,
    RecurringInput,
    SpendingAnomalyInput,
    UpdateGoalInput,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="MSB Financial Radar",
    version="0.1.0",
    description="Proactive financial AI agent with deterministic financial evidence.",
    lifespan=lifespan,
)
registry = build_tool_registry()
settings = get_settings()
runtime = build_agent_runtime(settings=settings, registry=registry)
DbSession = Annotated[Session, Depends(get_db)]


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "runtime": type(runtime).__name__,
        "llm_provider": (
            settings.llm_provider
            if settings.agent_runtime == "greennode"
            else "mock"
        ),
    }


def _execute_tool(session: Session, tool_name: str, payload: BaseModel) -> dict:
    try:
        result = runtime.trace_tool(
            session,
            customer_id=payload.customer_id,
            tool_name=tool_name,
            arguments=payload.model_dump(mode="json"),
        )
        return result.model_dump(mode="json")
    except (ValueError, ToolExecutionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/customers/{customer_id}/snapshot")
def customer_snapshot(customer_id: str, session: DbSession) -> dict:
    return _execute_tool(session, "get_financial_snapshot", FinancialSnapshotInput(customer_id=customer_id))


@app.get("/api/customers/{customer_id}/radar", response_model=AgentResponse)
def customer_radar(customer_id: str, session: DbSession, as_of: date | None = None) -> AgentResponse:
    try:
        state = runtime.run(
            session,
            customer_id=customer_id,
            message="Chủ động quét Financial Radar",
            as_of=as_of or date.today(),
        )
        return response_from_state(state)
    except LLMAuthenticationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except LLMTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except (LLMStructuredOutputError, LLMRequestError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/tools/forecast-cashflow")
def api_forecast(payload: CashflowInput, session: DbSession) -> dict:
    return _execute_tool(session, "forecast_cashflow", payload)


@app.post("/api/tools/detect-spending-anomaly")
def api_spending(payload: SpendingAnomalyInput, session: DbSession) -> dict:
    return _execute_tool(session, "detect_spending_anomaly", payload)


@app.post("/api/tools/detect-recurring")
def api_recurring(payload: RecurringInput, session: DbSession) -> dict:
    return _execute_tool(session, "detect_upcoming_recurring", payload)


@app.post("/api/tools/simulate-goal")
def api_goal(payload: GoalSimulationInput, session: DbSession) -> dict:
    return _execute_tool(session, "simulate_goal_scenarios", payload)


def _prepare_direct_action(
    session: Session, tool_name: str, payload: BaseModel
) -> AgentResponse:
    try:
        state = runtime.prepare_action(
            session,
            customer_id=payload.customer_id,
            tool_name=tool_name,
            arguments=payload.model_dump(mode="json"),
        )
        return response_from_state(state)
    except (ValueError, ToolExecutionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/actions/create-budget", response_model=AgentResponse)
def api_create_budget(payload: CreateBudgetInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "create_budget", payload)


@app.post("/api/actions/create-reminder", response_model=AgentResponse)
def api_create_reminder(payload: CreateReminderInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "create_reminder", payload)


@app.post("/api/actions/update-goal", response_model=AgentResponse)
def api_update_goal(payload: UpdateGoalInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "update_goal", payload)


@app.post("/api/agent/run", response_model=AgentResponse)
def agent_run(payload: AgentRunRequest, session: DbSession) -> AgentResponse:
    try:
        state = runtime.run(
            session,
            customer_id=payload.customer_id,
            message=payload.message,
            as_of=payload.as_of or date.today(),
        )
        return response_from_state(state)
    except LLMAuthenticationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except LLMTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except (LLMStructuredOutputError, LLMRequestError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/agent/select", response_model=AgentResponse)
def agent_select(payload: AgentSelectRequest, session: DbSession) -> AgentResponse:
    try:
        return response_from_state(
            runtime.select(
                session,
                recommendation_id=payload.recommendation_id,
                option_id=payload.option_id,
            )
        )
    except ValueError as error:
        message = str(error)
        if "expired" in message or "no longer active" in message:
            status_code = 409
        elif "Unknown recommendation_id" in message:
            status_code = 404
        else:
            status_code = 422
        raise HTTPException(status_code=status_code, detail=message) from error


@app.post("/api/agent/confirm", response_model=AgentResponse)
def agent_confirm(payload: AgentConfirmRequest, session: DbSession) -> AgentResponse:
    try:
        return response_from_state(
            runtime.confirm(
                session, action_id=payload.action_id, confirmed=payload.confirmed
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/agent/actions/{action_id}", response_model=AgentActionLogRead)
def get_action(action_id: str, session: DbSession) -> AgentActionLog:
    action = session.get(AgentActionLog, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@app.get("/api/customers/{customer_id}/signals", response_model=list[RadarSignalRead])
def get_signals(customer_id: str, session: DbSession) -> list[RadarSignal]:
    if session.get(Customer, customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return list(
        session.scalars(
            select(RadarSignal)
            .where(RadarSignal.customer_id == customer_id)
            .order_by(RadarSignal.created_at.desc())
        ).all()
    )
