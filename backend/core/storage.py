from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

MEDIA_KIND_FOLDERS = {
  "posters": "posters",
  "trailer": "trailers",
  "gallery": "gallery",
  "music": "music",
  "content": "content",
}


def _r2_enabled() -> bool:
  settings = get_settings()
  return bool(
    settings.r2_account_id
    and settings.r2_access_key_id
    and settings.r2_secret_access_key
    and settings.r2_bucket_name
  )


def r2_enabled() -> bool:
  """Public alias so routes and tooling can branch on R2 availability."""
  return _r2_enabled()


@lru_cache(maxsize=1)
def _get_r2_client():
  """Lazily build the boto3 S3 client pointed at Cloudflare R2."""
  settings = get_settings()
  import boto3
  from botocore.config import Config

  return boto3.client(
    "s3",
    endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    region_name="auto",
    config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
  )


# ---------------------------------------------------------------------------
# Object key layout
#
# The R2 bucket mirrors the previous local media/library layout so existing
# torrent webseed paths and viewer code keep working:
#
#   {movie_id}/posters/{vertical|horizontal}/{filename}
#   {movie_id}/trailers/{filename}
#   {movie_id}/gallery/{filename}
#   {movie_id}/music/{filename}
#   {movie_id}/content/manifest.json
#   {movie_id}/content/{quality}.torrent
#   {movie_id}/content/{chunk_name}            (encrypted content chunks)
# ---------------------------------------------------------------------------


def media_object_key(
  movie_id: str,
  kind: str,
  filename: str,
  orientation: str | None = None,
) -> str:
  """Return the R2 object key for a media asset.

  ``kind`` accepts the API kind values (posters, trailer, gallery, music,
  content).  Trailer is normalized to the ``trailers`` folder.
  """
  folder = MEDIA_KIND_FOLDERS.get(kind, kind)
  if kind == "posters":
    orientation_part = f"{orientation}/" if orientation else ""
    return f"{movie_id}/{folder}/{orientation_part}{filename}"
  return f"{movie_id}/{folder}/{filename}"


def _object_key(movie_id: str, chunk_name: str) -> str:
  """Backwards-compatible chunk key: ``{movie_id}/content/{chunk_name}``."""
  return f"{movie_id}/content/{chunk_name}"


def _put_object(key: str, body: bytes, content_type: str | None = None) -> None:
  if content_type is None:
    content_type = "application/octet-stream"
  client = _get_r2_client()
  client.put_object(
    Bucket=get_settings().r2_bucket_name,
    Key=key,
    Body=body,
    ContentType=content_type,
  )


def _get_object(key: str) -> bytes | None:
  client = _get_r2_client()
  try:
    response = client.get_object(
      Bucket=get_settings().r2_bucket_name,
      Key=key,
    )
    return response["Body"].read()
  except Exception:
    return None


def _object_exists(key: str) -> bool:
  client = _get_r2_client()
  try:
    client.head_object(
      Bucket=get_settings().r2_bucket_name,
      Key=key,
    )
    return True
  except Exception:
    return False


def _delete_object(key: str) -> None:
  client = _get_r2_client()
  client.delete_object(
    Bucket=get_settings().r2_bucket_name,
    Key=key,
  )


# ---------------------------------------------------------------------------
# Content chunk helpers (existing API, now layered over the generic layer)
# ---------------------------------------------------------------------------


def content_package_object_key(movie_id: str, package_name: str, chunk_name: str) -> str | None:
  """Return the BEP19 package-nested R2 key for a chunk, or None when unsafe.

  Multi-file web seed clients (BEP19: BitComet, libtorrent, qBittorrent) build
  chunk URLs as ``url-list base + torrent ``name`` folder + file path``.  When
  the url-list base is ``{movie_id}/content/`` and the torrent ``name`` is the
  package folder, the key those clients request is the mirrored
  ``{movie_id}/content/{package_name}/{chunk_name}`` layout.
  """
  safe_package = Path(package_name).name
  safe_chunk = Path(chunk_name).name
  if not safe_package or safe_package != package_name:
    return None
  if not safe_chunk or safe_chunk != chunk_name:
    return None
  return f"{movie_id}/content/{safe_package}/{safe_chunk}"


