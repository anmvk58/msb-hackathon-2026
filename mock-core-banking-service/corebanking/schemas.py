from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from corebanking.models import Category, Direction


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerRead(ORMModel):
    customer_id: str
    customer_name: str
    monthly_income: Decimal
    salary_day: int
    preferred_safe_balance: Decimal
    risk_preference: str


class CustomerFinancialSettingsUpdate(BaseModel):
    monthly_income: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000000"))
    preferred_safe_balance: Decimal | None = Field(default=None, ge=0, le=Decimal("10000000000"))
    salary_day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode="after")
    def require_change(self) -> "CustomerFinancialSettingsUpdate":
        if self.monthly_income is None and self.preferred_safe_balance is None and self.salary_day is None:
            raise ValueError("At least one financial setting must be changed")
        return self


class DemoLoginRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"customer_id": "C001"}]})
    customer_id: str = Field(min_length=1, max_length=32)


class DemoLoginResponse(BaseModel):
    session_token: str
    customer: CustomerRead
    warning: str


class AccountRead(ORMModel):
    account_id: str
    customer_id: str
    account_type: str
    available_balance: Decimal
    currency: str
    updated_at: datetime


class OverdraftRead(ORMModel):
    facility_id: str; customer_id: str; account_id: str
    credit_limit: Decimal; used_amount: Decimal
    annual_interest_rate: Decimal; expires_at: date; status: str


class OverdraftDrawRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=Decimal("1000000000"))


class OverdraftDrawResponse(BaseModel):
    status: str
    facility_id: str
    account_id: str
    amount: Decimal
    account_available_balance: Decimal
    used_amount: Decimal
    available_limit: Decimal
    transaction_id: str


class TermDepositRead(ORMModel):
    deposit_id: str; customer_id: str; product_name: str
    current_balance: Decimal; available_withdrawal_amount: Decimal
    interest_rate: Decimal; early_withdrawal_rate: Decimal
    opened_at: date; maturity_date: date
    partial_withdrawal_allowed: bool; status: str


class CreditCardRead(ORMModel):
    card_id: str; customer_id: str; masked_number: str; product_name: str
    credit_limit: Decimal; outstanding_amount: Decimal
    payment_due_day: int; status: str


class LoanOfferRead(ORMModel):
    offer_id: str; customer_id: str; product_code: str; display_name: str
    approved_limit: Decimal; minimum_amount: Decimal
    annual_interest_rate: Decimal; term_months: int; valid_until: date
    eligibility_status: str; status: str


class TransactionRead(ORMModel):
    transaction_id: str
    customer_id: str
    account_id: str
    transaction_date: date
    amount: Decimal
    direction: Direction
    merchant: str | None
    description: str | None
    category: Category
    transaction_type: str
    created_at: datetime


class TransactionCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "account_id": "A-C001",
                "amount": 1500000,
                "direction": "DEBIT",
                "category": "SHOPPING",
                "merchant": "Mall B",
                "description": "Demo card payment",
                "transaction_date": "2026-09-02",
                "transaction_type": "CARD",
            }]
        }
    )
    account_id: str
    amount: Decimal = Field(gt=0, le=Decimal("1000000000"))
    direction: Direction
    category: Category
    merchant: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    transaction_date: date = Field(default_factory=date.today)
    transaction_type: str = Field(default="CARD", max_length=50)


class TransactionCreateResponse(BaseModel):
    transaction: TransactionRead
    account: AccountRead


class RecurringEventRead(ORMModel):
    recurring_id: str
    customer_id: str
    name: str
    category: Category
    expected_amount: Decimal
    expected_day: int
    frequency: str
    confidence: Decimal
    active_flag: bool


class RecurringEventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: Category
    expected_amount: Decimal = Field(gt=0, le=Decimal("1000000000"))
    expected_day: int = Field(ge=1, le=31)
    frequency: str = Field(default="MONTHLY", pattern="^(MONTHLY)$")


class RecurringEventUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: Category | None = None
    expected_amount: Decimal | None = Field(default=None, gt=0, le=Decimal("1000000000"))
    expected_day: int | None = Field(default=None, ge=1, le=31)
    active_flag: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "RecurringEventUpdate":
        if all(value is None for value in (self.name, self.category, self.expected_amount, self.expected_day, self.active_flag)):
            raise ValueError("At least one recurring event field must be changed")
        return self


class BudgetRead(ORMModel):
    budget_id: str
    customer_id: str
    category: Category
    amount: Decimal
    spent_amount: Decimal
    alert_threshold: Decimal
    start_date: date
    end_date: date
    status: str


class BudgetCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "category": "SHOPPING",
                "amount": 3000000,
                "alert_threshold": 0.8,
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
            }]
        }
    )
    category: Category
    amount: Decimal = Field(gt=0, le=Decimal("1000000000"))
    alert_threshold: Decimal = Field(default=Decimal("0.8"), gt=0, le=1)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_budget(self) -> "BudgetCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.category in {Category.SALARY, Category.TRANSFER}:
            raise ValueError("Budget category must represent spending")
        return self


class GoalRead(ORMModel):
    goal_id: str
    customer_id: str
    goal_name: str
    target_amount: Decimal
    current_amount: Decimal
    start_date: date
    target_date: date
    monthly_contribution: Decimal
    status: str


class GoalCreate(BaseModel):
    goal_name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal = Field(gt=0, le=Decimal("10000000000"))
    current_amount: Decimal = Field(default=Decimal(0), ge=0)
    start_date: date
    target_date: date
    monthly_contribution: Decimal = Field(gt=0, le=Decimal("1000000000"))

    @model_validator(mode="after")
    def validate_goal(self) -> "GoalCreate":
        if self.target_date <= self.start_date:
            raise ValueError("target_date must be after start_date")
        if self.current_amount > self.target_amount:
            raise ValueError("current_amount must not exceed target_amount")
        return self


class GoalUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"monthly_contribution": 9000000, "target_date": "2027-06-30"}]}
    )
    goal_name: str | None = Field(default=None, min_length=1, max_length=200)
    target_amount: Decimal | None = Field(default=None, gt=0, le=Decimal("10000000000"))
    current_amount: Decimal | None = Field(default=None, ge=0)
    monthly_contribution: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None

    @model_validator(mode="after")
    def require_change(self) -> "GoalUpdate":
        if all(value is None for value in (self.goal_name, self.target_amount, self.current_amount, self.monthly_contribution, self.target_date)):
            raise ValueError("At least one goal field must be changed")
        return self


class ReminderRead(ORMModel):
    reminder_id: str
    customer_id: str
    title: str
    remind_at: datetime
    message: str
    status: str
    created_at: datetime


class ReminderCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "title": "Kiểm tra số dư",
                "remind_at": "2026-09-04T09:00:00",
                "message": "Kiểm tra số dư trước ngày thanh toán tiền thuê",
            }]
        }
    )
    title: str = Field(min_length=1, max_length=200)
    remind_at: datetime
    message: str = Field(min_length=1, max_length=500)


class FinancialContext(BaseModel):
    customer: CustomerRead
    accounts: list[AccountRead]
    recent_transactions: list[TransactionRead]
    recurring_events: list[RecurringEventRead]
    active_budgets: list[BudgetRead]
    active_goals: list[GoalRead]
    overdraft_facilities: list[OverdraftRead]
    term_deposits: list[TermDepositRead]
    credit_cards: list[CreditCardRead]
    preapproved_loan_offers: list[LoanOfferRead]
    generated_at: datetime
