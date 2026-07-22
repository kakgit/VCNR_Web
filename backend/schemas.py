from __future__ import annotations

from pydantic import BaseModel, Field


class CastCreditEntry(BaseModel):
  role: str = Field(min_length=2, max_length=80)
  name: str = Field(min_length=1, max_length=255)
  link: str | None = Field(default=None, max_length=500)


class HealthResponse(BaseModel):
  status: str
  app: str
  environment: str


class LoginRequest(BaseModel):
  email: str
  password: str


class RegisterRequest(BaseModel):
  name: str = Field(min_length=2)
  email: str
  password: str = Field(min_length=3)


class LoginResponse(BaseModel):
  message: str
  role: str
  next_view: str
  token: str


class ViewerSessionResponse(BaseModel):
  id: str
  name: str
  email: str
  role: str
  status: str
  star_balance: int = 0
  blocked_stars: int = 0
  disc_balance: int = 0
  reservations: list["ViewerReservationResponse"] = []
  notifications: list["ViewerNotificationResponse"] = []


class ViewerReservationResponse(BaseModel):
  movie_id: str
  title: str
  title_caption: str | None = None
  stars_required: int = 0
  status: str
  reservation_mode: str | None = None
  quality_code: str | None = None
  release_date: str | None = None


class ViewerNotificationResponse(BaseModel):
  id: int
  movie_id: str
  notification_type: str
  title: str
  message: str
  is_read: bool = False
  read_at: str | None = None
  created_at: str


class OnlinePricingOptionResponse(BaseModel):
  quality_code: str
  quality_label: str
  stars_required: int = 0
  sort_order: int = 0


class MovieResponse(BaseModel):
  id: str
  archived: bool = False
  stage: str
  approval_status: str = "published"
  approval_status_label: str = "Published"
  requires_super_admin_approval: bool = False
  title_category: str | None = None
  title: str
  title_caption: str | None = None
  poster: str | None = None
  genre: str
  cast_credits: list[CastCreditEntry] = []
  stars_required: int = 1
  online_pricing_options: list[OnlinePricingOptionResponse] = []
  stars_required_theatre: int = 3
  expected_stars: int = 0
  reserve_enabled: bool = False
  reserve_star_price: int = 0
  buy_now_enabled: bool = False
  release_decision: str = "pending"
  reservation_close_at: str | None = None
  delivery_start_at: str | None = None
  password_publish_at: str | None = None
  release_passcode: str | None = None
  strict_target_required: bool = False
  playback_requires_subscription: bool = True
  viewer_reservation_status: str | None = None
  viewer_reservation_online_status: str | None = None
  viewer_reservation_theatre_status: str | None = None
  stage_label: str
  countdown: str
  release_date: str
  description: str
  budget: str
  expected_revenue: str
  wish_count: int
  wish_online_count: int = 0
  wish_theatre_count: int = 0
  viewer_wish_kind: str | None = None
  reserve_count: int
  revenue: str
  posters: str
  music: str
  reward_bonus: str


class MovieListResponse(BaseModel):
  items: list[MovieResponse]


class AdminMovieListResponse(BaseModel):
  items: list[MovieResponse]


class MediaAssetResponse(BaseModel):
  name: str
  path: str
  url: str
  kind: str
  orientation: str | None = None


class MediaAssetListResponse(BaseModel):
  items: list[MediaAssetResponse]


class ContentQualityResponse(BaseModel):
  quality_code: str
  quality_label: str
  stars_required: int = 0
  uploaded: bool = False
  source_name: str | None = None
  source_extension: str | None = None
  chunk_count: int = 0
  uploaded_at: str | None = None


class ContentQualityListResponse(BaseModel):
  items: list[ContentQualityResponse]
  is_complete: bool = False


class DeliveryQueueItemResponse(BaseModel):
  movie_id: str
  movie_title: str
  user_id: str
  user_name: str
  user_email: str
  fifo_position: int | None = None
  quality_code: str | None = None
  quality_label: str | None = None
  stars_required: int = 0
  device_label: str | None = None
  status: str
  queue_position: int | None = None
  wifi_only: bool = True
  charging_only: bool = False
  auto_download: bool = True
  accepted_at: str
  updated_at: str
  download_started_at: str | None = None
  download_completed_at: str | None = None
  slot_expires_at: str | None = None
  last_error: str | None = None


class DeliveryQueueSummaryResponse(BaseModel):
  accepted: int = 0
  queued: int = 0
  slot_granted: int = 0
  downloading: int = 0
  downloaded: int = 0
  failed: int = 0


