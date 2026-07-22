from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
  pass


class MovieRecord(Base):
  __tablename__ = "movies"

  id: Mapped[str] = mapped_column(String(120), primary_key=True)
  archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  stage: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
  title_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  title_caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
  poster: Mapped[str | None] = mapped_column(String(255), nullable=True)
  genre: Mapped[str] = mapped_column(String(120), nullable=False)
  stars_required: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
  online_pricing_options: Mapped[str | None] = mapped_column(Text, nullable=True)
  stars_required_theatre: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
  expected_stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  reserve_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  reserve_star_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  buy_now_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  release_decision: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
  reservation_close_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
  delivery_start_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
  password_publish_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
  release_passcode: Mapped[str | None] = mapped_column(String(255), nullable=True)
  strict_target_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  playback_requires_subscription: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  stage_label: Mapped[str] = mapped_column(String(40), nullable=False)
  countdown: Mapped[str] = mapped_column(String(120), nullable=False)
  release_date: Mapped[str] = mapped_column(String(80), nullable=False)
  description: Mapped[str] = mapped_column(Text, nullable=False)
  budget: Mapped[str] = mapped_column(String(40), nullable=False)
  expected_revenue: Mapped[str] = mapped_column(String(40), nullable=False)
  pricing_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
  wish_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  wish_online_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  wish_theatre_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  reserve_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  revenue: Mapped[str] = mapped_column(String(40), nullable=False)
  posters: Mapped[str] = mapped_column(String(120), nullable=False)
  music: Mapped[str] = mapped_column(String(120), nullable=False)
  reward_bonus: Mapped[str] = mapped_column(String(80), nullable=False)


