from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from corebanking.config import get_core_banking_settings
from corebanking.database import (
    CoreBankingSessionLocal,
    create_core_banking_schema_with_retry,
    get_core_banking_db,
)
from corebanking.idempotency import remember, replay
from corebanking.models import Account, Budget, Customer, Direction, RecurringEvent, Reminder, SavingGoal, Transaction
from corebanking.schemas import (
    AccountRead,
    BudgetCreate,
    BudgetRead,
    CustomerRead,
    CustomerFinancialSettingsUpdate,
    DemoLoginRequest,
    DemoLoginResponse,
    FinancialContext,
    GoalRead,
    GoalCreate,
    GoalUpdate,
    RecurringEventRead,
    RecurringEventCreate,
    RecurringEventUpdate,
    ReminderCreate,
    ReminderRead,
    TransactionCreate,
    TransactionCreateResponse,
    TransactionRead,
)
from corebanking.seed import seed_core_banking_if_empty


DESCRIPTION = """
Mock Core Banking API sở hữu dữ liệu nghiệp vụ cho Mobile Banking demo và
Financial Radar Agent.

### Phạm vi
- Dữ liệu hoàn toàn giả lập (`C001`–`C004`), không kết nối hệ thống MSB thật.
- `demo-login` không phải cơ chế xác thực production.
- Các write API hỗ trợ `Idempotency-Key` để Agent retry an toàn.
- Agent phải dùng REST API này, không truy cập trực tiếp database Core Banking.
"""

TAGS = [
    {"name": "System", "description": "Health và thông tin service."},
    {"name": "Demo auth", "description": "Đăng nhập giả lập cho Mobile Banking demo."},
    {"name": "Customer context", "description": "Context tổng hợp dành cho Financial Radar Agent."},
    {"name": "Accounts", "description": "Tài khoản và số dư của khách hàng."},
    {"name": "Transactions", "description": "Lịch sử và giao dịch mô phỏng."},
    {"name": "Recurring events", "description": "Lịch trả tiền định kỳ do khách hàng thiết lập."},
    {"name": "Budgets", "description": "Ngân sách được áp dụng vào Mobile Banking demo."},
    {"name": "Goals", "description": "Mục tiêu tiết kiệm của khách hàng."},
    {"name": "Reminders", "description": "Nhắc nhở hiển thị trong ứng dụng demo."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_core_banking_schema_with_retry()
    if get_core_banking_settings().seed_demo_on_start:
        with CoreBankingSessionLocal() as session:
            seed_core_banking_if_empty(session)
    yield


app = FastAPI(
    title="MSB Mock Core Banking",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=TAGS,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_core_banking_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DbSession = Annotated[Session, Depends(get_core_banking_db)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=100)]


def _customer_or_404(session: Session, customer_id: str) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@app.get("/", tags=["System"], summary="Thông tin Mock Core Banking")
def root() -> dict[str, str]:
    return {"name": "MSB Mock Core Banking", "status": "running", "documentation": "/docs", "scope": "Synthetic demo data only"}


@app.get("/health", tags=["System"], summary="Kiểm tra sức khỏe service")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "mock-core-banking"}


@app.post("/api/auth/demo-login", response_model=DemoLoginResponse, tags=["Demo auth"], summary="Đăng nhập khách hàng demo")
def demo_login(payload: DemoLoginRequest, session: DbSession) -> DemoLoginResponse:
    customer = _customer_or_404(session, payload.customer_id)
    return DemoLoginResponse(
        session_token=f"demo-session:{customer.customer_id}",
        customer=CustomerRead.model_validate(customer),
        warning="Demo authentication only; not valid for production.",
    )


@app.get("/api/customers/{customer_id}/financial-context", response_model=FinancialContext, tags=["Customer context"], summary="Lấy context tài chính tổng hợp")
def financial_context(
    customer_id: str,
    session: DbSession,
    transaction_limit: int = Query(default=100, ge=1, le=500),
) -> FinancialContext:
    customer = _customer_or_404(session, customer_id)
    accounts = list(session.scalars(select(Account).where(Account.customer_id == customer_id)).all())
    transactions = list(session.scalars(select(Transaction).where(Transaction.customer_id == customer_id).order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc()).limit(transaction_limit)).all())
    recurring = list(session.scalars(select(RecurringEvent).where(RecurringEvent.customer_id == customer_id, RecurringEvent.active_flag.is_(True))).all())
    budgets = list(session.scalars(select(Budget).where(Budget.customer_id == customer_id, Budget.status == "ACTIVE")).all())
    goals = list(session.scalars(select(SavingGoal).where(SavingGoal.customer_id == customer_id, SavingGoal.status == "ACTIVE")).all())
    return FinancialContext(
        customer=CustomerRead.model_validate(customer),
        accounts=[AccountRead.model_validate(item) for item in accounts],
        recent_transactions=[TransactionRead.model_validate(item) for item in transactions],
        recurring_events=[RecurringEventRead.model_validate(item) for item in recurring],
        active_budgets=[BudgetRead.model_validate(item) for item in budgets],
        active_goals=[GoalRead.model_validate(item) for item in goals],
        generated_at=datetime.utcnow(),
    )


