from datetime import date
from decimal import Decimal

import pytest
from app.banking.schemas import FinancialContext
from app.financial_engine import (
    calculate_goal_gap,
    detect_spending_anomaly,
    detect_upcoming_recurring,
    forecast_cashflow,
    simulate_goal_scenarios,
)
from app.models import Category
from tests.fakes import FakeBankingGateway


AS_OF = date(2026, 9, 1)


def _context(gateway: FakeBankingGateway, customer_id: str) -> FinancialContext:
    return gateway.get_financial_context(customer_id)


def test_spending_anomaly_c002(fake_banking_gateway: FakeBankingGateway) -> None:
    result = detect_spending_anomaly(_context(fake_banking_gateway, "C002"), "C002", as_of=AS_OF)
    assert len(result.anomalies) == 1
    anomaly = result.anomalies[0]
    assert anomaly.category == Category.FOOD
    assert anomaly.baseline_amount == Decimal("4000000")
    assert anomaly.current_amount == Decimal("5000000")
    assert anomaly.change_pct == Decimal("0.2500")


def test_cashflow_risk_c001(fake_banking_gateway: FakeBankingGateway) -> None:
    result = forecast_cashflow(
        _context(fake_banking_gateway, "C001"), "C001", as_of=AS_OF, forecast_until=date(2026, 9, 15)
    )
    assert Decimal("1000000") <= result.forecast_balance <= Decimal("2000000")
    assert result.forecast_balance == Decimal("1366667")
    assert result.gap < 0
    assert result.risk_level == "HIGH"
    assert {driver.type for driver in result.drivers} == {
        "RECURRING",
        "SPENDING_TREND",
    }


def test_goal_drift_c003(fake_banking_gateway: FakeBankingGateway) -> None:
    context = _context(fake_banking_gateway, "C003")
    result = calculate_goal_gap(context, "C003", as_of=AS_OF)
    assert result.actual_progress == Decimal("22000000")
    assert result.expected_progress > Decimal("33000000")
    assert result.gap < Decimal("-11000000")
    assert result.is_drifting is True
    simulation = simulate_goal_scenarios(context, "C003", as_of=AS_OF)
    assert {item.action_type for item in simulation.scenarios} == {
        "INCREASE_CONTRIBUTION",
        "EXTEND_DEADLINE",
    }


def test_recurring_c004(fake_banking_gateway: FakeBankingGateway) -> None:
    result = detect_upcoming_recurring(_context(fake_banking_gateway, "C004"), "C004", as_of=AS_OF, window_days=7)
    assert len(result.events) == 1
    assert result.events[0].name == "Rent"
    assert result.events[0].expected_amount == Decimal("8000000")
    assert result.events[0].days_until == 2


def test_cross_signal_recurring_to_cashflow(fake_banking_gateway: FakeBankingGateway) -> None:
    context = _context(fake_banking_gateway, "C004")
    upcoming = detect_upcoming_recurring(context, "C004", as_of=AS_OF, window_days=7)
    forecast = forecast_cashflow(
        context, "C004", as_of=AS_OF, forecast_until=date(2026, 9, 7)
    )
    assert upcoming.events
    assert forecast.forecast_balance == Decimal("-800000")
    assert forecast.risk_level == "HIGH"
    assert any(
        driver.type == "RECURRING" and driver.impact == Decimal("-8000000")
        for driver in forecast.drivers
    )


def test_forecast_rejects_invalid_horizon(fake_banking_gateway: FakeBankingGateway) -> None:
    with pytest.raises(ValueError, match="forecast_until"):
        forecast_cashflow(
            _context(fake_banking_gateway, "C001"), "C001", as_of=AS_OF, forecast_until=date(2026, 8, 31)
        )