class MovieWishRecord(Base):
  __tablename__ = "movie_wishes"
  __table_args__ = (UniqueConstraint("movie_id", "user_id", name="uq_movie_wishes_movie_user"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id"), nullable=False, index=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  wish_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="online")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MovieChangeRequestRecord(Base):
  __tablename__ = "movie_change_requests"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id"), nullable=False, unique=True, index=True)
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_super_admin_approval", index=True)
  baseline_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
  pending_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
  baseline_assets_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
  pending_assets_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class QueueItemRecord(Base):
  __tablename__ = "publish_queue"

  id: Mapped[str] = mapped_column(String(120), primary_key=True)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  stage: Mapped[str] = mapped_column(String(20), nullable=False)
  status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
  note: Mapped[str] = mapped_column(Text, nullable=False)


class AdminStateRecord(Base):
  __tablename__ = "admin_state"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
  featured_stage: Mapped[str] = mapped_column(String(20), nullable=False)
  reward_campaign_boosts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  star_price_settings: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserRecord(Base):
  __tablename__ = "users"

  id: Mapped[str] = mapped_column(String(120), primary_key=True)
  name: Mapped[str] = mapped_column(String(255), nullable=False)
  email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
  password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
  role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
  status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
  points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class CreatorProfileRecord(Base):
  __tablename__ = "creator_profiles"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
  display_name: Mapped[str] = mapped_column(String(255), nullable=False)
  company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AdvertiserProfileRecord(Base):
  __tablename__ = "advertiser_profiles"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
  display_name: Mapped[str] = mapped_column(String(255), nullable=False)
  company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CategoryRecord(Base):
  __tablename__ = "categories"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  description: Mapped[str | None] = mapped_column(Text, nullable=True)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GenreRecord(Base):
  __tablename__ = "genres"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GradeRecord(Base):
  __tablename__ = "grades"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
  name: Mapped[str] = mapped_column(String(40), nullable=False)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LanguageRecord(Base):
  __tablename__ = "languages"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
  name: Mapped[str] = mapped_column(String(120), nullable=False)
  sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TitleRecord(Base):
  __tablename__ = "titles"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
  legacy_movie_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
  title_name: Mapped[str] = mapped_column(String(255), nullable=False)
  caption: Mapped[str | None] = mapped_column(String(255), nullable=True)
  category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
  creator_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
  stage: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
  availability_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="approved", index=True)
  archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  grade_id: Mapped[int | None] = mapped_column(ForeignKey("grades.id"), nullable=True, index=True)
  story_text: Mapped[str] = mapped_column(Text, nullable=False)
  duration_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
  cast_text: Mapped[str | None] = mapped_column(Text, nullable=True)
  production_house: Mapped[str | None] = mapped_column(String(255), nullable=True)
  release_date_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
  tentative_release_date_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
  reserve_star_price: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  online_pricing_options: Mapped[str | None] = mapped_column(Text, nullable=True)
  reserve_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  buy_now_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  release_decision: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
  reservation_close_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
  delivery_start_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
  password_publish_at: Mapped[str | None] = mapped_column(String(80), nullable=True)
  release_passcode: Mapped[str | None] = mapped_column(String(255), nullable=True)
  strict_target_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  playback_requires_subscription: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  cancellation_lock_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
  expected_revenue_target: Mapped[str | None] = mapped_column(String(80), nullable=True)
  pricing_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
  current_reserved_stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  current_wish_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class TitleGenreRecord(Base):
  __tablename__ = "title_genres"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"), nullable=False, index=True)


class TitleLanguageRecord(Base):
  __tablename__ = "title_languages"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"), nullable=False, index=True)
  language_type: Mapped[str] = mapped_column(String(40), nullable=False, default="primary")


class TitlePosterRecord(Base):
  __tablename__ = "title_posters"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
  orientation: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
  label: Mapped[str | None] = mapped_column(String(80), nullable=True)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TitleMusicRecord(Base):
  __tablename__ = "title_music"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
  music_type: Mapped[str] = mapped_column(String(40), nullable=False, default="soundtrack")
  label: Mapped[str | None] = mapped_column(String(120), nullable=True)
  is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TitleTrailerRecord(Base):
  __tablename__ = "title_trailers"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
  media_type: Mapped[str] = mapped_column(String(20), nullable=False, default="trailer")
  is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TitleContentFileRecord(Base):
  __tablename__ = "title_content_files"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
  content_part_type: Mapped[str] = mapped_column(String(30), nullable=False, default="main_feature")
  season_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
  episode_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
  is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TitleSubtitleTrackRecord(Base):
  __tablename__ = "title_subtitle_tracks"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  content_file_id: Mapped[int | None] = mapped_column(ForeignKey("title_content_files.id"), nullable=True, index=True)
  language_id: Mapped[int | None] = mapped_column(ForeignKey("languages.id"), nullable=True, index=True)
  relative_path: Mapped[str] = mapped_column(String(255), nullable=False)
  format: Mapped[str] = mapped_column(String(20), nullable=False, default="vtt")
  is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TitleAudioTrackRecord(Base):
  __tablename__ = "title_audio_tracks"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  content_file_id: Mapped[int | None] = mapped_column(ForeignKey("title_content_files.id"), nullable=True, index=True)
  language_id: Mapped[int | None] = mapped_column(ForeignKey("languages.id"), nullable=True, index=True)
  relative_path_or_track_key: Mapped[str] = mapped_column(String(255), nullable=False)
  track_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="separate_file")
  is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WalletRecord(Base):
  __tablename__ = "wallets"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
  available_stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  blocked_stars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  disks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WalletTransactionRecord(Base):
  __tablename__ = "wallet_transactions"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  transaction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
  stars_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  blocked_stars_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  disks_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
  reference_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
  note: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ReservationRecord(Base):
  __tablename__ = "reservations"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  title_id: Mapped[int] = mapped_column(ForeignKey("titles.id"), nullable=False, index=True)
  reservation_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="online", index=True)
  quality_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
  stars_required: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  status: Mapped[str] = mapped_column(String(30), nullable=False, default="blocked", index=True)
  lock_cutoff_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
  release_delivery_state: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class NotificationRecord(Base):
  __tablename__ = "notifications"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  movie_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
  notification_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
  title: Mapped[str] = mapped_column(String(255), nullable=False)
  message: Mapped[str] = mapped_column(Text, nullable=False)
  is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
  read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class PublishSubmissionRecord(Base):
  __tablename__ = "publish_submissions"

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  title_id: Mapped[int | None] = mapped_column(ForeignKey("titles.id"), nullable=True, index=True)
  creator_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
  submission_type: Mapped[str] = mapped_column(String(40), nullable=False, default="publish")
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="submitted", index=True)
  note: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ContentDeliveryEnrollmentRecord(Base):
  __tablename__ = "content_delivery_enrollments"
  __table_args__ = (UniqueConstraint("user_id", "movie_id", "quality_code", name="uq_content_delivery_user_movie_quality"),)

  id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
  movie_id: Mapped[str] = mapped_column(ForeignKey("movies.id"), nullable=False, index=True)
  quality_code: Mapped[str] = mapped_column(String(40), default="", nullable=False, index=True)
  wifi_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  charging_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  auto_download: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  status: Mapped[str] = mapped_column(String(40), default="accepted", nullable=False, index=True)
  local_encrypted_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
  device_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
  slot_token: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
  slot_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  download_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  download_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
  accepted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
