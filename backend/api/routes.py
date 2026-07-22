from __future__ import annotations

from base64 import b64encode
from pathlib import Path
import hashlib
import json
import re
import secrets
import shutil
import site
import sys
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
import zipfile

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
user_site_packages = site.getusersitepackages()
if user_site_packages and user_site_packages not in sys.path:
  sys.path.append(user_site_packages)
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from backend import auth as session_auth
from backend.core.config import get_settings
from backend.core.time_utils import app_now, is_app_time_reached, parse_app_datetime
from backend import persistence
from backend.data import demo_store
from backend.db import get_db
from backend.models import ContentDeliveryEnrollmentRecord, ReservationRecord, TitleRecord, UserRecord
from backend.schemas import (
  AdminActionResponse,
  ApprovalUpdateRequest,
  ApprovalReviewResponse,
  AdminMovieCreateRequest,
  AdminMoviePricingConfigRequest,
  DeliveryDownloadCompleteRequest,
  DeliveryManifestResponse,
  DeliveryPreferenceRequest,
  DeliverySlotAcquireRequest,
  DeliverySlotHeartbeatRequest,
  DeliverySlotResponse,
  DeliveryStatusResponse,
  AdminMovieUpdateRequest,
  AdminMovieActionResponse,
  AdminMovieListResponse,
  ContentQualityListResponse,
  ContentQualityResponse,
  DeliveryQueueItemResponse,
  DeliveryQueueListResponse,
  DeliveryQueueSummaryResponse,
  MediaAssetListResponse,
  MediaAssetResponse,
  AdminSummaryResponse,
  StarPricingSettingsRequest,
  StarPricingSettingsResponse,
  AdminUserCreateRequest,
  MovieDetailResponse,
  RegisterRequest,
  ReleaseMainContentRequest,
  TaxonomyActionResponse,
  TaxonomyListResponse,
  TaxonomyUpsertRequest,
  AdminUserActionResponse,
  AdminUserListResponse,
  AdminUserUpdateRequest,
  HealthResponse,
  LoginRequest,
  LoginResponse,
  MovieInterestRequest,
  MovieInterestResponse,
  MovieListResponse,
  PublishMovieRequest,
  MoviePublishRequest,
  PlatformSummaryResponse,
  ProducerPublishResponse,
  QueueItemUpdateResponse,
  QueueStatusUpdateRequest,
  QueueListResponse,
  StageUpdateRequest,
  ViewerSessionResponse,
)

router = APIRouter(prefix="/api")
SUPPORTED_TAXONOMIES = {"categories", "genres", "grades"}
LIBRARY_MEDIA_ROOT = Path(__file__).resolve().parents[2] / "media" / "library"
CONTENT_KDF_ITERATIONS = 390_000
CONTENT_TAG_SIZE = 16
CONTENT_NONCE_SIZE = 12
CONTENT_SALT_SIZE = 16
CONTENT_PLAINTEXT_CHUNK_SIZE = 8 * 1024 * 1024
WEB_PLAYABLE_MAIN_CONTENT_EXTENSIONS = {".mp4", ".m4v", ".webm"}
DELIVERY_SLOT_TTL_MINUTES = 20
DELIVERY_MAX_ACTIVE_SLOTS_PER_MOVIE = 3
DELIVERY_QUEUE_MIN_RETRY_SECONDS = 60
DELIVERY_QUEUE_DEFAULT_RETRY_SECONDS = 120
DELIVERY_QUEUE_MAX_RETRY_SECONDS = 900


def _safe_name(value: str) -> str:
  return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "file"


def _is_valid_email(value: str) -> bool:
  return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value.strip()))


def _asset_extension(upload: UploadFile, fallback: str = ".bin") -> str:
  extension = Path(upload.filename or "").suffix.lower()
  sanitized = re.sub(r"[^a-z0-9.]+", "", extension)
  return sanitized if sanitized.startswith(".") and len(sanitized) > 1 else fallback


def _build_asset_filename(movie_id: str, asset_code: str, upload: UploadFile, variant: str | None = None) -> str:
  movie_code = re.sub(r"[^A-Z0-9]+", "", movie_id.upper()) or "TITLE"
  unique_code = secrets.token_hex(4).upper()
  parts = [movie_code]
  if variant:
    parts.append(variant.upper())
  parts.extend([asset_code.upper(), unique_code])
  return f'{"-".join(parts)}{_asset_extension(upload)}'


def _normalize_quality_code(value: str) -> str:
  return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _movie_content_qualities(movie: dict) -> list[dict]:
  options = movie.get("online_pricing_options") or []
  qualities: list[dict] = []
  for index, item in enumerate(options, start=1):
    quality_code = _normalize_quality_code(str(item.get("quality_code") or ""))
    quality_label = str(item.get("quality_label") or "").strip()
    stars_required = int(item.get("stars_required") or 0)
    sort_order = int(item.get("sort_order") or index)
    if not quality_code or not quality_label or stars_required <= 0:
      continue
    qualities.append(
      {
        "quality_code": quality_code,
        "quality_label": quality_label,
        "stars_required": stars_required,
        "sort_order": sort_order,
      }
    )
  if not qualities:
    fallback_stars = max(1, int(movie.get("stars_required") or movie.get("reserve_star_price") or 1))
    qualities.append(
      {
        "quality_code": "main",
        "quality_label": "Main Quality",
        "stars_required": fallback_stars,
        "sort_order": 1,
      }
    )
  qualities.sort(key=lambda item: (item["sort_order"], item["quality_label"]))
  return qualities


def _build_content_chunk_filename(movie_id: str, quality_code: str, source_index: int, chunk_index: int) -> str:
  movie_code = re.sub(r"[^A-Z0-9]+", "", movie_id.upper()) or "TITLE"
  quality_code = re.sub(r"[^A-Z0-9]+", "", quality_code.upper()) or "QUALITY"
  unique_code = secrets.token_hex(4).upper()
  return f"{movie_code}-{quality_code}-SRC{source_index:03d}-CH{chunk_index:04d}-CONT-{unique_code}.vcnr"


def _validate_web_playable_main_content(upload: UploadFile) -> None:
  extension = Path(upload.filename or "").suffix.lower()
  if extension not in WEB_PLAYABLE_MAIN_CONTENT_EXTENSIONS:
    raise HTTPException(
      status_code=400,
      detail="For the website player, Upload Main Content accepts only MP4, M4V, or WebM files.",
    )


def _get_movie_or_404(db: Session | None, movie_id: str) -> dict:
  movie_items = persistence.list_movies(db, include_archived=True) if db else demo_store.list_movies(include_archived=True)
  matched = next((item for item in movie_items if item["id"] == movie_id), None)
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return matched


def _relative_media_path(file_path: Path) -> str:
  return (Path("media") / file_path.relative_to(LIBRARY_MEDIA_ROOT.parent)).as_posix()


def _delete_movie_media_folder(movie_id: str) -> None:
  target_path = (LIBRARY_MEDIA_ROOT / movie_id).resolve()
  library_root = LIBRARY_MEDIA_ROOT.resolve()
  try:
    target_path.relative_to(library_root)
  except ValueError as error:
    raise HTTPException(status_code=400, detail="Invalid movie media path.") from error

  if target_path.exists():
    shutil.rmtree(target_path)


def _delete_movie_content_folder(movie_id: str) -> None:
  target_path = (LIBRARY_MEDIA_ROOT / movie_id / "content").resolve()
  library_root = LIBRARY_MEDIA_ROOT.resolve()
  try:
    target_path.relative_to(library_root)
  except ValueError as error:
    raise HTTPException(status_code=400, detail="Invalid movie content path.") from error

  if target_path.exists():
    shutil.rmtree(target_path)


def _media_asset_payload(file_path: Path, kind: str, orientation: str | None = None) -> dict:
  relative_path = _relative_media_path(file_path)
  return {
    "name": file_path.name,
    "path": relative_path,
    "url": f'/{relative_path}',
    "kind": kind,
    "orientation": orientation,
  }


def _sanitize_movie_payload(movie: dict | None) -> dict | None:
  if movie is None:
    return None

  normalized = dict(movie)
  online_pricing_options = normalized.get("online_pricing_options")
  if isinstance(online_pricing_options, str):
    try:
      online_pricing_options = json.loads(online_pricing_options)
    except json.JSONDecodeError:
      online_pricing_options = []
  normalized["online_pricing_options"] = online_pricing_options if isinstance(online_pricing_options, list) else []

  cast_credits = normalized.get("cast_credits")
  if isinstance(cast_credits, str):
    try:
      cast_credits = json.loads(cast_credits)
    except json.JSONDecodeError:
      cast_credits = []
  normalized["cast_credits"] = cast_credits if isinstance(cast_credits, list) else []

  poster_path = normalized.get("poster")
  if isinstance(poster_path, str) and poster_path.startswith("media/"):
    local_path = LIBRARY_MEDIA_ROOT.parent / Path(poster_path).relative_to("media")
    if not local_path.exists():
      normalized["poster"] = None
  return normalized


def _sanitize_movie_payloads(items: list[dict]) -> list[dict]:
  return [item for item in (_sanitize_movie_payload(movie) for movie in items) if item is not None]


def _list_media_assets(movie_id: str, kind: str) -> list[dict]:
  base_path = LIBRARY_MEDIA_ROOT / movie_id
  items: list[dict] = []

  if kind == "posters":
    for orientation in ("vertical", "horizontal"):
      folder = base_path / "posters" / orientation
      if not folder.exists():
        continue
      for file_path in sorted([item for item in folder.iterdir() if item.is_file()]):
        items.append(_media_asset_payload(file_path, kind, orientation))
  else:
    folder_name = "trailers" if kind == "trailer" else "gallery" if kind == "gallery" else "music" if kind == "music" else "content"
    folder = base_path / folder_name
    if folder.exists():
      for file_path in sorted([item for item in folder.iterdir() if item.is_file()]):
        if kind == "content" and file_path.name == "manifest.json":
          continue
        items.append(_media_asset_payload(file_path, kind))

  return items


def _poster_asset_summary(movie_id: str) -> tuple[str | None, str]:
  poster_items = _list_media_assets(movie_id, "posters")
  primary = next((item["path"] for item in poster_items if item.get("orientation") == "vertical"), None)
  if primary is None and poster_items:
    primary = poster_items[0]["path"]
  count_label = f"{len(poster_items)} poster upload{'s' if len(poster_items) != 1 else ''}" if poster_items else "Poster upload pending"
  return primary, count_label


