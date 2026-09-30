"""Catalogue stages and prices; section changes never mutate ownership or media."""
from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json

from backend.core.time_utils import APP_TIMEZONE, app_now, parse_app_datetime

# Economy defaults. The two rupee values are admin editable (Admin > Star Pricing)
# and are stored with the star pricing snapshot, so the disc exchange rate always
# follows the admin's numbers instead of a hard-coded constant:
# 1 Star = Rs 50 and 1 Disc = Rs 0.10 → 500 discs per star.
DEFAULT_STAR_PRICE_INR = Decimal("50")
DEFAULT_DISC_PRICE_INR = Decimal("0.10")
DEFAULT_DISCS_PER_STAR = 500
# Inclusive starts measured from release; the next band is exclusive.
LIBRARY_PRICE_BANDS = ((12, 10), (6, 50), (4, 80), (1, 100))


def _decimal_value(value, fallback: Decimal) -> Decimal:
  try:
    return Decimal(str(value))
  except (InvalidOperation, ValueError, TypeError):
    return fallback


def compute_discs_per_star(star_price_inr=None, disc_price_inr=None) -> int:
  """Whole discs that one star converts into.

  Derived from the two admin-set rupee values so star pricing and disc pricing can
  never drift apart: Rs 50 per star / Rs 0.10 per disc = 500 discs per star. A
  missing, zero, or non-numeric value falls back to the shipped defaults, which
  keeps the viewer conversion page from ever dividing by zero.
  """
  star = _decimal_value(star_price_inr, DEFAULT_STAR_PRICE_INR) if star_price_inr is not None else DEFAULT_STAR_PRICE_INR
  disc = _decimal_value(disc_price_inr, DEFAULT_DISC_PRICE_INR) if disc_price_inr is not None else DEFAULT_DISC_PRICE_INR
  if star <= 0 or disc <= 0:
    return DEFAULT_DISCS_PER_STAR
  return max(1, int((star / disc).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))


def discs_per_star_from_settings(settings: dict | None) -> int:
  """Read the disc exchange rate out of a stored star pricing snapshot."""
  payload = settings if isinstance(settings, dict) else {}
  return compute_discs_per_star(payload.get("price_inr"), payload.get("disc_price_inr"))


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


def catalogue_view(movie: dict, now: datetime | None = None, discs_per_star: int | None = None) -> dict:
  """Project viewer stage/pricing without writing a stage back to the database.

  Release dates use the existing Asia/Kolkata application timezone. Date-only
  releases start at midnight. Missing/invalid dates never trigger a transition.
  Content readiness and payment authorization remain separate from visibility.

  `discs_per_star` is the admin-set exchange rate (see compute_discs_per_star) used
  to price newly released Library titles in discs. Callers with a settings source
  pass it in; a missing value falls back to the shipped default so this projection
  stays usable without a database.
  """
  item = deepcopy(movie)
  disc_rate = int(discs_per_star) if discs_per_star else DEFAULT_DISCS_PER_STAR
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
      dict(option, currency="discs", amount=int(option["stars_required"]) * disc_rate * percent // 100)
      for option in options
    ]
  return item
