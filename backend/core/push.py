"""Outbound push delivery through the Expo push service.

In-app notification rows only become visible when a viewer opens the app.
Download-date approvals must also reach viewers whose app is closed or whose
device is currently offline, so every stored notification is mirrored to the
Expo push service. Expo hands the payload to FCM/APNs, which queue the message
and deliver it when the device comes back online.

Only the Python standard library is used here so no new runtime dependency is
introduced, matching the other outbound HTTP calls in this project.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Sequence

from backend.core.config import get_settings


EXPO_PUSH_ENDPOINT = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_BATCH_SIZE = 100
EXPO_PUSH_TIMEOUT_SECONDS = 12
PUSH_ANDROID_CHANNEL_ID = "vcnr-updates"

# Expo reports these when a token belongs to an app that was uninstalled or to a
# build that can no longer receive pushes. Such tokens must be retired.
DEAD_TOKEN_ERRORS = {"DeviceNotRegistered", "InvalidCredentials"}


def is_expo_push_token(value: str | None) -> bool:
  normalized = str(value or "").strip()
  if not normalized.endswith("]"):
    return False
  return normalized.startswith("ExponentPushToken[") or normalized.startswith("ExpoPushToken[")


def normalize_push_token(value: str | None) -> str:
  return str(value or "").strip()


def build_push_message(
  token: str,
  title: str,
  body: str,
  data: dict | None = None,
) -> dict:
  """Build a single Expo push message.

  ``priority`` is set to ``high`` so Android delivers the message even while the
  device is in Doze mode, and ``channelId`` matches the channel the mobile app
  registers on first launch.
  """
  message: dict = {
    "to": normalize_push_token(token),
    "title": title,
    "body": body,
    "sound": "default",
    "priority": "high",
    "channelId": PUSH_ANDROID_CHANNEL_ID,
  }
  if data:
    message["data"] = data
  return message


def _chunked(items: Sequence[dict], size: int) -> Iterator[Sequence[dict]]:
  for index in range(0, len(items), size):
    yield items[index : index + size]


def _post_batch(batch: Sequence[dict]) -> list[dict]:
  payload = json.dumps(list(batch)).encode("utf-8")
  headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Accept-Encoding": "identity",
  }
  access_token = getattr(get_settings(), "expo_access_token", "")
  if access_token:
    headers["Authorization"] = f"Bearer {access_token}"

  request = urllib.request.Request(EXPO_PUSH_ENDPOINT, data=payload, headers=headers, method="POST")
  with urllib.request.urlopen(request, timeout=EXPO_PUSH_TIMEOUT_SECONDS) as response:
    raw = response.read().decode("utf-8", errors="replace")

  parsed = json.loads(raw or "{}")
  tickets = parsed.get("data") if isinstance(parsed, dict) else None
  return tickets if isinstance(tickets, list) else []


def send_push_messages(messages: Iterable[dict]) -> tuple[int, list[str]]:
  """Send messages to Expo and report ``(accepted_count, dead_tokens)``.

  Push delivery must never break the admin action that triggered it, so every
  transport failure is swallowed. The stored in-app notification row remains the
  source of truth.
  """
  valid = [message for message in messages if is_expo_push_token(message.get("to"))]
  if not valid:
    return 0, []

  accepted = 0
  dead_tokens: list[str] = []
  for batch in _chunked(valid, EXPO_PUSH_BATCH_SIZE):
    try:
      tickets = _post_batch(batch)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
      continue

    for index, ticket in enumerate(tickets):
      if not isinstance(ticket, dict):
        continue
      if ticket.get("status") == "ok":
        accepted += 1
        continue
      details = ticket.get("details")
      error_code = str(details.get("error") or "") if isinstance(details, dict) else ""
      if error_code in DEAD_TOKEN_ERRORS and index < len(batch):
        dead_tokens.append(normalize_push_token(batch[index].get("to")))

  return accepted, [token for token in dead_tokens if token]


def send_push_messages_async(
  messages: Iterable[dict],
  on_dead_tokens: Callable[[list[str]], None] | None = None,
) -> None:
  """Deliver pushes on a daemon thread so API responses stay fast."""
  snapshot = [dict(message) for message in messages]
  if not snapshot:
    return

  def worker() -> None:
    try:
      _accepted, dead_tokens = send_push_messages(snapshot)
    except Exception:
      return
    if dead_tokens and on_dead_tokens is not None:
      try:
        on_dead_tokens(dead_tokens)
      except Exception:
        return

  threading.Thread(target=worker, name="expo-push-dispatch", daemon=True).start()
