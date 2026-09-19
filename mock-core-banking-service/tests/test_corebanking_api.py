from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from corebanking.database import CoreBankingBase, get_core_banking_db
from corebanking.main import app
from corebanking.models import Account, Budget, OverdraftFacility, Reminder, SavingGoal, Transaction
from corebanking.seed import seed_core_banking_demo


@pytest.fixture
def core_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    CoreBankingBase.metadata.create_all(engine)
    with Session(engine) as session:
        seed_core_banking_demo(session)
        yield session
    CoreBankingBase.metadata.drop_all(engine)


@pytest.fixture
def core_client(core_session: Session) -> TestClient:
    def override_db():
        yield core_session

    app.dependency_overrides[get_core_banking_db] = override_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_demo_login_and_financial_context(core_client: TestClient) -> None:
    login = core_client.post("/api/auth/demo-login", json={"customer_id": "C001"})
    context = core_client.get("/api/customers/C001/financial-context")

    assert login.status_code == 200
    assert login.json()["customer"]["customer_name"] == "Nguyen Minh An"
    assert context.status_code == 200
    assert context.json()["accounts"][0]["available_balance"] == "9000000.00"
    assert context.json()["recurring_events"][0]["expected_amount"] == "6000000.00"


def test_list_customers_returns_every_customer(core_client: TestClient) -> None:
    response = core_client.get("/api/customers")

    assert response.status_code == 200
    assert [customer["customer_id"] for customer in response.json()] == [
        "C001",
        "C002",
        "C003",
        "C004",
        "C005",
    ]


def test_m_sinh_loi_activation_sweep_and_flexible_withdrawal(core_client: TestClient) -> None:
    path = "/api/customers/C005/m-sinh-loi"
    assert core_client.get(path).json() is None
    headers = {"Idempotency-Key": "activate-c005-demo"}
    created = core_client.post(path, json={"minimum_payment_balance": "5000000"}, headers=headers)
    repeated = core_client.post(path, json={"minimum_payment_balance": "5000000"}, headers=headers)
    assert created.status_code == repeated.status_code == 200
    assert created.json() == repeated.json()
    assert created.json()["balance"] == "25000000.00"
    assert core_client.get("/api/customers/C005/accounts").json()[0]["available_balance"] == "5000000.00"

    swept = core_client.post(path + "/sweep?demo_now=true")
    assert swept.status_code == 200
    assert swept.json()["balance"] == "25000000.00"
    context = core_client.get("/api/customers/C005/financial-context").json()
    assert context["accounts"][0]["available_balance"] == "5000000.00"
    assert context["m_sinh_loi"]["minimum_payment_balance"] == "5000000.00"

    withdrawn = core_client.post(path + "/withdraw", json={"amount": "3000000"})
    assert withdrawn.status_code == 200
    assert withdrawn.json()["balance"] == "22000000.00"
    assert core_client.get("/api/customers/C005/accounts").json()[0]["available_balance"] == "8000000.00"


def test_admin_manages_m_sinh_loi_resource(core_client: TestClient) -> None:
    resource = "/api/admin/customers/C005/m-sinh-loi-accounts"
    metadata = core_client.get("/api/admin/metadata").json()["resources"]["m-sinh-loi-accounts"]
    assert metadata["id_field"] == "account_id"
    assert "minimum_payment_balance" in metadata["fields"]

    wrong_owner = core_client.post(resource, json={"payment_account_id": "A-C001", "minimum_payment_balance": "5000000"})
    assert wrong_owner.status_code == 422
    created = core_client.post(resource, json={"payment_account_id": "A-C005", "minimum_payment_balance": "5000000"})
    assert created.status_code == 201
    account_id = created.json()["account_id"]
    assert core_client.post(resource, json={"payment_account_id": "A-C005", "minimum_payment_balance": "5000000"}).status_code == 409
    assert core_client.get(resource).json()[0]["account_id"] == account_id
    assert core_client.get("/api/admin/customers/C005/overview").json()["m-sinh-loi-accounts"][0]["account_id"] == account_id

    updated = core_client.patch(f"{resource}/{account_id}", json={"minimum_payment_balance": "6000000", "sweep_hour": 16})
    assert updated.status_code == 200
    assert updated.json()["minimum_payment_balance"] == "6000000.00"
    assert core_client.delete("/api/admin/customers/C005").status_code == 204
    assert core_client.get(resource).status_code == 404


