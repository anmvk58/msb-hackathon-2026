from decimal import Decimal

from sqlalchemy.orm import Session

from app.banking import BankingGateway
from app.financial_engine import detect_spending_anomaly, detect_upcoming_recurring, forecast_cashflow, simulate_goal_scenarios
from app.tools.contracts import ConfirmationPolicy, RiskLevel
from app.tools.schemas import (
    CashflowInput, CashflowOutput, CreateBudgetInput, CreateBudgetOutput,
    CreateReminderInput, CreateReminderOutput, FinancialSnapshotInput,
    FinancialSnapshotOutput, GoalSimulationInput, GoalSimulationOutput,
    RecurringInput, RecurringOutput, SpendingAnomalyInput, SpendingAnomalyOutput,
    UpdateGoalInput, UpdateGoalOutput, PrepareFundingInput, PrepareFundingOutput,
)


class GatewayTool:
    def __init__(self, gateway: BankingGateway) -> None:
        self.gateway = gateway


class GetFinancialSnapshotTool(GatewayTool):
    name = "get_financial_snapshot"
    description = "Read the validated financial snapshot from Core Banking."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = FinancialSnapshotInput
    output_model = FinancialSnapshotOutput

    def execute(self, session: Session, arguments: FinancialSnapshotInput, *, idempotency_key: str | None = None) -> FinancialSnapshotOutput:
        del session
        context = self.gateway.get_financial_context(arguments.customer_id)
        currency = context.accounts[0].currency if context.accounts else "VND"
        return FinancialSnapshotOutput(
            customer_id=context.customer.customer_id, customer_name=context.customer.customer_name,
            monthly_income=context.customer.monthly_income, salary_day=context.customer.salary_day,
            safe_balance=context.customer.preferred_safe_balance,
            total_available_balance=sum((item.available_balance for item in context.accounts), Decimal(0)),
            currency=currency, active_goal_count=len(context.active_goals), active_budget_count=len(context.active_budgets),
        )


class DetectSpendingAnomalyTool(GatewayTool):
    name = "detect_spending_anomaly"
    description = "Calculate category spending anomalies from Core Banking transactions."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = SpendingAnomalyInput
    output_model = SpendingAnomalyOutput

    def execute(self, session: Session, arguments: SpendingAnomalyInput, *, idempotency_key: str | None = None) -> SpendingAnomalyOutput:
        del session, idempotency_key
        result = detect_spending_anomaly(self.gateway.get_financial_context(arguments.customer_id), arguments.customer_id, as_of=arguments.as_of)
        return SpendingAnomalyOutput.model_validate(result.model_dump())


class DetectRecurringTool(GatewayTool):
    name = "detect_upcoming_recurring"
    description = "Find recurring events from Core Banking due within a bounded window."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = RecurringInput
    output_model = RecurringOutput

    def execute(self, session: Session, arguments: RecurringInput, *, idempotency_key: str | None = None) -> RecurringOutput:
        del session, idempotency_key
        result = detect_upcoming_recurring(self.gateway.get_financial_context(arguments.customer_id), arguments.customer_id, as_of=arguments.as_of, window_days=arguments.window_days)
        return RecurringOutput.model_validate(result.model_dump())


class ForecastCashflowTool(GatewayTool):
    name = "forecast_cashflow"
    description = "Produce a deterministic forecast from Core Banking evidence."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = CashflowInput
    output_model = CashflowOutput

    def execute(self, session: Session, arguments: CashflowInput, *, idempotency_key: str | None = None) -> CashflowOutput:
        del session, idempotency_key
        result = forecast_cashflow(self.gateway.get_financial_context(arguments.customer_id), arguments.customer_id, as_of=arguments.as_of, forecast_until=arguments.forecast_until)
        return CashflowOutput.model_validate(result.model_dump())


class SimulateGoalScenariosTool(GatewayTool):
    name = "simulate_goal_scenarios"
    description = "Calculate goal recovery scenarios from Core Banking context."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = GoalSimulationInput
    output_model = GoalSimulationOutput

    def execute(self, session: Session, arguments: GoalSimulationInput, *, idempotency_key: str | None = None) -> GoalSimulationOutput:
        del session, idempotency_key
        result = simulate_goal_scenarios(self.gateway.get_financial_context(arguments.customer_id), arguments.customer_id, as_of=arguments.as_of, goal_id=arguments.goal_id)
        return GoalSimulationOutput.model_validate(result.model_dump())


