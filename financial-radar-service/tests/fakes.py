from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from app.banking.schemas import (
    AccountData,
    BudgetData,
    CustomerData,
    FinancialContext,
    GoalData,
    RecurringEventData,
    TransactionData,
)
from app.models import Category, Direction
from app.tools.contracts import ToolExecutionError


def _transaction(tx_id: str, customer_id: str, when: date, amount: int, category: Category) -> TransactionData:
    return TransactionData(
        transaction_id=tx_id, customer_id=customer_id, account_id=f"A-{customer_id}",
        transaction_date=when, amount=Decimal(amount), direction=Direction.DEBIT,
        merchant="Demo merchant", description="Synthetic transaction",
        category=category, transaction_type="CARD", created_at=datetime(2026, 9, 1),
    )


class FakeBankingGateway:
    def __init__(self) -> None:
        profiles = {
            "C001": ("Nguyen Minh An", 25_000_000, 25, 3_000_000, "BALANCED", 9_000_000),
            "C002": ("Tran Thu Ha", 32_000_000, 25, 5_000_000, "CONSERVATIVE", 18_500_000),
            "C003": ("Le Quang Huy", 28_000_000, 28, 4_000_000, "BALANCED", 12_000_000),
            "C004": ("Pham Bao Linh", 20_000_000, 25, 3_000_000, "CONSERVATIVE", 7_200_000),
        }
        self.contexts: dict[str, FinancialContext] = {}
        for customer_id, (name, income, salary_day, safe, risk, balance) in profiles.items():
            self.contexts[customer_id] = FinancialContext(
                customer=CustomerData(customer_id=customer_id, customer_name=name, monthly_income=Decimal(income), salary_day=salary_day, preferred_safe_balance=Decimal(safe), risk_preference=risk),
                accounts=[AccountData(account_id=f"A-{customer_id}", customer_id=customer_id, account_type="PAYMENT", available_balance=Decimal(f"{balance}.00"), currency="VND", updated_at=datetime(2026, 9, 1))],
                recent_transactions=[], recurring_events=[], active_budgets=[], active_goals=[], generated_at=datetime(2026, 9, 1),
            )
        self.contexts["C001"].recent_transactions = [
            _transaction("T-C001-AUG-001", "C001", date(2026, 8, 10), 2_000_000, Category.SHOPPING),
            _transaction("T-C001-AUG-002", "C001", date(2026, 8, 20), 1_500_000, Category.FOOD),
            _transaction("T-C001-001", "C001", date(2026, 9, 1), 750_000, Category.SHOPPING),
            _transaction("T-C001-002", "C001", date(2026, 9, 1), 450_000, Category.FOOD),
        ]
        self.contexts["C001"].recurring_events = [RecurringEventData(recurring_id="R-C001-RENT", customer_id="C001", name="Rent", category=Category.RENT, expected_amount=Decimal(6_000_000), expected_day=5, frequency="MONTHLY", confidence=Decimal("0.98"), active_flag=True)]
        self.contexts["C002"].recent_transactions = [
            _transaction("T-C002-6", "C002", date(2026, 6, 15), 4_000_000, Category.FOOD),
            _transaction("T-C002-7", "C002", date(2026, 7, 15), 3_800_000, Category.FOOD),
            _transaction("T-C002-8", "C002", date(2026, 8, 15), 4_200_000, Category.FOOD),
            _transaction("T-C002-SEP", "C002", date(2026, 9, 1), 5_000_000, Category.FOOD),
        ]
        self.contexts["C002"].active_budgets = [BudgetData(budget_id="B-C002-FOOD", customer_id="C002", category=Category.FOOD, amount=Decimal(6_000_000), spent_amount=Decimal(5_000_000), alert_threshold=Decimal("0.8"), start_date=date(2026, 9, 1), end_date=date(2026, 9, 30), status="ACTIVE")]
        self.contexts["C003"].active_goals = [GoalData(goal_id="G-C003-HOME", customer_id="C003", goal_name="Home deposit", target_amount=Decimal(100_000_000), current_amount=Decimal(22_000_000), start_date=date(2026, 5, 1), target_date=date(2027, 4, 30), monthly_contribution=Decimal(8_333_333), status="ACTIVE")]
        self.contexts["C004"].recurring_events = [RecurringEventData(recurring_id="R-C004-RENT", customer_id="C004", name="Rent", category=Category.RENT, expected_amount=Decimal(8_000_000), expected_day=3, frequency="MONTHLY", confidence=Decimal("0.99"), active_flag=True)]
        self.reminders: list[dict[str, Any]] = []
        self.idempotent_results: dict[str, dict[str, Any]] = {}

    def get_financial_context(self, customer_id: str) -> FinancialContext:
        try:
            return self.contexts[customer_id]
        except KeyError as error:
            raise ToolExecutionError(f"Core Banking returned 404: Customer not found") from error

    def create_budget(self, customer_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]:
        if idempotency_key and idempotency_key in self.idempotent_results:
            return self.idempotent_results[idempotency_key]
        context = self.get_financial_context(customer_id)
        category = Category(payload["category"])
        start_date = date.fromisoformat(payload["start_date"])
        end_date = date.fromisoformat(payload["end_date"])
        if any(item.category == category and item.start_date <= end_date and item.end_date >= start_date for item in context.active_budgets):
            raise ToolExecutionError(f"Core Banking returned 409: An active overlapping {category.value} budget already exists")
        result = {"budget_id": f"B-{uuid4().hex[:12].upper()}", "customer_id": customer_id, **payload, "spent_amount": "0", "status": "ACTIVE"}
        context.active_budgets.append(BudgetData.model_validate(result))
        if idempotency_key:
            self.idempotent_results[idempotency_key] = result
        return result

    def create_reminder(self, customer_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]:
        if idempotency_key and idempotency_key in self.idempotent_results:
            return self.idempotent_results[idempotency_key]
        self.get_financial_context(customer_id)
        result = {"reminder_id": f"RM-{uuid4().hex[:12].upper()}", "customer_id": customer_id, **payload, "status": "ACTIVE", "created_at": datetime.utcnow().isoformat()}
        self.reminders.append(result)
        if idempotency_key:
            self.idempotent_results[idempotency_key] = result
        return result

    def update_goal(self, customer_id: str, goal_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]:
        if idempotency_key and idempotency_key in self.idempotent_results:
            return self.idempotent_results[idempotency_key]
        goal = next((item for item in self.get_financial_context(customer_id).active_goals if item.goal_id == goal_id), None)
        if goal is None:
            raise ToolExecutionError("Core Banking returned 404: Active goal not found")
        if payload.get("monthly_contribution") is not None:
            goal.monthly_contribution = Decimal(str(payload["monthly_contribution"]))
        if payload.get("target_date") is not None:
            goal.target_date = date.fromisoformat(payload["target_date"])
        result = goal.model_dump(mode="json")
        if idempotency_key:
            self.idempotent_results[idempotency_key] = result
        return result
