from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import Category, Direction


class CustomerData(BaseModel):
    customer_id: str
    customer_name: str
    monthly_income: Decimal
    salary_day: int
    preferred_safe_balance: Decimal
    risk_preference: str


class AccountData(BaseModel):
    account_id: str
    customer_id: str
    account_type: str
    available_balance: Decimal
    currency: str
    updated_at: datetime


class TransactionData(BaseModel):
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


class RecurringEventData(BaseModel):
    recurring_id: str
    customer_id: str
    name: str
    category: Category
    expected_amount: Decimal
    expected_day: int
    frequency: str
    confidence: Decimal
    active_flag: bool


class BudgetData(BaseModel):
    budget_id: str
    customer_id: str
    category: Category
    amount: Decimal
    spent_amount: Decimal
    alert_threshold: Decimal
    start_date: date
    end_date: date
    status: str


class GoalData(BaseModel):
    goal_id: str
    customer_id: str
    goal_name: str
    target_amount: Decimal
    current_amount: Decimal
    start_date: date
    target_date: date
    monthly_contribution: Decimal
    status: str


class FinancialContext(BaseModel):
    customer: CustomerData
    accounts: list[AccountData]
    recent_transactions: list[TransactionData]
    recurring_events: list[RecurringEventData]
    active_budgets: list[BudgetData]
    active_goals: list[GoalData]
    generated_at: datetime