def _delete_media_asset(movie_id: str, kind: str, asset_name: str) -> None:
  safe_asset_name = Path(asset_name).name
  if safe_asset_name != asset_name:
    raise HTTPException(status_code=400, detail="Invalid asset name.")

  if kind == "posters":
    candidate_paths = [
      LIBRARY_MEDIA_ROOT / movie_id / "posters" / "vertical" / safe_asset_name,
      LIBRARY_MEDIA_ROOT / movie_id / "posters" / "horizontal" / safe_asset_name,
    ]
  elif kind == "trailer":
    candidate_paths = [LIBRARY_MEDIA_ROOT / movie_id / "trailers" / safe_asset_name]
  elif kind == "gallery":
    candidate_paths = [LIBRARY_MEDIA_ROOT / movie_id / "gallery" / safe_asset_name]
  elif kind == "music":
    candidate_paths = [LIBRARY_MEDIA_ROOT / movie_id / "music" / safe_asset_name]
  elif kind == "content":
    candidate_paths = [LIBRARY_MEDIA_ROOT / movie_id / "content" / safe_asset_name]
  else:
    raise HTTPException(status_code=404, detail="Media type not found.")

  target_path = next((path for path in candidate_paths if path.exists() and path.is_file()), None)
  if target_path is None:
    raise HTTPException(status_code=404, detail="Media file not found.")
  target_path.unlink()


def _content_manifest_path(movie_id: str) -> Path:
  return LIBRARY_MEDIA_ROOT / movie_id / "content" / "manifest.json"


def _content_folder_path(movie_id: str) -> Path:
  return LIBRARY_MEDIA_ROOT / movie_id / "content"


def _viewer_content_manifest_payload(manifest: dict, quality_code: str | None = None) -> dict:
  normalized_quality_code = _normalize_quality_code(quality_code) if quality_code else ""
  qualities = manifest.get("qualities", [])
  files = manifest.get("files", [])
  if normalized_quality_code:
    qualities = [
      item for item in qualities
      if _normalize_quality_code(str(item.get("quality_code") or "")) == normalized_quality_code
    ]
    files = [
      item for item in files
      if _normalize_quality_code(str(item.get("quality_code") or "")) == normalized_quality_code
    ]
  return {
    "movie_id": manifest.get("movie_id"),
    "movie_title": manifest.get("movie_title"),
    "delivery_start_at": manifest.get("delivery_start_at"),
    "upload_start_at": manifest.get("upload_start_at"),
    "password_publish_at": manifest.get("password_publish_at"),
    "qualities": qualities,
    "encryption": manifest.get("encryption", {}),
    "chunk_count": len(files),
    "files": files,
    "updated_at": manifest.get("updated_at"),
  }


def _download_is_available(movie: dict, manifest: dict | None = None) -> bool:
  delivery_start_at = (manifest or {}).get("delivery_start_at") or movie.get("delivery_start_at")
  return is_app_time_reached(str(delivery_start_at or ""))


def _release_is_unlocked(movie: dict) -> bool:
  password_publish_at = movie.get("password_publish_at")
  release_passcode = (movie.get("release_passcode") or "").strip()
  if not password_publish_at or not release_passcode:
    return False
  return is_app_time_reached(str(password_publish_at))


def _delivery_entitlement_status(movie: dict) -> str:
  status = movie.get("viewer_reservation_online_status") or movie.get("viewer_reservation_status")
  if status in {"blocked", "fulfilled"}:
    return status
  return "none"


def _require_delivery_entitlement(movie: dict) -> None:
  if _delivery_entitlement_status(movie) not in {"blocked", "fulfilled"}:
    raise HTTPException(status_code=403, detail="Reserve or buy this title first to manage content delivery.")


def _require_delivery_reservation(
  db: Session,
  movie_id: str,
  user_id: str,
  quality_code: str,
) -> ReservationRecord:
  normalized_quality_code = _normalize_quality_code(quality_code)
  linked_title = db.query(TitleRecord).filter(TitleRecord.legacy_movie_id == movie_id).first()
  if linked_title is None:
    raise HTTPException(status_code=404, detail="Linked title not found for this movie.")
  reservation = (
    db.query(ReservationRecord)
    .filter(
      ReservationRecord.title_id == linked_title.id,
      ReservationRecord.user_id == user_id,
      ReservationRecord.reservation_kind == "online",
      ReservationRecord.quality_code == normalized_quality_code,
      ReservationRecord.status.in_(["blocked", "fulfilled"]),
    )
    .first()
  )
  if reservation is None:
    raise HTTPException(status_code=403, detail="Reserve this exact title quality before managing delivery.")
  return reservation


def _get_or_create_delivery_enrollment(
  db: Session,
  movie_id: str,
  user_id: str,
  quality_code: str,
) -> ContentDeliveryEnrollmentRecord:
  normalized_quality_code = _normalize_quality_code(quality_code)
  enrollment = (
    db.query(ContentDeliveryEnrollmentRecord)
    .filter(
      ContentDeliveryEnrollmentRecord.movie_id == movie_id,
      ContentDeliveryEnrollmentRecord.user_id == user_id,
      ContentDeliveryEnrollmentRecord.quality_code == normalized_quality_code,
    )
    .first()
  )
  if enrollment is None:
    enrollment = ContentDeliveryEnrollmentRecord(movie_id=movie_id, user_id=user_id, quality_code=normalized_quality_code)
    db.add(enrollment)
    db.flush()
  return enrollment


def _active_delivery_slots_query(db: Session, movie_id: str):
  now = datetime.utcnow()
  return (
    db.query(ContentDeliveryEnrollmentRecord)
    .filter(
      ContentDeliveryEnrollmentRecord.movie_id == movie_id,
      ContentDeliveryEnrollmentRecord.slot_token.is_not(None),
      ContentDeliveryEnrollmentRecord.slot_expires_at.is_not(None),
      ContentDeliveryEnrollmentRecord.slot_expires_at > now,
      ContentDeliveryEnrollmentRecord.status.in_(["slot_granted", "downloading"]),
    )
  )


def _queue_position_for_enrollment(db: Session, movie_id: str, enrollment: ContentDeliveryEnrollmentRecord) -> int | None:
  queued = (
    db.query(ContentDeliveryEnrollmentRecord)
    .filter(
      ContentDeliveryEnrollmentRecord.movie_id == movie_id,
      ContentDeliveryEnrollmentRecord.status == "queued",
    )
    .order_by(ContentDeliveryEnrollmentRecord.accepted_at.asc(), ContentDeliveryEnrollmentRecord.id.asc())
    .all()
  )
  for index, item in enumerate(queued, start=1):
    if item.id == enrollment.id:
      return index
  return None


def _recommended_delivery_retry_seconds(queue_position: int | None) -> int:
  if not queue_position or queue_position <= 1:
    return DELIVERY_QUEUE_MIN_RETRY_SECONDS
  # Spread retries out as queue depth grows so large waves do not hit the server together.
  recommended = DELIVERY_QUEUE_DEFAULT_RETRY_SECONDS + ((queue_position - 1) * 15)
  return max(
    DELIVERY_QUEUE_MIN_RETRY_SECONDS,
    min(DELIVERY_QUEUE_MAX_RETRY_SECONDS, recommended),
  )


def _delivery_queue_quality_lookup(movie: dict) -> dict[str, dict]:
  return {item["quality_code"]: item for item in _movie_content_qualities(movie)}


def _serialize_delivery_status(
  movie: dict,
  enrollment: ContentDeliveryEnrollmentRecord | None,
  queue_position: int | None = None,
  reservation: ReservationRecord | None = None,
) -> DeliveryStatusResponse:
  quality_lookup = _delivery_queue_quality_lookup(movie)
  quality_code = enrollment.quality_code if enrollment else str(reservation.quality_code or "").strip().lower() if reservation else ""
  quality_info = quality_lookup.get(quality_code) if quality_code else None
  has_active_slot = bool(
    enrollment
    and enrollment.slot_token
    and enrollment.slot_expires_at
    and enrollment.slot_expires_at > datetime.utcnow()
    and enrollment.status in {"slot_granted", "downloading"}
  )
  return DeliveryStatusResponse(
    movie_id=movie["id"],
    quality_code=quality_code or None,
    quality_label=quality_info["quality_label"] if quality_info else None,
    stars_required=int(reservation.stars_required if reservation else quality_info["stars_required"] if quality_info else 0),
    delivery_start_at=movie.get("delivery_start_at"),
    password_publish_at=movie.get("password_publish_at"),
    release_date=movie.get("release_date"),
    entitlement_status=_delivery_entitlement_status(movie),
    is_download_window_open=_download_is_available(movie),
    is_release_unlocked=_release_is_unlocked(movie),
    release_passcode_available=_release_is_unlocked(movie),
    release_passcode=(movie.get("release_passcode") or "").strip() or None if _release_is_unlocked(movie) else None,
    enrollment_status=enrollment.status if enrollment else None,
    wifi_only=enrollment.wifi_only if enrollment else True,
    charging_only=enrollment.charging_only if enrollment else False,
    auto_download=enrollment.auto_download if enrollment else True,
    has_active_slot=has_active_slot,
    slot_token=enrollment.slot_token if has_active_slot else None,
    slot_expires_at=enrollment.slot_expires_at.isoformat(timespec="minutes") if has_active_slot and enrollment.slot_expires_at else None,
    queue_position=queue_position,
    local_encrypted_path=enrollment.local_encrypted_path if enrollment else None,
  )


def _delivery_queue_summary_from_rows(rows: list[ContentDeliveryEnrollmentRecord]) -> dict[str, int]:
  summary = {
    "accepted": 0,
    "queued": 0,
    "slot_granted": 0,
    "downloading": 0,
    "downloaded": 0,
    "failed": 0,
  }
  for row in rows:
    status = str(row.status or "").strip().lower()
    if status not in summary:
      continue
    summary[status] += 1
  return summary


