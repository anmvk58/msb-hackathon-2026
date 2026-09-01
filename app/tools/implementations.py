from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.financial_engine import (
    detect_spending_anomaly,
    detect_upcoming_recurring,
    forecast_cashflow,
    simulate_goal_scenarios,
)
from app.models import Account, Budget, Customer, Reminder, SavingGoal
from app.tools.contracts import ConfirmationPolicy, RiskLevel, ToolExecutionError
from app.tools.schemas import (
    CashflowInput,
    CashflowOutput,
    CreateBudgetInput,
    CreateBudgetOutput,
    CreateReminderInput,
    CreateReminderOutput,
    FinancialSnapshotInput,
    FinancialSnapshotOutput,
    GoalSimulationInput,
    GoalSimulationOutput,
    RecurringInput,
    RecurringOutput,
    SpendingAnomalyInput,
    SpendingAnomalyOutput,
    UpdateGoalInput,
    UpdateGoalOutput,
)


def _ensure_customer(session: Session, customer_id: str) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise ToolExecutionError(f"Unknown customer_id: {customer_id}")
    return customer


class GetFinancialSnapshotTool:
    name = "get_financial_snapshot"
    description = "Read the validated financial snapshot for one customer."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = FinancialSnapshotInput
    output_model = FinancialSnapshotOutput

    def execute(self, session: Session, arguments: FinancialSnapshotInput) -> FinancialSnapshotOutput:
        customer = _ensure_customer(session, arguments.customer_id)
        total_balance = session.scalar(
            select(func.coalesce(func.sum(Account.available_balance), 0)).where(
                Account.customer_id == arguments.customer_id
            )
        )
        goal_count = session.scalar(
            select(func.count()).select_from(SavingGoal).where(
                SavingGoal.customer_id == arguments.customer_id,
                SavingGoal.status == "ACTIVE",
            )
        )
        budget_count = session.scalar(
            select(func.count()).select_from(Budget).where(
                Budget.customer_id == arguments.customer_id, Budget.status == "ACTIVE"
            )
        )
        currency = session.scalar(
            select(Account.currency).where(Account.customer_id == arguments.customer_id).limit(1)
        ) or "VND"
        return FinancialSnapshotOutput(
            customer_id=customer.customer_id,
            customer_name=customer.customer_name,
            monthly_income=customer.monthly_income,
            safe_balance=customer.preferred_safe_balance,
            total_available_balance=Decimal(total_balance or 0),
            currency=currency,
            active_goal_count=int(goal_count or 0),
            active_budget_count=int(budget_count or 0),
        )


class DetectSpendingAnomalyTool:
    name = "detect_spending_anomaly"
    description = "Calculate category spending anomalies from transaction evidence."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = SpendingAnomalyInput
    output_model = SpendingAnomalyOutput

    def execute(self, session: Session, arguments: SpendingAnomalyInput) -> SpendingAnomalyOutput:
        _ensure_customer(session, arguments.customer_id)
        result = detect_spending_anomaly(
            session, arguments.customer_id, as_of=arguments.as_of
        )
        return SpendingAnomalyOutput.model_validate(result.model_dump())


class DetectRecurringTool:
    name = "detect_upcoming_recurring"
    description = "Find recurring events due within a bounded future window."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = RecurringInput
    output_model = RecurringOutput

    def execute(self, session: Session, arguments: RecurringInput) -> RecurringOutput:
        _ensure_customer(session, arguments.customer_id)
        result = detect_upcoming_recurring(
            session,
            arguments.customer_id,
            as_of=arguments.as_of,
            window_days=arguments.window_days,
        )
        return RecurringOutput.model_validate(result.model_dump())


class ForecastCashflowTool:
    name = "forecast_cashflow"
    description = "Produce a deterministic cashflow forecast with evidence drivers."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = CashflowInput
    output_model = CashflowOutput

    def execute(self, session: Session, arguments: CashflowInput) -> CashflowOutput:
        result = forecast_cashflow(
            session,
            arguments.customer_id,
            as_of=arguments.as_of,
            forecast_until=arguments.forecast_until,
        )
        return CashflowOutput.model_validate(result.model_dump())


