import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from corebanking.models import (
    Account,
    Budget,
    Category,
    Customer,
    Direction,
    RecurringEvent,
    SavingGoal,
    Transaction,
)


DEMO_AS_OF = date(2026, 9, 1)
BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

CUSTOMERS = (
    ("C001", "Nguyen Minh An", 25_000_000, 25, 3_000_000, "BALANCED", 9_000_000),
    ("C002", "Tran Thu Ha", 32_000_000, 25, 5_000_000, "CONSERVATIVE", 18_500_000),
    ("C003", "Le Quang Huy", 28_000_000, 28, 4_000_000, "BALANCED", 12_000_000),
    ("C004", "Pham Bao Linh", 20_000_000, 25, 3_000_000, "CONSERVATIVE", 7_200_000),
)


def _shift_month(value: date, months: int, day: int | None = None) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    target_day = min(day or value.day, calendar.monthrange(year, month)[1])
    return date(year, month, target_day)


def _tx(tx_id: str, customer_id: str, when: date, amount: int, category: Category, merchant: str) -> Transaction:
    return Transaction(
        transaction_id=tx_id,
        customer_id=customer_id,
        account_id=f"A-{customer_id}",
        transaction_date=when,
        amount=Decimal(amount),
        direction=Direction.DEBIT,
        merchant=merchant,
        description=f"Synthetic {category.value.lower()} transaction",
        category=category,
        transaction_type="CARD",
        created_at=datetime.combine(when, datetime.min.time()),
    )


def seed_core_banking_demo(session: Session, *, as_of: date = DEMO_AS_OF) -> None:
    created_at = datetime.combine(as_of, datetime.min.time())
    current_month = as_of.replace(day=1)
    previous_month = _shift_month(current_month, -1)
    for customer_id, name, income, salary_day, safe, risk, balance in CUSTOMERS:
        session.add(Customer(customer_id=customer_id, customer_name=name, monthly_income=Decimal(income), salary_day=salary_day, preferred_safe_balance=Decimal(safe), risk_preference=risk, created_at=created_at))
    session.flush()
    for customer_id, _, _, _, _, _, balance in CUSTOMERS:
        session.add(Account(account_id=f"A-{customer_id}", customer_id=customer_id, account_type="PAYMENT", available_balance=Decimal(balance), currency="VND", updated_at=created_at))
    session.flush()

    session.add_all([
        _tx("T-C001-PREV-001", "C001", previous_month.replace(day=10), 2_000_000, Category.SHOPPING, "Mall A"),
        _tx("T-C001-PREV-002", "C001", previous_month.replace(day=20), 1_500_000, Category.FOOD, "Supermarket"),
        _tx("T-C001-001", "C001", as_of, 750_000, Category.SHOPPING, "Mall A"),
        _tx("T-C001-002", "C001", as_of, 450_000, Category.FOOD, "Supermarket"),
        RecurringEvent(recurring_id="R-C001-RENT", customer_id="C001", name="Rent", category=Category.RENT, expected_amount=Decimal(6_000_000), expected_day=(as_of + timedelta(days=4)).day, frequency="MONTHLY", confidence=Decimal("0.98"), active_flag=True),
    ])
    for offset, amount in ((-3, 4_000_000), (-2, 3_800_000), (-1, 4_200_000)):
        when = _shift_month(current_month, offset, 15)
        session.add(_tx(f"T-C002-{when:%Y%m}", "C002", when, amount, Category.FOOD, "Food merchants"))
    session.add(_tx("T-C002-CURRENT", "C002", as_of, 5_000_000, Category.FOOD, "Food merchants"))
    session.add(SavingGoal(goal_id="G-C003-HOME", customer_id="C003", goal_name="Home deposit", target_amount=Decimal(100_000_000), current_amount=Decimal(22_000_000), start_date=_shift_month(current_month, -4), target_date=_shift_month(current_month, 8) - timedelta(days=1), monthly_contribution=Decimal(8_333_333), status="ACTIVE"))
    session.add(RecurringEvent(recurring_id="R-C004-RENT", customer_id="C004", name="Rent", category=Category.RENT, expected_amount=Decimal(8_000_000), expected_day=(as_of + timedelta(days=2)).day, frequency="MONTHLY", confidence=Decimal("0.99"), active_flag=True))
    session.add(Budget(budget_id="B-C002-FOOD", customer_id="C002", category=Category.FOOD, amount=Decimal(6_000_000), spent_amount=Decimal(5_000_000), alert_threshold=Decimal("0.80"), start_date=current_month, end_date=current_month.replace(day=calendar.monthrange(as_of.year, as_of.month)[1]), status="ACTIVE"))
    session.commit()


def seed_core_banking_if_empty(session: Session) -> bool:
    count = session.scalar(select(func.count()).select_from(Customer)) or 0
    if count:
        return False
    seed_core_banking_demo(session, as_of=datetime.now(BUSINESS_TIMEZONE).date())
    return True
