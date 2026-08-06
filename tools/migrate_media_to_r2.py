"""One-time migration: upload existing local media/library files to R2.

Run from the project root after configuring R2 env vars:

    python tools/migrate_media_to_r2.py

This walks the local media/library tree and uploads every file to R2 using
the same object key layout the backend expects:

    {movie_id}/posters/{vertical|horizontal}/{filename}
    {movie_id}/trailers/{filename}
    {movie_id}/gallery/{filename}
    {movie_id}/music/{filename}
    {movie_id}/content/manifest.json
    {movie_id}/content/{quality}.torrent
    {movie_id}/content/{chunk_name}

Files already present in R2 are skipped (idempotent). Run it again any time
to backfill new local files.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.storage import (  # noqa: E402
  media_content_type,
  media_object_exists,
  r2_enabled,
  upload_media_object,
)

LIBRARY_MEDIA_ROOT = Path(__file__).resolve().parents[1] / "media" / "library"


def _r2_key_for_local_path(relative_path: Path) -> str:
  """Map a local media/library relative path to the R2 object key."""
  parts = relative_path.parts
  # parts[0] is the movie_id
  movie_id = parts[0]
  rest = parts[1:]
  if not rest:
    return movie_id
  if rest[0] == "posters" and len(rest) >= 3:
    # posters/{orientation}/{filename}
    return f"{movie_id}/posters/{rest[1]}/{rest[2]}"
  if rest[0] == "trailers":
    return f"{movie_id}/trailers/{rest[1]}"
  if rest[0] == "gallery":
    return f"{movie_id}/gallery/{rest[1]}"
  if rest[0] == "music":
    return f"{movie_id}/music/{rest[1]}"
  if rest[0] == "content":
    return f"{movie_id}/content/{rest[1]}"
  return f"{movie_id}/{'/'.join(rest)}"


def main() -> int:
  if not r2_enabled():
    print("R2 is not configured. Set R2_* env vars first (see .env.example).")
    return 1
  if not LIBRARY_MEDIA_ROOT.is_dir():
    print(f"No local media library found at {LIBRARY_MEDIA_ROOT}")
    return 0

  uploaded = 0
  skipped = 0
  failed = 0
  for file_path in sorted(LIBRARY_MEDIA_ROOT.rglob("*")):
    if not file_path.is_file():
      continue
    relative_path = file_path.relative_to(LIBRARY_MEDIA_ROOT)
    key = _r2_key_for_local_path(relative_path)
    if media_object_exists(key):
      skipped += 1
      continue
    try:
      data = file_path.read_bytes()
      if upload_media_object(key, data):
        uploaded += 1
        print(f"  uploaded {key} ({len(data)} bytes)")
      else:
        failed += 1
        print(f"  FAILED  {key}")
    except Exception as error:  # noqa: BLE001
      failed += 1
      print(f"  ERROR   {key}: {error}")

  print(f"\nDone. Uploaded: {uploaded}, skipped (already in R2): {skipped}, failed: {failed}")
  return 0 if failed == 0 else 1


if __name__ == "__main__":
  raise SystemExit(main())