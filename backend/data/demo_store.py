from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib


APPROVAL_STATUS_LABELS = {
  "draft": "Draft",
  "pending_admin_review": "Pending Admin Review",
  "pending_super_admin_approval": "Pending Super Admin Approval",
  "approved": "Approved",
  "published": "Published",
  "changes_requested": "Changes Requested",
  "archived": "Archived",
}


MOVIES = []
MOVIE_CHANGE_REQUESTS: dict[str, dict] = {}
MOVIE_WISHES: list[dict] = []
MOVIE_RESERVATIONS: list[dict] = []
DEFAULT_STAR_PRICE_SETTINGS = {
  "price_inr": 50,
  "price_usd": 0.0,
  "price_eur": 0.0,
  "effective_from": None,
}
MOVIE_NOTIFICATIONS: list[dict] = []


def _approval_label(status: str) -> str:
  return APPROVAL_STATUS_LABELS.get(status, status.replace("_", " ").title())


def _normalize_online_pricing_options(entries) -> list[dict]:
  normalized: list[dict] = []
  if isinstance(entries, str):
    try:
      entries = json.loads(entries)
    except json.JSONDecodeError:
      entries = []
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


def _derive_default_online_stars(entries) -> int:
  normalized = _normalize_online_pricing_options(entries)
  if not normalized:
    return 1
  return min(int(item["stars_required"]) for item in normalized)


def _decorate_movie(movie: dict, viewer_wish_kind: str | None = None) -> dict:
  item = deepcopy(movie)
  approval_status = "archived" if item.get("archived") else item.get("approval_status", "published")
  item["approval_status"] = approval_status
  item["approval_status_label"] = _approval_label(approval_status)
  item["requires_super_admin_approval"] = approval_status in {"pending_admin_review", "pending_super_admin_approval", "changes_requested"}
  item.setdefault("wish_online_count", item.get("wish_count", 0))
  item.setdefault("wish_theatre_count", 0)
  item.setdefault("cast_credits", [])
  item.setdefault("online_pricing_options", [])
  item["viewer_wish_kind"] = viewer_wish_kind
  return item


def _movie_payload(movie: dict) -> dict:
  return deepcopy({key: value for key, value in movie.items() if key not in {"approval_status", "approval_status_label", "requires_super_admin_approval"}})


def _prepare_movie_change_request(movie: dict, is_new_title: bool = False) -> dict:
  change_request = MOVIE_CHANGE_REQUESTS.get(movie["id"])
  if change_request is None:
    change_request = {
      "baseline": {} if is_new_title else _movie_payload(movie),
      "pending": _movie_payload(movie),
      "baseline_assets": {"posters": [], "trailer": [], "gallery": [], "music": [], "content": []},
      "pending_assets": {"posters": [], "trailer": [], "gallery": [], "music": [], "content": []},
    }
    MOVIE_CHANGE_REQUESTS[movie["id"]] = change_request
  return change_request


def _get_viewer_wish_kind(movie_id: str, user_id: str | None) -> str | None:
  if not user_id:
    return None
  match = next((item for item in MOVIE_WISHES if item["movie_id"] == movie_id and item["user_id"] == user_id), None)
  return match["wish_kind"] if match else None


def _get_viewer_reservation_status(movie_id: str, user_id: str | None, reservation_mode: str | None = None) -> str | None:
  if not user_id:
    return None
  match = next(
    (
      item
      for item in MOVIE_RESERVATIONS
      if item["movie_id"] == movie_id
      and item["user_id"] == user_id
      and item["status"] in {"blocked", "fulfilled"}
      and (reservation_mode is None or item.get("reservation_mode", "online") == reservation_mode)
    ),
    None,
  )
  return match["status"] if match else None


