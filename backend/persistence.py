from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import secrets

from sqlalchemy.orm import Session

from backend.data.demo_store import ADMIN_STATE, MOVIES, PUBLISH_QUEUE, USERS
from backend.models import (
  AdminStateRecord,
  AdvertiserProfileRecord,
  CategoryRecord,
  ContentDeliveryEnrollmentRecord,
  CreatorProfileRecord,
  GenreRecord,
  GradeRecord,
  LanguageRecord,
  NotificationRecord,
  MovieRecord,
  MovieChangeRequestRecord,
  MovieWishRecord,
  PublishSubmissionRecord,
  QueueItemRecord,
  ReservationRecord,
  TitleAudioTrackRecord,
  TitleContentFileRecord,
  TitleGenreRecord,
  TitleLanguageRecord,
  TitleMusicRecord,
  TitlePosterRecord,
  TitleRecord,
  TitleSubtitleTrackRecord,
  TitleTrailerRecord,
  UserRecord,
  WalletRecord,
  WalletTransactionRecord,
)

LIBRARY_MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media" / "library"


DEFAULT_CATEGORIES = [
  {"slug": "movies", "name": "Movies", "description": "Feature-length film titles.", "sort_order": 1},
  {"slug": "web-series", "name": "Web Series", "description": "Episodic streaming-first shows.", "sort_order": 2},
  {"slug": "tv-shows", "name": "TV Shows", "description": "Television-origin shows and programs.", "sort_order": 3},
  {"slug": "short-films", "name": "Short Films", "description": "Short-form narrative content.", "sort_order": 4},
  {"slug": "documentaries", "name": "Documentaries", "description": "Documentary and factual titles.", "sort_order": 5},
  {"slug": "music-videos", "name": "Music Videos", "description": "Music-led video releases.", "sort_order": 6},
  {"slug": "specials", "name": "Specials", "description": "Stand-alone specials and events.", "sort_order": 7},
  {"slug": "kids-content", "name": "Kids Content", "description": "Child-friendly viewing catalog.", "sort_order": 8},
]

DEFAULT_GENRES = [
  "Fantasy",
  "Horror",
  "Sci-Fi",
  "Romance",
  "Thriller",
  "Drama",
  "Epic",
  "Action",
  "Heist",
  "Comedy",
  "Adventure",
  "Crime",
  "Mystery",
  "Family",
  "Animation",
  "Documentary",
  "Biography",
  "Historical",
  "War",
  "Sports",
  "Musical",
  "Suspense",
  "Supernatural",
]

DEFAULT_GRADES = ["PG", "16+", "A", "U", "U/A 7+", "U/A 13+", "U/A 16+", "18+"]

TAXONOMY_MODELS = {
  "categories": CategoryRecord,
  "genres": GenreRecord,
  "grades": GradeRecord,
}

APPROVAL_STATUS_LABELS = {
  "draft": "Draft",
  "pending_admin_review": "Pending Admin Review",
  "pending_super_admin_approval": "Pending Super Admin Approval",
  "approved": "Approved",
  "published": "Published",
  "changes_requested": "Changes Requested",
  "archived": "Archived",
}

CAST_CREDIT_SNAPSHOT_FIELDS = {"cast_credits"}

LEGACY_DEMO_MOVIE_IDS = {
  "solar-dominion",
  "monsoon-crown",
  "night-circuit",
  "harbor-flame",
  "atlas-run",
  "golden-memoir",
}

LEGACY_DEMO_QUEUE_IDS = {"queue-1", "queue-2"}

LEGACY_DEMO_SUBMISSION_NOTES = {
  "Teaser art, music drop, and reserve page complete.",
  "Featured in New Release section with active reward bonus.",
}

LEGACY_DEMO_USER_EMAILS = {
  "mahesh@cineproxima.com",
  "aarav@studioflow.com",
  "meera.viewer@example.com",
  "vikram.rewards@example.com",
}

MOVIE_RECORD_FIELDS = {
  "id",
  "archived",
  "stage",
  "title_category",
  "title",
  "title_caption",
  "poster",
  "genre",
  "stars_required",
  "online_pricing_options",
  "stars_required_theatre",
  "expected_stars",
  "reserve_enabled",
  "reserve_star_price",
  "buy_now_enabled",
  "release_decision",
  "reservation_close_at",
  "delivery_start_at",
  "password_publish_at",
  "release_passcode",
  "strict_target_required",
  "playback_requires_subscription",
  "stage_label",
  "countdown",
  "release_date",
  "description",
  "budget",
  "expected_revenue",
  "pricing_snapshot",
  "wish_count",
  "wish_online_count",
  "wish_theatre_count",
  "reserve_count",
  "revenue",
  "posters",
  "music",
  "reward_bonus",
}

QUEUE_RECORD_FIELDS = {
  "id",
  "title",
  "stage",
  "status",
  "note",
}

USER_RECORD_FIELDS = {
  "id",
  "name",
  "email",
  "password_hash",
  "role",
  "status",
  "points",
}

ADMIN_STATE_RECORD_FIELDS = {
  "featured_stage",
  "reward_campaign_boosts",
  "star_price_settings",
}


def _slugify(value: str) -> str:
  return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _approval_status_label(status: str) -> str:
  return APPROVAL_STATUS_LABELS.get(status, status.replace("_", " ").title())


def _derive_reservation_close_at(password_publish_at: str | None) -> str | None:
  if not password_publish_at:
    return None

  normalized = str(password_publish_at).strip()
  for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
    try:
      parsed = datetime.strptime(normalized, fmt)
      derived = parsed.timestamp() - (15 * 60)
      return datetime.fromtimestamp(derived).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
      continue
  return None


REVIEW_FIELD_ORDER = [
  "title_category",
  "title",
  "title_caption",
  "genre",
  "cast_credits",
  "stage_label",
  "release_date",
  "online_pricing_options",
  "stars_required",
  "stars_required_theatre",
  "expected_stars",
  "description",
  "poster",
  "posters",
  "music",
]

REVIEW_FIELD_LABELS = {
  "title_category": "Title Category",
  "title": "Title Name",
  "title_caption": "Title Caption",
  "genre": "Genre",
  "cast_credits": "Cast & Credits",
  "stage_label": "Stage",
  "release_date": "Release Date",
  "online_pricing_options": "Stars Required - Online",
  "stars_required": "Stars Required - Online",
  "stars_required_theatre": "Stars Required - Theatre",
  "expected_stars": "Target Stars",
  "buy_now_enabled": "Buy Now",
  "release_decision": "Release Decision",
  "reservation_close_at": "Reserve Closes",
  "delivery_start_at": "Delivery Start",
  "password_publish_at": "Password Publish",
  "strict_target_required": "Strict Target Rule",
  "playback_requires_subscription": "Subscription Check",
  "description": "Story Line",
  "poster": "Primary Poster",
  "posters": "Poster Summary",
  "music": "Music Summary",
}


def _json_dump(value: dict | list | None) -> str | None:
  if value is None:
    return None
  return json.dumps(value)


def _json_load(value: str | None, default):
  if not value:
    return deepcopy(default)
  try:
    return json.loads(value)
  except json.JSONDecodeError:
    return deepcopy(default)


def _normalize_cast_credit_entries(entries) -> list[dict]:
  normalized: list[dict] = []
  if not isinstance(entries, list):
    return normalized

  for item in entries:
    if not isinstance(item, dict):
      continue
    role = str(item.get("role") or "").strip()
    name = str(item.get("name") or "").strip()
    link = str(item.get("link") or "").strip() or None
    if not role or not name:
      continue
    normalized.append({
      "role": role,
      "name": name,
      "link": link,
    })
  return normalized


def _normalize_online_pricing_options(entries) -> list[dict]:
  normalized: list[dict] = []
  if isinstance(entries, str):
    entries = _json_load(entries, [])
  if not isinstance(entries, list):
    return normalized

  seen_codes: set[str] = set()
  for index, item in enumerate(entries):
    if not isinstance(item, dict):
      continue
    quality_code = str(item.get("quality_code") or "").strip().lower()
    quality_label = str(item.get("quality_label") or "").strip()
    stars_required = int(item.get("stars_required") or 0)
    sort_order = int(item.get("sort_order", index) or index)
    if not quality_code or not quality_label or stars_required <= 0 or quality_code in seen_codes:
      continue
    seen_codes.add(quality_code)
    normalized.append({
      "quality_code": quality_code,
      "quality_label": quality_label,
      "stars_required": stars_required,
      "sort_order": sort_order,
    })

  normalized.sort(key=lambda item: (item["sort_order"], item["quality_label"]))
  return normalized


def _load_online_pricing_options(raw_value: str | None) -> list[dict]:
  return _normalize_online_pricing_options(_json_load(raw_value, []))


def _dump_online_pricing_options(entries: list[dict] | None) -> str | None:
  normalized = _normalize_online_pricing_options(entries or [])
  return _json_dump(normalized) if normalized else None


def _derive_default_online_stars(entries: list[dict] | None) -> int:
  normalized = _normalize_online_pricing_options(entries or [])
  if not normalized:
    return 1
  return min(int(item["stars_required"]) for item in normalized)


def _load_cast_credits(raw_value: str | None) -> list[dict]:
  return _normalize_cast_credit_entries(_json_load(raw_value, []))


def _dump_cast_credits(entries: list[dict] | None) -> str | None:
  normalized = _normalize_cast_credit_entries(entries or [])
  return _json_dump(normalized) if normalized else None


def _movie_record_payload(payload: dict) -> dict:
  normalized = {key: value for key, value in deepcopy(payload).items() if key in MOVIE_RECORD_FIELDS}
  if "online_pricing_options" in normalized:
    normalized["online_pricing_options"] = _dump_online_pricing_options(normalized.get("online_pricing_options"))
  return normalized


def _queue_record_payload(payload: dict) -> dict:
  return {key: value for key, value in deepcopy(payload).items() if key in QUEUE_RECORD_FIELDS}


def _user_record_payload(payload: dict) -> dict:
  return {key: value for key, value in deepcopy(payload).items() if key in USER_RECORD_FIELDS}


def _admin_state_record_payload(payload: dict) -> dict:
  return {key: value for key, value in deepcopy(payload).items() if key in ADMIN_STATE_RECORD_FIELDS}


def _default_star_price_settings() -> dict:
  return {
    "price_inr": 50,
    "price_usd": 0.0,
    "price_eur": 0.0,
    "effective_from": None,
  }


def _normalize_star_price_settings(payload: dict | None) -> dict:
  settings = _default_star_price_settings()
  if not isinstance(payload, dict):
    return settings
  settings["price_inr"] = float(payload.get("price_inr", settings["price_inr"]) or settings["price_inr"])
  settings["price_usd"] = float(payload.get("price_usd", settings["price_usd"]) or settings["price_usd"])
  settings["price_eur"] = float(payload.get("price_eur", settings["price_eur"]) or settings["price_eur"])
  effective_from = payload.get("effective_from")
  settings["effective_from"] = str(effective_from).strip() if effective_from else None
  return settings


