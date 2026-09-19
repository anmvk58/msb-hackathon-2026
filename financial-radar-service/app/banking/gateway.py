from typing import Any, Protocol

import httpx

from app.banking.schemas import FinancialContext
from app.config import Settings, get_settings
from app.errors import ToolExecutionError


class BankingGateway(Protocol):
    def list_customer_ids(self) -> list[str]: ...

    def get_financial_context(self, customer_id: str) -> FinancialContext: ...

    def create_budget(self, customer_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]: ...

    def create_reminder(self, customer_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]: ...

    def update_goal(self, customer_id: str, goal_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]: ...

    def draw_overdraft(self, customer_id: str, facility_id: str, amount: str, *, idempotency_key: str | None) -> dict[str, Any]: ...
    def activate_m_sinh_loi(self, customer_id: str, minimum_payment_balance: str, *, idempotency_key: str | None) -> dict[str, Any]: ...
    def sweep_m_sinh_loi(self, customer_id: str) -> dict[str, Any] | None: ...


class HttpBankingGateway:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout_seconds, transport=transport)

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request(self, method: str, path: str, *, payload: dict[str, Any] | None = None, idempotency_key: str | None = None) -> Any:
        try:
            response = self.client.request(method, f"{self.base_url}{path}", json=payload, headers=self._headers(idempotency_key))
        except httpx.TimeoutException as error:
            raise ToolExecutionError("Core Banking request timed out") from error
        except httpx.HTTPError as error:
            raise ToolExecutionError(f"Core Banking connection failed: {error}") from error
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ToolExecutionError(f"Core Banking returned {response.status_code}: {detail}")
        return response.json()

    def list_customer_ids(self) -> list[str]:
        data = self._request("GET", "/api/customers")
        if not isinstance(data, list):
            raise ToolExecutionError("Core Banking returned an invalid customer list")
        customer_ids = [
            str(item["customer_id"])
            for item in data
            if isinstance(item, dict) and item.get("customer_id")
        ]
        if len(customer_ids) != len(data):
            raise ToolExecutionError("Core Banking returned an invalid customer entry")
        return customer_ids

    def get_financial_context(self, customer_id: str) -> FinancialContext:
        data = self._request("GET", f"/api/customers/{customer_id}/financial-context")
        return FinancialContext.model_validate(data)

    def create_budget(self, customer_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]:
        return self._request("POST", f"/api/customers/{customer_id}/budgets", payload=payload, idempotency_key=idempotency_key)

    def create_reminder(self, customer_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]:
        return self._request("POST", f"/api/customers/{customer_id}/reminders", payload=payload, idempotency_key=idempotency_key)

    def update_goal(self, customer_id: str, goal_id: str, payload: dict[str, Any], *, idempotency_key: str | None) -> dict[str, Any]:
        return self._request("PATCH", f"/api/customers/{customer_id}/goals/{goal_id}", payload=payload, idempotency_key=idempotency_key)

    def draw_overdraft(self, customer_id: str, facility_id: str, amount: str, *, idempotency_key: str | None) -> dict[str, Any]:
        return self._request("POST", f"/api/customers/{customer_id}/overdraft-facilities/{facility_id}/draw", payload={"amount": amount}, idempotency_key=idempotency_key)

    def activate_m_sinh_loi(self, customer_id: str, minimum_payment_balance: str, *, idempotency_key: str | None) -> dict[str, Any]:
        return self._request("POST", f"/api/customers/{customer_id}/m-sinh-loi", payload={"minimum_payment_balance": minimum_payment_balance}, idempotency_key=idempotency_key)

    def sweep_m_sinh_loi(self, customer_id: str) -> dict[str, Any] | None:
        account = self._request("GET", f"/api/customers/{customer_id}/m-sinh-loi")
        if account is None:
            return None
        return self._request("POST", f"/api/customers/{customer_id}/m-sinh-loi/sweep")


def build_banking_gateway(
    settings: Settings | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> HttpBankingGateway:
    config = settings or get_settings()
    return HttpBankingGateway(
        base_url=config.core_banking_base_url,
        timeout_seconds=config.core_banking_timeout_seconds,
        api_key=config.core_banking_api_key,
        transport=transport,
    )