def _serialize_delivery_queue_item(
  movie: dict,
  enrollment: ContentDeliveryEnrollmentRecord,
  user_name: str,
  user_email: str,
  reservation: ReservationRecord | None,
  fifo_position: int | None,
  queue_position: int | None,
) -> dict:
  quality_lookup = _delivery_queue_quality_lookup(movie)
  quality_code = str(enrollment.quality_code or "").strip().lower()
  quality_info = quality_lookup.get(quality_code) if quality_code else None
  accepted_at = enrollment.accepted_at.isoformat(timespec="seconds") if enrollment.accepted_at else datetime.utcnow().isoformat(timespec="seconds")
  updated_at = enrollment.updated_at.isoformat(timespec="seconds") if enrollment.updated_at else accepted_at
  slot_expires_at = enrollment.slot_expires_at.isoformat(timespec="seconds") if enrollment.slot_expires_at else None
  download_started_at = enrollment.download_started_at.isoformat(timespec="seconds") if enrollment.download_started_at else None
  download_completed_at = enrollment.download_completed_at.isoformat(timespec="seconds") if enrollment.download_completed_at else None
  return {
    "movie_id": movie["id"],
    "movie_title": movie["title"],
    "user_id": enrollment.user_id,
    "user_name": user_name,
    "user_email": user_email,
    "fifo_position": fifo_position,
    "quality_code": quality_code or None,
    "quality_label": quality_info["quality_label"] if quality_info else None,
    "stars_required": int(reservation.stars_required if reservation else quality_info["stars_required"] if quality_info else 0),
    "device_label": enrollment.device_label,
    "status": enrollment.status,
    "queue_position": queue_position,
    "wifi_only": bool(enrollment.wifi_only),
    "charging_only": bool(enrollment.charging_only),
    "auto_download": bool(enrollment.auto_download),
    "accepted_at": accepted_at,
    "updated_at": updated_at,
    "download_started_at": download_started_at,
    "download_completed_at": download_completed_at,
    "slot_expires_at": slot_expires_at,
    "last_error": enrollment.last_error,
  }


def _require_valid_slot(
  db: Session,
  movie_id: str,
  user_id: str,
  slot_token: str,
) -> ContentDeliveryEnrollmentRecord:
  enrollment = (
    db.query(ContentDeliveryEnrollmentRecord)
    .filter(
      ContentDeliveryEnrollmentRecord.movie_id == movie_id,
      ContentDeliveryEnrollmentRecord.user_id == user_id,
      ContentDeliveryEnrollmentRecord.slot_token == slot_token,
    )
    .first()
  )
  if enrollment is None or enrollment.slot_expires_at is None or enrollment.slot_expires_at <= datetime.utcnow():
    raise HTTPException(status_code=403, detail="A valid active download slot is required.")
  return enrollment


async def _save_upload_file(target_path: Path, upload: UploadFile) -> None:
  target_path.parent.mkdir(parents=True, exist_ok=True)
  with target_path.open("wb") as output:
    while True:
      chunk = await upload.read(1024 * 1024)
      if not chunk:
        break
      output.write(chunk)
  await upload.close()


def _normalize_datetime_local(value: str | None) -> str:
  normalized = (value or "").strip()
  if not normalized:
    raise HTTPException(status_code=400, detail="Please choose the upload future start date and time.")

  parsed = parse_app_datetime(normalized)
  if parsed is None:
    raise HTTPException(status_code=400, detail="Enter a valid upload future start date and time.")

  parsed = parsed.replace(second=0, microsecond=0)
  if parsed <= app_now():
    raise HTTPException(status_code=400, detail="Upload future start date and time must be in the future.")

  return parsed.replace(tzinfo=None).isoformat(timespec="minutes")


def _derive_content_key(password: str, salt: bytes) -> bytes:
  kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt,
    iterations=CONTENT_KDF_ITERATIONS,
  )
  return kdf.derive(password.encode("utf-8"))


async def _encrypt_upload_file_into_chunks(
  content_root: Path,
  upload: UploadFile,
  password: str,
  aad_prefix: str,
  movie_id: str,
  quality_code: str,
  quality_label: str,
  source_index: int,
) -> list[dict]:
  chunk_records: list[dict] = []
  chunk_index = 0
  source_name = upload.filename or f"source-{source_index}"

  while True:
    plaintext = await upload.read(CONTENT_PLAINTEXT_CHUNK_SIZE)
    if not plaintext:
      break

    chunk_index += 1
    chunk_name = _build_content_chunk_filename(movie_id, quality_code, source_index, chunk_index)
    target_path = content_root / chunk_name
    salt = secrets.token_bytes(CONTENT_SALT_SIZE)
    nonce = secrets.token_bytes(CONTENT_NONCE_SIZE)
    aad = f"{aad_prefix}:{quality_code}:{source_index}:{chunk_index}:{source_name}:{target_path.name}".encode("utf-8")
    key = _derive_content_key(password, salt)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(aad)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("wb") as output:
      output.write(encryptor.update(plaintext))
      output.write(encryptor.finalize())
      output.write(encryptor.tag)

    chunk_records.append({
      "name": target_path.name,
      "quality_code": quality_code,
      "quality_label": quality_label,
      "original_name": source_name,
      "source_index": source_index,
      "chunk_index": chunk_index,
      "salt": b64encode(salt).decode("ascii"),
      "nonce": b64encode(nonce).decode("ascii"),
      "aad": b64encode(aad).decode("ascii"),
      "source_size": len(plaintext),
      "encrypted_size": target_path.stat().st_size,
    })

  await upload.close()
  return chunk_records


