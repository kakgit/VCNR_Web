from __future__ import annotations

import logging
from functools import lru_cache

from backend.core.config import get_settings

logger = logging.getLogger(__name__)


def _r2_enabled() -> bool:
  settings = get_settings()
  return bool(
    settings.r2_account_id
    and settings.r2_access_key_id
    and settings.r2_secret_access_key
    and settings.r2_bucket_name
  )


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


def _object_key(movie_id: str, chunk_name: str) -> str:
  return f"{movie_id}/content/{chunk_name}"


def upload_chunk(movie_id: str, chunk_name: str, data: bytes) -> None:
  """Upload an encrypted chunk to R2 when configured, otherwise no-op.

  The caller is responsible for writing the chunk to local disk as well;
  this function only mirrors the chunk to R2 for permanent storage.
  """
  if not _r2_enabled():
    return
  settings = get_settings()
  try:
    client = _get_r2_client()
    client.put_object(
      Bucket=settings.r2_bucket_name,
      Key=_object_key(movie_id, chunk_name),
      Body=data,
      ContentType="application/octet-stream",
    )
  except Exception:
    logger.exception("R2 upload failed for %s/%s", movie_id, chunk_name)


def chunk_exists(movie_id: str, chunk_name: str) -> bool:
  """Return True if the chunk exists in R2 (when configured)."""
  if not _r2_enabled():
    return False
  settings = get_settings()
  try:
    client = _get_r2_client()
    client.head_object(
      Bucket=settings.r2_bucket_name,
      Key=_object_key(movie_id, chunk_name),
    )
    return True
  except Exception:
    return False


def chunk_public_url(movie_id: str, chunk_name: str) -> str | None:
  """Return the public R2 URL for a chunk, or None if R2 is not configured."""
  settings = get_settings()
  if not settings.r2_public_base_url:
    return None
  return f"{settings.r2_public_base_url}/{_object_key(movie_id, chunk_name)}"


def chunk_webseed_base(movie_id: str) -> str | None:
  """Return the R2 webseed base URL for a movie, or None if R2 is not configured.

  Torrent clients append the chunk filename (torrent file path) to this base,
  matching the public R2 object layout ``{movie_id}/content/<chunk_name>``.
  """
  settings = get_settings()
  if not settings.r2_public_base_url:
    return None
  return f"{settings.r2_public_base_url}/{movie_id}/content/"


def delete_chunk(movie_id: str, chunk_name: str) -> None:
  """Delete a chunk from R2 when configured."""
  if not _r2_enabled():
    return
  settings = get_settings()
  try:
    client = _get_r2_client()
    client.delete_object(
      Bucket=settings.r2_bucket_name,
      Key=_object_key(movie_id, chunk_name),
    )
  except Exception:
    logger.exception("R2 delete failed for %s/%s", movie_id, chunk_name)


def delete_movie_prefix(movie_id: str) -> None:
  """Delete all objects under the movie prefix in R2 when configured."""
  if not _r2_enabled():
    return
  settings = get_settings()
  try:
    client = _get_r2_client()
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(
      Bucket=settings.r2_bucket_name,
      Prefix=f"{movie_id}/",
    ):
      contents = page.get("Contents", [])
      if not contents:
        continue
      client.delete_objects(
        Bucket=settings.r2_bucket_name,
        Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
      )
  except Exception:
    logger.exception("R2 prefix delete failed for %s", movie_id)