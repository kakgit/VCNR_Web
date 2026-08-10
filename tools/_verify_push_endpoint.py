"""Live HTTP round-trip for the push device registration endpoints.

Starts the API in-process on a spare port and exercises
``POST/DELETE /api/push/devices`` with a real signed-in session so the
auth wiring, request schema, and validation errors are all covered.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from backend.main import app


BASE_URL = "http://127.0.0.1:8137/api"


def _call(path: str, method: str = "GET", body: dict | None = None, token: str | None = None):
  data = json.dumps(body).encode("utf-8") if body is not None else None
  headers = {"Accept": "application/json"}
  if data is not None:
    headers["Content-Type"] = "application/json"
  if token:
    headers["Authorization"] = f"Bearer {token}"
  request = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
  try:
    with urllib.request.urlopen(request, timeout=15) as response:
      return response.status, json.loads(response.read().decode("utf-8") or "{}")
  except urllib.error.HTTPError as error:
    return error.code, json.loads(error.read().decode("utf-8") or "{}")


def main() -> None:
  config = uvicorn.Config(app, host="127.0.0.1", port=8137, log_level="warning")
  server = uvicorn.Server(config)
  thread = threading.Thread(target=server.run, daemon=True)
  thread.start()

  for _ in range(60):
    if server.started:
      break
    time.sleep(0.5)
  assert server.started, "API server did not start"

  try:
    status, payload = _call("/push/devices", "POST", {"push_token": "ExponentPushToken[nope]"})
    assert status == 401, (status, payload)
    print("unauthenticated register ->", status)

    status, payload = _call(
      "/auth/login", "POST", {"email": "kamarthi.anil@gmail.com", "password": "asd"}
    )
    assert status == 200, (status, payload)
    token = payload["token"]
    print("login ->", status)

    status, payload = _call("/push/devices", "POST", {"push_token": "plain-token"}, token)
    assert status == 400, (status, payload)
    print("invalid token rejected ->", status, payload.get("detail"))

    status, payload = _call(
      "/push/devices",
      "POST",
      {"push_token": "ExponentPushToken[live-check]", "platform": "android", "device_label": "CI"},
      token,
    )
    assert status == 200 and payload.get("registered") is True, (status, payload)
    print("register ->", status, payload.get("message"))

    # Re-registering the same device must stay idempotent.
    status, payload = _call(
      "/push/devices",
      "POST",
      {"push_token": "ExponentPushToken[live-check]", "platform": "android"},
      token,
    )
    assert status == 200, (status, payload)
    print("re-register ->", status)

    status, payload = _call(
      "/push/devices", "DELETE", {"push_token": "ExponentPushToken[live-check]"}, token
    )
    assert status == 200 and payload.get("registered") is False, (status, payload)
    print("unregister ->", status, payload.get("message"))

    status, payload = _call("/auth/me", token=token)
    assert status == 200 and "notifications" in payload, (status, payload)
    print("auth/me still returns notifications ->", len(payload["notifications"]))
  finally:
    server.should_exit = True
    thread.join(timeout=15)

  print("\nPush endpoint round-trip passed.")


if __name__ == "__main__":
  main()
