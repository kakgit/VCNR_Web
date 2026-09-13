"""HLS adaptive streaming for Library titles.

Raw .mp4/.mkv library uploads are uploaded to R2 as a single object, then a
background job segments them into HLS (adaptive) playlists with ffmpeg and
uploads the segments back to R2 under ``{movie_id}/content/hls/``.

Viewers then stream small ~6-second segments directly from R2 via short-lived
presigned URLs, so:
  * mobile playback adapts to the connection (adaptive bitrate),
  * data usage is minimized (only the segments the viewer actually watches),
  * neither the raw bytes nor the HLS segments are buffered in server memory.
"""

from __future__ import annotations

import io
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import quote

from backend.core.storage import (
  delete_media_prefix,
  download_media_object,
  list_media_keys,
  media_object_exists,
  upload_media_object_stream,
)

logger = logging.getLogger(__name__)

HLS_FOLDER = "hls"
SEGMENT_SECONDS = 6

# (label, max width, max height, video bitrate, estimated bandwidth)
RENDITIONS = [
  {"label": "720", "max_width": 1280, "max_height": 720, "vbr": "2200k", "bandwidth": 2600000},
  {"label": "480", "max_width": 854, "max_height": 480, "vbr": "900k", "bandwidth": 1100000},
]


def library_hls_prefix(movie_id: str) -> str:
  """R2 key prefix for a movie's HLS artifacts."""
  return f"{movie_id}/content/{HLS_FOLDER}/"


def library_hls_manifest_key(movie_id: str) -> str:
  """R2 key of the HLS master playlist for a movie."""
  return f"{library_hls_prefix(movie_id)}master.m3u8"


def library_hls_ready(movie_id: str) -> bool:
  """True when the movie's HLS master playlist exists in R2."""
  return media_object_exists(library_hls_manifest_key(movie_id))


def _hls_status_key(movie_id: str) -> str:
  return f"{library_hls_prefix(movie_id)}.hls-status.json"


def _write_hls_status(movie_id: str, state: str, detail: str = "") -> None:
  """Persist a machine-readable HLS job state into R2 so the admin UI can tell
  ``running`` from ``failed`` instead of showing a stuck spinner."""
  payload = json.dumps(
    {"state": state, "detail": detail, "updated_at": int(time.time())},
    ensure_ascii=False,
  ).encode("utf-8")
  try:
    upload_media_object_stream(_hls_status_key(movie_id), io.BytesIO(payload), "application/json")
  except Exception:
    logger.exception("HLS status write failed for %s", movie_id)


def library_hls_status(movie_id: str) -> dict:
  """Return the last HLS job state: ``ready`` (master exists), ``running``,
  ``failed`` (+ detail), or ``pending`` (no job has started yet)."""
  if library_hls_ready(movie_id):
    return {"state": "ready", "detail": ""}
  data = download_media_object(_hls_status_key(movie_id))
  if not data:
    return {"state": "pending", "detail": ""}
  try:
    parsed = json.loads(data.decode("utf-8", errors="replace"))
    return {
      "state": str(parsed.get("state") or "pending"),
      "detail": str(parsed.get("detail") or ""),
    }
  except Exception:
    return {"state": "pending", "detail": ""}


def _ffmpeg_exe() -> str | None:
  """Locate a usable ffmpeg binary.

  Prefers the statically-linked ffmpeg bundled by ``imageio-ffmpeg`` (works on
  Railway / Render without a system package install), then falls back to any
  ``ffmpeg`` on PATH.
  """
  try:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()
  except Exception:
    pass
  return shutil.which("ffmpeg")


def _run(cmd: list[str], timeout: int = 60 * 60) -> bool:
  try:
    result = subprocess.run(cmd, capture_output=True, timeout=timeout)
  except Exception:
    logger.exception("ffmpeg subprocess failed: %s", " ".join(cmd[:8]))
    return False
  if result.returncode != 0:
    logger.error(
      "ffmpeg failed (%s): %s",
      result.returncode,
      result.stderr.decode(errors="replace")[-3000:],
    )
    return False
  return True