def _get_viewer_notifications(user_id: str | None, limit: int = 10) -> list[dict]:
  if not user_id:
    return []
  rows = [item for item in MOVIE_NOTIFICATIONS if item["user_id"] == user_id]
  rows.sort(key=lambda item: (item["created_at"], item["id"]), reverse=True)
  return [
    {
      "id": item["id"],
      "movie_id": item["movie_id"],
      "notification_type": item["notification_type"],
      "title": item["title"],
      "message": item["message"],
      "is_read": item.get("is_read", False),
      "read_at": item["read_at"],
      "created_at": item["created_at"],
    }
    for item in rows[:limit]
  ]


def _notify_wishers_for_reserve_start(movie: dict) -> int:
  user_ids = sorted({item["user_id"] for item in MOVIE_WISHES if item["movie_id"] == movie["id"]})
  count = 0
  for user_id in user_ids:
    MOVIE_NOTIFICATIONS.append(
      {
        "id": len(MOVIE_NOTIFICATIONS) + 1,
        "user_id": user_id,
        "movie_id": movie["id"],
        "notification_type": "reserve_start",
        "title": movie["title"],
        "message": f'Reserve Now is now active for "{movie["title"]}". Open the title to reserve your stars.',
        "is_read": False,
        "read_at": None,
        "created_at": datetime.utcnow().isoformat(timespec="minutes"),
      }
    )
    count += 1
  return count


def _pending_or_live(movie: dict, prefer_pending: bool = False, viewer_user_id: str | None = None) -> dict:
  if prefer_pending and movie["id"] in MOVIE_CHANGE_REQUESTS:
    pending = deepcopy(MOVIE_CHANGE_REQUESTS[movie["id"]].get("pending") or {})
    if pending:
      pending["approval_status"] = movie.get("approval_status", "pending_super_admin_approval")
      item = _decorate_movie(pending, _get_viewer_wish_kind(movie["id"], viewer_user_id))
      item["viewer_reservation_online_status"] = _get_viewer_reservation_status(movie["id"], viewer_user_id, "online")
      item["viewer_reservation_theatre_status"] = _get_viewer_reservation_status(movie["id"], viewer_user_id, "theatre")
      item["viewer_reservation_status"] = item["viewer_reservation_online_status"] or item["viewer_reservation_theatre_status"]
      return item
  item = _decorate_movie(movie, _get_viewer_wish_kind(movie["id"], viewer_user_id))
  item["viewer_reservation_online_status"] = _get_viewer_reservation_status(movie["id"], viewer_user_id, "online")
  item["viewer_reservation_theatre_status"] = _get_viewer_reservation_status(movie["id"], viewer_user_id, "theatre")
  item["viewer_reservation_status"] = item["viewer_reservation_online_status"] or item["viewer_reservation_theatre_status"]
  return item


def _update_movie_approval_status(movie: dict, status: str) -> None:
  movie["approval_status"] = "archived" if movie.get("archived") else status


def _is_viewer_visible(movie: dict) -> bool:
  return movie.get("approval_status") in {"approved", "published"}

PUBLISH_QUEUE = []

ADMIN_STATE = {
  "featured_stage": "upcoming",
  "reward_campaign_boosts": 0,
  "star_price_settings": deepcopy(DEFAULT_STAR_PRICE_SETTINGS),
}

USERS = [
  {
    "id": "user-0",
    "name": "Super Admin",
    "email": "kamarthi.anil@gmail.com",
    "password_hash": hashlib.sha256("asd".encode("utf-8")).hexdigest(),
    "role": "super_admin",
    "status": "active",
    "points": 0,
  },
]


def list_movies(
  stage: str | None = None,
  include_archived: bool = False,
  prefer_pending: bool = False,
  viewer_user_id: str | None = None,
) -> list[dict]:
  movies = [_pending_or_live(movie, prefer_pending=prefer_pending, viewer_user_id=viewer_user_id) for movie in MOVIES]
  if not include_archived:
    movies = [movie for movie in movies if not movie.get("archived", False)]
    movies = [movie for movie in movies if _is_viewer_visible(movie)]
  if stage:
    movies = [movie for movie in movies if movie["stage"] == stage]
  return movies