def _read_content_manifest(movie_id: str) -> dict | None:
  manifest_path = _content_manifest_path(movie_id)
  if not manifest_path.exists():
    return None
  try:
    return json.loads(manifest_path.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    return None


def _write_content_manifest(movie_id: str, manifest: dict) -> None:
  manifest_path = _content_manifest_path(movie_id)
  manifest_path.parent.mkdir(parents=True, exist_ok=True)
  manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")


def _default_content_manifest(movie: dict) -> dict:
  return {
    "movie_id": movie["id"],
    "movie_title": movie["title"],
    "delivery_start_at": movie.get("delivery_start_at"),
    "upload_start_at": movie.get("delivery_start_at"),
    "password_publish_at": movie.get("password_publish_at"),
    "qualities": [],
    "chunk_count": 0,
    "encryption": {},
    "files": [],
    "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
  }


def _load_content_manifest(movie: dict) -> dict:
  manifest = _read_content_manifest(movie["id"])
  if manifest is None:
    manifest = _default_content_manifest(movie)
  manifest.setdefault("movie_id", movie["id"])
  manifest.setdefault("movie_title", movie["title"])
  manifest.setdefault("delivery_start_at", movie.get("delivery_start_at"))
  manifest.setdefault("upload_start_at", movie.get("delivery_start_at"))
  manifest.setdefault("password_publish_at", movie.get("password_publish_at"))
  manifest.setdefault("qualities", [])
  manifest.setdefault("files", [])
  manifest.setdefault("chunk_count", len(manifest.get("files", [])))
  manifest.setdefault("encryption", {})
  manifest.setdefault("updated_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
  return manifest


def _content_quality_lookup(manifest: dict) -> dict[str, dict]:
  return {
    str(item.get("quality_code") or "").strip().lower(): item
    for item in manifest.get("qualities", [])
    if str(item.get("quality_code") or "").strip()
  }


def _require_manifest_quality(manifest: dict, quality_code: str) -> None:
  normalized_quality_code = _normalize_quality_code(quality_code)
  if normalized_quality_code not in _content_quality_lookup(manifest):
    raise HTTPException(status_code=404, detail="Encrypted content is not uploaded for this title quality.")


def _content_is_complete(movie: dict, manifest: dict) -> bool:
  required_codes = {_normalize_quality_code(item["quality_code"]) for item in _movie_content_qualities(movie)}
  available_codes = set(_content_quality_lookup(manifest).keys())
  return bool(required_codes) and required_codes.issubset(available_codes)


def _quality_file_root(movie_id: str, quality_code: str) -> Path:
  return _content_folder_path(movie_id) / _normalize_quality_code(quality_code)


def _delete_quality_files(movie_id: str, manifest: dict, quality_code: str) -> int:
  quality_key = _normalize_quality_code(quality_code)
  quality_entry = _content_quality_lookup(manifest).get(quality_key)
  if quality_entry is None:
    return 0

  removed = 0
  target_root = _quality_file_root(movie_id, quality_key)
  if target_root.exists():
    removed = sum(1 for file_path in target_root.rglob("*") if file_path.is_file())
    shutil.rmtree(target_root)
  manifest["qualities"] = [
    item for item in manifest.get("qualities", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) != quality_key
  ]
  manifest["files"] = [
    item for item in manifest.get("files", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) != quality_key
  ]
  manifest["chunk_count"] = len(manifest.get("files", []))
  manifest["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
  if manifest["qualities"]:
    _write_content_manifest(movie_id, manifest)
  else:
    _content_manifest_path(movie_id).unlink(missing_ok=True)
  return removed


def _content_quality_statuses(movie: dict, manifest: dict) -> list[ContentQualityResponse]:
  quality_lookup = _content_quality_lookup(manifest)
  items: list[ContentQualityResponse] = []
  for option in _movie_content_qualities(movie):
    quality_key = option["quality_code"]
    quality_entry = quality_lookup.get(quality_key)
    items.append(
      ContentQualityResponse(
        quality_code=quality_key,
        quality_label=option["quality_label"],
        stars_required=option["stars_required"],
        uploaded=quality_entry is not None,
        source_name=str(quality_entry.get("source_name")) if quality_entry and quality_entry.get("source_name") else None,
        source_extension=str(quality_entry.get("source_extension")) if quality_entry and quality_entry.get("source_extension") else None,
        chunk_count=int(quality_entry.get("chunk_count") or 0) if quality_entry else 0,
        uploaded_at=str(quality_entry.get("uploaded_at")) if quality_entry and quality_entry.get("uploaded_at") else None,
      )
    )
  return items


def _replace_content_quality_entry(manifest: dict, quality_code: str, quality_entry: dict) -> None:
  normalized_quality_code = _normalize_quality_code(quality_code)
  manifest["qualities"] = [
    item for item in manifest.get("qualities", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) != normalized_quality_code
  ]
  manifest["qualities"].append(quality_entry)
  manifest["qualities"].sort(key=lambda item: (int(item.get("sort_order") or 0), str(item.get("quality_label") or "")))
  manifest["files"] = [
    item for item in manifest.get("files", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) != normalized_quality_code
  ]
  manifest["files"].extend(quality_entry.get("files", []))
  manifest["chunk_count"] = len(manifest["files"])
  manifest["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"


async def _store_content_quality_upload(
  movie: dict,
  quality_code: str,
  file: UploadFile,
  password: str,
) -> tuple[dict, dict, int]:
  quality_options = {option["quality_code"]: option for option in _movie_content_qualities(movie)}
  normalized_quality_code = _normalize_quality_code(quality_code)
  quality_option = quality_options.get(normalized_quality_code)
  if quality_option is None:
    raise HTTPException(status_code=400, detail="That title quality is not configured for this title.")
  if not password.strip():
    raise HTTPException(status_code=400, detail="Please enter a password.")
  _validate_web_playable_main_content(file)

  content_root = _quality_file_root(movie["id"], normalized_quality_code)
  content_root.mkdir(parents=True, exist_ok=True)
  manifest = _load_content_manifest(movie)
  quality_lookup = _content_quality_lookup(manifest)
  if normalized_quality_code in quality_lookup:
    _delete_quality_files(movie["id"], manifest, normalized_quality_code)

  saved_chunks = await _encrypt_upload_file_into_chunks(
    content_root=content_root,
    upload=file,
    password=password,
    aad_prefix=f'{movie["id"]}:{normalized_quality_code}',
    movie_id=movie["id"],
    quality_code=normalized_quality_code,
    quality_label=quality_option["quality_label"],
    source_index=1,
  )
  for chunk in saved_chunks:
    chunk["source_extension"] = Path(chunk["original_name"]).suffix.lower() or None

  quality_entry = {
    "quality_code": normalized_quality_code,
    "quality_label": quality_option["quality_label"],
    "stars_required": quality_option["stars_required"],
    "sort_order": quality_option["sort_order"],
    "source_name": file.filename or f'{quality_option["quality_label"]}.mp4',
    "source_extension": Path(file.filename or "").suffix.lower() or None,
    "password_sha256": hashlib.sha256(password.encode("utf-8")).hexdigest(),
    "uploaded_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    "chunk_count": len(saved_chunks),
    "files": saved_chunks,
  }
  _replace_content_quality_entry(manifest, normalized_quality_code, quality_entry)
  manifest["movie_id"] = movie["id"]
  manifest["movie_title"] = movie["title"]
  manifest["delivery_start_at"] = movie.get("delivery_start_at")
  manifest["upload_start_at"] = movie.get("delivery_start_at")
  manifest["password_publish_at"] = movie.get("password_publish_at")
  manifest["encryption"] = {
    "algorithm": "AES-256-GCM",
    "kdf": "PBKDF2-HMAC-SHA256",
    "iterations": CONTENT_KDF_ITERATIONS,
    "salt_bytes": CONTENT_SALT_SIZE,
    "nonce_bytes": CONTENT_NONCE_SIZE,
    "tag_bytes": CONTENT_TAG_SIZE,
  }
  _write_content_manifest(movie["id"], manifest)
  return quality_option, quality_entry, len(saved_chunks)


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, str]:
  if not authorization:
    raise HTTPException(status_code=401, detail="Sign in is required.")

  scheme, _, token = authorization.partition(" ")
  if scheme.lower() != "bearer" or not token:
    raise HTTPException(status_code=401, detail="A valid session token is required.")

  session = session_auth.get_session(token)
  if session is None:
    raise HTTPException(status_code=401, detail="Your session has expired. Please sign in again.")
  if session.status != "active":
    raise HTTPException(status_code=403, detail="This account is not active.")

  return session.to_user()


def require_admin(current_user: dict[str, str] = Depends(get_current_user)) -> dict[str, str]:
  if current_user["role"] not in {"admin", "super_admin"}:
    raise HTTPException(status_code=403, detail="Admin access is required.")
  return current_user


def get_optional_current_user(authorization: str | None = Header(default=None)) -> dict[str, str] | None:
  if not authorization:
    return None
  scheme, _, token = authorization.partition(" ")
  if scheme.lower() != "bearer" or not token:
    return None
  session = session_auth.get_session(token)
  if session is None or session.status != "active":
    return None
  return session.to_user()


def validate_taxonomy_kind(kind: str) -> str:
  if kind not in SUPPORTED_TAXONOMIES:
    raise HTTPException(status_code=404, detail="Taxonomy type not found.")
  return kind


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
  settings = get_settings()
  return HealthResponse(
    status="ok",
    app=settings.app_name,
    environment=settings.app_env,
  )


@router.get("/platform/summary", response_model=PlatformSummaryResponse)
def platform_summary(db: Session | None = Depends(get_db)) -> PlatformSummaryResponse:
  summary = persistence.get_platform_summary(db) if db else demo_store.get_platform_summary()
  return PlatformSummaryResponse(**summary)


@router.get("/movies", response_model=MovieListResponse)
def get_movies(
  stage: str | None = None,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] | None = Depends(get_optional_current_user),
) -> MovieListResponse:
  items = (
    persistence.list_movies(db, stage=stage, viewer_user_id=current_user["id"] if current_user else None)
    if db
    else demo_store.list_movies(stage=stage, viewer_user_id=current_user["id"] if current_user else None)
  )
  return MovieListResponse(items=_sanitize_movie_payloads(items))


@router.get("/movies/{movie_id}/details", response_model=MovieDetailResponse)
def get_movie_details(
  movie_id: str,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] | None = Depends(get_optional_current_user),
) -> MovieDetailResponse:
  items = (
    persistence.list_movies(db, viewer_user_id=current_user["id"] if current_user else None)
    if db
    else demo_store.list_movies(viewer_user_id=current_user["id"] if current_user else None)
  )
  matched = next((item for item in items if item["id"] == movie_id), None)
  if matched is None or matched.get("archived"):
    raise HTTPException(status_code=404, detail="Movie not found.")

  return MovieDetailResponse(
    item=_sanitize_movie_payload(matched),
    posters=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "posters")],
    trailers=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "trailer")],
    gallery=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "gallery")],
    music=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "music")],
    content=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "content")],
  )


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session | None = Depends(get_db)) -> LoginResponse:
  user = persistence.authenticate_user(db, payload.email, payload.password) if db else demo_store.authenticate_user(payload.email, payload.password)
  if user is None:
    raise HTTPException(status_code=401, detail="Invalid email or password.")
  if user["status"] != "active":
    raise HTTPException(status_code=403, detail="This account is not active.")

  next_view = "viewer"
  if user["role"] in {"producer", "creator"}:
    next_view = "producer"
  elif user["role"] in {"admin", "super_admin"}:
    next_view = "admin"

  session = session_auth.create_session(user)

  return LoginResponse(
    message=f'Welcome back, {user["name"]}.',
    role=user["role"],
    next_view=next_view,
    token=session.token,
  )


@router.post("/auth/register", response_model=LoginResponse)
def register(payload: RegisterRequest, db: Session | None = Depends(get_db)) -> LoginResponse:
  normalized_email = payload.email.strip().lower()
  if not _is_valid_email(normalized_email):
    raise HTTPException(status_code=400, detail="Enter a valid email address.")

  registration_payload = {
    "name": payload.name.strip(),
    "email": normalized_email,
    "password": payload.password,
    "role": "viewer",
    "status": "active",
    "star_balance": 0,
  }

  try:
    user = persistence.create_user(db, registration_payload) if db else demo_store.create_user(registration_payload)
  except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error

  session = session_auth.create_session(user)
  return LoginResponse(
    message=f'Welcome to Cine Vault, {user["name"]}. Your viewer account is now active.',
    role=user["role"],
    next_view="viewer",
    token=session.token,
  )


@router.get("/auth/me", response_model=ViewerSessionResponse)
def auth_me(
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] = Depends(get_current_user),
) -> ViewerSessionResponse:
  user = persistence.get_user_profile(db, current_user["id"]) if db else demo_store.get_user_profile(current_user["id"])
  if user is None:
    raise HTTPException(status_code=404, detail="User not found.")
  return ViewerSessionResponse(**user)


@router.post("/movies/{movie_id}/interest", response_model=MovieInterestResponse)
def movie_interest(
  movie_id: str,
  payload: MovieInterestRequest,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] | None = Depends(get_optional_current_user),
) -> MovieInterestResponse:
  if payload.kind == "wish" and current_user is None:
    raise HTTPException(status_code=401, detail="Sign in is required.")
  if payload.kind == "wish" and payload.wish_mode not in {"online", "theatre"}:
    raise HTTPException(status_code=400, detail="Choose how you wish to watch.")

  try:
    result = (
      persistence.update_movie_interest(db, movie_id, payload.kind, current_user["id"] if current_user else None, payload.wish_mode, payload.quality_code)
      if db
      else demo_store.update_movie_interest(movie_id, payload.kind, current_user["id"] if current_user else None, payload.wish_mode, payload.quality_code)
    )
  except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
  if result is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  movie, created = result

  if payload.kind == "wish":
    if created:
      action = "Wish To Watch Online" if payload.wish_mode == "online" else "Wish To Watch In Theatre"
      message = f'{action} recorded for "{movie["title"]}".'
    else:
      message = f'"{movie["title"]}" is already in your wishlist.'
  elif payload.kind == "buy":
    message = f'Buy Now confirmed for "{movie["title"]}".'
  else:
    message = f'Reserve Now recorded for "{movie["title"]}".'
  return MovieInterestResponse(
    item=_sanitize_movie_payload(movie),
    message=message,
  )


@router.get("/producer/queue", response_model=QueueListResponse)
def producer_queue(db: Session | None = Depends(get_db)) -> QueueListResponse:
  items = persistence.list_publish_queue(db) if db else demo_store.list_publish_queue()
  return QueueListResponse(items=items)


