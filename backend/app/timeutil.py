"""Time helpers. The API contract requires ISO 8601 UTC timestamps without fractional seconds."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; we always store UTC, so naive means UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_required(value: datetime) -> str:
    return as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def week_start(value: datetime | None = None) -> date:
    """Monday of the (UTC) week containing `value`."""
    moment = as_utc(value or utcnow())
    return (moment - timedelta(days=moment.weekday())).date()


def week_bounds(value: datetime | None = None) -> tuple[datetime, datetime]:
    start = week_start(value)
    start_dt = datetime(start.year, start.month, start.day, tzinfo=UTC)
    return start_dt, start_dt + timedelta(days=7)


def short_date(value: datetime) -> str:
    """'Oct 26' style label used in context labels."""
    moment = as_utc(value)
    return f"{moment.strftime('%b')} {moment.day}"


def parse_date(value: str) -> date:
    return date.fromisoformat(value)
