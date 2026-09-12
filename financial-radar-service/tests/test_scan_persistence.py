from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.local_runtime import LocalAgentRuntime
from app.models import RadarScanRun, ScanStatus, ScanTrigger
from app.scan_service import create_pending_scan, get_scan, get_latest_completed_scan, run_and_record_scan


def test_async_scan_can_be_created_and_polled_while_running(session: Session) -> None:
    scan = create_pending_scan(
        session,
        customer_id="C004",
        trigger_type=ScanTrigger.MANUAL,
        message="Quét bất đồng bộ",
        as_of=date(2026, 9, 1),
    )

    polled = get_scan(session, scan.scan_id)

    assert polled is not None
    assert polled.status == ScanStatus.RUNNING
    assert polled.result is None
    assert polled.completed_at is None


def test_manual_scan_is_persisted_and_available_as_latest(session: Session) -> None:
    response = run_and_record_scan(
        session,
        LocalAgentRuntime(),
        customer_id="C004",
        trigger_type=ScanTrigger.MANUAL,
        message="Quét lại Financial Sensing",
        as_of=date(2026, 9, 1),
    )

    stored = session.scalar(select(RadarScanRun))
    assert stored is not None
    assert stored.trigger_type == ScanTrigger.MANUAL
    assert stored.status == ScanStatus.COMPLETED
    assert stored.result_data["customer_id"] == "C004"

    latest = get_latest_completed_scan(session, "C004")
    assert latest is not None
    assert latest.scan_id == stored.scan_id
    assert latest.result == response