def upload_chunk(movie_id: str, chunk_name: str, data: bytes, package_name: str | None = None) -> None:
  """Upload an encrypted chunk to R2 when configured, otherwise no-op.

  The caller is responsible for writing the chunk to local disk as well;
  this function only mirrors the chunk to R2 for permanent storage.

  When ``package_name`` is given, the chunk is also mirrored under the BEP19
  package-nested key ``content/{package_name}/{chunk_name}`` so multi-file web
  seed clients (which append the torrent ``name`` folder to the url-list base)
  can fetch the chunk directly from the CDN.
  """
  if not _r2_enabled():
    return
  try:
    _put_object(_object_key(movie_id, chunk_name), data)
    if package_name:
      nested_key = content_package_object_key(movie_id, package_name, chunk_name)
      if nested_key:
        _put_object(nested_key, data)
  except Exception:
    logger.exception("R2 upload failed for %s/%s", movie_id, chunk_name)


def copy_chunk_to_package(movie_id: str, package_name: str, chunk_name: str) -> bool:
  """Server-side copy a flat chunk into the BEP19 package-nested key.

  Backfill for chunks uploaded before the package-nested layout existed.  Uses
  R2's S3 copy (no bytes cross the client).  Returns True when R2 handled the
  copy, False when R2 is not configured or the copy failed.
  """
  if not _r2_enabled():
    return False
  nested_key = content_package_object_key(movie_id, package_name, chunk_name)
  if nested_key is None:
    return False
  try:
    client = _get_r2_client()
    client.copy_object(
      Bucket=get_settings().r2_bucket_name,
      Key=nested_key,
      CopySource={"Bucket": get_settings().r2_bucket_name, "Key": _object_key(movie_id, chunk_name)},
    )
    return True
  except Exception:
    logger.exception("R2 chunk package copy failed for %s/%s -> %s", movie_id, chunk_name, package_name)
    return False


def chunk_has_package_copy(movie_id: str, package_name: str, chunk_name: str) -> bool:
  """Return True when the BEP19 package-nested copy already exists in R2."""
  if not _r2_enabled():
    return False
  nested_key = content_package_object_key(movie_id, package_name, chunk_name)
  if nested_key is None:
    return False
  return _object_exists(nested_key)


def chunk_exists(movie_id: str, chunk_name: str) -> bool:
  """Return True if the chunk exists in R2 (when configured)."""
  if not _r2_enabled():
    return False
  return _object_exists(_object_key(movie_id, chunk_name))


def chunk_public_url(movie_id: str, chunk_name: str) -> str | None:
  """Return the public R2 URL for a chunk, or None if R2 is not configured."""
  return media_public_url(_object_key(movie_id, chunk_name))


def chunk_webseed_base(movie_id: str) -> str | None:
  """Return the R2 webseed base URL for a movie, or None if R2 is not configured.

  Torrent clients append the chunk filename (torrent file path) to this base,
  matching the public R2 object layout ``{movie_id}/content/<chunk_name>``.
  """
  settings = get_settings()
  if not settings.r2_public_base_url:
    return None
  return f"{settings.r2_public_base_url}/{movie_id}/content/"


def delete_chunk(movie_id: str, chunk_name: str, package_name: str | None = None) -> None:
  """Delete a chunk from R2 when configured.

  When ``package_name`` is given, the BEP19 package-nested copy
  ``content/{package_name}/{chunk_name}`` is removed as well so no orphaned
  ``*.vcnr-pkg`` webseed objects are left behind on delete or re-upload.
  """
  if not _r2_enabled():
    return
  try:
    _delete_object(_object_key(movie_id, chunk_name))
    if package_name:
      nested_key = content_package_object_key(movie_id, package_name, chunk_name)
      if nested_key:
        _delete_object(nested_key)
  except Exception:
    logger.exception("R2 delete failed for %s/%s", movie_id, chunk_name)


def delete_movie_prefix(movie_id: str) -> None:
  """Delete all objects under the movie prefix in R2 when configured."""
  delete_media_prefix(f"{movie_id}/")


# ---------------------------------------------------------------------------
# Generic media object helpers (posters, trailer, gallery, music, manifests)
# ---------------------------------------------------------------------------


def media_content_type(filename: str) -> str:
  """Guess a reasonable Content-Type for a media filename."""
  suffix = Path(filename).suffix.lower()
  return {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".m4v": "video/x-m4v",
    ".mov": "video/quicktime",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".json": "application/json",
    ".torrent": "application/x-bittorrent",
    ".enc": "application/octet-stream",
    ".bin": "application/octet-stream",
  }.get(suffix, "application/octet-stream")


