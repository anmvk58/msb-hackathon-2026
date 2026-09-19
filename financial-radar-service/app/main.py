import json
from pathlib import Path
from datetime import date, datetime
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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
from app.database import SessionLocal, create_schema, get_db
from app.llm import (
    LLMAuthenticationError,
    LLMRequestError,
    LLMStructuredOutputError,
    LLMTimeoutError,
)
from app.models import AgentActionLog, RadarSignal, ScanTrigger
from app.scan_schemas import RadarScanRead
from app.scan_service import (
    create_pending_scan,
    execute_pending_scan,
    get_latest_completed_scan,
    get_scan,
    run_and_record_scan,
)
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
    ActivateMSinhLoiInput,
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
M_SINH_LOI_KNOWLEDGE = (Path(__file__).parent / "knowledge" / "m_sinh_loi.md").read_text(encoding="utf-8")


def business_today() -> date:
    return datetime.now(BUSINESS_TIMEZONE).date()
DbSession = Annotated[Session, Depends(get_db)]


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=2000)


class FinancialChatRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=10)


class FinancialChatResponse(BaseModel):
    reply: str
    action_offer: str | None = None


class ChatIntentDecision(BaseModel):
    intent: Literal["EXPLORE_FLEXIBLE", "ACCEPT_M_SINH_LOI", "OTHER"]
    reply: str = Field(min_length=1, max_length=2000)


M_SINH_LOI_CHAT_PROMPT = (
    "Bạn là FinSen, trợ lý tài chính trong ứng dụng demo. Đọc toàn bộ hội thoại nhưng "
    "phân loại ý định từ lời NHẮN MỚI NHẤT của khách hàng. "
    "EXPLORE_FLEXIBLE: khách nói có thể cần dùng tiền, muốn rút linh hoạt hoặc hỏi giải pháp "
    "sinh lời linh hoạt, nhưng CHƯA đồng ý kích hoạt sản phẩm. "
    "ACCEPT_M_SINH_LOI: khách thể hiện rõ muốn sử dụng hoặc thiết lập M-Sinh lời; "
    "lời đồng ý ngắn chỉ đủ nghĩa khi hội thoại ngay trước đó đã giới thiệu M-Sinh lời. "
    "OTHER: khách từ chối, hỏi chuyện khác, hoặc ý định chưa rõ. "
    "Không suy ra sự đồng ý chỉ từ việc khách quan tâm sản phẩm. "
    "Viết reply tự nhiên, ngắn gọn bằng tiếng Việt. Khi nói về M-Sinh lời, phải nêu đây "
    "là khoản cho SBSI vay, không phải tiền gửi tiết kiệm MSB. Không hứa lợi tức hay "
    "khẳng định đã kích hoạt. Sau khi khách đồng ý, hướng dẫn chọn Action và xác nhận.\n\n"
    + M_SINH_LOI_KNOWLEDGE
)


def _run_scan_background(scan_id: str) -> None:
    with SessionLocal() as session:
        try:
            execute_pending_scan(session, runtime, scan_id)
        except Exception:
            # execute_pending_scan persists FAILED and the error for polling clients.
            return


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
        "llm_provider": settings.llm_provider,
    }


