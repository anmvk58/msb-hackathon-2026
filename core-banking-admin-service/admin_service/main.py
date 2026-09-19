from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse

from admin_service.gateway import CoreBankingAdminGateway


STATIC_DIR = Path(__file__).parent / "static"
gateway: CoreBankingAdminGateway | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global gateway
    gateway = CoreBankingAdminGateway()
    yield
    await gateway.close()
    gateway = None


app = FastAPI(
    title="MSB Mock Core Banking Admin",
    version="0.1.0",
    description="Admin facade không authentication cho dữ liệu demo. Service chỉ giao tiếp với Mock Core Banking qua REST.",
    lifespan=lifespan,
)


def get_gateway() -> CoreBankingAdminGateway:
    if gateway is None:
        raise HTTPException(status_code=503, detail="Admin gateway is not ready")
    return gateway


Gateway = Annotated[CoreBankingAdminGateway, Depends(get_gateway)]


@app.get("/health", tags=["System"])
async def health(admin_gateway: Gateway) -> dict[str, str]:
    try:
        response = await admin_gateway.request("GET", "metadata")
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Mock Core Banking is unavailable") from exc
    return {"status": "healthy", "service": "core-banking-admin"}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"], tags=["Admin proxy"])
async def proxy(path: str, request: Request, admin_gateway: Gateway) -> Response:
    body: Any = None
    if request.method in {"POST", "PATCH"}:
        try:
            body = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
    try:
        upstream = await admin_gateway.request(request.method, path, body)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Cannot connect to Mock Core Banking") from exc
    excluded = {"content-length", "content-encoding", "transfer-encoding", "connection"}
    headers = {key: value for key, value in upstream.headers.items() if key.lower() not in excluded}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=headers)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