def media_public_url(key: str) -> str | None:
  """Return the public R2 URL for an object key, or None if R2 is not configured."""
  settings = get_settings()
  if not settings.r2_public_base_url:
    return None
  return f"{settings.r2_public_base_url}/{key}"


def upload_media_object(key: str, data: bytes, content_type: str | None = None) -> bool:
  """Upload a media object to R2. Returns True on success (R2 configured).

  A local mirror is NOT written here; R2 is the single source of truth for
  media objects.  Callers that need a local cache manage it themselves.
  """
  if not _r2_enabled():
    return False
  if content_type is None:
    content_type = media_content_type(key)
  try:
    _put_object(key, data, content_type)
    return True
  except Exception:
    logger.exception("R2 media upload failed for %s", key)
    return False


def download_media_object(key: str) -> bytes | None:
  """Download a media object's bytes from R2, or None if unavailable."""
  if not _r2_enabled():
    return None
  return _get_object(key)


def media_object_exists(key: str) -> bool:
  """Return True if the object exists in R2 (when configured)."""
  if not _r2_enabled():
    return False
  return _object_exists(key)


def delete_media_object(key: str) -> bool:
  """Delete a single media object from R2. Returns True when R2 handled it."""
  if not _r2_enabled():
    return False
  try:
    _delete_object(key)
    return True
  except Exception:
    logger.exception("R2 media delete failed for %s", key)
    return False


def list_media_keys(prefix: str) -> list[str]:
  """List object keys under a prefix in R2 (when configured), sorted."""
  if not _r2_enabled():
    return []
  settings = get_settings()
  try:
    client = _get_r2_client()
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(
      Bucket=settings.r2_bucket_name,
      Prefix=prefix,
    ):
      for obj in page.get("Contents", []):
        keys.append(obj["Key"])
    return sorted(keys)
  except Exception:
    logger.exception("R2 list failed for prefix %s", prefix)
    return []


def delete_media_prefix(prefix: str) -> None:
  """Delete all objects under a prefix in R2 when configured."""
  if not _r2_enabled():
    return
  settings = get_settings()
  try:
    client = _get_r2_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(
      Bucket=settings.r2_bucket_name,
      Prefix=prefix,
    ):
      contents = page.get("Contents", [])
      if not contents:
        continue
      client.delete_objects(
        Bucket=settings.r2_bucket_name,
        Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
      )
  except Exception:
    logger.exception("R2 prefix delete failed for %s", prefix)


def presign_media_upload(
  key: str,
  content_type: str | None = None,
  expires_seconds: int = 900,
) -> str | None:
  """Return a presigned R2 PUT URL for direct browser upload, or None.

  The URL allows the caller to PUT the object directly to R2, bypassing
  the Render API entirely.  Expires after ``expires_seconds``.

  ``content_type`` is intentionally NOT included in the signed params.  The
  browser sends its own Content-Type header when uploading a File, and if it
  differs from a signed value the signature check fails with 403.  Omitting
  it lets the browser send any Content-Type (R2 stores whatever it receives).
  """
  if not _r2_enabled():
    return None
  try:
    client = _get_r2_client()
    return client.generate_presigned_url(
      ClientMethod="put_object",
      Params={
        "Bucket": get_settings().r2_bucket_name,
        "Key": key,
      },
      ExpiresIn=expires_seconds,
    )
  except Exception:
    logger.exception("R2 presign failed for %s", key)
    return None


def presign_media_download(key: str, expires_seconds: int = 900) -> str | None:
  """Return a presigned R2 GET URL, or None when R2 is not configured.

  Used as a fallback when the bucket is not public (no R2_PUBLIC_BASE_URL).
  """
  if not _r2_enabled():
    return None
  try:
    client = _get_r2_client()
    return client.generate_presigned_url(
      ClientMethod="get_object",
      Params={
        "Bucket": get_settings().r2_bucket_name,
        "Key": key,
      },
      ExpiresIn=expires_seconds,
    )
  except Exception:
    logger.exception("R2 download presign failed for %s", key)
    return None


def media_download_url(key: str) -> str | None:
  """Best-effort public URL for an object key.

  Prefers the public bucket URL when configured, otherwise a short-lived
  presigned GET URL.
  """
  public_url = media_public_url(key)
  if public_url:
    return public_url
  return presign_media_download(key)


Any  # noqa: F401 (kept for forward-compat type annotations)