from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.financial_engine.schemas import (
    BudgetGuardrailResult,
    SpendingAnomalyResult,
    SpendingEvidence,
)
from app.financial_engine.utils import add_months, money, ratio
from app.models import Category, Customer, Direction, Transaction


def calculate_budget_guardrail(
    session: Session, customer_id: str, category: Category
) -> BudgetGuardrailResult:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"Unknown customer_id: {customer_id}")
    configured_ratio = Decimal(str(get_settings().shopping_budget_income_ratio))
    recommended = money(customer.monthly_income * configured_ratio)
    return BudgetGuardrailResult(
        customer_id=customer_id,
        category=category,
        recommended_amount=recommended,
        income_ratio=configured_ratio,
        evidence={
            "monthly_income": money(customer.monthly_income),
            "configured_rule": "monthly_income * shopping_budget_income_ratio",
        },
    )


def detect_spending_anomaly(
    session: Session,
    customer_id: str,
    *,
    as_of: date,
    baseline_months: int | None = None,
    threshold: Decimal | None = None,
) -> SpendingAnomalyResult:
    settings = get_settings()
    months = baseline_months or settings.spending_baseline_months
    anomaly_threshold = threshold or Decimal(str(settings.spending_anomaly_threshold))
    current_start = as_of.replace(day=1)
    baseline_start = add_months(current_start, -months)

    transactions = session.scalars(
        select(Transaction)
        .where(
            Transaction.customer_id == customer_id,
            Transaction.direction == Direction.DEBIT,
            Transaction.transaction_date >= baseline_start,
            Transaction.transaction_date <= as_of,
            Transaction.category.not_in([Category.RENT, Category.TRANSFER]),
        )
    ).all()

    period_totals: dict[Category, dict[str, Decimal]] = {}
    for transaction in transactions:
        period = transaction.transaction_date.strftime("%Y-%m")
        category_totals = period_totals.setdefault(transaction.category, {})
        category_totals[period] = category_totals.get(period, Decimal(0)) + transaction.amount

    current_period = current_start.strftime("%Y-%m")
    baseline_periods = [
        add_months(current_start, -offset).strftime("%Y-%m")
        for offset in range(1, months + 1)
    ]
    evaluated: list[SpendingEvidence] = []
    for category in sorted(period_totals, key=lambda item: item.value):
        values = period_totals[category]
        history = [values[period] for period in baseline_periods if period in values]
        if len(history) != months:
            continue
        baseline = sum(history, Decimal(0)) / Decimal(months)
        current = values.get(current_period, Decimal(0))
        change_pct = None if baseline == 0 else ratio((current - baseline) / baseline)
        evaluated.append(
            SpendingEvidence(
                category=category,
                baseline_months=months,
                baseline_amount=money(baseline),
                current_amount=money(current),
                change_pct=change_pct,
                threshold=anomaly_threshold,
                is_anomaly=change_pct is not None and change_pct >= anomaly_threshold,
            )
        )

    return SpendingAnomalyResult(
        customer_id=customer_id,
        as_of=as_of,
        anomalies=[item for item in evaluated if item.is_anomaly],
        evaluated_categories=evaluated,
    )