class DeliveryQueueListResponse(BaseModel):
  movie_id: str | None = None
  movie_title: str | None = None
  total: int = 0
  page: int = 1
  page_size: int = 50
  summary: DeliveryQueueSummaryResponse = Field(default_factory=DeliveryQueueSummaryResponse)
  items: list[DeliveryQueueItemResponse] = Field(default_factory=list)


class MovieDetailResponse(BaseModel):
  item: MovieResponse
  posters: list[MediaAssetResponse] = []
  trailers: list[MediaAssetResponse] = []
  gallery: list[MediaAssetResponse] = []
  music: list[MediaAssetResponse] = []
  content: list[MediaAssetResponse] = []


class MovieInterestRequest(BaseModel):
  kind: str = Field(pattern="^(wish|reserve|buy)$")
  wish_mode: str | None = Field(default=None, pattern="^(online|theatre)$")
  quality_code: str | None = None


class MovieInterestResponse(BaseModel):
  item: MovieResponse
  message: str


class StageUpdateRequest(BaseModel):
  stage: str = Field(pattern="^(upcoming|released|library)$")


class PublishMovieRequest(BaseModel):
  release_date: str = Field(min_length=3)


class ReleaseMainContentRequest(BaseModel):
  release_date_time: str = Field(min_length=3)
  release_passcode: str = Field(min_length=1, max_length=255)


class DeliveryPreferenceRequest(BaseModel):
  quality_code: str = Field(min_length=2, max_length=40)
  wifi_only: bool = True
  charging_only: bool = False
  auto_download: bool = True
  device_label: str | None = Field(default=None, max_length=255)


class DeliveryStatusResponse(BaseModel):
  movie_id: str
  quality_code: str | None = None
  quality_label: str | None = None
  stars_required: int = 0
  delivery_start_at: str | None = None
  password_publish_at: str | None = None
  release_date: str | None = None
  entitlement_status: str
  is_download_window_open: bool = False
  is_release_unlocked: bool = False
  release_passcode_available: bool = False
  release_passcode: str | None = None
  enrollment_status: str | None = None
  wifi_only: bool = True
  charging_only: bool = False
  auto_download: bool = True
  has_active_slot: bool = False
  slot_token: str | None = None
  slot_expires_at: str | None = None
  queue_position: int | None = None
  local_encrypted_path: str | None = None


class DeliverySlotAcquireRequest(BaseModel):
  quality_code: str = Field(min_length=2, max_length=40)
  device_label: str | None = Field(default=None, max_length=255)


class DeliverySlotResponse(BaseModel):
  movie_id: str
  quality_code: str | None = None
  status: str
  slot_token: str | None = None
  slot_expires_at: str | None = None
  queue_position: int | None = None
  retry_after_seconds: int | None = None
  manifest_ready: bool = False


class DeliveryManifestResponse(BaseModel):
  movie_id: str
  movie_title: str | None = None
  delivery_start_at: str | None = None
  upload_start_at: str | None = None
  password_publish_at: str | None = None
  qualities: list[dict] = []
  chunk_count: int = 0
  encryption: dict = {}
  files: list[dict] = []
  updated_at: str | None = None


class DeliverySlotHeartbeatRequest(BaseModel):
  slot_token: str = Field(min_length=12, max_length=120)


class DeliveryDownloadCompleteRequest(BaseModel):
  quality_code: str = Field(min_length=2, max_length=40)
  local_encrypted_path: str | None = Field(default=None, max_length=500)


class ApprovalUpdateRequest(BaseModel):
  action: str = Field(pattern="^(approve|request_changes)$")


class ApprovalReviewFieldDiffResponse(BaseModel):
  field: str
  label: str
  current_value: str
  pending_value: str


class ApprovalReviewAssetDiffResponse(BaseModel):
  kind: str
  label: str
  current_items: list[str]
  pending_items: list[str]
  added_items: list[str]
  removed_items: list[str]


class AdminMovieUpdateRequest(BaseModel):
  title_category: str
  title: str
  title_caption: str | None = None
  genre: str
  cast_credits: list[CastCreditEntry] = []
  story_line: str
  stars_required: int = Field(default=1, ge=1, le=10)
  stars_required_theatre: int = Field(default=3, ge=1, le=10)
  expected_stars: int = Field(ge=0)
  release_date: str | None = None


