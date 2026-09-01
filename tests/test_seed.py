from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Account, Category, Customer, RecurringEvent, SavingGoal, Transaction
from app.seed.data import seed_demo


def test_seed_contains_four_personas(session: Session) -> None:
    ids = session.scalars(select(Customer.customer_id).order_by(Customer.customer_id)).all()
    assert ids == ["C001", "C002", "C003", "C004"]


def test_c001_hero_inputs_are_data_driven(session: Session) -> None:
    customer = session.get(Customer, "C001")
    account = session.get(Account, "A-C001")
    rent = session.get(RecurringEvent, "R-C001-RENT")
    assert customer is not None and account is not None and rent is not None
    assert customer.monthly_income == Decimal("25000000")
    assert customer.preferred_safe_balance == Decimal("3000000")
    assert account.available_balance == Decimal("9000000")
    assert rent.expected_amount == Decimal("6000000")


def test_c002_has_three_month_food_baseline_and_current_spend(session: Session) -> None:
    rows = session.execute(
        select(Transaction.transaction_date, Transaction.amount)
        .where(Transaction.customer_id == "C002", Transaction.category == Category.FOOD)
        .order_by(Transaction.transaction_date)
    ).all()
    assert [amount for _, amount in rows] == [
        Decimal("4000000"), Decimal("3800000"), Decimal("4200000"), Decimal("5000000")
    ]


def test_c003_goal_persona(session: Session) -> None:
    goal = session.get(SavingGoal, "G-C003-HOME")
    assert goal is not None
    assert goal.target_amount == Decimal("100000000")
    assert goal.current_amount == Decimal("22000000")
    assert (goal.target_date - goal.start_date).days == 364


def test_c004_upcoming_rent_exceeds_balance(session: Session) -> None:
    account = session.get(Account, "A-C004")
    rent = session.get(RecurringEvent, "R-C004-RENT")
    assert account is not None and rent is not None
    assert rent.expected_day == 3
    assert rent.expected_amount > account.available_balance


def test_seed_is_reproducible_after_schema_reset(session: Session) -> None:
    first_count = session.scalar(select(func.count()).select_from(Transaction))
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    seed_demo(session)
    second_count = session.scalar(select(func.count()).select_from(Transaction))
    assert first_count == second_count == 8
