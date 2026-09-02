from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import Category, Direction, SignalStatus, SignalType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerRead(ORMModel):
    customer_id: str
    customer_name: str
    monthly_income: Decimal
    salary_day: int = Field(ge=1, le=31)
    preferred_safe_balance: Decimal
    risk_preference: str
    created_at: datetime


class AccountRead(ORMModel):
    account_id: str
    customer_id: str
    account_type: str
    available_balance: Decimal
    currency: str
    updated_at: datetime


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


class RecurringEventRead(ORMModel):
    recurring_id: str
    customer_id: str
    name: str
    category: Category
    expected_amount: Decimal
    expected_day: int = Field(ge=1, le=31)
    frequency: str
    confidence: Decimal = Field(ge=0, le=1)
    active_flag: bool


class SavingGoalRead(ORMModel):
    goal_id: str
    customer_id: str
    goal_name: str
    target_amount: Decimal
    current_amount: Decimal
    start_date: date
    target_date: date
    monthly_contribution: Decimal
    status: str


class BudgetRead(ORMModel):
    budget_id: str
    customer_id: str
    category: Category
    amount: Decimal
    spent_amount: Decimal
    alert_threshold: Decimal = Field(ge=0, le=1)
    start_date: date
    end_date: date
    status: str


class RadarSignalRead(ORMModel):
    signal_id: str
    customer_id: str
    signal_type: SignalType
    severity: str
    signal_data: dict[str, Any]
    status: SignalStatus
    created_at: datetime
    resolved_at: datetime | None


class AgentActionLogRead(ORMModel):
    action_id: str
    customer_id: str
    signal_id: str | None
    recommendation_id: str | None
    action_type: str
    tool_name: str
    tool_input: dict[str, Any]
    policy_result: dict[str, Any]
    confirmation_required: bool
    confirmation_status: str
    tool_output: dict[str, Any] | None
    action_status: str
    latency_ms: int | None
    created_at: datetime
