import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def ratio(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def months_between_ceiling(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + end.month - start.month
    if end.day > start.day:
        months += 1
    return max(months, 1)

