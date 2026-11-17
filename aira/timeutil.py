"""Date and time helpers. Everything shown in the app uses Malaysia time."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

KL = ZoneInfo("Asia/Kuala_Lumpur")


def now_kl() -> datetime:
    return datetime.now(KL)


def today_kl() -> date:
    return now_kl().date()


def utc_now_iso() -> str:
    """The current moment, in the form the database stores (UTC)."""
    return datetime.now(timezone.utc).isoformat()


def minutes_since(started_at) -> int:
    """Whole minutes between a stored timestamp and now (at least 1)."""
    started = parse_timestamp(started_at)
    if started is None:
        return 1
    return max(1, round((now_kl() - started).total_seconds() / 60))


def format_time(value: datetime | None) -> str:
    """Example: 2:45 PM (Malaysia time)."""
    if value is None:
        return ""
    local = value.astimezone(KL)
    hour = local.hour % 12 or 12
    return f"{hour}:{local:%M} {local:%p}"


def parse_date(value) -> date | None:
    """Turn a database date such as '2026-11-13' into a Python date."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def parse_timestamp(value) -> datetime | None:
    """Turn a database timestamp (stored in UTC) into Malaysia time."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed.astimezone(KL)


def format_date(value: date | None) -> str:
    """Example: Fri 13 Nov 2026."""
    if value is None:
        return ""
    return f"{value:%a} {value.day} {value:%b %Y}"


def format_timestamp(value: datetime | None) -> str:
    """Example: 13 Nov 2026, 2:45 PM (Malaysia time)."""
    if value is None:
        return ""
    local = value.astimezone(KL)
    hour = local.hour % 12 or 12
    return f"{local.day} {local:%b %Y}, {hour}:{local:%M} {local:%p}"


def greeting(now: datetime | None = None) -> str:
    hour = (now or now_kl()).hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def due_label(due: date | None, today: date | None = None) -> str:
    """Plain-language description of a due date."""
    if due is None:
        return "No due date"
    today = today or today_kl()
    days = (due - today).days
    if days < -1:
        return f"Overdue by {-days} days"
    if days == -1:
        return "Overdue by 1 day"
    if days == 0:
        return "Due today"
    if days == 1:
        return "Due tomorrow"
    return f"Due {format_date(due)}"