@router.post("/producer/publish", response_model=ProducerPublishResponse)
def producer_publish(payload: MoviePublishRequest, db: Session | None = Depends(get_db)) -> ProducerPublishResponse:
  status = "Preview Ready" if payload.preview_only else "Published"
  queue_payload = (
    {
      "id": f"queue-{len((persistence.list_publish_queue(db) if db else demo_store.list_publish_queue())) + 1}",
      "title": payload.title,
      "stage": payload.stage,
      "status": status,
      "note": f"{payload.genre} | Budget {payload.budget} | Expected {payload.expected_revenue} | {payload.description}",
    }
  )
  queue_item = persistence.add_publish_queue_item(db, queue_payload) if db else demo_store.add_publish_queue_item(queue_payload)

  created_movie = None
  if not payload.preview_only:
    movie_payload = (
      {
        "id": f'{payload.title.lower().replace(" ", "-")}-{len((persistence.list_movies(db, include_archived=True) if db else demo_store.list_movies(include_archived=True))) + 1}',
        "stage": payload.stage,
        "title": payload.title,
        "poster": None,
        "genre": payload.genre,
        "stage_label": "Upcoming" if payload.stage == "upcoming" else "New Release" if payload.stage == "released" else "Old Movies",
        "countdown": "Release date to be confirmed" if payload.stage == "upcoming" else "Just published" if payload.stage == "released" else "Catalog placement",
        "release_date": "TBA",
        "description": payload.description,
        "budget": payload.budget,
        "expected_revenue": payload.expected_revenue,
        "wish_count": 0,
        "reserve_count": 0,
        "revenue": "$0K",
        "posters": "Poster upload pending",
        "music": "Music upload pending",
        "reward_bonus": "+0 pts",
      }
    )
    created_movie = persistence.create_movie(db, movie_payload) if db else demo_store.create_movie(movie_payload)

  return ProducerPublishResponse(item=queue_item, movie=_sanitize_movie_payload(created_movie))


