from datetime import UTC, date, datetime, time


def current_datetime() -> datetime:
    """Return the application's current timestamp in UTC."""
    return datetime.now(tz=UTC)


def current_date() -> date:
    """Return the application's current calendar date in UTC."""
    return current_datetime().date()


def start_of_day(day: date) -> datetime:
    """Return midnight UTC for a calendar date."""
    return datetime.combine(day, time.min, tzinfo=UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize timestamps to UTC, treating naive database values as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