def _probe_resolution(ffmpeg: str, path: str) -> tuple[int, int]:
  """Return (width, height) parsed from ffmpeg's stream info, or (0, 0)."""
  try:
    result = subprocess.run([ffmpeg, "-i", path], capture_output=True, timeout=120)
    info = result.stderr.decode(errors="replace")
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", info)
    if match:
      return int(match.group(1)), int(match.group(2))
  except Exception:
    logger.exception("ffmpeg probe failed for %s", path)
  return 0, 0
def _even_target_dimensions(
  width: int, height: int, max_width: int, max_height: int
) -> tuple[int, int] | None:
  """Compute an even-dimensioned fit-inside-box target size for libx264.

  scale's ``force_divisible_by`` option must NOT be used: the statically
  bundled imageio-ffmpeg binary (v4.2.2, the same one Railway runs) does not
  know it and every build dies with
  "Error initializing filter 'scale' ... Option not found".
  """
  if not width or not height:
    return None
  scale_factor = min(max_width / width, max_height / height, 1.0)
  out_w = max(2, int(round(width * scale_factor)))
  out_h = max(2, int(round(height * scale_factor)))
  out_w -= out_w % 2
  out_h -= out_h % 2
  return out_w, out_h


def _build_rendition(
  ffmpeg: str,
  source_path: str,
  out_dir: str,
  rendition: dict,
  source_width: int = 0,
  source_height: int = 0,
) -> bool:
  """Transcode one HLS rendition: h264 + aac, 6-second .ts segments, VOD playlist."""
  label = rendition["label"]
  script = Path(out_dir) / f"index_{label}.m3u8"
  segment_pattern = Path(out_dir) / f"seg_{label}_%05d.ts"
  max_w = rendition["max_width"]
  max_h = rendition["max_height"]
  # Even output dimensions are mandatory for libx264/yuv420p (odd widths abort
  # the encode). When the probe succeeded, compute the exact target size in
  # Python; only when it failed, fall back to a filter chain that old bundled
  # ffmpeg binaries actually support.
  target = _even_target_dimensions(source_width, source_height, max_w, max_h)
  if target:
    video_filter = f"scale={target[0]}:{target[1]}"
  else:
    video_filter = (
      f"scale={max_w}:{max_h}:force_original_aspect_ratio=decrease,"
      "pad=ceil(iw/2)*2:ceil(ih/2)*2"
    )
  cmd = [
    ffmpeg, "-y", "-nostdin", "-loglevel", "error", "-i", source_path,
    "-preset", "veryfast",
    "-c:v", "libx264",
    "-profile:v", "main",
    "-pix_fmt", "yuv420p",
    "-vf", video_filter,
    "-c:a", "aac", "-ac", "2", "-b:a", "96k",
    "-b:v", rendition["vbr"],
    "-movflags", "+faststart",
    "-hls_time", str(SEGMENT_SECONDS),
    "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
    "-hls_list_size", "0",
    "-hls_segment_filename", str(segment_pattern),
    "-hls_playlist_type", "vod",
    "-f", "hls", str(script),
  ]
  return _run(cmd)


def _upload_library_hls_file(tmp_dir: str, movie_id: str, filename: str) -> None:
  key = f"{library_hls_prefix(movie_id)}{filename}"
  content_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
  with open(Path(tmp_dir) / filename, "rb") as fileobj:
    upload_media_object_stream(key, fileobj, content_type)


