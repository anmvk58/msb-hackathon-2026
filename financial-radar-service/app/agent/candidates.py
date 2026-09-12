import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.banking import BankingGateway
from app.agent.state import CandidateActionPlan
from app.financial_engine import calculate_budget_guardrail
from app.models import Category, SignalType


class CandidateActionGenerator:
    """Creates the only tool names and financial parameters an LLM may select."""

    def __init__(self, gateway: BankingGateway) -> None:
        self.gateway = gateway

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
                self.gateway.get_financial_context(customer_id), customer_id, Category.SHOPPING
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
                                "end_date": as_of.replace(day=calendar.monthrange(as_of.year, as_of.month)[1]).isoformat(),
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
                                "remind_at": datetime.combine(as_of + timedelta(days=1), time(9)).isoformat(),
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
                self.gateway.get_financial_context(customer_id), customer_id, Category(anomaly["category"])
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
                                "end_date": as_of.replace(day=calendar.monthrange(as_of.year, as_of.month)[1]).isoformat(),
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
        context = self.gateway.get_financial_context(customer_id)
        required = max(
            Decimal(str(event["expected_amount"]))
            - sum((account.available_balance for account in context.accounts), Decimal(0)),
            Decimal(0),
        )
        funding_options = []
        overdraft = next((x for x in context.overdraft_facilities if x.status == "ACTIVE" and x.credit_limit - x.used_amount >= required), None)
        deposit = next((x for x in context.term_deposits if x.status == "ACTIVE" and x.partial_withdrawal_allowed and x.available_withdrawal_amount >= required), None)
        loan = next((x for x in context.preapproved_loan_offers if x.status == "ACTIVE" and x.eligibility_status == "ELIGIBLE" and x.minimum_amount <= required <= x.approved_limit), None)
        if required > 0 and overdraft:
            funding_options.append({"title": "Dùng hạn mức còn lại ở tài khoản thấu chi", "description": "Chuyển phần tiền còn thiếu từ hạn mức thấu chi vào tài khoản thanh toán.", "option_type": "OVERDRAFT", "reference_id": overdraft.facility_id, "impact": f"Số dư tài khoản thanh toán tăng {_vnd(required)} VND và hạn mức thấu chi còn lại giảm tương ứng; lãi suất {Decimal(overdraft.annual_interest_rate) * 100:.1f}%/năm."})
        if required > 0 and deposit:
            funding_options.append({"title": "Rút một phần tiền tiết kiệm", "description": "Dùng một phần khoản tiết kiệm để thanh toán đúng hạn.", "option_type": "PARTIAL_SAVING_WITHDRAWAL", "reference_id": deposit.deposit_id, "impact": f"Rút {_vnd(required)} VND; phần rút trước hạn hưởng lãi suất {Decimal(deposit.early_withdrawal_rate) * 100:.1f}%/năm."})
        if required > 0 and loan:
            funding_options.append({"title": "Đăng ký khoản vay ngắn hạn", "description": "Sử dụng đề nghị vay đã được duyệt sẵn trên ứng dụng.", "option_type": "SHORT_TERM_LOAN", "reference_id": loan.offer_id, "impact": f"Vay {_vnd(required)} VND trong {loan.term_months} tháng; lãi suất {Decimal(loan.annual_interest_rate) * 100:.1f}%/năm."})
        options = [
            {"option_id": chr(ord("A") + index), "title": item["title"], "description": item["description"], "action_type": "prepare_funding_option", "parameters": {"customer_id": customer_id, "option_type": item["option_type"], "reference_id": item["reference_id"], "amount": str(required)}, "expected_impact": item["impact"]}
            for index, item in enumerate(funding_options[:3])
        ]
        if not options:
            options = [{"option_id": "A", "title": "Tạo nhắc nhở", "description": "Nhắc kiểm tra số dư trước hạn.", "action_type": "create_reminder", "parameters": {"customer_id": customer_id, "title": f"Chuẩn bị {event['name']}", "remind_at": datetime.combine(as_of + timedelta(days=1), time(9)).isoformat(), "message": f"Khoản {event['name']} sắp đến hạn."}, "expected_impact": "Giảm nguy cơ bỏ lỡ khoản định kỳ."}]
        return CandidateActionPlan.model_validate(
            {
                "problem": "UPCOMING_RECURRING",
                "severity": "MEDIUM",
                "summary_hint": f"{event['name']} trị giá {_vnd(event['expected_amount'])} VND đến hạn sau {event['days_until']} ngày.",
                "reasoning_hint": "Chỉ chọn nguồn tiền đã được Core Banking xác nhận là có sẵn.",
                "evidence": [
                    {
                        "source": "detect_upcoming_recurring",
                        "metric": "expected_amount",
                        "value": event["expected_amount"],
                        "context": event,
                    }
                ],
                "candidate_options": options,
                "default_option_id": "A",
            }
        )


def _percent(value: object) -> str:
    return f"{Decimal(str(value)) * 100:.0f}%"


def _vnd(value: object) -> str:
    return f"{int(Decimal(str(value))):,}"
