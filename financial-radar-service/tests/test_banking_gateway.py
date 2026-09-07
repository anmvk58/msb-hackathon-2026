import httpx

from app.banking.gateway import HttpBankingGateway
from tests.fakes import FakeBankingGateway


def test_http_gateway_sends_action_id_as_idempotency_key(
    fake_banking_gateway: FakeBankingGateway,
) -> None:
    context = fake_banking_gateway.get_financial_context("C001")
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["idempotency_key"] = request.headers["Idempotency-Key"]
        return httpx.Response(
            201,
            json={
                "budget_id": "B-CORE-001",
                "customer_id": "C001",
                "category": "SHOPPING",
                "amount": "4000000.00",
                "spent_amount": "750000.00",
                "alert_threshold": "0.8000",
                "start_date": "2026-09-01",
                "end_date": "2026-09-28",
                "status": "ACTIVE",
            },
        )

    gateway = HttpBankingGateway(
        base_url="http://corebanking.test",
        transport=httpx.MockTransport(handler),
    )
    result = gateway.create_budget(
        context.customer.customer_id,
        {
            "category": "SHOPPING",
            "amount": "4000000",
            "alert_threshold": "0.8",
            "start_date": "2026-09-01",
            "end_date": "2026-09-28",
        },
        idempotency_key="A-AGENT-001",
    )

    assert result["budget_id"] == "B-CORE-001"
    assert captured["idempotency_key"] == "A-AGENT-001"


def test_agent_metadata_contains_no_core_banking_tables() -> None:
    from app.database import Base

    assert set(Base.metadata.tables) == {
        "radar_signals",
        "agent_recommendations",
        "agent_action_logs",
    }
