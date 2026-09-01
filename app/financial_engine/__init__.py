"""Deterministic, testable financial calculations. No LLM calls belong here."""

from app.financial_engine.cashflow import forecast_cashflow
from app.financial_engine.goal import calculate_goal_gap, simulate_goal_scenarios
from app.financial_engine.recurring import detect_upcoming_recurring
from app.financial_engine.spending import calculate_budget_guardrail, detect_spending_anomaly

__all__ = [
    "calculate_goal_gap",
    "calculate_budget_guardrail",
    "detect_spending_anomaly",
    "detect_upcoming_recurring",
    "forecast_cashflow",
    "simulate_goal_scenarios",
]
