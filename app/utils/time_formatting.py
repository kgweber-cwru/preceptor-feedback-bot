"""
Time formatting utilities for displaying human-readable timestamps.
"""

from datetime import datetime, timedelta


def timeago(dt: datetime) -> str:
    """
    Convert a datetime to a human-readable "time ago" format.

    Args:
        dt: Datetime to format

    Returns:
        String like "2 hours ago", "yesterday", "3 days ago"
    """
    if not dt:
        return "unknown"

    # Handle both timezone-aware and naive datetimes
    now = datetime.utcnow()

    # If dt is timezone-aware, make now timezone-aware too
    if dt.tzinfo is not None:
        from datetime import timezone
        now = datetime.now(timezone.utc)

    diff = now - dt

    # Handle negative differences (future dates)
    if diff.total_seconds() < 0:
        return "just now"

    # Less than a minute
    if diff.total_seconds() < 60:
        return "just now"

    # Less than an hour
    minutes = int(diff.total_seconds() / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    # Less than a day
    hours = int(diff.total_seconds() / 3600)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    # Less than a week
    days = diff.days
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"

    # Less than a month
    weeks = days // 7
    if weeks < 4:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"

    # Less than a year
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"

    # Over a year
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def format_datetime(dt: datetime, format_str: str = "%B %d, %Y at %I:%M %p") -> str:
    """
    Format a datetime using standard strftime format.

    Args:
        dt: Datetime to format
        format_str: strftime format string

    Returns:
        Formatted datetime string
    """
    if not dt:
        return "unknown"

    return dt.strftime(format_str)