def _json_load_star_price_settings(value: str | None) -> dict:
  try:
    return _normalize_star_price_settings(json.loads(value)) if value else _default_star_price_settings()
  except json.JSONDecodeError:
    return _default_star_price_settings()


def _is_viewer_visible_status(status: str) -> bool:
  return status in {"approved", "published"}


def _star_price_settings_from_state(state: AdminStateRecord | None) -> dict:
  if state is None or not state.star_price_settings:
    return _default_star_price_settings()
  return _json_load_star_price_settings(state.star_price_settings)


def _admin_state_to_dict(state: AdminStateRecord) -> dict:
  settings = _star_price_settings_from_state(state)
  return {
    "featured_stage": state.featured_stage,
    "reward_campaign_boosts": state.reward_campaign_boosts,
    "star_price_settings": settings,
    "star_price_inr": settings["price_inr"],
    "star_price_usd": settings["price_usd"],
    "star_price_eur": settings["price_eur"],
    "star_price_effective_from": settings["effective_from"],
  }


def _current_star_price_settings(session: Session | None = None) -> dict:
  if session is None:
    return _default_star_price_settings()
  state = session.get(AdminStateRecord, 1)
  if state is None:
    return _default_star_price_settings()
  return _star_price_settings_from_state(state)


def _current_star_price_snapshot(session: Session | None = None) -> str:
  return json.dumps(_current_star_price_settings(session))


def _capture_movie_snapshot(movie: MovieRecord) -> dict:
  return _movie_record_payload(
    {
      "id": movie.id,
      "archived": movie.archived,
      "stage": movie.stage,
      "title_category": movie.title_category,
      "title": movie.title,
      "title_caption": movie.title_caption,
      "poster": movie.poster,
      "genre": movie.genre,
      "stars_required": movie.stars_required,
      "online_pricing_options": _load_online_pricing_options(movie.online_pricing_options),
      "stars_required_theatre": movie.stars_required_theatre,
      "expected_stars": movie.expected_stars,
      "reserve_enabled": movie.reserve_enabled,
      "reserve_star_price": movie.reserve_star_price,
      "buy_now_enabled": movie.buy_now_enabled,
      "release_decision": movie.release_decision,
      "reservation_close_at": movie.reservation_close_at,
      "delivery_start_at": movie.delivery_start_at,
      "password_publish_at": movie.password_publish_at,
      "release_passcode": movie.release_passcode,
      "strict_target_required": movie.strict_target_required,
      "playback_requires_subscription": movie.playback_requires_subscription,
      "stage_label": movie.stage_label,
      "countdown": movie.countdown,
      "release_date": movie.release_date,
      "description": movie.description,
      "budget": movie.budget,
      "expected_revenue": movie.expected_revenue,
      "pricing_snapshot": movie.pricing_snapshot,
      "wish_count": movie.wish_count,
      "wish_online_count": movie.wish_online_count,
      "wish_theatre_count": movie.wish_theatre_count,
      "reserve_count": movie.reserve_count,
      "revenue": movie.revenue,
      "posters": movie.posters,
      "music": movie.music,
      "reward_bonus": movie.reward_bonus,
    }
  )


def _capture_movie_snapshot_with_extras(session: Session, movie: MovieRecord) -> dict:
  payload = _capture_movie_snapshot(movie)
  linked_title = _get_linked_title_by_movie_id(session, movie.id)
  payload["cast_credits"] = _load_cast_credits(linked_title.cast_text if linked_title else None)
  return payload


def _capture_movie_asset_snapshot(movie_id: str) -> dict[str, list[str]]:
  base_path = LIBRARY_MEDIA_ROOT / movie_id
  snapshot = {
    "posters": [],
    "trailer": [],
    "gallery": [],
    "music": [],
    "content": [],
  }

  for orientation, label in (("vertical", "Vertical"), ("horizontal", "Horizontal")):
    folder = base_path / "posters" / orientation
    if folder.exists():
      snapshot["posters"].extend(f"{label}: {item.name}" for item in sorted(folder.iterdir()) if item.is_file())

  for kind, folder_name in (("trailer", "trailers"), ("gallery", "gallery"), ("music", "music"), ("content", "content")):
    folder = base_path / folder_name
    if folder.exists():
      snapshot[kind] = [item.name for item in sorted(folder.iterdir()) if item.is_file()]

  return snapshot


def _movie_snapshot_to_dict(snapshot: dict, approval_status: str = "published") -> dict:
  payload = _movie_record_payload(snapshot)
  payload["cast_credits"] = _normalize_cast_credit_entries(snapshot.get("cast_credits", []))
  payload["online_pricing_options"] = _normalize_online_pricing_options(snapshot.get("online_pricing_options", []))
  payload.setdefault("id", "")
  payload.setdefault("archived", False)
  payload.setdefault("stage", "upcoming")
  payload.setdefault("title_category", None)
  payload.setdefault("title", "Untitled")
  payload.setdefault("title_caption", None)
  payload.setdefault("poster", None)
  payload.setdefault("genre", "")
  payload.setdefault("cast_credits", [])
  payload.setdefault("stars_required", 1)
  payload.setdefault("online_pricing_options", [])
  payload.setdefault("stars_required_theatre", 3)
  payload.setdefault("expected_stars", 0)
  payload.setdefault("reserve_enabled", False)
  payload.setdefault("reserve_star_price", payload["stars_required"])
  payload.setdefault("buy_now_enabled", False)
  payload.setdefault("release_decision", "pending")
  payload.setdefault("reservation_close_at", None)
  payload.setdefault("delivery_start_at", None)
  payload.setdefault("password_publish_at", None)
  payload.setdefault("release_passcode", None)
  payload.setdefault("strict_target_required", False)
  payload.setdefault("playback_requires_subscription", True)
  payload.setdefault("stage_label", "Upcoming")
  payload.setdefault("countdown", "Release date to be confirmed")
  payload.setdefault("release_date", "TBA")
  payload.setdefault("description", "")
  payload.setdefault("budget", "TBD")
  payload.setdefault("expected_revenue", f'{payload["expected_stars"]} stars')
  payload.setdefault("wish_count", 0)
  payload.setdefault("wish_online_count", 0)
  payload.setdefault("wish_theatre_count", 0)
  payload.setdefault("reserve_count", 0)
  payload.setdefault("revenue", "$0K")
  payload.setdefault("posters", "Poster upload pending")
  payload.setdefault("music", "Music upload pending")
  payload.setdefault("reward_bonus", "+0 pts")
  payload["approval_status"] = approval_status
  payload["approval_status_label"] = _approval_status_label(approval_status)
  payload["requires_super_admin_approval"] = approval_status in {"pending_admin_review", "pending_super_admin_approval", "changes_requested"}
  return payload


def _apply_movie_snapshot(movie: MovieRecord, snapshot: dict) -> None:
  payload = _movie_record_payload(snapshot)
  for key, value in payload.items():
    setattr(movie, key, value)


def _get_movie_change_request(session: Session, movie_id: str) -> MovieChangeRequestRecord | None:
  return session.query(MovieChangeRequestRecord).filter(MovieChangeRequestRecord.movie_id == movie_id).first()


def _prepare_movie_change_request(
  session: Session,
  movie: MovieRecord,
  *,
  status: str = "pending_super_admin_approval",
  is_new_title: bool = False,
  capture_assets: bool = False,
) -> tuple[MovieChangeRequestRecord, dict]:
  change_request = _get_movie_change_request(session, movie.id)
  current_snapshot = _capture_movie_snapshot_with_extras(session, movie)
  current_assets = _capture_movie_asset_snapshot(movie.id) if capture_assets else None

  if change_request is None:
    change_request = MovieChangeRequestRecord(
      movie_id=movie.id,
      status=status,
      baseline_snapshot=_json_dump({} if is_new_title else current_snapshot),
      pending_snapshot=_json_dump(current_snapshot),
      baseline_assets_snapshot=_json_dump({} if is_new_title and capture_assets else current_assets if capture_assets else None),
      pending_assets_snapshot=_json_dump(current_assets if capture_assets else None),
      created_at=datetime.utcnow(),
      updated_at=datetime.utcnow(),
    )
    session.add(change_request)
    session.flush()
    return change_request, deepcopy(current_snapshot)

  if not change_request.baseline_snapshot:
    change_request.baseline_snapshot = _json_dump({} if is_new_title else current_snapshot)
  pending_snapshot = _json_load(change_request.pending_snapshot, current_snapshot)
  if not pending_snapshot:
    pending_snapshot = deepcopy(current_snapshot)
  change_request.pending_snapshot = _json_dump(pending_snapshot)

  if capture_assets:
    if not change_request.baseline_assets_snapshot:
      change_request.baseline_assets_snapshot = _json_dump(current_assets)
    if not change_request.pending_assets_snapshot:
      change_request.pending_assets_snapshot = _json_dump(current_assets)

  change_request.status = status
  change_request.updated_at = datetime.utcnow()
  session.flush()
  return change_request, deepcopy(pending_snapshot)


def _save_pending_movie_snapshot(change_request: MovieChangeRequestRecord, snapshot: dict) -> None:
  payload = _movie_record_payload(snapshot)
  for key in CAST_CREDIT_SNAPSHOT_FIELDS:
    if key in snapshot:
      payload[key] = deepcopy(snapshot.get(key))
  change_request.pending_snapshot = _json_dump(payload)
  change_request.updated_at = datetime.utcnow()


def _save_pending_asset_snapshot(change_request: MovieChangeRequestRecord, snapshot: dict[str, list[str]]) -> None:
  change_request.pending_assets_snapshot = _json_dump(snapshot)
  change_request.updated_at = datetime.utcnow()


def _movie_to_dict(
  movie: MovieRecord,
  approval_status: str = "published",
  viewer_wish_kind: str | None = None,
  viewer_reservation_status: str | None = None,
  viewer_reservation_online_status: str | None = None,
  viewer_reservation_theatre_status: str | None = None,
  cast_credits: list[dict] | None = None,
  ) -> dict:
  return {
    "id": movie.id,
    "archived": movie.archived,
    "stage": movie.stage,
    "approval_status": approval_status,
    "approval_status_label": _approval_status_label(approval_status),
    "requires_super_admin_approval": approval_status in {"pending_admin_review", "pending_super_admin_approval", "changes_requested"},
    "title_category": movie.title_category,
    "title": movie.title,
    "title_caption": movie.title_caption,
    "poster": movie.poster,
    "genre": movie.genre,
    "cast_credits": _normalize_cast_credit_entries(cast_credits or []),
    "stars_required": movie.stars_required,
    "online_pricing_options": _load_online_pricing_options(movie.online_pricing_options),
    "stars_required_theatre": movie.stars_required_theatre,
    "expected_stars": movie.expected_stars,
    "reserve_enabled": movie.reserve_enabled,
    "reserve_star_price": movie.reserve_star_price,
    "buy_now_enabled": movie.buy_now_enabled,
    "release_decision": movie.release_decision,
    "reservation_close_at": movie.reservation_close_at,
    "delivery_start_at": movie.delivery_start_at,
    "password_publish_at": movie.password_publish_at,
    "release_passcode": movie.release_passcode,
    "strict_target_required": movie.strict_target_required,
    "playback_requires_subscription": movie.playback_requires_subscription,
    "viewer_reservation_status": viewer_reservation_status,
    "viewer_reservation_online_status": viewer_reservation_online_status,
    "viewer_reservation_theatre_status": viewer_reservation_theatre_status,
    "stage_label": movie.stage_label,
    "countdown": movie.countdown,
    "release_date": movie.release_date,
    "description": movie.description,
    "budget": movie.budget,
    "expected_revenue": movie.expected_revenue,
    "wish_count": movie.wish_count,
    "wish_online_count": movie.wish_online_count,
    "wish_theatre_count": movie.wish_theatre_count,
    "viewer_wish_kind": viewer_wish_kind,
    "reserve_count": movie.reserve_count,
    "revenue": movie.revenue,
    "posters": movie.posters,
    "music": movie.music,
    "reward_bonus": movie.reward_bonus,
  }


