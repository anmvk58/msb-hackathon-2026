from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models import Category


class SpendingEvidence(BaseModel):
    category: Category
    baseline_months: int
    baseline_amount: Decimal
    current_amount: Decimal
    change_pct: Decimal | None
    threshold: Decimal
    is_anomaly: bool


class SpendingAnomalyResult(BaseModel):
    customer_id: str
    as_of: date
    anomalies: list[SpendingEvidence]
    evaluated_categories: list[SpendingEvidence]


class BudgetGuardrailResult(BaseModel):
    customer_id: str
    category: Category
    recommended_amount: Decimal
    income_ratio: Decimal
    evidence: dict[str, Decimal | str]


class UpcomingRecurringItem(BaseModel):
    recurring_id: str
    name: str
    category: Category
    expected_amount: Decimal
    expected_date: date
    days_until: int
    confidence: Decimal = Field(ge=0, le=1)


class UpcomingRecurringResult(BaseModel):
    customer_id: str
    as_of: date
    window_days: int
    events: list[UpcomingRecurringItem]


class CashflowDriver(BaseModel):
    type: Literal["EXPECTED_INCOME", "RECURRING", "SPENDING_TREND"]
    impact: Decimal
    name: str | None = None
    category: Category | None = None
    evidence: dict[str, str | int | Decimal]


class CashflowForecastResult(BaseModel):
    customer_id: str
    as_of: date
    forecast_until: date
    current_balance: Decimal
    forecast_balance: Decimal
    safe_balance: Decimal
    gap: Decimal
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: Decimal = Field(ge=0, le=1)
    drivers: list[CashflowDriver]


class GoalGapResult(BaseModel):
    customer_id: str
    goal_id: str
    as_of: date
    target_amount: Decimal
    actual_progress: Decimal
    expected_progress: Decimal
    gap: Decimal
    progress_ratio: Decimal
    expected_ratio: Decimal
    is_drifting: bool


class GoalScenario(BaseModel):
    scenario_id: str
    action_type: Literal["INCREASE_CONTRIBUTION", "EXTEND_DEADLINE"]
    monthly_contribution: Decimal
    target_date: date
    months_remaining: int
    parameters: dict[str, str | int | Decimal]


class GoalSimulationResult(BaseModel):
    customer_id: str
    goal_id: str
    gap_analysis: GoalGapResult
    scenarios: list[GoalScenario]