class CreateBudgetTool(GatewayTool):
    name = "create_budget"
    description = "Create a validated budget in Core Banking."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.REQUIRED
    input_model = CreateBudgetInput
    output_model = CreateBudgetOutput

    def execute(self, session: Session, arguments: CreateBudgetInput, *, idempotency_key: str | None = None) -> CreateBudgetOutput:
        del session
        result = self.gateway.create_budget(arguments.customer_id, arguments.model_dump(mode="json", exclude={"customer_id"}), idempotency_key=idempotency_key)
        return CreateBudgetOutput(status="SUCCESS", budget_id=result["budget_id"], customer_id=result["customer_id"], category=result["category"], amount=result["amount"])


class CreateReminderTool(GatewayTool):
    name = "create_reminder"
    description = "Create a customer reminder in Core Banking."
    risk_level = RiskLevel.LOW
    confirmation_policy = ConfirmationPolicy.NONE
    input_model = CreateReminderInput
    output_model = CreateReminderOutput

    def execute(self, session: Session, arguments: CreateReminderInput, *, idempotency_key: str | None = None) -> CreateReminderOutput:
        del session
        result = self.gateway.create_reminder(arguments.customer_id, arguments.model_dump(mode="json", exclude={"customer_id"}), idempotency_key=idempotency_key)
        return CreateReminderOutput(status="SUCCESS", reminder_id=result["reminder_id"], customer_id=result["customer_id"], remind_at=result["remind_at"])


class UpdateGoalTool(GatewayTool):
    name = "update_goal"
    description = "Update an active saving goal in Core Banking."
    risk_level = RiskLevel.MEDIUM
    confirmation_policy = ConfirmationPolicy.EXPLICIT
    input_model = UpdateGoalInput
    output_model = UpdateGoalOutput

    def execute(self, session: Session, arguments: UpdateGoalInput, *, idempotency_key: str | None = None) -> UpdateGoalOutput:
        del session
        payload = arguments.model_dump(mode="json", exclude={"customer_id", "goal_id"}, exclude_none=True)
        result = self.gateway.update_goal(arguments.customer_id, arguments.goal_id, payload, idempotency_key=idempotency_key)
        return UpdateGoalOutput(status="SUCCESS", goal_id=result["goal_id"], customer_id=result["customer_id"], monthly_contribution=result["monthly_contribution"], target_date=result["target_date"])


class PrepareFundingOptionTool(GatewayTool):
    name = "prepare_funding_option"
    description = "Prepare a verified funding option for explicit customer confirmation."
    risk_level = RiskLevel.MEDIUM
    confirmation_policy = ConfirmationPolicy.EXPLICIT
    input_model = PrepareFundingInput
    output_model = PrepareFundingOutput

    def execute(self, session: Session, arguments: PrepareFundingInput, *, idempotency_key: str | None = None) -> PrepareFundingOutput:
        del session
        context = self.gateway.get_financial_context(arguments.customer_id)
        valid = {
            "OVERDRAFT": {x.facility_id: x.credit_limit - x.used_amount for x in context.overdraft_facilities if x.status == "ACTIVE"},
            "PARTIAL_SAVING_WITHDRAWAL": {x.deposit_id: x.available_withdrawal_amount for x in context.term_deposits if x.status == "ACTIVE" and x.partial_withdrawal_allowed},
            "SHORT_TERM_LOAN": {x.offer_id: x.approved_limit for x in context.preapproved_loan_offers if x.status == "ACTIVE" and x.eligibility_status == "ELIGIBLE"},
        }
        available = valid[arguments.option_type].get(arguments.reference_id)
        if available is None or arguments.amount > available:
            raise ValueError("Funding option is unavailable or insufficient")
        if arguments.option_type == "OVERDRAFT":
            result = self.gateway.draw_overdraft(arguments.customer_id, arguments.reference_id, str(arguments.amount), idempotency_key=idempotency_key)
            return PrepareFundingOutput(status=result["status"], **arguments.model_dump(), account_available_balance=result["account_available_balance"], used_amount=result["used_amount"], available_limit=result["available_limit"], transaction_id=result["transaction_id"])
        return PrepareFundingOutput(status="PREPARED", **arguments.model_dump())


def build_mvp_tools(gateway: BankingGateway) -> tuple[GatewayTool, ...]:
    return (
        GetFinancialSnapshotTool(gateway), DetectSpendingAnomalyTool(gateway),
        DetectRecurringTool(gateway), ForecastCashflowTool(gateway),
        SimulateGoalScenariosTool(gateway), CreateBudgetTool(gateway),
        CreateReminderTool(gateway), UpdateGoalTool(gateway),
        PrepareFundingOptionTool(gateway),
    )
