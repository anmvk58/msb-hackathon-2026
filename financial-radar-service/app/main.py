from datetime import date, datetime
from contextlib import asynccontextmanager
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
from app.models import AgentActionLog, RadarSignal, ScanTrigger
from app.scan_schemas import RadarScanRead
from app.scan_service import get_latest_completed_scan, run_and_record_scan
from app.schemas import AgentActionLogRead, RadarSignalRead
from app.tools import build_tool_registry
from app.tools.contracts import ToolExecutionError
from app.tools.schemas import (
    CashflowInput,
    CashflowOutput,
    CreateBudgetInput,
    CreateReminderInput,
    FinancialSnapshotInput,
    FinancialSnapshotOutput,
    GoalSimulationInput,
    GoalSimulationOutput,
    RecurringInput,
    RecurringOutput,
    SpendingAnomalyInput,
    SpendingAnomalyOutput,
    UpdateGoalInput,
)


API_DESCRIPTION = """
MSB Financial Sensing là API demo cho quy trình **phát hiện → khuyến nghị → lựa chọn
→ xác nhận → thực thi → audit**.

### Cách thử nhanh
1. Gọi `POST /api/agent/run` với `customer_id=C001`.
2. Lấy `recommendation_id` và một `option_id` từ response để gọi
   `POST /api/agent/select`.
3. Nếu response trả `WAITING_CONFIRMATION`, lấy `action_id` gọi
   `POST /api/agent/confirm` với `confirmed=true`.
4. Tra cứu kết quả bằng `GET /api/agent/actions/{action_id}`.

### Phạm vi demo
Agent lấy toàn bộ customer context và áp dụng action qua Mock Core Banking HTTP
API. Database của Agent chỉ lưu signal, recommendation và action audit. Mock Core
Banking vẫn là hệ thống giả lập, **không phải Core Banking MSB thật**.
"""

