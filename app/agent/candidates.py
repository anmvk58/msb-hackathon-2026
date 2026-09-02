from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.agent.state import CandidateActionPlan
from app.financial_engine import calculate_budget_guardrail
from app.models import Category, SignalType


class CandidateActionGenerator:
    """Creates the only tool names and financial parameters an LLM may select."""

    def generate(
        self,
        session: Session,
        *,
        customer_id: str,
        as_of: date,
        primary_type: SignalType,
        analysis: dict[str, Any],
    ) -> CandidateActionPlan:
        if primary_type == SignalType.CASHFLOW_RISK:
            guardrail = calculate_budget_guardrail(
                session, customer_id, Category.SHOPPING
            )
            summary = (
                f"Số dư dự báo là {_vnd(analysis['forecast_balance'])} VND, thấp hơn "
                f"mức an toàn {_vnd(analysis['safe_balance'])} VND."
            )
            return CandidateActionPlan.model_validate(
                {
                    "problem": "CASHFLOW_RISK",
                    "severity": analysis["risk_level"],
                    "summary_hint": summary,
                    "reasoning_hint": "Ưu tiên xử lý driver chi tiêu tùy ý lớn nhất.",
                    "evidence": [
                        {
                            "source": "forecast_cashflow",
                            "metric": "forecast_balance",
                            "value": analysis["forecast_balance"],
                            "context": {
                                "safe_balance": analysis["safe_balance"],
                                "gap": analysis["gap"],
                                "confidence": analysis["confidence"],
                            },
                        },
                        *[
                            {
                                "source": "forecast_cashflow",
                                "metric": driver["type"],
                                "value": driver["impact"],
                                "context": driver["evidence"],
                            }
                            for driver in analysis["drivers"]
                        ],
                    ],
                    "candidate_options": [
                        {
                            "option_id": "A",
                            "title": "Tạo ngân sách mua sắm",
                            "description": "Đặt giới hạn SHOPPING và cảnh báo ở mức 80%.",
                            "action_type": "create_budget",
                            "parameters": {
                                "customer_id": customer_id,
                                "category": "SHOPPING",
                                "amount": str(guardrail.recommended_amount),
                                "alert_threshold": "0.8",
                                "start_date": as_of.isoformat(),
                                "end_date": as_of.replace(day=28).isoformat(),
                            },
                            "expected_impact": "Giảm tốc độ chi tiêu tùy ý trong tháng.",
                        },
                        {
                            "option_id": "B",
                            "title": "Tạo nhắc nhở trước khoản định kỳ",
                            "description": "Nhắc kiểm tra số dư trước ngày đến hạn.",
                            "action_type": "create_reminder",
                            "parameters": {
                                "customer_id": customer_id,
                                "title": "Kiểm tra số dư trước khoản định kỳ",
                                "remind_at": datetime.combine(as_of, time(9)).isoformat(),
                                "message": "Kiểm tra số dư và chi tiêu trước khoản định kỳ.",
                            },
                            "expected_impact": "Chủ động điều chỉnh trước ngày thanh toán.",
                        },
                    ],
                    "default_option_id": "A",
                }
            )
        if primary_type == SignalType.SPENDING_ANOMALY:
            anomaly = analysis["anomalies"][0]
            guardrail = calculate_budget_guardrail(
                session, customer_id, Category(anomaly["category"])
            )
            return CandidateActionPlan.model_validate(
                {
                    "problem": "SPENDING_ANOMALY",
                    "severity": "MEDIUM",
                    "summary_hint": f"Chi tiêu {anomaly['category']} tăng {_percent(anomaly['change_pct'])} so với baseline.",
                    "reasoning_hint": "Guardrail được Financial Engine suy ra từ thu nhập.",
                    "evidence": [
                        {
                            "source": "detect_spending_anomaly",
                            "metric": "change_pct",
                            "value": anomaly["change_pct"],
                            "context": anomaly,
                        }
                    ],
                    "candidate_options": [
                        {
                            "option_id": "A",
                            "title": "Tạo ngân sách danh mục",
                            "description": "Áp dụng guardrail theo thu nhập.",
                            "action_type": "create_budget",
                            "parameters": {
                                "customer_id": customer_id,
                                "category": anomaly["category"],
                                "amount": str(guardrail.recommended_amount),
                                "alert_threshold": "0.8",
                                "start_date": as_of.isoformat(),
                                "end_date": as_of.replace(day=28).isoformat(),
                            },
                            "expected_impact": "Hạn chế chi vượt baseline.",
                        }
                    ],
                    "default_option_id": "A",
                }
            )
        if primary_type == SignalType.GOAL_DRIFT:
            options = []
            for index, scenario in enumerate(analysis["scenarios"]):
                parameters = {
                    "customer_id": customer_id,
                    "goal_id": analysis["goal_id"],
                }
                if scenario["action_type"] == "INCREASE_CONTRIBUTION":
                    parameters["monthly_contribution"] = scenario["monthly_contribution"]
                else:
                    parameters["target_date"] = scenario["target_date"]
                options.append(
                    {
                        "option_id": chr(ord("A") + index),
                        "title": "Tăng đóng góp" if index == 0 else "Gia hạn mục tiêu",
                        "description": "Kịch bản deterministic từ Financial Engine.",
                        "action_type": "update_goal",
                        "parameters": parameters,
                        "expected_impact": "Đưa lộ trình về trạng thái khả thi.",
                    }
                )
            gap = analysis["gap_analysis"]["gap"]
            return CandidateActionPlan.model_validate(
                {
                    "problem": "GOAL_DRIFT",
                    "severity": "MEDIUM",
                    "summary_hint": f"Tiến độ thấp hơn kỳ vọng {_vnd(abs(int(gap)))} VND.",
                    "reasoning_hint": "Kịch bản A giữ nguyên deadline.",
                    "evidence": [
                        {
                            "source": "simulate_goal_scenarios",
                            "metric": "goal_gap",
                            "value": gap,
                            "context": analysis["gap_analysis"],
                        }
                    ],
                    "candidate_options": options,
                    "default_option_id": "A",
                }
            )
        event = analysis["events"][0]
        return CandidateActionPlan.model_validate(
            {
                "problem": "UPCOMING_RECURRING",
                "severity": "MEDIUM",
                "summary_hint": f"{event['name']} trị giá {_vnd(event['expected_amount'])} VND đến hạn sau {event['days_until']} ngày.",
                "reasoning_hint": "Nhắc nhở là hành động low-risk phù hợp evidence.",
                "evidence": [
                    {
                        "source": "detect_upcoming_recurring",
                        "metric": "expected_amount",
                        "value": event["expected_amount"],
                        "context": event,
                    }
                ],
                "candidate_options": [
                    {
                        "option_id": "A",
                        "title": "Tạo nhắc nhở",
                        "description": "Nhắc kiểm tra số dư trước hạn.",
                        "action_type": "create_reminder",
                        "parameters": {
                            "customer_id": customer_id,
                            "title": f"Chuẩn bị {event['name']}",
                            "remind_at": datetime.combine(as_of, time(9)).isoformat(),
                            "message": f"Khoản {event['name']} sắp đến hạn.",
                        },
                        "expected_impact": "Giảm nguy cơ bỏ lỡ khoản định kỳ.",
                    }
                ],
                "default_option_id": "A",
            }
        )


def _percent(value: object) -> str:
    return f"{Decimal(str(value)) * 100:.0f}%"


def _vnd(value: object) -> str:
    return f"{int(Decimal(str(value))):,}"