def get_platform_summary() -> dict:
  active_movies = [movie for movie in MOVIES if not movie.get("archived", False)]
  wish_count = sum(movie["wish_count"] for movie in active_movies)
  reserve_count = sum(movie["reserve_count"] for movie in active_movies)
  return {
    "tracked_titles": len(active_movies),
    "wish_demand": wish_count,
    "reserve_count": reserve_count,
    "reserved_revenue": f"${round(reserve_count * 0.025)}K",
  }


def list_publish_queue() -> list[dict]:
  return deepcopy(PUBLISH_QUEUE)


def add_publish_queue_item(item: dict) -> dict:
  PUBLISH_QUEUE.insert(0, deepcopy(item))
  return deepcopy(item)


def create_movie(movie: dict) -> dict:
  movie.setdefault("archived", False)
  movie.setdefault("approval_status", "pending_super_admin_approval")
  movie["online_pricing_options"] = _normalize_online_pricing_options(movie.get("online_pricing_options", []))
  movie["stars_required"] = _derive_default_online_stars(movie["online_pricing_options"])
  movie.setdefault("stars_required_theatre", 3)
  movie.setdefault("pricing_snapshot", deepcopy(ADMIN_STATE.get("star_price_settings", DEFAULT_STAR_PRICE_SETTINGS)))
  MOVIES.insert(0, deepcopy(movie))
  _prepare_movie_change_request(movie, is_new_title=True)
  return _pending_or_live(movie, prefer_pending=True)


