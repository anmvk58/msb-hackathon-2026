from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import (
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


CUSTOMERS = (
    ("C001", "Nguyen Minh An", 25_000_000, 25, 3_000_000, "BALANCED", 9_000_000),
    ("C002", "Tran Thu Ha", 32_000_000, 25, 5_000_000, "CONSERVATIVE", 18_500_000),
    ("C003", "Le Quang Huy", 28_000_000, 28, 4_000_000, "BALANCED", 12_000_000),
    ("C004", "Pham Bao Linh", 20_000_000, 25, 3_000_000, "CONSERVATIVE", 7_200_000),
)


def _money(value: int) -> Decimal:
    return Decimal(value)


def _tx(
    tx_id: str,
    customer_id: str,
    when: date,
    amount: int,
    category: Category,
    merchant: str,
    direction: Direction = Direction.DEBIT,
) -> Transaction:
    return Transaction(
        transaction_id=tx_id,
        customer_id=customer_id,
        account_id=f"A-{customer_id}",
        transaction_date=when,
        amount=_money(amount),
        direction=direction,
        merchant=merchant,
        description=f"Synthetic {category.value.lower()} transaction",
        category=category,
        transaction_type="CARD" if direction == Direction.DEBIT else "BANK_TRANSFER",
    )


def seed_demo(session: Session) -> None:
    created_at = datetime(2026, 9, 1, 0, 0, 0)
    for customer_id, name, income, salary_day, safe, risk, balance in CUSTOMERS:
        session.add(
            Customer(
                customer_id=customer_id,
                customer_name=name,
                monthly_income=_money(income),
                salary_day=salary_day,
                preferred_safe_balance=_money(safe),
                risk_preference=risk,
                created_at=created_at,
            )
        )
        session.add(
            Account(
                account_id=f"A-{customer_id}",
                customer_id=customer_id,
                account_type="PAYMENT",
                available_balance=_money(balance),
                currency="VND",
                updated_at=created_at,
            )
        )

    # C001 hero: upcoming rent plus an elevated current shopping run-rate.
    session.add_all(
        [
            _tx("T-C001-AUG-001", "C001", date(2026, 8, 10), 2_000_000, Category.SHOPPING, "Mall A"),
            _tx("T-C001-AUG-002", "C001", date(2026, 8, 20), 1_500_000, Category.FOOD, "Supermarket"),
            _tx("T-C001-001", "C001", date(2026, 9, 1), 750_000, Category.SHOPPING, "Mall A"),
            _tx("T-C001-002", "C001", date(2026, 9, 1), 450_000, Category.FOOD, "Supermarket"),
            RecurringEvent(
                recurring_id="R-C001-RENT", customer_id="C001", name="Rent",
                category=Category.RENT, expected_amount=_money(6_000_000), expected_day=5,
                frequency="MONTHLY", confidence=Decimal("0.98"), active_flag=True,
            ),
        ]
    )

    # C002: three-month FOOD baseline = 4.0m; current month = 5.0m (+25%).
    for month, amount in ((6, 4_000_000), (7, 3_800_000), (8, 4_200_000)):
        session.add(_tx(f"T-C002-{month}", "C002", date(2026, month, 15), amount, Category.FOOD, "Food merchants"))
    session.add(_tx("T-C002-SEP", "C002", date(2026, 9, 1), 5_000_000, Category.FOOD, "Food merchants"))

    # C003: 100m / 12-month goal, four months elapsed, only 22m accumulated.
    session.add(
        SavingGoal(
            goal_id="G-C003-HOME", customer_id="C003", goal_name="Home deposit",
            target_amount=_money(100_000_000), current_amount=_money(22_000_000),
            start_date=date(2026, 5, 1), target_date=date(2027, 4, 30),
            monthly_contribution=_money(8_333_333), status="ACTIVE",
        )
    )

    # C004: upcoming 8m rent exceeds the current liquid balance.
    session.add(
        RecurringEvent(
            recurring_id="R-C004-RENT", customer_id="C004", name="Rent",
            category=Category.RENT, expected_amount=_money(8_000_000), expected_day=3,
            frequency="MONTHLY", confidence=Decimal("0.99"), active_flag=True,
        )
    )

    # A seed budget proves schema portability without pre-creating the hero action.
    session.add(
        Budget(
            budget_id="B-C002-FOOD", customer_id="C002", category=Category.FOOD,
            amount=_money(6_000_000), spent_amount=_money(5_000_000),
            alert_threshold=Decimal("0.80"), start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30), status="ACTIVE",
        )
    )
    session.commit()
