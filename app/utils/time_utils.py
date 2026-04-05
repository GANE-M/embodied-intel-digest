"""Timezone helpers for digests (v1.4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def parse_iso_datetime(value: str) -> datetime:
    """Parse assorted ISO/RFC date strings; always returns timezone-aware UTC."""
    from dateutil.parser import isoparse

    dt = isoparse(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_timezone(dt: datetime, tz: str) -> datetime:
    if tz.upper() == "UTC":
        zi: timezone | ZoneInfo = timezone.utc
    else:
        zi = ZoneInfo(tz)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(zi)
    return dt.astimezone(zi)


def now_in_tz(tz: str) -> datetime:
    if tz.upper() == "UTC":
        return datetime.now(timezone.utc)
    return datetime.now(ZoneInfo(tz))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_since(hours: int) -> datetime:
    return now_utc() - timedelta(hours=hours)


def format_date(dt: datetime, tz: str) -> str:
    return ensure_timezone(dt, tz).strftime("%Y-%m-%d")