def _movie_to_dict_for_session(
  session: Session,
  movie: MovieRecord,
  approval_status: str = "published",
  viewer_wish_kind: str | None = None,
  viewer_reservation_status: str | None = None,
  viewer_reservation_online_status: str | None = None,
  viewer_reservation_theatre_status: str | None = None,
) -> dict:
  linked_title = _get_linked_title_by_movie_id(session, movie.id)
  return _movie_to_dict(
    movie,
    approval_status,
    viewer_wish_kind,
    viewer_reservation_status,
    viewer_reservation_online_status,
    viewer_reservation_theatre_status,
    _load_cast_credits(linked_title.cast_text if linked_title else None),
  )


def _queue_to_dict(item: QueueItemRecord) -> dict:
  return {
    "id": item.id,
    "title": item.title,
    "stage": item.stage,
    "status": item.status,
    "note": item.note,
  }


def _user_to_dict(user: UserRecord, wallet: WalletRecord | None = None) -> dict:
  star_balance = wallet.available_stars if wallet is not None else max(user.points // 100, 0)
  blocked_stars = wallet.blocked_stars if wallet is not None else 0
  disc_balance = wallet.disks if wallet is not None else max(user.points * 10, 0)
  return {
    "id": user.id,
    "name": user.name,
    "email": user.email,
    "role": user.role,
    "status": user.status,
    "points": user.points,
    "star_balance": star_balance,
    "blocked_stars": blocked_stars,
    "disc_balance": disc_balance,
  }


def _password_hash(value: str) -> str:
  return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _taxonomy_to_dict(item: CategoryRecord | GenreRecord | GradeRecord) -> dict:
  return {
    "id": item.id,
    "slug": item.slug,
    "name": item.name,
    "description": getattr(item, "description", None),
    "sort_order": item.sort_order,
    "is_active": item.is_active,
  }


def _seed_taxonomies(session: Session) -> None:
  if session.query(CategoryRecord).first() is None:
    session.add_all(CategoryRecord(**item) for item in deepcopy(DEFAULT_CATEGORIES))

  if session.query(GenreRecord).first() is None:
    session.add_all(
      GenreRecord(slug=_slugify(name), name=name, sort_order=index + 1)
      for index, name in enumerate(DEFAULT_GENRES)
    )

  if session.query(GradeRecord).first() is None:
    session.add_all(
      GradeRecord(slug=_slugify(name), name=name, sort_order=index + 1)
      for index, name in enumerate(DEFAULT_GRADES)
    )


def _seed_profiles(session: Session) -> None:
  creator_user = session.query(UserRecord).filter(UserRecord.role == "producer").first()
  if creator_user and session.query(CreatorProfileRecord).filter(CreatorProfileRecord.user_id == creator_user.id).first() is None:
    session.add(
      CreatorProfileRecord(
        user_id=creator_user.id,
        display_name=creator_user.name,
        company_name="StudioFlow",
        contact_email=creator_user.email,
      )
    )

  advertiser_user = session.query(UserRecord).filter(UserRecord.role == "advertiser").first()
  if advertiser_user and session.query(AdvertiserProfileRecord).filter(AdvertiserProfileRecord.user_id == advertiser_user.id).first() is None:
    session.add(
      AdvertiserProfileRecord(
        user_id=advertiser_user.id,
        display_name=advertiser_user.name,
        company_name="Advertiser",
        contact_email=advertiser_user.email,
      )
    )


def _seed_wallets(session: Session) -> None:
  users = session.query(UserRecord).all()
  for user in users:
    if session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first() is None:
      session.add(
        WalletRecord(
          user_id=user.id,
          available_stars=max(user.points // 100, 0),
          blocked_stars=0,
          disks=user.points * 10,
        )
      )


def _seed_titles(session: Session) -> None:
  if session.query(TitleRecord).first() is not None:
    return

  movie_category = session.query(CategoryRecord).filter(CategoryRecord.slug == "movies").first()
  genre_lookup = {genre.name: genre for genre in session.query(GenreRecord).all()}
  grade = session.query(GradeRecord).filter(GradeRecord.name == "PG").first()
  creator_user = session.query(UserRecord).filter(UserRecord.role == "producer").first()

  for movie in MOVIES:
    title = TitleRecord(
      slug=movie["id"],
      legacy_movie_id=movie["id"],
      title_name=movie["title"],
      caption=movie["countdown"],
      category_id=movie_category.id if movie_category else None,
      creator_user_id=creator_user.id if creator_user else None,
      stage=movie["stage"],
      availability_type="reserve_now" if movie["stage"] == "upcoming" else "pay_now" if movie["stage"] == "released" else "free_with_ads",
      status="archived" if movie.get("archived", False) else "published",
      archived=movie.get("archived", False),
      grade_id=grade.id if grade else None,
      story_text=movie["description"],
      duration_text=None,
      cast_text=None,
      production_house=None,
      release_date_text=movie["release_date"],
      tentative_release_date_text=movie["release_date"] if movie["stage"] == "upcoming" else None,
      reserve_star_price=movie.get("reserve_star_price", 0),
      online_pricing_options=_dump_online_pricing_options(movie.get("online_pricing_options", [])),
      reserve_enabled=movie.get("reserve_enabled", False),
      buy_now_enabled=movie.get("buy_now_enabled", False),
      release_decision=movie.get("release_decision", "pending"),
      reservation_close_at=movie.get("reservation_close_at"),
      delivery_start_at=movie.get("delivery_start_at"),
      password_publish_at=movie.get("password_publish_at"),
      strict_target_required=movie.get("strict_target_required", False),
      playback_requires_subscription=movie.get("playback_requires_subscription", True),
      cancellation_lock_days=7 if movie["stage"] == "upcoming" else None,
      expected_revenue_target=movie["expected_revenue"],
      pricing_snapshot=_current_star_price_snapshot(session),
      current_reserved_stars=movie["reserve_count"],
      current_wish_count=movie["wish_count"],
    )
    session.add(title)
    session.flush()

    genre = genre_lookup.get(movie["genre"])
    if genre:
      session.add(TitleGenreRecord(title_id=title.id, genre_id=genre.id))

    poster_path = movie.get("poster")
    if poster_path:
      session.add(
        TitlePosterRecord(
          title_id=title.id,
          relative_path=poster_path,
          orientation="vertical",
          label="default",
          is_active=True,
        )
      )

    session.add(
      TitleMusicRecord(
        title_id=title.id,
        relative_path=f"content-root/{movie['id']}/music/theme.mp3",
        music_type="theme",
        label=movie["music"],
        is_primary=True,
        is_active=True,
      )
    )
    session.add(
      TitleTrailerRecord(
        title_id=title.id,
        relative_path=f"content-root/{movie['id']}/trailers/main-trailer.mp4",
        media_type="trailer",
        is_primary=True,
        is_active=True,
      )
    )
    session.add(
      TitleContentFileRecord(
        title_id=title.id,
        relative_path=f"content-root/{movie['id']}/content/main-feature.mp4",
        content_part_type="main_feature",
        is_primary=True,
        is_active=True,
      )
    )


def _seed_publish_submissions(session: Session) -> None:
  if session.query(PublishSubmissionRecord).first() is not None:
    return
  creator_user = session.query(UserRecord).filter(UserRecord.role == "producer").first()
  for item in PUBLISH_QUEUE:
    session.add(
      PublishSubmissionRecord(
        creator_user_id=creator_user.id if creator_user else None,
        submission_type="publish",
        status=item["status"].lower().replace(" ", "_"),
        note=item["note"],
      )
    )


def _purge_legacy_demo_library(session: Session) -> None:
  demo_titles = session.query(TitleRecord).filter(TitleRecord.legacy_movie_id.in_(LEGACY_DEMO_MOVIE_IDS)).all()
  demo_title_ids = [item.id for item in demo_titles]
  if demo_title_ids:
    session.query(MovieChangeRequestRecord).filter(MovieChangeRequestRecord.movie_id.in_(LEGACY_DEMO_MOVIE_IDS)).delete(synchronize_session=False)
    session.query(TitlePosterRecord).filter(TitlePosterRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleMusicRecord).filter(TitleMusicRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleTrailerRecord).filter(TitleTrailerRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleSubtitleTrackRecord).filter(TitleSubtitleTrackRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleAudioTrackRecord).filter(TitleAudioTrackRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleContentFileRecord).filter(TitleContentFileRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleGenreRecord).filter(TitleGenreRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleLanguageRecord).filter(TitleLanguageRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(ReservationRecord).filter(ReservationRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(PublishSubmissionRecord).filter(PublishSubmissionRecord.title_id.in_(demo_title_ids)).delete(synchronize_session=False)
    session.query(TitleRecord).filter(TitleRecord.id.in_(demo_title_ids)).delete(synchronize_session=False)

  session.query(PublishSubmissionRecord).filter(
    PublishSubmissionRecord.title_id.is_(None),
    PublishSubmissionRecord.note.in_(LEGACY_DEMO_SUBMISSION_NOTES),
  ).delete(synchronize_session=False)
  session.query(QueueItemRecord).filter(QueueItemRecord.id.in_(LEGACY_DEMO_QUEUE_IDS)).delete(synchronize_session=False)
  session.query(MovieRecord).filter(MovieRecord.id.in_(LEGACY_DEMO_MOVIE_IDS)).delete(synchronize_session=False)


def _purge_legacy_demo_users(session: Session) -> None:
  legacy_users = session.query(UserRecord).filter(UserRecord.email.in_(LEGACY_DEMO_USER_EMAILS)).all()
  legacy_user_ids = [user.id for user in legacy_users]
  if not legacy_user_ids:
    return

  session.query(TitleRecord).filter(TitleRecord.creator_user_id.in_(legacy_user_ids)).update(
    {TitleRecord.creator_user_id: None},
    synchronize_session=False,
  )
  session.query(PublishSubmissionRecord).filter(PublishSubmissionRecord.creator_user_id.in_(legacy_user_ids)).update(
    {PublishSubmissionRecord.creator_user_id: None},
    synchronize_session=False,
  )
  session.query(CreatorProfileRecord).filter(CreatorProfileRecord.user_id.in_(legacy_user_ids)).delete(synchronize_session=False)
  session.query(AdvertiserProfileRecord).filter(AdvertiserProfileRecord.user_id.in_(legacy_user_ids)).delete(synchronize_session=False)
  session.query(WalletRecord).filter(WalletRecord.user_id.in_(legacy_user_ids)).delete(synchronize_session=False)
  session.query(UserRecord).filter(UserRecord.id.in_(legacy_user_ids)).delete(synchronize_session=False)


def _get_taxonomy_model(kind: str):
  model = TAXONOMY_MODELS.get(kind)
  if model is None:
    raise ValueError(f"Unsupported taxonomy kind: {kind}")
  return model


def ensure_seeded(session: Session) -> None:
  _purge_legacy_demo_library(session)
  _purge_legacy_demo_users(session)

  if session.query(MovieRecord).first() is None:
    star_price_snapshot = _current_star_price_snapshot(session)
    session.add_all(
      MovieRecord(**{**_movie_record_payload(movie), "pricing_snapshot": star_price_snapshot})
      for movie in MOVIES
    )

  if session.query(QueueItemRecord).first() is None:
    session.add_all(QueueItemRecord(**_queue_record_payload(item)) for item in PUBLISH_QUEUE)

  if session.query(UserRecord).first() is None:
    session.add_all(UserRecord(**_user_record_payload(user)) for user in USERS)
  elif session.query(UserRecord).filter(UserRecord.email == "kamarthi.anil@gmail.com").first() is None:
    session.add(UserRecord(**_user_record_payload(USERS[0])))

  if session.get(AdminStateRecord, 1) is None:
    admin_state_payload = _admin_state_record_payload(ADMIN_STATE)
    admin_state_payload["star_price_settings"] = json.dumps(_default_star_price_settings())
    session.add(AdminStateRecord(id=1, **admin_state_payload))
  else:
    state = session.get(AdminStateRecord, 1)
    if state is not None and not state.star_price_settings:
      state.star_price_settings = json.dumps(_default_star_price_settings())

  _seed_taxonomies(session)
  _cleanup_language_taxonomy(session)
  session.flush()
  _seed_profiles(session)
  _seed_wallets(session)
  _seed_titles(session)
  _seed_publish_submissions(session)

  session.commit()


def _cleanup_language_taxonomy(session: Session) -> None:
  session.query(TitleLanguageRecord).delete()
  session.query(TitleSubtitleTrackRecord).update({TitleSubtitleTrackRecord.language_id: None})
  session.query(TitleAudioTrackRecord).update({TitleAudioTrackRecord.language_id: None})
  session.query(LanguageRecord).delete()


def _resolve_movie_approval_statuses(session: Session, movie_ids: list[str]) -> dict[str, str]:
  if not movie_ids:
    return {}

  rows = (
    session.query(TitleRecord.legacy_movie_id, TitleRecord.status, TitleRecord.archived)
    .filter(TitleRecord.legacy_movie_id.in_(movie_ids))
    .all()
  )
  status_map: dict[str, str] = {}
  for legacy_movie_id, status, archived in rows:
    if not legacy_movie_id:
      continue
    status_map[str(legacy_movie_id)] = "archived" if archived else status or "published"
  return status_map


def _resolve_movie_change_requests(session: Session, movie_ids: list[str]) -> dict[str, MovieChangeRequestRecord]:
  if not movie_ids:
    return {}
  rows = session.query(MovieChangeRequestRecord).filter(MovieChangeRequestRecord.movie_id.in_(movie_ids)).all()
  return {row.movie_id: row for row in rows}


def _resolve_viewer_wishes(session: Session, user_id: str | None, movie_ids: list[str]) -> dict[str, str]:
  if not user_id or not movie_ids:
    return {}
  rows = (
    session.query(MovieWishRecord)
    .filter(MovieWishRecord.user_id == user_id, MovieWishRecord.movie_id.in_(movie_ids))
    .all()
  )
  return {row.movie_id: row.wish_kind for row in rows}


def _resolve_viewer_reservations(session: Session, user_id: str | None, movie_ids: list[str]) -> dict[str, dict[str, str]]:
  if not user_id or not movie_ids:
    return {}
  title_rows = session.query(TitleRecord.id, TitleRecord.legacy_movie_id).filter(TitleRecord.legacy_movie_id.in_(movie_ids)).all()
  title_by_movie = {legacy_movie_id: title_id for title_id, legacy_movie_id in title_rows if legacy_movie_id}
  if not title_by_movie:
    return {}
  reservations = (
    session.query(ReservationRecord)
    .filter(
      ReservationRecord.user_id == user_id,
      ReservationRecord.title_id.in_(list(title_by_movie.values())),
      ReservationRecord.status.in_(["blocked", "fulfilled"]),
    )
    .all()
  )
  movie_by_title = {title_id: movie_id for movie_id, title_id in title_by_movie.items()}
  reservation_map: dict[str, dict[str, str]] = {}
  for reservation in reservations:
    if reservation.title_id not in movie_by_title:
      continue
    movie_id = movie_by_title[reservation.title_id]
    mode = (reservation.reservation_kind or "online").strip().lower()
    if mode not in {"online", "theatre"}:
      mode = "online"
    reservation_map.setdefault(movie_id, {})[mode] = reservation.status
  return reservation_map


def _combine_viewer_reservation_status(mode_map: dict[str, str] | None) -> str | None:
  if not mode_map:
    return None
  if mode_map.get("online") in {"blocked", "fulfilled"}:
    return mode_map.get("online")
  if mode_map.get("theatre") in {"blocked", "fulfilled"}:
    return mode_map.get("theatre")
  return None


def _movie_release_is_live(movie: MovieRecord) -> bool:
  if movie.stage != "released":
    return False
  password_publish_at = str(movie.password_publish_at or "").strip()
  if not password_publish_at:
    return False
  try:
    return datetime.fromisoformat(password_publish_at) <= datetime.now()
  except ValueError:
    return False


def _sync_live_release_entitlements(session: Session, movies: list[MovieRecord]) -> None:
  for movie in movies:
    if not _movie_release_is_live(movie):
      continue
    linked_title = _get_linked_title_by_movie_id(session, movie.id)
    if linked_title is None:
      continue
    blocked_exists = (
      session.query(ReservationRecord.id)
      .filter(
        ReservationRecord.title_id == linked_title.id,
        ReservationRecord.status == "blocked",
      )
      .first()
    )
    if blocked_exists is not None:
      commit_movie_reservations(session, movie.id)


def _notification_to_dict(notification: NotificationRecord) -> dict:
  return {
    "id": notification.id,
    "movie_id": notification.movie_id,
    "notification_type": notification.notification_type,
    "title": notification.title,
    "message": notification.message,
    "is_read": notification.is_read,
    "read_at": notification.read_at.isoformat(timespec="minutes") if notification.read_at else None,
    "created_at": notification.created_at.isoformat(timespec="minutes"),
  }


def _resolve_viewer_notifications(session: Session, user_id: str | None, limit: int = 10) -> list[dict]:
  if not user_id:
    return []
  rows = (
    session.query(NotificationRecord)
    .filter(NotificationRecord.user_id == user_id)
    .order_by(NotificationRecord.created_at.desc(), NotificationRecord.id.desc())
    .limit(limit)
    .all()
  )
  return [_notification_to_dict(row) for row in rows]


def _notify_wishers_for_reserve_start(session: Session, movie: MovieRecord) -> int:
  wish_user_ids = [
    row[0]
    for row in session.query(MovieWishRecord.user_id)
    .filter(MovieWishRecord.movie_id == movie.id)
    .distinct()
    .all()
  ]
  if not wish_user_ids:
    return 0

  count = 0
  for user_id in wish_user_ids:
    session.add(
      NotificationRecord(
        user_id=user_id,
        movie_id=movie.id,
        notification_type="reserve_start",
        title=movie.title,
        message=f'Reserve Now is now active for "{movie.title}". Open the title to reserve your stars.',
        created_at=datetime.utcnow(),
      )
    )
    count += 1
  return count


def _movie_list_to_dicts(
  session: Session,
  movies: list[MovieRecord],
  prefer_pending: bool = False,
  viewer_user_id: str | None = None,
) -> list[dict]:
  movie_ids = [movie.id for movie in movies]
  status_map = _resolve_movie_approval_statuses(session, movie_ids)
  change_requests = _resolve_movie_change_requests(session, movie_ids) if prefer_pending else {}
  linked_titles = {
    title.legacy_movie_id: title
    for title in session.query(TitleRecord).filter(TitleRecord.legacy_movie_id.in_(movie_ids)).all()
    if title.legacy_movie_id
  }
  viewer_wish_map = _resolve_viewer_wishes(session, viewer_user_id, movie_ids)
  viewer_reservation_map = _resolve_viewer_reservations(session, viewer_user_id, movie_ids)
  items = []
  for movie in movies:
    approval_status = "archived" if movie.archived else status_map.get(movie.id, "published")
    reservation_modes = viewer_reservation_map.get(movie.id, {})
    combined_reservation_status = _combine_viewer_reservation_status(reservation_modes)
    if prefer_pending:
      change_request = change_requests.get(movie.id)
      pending_snapshot = _json_load(change_request.pending_snapshot, {}) if change_request else {}
      if pending_snapshot and approval_status in {"pending_super_admin_approval", "changes_requested"}:
        pending_item = _movie_snapshot_to_dict(pending_snapshot, approval_status)
        pending_item["viewer_wish_kind"] = viewer_wish_map.get(movie.id)
        pending_item["viewer_reservation_status"] = combined_reservation_status
        pending_item["viewer_reservation_online_status"] = reservation_modes.get("online")
        pending_item["viewer_reservation_theatre_status"] = reservation_modes.get("theatre")
        items.append(pending_item)
        continue
    items.append(
      _movie_to_dict(
        movie,
        approval_status,
        viewer_wish_map.get(movie.id),
        combined_reservation_status,
        reservation_modes.get("online"),
        reservation_modes.get("theatre"),
        _load_cast_credits(linked_titles.get(movie.id).cast_text if linked_titles.get(movie.id) else None),
      )
    )
  return items


def _format_review_value(value) -> str:
  if value is None:
    return "Not set"
  online_options = _normalize_online_pricing_options(value)
  if online_options:
    return ", ".join(
      f'{item["quality_label"]}: {item["stars_required"]} {"Star" if int(item["stars_required"]) == 1 else "Stars"}'
      for item in online_options
    )
  if isinstance(value, bool):
    return "Yes" if value else "No"
  if isinstance(value, (list, tuple, set)):
    return ", ".join(str(item) for item in value) if value else "Not set"
  string_value = str(value).strip()
  return string_value if string_value else "Not set"


def get_movie_approval_review(session: Session, movie_id: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None

  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  change_request = _get_movie_change_request(session, movie.id)
  current_snapshot = _capture_movie_snapshot_with_extras(session, movie)
  pending_snapshot = _json_load(change_request.pending_snapshot if change_request else None, current_snapshot)
  baseline_snapshot = _json_load(change_request.baseline_snapshot if change_request else None, {})

  current_assets = _json_load(change_request.baseline_assets_snapshot if change_request else None, _capture_movie_asset_snapshot(movie.id))
  pending_assets = _json_load(change_request.pending_assets_snapshot if change_request else None, current_assets)

  changes = []
  comparison_current = baseline_snapshot if baseline_snapshot else {}
  for field in REVIEW_FIELD_ORDER:
    current_value = _format_review_value(comparison_current.get(field))
    pending_value = _format_review_value(pending_snapshot.get(field))
    if current_value == pending_value:
      continue
    changes.append(
      {
        "field": field,
        "label": REVIEW_FIELD_LABELS.get(field, field.replace("_", " ").title()),
        "current_value": current_value,
        "pending_value": pending_value,
      }
    )

  asset_changes = []
  for kind, label in (("posters", "Posters"), ("trailer", "Trailer"), ("gallery", "Gallery"), ("music", "Music"), ("content", "Content")):
    current_items = [str(item) for item in current_assets.get(kind, [])]
    pending_items = [str(item) for item in pending_assets.get(kind, current_items)]
    added_items = [item for item in pending_items if item not in current_items]
    removed_items = [item for item in current_items if item not in pending_items]
    if not added_items and not removed_items:
      continue
    asset_changes.append(
      {
        "kind": kind,
        "label": label,
        "current_items": current_items,
        "pending_items": pending_items,
        "added_items": added_items,
        "removed_items": removed_items,
      }
    )

  return {
    "item": _movie_snapshot_to_dict(pending_snapshot, approval_status),
    "current_item": _movie_snapshot_to_dict(baseline_snapshot, "approved" if approval_status != "archived" else "archived") if baseline_snapshot else None,
    "pending_item": _movie_snapshot_to_dict(pending_snapshot, approval_status),
    "changes": changes,
    "asset_changes": asset_changes,
    "has_pending_changes": bool(change_request or changes or asset_changes),
  }


def _ensure_linked_title(session: Session, movie: MovieRecord, approval_status: str = "pending_super_admin_approval") -> TitleRecord:
  linked_title = session.query(TitleRecord).filter(TitleRecord.legacy_movie_id == movie.id).first()
  if linked_title is not None:
    return linked_title

  category = None
  if movie.title_category:
    category = session.query(CategoryRecord).filter(CategoryRecord.name == movie.title_category).first()
  creator_user = session.query(UserRecord).filter(UserRecord.role.in_(["producer", "creator"])).first()
  linked_title = TitleRecord(
    slug=movie.id,
    legacy_movie_id=movie.id,
    title_name=movie.title,
    caption=movie.title_caption,
    category_id=category.id if category else None,
    creator_user_id=creator_user.id if creator_user else None,
    stage=movie.stage,
    availability_type="reserve_now" if movie.stage == "upcoming" else "pay_now" if movie.stage == "released" else "free_with_ads",
    status=approval_status,
    archived=movie.archived,
    grade_id=None,
    story_text=movie.description,
    duration_text=None,
    cast_text=None,
    production_house=None,
    release_date_text=movie.release_date,
    tentative_release_date_text=movie.release_date if movie.stage == "upcoming" else None,
    reserve_star_price=movie.reserve_star_price or movie.stars_required,
    online_pricing_options=movie.online_pricing_options,
    reserve_enabled=movie.reserve_enabled,
    buy_now_enabled=movie.buy_now_enabled,
    release_decision=movie.release_decision,
    reservation_close_at=movie.reservation_close_at,
    delivery_start_at=movie.delivery_start_at,
    password_publish_at=movie.password_publish_at,
    release_passcode=movie.release_passcode,
    strict_target_required=movie.strict_target_required,
    playback_requires_subscription=movie.playback_requires_subscription,
    cancellation_lock_days=7 if movie.stage == "upcoming" else None,
    expected_revenue_target=movie.expected_revenue,
    current_reserved_stars=movie.reserve_count,
    current_wish_count=movie.wish_count,
  )
  session.add(linked_title)
  session.flush()
  return linked_title


def _get_linked_title_by_movie_id(session: Session, movie_id: str) -> TitleRecord | None:
  return session.query(TitleRecord).filter(TitleRecord.legacy_movie_id == movie_id).first()


def _set_movie_approval_status(session: Session, movie: MovieRecord, status: str) -> str:
  linked_title = _ensure_linked_title(session, movie, status)
  linked_title.status = "archived" if movie.archived else status
  linked_title.archived = movie.archived
  linked_title.stage = movie.stage
  linked_title.availability_type = "reserve_now" if movie.stage == "upcoming" else "pay_now" if movie.stage == "released" else "free_with_ads"
  linked_title.title_name = movie.title
  linked_title.caption = movie.title_caption
  linked_title.story_text = movie.description
  linked_title.release_date_text = movie.release_date
  linked_title.reserve_enabled = movie.reserve_enabled
  linked_title.reserve_star_price = movie.reserve_star_price or movie.stars_required
  linked_title.online_pricing_options = movie.online_pricing_options
  linked_title.buy_now_enabled = movie.buy_now_enabled
  linked_title.release_decision = movie.release_decision
  linked_title.reservation_close_at = movie.reservation_close_at
  linked_title.delivery_start_at = movie.delivery_start_at
  linked_title.password_publish_at = movie.password_publish_at
  linked_title.release_passcode = movie.release_passcode
  linked_title.strict_target_required = movie.strict_target_required
  linked_title.playback_requires_subscription = movie.playback_requires_subscription
  linked_title.current_reserved_stars = movie.reserve_count
  linked_title.current_wish_count = movie.wish_count
  if movie.stage == "upcoming":
    linked_title.tentative_release_date_text = movie.release_date
  else:
    linked_title.tentative_release_date_text = None
  return linked_title.status


def _set_linked_title_cast_credits(session: Session, movie_id: str, cast_credits: list[dict] | None) -> None:
  linked_title = _get_linked_title_by_movie_id(session, movie_id)
  if linked_title is None:
    movie = session.get(MovieRecord, movie_id)
    if movie is None:
      return
    linked_title = _ensure_linked_title(session, movie)
  linked_title.cast_text = _dump_cast_credits(cast_credits)


def list_movies(
  session: Session,
  stage: str | None = None,
  include_archived: bool = False,
  prefer_pending: bool = False,
  viewer_user_id: str | None = None,
) -> list[dict]:
  ensure_seeded(session)
  query = session.query(MovieRecord)
  if not include_archived:
    query = query.filter(MovieRecord.archived.is_(False))
  if stage:
    query = query.filter(MovieRecord.stage == stage)
  movies = query.order_by(MovieRecord.title.asc()).all()
  _sync_live_release_entitlements(session, movies)
  items = _movie_list_to_dicts(session, movies, prefer_pending=prefer_pending, viewer_user_id=viewer_user_id)
  if not include_archived:
    items = [item for item in items if _is_viewer_visible_status(item["approval_status"])]
  return items


def start_movie_reserve(session: Session, movie_id: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None or movie.archived:
    return None
  if movie.buy_now_enabled and not movie.reserve_enabled:
    raise ValueError("Reserve Now cannot be restarted after this title has moved into Buy Now.")
  if not movie.reserve_enabled and not _load_online_pricing_options(movie.online_pricing_options):
    raise ValueError("Please add at least one online movie quality with pricing before starting Reserve Now.")
  movie.reserve_enabled = not movie.reserve_enabled
  if movie.reserve_enabled:
    movie.reserve_star_price = movie.stars_required
    movie.buy_now_enabled = False
  linked_title = _ensure_linked_title(session, movie)
  linked_title.reserve_enabled = movie.reserve_enabled
  if movie.reserve_enabled:
    linked_title.reserve_star_price = movie.stars_required
    linked_title.buy_now_enabled = False
    _notify_wishers_for_reserve_start(session, movie)
  session.commit()
  session.refresh(movie)
  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  return _movie_to_dict_for_session(session, movie, approval_status)


def commit_movie_reservations(session: Session, movie_id: str) -> tuple[dict, int] | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None or movie.archived:
    return None
  linked_title = _get_linked_title_by_movie_id(session, movie.id)
  if linked_title is None:
    linked_title = _ensure_linked_title(session, movie)

  blocked_reservations = (
    session.query(ReservationRecord)
    .filter(
      ReservationRecord.title_id == linked_title.id,
      ReservationRecord.status == "blocked",
    )
    .all()
  )

  committed_count = 0
  for reservation in blocked_reservations:
    wallet = session.query(WalletRecord).filter(WalletRecord.user_id == reservation.user_id).first()
    if wallet is None:
      wallet = WalletRecord(user_id=reservation.user_id, available_stars=0, blocked_stars=0, disks=0)
      session.add(wallet)
      session.flush()

    committed_stars = int(reservation.stars_required or 0)
    wallet.blocked_stars = max(0, int(wallet.blocked_stars or 0) - committed_stars)
    session.add(
      WalletTransactionRecord(
        user_id=reservation.user_id,
        transaction_type="reserve_commit",
        stars_delta=0,
        blocked_stars_delta=-committed_stars,
        disks_delta=0,
        reference_type="movie",
        reference_id=movie.id,
        note=f'Committed reserved stars for "{movie.title}"',
        created_at=datetime.utcnow(),
      )
    )
    reservation.status = "fulfilled"
    reservation.release_delivery_state = "committed"
    reservation.updated_at = datetime.utcnow()
    committed_count += 1

  movie.reserve_enabled = False
  movie.buy_now_enabled = True
  if movie.release_decision == "pending":
    movie.release_decision = "confirmed"
  linked_title.reserve_enabled = False
  linked_title.buy_now_enabled = True

  session.commit()
  session.refresh(movie)
  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  return _movie_to_dict_for_session(session, movie, approval_status), committed_count


def _refund_blocked_reservations_for_movie(session: Session, movie: MovieRecord) -> None:
  linked_title = _get_linked_title_by_movie_id(session, movie.id)
  if linked_title is None:
    return

  blocked_reservations = (
    session.query(ReservationRecord)
    .filter(
      ReservationRecord.title_id == linked_title.id,
      ReservationRecord.status == "blocked",
    )
    .all()
  )

  for reservation in blocked_reservations:
    wallet = session.query(WalletRecord).filter(WalletRecord.user_id == reservation.user_id).first()
    if wallet is None:
      wallet = WalletRecord(user_id=reservation.user_id, available_stars=0, blocked_stars=0, disks=0)
      session.add(wallet)
      session.flush()

    refund_stars = int(reservation.stars_required or 0)
    wallet.available_stars += refund_stars
    wallet.blocked_stars = max(0, int(wallet.blocked_stars or 0) - refund_stars)
    session.add(
      WalletTransactionRecord(
        user_id=reservation.user_id,
        transaction_type="reserve_refund",
        stars_delta=refund_stars,
        blocked_stars_delta=-refund_stars,
        disks_delta=0,
        reference_type="movie",
        reference_id=movie.id,
        note=f'Refunded blocked stars for archived title "{movie.title}"',
        created_at=datetime.utcnow(),
      )
    )
    reservation.status = "refunded"
    reservation.release_delivery_state = "cancelled"
    reservation.updated_at = datetime.utcnow()

  movie.reserve_enabled = False
  movie.buy_now_enabled = False
  movie.reserve_count = 0
  movie.revenue = "$0K"
  linked_title.reserve_enabled = False
  linked_title.buy_now_enabled = False
  linked_title.current_reserved_stars = 0


def get_platform_summary(session: Session) -> dict:
  ensure_seeded(session)
  movies = session.query(MovieRecord).filter(MovieRecord.archived.is_(False)).all()
  wish_count = sum(movie.wish_count for movie in movies)
  reserve_count = sum(movie.reserve_count for movie in movies)
  return {
    "tracked_titles": len(movies),
    "wish_demand": wish_count,
    "reserve_count": reserve_count,
    "reserved_revenue": f"${round(reserve_count * 0.025)}K",
  }


def list_publish_queue(session: Session) -> list[dict]:
  ensure_seeded(session)
  return [_queue_to_dict(item) for item in session.query(QueueItemRecord).order_by(QueueItemRecord.id.desc()).all()]


def add_publish_queue_item(session: Session, payload: dict) -> dict:
  ensure_seeded(session)
  item = QueueItemRecord(**_queue_record_payload(payload))
  session.add(item)
  session.commit()
  session.refresh(item)
  return _queue_to_dict(item)


def create_movie(session: Session, payload: dict) -> dict:
  ensure_seeded(session)
  cast_credits = _normalize_cast_credit_entries(payload.get("cast_credits", []))
  payload = _movie_record_payload(payload)
  payload.setdefault("archived", False)
  payload["pricing_snapshot"] = _current_star_price_snapshot(session)
  movie = MovieRecord(**payload)
  session.add(movie)
  session.flush()
  change_request, pending_snapshot = _prepare_movie_change_request(
    session,
    movie,
    status="pending_super_admin_approval",
    is_new_title=True,
    capture_assets=True,
  )
  pending_snapshot["cast_credits"] = cast_credits
  _save_pending_movie_snapshot(change_request, pending_snapshot)
  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  _set_linked_title_cast_credits(session, movie.id, cast_credits)
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def update_movie_interest(
  session: Session,
  movie_id: str,
  kind: str,
  user_id: str | None = None,
  wish_mode: str | None = None,
  quality_code: str | None = None,
) -> tuple[dict, bool] | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None or movie.archived:
    return None
  if kind == "wish":
    if not user_id or wish_mode not in {"online", "theatre"}:
      return None
    existing_wish = (
      session.query(MovieWishRecord)
      .filter(MovieWishRecord.movie_id == movie_id, MovieWishRecord.user_id == user_id)
      .first()
    )
    if existing_wish is not None:
      approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
      return _movie_to_dict_for_session(session, movie, approval_status, existing_wish.wish_kind), False

    session.add(
      MovieWishRecord(
        movie_id=movie.id,
        user_id=user_id,
        wish_kind=wish_mode,
        created_at=datetime.utcnow(),
      )
    )
    movie.wish_count += 1
    if wish_mode == "online":
      movie.wish_online_count += 1
    else:
      movie.wish_theatre_count += 1
  else:
    if not user_id:
      raise ValueError("Sign in is required.")
    linked_title = _get_linked_title_by_movie_id(session, movie_id)
    if linked_title is None:
      linked_title = _ensure_linked_title(session, movie)
    resolved_wish_mode = _resolve_viewer_wishes(session, user_id, [movie.id]).get(movie.id)
    reserve_mode = wish_mode if kind == "reserve" and wish_mode in {"online", "theatre"} else resolved_wish_mode
    if kind == "reserve":
      reserve_mode = reserve_mode or "online"
    elif kind == "buy":
      reserve_mode = "online"
    normalized_quality_code = str(quality_code or "").strip().lower()
    if normalized_quality_code:
      reserve_mode = "online"
    selected_quality = None
    if reserve_mode == "online":
      pricing_options = _load_online_pricing_options(movie.online_pricing_options)
      selected_quality = next(
        (item for item in pricing_options if item["quality_code"] == normalized_quality_code),
        None,
      )
      if not selected_quality:
        raise ValueError("Please select one movie quality before reserving online.")

    existing_query = (
      session.query(ReservationRecord)
      .filter(
        ReservationRecord.user_id == user_id,
        ReservationRecord.title_id == linked_title.id,
        ReservationRecord.status.in_(["blocked", "fulfilled"]),
        ReservationRecord.reservation_kind == reserve_mode,
      )
    )
    if reserve_mode == "online":
      existing_query = existing_query.filter(ReservationRecord.quality_code == selected_quality["quality_code"])
    else:
      existing_query = existing_query.filter(ReservationRecord.quality_code.is_(None))
    existing_reservation = existing_query.first()
    if existing_reservation is not None:
      approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
      reservation_modes = _resolve_viewer_reservations(session, user_id, [movie.id]).get(movie.id, {})
      return _movie_to_dict_for_session(
        session,
        movie,
        approval_status,
        resolved_wish_mode,
        _combine_viewer_reservation_status(reservation_modes),
        reservation_modes.get("online"),
        reservation_modes.get("theatre"),
      ), False

    if kind == "reserve":
      if not movie.reserve_enabled:
        raise ValueError("Reserve Now is not active for this title yet.")
    elif kind == "buy":
      if not movie.buy_now_enabled:
        raise ValueError("Buy Now is not active for this title yet.")
    else:
      raise ValueError("Unsupported title action.")

    wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user_id).first()
    if wallet is None:
      wallet = WalletRecord(user_id=user_id, available_stars=0, blocked_stars=0, disks=0)
      session.add(wallet)
      session.flush()

    reserve_stars = movie.stars_required_theatre if reserve_mode == "theatre" else (movie.reserve_star_price or movie.stars_required)
    if reserve_mode == "online" and selected_quality:
      reserve_stars = int(selected_quality["stars_required"])

    if kind == "reserve" and reserve_mode == "online" and selected_quality:
      active_online_reservations = (
        session.query(ReservationRecord)
        .filter(
          ReservationRecord.user_id == user_id,
          ReservationRecord.title_id == linked_title.id,
          ReservationRecord.status.in_(["blocked", "fulfilled"]),
          ReservationRecord.reservation_kind == "online",
          ReservationRecord.quality_code.is_not(None),
        )
        .order_by(ReservationRecord.created_at.desc(), ReservationRecord.id.desc())
        .all()
      )
      current_online_reservation = next(
        (
          reservation
          for reservation in active_online_reservations
          if str(reservation.quality_code or "").strip().lower() != selected_quality["quality_code"]
        ),
        None,
      )
      if current_online_reservation is not None:
        if current_online_reservation.status != "blocked":
          raise ValueError("This reservation cannot be changed after the title has been committed.")

        old_quality_code = str(current_online_reservation.quality_code or "").strip().lower()
        old_enrollments = (
          session.query(ContentDeliveryEnrollmentRecord)
          .filter(
            ContentDeliveryEnrollmentRecord.user_id == user_id,
            ContentDeliveryEnrollmentRecord.movie_id == movie.id,
            ContentDeliveryEnrollmentRecord.quality_code != selected_quality["quality_code"],
          )
          .all()
        )
        blocked_enrollment = next(
          (
            enrollment
            for enrollment in old_enrollments
            if enrollment.status not in {"accepted", "queued"}
          ),
          None,
        )
        if blocked_enrollment is not None:
          raise ValueError("Title quality cannot be changed after download has started.")

        old_stars = int(current_online_reservation.stars_required or 0)
        star_difference = reserve_stars - old_stars
        if star_difference > 0 and wallet.available_stars < star_difference:
          raise ValueError("Not enough available stars to upgrade this title quality.")

        if star_difference:
          wallet.available_stars -= star_difference
          wallet.blocked_stars = max(0, int(wallet.blocked_stars or 0) + star_difference)
          session.add(
            WalletTransactionRecord(
              user_id=user_id,
              transaction_type="reserve_quality_change",
              stars_delta=-star_difference,
              blocked_stars_delta=star_difference,
              disks_delta=0,
              reference_type="movie",
              reference_id=movie.id,
              note=f'Changed reserved quality for "{movie.title}" from {old_quality_code} to {selected_quality["quality_code"]}',
              created_at=datetime.utcnow(),
            )
          )

        now = datetime.utcnow()
        current_online_reservation.quality_code = selected_quality["quality_code"]
        current_online_reservation.stars_required = reserve_stars
        current_online_reservation.updated_at = now
        for extra_reservation in active_online_reservations:
          if extra_reservation.id != current_online_reservation.id:
            extra_reservation.status = "changed"
            extra_reservation.release_delivery_state = "cancelled"
            extra_reservation.updated_at = now

        carried_settings = {
          "wifi_only": old_enrollments[0].wifi_only,
          "charging_only": old_enrollments[0].charging_only,
          "auto_download": old_enrollments[0].auto_download,
          "device_label": old_enrollments[0].device_label,
        } if old_enrollments else None
        for old_enrollment in old_enrollments:
          session.delete(old_enrollment)

        new_enrollment = (
          session.query(ContentDeliveryEnrollmentRecord)
          .filter(
            ContentDeliveryEnrollmentRecord.user_id == user_id,
            ContentDeliveryEnrollmentRecord.movie_id == movie.id,
            ContentDeliveryEnrollmentRecord.quality_code == selected_quality["quality_code"],
          )
          .first()
        )
        if new_enrollment is None:
          new_enrollment = ContentDeliveryEnrollmentRecord(
            user_id=user_id,
            movie_id=movie.id,
            quality_code=selected_quality["quality_code"],
            status="accepted",
            accepted_at=now,
          )
          session.add(new_enrollment)
        new_enrollment.wifi_only = carried_settings["wifi_only"] if carried_settings else new_enrollment.wifi_only
        new_enrollment.charging_only = carried_settings["charging_only"] if carried_settings else new_enrollment.charging_only
        new_enrollment.auto_download = carried_settings["auto_download"] if carried_settings else new_enrollment.auto_download
        new_enrollment.device_label = carried_settings["device_label"] if carried_settings else new_enrollment.device_label
        new_enrollment.status = "accepted"
        new_enrollment.slot_token = None
        new_enrollment.slot_expires_at = None
        new_enrollment.updated_at = now

        session.commit()
        session.refresh(movie)
        approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
        reservation_modes = _resolve_viewer_reservations(session, user_id, [movie.id]).get(movie.id, {})
        return _movie_to_dict_for_session(
          session,
          movie,
          approval_status,
          resolved_wish_mode,
          _combine_viewer_reservation_status(reservation_modes),
          reservation_modes.get("online"),
          reservation_modes.get("theatre"),
        ), True

    if wallet.available_stars < reserve_stars:
      raise ValueError(f'Not enough available stars to {"buy" if kind == "buy" else "reserve"} this title.')

    wallet.available_stars -= reserve_stars
    if kind == "reserve":
      wallet.blocked_stars += reserve_stars
      session.add(
        WalletTransactionRecord(
          user_id=user_id,
          transaction_type="reserve_block",
          stars_delta=-reserve_stars,
          blocked_stars_delta=reserve_stars,
          disks_delta=0,
          reference_type="movie",
          reference_id=movie.id,
          note=f'Reserved "{movie.title}" ({reserve_mode.title()})',
          created_at=datetime.utcnow(),
        )
      )
      reservation_status = "blocked"
      delivery_state = "pending"
    else:
      session.add(
        WalletTransactionRecord(
          user_id=user_id,
          transaction_type="buy_now_purchase",
          stars_delta=-reserve_stars,
        blocked_stars_delta=0,
        disks_delta=0,
        reference_type="movie",
        reference_id=movie.id,
        note=f'Purchased "{movie.title}"',
        created_at=datetime.utcnow(),
      )
      )
      reservation_status = "fulfilled"
      delivery_state = "committed"

    now = datetime.utcnow()
    session.add(
      ReservationRecord(
        user_id=user_id,
        title_id=linked_title.id,
        reservation_kind=reserve_mode,
        quality_code=selected_quality["quality_code"] if reserve_mode == "online" and selected_quality else None,
        stars_required=reserve_stars,
        status=reservation_status,
        lock_cutoff_days=linked_title.cancellation_lock_days,
        release_delivery_state=delivery_state,
        created_at=now,
        updated_at=now,
      )
    )
    if reserve_mode == "online" and selected_quality:
      existing_enrollment = (
        session.query(ContentDeliveryEnrollmentRecord)
        .filter(
          ContentDeliveryEnrollmentRecord.user_id == user_id,
          ContentDeliveryEnrollmentRecord.movie_id == movie.id,
          ContentDeliveryEnrollmentRecord.quality_code == selected_quality["quality_code"],
        )
        .first()
      )
      if existing_enrollment is None:
        session.add(
          ContentDeliveryEnrollmentRecord(
            user_id=user_id,
            movie_id=movie.id,
            quality_code=selected_quality["quality_code"],
            status="accepted",
            accepted_at=now,
            updated_at=now,
          )
        )
    movie.reserve_count += 1
    movie.revenue = f"${round(movie.reserve_count * 0.025)}K"
    linked_title.current_reserved_stars = movie.reserve_count
  session.commit()
  session.refresh(movie)
  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  viewer_wish_kind = wish_mode if kind == "wish" else _resolve_viewer_wishes(session, user_id, [movie.id]).get(movie.id)
  reservation_modes = {} if kind == "wish" else _resolve_viewer_reservations(session, user_id, [movie.id]).get(movie.id, {})
  return _movie_to_dict_for_session(
    session,
    movie,
    approval_status,
    viewer_wish_kind,
    _combine_viewer_reservation_status(reservation_modes),
    reservation_modes.get("online"),
    reservation_modes.get("theatre"),
  ), True


def get_admin_summary(session: Session) -> dict:
  ensure_seeded(session)
  state = session.get(AdminStateRecord, 1)
  queue = session.query(QueueItemRecord).all()
  active_movies = session.query(MovieRecord).filter(MovieRecord.archived.is_(False)).all()
  summary = _admin_state_to_dict(state) if state is not None else {
    "featured_stage": "upcoming",
    "reward_campaign_boosts": 0,
    "star_price_settings": _default_star_price_settings(),
    "star_price_inr": 50,
    "star_price_usd": 0.0,
    "star_price_eur": 0.0,
    "star_price_effective_from": None,
  }
  return {
    **summary,
    "tracked_titles": len(active_movies),
    "queue_total": len(queue),
    "queue_ready": len([item for item in queue if item.status == "Ready For Review"]),
    "queue_published": len([item for item in queue if item.status == "Published"]),
  }


def set_featured_stage(session: Session, stage: str) -> dict:
  ensure_seeded(session)
  state = session.get(AdminStateRecord, 1)
  state.featured_stage = stage
  session.commit()
  return get_admin_summary(session)


def boost_reward_campaign(session: Session) -> dict:
  ensure_seeded(session)
  state = session.get(AdminStateRecord, 1)
  state.reward_campaign_boosts += 1
  session.commit()
  return get_admin_summary(session)


def get_star_pricing_settings(session: Session) -> dict:
  ensure_seeded(session)
  state = session.get(AdminStateRecord, 1)
  if state is None:
    return _default_star_price_settings()
  return _star_price_settings_from_state(state)


def update_star_pricing_settings(session: Session, payload: dict) -> dict:
  ensure_seeded(session)
  state = session.get(AdminStateRecord, 1)
  if state is None:
    state = AdminStateRecord(id=1, featured_stage="upcoming", reward_campaign_boosts=0)
    session.add(state)
    session.flush()
  state.star_price_settings = json.dumps(_normalize_star_price_settings(payload))
  session.commit()
  return get_star_pricing_settings(session)


def update_queue_item_status(session: Session, queue_id: str, status: str) -> dict | None:
  ensure_seeded(session)
  item = session.get(QueueItemRecord, queue_id)
  if item is None:
    return None
  item.status = status
  session.commit()
  session.refresh(item)
  return _queue_to_dict(item)


def update_movie_stage(session: Session, movie_id: str, stage: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  change_request, pending_snapshot = _prepare_movie_change_request(session, movie, status="pending_super_admin_approval")
  pending_snapshot["stage"] = stage
  pending_snapshot["stage_label"] = "Upcoming" if stage == "upcoming" else "New Release" if stage == "released" else "Old Movies"
  _save_pending_movie_snapshot(change_request, pending_snapshot)
  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def update_movie_details(session: Session, movie_id: str, payload: dict) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  change_request, pending_snapshot = _prepare_movie_change_request(session, movie, status="pending_super_admin_approval")
  pending_snapshot["title_category"] = payload["title_category"]
  pending_snapshot["title"] = payload["title"]
  pending_snapshot["title_caption"] = payload.get("title_caption") or None
  pending_snapshot["genre"] = payload["genre"]
  pending_snapshot["cast_credits"] = _normalize_cast_credit_entries(payload.get("cast_credits", []))
  pending_snapshot["description"] = payload["story_line"]
  pending_snapshot["stars_required"] = payload["stars_required"]
  pending_snapshot["stars_required_theatre"] = payload["stars_required_theatre"]
  pending_snapshot["expected_stars"] = payload["expected_stars"]
  pending_snapshot["expected_revenue"] = f'{payload["expected_stars"]} stars'
  if payload.get("release_date"):
    pending_snapshot["release_date"] = payload["release_date"]
  _save_pending_movie_snapshot(change_request, pending_snapshot)
  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  _set_linked_title_cast_credits(session, movie.id, pending_snapshot["cast_credits"])
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def update_movie_pricing_config(session: Session, movie_id: str, payload: dict) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None

  options = _normalize_online_pricing_options(payload.get("online_pricing_options", []))
  default_online_stars = _derive_default_online_stars(options)
  theatre_stars = int(payload.get("stars_required_theatre") or 3)
  target_stars = int(payload.get("expected_stars") or 0)

  movie.online_pricing_options = _dump_online_pricing_options(options)
  movie.stars_required = default_online_stars
  movie.reserve_star_price = default_online_stars
  movie.stars_required_theatre = theatre_stars
  movie.expected_stars = target_stars
  movie.expected_revenue = f"{target_stars} stars"

  change_request, pending_snapshot = _prepare_movie_change_request(session, movie, status="pending_super_admin_approval")
  pending_snapshot["online_pricing_options"] = options
  pending_snapshot["stars_required"] = default_online_stars
  pending_snapshot["stars_required_theatre"] = theatre_stars
  pending_snapshot["expected_stars"] = target_stars
  pending_snapshot["expected_revenue"] = f"{target_stars} stars"
  _save_pending_movie_snapshot(change_request, pending_snapshot)

  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def release_movie_main_content(session: Session, movie_id: str, release_date_time: str, release_passcode: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  movie.password_publish_at = release_date_time
  movie.release_passcode = release_passcode.strip()
  movie.reservation_close_at = _derive_reservation_close_at(release_date_time)
  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  approval_status = _set_movie_approval_status(session, movie, approval_status)
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def publish_movie(session: Session, movie_id: str, release_date: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  current_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  if current_status not in {"approved", "published"}:
    raise ValueError("Title must be approved by Super Admin before publishing.")
  movie.stage = "released"
  movie.stage_label = "New Release"
  movie.release_date = release_date
  movie.countdown = f"Released on {release_date}"
  existing_request = _get_movie_change_request(session, movie.id)
  if existing_request is not None:
    session.delete(existing_request)
  approval_status = _set_movie_approval_status(session, movie, "published")
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def update_movie_poster_assets(session: Session, movie_id: str, poster_path: str | None, poster_count_label: str | None) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  change_request, pending_snapshot = _prepare_movie_change_request(session, movie, status="pending_super_admin_approval", capture_assets=True)
  if poster_path:
    pending_snapshot["poster"] = poster_path
  if poster_count_label:
    pending_snapshot["posters"] = poster_count_label
  _save_pending_movie_snapshot(change_request, pending_snapshot)
  _save_pending_asset_snapshot(change_request, _capture_movie_asset_snapshot(movie.id))
  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def prime_movie_asset_change(session: Session, movie_id: str) -> None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return
  _prepare_movie_change_request(session, movie, status="pending_super_admin_approval", capture_assets=True)
  session.flush()


def register_movie_asset_change(session: Session, movie_id: str, kind: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  change_request, pending_snapshot = _prepare_movie_change_request(session, movie, status="pending_super_admin_approval", capture_assets=True)
  if kind == "music":
    item_count = len(_capture_movie_asset_snapshot(movie.id).get("music", []))
    pending_snapshot["music"] = f"{item_count} music file{'s' if item_count != 1 else ''} uploaded" if item_count else "Music upload pending"
    _save_pending_movie_snapshot(change_request, pending_snapshot)
  _save_pending_asset_snapshot(change_request, _capture_movie_asset_snapshot(movie.id))
  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def update_movie_content_delivery_start(session: Session, movie_id: str, delivery_start_at: str | None) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  movie.delivery_start_at = delivery_start_at
  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  approval_status = _set_movie_approval_status(session, movie, approval_status)
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def clear_movie_content_release_state(session: Session, movie_id: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None

  movie.delivery_start_at = None
  movie.password_publish_at = None
  movie.release_passcode = None
  movie.reservation_close_at = None
  movie.release_date = "TBA"
  movie.buy_now_enabled = False
  movie.release_decision = "pending"
  movie.stage = "upcoming"
  movie.stage_label = "Upcoming"
  movie.countdown = "Release date to be confirmed"

  approval_status = _resolve_movie_approval_statuses(session, [movie.id]).get(movie.id, "published")
  approval_status = _set_movie_approval_status(session, movie, approval_status)
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def archive_movie(session: Session, movie_id: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  _refund_blocked_reservations_for_movie(session, movie)
  movie.archived = True
  approval_status = _set_movie_approval_status(session, movie, "archived")
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def restore_movie(session: Session, movie_id: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  movie.archived = False
  change_request, pending_snapshot = _prepare_movie_change_request(session, movie, status="pending_super_admin_approval")
  pending_snapshot["archived"] = False
  _save_pending_movie_snapshot(change_request, pending_snapshot)
  approval_status = _set_movie_approval_status(session, movie, "pending_super_admin_approval")
  session.commit()
  session.refresh(movie)
  return _movie_snapshot_to_dict(pending_snapshot, approval_status)


def update_movie_approval_status(session: Session, movie_id: str, status: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None
  change_request = _get_movie_change_request(session, movie.id)
  if change_request is not None:
    change_request.status = status
    change_request.updated_at = datetime.utcnow()
  approval_status = _set_movie_approval_status(session, movie, status)
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def review_movie_approval(session: Session, movie_id: str, action: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None

  change_request = _get_movie_change_request(session, movie_id)
  if action == "approve":
    if change_request is not None:
      pending_snapshot = _json_load(change_request.pending_snapshot, _capture_movie_snapshot_with_extras(session, movie))
      _apply_movie_snapshot(movie, pending_snapshot)
      _set_linked_title_cast_credits(session, movie.id, pending_snapshot.get("cast_credits", []))
      session.delete(change_request)
    approval_status = _set_movie_approval_status(session, movie, "approved")
    session.commit()
    session.refresh(movie)
    return _movie_to_dict_for_session(session, movie, approval_status)

  if change_request is not None:
    change_request.status = "changes_requested"
    change_request.updated_at = datetime.utcnow()
  approval_status = _set_movie_approval_status(session, movie, "changes_requested")
  session.commit()
  session.refresh(movie)
  return _movie_to_dict_for_session(session, movie, approval_status)


def delete_movie_permanently(session: Session, movie_id: str) -> dict | None:
  ensure_seeded(session)
  movie = session.get(MovieRecord, movie_id)
  if movie is None:
    return None

  deleted_movie = _movie_to_dict_for_session(session, movie)
  session.query(MovieChangeRequestRecord).filter(MovieChangeRequestRecord.movie_id == movie_id).delete()
  session.query(MovieWishRecord).filter(MovieWishRecord.movie_id == movie_id).delete()
  session.query(ContentDeliveryEnrollmentRecord).filter(ContentDeliveryEnrollmentRecord.movie_id == movie_id).delete()
  linked_title = session.query(TitleRecord).filter(TitleRecord.legacy_movie_id == movie_id).first()
  if linked_title is not None:
    session.query(TitlePosterRecord).filter(TitlePosterRecord.title_id == linked_title.id).delete()
    session.query(TitleMusicRecord).filter(TitleMusicRecord.title_id == linked_title.id).delete()
    session.query(TitleTrailerRecord).filter(TitleTrailerRecord.title_id == linked_title.id).delete()
    session.query(TitleSubtitleTrackRecord).filter(TitleSubtitleTrackRecord.title_id == linked_title.id).delete()
    session.query(TitleAudioTrackRecord).filter(TitleAudioTrackRecord.title_id == linked_title.id).delete()
    session.query(TitleContentFileRecord).filter(TitleContentFileRecord.title_id == linked_title.id).delete()
    session.query(TitleGenreRecord).filter(TitleGenreRecord.title_id == linked_title.id).delete()
    session.query(TitleLanguageRecord).filter(TitleLanguageRecord.title_id == linked_title.id).delete()
    session.query(ReservationRecord).filter(ReservationRecord.title_id == linked_title.id).delete()
    session.query(PublishSubmissionRecord).filter(PublishSubmissionRecord.title_id == linked_title.id).delete()
    session.delete(linked_title)

  session.delete(movie)
  session.commit()
  return deleted_movie


def list_users(session: Session) -> list[dict]:
  ensure_seeded(session)
  users = session.query(UserRecord).order_by(UserRecord.name.asc()).all()
  wallets = {
    wallet.user_id: wallet
    for wallet in session.query(WalletRecord).filter(WalletRecord.user_id.in_([user.id for user in users])).all()
  }
  return [_user_to_dict(user, wallets.get(user.id)) for user in users]


def get_user_profile(session: Session, user_id: str) -> dict | None:
  ensure_seeded(session)
  user = session.get(UserRecord, user_id)
  if user is None:
    return None
  _sync_live_release_entitlements(session, session.query(MovieRecord).filter(MovieRecord.archived.is_(False)).all())
  wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first()
  profile = _user_to_dict(user, wallet)
  profile["notifications"] = _resolve_viewer_notifications(session, user.id, 10)
  reservations = (
    session.query(ReservationRecord, TitleRecord)
    .join(TitleRecord, TitleRecord.id == ReservationRecord.title_id)
    .filter(ReservationRecord.user_id == user.id, ReservationRecord.status.in_(["blocked", "fulfilled"]))
    .order_by(ReservationRecord.created_at.desc())
    .all()
  )
  profile["reservations"] = [
    {
      "movie_id": title.legacy_movie_id or title.slug,
      "title": title.title_name,
      "title_caption": title.caption,
      "stars_required": reservation.stars_required,
      "status": reservation.status,
      "reservation_mode": reservation.reservation_kind,
      "quality_code": reservation.quality_code,
      "release_date": title.release_date_text,
    }
    for reservation, title in reservations
  ]
  return profile


def update_user_access(session: Session, user_id: str, name: str, role: str, status: str, star_balance: int) -> dict | None:
  ensure_seeded(session)
  user = session.get(UserRecord, user_id)
  if user is None:
    return None
  wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first()
  if wallet is None:
    wallet = WalletRecord(user_id=user.id, available_stars=0, blocked_stars=0, disks=0)
    session.add(wallet)
    session.flush()
  user.name = name
  # keep legacy points in sync with the wallet until points is fully removed from the model
  user.role = role
  user.status = status
  wallet.available_stars = star_balance
  user.points = star_balance * 100
  session.commit()
  session.refresh(user)
  return _user_to_dict(user, wallet)


def authenticate_user(session: Session, email: str, password: str) -> dict | None:
  ensure_seeded(session)
  normalized_email = email.strip().lower()
  user = session.query(UserRecord).filter(UserRecord.email == normalized_email).first()
  if user is None:
    return None
  if user.password_hash != _password_hash(password):
    return None
  wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first()
  return _user_to_dict(user, wallet)


def create_user(session: Session, payload: dict) -> dict:
  ensure_seeded(session)
  normalized_email = payload["email"].strip().lower()
  existing = session.query(UserRecord).filter(UserRecord.email == normalized_email).first()
  if existing is not None:
    raise ValueError("A user with this email already exists.")

  user = UserRecord(
    id=f"acct-{secrets.token_hex(4)}",
    name=payload["name"],
    email=normalized_email,
    password_hash=_password_hash(payload["password"]),
    role=payload["role"],
    status=payload["status"],
    points=payload["star_balance"] * 100,
  )
  session.add(user)
  session.flush()

  session.add(
    WalletRecord(
      user_id=user.id,
      available_stars=payload["star_balance"],
      blocked_stars=0,
      disks=0,
    )
  )
  session.commit()
  session.refresh(user)
  wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first()
  return _user_to_dict(user, wallet)


def soft_delete_user(session: Session, user_id: str) -> dict | None:
  ensure_seeded(session)
  user = session.get(UserRecord, user_id)
  if user is None:
    return None
  user.status = "disabled"
  session.commit()
  session.refresh(user)
  wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first()
  return _user_to_dict(user, wallet)


def delete_user(session: Session, user_id: str) -> dict | None:
  ensure_seeded(session)
  user = session.get(UserRecord, user_id)
  if user is None:
    return None

  wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user.id).first()
  deleted_user = _user_to_dict(user, wallet)

  session.query(TitleRecord).filter(TitleRecord.creator_user_id == user.id).update(
    {TitleRecord.creator_user_id: None},
    synchronize_session=False,
  )
  session.query(PublishSubmissionRecord).filter(PublishSubmissionRecord.creator_user_id == user.id).update(
    {PublishSubmissionRecord.creator_user_id: None},
    synchronize_session=False,
  )

  session.query(CreatorProfileRecord).filter(CreatorProfileRecord.user_id == user.id).delete(synchronize_session=False)
  session.query(AdvertiserProfileRecord).filter(AdvertiserProfileRecord.user_id == user.id).delete(synchronize_session=False)
  session.query(ReservationRecord).filter(ReservationRecord.user_id == user.id).delete(synchronize_session=False)
  session.query(WalletTransactionRecord).filter(WalletTransactionRecord.user_id == user.id).delete(synchronize_session=False)
  session.query(WalletRecord).filter(WalletRecord.user_id == user.id).delete(synchronize_session=False)

  session.delete(user)
  session.commit()
  return deleted_user


def list_taxonomy_items(session: Session, kind: str) -> list[dict]:
  ensure_seeded(session)
  model = _get_taxonomy_model(kind)
  return [_taxonomy_to_dict(item) for item in session.query(model).order_by(model.sort_order.asc(), model.name.asc()).all()]


def create_taxonomy_item(session: Session, kind: str, payload: dict) -> dict:
  ensure_seeded(session)
  model = _get_taxonomy_model(kind)
  item = model(**deepcopy(payload))
  session.add(item)
  session.commit()
  session.refresh(item)
  return _taxonomy_to_dict(item)


def update_taxonomy_item(session: Session, kind: str, item_id: int, payload: dict) -> dict | None:
  ensure_seeded(session)
  model = _get_taxonomy_model(kind)
  item = session.get(model, item_id)
  if item is None:
    return None

  item.slug = payload["slug"]
  item.name = payload["name"]
  if hasattr(item, "description"):
    item.description = payload.get("description")
  item.sort_order = payload["sort_order"]
  item.is_active = payload["is_active"]
  session.commit()
  session.refresh(item)
  return _taxonomy_to_dict(item)


def delete_taxonomy_item(session: Session, kind: str, item_id: int) -> dict | None:
  ensure_seeded(session)
  model = _get_taxonomy_model(kind)
  item = session.get(model, item_id)
  if item is None:
    return None

  deleted_item = _taxonomy_to_dict(item)
  session.delete(item)
  session.commit()
  return deleted_item
