"""Date parsing, validation, and time-to-expiry calculation utilities."""

from datetime import date, datetime, timezone
from typing import Union


def parse_date(date_str: str) -> date:
    """
    Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Parsed date object

    Raises:
        ValueError: If date string is not in valid format
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD.") from e


def parse_datetime(dt_str: str) -> datetime:
    """
    Parse an ISO 8601 datetime string.

    Args:
        dt_str: ISO 8601 datetime string

    Returns:
        Parsed datetime object (UTC timezone)

    Raises:
        ValueError: If datetime string is not valid
    """
    try:
        # Try parsing with timezone info first
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        # Ensure UTC timezone
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as e:
        raise ValueError(f"Invalid datetime format '{dt_str}'. Expected ISO 8601 format.") from e


def validate_future_date(expiry: date, name: str = "Expiry") -> None:
    """
    Validate that a date is in the future.

    Args:
        expiry: Date to validate
        name: Name of the date field (for error messages)

    Raises:
        ValueError: If date is not in the future
    """
    today = date.today()
    if expiry <= today:
        raise ValueError(f"{name} date {expiry} must be in the future (today is {today})")


def time_to_expiry_years(expiry: date, reference_date: date = None) -> float:
    """
    Calculate time to expiry in years (365-day convention).

    Args:
        expiry: Expiration date
        reference_date: Reference date (defaults to today)

    Returns:
        Time to expiry in years (decimal)

    Raises:
        ValueError: If expiry is before reference date
    """
    if reference_date is None:
        reference_date = date.today()

    if expiry < reference_date:
        raise ValueError(f"Expiry {expiry} is before reference date {reference_date}")

    days_to_expiry = (expiry - reference_date).days
    # Use 365-day year convention (could also use 365.25 for more precision)
    return days_to_expiry / 365.0


def format_date(d: Union[date, datetime]) -> str:
    """
    Format a date or datetime as YYYY-MM-DD string.

    Args:
        d: Date or datetime object

    Returns:
        Formatted date string
    """
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%Y-%m-%d")
