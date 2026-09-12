from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models import Category, Direction


class CustomerData(BaseModel):
    customer_id: str
    customer_name: str
    monthly_income: Decimal
    salary_day: int
    preferred_safe_balance: Decimal
    risk_preference: str


class AccountData(BaseModel):
    account_id: str
    customer_id: str
    account_type: str
    available_balance: Decimal
    currency: str
    updated_at: datetime


class TransactionData(BaseModel):
    transaction_id: str
    customer_id: str
    account_id: str
    transaction_date: date
    amount: Decimal
    direction: Direction
    merchant: str | None
    description: str | None
    category: Category
    transaction_type: str
    created_at: datetime


class RecurringEventData(BaseModel):
    recurring_id: str
    customer_id: str
    name: str
    category: Category
    expected_amount: Decimal
    expected_day: int
    frequency: str
    confidence: Decimal
    active_flag: bool


class BudgetData(BaseModel):
    budget_id: str
    customer_id: str
    category: Category
    amount: Decimal
    spent_amount: Decimal
    alert_threshold: Decimal
    start_date: date
    end_date: date
    status: str


class GoalData(BaseModel):
    goal_id: str
    customer_id: str
    goal_name: str
    target_amount: Decimal
    current_amount: Decimal
    start_date: date
    target_date: date
    monthly_contribution: Decimal
    status: str


class OverdraftData(BaseModel):
    facility_id: str; customer_id: str; account_id: str
    credit_limit: Decimal; used_amount: Decimal
    annual_interest_rate: Decimal; expires_at: date; status: str


class TermDepositData(BaseModel):
    deposit_id: str; customer_id: str; product_name: str
    current_balance: Decimal; available_withdrawal_amount: Decimal
    interest_rate: Decimal; early_withdrawal_rate: Decimal
    opened_at: date; maturity_date: date
    partial_withdrawal_allowed: bool; status: str


class CreditCardData(BaseModel):
    card_id: str; customer_id: str; masked_number: str; product_name: str
    credit_limit: Decimal; outstanding_amount: Decimal
    payment_due_day: int; status: str


class LoanOfferData(BaseModel):
    offer_id: str; customer_id: str; product_code: str; display_name: str
    approved_limit: Decimal; minimum_amount: Decimal
    annual_interest_rate: Decimal; term_months: int; valid_until: date
    eligibility_status: str; status: str


class FinancialContext(BaseModel):
    customer: CustomerData
    accounts: list[AccountData]
    recent_transactions: list[TransactionData]
    recurring_events: list[RecurringEventData]
    active_budgets: list[BudgetData]
    active_goals: list[GoalData]
    overdraft_facilities: list[OverdraftData] = []
    term_deposits: list[TermDepositData] = []
    credit_cards: list[CreditCardData] = []
    preapproved_loan_offers: list[LoanOfferData] = []
    generated_at: datetime
