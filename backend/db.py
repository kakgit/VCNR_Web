from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from fastapi import HTTPException, Request
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings
from backend.models import Base


@lru_cache(maxsize=1)
def get_engine() -> Engine:
  settings = get_settings()
  return create_engine(settings.database_url, future=True, pool_pre_ping=True)


SessionLocal = sessionmaker(
  autocommit=False,
  autoflush=False,
  bind=get_engine(),
  future=True,
)


def _requires_persistent_db(request: Request) -> bool:
  path = request.url.path
  return path.startswith("/api/admin") or path.startswith("/api/producer")


def get_db(request: Request) -> Generator[Session | None, None, None]:
  try:
    session = SessionLocal()
    session.execute(text("SELECT 1"))
  except SQLAlchemyError:
    if _requires_persistent_db(request):
      raise HTTPException(
        status_code=503,
        detail="Database unavailable. Admin and producer actions are disabled until PostgreSQL reconnects.",
      )
    yield None
    return

  try:
    yield session
  except Exception:
    session.rollback()
    raise
  finally:
    session.close()


def init_db() -> bool:
  try:
    Base.metadata.create_all(bind=get_engine())
    with get_engine().begin() as connection:
      connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) NOT NULL DEFAULT ''"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS title_category VARCHAR(120)"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS title_caption VARCHAR(255)"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS stars_required INTEGER NOT NULL DEFAULT 1"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS online_pricing_options TEXT"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS stars_required_theatre INTEGER NOT NULL DEFAULT 3"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS expected_stars INTEGER NOT NULL DEFAULT 0"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS reserve_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS reserve_star_price INTEGER NOT NULL DEFAULT 0"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS buy_now_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS release_decision VARCHAR(30) NOT NULL DEFAULT 'pending'"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS reservation_close_at VARCHAR(80)"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS delivery_start_at VARCHAR(80)"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS password_publish_at VARCHAR(80)"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS release_passcode VARCHAR(255)"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS strict_target_required BOOLEAN NOT NULL DEFAULT FALSE"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS playback_requires_subscription BOOLEAN NOT NULL DEFAULT TRUE"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS pricing_snapshot TEXT"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS wish_online_count INTEGER NOT NULL DEFAULT 0"))
      connection.execute(text("ALTER TABLE movies ADD COLUMN IF NOT EXISTS wish_theatre_count INTEGER NOT NULL DEFAULT 0"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS release_decision VARCHAR(30) NOT NULL DEFAULT 'pending'"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS online_pricing_options TEXT"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS buy_now_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS reservation_close_at VARCHAR(80)"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS delivery_start_at VARCHAR(80)"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS password_publish_at VARCHAR(80)"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS release_passcode VARCHAR(255)"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS strict_target_required BOOLEAN NOT NULL DEFAULT FALSE"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS playback_requires_subscription BOOLEAN NOT NULL DEFAULT TRUE"))
      connection.execute(text("ALTER TABLE titles ADD COLUMN IF NOT EXISTS pricing_snapshot TEXT"))
      connection.execute(text("ALTER TABLE admin_state ADD COLUMN IF NOT EXISTS star_price_settings TEXT"))
      connection.execute(text("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS reservation_kind VARCHAR(20) NOT NULL DEFAULT 'online'"))
      connection.execute(text("ALTER TABLE reservations ADD COLUMN IF NOT EXISTS quality_code VARCHAR(40)"))
      connection.execute(text("ALTER TABLE content_delivery_enrollments ADD COLUMN IF NOT EXISTS quality_code VARCHAR(40) NOT NULL DEFAULT ''"))
      connection.execute(
        text(
          """
          UPDATE reservations
          SET reservation_kind = 'online'
          WHERE reservation_kind = 'theatre'
            AND quality_code IS NOT NULL
            AND quality_code <> ''
          """
        )
      )
      connection.execute(
        text(
          """
          UPDATE content_delivery_enrollments enrollment
          SET quality_code = reservation.quality_code
          FROM reservations reservation
          JOIN titles title_record ON title_record.id = reservation.title_id
          WHERE enrollment.quality_code = ''
            AND title_record.legacy_movie_id = enrollment.movie_id
            AND reservation.user_id = enrollment.user_id
            AND reservation.reservation_kind = 'online'
            AND reservation.status IN ('blocked', 'fulfilled')
            AND reservation.quality_code IS NOT NULL
            AND reservation.quality_code <> ''
          """
        )
      )
      connection.execute(text("UPDATE content_delivery_enrollments SET quality_code = 'legacy' WHERE quality_code = ''"))
      connection.execute(text("ALTER TABLE content_delivery_enrollments DROP CONSTRAINT IF EXISTS uq_content_delivery_user_movie"))
      connection.execute(
        text(
          """
          CREATE UNIQUE INDEX IF NOT EXISTS uq_content_delivery_user_movie_quality_idx
          ON content_delivery_enrollments (user_id, movie_id, quality_code)
          """
        )
      )
      connection.execute(
        text(
          """
          INSERT INTO content_delivery_enrollments (
            user_id,
            movie_id,
            quality_code,
            wifi_only,
            charging_only,
            auto_download,
            status,
            accepted_at,
            updated_at
          )
          SELECT DISTINCT ON (reservation.user_id, title_record.legacy_movie_id, reservation.quality_code)
            reservation.user_id,
            title_record.legacy_movie_id,
            LOWER(TRIM(reservation.quality_code)),
            TRUE,
            FALSE,
            TRUE,
            'accepted',
            reservation.created_at,
            NOW()
          FROM reservations reservation
          JOIN titles title_record ON title_record.id = reservation.title_id
          WHERE title_record.legacy_movie_id IS NOT NULL
            AND title_record.legacy_movie_id <> ''
            AND reservation.reservation_kind = 'online'
            AND reservation.status IN ('blocked', 'fulfilled')
            AND reservation.quality_code IS NOT NULL
            AND reservation.quality_code <> ''
            AND NOT EXISTS (
              SELECT 1
              FROM content_delivery_enrollments enrollment
              WHERE enrollment.user_id = reservation.user_id
                AND enrollment.movie_id = title_record.legacy_movie_id
                AND enrollment.quality_code = LOWER(TRIM(reservation.quality_code))
            )
          ORDER BY reservation.user_id, title_record.legacy_movie_id, reservation.quality_code, reservation.created_at
          """
        )
      )
      connection.execute(
        text(
          """
          UPDATE reservations
          SET reservation_kind = 'theatre'
          WHERE (reservation_kind IS NULL OR reservation_kind = 'online')
            AND (quality_code IS NULL OR quality_code = '')
            AND EXISTS (
              SELECT 1
              FROM titles
              JOIN movie_wishes ON movie_wishes.movie_id = titles.legacy_movie_id
              WHERE titles.id = reservations.title_id
                AND movie_wishes.user_id = reservations.user_id
                AND movie_wishes.wish_kind = 'theatre'
            )
          """
        )
      )
      connection.execute(
        text(
          """
          UPDATE reservations
          SET reservation_kind = 'online'
          WHERE quality_code IS NOT NULL
            AND quality_code <> ''
            AND reservation_kind <> 'online'
          """
        )
      )
      connection.execute(
        text(
          """
          UPDATE movies
          SET wish_online_count = wish_count
          WHERE wish_count > 0
            AND wish_online_count = 0
            AND wish_theatre_count = 0
          """
        )
      )
    return True
  except SQLAlchemyError:
    return False