class SimulateGoalScenariosTool:
    name = "simulate_goal_scenarios"
    description = "Calculate valid goal recovery scenarios without mutating the goal."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = GoalSimulationInput
    output_model = GoalSimulationOutput

    def execute(self, session: Session, arguments: GoalSimulationInput) -> GoalSimulationOutput:
        result = simulate_goal_scenarios(
            session,
            arguments.customer_id,
            as_of=arguments.as_of,
            goal_id=arguments.goal_id,
        )
        return GoalSimulationOutput.model_validate(result.model_dump())


class CreateBudgetTool:
    name = "create_budget"
    description = "Create a validated category spending budget."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.REQUIRED
    input_model = CreateBudgetInput
    output_model = CreateBudgetOutput

    def execute(self, session: Session, arguments: CreateBudgetInput) -> CreateBudgetOutput:
        _ensure_customer(session, arguments.customer_id)
        duplicate = session.scalar(
            select(Budget.budget_id).where(
                Budget.customer_id == arguments.customer_id,
                Budget.category == arguments.category,
                Budget.status == "ACTIVE",
                Budget.start_date <= arguments.end_date,
                Budget.end_date >= arguments.start_date,
            ).limit(1)
        )
        if duplicate:
            raise ToolExecutionError(
                f"An active overlapping {arguments.category.value} budget already exists"
            )
        budget_id = f"B-{uuid4().hex[:12].upper()}"
        budget = Budget(
            budget_id=budget_id,
            customer_id=arguments.customer_id,
            category=arguments.category,
            amount=arguments.amount,
            spent_amount=Decimal(0),
            alert_threshold=arguments.alert_threshold,
            start_date=arguments.start_date,
            end_date=arguments.end_date,
            status="ACTIVE",
        )
        session.add(budget)
        session.commit()
        return CreateBudgetOutput(
            status="SUCCESS",
            budget_id=budget_id,
            customer_id=arguments.customer_id,
            category=arguments.category,
            amount=arguments.amount,
        )


class CreateReminderTool:
    name = "create_reminder"
    description = "Create a customer reminder."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = CreateReminderInput
    output_model = CreateReminderOutput

    def execute(self, session: Session, arguments: CreateReminderInput) -> CreateReminderOutput:
        _ensure_customer(session, arguments.customer_id)
        reminder_id = f"RM-{uuid4().hex[:12].upper()}"
        session.add(
            Reminder(
                reminder_id=reminder_id,
                customer_id=arguments.customer_id,
                title=arguments.title,
                remind_at=arguments.remind_at,
                message=arguments.message,
                status="ACTIVE",
                created_at=datetime.utcnow(),
            )
        )
        session.commit()
        return CreateReminderOutput(
            status="SUCCESS",
            reminder_id=reminder_id,
            customer_id=arguments.customer_id,
            remind_at=arguments.remind_at,
        )


class UpdateGoalTool:
    name = "update_goal"
    description = "Update validated contribution or deadline fields on an active goal."
    risk_level = RiskLevel.MEDIUM
    confirmation_policy = ConfirmationPolicy.EXPLICIT
    input_model = UpdateGoalInput
    output_model = UpdateGoalOutput

    def execute(self, session: Session, arguments: UpdateGoalInput) -> UpdateGoalOutput:
        _ensure_customer(session, arguments.customer_id)
        goal = session.get(SavingGoal, arguments.goal_id)
        if goal is None or goal.customer_id != arguments.customer_id or goal.status != "ACTIVE":
            raise ToolExecutionError("Active goal not found for customer")
        if arguments.target_date is not None:
            if arguments.target_date <= goal.start_date:
                raise ToolExecutionError("target_date must be after goal start_date")
            goal.target_date = arguments.target_date
        if arguments.monthly_contribution is not None:
            goal.monthly_contribution = arguments.monthly_contribution
        session.commit()
        return UpdateGoalOutput(
            status="SUCCESS",
            goal_id=goal.goal_id,
            customer_id=goal.customer_id,
            monthly_contribution=goal.monthly_contribution,
            target_date=goal.target_date,
        )


MVP_TOOLS = (
    GetFinancialSnapshotTool(),
    DetectSpendingAnomalyTool(),
    DetectRecurringTool(),
    ForecastCashflowTool(),
    SimulateGoalScenariosTool(),
    CreateBudgetTool(),
    CreateReminderTool(),
    UpdateGoalTool(),
)
