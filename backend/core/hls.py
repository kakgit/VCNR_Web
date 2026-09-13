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

import logging
import re
import shutil
import subprocess
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
def _build_rendition(
  ffmpeg: str,
  source_path: str,
  out_dir: str,
  rendition: dict,
) -> bool:
  """Transcode one HLS rendition: h264 + aac, 6-second .ts segments, VOD playlist."""
  label = rendition["label"]
  script = Path(out_dir) / f"index_{label}.m3u8"
  segment_pattern = Path(out_dir) / f"seg_{label}_%05d.ts"
  max_w = rendition["max_width"]
  max_h = rendition["max_height"]
  cmd = [
    ffmpeg, "-y", "-i", source_path,
    "-preset", "veryfast",
    "-c:v", "libx264",
    "-profile:v", "main",
    "-pix_fmt", "yuv420p",
    "-vf", f"scale={max_w}:{max_h}:force_original_aspect_ratio=decrease",
    "-c:a", "aac", "-ac", "2", "-b:a", "96k",
    "-b:v", rendition["vbr"],
    "-movflags", "+faststart",
    "-hls_time", str(SEGMENT_SECONDS),
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
  present in R2.
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
      logger.warning("build_library_hls: no raw library source found for %s", movie_id)
      return False

    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
      logger.warning("build_library_hls: ffmpeg is not available; skipping HLS for %s", movie_id)
      return False

    data = download_media_object(source_key)
    if not data:
      logger.warning("build_library_hls: could not download raw source for %s", movie_id)
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
        if not _build_rendition(ffmpeg, str(source_path), tmp_dir, rendition):
          logger.error("build_library_hls: rendition %s failed for %s", rendition["label"], movie_id)
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

      return library_hls_ready(movie_id)
  except Exception:
    logger.exception("build_library_hls failed for %s", movie_id)
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
  "build_library_hls",
  "delete_library_hls",
  "rewrite_hls_manifest",
]