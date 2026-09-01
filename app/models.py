from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Direction(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Category(StrEnum):
    FOOD = "FOOD"
    SHOPPING = "SHOPPING"
    TRANSPORT = "TRANSPORT"
    RENT = "RENT"
    UTILITY = "UTILITY"
    ENTERTAINMENT = "ENTERTAINMENT"
    HEALTH = "HEALTH"
    SALARY = "SALARY"
    TRANSFER = "TRANSFER"
    OTHER = "OTHER"


class SignalType(StrEnum):
    CASHFLOW_RISK = "CASHFLOW_RISK"
    SPENDING_ANOMALY = "SPENDING_ANOMALY"
    UPCOMING_RECURRING = "UPCOMING_RECURRING"
    GOAL_DRIFT = "GOAL_DRIFT"
    BUDGET_THRESHOLD = "BUDGET_THRESHOLD"


class SignalStatus(StrEnum):
    NEW = "NEW"
    SHOWN = "SHOWN"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    ACTIONED = "ACTIONED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


money = Numeric(18, 2)


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(200))
    monthly_income: Mapped[Decimal] = mapped_column(money)
    salary_day: Mapped[int]
    preferred_safe_balance: Mapped[Decimal] = mapped_column(money)
    risk_preference: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    accounts: Mapped[list["Account"]] = relationship(cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    account_type: Mapped[str] = mapped_column(String(32))
    available_balance: Mapped[Decimal] = mapped_column(money)
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.account_id"), index=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(money)
    direction: Mapped[Direction] = mapped_column(Enum(Direction, native_enum=False))
    merchant: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category: Mapped[Category] = mapped_column(Enum(Category, native_enum=False), index=True)
    transaction_type: Mapped[str] = mapped_column(String(50))


class RecurringEvent(Base):
    __tablename__ = "recurring_events"

    recurring_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[Category] = mapped_column(Enum(Category, native_enum=False))
    expected_amount: Mapped[Decimal] = mapped_column(money)
    expected_day: Mapped[int]
    frequency: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)


class SavingGoal(Base):
    __tablename__ = "saving_goals"

    goal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    goal_name: Mapped[str] = mapped_column(String(200))
    target_amount: Mapped[Decimal] = mapped_column(money)
    current_amount: Mapped[Decimal] = mapped_column(money)
    start_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date] = mapped_column(Date)
    monthly_contribution: Mapped[Decimal] = mapped_column(money)
    status: Mapped[str] = mapped_column(String(32))


class Budget(Base):
    __tablename__ = "budgets"

    budget_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    category: Mapped[Category] = mapped_column(Enum(Category, native_enum=False))
    amount: Mapped[Decimal] = mapped_column(money)
    spent_amount: Mapped[Decimal] = mapped_column(money, default=0)
    alert_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))


class Reminder(Base):
    __tablename__ = "reminders"

    reminder_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    remind_at: Mapped[datetime] = mapped_column(DateTime)
    message: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RadarSignal(Base):
    __tablename__ = "radar_signals"

    signal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType, native_enum=False))
    severity: Mapped[str] = mapped_column(String(20))
    signal_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[SignalStatus] = mapped_column(Enum(SignalStatus, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentActionLog(Base):
    __tablename__ = "agent_action_logs"

    action_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("radar_signals.signal_id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(50))
    tool_name: Mapped[str] = mapped_column(String(100))
    tool_input: Mapped[dict[str, Any]] = mapped_column(JSON)
    policy_result: Mapped[dict[str, Any]] = mapped_column(JSON)
    confirmation_required: Mapped[bool] = mapped_column(Boolean)
    confirmation_status: Mapped[str] = mapped_column(String(32))
    tool_output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    action_status: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
