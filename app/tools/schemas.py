from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.financial_engine.schemas import (
    CashflowForecastResult,
    GoalSimulationResult,
    SpendingAnomalyResult,
    UpcomingRecurringResult,
)
from app.models import Category


class CustomerInput(BaseModel):
    customer_id: str = Field(min_length=1, max_length=32)


class FinancialSnapshotInput(CustomerInput):
    pass


class FinancialSnapshotOutput(BaseModel):
    customer_id: str
    customer_name: str
    monthly_income: Decimal
    safe_balance: Decimal
    total_available_balance: Decimal
    currency: str
    active_goal_count: int
    active_budget_count: int


class SpendingAnomalyInput(CustomerInput):
    as_of: date


class SpendingAnomalyOutput(SpendingAnomalyResult):
    pass


class RecurringInput(CustomerInput):
    as_of: date
    window_days: int = Field(default=14, ge=0, le=90)


class RecurringOutput(UpcomingRecurringResult):
    pass


class CashflowInput(CustomerInput):
    as_of: date
    forecast_until: date

    @model_validator(mode="after")
    def valid_horizon(self) -> "CashflowInput":
        if self.forecast_until < self.as_of:
            raise ValueError("forecast_until must be on or after as_of")
        return self


class CashflowOutput(CashflowForecastResult):
    pass


class GoalSimulationInput(CustomerInput):
    as_of: date
    goal_id: str | None = None


class GoalSimulationOutput(GoalSimulationResult):
    pass


class CreateBudgetInput(CustomerInput):
    category: Category
    amount: Decimal = Field(gt=0, le=Decimal("1000000000"))
    alert_threshold: Decimal = Field(default=Decimal("0.8"), gt=0, le=1)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def valid_dates(self) -> "CreateBudgetInput":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.category in {Category.SALARY, Category.TRANSFER}:
            raise ValueError("Budget category must represent spending")
        return self


class CreateBudgetOutput(BaseModel):
    status: str
    budget_id: str
    customer_id: str
    category: Category
    amount: Decimal


class CreateReminderInput(CustomerInput):
    title: str = Field(min_length=1, max_length=200)
    remind_at: datetime
    message: str = Field(min_length=1, max_length=500)


class CreateReminderOutput(BaseModel):
    status: str
    reminder_id: str
    customer_id: str
    remind_at: datetime


class UpdateGoalInput(CustomerInput):
    goal_id: str
    monthly_contribution: Decimal | None = Field(default=None, gt=0)
    target_date: date | None = None

    @model_validator(mode="after")
    def has_change(self) -> "UpdateGoalInput":
        if self.monthly_contribution is None and self.target_date is None:
            raise ValueError("At least one goal field must be changed")
        return self


class UpdateGoalOutput(BaseModel):
    status: str
    goal_id: str
    customer_id: str
    monthly_contribution: Decimal
    target_date: date


class ToolInvocation(BaseModel):
    tool: str
    arguments: dict[str, Any]


class ToolInvocationResult(BaseModel):
    tool: str
    output: dict[str, Any]

