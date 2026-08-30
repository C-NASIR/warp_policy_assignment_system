from datetime import UTC, date, datetime


def current_date() -> date:
    """Return the application's current calendar date in UTC."""
    return datetime.now(tz=UTC).date()
