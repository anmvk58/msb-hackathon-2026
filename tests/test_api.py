from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


def client_for(session: Session) -> TestClient:
    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_snapshot_endpoint(session: Session) -> None:
    with client_for(session) as client:
        response = client.get("/api/customers/C001/snapshot")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total_available_balance"] == "9000000.00"


def test_financial_tool_endpoints(session: Session) -> None:
    with client_for(session) as client:
        forecast = client.post(
            "/api/tools/forecast-cashflow",
            json={
                "customer_id": "C001",
                "as_of": "2026-09-01",
                "forecast_until": "2026-09-15",
            },
        )
        anomaly = client.post(
            "/api/tools/detect-spending-anomaly",
            json={"customer_id": "C002", "as_of": "2026-09-01"},
        )
    app.dependency_overrides.clear()
    assert forecast.status_code == 200
    assert forecast.json()["forecast_balance"] == "1366667"
    assert anomaly.json()["anomalies"][0]["change_pct"] == "0.2500"


def test_agent_confirmation_e2e(session: Session) -> None:
    with client_for(session) as client:
        recommendation = client.post(
            "/api/agent/run",
            json={
                "customer_id": "C001",
                "message": "Tài chính tháng này của tôi thế nào?",
                "as_of": "2026-09-01",
            },
        )
        waiting = client.post(
            "/api/agent/select",
            json={
                "recommendation_id": recommendation.json()["recommendation_id"],
                "option_id": "A",
            },
        )
        action_id = waiting.json()["action_id"]
        before = client.get(f"/api/agent/actions/{action_id}")
        confirmed = client.post(
            "/api/agent/confirm",
            json={"action_id": action_id, "confirmed": True},
        )
        after = client.get(f"/api/agent/actions/{action_id}")
    app.dependency_overrides.clear()

    assert recommendation.status_code == 200
    assert recommendation.json()["state"] == "RECOMMENDATION_READY"
    assert waiting.json()["state"] == "WAITING_CONFIRMATION"
    assert waiting.json()["confirmation"]["required"] is True
    assert before.json()["action_status"] == "PREPARED"
    assert before.json()["tool_output"] is None
    assert confirmed.json()["state"] == "MONITORING"
    assert confirmed.json()["execution_result"]["status"] == "SUCCESS"
    assert after.json()["action_status"] == "SUCCESS"


def test_direct_budget_endpoint_also_requires_confirmation(session: Session) -> None:
    with client_for(session) as client:
        response = client.post(
            "/api/actions/create-budget",
            json={
                "customer_id": "C001",
                "category": "SHOPPING",
                "amount": "4000000",
                "alert_threshold": "0.8",
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
            },
        )
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["state"] == "WAITING_CONFIRMATION"


def test_signals_endpoint(session: Session) -> None:
    with client_for(session) as client:
        client.post(
            "/api/agent/run",
            json={
                "customer_id": "C004",
                "message": "Quét radar",
                "as_of": "2026-09-01",
            },
        )
        response = client.get("/api/customers/C004/signals")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["signal_type"] == "CASHFLOW_RISK"
