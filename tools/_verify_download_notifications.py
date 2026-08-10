"""Manual verification for download-date approval notifications.

Runs the persistence and demo-store notification paths against an in-memory
database so the reserve -> schedule download date -> approve flow can be
checked without starting the API server.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import persistence
from backend.core import push as push_module
from backend.data import demo_store
from backend.models import (
  Base,
  MovieRecord,
  MovieWishRecord,
  NotificationRecord,
  PushDeviceTokenRecord,
  ReservationRecord,
  TitleRecord,
  UserRecord,
)


def _build_session():
  engine = create_engine("sqlite://")
  Base.metadata.create_all(engine)
  return sessionmaker(bind=engine, expire_on_commit=False)()


def _seed(session):
  for user_id, name in (("u-reserve", "Reserver"), ("u-buy", "Buyer"), ("u-wish", "Wisher")):
    session.add(
      UserRecord(
        id=user_id,
        name=name,
        email=f"{user_id}@example.com",
        password_hash="x",
        role="viewer",
        status="active",
        points=0,
      )
    )
  session.add(
    MovieRecord(
      id="mv-1",
      stage="upcoming",
      title="Test Title",
      genre="Drama",
      delivery_start_at="2026-08-15T10:00",
      stage_label="Upcoming",
      countdown="Soon",
      release_date="TBA",
      description="d",
      budget="0",
      expected_revenue="0",
      revenue="$0K",
      posters="0",
      music="0",
      reward_bonus="0",
    )
  )
  title = TitleRecord(
    slug="test-title",
    legacy_movie_id="mv-1",
    title_name="Test Title",
    stage="upcoming",
    availability_type="online",
    story_text="s",
  )
  session.add(title)
  session.flush()
  session.add(ReservationRecord(user_id="u-reserve", title_id=title.id, status="blocked"))
  session.add(ReservationRecord(user_id="u-buy", title_id=title.id, status="fulfilled"))
  session.add(ReservationRecord(user_id="u-wish", title_id=title.id, status="cancelled"))
  session.add(MovieWishRecord(movie_id="mv-1", user_id="u-wish", wish_kind="online"))
  session.commit()


def _messages(session):
  return [
    (row.user_id, row.message)
    for row in session.query(NotificationRecord)
    .filter(NotificationRecord.notification_type == "download_ready")
    .order_by(NotificationRecord.user_id)
    .all()
  ]


def check_persistence() -> None:
  session = _build_session()
  _seed(session)
  movie = session.get(MovieRecord, "mv-1")

  created = persistence._notify_reservers_for_download_ready(session, movie)
  session.commit()
  rows = _messages(session)
  assert created == 2, f"expected 2 notifications, got {created}"
  assert [row[0] for row in rows] == ["u-buy", "u-reserve"], rows
  assert "15 Aug 2026, 10:00 AM" in rows[0][1], rows[0][1]
  assert 'Download is confirmed for "Test Title"' in rows[0][1], rows[0][1]
  print("persistence message:", rows[0][1])

  repeat = persistence._notify_reservers_for_download_ready(session, movie)
  session.commit()
  assert repeat == 0, f"expected no duplicates, got {repeat}"
  assert len(_messages(session)) == 2

  movie.delivery_start_at = "2026-09-01T18:30"
  changed = persistence._notify_reservers_for_download_ready(session, movie)
  session.commit()
  assert changed == 2, f"expected 2 new notifications, got {changed}"
  updated = [msg for _, msg in _messages(session) if "1 Sep 2026" in msg]
  assert len(updated) == 2, updated
  assert "6:30 PM" in updated[0], updated[0]
  print("persistence updated message:", updated[0])

  movie.delivery_start_at = None
  assert persistence._notify_reservers_for_download_ready(session, movie) == 0
  assert all(user_id != "u-wish" for user_id, _ in _messages(session))

  visible = persistence._resolve_viewer_notifications(session, "u-reserve", 10)
  assert visible and visible[0]["notification_type"] == "download_ready", visible
  print("viewer session notifications:", len(visible))

  session.query(NotificationRecord).delete()
  movie.delivery_start_at = "2026-08-15T10:00"
  session.commit()
  persistence.review_movie_approval(session, "mv-1", "approve")
  assert len(_messages(session)) == 2, _messages(session)
  print("review_movie_approval hook OK")


def check_demo_store() -> None:
  demo_store.MOVIES.clear()
  demo_store.MOVIE_RESERVATIONS.clear()
  demo_store.MOVIE_NOTIFICATIONS.clear()
  demo_store.MOVIE_CHANGE_REQUESTS.clear()

  movie = {
    "id": "mv-1",
    "title": "Test Title",
    "delivery_start_at": "2026-08-15T10:00",
    "approval_status": "pending_super_admin_approval",
  }
  demo_store.MOVIES.append(movie)
  demo_store.MOVIE_RESERVATIONS.append({"user_id": "u-reserve", "movie_id": "mv-1", "status": "blocked"})
  demo_store.MOVIE_RESERVATIONS.append({"user_id": "u-buy", "movie_id": "mv-1", "status": "fulfilled"})
  demo_store.MOVIE_RESERVATIONS.append({"user_id": "u-other", "movie_id": "mv-1", "status": "cancelled"})

  demo_store.review_movie_approval("mv-1", "approve")
  rows = demo_store.MOVIE_NOTIFICATIONS
  assert len(rows) == 2, rows
  assert {row["user_id"] for row in rows} == {"u-reserve", "u-buy"}
  assert "15 Aug 2026, 10:00 AM" in rows[0]["message"], rows[0]["message"]
  print("demo_store message:", rows[0]["message"])

  demo_store.review_movie_approval("mv-1", "approve")
  assert len(demo_store.MOVIE_NOTIFICATIONS) == 2, "demo store duplicated notifications"

  visible = demo_store._get_viewer_notifications("u-reserve", 10)
  assert visible and visible[0]["notification_type"] == "download_ready", visible
  print("demo_store viewer notifications:", len(visible))


def check_offline_push() -> None:
  """Offline viewers must be reached through the Expo push service."""
  sent: list[list[dict]] = []

  def fake_send(messages, on_dead_tokens=None):
    captured = [dict(message) for message in messages]
    sent.append(captured)
    if on_dead_tokens is not None:
      dead = [message["to"] for message in captured if message["to"].endswith("[dead]")]
      if dead:
        on_dead_tokens(dead)

  original_persistence_send = persistence.send_push_messages_async
  original_demo_send = demo_store.send_push_messages_async
  persistence.send_push_messages_async = fake_send
  demo_store.send_push_messages_async = fake_send
  try:
    session = _build_session()
    _seed(session)
    movie = session.get(MovieRecord, "mv-1")

    assert persistence.register_push_device_token(
      session, "u-reserve", "ExponentPushToken[reserve]", "android", "Pixel"
    )
    assert persistence.register_push_device_token(
      session, "u-buy", "ExponentPushToken[buy]", "ios", "iPhone"
    )
    # A wisher never reserved, so no push should be addressed to them.
    assert persistence.register_push_device_token(
      session, "u-wish", "ExponentPushToken[wish]", "android", "Tab"
    )
    assert not persistence.register_push_device_token(session, "u-reserve", "   ")

    persistence.review_movie_approval(session, "mv-1", "approve")
    assert len(_messages(session)) == 2, _messages(session)
    assert sent, "no push batch was dispatched"

    pushed = sent[-1]
    targets = sorted(message["to"] for message in pushed)
    assert targets == ["ExponentPushToken[buy]", "ExponentPushToken[reserve]"], targets
    body = pushed[0]["body"]
    assert "15 Aug 2026, 10:00 AM" in body, body
    assert pushed[0]["title"] == "Test Title", pushed[0]
    assert pushed[0]["priority"] == "high", pushed[0]
    assert pushed[0]["channelId"] == push_module.PUSH_ANDROID_CHANNEL_ID, pushed[0]
    assert pushed[0]["data"]["notification_type"] == "download_ready", pushed[0]
    print("push targets:", targets)
    print("push body:", body)

    # Re-approving the same date is a no-op, so no repeat push is sent.
    batches_before = len(sent)
    persistence.review_movie_approval(session, "mv-1", "approve")
    assert len(sent) == batches_before, "duplicate push dispatched for unchanged date"

    # A signed-out device stops receiving alerts.
    assert persistence.unregister_push_device_token(session, "u-reserve", "ExponentPushToken[reserve]")
    inactive = (
      session.query(PushDeviceTokenRecord)
      .filter(PushDeviceTokenRecord.push_token == "ExponentPushToken[reserve]")
      .first()
    )
    assert inactive is not None and inactive.is_active is False
    tokens = persistence._list_active_push_tokens(session, ["u-reserve", "u-buy"])
    assert "u-reserve" not in tokens, tokens
    print("unregistered device excluded from push targets")

    # Demo store mirror.
    demo_store.MOVIES.clear()
    demo_store.MOVIE_RESERVATIONS.clear()
    demo_store.MOVIE_NOTIFICATIONS.clear()
    demo_store.MOVIE_CHANGE_REQUESTS.clear()
    demo_store.PUSH_DEVICE_TOKENS.clear()
    demo_store.MOVIES.append(
      {
        "id": "mv-1",
        "title": "Test Title",
        "delivery_start_at": "2026-08-15T10:00",
        "approval_status": "pending_super_admin_approval",
      }
    )
    demo_store.MOVIE_RESERVATIONS.append({"user_id": "u-reserve", "movie_id": "mv-1", "status": "blocked"})
    demo_store.register_push_device_token("u-reserve", "ExponentPushToken[demo]", "android")
    demo_store.review_movie_approval("mv-1", "approve")
    assert sent[-1][0]["to"] == "ExponentPushToken[demo]", sent[-1]
    print("demo_store push target:", sent[-1][0]["to"])

    # Tokens Expo rejects are retired automatically.
    demo_store.register_push_device_token("u-reserve", "ExponentPushToken[dead]", "android")
    demo_store.dispatch_push_for_notifications(
      [{"user_id": "u-reserve", "movie_id": "mv-1", "notification_type": "download_ready", "title": "T", "message": "m"}]
    )
    dead_record = next(
      item for item in demo_store.PUSH_DEVICE_TOKENS if item["push_token"] == "ExponentPushToken[dead]"
    )
    assert dead_record["is_active"] is False, dead_record
    print("dead token retired OK")
  finally:
    persistence.send_push_messages_async = original_persistence_send
    demo_store.send_push_messages_async = original_demo_send


def check_push_helpers() -> None:
  assert push_module.is_expo_push_token("ExponentPushToken[abc]")
  assert push_module.is_expo_push_token("ExpoPushToken[abc]")
  assert not push_module.is_expo_push_token("random-token")
  assert not push_module.is_expo_push_token("")
  assert push_module.send_push_messages([]) == (0, [])
  assert push_module.send_push_messages([{"to": "not-a-token"}]) == (0, [])
  print("push token helpers OK")


if __name__ == "__main__":
  check_persistence()
  check_demo_store()
  check_push_helpers()
  check_offline_push()
  print("\nAll download-date notification checks passed.")
