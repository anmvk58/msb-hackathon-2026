from datetime import date
from decimal import Decimal, ROUND_CEILING

from app.banking.schemas import FinancialContext, GoalData
from app.financial_engine.schemas import GoalGapResult, GoalScenario, GoalSimulationResult
from app.financial_engine.utils import add_months, money, months_between_ceiling, ratio


def _get_goal(context: FinancialContext, customer_id: str, goal_id: str | None) -> GoalData:
    goals = [
        item for item in context.active_goals
        if item.customer_id == customer_id and item.status == "ACTIVE"
        and (goal_id is None or item.goal_id == goal_id)
    ]
    goal = min(goals, key=lambda item: item.target_date) if goals else None
    if goal is None:
        raise ValueError(f"No active saving goal for customer {customer_id}")
    return goal


def calculate_goal_gap(
    context: FinancialContext,
    customer_id: str,
    *,
    as_of: date,
    goal_id: str | None = None,
) -> GoalGapResult:
    goal = _get_goal(context, customer_id, goal_id)
    total_days = max((goal.target_date - goal.start_date).days, 1)
    elapsed_days = min(max((as_of - goal.start_date).days, 0), total_days)
    expected_ratio = Decimal(elapsed_days) / Decimal(total_days)
    expected = money(goal.target_amount * expected_ratio)
    actual_ratio = (
        goal.current_amount / goal.target_amount if goal.target_amount else Decimal(0)
    )
    gap = money(goal.current_amount - expected)
    return GoalGapResult(
        customer_id=customer_id,
        goal_id=goal.goal_id,
        as_of=as_of,
        target_amount=money(goal.target_amount),
        actual_progress=money(goal.current_amount),
        expected_progress=expected,
        gap=gap,
        progress_ratio=ratio(actual_ratio),
        expected_ratio=ratio(expected_ratio),
        is_drifting=gap < 0,
    )


def simulate_goal_scenarios(
    context: FinancialContext,
    customer_id: str,
    *,
    as_of: date,
    goal_id: str | None = None,
) -> GoalSimulationResult:
    goal = _get_goal(context, customer_id, goal_id)
    gap = calculate_goal_gap(context, customer_id, as_of=as_of, goal_id=goal.goal_id)
    remaining = max(goal.target_amount - goal.current_amount, Decimal(0))
    months_remaining = months_between_ceiling(as_of, goal.target_date)
    required_contribution = money(remaining / Decimal(months_remaining))
    scenarios = [
        GoalScenario(
            scenario_id="INCREASE_CONTRIBUTION",
            action_type="INCREASE_CONTRIBUTION",
            monthly_contribution=required_contribution,
            target_date=goal.target_date,
            months_remaining=months_remaining,
            parameters={
                "increase_by": money(
                    max(required_contribution - goal.monthly_contribution, Decimal(0))
                )
            },
        )
    ]
    if goal.monthly_contribution > 0:
        extension_months = int(
            (remaining / goal.monthly_contribution).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        extended_date = add_months(as_of, extension_months)
        scenarios.append(
            GoalScenario(
                scenario_id="EXTEND_DEADLINE",
                action_type="EXTEND_DEADLINE",
                monthly_contribution=money(goal.monthly_contribution),
                target_date=extended_date,
                months_remaining=extension_months,
                parameters={
                    "extension_months": max(extension_months - months_remaining, 0)
                },
            )
        )
    return GoalSimulationResult(
        customer_id=customer_id,
        goal_id=goal.goal_id,
        gap_analysis=gap,
        scenarios=scenarios,
    )
