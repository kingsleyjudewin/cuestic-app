from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from flask import current_app


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


def format_iso_utc(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 string in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def to_local_datetime(dt: datetime | None, tz_name: str | None = None) -> datetime | None:
    """Convert UTC datetime to given local timezone."""
    if dt is None:
        return None
    if tz_name is None:
        try:
            tz_name = current_app.config.get("APP_TIMEZONE", "Asia/Kolkata")
        except RuntimeError:
            tz_name = "Asia/Kolkata"
            
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    local_tz = ZoneInfo(tz_name)
    return dt.astimezone(local_tz)


def format_friendly_local(dt: datetime | None, tz_name: str | None = None) -> str:
    """Format datetime in friendly readable format: '28 October 2026, 05:00 PM IST'."""
    if dt is None:
        return "N/A"
    local_dt = to_local_datetime(dt, tz_name)
    # tz abbreviation e.g. IST
    tz_abbr = local_dt.strftime("%Z") or "IST"
    return f"{local_dt.strftime('%d %B %Y, %I:%M %p')} {tz_abbr}".strip()