@app.patch("/api/customers/{customer_id}/financial-settings", response_model=CustomerRead, tags=["Customer context"], summary="Cập nhật thông tin tài chính cá nhân")
def update_financial_settings(customer_id: str, payload: CustomerFinancialSettingsUpdate, session: DbSession) -> CustomerRead:
    customer = _customer_or_404(session, customer_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(customer, field, value)
    session.commit()
    session.refresh(customer)
    return CustomerRead.model_validate(customer)


@app.get("/api/customers/{customer_id}/recurring-events", response_model=list[RecurringEventRead], tags=["Recurring events"], summary="Liệt kê lịch thanh toán định kỳ")
def get_recurring_events(customer_id: str, session: DbSession) -> list[RecurringEvent]:
    _customer_or_404(session, customer_id)
    return list(session.scalars(select(RecurringEvent).where(RecurringEvent.customer_id == customer_id).order_by(RecurringEvent.expected_day)).all())


@app.post("/api/customers/{customer_id}/recurring-events", response_model=RecurringEventRead, status_code=201, tags=["Recurring events"], summary="Tạo lịch thanh toán định kỳ")
def create_recurring_event(customer_id: str, payload: RecurringEventCreate, session: DbSession) -> RecurringEventRead:
    _customer_or_404(session, customer_id)
    event = RecurringEvent(
        recurring_id=f"R-{uuid4().hex[:12].upper()}", customer_id=customer_id,
        confidence=Decimal("1.0"), active_flag=True, **payload.model_dump(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return RecurringEventRead.model_validate(event)


@app.patch("/api/customers/{customer_id}/recurring-events/{recurring_id}", response_model=RecurringEventRead, tags=["Recurring events"], summary="Cập nhật lịch thanh toán định kỳ")
def update_recurring_event(customer_id: str, recurring_id: str, payload: RecurringEventUpdate, session: DbSession) -> RecurringEventRead:
    _customer_or_404(session, customer_id)
    event = session.get(RecurringEvent, recurring_id)
    if event is None or event.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Recurring event not found for customer")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(event, field, value)
    session.commit()
    session.refresh(event)
    return RecurringEventRead.model_validate(event)


@app.get("/api/customers/{customer_id}/accounts", response_model=list[AccountRead], tags=["Accounts"], summary="Liệt kê tài khoản")
def get_accounts(customer_id: str, session: DbSession) -> list[Account]:
    _customer_or_404(session, customer_id)
    return list(session.scalars(select(Account).where(Account.customer_id == customer_id)).all())


@app.get("/api/customers/{customer_id}/transactions", response_model=list[TransactionRead], tags=["Transactions"], summary="Lấy lịch sử giao dịch")
def get_transactions(customer_id: str, session: DbSession, limit: int = Query(default=100, ge=1, le=500)) -> list[Transaction]:
    _customer_or_404(session, customer_id)
    return list(session.scalars(select(Transaction).where(Transaction.customer_id == customer_id).order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc()).limit(limit)).all())


@app.post("/api/customers/{customer_id}/transactions", response_model=TransactionCreateResponse, status_code=201, tags=["Transactions"], summary="Tạo giao dịch demo")
def create_transaction(customer_id: str, payload: TransactionCreate, session: DbSession, idempotency_key: IdempotencyKey = None) -> TransactionCreateResponse:
    operation = f"create-transaction:{customer_id}"
    cached = replay(session, operation=operation, key=idempotency_key, response_model=TransactionCreateResponse)
    if cached:
        return cached
    _customer_or_404(session, customer_id)
    account = session.get(Account, payload.account_id)
    if account is None or account.customer_id != customer_id:
        raise HTTPException(status_code=404, detail="Account not found for customer")
    if payload.direction == Direction.DEBIT and account.available_balance < payload.amount:
        raise HTTPException(status_code=409, detail="Insufficient available balance")
    account.available_balance += payload.amount if payload.direction == Direction.CREDIT else -payload.amount
    account.updated_at = datetime.utcnow()
    transaction = Transaction(
        transaction_id=f"TX-{uuid4().hex[:12].upper()}", customer_id=customer_id,
        account_id=payload.account_id, transaction_date=payload.transaction_date,
        amount=payload.amount, direction=payload.direction, merchant=payload.merchant,
        description=payload.description, category=payload.category,
        transaction_type=payload.transaction_type, created_at=datetime.utcnow(),
    )
    session.add(transaction)
    if payload.direction == Direction.DEBIT:
        budgets = session.scalars(select(Budget).where(Budget.customer_id == customer_id, Budget.category == payload.category, Budget.status == "ACTIVE", Budget.start_date <= payload.transaction_date, Budget.end_date >= payload.transaction_date)).all()
        for budget in budgets:
            budget.spent_amount += payload.amount
    session.flush()
    session.refresh(transaction)
    session.refresh(account)
    response = TransactionCreateResponse(transaction=TransactionRead.model_validate(transaction), account=AccountRead.model_validate(account))
    remember(session, operation=operation, key=idempotency_key, response=response)
    session.commit()
    return response


@app.get("/api/customers/{customer_id}/budgets", response_model=list[BudgetRead], tags=["Budgets"], summary="Liệt kê ngân sách")
def get_budgets(customer_id: str, session: DbSession) -> list[Budget]:
    _customer_or_404(session, customer_id)
    return list(session.scalars(select(Budget).where(Budget.customer_id == customer_id).order_by(Budget.start_date.desc())).all())


@app.post("/api/customers/{customer_id}/budgets", response_model=BudgetRead, status_code=201, tags=["Budgets"], summary="Tạo ngân sách")
def create_budget(customer_id: str, payload: BudgetCreate, session: DbSession, idempotency_key: IdempotencyKey = None) -> BudgetRead:
    operation = f"create-budget:{customer_id}"
    cached = replay(session, operation=operation, key=idempotency_key, response_model=BudgetRead)
    if cached:
        return cached
    _customer_or_404(session, customer_id)
    duplicate = session.scalar(select(Budget).where(Budget.customer_id == customer_id, Budget.category == payload.category, Budget.status == "ACTIVE", Budget.start_date <= payload.end_date, Budget.end_date >= payload.start_date).limit(1))
    if duplicate:
        raise HTTPException(status_code=409, detail="An active overlapping budget already exists")
    spent = session.scalar(select(func.sum(Transaction.amount)).where(Transaction.customer_id == customer_id, Transaction.direction == Direction.DEBIT, Transaction.category == payload.category, Transaction.transaction_date >= payload.start_date, Transaction.transaction_date <= payload.end_date))
    budget = Budget(budget_id=f"B-{uuid4().hex[:12].upper()}", customer_id=customer_id, category=payload.category, amount=payload.amount, spent_amount=spent or Decimal(0), alert_threshold=payload.alert_threshold, start_date=payload.start_date, end_date=payload.end_date, status="ACTIVE")
    session.add(budget)
    session.flush()
    session.refresh(budget)
    response = BudgetRead.model_validate(budget)
    remember(session, operation=operation, key=idempotency_key, response=response)
    session.commit()
    return response


@app.get("/api/customers/{customer_id}/goals", response_model=list[GoalRead], tags=["Goals"], summary="Liệt kê mục tiêu tiết kiệm")
def get_goals(customer_id: str, session: DbSession) -> list[SavingGoal]:
    _customer_or_404(session, customer_id)
    return list(session.scalars(select(SavingGoal).where(SavingGoal.customer_id == customer_id)).all())


@app.post("/api/customers/{customer_id}/goals", response_model=GoalRead, status_code=201, tags=["Goals"], summary="Tạo mục tiêu tiết kiệm")
def create_goal(customer_id: str, payload: GoalCreate, session: DbSession) -> GoalRead:
    _customer_or_404(session, customer_id)
    goal = SavingGoal(
        goal_id=f"G-{uuid4().hex[:12].upper()}", customer_id=customer_id,
        status="ACTIVE", **payload.model_dump(),
    )
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return GoalRead.model_validate(goal)


@app.patch("/api/customers/{customer_id}/goals/{goal_id}", response_model=GoalRead, tags=["Goals"], summary="Cập nhật mục tiêu tiết kiệm")
def update_goal(customer_id: str, goal_id: str, payload: GoalUpdate, session: DbSession, idempotency_key: IdempotencyKey = None) -> GoalRead:
    operation = f"update-goal:{customer_id}:{goal_id}"
    cached = replay(session, operation=operation, key=idempotency_key, response_model=GoalRead)
    if cached:
        return cached
    _customer_or_404(session, customer_id)
    goal = session.get(SavingGoal, goal_id)
    if goal is None or goal.customer_id != customer_id or goal.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Active goal not found for customer")
    if payload.target_date is not None:
        if payload.target_date <= goal.start_date:
            raise HTTPException(status_code=422, detail="target_date must be after goal start_date")
        goal.target_date = payload.target_date
    proposed_target = payload.target_amount if payload.target_amount is not None else goal.target_amount
    proposed_current = payload.current_amount if payload.current_amount is not None else goal.current_amount
    if proposed_current > proposed_target:
        raise HTTPException(status_code=422, detail="current_amount must not exceed target_amount")
    if payload.goal_name is not None:
        goal.goal_name = payload.goal_name
    if payload.target_amount is not None:
        goal.target_amount = payload.target_amount
    if payload.current_amount is not None:
        goal.current_amount = payload.current_amount
    if payload.monthly_contribution is not None:
        goal.monthly_contribution = payload.monthly_contribution
    session.flush()
    session.refresh(goal)
    response = GoalRead.model_validate(goal)
    remember(session, operation=operation, key=idempotency_key, response=response)
    session.commit()
    return response


@app.get("/api/customers/{customer_id}/reminders", response_model=list[ReminderRead], tags=["Reminders"], summary="Liệt kê nhắc nhở")
def get_reminders(customer_id: str, session: DbSession) -> list[Reminder]:
    _customer_or_404(session, customer_id)
    return list(session.scalars(select(Reminder).where(Reminder.customer_id == customer_id).order_by(Reminder.remind_at)).all())


@app.post("/api/customers/{customer_id}/reminders", response_model=ReminderRead, status_code=201, tags=["Reminders"], summary="Tạo nhắc nhở")
def create_reminder(customer_id: str, payload: ReminderCreate, session: DbSession, idempotency_key: IdempotencyKey = None) -> ReminderRead:
    operation = f"create-reminder:{customer_id}"
    cached = replay(session, operation=operation, key=idempotency_key, response_model=ReminderRead)
    if cached:
        return cached
    _customer_or_404(session, customer_id)
    reminder = Reminder(reminder_id=f"RM-{uuid4().hex[:12].upper()}", customer_id=customer_id, title=payload.title, remind_at=payload.remind_at, message=payload.message, status="ACTIVE", created_at=datetime.utcnow())
    session.add(reminder)
    session.flush()
    session.refresh(reminder)
    response = ReminderRead.model_validate(reminder)
    remember(session, operation=operation, key=idempotency_key, response=response)
    session.commit()
    return response
