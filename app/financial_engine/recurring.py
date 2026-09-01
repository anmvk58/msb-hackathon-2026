import calendar
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.financial_engine.schemas import UpcomingRecurringItem, UpcomingRecurringResult
from app.models import RecurringEvent


def _next_occurrence(as_of: date, expected_day: int) -> date:
    day = min(expected_day, calendar.monthrange(as_of.year, as_of.month)[1])
    candidate = date(as_of.year, as_of.month, day)
    if candidate >= as_of:
        return candidate
    next_month = (as_of.replace(day=28) + timedelta(days=4)).replace(day=1)
    day = min(expected_day, calendar.monthrange(next_month.year, next_month.month)[1])
    return next_month.replace(day=day)


def detect_upcoming_recurring(
    session: Session,
    customer_id: str,
    *,
    as_of: date,
    window_days: int | None = None,
) -> UpcomingRecurringResult:
    window = window_days if window_days is not None else get_settings().recurring_lookahead_days
    if window < 0:
        raise ValueError("window_days must not be negative")
    events = session.scalars(
        select(RecurringEvent).where(
            RecurringEvent.customer_id == customer_id,
            RecurringEvent.active_flag.is_(True),
        )
    ).all()
    upcoming = []
    for event in events:
        occurrence = _next_occurrence(as_of, event.expected_day)
        days_until = (occurrence - as_of).days
        if days_until <= window:
            upcoming.append(
                UpcomingRecurringItem(
                    recurring_id=event.recurring_id,
                    name=event.name,
                    category=event.category,
                    expected_amount=event.expected_amount,
                    expected_date=occurrence,
                    days_until=days_until,
                    confidence=event.confidence,
                )
            )
    upcoming.sort(key=lambda item: (item.expected_date, item.recurring_id))
    return UpcomingRecurringResult(
        customer_id=customer_id, as_of=as_of, window_days=window, events=upcoming
    )

