"""Catalogue stages and prices; section changes never mutate ownership or media."""
from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import datetime
import json

from backend.core.time_utils import APP_TIMEZONE, app_now, parse_app_datetime

DISCS_PER_STAR = 1000
# Inclusive starts measured from release; the next band is exclusive.
LIBRARY_PRICE_BANDS = ((12, 10), (6, 50), (4, 80), (1, 100))


def add_calendar_months(value: datetime, months: int) -> datetime:
  index = value.year * 12 + value.month - 1 + months
  year, month = divmod(index, 12)
  month += 1
  return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def pricing_entries(value) -> list[dict]:
  if isinstance(value, str):
    try:
      value = json.loads(value)
    except (ValueError, TypeError):
      return []
  return deepcopy(value) if isinstance(value, list) else []


def normalize_stage(stage) -> str:
  return str(stage or "").strip().lower().replace(" ", "_").replace("-", "_")


def is_library_stage(stage) -> bool:
  """Library covers the plain stage plus the Free/Paid variants."""

  value = normalize_stage(stage)
  return value == "library" or value.startswith("library_")


def title_origin(movie: dict) -> str:
  origin = movie.get("catalog_origin")
  if origin in {"upcoming", "library"}:
    return origin
  # Existing library records are direct uploads unless explicitly classified.
  return "library" if is_library_stage(movie.get("stage")) else "upcoming"


def catalogue_view(movie: dict, now: datetime | None = None) -> dict:
  """Project viewer stage/pricing without writing a stage back to the database.

  Release dates use the existing Asia/Kolkata application timezone. Date-only
  releases start at midnight. Missing/invalid dates never trigger a transition.
  Content readiness and payment authorization remain separate from visibility.
  """
  item = deepcopy(movie)
  current = now or app_now()
  current = current.replace(tzinfo=APP_TIMEZONE) if current.tzinfo is None else current.astimezone(APP_TIMEZONE)
  origin = title_origin(item)
  item["catalog_origin"] = origin
  release = parse_app_datetime(item.get("release_date"))
  item["library_pricing_options"] = pricing_entries(item.get("library_pricing_options"))
  item["library_price_source"] = "direct" if origin == "library" else "stars"
  item["library_available_at"] = add_calendar_months(release, 1).isoformat() if release and origin == "upcoming" else None
  stage = item.get("stage", "upcoming")
  if origin == "library":
    # Keep the Free/Paid variants intact so the existing Library sections split correctly.
    stage = stage or "library"
  elif release:
    stage = "upcoming" if current < release else "released" if current < add_calendar_months(release, 1) else "library"
  item["stage"] = stage
  if normalize_stage(stage) in {"upcoming", "released", "library"}:
    item["stage_label"] = {"upcoming": "Upcoming", "released": "New Release", "library": "Library"}[normalize_stage(stage)]
  item["effective_pricing_options"] = []
  item["library_price_percent"] = None
  options = pricing_entries(item.get("online_pricing_options"))
  if not is_library_stage(stage):
    item["effective_pricing_options"] = [dict(option, currency="stars", amount=option["stars_required"]) for option in options]
  elif origin == "library":
    item["effective_pricing_options"] = [dict(option, currency="discs", amount=option["discs_required"]) for option in item["library_pricing_options"]]
  elif release:
    percent = next((percent for months, percent in LIBRARY_PRICE_BANDS if current >= add_calendar_months(release, months)), 100)
    item["library_price_percent"] = percent
    item["effective_pricing_options"] = [
      dict(option, currency="discs", amount=int(option["stars_required"]) * DISCS_PER_STAR * percent // 100)
      for option in options
    ]
  return item
