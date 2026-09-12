from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.agent.schemas import AgentResponse
from app.models import ScanStatus, ScanTrigger


class RadarScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scan_id: str
    customer_id: str
    trigger_type: ScanTrigger
    status: ScanStatus
    risk_level: str | None
    alert_summary: str | None
    started_at: datetime
    completed_at: datetime | None
    result: AgentResponse | None = None

