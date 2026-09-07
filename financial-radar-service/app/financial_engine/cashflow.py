import calendar
from datetime import date, timedelta
from decimal import Decimal

from app.banking.schemas import CustomerData, FinancialContext
from app.config import get_settings
from app.financial_engine.recurring import detect_upcoming_recurring
from app.financial_engine.schemas import CashflowDriver, CashflowForecastResult
from app.financial_engine.utils import money, ratio
from app.models import Category, Direction


def _salary_dates(customer: CustomerData, as_of: date, until: date) -> list[date]:
    dates: list[date] = []
    cursor = as_of.replace(day=1)
    while cursor <= until:
        salary_date = cursor.replace(
            day=min(customer.salary_day, calendar.monthrange(cursor.year, cursor.month)[1])
        )
        if as_of < salary_date <= until:
            dates.append(salary_date)
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return dates


def forecast_cashflow(
    context: FinancialContext,
    customer_id: str,
    *,
    forecast_until: date,
    as_of: date,
) -> CashflowForecastResult:
    if forecast_until < as_of:
        raise ValueError("forecast_until must be on or after as_of")
    customer = context.customer
    if customer.customer_id != customer_id:
        raise ValueError(f"Unknown customer_id: {customer_id}")
    accounts = context.accounts
    if not accounts:
        raise ValueError(f"Customer {customer_id} has no account")

    settings = get_settings()
    current_balance = sum((account.available_balance for account in accounts), Decimal(0))
    horizon_days = (forecast_until - as_of).days
    drivers: list[CashflowDriver] = []

    salary_count = len(_salary_dates(customer, as_of, forecast_until))
    expected_income = customer.monthly_income * salary_count
    if expected_income:
        drivers.append(
            CashflowDriver(
                type="EXPECTED_INCOME",
                name="Salary",
                impact=money(expected_income),
                evidence={"occurrences": salary_count},
            )
        )

    recurring = detect_upcoming_recurring(
        context, customer_id, as_of=as_of, window_days=horizon_days
    )
    expected_recurring = sum((item.expected_amount for item in recurring.events), Decimal(0))
    for item in recurring.events:
        drivers.append(
            CashflowDriver(
                type="RECURRING",
                name=item.name,
                category=item.category,
                impact=-money(item.expected_amount),
                evidence={
                    "expected_date": item.expected_date.isoformat(),
                    "confidence": item.confidence,
                },
            )
        )

    lookback_start = as_of - timedelta(days=settings.cashflow_spending_lookback_days)
    historical_spend = sum(
        (
            item.amount for item in context.recent_transactions
            if item.direction == Direction.DEBIT
            and lookback_start <= item.transaction_date < as_of
            and item.category not in {Category.RENT, Category.UTILITY, Category.TRANSFER}
        ),
        Decimal(0),
    )
    daily_average = historical_spend / Decimal(settings.cashflow_spending_lookback_days)
    discretionary = money(daily_average * Decimal(horizon_days))
    if discretionary:
        drivers.append(
            CashflowDriver(
                type="SPENDING_TREND",
                name="Discretionary spending",
                impact=-discretionary,
                evidence={
                    "lookback_days": settings.cashflow_spending_lookback_days,
                    "historical_spend": money(historical_spend),
                    "daily_average": money(daily_average),
                    "forecast_days": horizon_days,
                },
            )
        )

    forecast = money(
        current_balance + expected_income - expected_recurring - discretionary
    )
    safe = money(customer.preferred_safe_balance)
    gap = money(forecast - safe)
    if forecast >= safe:
        risk = "LOW"
    elif forecast >= safe * Decimal(str(settings.cashflow_medium_ratio)):
        risk = "MEDIUM"
    else:
        risk = "HIGH"

    recurring_confidence = (
        sum((item.confidence for item in recurring.events), Decimal(0))
        / len(recurring.events)
        if recurring.events
        else Decimal("0.80")
    )
    history_factor = min(
        Decimal("1"), historical_spend / max(customer.monthly_income, Decimal("1"))
    )
    confidence = ratio(
        Decimal("0.75")
        + Decimal("0.15") * recurring_confidence
        + Decimal("0.10") * history_factor
    )
    return CashflowForecastResult(
        customer_id=customer_id,
        as_of=as_of,
        forecast_until=forecast_until,
        current_balance=money(current_balance),
        forecast_balance=forecast,
        safe_balance=safe,
        gap=gap,
        risk_level=risk,
        confidence=confidence,
        drivers=drivers,
    )
