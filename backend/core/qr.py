"""QR code helpers for Cine Vault gift / advertisement deliveries.

The generated codes encode ``cinevault://movie/...`` deep-link payloads that
mirror the existing ``cinevault://user`` profile codes, so any Cine Vault app
scanner can tell a viewer gift apart from other payloads.
"""

from __future__ import annotations

import io
import urllib.parse

QR_IMAGE_SIZE = 420


def build_movie_gift_qr_payload(
  movie_id: str,
  movie_title: str = "",
  sponsor_brand: str = "",
  gift_code: str = "",
  quality_code: str | None = None,
) -> str:
  """Build the payload encoded into a sponsored-movie gift QR code."""
  params: dict[str, str] = {}
  if movie_title.strip():
    params["title"] = movie_title.strip()
  if sponsor_brand.strip():
    params["sponsor"] = sponsor_brand.strip()
  if gift_code.strip():
    params["code"] = gift_code.strip()
  if quality_code and quality_code.strip():
    params["quality"] = quality_code.strip()
  query = urllib.parse.urlencode(params)
  base = f"cinevault://movie/{urllib.parse.quote(str(movie_id).strip(), safe='')}"
  return f"{base}?{query}" if query else base


def build_qr_png_bytes(payload: str) -> bytes:
  """Render a QR code for the payload and return PNG bytes."""
  import qrcode  # Imported lazily so the API can boot without the extra dep.

  qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    box_size=10,
    border=2,
  )
  qr.add_data(payload)
  qr.make(fit=True)
  image = qr.make_image(fill_color="black", back_color="white")
  buffer = io.BytesIO()
  image.save(buffer, format="PNG")
  return buffer.getvalue()