@app.post("/api/chat", response_model=FinancialChatResponse, tags=["Agent workflow"], summary="Trò chuyện với trợ lý Financial Sensing")
def financial_chat(payload: FinancialChatRequest, session: DbSession) -> FinancialChatResponse:
    try:
        context = registry.gateway.get_financial_context(payload.customer_id)
        latest = get_latest_completed_scan(session, payload.customer_id)
        idle_cash_case = bool(latest and latest.result and (latest.result.analysis or {}).get("risk_flags", {}).get("idle_cash") and context.m_sinh_loi is None)
        if idle_cash_case:
            decision = runtime.llm.generate_structured(
                system_prompt=M_SINH_LOI_CHAT_PROMPT,
                user_prompt="Phân loại ý định của lời nhắn mới nhất và trả lời khách hàng.",
                response_model=ChatIntentDecision,
                context={
                    "history": [item.model_dump() for item in payload.history],
                    "latest_user_message": payload.message,
                    "current_payment_balance": str(next((item.available_balance for item in context.accounts if item.account_type == "PAYMENT"), 0)),
                    "safe_balance": str(context.customer.preferred_safe_balance),
                    "latest_recommendations": [item.model_dump(mode="json") for item in latest.result.recommendations],
                    "m_sinh_loi_active": False,
                },
            )
            if decision.intent == "ACCEPT_M_SINH_LOI":
                return FinancialChatResponse(
                    reply="Được, tôi đã đổi gợi ý sang M-Sinh lời. Hãy chọn hành động mới bên trên, nhập số dư tối thiểu và xác nhận. Sau xác nhận, bản demo sẽ chuyển ngay phần vượt ngưỡng; từ ngày tiếp theo kiểm tra phần dư lúc 16h. Đây là khoản cho SBSI vay, không phải tiền gửi tiết kiệm tại MSB.",
                    action_offer="ACTIVATE_M_SINH_LOI",
                )
            reply = decision.reply.strip()
            if decision.intent == "EXPLORE_FLEXIBLE" and ("SBSI" not in reply or "không phải tiền gửi" not in reply.lower()):
                reply += " M-Sinh lời là khoản bạn cho SBSI vay qua nền tảng tích hợp MSB, không phải tiền gửi tiết kiệm tại MSB."
            return FinancialChatResponse(reply=reply)
        compact_context = {
            "customer": context.customer.model_dump(mode="json"),
            "accounts": [item.model_dump(mode="json") for item in context.accounts],
            "recent_transactions": [item.model_dump(mode="json") for item in context.recent_transactions[:20]],
            "recurring_events": [item.model_dump(mode="json") for item in context.recurring_events],
            "active_budgets": [item.model_dump(mode="json") for item in context.active_budgets],
            "active_goals": [item.model_dump(mode="json") for item in context.active_goals],
            "overdraft_facilities": [item.model_dump(mode="json") for item in context.overdraft_facilities],
            "term_deposits": [item.model_dump(mode="json") for item in context.term_deposits],
            "credit_cards": [item.model_dump(mode="json") for item in context.credit_cards],
            "preapproved_loan_offers": [item.model_dump(mode="json") for item in context.preapproved_loan_offers],
            "m_sinh_loi": context.m_sinh_loi,
            "latest_financial_sensing": (
                latest.result.model_dump(mode="json")
                if latest and latest.result
                else None
            ),
        }
        conversation = "\n".join(
            f"{'Khách hàng' if item.role == 'user' else 'Trợ lý'}: {item.content}"
            for item in payload.history[-10:]
        )
        user_prompt = (
            "Dữ liệu tài chính hiện tại:\n"
            + json.dumps(compact_context, ensure_ascii=False, default=str)
            + (f"\n\nHội thoại gần đây:\n{conversation}" if conversation else "")
            + f"\n\nCâu hỏi mới của khách hàng: {payload.message}"
        )
        reply = runtime.llm.generate(
            system_prompt=(
                "Bạn là trợ lý Financial Sensing trong ứng dụng ngân hàng. Trả lời bằng tiếng Việt, "
                "thân thiện, ngắn gọn và dễ hiểu với người không có nghiệp vụ ngân hàng. Chỉ dùng dữ "
                "liệu được cung cấp; nếu thiếu dữ liệu thì nói rõ. Có thể giải thích sức khỏe tài chính, "
                "chi tiêu, dòng tiền, tiết kiệm và kiến thức tài chính liên quan. Không khẳng định chắc "
                "chắn về tương lai, không hứa lợi nhuận, không yêu cầu mật khẩu hoặc OTP và không tuyên "
                "bố đã thực hiện giao dịch. Với quyết định vay hoặc đầu tư, nêu rủi ro và khuyên khách "
                "hàng cân nhắc điều kiện sản phẩm. Không dùng Markdown phức tạp; tối đa khoảng 180 từ.\n\n"
                + M_SINH_LOI_KNOWLEDGE
            ),
            user_prompt=user_prompt,
        ).strip()
        return FinancialChatResponse(reply=reply)
    except LLMAuthenticationError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except LLMTimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except (LLMStructuredOutputError, LLMRequestError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except (ValueError, ToolExecutionError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


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


@app.post("/api/actions/activate-m-sinh-loi", response_model=AgentResponse, tags=["Demo actions"], summary="Chuẩn bị kích hoạt M-Sinh lời mô phỏng")
def api_activate_m_sinh_loi(payload: ActivateMSinhLoiInput, session: DbSession) -> AgentResponse:
    return _prepare_direct_action(session, "activate_m_sinh_loi", payload)


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


@app.post(
    "/api/agent/run-async",
    response_model=RadarScanRead,
    status_code=202,
    tags=["Agent workflow"],
    summary="Khởi tạo quét Financial Sensing bất đồng bộ",
    description="Trả scan_id ngay; dùng GET /api/scans/{scan_id} để theo dõi đến khi hoàn tất.",
)
def agent_run_async(
    payload: AgentRunRequest,
    background_tasks: BackgroundTasks,
    session: DbSession,
) -> RadarScanRead:
    scan = create_pending_scan(
        session,
        customer_id=payload.customer_id,
        message=payload.message,
        trigger_type=ScanTrigger.MANUAL,
        as_of=payload.as_of or business_today(),
    )
    background_tasks.add_task(_run_scan_background, scan.scan_id)
    result = get_scan(session, scan.scan_id)
    if result is None:
        raise HTTPException(status_code=500, detail="Could not create scan")
    return result


@app.get(
    "/api/scans/{scan_id}",
    response_model=RadarScanRead,
    tags=["Agent workflow"],
    summary="Theo dõi trạng thái một lần quét",
)
def scan_status(scan_id: str, session: DbSession) -> RadarScanRead:
    result = get_scan(session, scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown scan_id")
    return result


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
