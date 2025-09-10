# common/timezone_utils.py
from datetime import datetime, time, date, timedelta
from zoneinfo import ZoneInfo
from django.utils import timezone


def day_bounds_utc(local_date: date, tz: str) -> tuple[datetime, datetime]:
    """
    Convert a local date to UTC datetime bounds for that day.
    
    Args:
        local_date: The date in the user's timezone
        tz: IANA timezone string (e.g., 'Africa/Kampala')
    
    Returns:
        Tuple of (start_utc, end_utc) datetime objects in UTC
    """
    try:
        zone = ZoneInfo(tz)
        start_local = datetime.combine(local_date, time.min, tzinfo=zone)
        end_local = start_local + timedelta(days=1)
        return (
            start_local.astimezone(ZoneInfo("UTC")), 
            end_local.astimezone(ZoneInfo("UTC"))
        )
    except Exception:
        # Fallback to UTC if timezone is invalid
        start_utc = datetime.combine(local_date, time.min, tzinfo=ZoneInfo("UTC"))
        end_utc = start_utc + timedelta(days=1)
        return start_utc, end_utc


def get_user_timezone(user) -> str:
    """
    Get user's timezone preference, with fallback to default.
    
    Args:
        user: Django User instance
    
    Returns:
        IANA timezone string
    """
    try:
        return getattr(getattr(user, 'preferences', None), 'timezone', 'Africa/Kampala')
    except AttributeError:
        return 'Africa/Kampala'


def convert_to_user_timezone(dt: datetime, user_tz: str) -> datetime:
    """
    Convert a UTC datetime to user's timezone.
    
    Args:
        dt: UTC datetime object
        user_tz: IANA timezone string
    
    Returns:
        Datetime in user's timezone
    """
    try:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo(user_tz))
    except Exception:
        return dt


def make_aware_in_timezone(naive_dt: datetime, tz: str) -> datetime:
    """
    Make a naive datetime aware in the specified timezone.
    
    Args:
        naive_dt: Naive datetime object
        tz: IANA timezone string
    
    Returns:
        Timezone-aware datetime
    """
    try:
        return timezone.make_aware(naive_dt, ZoneInfo(tz))
    except Exception:
        return timezone.make_aware(naive_dt, ZoneInfo("UTC"))