@router.get("/admin/review-queue", response_model=QueueListResponse)
def admin_review_queue(
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> QueueListResponse:
  items = persistence.list_publish_queue(db) if db else demo_store.list_publish_queue()
  return QueueListResponse(items=items)


@router.get("/admin/summary", response_model=AdminSummaryResponse)
def admin_summary(
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminSummaryResponse:
  summary = persistence.get_admin_summary(db) if db else demo_store.get_admin_summary()
  return AdminSummaryResponse(**summary)


@router.get("/admin/star-pricing", response_model=StarPricingSettingsResponse)
def admin_star_pricing(
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> StarPricingSettingsResponse:
  settings = persistence.get_star_pricing_settings(db) if db else demo_store.get_star_pricing_settings()
  return StarPricingSettingsResponse(**settings)


@router.put("/admin/star-pricing", response_model=StarPricingSettingsResponse)
def admin_update_star_pricing(
  payload: StarPricingSettingsRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> StarPricingSettingsResponse:
  settings_payload = payload.model_dump()
  settings = persistence.update_star_pricing_settings(db, settings_payload) if db else demo_store.update_star_pricing_settings(settings_payload)
  return StarPricingSettingsResponse(**settings)


@router.get("/admin/taxonomies/{kind}", response_model=TaxonomyListResponse)
def admin_list_taxonomy(
  kind: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> TaxonomyListResponse:
  kind = validate_taxonomy_kind(kind)
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for taxonomy management.")
  items = persistence.list_taxonomy_items(db, kind)
  return TaxonomyListResponse(items=items)


@router.post("/admin/taxonomies/{kind}", response_model=TaxonomyActionResponse)
def admin_create_taxonomy(
  kind: str,
  payload: TaxonomyUpsertRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> TaxonomyActionResponse:
  kind = validate_taxonomy_kind(kind)
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for taxonomy management.")
  item = persistence.create_taxonomy_item(db, kind, payload.model_dump())
  return TaxonomyActionResponse(
    message=f'{kind[:-1].title()} "{item["name"]}" created.',
    item=item,
  )


@router.post("/admin/taxonomies/{kind}/{item_id}", response_model=TaxonomyActionResponse)
def admin_update_taxonomy(
  kind: str,
  item_id: int,
  payload: TaxonomyUpsertRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> TaxonomyActionResponse:
  kind = validate_taxonomy_kind(kind)
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for taxonomy management.")
  item = persistence.update_taxonomy_item(db, kind, item_id, payload.model_dump())
  if item is None:
    raise HTTPException(status_code=404, detail="Taxonomy item not found.")
  return TaxonomyActionResponse(
    message=f'{kind[:-1].title()} "{item["name"]}" updated.',
    item=item,
  )


@router.delete("/admin/taxonomies/{kind}/{item_id}", response_model=TaxonomyActionResponse)
def admin_delete_taxonomy(
  kind: str,
  item_id: int,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> TaxonomyActionResponse:
  kind = validate_taxonomy_kind(kind)
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for taxonomy management.")
  item = persistence.delete_taxonomy_item(db, kind, item_id)
  if item is None:
    raise HTTPException(status_code=404, detail="Taxonomy item not found.")
  return TaxonomyActionResponse(
    message=f'{kind[:-1].title()} "{item["name"]}" deleted.',
    item=item,
  )


@router.get("/admin/movies", response_model=AdminMovieListResponse)
def admin_movies(
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieListResponse:
  items = persistence.list_movies(db, include_archived=True, prefer_pending=True) if db else demo_store.list_movies(include_archived=True, prefer_pending=True)
  return AdminMovieListResponse(items=_sanitize_movie_payloads(items))


@router.post("/admin/movies", response_model=AdminMovieActionResponse)
def admin_create_movie(
  payload: AdminMovieCreateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  slug_base = payload.title.lower().replace("&", "and")
  movie_id = "-".join(filter(None, ["".join(character if character.isalnum() else "-" for character in slug_base).strip("-"), "admin"]))
  total_movies = len(persistence.list_movies(db, include_archived=True) if db else demo_store.list_movies(include_archived=True))
  movie_payload = {
    "id": f"{movie_id}-{total_movies + 1}",
    "stage": payload.stage,
    "title_category": payload.title_category,
    "title": payload.title,
    "title_caption": payload.title_caption,
    "poster": None,
    "genre": payload.genre,
    "cast_credits": [item.model_dump() for item in payload.cast_credits],
    "stars_required": payload.stars_required,
    "stars_required_theatre": payload.stars_required_theatre,
    "expected_stars": payload.expected_stars,
    "stage_label": "Upcoming" if payload.stage == "upcoming" else "New Release" if payload.stage == "released" else "Old Movies",
    "countdown": "Release date to be confirmed" if payload.stage == "upcoming" else "Now showing" if payload.stage == "released" else "Library title",
    "release_date": payload.release_date or "TBA",
    "description": payload.story_line,
    "budget": "TBD",
    "expected_revenue": f"{payload.expected_stars} stars",
    "wish_count": 0,
    "reserve_count": 0,
    "revenue": "$0K",
    "posters": "Poster upload pending",
    "music": "Music upload pending",
    "reward_bonus": "+0 pts",
  }
  movie = persistence.create_movie(db, movie_payload) if db else demo_store.create_movie(movie_payload)
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" created in {movie["stage_label"]} and sent for Super Admin approval.',
  )


@router.post("/admin/movies/{movie_id}/publish", response_model=AdminMovieActionResponse)
def admin_publish_movie(
  movie_id: str,
  payload: PublishMovieRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  try:
    movie = persistence.publish_movie(db, movie_id, payload.release_date) if db else demo_store.publish_movie(movie_id, payload.release_date)
  except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" published with release date {movie["release_date"]}.',
  )


@router.post("/admin/movies/{movie_id}/release-main-content", response_model=AdminMovieActionResponse)
def admin_release_movie_main_content(
  movie_id: str,
  payload: ReleaseMainContentRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  release_date_time = payload.release_date_time.strip()
  if not release_date_time:
    raise HTTPException(status_code=400, detail="Choose a future release date and time.")
  parsed_release_date = parse_app_datetime(release_date_time)
  if parsed_release_date is None:
    raise HTTPException(status_code=400, detail="Choose a valid release date and time.")
  if parsed_release_date <= app_now():
    raise HTTPException(status_code=400, detail="Release date and time must be in the future.")

  movie = persistence.release_movie_main_content(db, movie_id, release_date_time, payload.release_passcode) if db else demo_store.release_movie_main_content(movie_id, release_date_time, payload.release_passcode)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'Main content release scheduled for "{movie["title"]}" at {release_date_time}.',
  )


@router.post("/admin/movies/{movie_id}/reserve-start", response_model=AdminMovieActionResponse)
def admin_start_movie_reserve(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  try:
    movie = persistence.start_movie_reserve(db, movie_id) if db else demo_store.start_movie_reserve(movie_id)
  except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  reserve_enabled = bool(movie.get("reserve_enabled"))
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=(f'Reserve Now started for "{movie["title"]}".' if reserve_enabled else f'Reserve Now stopped for "{movie["title"]}".'),
  )


@router.post("/admin/movies/{movie_id}/assets/posters", response_model=AdminMovieActionResponse)
async def admin_upload_movie_posters(
  movie_id: str,
  files: list[UploadFile] = File(...),
  orientations: list[str] = Form(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  if len(files) != len(orientations):
    raise HTTPException(status_code=400, detail="Each poster file must include an orientation.")
  if db:
    persistence.prime_movie_asset_change(db, movie_id)

  saved_vertical: list[str] = []
  saved_horizontal: list[str] = []
  for file, orientation in zip(files, orientations, strict=False):
    normalized_orientation = "horizontal" if orientation == "horizontal" else "vertical"
    variant_code = "H" if normalized_orientation == "horizontal" else "V"
    filename = _build_asset_filename(movie_id, "PSTR", file, variant=variant_code)
    relative_path = Path("media") / "library" / movie_id / "posters" / normalized_orientation / filename
    await _save_upload_file(LIBRARY_MEDIA_ROOT.parent / relative_path.relative_to("media"), file)
    if normalized_orientation == "vertical":
      saved_vertical.append(relative_path.as_posix())
    else:
      saved_horizontal.append(relative_path.as_posix())

  primary_poster = saved_vertical[0] if saved_vertical else saved_horizontal[0] if saved_horizontal else None
  poster_count_label = f"{len(saved_vertical) + len(saved_horizontal)} poster uploads"
  movie = persistence.update_movie_poster_assets(db, movie_id, primary_poster, poster_count_label) if db else demo_store.update_movie_poster_assets(movie_id, primary_poster, poster_count_label)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'Poster upload saved for "{movie["title"]}". Vertical: {len(saved_vertical)}, Horizontal: {len(saved_horizontal)}. Sent for Super Admin approval.',
  )


@router.get("/admin/movies/{movie_id}/assets/posters", response_model=MediaAssetListResponse)
def admin_list_movie_posters(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> MediaAssetListResponse:
  _get_movie_or_404(db, movie_id)
  return MediaAssetListResponse(items=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "posters")])


@router.post("/admin/movies/{movie_id}/assets/trailer", response_model=AdminMovieActionResponse)
async def admin_upload_movie_trailer(
  movie_id: str,
  file: UploadFile = File(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  if db:
    persistence.prime_movie_asset_change(db, movie_id)
  filename = _build_asset_filename(movie_id, "TRLR", file)
  target_path = LIBRARY_MEDIA_ROOT / movie_id / "trailers" / filename
  await _save_upload_file(target_path, file)
  matched = persistence.register_movie_asset_change(db, movie_id, "trailer") if db else demo_store.register_movie_asset_change(movie_id, "trailer")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=f'Trailer uploaded for "{matched["title"]}" and sent for Super Admin approval.',
  )


@router.get("/admin/movies/{movie_id}/assets/trailer", response_model=MediaAssetListResponse)
def admin_list_movie_trailers(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> MediaAssetListResponse:
  _get_movie_or_404(db, movie_id)
  return MediaAssetListResponse(items=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "trailer")])


@router.post("/admin/movies/{movie_id}/assets/content/{quality_code}", response_model=AdminMovieActionResponse)
async def admin_upload_movie_content_quality(
  movie_id: str,
  quality_code: str,
  file: UploadFile = File(...),
  password: str = Form(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = _get_movie_or_404(db, movie_id)
  quality_option, quality_entry, chunk_count = await _store_content_quality_upload(movie, quality_code, file, password)

  if db:
    schedule_movie = persistence.update_movie_content_delivery_start(db, movie_id, None)
  else:
    schedule_movie = demo_store.update_movie_content_delivery_start(movie_id, None)
  if schedule_movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  matched = persistence.register_movie_asset_change(db, movie_id, "content") if db else demo_store.register_movie_asset_change(movie_id, "content")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=(
      f'{quality_option["quality_label"]} content uploaded for "{matched["title"]}" '
      f'with {chunk_count} encrypted chunk file{"s" if chunk_count != 1 else ""}. '
      "Upload future start time was reset."
    ),
  )


@router.post("/admin/movies/{movie_id}/assets/content", response_model=AdminMovieActionResponse)
def admin_schedule_movie_content(
  movie_id: str,
  upload_start_at: str = Form(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = _get_movie_or_404(db, movie_id)
  manifest = _load_content_manifest(movie)
  if not _content_is_complete(movie, manifest):
    raise HTTPException(status_code=400, detail="Upload every required title quality before scheduling the future start time.")

  delivery_start_at = _normalize_datetime_local(upload_start_at)
  if db:
    schedule_movie = persistence.update_movie_content_delivery_start(db, movie_id, delivery_start_at)
  else:
    schedule_movie = demo_store.update_movie_content_delivery_start(movie_id, delivery_start_at)
  if schedule_movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  manifest["delivery_start_at"] = delivery_start_at
  manifest["upload_start_at"] = delivery_start_at
  manifest["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
  _write_content_manifest(movie_id, manifest)

  matched = persistence.register_movie_asset_change(db, movie_id, "content") if db else demo_store.register_movie_asset_change(movie_id, "content")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=f'Future start time saved for "{matched["title"]}" at {delivery_start_at}.',
  )


@router.get("/admin/movies/{movie_id}/assets/content", response_model=ContentQualityListResponse)
def admin_list_movie_content(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> ContentQualityListResponse:
  movie = _get_movie_or_404(db, movie_id)
  manifest = _load_content_manifest(movie)
  items = _content_quality_statuses(movie, manifest)
  return ContentQualityListResponse(items=items, is_complete=_content_is_complete(movie, manifest))


@router.get("/movies/{movie_id}/content/download")
def download_movie_content(
  movie_id: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> FileResponse:
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"]) if db else demo_store.list_movies(include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  if _delivery_entitlement_status(movie) not in {"blocked", "fulfilled"}:
    raise HTTPException(status_code=403, detail="Buy this title first to download its content package.")
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  if not _download_is_available(movie, manifest):
    raise HTTPException(status_code=403, detail="Downloads are not available yet.")

  content_root = _content_folder_path(movie_id)
  chunk_files = sorted([
    file_path
    for file_path in content_root.rglob("*")
    if file_path.is_file() and file_path.name != "manifest.json"
  ]) if content_root.exists() else []
  if not chunk_files:
    raise HTTPException(status_code=404, detail="No encrypted content chunks were found.")

  download_name = f"{_safe_name(movie['title'])}-content.zip"
  with NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
    temp_zip_path = Path(tmp_file.name)

  try:
    with zipfile.ZipFile(temp_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
      for file_path in chunk_files:
        zip_file.write(file_path, arcname=file_path.name)
    return FileResponse(
      path=temp_zip_path,
      filename=download_name,
      media_type="application/zip",
      headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
        "Expires": "0",
      },
      background=BackgroundTask(temp_zip_path.unlink, missing_ok=True),
    )
  except Exception:
    temp_zip_path.unlink(missing_ok=True)
    raise


@router.get("/movies/{movie_id}/content/manifest")
def get_movie_content_manifest(
  movie_id: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> dict:
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"]) if db else demo_store.list_movies(include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  if _delivery_entitlement_status(movie) not in {"blocked", "fulfilled"}:
    raise HTTPException(status_code=403, detail="This title is not in your collection.")

  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  if not _download_is_available(movie, manifest):
    raise HTTPException(status_code=403, detail="Content download is not available yet.")

  return _viewer_content_manifest_payload(manifest)


@router.get("/movies/{movie_id}/delivery/status", response_model=DeliveryStatusResponse)
def get_movie_delivery_status(
  movie_id: str,
  quality_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryStatusResponse:
  normalized_quality_code = _normalize_quality_code(quality_code)
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"]) if db else demo_store.list_movies(include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  if db is None:
    return _serialize_delivery_status(movie, None)
  reservation = _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)

  enrollment = None
  queue_position = None
  enrollment = (
    db.query(ContentDeliveryEnrollmentRecord)
    .filter(
      ContentDeliveryEnrollmentRecord.movie_id == movie_id,
      ContentDeliveryEnrollmentRecord.user_id == current_user["id"],
      ContentDeliveryEnrollmentRecord.quality_code == normalized_quality_code,
    )
    .first()
  )
  if enrollment is not None and enrollment.status == "queued":
    queue_position = _queue_position_for_enrollment(db, movie_id, enrollment)
  return _serialize_delivery_status(movie, enrollment, queue_position, reservation)


@router.get("/admin/movies/{movie_id}/delivery-queue", response_model=DeliveryQueueListResponse)
def admin_movie_delivery_queue(
  movie_id: str,
  page: int = 1,
  page_size: int = 50,
  status: str | None = None,
  search: str | None = None,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> DeliveryQueueListResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for delivery queue control.")

  movie = _get_movie_or_404(db, movie_id)
  sanitized_page = max(1, page)
  sanitized_page_size = max(1, min(100, page_size))
  status_filter = str(status or "").strip().lower()
  search_term = str(search or "").strip().lower()

  query = db.query(ContentDeliveryEnrollmentRecord).filter(ContentDeliveryEnrollmentRecord.movie_id == movie_id)
  if status_filter and status_filter != "all":
    query = query.filter(ContentDeliveryEnrollmentRecord.status == status_filter)
  if search_term:
    like_term = f"%{search_term}%"
    query = query.join(UserRecord, UserRecord.id == ContentDeliveryEnrollmentRecord.user_id).filter(
      or_(
        func.lower(UserRecord.name).like(like_term),
        func.lower(UserRecord.email).like(like_term),
        func.lower(ContentDeliveryEnrollmentRecord.device_label).like(like_term),
      )
    )

  total = query.count()
  fifo_positions: dict[int, int] = {}
  fifo_rows = (
    db.query(ContentDeliveryEnrollmentRecord.id)
    .filter(ContentDeliveryEnrollmentRecord.movie_id == movie_id)
    .order_by(ContentDeliveryEnrollmentRecord.accepted_at.asc(), ContentDeliveryEnrollmentRecord.id.asc())
    .all()
  )
  for index, fifo_row in enumerate(fifo_rows, start=1):
    fifo_positions[fifo_row.id] = index

  ordered_rows = (
    query
    .order_by(ContentDeliveryEnrollmentRecord.accepted_at.asc(), ContentDeliveryEnrollmentRecord.id.asc())
    .offset((sanitized_page - 1) * sanitized_page_size)
    .limit(sanitized_page_size)
    .all()
  )

  all_status_counts = dict(
    db.query(ContentDeliveryEnrollmentRecord.status, func.count(ContentDeliveryEnrollmentRecord.id))
    .filter(ContentDeliveryEnrollmentRecord.movie_id == movie_id)
    .group_by(ContentDeliveryEnrollmentRecord.status)
    .all()
  )
  summary = {
    "accepted": int(all_status_counts.get("accepted", 0) or 0),
    "queued": int(all_status_counts.get("queued", 0) or 0),
    "slot_granted": int(all_status_counts.get("slot_granted", 0) or 0),
    "downloading": int(all_status_counts.get("downloading", 0) or 0),
    "downloaded": int(all_status_counts.get("downloaded", 0) or 0),
    "failed": int(all_status_counts.get("failed", 0) or 0),
  }

  queued_positions: dict[int, int] = {}
  queued_rows = (
    db.query(ContentDeliveryEnrollmentRecord)
    .filter(
      ContentDeliveryEnrollmentRecord.movie_id == movie_id,
      ContentDeliveryEnrollmentRecord.status == "queued",
    )
    .order_by(ContentDeliveryEnrollmentRecord.accepted_at.asc(), ContentDeliveryEnrollmentRecord.id.asc())
    .all()
  )
  for index, queued_row in enumerate(queued_rows, start=1):
    queued_positions[queued_row.id] = index

  linked_title = db.query(TitleRecord).filter(TitleRecord.legacy_movie_id == movie_id).first()
  reservation_lookup: dict[tuple[str, str], ReservationRecord] = {}
  if linked_title is not None and ordered_rows:
    user_ids = [row.user_id for row in ordered_rows]
    quality_codes = [row.quality_code for row in ordered_rows]
    reservations = (
      db.query(ReservationRecord)
      .filter(
        ReservationRecord.title_id == linked_title.id,
        ReservationRecord.user_id.in_(user_ids),
        ReservationRecord.quality_code.in_(quality_codes),
        ReservationRecord.status.in_(["blocked", "fulfilled"]),
        ReservationRecord.reservation_kind == "online",
      )
      .order_by(ReservationRecord.created_at.asc(), ReservationRecord.id.asc())
      .all()
    )
    for reservation in reservations:
      reservation_lookup[(reservation.user_id, str(reservation.quality_code or "").strip().lower())] = reservation

  user_lookup = {
    user.id: user
    for user in db.query(UserRecord).filter(UserRecord.id.in_([row.user_id for row in ordered_rows])).all()
  }

  return DeliveryQueueListResponse(
    movie_id=movie_id,
    movie_title=movie["title"],
    total=total,
    page=sanitized_page,
    page_size=sanitized_page_size,
    summary=DeliveryQueueSummaryResponse(**summary),
    items=[
      DeliveryQueueItemResponse(**_serialize_delivery_queue_item(
        movie,
        row,
        user_lookup.get(row.user_id).name if user_lookup.get(row.user_id) else "Unknown user",
        user_lookup.get(row.user_id).email if user_lookup.get(row.user_id) else "unknown@example.com",
        reservation_lookup.get((row.user_id, row.quality_code)),
        fifo_positions.get(row.id),
        queued_positions.get(row.id),
      ))
      for row in ordered_rows
    ],
  )


@router.post("/movies/{movie_id}/delivery/preferences", response_model=DeliveryStatusResponse)
def save_movie_delivery_preferences(
  movie_id: str,
  payload: DeliveryPreferenceRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryStatusResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery enrollment.")
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  reservation = _require_delivery_reservation(db, movie_id, current_user["id"], payload.quality_code)

  enrollment = _get_or_create_delivery_enrollment(db, movie_id, current_user["id"], reservation.quality_code or payload.quality_code)
  enrollment.wifi_only = payload.wifi_only
  enrollment.charging_only = payload.charging_only
  enrollment.auto_download = payload.auto_download
  enrollment.device_label = payload.device_label.strip() if payload.device_label else None
  enrollment.status = "accepted"
  enrollment.last_error = None
  enrollment.updated_at = datetime.utcnow()
  db.commit()
  db.refresh(enrollment)
  return _serialize_delivery_status(movie, enrollment, reservation=reservation)


@router.post("/movies/{movie_id}/delivery/slot", response_model=DeliverySlotResponse)
def acquire_movie_delivery_slot(
  movie_id: str,
  payload: DeliverySlotAcquireRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliverySlotResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery queue control.")
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  reservation = _require_delivery_reservation(db, movie_id, current_user["id"], payload.quality_code)
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  _require_manifest_quality(manifest, reservation.quality_code or payload.quality_code)
  if not _download_is_available(movie, manifest):
    raise HTTPException(status_code=403, detail="Content download is not available yet.")

  enrollment = _get_or_create_delivery_enrollment(db, movie_id, current_user["id"], reservation.quality_code or payload.quality_code)
  enrollment.device_label = payload.device_label.strip() if payload.device_label else enrollment.device_label
  now = datetime.utcnow()
  if enrollment.slot_token and enrollment.slot_expires_at and enrollment.slot_expires_at > now and enrollment.status in {"slot_granted", "downloading"}:
    enrollment.updated_at = now
    db.commit()
    return DeliverySlotResponse(
      movie_id=movie_id,
      quality_code=enrollment.quality_code,
      status="slot_granted",
      slot_token=enrollment.slot_token,
      slot_expires_at=enrollment.slot_expires_at.isoformat(timespec="minutes"),
      manifest_ready=True,
    )

  active_count = _active_delivery_slots_query(db, movie_id).count()
  if active_count < DELIVERY_MAX_ACTIVE_SLOTS_PER_MOVIE:
    expires_at = now + timedelta(minutes=DELIVERY_SLOT_TTL_MINUTES)
    enrollment.slot_token = secrets.token_urlsafe(24)
    enrollment.slot_expires_at = expires_at
    enrollment.status = "slot_granted"
    enrollment.download_started_at = enrollment.download_started_at or now
    enrollment.updated_at = now
    db.commit()
    db.refresh(enrollment)
    return DeliverySlotResponse(
      movie_id=movie_id,
      quality_code=enrollment.quality_code,
      status="slot_granted",
      slot_token=enrollment.slot_token,
      slot_expires_at=enrollment.slot_expires_at.isoformat(timespec="minutes"),
      manifest_ready=True,
    )

  enrollment.status = "queued"
  enrollment.updated_at = now
  enrollment.slot_token = None
  enrollment.slot_expires_at = None
  db.commit()
  db.refresh(enrollment)
  queue_position = _queue_position_for_enrollment(db, movie_id, enrollment)
  return DeliverySlotResponse(
    movie_id=movie_id,
    quality_code=enrollment.quality_code,
    status="queued",
    queue_position=queue_position,
    retry_after_seconds=_recommended_delivery_retry_seconds(queue_position),
    manifest_ready=False,
  )


@router.post("/movies/{movie_id}/delivery/slot/heartbeat", response_model=DeliverySlotResponse)
def heartbeat_movie_delivery_slot(
  movie_id: str,
  payload: DeliverySlotHeartbeatRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliverySlotResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery queue control.")
  enrollment = _require_valid_slot(db, movie_id, current_user["id"], payload.slot_token)
  enrollment.slot_expires_at = datetime.utcnow() + timedelta(minutes=DELIVERY_SLOT_TTL_MINUTES)
  enrollment.status = "downloading"
  enrollment.updated_at = datetime.utcnow()
  db.commit()
  db.refresh(enrollment)
  return DeliverySlotResponse(
    movie_id=movie_id,
    quality_code=enrollment.quality_code,
    status="downloading",
    slot_token=enrollment.slot_token,
    slot_expires_at=enrollment.slot_expires_at.isoformat(timespec="minutes"),
    manifest_ready=True,
  )


@router.get("/movies/{movie_id}/delivery/manifest", response_model=DeliveryManifestResponse)
def get_movie_delivery_manifest(
  movie_id: str,
  slot_token: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryManifestResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery queue control.")
  enrollment = _require_valid_slot(db, movie_id, current_user["id"], slot_token)
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  _require_manifest_quality(manifest, enrollment.quality_code)
  return DeliveryManifestResponse(**_viewer_content_manifest_payload(manifest, enrollment.quality_code))


@router.get("/movies/{movie_id}/delivery/chunks/{chunk_name}")
def download_movie_delivery_chunk(
  movie_id: str,
  chunk_name: str,
  slot_token: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> FileResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery queue control.")
  enrollment = _require_valid_slot(db, movie_id, current_user["id"], slot_token)
  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  allowed_chunk_names = {
    str(item.get("name") or "")
    for item in manifest.get("files", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) == enrollment.quality_code
  }
  if safe_name not in allowed_chunk_names:
    raise HTTPException(status_code=403, detail="This chunk does not belong to the reserved title quality.")
  content_root = _content_folder_path(movie_id)
  target_path = next((file_path for file_path in content_root.rglob(safe_name) if file_path.is_file()), None) if content_root.exists() else None
  if target_path is None or not target_path.is_file():
    raise HTTPException(status_code=404, detail="Encrypted chunk not found.")
  return FileResponse(target_path, filename=safe_name, media_type="application/octet-stream")


@router.post("/movies/{movie_id}/delivery/complete", response_model=DeliveryStatusResponse)
def complete_movie_delivery_download(
  movie_id: str,
  payload: DeliveryDownloadCompleteRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryStatusResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery queue control.")
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  reservation = _require_delivery_reservation(db, movie_id, current_user["id"], payload.quality_code)
  enrollment = _get_or_create_delivery_enrollment(db, movie_id, current_user["id"], reservation.quality_code or payload.quality_code)
  enrollment.status = "downloaded"
  enrollment.local_encrypted_path = payload.local_encrypted_path.strip() if payload.local_encrypted_path else enrollment.local_encrypted_path
  enrollment.download_completed_at = datetime.utcnow()
  enrollment.slot_token = None
  enrollment.slot_expires_at = None
  enrollment.updated_at = datetime.utcnow()
  db.commit()
  db.refresh(enrollment)
  return _serialize_delivery_status(movie, enrollment, reservation=reservation)


@router.get("/movies/{movie_id}/delivery/unlock", response_model=DeliveryStatusResponse)
def get_movie_delivery_unlock_status(
  movie_id: str,
  quality_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryStatusResponse:
  normalized_quality_code = _normalize_quality_code(quality_code)
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"]) if db else demo_store.list_movies(include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  reservation = _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code) if db is not None else None
  enrollment = None
  if db is not None:
    enrollment = (
      db.query(ContentDeliveryEnrollmentRecord)
      .filter(
        ContentDeliveryEnrollmentRecord.movie_id == movie_id,
        ContentDeliveryEnrollmentRecord.user_id == current_user["id"],
        ContentDeliveryEnrollmentRecord.quality_code == normalized_quality_code,
      )
      .first()
    )
  return _serialize_delivery_status(movie, enrollment, reservation=reservation)


@router.delete("/admin/movies/{movie_id}/assets/content-folder")
def admin_delete_movie_content_folder(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  movie = _get_movie_or_404(db, movie_id)
  _delete_movie_content_folder(movie_id)
  if db:
    persistence.clear_movie_content_release_state(db, movie_id)
  else:
    demo_store.clear_movie_content_release_state(movie_id)
  return {"message": f'Content chunk folder deleted for "{movie["title"]}".'}


@router.delete("/admin/movies/{movie_id}/assets/content/{quality_code}", response_model=AdminMovieActionResponse)
def admin_delete_movie_content_quality(
  movie_id: str,
  quality_code: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  movie = _get_movie_or_404(db, movie_id)
  manifest = _load_content_manifest(movie)
  normalized_quality_code = _normalize_quality_code(quality_code)
  quality_lookup = _content_quality_lookup(manifest)
  quality_entry = quality_lookup.get(normalized_quality_code)
  if quality_entry is None:
    raise HTTPException(status_code=404, detail="Title quality content not found.")

  _delete_quality_files(movie_id, manifest, normalized_quality_code)
  if db:
    schedule_movie = persistence.update_movie_content_delivery_start(db, movie_id, None)
  else:
    schedule_movie = demo_store.update_movie_content_delivery_start(movie_id, None)
  if schedule_movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  if manifest.get("qualities"):
    _write_content_manifest(movie_id, manifest)

  matched = persistence.register_movie_asset_change(db, movie_id, "content") if db else demo_store.register_movie_asset_change(movie_id, "content")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=(
      f'{quality_entry.get("quality_label") or normalized_quality_code} content deleted for "{matched["title"]}". '
      "Upload future start time was reset."
    ),
  )


@router.post("/admin/movies/{movie_id}/assets/gallery", response_model=AdminMovieActionResponse)
async def admin_upload_movie_gallery(
  movie_id: str,
  file: UploadFile = File(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  if db:
    persistence.prime_movie_asset_change(db, movie_id)
  filename = _build_asset_filename(movie_id, "GLLR", file)
  target_path = LIBRARY_MEDIA_ROOT / movie_id / "gallery" / filename
  await _save_upload_file(target_path, file)
  matched = persistence.register_movie_asset_change(db, movie_id, "gallery") if db else demo_store.register_movie_asset_change(movie_id, "gallery")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=f'Gallery uploaded for "{matched["title"]}" and sent for Super Admin approval.',
  )


@router.get("/admin/movies/{movie_id}/assets/gallery", response_model=MediaAssetListResponse)
def admin_list_movie_gallery(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> MediaAssetListResponse:
  _get_movie_or_404(db, movie_id)
  return MediaAssetListResponse(items=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "gallery")])


@router.post("/admin/movies/{movie_id}/assets/music", response_model=AdminMovieActionResponse)
async def admin_upload_movie_music(
  movie_id: str,
  file: UploadFile = File(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  if db:
    persistence.prime_movie_asset_change(db, movie_id)
  filename = _build_asset_filename(movie_id, "MUSC", file)
  target_path = LIBRARY_MEDIA_ROOT / movie_id / "music" / filename
  await _save_upload_file(target_path, file)
  matched = persistence.register_movie_asset_change(db, movie_id, "music") if db else demo_store.register_movie_asset_change(movie_id, "music")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=f'Music uploaded for "{matched["title"]}" and sent for Super Admin approval.',
  )


@router.get("/admin/movies/{movie_id}/assets/music", response_model=MediaAssetListResponse)
def admin_list_movie_music(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> MediaAssetListResponse:
  _get_movie_or_404(db, movie_id)
  return MediaAssetListResponse(items=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "music")])


@router.delete("/admin/movies/{movie_id}/assets/{kind}/{asset_name}")
def admin_delete_movie_asset(
  movie_id: str,
  kind: str,
  asset_name: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  movie = _get_movie_or_404(db, movie_id)
  if db:
    persistence.prime_movie_asset_change(db, movie_id)
  _delete_media_asset(movie_id, kind, asset_name)
  if db:
    if kind == "posters":
      primary_poster, poster_count_label = _poster_asset_summary(movie_id)
      persistence.update_movie_poster_assets(db, movie_id, primary_poster, poster_count_label)
    else:
      persistence.register_movie_asset_change(db, movie_id, kind)
  else:
    if kind == "posters":
      primary_poster, poster_count_label = _poster_asset_summary(movie_id)
      demo_store.update_movie_poster_assets(movie_id, primary_poster, poster_count_label)
    else:
      demo_store.register_movie_asset_change(movie_id, kind)
  return {"message": f'{kind.title()} asset deleted for "{movie["title"]}" and sent for Super Admin approval.'}


@router.post("/admin/feature-stage", response_model=AdminActionResponse)
def admin_feature_stage(
  payload: StageUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminActionResponse:
  summary = persistence.set_featured_stage(db, payload.stage) if db else demo_store.set_featured_stage(payload.stage)
  return AdminActionResponse(
    message=f'{payload.stage.title()} is now the featured viewer entry section.',
    summary=AdminSummaryResponse(**summary),
  )


@router.post("/admin/reward-campaign/boost", response_model=AdminActionResponse)
def admin_reward_campaign_boost(
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminActionResponse:
  summary = persistence.boost_reward_campaign(db) if db else demo_store.boost_reward_campaign()
  return AdminActionResponse(
    message="Reward campaign boost recorded.",
    summary=AdminSummaryResponse(**summary),
  )


@router.post("/admin/review-queue/{queue_id}/status", response_model=QueueItemUpdateResponse)
def admin_update_review_queue_status(
  queue_id: str,
  payload: QueueStatusUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> QueueItemUpdateResponse:
  item = persistence.update_queue_item_status(db, queue_id, payload.status) if db else demo_store.update_queue_item_status(queue_id, payload.status)
  if item is None:
    raise HTTPException(status_code=404, detail="Queue item not found.")

  return QueueItemUpdateResponse(
    item=item,
    message=f'Queue item "{item["title"]}" updated to {item["status"]}.',
  )


@router.post("/admin/movies/{movie_id}/stage", response_model=AdminMovieActionResponse)
def admin_update_movie_stage(
  movie_id: str,
  payload: StageUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = persistence.update_movie_stage(db, movie_id, payload.stage) if db else demo_store.update_movie_stage(movie_id, payload.stage)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" moved to {movie["stage_label"]} and sent for Super Admin approval.',
  )


@router.post("/admin/movies/{movie_id}/details", response_model=AdminMovieActionResponse)
def admin_update_movie_details(
  movie_id: str,
  payload: AdminMovieUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = persistence.update_movie_details(db, movie_id, payload.model_dump()) if db else demo_store.update_movie_details(movie_id, payload.model_dump())
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" details updated and sent for Super Admin approval.',
  )


@router.post("/admin/movies/{movie_id}/pricing-config", response_model=AdminMovieActionResponse)
def admin_update_movie_pricing_config(
  movie_id: str,
  payload: AdminMoviePricingConfigRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = (
    persistence.update_movie_pricing_config(db, movie_id, payload.model_dump())
    if db
    else demo_store.update_movie_pricing_config(movie_id, payload.model_dump())
  )
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'Pricing and target setup updated for "{movie["title"]}" and sent for Super Admin approval.',
  )


@router.post("/admin/movies/{movie_id}/approval", response_model=AdminMovieActionResponse)
def admin_review_movie_approval(
  movie_id: str,
  payload: ApprovalUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = persistence.review_movie_approval(db, movie_id, payload.action) if db else demo_store.review_movie_approval(movie_id, payload.action)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  message = (
    f'"{movie["title"]}" approved for viewer publishing.'
    if payload.action == "approve"
    else f'Changes requested for "{movie["title"]}".'
  )
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=message,
  )


@router.get("/admin/movies/{movie_id}/approval-review", response_model=ApprovalReviewResponse)
def admin_movie_approval_review(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> ApprovalReviewResponse:
  review = persistence.get_movie_approval_review(db, movie_id) if db else demo_store.get_movie_approval_review(movie_id)
  if review is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  review["item"] = _sanitize_movie_payload(review["item"])
  if review.get("current_item"):
    review["current_item"] = _sanitize_movie_payload(review["current_item"])
  if review.get("pending_item"):
    review["pending_item"] = _sanitize_movie_payload(review["pending_item"])
  return ApprovalReviewResponse(**review)


@router.post("/admin/movies/{movie_id}/archive", response_model=AdminMovieActionResponse)
def admin_archive_movie(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = persistence.archive_movie(db, movie_id) if db else demo_store.archive_movie(movie_id)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" archived from the viewer catalog. Any blocked stars for this title were refunded first.',
  )


@router.post("/admin/movies/{movie_id}/restore", response_model=AdminMovieActionResponse)
def admin_restore_movie(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = persistence.restore_movie(db, movie_id) if db else demo_store.restore_movie(movie_id)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" restored to the library list and sent for Super Admin approval.',
  )


@router.delete("/admin/movies/{movie_id}")
def admin_delete_movie(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  movie = _get_movie_or_404(db, movie_id)
  _delete_movie_media_folder(movie_id)
  deleted_movie = persistence.delete_movie_permanently(db, movie_id) if db else demo_store.delete_movie_permanently(movie_id)
  if deleted_movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  _delete_movie_media_folder(movie_id)
  return {"message": f'"{movie["title"]}" and all related media were deleted permanently.'}


@router.get("/admin/users", response_model=AdminUserListResponse)
def admin_users(
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminUserListResponse:
  items = persistence.list_users(db) if db else demo_store.list_users()
  return AdminUserListResponse(items=items)


@router.post("/admin/users", response_model=AdminUserActionResponse)
def admin_create_user(
  payload: AdminUserCreateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminUserActionResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for user management.")

  try:
    user = persistence.create_user(db, payload.model_dump())
  except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error

  return AdminUserActionResponse(
    item=user,
    message=f'{user["name"]} created with role {user["role"]}.',
  )


@router.post("/admin/users/{user_id}", response_model=AdminUserActionResponse)
def admin_update_user(
  user_id: str,
  payload: AdminUserUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminUserActionResponse:
  user = (
    persistence.update_user_access(db, user_id, payload.name, payload.role, payload.status, payload.star_balance)
    if db
    else demo_store.update_user_access(user_id, payload.name, payload.role, payload.status, payload.star_balance)
  )
  if user is None:
    raise HTTPException(status_code=404, detail="User not found.")

  return AdminUserActionResponse(
    item=user,
    message=f'{user["name"]} updated to role {user["role"]} with {user["status"]} access.',
  )


@router.delete("/admin/users/{user_id}", response_model=AdminUserActionResponse)
def admin_delete_user(
  user_id: str,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] = Depends(require_admin),
) -> AdminUserActionResponse:
  if current_user["id"] == user_id:
    raise HTTPException(status_code=400, detail="You cannot delete your own account from this screen.")

  all_users = persistence.list_users(db) if db else demo_store.list_users()
  target = next((item for item in all_users if item["id"] == user_id), None)
  if target is not None and target["role"] == "super_admin":
    raise HTTPException(status_code=400, detail="Super Admin accounts cannot be deleted from this screen.")

  user = persistence.delete_user(db, user_id) if db else demo_store.delete_user(user_id)
  if user is None:
    raise HTTPException(status_code=404, detail="User not found.")

  session_auth.revoke_user_sessions(user_id)

  return AdminUserActionResponse(
    item=user,
    message=f'{user["name"]} has been deleted permanently.',
  )