class AdminMovieCreateRequest(BaseModel):
  title_category: str
  title: str
  title_caption: str | None = None
  genre: str
  cast_credits: list[CastCreditEntry] = []
  story_line: str
  stars_required: int = Field(default=1, ge=1, le=10)
  stars_required_theatre: int = Field(default=3, ge=1, le=10)
  expected_stars: int = Field(default=0, ge=0)
  release_date: str | None = None
  stage: str = Field(pattern="^(upcoming|released|library)$")


class OnlinePricingOptionRequest(BaseModel):
  quality_code: str = Field(min_length=2, max_length=40)
  quality_label: str = Field(min_length=2, max_length=80)
  stars_required: int = Field(ge=1, le=10)
  sort_order: int = Field(default=0, ge=0)


class AdminMoviePricingConfigRequest(BaseModel):
  online_pricing_options: list[OnlinePricingOptionRequest] = []
  stars_required_theatre: int = Field(default=3, ge=1, le=10)
  expected_stars: int = Field(default=0, ge=0)


class MoviePublishRequest(BaseModel):
  title: str
  genre: str
  budget: str
  expected_revenue: str
  description: str
  stage: str = Field(pattern="^(upcoming|released|library)$")
  preview_only: bool = False


class PlatformSummaryResponse(BaseModel):
  tracked_titles: int
  wish_demand: int
  reserve_count: int
  reserved_revenue: str


class QueueItemResponse(BaseModel):
  id: str
  title: str
  stage: str
  status: str
  note: str


class QueueListResponse(BaseModel):
  items: list[QueueItemResponse]


class ProducerPublishResponse(BaseModel):
  item: QueueItemResponse
  movie: MovieResponse | None = None


class QueueStatusUpdateRequest(BaseModel):
  status: str = Field(pattern="^(Ready For Review|Published|Needs Changes)$")


class QueueItemUpdateResponse(BaseModel):
  item: QueueItemResponse
  message: str


class AdminSummaryResponse(BaseModel):
  featured_stage: str
  reward_campaign_boosts: int
  star_price_inr: float = 50
  star_price_usd: float = 0.0
  star_price_eur: float = 0.0
  star_price_effective_from: str | None = None
  tracked_titles: int
  queue_total: int
  queue_ready: int
  queue_published: int


class AdminActionResponse(BaseModel):
  message: str
  summary: AdminSummaryResponse


class StarPricingSettingsResponse(BaseModel):
  price_inr: float = 50
  price_usd: float = 0.0
  price_eur: float = 0.0
  effective_from: str | None = None


class StarPricingSettingsRequest(BaseModel):
  price_inr: float = Field(ge=1)
  price_usd: float = Field(ge=0)
  price_eur: float = Field(ge=0)
  effective_from: str | None = None


class AdminMovieActionResponse(BaseModel):
  message: str
  item: MovieResponse


class ApprovalReviewResponse(BaseModel):
  item: MovieResponse
  current_item: MovieResponse | None = None
  pending_item: MovieResponse | None = None
  changes: list[ApprovalReviewFieldDiffResponse]
  asset_changes: list[ApprovalReviewAssetDiffResponse]
  has_pending_changes: bool = False


class AdminUserResponse(BaseModel):
  id: str
  name: str
  email: str
  role: str
  status: str
  points: int
  star_balance: int = 0
  disc_balance: int = 0


class AdminUserListResponse(BaseModel):
  items: list[AdminUserResponse]


class AdminUserCreateRequest(BaseModel):
  name: str
  email: str
  password: str = Field(min_length=3)
  role: str = Field(pattern="^(viewer|producer|creator|admin|super_admin|advertiser)$")
  status: str = Field(pattern="^(active|disabled|pending)$")
  star_balance: int = Field(ge=0, default=0)


class AdminUserUpdateRequest(BaseModel):
  name: str
  role: str = Field(pattern="^(viewer|producer|creator|admin|super_admin|advertiser)$")
  status: str = Field(pattern="^(active|disabled|pending)$")
  star_balance: int = Field(ge=0, default=0)


class AdminUserActionResponse(BaseModel):
  message: str
  item: AdminUserResponse


class TaxonomyItemResponse(BaseModel):
  id: int
  slug: str
  name: str
  description: str | None = None
  sort_order: int
  is_active: bool


class TaxonomyListResponse(BaseModel):
  items: list[TaxonomyItemResponse]


class TaxonomyUpsertRequest(BaseModel):
  slug: str
  name: str
  description: str | None = None
  sort_order: int = 0
  is_active: bool = True


class TaxonomyActionResponse(BaseModel):
  message: str
  item: TaxonomyItemResponse
