from typing import Any

import httpx

from admin_service.config import get_settings


class CoreBankingAdminGateway:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._client = client or httpx.AsyncClient(
            base_url=settings.core_banking_base_url.rstrip("/"),
            timeout=settings.core_banking_timeout_seconds,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(self, method: str, path: str, body: Any = None) -> httpx.Response:
        return await self._client.request(method, f"/api/admin/{path.lstrip('/')}", json=body)
