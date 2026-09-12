import logging
from datetime import datetime
from time import monotonic, sleep
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.agent.factory import build_agent_runtime
from app.config import get_settings
from app.database import SessionLocal
from app.models import ScanTrigger
from app.scan_service import run_and_record_scan


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("financial-radar-scheduler")
ADVISORY_LOCK_ID = 724331
BUSINESS_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def business_today():
    return datetime.now(BUSINESS_TIMEZONE).date()


def run_cycle() -> None:
    settings = get_settings()
    runtime = build_agent_runtime(settings=settings)
    with SessionLocal() as session:
        locked = bool(session.scalar(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID}))
        if not locked:
            logger.info("Skipping cycle because another scheduler owns the lock")
            return
        try:
            for customer_id in settings.scheduler_customers:
                try:
                    run_and_record_scan(
                        session,
                        runtime,
                        customer_id=customer_id,
                        trigger_type=ScanTrigger.SCHEDULED,
                        message="Tự động quét Financial Sensing định kỳ",
                        as_of=business_today(),
                    )
                    logger.info("Scheduled scan completed customer_id=%s", customer_id)
                except Exception:
                    logger.exception("Scheduled scan failed customer_id=%s", customer_id)
        finally:
            session.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": ADVISORY_LOCK_ID})
            session.commit()


def main() -> None:
    settings = get_settings()
    logger.info(
        "Scheduler started interval_seconds=%s customers=%s",
        settings.scheduler_interval_seconds,
        ",".join(settings.scheduler_customers),
    )
    while True:
        started = monotonic()
        try:
            run_cycle()
        except Exception:
            logger.exception("Scheduler cycle failed")
        elapsed = monotonic() - started
        sleep(max(1, settings.scheduler_interval_seconds - elapsed))


if __name__ == "__main__":
    main()
