"""Send a test push to a device token, to verify FCM/APNs delivery.

Use this while testing on a real phone:

  python tools/send_test_push.py ExponentPushToken[xxxxxxxx]

Lock the phone (or swipe the app away) before running it: the alert should
still arrive, which is the whole point of the offline notification work.

Pass --list to instead show every device token currently registered in the
database, so you can confirm the app reached the backend at all.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.push import build_push_message, is_expo_push_token, send_push_messages


def _list_tokens() -> None:
  from backend.db import SessionLocal
  from backend.models import PushDeviceTokenRecord, UserRecord

  if SessionLocal is None:
    print("No database configured; tokens are only held in the in-memory demo store.")
    return

  session = SessionLocal()
  try:
    rows = (
      session.query(PushDeviceTokenRecord, UserRecord)
      .outerjoin(UserRecord, UserRecord.id == PushDeviceTokenRecord.user_id)
      .order_by(PushDeviceTokenRecord.updated_at.desc())
      .all()
    )
    if not rows:
      print("No push devices registered yet. Sign in on the phone first.")
      return
    print(f"{len(rows)} registered device(s):\n")
    for record, user in rows:
      state = "active" if record.is_active else "inactive"
      email = getattr(user, "email", None) or record.user_id
      label = record.device_label or "-"
      print(f"  [{state:8}] {email:34} {record.platform or '?':8} {label:20} {record.push_token}")
  finally:
    session.close()


def main() -> None:
  parser = argparse.ArgumentParser(description="Send a test Expo push notification.")
  parser.add_argument("token", nargs="?", help="Expo push token, e.g. ExponentPushToken[...]")
  parser.add_argument("--list", action="store_true", help="List registered device tokens and exit.")
  parser.add_argument("--title", default="Cine Vault", help="Notification title.")
  parser.add_argument(
    "--body",
    default='Download is confirmed for "Test Movie". You can download this title from 15 Aug 2026, 10:00 AM.',
    help="Notification body.",
  )
  args = parser.parse_args()

  if args.list:
    _list_tokens()
    return

  if not args.token:
    parser.error("provide a push token, or use --list")

  if not is_expo_push_token(args.token):
    parser.error(f"'{args.token}' is not a valid Expo push token")

  message = build_push_message(
    args.token,
    args.title,
    args.body,
    {"notification_type": "download_ready", "source": "send_test_push"},
  )
  accepted, dead = send_push_messages([message])
  print(f"accepted by Expo: {accepted}")
  if dead:
    print(f"rejected/dead tokens: {dead}")
    print("The device must re-register (reinstall or sign in again).")
  elif accepted:
    print("Expo accepted the push. It should appear on the device shortly.")
  else:
    print("Expo did not accept the push; check network access to exp.host.")


if __name__ == "__main__":
  main()
