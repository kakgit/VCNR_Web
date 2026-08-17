from __future__ import annotations

from base64 import b64encode
from pathlib import Path
import hashlib
import json
import os
import re
import secrets
import shutil
import site
import sys
import time
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile, TemporaryDirectory
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
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
from backend.core.push import build_push_message, is_expo_push_token, send_push_messages_async
from backend.core.storage import (
  chunk_exists,
  chunk_public_url,
  chunk_webseed_base,
  delete_chunk,
  delete_media_object,
  delete_media_prefix,
  delete_movie_prefix,
  download_media_object,
  list_media_keys,
  media_download_url,
  media_object_exists,
  media_object_key,
  media_public_url,
  presign_media_download,
  presign_media_upload,
  r2_enabled,
  upload_media_object,
)
from backend.core.time_utils import app_now, is_app_time_reached, parse_app_datetime
from backend import persistence
from backend.data import demo_store
from backend.db import get_db
from backend.models import ContentDeliveryEnrollmentRecord, ReservationRecord, TitleRecord, UserRecord
from backend.schemas import (
  AdminActionResponse,
  AdminPushTestRequest,
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
  DeliveryTorrentResponse,
  TransferPairingCreateRequest,
  TransferPairingCreateResponse,
  TransferPairingInventoryRequest,
  TransferPairingInventoryResponse,
  TransferPairingJoinRequest,
  TransferPairingJoinResponse,
  TransferPairingManifestRequest,
  TransferPairingManifestResponse,
  TransferPairingStatusResponse,
  TransferRelayChunkUploadResponse,
  SwarmInventoryRequest,
  SwarmInventoryResponse,
  SwarmAutoSessionRequest,
  SwarmAutoSessionResponse,
  SwarmDemandCreateRequest,
  SwarmDemandEntry,
  SwarmDemandListResponse,
  SwarmDemandResponse,
  SwarmSeederAnnounceRequest,
  SwarmSeederAnnounceResponse,
  SwarmSeederAssignmentResponse,
  SwarmSeederCooldownResponse,
  SwarmSeederListResponse,
  SwarmSessionCreateRequest,
  SwarmSessionResponse,
  SwarmSourceEntry,
  SwarmSourcePublishRequest,
  SwarmSourcePublishResponse,
  SwarmSourcesResponse,
  SwarmRelayChunkUploadResponse,
  SwarmSignalActionResponse,
  SwarmSignalAnswerRequest,
  SwarmSignalCandidateRequest,
  SwarmSignalOfferRequest,
  SwarmSignalStateResponse,
  AdminMovieUpdateRequest,
  AdminMovieActionResponse,
  AdminMovieListResponse,
  CastImageLookupRequest,
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
  TeaserLinksResponse,
  TeaserLinksUpdateRequest,
  AdminUserCreateRequest,
  MovieDetailResponse,
  PushDeviceRegisterRequest,
  PushDeviceResponse,
  PushDeviceUnregisterRequest,
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
STAR_CAST_ROOT = Path(__file__).resolve().parents[2] / "media" / "star_cast"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_API_USER_AGENT = "VCNR-Admin/1.0 (https://github.com/vcnr; contact: admin@vcnr.local)"
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
TRANSFER_PAIRING_TTL_MINUTES = 10
TRANSFER_PAIRING_SESSIONS: dict[str, dict[str, str]] = {}
TRANSFER_RELAY_ROOT = LIBRARY_MEDIA_ROOT / "_transfer_relay"
SWARM_SESSION_TTL_MINUTES = 60
SWARM_SEEDER_TTL_MINUTES = 10
SWARM_DEMAND_TTL_MINUTES = 10
SWARM_SEEDER_COOLDOWN_MINUTES = 2
SWARM_SEEDER_FRESHNESS_SECONDS = 45
SWARM_SESSIONS: dict[str, dict[str, str]] = {}
SWARM_AVAILABLE_SEEDERS: dict[str, dict[str, str]] = {}
SWARM_ACTIVE_DEMANDS: dict[str, dict[str, str]] = {}
SWARM_MANIFEST_INTEGRITY_CACHE: dict[str, dict] = {}
SWARM_RELAY_ROOT = LIBRARY_MEDIA_ROOT / "_swarm_relay"
TORRENT_TEST_SEEDER_TTL_MINUTES = 10
TORRENT_TEST_SEEDERS: dict[str, dict[str, str]] = {}


def _swarm_transport_payload() -> dict[str, str]:
  config = get_settings()
  return {
    "stun_url": config.swarm_stun_url or "stun:stun.l.google.com:19302",
    "turn_url": config.swarm_turn_url or "",
    "turn_username": config.swarm_turn_username or "",
    "turn_credential": config.swarm_turn_credential or "",
  }


def _torrent_test_seeder_expiry() -> datetime:
  return datetime.utcnow() + timedelta(minutes=TORRENT_TEST_SEEDER_TTL_MINUTES)


def _cleanup_torrent_test_seeders() -> None:
  now = datetime.utcnow()
  expired_keys = [
    key
    for key, item in TORRENT_TEST_SEEDERS.items()
    if datetime.fromisoformat(str(item.get("expires_at") or now.isoformat())) <= now
  ]
  for key in expired_keys:
    TORRENT_TEST_SEEDERS.pop(key, None)


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


def _sanitize_cast_image_name(name: str) -> str:
  slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
  return slug or "person"


def _wikipedia_get_json(params: dict[str, str], timeout: float = 10.0) -> dict | None:
  query = urllib.parse.urlencode(params)
  request = urllib.request.Request(
    f"{WIKIPEDIA_API_URL}?{query}",
    headers={
      "User-Agent": WIKIPEDIA_API_USER_AGENT,
      "Accept": "application/json",
    },
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      if response.status != 200:
        return None
      return json.loads(response.read().decode("utf-8"))
  except (OSError, ValueError):
    return None


def _resolve_wikipedia_portrait(name: str) -> dict | None:
  """Resolve the celebrity name to a Wikipedia portrait thumbnail URL."""
  search = _wikipedia_get_json(
    {
      "action": "query",
      "list": "search",
      "srsearch": name,
      "srlimit": 1,
      "format": "json",
      "origin": "*",
    }
  )
  if not search:
    return None
  hits = (search.get("query") or {}).get("search") or []
  if not hits:
    return None
  title = str(hits[0].get("title") or "").strip()
  if not title:
    return None
  image = _wikipedia_get_json(
    {
      "action": "query",
      "prop": "pageimages",
      "piprop": "thumbnail",
      "pithumbsize": 300,
      "titles": title,
      "format": "json",
      "origin": "*",
    }
  )
  if not image:
    return None
  pages = (image.get("query") or {}).get("pages") or {}
  if not isinstance(pages, dict):
    return None
  for page in pages.values():
    if not isinstance(page, dict):
      continue
    thumbnail = page.get("thumbnail") or {}
    source = str(thumbnail.get("source") or "").strip()
    if source:
      return {"source": source, "title": title}
  return None


def _cast_image_extension(source_url: str) -> str:
  extension = Path(urllib.parse.urlparse(source_url).path).suffix.lower()
  if not extension.startswith(".") or len(extension) > 10:
    extension = ".jpg"
  return extension


def _download_cast_image(source_url: str, timeout: float = 30.0) -> bytes | None:
  request = urllib.request.Request(
    source_url,
    headers={"User-Agent": WIKIPEDIA_API_USER_AGENT},
  )
  try:
    with urllib.request.urlopen(request, timeout=timeout) as response:
      if response.status != 200:
        return None
      return response.read()
  except (OSError, ValueError):
    return None


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
  # R2 is the source of truth for media objects; clear the movie prefix first.
  delete_media_prefix(f"{movie_id}/")

  target_path = (LIBRARY_MEDIA_ROOT / movie_id).resolve()
  library_root = LIBRARY_MEDIA_ROOT.resolve()
  try:
    target_path.relative_to(library_root)
  except ValueError as error:
    raise HTTPException(status_code=400, detail="Invalid movie media path.") from error

  if target_path.exists():
    last_error: Exception | None = None
    for _attempt in range(3):
      try:
        shutil.rmtree(target_path)
        return
      except FileNotFoundError:
        return
      except PermissionError as error:
        last_error = error
        time.sleep(0.25)
      except OSError as error:
        last_error = error
        time.sleep(0.25)
    detail = (
      f'Unable to delete "{movie_id}" completely because one of its media files is still in use. '
      "Close any video player, torrent client, File Explorer window, or app process using that title and try again."
    )
    raise HTTPException(status_code=409, detail=detail) from last_error


def _delete_movie_content_folder(movie_id: str) -> None:
  # R2 content objects (chunks, manifest, torrents) are removed via the prefix.
  delete_media_prefix(f"{movie_id}/content/")

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


def _media_asset_payload_from_key(key: str, kind: str, orientation: str | None = None) -> dict:
  """Build a MediaAssetResponse payload from an R2 object key.

  The public URL is used when R2 is configured; otherwise the local
  relative media path is used as a fallback.
  """
  name = Path(key).name
  public_url = media_public_url(key)
  if public_url:
    return {
      "name": name,
      "path": key,
      "url": public_url,
      "kind": kind,
      "orientation": orientation,
    }
  # Fallback: derive a local media path from the R2-style key.
  relative_path = f"media/library/{key}"
  return {
    "name": name,
    "path": relative_path,
    "url": f"/{relative_path}",
    "kind": kind,
    "orientation": orientation,
  }


TEASER_LINKS_SIDECAR_NAME = "teasers.json"


def _teaser_links_sidecar_key(movie_id: str) -> str:
  return f"{movie_id}/trailers/{TEASER_LINKS_SIDECAR_NAME}"


def _read_teaser_links(movie_id: str) -> list[str]:
  """Read the saved YouTube teaser links for a movie, if any."""
  if r2_enabled():
    raw = download_media_object(_teaser_links_sidecar_key(movie_id))
    if not raw:
      return []
    try:
      parsed = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
      return []
    return [link for link in parsed if isinstance(link, str) and link.strip()] if isinstance(parsed, list) else []

  sidecar_path = LIBRARY_MEDIA_ROOT / movie_id / "trailers" / TEASER_LINKS_SIDECAR_NAME
  if not sidecar_path.exists():
    return []
  try:
    parsed = json.loads(sidecar_path.read_text(encoding="utf-8"))
  except (json.JSONDecodeError, OSError, ValueError):
    return []
  return [link for link in parsed if isinstance(link, str) and link.strip()] if isinstance(parsed, list) else []


def _save_teaser_links(movie_id: str, links: list[str]) -> None:
  """Persist the YouTube teaser link list for a movie (local + R2 sidecar)."""
  normalized_links = [str(link or "").strip() for link in links if str(link or "").strip()]
  payload = json.dumps(normalized_links, ensure_ascii=False, indent=2)
  if r2_enabled():
    upload_media_object(_teaser_links_sidecar_key(movie_id), payload.encode("utf-8"))
  folder = LIBRARY_MEDIA_ROOT / movie_id / "trailers"
  folder.mkdir(parents=True, exist_ok=True)
  (folder / TEASER_LINKS_SIDECAR_NAME).write_text(payload, encoding="utf-8")


def _normalize_teaser_link(link: str) -> str | None:
  """Validate a YouTube link and normalize it to a canonical watch URL."""
  candidate = (link or "").strip()
  if not candidate:
    return None
  video_id = None
  patterns = (
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?(?:.*[?&])?v=([A-Za-z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/live/([A-Za-z0-9_-]{11})",
  )
  for pattern in patterns:
    match = re.search(pattern, candidate)
    if match:
      video_id = match.group(1)
      break
  if not video_id:
    return None
  return f"https://www.youtube.com/watch?v={video_id}"


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

  # Cast profile photos are stored as local /media/star_cast/ paths, but that
  # folder is gitignored runtime media - it only exists on an app server while a
  # file was written there and does not survive a Render redeploy. When R2 is
  # configured, serve the images from the public R2 URL instead; if the object is
  # missing there too, null the image so the viewer falls back to its
  # initial-letter placeholder instead of a broken/blank photo.
  if r2_enabled() and isinstance(cast_credits, list):
    for entry in cast_credits:
      if not isinstance(entry, dict):
        continue
      cast_image = str(entry.get("image") or "").strip()
      if not cast_image.startswith("/media/star_cast/"):
        continue
      relative_key = cast_image.removeprefix("/media/star_cast/")
      r2_key = f"star_cast/{relative_key}" if relative_key else ""
      if r2_key and media_object_exists(r2_key):
        entry["image"] = media_public_url(r2_key) or cast_image
      else:
        entry["image"] = None

  poster_path = normalized.get("poster")
  if isinstance(poster_path, str) and poster_path.startswith(("http://", "https://")):
    # Public R2 URL: keep as-is. Without R2 configured these never occur.
    pass
  elif isinstance(poster_path, str) and poster_path.startswith("media/") and not r2_enabled():
    local_path = LIBRARY_MEDIA_ROOT.parent / Path(poster_path).relative_to("media")
    if not local_path.exists():
      normalized["poster"] = None
  elif isinstance(poster_path, str) and r2_enabled():
    # Legacy local path stored before R2 was enabled; map to the R2 key if reachable.
    relative_key = poster_path.removeprefix("media/library/")
    if relative_key and not media_object_exists(relative_key):
      normalized["poster"] = None
    elif relative_key:
      # Public R2 URL is preferred so the viewer can render the poster.
      normalized["poster"] = media_public_url(relative_key) or poster_path

  movie_id = str(normalized.get("id") or "")
  normalized["teaser_links"] = _read_teaser_links(movie_id) if movie_id else []
  return normalized


def _sanitize_movie_payloads(items: list[dict]) -> list[dict]:
  return [item for item in (_sanitize_movie_payload(movie) for movie in items) if item is not None]


def _list_media_assets(movie_id: str, kind: str) -> list[dict]:
  # R2 is the source of truth for media objects when configured.
  if r2_enabled():
    if kind == "posters":
      items: list[dict] = []
      for key in list_media_keys(f"{movie_id}/posters/"):
        parts = key.split("/")
        orientation = parts[2] if len(parts) >= 4 else None
        items.append(_media_asset_payload_from_key(key, kind, orientation))
      return items
    folder_name = "trailers" if kind == "trailer" else "gallery" if kind == "gallery" else "music" if kind == "music" else "content"
    prefix = f"{movie_id}/{folder_name}/"
    items = []
    for key in list_media_keys(prefix):
      key_name = Path(key).name
      if (kind == "content" and key_name == "manifest.json") or (kind == "trailer" and key_name == TEASER_LINKS_SIDECAR_NAME):
        continue
      items.append(_media_asset_payload_from_key(key, kind))
    return items

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
        if (kind == "content" and file_path.name == "manifest.json") or (kind == "trailer" and file_path.name == TEASER_LINKS_SIDECAR_NAME):
          continue
        items.append(_media_asset_payload(file_path, kind))

  return items


def _poster_asset_summary(movie_id: str) -> tuple[str | None, str]:
  poster_items = _list_media_assets(movie_id, "posters")
  # Prefer a public R2 URL so the viewer can render the poster directly;
  # otherwise use the relative media path for local disk storage.
  primary = next((item["url"] for item in poster_items if item.get("orientation") == "vertical"), None)
  if primary is None and poster_items:
    primary = poster_items[0]["url"]
  count_label = f"{len(poster_items)} poster upload{'s' if len(poster_items) != 1 else ''}" if poster_items else "Poster upload pending"
  return primary, count_label


def _delete_media_asset(movie_id: str, kind: str, asset_name: str) -> None:
  safe_asset_name = Path(asset_name).name
  if safe_asset_name != asset_name:
    raise HTTPException(status_code=400, detail="Invalid asset name.")

  # Remove from R2 first when configured.
  if r2_enabled():
    if kind == "posters":
      for orientation in ("vertical", "horizontal"):
        delete_media_object(media_object_key(movie_id, kind, safe_asset_name, orientation))
    else:
      delete_media_object(media_object_key(movie_id, kind, safe_asset_name))

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


def _content_torrent_path(movie_id: str, quality_code: str) -> Path:
  normalized_quality_code = _normalize_quality_code(quality_code)
  return LIBRARY_MEDIA_ROOT / movie_id / "content" / f"{normalized_quality_code}.torrent"


def _content_folder_path(movie_id: str) -> Path:
  return LIBRARY_MEDIA_ROOT / movie_id / "content"


def _quality_file_root(movie_id: str, quality_code: str) -> Path:
  return _content_folder_path(movie_id) / _normalize_quality_code(quality_code)


def _content_package_name(movie_id: str, quality_code: str) -> str:
  return f"{movie_id}-{_normalize_quality_code(quality_code)}.vcnr-pkg"


def _quality_package_root(movie_id: str, quality_code: str) -> Path:
  return _quality_file_root(movie_id, quality_code) / _content_package_name(movie_id, quality_code)


def _quality_content_manifest_path(movie_id: str, quality_code: str) -> Path:
  return _quality_file_root(movie_id, quality_code) / "manifest.json"


def _quality_content_torrent_path(movie_id: str, quality_code: str) -> Path:
  normalized_quality_code = _normalize_quality_code(quality_code)
  return _quality_file_root(movie_id, normalized_quality_code) / f"{normalized_quality_code}.torrent"


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


def _transfer_pairing_expiry() -> datetime:
  return datetime.utcnow() + timedelta(minutes=TRANSFER_PAIRING_TTL_MINUTES)


def _transfer_pairing_folder(pairing_code: str) -> Path:
  return TRANSFER_RELAY_ROOT / pairing_code.upper()


def _delete_transfer_pairing_files(pairing_code: str) -> None:
  target = _transfer_pairing_folder(pairing_code)
  if target.exists():
    shutil.rmtree(target, ignore_errors=True)


def _cleanup_transfer_pairing_sessions() -> None:
  now = datetime.utcnow()
  expired_codes = [
    code
    for code, session in TRANSFER_PAIRING_SESSIONS.items()
    if datetime.fromisoformat(session["expires_at"]) <= now
  ]
  for code in expired_codes:
    TRANSFER_PAIRING_SESSIONS.pop(code, None)
    _delete_transfer_pairing_files(code)


def _create_transfer_pairing_code() -> str:
  for _ in range(20):
    code = secrets.token_hex(3).upper()
    if code not in TRANSFER_PAIRING_SESSIONS:
      return code
  raise HTTPException(status_code=500, detail="Unable to generate a transfer pairing code right now.")


def _get_transfer_pairing_session_or_404(pairing_code: str) -> dict[str, str]:
  _cleanup_transfer_pairing_sessions()
  session = TRANSFER_PAIRING_SESSIONS.get(pairing_code.upper())
  if session is None:
    raise HTTPException(status_code=404, detail="That pairing code was not found or has expired.")
  return session


def _get_transfer_chunk_names(session: dict[str, str], key: str) -> set[str]:
  raw = session.get(key) or "[]"
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError:
    parsed = []
  return {str(item).strip() for item in parsed if str(item).strip()}


def _set_transfer_chunk_names(session: dict[str, str], key: str, chunk_names: set[str]) -> None:
  session[key] = json.dumps(sorted(chunk_names))


def _get_transfer_manifest(session: dict[str, str]) -> dict:
  if not session.get("manifest_json"):
    return {}
  try:
    manifest = json.loads(session["manifest_json"])
  except json.JSONDecodeError:
    return {}
  return manifest if isinstance(manifest, dict) else {}


def _get_transfer_expected_chunk_names(session: dict[str, str]) -> set[str]:
  manifest = _get_transfer_manifest(session)
  if not manifest:
    return set()
  chunk_lookup = _chunk_manifest_lookup(manifest, session["quality_code"])
  return set(chunk_lookup.keys())


def _serialize_transfer_status(session: dict[str, str]) -> TransferPairingStatusResponse:
  expected_chunks = _get_transfer_expected_chunk_names(session)
  sender_chunks = expected_chunks or _get_transfer_chunk_names(session, "sender_chunk_names")
  receiver_chunks = _get_transfer_chunk_names(session, "receiver_chunk_names")
  if expected_chunks:
    receiver_chunks = receiver_chunks.intersection(expected_chunks)
  relay_chunks = _get_transfer_chunk_names(session, "relay_chunk_names")
  if expected_chunks:
    relay_chunks = relay_chunks.intersection(expected_chunks)
  missing_chunks = sender_chunks.difference(receiver_chunks)
  return TransferPairingStatusResponse(
    movie_id=session["movie_id"],
    quality_code=session["quality_code"],
    pairing_code=session["pairing_code"],
    expires_at=datetime.fromisoformat(session["expires_at"]).isoformat(timespec="seconds") + "Z",
    session_status=session["session_status"],
    receiver_user_id=session["receiver_user_id"],
    sender_user_id=session.get("sender_user_id") or None,
    sender_joined=bool(session.get("sender_user_id")),
    sender_chunk_count=len(sender_chunks),
    receiver_chunk_count=len(receiver_chunks),
    missing_chunk_count=len(missing_chunks),
    relay_ready_chunk_count=len(relay_chunks),
    relay_ready_chunk_names=sorted(relay_chunks),
    manifest_available=bool(session.get("manifest_json")),
  )


def _chunk_manifest_lookup(manifest: dict, quality_code: str) -> dict[str, dict]:
  normalized_quality_code = _normalize_quality_code(quality_code)
  return {
    str(item.get("name") or ""): item
    for item in manifest.get("files", [])
    if str(item.get("name") or "").strip()
    and _normalize_quality_code(str(item.get("quality_code") or "")) == normalized_quality_code
  }


def _validate_transfer_manifest_integrity(manifest: dict, quality_code: str) -> dict[str, dict]:
  chunk_lookup = _chunk_manifest_lookup(manifest, quality_code)
  if not chunk_lookup:
    raise HTTPException(status_code=400, detail="Transfer manifest does not include encrypted chunks for this title quality.")

  invalid_names: list[str] = []
  missing_integrity_names: list[str] = []
  for name, record in chunk_lookup.items():
    if Path(name).name != name:
      invalid_names.append(name)
      continue
    expected_size = int(record.get("encrypted_size") or 0)
    expected_sha256 = str(record.get("encrypted_sha256") or "").strip().lower()
    expected_md5 = str(record.get("encrypted_md5") or "").strip().lower()
    if expected_size <= 0 or (not expected_sha256 and not expected_md5):
      missing_integrity_names.append(name)

  if invalid_names:
    raise HTTPException(status_code=400, detail="Transfer manifest contains invalid chunk names.")
  if missing_integrity_names:
    raise HTTPException(
      status_code=400,
      detail="Transfer manifest is missing chunk size/checksum data. Reopen sender after updating the app and retry.",
    )
  return chunk_lookup


def _swarm_session_expiry() -> datetime:
  return datetime.utcnow() + timedelta(minutes=SWARM_SESSION_TTL_MINUTES)


def _swarm_seeder_expiry() -> datetime:
  return datetime.utcnow() + timedelta(minutes=SWARM_SEEDER_TTL_MINUTES)


def _swarm_seeder_cooldown_expiry() -> datetime:
  return datetime.utcnow() + timedelta(minutes=SWARM_SEEDER_COOLDOWN_MINUTES)


def _swarm_demand_expiry() -> datetime:
  return datetime.utcnow() + timedelta(minutes=SWARM_DEMAND_TTL_MINUTES)


def _swarm_demand_key(movie_id: str, quality_code: str) -> str:
  return f"{movie_id}:{_normalize_quality_code(quality_code)}"


def _cleanup_swarm_sessions() -> None:
  now = datetime.utcnow()
  expired_ids = [
    session_id
    for session_id, session in SWARM_SESSIONS.items()
    if datetime.fromisoformat(session["expires_at"]) <= now
  ]
  for session_id in expired_ids:
    SWARM_SESSIONS.pop(session_id, None)
    _delete_swarm_relay_files(session_id)


def _cleanup_swarm_seeders() -> None:
  now = datetime.utcnow()
  expired_ids = [
    seeder_id
    for seeder_id, seeder in SWARM_AVAILABLE_SEEDERS.items()
    if datetime.fromisoformat(seeder["expires_at"]) <= now
  ]
  for seeder_id in expired_ids:
    SWARM_AVAILABLE_SEEDERS.pop(seeder_id, None)


def _cleanup_swarm_demands() -> None:
  now = datetime.utcnow()
  expired_ids = [
    demand_id
    for demand_id, demand in SWARM_ACTIVE_DEMANDS.items()
    if datetime.fromisoformat(demand["expires_at"]) <= now
  ]
  for demand_id in expired_ids:
    SWARM_ACTIVE_DEMANDS.pop(demand_id, None)


def _create_swarm_session_id() -> str:
  for _ in range(20):
    session_id = secrets.token_urlsafe(18)
    if session_id not in SWARM_SESSIONS:
      return session_id
  raise HTTPException(status_code=500, detail="Unable to create a swarm session right now.")


def _create_swarm_seeder_id(user_id: str, device_id: str | None) -> str:
  clean_device_id = _safe_name(device_id or "")
  if clean_device_id:
    return f"seeder:{user_id}:{clean_device_id}"
  return f"seeder:{user_id}:{secrets.token_urlsafe(8)}"


def _drop_swarm_receiver_sessions(movie_id: str, quality_code: str, user_id: str, device_label: str | None = None) -> None:
  normalized_quality_code = _normalize_quality_code(quality_code)
  normalized_label = (device_label or "").strip()
  stale_ids: list[str] = []
  for session_id, session in SWARM_SESSIONS.items():
    if session["movie_id"] != movie_id or session["quality_code"] != normalized_quality_code:
      continue
    if session.get("user_id") != user_id:
      continue
    if normalized_label and (session.get("device_label") or "").strip() != normalized_label:
      continue
    stale_ids.append(session_id)
  for session_id in stale_ids:
    SWARM_SESSIONS.pop(session_id, None)
    _delete_swarm_relay_files(session_id)
  if not stale_ids:
    return
  for seeder in SWARM_AVAILABLE_SEEDERS.values():
    if str(seeder.get("assigned_session_id") or "") in stale_ids:
      seeder["assigned_session_id"] = ""


def _get_swarm_session_or_404(session_id: str) -> dict[str, str]:
  _cleanup_swarm_sessions()
  session = SWARM_SESSIONS.get(session_id)
  if session is None:
    raise HTTPException(status_code=404, detail="That swarm session was not found or has expired.")
  return session


def _swarm_available_seeders(movie_id: str, quality_code: str, missing_chunks: set[str]) -> list[SwarmSourceEntry]:
  _cleanup_swarm_seeders()
  normalized_quality_code = _normalize_quality_code(quality_code)
  entries: list[SwarmSourceEntry] = []
  freshness_cutoff = datetime.utcnow() - timedelta(seconds=SWARM_SEEDER_FRESHNESS_SECONDS)
  for seeder in SWARM_AVAILABLE_SEEDERS.values():
    if seeder["movie_id"] != movie_id or seeder["quality_code"] != normalized_quality_code:
      continue
    try:
      updated_at = datetime.fromisoformat(seeder["updated_at"])
    except ValueError:
      continue
    if updated_at < freshness_cutoff:
      continue
    cooldown_until = str(seeder.get("cooldown_until") or "").strip()
    if cooldown_until:
      try:
        if datetime.fromisoformat(cooldown_until) > datetime.utcnow():
          continue
      except ValueError:
        pass
    chunk_names = sorted(_get_swarm_json_set(seeder, "chunk_names").intersection(missing_chunks))
    if not chunk_names:
      continue
    entries.append(
      SwarmSourceEntry(
        source_id=seeder["seeder_id"],
        source_type="webrtc_peer",
        user_id=seeder.get("user_id"),
        device_label=seeder.get("device_label"),
        chunk_names=chunk_names,
        chunk_count=len(chunk_names),
        last_seen_at=updated_at.isoformat(timespec="seconds") + "Z",
      )
    )
  def _sort_key(item: SwarmSourceEntry) -> tuple[int, datetime]:
    try:
      last_seen = datetime.fromisoformat(item.last_seen_at.replace("Z", ""))
    except ValueError:
      last_seen = datetime.min
    return (item.chunk_count, last_seen)

  entries.sort(key=_sort_key, reverse=True)
  return entries


def _assign_seeders_to_active_receiver_sessions(movie_id: str, quality_code: str, seeders: list[SwarmSourceEntry]) -> None:
  if not seeders:
    return
  _cleanup_swarm_sessions()
  normalized_quality_code = _normalize_quality_code(quality_code)
  selected_ids = [seeder.source_id for seeder in seeders]
  for session in SWARM_SESSIONS.values():
    if session["movie_id"] != movie_id or session["quality_code"] != normalized_quality_code:
      continue
    assigned_ids = _get_swarm_json_set(session, "assigned_seeder_ids")
    changed = False
    for seeder_id in selected_ids:
      if seeder_id not in assigned_ids:
        assigned_ids.add(seeder_id)
        changed = True
      if seeder_id in SWARM_AVAILABLE_SEEDERS:
        SWARM_AVAILABLE_SEEDERS[seeder_id]["assigned_session_id"] = session["session_id"]
    if changed:
      session["assigned_seeder_ids"] = json.dumps(sorted(assigned_ids))
      if not session.get("selected_seeder_id") and selected_ids:
        session["selected_seeder_id"] = selected_ids[0]
      _touch_swarm_session(session)


def _swarm_demand_entries_for_chunks(movie_id: str, quality_code: str, available_chunks: set[str]) -> list[SwarmDemandEntry]:
  _cleanup_swarm_demands()
  normalized_quality_code = _normalize_quality_code(quality_code)
  entries: list[SwarmDemandEntry] = []
  for demand in SWARM_ACTIVE_DEMANDS.values():
    if demand["movie_id"] != movie_id or demand["quality_code"] != normalized_quality_code:
      continue
    missing_chunks = _get_swarm_json_set(demand, "missing_chunk_names")
    useful_chunks = missing_chunks.intersection(available_chunks)
    if not useful_chunks:
      continue
    entries.append(
      SwarmDemandEntry(
        movie_id=movie_id,
        quality_code=normalized_quality_code,
        receiver_count=int(demand.get("receiver_count") or 0),
        missing_chunk_count=len(useful_chunks),
        expires_at=datetime.fromisoformat(demand["expires_at"]).isoformat(timespec="seconds") + "Z",
      )
    )
  return entries


def _get_swarm_json_set(session: dict[str, str], key: str) -> set[str]:
  raw = session.get(key) or "[]"
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError:
    parsed = []
  return {str(item).strip() for item in parsed if str(item).strip()}


def _set_swarm_json_set(session: dict[str, str], key: str, values: set[str]) -> None:
  session[key] = json.dumps(sorted(values))


def _get_swarm_sources(session: dict[str, str]) -> dict[str, dict]:
  raw = session.get("sources_json") or "{}"
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError:
    parsed = {}
  return parsed if isinstance(parsed, dict) else {}


def _set_swarm_sources(session: dict[str, str], sources: dict[str, dict]) -> None:
  session["sources_json"] = json.dumps(sources)


def _normalize_swarm_seeder_id(value: str | None) -> str:
  return str(value or "").strip()


def _get_swarm_peer_links(session: dict[str, str]) -> dict[str, dict]:
  raw = session.get("webrtc_peer_links_json") or "{}"
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError:
    parsed = {}
  return parsed if isinstance(parsed, dict) else {}


def _set_swarm_peer_links(session: dict[str, str], links: dict[str, dict]) -> None:
  session["webrtc_peer_links_json"] = json.dumps(links)


def _get_or_create_swarm_peer_link(session: dict[str, str], seeder_id: str) -> dict:
  normalized_seeder_id = _normalize_swarm_seeder_id(seeder_id)
  if not normalized_seeder_id:
    raise HTTPException(status_code=400, detail="Seeder id is required for peer-specific signaling.")
  links = _get_swarm_peer_links(session)
  link = links.get(normalized_seeder_id)
  if not isinstance(link, dict):
    link = {
      "seeder_id": normalized_seeder_id,
      "offer": None,
      "answer": None,
      "receiver_candidates": [],
      "sender_candidates": [],
      "updated_at": datetime.utcnow().isoformat(),
    }
  links[normalized_seeder_id] = link
  _set_swarm_peer_links(session, links)
  return link


def _set_swarm_peer_link(session: dict[str, str], seeder_id: str, link: dict) -> None:
  normalized_seeder_id = _normalize_swarm_seeder_id(seeder_id)
  links = _get_swarm_peer_links(session)
  links[normalized_seeder_id] = link
  _set_swarm_peer_links(session, links)


def _require_owned_swarm_seeder(movie_id: str, quality_code: str, seeder_id: str, user_id: str) -> dict[str, str]:
  _cleanup_swarm_seeders()
  seeder = SWARM_AVAILABLE_SEEDERS.get(seeder_id)
  if seeder is None or seeder["movie_id"] != movie_id or seeder["quality_code"] != _normalize_quality_code(quality_code):
    raise HTTPException(status_code=404, detail="That live seeder is not available.")
  if seeder["user_id"] != user_id:
    raise HTTPException(status_code=403, detail="Only that seeder device can publish this signaling lane.")
  return seeder


def _get_swarm_signal_json(session: dict[str, str], key: str) -> dict | None:
  raw = session.get(key) or ""
  if not raw:
    return None
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError:
    return None
  return parsed if isinstance(parsed, dict) else None


def _set_swarm_signal_json(session: dict[str, str], key: str, payload: dict) -> None:
  session[key] = json.dumps(payload)


def _get_swarm_signal_list(session: dict[str, str], key: str) -> list[dict]:
  raw = session.get(key) or "[]"
  try:
    parsed = json.loads(raw)
  except json.JSONDecodeError:
    parsed = []
  return [item for item in parsed if isinstance(item, dict)]


def _append_swarm_signal_candidate(session: dict[str, str], key: str, candidate: dict) -> int:
  candidates = _get_swarm_signal_list(session, key)
  if candidate not in candidates:
    candidates.append(candidate)
  session[key] = json.dumps(candidates[-80:])
  return len(candidates[-80:])


def _append_swarm_peer_candidate(link: dict, key: str, candidate: dict) -> int:
  candidates = [item for item in (link.get(key) or []) if isinstance(item, dict)]
  if candidate not in candidates:
    candidates.append(candidate)
  trimmed = candidates[-80:]
  link[key] = trimmed
  link["updated_at"] = datetime.utcnow().isoformat()
  return len(trimmed)


def _serialize_swarm_signal_state(session: dict[str, str], seeder_id: str | None = None) -> SwarmSignalStateResponse:
  normalized_seeder_id = _normalize_swarm_seeder_id(seeder_id)
  if normalized_seeder_id:
    link = _get_swarm_peer_links(session).get(normalized_seeder_id) or {}
    return SwarmSignalStateResponse(
      movie_id=session["movie_id"],
      quality_code=session["quality_code"],
      session_id=session["session_id"],
      seeder_id=normalized_seeder_id,
      offer=link.get("offer") if isinstance(link.get("offer"), dict) else None,
      answer=link.get("answer") if isinstance(link.get("answer"), dict) else None,
      receiver_candidates=[item for item in (link.get("receiver_candidates") or []) if isinstance(item, dict)],
      sender_candidates=[item for item in (link.get("sender_candidates") or []) if isinstance(item, dict)],
      updated_at=datetime.fromisoformat(str(link.get("updated_at") or session["updated_at"])).isoformat(timespec="seconds") + "Z",
    )
  return SwarmSignalStateResponse(
    movie_id=session["movie_id"],
    quality_code=session["quality_code"],
    session_id=session["session_id"],
    seeder_id=None,
    offer=_get_swarm_signal_json(session, "webrtc_offer_json"),
    answer=_get_swarm_signal_json(session, "webrtc_answer_json"),
    receiver_candidates=_get_swarm_signal_list(session, "webrtc_receiver_candidates_json"),
    sender_candidates=_get_swarm_signal_list(session, "webrtc_sender_candidates_json"),
    updated_at=datetime.fromisoformat(session["updated_at"]).isoformat(timespec="seconds") + "Z",
  )


def _touch_swarm_session(session: dict[str, str]) -> None:
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()


def _swarm_relay_source_folder(session_id: str, source_id: str) -> Path:
  return SWARM_RELAY_ROOT / _safe_name(session_id) / _safe_name(source_id)


def _delete_swarm_relay_files(session_id: str) -> None:
  target = SWARM_RELAY_ROOT / _safe_name(session_id)
  if target.exists():
    shutil.rmtree(target, ignore_errors=True)


def _require_swarm_manifest_chunks(movie_id: str, quality_code: str) -> tuple[dict, dict[str, dict]]:
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  normalized_quality_code = _normalize_quality_code(quality_code)
  _require_manifest_quality(manifest, normalized_quality_code)
  chunk_lookup = _chunk_manifest_lookup(manifest, normalized_quality_code)
  if not chunk_lookup:
    raise HTTPException(status_code=404, detail="No encrypted chunks found for this title quality.")
  return manifest, chunk_lookup


def _safe_swarm_chunk_names(names: list[str], expected_chunks: set[str]) -> set[str]:
  accepted: set[str] = set()
  for item in names:
    name = str(item or "").strip()
    if not name or Path(name).name != name:
      continue
    if name in expected_chunks:
      accepted.add(name)
  return accepted


def _serialize_swarm_session(session: dict[str, str], expected_chunks: set[str]) -> SwarmSessionResponse:
  verified_chunks = _get_swarm_json_set(session, "verified_chunk_names").intersection(expected_chunks)
  return SwarmSessionResponse(
    movie_id=session["movie_id"],
    quality_code=session["quality_code"],
    session_id=session["session_id"],
    expires_at=datetime.fromisoformat(session["expires_at"]).isoformat(timespec="seconds") + "Z",
    user_id=session["user_id"],
    device_label=session.get("device_label") or None,
    manifest_available=bool(expected_chunks),
    expected_chunk_count=len(expected_chunks),
    verified_chunk_count=len(verified_chunks),
    missing_chunk_count=max(0, len(expected_chunks) - len(verified_chunks)),
  )


def _server_swarm_source(movie_id: str, expected_chunks: set[str]) -> SwarmSourceEntry | None:
  content_root = _content_folder_path(movie_id)
  available = set()
  for name in expected_chunks:
    local_exists = (
      next((file_path for file_path in content_root.rglob(name) if file_path.is_file()), None) is not None
      if content_root.exists()
      else False
    )
    if local_exists or chunk_exists(movie_id, name):
      available.add(name)
  if not available:
    return None
  return SwarmSourceEntry(
    source_id="server",
    source_type="server",
    user_id=None,
    device_label="VCNR server",
    chunk_names=sorted(available),
    chunk_count=len(available),
    last_seen_at=app_now().isoformat(timespec="seconds"),
  )


def _swarm_manifest_with_integrity(movie_id: str, manifest: dict, quality_code: str) -> dict:
  manifest_updated_at = str(manifest.get("updated_at") or "")
  cache_key = f"{movie_id}:{_normalize_quality_code(quality_code)}:{manifest_updated_at}"
  cached = SWARM_MANIFEST_INTEGRITY_CACHE.get(cache_key)
  if cached is not None:
    return cached

  enriched_manifest = json.loads(json.dumps(manifest))
  normalized_quality_code = _normalize_quality_code(quality_code)
  content_root = _content_folder_path(movie_id)
  for item in enriched_manifest.get("files", []):
    if _normalize_quality_code(str(item.get("quality_code") or "")) != normalized_quality_code:
      continue
    chunk_name = str(item.get("name") or "").strip()
    if not chunk_name or Path(chunk_name).name != chunk_name:
      continue
    target_path = next((file_path for file_path in content_root.rglob(chunk_name) if file_path.is_file()), None) if content_root.exists() else None
    if target_path is None:
      continue
    chunk_bytes = target_path.read_bytes()
    item["encrypted_size"] = len(chunk_bytes)
    item["encrypted_md5"] = hashlib.md5(chunk_bytes).hexdigest()
    item["encrypted_sha256"] = hashlib.sha256(chunk_bytes).hexdigest()
  SWARM_MANIFEST_INTEGRITY_CACHE.clear()
  SWARM_MANIFEST_INTEGRITY_CACHE[cache_key] = enriched_manifest
  return enriched_manifest


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
  normalized_quality_code = _normalize_quality_code(quality_code)
  package_name = _content_package_name(movie_id, normalized_quality_code)
  package_root = content_root / package_name

  while True:
    plaintext = await upload.read(CONTENT_PLAINTEXT_CHUNK_SIZE)
    if not plaintext:
      break

    chunk_index += 1
    chunk_name = _build_content_chunk_filename(movie_id, quality_code, source_index, chunk_index)
    target_path = package_root / chunk_name
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

    encrypted_bytes = target_path.read_bytes()
    upload_media_object(
      media_object_key(movie_id, "content", f"{normalized_quality_code}/{package_name}/{target_path.name}"),
      encrypted_bytes,
      "application/octet-stream",
    )
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
      "encrypted_sha256": hashlib.sha256(encrypted_bytes).hexdigest(),
      "encrypted_md5": hashlib.md5(encrypted_bytes).hexdigest(),
    })

  await upload.close()
  return chunk_records


def _read_content_manifest(movie_id: str) -> dict | None:
  manifest_path = _content_manifest_path(movie_id)
  if manifest_path.exists():
    try:
      return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
      pass
  raw = download_media_object(media_object_key(movie_id, "content", "manifest.json"))
  if raw is None:
    return None
  try:
    return json.loads(raw.decode("utf-8"))
  except json.JSONDecodeError:
    return None


def _write_content_manifest(movie_id: str, manifest: dict) -> None:
  payload = json.dumps(manifest, indent=2, ensure_ascii=True).encode("utf-8")
  upload_media_object(media_object_key(movie_id, "content", "manifest.json"), payload, "application/json")
  manifest_path = _content_manifest_path(movie_id)
  manifest_path.parent.mkdir(parents=True, exist_ok=True)
  manifest_path.write_bytes(payload)
  for quality in manifest.get("qualities", []):
    quality_code = _normalize_quality_code(str(quality.get("quality_code") or ""))
    if quality_code:
      _delete_quality_content_manifest(movie_id, quality_code)


def _delete_quality_content_manifest(movie_id: str, quality_code: str) -> None:
  normalized_quality_code = _normalize_quality_code(quality_code)
  manifest_path = _quality_content_manifest_path(movie_id, normalized_quality_code)
  manifest_path.unlink(missing_ok=True)
  delete_media_object(media_object_key(movie_id, "content", f"{normalized_quality_code}/manifest.json"))


def _normalize_upload_torrent_webseed_base(
  movie_id: str | None = None,
  quality_code: str = "",
) -> str:
  """Return the full webseed folder URL for a movie's delivery torrent.

  The returned value is a BitTorrent HTTP webseed base.  BitComet / libtorrent
  append the torrent ``info.name`` folder and each file path to this base
  (BEP19 multi-file layout) to build the chunk download URL.

  Webseed layouts:

  * **App API (preferred)**: ``{frontend_origin}/api/movies/{movie_id}/delivery/
    public-chunks/{quality}/``. Every chunk request is answered by the app,
    which streams from local disk when the chunk is present or redirects to a
    short-lived presigned R2 GET URL otherwise. This works whether or not the R2
    bucket has public read access enabled, so it is the reliable default.

  * **Direct R2 (optional secondary in ``url-list``)**: the public content folder
    ``{r2_public_base_url}/{movie_id}/content/``. Only usable when the bucket's
    public access is enabled.

  Returns an empty string when no usable webseed base is configured (e.g. no R2
  and a loopback-only frontend origin).
  """
  settings = get_settings()
  base = settings.frontend_origin.strip().rstrip("/")
  lowered = base.lower()
  loopback_hosts = ("localhost", "127.0.0.1", "0.0.0.0")
  if (
    base.startswith(("http://", "https://"))
    and not any(token in lowered for token in loopback_hosts)
    and movie_id
  ):
    normalized = _normalize_quality_code(quality_code)
    if normalized:
      return f"{base}/api/movies/{movie_id}/delivery/public-chunks/{normalized}/"
  # No usable public app origin: fall back to the direct R2 public bucket folder.
  if movie_id:
    r2_base = _quality_chunk_webseed_base(movie_id, quality_code)
    if r2_base and r2_base.startswith(("http://", "https://")):
      return r2_base.rstrip("/") + "/"
  return ""


def _quality_chunk_webseed_base(movie_id: str, quality_code: str) -> str | None:
  r2_base = chunk_webseed_base(movie_id)
  if not r2_base:
    return None
  normalized_quality_code = _normalize_quality_code(quality_code)
  if not normalized_quality_code:
    return r2_base.rstrip("/") + "/"
  return r2_base.rstrip("/") + f"/{normalized_quality_code}/"


def _r2_chunk_download_url(movie_id: str, quality_code: str, chunk_name: str) -> str | None:
  """Return a short-lived presigned R2 GET URL for a chunk, or None.

  Chunk delivery goes through the app's API, which signs an R2 GET on demand and
  redirects the torrent client / mobile app to it. This works even when the R2
  bucket's public read access is NOT enabled (the ``pub-...r2.dev`` URL would
  otherwise return Cloudflare's "Is this your bucket?" 404 page).

  Returns None when the object is missing so callers can fail fast (404) instead
  of redirecting peers to a dead R2 URL. That lets mobile clients fall back to
  DHT/LAN seeders when server packages were deleted.
  """
  if not r2_enabled():
    return None
  normalized_quality_code = _normalize_quality_code(quality_code)
  package_name = _content_package_name(movie_id, normalized_quality_code)
  key = media_object_key(movie_id, "content", f"{normalized_quality_code}/{package_name}/{chunk_name}")
  if not media_object_exists(key):
    # Legacy flat layout used by older uploads.
    legacy_key = media_object_key(movie_id, "content", f"{normalized_quality_code}/{chunk_name}")
    if media_object_exists(legacy_key):
      return presign_media_download(legacy_key, expires_seconds=3600)
    return None
  return presign_media_download(key, expires_seconds=3600)


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
    "torrent_packages": {},
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
  manifest.setdefault("torrent_packages", {})
  manifest.setdefault("updated_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")
  return manifest


def _content_quality_lookup(manifest: dict) -> dict[str, dict]:
  return {
    str(item.get("quality_code") or "").strip().lower(): item
    for item in manifest.get("qualities", [])
    if str(item.get("quality_code") or "").strip()
  }


def _quality_manifest_files(manifest: dict, quality_code: str) -> list[dict]:
  normalized_quality_code = _normalize_quality_code(quality_code)
  quality_entry = _content_quality_lookup(manifest).get(normalized_quality_code) or {}
  quality_files = quality_entry.get("files")
  if isinstance(quality_files, list) and quality_files:
    return [
      item
      for item in quality_files
      if _normalize_quality_code(str(item.get("quality_code") or normalized_quality_code)) == normalized_quality_code
    ]
  return [
    item
    for item in manifest.get("files", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) == normalized_quality_code
  ]


def _require_manifest_quality(manifest: dict, quality_code: str) -> None:
  normalized_quality_code = _normalize_quality_code(quality_code)
  if normalized_quality_code not in _content_quality_lookup(manifest):
    raise HTTPException(status_code=404, detail="Encrypted content is not uploaded for this title quality.")


def _content_is_complete(movie: dict, manifest: dict) -> bool:
  required_codes = {_normalize_quality_code(item["quality_code"]) for item in _movie_content_qualities(movie)}
  available_codes = set(_content_quality_lookup(manifest).keys())
  return bool(required_codes) and required_codes.issubset(available_codes)


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
  delete_media_prefix(f"{movie_id}/content/{quality_key}/")
  # BEP19 package folder for the torrent ``name``. Delete the nested webseed
  # copies together with the flat chunks so re-upload/deletion does not leave
  # orphaned ``{movie_id}/content/{package_name}/{chunk}`` objects in R2.
  package_name = _content_package_name(movie_id, quality_key)
  for chunk_record in quality_entry.get("files", []):
    chunk_name = str(chunk_record.get("name") or "").strip()
    if chunk_name:
      delete_chunk(movie_id, chunk_name, package_name=package_name)
  manifest["qualities"] = [
    item for item in manifest.get("qualities", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) != quality_key
  ]
  manifest["files"] = [
    item for item in manifest.get("files", [])
    if _normalize_quality_code(str(item.get("quality_code") or "")) != quality_key
  ]
  torrent_packages = manifest.get("torrent_packages")
  if isinstance(torrent_packages, dict):
    torrent_packages.pop(quality_key, None)
  _content_torrent_path(movie_id, quality_key).unlink(missing_ok=True)
  delete_media_object(media_object_key(movie_id, "content", f"{quality_key}.torrent"))
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


def _normalize_upload_relative_path(value: str) -> str:
  cleaned = str(value or "").replace("\\", "/").strip().lstrip("/")
  parts = [part for part in cleaned.split("/") if part and part not in {".", ".."}]
  if "content" in parts:
    parts = parts[parts.index("content") + 1:]
  return "/".join(parts)


def _converted_package_file_lookup(files: list[UploadFile], relative_paths: list[str]) -> dict[str, UploadFile]:
  lookup: dict[str, UploadFile] = {}
  for index, upload in enumerate(files):
    supplied_path = relative_paths[index] if index < len(relative_paths) else ""
    candidates = [
      _normalize_upload_relative_path(supplied_path),
      _normalize_upload_relative_path(upload.filename or ""),
      Path(upload.filename or "").name,
    ]
    for candidate in candidates:
      if candidate:
        lookup[candidate] = upload
  return lookup


async def _read_converted_package_manifest(files: list[UploadFile], relative_paths: list[str]) -> dict:
  for index, upload in enumerate(files):
    supplied_path = relative_paths[index] if index < len(relative_paths) else ""
    normalized_path = _normalize_upload_relative_path(supplied_path or upload.filename or "")
    if normalized_path == "manifest.json" or Path(upload.filename or "").name == "manifest.json":
      raw = await upload.read()
      await upload.seek(0)
      try:
        manifest = json.loads(raw.decode("utf-8"))
      except Exception:
        raise HTTPException(status_code=400, detail="The selected content folder has an invalid manifest.json.")
      if not isinstance(manifest, dict):
        raise HTTPException(status_code=400, detail="The selected content folder manifest is not valid.")
      return manifest
  raise HTTPException(status_code=400, detail="Please select the converted content folder that contains manifest.json.")


async def _stage_converted_content_package(
  movie: dict,
  source_manifest: dict,
  uploaded_lookup: dict[str, UploadFile],
  staging_root: Path,
) -> tuple[dict, int]:
  configured_qualities = {
    _normalize_quality_code(item["quality_code"]): item
    for item in _movie_content_qualities(movie)
  }
  if not configured_qualities:
    raise HTTPException(status_code=400, detail="No title qualities are configured for this title.")

  source_quality_lookup = _content_quality_lookup(source_manifest)
  source_codes = set(source_quality_lookup.keys())
  required_codes = set(configured_qualities.keys())
  missing_codes = sorted(required_codes - source_codes)
  unknown_codes = sorted(source_codes - required_codes)
  if missing_codes:
    raise HTTPException(status_code=400, detail=f"Converted package is missing title qualities: {', '.join(missing_codes)}.")
  if unknown_codes:
    raise HTTPException(status_code=400, detail=f"Converted package has unknown title qualities: {', '.join(unknown_codes)}.")

  manifest = _default_content_manifest(movie)
  manifest["movie_id"] = movie["id"]
  manifest["movie_title"] = movie["title"]
  manifest["delivery_start_at"] = None
  manifest["upload_start_at"] = None
  manifest["password_publish_at"] = movie.get("password_publish_at")
  manifest["encryption"] = source_manifest.get("encryption") or {
    "algorithm": "AES-256-GCM",
    "kdf": "PBKDF2-HMAC-SHA256",
    "iterations": CONTENT_KDF_ITERATIONS,
    "salt_bytes": CONTENT_SALT_SIZE,
    "nonce_bytes": CONTENT_NONCE_SIZE,
    "tag_bytes": CONTENT_TAG_SIZE,
  }
  manifest["qualities"] = []
  manifest["files"] = []
  manifest["torrent_packages"] = {}

  total_chunks = 0
  for quality_code in sorted(required_codes, key=lambda code: (configured_qualities[code]["sort_order"], configured_qualities[code]["quality_label"])):
    source_entry = source_quality_lookup[quality_code]
    configured_entry = configured_qualities[quality_code]
    source_files = [
      dict(item)
      for item in source_entry.get("files", [])
      if _normalize_quality_code(str(item.get("quality_code") or "")) == quality_code
    ]
    if not source_files:
      raise HTTPException(status_code=400, detail=f"{configured_entry['quality_label']} has no chunk records in manifest.json.")

    package = _content_package_name(movie["id"], quality_code)
    staged_package_root = staging_root / quality_code / package
    staged_package_root.mkdir(parents=True, exist_ok=True)
    saved_files: list[dict] = []

    for record in sorted(source_files, key=lambda item: (int(item.get("chunk_index") or 0), str(item.get("name") or ""))):
      chunk_name = Path(str(record.get("name") or "")).name
      if not chunk_name or not chunk_name.endswith(".vcnr"):
        raise HTTPException(status_code=400, detail=f"{configured_entry['quality_label']} has an invalid chunk name in manifest.json.")
      candidate_paths = [
        f"{quality_code}/{package}/{chunk_name}",
        f"{quality_code}/{chunk_name}",
        chunk_name,
      ]
      upload = next((uploaded_lookup.get(path) for path in candidate_paths if uploaded_lookup.get(path)), None)
      if upload is None:
        upload = next((
          candidate
          for path, candidate in uploaded_lookup.items()
          if path.endswith(f"/{chunk_name}") or path == chunk_name
        ), None)
      if upload is None:
        raise HTTPException(status_code=400, detail=f"Missing chunk file for {configured_entry['quality_label']}: {chunk_name}.")

      raw = await upload.read()
      await upload.seek(0)
      expected_size = int(record.get("encrypted_size") or 0)
      if expected_size > 0 and len(raw) != expected_size:
        raise HTTPException(status_code=400, detail=f"Chunk size mismatch for {chunk_name}.")
      expected_sha256 = str(record.get("encrypted_sha256") or "").strip().lower()
      actual_sha256 = hashlib.sha256(raw).hexdigest()
      if expected_sha256 and actual_sha256.lower() != expected_sha256:
        raise HTTPException(status_code=400, detail=f"Chunk checksum mismatch for {chunk_name}.")

      (staged_package_root / chunk_name).write_bytes(raw)
      saved_record = dict(record)
      saved_record["name"] = chunk_name
      saved_record["quality_code"] = quality_code
      saved_record["quality_label"] = configured_entry["quality_label"]
      saved_record["encrypted_size"] = len(raw)
      saved_record["encrypted_sha256"] = actual_sha256
      saved_record["encrypted_md5"] = hashlib.md5(raw).hexdigest()
      saved_files.append(saved_record)

    quality_entry = {
      "quality_code": quality_code,
      "quality_label": configured_entry["quality_label"],
      "stars_required": configured_entry["stars_required"],
      "sort_order": configured_entry["sort_order"],
      "source_name": source_entry.get("source_name") or configured_entry["quality_label"],
      "source_extension": source_entry.get("source_extension"),
      "password_sha256": source_entry.get("password_sha256"),
      "uploaded_at": source_entry.get("uploaded_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
      "chunk_count": len(saved_files),
      "files": saved_files,
    }
    _replace_content_quality_entry(manifest, quality_code, quality_entry)
    total_chunks += len(saved_files)

  return manifest, total_chunks


async def _store_converted_content_package(
  movie: dict,
  files: list[UploadFile],
  relative_paths: list[str],
) -> tuple[dict, int]:
  if not files:
    raise HTTPException(status_code=400, detail="Please select the converted content folder.")
  source_manifest = await _read_converted_package_manifest(files, relative_paths)
  uploaded_lookup = _converted_package_file_lookup(files, relative_paths)

  with TemporaryDirectory(prefix="vcnr-converted-") as tmp_dir:
    staged_root = Path(tmp_dir) / "content"
    manifest, total_chunks = await _stage_converted_content_package(movie, source_manifest, uploaded_lookup, staged_root)

    for quality_entry in manifest.get("qualities", []):
      quality_code = _normalize_quality_code(str(quality_entry.get("quality_code") or ""))
      package = _content_package_name(movie["id"], quality_code)
      staged_package_root = staged_root / quality_code / package
      final_package_root = _quality_package_root(movie["id"], quality_code)
      final_package_root.mkdir(parents=True, exist_ok=True)
      shutil.copytree(staged_package_root, final_package_root, dirs_exist_ok=True)
      for chunk_path in final_package_root.glob("*.vcnr"):
        if chunk_path.name not in {str(item.get("name") or "") for item in quality_entry.get("files", [])}:
          continue
        upload_media_object(
          media_object_key(movie["id"], "content", f"{quality_code}/{package}/{chunk_path.name}"),
          chunk_path.read_bytes(),
          "application/octet-stream",
        )
      _save_quality_torrent_package(manifest, movie["id"], quality_code)

    _write_content_manifest(movie["id"], manifest)
  return manifest, total_chunks


def _converted_content_destination(movie_id: str, relative_path: str, final_quality_code: str | None = None) -> tuple[str, str, str]:
  normalized_path = _normalize_upload_relative_path(relative_path)
  path = Path(normalized_path)
  filename = path.name
  if not filename:
    raise HTTPException(status_code=400, detail="Invalid converted content file path.")
  suffix = path.suffix.lower()
  parts = normalized_path.split("/")
  quality_code = _normalize_quality_code(final_quality_code or (parts[0] if len(parts) > 1 else path.stem))
  if suffix == ".vcnr":
    if len(parts) < 2:
      raise HTTPException(status_code=400, detail="Encrypted chunk files must be inside a quality folder.")
    package = _content_package_name(movie_id, quality_code)
    return quality_code, filename, media_object_key(movie_id, "content", f"{quality_code}/{package}/{filename}")
  if suffix == ".torrent":
    if len(parts) < 2:
      raise HTTPException(status_code=400, detail="Torrent files must be inside a quality folder.")
    return quality_code, filename, media_object_key(movie_id, "content", f"{quality_code}/{quality_code}.torrent")
  raise HTTPException(status_code=400, detail="Only .vcnr chunks and .torrent files are uploaded directly.")


def _converted_quality_label_key(value: str) -> str:
  return _normalize_quality_code(str(value or ""))


def _map_converted_qualities_to_configured(movie: dict, source_manifest: dict) -> tuple[dict[str, dict], dict[str, str]]:
  configured_qualities = {
    _normalize_quality_code(item["quality_code"]): item
    for item in _movie_content_qualities(movie)
  }
  configured_by_label = {
    _converted_quality_label_key(item.get("quality_label") or item.get("quality_code")): code
    for code, item in configured_qualities.items()
  }
  source_quality_lookup = _content_quality_lookup(source_manifest)
  source_to_configured: dict[str, str] = {}
  used_configured: set[str] = set()
  unknown_sources: list[str] = []

  for source_code, source_entry in source_quality_lookup.items():
    matched_code = source_code if source_code in configured_qualities else ""
    if not matched_code:
      label_key = _converted_quality_label_key(source_entry.get("quality_label") or source_code)
      matched_code = configured_by_label.get(label_key, "")
    if not matched_code:
      unknown_sources.append(source_code)
      continue
    if matched_code in used_configured:
      raise HTTPException(status_code=400, detail=f"Multiple converted qualities map to {matched_code}. Please fix the converter quality codes.")
    source_to_configured[source_code] = matched_code
    used_configured.add(matched_code)

  required_codes = set(configured_qualities.keys())
  missing_codes = sorted(required_codes - used_configured)
  if missing_codes:
    expected = ", ".join(
      f'{item["quality_code"]} ({item["quality_label"]})'
      for item in _movie_content_qualities(movie)
    )
    received = ", ".join(
      f'{code} ({source_quality_lookup[code].get("quality_label") or code})'
      for code in sorted(source_quality_lookup.keys())
    ) or "none"
    raise HTTPException(
      status_code=400,
      detail=f"Converted package quality mismatch. Expected: {expected}. Received: {received}.",
    )
  if unknown_sources:
    raise HTTPException(status_code=400, detail=f"Converted package has unknown title qualities: {', '.join(sorted(unknown_sources))}.")

  return configured_qualities, source_to_configured


def _build_registered_converted_manifest(movie: dict, source_manifest: dict) -> tuple[dict, int]:
  configured_qualities, source_to_configured = _map_converted_qualities_to_configured(movie, source_manifest)
  source_quality_lookup = _content_quality_lookup(source_manifest)

  manifest = _default_content_manifest(movie)
  manifest["movie_id"] = movie["id"]
  manifest["movie_title"] = movie["title"]
  manifest["delivery_start_at"] = None
  manifest["upload_start_at"] = None
  manifest["password_publish_at"] = movie.get("password_publish_at")
  manifest["encryption"] = source_manifest.get("encryption") or {
    "algorithm": "AES-256-GCM",
    "kdf": "PBKDF2-HMAC-SHA256",
    "iterations": CONTENT_KDF_ITERATIONS,
    "salt_bytes": CONTENT_SALT_SIZE,
    "nonce_bytes": CONTENT_NONCE_SIZE,
    "tag_bytes": CONTENT_TAG_SIZE,
  }
  manifest["qualities"] = []
  manifest["files"] = []
  manifest["torrent_packages"] = {}

  total_chunks = 0
  for source_code, quality_code in sorted(source_to_configured.items(), key=lambda item: (configured_qualities[item[1]]["sort_order"], configured_qualities[item[1]]["quality_label"])):
    source_entry = source_quality_lookup[source_code]
    configured_entry = configured_qualities[quality_code]
    source_files = [
      dict(item)
      for item in source_entry.get("files", [])
      if _normalize_quality_code(str(item.get("quality_code") or "")) == source_code
    ]
    if not source_files:
      raise HTTPException(status_code=400, detail=f"{configured_entry['quality_label']} has no chunk records in manifest.json.")

    saved_files: list[dict] = []
    for record in sorted(source_files, key=lambda item: (int(item.get("chunk_index") or 0), str(item.get("name") or ""))):
      chunk_name = Path(str(record.get("name") or "")).name
      if not chunk_name.endswith(".vcnr"):
        raise HTTPException(status_code=400, detail=f"{configured_entry['quality_label']} has an invalid chunk name in manifest.json.")
      package = _content_package_name(movie["id"], quality_code)
      if not media_object_exists(media_object_key(movie["id"], "content", f"{quality_code}/{package}/{chunk_name}")):
        raise HTTPException(status_code=404, detail=f"Uploaded chunk was not found in R2: {chunk_name}.")
      saved_record = dict(record)
      saved_record["name"] = chunk_name
      saved_record["quality_code"] = quality_code
      saved_record["quality_label"] = configured_entry["quality_label"]
      saved_files.append(saved_record)

    torrent_file_name = f"{quality_code}.torrent"
    torrent_object_key = media_object_key(movie["id"], "content", f"{quality_code}/{torrent_file_name}")
    if not media_object_exists(torrent_object_key):
      raise HTTPException(status_code=404, detail=f"Uploaded torrent was not found in R2: {torrent_file_name}.")

    torrent_metadata = (
      source_manifest.get("torrent_packages", {}).get(source_code)
      or source_entry.get("torrent")
      or {}
    )
    if not isinstance(torrent_metadata, dict):
      torrent_metadata = {}
    else:
      torrent_metadata = dict(torrent_metadata)

    # Converter torrents are often saved with an empty url-list. Inject the
    # current App-API (+ optional R2) webseeds before the package goes live.
    try:
      stored_torrent = download_media_object(torrent_object_key)
    except Exception:
      stored_torrent = None
    if not stored_torrent:
      raise HTTPException(status_code=404, detail=f"Uploaded torrent was not found in R2: {torrent_file_name}.")
    _refreshed_torrent, torrent_metadata = _refresh_quality_torrent_bytes(
      movie["id"],
      quality_code,
      stored_torrent,
      persist=True,
      existing_metadata=torrent_metadata,
    )

    quality_entry = {
      "quality_code": quality_code,
      "quality_label": configured_entry["quality_label"],
      "stars_required": configured_entry["stars_required"],
      "sort_order": configured_entry["sort_order"],
      "source_name": source_entry.get("source_name") or configured_entry["quality_label"],
      "source_extension": source_entry.get("source_extension"),
      "password_sha256": source_entry.get("password_sha256"),
      "uploaded_at": source_entry.get("uploaded_at") or datetime.utcnow().isoformat(timespec="seconds") + "Z",
      "chunk_count": len(saved_files),
      "files": saved_files,
      "torrent": torrent_metadata,
    }
    _replace_content_quality_entry(manifest, quality_code, quality_entry)
    manifest["torrent_packages"][quality_code] = torrent_metadata
    total_chunks += len(saved_files)

  return manifest, total_chunks


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
  _save_quality_torrent_package(manifest, movie["id"], normalized_quality_code)
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


@router.post("/torrent-test/seeders/announce")
def announce_torrent_test_seeder(payload: dict) -> dict:
  movie_id = str(payload.get("movie_id") or "").strip()
  quality_code = _normalize_quality_code(str(payload.get("quality_code") or ""))
  base_url = str(payload.get("base_url") or "").strip().rstrip("/") + "/"
  chunk_names = [
    _safe_name(str(item))
    for item in (payload.get("chunk_names") or [])
    if str(item).strip()
  ]
  device_label = str(payload.get("device_label") or "Torrent Test Seeder").strip()[:120]
  if not movie_id or not quality_code or not base_url.startswith(("http://", "https://")):
    raise HTTPException(status_code=400, detail="movie_id, quality_code, and base_url are required.")
  if not chunk_names:
    raise HTTPException(status_code=400, detail="At least one chunk name is required.")
  _cleanup_torrent_test_seeders()
  key = f"{movie_id}|{quality_code}|{base_url}"
  unique_chunks = sorted(set(chunk_names))
  expires_at = _torrent_test_seeder_expiry()
  TORRENT_TEST_SEEDERS[key] = {
    "movie_id": movie_id,
    "quality_code": quality_code,
    "base_url": base_url,
    "device_label": device_label,
    "chunk_names": json.dumps(unique_chunks),
    "chunk_count": str(len(unique_chunks)),
    "updated_at": datetime.utcnow().isoformat(),
    "expires_at": expires_at.isoformat(),
  }
  return {
    "status": "ok",
    "movie_id": movie_id,
    "quality_code": quality_code,
    "base_url": base_url,
    "chunk_count": len(unique_chunks),
    "expires_at": expires_at.isoformat(timespec="seconds") + "Z",
  }


@router.get("/torrent-test/seeders")
def list_torrent_test_seeders(movie_id: str, quality_code: str) -> dict:
  normalized_quality_code = _normalize_quality_code(quality_code)
  _cleanup_torrent_test_seeders()
  seeders = []
  for item in TORRENT_TEST_SEEDERS.values():
    if item.get("movie_id") != movie_id or item.get("quality_code") != normalized_quality_code:
      continue
    seeders.append(
      {
        "base_url": str(item.get("base_url") or ""),
        "device_label": str(item.get("device_label") or "Torrent Test Seeder"),
        "chunk_count": int(item.get("chunk_count") or 0),
        "chunk_names": json.loads(str(item.get("chunk_names") or "[]")),
        "updated_at": str(item.get("updated_at") or ""),
        "expires_at": str(item.get("expires_at") or ""),
      }
    )
  return {
    "movie_id": movie_id,
    "quality_code": normalized_quality_code,
    "seeder_count": len(seeders),
    "seeders": seeders,
  }


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


@router.post("/push/devices", response_model=PushDeviceResponse)
def register_push_device(
  payload: PushDeviceRegisterRequest,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] = Depends(get_current_user),
) -> PushDeviceResponse:
  """Store the device push token so alerts arrive while the app is closed."""
  if not is_expo_push_token(payload.push_token):
    raise HTTPException(status_code=400, detail="A valid Expo push token is required.")

  registered = (
    persistence.register_push_device_token(
      db,
      current_user["id"],
      payload.push_token,
      payload.platform,
      payload.device_label,
    )
    if db
    else demo_store.register_push_device_token(
      current_user["id"],
      payload.push_token,
      payload.platform,
      payload.device_label,
    )
  )
  if not registered:
    raise HTTPException(status_code=400, detail="This device could not be registered for alerts.")
  return PushDeviceResponse(registered=True, message="This device will now receive Cine Vault alerts.")


@router.delete("/push/devices", response_model=PushDeviceResponse)
def unregister_push_device(
  payload: PushDeviceUnregisterRequest,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] = Depends(get_current_user),
) -> PushDeviceResponse:
  removed = (
    persistence.unregister_push_device_token(db, current_user["id"], payload.push_token)
    if db
    else demo_store.unregister_push_device_token(current_user["id"], payload.push_token)
  )
  return PushDeviceResponse(
    registered=False,
    message="This device will no longer receive Cine Vault alerts." if removed else "This device was not registered.",
  )


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


@router.delete("/movies/{movie_id}/wish", response_model=MovieInterestResponse)
def remove_movie_wish(
  movie_id: str,
  db: Session | None = Depends(get_db),
  current_user: dict[str, str] = Depends(get_current_user),
) -> MovieInterestResponse:
  try:
    movie = (
      persistence.remove_movie_wish(db, movie_id, current_user["id"])
      if db
      else demo_store.remove_movie_wish(movie_id, current_user["id"])
    )
  except ValueError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return MovieInterestResponse(
    item=_sanitize_movie_payload(movie),
    message=f'"{movie["title"]}" removed from your wish list.',
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


@router.post("/admin/cast-lookup")
def admin_cast_image_lookup(
  payload: CastImageLookupRequest,
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  name = payload.name.strip()
  slug = _sanitize_cast_image_name(name)
  STAR_CAST_ROOT.mkdir(parents=True, exist_ok=True)

  existing = sorted(STAR_CAST_ROOT.glob(f"{slug}.*"))
  if existing:
    if r2_enabled():
      upload_media_object(f"star_cast/{existing[0].name}", existing[0].read_bytes())
    return {
      "success": True,
      "name": name,
      "image_path": f"/media/star_cast/{existing[0].name}",
      "source": "wikipedia",
    }

  portrait = _resolve_wikipedia_portrait(name)
  if not portrait:
    return {
      "success": False,
      "name": name,
      "message": "No profile image found for this name on Wikipedia.",
    }

  image_bytes = _download_cast_image(portrait["source"])
  if not image_bytes:
    return {
      "success": False,
      "name": name,
      "message": "Could not download the profile image from Wikipedia.",
    }

  target = STAR_CAST_ROOT / f"{slug}{_cast_image_extension(portrait['source'])}"
  target.write_bytes(image_bytes)
  if r2_enabled():
    upload_media_object(f"star_cast/{target.name}", image_bytes)
  return {
    "success": True,
    "name": name,
    "image_path": f"/media/star_cast/{target.name}",
    "source": "wikipedia",
  }


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
  # If both fields are empty/None, clear the release schedule
  if not payload.release_date_time and not payload.release_passcode:
    movie = persistence.clear_movie_content_release_state(db, movie_id) if db else demo_store.clear_movie_content_release_state(movie_id)
    if movie is None:
      raise HTTPException(status_code=404, detail="Movie not found.")
    return AdminMovieActionResponse(
      item=_sanitize_movie_payload(movie),
      message=f'Main content release schedule cleared for "{movie["title"]}".',
    )

  # Otherwise, schedule the release (both fields required)
  release_date_time = (payload.release_date_time or "").strip()
  release_passcode = (payload.release_passcode or "").strip()
  if not release_date_time:
    raise HTTPException(status_code=400, detail="Choose a future release date and time.")
  if not release_passcode:
    raise HTTPException(status_code=400, detail="Enter the release passcode.")
  parsed_release_date = parse_app_datetime(release_date_time)
  if parsed_release_date is None:
    raise HTTPException(status_code=400, detail="Choose a valid release date and time.")
  if parsed_release_date <= app_now():
    raise HTTPException(status_code=400, detail="Release date and time must be in the future.")

  movie = persistence.release_movie_main_content(db, movie_id, release_date_time, release_passcode) if db else demo_store.release_movie_main_content(movie_id, release_date_time, release_passcode)
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
    # Mirror the poster to R2 when configured.
    if r2_enabled():
      key = media_object_key(movie_id, "posters", filename, normalized_orientation)
      upload_media_object(key, (LIBRARY_MEDIA_ROOT / movie_id / "posters" / normalized_orientation / filename).read_bytes())
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


@router.post("/admin/movies/{movie_id}/assets/presign")
def admin_presign_movie_asset_upload(
  movie_id: str,
  kind: str = Form(...),
  filename: str = Form(...),
  orientation: str | None = Form(default=None),
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  """Return a presigned R2 PUT URL for a direct browser upload.

  The admin UI uploads the file straight to R2 (bypassing the Render API),
  then calls the matching register endpoint to update the movie record.
  """
  if not r2_enabled():
    raise HTTPException(status_code=503, detail="R2 storage is not configured on this server.")

  safe_kind = str(kind or "").strip().lower()
  if safe_kind not in {"posters", "trailer", "gallery", "music"}:
    raise HTTPException(status_code=400, detail="Unsupported media kind for presigned upload.")

  safe_name = Path(filename).name
  if safe_name != filename or not safe_name:
    raise HTTPException(status_code=400, detail="Invalid filename.")

  normalized_orientation = None
  if safe_kind == "posters":
    normalized_orientation = "horizontal" if orientation == "horizontal" else "vertical"

  key = media_object_key(movie_id, safe_kind, safe_name, normalized_orientation)
  upload_url = presign_media_upload(key)
  if upload_url is None:
    raise HTTPException(status_code=503, detail="Unable to create a presigned upload URL right now.")

  return {
    "movie_id": movie_id,
    "kind": safe_kind,
    "filename": safe_name,
    "orientation": normalized_orientation,
    "key": key,
    "upload_url": upload_url,
    "public_url": media_public_url(key),
  }


@router.post("/admin/movies/{movie_id}/assets/register")
def admin_register_movie_asset_upload(
  movie_id: str,
  kind: str = Form(...),
  filename: str = Form(...),
  orientation: str | None = Form(default=None),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  """Register a media asset that was uploaded directly to R2.

  Called by the admin UI after a successful presigned PUT to R2.
  """
  safe_kind = _safe_name(kind or "").strip().lower()
  if safe_kind not in {"posters", "trailer", "gallery", "music"}:
    raise HTTPException(status_code=400, detail="Unsupported media kind.")

  safe_name = Path(filename).name
  if safe_name != filename or not safe_name:
    raise HTTPException(status_code=400, detail="Invalid filename.")

  normalized_orientation = None
  if safe_kind == "posters":
    normalized_orientation = "horizontal" if orientation == "horizontal" else "vertical"

  key = media_object_key(movie_id, safe_kind, safe_name, normalized_orientation)
  if not media_object_exists(key):
    raise HTTPException(status_code=404, detail="The uploaded file was not found in storage. Please retry the upload.")

  if db:
    persistence.prime_movie_asset_change(db, movie_id)

  if safe_kind == "posters":
    primary_poster, poster_count_label = _poster_asset_summary(movie_id)
    movie = persistence.update_movie_poster_assets(db, movie_id, primary_poster, poster_count_label) if db else demo_store.update_movie_poster_assets(movie_id, primary_poster, poster_count_label)
  else:
    movie = persistence.register_movie_asset_change(db, movie_id, safe_kind) if db else demo_store.register_movie_asset_change(movie_id, safe_kind)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  kind_label = "Teaser" if safe_kind == "trailer" else safe_kind.title()
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(movie),
    message=f'{kind_label} uploaded for "{movie["title"]}" and sent for Super Admin approval.',
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
  if r2_enabled():
    upload_media_object(media_object_key(movie_id, "trailer", filename), target_path.read_bytes())
  matched = persistence.register_movie_asset_change(db, movie_id, "trailer") if db else demo_store.register_movie_asset_change(movie_id, "trailer")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=f'Teaser uploaded for "{matched["title"]}" and sent for Super Admin approval.',
  )


@router.get("/admin/movies/{movie_id}/assets/trailer", response_model=MediaAssetListResponse)
def admin_list_movie_trailers(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> MediaAssetListResponse:
  _get_movie_or_404(db, movie_id)
  return MediaAssetListResponse(items=[MediaAssetResponse(**item) for item in _list_media_assets(movie_id, "trailer")])


@router.get("/admin/movies/{movie_id}/teasers", response_model=TeaserLinksResponse)
def admin_list_movie_teaser_links(
  movie_id: str,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> TeaserLinksResponse:
  _get_movie_or_404(db, movie_id)
  return TeaserLinksResponse(items=_read_teaser_links(movie_id))


@router.put("/admin/movies/{movie_id}/teasers", response_model=AdminMovieActionResponse)
def admin_update_movie_teaser_links(
  movie_id: str,
  payload: TeaserLinksUpdateRequest,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = _get_movie_or_404(db, movie_id)
  normalized_links: list[str] = []
  for link in payload.links:
    normalized = _normalize_teaser_link(link)
    if normalized is None:
      raise HTTPException(status_code=400, detail="Each teaser link must be a valid YouTube watch, short, share, or embed link.")
    if normalized not in normalized_links:
      normalized_links.append(normalized)
  _save_teaser_links(movie_id, normalized_links)
  if db:
    persistence.prime_movie_asset_change(db, movie_id)
    matched = persistence.register_movie_asset_change(db, movie_id, "trailer")
  else:
    matched = demo_store.register_movie_asset_change(movie_id, "trailer")
  if matched is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  return AdminMovieActionResponse(
    item=_sanitize_movie_payload(matched),
    message=f'Teaser links saved for "{matched["title"]}" and sent for Super Admin approval.',
  )


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


@router.post("/admin/movies/{movie_id}/assets/content-package", response_model=AdminMovieActionResponse)
async def admin_upload_movie_converted_content_package(
  movie_id: str,
  files: list[UploadFile] = File(...),
  relative_paths: list[str] = Form(default=[]),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = _get_movie_or_404(db, movie_id)
  _manifest, chunk_count = await _store_converted_content_package(movie, files, relative_paths)

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
      f'Converted content package uploaded for "{matched["title"]}" '
      f'with {chunk_count} encrypted chunk file{"s" if chunk_count != 1 else ""}. '
      "Upload future start time was reset."
    ),
  )


@router.post("/admin/movies/{movie_id}/assets/content-package/presign")
def admin_presign_movie_converted_content_file(
  movie_id: str,
  relative_path: str = Form(...),
  final_quality_code: str | None = Form(default=None),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> dict:
  _get_movie_or_404(db, movie_id)
  quality_code, filename, key = _converted_content_destination(movie_id, relative_path, final_quality_code)
  upload_url = presign_media_upload(key)
  if upload_url is None:
    raise HTTPException(status_code=503, detail="Unable to create a direct upload URL right now.")
  return {
    "movie_id": movie_id,
    "quality_code": quality_code,
    "filename": filename,
    "key": key,
    "upload_url": upload_url,
  }


@router.post("/admin/movies/{movie_id}/assets/content-package/register", response_model=AdminMovieActionResponse)
def admin_register_movie_converted_content_package(
  movie_id: str,
  manifest_json: str = Form(...),
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminMovieActionResponse:
  movie = _get_movie_or_404(db, movie_id)
  try:
    source_manifest = json.loads(manifest_json)
  except Exception:
    raise HTTPException(status_code=400, detail="The converted manifest.json is invalid.")
  if not isinstance(source_manifest, dict):
    raise HTTPException(status_code=400, detail="The converted manifest.json is invalid.")

  manifest, chunk_count = _build_registered_converted_manifest(movie, source_manifest)
  _write_content_manifest(movie_id, manifest)

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
      f'Converted content package uploaded for "{matched["title"]}" '
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
  quality_files = _quality_manifest_files(manifest, enrollment.quality_code)
  allowed_chunk_names = {
    str(item.get("name") or "")
    for item in quality_files
  }
  if safe_name not in allowed_chunk_names:
    raise HTTPException(status_code=403, detail="This chunk does not belong to the reserved title quality.")
  normalized_quality_code = _normalize_quality_code(enrollment.quality_code)
  package_root = _quality_package_root(movie_id, normalized_quality_code)
  target_path = package_root / safe_name if package_root.is_dir() else None
  if target_path is None or not target_path.is_file():
    content_root = _content_folder_path(movie_id)
    target_path = next((file_path for file_path in content_root.rglob(safe_name) if file_path.is_file()), None) if content_root.exists() else None
  if target_path is None or not target_path.is_file():
    r2_url = _r2_chunk_download_url(movie_id, normalized_quality_code, safe_name)
    if r2_url:
      return RedirectResponse(r2_url)
    raise HTTPException(status_code=404, detail="Encrypted chunk not found.")
  return FileResponse(target_path, filename=safe_name, media_type="application/octet-stream")


def _bencode_value(value) -> bytes:
  if isinstance(value, (bytes, bytearray)):
    return f"{len(value)}:".encode("utf-8") + bytes(value)
  if isinstance(value, str):
    raw = value.encode("utf-8")
    return f"{len(raw)}:".encode("utf-8") + raw
  if isinstance(value, bool):
    return _bencode_value(int(value))
  if isinstance(value, int):
    return f"i{value}e".encode("utf-8")
  if isinstance(value, list):
    return b"l" + b"".join(_bencode_value(v) for v in value) + b"e"
  if isinstance(value, dict):
    items = sorted(
      ((str(k) if not isinstance(k, (bytes, bytearray)) else k, v) for k, v in value.items()),
      key=lambda kv: (kv[0].encode("utf-8") if isinstance(kv[0], str) else bytes(kv[0])),
    )
    out = bytearray(b"d")
    for k, v in items:
      key_bytes = k.encode("utf-8") if isinstance(k, str) else bytes(k)
      out += f"{len(key_bytes)}:".encode("utf-8") + key_bytes
      out += _bencode_value(v)
    out += b"e"
    return bytes(out)
  raise TypeError(f"Cannot bencode type {type(value)!r}")


def _bdecode(data: bytes):
  """Minimal bencode decoder returning lists/dicts/ints/bytes (root dict keys are bytes)."""
  def _val(i: int):
    token = data[i:i + 1]
    if token == b"i":
      j = data.index(b"e", i + 1)
      return int(data[i + 1:j]), j + 1
    if token == b"l":
      i += 1
      out = []
      while data[i:i + 1] != b"e":
        v, i = _val(i)
        out.append(v)
      return out, i + 1
    if token == b"d":
      i += 1
      out = {}
      while data[i:i + 1] != b"e":
        k, i = _val(i)
        v, i = _val(i)
        out[k] = v
      return out, i + 1
    j = data.index(b":", i)
    n = int(data[i:j])
    i = j + 1
    return data[i:i + n], i + n
  root, _ = _val(0)
  return root


def _torrent_with_webseeds(
  torrent_bytes: bytes,
  webseed_urls: list[str],
  trackers: list[str],
) -> bytes:
  """Re-bencode a stored torrent with the current webseed/tracker lists.

  Only the top-level ``url-list`` / ``announce`` keys change, so the ``info``
  section (and therefore the torrent infohash) is left untouched. This lets us
  recover a torrent from R after an ephemeral disk wipe and refresh its webseed
  without re-reading the chunk bytes to recompute piece hashes.
  """
  root = _bdecode(torrent_bytes)
  if not isinstance(root, dict) or b"info" not in root:
    raise ValueError("torrent root is missing the info section")
  if webseed_urls:
    root[b"url-list"] = [u.encode("utf-8") for u in webseed_urls]
  else:
    root.pop(b"url-list", None)
  if trackers:
    root[b"announce"] = trackers[0].encode("utf-8")
    root[b"announce-list"] = [[t.encode("utf-8")] for t in trackers]
  else:
    root.pop(b"announce", None)
    root.pop(b"announce-list", None)
  return _bencode_value(root)


def _torrent_webseed_urls(
  movie_id: str,
  quality_code: str,
  torrent_info_name: str | None = None,
) -> list[str]:
  """Build the current webseed list (App-API primary + direct R2 secondary).

  When ``torrent_info_name`` is provided and differs from the server package
  folder (common for VCNR Converter packages renamed on upload), the App-API
  webseed base is extended with the *server* package segment. BitComet then
  requests ``{base}/{server_pkg}/{info.name}/{chunk}``, which the catch-all
  public-chunks route resolves by chunk filename. That keeps webseeds working
  on deployments that still require ``package_name == {movie_id}-{quality}.vcnr-pkg``.
  """
  webseed_urls: list[str] = []
  api_base = _normalize_upload_torrent_webseed_base(movie_id, quality_code)
  if api_base:
    normalized = _normalize_quality_code(quality_code)
    expected_package = _content_package_name(movie_id, normalized) if normalized else ""
    if torrent_info_name and expected_package and torrent_info_name != expected_package:
      api_base = api_base.rstrip("/") + f"/{expected_package}/"
    webseed_urls.append(api_base.rstrip("/") + "/")
  r2_folder = _quality_chunk_webseed_base(movie_id, quality_code) if r2_enabled() else None
  if r2_folder and r2_folder.startswith(("http://", "https://")):
    norm_r2 = r2_folder.rstrip("/") + "/"
    if norm_r2 not in webseed_urls:
      webseed_urls.append(norm_r2)
  return webseed_urls


def _torrent_tracker_list() -> list[str]:
  return [tracker for tracker in get_settings().public_torrent_trackers if tracker]


def _torrent_display_name(torrent_bytes: bytes, fallback: str) -> str:
  try:
    root = _bdecode(torrent_bytes)
    info = root.get(b"info") if isinstance(root, dict) else None
    if isinstance(info, dict):
      raw_name = info.get(b"name")
      if isinstance(raw_name, (bytes, bytearray)):
        name = bytes(raw_name).decode("utf-8", "replace").strip()
        if name:
          return name
  except Exception:
    pass
  return fallback


def _magnet_uri_for_delivery(
  info_hash: str,
  display_name: str,
  webseed_urls: list[str],
  trackers: list[str],
) -> str:
  magnet_parts = [f"xt=urn:btih:{info_hash}", f"dn={display_name}"]
  for ws in webseed_urls:
    magnet_parts.append(f"ws={ws}")
  for tracker in trackers:
    magnet_parts.append(f"tr={tracker}")
  return "magnet:?" + "&".join(magnet_parts)


def _refresh_quality_torrent_bytes(
  movie_id: str,
  quality_code: str,
  torrent_bytes: bytes,
  *,
  persist: bool = False,
  existing_metadata: dict | None = None,
) -> tuple[bytes, dict]:
  """Re-apply current webseed/tracker lists to a stored torrent (infohash unchanged).

  Converter-uploaded torrents often ship with an empty ``url-list``. Refreshing
  here is what makes BitComet / libtorrent able to HTTP-webseed from the App API
  (and optional public R2 folder) without rebuilding piece hashes.
  """
  normalized = _normalize_quality_code(quality_code)
  torrent_info_name = _torrent_display_name(torrent_bytes, "")
  webseed_urls = _torrent_webseed_urls(
    movie_id,
    normalized,
    torrent_info_name=torrent_info_name or None,
  )
  trackers = _torrent_tracker_list()
  refreshed = _torrent_with_webseeds(torrent_bytes, webseed_urls, trackers)
  info_hash = _info_hash_from_torrent_bytes(refreshed) or str((existing_metadata or {}).get("info_hash_sha1") or "")
  torrent_name = torrent_info_name or _torrent_display_name(
    refreshed,
    str((existing_metadata or {}).get("torrent_name") or f"{movie_id}-{normalized}.vcnr-pkg"),
  )
  torrent_path = _quality_content_torrent_path(movie_id, normalized)
  legacy_torrent_path = _content_torrent_path(movie_id, normalized)
  saved_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
  metadata = {
    key: value
    for key, value in (existing_metadata or {}).items()
    if key not in {"torrent_file_name", "quality_torrent_file_name", "saved_at"}
  }
  metadata.update(
    {
      "info_hash_sha1": info_hash,
      "torrent_name": torrent_name,
      "trackers": list(trackers),
      "webseed_urls": list(webseed_urls),
      "magnet_uri": _magnet_uri_for_delivery(info_hash, torrent_name, webseed_urls, trackers) if info_hash else "",
      "bootstrap_nodes": list(metadata.get("bootstrap_nodes") or TORRENT_BOOTSTRAP_DHT_NODES),
      "use_dht": True,
      "use_lsd": True,
      "use_pex": True,
      "torrent_file_name": torrent_path.name,
      "quality_torrent_file_name": torrent_path.name,
      "saved_at": saved_at,
    }
  )
  if persist:
    torrent_path.parent.mkdir(parents=True, exist_ok=True)
    torrent_path.write_bytes(refreshed)
    legacy_torrent_path.unlink(missing_ok=True)
    if r2_enabled():
      delete_media_object(media_object_key(movie_id, "content", legacy_torrent_path.name))
      upload_media_object(
        media_object_key(movie_id, "content", f"{normalized}/{torrent_path.name}"),
        refreshed,
        "application/x-bittorrent",
      )
  return refreshed, metadata


def _info_hash_from_torrent_bytes(torrent_bytes: bytes) -> str:
  """Return the SHA1 infohash of a bencoded torrent's info section, or ''."""
  try:
    root = _bdecode(torrent_bytes)
    info = root.get(b"info") if isinstance(root, dict) else None
    if isinstance(info, dict):
      return hashlib.sha1(_bencode_value(info)).hexdigest()
  except Exception:
    pass
  return ""


def _iter_streamed_content(content_root: Path, file_entries: list[tuple[str, int]]):
  for name, _expected_size in file_entries:
    path = content_root / name
    if not path.is_file():
      raise HTTPException(status_code=500, detail=f"Torrent build failed: missing chunk {name}")
    with path.open("rb") as fh:
      while True:
        buf = fh.read(1024 * 1024)
        if not buf:
          break
        yield buf


DEFAULT_TORRENT_PIECE_LENGTH = 1024 * 1024
TORRENT_BOOTSTRAP_DHT_NODES = [
  "router.bittorrent.com:6881",
  "dht.transmissionbt.com:6881",
  "router.utorrent.com:6881",
  "dht.aelitis.com:6881",
  "dht.libtorrent.org:25401",
]


def _build_torrent_for_quality(
  manifest: dict,
  movie_id: str,
  quality_code: str,
  webseed_base_url: str,
) -> tuple[dict, bytes, str]:
  settings = get_settings()
  normalized = _normalize_quality_code(quality_code)
  _require_manifest_quality(manifest, normalized)
  chunk_lookup = _chunk_manifest_lookup(manifest, normalized)
  if not chunk_lookup:
    raise HTTPException(status_code=404, detail="No encrypted chunks available for this quality.")
  content_root = _quality_package_root(movie_id, normalized)
  if not content_root.is_dir():
    raise HTTPException(status_code=404, detail="Quality content folder missing on the server.")
  ordered = sorted(chunk_lookup.items(), key=lambda kv: (int(kv[1].get("chunk_index") or 0), kv[0]))
  file_entries: list[tuple[str, int]] = []
  for name, record in ordered:
    size = int(record.get("encrypted_size") or 0)
    if size <= 0:
      path = content_root / name
      if path.is_file():
        size = path.stat().st_size
      else:
        raise HTTPException(status_code=500, detail=f"Invalid chunk size for {name}")
    file_entries.append((name, size))
  total_bytes = sum(size for _, size in file_entries)
  piece_length = DEFAULT_TORRENT_PIECE_LENGTH
  if total_bytes > 0:
    # For extremely large swarms bump piece length to keep < ~16k pieces
    if total_bytes > 1024 * 1024 * 1024 * 16:
      piece_length = 4 * 1024 * 1024
    elif total_bytes > 1024 * 1024 * 1024 * 4:
      piece_length = 2 * 1024 * 1024
  pieces = bytearray()
  buf_view = memoryview(bytearray(piece_length))
  write_pos = 0

  def commit_piece(remaining: int):
    if remaining <= 0:
      return
    digest = hashlib.sha1(buf_view[:remaining]).digest()
    pieces.extend(digest)

  stream = _iter_streamed_content(content_root, file_entries)
  for chunk in stream:
    mem = memoryview(chunk)
    off = 0
    remaining = len(mem)
    while remaining > 0:
      space = piece_length - write_pos
      take = remaining if remaining <= space else space
      buf_view[write_pos:write_pos + take] = mem[off:off + take]
      write_pos += take
      off += take
      remaining -= take
      if write_pos == piece_length:
        commit_piece(piece_length)
        write_pos = 0
  if write_pos > 0:
    commit_piece(write_pos)
  torrent_name = f"{movie_id}-{normalized}.vcnr-pkg"
  info = {
    "name": torrent_name,
    "piece length": piece_length,
    "pieces": bytes(pieces),
    "files": [
      {"length": size, "path": [name]}
      for name, size in file_entries
    ],
  }
  info_bencoded = _bencode_value(info)
  info_hash = hashlib.sha1(info_bencoded).hexdigest()
  created_at = int(datetime.utcnow().timestamp())
  safe_torrent_name = (
    (manifest.get("movie_title") or movie_id).replace("/", "-").replace("\\", "-").strip()
    or torrent_name
  )
  root_meta: dict = {
    "info": info,
    "created by": "CineVault/VCNR (libtorrent-compatible)",
    "creation date": created_at,
    "comment": f"VCNR encrypted delivery torrent for {movie_id}/{normalized}. "
               f"Public DHT/tracker swarm with HTTP webseed bootstrap for VCNR encrypted chunks.",
  }
  trackers = [tracker for tracker in settings.public_torrent_trackers if tracker]
  if trackers:
    root_meta["announce"] = trackers[0]
    root_meta["announce-list"] = [[tracker] for tracker in trackers]
  webseed_urls: list[str] = []
  if webseed_base_url:
    # ``webseed_base_url`` is already the full HTTP webseed root (normally the
    # delivery API folder). Only normalise the trailing slash so torrent clients
    # append chunk paths correctly.
    webseed_urls.append(webseed_base_url.rstrip("/") + "/")
  # Advertise the direct public R2 content folder as an extra webseed so torrent
  # clients can fetch straight from the CDN when the bucket's public read access
  # is enabled (no app proxy hop). Delivery via the app API remains the primary
  # webseed because it works even when public access is disabled.
  if r2_enabled() and movie_id:
    r2_folder = _quality_chunk_webseed_base(movie_id, normalized)
    if r2_folder and r2_folder.startswith(("http://", "https://")):
      normalized_r2 = r2_folder.rstrip("/") + "/"
      if normalized_r2 not in webseed_urls:
        webseed_urls.append(normalized_r2)
  if webseed_urls:
    root_meta["url-list"] = webseed_urls
  magnet_parts = [
    f"xt=urn:btih:{info_hash}",
    f"dn={safe_torrent_name}",
  ]
  for ws in webseed_urls:
    magnet_parts.append(f"ws={ws}")
  for tracker in trackers:
    magnet_parts.append(f"tr={tracker}")
  magnet_uri = "magnet:?" + "&".join(magnet_parts)
  root_meta["info"]["private"] = 0
  torrent_bytes = _bencode_value(root_meta)
  return ({
    "info_hash_sha1": info_hash,
    "torrent_name": torrent_name,
    "total_bytes": int(total_bytes),
    "piece_length": int(piece_length),
    "piece_count": max(0, (int(total_bytes) + piece_length - 1) // piece_length) if int(total_bytes) > 0 else 0,
    "file_count": len(file_entries),
    "comment": root_meta["comment"],
    "created_by": root_meta["created by"],
    "created_at": int(created_at),
    "trackers": trackers,
    "webseed_urls": list(webseed_urls),
    "magnet_uri": magnet_uri,
    "torrent_base64": b64encode(torrent_bytes).decode("ascii"),
    "bootstrap_nodes": list(TORRENT_BOOTSTRAP_DHT_NODES),
    "use_dht": True,
    "use_lsd": True,
    "use_pex": True,
  }, torrent_bytes, info_hash)


def _save_quality_torrent_package(
  manifest: dict,
  movie_id: str,
  quality_code: str,
) -> dict:
  normalized_quality_code = _normalize_quality_code(quality_code)
  payload, torrent_bytes, _info_hash = _build_torrent_for_quality(
    manifest,
    movie_id,
    normalized_quality_code,
    _normalize_upload_torrent_webseed_base(movie_id, normalized_quality_code),
  )
  torrent_path = _quality_content_torrent_path(movie_id, normalized_quality_code)
  legacy_torrent_path = _content_torrent_path(movie_id, normalized_quality_code)
  legacy_torrent_path.unlink(missing_ok=True)
  torrent_path.parent.mkdir(parents=True, exist_ok=True)
  torrent_path.write_bytes(torrent_bytes)
  # Mirror the torrent package to R2 when configured.
  if r2_enabled():
    delete_media_object(media_object_key(movie_id, "content", legacy_torrent_path.name))
    upload_media_object(
      media_object_key(movie_id, "content", f"{normalized_quality_code}/{torrent_path.name}"),
      torrent_bytes,
      "application/x-bittorrent",
    )
  saved_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
  torrent_metadata = {
    key: value
    for key, value in payload.items()
    if key != "torrent_base64"
  }
  torrent_metadata["torrent_file_name"] = torrent_path.name
  torrent_metadata["quality_torrent_file_name"] = torrent_path.name
  torrent_metadata["saved_at"] = saved_at
  manifest.setdefault("torrent_packages", {})
  manifest["torrent_packages"][normalized_quality_code] = torrent_metadata
  quality_lookup = _content_quality_lookup(manifest)
  quality_entry = quality_lookup.get(normalized_quality_code)
  if quality_entry is not None:
    quality_entry["torrent"] = torrent_metadata
  manifest["updated_at"] = saved_at
  return torrent_metadata


@router.get("/movies/{movie_id}/delivery/torrent", response_model=DeliveryTorrentResponse)
def get_movie_delivery_torrent(
  movie_id: str,
  quality_code: str,
  slot_token: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryTorrentResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for mobile delivery queue control.")
  normalized = _normalize_quality_code(quality_code)
  enrollment = _require_valid_slot(db, movie_id, current_user["id"], slot_token)
  if enrollment.quality_code != normalized:
    raise HTTPException(status_code=400, detail="Requested quality does not match the reserved delivery slot.")
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")

  torrent_path = _quality_content_torrent_path(movie_id, normalized)
  legacy_torrent_path = _content_torrent_path(movie_id, normalized)
  quality_lookup = _content_quality_lookup(manifest)
  quality_entry = quality_lookup.get(normalized) or {}
  saved_metadata = (
    manifest.get("torrent_packages", {}).get(normalized)
    or quality_entry.get("torrent")
    or {}
  )

  readable_torrent_path = torrent_path if torrent_path.is_file() else legacy_torrent_path
  if readable_torrent_path.is_file():
    try:
      refreshed_torrent, torrent_metadata = _refresh_quality_torrent_bytes(
        movie_id,
        normalized,
        readable_torrent_path.read_bytes(),
        persist=True,
        existing_metadata=saved_metadata if isinstance(saved_metadata, dict) else {},
      )
      manifest.setdefault("torrent_packages", {})
      manifest["torrent_packages"][normalized] = torrent_metadata
      quality_lookup = _content_quality_lookup(manifest)
      quality_entry = quality_lookup.get(normalized)
      if quality_entry is not None:
        quality_entry["torrent"] = torrent_metadata
      manifest["updated_at"] = str(torrent_metadata.get("saved_at") or "")
      _write_content_manifest(movie_id, manifest)
    except Exception:
      refreshed_torrent = readable_torrent_path.read_bytes()
      torrent_metadata = saved_metadata if isinstance(saved_metadata, dict) else {}
    if refreshed_torrent:
      payload = {
        key: value
        for key, value in torrent_metadata.items()
        if key not in {"torrent_file_name", "quality_torrent_file_name", "saved_at"}
      }
      payload["torrent_base64"] = b64encode(refreshed_torrent).decode("ascii")
      return DeliveryTorrentResponse(
        movie_id=movie_id,
        quality_code=normalized,
        **payload,
      )

  # Local torrent file missing (e.g. fresh ephemeral disk after a redeploy).
  # Recover the previously generated torrent package from R2 and re-apply the
  # CURRENT webseed/tracker lists so clients get the working App-API webseed
  # without re-uploading the content.
  if r2_enabled():
    stored_bytes = None
    for object_name in (f"{normalized}/{torrent_path.name}", legacy_torrent_path.name):
      try:
        stored_bytes = download_media_object(media_object_key(movie_id, "content", object_name))
      except Exception:
        stored_bytes = None
      if stored_bytes:
        break
    if stored_bytes:
      try:
        recovered_torrent, torrent_metadata = _refresh_quality_torrent_bytes(
          movie_id,
          normalized,
          stored_bytes,
          persist=True,
          existing_metadata=saved_metadata if isinstance(saved_metadata, dict) else {},
        )
        manifest.setdefault("torrent_packages", {})
        manifest["torrent_packages"][normalized] = torrent_metadata
        quality_lookup = _content_quality_lookup(manifest)
        quality_entry = quality_lookup.get(normalized)
        if quality_entry is not None:
          quality_entry["torrent"] = torrent_metadata
        manifest["updated_at"] = str(torrent_metadata.get("saved_at") or "")
        _write_content_manifest(movie_id, manifest)
      except Exception:
        recovered_torrent = None
        torrent_metadata = None
      if recovered_torrent and torrent_metadata is not None:
        payload = {
          key: value
          for key, value in torrent_metadata.items()
          if key not in {"torrent_file_name", "quality_torrent_file_name", "saved_at"}
        }
        payload["torrent_base64"] = b64encode(recovered_torrent).decode("ascii")
        return DeliveryTorrentResponse(
          movie_id=movie_id,
          quality_code=normalized,
          **payload,
        )

  # No recoverable torrent package: build a fresh torrent from local chunk files
  # (used at upload time and when R2 is unavailable).
  webseed_base = _normalize_upload_torrent_webseed_base(movie_id, normalized)
  payload, torrent_bytes, _info_hash = _build_torrent_for_quality(
    manifest,
    movie_id,
    normalized,
    webseed_base,
  )
  payload["torrent_base64"] = b64encode(torrent_bytes).decode("ascii")
  try:
    torrent_path.parent.mkdir(parents=True, exist_ok=True)
    torrent_path.write_bytes(torrent_bytes)
    legacy_torrent_path.unlink(missing_ok=True)
    if r2_enabled():
      delete_media_object(media_object_key(movie_id, "content", legacy_torrent_path.name))
      upload_media_object(
        media_object_key(movie_id, "content", f"{normalized}/{torrent_path.name}"),
        torrent_bytes,
        "application/x-bittorrent",
      )
    saved_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    torrent_metadata = {
      key: value
      for key, value in payload.items()
      if key != "torrent_base64"
    }
    torrent_metadata["torrent_file_name"] = torrent_path.name
    torrent_metadata["quality_torrent_file_name"] = torrent_path.name
    torrent_metadata["saved_at"] = saved_at
    manifest.setdefault("torrent_packages", {})
    manifest["torrent_packages"][normalized] = torrent_metadata
    quality_lookup = _content_quality_lookup(manifest)
    quality_entry = quality_lookup.get(normalized)
    if quality_entry is not None:
      quality_entry["torrent"] = torrent_metadata
    manifest["updated_at"] = saved_at
    _write_content_manifest(movie_id, manifest)
  except Exception:
    # Best-effort refresh so mobile delivery can still proceed even if manifest persistence fails.
    pass
  payload_out = {
    "movie_id": movie_id,
    "quality_code": normalized,
    **payload,
  }
  return DeliveryTorrentResponse(**payload_out)


def _proxy_presigned_r2_chunk(
  r2_url: str,
  *,
  range_header: str | None = None,
  method: str = "GET",
) -> StreamingResponse:
  """Stream a presigned R2 object through the app (HTTP 200/206, no redirect).

  BitComet and some other torrent clients fail to follow ``307`` redirects to
  signed R2 URLs for BEP19 webseeds. Proxying keeps the webseed URL stable and
  returns a direct body they can consume.
  """
  request_headers: dict[str, str] = {}
  if range_header:
    request_headers["Range"] = range_header
  upstream_method = "HEAD" if method.upper() == "HEAD" else "GET"
  upstream_request = urllib.request.Request(
    r2_url,
    headers=request_headers,
    method=upstream_method,
  )
  try:
    upstream = urllib.request.urlopen(upstream_request, timeout=60)
  except urllib.error.HTTPError as exc:
    if exc.code in {401, 403, 404}:
      raise HTTPException(status_code=404, detail="Encrypted chunk not found in object storage.") from exc
    raise HTTPException(status_code=502, detail="Upstream chunk fetch failed.") from exc
  except Exception as exc:
    raise HTTPException(status_code=502, detail="Upstream chunk fetch failed.") from exc

  response_headers = {
    "Accept-Ranges": "bytes",
    "Cache-Control": "public, max-age=300",
    "Content-Type": "application/octet-stream",
  }
  content_length = upstream.headers.get("Content-Length")
  if content_length:
    response_headers["Content-Length"] = content_length
  content_range = upstream.headers.get("Content-Range")
  if content_range:
    response_headers["Content-Range"] = content_range

  if upstream_method == "HEAD":
    upstream.close()

    def _empty():
      if False:
        yield b""

    return StreamingResponse(
      _empty(),
      status_code=int(getattr(upstream, "status", 200) or 200),
      headers=response_headers,
      media_type="application/octet-stream",
    )

  def _iter_bytes():
    try:
      while True:
        chunk = upstream.read(64 * 1024)
        if not chunk:
          break
        yield chunk
    finally:
      upstream.close()

  return StreamingResponse(
    _iter_bytes(),
    status_code=int(getattr(upstream, "status", 200) or 200),
    headers=response_headers,
    media_type="application/octet-stream",
  )


def _download_movie_public_delivery_chunk_impl(
  movie_id: str,
  quality_code: str,
  chunk_name: str,
  db: Session | None = Depends(get_db),
  range_header: str | None = None,
  request_method: str = "GET",
) -> FileResponse | StreamingResponse:
  normalized = _normalize_quality_code(quality_code)
  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")
  manifest = _read_content_manifest(movie_id)
  if manifest is None:
    raise HTTPException(status_code=404, detail="Content package not found.")
  quality_files = _quality_manifest_files(manifest, normalized)
  allowed_chunk_names = {
    str(item.get("name") or "")
    for item in quality_files
  }
  if safe_name not in allowed_chunk_names:
    raise HTTPException(status_code=403, detail="Chunk does not belong to this title/quality.")
  package_root = _quality_package_root(movie_id, normalized)
  target_path = package_root / safe_name if package_root.is_dir() else None
  if target_path is None or not target_path.is_file():
    content_root2 = _content_folder_path(movie_id)
    target_path = next((p for p in content_root2.rglob(safe_name) if p.is_file()), None) if content_root2.exists() else None
  if target_path is None or not target_path.is_file():
    r2_url = _r2_chunk_download_url(movie_id, normalized, safe_name)
    if r2_url:
      # Prefer proxy streaming over RedirectResponse so BitComet webseeds work.
      return _proxy_presigned_r2_chunk(
        r2_url,
        range_header=range_header,
        method=request_method,
      )
    raise HTTPException(status_code=404, detail="Encrypted chunk not found.")
  expected_size = None
  for item in quality_files:
    if str(item.get("name") or "") == safe_name:
      try:
        expected_size = int(item.get("encrypted_size") or 0)
      except Exception:
        expected_size = None
      break
  if expected_size is None or expected_size <= 0:
    expected_size = target_path.stat().st_size
  return FileResponse(
    target_path,
    filename=safe_name,
    media_type="application/octet-stream",
    headers={
      "Accept-Ranges": "bytes",
      "Content-Length": str(int(expected_size)),
      "Cache-Control": "public, max-age=604800, immutable",
    },
  )


@router.api_route("/movies/{movie_id}/delivery/public-chunks/{quality_code}/{chunk_name}", methods=["GET", "HEAD"])
def download_movie_public_delivery_chunk(
  movie_id: str,
  quality_code: str,
  chunk_name: str,
  request: Request,
  db: Session | None = Depends(get_db),
  range_header: str | None = Header(default=None, alias="Range"),
) -> FileResponse | StreamingResponse:
  return _download_movie_public_delivery_chunk_impl(
    movie_id,
    quality_code,
    chunk_name,
    db,
    range_header=range_header,
    request_method=request.method,
  )


@router.api_route("/movies/{movie_id}/delivery/public-chunks/{quality_code}/{package_name}/{chunk_name}", methods=["GET", "HEAD"])
def download_movie_public_delivery_chunk_with_package(
  movie_id: str,
  quality_code: str,
  package_name: str,
  chunk_name: str,
  request: Request,
  db: Session | None = Depends(get_db),
  range_header: str | None = Header(default=None, alias="Range"),
) -> FileResponse | StreamingResponse:
  """Serve BEP19 nested webseed paths: ``{base}/{torrent_name}/{chunk}``.

  ``torrent_name`` (info.name) may differ from ``{movie_id}-{quality}.vcnr-pkg``
  when the package was created under an older movie id/title. Chunk membership
  is still enforced inside the shared impl — only reject unsafe path segments.
  """
  safe_package_name = Path(package_name).name
  if (
    safe_package_name != package_name
    or not package_name
    or ".." in package_name
    or "/" in package_name
    or "\\" in package_name
  ):
    raise HTTPException(status_code=404, detail="Torrent package path not found.")
  return _download_movie_public_delivery_chunk_impl(
    movie_id,
    quality_code,
    chunk_name,
    db,
    range_header=range_header,
    request_method=request.method,
  )


@router.api_route("/movies/{movie_id}/delivery/public-chunks/{quality_code}/{package_path:path}", methods=["GET", "HEAD"])
def download_movie_public_delivery_chunk_with_nested_package_path(
  movie_id: str,
  quality_code: str,
  package_path: str,
  request: Request,
  db: Session | None = Depends(get_db),
  range_header: str | None = Header(default=None, alias="Range"),
) -> FileResponse | StreamingResponse:
  safe_path = str(package_path).strip("/")
  if not safe_path:
    raise HTTPException(status_code=400, detail="Invalid chunk path.")
  safe_name = Path(safe_path).name
  return _download_movie_public_delivery_chunk_impl(
    movie_id,
    quality_code,
    safe_name,
    db,
    range_header=range_header,
    request_method=request.method,
  )


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


@router.post("/movies/{movie_id}/swarm/session", response_model=SwarmSessionResponse)
def create_movie_swarm_session(
  movie_id: str,
  payload: SwarmSessionCreateRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSessionResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)

  _cleanup_swarm_sessions()
  session_id = _create_swarm_session_id()
  expires_at = _swarm_session_expiry()
  SWARM_SESSIONS[session_id] = {
    "session_id": session_id,
    "movie_id": movie_id,
    "quality_code": normalized_quality_code,
    "user_id": current_user["id"],
    "device_label": (payload.device_label or "").strip(),
    "verified_chunk_names": "[]",
    "sources_json": "{}",
    "expires_at": expires_at.isoformat(),
    "created_at": datetime.utcnow().isoformat(),
    "updated_at": datetime.utcnow().isoformat(),
  }
  return _serialize_swarm_session(SWARM_SESSIONS[session_id], set(chunk_lookup.keys()))


@router.post("/movies/{movie_id}/swarm/seeders/announce", response_model=SwarmSeederAnnounceResponse)
def announce_movie_swarm_seeder(
  movie_id: str,
  payload: SwarmSeederAnnounceRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSeederAnnounceResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  accepted_chunks = _safe_swarm_chunk_names(payload.available_chunk_names, expected_chunks)
  if not accepted_chunks:
    raise HTTPException(status_code=400, detail="This seeder has no verified chunks for that title quality.")

  _cleanup_swarm_seeders()
  seeder_id = _create_swarm_seeder_id(current_user["id"], payload.device_id)
  previous = SWARM_AVAILABLE_SEEDERS.get(seeder_id, {})
  expires_at = _swarm_seeder_expiry()
  SWARM_AVAILABLE_SEEDERS[seeder_id] = {
    "seeder_id": seeder_id,
    "movie_id": movie_id,
    "quality_code": normalized_quality_code,
    "user_id": current_user["id"],
    "device_id": (payload.device_id or "").strip(),
    "device_label": (payload.device_label or current_user.get("name") or current_user.get("email") or "Seeder phone").strip(),
    "chunk_names": json.dumps(sorted(accepted_chunks)),
    # Always clear any previous receiver assignment when a device republishes itself.
    # The active receiver, if any, will be reassigned immediately below.
    "assigned_session_id": "",
    "cooldown_until": str(previous.get("cooldown_until") or ""),
    "expires_at": expires_at.isoformat(),
    "created_at": str(previous.get("created_at") or datetime.utcnow().isoformat()),
    "updated_at": datetime.utcnow().isoformat(),
  }
  seeders = _swarm_available_seeders(movie_id, normalized_quality_code, expected_chunks)
  _assign_seeders_to_active_receiver_sessions(movie_id, normalized_quality_code, seeders)
  return SwarmSeederAnnounceResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    seeder_id=seeder_id,
    accepted_chunk_count=len(accepted_chunks),
    expected_chunk_count=len(expected_chunks),
    expires_at=expires_at.isoformat(timespec="seconds") + "Z",
  )


@router.post("/movies/{movie_id}/swarm/demand", response_model=SwarmDemandResponse)
def create_movie_swarm_demand(
  movie_id: str,
  payload: SwarmDemandCreateRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmDemandResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  missing_chunks = _safe_swarm_chunk_names(payload.missing_chunk_names, expected_chunks) if payload.missing_chunk_names else expected_chunks
  demand_id = _swarm_demand_key(movie_id, normalized_quality_code)
  previous = SWARM_ACTIVE_DEMANDS.get(demand_id, {})
  receiver_ids = _get_swarm_json_set(previous, "receiver_user_ids") if previous else set()
  receiver_ids.add(current_user["id"])
  existing_missing = _get_swarm_json_set(previous, "missing_chunk_names") if previous else set()
  combined_missing = missing_chunks.union(existing_missing).intersection(expected_chunks)
  expires_at = _swarm_demand_expiry()
  SWARM_ACTIVE_DEMANDS[demand_id] = {
    "demand_id": demand_id,
    "movie_id": movie_id,
    "quality_code": normalized_quality_code,
    "device_label": (payload.device_label or "Receiver demand").strip(),
    "receiver_user_ids": json.dumps(sorted(receiver_ids)),
    "receiver_count": str(len(receiver_ids)),
    "missing_chunk_names": json.dumps(sorted(combined_missing)),
    "expires_at": expires_at.isoformat(),
    "created_at": str(previous.get("created_at") or datetime.utcnow().isoformat()),
    "updated_at": datetime.utcnow().isoformat(),
  }
  return SwarmDemandResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    demand_id=demand_id,
    receiver_count=len(receiver_ids),
    missing_chunk_count=len(combined_missing),
    expires_at=expires_at.isoformat(timespec="seconds") + "Z",
  )


@router.post("/movies/{movie_id}/swarm/demand/check", response_model=SwarmDemandListResponse)
def check_movie_swarm_demand(
  movie_id: str,
  payload: SwarmSeederAnnounceRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmDemandListResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  available_chunks = _safe_swarm_chunk_names(payload.available_chunk_names, expected_chunks)
  return SwarmDemandListResponse(demands=_swarm_demand_entries_for_chunks(movie_id, normalized_quality_code, available_chunks))


@router.get("/movies/{movie_id}/swarm/seeders", response_model=SwarmSeederListResponse)
def list_movie_swarm_seeders(
  movie_id: str,
  quality_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSeederListResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(quality_code)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  seeders = _swarm_available_seeders(movie_id, normalized_quality_code, expected_chunks)
  _assign_seeders_to_active_receiver_sessions(movie_id, normalized_quality_code, seeders)
  return SwarmSeederListResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    expected_chunk_count=len(expected_chunks),
    seeders=seeders,
  )


@router.post("/movies/{movie_id}/swarm/auto-session", response_model=SwarmAutoSessionResponse)
def create_movie_swarm_auto_session(
  movie_id: str,
  payload: SwarmAutoSessionRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmAutoSessionResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  movie_items = persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  receiver_chunks = _safe_swarm_chunk_names(payload.verified_chunk_names, expected_chunks)
  missing_chunks = expected_chunks.difference(receiver_chunks)
  _drop_swarm_receiver_sessions(movie_id, normalized_quality_code, current_user["id"], payload.device_label)
  seeders = _swarm_available_seeders(movie_id, normalized_quality_code, missing_chunks)
  _assign_seeders_to_active_receiver_sessions(movie_id, normalized_quality_code, seeders)

  _cleanup_swarm_sessions()
  session_id = _create_swarm_session_id()
  expires_at = _swarm_session_expiry()
  assigned_seeder_ids = [seeder.source_id for seeder in seeders]
  selected_seeder_id = assigned_seeder_ids[0] if assigned_seeder_ids else None
  SWARM_SESSIONS[session_id] = {
    "session_id": session_id,
    "movie_id": movie_id,
    "quality_code": normalized_quality_code,
    "user_id": current_user["id"],
    "device_label": (payload.device_label or "Auto receiver").strip(),
    "verified_chunk_names": json.dumps(sorted(receiver_chunks)),
    "sources_json": "{}",
    "selected_seeder_id": selected_seeder_id or "",
    "assigned_seeder_ids": json.dumps(assigned_seeder_ids),
    "expires_at": expires_at.isoformat(),
    "created_at": datetime.utcnow().isoformat(),
    "updated_at": datetime.utcnow().isoformat(),
  }
  for seeder_id in assigned_seeder_ids:
    if seeder_id in SWARM_AVAILABLE_SEEDERS:
      SWARM_AVAILABLE_SEEDERS[seeder_id]["assigned_session_id"] = session_id

  return SwarmAutoSessionResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session_id,
    selected_seeder_id=selected_seeder_id,
    assigned_seeder_ids=assigned_seeder_ids,
    expected_chunk_count=len(expected_chunks),
    receiver_verified_chunk_count=len(receiver_chunks),
    seeders=seeders,
    **_swarm_transport_payload(),
  )


@router.get("/movies/{movie_id}/swarm/seeders/{seeder_id}/assignment", response_model=SwarmSeederAssignmentResponse)
def get_movie_swarm_seeder_assignment(
  movie_id: str,
  seeder_id: str,
  quality_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSeederAssignmentResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(quality_code)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _cleanup_swarm_seeders()
  _cleanup_swarm_sessions()
  seeder = SWARM_AVAILABLE_SEEDERS.get(seeder_id)
  if seeder is None or seeder["movie_id"] != movie_id or seeder["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=404, detail="That live seeder is not available.")
  if seeder["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only that seeder device can read this assignment.")
  session_id = seeder.get("assigned_session_id") or ""
  session = SWARM_SESSIONS.get(session_id) if session_id else None
  if session is None:
    return SwarmSeederAssignmentResponse(
      movie_id=movie_id,
      quality_code=normalized_quality_code,
      seeder_id=seeder_id,
      session_id=None,
      receiver_device_label=None,
      receiver_missing_chunk_count=0,
      message="No receiver is assigned yet.",
      **_swarm_transport_payload(),
    )
  expected_chunks = set(_require_swarm_manifest_chunks(movie_id, normalized_quality_code)[1].keys())
  receiver_chunks = _get_swarm_json_set(session, "verified_chunk_names").intersection(expected_chunks)
  return SwarmSeederAssignmentResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    seeder_id=seeder_id,
    session_id=session_id,
    receiver_device_label=session.get("device_label") or "Receiver phone",
    receiver_missing_chunk_count=max(0, len(expected_chunks) - len(receiver_chunks)),
    message="Receiver assignment is ready.",
    **_swarm_transport_payload(),
  )


@router.post("/movies/{movie_id}/swarm/seeders/{seeder_id}/cooldown", response_model=SwarmSeederCooldownResponse)
def cooldown_movie_swarm_seeder(
  movie_id: str,
  seeder_id: str,
  quality_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSeederCooldownResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  normalized_quality_code = _normalize_quality_code(quality_code)
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _cleanup_swarm_seeders()
  seeder = SWARM_AVAILABLE_SEEDERS.get(seeder_id)
  if seeder is None or seeder["movie_id"] != movie_id or seeder["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=404, detail="That live seeder is not available.")
  cooldown_until = _swarm_seeder_cooldown_expiry()
  seeder["cooldown_until"] = cooldown_until.isoformat()
  seeder["updated_at"] = datetime.utcnow().isoformat()
  return SwarmSeederCooldownResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    seeder_id=seeder_id,
    cooldown_until=cooldown_until.isoformat(timespec="seconds") + "Z",
    message="Seeder moved to cooldown after receiver timeout.",
  )


@router.post("/movies/{movie_id}/swarm/inventory", response_model=SwarmInventoryResponse)
def update_movie_swarm_inventory(
  movie_id: str,
  payload: SwarmInventoryRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmInventoryResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(payload.session_id)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  if session["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the receiver device can update this swarm inventory.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  accepted_chunks = _safe_swarm_chunk_names(payload.verified_chunk_names, expected_chunks)
  _set_swarm_json_set(session, "verified_chunk_names", accepted_chunks)
  if payload.device_label:
    session["device_label"] = payload.device_label.strip()
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return SwarmInventoryResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    accepted_chunk_count=len(accepted_chunks),
    expected_chunk_count=len(expected_chunks),
    missing_chunk_count=max(0, len(expected_chunks) - len(accepted_chunks)),
  )


@router.post("/movies/{movie_id}/swarm/sources", response_model=SwarmSourcePublishResponse)
def publish_movie_swarm_source(
  movie_id: str,
  payload: SwarmSourcePublishRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSourcePublishResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(payload.session_id)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  accepted_chunks = _safe_swarm_chunk_names(payload.available_chunk_names, expected_chunks)
  source_id = f"user:{current_user['id']}"
  sources = _get_swarm_sources(session)
  sources[source_id] = {
    "source_id": source_id,
    "source_type": "peer_relay",
    "user_id": current_user["id"],
    "device_label": (payload.device_label or current_user.get("name") or current_user.get("email") or "Peer device").strip(),
    "chunk_names": sorted(accepted_chunks),
    "relay_chunk_names": sources.get(source_id, {}).get("relay_chunk_names", "[]"),
    "last_seen_at": datetime.utcnow().isoformat(),
  }
  _set_swarm_sources(session, sources)
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return SwarmSourcePublishResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    source_id=source_id,
    accepted_chunk_count=len(accepted_chunks),
    expected_chunk_count=len(expected_chunks),
  )


@router.get("/movies/{movie_id}/swarm/sources", response_model=SwarmSourcesResponse)
def get_movie_swarm_sources(
  movie_id: str,
  quality_code: str,
  session_id: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSourcesResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(session_id)
  normalized_quality_code = _normalize_quality_code(quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  if session["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the receiver device can discover sources for this swarm session.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  expected_chunks = set(chunk_lookup.keys())
  receiver_chunks = _get_swarm_json_set(session, "verified_chunk_names").intersection(expected_chunks)
  missing_chunks = expected_chunks.difference(receiver_chunks)
  sources: list[SwarmSourceEntry] = []
  server_source = _server_swarm_source(movie_id, missing_chunks)
  if server_source is not None:
    sources.append(server_source)
  for raw_source in _get_swarm_sources(session).values():
    source_chunks = set(raw_source.get("chunk_names") or [])
    if str(raw_source.get("source_type") or "") == "peer_relay":
      source_chunks = source_chunks.intersection(_get_swarm_json_set(raw_source, "relay_chunk_names"))
    chunk_names = sorted(source_chunks.intersection(missing_chunks))
    if not chunk_names:
      continue
    sources.append(
      SwarmSourceEntry(
        source_id=str(raw_source.get("source_id") or ""),
        source_type=str(raw_source.get("source_type") or "peer"),
        user_id=str(raw_source.get("user_id") or "") or None,
        device_label=str(raw_source.get("device_label") or "") or None,
        chunk_names=chunk_names,
        chunk_count=len(chunk_names),
        last_seen_at=str(raw_source.get("last_seen_at") or "") or None,
      )
    )
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return SwarmSourcesResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    expected_chunk_count=len(expected_chunks),
    receiver_verified_chunk_count=len(receiver_chunks),
    missing_chunk_count=len(missing_chunks),
    sources=sources,
  )


@router.get("/movies/{movie_id}/swarm/manifest", response_model=DeliveryManifestResponse)
def get_movie_swarm_manifest(
  movie_id: str,
  quality_code: str,
  session_id: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> DeliveryManifestResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(session_id)
  normalized_quality_code = _normalize_quality_code(quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  if session["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the receiver device can access this swarm manifest.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  manifest, _chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return DeliveryManifestResponse(**_viewer_content_manifest_payload(_swarm_manifest_with_integrity(movie_id, manifest, normalized_quality_code), normalized_quality_code))


@router.post("/movies/{movie_id}/swarm/webrtc/offer", response_model=SwarmSignalActionResponse)
def publish_movie_swarm_webrtc_offer(
  movie_id: str,
  payload: SwarmSignalOfferRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSignalActionResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm WebRTC signaling.")
  session = _get_swarm_session_or_404(payload.session_id)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  if session["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the receiver device can publish this WebRTC offer.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  normalized_seeder_id = _normalize_swarm_seeder_id(payload.seeder_id)
  if normalized_seeder_id:
    link = _get_or_create_swarm_peer_link(session, normalized_seeder_id)
    link["offer"] = payload.offer
    link["answer"] = None
    link["receiver_candidates"] = []
    link["sender_candidates"] = []
    link["updated_at"] = datetime.utcnow().isoformat()
    _set_swarm_peer_link(session, normalized_seeder_id, link)
  else:
    _set_swarm_signal_json(session, "webrtc_offer_json", payload.offer)
    session["webrtc_answer_json"] = ""
    session["webrtc_receiver_candidates_json"] = "[]"
    session["webrtc_sender_candidates_json"] = "[]"
  _touch_swarm_session(session)
  return SwarmSignalActionResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    message="WebRTC receiver offer published.",
    updated_at=datetime.fromisoformat(session["updated_at"]).isoformat(timespec="seconds") + "Z",
  )


@router.post("/movies/{movie_id}/swarm/webrtc/answer", response_model=SwarmSignalActionResponse)
def publish_movie_swarm_webrtc_answer(
  movie_id: str,
  payload: SwarmSignalAnswerRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSignalActionResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm WebRTC signaling.")
  session = _get_swarm_session_or_404(payload.session_id)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  normalized_seeder_id = _normalize_swarm_seeder_id(payload.seeder_id)
  if normalized_seeder_id:
    _require_owned_swarm_seeder(movie_id, normalized_quality_code, normalized_seeder_id, current_user["id"])
    link = _get_or_create_swarm_peer_link(session, normalized_seeder_id)
    link["answer"] = payload.answer
    link["updated_at"] = datetime.utcnow().isoformat()
    _set_swarm_peer_link(session, normalized_seeder_id, link)
  else:
    _set_swarm_signal_json(session, "webrtc_answer_json", payload.answer)
  _touch_swarm_session(session)
  return SwarmSignalActionResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    message="WebRTC sender answer published.",
    updated_at=datetime.fromisoformat(session["updated_at"]).isoformat(timespec="seconds") + "Z",
  )


@router.post("/movies/{movie_id}/swarm/webrtc/candidate", response_model=SwarmSignalActionResponse)
def publish_movie_swarm_webrtc_candidate(
  movie_id: str,
  payload: SwarmSignalCandidateRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSignalActionResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm WebRTC signaling.")
  session = _get_swarm_session_or_404(payload.session_id)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  normalized_seeder_id = _normalize_swarm_seeder_id(payload.seeder_id)
  if normalized_seeder_id:
    if payload.role == "sender":
      _require_owned_swarm_seeder(movie_id, normalized_quality_code, normalized_seeder_id, current_user["id"])
    elif session["user_id"] != current_user["id"]:
      raise HTTPException(status_code=403, detail="Only the receiver device can publish this WebRTC candidate.")
    link = _get_or_create_swarm_peer_link(session, normalized_seeder_id)
    candidate_key = "receiver_candidates" if payload.role == "receiver" else "sender_candidates"
    candidate_count = _append_swarm_peer_candidate(link, candidate_key, payload.candidate)
    _set_swarm_peer_link(session, normalized_seeder_id, link)
  else:
    candidate_key = "webrtc_receiver_candidates_json" if payload.role == "receiver" else "webrtc_sender_candidates_json"
    candidate_count = _append_swarm_signal_candidate(session, candidate_key, payload.candidate)
  _touch_swarm_session(session)
  return SwarmSignalActionResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    message=f"WebRTC {payload.role} candidate accepted ({candidate_count}).",
    updated_at=datetime.fromisoformat(session["updated_at"]).isoformat(timespec="seconds") + "Z",
  )


@router.get("/movies/{movie_id}/swarm/webrtc/state", response_model=SwarmSignalStateResponse)
def get_movie_swarm_webrtc_state(
  movie_id: str,
  quality_code: str,
  session_id: str,
  seeder_id: str | None = None,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmSignalStateResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm WebRTC signaling.")
  session = _get_swarm_session_or_404(session_id)
  normalized_quality_code = _normalize_quality_code(quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  normalized_seeder_id = _normalize_swarm_seeder_id(seeder_id)
  if normalized_seeder_id and session["user_id"] != current_user["id"]:
    _require_owned_swarm_seeder(movie_id, normalized_quality_code, normalized_seeder_id, current_user["id"])
  _touch_swarm_session(session)
  return _serialize_swarm_signal_state(session, normalized_seeder_id or None)


@router.get("/movies/{movie_id}/swarm/chunks/{chunk_name}")
def download_movie_swarm_chunk(
  movie_id: str,
  chunk_name: str,
  quality_code: str,
  session_id: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> FileResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(session_id)
  normalized_quality_code = _normalize_quality_code(quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  if session["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the receiver device can download chunks for this swarm session.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  _manifest, chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")
  if safe_name not in chunk_lookup:
    raise HTTPException(status_code=403, detail="This chunk does not belong to the swarm title quality.")
  package_root = _quality_package_root(movie_id, normalized_quality_code)
  target_path = package_root / safe_name if package_root.is_dir() else None
  if target_path is None or not target_path.is_file():
    content_root = _content_folder_path(movie_id)
    target_path = next((file_path for file_path in content_root.rglob(safe_name) if file_path.is_file()), None) if content_root.exists() else None
  if target_path is None or not target_path.is_file():
    r2_url = _r2_chunk_download_url(movie_id, normalized_quality_code, safe_name)
    if r2_url:
      session["expires_at"] = _swarm_session_expiry().isoformat()
      session["updated_at"] = datetime.utcnow().isoformat()
      return RedirectResponse(r2_url)
    raise HTTPException(status_code=404, detail="Encrypted chunk not found.")
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return FileResponse(target_path, filename=safe_name, media_type="application/octet-stream")


@router.post("/movies/{movie_id}/swarm/sources/{source_id}/chunks/{chunk_name}", response_model=SwarmRelayChunkUploadResponse)
async def upload_movie_swarm_relay_chunk(
  movie_id: str,
  source_id: str,
  chunk_name: str,
  quality_code: str = Form(...),
  session_id: str = Form(...),
  file: UploadFile = File(...),
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> SwarmRelayChunkUploadResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(session_id)
  normalized_quality_code = _normalize_quality_code(quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  sources = _get_swarm_sources(session)
  source = sources.get(source_id)
  if source is None:
    raise HTTPException(status_code=404, detail="Publish this source inventory before uploading relay chunks.")
  if str(source.get("user_id") or "") != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the published source device can upload these chunks.")

  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")
  manifest, _chunk_lookup = _require_swarm_manifest_chunks(movie_id, normalized_quality_code)
  enriched_manifest = _swarm_manifest_with_integrity(movie_id, manifest, normalized_quality_code)
  chunk_lookup = _chunk_manifest_lookup(enriched_manifest, normalized_quality_code)
  chunk_record = chunk_lookup.get(safe_name)
  if chunk_record is None or safe_name not in set(source.get("chunk_names") or []):
    raise HTTPException(status_code=403, detail="This chunk does not belong to the published swarm source.")

  target_folder = _swarm_relay_source_folder(session["session_id"], source_id)
  target_folder.mkdir(parents=True, exist_ok=True)
  target_path = target_folder / safe_name
  with target_path.open("wb") as buffer:
    while True:
      content = await file.read(1024 * 1024)
      if not content:
        break
      buffer.write(content)

  uploaded_bytes = target_path.read_bytes()
  expected_size = int(chunk_record.get("encrypted_size") or 0)
  expected_sha256 = str(chunk_record.get("encrypted_sha256") or "").strip().lower()
  expected_md5 = str(chunk_record.get("encrypted_md5") or "").strip().lower()
  if len(uploaded_bytes) != expected_size:
    target_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail=f"Uploaded chunk size mismatch for {safe_name}.")
  if expected_sha256 and hashlib.sha256(uploaded_bytes).hexdigest().lower() != expected_sha256:
    target_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail=f"Uploaded chunk checksum mismatch for {safe_name}.")
  if not expected_sha256 and hashlib.md5(uploaded_bytes).hexdigest().lower() != expected_md5:
    target_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail=f"Uploaded chunk checksum mismatch for {safe_name}.")

  relay_chunks = _get_swarm_json_set(source, "relay_chunk_names")
  relay_chunks.add(safe_name)
  source["relay_chunk_names"] = json.dumps(sorted(relay_chunks))
  source["last_seen_at"] = datetime.utcnow().isoformat()
  sources[source_id] = source
  _set_swarm_sources(session, sources)
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return SwarmRelayChunkUploadResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    session_id=session["session_id"],
    source_id=source_id,
    chunk_name=safe_name,
    relay_ready_chunk_count=len(relay_chunks),
  )


@router.get("/movies/{movie_id}/swarm/sources/{source_id}/chunks/{chunk_name}")
def download_movie_swarm_relay_chunk(
  movie_id: str,
  source_id: str,
  chunk_name: str,
  quality_code: str,
  session_id: str,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> FileResponse:
  if db is None:
    raise HTTPException(status_code=503, detail="Database is required for swarm tracker control.")
  session = _get_swarm_session_or_404(session_id)
  normalized_quality_code = _normalize_quality_code(quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That swarm session belongs to a different title quality.")
  if session["user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Only the receiver device can download chunks for this swarm session.")
  _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
  sources = _get_swarm_sources(session)
  source = sources.get(source_id)
  if source is None:
    raise HTTPException(status_code=404, detail="Swarm source not found.")
  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")
  relay_chunks = _get_swarm_json_set(source, "relay_chunk_names")
  if safe_name not in relay_chunks:
    raise HTTPException(status_code=404, detail="Relayed swarm chunk is not available yet.")
  target_path = _swarm_relay_source_folder(session["session_id"], source_id) / safe_name
  if not target_path.exists() or not target_path.is_file():
    raise HTTPException(status_code=404, detail="Relayed swarm chunk file was not found.")
  session["expires_at"] = _swarm_session_expiry().isoformat()
  session["updated_at"] = datetime.utcnow().isoformat()
  return FileResponse(target_path, filename=safe_name, media_type="application/octet-stream")


@router.post("/movies/{movie_id}/transfer/pairing", response_model=TransferPairingCreateResponse)
def create_movie_transfer_pairing(
  movie_id: str,
  payload: TransferPairingCreateRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> TransferPairingCreateResponse:
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  movie_items = (
    persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
    if db
    else demo_store.list_movies(include_archived=True, viewer_user_id=current_user["id"])
  )
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  if db is not None:
    _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)

  _cleanup_transfer_pairing_sessions()
  existing_session = next(
    (
      session
      for session in TRANSFER_PAIRING_SESSIONS.values()
      if session["movie_id"] == movie_id
      and session["quality_code"] == normalized_quality_code
      and session["receiver_user_id"] == current_user["id"]
      and session["session_status"] in {"waiting_for_sender", "paired", "syncing"}
    ),
    None,
  )
  if existing_session is not None:
    expires_at = _transfer_pairing_expiry()
    existing_session["expires_at"] = expires_at.isoformat()
    return TransferPairingCreateResponse(
      movie_id=movie_id,
      quality_code=normalized_quality_code,
      pairing_code=existing_session["pairing_code"],
      expires_at=expires_at.isoformat(timespec="seconds") + "Z",
      session_status=existing_session["session_status"],
      receiver_user_id=current_user["id"],
    )
  pairing_code = _create_transfer_pairing_code()
  expires_at = _transfer_pairing_expiry()
  TRANSFER_PAIRING_SESSIONS[pairing_code] = {
    "movie_id": movie_id,
    "quality_code": normalized_quality_code,
    "pairing_code": pairing_code,
    "receiver_user_id": current_user["id"],
    "sender_user_id": "",
    "session_status": "waiting_for_sender",
    "expires_at": expires_at.isoformat(),
    "sender_chunk_names": "[]",
    "receiver_chunk_names": "[]",
    "relay_chunk_names": "[]",
    "manifest_json": "",
  }
  return TransferPairingCreateResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    pairing_code=pairing_code,
    expires_at=expires_at.isoformat(timespec="seconds") + "Z",
    session_status="waiting_for_sender",
    receiver_user_id=current_user["id"],
  )


@router.post("/movies/{movie_id}/transfer/pairing/join", response_model=TransferPairingJoinResponse)
def join_movie_transfer_pairing(
  movie_id: str,
  payload: TransferPairingJoinRequest,
  current_user: dict[str, str] = Depends(get_current_user),
  db: Session | None = Depends(get_db),
) -> TransferPairingJoinResponse:
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  movie_items = (
    persistence.list_movies(db, include_archived=True, viewer_user_id=current_user["id"])
    if db
    else demo_store.list_movies(include_archived=True, viewer_user_id=current_user["id"])
  )
  movie = next((item for item in movie_items if item["id"] == movie_id), None)
  if movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")
  _require_delivery_entitlement(movie)
  if db is not None:
    sender_reservation = _require_delivery_reservation(db, movie_id, current_user["id"], normalized_quality_code)
    sender_enrollment = _get_or_create_delivery_enrollment(db, movie_id, current_user["id"], sender_reservation.quality_code or normalized_quality_code)
    if not (sender_enrollment.local_encrypted_path or "").strip():
      raise HTTPException(status_code=400, detail="This sender device does not have a registered local VCNR package yet.")

  session = _get_transfer_pairing_session_or_404(payload.pairing_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title quality.")
  if session["receiver_user_id"] != current_user["id"]:
    raise HTTPException(status_code=403, detail="Phase 1 pairing currently works only for the same signed-in account on both devices.")

  session["sender_user_id"] = current_user["id"]
  session["session_status"] = "paired"
  expires_at = _transfer_pairing_expiry()
  session["expires_at"] = expires_at.isoformat()

  return TransferPairingJoinResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    pairing_code=session["pairing_code"],
    expires_at=expires_at.isoformat(timespec="seconds") + "Z",
    session_status="paired",
    receiver_user_id=session["receiver_user_id"],
    sender_user_id=current_user["id"],
    message="Pairing session confirmed. The next step is direct chunk discovery and sync between both phones.",
  )


@router.get("/movies/{movie_id}/transfer/pairing/status", response_model=TransferPairingStatusResponse)
def get_movie_transfer_pairing_status(
  movie_id: str,
  pairing_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
) -> TransferPairingStatusResponse:
  session = _get_transfer_pairing_session_or_404(pairing_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if current_user["id"] not in {session["receiver_user_id"], session.get("sender_user_id") or ""}:
    raise HTTPException(status_code=403, detail="You do not have access to this transfer session.")
  return _serialize_transfer_status(session)


@router.post("/movies/{movie_id}/transfer/pairing/inventory", response_model=TransferPairingInventoryResponse)
def update_movie_transfer_pairing_inventory(
  movie_id: str,
  payload: TransferPairingInventoryRequest,
  current_user: dict[str, str] = Depends(get_current_user),
) -> TransferPairingInventoryResponse:
  session = _get_transfer_pairing_session_or_404(payload.pairing_code)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title quality.")
  expected_chunks = _get_transfer_expected_chunk_names(session)
  reported_chunks = {Path(item).name for item in payload.chunk_names if item.strip() and Path(item).name == item.strip()}
  if expected_chunks:
    reported_chunks = reported_chunks.intersection(expected_chunks)
  if payload.role == "receiver":
    if current_user["id"] != session["receiver_user_id"]:
      raise HTTPException(status_code=403, detail="Only the receiver device can update receiver inventory.")
    _set_transfer_chunk_names(session, "receiver_chunk_names", reported_chunks)
  else:
    if current_user["id"] != (session.get("sender_user_id") or ""):
      raise HTTPException(status_code=403, detail="Only the sender device can update sender inventory.")
    _set_transfer_chunk_names(session, "sender_chunk_names", reported_chunks)
    if session["session_status"] == "paired":
      session["session_status"] = "syncing"
  sender_chunks = expected_chunks or _get_transfer_chunk_names(session, "sender_chunk_names")
  receiver_chunks = _get_transfer_chunk_names(session, "receiver_chunk_names")
  if expected_chunks:
    receiver_chunks = receiver_chunks.intersection(expected_chunks)
  missing_chunks = sender_chunks.difference(receiver_chunks)
  if sender_chunks and not missing_chunks:
    session["session_status"] = "completed"
    _delete_transfer_pairing_files(session["pairing_code"])
  return TransferPairingInventoryResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    pairing_code=session["pairing_code"],
    role=payload.role,
    chunk_count=len(sender_chunks if payload.role == "sender" else receiver_chunks),
    missing_chunk_count=len(missing_chunks),
    session_status=session["session_status"],
  )


@router.post("/movies/{movie_id}/transfer/pairing/manifest", response_model=TransferPairingManifestResponse)
def upload_movie_transfer_pairing_manifest(
  movie_id: str,
  payload: TransferPairingManifestRequest,
  current_user: dict[str, str] = Depends(get_current_user),
) -> TransferPairingManifestResponse:
  session = _get_transfer_pairing_session_or_404(payload.pairing_code)
  normalized_quality_code = _normalize_quality_code(payload.quality_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if session["quality_code"] != normalized_quality_code:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title quality.")
  if current_user["id"] != (session.get("sender_user_id") or ""):
    raise HTTPException(status_code=403, detail="Only the sender device can upload the transfer manifest.")

  manifest = payload.manifest if isinstance(payload.manifest, dict) else {}
  files = manifest.get("files", []) if isinstance(manifest.get("files", []), list) else []
  _validate_transfer_manifest_integrity(manifest, normalized_quality_code)
  session["manifest_json"] = json.dumps(manifest)
  folder = _transfer_pairing_folder(session["pairing_code"])
  folder.mkdir(parents=True, exist_ok=True)
  (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
  return TransferPairingManifestResponse(
    movie_id=movie_id,
    quality_code=normalized_quality_code,
    pairing_code=session["pairing_code"],
    session_status=session["session_status"],
    manifest_available=True,
    chunk_count=len(files),
  )


@router.get("/movies/{movie_id}/transfer/pairing/manifest", response_model=DeliveryManifestResponse)
def get_movie_transfer_pairing_manifest(
  movie_id: str,
  pairing_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
) -> DeliveryManifestResponse:
  session = _get_transfer_pairing_session_or_404(pairing_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if current_user["id"] not in {session["receiver_user_id"], session.get("sender_user_id") or ""}:
    raise HTTPException(status_code=403, detail="You do not have access to this transfer session.")
  if not session.get("manifest_json"):
    raise HTTPException(status_code=404, detail="Transfer manifest is not available yet.")
  manifest = json.loads(session["manifest_json"])
  return DeliveryManifestResponse(**_viewer_content_manifest_payload(manifest, session["quality_code"]))


@router.post("/movies/{movie_id}/transfer/pairing/chunks/{chunk_name}", response_model=TransferRelayChunkUploadResponse)
async def upload_movie_transfer_pairing_chunk(
  movie_id: str,
  chunk_name: str,
  pairing_code: str = Form(...),
  file: UploadFile = File(...),
  current_user: dict[str, str] = Depends(get_current_user),
) -> TransferRelayChunkUploadResponse:
  session = _get_transfer_pairing_session_or_404(pairing_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if current_user["id"] != (session.get("sender_user_id") or ""):
    raise HTTPException(status_code=403, detail="Only the sender device can upload transfer chunks.")
  if not session.get("manifest_json"):
    raise HTTPException(status_code=400, detail="Upload the sender manifest before relaying chunks.")

  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")

  manifest = _get_transfer_manifest(session)
  chunk_lookup = _validate_transfer_manifest_integrity(manifest, session["quality_code"])
  chunk_record = chunk_lookup.get(safe_name)
  if chunk_record is None:
    raise HTTPException(status_code=403, detail="This chunk does not belong to the paired title quality.")

  folder = _transfer_pairing_folder(session["pairing_code"]) / "chunks"
  folder.mkdir(parents=True, exist_ok=True)
  target_path = folder / safe_name
  with target_path.open("wb") as buffer:
    while True:
      content = await file.read(1024 * 1024)
      if not content:
        break
      buffer.write(content)
  uploaded_bytes = target_path.read_bytes()
  expected_size = int(chunk_record.get("encrypted_size") or 0)
  expected_sha256 = str(chunk_record.get("encrypted_sha256") or "").strip().lower()
  expected_md5 = str(chunk_record.get("encrypted_md5") or "").strip().lower()
  if len(uploaded_bytes) != expected_size:
    target_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail=f"Uploaded chunk size mismatch for {safe_name}.")
  if expected_sha256 and hashlib.sha256(uploaded_bytes).hexdigest().lower() != expected_sha256:
    target_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail=f"Uploaded chunk checksum mismatch for {safe_name}.")
  if not expected_sha256 and hashlib.md5(uploaded_bytes).hexdigest().lower() != expected_md5:
    target_path.unlink(missing_ok=True)
    raise HTTPException(status_code=400, detail=f"Uploaded chunk checksum mismatch for {safe_name}.")
  relay_chunks = _get_transfer_chunk_names(session, "relay_chunk_names")
  relay_chunks.add(safe_name)
  _set_transfer_chunk_names(session, "relay_chunk_names", relay_chunks)
  session["session_status"] = "syncing"
  return TransferRelayChunkUploadResponse(
    movie_id=movie_id,
    quality_code=session["quality_code"],
    pairing_code=session["pairing_code"],
    chunk_name=safe_name,
    relay_ready_chunk_count=len(relay_chunks),
    session_status=session["session_status"],
  )


@router.get("/movies/{movie_id}/transfer/pairing/chunks/{chunk_name}")
def download_movie_transfer_pairing_chunk(
  movie_id: str,
  chunk_name: str,
  pairing_code: str,
  current_user: dict[str, str] = Depends(get_current_user),
) -> FileResponse:
  session = _get_transfer_pairing_session_or_404(pairing_code)
  if session["movie_id"] != movie_id:
    raise HTTPException(status_code=400, detail="That pairing code belongs to a different title.")
  if current_user["id"] not in {session["receiver_user_id"], session.get("sender_user_id") or ""}:
    raise HTTPException(status_code=403, detail="You do not have access to this transfer session.")
  safe_name = Path(chunk_name).name
  if safe_name != chunk_name:
    raise HTTPException(status_code=400, detail="Invalid chunk name.")
  target_path = _transfer_pairing_folder(session["pairing_code"]) / "chunks" / safe_name
  if not target_path.exists() or not target_path.is_file():
    raise HTTPException(status_code=404, detail="Relayed transfer chunk not found yet.")
  return FileResponse(target_path, filename=safe_name, media_type="application/octet-stream")


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
  if r2_enabled():
    upload_media_object(media_object_key(movie_id, "gallery", filename), target_path.read_bytes())
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
  if r2_enabled():
    upload_media_object(media_object_key(movie_id, "music", filename), target_path.read_bytes())
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


@router.post("/admin/push/test", response_model=AdminActionResponse)
def admin_push_test(
  payload: AdminPushTestRequest | None = None,
  db: Session | None = Depends(get_db),
  _: dict[str, str] = Depends(require_admin),
) -> AdminActionResponse:
  """Broadcast a test push to every registered device token."""
  title = "Cine Vault Test"
  body = "Push notifications are working!"
  if payload:
    title = (payload.title or title).strip()[:100] or title
    body = (payload.message or body).strip()[:200] or body

  if db:
    tokens = persistence._list_all_active_push_tokens(db)
  else:
    tokens = demo_store.list_all_active_push_tokens()

  unique_tokens = sorted({token for token_list in tokens.values() for token in token_list})
  if not unique_tokens:
    summary = persistence.get_admin_summary(db) if db else demo_store.get_admin_summary()
    return AdminActionResponse(
      message="No registered devices found. Open the app and sign in first.",
      summary=AdminSummaryResponse(**summary),
    )

  messages = [build_push_message(token, title, body, {"notification_type": "test_push"}) for token in unique_tokens]
  send_push_messages_async(messages)
  summary = persistence.get_admin_summary(db) if db else demo_store.get_admin_summary()
  return AdminActionResponse(
    message=f"Test push queued for {len(unique_tokens)} device(s).",
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
  deleted_movie = persistence.delete_movie_permanently(db, movie_id) if db else demo_store.delete_movie_permanently(movie_id)
  if deleted_movie is None:
    raise HTTPException(status_code=404, detail="Movie not found.")

  cleanup_warning: str | None = None
  delete_movie_prefix(movie_id)
  try:
    _delete_movie_media_folder(movie_id)
  except HTTPException as error:
    if error.status_code == 409:
      cleanup_warning = (
        f'"{movie["title"]}" was deleted from VCNR, but Windows is still holding its media folder open. '
        "Close File Explorer, BitComet, video players, or any process using that title, then remove the leftover folder later."
      )
    else:
      raise

  if cleanup_warning:
    return {
      "message": cleanup_warning,
      "media_cleanup_pending": True,
      "media_folder": str((LIBRARY_MEDIA_ROOT / movie_id).resolve()),
    }

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