def update_movie_interest(
  movie_id: str,
  kind: str,
  user_id: str | None = None,
  wish_mode: str | None = None,
  quality_code: str | None = None,
) -> tuple[dict, bool] | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    if movie.get("archived", False):
      return None
    if kind == "wish":
      if not user_id or wish_mode not in {"online", "theatre"}:
        return None
      existing_wish = next((item for item in MOVIE_WISHES if item["movie_id"] == movie_id and item["user_id"] == user_id), None)
      if existing_wish is not None:
        return _decorate_movie(movie, existing_wish["wish_kind"]), False
      MOVIE_WISHES.append({"movie_id": movie_id, "user_id": user_id, "wish_kind": wish_mode})
      movie["wish_count"] += 1
      movie["wish_online_count"] = int(movie.get("wish_online_count", 0)) + (1 if wish_mode == "online" else 0)
      movie["wish_theatre_count"] = int(movie.get("wish_theatre_count", 0)) + (1 if wish_mode == "theatre" else 0)
    else:
      if not user_id:
        raise ValueError("Sign in is required.")
      if kind == "reserve":
        if not movie.get("reserve_enabled", False):
          raise ValueError("Reserve Now is not active for this title yet.")
      elif kind == "buy":
        if not movie.get("buy_now_enabled", False):
          raise ValueError("Buy Now is not active for this title yet.")
      else:
        raise ValueError("Unsupported title action.")
      reserve_mode = wish_mode if kind == "reserve" and wish_mode in {"online", "theatre"} else _get_viewer_wish_kind(movie_id, user_id) or "online"
      normalized_quality_code = str(quality_code or "").strip().lower()
      if normalized_quality_code:
        reserve_mode = "online"
      selected_quality = None
      if reserve_mode == "online":
        pricing_options = _normalize_online_pricing_options(movie.get("online_pricing_options", []))
        selected_quality = next(
          (item for item in pricing_options if item["quality_code"] == normalized_quality_code),
          None,
        )
        if not selected_quality:
          raise ValueError("Please select one movie quality before reserving online.")
      existing_reservation = next((
        item
        for item in MOVIE_RESERVATIONS
        if item["movie_id"] == movie_id
        and item["user_id"] == user_id
        and item["status"] in {"blocked", "fulfilled"}
        and item.get("reservation_mode", "online") == reserve_mode
        and (item.get("quality_code") == selected_quality["quality_code"] if reserve_mode == "online" and selected_quality else not item.get("quality_code"))
      ), None)
      if existing_reservation is not None:
        item = _decorate_movie(movie, _get_viewer_wish_kind(movie_id, user_id))
        item["viewer_reservation_online_status"] = _get_viewer_reservation_status(movie_id, user_id, "online")
        item["viewer_reservation_theatre_status"] = _get_viewer_reservation_status(movie_id, user_id, "theatre")
        item["viewer_reservation_status"] = item["viewer_reservation_online_status"] or item["viewer_reservation_theatre_status"]
        return item, False
      user = next((entry for entry in USERS if entry["id"] == user_id), None)
      if user is None:
        raise ValueError("Sign in is required.")
      reserve_stars = int(movie.get("stars_required_theatre", 3) if reserve_mode == "theatre" else movie.get("reserve_star_price", movie.get("stars_required", 0)) or movie.get("stars_required", 0))
      if reserve_mode == "online" and selected_quality:
        reserve_stars = int(selected_quality["stars_required"])
      available_stars = int(user.get("available_stars", max(user.get("points", 0) // 100, 0)))
      blocked_stars = int(user.get("blocked_stars", 0))
      if kind == "reserve" and reserve_mode == "online" and selected_quality:
        current_online_reservation = next((
          item
          for item in MOVIE_RESERVATIONS
          if item["movie_id"] == movie_id
          and item["user_id"] == user_id
          and item["status"] in {"blocked", "fulfilled"}
          and item.get("reservation_mode", "online") == "online"
          and item.get("quality_code") != selected_quality["quality_code"]
        ), None)
        if current_online_reservation is not None:
          if current_online_reservation["status"] != "blocked":
            raise ValueError("This reservation cannot be changed after the title has been committed.")
          old_stars = int(current_online_reservation.get("stars_required", 0))
          star_difference = reserve_stars - old_stars
          if star_difference > 0 and available_stars < star_difference:
            raise ValueError("Not enough available stars to upgrade this title quality.")
          available_stars -= star_difference
          blocked_stars = max(0, blocked_stars + star_difference)
          user["available_stars"] = available_stars
          user["blocked_stars"] = blocked_stars
          user["points"] = available_stars * 100
          current_online_reservation["quality_code"] = selected_quality["quality_code"]
          current_online_reservation["stars_required"] = reserve_stars
          item = _decorate_movie(movie, _get_viewer_wish_kind(movie_id, user_id))
          item["viewer_reservation_online_status"] = _get_viewer_reservation_status(movie_id, user_id, "online")
          item["viewer_reservation_theatre_status"] = _get_viewer_reservation_status(movie_id, user_id, "theatre")
          item["viewer_reservation_status"] = item["viewer_reservation_online_status"] or item["viewer_reservation_theatre_status"]
          return item, True
      if available_stars < reserve_stars:
        raise ValueError(f'Not enough available stars to {"buy" if kind == "buy" else "reserve"} this title.')
      user["available_stars"] = available_stars - reserve_stars
      user["blocked_stars"] = blocked_stars + reserve_stars if kind == "reserve" else blocked_stars
      user["points"] = user["available_stars"] * 100
      MOVIE_RESERVATIONS.append({
        "user_id": user_id,
        "movie_id": movie_id,
        "title": movie["title"],
        "title_caption": movie.get("title_caption"),
        "reservation_mode": reserve_mode,
        "quality_code": selected_quality["quality_code"] if reserve_mode == "online" and selected_quality else None,
        "stars_required": reserve_stars,
        "status": "fulfilled" if kind == "buy" else "blocked",
        "release_date": movie.get("release_date"),
      })
      movie["reserve_count"] += 1
      movie["revenue"] = f"${round(movie['reserve_count'] * 0.025)}K"
    item = _decorate_movie(movie, wish_mode if kind == "wish" else _get_viewer_wish_kind(movie_id, user_id))
    item["viewer_reservation_online_status"] = None if kind == "wish" else _get_viewer_reservation_status(movie_id, user_id, "online")
    item["viewer_reservation_theatre_status"] = None if kind == "wish" else _get_viewer_reservation_status(movie_id, user_id, "theatre")
    item["viewer_reservation_status"] = item["viewer_reservation_online_status"] or item["viewer_reservation_theatre_status"]
    return item, True
  return None


def get_admin_summary() -> dict:
  queue = list_publish_queue()
  active_movies = [movie for movie in MOVIES if not movie.get("archived", False)]
  pricing = deepcopy(ADMIN_STATE.get("star_price_settings", DEFAULT_STAR_PRICE_SETTINGS))
  return {
    "featured_stage": ADMIN_STATE["featured_stage"],
    "reward_campaign_boosts": ADMIN_STATE["reward_campaign_boosts"],
    "star_price_inr": pricing["price_inr"],
    "star_price_usd": pricing["price_usd"],
    "star_price_eur": pricing["price_eur"],
    "star_price_effective_from": pricing["effective_from"],
    "tracked_titles": len(active_movies),
    "queue_total": len(queue),
    "queue_ready": len([item for item in queue if item["status"] == "Ready For Review"]),
    "queue_published": len([item for item in queue if item["status"] == "Published"]),
  }


def get_star_pricing_settings() -> dict:
  return deepcopy(ADMIN_STATE.get("star_price_settings", DEFAULT_STAR_PRICE_SETTINGS))


def update_star_pricing_settings(payload: dict) -> dict:
  settings = deepcopy(DEFAULT_STAR_PRICE_SETTINGS)
  settings["price_inr"] = float(payload.get("price_inr", settings["price_inr"]) or settings["price_inr"])
  settings["price_usd"] = float(payload.get("price_usd", settings["price_usd"]) or settings["price_usd"])
  settings["price_eur"] = float(payload.get("price_eur", settings["price_eur"]) or settings["price_eur"])
  settings["effective_from"] = payload.get("effective_from") or None
  ADMIN_STATE["star_price_settings"] = settings
  return deepcopy(settings)


def set_featured_stage(stage: str) -> dict:
  ADMIN_STATE["featured_stage"] = stage
  return get_admin_summary()


def boost_reward_campaign() -> dict:
  ADMIN_STATE["reward_campaign_boosts"] += 1
  return get_admin_summary()


def update_queue_item_status(queue_id: str, status: str) -> dict | None:
  for item in PUBLISH_QUEUE:
    if item["id"] == queue_id:
      item["status"] = status
      return deepcopy(item)
  return None


def update_movie_stage(movie_id: str, stage: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = _prepare_movie_change_request(movie)
    request["pending"]["stage"] = stage
    request["pending"]["stage_label"] = "Upcoming" if stage == "upcoming" else "New Release" if stage == "released" else "Old Movies"
    if not movie.get("archived"):
      _update_movie_approval_status(movie, "pending_super_admin_approval")
    return _pending_or_live(movie, prefer_pending=True)
  return None


def start_movie_reserve(movie_id: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    if not movie.get("reserve_enabled", False) and not _normalize_online_pricing_options(movie.get("online_pricing_options", [])):
      raise ValueError("Please add at least one online movie quality with pricing before starting Reserve Now.")
    movie["reserve_enabled"] = not movie.get("reserve_enabled", False)
    if movie["reserve_enabled"]:
      movie["reserve_star_price"] = int(movie.get("stars_required", 0) or 0)
      _notify_wishers_for_reserve_start(movie)
    return _decorate_movie(movie)
  return None


def _refund_blocked_reservations_for_movie(movie: dict) -> None:
  refunded_count = 0
  for reservation in MOVIE_RESERVATIONS:
    if reservation.get("movie_id") != movie["id"] or reservation.get("status") != "blocked":
      continue
    user = next((entry for entry in USERS if entry["id"] == reservation["user_id"]), None)
    if user is not None:
      refund_stars = int(reservation.get("stars_required", 0) or 0)
      user["available_stars"] = int(user.get("available_stars", max(user.get("points", 0) // 100, 0))) + refund_stars
      user["blocked_stars"] = max(0, int(user.get("blocked_stars", 0)) - refund_stars)
      user["points"] = int(user["available_stars"]) * 100
    reservation["status"] = "refunded"
    refunded_count += 1

  movie["reserve_enabled"] = False
  movie["reserve_count"] = 0
  movie["revenue"] = "$0K"
  movie["refunded_reservations"] = refunded_count


def archive_movie(movie_id: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    _refund_blocked_reservations_for_movie(movie)
    movie["archived"] = True
    _update_movie_approval_status(movie, "archived")
    return _decorate_movie(movie)
  return None


def restore_movie(movie_id: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    movie["archived"] = False
    request = _prepare_movie_change_request(movie)
    request["pending"]["archived"] = False
    _update_movie_approval_status(movie, "pending_super_admin_approval")
    return _pending_or_live(movie, prefer_pending=True)
  return None


def delete_movie_permanently(movie_id: str) -> dict | None:
  for index, movie in enumerate(MOVIES):
    if movie["id"] != movie_id:
      continue
    deleted_movie = _decorate_movie(movie)
    MOVIE_CHANGE_REQUESTS.pop(movie_id, None)
    del MOVIES[index]
    return deleted_movie
  return None


def update_movie_details(movie_id: str, payload: dict) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = _prepare_movie_change_request(movie)
    request["pending"]["title_category"] = payload["title_category"]
    request["pending"]["title"] = payload["title"]
    request["pending"]["title_caption"] = payload.get("title_caption") or None
    request["pending"]["genre"] = payload["genre"]
    request["pending"]["cast_credits"] = deepcopy(payload.get("cast_credits") or [])
    request["pending"]["description"] = payload["story_line"]
    request["pending"]["stars_required"] = payload["stars_required"]
    request["pending"]["stars_required_theatre"] = payload["stars_required_theatre"]
    request["pending"]["expected_stars"] = payload["expected_stars"]
    request["pending"]["expected_revenue"] = f'{payload["expected_stars"]} stars'
    if payload.get("release_date"):
      request["pending"]["release_date"] = payload["release_date"]
    if not movie.get("archived"):
      _update_movie_approval_status(movie, "pending_super_admin_approval")
    return _pending_or_live(movie, prefer_pending=True)
  return None


def update_movie_pricing_config(movie_id: str, payload: dict) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = _prepare_movie_change_request(movie)
    options = _normalize_online_pricing_options(payload.get("online_pricing_options", []))
    default_online_stars = _derive_default_online_stars(options)
    request["pending"]["online_pricing_options"] = deepcopy(options)
    request["pending"]["stars_required"] = default_online_stars
    request["pending"]["stars_required_theatre"] = int(payload.get("stars_required_theatre") or 3)
    request["pending"]["expected_stars"] = int(payload.get("expected_stars") or 0)
    request["pending"]["expected_revenue"] = f'{request["pending"]["expected_stars"]} stars'
    movie["online_pricing_options"] = deepcopy(options)
    movie["stars_required"] = default_online_stars
    movie["reserve_star_price"] = default_online_stars
    movie["stars_required_theatre"] = request["pending"]["stars_required_theatre"]
    movie["expected_stars"] = request["pending"]["expected_stars"]
    movie["expected_revenue"] = request["pending"]["expected_revenue"]
    if not movie.get("archived"):
      _update_movie_approval_status(movie, "pending_super_admin_approval")
    return _pending_or_live(movie, prefer_pending=True)
  return None


def publish_movie(movie_id: str, release_date: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    if movie.get("approval_status") not in {"approved", "published"}:
      raise ValueError("Title must be approved by Super Admin before publishing.")
    movie["stage"] = "released"
    movie["stage_label"] = "New Release"
    movie["release_date"] = release_date
    movie["countdown"] = f"Released on {release_date}"
    _update_movie_approval_status(movie, "published")
    return _decorate_movie(movie)
  return None


def update_movie_poster_assets(movie_id: str, poster_path: str | None, poster_count_label: str | None) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = _prepare_movie_change_request(movie)
    if poster_path:
      request["pending"]["poster"] = poster_path
    if poster_count_label:
      request["pending"]["posters"] = poster_count_label
    if not movie.get("archived"):
      _update_movie_approval_status(movie, "pending_super_admin_approval")
    return _pending_or_live(movie, prefer_pending=True)


def update_movie_approval_status(movie_id: str, status: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = MOVIE_CHANGE_REQUESTS.get(movie_id)
    if request is not None:
      request["status"] = status
    _update_movie_approval_status(movie, status)
    return _decorate_movie(movie)
  return None


def review_movie_approval(movie_id: str, action: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    if action == "approve":
      request = MOVIE_CHANGE_REQUESTS.pop(movie_id, None)
      if request and request.get("pending"):
        pending = _movie_payload(request["pending"])
        movie.update(pending)
      _update_movie_approval_status(movie, "approved")
      return _decorate_movie(movie)
    _update_movie_approval_status(movie, "changes_requested")
    return _decorate_movie(movie)
  return None


def register_movie_asset_change(movie_id: str, kind: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = _prepare_movie_change_request(movie)
    if kind == "music":
      request["pending"]["music"] = "Music asset updated"
    if not movie.get("archived"):
      _update_movie_approval_status(movie, "pending_super_admin_approval")
    return _pending_or_live(movie, prefer_pending=True)
  return None


def update_movie_content_delivery_start(movie_id: str, delivery_start_at: str | None) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    movie["delivery_start_at"] = delivery_start_at
    return _pending_or_live(movie)
  return None


def release_movie_main_content(movie_id: str, release_date_time: str, release_passcode: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    movie["password_publish_at"] = release_date_time
    movie["release_passcode"] = release_passcode.strip()
    movie["reservation_close_at"] = _derive_reservation_close_at(release_date_time)
    return _pending_or_live(movie)
  return None


def clear_movie_content_release_state(movie_id: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    movie["delivery_start_at"] = None
    movie["password_publish_at"] = None
    movie["release_passcode"] = None
    movie["reservation_close_at"] = None
    movie["release_date"] = "TBA"
    movie["buy_now_enabled"] = False
    movie["release_decision"] = "pending"
    movie["stage"] = "upcoming"
    movie["stage_label"] = "Upcoming"
    movie["countdown"] = "Release date to be confirmed"
    return _pending_or_live(movie)
  return None


def get_movie_approval_review(movie_id: str) -> dict | None:
  for movie in MOVIES:
    if movie["id"] != movie_id:
      continue
    request = MOVIE_CHANGE_REQUESTS.get(movie_id, {})
    baseline = deepcopy(request.get("baseline") or {})
    pending = deepcopy(request.get("pending") or _movie_payload(movie))
    changes = []
    for field, label in {
      "title_category": "Title Category",
      "title": "Title Name",
      "title_caption": "Title Caption",
      "genre": "Genre",
      "cast_credits": "Cast & Credits",
      "stage_label": "Stage",
      "release_date": "Release Date",
      "stars_required": "Stars Required - Online",
      "stars_required_theatre": "Stars Required - Theatre",
      "expected_stars": "Target Stars",
      "description": "Story Line",
      "poster": "Primary Poster",
      "posters": "Poster Summary",
      "music": "Music Summary",
    }.items():
      current_value = str(baseline.get(field) or "Not set")
      pending_value = str(pending.get(field) or "Not set")
      if current_value == pending_value:
        continue
      changes.append({
        "field": field,
        "label": label,
        "current_value": current_value,
        "pending_value": pending_value,
      })
    return {
      "item": _pending_or_live(movie, prefer_pending=True),
      "current_item": _decorate_movie(baseline) if baseline else None,
      "pending_item": _decorate_movie(pending),
      "changes": changes,
      "asset_changes": [],
      "has_pending_changes": bool(request or changes),
    }
  return None


def list_users() -> list[dict]:
  items = []
  for user in deepcopy(USERS):
    item = {key: value for key, value in user.items() if key != "password_hash"}
    item["star_balance"] = int(item.get("available_stars", max(item.get("points", 0) // 100, 0)))
    item["blocked_stars"] = int(item.get("blocked_stars", 0))
    item["disc_balance"] = max(item.get("points", 0) * 10, 0)
    items.append(item)
  return items


def get_user_profile(user_id: str) -> dict | None:
  for item in list_users():
    if item["id"] == user_id:
      item["blocked_stars"] = 0
      item["reservations"] = [
        {
          "movie_id": reservation["movie_id"],
          "title": reservation["title"],
          "title_caption": reservation.get("title_caption"),
          "stars_required": reservation["stars_required"],
          "status": reservation["status"],
          "reservation_mode": reservation.get("reservation_mode"),
          "quality_code": reservation.get("quality_code"),
          "release_date": reservation.get("release_date"),
        }
        for reservation in MOVIE_RESERVATIONS
        if reservation["user_id"] == user_id and reservation["status"] in {"blocked", "fulfilled"}
      ]
      item["notifications"] = _get_viewer_notifications(user_id, 10)
      return item
  return None


def authenticate_user(email: str, password: str) -> dict | None:
  password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
  for user in USERS:
    if user["email"].lower() == email.lower() and user["password_hash"] == password_hash:
      return {key: value for key, value in deepcopy(user).items() if key != "password_hash"}
  return None


def create_user(payload: dict) -> dict:
  normalized_email = payload["email"].strip().lower()
  for existing in USERS:
    if existing["email"].lower() == normalized_email:
      raise ValueError("A user with this email already exists.")

  user = {
    "id": f'acct-{secrets.token_hex(4)}',
    "name": payload["name"].strip(),
    "email": normalized_email,
    "password_hash": hashlib.sha256(payload["password"].encode("utf-8")).hexdigest(),
    "role": payload["role"],
    "status": payload["status"],
    "points": int(payload.get("star_balance", 0)) * 100,
    "available_stars": int(payload.get("star_balance", 0)),
    "blocked_stars": 0,
  }
  USERS.append(user)
  created = {key: value for key, value in deepcopy(user).items() if key != "password_hash"}
  created["star_balance"] = max(created.get("points", 0) // 100, 0)
  created["disc_balance"] = max(created.get("points", 0) * 10, 0)
  return created


def update_user_access(user_id: str, name: str, role: str, status: str, star_balance: int) -> dict | None:
  for user in USERS:
    if user["id"] != user_id:
      continue
    user["name"] = name
    user["role"] = role
    user["status"] = status
    user["points"] = star_balance * 100
    user["available_stars"] = star_balance
    user["blocked_stars"] = int(user.get("blocked_stars", 0))
    return {key: value for key, value in deepcopy(user).items() if key != "password_hash"}
  return None


def delete_user(user_id: str) -> dict | None:
  for index, user in enumerate(USERS):
    if user["id"] != user_id:
      continue
    deleted_user = {key: value for key, value in deepcopy(user).items() if key != "password_hash"}
    del USERS[index]
    return deleted_user
  return None
