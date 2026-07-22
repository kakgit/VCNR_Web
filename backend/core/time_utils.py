from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


APP_TIMEZONE = ZoneInfo("Asia/Kolkata")


def app_now() -> datetime:
  return datetime.now(APP_TIMEZONE)


def parse_app_datetime(value: str | None) -> datetime | None:
  normalized = str(value or "").strip()
  if not normalized:
    return None

  for candidate in (normalized, normalized.replace(" ", "T")):
    try:
      parsed = datetime.fromisoformat(candidate)
      if parsed.tzinfo is not None:
        return parsed.astimezone(APP_TIMEZONE)
      return parsed.replace(tzinfo=APP_TIMEZONE)
    except ValueError:
      continue

  return None


def is_app_time_reached(value: str | None) -> bool:
  parsed = parse_app_datetime(value)
  if parsed is None:
    return False
  return parsed <= app_now()
