from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


APP_TIMEZONE = "Asia/Taipei"
APP_TIMEZONE_INFO = ZoneInfo(APP_TIMEZONE)
DB_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_db_time() -> str:
    return datetime.now(APP_TIMEZONE_INFO).strftime(DB_TIME_FORMAT)


def unix_to_db_time(value: object) -> str | None:
    if not value:
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).astimezone(APP_TIMEZONE_INFO).strftime(
        DB_TIME_FORMAT
    )


def iso_to_db_time(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(APP_TIMEZONE_INFO).strftime(DB_TIME_FORMAT)
