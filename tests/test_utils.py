"""
Unit tests for time formatting utilities.
Pure functions — no mocking required.
"""

import pytest
from datetime import datetime, timedelta, timezone
from app.utils.time_formatting import timeago, format_datetime


class TestTimeago:

    def _dt(self, **kwargs):
        """Return a datetime that is `kwargs` ago from now."""
        return datetime.utcnow() - timedelta(**kwargs)

    def test_none_returns_unknown(self):
        assert timeago(None) == "unknown"

    def test_future_date_returns_just_now(self):
        future = datetime.utcnow() + timedelta(minutes=5)
        assert timeago(future) == "just now"

    def test_seconds_ago_returns_just_now(self):
        assert timeago(self._dt(seconds=30)) == "just now"

    def test_one_minute_ago(self):
        assert timeago(self._dt(seconds=90)) == "1 minute ago"

    def test_plural_minutes(self):
        assert timeago(self._dt(minutes=5)) == "5 minutes ago"

    def test_one_hour_ago(self):
        assert timeago(self._dt(hours=1, minutes=1)) == "1 hour ago"

    def test_plural_hours(self):
        assert timeago(self._dt(hours=3)) == "3 hours ago"

    def test_yesterday(self):
        assert timeago(self._dt(days=1, hours=1)) == "yesterday"

    def test_days_ago(self):
        assert timeago(self._dt(days=4)) == "4 days ago"

    def test_one_week_ago(self):
        assert timeago(self._dt(days=7)) == "1 week ago"

    def test_plural_weeks(self):
        assert timeago(self._dt(days=14)) == "2 weeks ago"

    def test_one_month_ago(self):
        assert timeago(self._dt(days=32)) == "1 month ago"

    def test_plural_months(self):
        assert timeago(self._dt(days=90)) == "3 months ago"

    def test_one_year_ago(self):
        assert timeago(self._dt(days=366)) == "1 year ago"

    def test_plural_years(self):
        assert timeago(self._dt(days=730)) == "2 years ago"

    def test_timezone_aware_datetime(self):
        aware_dt = datetime.now(timezone.utc) - timedelta(hours=2)
        result = timeago(aware_dt)
        assert "hour" in result


class TestFormatDatetime:

    def test_none_returns_unknown(self):
        assert format_datetime(None) == "unknown"

    def test_default_format(self):
        dt = datetime(2025, 6, 15, 14, 30, 0)
        result = format_datetime(dt)
        assert "June" in result
        assert "15" in result
        assert "2025" in result

    def test_custom_format(self):
        dt = datetime(2025, 6, 15, 14, 30, 0)
        result = format_datetime(dt, "%Y-%m-%d")
        assert result == "2025-06-15"

    def test_iso_format(self):
        dt = datetime(2025, 1, 1, 0, 0, 0)
        result = format_datetime(dt, "%Y-%m-%dT%H:%M:%S")
        assert result == "2025-01-01T00:00:00"