def test_transaction_updates_balance_and_is_idempotent(
    core_client: TestClient, core_session: Session
) -> None:
    payload = {
        "account_id": "A-C001",
        "amount": "1500000",
        "direction": "DEBIT",
        "category": "SHOPPING",
        "merchant": "Mall B",
        "description": "Demo card payment",
        "transaction_date": "2026-09-02",
        "transaction_type": "CARD",
    }
    headers = {"Idempotency-Key": "demo-payment-001"}

    first = core_client.post("/api/customers/C001/transactions", json=payload, headers=headers)
    second = core_client.post("/api/customers/C001/transactions", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["transaction"]["transaction_id"] == second.json()["transaction"]["transaction_id"]
    assert first.json()["account"]["available_balance"] == "7500000.00"
    assert core_session.get(Account, "A-C001").available_balance == 7_500_000
    assert core_session.query(Transaction).filter(Transaction.customer_id == "C001").count() == 5


def test_transaction_rejects_insufficient_balance(core_client: TestClient) -> None:
    response = core_client.post(
        "/api/customers/C001/transactions",
        json={
            "account_id": "A-C001",
            "amount": "10000000",
            "direction": "DEBIT",
            "category": "SHOPPING",
            "transaction_date": "2026-09-02",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Insufficient available balance"


def test_overdraft_draw_increases_payment_balance_and_reduces_available_limit(
    core_client: TestClient, core_session: Session
) -> None:
    endpoint = "/api/customers/C004/overdraft-facilities/OD-C004-001/draw"
    headers = {"Idempotency-Key": "agent-overdraft-A004"}

    first = core_client.post(endpoint, json={"amount": "2000000"}, headers=headers)
    second = core_client.post(endpoint, json={"amount": "2000000"}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["transaction_id"] == second.json()["transaction_id"]
    assert first.json()["account_available_balance"] == "9200000.00"
    assert first.json()["used_amount"] == "2000000.00"
    assert first.json()["available_limit"] == "8000000.00"
    assert core_session.get(Account, "A-C004").available_balance == 9_200_000
    assert core_session.get(OverdraftFacility, "OD-C004-001").used_amount == 2_000_000
    assert core_session.query(Transaction).filter(Transaction.transaction_type == "OVERDRAFT_DRAW").count() == 1


def test_budget_is_applied_and_tracks_period_spending(
    core_client: TestClient, core_session: Session
) -> None:
    payload = {
        "category": "SHOPPING",
        "amount": "3000000",
        "alert_threshold": "0.8",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
    }
    headers = {"Idempotency-Key": "agent-action-A001"}
    first = core_client.post("/api/customers/C001/budgets", json=payload, headers=headers)
    second = core_client.post("/api/customers/C001/budgets", json=payload, headers=headers)

    assert first.status_code == 201
    assert first.json()["spent_amount"] == "750000.00"
    assert second.json()["budget_id"] == first.json()["budget_id"]
    assert core_session.query(Budget).filter(Budget.customer_id == "C001").count() == 1


def test_goal_and_reminder_actions_apply_to_core_banking(
    core_client: TestClient, core_session: Session
) -> None:
    goal = core_client.patch(
        "/api/customers/C003/goals/G-C003-HOME",
        json={"monthly_contribution": "9000000", "target_date": "2027-06-30"},
        headers={"Idempotency-Key": "agent-goal-A001"},
    )
    reminder = core_client.post(
        "/api/customers/C001/reminders",
        json={
            "title": "Kiểm tra số dư",
            "remind_at": "2026-09-04T09:00:00",
            "message": "Kiểm tra số dư trước tiền thuê",
        },
        headers={"Idempotency-Key": "agent-reminder-A001"},
    )

    assert goal.status_code == 200
    assert goal.json()["monthly_contribution"] == "9000000.00"
    assert core_session.get(SavingGoal, "G-C003-HOME").target_date == date(2027, 6, 30)
    assert reminder.status_code == 201
    assert core_session.query(Reminder).filter(Reminder.customer_id == "C001").count() == 1


def test_core_banking_openapi_explains_ownership(core_client: TestClient) -> None:
    schema = core_client.get("/openapi.json").json()

    assert "không truy cập trực tiếp database" in schema["info"]["description"]
    assert schema["paths"]["/api/customers/{customer_id}/financial-context"]["get"]["summary"] == "Lấy context tài chính tổng hợp"
    assert schema["components"]["schemas"]["TransactionCreate"]["examples"][0]["account_id"] == "A-C001"


def test_customer_can_manage_financial_context(core_client: TestClient) -> None:
    profile = core_client.patch(
        "/api/customers/C001/financial-settings",
        json={"monthly_income": "27000000", "preferred_safe_balance": "4500000", "salary_day": 26},
    )
    recurring = core_client.post(
        "/api/customers/C001/recurring-events",
        json={"name": "Tiền điện", "category": "UTILITY", "expected_amount": "1200000", "expected_day": 12, "frequency": "MONTHLY"},
    )
    goal = core_client.post(
        "/api/customers/C001/goals",
        json={"goal_name": "Quỹ dự phòng", "target_amount": "50000000", "current_amount": "5000000", "start_date": "2026-09-01", "target_date": "2027-09-01", "monthly_contribution": "4000000"},
    )
    context = core_client.get("/api/customers/C001/financial-context").json()

    assert profile.status_code == 200
    assert recurring.status_code == 201
    assert goal.status_code == 201
    assert context["customer"]["monthly_income"] == "27000000.00"
    assert context["customer"]["preferred_safe_balance"] == "4500000.00"
    assert any(item["name"] == "Tiền điện" for item in context["recurring_events"])
    assert any(item["goal_name"] == "Quỹ dự phòng" for item in context["active_goals"])


def test_admin_customer_and_nested_resource_full_crud(core_client: TestClient) -> None:
    created = core_client.post(
        "/api/admin/customers",
        json={
            "customer_id": "C099",
            "customer_name": "Demo Admin",
            "monthly_income": "20000000",
            "salary_day": 20,
            "preferred_safe_balance": "3000000",
            "risk_preference": "BALANCED",
        },
    )
    assert created.status_code == 201

    account = core_client.post(
        "/api/admin/customers/C099/accounts",
        json={
            "account_id": "A-C099",
            "account_type": "PAYMENT",
            "available_balance": "5000000",
            "currency": "VND",
        },
    )
    assert account.status_code == 201
    assert account.json()["account_id"] == "A-C099"

    updated = core_client.patch(
        "/api/admin/customers/C099/accounts/A-C099",
        json={"available_balance": "6500000"},
    )
    assert updated.status_code == 200
    assert updated.json()["available_balance"] == "6500000.00"

    overview = core_client.get("/api/admin/customers/C099/overview")
    assert overview.status_code == 200
    assert overview.json()["accounts"][0]["available_balance"] == "6500000.00"

    assert core_client.delete("/api/admin/customers/C099/accounts/A-C099").status_code == 204
    assert core_client.delete("/api/admin/customers/C099").status_code == 204
    assert core_client.get("/api/admin/customers/C099").status_code == 404
