"""Time helpers. The API contract requires ISO 8601 UTC timestamps without fractional seconds.

Everything user-facing that depends on "today" or "this week" uses the user's own timezone (IANA name), so a
session at 01:00 in Bengaluru on a Monday belongs to Monday's week, not to Sunday in UTC.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


# ------------------------------------------------------------------ timezones


def zone(name: str | None) -> ZoneInfo:
    """The named IANA zone, or UTC when the name is missing or unknown."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def to_local(value: datetime, tz: str | None) -> datetime:
    return as_utc(value).astimezone(zone(tz))


def local_date(value: datetime, tz: str | None) -> date:
    return to_local(value, tz).date()


def local_datetime(day: date, at: time, tz: str | None) -> datetime:
    """`day` at wall-clock time `at` in `tz`, as an aware UTC datetime (DST-safe)."""
    return datetime.combine(day, at, tzinfo=zone(tz)).astimezone(UTC)


def day_bounds(day: date, tz: str | None) -> tuple[datetime, datetime]:
    """UTC start (inclusive) and end (exclusive) of a local calendar day."""
    return local_datetime(day, time(0, 0), tz), local_datetime(day + timedelta(days=1), time(0, 0), tz)


def week_start(value: datetime | None = None, tz: str | None = None) -> date:
    """Monday of the local week containing `value` (UTC when no timezone is given)."""
    day = local_date(value or utcnow(), tz)
    return day - timedelta(days=day.weekday())


def week_bounds(value: datetime | None = None, tz: str | None = None) -> tuple[datetime, datetime]:
    """UTC start (Monday 00:00 local) and end (next Monday 00:00 local) of the week containing `value`."""
    start = week_start(value, tz)
    return local_datetime(start, time(0, 0), tz), local_datetime(start + timedelta(days=7), time(0, 0), tz)


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def short_date(value: datetime, market: str = "us", tz: str | None = None) -> str:
    """'Oct 26' (US/global) or '26 Oct' (India) for labels, on the user's local calendar."""
    moment = to_local(value, tz)
    month = moment.strftime("%b")
    return f"{moment.day} {month}" if market == "in" else f"{month} {moment.day}"


def parse_date(value: str) -> date:
    return date.fromisoformat(value)
