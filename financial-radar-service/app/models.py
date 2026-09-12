from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

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


class RecommendationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SELECTED = "SELECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ScanTrigger(StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class ScanStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RadarScanRun(Base):
    __tablename__ = "radar_scan_runs"
    __table_args__ = (
        Index("ix_radar_scan_customer_completed", "customer_id", "status", "completed_at"),
    )

    scan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    trigger_type: Mapped[ScanTrigger] = mapped_column(Enum(ScanTrigger, native_enum=False), index=True)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus, native_enum=False), index=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alert_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RadarSignal(Base):
    __tablename__ = "radar_signals"

    signal_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    signal_type: Mapped[SignalType] = mapped_column(Enum(SignalType, native_enum=False))
    severity: Mapped[str] = mapped_column(String(20))
    signal_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[SignalStatus] = mapped_column(Enum(SignalStatus, native_enum=False))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentRecommendation(Base):
    __tablename__ = "agent_recommendations"

    recommendation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("radar_signals.signal_id"), nullable=True)
    problem: Mapped[str] = mapped_column(String(500))
    severity: Mapped[str] = mapped_column(String(20))
    recommendation_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus, native_enum=False), default=RecommendationStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentActionLog(Base):
    __tablename__ = "agent_action_logs"

    action_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    signal_id: Mapped[str | None] = mapped_column(ForeignKey("radar_signals.signal_id"), nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_recommendations.recommendation_id"), nullable=True, index=True
    )
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
