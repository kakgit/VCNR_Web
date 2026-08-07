"""Backfill R2 chunks into BEP19 package-nested keys for multi-file web seeds.

Multi-file web seed clients (BitComet, libtorrent, qBittorrent) follow BEP19:
they resolve each file's URL as ``url-list base + torrent ``name`` folder +
file path``.  The ``url-list`` already advertises ``{r2_public_base_url}/{movie_id}/content/``,
so for the existing ``title-1-admin-1-720p.vcnr-pkg`` torrent the client requests:

    .../content/title-1-admin-1-720p.vcnr-pkg/TITLE1-...-CH0001.vcnr

Chunks uploaded before the package-nested layout existed only live at the flat
key ``{movie_id}/content/{chunk}``, so that request 404s and the torrent stalls
at 0%.  This tool mirrors each quality's chunks (server-side R2 copy, no bytes
cross the network) into the nested layout so the already-published torrent works.
The torrent file itself is unchanged: same info hash, same ``url-list``.

Requires R2 credentials in the environment (the ones Render uses):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME, R2_PUBLIC_BASE_URL

Usage:
    # Backfill every title found in the bucket
    python tools/mirror_torrent_package_webseeds.py

    # Backfill a single movie, or a single quality of a movie
    python tools/mirror_torrent_package_webseeds.py --movie title-1-admin-1
    python tools/mirror_torrent_package_webseeds.py --movie title-1-admin-1 --quality 720p

    # Preview what the client will fetch (no copies are made)
    python tools/mirror_torrent_package_webseeds.py --movie title-1-admin-1 --dry-run

    # Delete package-nested copies whose chunk is no longer in the manifest
    # (orphans left behind by deletes/re-uploads before the delete path was fixed).
    # Always preview first with --dry-run:
    python tools/mirror_torrent_package_webseeds.py --prune-orphans --dry-run
    python tools/mirror_torrent_package_webseeds.py --prune-orphans
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import get_settings  # noqa: E402
from backend.core import storage  # noqa: E402


def normalize_quality_code(value: str) -> str:
  return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def package_folder(movie_id: str, quality_code: str) -> str:
  return f"{movie_id}-{normalize_quality_code(quality_code)}.vcnr-pkg"


def quality_chunk_names(manifest: dict, quality_code: str) -> list[str]:
  """Return the chunk filenames belonging to a quality (mirrors routes helper)."""
  normalized = normalize_quality_code(quality_code)
  quality_entry = {
    str(item.get("quality_code") or "").strip().lower(): item
    for item in manifest.get("qualities", [])
    if str(item.get("quality_code") or "").strip()
  }.get(normalized) or {}

  quality_files = quality_entry.get("files")
  if isinstance(quality_files, list) and quality_files:
    candidates = quality_files
  else:
    candidates = manifest.get("files", [])

  names: list[str] = []
  for item in candidates:
    if normalize_quality_code(str(item.get("quality_code") or normalized)) != normalized:
      continue
    name = str(item.get("name") or "").strip()
    if name:
      names.append(name)
  return sorted(set(names))


def discover_movie_ids() -> list[str]:
  """Discover movie ids from the R2 layout ``{movie_id}/content/<thing>``."""
  movie_ids: set[str] = set()
  for key in storage.list_media_keys(""):
    parts = key.split("/")
    if len(parts) >= 2 and parts[1] == "content" and parts[0]:
      movie_ids.add(parts[0])
  return sorted(movie_ids)


def manifest_qualities(manifest: dict) -> list[dict]:
  qualities = manifest.get("qualities")
  if isinstance(qualities, list) and qualities:
    return qualities
  flat_codes = {
    normalize_quality_code(str(item.get("quality_code") or ""))
    for item in manifest.get("files", [])
    if str(item.get("quality_code") or "").strip()
  }
  return [{"quality_code": code} for code in sorted(flat_codes) if code]


def backfill_movie(movie_id: str, quality_filter: str | None, dry_run: bool, verbosity: int) -> tuple[int, int]:
  manifest_key = storage.media_object_key(movie_id, "content", "manifest.json")
  raw = storage.download_media_object(manifest_key)
  if raw is None:
    print(f"[skip] {movie_id}: manifest.json not found in R2", flush=True)
    return 0, 0

  try:
    manifest = json.loads(raw.decode("utf-8"))
  except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    print(f"[skip] {movie_id}: manifest.json is not valid JSON ({exc})", flush=True)
    return 0, 0

  qualities = manifest_qualities(manifest)
  if not qualities:
    print(f"[warn] {movie_id}: no qualities found in manifest; nothing to mirror", flush=True)
    return 0, 0

  copied = 0
  skipped = 0
  for quality in qualities:
    code = normalize_quality_code(str(quality.get("quality_code") or "").strip())
    if not code:
      continue
    if quality_filter and normalize_quality_code(quality_filter) != code:
      continue
    chunk_names = quality_chunk_names(manifest, code)
    if not chunk_names:
      print(f"[warn] {movie_id}: quality {code} has no chunk files listed", flush=True)
      continue

    package_name = package_folder(movie_id, code)
    print(
      f"[{movie_id}] quality={code} package={package_name} files={len(chunk_names)}",
      flush=True,
    )
    for chunk_name in chunk_names:
      nested_key = storage.content_package_object_key(movie_id, package_name, chunk_name)
      if nested_key is None:
        print(f"[warn] unsafe chunk name skipped: {chunk_name!r}", flush=True)
        continue
      if dry_run:
        if verbosity:
          print(f"  would copy -> {nested_key}", flush=True)
        skipped += 1
        continue
      if storage.chunk_has_package_copy(movie_id, package_name, chunk_name):
        if verbosity > 1:
          print(f"  [exists] {nested_key}", flush=True)
        skipped += 1
        continue
      if storage.copy_chunk_to_package(movie_id, package_name, chunk_name):
        copied += 1
        if verbosity:
          print(f"  [copied] {nested_key}", flush=True)
      else:
        print(f"  [FAILED] {nested_key}", flush=True)

  print(f"[{movie_id}] summary: copied={copied} skipped={skipped}", flush=True)
  return copied, skipped


def prune_orphan_package_copies(
  movie_id: str,
  quality_filter: str | None,
  dry_run: bool,
  verbosity: int,
) -> tuple[int, int]:
  """Delete BEP19 package-nested copies that the current manifest no longer references.

  Older uploads wrote the nested ``{movie_id}/content/{package}/{chunk}`` keys but
  the delete/re-upload path only removed the flat chunks, leaving orphaned
  ``*.vcnr-pkg`` objects in R2.  This sweeps only keys under the package-nested
  layout whose chunk name is not listed in the manifest (the flat canonical copy
  is never touched).  Movies without a readable manifest are skipped entirely.

  Returns ``(deleted, kept)``.
  """
  manifest_key = storage.media_object_key(movie_id, "content", "manifest.json")
  raw = storage.download_media_object(manifest_key)
  if raw is None:
    print(f"[skip] {movie_id}: manifest.json not found in R2", flush=True)
    return 0, 0
  try:
    manifest = json.loads(raw.decode("utf-8"))
  except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    print(f"[skip] {movie_id}: manifest.json is not valid JSON ({exc})", flush=True)
    return 0, 0

  expected_keys: set[str] = set()
  for quality in manifest_qualities(manifest):
    code = normalize_quality_code(str(quality.get("quality_code") or "").strip())
    if not code:
      continue
    if quality_filter and normalize_quality_code(quality_filter) != code:
      continue
    for chunk_name in quality_chunk_names(manifest, code):
      nested_key = storage.content_package_object_key(movie_id, package_folder(movie_id, code), chunk_name)
      if nested_key:
        expected_keys.add(nested_key)

  deleted = 0
  kept = 0
  for key in storage.list_media_keys(f"{movie_id}/content/"):
    parts = key.split("/")
    # Only the nested layout: {movie_id}/content/{package}/{chunk}
    if len(parts) != 4 or not parts[2].endswith(".vcnr-pkg"):
      continue
    if quality_filter and parts[2] != package_folder(movie_id, quality_filter):
      continue
    if key in expected_keys:
      kept += 1
      continue
    if dry_run:
      print(f"  would delete {key}", flush=True)
      deleted += 1
      continue
    if storage.delete_media_object(key):
      deleted += 1
      if verbosity:
        print(f"  [deleted] {key}", flush=True)
    else:
      print(f"  [FAILED] {key}", flush=True)

  print(f"[{movie_id}] prune summary: deleted={deleted} kept={kept}", flush=True)
  return deleted, kept


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--movie", action="append", default=None, help="Movie id to backfill (repeatable). Default: all movies found in the bucket.")
  parser.add_argument("--quality", default=None, help="Only backfill this normalized quality code (e.g. 720p).")
  parser.add_argument("--dry-run", action="store_true", help="Print the keys that would be written/deleted without touching R2.")
  parser.add_argument("--prune-orphans", action="store_true", help="Delete package-nested copies not listed in the current manifest (orphans).")
  parser.add_argument("-v", "--verbose", action="count", default=0, help="Print each key being processed (-v), or full detail (-vv).")
  args = parser.parse_args()

  settings = get_settings()
  required = (
    ("r2_account_id", "R2_ACCOUNT_ID"),
    ("r2_access_key_id", "R2_ACCESS_KEY_ID"),
    ("r2_secret_access_key", "R2_SECRET_ACCESS_KEY"),
  )
  missing = [env_name for attr, env_name in required if not getattr(settings, attr)]
  if missing:
    print(f"R2 is not configured. Add {', '.join(missing)} to the environment and retry.", flush=True)
    sys.exit(2)
  if not settings.r2_public_base_url:
    print("R2_PUBLIC_BASE_URL is empty; verification URLs cannot be printed.", flush=True)
  print(
    f"bucket={settings.r2_bucket_name or '(unset)'} movie_filter={args.movie or '(all)'} "
    f"quality_filter={args.quality or '(all)'} dry_run={args.dry_run} prune_orphans={args.prune_orphans}",
    flush=True,
  )

  movies = args.movie or discover_movie_ids()
  if not movies:
    print("No movies to process.", flush=True)
    sys.exit(0)

  if args.prune_orphans:
    totals = {"deleted": 0, "kept": 0}
    for movie_id in movies:
      deleted, kept = prune_orphan_package_copies(movie_id, args.quality, args.dry_run, args.verbose)
      totals["deleted"] += deleted
      totals["kept"] += kept
    print(f"\n[all] movies={len(movies)} prune deleted={totals['deleted']} kept={totals['kept']}", flush=True)
    return

  totals = {"copied": 0, "skip": 0}
  for movie_id in movies:
    copied, skipped = backfill_movie(movie_id, args.quality, args.dry_run, args.verbose)
    totals["copied"] += copied
    totals["skip"] += skipped

  print(f"\n[all] movies={len(movies)} copied={totals['copied']} skipped={totals['skip']}", flush=True)
  if not args.dry_run and settings.r2_public_base_url:
    for movie_id in movies[:1]:
      sample_key = f"{movie_id}/content/{package_folder(movie_id, '720p')}/<chunk-name>.vcnr"
      print(f"Verify with:  curl -I \"{settings.r2_public_base_url}/{sample_key}\"  (expect HTTP 206 for real chunks)", flush=True)


if __name__ == "__main__":
  main()