def build_library_hls(movie_id: str) -> bool:
  """Segment a library title's raw video into adaptive HLS and upload to R2.

  Safe to run as a background task after the raw upload completes.  Returns
  True when the full HLS package (master + variant playlists + segments) is
  present in R2.  A machine-readable job state (``running`` / ``ready`` /
  ``failed``) is persisted next to the segments so the admin UI can surface
  failures instead of showing a stuck spinner.
  """
  try:
    source_key = next(
      (
        key
        for key in list_media_keys(f"{movie_id}/content/")
        if key.lower().endswith((".mp4", ".mkv")) and f"/{HLS_FOLDER}/" not in key
      ),
      None,
    )
    if source_key is None:
      detail = "No raw library video found in storage."
      logger.warning("build_library_hls(%s): %s", movie_id, detail)
      _write_hls_status(movie_id, "failed", detail)
      return False

    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
      detail = "ffmpeg binary is not available on the server."
      logger.warning("build_library_hls(%s): %s", movie_id, detail)
      _write_hls_status(movie_id, "failed", detail)
      return False

    _write_hls_status(movie_id, "running")

    data = download_media_object(source_key)
    if not data:
      detail = "Could not download the raw video from storage."
      logger.warning("build_library_hls(%s): %s", movie_id, detail)
      _write_hls_status(movie_id, "failed", detail)
      return False

    with TemporaryDirectory() as tmp_dir:
      tmp_path = Path(tmp_dir)
      source_path = tmp_path / f"source{Path(source_key).suffix.lower() or '.mp4'}"
      source_path.write_bytes(data)
      del data

      width, height = _probe_resolution(ffmpeg, str(source_path))

      active = [
        rendition
        for rendition in RENDITIONS
        if not height or height >= rendition["max_height"]
      ]
      if not active:
        active = [RENDITIONS[-1]]
      if width and height and width < height:
        # Portrait/vertical video: swap width/height so the variant metadata matches.
        active = [dict(item) for item in active]
        for rendition in active:
          rendition["max_width"], rendition["max_height"] = rendition["max_height"], rendition["max_width"]

      for rendition in active:
        if not _build_rendition(ffmpeg, str(source_path), tmp_dir, rendition, width, height):
          detail = f"HLS rendition {rendition['label']} failed to build (see server logs for the ffmpeg error)."
          logger.error("build_library_hls(%s): %s", movie_id, detail)
          _write_hls_status(movie_id, "failed", detail)
          return False

      master_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
      for rendition in active:
        master_lines.extend([
          (
            f"#EXT-X-STREAM-INF:BANDWIDTH={rendition['bandwidth']},"
            f"RESOLUTION={rendition['max_width']}x{rendition['max_height']},"
            f'NAME="{rendition["label"]}"'
          ),
          f"index_{rendition['label']}.m3u8",
        ])
      (tmp_path / "master.m3u8").write_text("\n".join(master_lines) + "\n", encoding="utf-8")

      for file_path in tmp_path.glob("*"):
        if file_path.is_file() and file_path.suffix in {".ts", ".m3u8"}:
          _upload_library_hls_file(tmp_dir, movie_id, file_path.name)

      ready = library_hls_ready(movie_id)
      if ready:
        _write_hls_status(movie_id, "ready")
      else:
        detail = "HLS upload to storage did not complete."
        logger.error("build_library_hls(%s): %s", movie_id, detail)
        _write_hls_status(movie_id, "failed", detail)
      return ready
  except Exception as error:
    detail = f"{type(error).__name__}: {error}"
    logger.exception("build_library_hls failed for %s", movie_id)
    _write_hls_status(movie_id, "failed", detail)
    return False


def delete_library_hls(movie_id: str) -> None:
  """Remove all HLS artifacts for a movie from R2."""
  delete_media_prefix(library_hls_prefix(movie_id))


def rewrite_hls_manifest(text: str, movie_id: str, base_url: str, token: str) -> str:
  """Rewrite relative HLS URIs to absolute, authenticated API URLs.

  The player must attach the session token to every segment/playlist request,
  but browser <video> / mobile video players cannot send an Authorization
  header on each fetch.  Embedding ``?token=`` into each rewritten URL keeps the
  whole stream authenticated.
  """
  base = str(base_url).rstrip("/")
  prefix = f"{base}/movies/{movie_id}/content/hls/"
  quoted_token = quote(token, safe="")
  lines = []
  for line in text.splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith(("http://", "https://")):
      lines.append(line)
      continue
    lines.append(f"{prefix}{quote(stripped, safe='/')}?token={quoted_token}")
  return "\n".join(lines) + "\n"


__all__ = [
  "library_hls_prefix",
  "library_hls_manifest_key",
  "library_hls_ready",
  "library_hls_status",
  "build_library_hls",
  "delete_library_hls",
  "rewrite_hls_manifest",
]