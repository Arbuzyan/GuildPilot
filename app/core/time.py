"""Timezone-aware clock helpers for GuildPilot.

Policy:
- Persist absolute moments in UTC.
- Interpret user-entered schedules in the computer's configured timezone.
- Convert to local time only for user-facing display and calendar decisions.

Naive datetimes are deliberately rejected by conversion helpers. Existing
PostgreSQL values need an explicit, field-specific migration policy; silently
assuming a timezone here could shift historical records.
"""

from datetime import date, datetime, time, timedelta, timezone, tzinfo


UTC = timezone.utc


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def local_timezone() -> tzinfo:
    """Return the computer's configured timezone, including DST rules."""
    try:
        from tzlocal import get_localzone
    except ImportError as error:
        raise RuntimeError(
            "tzlocal is required to detect the computer timezone. "
            "Install project dependencies with: pip install -r requirements.txt"
        ) from error
    return get_localzone()


def local_now() -> datetime:
    """Return the current timezone-aware datetime in the computer's timezone."""
    return utc_now().astimezone(local_timezone())


def local_today() -> date:
    """Return today's calendar date in the computer's timezone."""
    return local_now().date()


def to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC; reject naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected a timezone-aware datetime; naive values are ambiguous")
    return value.astimezone(UTC)


def to_local(value: datetime) -> datetime:
    """Convert an aware datetime to the computer's configured timezone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Expected a timezone-aware datetime; naive values are ambiguous")
    return value.astimezone(local_timezone())


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """Return [start, end) of a local calendar day as aware UTC datetimes."""
    zone = local_timezone()
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return to_utc(start_local), to_utc(end_local)
