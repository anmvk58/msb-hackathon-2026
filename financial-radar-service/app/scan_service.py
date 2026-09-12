from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.runtime import AgentRuntime
from app.agent.schemas import AgentResponse, response_from_state
from app.models import RadarScanRun, ScanStatus, ScanTrigger
from app.scan_schemas import RadarScanRead


def run_and_record_scan(
    session: Session,
    runtime: AgentRuntime,
    *,
    customer_id: str,
    trigger_type: ScanTrigger,
    message: str,
    as_of: date,
) -> AgentResponse:
    scan = create_pending_scan(
        session,
        customer_id=customer_id,
        trigger_type=trigger_type,
        message=message,
        as_of=as_of,
    )
    response = execute_pending_scan(session, runtime, scan.scan_id)
    if response is None:
        raise RuntimeError("Scan completed without a result")
    return response


def create_pending_scan(
    session: Session,
    *,
    customer_id: str,
    trigger_type: ScanTrigger,
    message: str,
    as_of: date,
) -> RadarScanRun:
    scan = RadarScanRun(
        scan_id=f"SCAN-{uuid4().hex[:20].upper()}",
        customer_id=customer_id,
        trigger_type=trigger_type,
        status=ScanStatus.RUNNING,
        input_snapshot={"message": message, "as_of": as_of.isoformat()},
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def execute_pending_scan(
    session: Session,
    runtime: AgentRuntime,
    scan_id: str,
) -> AgentResponse | None:
    scan = session.get(RadarScanRun, scan_id)
    if scan is None:
        raise ValueError("Unknown scan_id")
    if scan.status != ScanStatus.RUNNING:
        return AgentResponse.model_validate(scan.result_data) if scan.result_data else None
    try:
        as_of = date.fromisoformat(scan.input_snapshot["as_of"])
        response = response_from_state(
            runtime.run(
                session,
                customer_id=scan.customer_id,
                message=scan.input_snapshot["message"],
                as_of=as_of,
            )
        )
        risk_level = (response.analysis or {}).get("risk_level")
        if not risk_level and response.signals:
            risk_level = response.signals[0].get("severity")
        scan.status = ScanStatus.COMPLETED
        scan.risk_level = str(risk_level or "LOW").upper()
        scan.alert_summary = response.alert_summary or response.message
        scan.result_data = response.model_dump(mode="json")
        scan.completed_at = datetime.utcnow()
        session.commit()
        return response
    except Exception as error:
        session.rollback()
        failed_scan = session.get(RadarScanRun, scan_id)
        if failed_scan is not None:
            failed_scan.status = ScanStatus.FAILED
            failed_scan.error_message = str(error)[:1000]
            failed_scan.completed_at = datetime.utcnow()
            session.commit()
        raise


def get_scan(session: Session, scan_id: str) -> RadarScanRead | None:
    scan = session.get(RadarScanRun, scan_id)
    return _scan_read(scan) if scan else None


def get_latest_completed_scan(session: Session, customer_id: str) -> RadarScanRead | None:
    scan = session.scalar(
        select(RadarScanRun)
        .where(
            RadarScanRun.customer_id == customer_id,
            RadarScanRun.status == ScanStatus.COMPLETED,
        )
        .order_by(RadarScanRun.completed_at.desc(), RadarScanRun.started_at.desc())
        .limit(1)
    )
    return _scan_read(scan) if scan else None


def _scan_read(scan: RadarScanRun) -> RadarScanRead:
    result = AgentResponse.model_validate(scan.result_data) if scan.result_data else None
    reassuring_message = "Tài chính của bạn đang ổn định, hiện chưa có điều gì cần lo lắng."
    if result and scan.risk_level == "LOW" and result.message == "Financial Sensing completed.":
        result = result.model_copy(update={"message": reassuring_message})
    alert_summary = scan.alert_summary
    if scan.risk_level == "LOW" and alert_summary == "Financial Sensing completed.":
        alert_summary = reassuring_message
    return RadarScanRead(
        scan_id=scan.scan_id,
        customer_id=scan.customer_id,
        trigger_type=scan.trigger_type,
        status=scan.status,
        risk_level=scan.risk_level,
        alert_summary=alert_summary,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        error_message=scan.error_message,
        result=result,
    )
