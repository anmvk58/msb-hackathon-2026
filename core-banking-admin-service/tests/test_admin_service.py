import httpx
from fastapi.testclient import TestClient

from admin_service.gateway import CoreBankingAdminGateway
from admin_service.main import app, get_gateway


def test_admin_proxy_and_dashboard() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/admin/metadata":
            return httpx.Response(200, json={"authentication": False, "resources": {}})
        if request.url.path == "/api/admin/customers":
            return httpx.Response(200, json=[{"customer_id": "C001"}])
        if request.url.path == "/api/admin/customers/C005/m-sinh-loi-accounts":
            return httpx.Response(200, json=[{"account_id": "MSL-C005", "balance": "25000000.00"}])
        return httpx.Response(404, json={"detail": "Not found"})

    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="http://corebanking"
    )
    fake_gateway = CoreBankingAdminGateway(async_client)
    app.dependency_overrides[get_gateway] = lambda: fake_gateway
    try:
        with TestClient(app) as client:
            assert client.get("/").status_code == 200
            assert client.get("/health").json()["status"] == "healthy"
            assert client.get("/api/customers").json() == [{"customer_id": "C001"}]
            assert client.get("/api/customers/C005/m-sinh-loi-accounts").json()[0]["account_id"] == "MSL-C005"
    finally:
        app.dependency_overrides.clear()