OPENAPI_TAGS = [
    {"name": "System", "description": "Khám phá API và kiểm tra tình trạng runtime."},
    {"name": "Agent workflow", "description": "Luồng nghiệp vụ chính của Financial Sensing."},
    {"name": "Customer insights", "description": "Dữ liệu tổng hợp và tín hiệu theo khách hàng."},
    {"name": "Financial tools", "description": "Các phép tính deterministic, không thay đổi dữ liệu."},
    {"name": "Demo actions", "description": "Chuẩn bị hành động áp dụng qua Mock Core Banking; không tác động hệ thống MSB thật."},
    {"name": "Audit", "description": "Tra cứu dấu vết và kết quả thực thi hành động."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_schema()
    yield


app = FastAPI(
    title="MSB Financial Sensing",
    version="0.1.0",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
registry = build_tool_registry()
settings = get_settings()
runtime = build_agent_runtime(settings=settings, registry=registry)
BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def business_today() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()
DbSession = Annotated[Session, Depends(get_db)]


@app.get(
    "/",
    tags=["System"],
    summary="Thông tin và đường dẫn sử dụng API",
    description="Landing response dành cho người mở endpoint gốc trên trình duyệt.",
)
def api_home() -> dict[str, str]:
    return {
        "name": "MSB Financial Sensing",
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "scope": "Demo API; customer data and actions are served by Mock Core Banking",
    }


@app.get(
    "/health",
    tags=["System"],
    summary="Kiểm tra sức khỏe runtime",
    description="Trả về runtime adapter và LLM provider đang được sử dụng.",
)
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


@app.get(
    "/api/customers/{customer_id}/snapshot",
    response_model=FinancialSnapshotOutput,
    tags=["Customer insights"],
    summary="Lấy ảnh chụp tài chính khách hàng",
    description="Tổng hợp thu nhập, số dư an toàn, tài khoản, mục tiêu và ngân sách đang hoạt động. Dùng `C001` để thử dữ liệu demo.",
)
def customer_snapshot(customer_id: str, session: DbSession) -> dict:
    return _execute_tool(session, "get_financial_snapshot", FinancialSnapshotInput(customer_id=customer_id))


@app.get(
    "/api/customers/{customer_id}/radar",
    response_model=AgentResponse,
    tags=["Agent workflow"],
    summary="Chủ động quét Financial Sensing",
    description="Chạy toàn bộ phân tích và sinh khuyến nghị cho khách hàng mà không cần message đầu vào.",
)
def customer_radar(customer_id: str, session: DbSession, as_of: date | None = None) -> AgentResponse:
    try:
        return run_and_record_scan(
            session,
            runtime,
            customer_id=customer_id,
            message="Chủ động quét Financial Sensing",
            trigger_type=ScanTrigger.MANUAL,
            as_of=as_of or business_today(),
        )
    except LLMAuthenticationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except LLMTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except (LLMStructuredOutputError, LLMRequestError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get(
    "/api/customers/{customer_id}/radar/latest",
    response_model=RadarScanRead,
    tags=["Customer insights"],
    summary="Lấy kết quả Financial Sensing gần nhất",
    description="Trả kết quả quét hoàn tất gần nhất từ database, không gọi LLM.",
)
def latest_customer_radar(customer_id: str, session: DbSession) -> RadarScanRead:
    latest = get_latest_completed_scan(session, customer_id)
    if latest is None:
        raise HTTPException(status_code=404, detail="Customer has no completed radar scan")
    return latest


@app.post("/api/tools/forecast-cashflow", response_model=CashflowOutput, tags=["Financial tools"], summary="Dự báo dòng tiền", description="Dự báo số dư đến một ngày tương lai dựa trên dữ liệu giao dịch và khoản định kỳ.")
def api_forecast(payload: CashflowInput, session: DbSession) -> dict:
    return _execute_tool(session, "forecast_cashflow", payload)


@app.post("/api/tools/detect-spending-anomaly", response_model=SpendingAnomalyOutput, tags=["Financial tools"], summary="Phát hiện chi tiêu bất thường", description="So sánh chi tiêu theo danh mục với lịch sử và ngân sách tại ngày phân tích.")
def api_spending(payload: SpendingAnomalyInput, session: DbSession) -> dict:
    return _execute_tool(session, "detect_spending_anomaly", payload)


@app.post("/api/tools/detect-recurring", response_model=RecurringOutput, tags=["Financial tools"], summary="Phát hiện khoản định kỳ sắp tới", description="Tìm các khoản thu/chi định kỳ trong cửa sổ thời gian được yêu cầu.")
def api_recurring(payload: RecurringInput, session: DbSession) -> dict:
    return _execute_tool(session, "detect_upcoming_recurring", payload)


@app.post("/api/tools/simulate-goal", response_model=GoalSimulationOutput, tags=["Financial tools"], summary="Mô phỏng mục tiêu tiết kiệm", description="Đánh giá độ lệch mục tiêu và đề xuất kịch bản tăng đóng góp hoặc gia hạn.")
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


@app.post("/api/actions/create-budget", response_model=AgentResponse, tags=["Demo actions"], summary="Chuẩn bị tạo ngân sách demo", description="Tạo action chờ xác nhận. Sau khi xác nhận, Agent gọi Mock Core Banking để ngân sách xuất hiện trong Mobile Banking demo.")
def api_create_budget(payload: CreateBudgetInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "create_budget", payload)


@app.post("/api/actions/create-reminder", response_model=AgentResponse, tags=["Demo actions"], summary="Chuẩn bị tạo nhắc nhở demo", description="Tạo reminder qua Mock Core Banking; hiện chưa gửi push notification, SMS hoặc email thật.")
def api_create_reminder(payload: CreateReminderInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "create_reminder", payload)


@app.post("/api/actions/update-goal", response_model=AgentResponse, tags=["Demo actions"], summary="Chuẩn bị cập nhật mục tiêu demo", description="Sau xác nhận sẽ cập nhật mục tiêu qua Mock Core Banking; chưa kết nối Core Banking MSB thật.")
def api_update_goal(payload: UpdateGoalInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "update_goal", payload)


@app.post("/api/agent/run", response_model=AgentResponse, tags=["Agent workflow"], summary="Chạy Agent Financial Sensing", description="Điểm vào chính: phân tích khách hàng, gọi LLM để diễn giải và trả về các lựa chọn khuyến nghị. Dùng `C001` cho demo.")
def agent_run(payload: AgentRunRequest, session: DbSession) -> AgentResponse:
    try:
        return run_and_record_scan(
            session,
            runtime,
            customer_id=payload.customer_id,
            message=payload.message,
            trigger_type=ScanTrigger.MANUAL,
            as_of=payload.as_of or business_today(),
        )
    except LLMAuthenticationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except LLMTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except (LLMStructuredOutputError, LLMRequestError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/agent/select", response_model=AgentResponse, tags=["Agent workflow"], summary="Chọn một phương án khuyến nghị", description="Dùng `recommendation_id` và `option_id` từ bước run. Agent tạo action draft và áp dụng policy xác nhận.")
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


@app.post("/api/agent/confirm", response_model=AgentResponse, tags=["Agent workflow"], summary="Xác nhận hoặc từ chối hành động", description="Dùng `action_id` từ bước select. `confirmed=true` cho phép tool gọi Mock Core Banking với idempotency key; `false` hủy hành động.")
def agent_confirm(payload: AgentConfirmRequest, session: DbSession) -> AgentResponse:
    try:
        return response_from_state(
            runtime.confirm(
                session, action_id=payload.action_id, confirmed=payload.confirmed
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/agent/actions/{action_id}", response_model=AgentActionLogRead, tags=["Audit"], summary="Tra cứu audit log của hành động", description="Trả về input, policy, trạng thái xác nhận, output và liên kết signal/recommendation của action.")
def get_action(action_id: str, session: DbSession) -> AgentActionLog:
    action = session.get(AgentActionLog, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@app.get("/api/customers/{customer_id}/signals", response_model=list[RadarSignalRead], tags=["Customer insights"], summary="Liệt kê tín hiệu Financial Sensing", description="Trả về các tín hiệu đã phát hiện của khách hàng, mới nhất trước.")
def get_signals(customer_id: str, session: DbSession) -> list[RadarSignal]:
    registry.gateway.get_financial_context(customer_id)
    return list(
        session.scalars(
            select(RadarSignal)
            .where(RadarSignal.customer_id == customer_id)
            .order_by(RadarSignal.created_at.desc())
        ).all()
    )
    FinancialSnapshotOutput,
    GoalSimulationOutput,
    RecurringOutput,
    SpendingAnomalyOutput,
