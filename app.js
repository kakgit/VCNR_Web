import {
  FragmentedMp4Assembler,
  joinBytes,
  mimeFromInitializationSegment,
} from "./mp4_segments.js";

const DEMO_STREAM_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8";
const MAGIC = new TextEncoder().encode("VCNRCMP3");
const VERSION = 3;
const END_MARKER = 0xffffffff;
const MAX_HEADER = 1024 * 1024;
const MAX_CIPHER = 1024 * 1024 + 16;
const SAMPLE_CONFIG_PATH = "/sample-config.json";
const API_BASE = "/api";
const entryMode = document.body.dataset.entry || "viewer";

const movieSeed = [];

let movies = movieSeed.map((movie) => ({ ...movie }));
let publishQueue = [];

let activeStage = "upcoming";
let selectedMovieId = movies[0]?.id || "";
let activeView = "viewer";
let sessionToken = window.localStorage.getItem("cineproxima_session_token") || "";
let viewerSessionProfile = null;
let activeAccountPanel = "profile";
let activeAccountEntry = "account";
let activeWishMovieId = "";
let activeReserveMovieId = "";
let activeReserveAction = "reserve";
let activeAdminPanel = "users";
let adminSessionProfile = {
  role: window.localStorage.getItem("cineproxima_session_role") || "",
  email: window.localStorage.getItem("cineproxima_session_email") || "",
};

const viewSections = Array.from(document.querySelectorAll("[data-view]"));
const navViewTriggers = Array.from(document.querySelectorAll("[data-nav-view]"));
const authForm = document.getElementById("authForm");
const authEmail = document.getElementById("authEmail");
const authPassword = document.getElementById("authPassword");
const authHelper = document.getElementById("authHelper");
const openSignupButton = document.getElementById("openSignupButton");
const signupForm = document.getElementById("signupForm");
const signupName = document.getElementById("signupName");
const signupEmail = document.getElementById("signupEmail");
const signupPassword = document.getElementById("signupPassword");
const signupConfirmPassword = document.getElementById("signupConfirmPassword");
const signupHelper = document.getElementById("signupHelper");
const closeSignupButton = document.getElementById("closeSignupButton");
const guestEntryButton = document.getElementById("guestEntryButton");
const viewerDiscBalance = document.getElementById("viewerDiscBalance");
const viewerStarBalance = document.getElementById("viewerStarBalance");
const viewerAccountButton = document.getElementById("viewerAccountButton");
const accountBackButton = document.getElementById("accountBackButton");
const accountPageTitle = document.getElementById("accountPageTitle");
const accountPageSubtitle = document.getElementById("accountPageSubtitle");
const accountProfileName = document.getElementById("accountProfileName");
const accountProfileEmail = document.getElementById("accountProfileEmail");
const accountSidebarStars = document.getElementById("accountSidebarStars");
const accountSidebarDiscs = document.getElementById("accountSidebarDiscs");
const accountOverviewStars = document.getElementById("accountOverviewStars");
const accountOverviewStarsValue = document.getElementById("accountOverviewStarsValue");
const accountOverviewDiscs = document.getElementById("accountOverviewDiscs");
const accountOverviewDiscsValue = document.getElementById("accountOverviewDiscsValue");
const accountOverviewLibrary = document.getElementById("accountOverviewLibrary");
const accountOverviewUpcoming = document.getElementById("accountOverviewUpcoming");
const accountReferralCode = document.getElementById("accountReferralCode");
const accountReferralUsers = document.getElementById("accountReferralUsers");
const accountReferralEarnings = document.getElementById("accountReferralEarnings");
const accountCopyReferralButton = document.getElementById("accountCopyReferralButton");
const accountWalletStars = document.getElementById("accountWalletStars");
const accountWalletBlockedStars = document.getElementById("accountWalletBlockedStars");
const accountWalletDiscs = document.getElementById("accountWalletDiscs");
const accountWalletValue = document.getElementById("accountWalletValue");
const accountMoviesList = document.getElementById("accountMoviesList");
const accountReservationsList = document.getElementById("accountReservationsList");
const accountSettingsRole = document.getElementById("accountSettingsRole");
const accountSettingsStatus = document.getElementById("accountSettingsStatus");
const accountSettingsEmail = document.getElementById("accountSettingsEmail");
const viewerAccountSignoutButton = document.getElementById("viewerAccountSignoutButton");
const accountPanelTriggers = Array.from(document.querySelectorAll("[data-account-panel-target]"));
const accountPanelViews = Array.from(document.querySelectorAll("[data-account-panel-view]"));

const stageTabs = Array.from(document.querySelectorAll(".stage-tab"));
const stripStageLinks = Array.from(document.querySelectorAll(".main-strip [data-stage]"));
const movieGrid = document.getElementById("movieGrid");
const catalogHero = document.querySelector(".catalog-hero");
const movieGridSection = document.querySelector(".movie-grid-section");
const viewerHeadline = document.getElementById("viewerHeadline");
const viewerSubhead = document.getElementById("viewerSubhead");
const viewerCount = document.getElementById("viewerCount");
const spotlightTitle = document.getElementById("spotlightTitle");
const spotlightMeta = document.getElementById("spotlightMeta");
const spotlightCopy = document.getElementById("spotlightCopy");
const spotlightWish = document.getElementById("spotlightWish");
const spotlightReserve = document.getElementById("spotlightReserve");
const spotlightRevenue = document.getElementById("spotlightRevenue");
const viewerTitleDetailPage = document.getElementById("viewerTitleDetailPage");
const viewerTitleBackdrop = document.getElementById("viewerTitleBackdrop");
const viewerTitleBackButton = document.getElementById("viewerTitleBackButton");
const detailTitle = document.getElementById("detailTitle");
const detailCaption = document.getElementById("detailCaption");
const detailStage = document.getElementById("detailStage");
const detailDescription = document.getElementById("detailDescription");
const detailPosterImage = document.getElementById("detailPosterImage");
const detailStagePill = document.getElementById("detailStagePill");
const detailCategory = document.getElementById("detailCategory");
const detailGenre = document.getElementById("detailGenre");
const detailReleaseDate = document.getElementById("detailReleaseDate");
const detailUploadDateTime = document.getElementById("detailUploadDateTime");
const detailReleaseDateTime = document.getElementById("detailReleaseDateTime");
const detailStarsRequired = document.getElementById("detailStarsRequired");
const detailExpected = document.getElementById("detailExpected");
const detailTargetProgressFill = document.getElementById("detailTargetProgressFill");
const detailTargetProgressLabel = document.getElementById("detailTargetProgressLabel");
const detailCastCredits = document.getElementById("detailCastCredits");
const detailDownloadStatus = document.getElementById("detailDownloadStatus");
const detailDownloadAction = document.getElementById("detailDownloadAction");
const detailPosterPlayButton = document.getElementById("detailPosterPlayButton");
const detailWatchNowButton = document.getElementById("detailWatchNowButton");
const detailWishButton = document.getElementById("detailWishButton");
const detailReserveButton = document.getElementById("detailReserveButton");
const detailPostersButton = document.getElementById("detailPostersButton");
const detailTrailersButton = document.getElementById("detailTrailersButton");
const detailGalleryButton = document.getElementById("detailGalleryButton");
const detailMusicButton = document.getElementById("detailMusicButton");
const detailContentButton = document.getElementById("detailContentButton");
const viewerAssetModal = document.getElementById("viewerAssetModal");
const viewerAssetModalTitle = document.getElementById("viewerAssetModalTitle");
const viewerAssetModalBody = document.getElementById("viewerAssetModalBody");
const viewerLocalContentInput = document.getElementById("viewerLocalContentInput");
const viewerWishModal = document.getElementById("viewerWishModal");
const viewerWishModalMovie = document.getElementById("viewerWishModalMovie");
const viewerReserveModal = document.getElementById("viewerReserveModal");
const viewerReserveModalMovie = document.getElementById("viewerReserveModalMovie");
const viewerReserveModalCopy = document.getElementById("viewerReserveModalCopy");
const viewerReserveConfirmButton = document.getElementById("viewerReserveConfirmButton");
const metricTitles = document.getElementById("metricTitles");
const metricWish = document.getElementById("metricWish");
const metricRevenue = document.getElementById("metricRevenue");

const producerQueue = document.getElementById("producerQueue");
const adminReviewList = document.getElementById("adminReviewList");
const adminOpenViewer = document.getElementById("adminOpenViewer");
const adminHeaderSignoutButton = document.getElementById("adminHeaderSignoutButton");
const adminHelper = document.getElementById("adminHelper");
const adminFeaturedStage = document.getElementById("adminFeaturedStage");
const adminQueueReady = document.getElementById("adminQueueReady");
const adminRewardBoosts = document.getElementById("adminRewardBoosts");
const adminStarPricingNavLink = document.getElementById("adminStarPricingNavLink");
const adminStarPricingNavValue = document.getElementById("adminStarPricingNavValue");
const adminStarPriceSummary = document.getElementById("adminStarPriceSummary");
const adminStarPricingForm = document.getElementById("adminStarPricingForm");
const adminStarPriceInr = document.getElementById("adminStarPriceInr");
const adminStarPriceUsd = document.getElementById("adminStarPriceUsd");
const adminStarPriceEur = document.getElementById("adminStarPriceEur");
const adminStarPriceEffectiveFrom = document.getElementById("adminStarPriceEffectiveFrom");
const adminStarPricingFeedback = document.getElementById("adminStarPricingFeedback");
const adminMovieList = document.getElementById("adminMovieList");
const adminArchiveMovieList = document.getElementById("adminArchiveMovieList");
const adminLibrarySearch = document.getElementById("adminLibrarySearch");
const adminLibraryStage = document.getElementById("adminLibraryStage");
const adminLibrarySort = document.getElementById("adminLibrarySort");
const adminAddLibraryButton = document.getElementById("adminAddLibraryButton");
const adminUserList = document.getElementById("adminUserList");
const adminUserSearch = document.getElementById("adminUserSearch");
const adminUserSort = document.getElementById("adminUserSort");
const adminAddUserButton = document.getElementById("adminAddUserButton");
const adminUserModal = document.getElementById("adminUserModal");
const adminUserEditor = document.getElementById("adminUserEditor");
const adminUserEditId = document.getElementById("adminUserEditId");
const adminUserModalTitle = document.getElementById("adminUserModalTitle");
const adminUserModalCopy = document.getElementById("adminUserModalCopy");
const adminUserName = document.getElementById("adminUserName");
const adminUserEmail = document.getElementById("adminUserEmail");
const adminUserPassword = document.getElementById("adminUserPassword");
const adminUserPasswordField = document.getElementById("adminUserPasswordField");
const adminUserRole = document.getElementById("adminUserRole");
const adminUserStatus = document.getElementById("adminUserStatus");
const adminUserPoints = document.getElementById("adminUserPoints");
const adminUserCancelButton = document.getElementById("adminUserCancelButton");
const adminDeleteDialog = document.getElementById("adminDeleteDialog");
const adminDeleteTitle = document.getElementById("adminDeleteTitle");
const adminDeleteKicker = adminDeleteDialog?.querySelector(".section-kicker");
const adminDeleteCopy = document.getElementById("adminDeleteCopy");
const adminDeleteConfirmButton = document.getElementById("adminDeleteConfirmButton");
const adminDeleteCancelButton = document.getElementById("adminDeleteCancelButton");
const adminPanelTriggers = Array.from(document.querySelectorAll("[data-admin-panel-target]"));
const adminPanelViews = Array.from(document.querySelectorAll("[data-admin-panel-view]"));
const adminUsersCount = document.getElementById("adminUsersCount");
const adminCategoriesCount = document.getElementById("adminCategoriesCount");
const adminLibraryCount = document.getElementById("adminLibraryCount");
const adminTotalUsers = document.getElementById("adminTotalUsers");
const adminActiveUsers = document.getElementById("adminActiveUsers");
const adminPendingUsers = document.getElementById("adminPendingUsers");
const adminTrackedTitles = document.getElementById("adminTrackedTitles");
const adminArchiveCount = document.getElementById("adminArchiveCount");
const adminArchiveNavLink = document.getElementById("adminArchiveNavLink");
const adminArchiveNavCount = document.getElementById("adminArchiveNavCount");
const adminArchiveSection = document.getElementById("adminArchiveSection");
const adminQueueTotal = document.getElementById("adminQueueTotal");
const adminDeliveryQueueNavLink = document.getElementById("adminDeliveryQueueNavLink");
const adminDeliveryQueueCount = document.getElementById("adminDeliveryQueueCount");
const adminDeliveryQueueMovieTitle = document.getElementById("adminDeliveryQueueMovieTitle");
const adminDeliveryQueueMovieSubtitle = document.getElementById("adminDeliveryQueueMovieSubtitle");
const adminDeliveryQueueSummary = document.getElementById("adminDeliveryQueueSummary");
const adminDeliveryQueueList = document.getElementById("adminDeliveryQueueList");
const adminDeliveryQueueSearch = document.getElementById("adminDeliveryQueueSearch");
const adminDeliveryQueueStatus = document.getElementById("adminDeliveryQueueStatus");
const adminDeliveryQueueRefresh = document.getElementById("adminDeliveryQueueRefresh");
const adminTaxonomyList = document.getElementById("adminTaxonomyList");
const adminTaxonomySearch = document.getElementById("adminTaxonomySearch");
const adminTaxonomyKind = document.getElementById("adminTaxonomyKind");
const adminTaxonomySort = document.getElementById("adminTaxonomySort");
const adminAddTaxonomyButton = document.getElementById("adminAddTaxonomyButton");
const adminTaxonomyModal = document.getElementById("adminTaxonomyModal");
const adminTaxonomyEditor = document.getElementById("adminTaxonomyEditor");
const adminTaxonomyEditId = document.getElementById("adminTaxonomyEditId");
const adminTaxonomyModalTitle = document.getElementById("adminTaxonomyModalTitle");
const adminTaxonomyModalCopy = document.getElementById("adminTaxonomyModalCopy");
const adminTaxonomyEditorKind = document.getElementById("adminTaxonomyEditorKind");
const adminTaxonomyName = document.getElementById("adminTaxonomyName");
const adminTaxonomySlug = document.getElementById("adminTaxonomySlug");
const adminTaxonomySortOrder = document.getElementById("adminTaxonomySortOrder");
const adminTaxonomyStatus = document.getElementById("adminTaxonomyStatus");
const adminTaxonomyDescription = document.getElementById("adminTaxonomyDescription");
const adminTaxonomyCancelButton = document.getElementById("adminTaxonomyCancelButton");
const adminLibraryModal = document.getElementById("adminLibraryModal");
const adminLibraryEditor = document.getElementById("adminLibraryEditor");
const adminLibraryEditId = document.getElementById("adminLibraryEditId");
const adminLibraryModalTitle = document.getElementById("adminLibraryModalTitle");
const adminLibraryModalCopy = document.getElementById("adminLibraryModalCopy");
const adminLibraryCategory = document.getElementById("adminLibraryCategory");
const adminLibraryTitle = document.getElementById("adminLibraryTitle");
const adminLibraryCaption = document.getElementById("adminLibraryCaption");
const adminLibraryGenre = document.getElementById("adminLibraryGenre");
const adminLibraryMovieStage = document.getElementById("adminLibraryMovieStage");
const adminLibraryExpectedDate = document.getElementById("adminLibraryExpectedDate");
const adminLibraryCastCredits = document.getElementById("adminLibraryCastCredits");
const adminLibraryAddCastCreditButton = document.getElementById("adminLibraryAddCastCreditButton");
const adminLibraryDescription = document.getElementById("adminLibraryDescription");
const adminLibraryCancelButton = document.getElementById("adminLibraryCancelButton");
const adminPricingTargetsModal = document.getElementById("adminPricingTargetsModal");
const adminPricingTargetsForm = document.getElementById("adminPricingTargetsForm");
const adminPricingTargetsMovieId = document.getElementById("adminPricingTargetsMovieId");
const adminPricingTargetsCopy = document.getElementById("adminPricingTargetsCopy");
const adminPricingOnlineRows = document.getElementById("adminPricingOnlineRows");
const adminPricingAddOnlineRowButton = document.getElementById("adminPricingAddOnlineRowButton");
const adminPricingTheatreStars = document.getElementById("adminPricingTheatreStars");
const adminPricingTargetStars = document.getElementById("adminPricingTargetStars");
const adminPricingTargetsCancelButton = document.getElementById("adminPricingTargetsCancelButton");
const adminReservationCloseAt = document.getElementById("adminReservationCloseAt");
const adminPasswordPublishAt = document.getElementById("adminPasswordPublishAt");
const adminReleaseMainContentModal = document.getElementById("adminReleaseMainContentModal");
const adminReleaseMainContentForm = document.getElementById("adminReleaseMainContentForm");
const adminReleaseMainContentMovieId = document.getElementById("adminReleaseMainContentMovieId");
const adminReleaseMainContentCopy = document.getElementById("adminReleaseMainContentCopy");
const adminReleaseMainContentDateTime = document.getElementById("adminReleaseMainContentDateTime");
const adminReleaseMainContentPasscode = document.getElementById("adminReleaseMainContentPasscode");
const adminReleaseMainContentCancelButton = document.getElementById("adminReleaseMainContentCancelButton");
const adminApprovalModal = document.getElementById("adminApprovalModal");
const adminApprovalMovieId = document.getElementById("adminApprovalMovieId");
const adminApprovalCopy = document.getElementById("adminApprovalCopy");
const adminApprovalDiffList = document.getElementById("adminApprovalDiffList");
const adminApprovalAssetList = document.getElementById("adminApprovalAssetList");
const adminApprovalApproveButton = document.getElementById("adminApprovalApproveButton");
const adminApprovalCancelButton = document.getElementById("adminApprovalCancelButton");
const adminPosterUploadModal = document.getElementById("adminPosterUploadModal");
const adminPosterUploadForm = document.getElementById("adminPosterUploadForm");
const adminPosterMovieId = document.getElementById("adminPosterMovieId");
const adminPosterFiles = document.getElementById("adminPosterFiles");
const adminPosterUploadPreview = document.getElementById("adminPosterUploadPreview");
const adminPosterAssetList = document.getElementById("adminPosterAssetList");
const adminPosterCancelButton = document.getElementById("adminPosterCancelButton");
const adminTrailerUploadModal = document.getElementById("adminTrailerUploadModal");
const adminTrailerUploadForm = document.getElementById("adminTrailerUploadForm");
const adminTrailerMovieId = document.getElementById("adminTrailerMovieId");
const adminTrailerFile = document.getElementById("adminTrailerFile");
const adminTrailerAssetList = document.getElementById("adminTrailerAssetList");
const adminTrailerCancelButton = document.getElementById("adminTrailerCancelButton");
const adminGalleryUploadModal = document.getElementById("adminGalleryUploadModal");
const adminGalleryUploadForm = document.getElementById("adminGalleryUploadForm");
const adminGalleryMovieId = document.getElementById("adminGalleryMovieId");
const adminGalleryFile = document.getElementById("adminGalleryFile");
const adminGalleryAssetList = document.getElementById("adminGalleryAssetList");
const adminGalleryCancelButton = document.getElementById("adminGalleryCancelButton");
const adminMusicUploadModal = document.getElementById("adminMusicUploadModal");
const adminMusicUploadForm = document.getElementById("adminMusicUploadForm");
const adminMusicMovieId = document.getElementById("adminMusicMovieId");
const adminMusicFile = document.getElementById("adminMusicFile");
const adminMusicAssetList = document.getElementById("adminMusicAssetList");
const adminMusicCancelButton = document.getElementById("adminMusicCancelButton");
const adminContentUploadModal = document.getElementById("adminContentUploadModal");
const adminContentUploadForm = document.getElementById("adminContentUploadForm");
const adminContentMovieId = document.getElementById("adminContentMovieId");
const adminContentFiles = document.getElementById("adminContentFiles");
const adminContentPassword = document.getElementById("adminContentPassword");
const adminContentGeneratePasswordButton = document.getElementById("adminContentGeneratePasswordButton");
const adminContentUploadStartAt = document.getElementById("adminContentUploadStartAt");
const adminContentAssetList = document.getElementById("adminContentAssetList");
const adminContentUploadPreview = document.getElementById("adminContentUploadPreview");
const adminContentDeleteFolderButton = document.getElementById("adminContentDeleteFolderButton");
const adminContentCancelButton = document.getElementById("adminContentCancelButton");
const adminContentUploadStartAtDisplay = document.getElementById("adminContentUploadStartAtDisplay");
const adminLibraryUploadStartAtDisplay = document.getElementById("adminLibraryUploadStartAtDisplay");

let adminContentPreviewUrls = new Map();
let adminContentQualityState = {
  movieId: "",
  items: [],
  isComplete: false,
};
const adminSessionRole = document.getElementById("adminSessionRole");
const adminSessionEmail = document.getElementById("adminSessionEmail");
const adminSignoutButton = document.getElementById("adminSignoutButton");
const adminSignoutSidebarButton = document.getElementById("adminSignoutSidebarButton");

const superAdminNavLink = document.getElementById("superAdminNavLink");
const adminSuperCount = document.getElementById("adminSuperCount");
const adminSuperUsers = document.getElementById("adminSuperUsers");
const adminTaxonomyTotal = document.getElementById("adminTaxonomyTotal");
const adminTaxonomyItemsCount = document.getElementById("adminTaxonomyItemsCount");
const adminTaxonomyActiveCount = document.getElementById("adminTaxonomyActiveCount");
const adminTaxonomyGroupCount = document.getElementById("adminTaxonomyGroupCount");
const adminRoleCount = document.getElementById("adminRoleCount");
const superAdminTaxonomyGrid = document.getElementById("superAdminTaxonomyGrid");

const video = document.getElementById("video");
const form = document.getElementById("streamForm");
const streamUrlInput = document.getElementById("streamUrl");
const vcnrUrlInput = document.getElementById("vcnrUrl");
const vcnrFileInput = document.getElementById("vcnrFile");
const passcodeInput = document.getElementById("passcode");
const statusText = document.getElementById("status");
const metadataPanel = document.getElementById("metadata");
const liveBadge = document.getElementById("liveBadge");
const loadDemoButton = document.getElementById("loadDemo");
const stopButton = document.getElementById("stopStream");
const playVcnrButton = document.getElementById("playVcnr");
const sampleBox = document.getElementById("sampleBox");
const sampleLabel = document.getElementById("sampleLabel");
const sampleLoadButton = document.getElementById("sampleLoad");
const modeTabs = Array.from(document.querySelectorAll(".mode-tab"));
const modePanels = Array.from(document.querySelectorAll(".mode-panel"));

let hlsInstance = null;
let activeObjectUrl = null;
let activeReader = null;
let activeMediaSource = null;
let activeAbortController = null;
let stopped = false;
let sampleUrl = null;
let adminSummaryState = null;
let adminStarPricingState = null;
let adminMovies = [];
let adminUsers = [];
let adminUserSearchTerm = "";
let adminUserSortValue = "name-desc";
let adminUserPage = 1;
const ADMIN_USERS_PER_PAGE = 5;
let adminPendingDelete = null;
let adminTaxonomySearchTerm = "";
let adminTaxonomyKindFilter = "all";
let adminTaxonomySortValue = "kind-asc";
let adminTaxonomyPage = 1;
const ADMIN_TAXONOMY_PER_PAGE = 6;
let adminLibrarySearchTerm = "";
let adminLibraryStageFilter = "all";
let adminLibrarySortValue = "title-asc";
let adminLibraryPage = 1;
const ADMIN_LIBRARY_PER_PAGE = 5;
let adminDeliveryQueueMovieId = "";
let adminDeliveryQueueSearchTerm = "";
let adminDeliveryQueueStatusFilter = "all";
let adminDeliveryQueuePage = 1;
let adminDeliveryQueuePageSize = 25;
let adminDeliveryQueueState = null;
let adminTaxonomies = {
  categories: [],
  genres: [],
  grades: [],
};
const ADMIN_ONLINE_QUALITY_OPTIONS = [
  { code: "360p", label: "360p low bandwidth" },
  { code: "480p", label: "480p SD" },
  { code: "720p", label: "720p HD" },
  { code: "1080p", label: "1080p Full HD" },
  { code: "1440p", label: "1440p / 2K QHD" },
  { code: "2160p", label: "2160p / 4K UHD" },
];
let adminPosterAssets = [];
let adminPosterCarouselIndex = 0;
let adminTrailerAssets = [];
let adminTrailerCarouselIndex = 0;
let adminGalleryAssets = [];
let adminGalleryCarouselIndex = 0;
let adminMusicAssets = [];
let adminMusicCarouselIndex = 0;
let adminApprovalReview = null;
let viewerMovieDetails = new Map();
let viewerDetailState = {
  movieId: "",
  item: null,
  posters: [],
  trailers: [],
  gallery: [],
  music: [],
  content: [],
};
let viewerAssetCarouselState = {
  kind: "",
  title: "",
  items: [],
  index: 0,
};
let viewerContentManifestCache = new Map();
let viewerLocalContentPlaybackUrl = "";

function formatRoleLabel(role) {
  if (role === "producer" || role === "creator") {
    return "Creator";
  }
  if (role === "advertiser") {
    return "Advertiser";
  }
  if (role === "super_admin") {
    return "Super Admin";
  }
  return role.charAt(0).toUpperCase() + role.slice(1);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character] || character;
  });
}

function toAssetUrl(path) {
  if (!path) {
    return "/media/posters/no-poster.svg";
  }
  if (/^(https?:)?\/\//i.test(path) || path.startsWith("/")) {
    return path;
  }
  return `/${path.replace(/^\/+/, "")}`;
}

function getAdminUserSortMeta() {
  const [key = "name", direction = "asc"] = (adminUserSortValue || "name-asc").split("-");
  return { key, direction };
}

function compareAdminUsers(first, second, key, direction) {
  const multiplier = direction === "desc" ? -1 : 1;
  let left = first[key];
  let right = second[key];

  if (key === "points" || key === "star_balance" || key === "disc_balance") {
    left = Number(left || 0);
    right = Number(right || 0);
    return (left - right) * multiplier;
  }

  left = String(left || "").toLowerCase();
  right = String(right || "").toLowerCase();
  return left.localeCompare(right) * multiplier;
}

function getProcessedAdminUsers() {
  const searchTerm = adminUserSearchTerm.trim().toLowerCase();
  const filteredUsers = adminUsers.filter((user) => {
    if (!searchTerm) {
      return true;
    }

    return [user.name, user.email, user.role, user.status]
      .some((value) => String(value || "").toLowerCase().includes(searchTerm));
  });

  const { key, direction } = getAdminUserSortMeta();
  const sortedUsers = [...filteredUsers].sort((first, second) => compareAdminUsers(first, second, key, direction));
  const totalPages = Math.max(1, Math.ceil(sortedUsers.length / ADMIN_USERS_PER_PAGE));
  adminUserPage = Math.min(adminUserPage, totalPages);
  adminUserPage = Math.max(adminUserPage, 1);

  const startIndex = (adminUserPage - 1) * ADMIN_USERS_PER_PAGE;
  const pagedUsers = sortedUsers.slice(startIndex, startIndex + ADMIN_USERS_PER_PAGE);

  return {
    filteredUsers,
    sortedUsers,
    pagedUsers,
    totalPages,
    startIndex,
  };
}

function formatTaxonomyKindLabel(kind) {
  const labels = {
    categories: "Category",
    genres: "Genre",
    grades: "Grade",
  };
  return labels[kind] || kind;
}

function formatClassificationKindLabel(kind) {
  return formatTaxonomyKindLabel(kind);
}

function getFlattenedTaxonomies() {
  return Object.entries(adminTaxonomies).flatMap(([kind, items]) =>
    (items || []).map((item) => ({ ...item, kind }))
  );
}

function compareAdminTaxonomies(first, second, key, direction) {
  const multiplier = direction === "desc" ? -1 : 1;
  let left = first[key];
  let right = second[key];

  if (key === "sort_order") {
    return (Number(left || 0) - Number(right || 0)) * multiplier;
  }

  if (key === "is_active") {
    return (Number(Boolean(left)) - Number(Boolean(right))) * multiplier;
  }

  left = String(left || "").toLowerCase();
  right = String(right || "").toLowerCase();
  return left.localeCompare(right) * multiplier;
}

function getProcessedAdminTaxonomies() {
  const searchTerm = adminTaxonomySearchTerm.trim().toLowerCase();
  const items = getFlattenedTaxonomies()
    .filter((item) => adminTaxonomyKindFilter === "all" || item.kind === adminTaxonomyKindFilter)
    .filter((item) => {
      if (!searchTerm) {
        return true;
      }

      return [item.name, item.slug, item.description, item.kind]
        .some((value) => String(value || "").toLowerCase().includes(searchTerm));
    });

  const [key = "kind", direction = "asc"] = adminTaxonomySortValue.split("-");
  const sortedItems = [...items].sort((first, second) => compareAdminTaxonomies(first, second, key, direction));
  const totalPages = Math.max(1, Math.ceil(sortedItems.length / ADMIN_TAXONOMY_PER_PAGE));
  adminTaxonomyPage = Math.min(adminTaxonomyPage, totalPages);
  adminTaxonomyPage = Math.max(adminTaxonomyPage, 1);
  const startIndex = (adminTaxonomyPage - 1) * ADMIN_TAXONOMY_PER_PAGE;
  const pagedItems = sortedItems.slice(startIndex, startIndex + ADMIN_TAXONOMY_PER_PAGE);

  return {
    filteredItems: items,
    sortedItems,
    pagedItems,
    totalPages,
    startIndex,
  };
}

function getAdminMovieSortMeta() {
  const [key = "title", direction = "asc"] = (adminLibrarySortValue || "title-asc").split("-");
  return { key, direction };
}

function getAdminMovieStageLabel(movie) {
  if (movie.archived) {
    return "Archived";
  }
  return movie.stageLabel || buildStageLabel(movie.stage);
}

function formatAdminReleaseDate(value) {
  if (!value || value === "TBA") {
    return "TBA";
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  const day = String(parsedDate.getDate()).padStart(2, "0");
  const month = String(parsedDate.getMonth() + 1).padStart(2, "0");
  const year = String(parsedDate.getFullYear());
  const hours = String(parsedDate.getHours()).padStart(2, "0");
  const minutes = String(parsedDate.getMinutes()).padStart(2, "0");
  const hasExplicitTime = /(\d{1,2}:\d{2})|T\d{2}:\d{2}/.test(String(value));

  return hasExplicitTime ? `${day}-${month}-${year} ${hours}:${minutes}` : `${day}-${month}-${year}`;
}

function formatViewerUploadDateTime(value) {
  if (!value) {
    return "Not set";
  }

  const parsedDate = new Date(value);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  const day = String(parsedDate.getDate()).padStart(2, "0");
  const month = String(parsedDate.getMonth() + 1).padStart(2, "0");
  const year = String(parsedDate.getFullYear());
  const hours = String(parsedDate.getHours()).padStart(2, "0");
  const minutes = String(parsedDate.getMinutes()).padStart(2, "0");
  return `${day}-${month}-${year} ${hours}:${minutes}`;
}

function isViewerDownloadUnlocked(movie) {
  if (!movie?.deliveryStartAt) {
    return false;
  }
  const parsedDate = new Date(movie.deliveryStartAt);
  return !Number.isNaN(parsedDate.getTime()) && parsedDate.getTime() <= Date.now();
}

function compareAdminMovies(first, second, key, direction) {
  const multiplier = direction === "desc" ? -1 : 1;

  if (key === "wishCount" || key === "reserveCount") {
    return ((Number(first[key] || 0) - Number(second[key] || 0)) * multiplier);
  }

  if (key === "releaseDate") {
    const left = Date.parse(first.releaseDate || "");
    const right = Date.parse(second.releaseDate || "");
    const safeLeft = Number.isNaN(left) ? 0 : left;
    const safeRight = Number.isNaN(right) ? 0 : right;
    return (safeLeft - safeRight) * multiplier;
  }

  const left = String(first[key] || "").toLowerCase();
  const right = String(second[key] || "").toLowerCase();
  return left.localeCompare(right) * multiplier;
}

function getProcessedAdminMovies() {
  const searchTerm = adminLibrarySearchTerm.trim().toLowerCase();
  const filteredMovies = adminMovies
    .filter((movie) => {
      if (movie.archived) {
        return false;
      }
      if (adminLibraryStageFilter === "all") {
        return true;
      }
      return movie.stage === adminLibraryStageFilter;
    })
    .filter((movie) => {
      if (!searchTerm) {
        return true;
      }

      return [movie.title, movie.genre, movie.description, movie.releaseDate, movie.stage]
        .some((value) => String(value || "").toLowerCase().includes(searchTerm));
    });

  const { key, direction } = getAdminMovieSortMeta();
  const sortedMovies = [...filteredMovies].sort((first, second) => compareAdminMovies(first, second, key, direction));
  const totalPages = Math.max(1, Math.ceil(sortedMovies.length / ADMIN_LIBRARY_PER_PAGE));
  adminLibraryPage = Math.min(adminLibraryPage, totalPages);
  adminLibraryPage = Math.max(adminLibraryPage, 1);
  const startIndex = (adminLibraryPage - 1) * ADMIN_LIBRARY_PER_PAGE;
  const pagedMovies = sortedMovies.slice(startIndex, startIndex + ADMIN_LIBRARY_PER_PAGE);

  return {
    filteredMovies,
    pagedMovies,
    totalPages,
    startIndex,
  };
}

function getProcessedArchivedMovies() {
  const searchTerm = adminLibrarySearchTerm.trim().toLowerCase();
  const archivedMovies = adminMovies
    .filter((movie) => movie.archived)
    .filter((movie) => {
      if (!searchTerm) {
        return true;
      }

      return [movie.title, movie.genre, movie.description, movie.releaseDate, movie.stage]
        .some((value) => String(value || "").toLowerCase().includes(searchTerm));
    })
    .sort((first, second) => compareAdminMovies(first, second, "title", "asc"));

  return archivedMovies;
}

class ExactReader {
  constructor(stream) {
    this.reader = stream.getReader();
    this.pending = new Uint8Array(0);
  }

  async readExact(length) {
    const output = new Uint8Array(length);
    let written = 0;

    while (written < length) {
      if (this.pending.length) {
        const count = Math.min(this.pending.length, length - written);
        output.set(this.pending.subarray(0, count), written);
        written += count;
        this.pending = this.pending.subarray(count);
        continue;
      }

      const { value, done } = await this.reader.read();
      if (done) {
        throw new Error("The VCNR stream ended unexpectedly.");
      }
      this.pending = value;
    }

    return output;
  }

  async uint32() {
    const bytes = await this.readExact(4);
    return new DataView(bytes.buffer, bytes.byteOffset, 4).getUint32(0, false);
  }

  cancel() {
    return this.reader.cancel().catch(() => {});
  }
}

function formatNumber(value) {
  const numericValue = Number(value ?? 0);
  return Number.isFinite(numericValue) ? numericValue.toLocaleString("en-US") : "0";
}

function buildStageLabel(stage) {
  if (stage === "released") {
    return "New Release";
  }
  if (stage === "library") {
    return "Library";
  }
  return "Upcoming";
}

function formatReleaseDecisionLabel(value) {
  if (value === "scheduled") {
    return "Scheduled";
  }
  if (value === "confirmed") {
    return "Confirmed";
  }
  if (value === "cancelled") {
    return "Cancelled";
  }
  return "Pending";
}

function getApprovalStatusClass(status) {
  if (status === "published") {
    return "is-published";
  }
  if (status === "approved") {
    return "is-approved";
  }
  if (status === "changes_requested") {
    return "is-changes-requested";
  }
  if (status === "archived") {
    return "is-archived";
  }
  return "is-pending";
}

function isViewerVisibleStatus(status) {
  return ["approved", "published"].includes(status);
}

function canApproveMovie(movie) {
  return !movie.archived && !["approved", "published"].includes(movie.approvalStatus);
}

function canToggleReserve(movie) {
  return !movie.archived
    && movie.stage === "upcoming"
    && !movie.buyNowEnabled
    && ["approved", "published"].includes(movie.approvalStatus);
}

function hasOnlinePricingOption(movie) {
  return Array.isArray(movie?.onlinePricingOptions) && movie.onlinePricingOptions.some((item) => Number(item.starsRequired || 0) > 0);
}

function buildAdminPricingSummaryMarkup(movie) {
  const options = Array.isArray(movie?.onlinePricingOptions) ? movie.onlinePricingOptions : [];
  if (!options.length) {
    return '<div class="admin-pricing-summary is-empty">No online pricing added</div>';
  }

  return `
    <div class="admin-pricing-summary" aria-label="Online pricing options">
      ${options
        .map((item) => `
          <span class="admin-pricing-chip">
            ${escapeHtml(item.qualityLabel || item.qualityCode)}
            <b>${escapeHtml(formatNumber(item.starsRequired))} ${Number(item.starsRequired) === 1 ? "Star" : "Stars"}</b>
          </span>
        `)
        .join("")}
    </div>
  `;
}

function buildStageName(stage) {
  if (stage === "released") {
    return "New Released";
  }
  if (stage === "library") {
    return "Library";
  }
  return "Up Coming";
}

function getViewerEffectiveStage(movie) {
  if (!movie) {
    return "upcoming";
  }
  if (movie.stage === "library") {
    return "library";
  }
  if (movie.stage === "released") {
    return "released";
  }
  const releaseAt = movie.passwordPublishAt ? new Date(movie.passwordPublishAt) : null;
  if (releaseAt && !Number.isNaN(releaseAt.getTime()) && releaseAt.getTime() <= Date.now()) {
    return "released";
  }
  return movie.stage || "upcoming";
}

function isViewerCollectionMovie(movie) {
  const stage = getViewerEffectiveStage(movie);
  const reservedByViewer = movie.viewerReservationStatus === "blocked" || movie.viewerReservationStatus === "fulfilled";
  return (stage === "released" || stage === "library") && reservedByViewer;
}

function refreshTimeDrivenMovieViews() {
  refreshViewerStageHeader();
  renderMovieGrid();
  renderAccountView();
  renderAdminMovieList();
  if (viewerTitleDetailPage && !viewerTitleDetailPage.classList.contains("hidden") && viewerDetailState.item) {
    renderViewerDetailPage(viewerDetailState);
  }
}

function formatRevenueFromCounts(count) {
  return `$${Math.round(count * 0.025)}K`;
}

function toDateTimeLocalValue(value) {
  if (!value) {
    return "";
  }

  const normalized = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(normalized)) {
    return normalized.slice(0, 16);
  }

  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const hours = String(parsed.getHours()).padStart(2, "0");
  const minutes = String(parsed.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function generateStrongPassword(length = 16) {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*";
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  let password = "";
  for (let index = 0; index < length; index += 1) {
    password += alphabet[bytes[index] % alphabet.length];
  }
  return password;
}

function isMovieWished(movie) {
  return Boolean(movie?.viewerWishKind);
}

function isMovieReserveReady(movie) {
  return Boolean(movie?.reserveEnabled) && (activeStage === "upcoming" || activeStage === "wishlist");
}

function isMovieBuyReady(movie) {
  if (!movie) {
    return false;
  }
  return getViewerEffectiveStage(movie) === "released" && movie.viewerReservationStatus !== "blocked" && movie.viewerReservationStatus !== "fulfilled";
}

function getWishButtonMarkup(movie) {
  const wished = isMovieWished(movie);
  return `
    <button
      type="button"
      class="wish-watch-btn${wished ? " is-active" : ""}"
      data-movie-card-wish="${movie.id}"
      aria-label="${wished ? `${movie.title} is already in your wishlist` : `Wish 2 Watch ${movie.title}`}"
      ${wished ? "disabled" : ""}
    >
      <span class="wish-watch-icon" aria-hidden="true">${wished ? "&#10003;" : "&#9825;"}</span>
      <span>${wished ? "In Wishlist" : "Wish 2 Watch"}</span>
    </button>
  `;
}

function getMovieCardActionMarkup(movie) {
  const effectiveStage = getViewerEffectiveStage(movie);
  const alreadyOwnedOrReserved = movie.viewerReservationStatus === "blocked" || movie.viewerReservationStatus === "fulfilled";

  if (effectiveStage === "released" || effectiveStage === "library") {
    if (isMovieBuyReady(movie) && !alreadyOwnedOrReserved) {
      return `
        <button
          type="button"
          class="wish-watch-btn reserve-now-btn is-blinking"
          data-movie-card-reserve="${movie.id}"
          aria-label="Buy Now for ${movie.title}"
        >
          <span class="wish-watch-icon" aria-hidden="true">&#9733;</span>
          <span>Buy Now</span>
        </button>
        <button
          type="button"
          class="ghost-btn viewer-card-details-btn"
          data-movie-card-details="${movie.id}"
          aria-label="Open details for ${movie.title}"
        >
          Details
        </button>
      `;
    }

    const playLabel = "Watch Now";
    return `
      <button
        type="button"
        class="wish-watch-btn reserve-now-btn is-active"
        data-movie-card-play="${movie.id}"
        aria-label="${playLabel} ${movie.title}"
      >
        <span class="wish-watch-icon" aria-hidden="true">&#9654;</span>
        <span>${playLabel}</span>
      </button>
      <button
        type="button"
        class="ghost-btn viewer-card-details-btn"
        data-movie-card-details="${movie.id}"
        aria-label="Open details for ${movie.title}"
      >
        Details
      </button>
    `;
  }

  if (activeStage === "reserved") {
    const fulfilled = movie.viewerReservationStatus === "fulfilled";
    const reserved = movie.viewerReservationStatus === "blocked" || fulfilled;
    const label = fulfilled ? "Owned" : reserved ? "Reserved" : "Reserve";
    return `
      <button
        type="button"
        class="wish-watch-btn reserve-now-btn is-active"
        data-movie-card-reserve="${movie.id}"
        aria-label="${label} for ${movie.title}"
        disabled
      >
        <span class="wish-watch-icon" aria-hidden="true">&#9733;</span>
        <span>${label}</span>
      </button>
    `;
  }

  const reserveReady = isMovieReserveReady(movie);
  if (reserveReady) {
    const alreadyReserved = movie.viewerReservationStatus === "blocked" || movie.viewerReservationStatus === "fulfilled";
    const reserveLabel = movie.viewerReservationStatus === "fulfilled"
      ? "Owned"
      : alreadyReserved
        ? "Reserved"
        : "Reserve Now";
    const reserveClass = alreadyReserved ? " is-active" : " is-blinking";
    return `
      <button
        type="button"
        class="wish-watch-btn reserve-now-btn${reserveClass}"
        data-movie-card-reserve="${movie.id}"
        aria-label="${reserveLabel} for ${movie.title}"
        ${alreadyReserved ? "disabled" : ""}
      >
        <span class="wish-watch-icon" aria-hidden="true">&#9733;</span>
        <span>${reserveLabel}</span>
      </button>
    `;
  }

  return getWishButtonMarkup(movie);
}

async function apiRequest(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (sessionToken) {
    headers.Authorization = `Bearer ${sessionToken}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Ignore invalid JSON error bodies.
    }
    if (response.status === 401) {
      clearSessionToken();
    }
    throw new Error(message);
  }

  return response.json();
}

async function apiUploadRequest(path, formData, options = {}) {
  const headers = {
    ...(options.headers || {}),
  };

  if (sessionToken) {
    headers.Authorization = `Bearer ${sessionToken}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Ignore invalid JSON error bodies.
    }
    if (response.status === 401) {
      clearSessionToken();
    }
    throw new Error(message);
  }

  return response.json();
}

async function apiDeleteRequest(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
  };

  if (sessionToken) {
    headers.Authorization = `Bearer ${sessionToken}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Ignore invalid JSON error bodies.
    }
    if (response.status === 401) {
      clearSessionToken();
    }
    throw new Error(message);
  }

  return response.json();
}

function saveSessionToken(token) {
  sessionToken = token || "";
  if (sessionToken) {
    window.localStorage.setItem("cineproxima_session_token", sessionToken);
  } else {
    window.localStorage.removeItem("cineproxima_session_token");
    window.localStorage.removeItem("cineproxima_session_role");
    window.localStorage.removeItem("cineproxima_session_email");
  }
}

function syncViewerHeader() {
  setText(viewerDiscBalance, formatNumber(viewerSessionProfile?.disc_balance ?? 0));
  setText(viewerStarBalance, formatNumber(viewerSessionProfile?.star_balance ?? 0));
  if (viewerAccountButton) {
    viewerAccountButton.textContent = viewerSessionProfile ? "My Account" : "Sign In";
  }
}

function formatCurrencyInr(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN")}`;
}

function buildReferralCode(profile) {
  if (!profile) {
    return "CV000000";
  }
  const emailRoot = String(profile.email || "viewer").split("@")[0].replace(/[^a-z0-9]/gi, "").toUpperCase();
  const idRoot = String(profile.id || "0000").replace(/[^a-z0-9]/gi, "").toUpperCase();
  return `CV${(emailRoot + idRoot).slice(0, 10)}`;
}

function renderAccountList(container, items, emptyText) {
  if (!container) {
    return;
  }
  if (!items.length) {
    container.innerHTML = `<p class="account-empty-copy">${emptyText}</p>`;
    return;
  }
  container.innerHTML = items.map((item) => `
    <article class="account-list-item">
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(item.meta)}</span>
    </article>
  `).join("");
}

function renderAccountView() {
  const profile = viewerSessionProfile;
  const stars = Number(profile?.star_balance ?? 0);
  const blockedStars = Number(profile?.blocked_stars ?? 0);
  const discs = Number(profile?.disc_balance ?? 0);
  const collectionReservations = Array.isArray(profile?.reservations)
    ? profile.reservations.filter((item) => {
      if (item.status !== "fulfilled") {
        return false;
      }
      const linkedMovie = movies.find((movie) => movie.id === item.movie_id);
      return linkedMovie ? isViewerCollectionMovie(linkedMovie) && isViewerVisibleStatus(linkedMovie.approvalStatus) : false;
    })
    : [];
  const collectionTitles = collectionReservations
    .map((item) => ({
      reservation: item,
      movie: movies.find((movie) => movie.id === item.movie_id) || null,
    }))
    .filter((item) => item.movie);
  const reservations = Array.isArray(profile?.reservations)
    ? profile.reservations.filter((item) => {
      const linkedMovie = movies.find((movie) => movie.id === item.movie_id);
      return linkedMovie ? getViewerEffectiveStage(linkedMovie) === "upcoming" : true;
    })
    : [];
  const referralUsers = Math.max(0, Math.min(9, Math.floor(discs / 150)));
  const referralEarnings = referralUsers * 100;

  setText(accountPageTitle, activeAccountEntry === "collection" ? "My Collection" : "My Account");
  setText(
    accountPageSubtitle,
    activeAccountEntry === "collection"
      ? "Purchased titles that are ready to watch after release"
      : "Manage your profile, stars, and movie collection"
  );
  setText(accountProfileName, profile?.name || "Guest Viewer");
  setText(accountProfileEmail, profile?.email || "Sign in to view your account");
  setText(accountSidebarStars, formatNumber(stars));
  setText(accountSidebarDiscs, formatNumber(discs));
  setText(accountOverviewStars, formatNumber(stars));
  setText(accountOverviewStarsValue, `${formatCurrencyInr(stars * 100)} value`);
  setText(accountOverviewDiscs, formatNumber(discs));
  setText(accountOverviewDiscsValue, `${formatNumber(discs)} disks`);
  setText(accountOverviewLibrary, formatNumber(collectionTitles.length));
  setText(accountOverviewUpcoming, formatNumber(reservations.length));
  setText(accountReferralCode, buildReferralCode(profile));
  setText(accountReferralUsers, formatNumber(referralUsers));
  setText(accountReferralEarnings, formatCurrencyInr(referralEarnings));
  setText(accountWalletStars, formatNumber(stars));
  setText(accountWalletBlockedStars, formatNumber(blockedStars));
  setText(accountWalletDiscs, formatNumber(discs));
  setText(accountWalletValue, formatCurrencyInr(stars * 100));
  setText(accountSettingsRole, formatRoleLabel(profile?.role || "viewer"));
  setText(accountSettingsStatus, String(profile?.status || "guest"));
  setText(accountSettingsEmail, profile?.email || "Not signed in");

  renderAccountList(
    accountMoviesList,
    collectionTitles.map(({ movie, reservation }) => ({
      title: movie.title,
      meta: `${movie.genre} - Purchased - ${reservation.release_date || movie.releaseDate || "TBA"}`,
    })),
    "No purchased titles are ready yet."
  );
  renderAccountList(
    accountReservationsList,
    reservations.map((item) => ({
      title: item.title,
      meta: `${item.status === "fulfilled" ? "Ready to watch" : `${item.stars_required} star${Number(item.stars_required || 0) === 1 ? "" : "s"} blocked`} - ${item.release_date || "TBA"}`,
    })),
    "No reserved titles are listed yet."
  );
}

function setAccountPanel(panel) {
  activeAccountPanel = panel;
  accountPanelTriggers.forEach((trigger) => {
    trigger.classList.toggle("is-active", trigger.dataset.accountPanelTarget === panel);
  });
  accountPanelViews.forEach((section) => {
    section.classList.toggle("is-active", section.dataset.accountPanelView === panel);
  });
}

function handleViewerSignout() {
  clearSessionToken();
  closeViewerDetailPage({ syncHash: false });
  closeViewerAssetModal();
  closeViewerWishModal();
  closeViewerReserveModal();
  closeSignupFlow();
  setAccountPanel("profile");
  setView("auth");
}

function clearSessionToken() {
  saveSessionToken("");
  viewerSessionProfile = null;
  viewerMovieDetails.clear();
  movies = movies.map((movie) => ({ ...movie, viewerWishKind: "" }));
  setAdminSession("", "");
  syncViewerHeader();
  renderAccountView();
  renderMovieGrid();
  syncDetailPanel();
}

function normalizeMovie(movie) {
  return {
    id: movie.id,
    archived: Boolean(movie.archived),
    stage: movie.stage,
    approvalStatus: movie.approval_status || (movie.archived ? "archived" : "published"),
    approvalStatusLabel: movie.approval_status_label || (movie.archived ? "Archived" : "Published"),
    requiresSuperAdminApproval: Boolean(movie.requires_super_admin_approval),
    titleCategory: movie.title_category || "",
    title: movie.title,
    titleCaption: movie.title_caption || "",
    poster: movie.poster || null,
    genre: movie.genre,
    castCredits: Array.isArray(movie.cast_credits)
      ? movie.cast_credits
        .map((item) => ({
          role: String(item?.role || "").trim(),
          name: String(item?.name || "").trim(),
          link: String(item?.link || "").trim(),
        }))
        .filter((item) => item.role && item.name)
      : [],
    onlinePricingOptions: Array.isArray(movie.online_pricing_options)
      ? movie.online_pricing_options
        .map((item) => ({
          qualityCode: String(item?.quality_code || "").trim().toLowerCase(),
          qualityLabel: String(item?.quality_label || "").trim(),
          starsRequired: Number(item?.stars_required || 0),
          sortOrder: Number(item?.sort_order || 0),
        }))
        .filter((item) => item.qualityCode && item.qualityLabel && item.starsRequired > 0)
      : [],
    starsRequired: Number(movie.stars_required || 1),
    starsRequiredTheatre: Number(movie.stars_required_theatre || movie.reserve_star_price || 3),
    expectedStars: Number(movie.expected_stars || 0),
    reserveEnabled: Boolean(movie.reserve_enabled),
    reserveStarPrice: Number(movie.reserve_star_price || movie.stars_required || 0),
    buyNowEnabled: Boolean(movie.buy_now_enabled),
    releaseDecision: movie.release_decision || "pending",
    reservationCloseAt: movie.reservation_close_at || "",
    deliveryStartAt: movie.delivery_start_at || "",
    passwordPublishAt: movie.password_publish_at || "",
    releasePasscode: movie.release_passcode || "",
    strictTargetRequired: Boolean(movie.strict_target_required),
    playbackRequiresSubscription: movie.playback_requires_subscription !== false,
    viewerReservationStatus: movie.viewer_reservation_status || "",
    stageLabel: movie.stage_label,
    countdown: movie.countdown,
    releaseDate: movie.release_date,
    description: movie.description,
    budget: movie.budget,
    expectedRevenue: movie.expected_revenue,
    wishCount: Number(movie.wish_count || 0),
    wishOnlineCount: Number(movie.wish_online_count || 0),
    wishTheatreCount: Number(movie.wish_theatre_count || 0),
    viewerWishKind: movie.viewer_wish_kind || "",
    reserveCount: movie.reserve_count,
    revenue: movie.revenue,
    posters: movie.posters,
    music: movie.music,
    rewardBonus: movie.reward_bonus,
  };
}

function normalizeCastCreditEntry(entry = {}) {
  return {
    role: String(entry.role || "").trim(),
    name: String(entry.name || "").trim(),
    link: String(entry.link || "").trim(),
  };
}

function formatAdminDateForInput(value) {
  const raw = String(value || "").trim();
  if (!raw || raw.toUpperCase() === "TBA") {
    return "";
  }

  const asDate = (dateValue) => {
    if (!(dateValue instanceof Date) || Number.isNaN(dateValue.getTime())) {
      return "";
    }
    const year = String(dateValue.getFullYear());
    const month = String(dateValue.getMonth() + 1).padStart(2, "0");
    const day = String(dateValue.getDate()).padStart(2, "0");
    const hours = String(dateValue.getHours()).padStart(2, "0");
    const minutes = String(dateValue.getMinutes()).padStart(2, "0");
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  };

  const ddmmyyyyMatch = raw.match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (ddmmyyyyMatch) {
    const [, day, month, year] = ddmmyyyyMatch;
    return `${year}-${month}-${day}`;
  }

  const yyyymmddMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (yyyymmddMatch) {
    return raw;
  }

  const isoDateTimeMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::\d{2})?(?:\.\d+)?$/);
  if (isoDateTimeMatch) {
    const [, year, month, day, hour, minute] = isoDateTimeMatch;
    return `${year}-${month}-${day}T${hour}:${minute}`;
  }

  const parsedDate = new Date(raw);
  return Number.isNaN(parsedDate.getTime()) ? "" : asDate(parsedDate);
}

function formatAdminDateTimeDisplay(value) {
  const raw = String(value || "").trim();
  if (!raw || raw.toUpperCase() === "TBA") {
    return "Not set";
  }

  const ddmmyyyyTimeMatch = raw.match(/^(\d{2})-(\d{2})-(\d{4})[T ](\d{2}):(\d{2})(?::\d{2})?(?:\.\d+)?$/);
  if (ddmmyyyyTimeMatch) {
    const [, day, month, year, hours, minutes] = ddmmyyyyTimeMatch;
    return `${day}-${month}-${year} ${hours}:${minutes}`;
  }

  const parsedDate = new Date(raw);
  if (!Number.isNaN(parsedDate.getTime())) {
    const day = String(parsedDate.getDate()).padStart(2, "0");
    const month = String(parsedDate.getMonth() + 1).padStart(2, "0");
    const year = String(parsedDate.getFullYear());
    const hours = String(parsedDate.getHours()).padStart(2, "0");
    const minutes = String(parsedDate.getMinutes()).padStart(2, "0");
    return `${day}-${month}-${year} ${hours}:${minutes}`;
  }

  return raw;
}

function formatAdminUploadStartLabel(uploadStartAt) {
  return `Upload Start Date Time - ${formatAdminDateTimeDisplay(uploadStartAt)}`;
}

function formatAdminDateForApi(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "";
  }

  const yyyymmddMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (yyyymmddMatch) {
    const [, year, month, day] = yyyymmddMatch;
    return `${day}-${month}-${year}`;
  }

  return raw;
}

function getTargetProgressPercent(movie) {
  const targetStars = Number(movie?.expectedStars || 0);
  const currentStars = Number(movie?.reserveCount || 0);
  if (targetStars <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round((currentStars / targetStars) * 100)));
}

function getMovieCastCredits(movie) {
  return Array.isArray(movie?.castCredits) ? movie.castCredits.map(normalizeCastCreditEntry).filter((item) => item.role && item.name) : [];
}

function renderViewerCastCredits(movie) {
  if (!detailCastCredits) {
    return;
  }

  const items = getMovieCastCredits(movie);
  if (!items.length) {
    detailCastCredits.innerHTML = `<p class="viewer-title-cast-empty">Cast and credits will appear here after they are added.</p>`;
    return;
  }

  detailCastCredits.innerHTML = items.map((item) => {
    const hasLink = item.link && /^https?:\/\//i.test(item.link);
    const nameMarkup = hasLink
      ? `<a class="viewer-title-cast-link" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer noopener">${escapeHtml(item.name)}</a>`
      : `<span class="viewer-title-cast-name">${escapeHtml(item.name)}</span>`;
    return `
      <div class="viewer-title-cast-row">
        <span class="viewer-title-cast-role">${escapeHtml(item.role)}</span>
        <div>${nameMarkup}</div>
      </div>
    `;
  }).join("");
}

function renderViewerDownloadLinks(movie) {
  if (!detailDownloadStatus || !detailDownloadAction) {
    return;
  }

  const contentItems = viewerDetailState.content || [];
  const unlockLabel = movie?.deliveryStartAt ? formatViewerUploadDateTime(movie.deliveryStartAt) : "Not set";
  const unlocked = isViewerDownloadUnlocked(movie) && contentItems.length > 0;
  const ownedForDownload = isViewerCollectionMovie(movie);

  if (!movie?.deliveryStartAt && !contentItems.length) {
    detailDownloadStatus.textContent = "No downloadable content has been uploaded yet.";
    detailDownloadAction.innerHTML = "";
    return;
  }

  if (!ownedForDownload) {
    detailDownloadStatus.textContent = "Buy this title to unlock the downloadable content package.";
    detailDownloadAction.innerHTML = `
      <div class="viewer-download-empty">
        Download will become available here right after Buy Now is confirmed.
      </div>
    `;
    return;
  }

  if (!unlocked) {
    detailDownloadStatus.textContent = `Downloads unlock from ${unlockLabel}.`;
    detailDownloadAction.innerHTML = `
      <div class="viewer-download-empty">
        Download Now will appear here after the scheduled time.
      </div>
    `;
    return;
  }

  detailDownloadStatus.textContent = `Downloads are available from ${unlockLabel}.`;
  detailDownloadAction.innerHTML = `
    <button
      type="button"
      class="primary-btn viewer-download-button"
      data-download-movie-id="${escapeHtml(movie.id)}"
      data-download-filename="${escapeHtml(`${movie.title || "title"}-content.zip`)}"
    >
      Download Now
    </button>
  `;
}

async function saveBlobToUserLocation(blob, suggestedName) {
  if (window.showSaveFilePicker) {
    try {
      const fileHandle = await window.showSaveFilePicker({
        suggestedName,
        types: [
          {
            description: "Zip archive",
            accept: {
              "application/zip": [".zip"],
            },
          },
        ],
      });
      const writable = await fileHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    } catch (error) {
      if (error?.name === "AbortError") {
        throw error;
      }
      // If the native picker fails on a repeat attempt, fall back to a normal browser download.
    }
  }

  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = suggestedName;
  anchor.rel = "noreferrer";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

async function downloadMovieContentPackage(movieId, suggestedName) {
  const headers = {};
  if (sessionToken) {
    headers.Authorization = `Bearer ${sessionToken}`;
  }
  const response = await fetch(`/api/movies/${encodeURIComponent(movieId)}/content/download?ts=${Date.now()}`, {
    cache: "no-store",
    headers,
  });
  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;
    try {
      const payload = await response.json();
      if (payload && typeof payload.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Ignore non-JSON error bodies.
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  await saveBlobToUserLocation(blob, suggestedName);
}

function renderAdminCastCreditRows(items = []) {
  if (!adminLibraryCastCredits) {
    return;
  }

  const rows = items.length ? items : [{}];
  adminLibraryCastCredits.innerHTML = rows.map((entry, index) => {
    const normalized = normalizeCastCreditEntry(entry);

    return `
      <div class="admin-cast-credit-row" data-cast-credit-row="${index}">
        <label class="field">
          <span class="sr-only">Role Title</span>
          <input type="text" data-cast-credit-role placeholder="Role title" value="${escapeHtml(normalized.role)}">
        </label>
        <label class="field">
          <span class="sr-only">Name</span>
          <input type="text" data-cast-credit-name placeholder="Name of cast or credit" value="${escapeHtml(normalized.name)}">
        </label>
        <label class="field">
          <span class="sr-only">External link</span>
          <input type="url" data-cast-credit-link placeholder="https://example.com/profile" value="${escapeHtml(normalized.link)}">
        </label>
        <button type="button" class="icon-btn danger" data-remove-cast-credit-row title="Remove row" aria-label="Remove row">&#128465;</button>
      </div>
    `;
  }).join("");
}

function readAdminCastCreditRows() {
  if (!adminLibraryCastCredits) {
    return [];
  }

  return Array.from(adminLibraryCastCredits.querySelectorAll("[data-cast-credit-row]"))
    .map((row) => ({
      role: row.querySelector("[data-cast-credit-role]")?.value.trim() || "",
      name: row.querySelector("[data-cast-credit-name]")?.value.trim() || "",
      link: row.querySelector("[data-cast-credit-link]")?.value.trim() || "",
    }))
    .filter((item) => item.role || item.name || item.link);
}

function appendAdminCastCreditRow() {
  const items = readAdminCastCreditRows();
  items.push({ role: "", name: "", link: "" });
  renderAdminCastCreditRows(items);
}

function renderAdminPricingRows(items = []) {
  if (!adminPricingOnlineRows) {
    return;
  }

  const rows = items.length ? items : [{ qualityCode: "", qualityLabel: "", starsRequired: "" }];
  const optionsMarkup = ADMIN_ONLINE_QUALITY_OPTIONS
    .map((item) => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.label)}</option>`)
    .join("");

  adminPricingOnlineRows.innerHTML = rows.map((entry, index) => {
    const qualityCode = String(entry.qualityCode || entry.quality_code || "").trim().toLowerCase();
    const starsRequired = String(entry.starsRequired || entry.stars_required || "").trim();
    return `
      <div class="admin-pricing-row" data-pricing-row="${index}">
        <label class="field">
          <span class="sr-only">Quality</span>
          <select class="select-input" data-pricing-quality>
            <option value="">Select quality</option>
            ${optionsMarkup}
          </select>
        </label>
        <label class="field">
          <span class="sr-only">Stars required</span>
          <input type="number" min="1" max="10" step="1" data-pricing-stars placeholder="Stars required" value="${escapeHtml(starsRequired)}">
        </label>
        <button type="button" class="icon-btn danger" data-remove-pricing-row title="Remove row" aria-label="Remove row">&#128465;</button>
      </div>
    `;
  }).join("");

  Array.from(adminPricingOnlineRows.querySelectorAll("[data-pricing-row]")).forEach((row, index) => {
    const select = row.querySelector("[data-pricing-quality]");
    const qualityCode = String(rows[index].qualityCode || rows[index].quality_code || "").trim().toLowerCase();
    if (select) {
      select.value = qualityCode;
    }
  });
}

function readAdminPricingRows() {
  if (!adminPricingOnlineRows) {
    return [];
  }

  return Array.from(adminPricingOnlineRows.querySelectorAll("[data-pricing-row]"))
    .map((row, index) => {
      const qualityCode = row.querySelector("[data-pricing-quality]")?.value.trim().toLowerCase() || "";
      const label = ADMIN_ONLINE_QUALITY_OPTIONS.find((item) => item.code === qualityCode)?.label || "";
      const starsRequired = Number(row.querySelector("[data-pricing-stars]")?.value || 0);
      return {
        qualityCode,
        qualityLabel: label,
        starsRequired,
        sortOrder: index,
      };
    })
    .filter((item) => item.qualityCode || item.starsRequired);
}

function appendAdminPricingRow() {
  const items = readAdminPricingRows();
  items.push({ qualityCode: "", qualityLabel: "", starsRequired: "", sortOrder: items.length });
  renderAdminPricingRows(items);
}

function replaceMovies(items) {
  movies = items.map(normalizeMovie);
  if (!movies.some((movie) => movie.id === selectedMovieId)) {
    selectedMovieId = movies[0]?.id || "";
  }
}

function replaceQueue(items) {
  publishQueue = items.map((item) => ({ ...item }));
}

function applyPlatformSummary(summary) {
  setText(metricTitles, String(summary.tracked_titles));
  setText(metricWish, formatNumber(summary.wish_demand));
  setText(metricRevenue, summary.reserved_revenue);
}

async function loadMoviesFromApi() {
  const response = await apiRequest("/movies");
  replaceMovies(response.items || []);
}

async function loadMovieDetailsFromApi(movieId, { force = false } = {}) {
  if (!movieId) {
    return null;
  }
  if (!force && viewerMovieDetails.has(movieId)) {
    return viewerMovieDetails.get(movieId);
  }

  const response = await apiRequest(`/movies/${movieId}/details`);
  const detail = {
    item: normalizeMovie(response.item),
    posters: response.posters || [],
    trailers: response.trailers || [],
    gallery: response.gallery || [],
    music: response.music || [],
    content: response.content || [],
  };
  viewerMovieDetails.set(movieId, detail);
  return detail;
}

function openViewerContentHandleStore() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      resolve(null);
      return;
    }

    const request = window.indexedDB.open("cineproxima-local-content", 1);
    request.addEventListener("upgradeneeded", () => {
      const database = request.result;
      if (!database.objectStoreNames.contains("handles")) {
        database.createObjectStore("handles");
      }
    });
    request.addEventListener("success", () => {
      resolve(request.result);
    });
    request.addEventListener("error", () => {
      reject(request.error || new Error("Could not open local content storage."));
    });
  });
}

async function getStoredLocalContentHandle(movieId) {
  if (!movieId) {
    return null;
  }
  const database = await openViewerContentHandleStore();
  if (!database) {
    return null;
  }

  return new Promise((resolve, reject) => {
    const transaction = database.transaction("handles", "readonly");
    const store = transaction.objectStore("handles");
    const request = store.get(movieId);
    request.addEventListener("success", () => {
      resolve(request.result || null);
    });
    request.addEventListener("error", () => {
      reject(request.error || new Error("Could not read the saved content link."));
    });
  });
}

async function saveStoredLocalContentHandle(movieId, handle) {
  if (!movieId || !handle) {
    return;
  }
  const database = await openViewerContentHandleStore();
  if (!database) {
    return;
  }

  await new Promise((resolve, reject) => {
    const transaction = database.transaction("handles", "readwrite");
    const store = transaction.objectStore("handles");
    const request = store.put(handle, movieId);
    request.addEventListener("success", () => resolve());
    request.addEventListener("error", () => reject(request.error || new Error("Could not save the content link.")));
  });
}

async function deleteStoredLocalContentHandle(movieId) {
  if (!movieId) {
    return;
  }
  const database = await openViewerContentHandleStore();
  if (!database) {
    return;
  }

  await new Promise((resolve, reject) => {
    const transaction = database.transaction("handles", "readwrite");
    const store = transaction.objectStore("handles");
    const request = store.delete(movieId);
    request.addEventListener("success", () => resolve());
    request.addEventListener("error", () => reject(request.error || new Error("Could not clear the saved content link.")));
  });
}

async function loadMovieContentManifest(movieId, { force = false } = {}) {
  if (!movieId) {
    return null;
  }
  if (!force && viewerContentManifestCache.has(movieId)) {
    return viewerContentManifestCache.get(movieId);
  }

  const manifest = await apiRequest(`/movies/${movieId}/content/manifest`);
  viewerContentManifestCache.set(movieId, manifest);
  return manifest;
}

function getViewerDetailHash(movieId) {
  return movieId ? `#title/${encodeURIComponent(movieId)}` : "";
}

function getMovieIdFromHash() {
  const hash = String(window.location.hash || "");
  const matched = hash.match(/^#title\/(.+)$/);
  if (!matched) {
    return "";
  }
  try {
    return decodeURIComponent(matched[1]);
  } catch {
    return "";
  }
}

async function loadPlatformSummaryFromApi() {
  const summary = await apiRequest("/platform/summary");
  applyPlatformSummary(summary);
}

async function loadPublishQueueFromApi() {
  const response = await apiRequest("/producer/queue");
  replaceQueue(response.items || []);
}

async function loadAdminSummaryFromApi() {
  adminSummaryState = await apiRequest("/admin/summary");
  applyAdminSummary(adminSummaryState);
}

async function loadAdminStarPricingFromApi() {
  adminStarPricingState = await apiRequest("/admin/star-pricing");
  applyAdminStarPricing(adminStarPricingState);
}

async function loadAdminMoviesFromApi() {
  const response = await apiRequest("/admin/movies");
  adminMovies = (response.items || []).map(normalizeMovie);
}

async function loadAdminUsersFromApi() {
  const response = await apiRequest("/admin/users");
  adminUsers = response.items || [];
}

async function loadAdminTaxonomiesFromApi() {
  const [categories, genres, grades] = await Promise.all([
    apiRequest("/admin/taxonomies/categories"),
    apiRequest("/admin/taxonomies/genres"),
    apiRequest("/admin/taxonomies/grades"),
  ]);
  adminTaxonomies = {
    categories: categories.items || [],
    genres: genres.items || [],
    grades: grades.items || [],
  };
  renderAdminLibraryOptions();
}

async function loadViewerSessionFromApi() {
  if (!sessionToken) {
    viewerSessionProfile = null;
    syncViewerHeader();
    renderAccountView();
    return null;
  }

  const profile = await apiRequest("/auth/me");
  viewerSessionProfile = profile;
  viewerMovieDetails.clear();
  await loadMoviesFromApi();
  syncViewerHeader();
  renderAccountView();
  return profile;
}

async function bootstrapAppData() {
  try {
    await Promise.all([loadMoviesFromApi(), loadPlatformSummaryFromApi(), loadPublishQueueFromApi()]);
    let profile = null;
    if (sessionToken) {
      profile = await loadViewerSessionFromApi();
      if (profile && ["admin", "super_admin"].includes(profile.role)) {
        setAdminSession(profile.role, profile.email);
        await loadAdminSummaryFromApi();
        await Promise.all([loadAdminStarPricingFromApi(), loadAdminMoviesFromApi(), loadAdminUsersFromApi(), loadAdminTaxonomiesFromApi()]);
      }
      if (entryMode === "admin" && profile && ["admin", "super_admin"].includes(profile.role)) {
        setView("admin");
        setAdminPanel(profile.role === "super_admin" ? "super-admin" : "users");
      } else if (entryMode === "creator" && profile && ["producer", "creator"].includes(profile.role)) {
        setView("viewer");
      }
    } else {
      syncViewerHeader();
    }
    renderMovieGrid();
    syncDetailPanel();
    renderPublishQueue();
    renderAdminMovieList();
    renderAdminArchiveMovieList();
    renderAdminUserList();
    renderSuperAdminPanel();
    setStage(activeStage);
    await prefetchStageMovieDetails(activeStage);
    renderMovieGrid();
    const hashMovieId = getMovieIdFromHash();
    if (hashMovieId) {
      await openViewerDetailPage(hashMovieId, { syncHash: false });
    } else {
      showViewerCatalogPage();
    }
    renderAccountView();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Backend sync failed.";
    const sessionExpired = !sessionToken && /401|unauthorized|expired|invalid/i.test(message);
    if ((entryMode === "admin" || entryMode === "creator") && sessionExpired) {
      setAdminSession("", "");
      adminMovies = [];
      adminUsers = [];
      adminStarPricingState = null;
      if (adminStarPricingFeedback) {
        adminStarPricingFeedback.textContent = "";
      }
      syncViewerHeader();
      renderAdminMovieList();
      renderAdminArchiveMovieList();
      renderAdminUserList();
      renderSuperAdminPanel();
      renderAccountView();
      setView("auth");
      setStatus("Your sign-in session ended when the server restarted. Please sign in again to load admin data.", true);
      return;
    }

    setStatus(`Backend sync failed, using local demo data. ${message}`, true);
    syncViewerHeader();
    refreshMetrics();
    renderMovieGrid();
    syncDetailPanel();
    renderPublishQueue();
    adminMovies = movies.map((movie) => ({
      ...movie,
      archived: false,
      approvalStatus: movie.approvalStatus || "published",
      approvalStatusLabel: movie.approvalStatusLabel || "Published",
      requiresSuperAdminApproval: false,
    }));
    renderAdminMovieList();
    renderAdminArchiveMovieList();
    adminUsers = [];
    renderAdminUserList();
    renderSuperAdminPanel();
    setStage(activeStage);
    showViewerCatalogPage();
    renderAccountView();
  }
}

function applyAdminSummary(summary) {
  if (!summary) {
    return;
  }

  adminSummaryState = summary;
  setText(adminFeaturedStage, buildStageName(summary.featured_stage));
  setText(adminQueueReady, String(summary.queue_ready));
  setText(adminRewardBoosts, String(summary.reward_campaign_boosts));
  setText(adminQueueTotal, String(summary.queue_total));
  setText(adminStarPriceSummary, `Rs ${formatNumber(summary.star_price_inr || 0)}`);
  setText(adminStarPricingNavValue, `Rs ${formatNumber(summary.star_price_inr || 0)}`);
}

function applyAdminStarPricing(settings) {
  if (!settings) {
    return;
  }

  adminStarPricingState = settings;
  if (adminStarPriceInr) {
    adminStarPriceInr.value = String(settings.price_inr ?? 50);
  }
  if (adminStarPriceUsd) {
    adminStarPriceUsd.value = String(settings.price_usd ?? 0);
  }
  if (adminStarPriceEur) {
    adminStarPriceEur.value = String(settings.price_eur ?? 0);
  }
  if (adminStarPriceEffectiveFrom) {
    adminStarPriceEffectiveFrom.value = toDateTimeLocalValue(settings.effective_from);
  }
}

function getSelectedMovie() {
  return movies.find((movie) => movie.id === selectedMovieId) || movies[0] || null;
}

function getStageMovies(stage) {
  if (stage === "wishlist") {
    return movies.filter((movie) => Boolean(movie.viewerWishKind) && isViewerVisibleStatus(movie.approvalStatus) && getViewerEffectiveStage(movie) === "upcoming");
  }
  if (stage === "reserved") {
    return movies.filter((movie) => (movie.viewerReservationStatus === "blocked" || movie.viewerReservationStatus === "fulfilled") && isViewerVisibleStatus(movie.approvalStatus) && getViewerEffectiveStage(movie) === "upcoming");
  }
  if (stage === "collection") {
    return movies.filter((movie) => isViewerCollectionMovie(movie) && isViewerVisibleStatus(movie.approvalStatus));
  }
  return movies.filter((movie) => getViewerEffectiveStage(movie) === stage && isViewerVisibleStatus(movie.approvalStatus));
}

function setText(node, value) {
  if (node) {
    node.textContent = value;
  }
}

function setAdminUserModalMessage(message, isError = false) {
  if (!adminUserModalCopy) {
    return;
  }
  adminUserModalCopy.textContent = message;
  adminUserModalCopy.classList.toggle("is-error", isError);
}

function clearAdminUserEmailError() {
  adminUserEmail?.classList.remove("input-error");
}

function isDuplicateAdminUserEmail(email, editId = "") {
  const normalizedEmail = String(email || "").trim().toLowerCase();
  if (!normalizedEmail) {
    return false;
  }
  return adminUsers.some((user) => String(user.email || "").trim().toLowerCase() === normalizedEmail && user.id !== editId);
}

function flagDuplicateAdminUserEmail() {
  adminUserEmail?.classList.add("input-error");
  setAdminUserModalMessage("This email address already exists. Please use a different email.", true);
}

function formatCompactCount(value) {
  return `${value} ${value === 1 ? "Movie" : "Movies"}`;
}

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size >= 10 || unitIndex === 0 ? Math.round(size) : size.toFixed(1)} ${units[unitIndex]}`;
}

function buildStageHeading(stage) {
  if (stage === "wishlist") {
    return {
      title: "Wish To Watch",
      subhead: "Titles already saved in your watchlist",
    };
  }

  if (stage === "reserved") {
    return {
      title: "Reserved",
      subhead: "Titles you have already reserved",
    };
  }

  if (stage === "collection") {
    return {
      title: "My Collection",
      subhead: "Released titles you already reserved and now own",
    };
  }

  if (stage === "released") {
    return {
      title: "New Released",
      subhead: "Fresh premieres now open for viewers",
    };
  }

  if (stage === "library") {
    return {
      title: "Library",
      subhead: "Rediscover vault favorites and long-run hits",
    };
  }

  return {
    title: "Up Coming",
    subhead: "Get ready for the biggest blockbusters",
  };
}

function refreshViewerStageHeader() {
  const heading = buildStageHeading(activeStage);
  const count = getStageMovies(activeStage).length;
  setText(viewerHeadline, heading.title);
  setText(viewerSubhead, heading.subhead);
  setText(viewerCount, formatCompactCount(count));
}

function buildPosterStyle(movie) {
  const styles = {
    "solar-dominion": "linear-gradient(180deg, rgba(255,158,74,0.12) 0%, rgba(8,11,18,0.18) 100%), radial-gradient(circle at 20% 20%, #ff934f 0%, #b43f3f 35%, #161a28 72%)",
    "monsoon-crown": "linear-gradient(180deg, rgba(118,230,223,0.12) 0%, rgba(10,14,22,0.22) 100%), radial-gradient(circle at 30% 18%, #84d6c5 0%, #2e6f72 40%, #141925 76%)",
    "night-circuit": "linear-gradient(180deg, rgba(255,92,92,0.12) 0%, rgba(8,11,18,0.2) 100%), radial-gradient(circle at 50% 12%, #d84f36 0%, #6a171d 42%, #10131e 78%)",
    "harbor-flame": "linear-gradient(180deg, rgba(255,143,92,0.16) 0%, rgba(8,11,18,0.22) 100%), radial-gradient(circle at 44% 18%, #ff855d 0%, #8f2a27 40%, #121620 77%)",
    "atlas-run": "linear-gradient(180deg, rgba(241,203,102,0.14) 0%, rgba(8,11,18,0.2) 100%), radial-gradient(circle at 50% 16%, #f1b95d 0%, #916031 38%, #151923 75%)",
    "golden-memoir": "linear-gradient(180deg, rgba(230,188,108,0.16) 0%, rgba(8,11,18,0.18) 100%), radial-gradient(circle at 35% 18%, #dcb46d 0%, #7e5230 42%, #151924 76%)",
  };

  return styles[movie.id] || "linear-gradient(180deg, rgba(255,141,77,0.14) 0%, rgba(8,11,18,0.22) 100%), radial-gradient(circle at 50% 16%, #f17b4c 0%, #7d2f30 42%, #121620 78%)";
}

function buildPosterAccent(movie) {
  const accents = {
    "solar-dominion": "#ffb14a",
    "monsoon-crown": "#7fe1d8",
    "night-circuit": "#ff6c5f",
    "harbor-flame": "#ff9f68",
    "atlas-run": "#f1c56c",
    "golden-memoir": "#dfb877",
  };

  return accents[movie.id] || "#ff9f68";
}

function setView(view) {
  activeView = view;
  document.body.classList.toggle("admin-mode", view === "admin");
  document.body.classList.toggle("account-mode", view === "account");
  viewSections.forEach((section) => {
    section.classList.toggle("is-active", section.dataset.view === view);
  });
  if (view === "viewer") {
    renderMovieGrid();
    syncDetailPanel();
  }
}

function setAdminPanel(panel) {
  activeAdminPanel = panel;
  adminPanelTriggers.forEach((trigger) => {
    trigger.classList.toggle("is-active", trigger.dataset.adminPanelTarget === panel);
  });
  adminPanelViews.forEach((section) => {
    section.classList.toggle("is-active", section.dataset.adminPanelView === panel);
  });
}

function renderAdminTaxonomyList() {
  if (!adminTaxonomyList) {
    return;
  }

  const { filteredItems, pagedItems, totalPages, startIndex } = getProcessedAdminTaxonomies();
  if (!filteredItems.length) {
    adminTaxonomyList.innerHTML = `<div class="admin-user-empty">No classification items matched your filters.</div>`;
    return;
  }

  adminTaxonomyList.innerHTML = `
    <div class="admin-taxonomy-table-head">
      <span>Type</span>
      <span>Name</span>
      <span>Slug</span>
      <span>Status</span>
      <span>Order</span>
      <span>Action</span>
    </div>
    ${pagedItems
      .map(
        (item) => `
          <article class="admin-taxonomy-row" data-admin-taxonomy-kind="${item.kind}" data-admin-taxonomy-id="${item.id}">
            <div>
              <span class="admin-taxonomy-kind">${escapeHtml(formatClassificationKindLabel(item.kind))}</span>
            </div>
            <div class="admin-taxonomy-main">
              <strong>${escapeHtml(item.name)}</strong>
              <p>${escapeHtml(item.description || "No description yet.")}</p>
            </div>
            <div>${escapeHtml(item.slug)}</div>
            <div>
              <span class="admin-user-badge status-${item.is_active ? "active" : "disabled"}">${item.is_active ? "active" : "inactive"}</span>
            </div>
            <div class="admin-taxonomy-order">
              <button type="button" class="icon-btn taxonomy-move-up" data-admin-taxonomy-action="move-up" title="Move up" aria-label="Move up">&#8593;</button>
              <span class="admin-taxonomy-order-value">${escapeHtml(item.sort_order ?? 0)}</span>
              <button type="button" class="icon-btn taxonomy-move-down" data-admin-taxonomy-action="move-down" title="Move down" aria-label="Move down">&#8595;</button>
            </div>
            <div class="admin-user-row-actions">
              <button type="button" class="icon-btn taxonomy-edit-btn" data-admin-taxonomy-action="edit" title="Edit item" aria-label="Edit item">&#9998;</button>
              <button type="button" class="icon-btn danger" data-admin-taxonomy-action="delete" title="Delete item" aria-label="Delete item">&#128465;</button>
            </div>
          </article>
        `
      )
      .join("")}
    <div class="admin-table-footer">
      <p class="admin-table-footnote">Showing ${startIndex + 1}-${startIndex + pagedItems.length} of ${filteredItems.length} items</p>
      <div class="admin-pagination">
        <button type="button" class="ghost-btn" data-admin-taxonomy-page="prev" ${adminTaxonomyPage <= 1 ? "disabled" : ""}>Previous</button>
        <span class="admin-page-indicator">Page ${adminTaxonomyPage} of ${totalPages}</span>
        <button type="button" class="ghost-btn" data-admin-taxonomy-page="next" ${adminTaxonomyPage >= totalPages ? "disabled" : ""}>Next</button>
      </div>
    </div>
  `;
}

function renderAdminSummaryMetrics() {
  const totalUsers = adminUsers.length;
  const activeUsers = adminUsers.filter((user) => user.status === "active").length;
  const pendingUsers = adminUsers.filter((user) => user.status === "pending").length;
  const archivedTitles = adminMovies.filter((movie) => movie.archived).length;
  const superUsers = adminUsers.filter((user) => user.role === "super_admin").length;
  const taxonomyTotal = Object.values(adminTaxonomies).reduce((sum, items) => sum + items.length, 0);
  const categoryCount = (adminTaxonomies.categories || []).length;
  const taxonomyActiveCount = getFlattenedTaxonomies().filter((item) => item.is_active).length;
  const taxonomyGroupCount = Object.keys(adminTaxonomies).length;

  setText(adminUsersCount, String(totalUsers));
  setText(adminCategoriesCount, String(categoryCount));
  setText(adminLibraryCount, String(adminMovies.length));
  setText(adminArchiveNavCount, String(archivedTitles));
  setText(adminTotalUsers, String(totalUsers));
  setText(adminActiveUsers, String(activeUsers));
  setText(adminPendingUsers, String(pendingUsers));
  setText(adminTrackedTitles, String(adminMovies.length));
  setText(adminArchiveCount, String(archivedTitles));
  setText(adminQueueTotal, adminSummaryState ? String(adminSummaryState.queue_total) : String(publishQueue.length));
  setText(adminSuperCount, String(superUsers));
  setText(adminSuperUsers, String(superUsers));
  setText(adminTaxonomyTotal, String(taxonomyTotal));
  setText(adminTaxonomyItemsCount, String(taxonomyTotal));
  setText(adminTaxonomyActiveCount, String(taxonomyActiveCount));
  setText(adminTaxonomyGroupCount, String(taxonomyGroupCount));
  setText(adminRoleCount, "5");

  const libraryMovieWithStart = adminMovies.find((movie) => !movie.archived && movie.deliveryStartAt)
    || adminMovies.find((movie) => movie.deliveryStartAt)
    || adminMovies[0]
    || null;
  if (libraryMovieWithStart) {
    setAdminLibraryUploadStartAtDisplay(libraryMovieWithStart.title, libraryMovieWithStart.deliveryStartAt);
  } else {
    setAdminLibraryUploadStartAtDisplay("", "");
  }

  renderAdminTaxonomyList();
  renderSuperAdminPanel();
}

function setAdminSession(role, email) {
  adminSessionProfile = {
    role: role || "",
    email: email || "",
  };

  if (role) {
    window.localStorage.setItem("cineproxima_session_role", role);
  } else {
    window.localStorage.removeItem("cineproxima_session_role");
  }

  if (email) {
    window.localStorage.setItem("cineproxima_session_email", email);
  } else {
    window.localStorage.removeItem("cineproxima_session_email");
  }

  const roleLabel = role ? role.replace(/_/g, " ") : "Admin Session";
  setText(adminSessionRole, roleLabel.replace(/\b\w/g, (value) => value.toUpperCase()));
  setText(adminSessionEmail, email || "Control panel access is active for this session.");
  if (superAdminNavLink) {
    superAdminNavLink.classList.toggle("hidden", role !== "super_admin");
  }
  if (adminStarPricingNavLink) {
    adminStarPricingNavLink.classList.toggle("hidden", role !== "super_admin");
  }
  if (role !== "super_admin" && ["super-admin", "star-pricing"].includes(activeAdminPanel)) {
    setAdminPanel("users");
  }
}

function applyStoredAdminSession() {
  if (!entryMode || entryMode !== "admin") {
    return;
  }

  if (sessionToken && (adminSessionProfile.role || adminSessionProfile.email)) {
    setAdminSession(adminSessionProfile.role, adminSessionProfile.email);
  }
}

function renderSuperAdminPanel() {
  if (!superAdminTaxonomyGrid) {
    return;
  }

  const taxonomyMeta = [
    {
      key: "categories",
      title: "Categories",
      copy: "Top-level catalog sections such as Movies, Web Series, and TV Shows.",
    },
    {
      key: "genres",
      title: "Genres",
      copy: "Searchable creative tags used across detail pages, cards, and filters.",
    },
    {
      key: "grades",
      title: "Grades",
      copy: "Viewer guidance and parental-control grades available per title.",
    },
  ];

  superAdminTaxonomyGrid.innerHTML = taxonomyMeta
    .map(({ key, title, copy }) => {
      const items = adminTaxonomies[key] || [];
      const rows = items
        .map(
          (item) => `
            <article class="taxonomy-item">
              <div>
                <strong>${item.name}</strong>
                <small>${item.description || `${title} item with slug "${item.slug}".`}</small>
                <div class="taxonomy-meta">
                  <span>Slug: ${item.slug}</span>
                  <span class="taxonomy-status">${item.is_active ? "Active" : "Inactive"}</span>
                </div>
              </div>
              <div class="taxonomy-actions">
                <button type="button" class="ghost-btn" data-taxonomy-edit-kind="${key}" data-taxonomy-edit-id="${item.id}">Edit</button>
              </div>
            </article>
          `
        )
        .join("");

      return `
        <article class="taxonomy-card" data-taxonomy-card="${key}">
          <h3>${title}</h3>
          <p>${copy}</p>
          <div class="taxonomy-list">${rows || '<p class="helper-text">No items yet.</p>'}</div>
          <form class="taxonomy-form" data-taxonomy-form="${key}">
            <input type="hidden" data-taxonomy-id value="">
            <label class="field">
              <span>Name</span>
              <input type="text" data-taxonomy-name placeholder="Enter ${title.toLowerCase()} name">
            </label>
            <div class="taxonomy-form-row">
              <label class="field">
                <span>Slug</span>
                <input type="text" data-taxonomy-slug placeholder="auto-generated-slug">
              </label>
              <label class="field">
                <span>Sort Order</span>
                <input type="number" data-taxonomy-sort value="${items.length + 1}" min="0" step="1">
              </label>
              <label class="field">
                <span>Status</span>
                <select class="select-input" data-taxonomy-active>
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>
            <label class="field">
              <span>Description</span>
              <textarea data-taxonomy-description placeholder="Optional description"></textarea>
            </label>
            <div class="taxonomy-form-actions">
              <button type="submit" class="primary-btn">Save ${title.slice(0, -1) || title}</button>
              <button type="button" class="ghost-btn" data-taxonomy-clear="${key}">Clear</button>
            </div>
          </form>
        </article>
      `;
    })
    .join("");
}

function slugifyValue(value) {
  return value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

function fillTaxonomyForm(kind, itemId) {
  const form = document.querySelector(`[data-taxonomy-form="${kind}"]`);
  const item = (adminTaxonomies[kind] || []).find((entry) => String(entry.id) === String(itemId));
  if (!form || !item) {
    return;
  }

  form.querySelector("[data-taxonomy-id]").value = String(item.id);
  form.querySelector("[data-taxonomy-name]").value = item.name;
  form.querySelector("[data-taxonomy-slug]").value = item.slug;
  form.querySelector("[data-taxonomy-sort]").value = String(item.sort_order ?? 0);
  form.querySelector("[data-taxonomy-active]").value = item.is_active ? "true" : "false";
  form.querySelector("[data-taxonomy-description]").value = item.description || "";
}

function clearTaxonomyForm(kind) {
  const form = document.querySelector(`[data-taxonomy-form="${kind}"]`);
  if (!form) {
    return;
  }
  const itemCount = (adminTaxonomies[kind] || []).length;
  form.querySelector("[data-taxonomy-id]").value = "";
  form.querySelector("[data-taxonomy-name]").value = "";
  form.querySelector("[data-taxonomy-slug]").value = "";
  form.querySelector("[data-taxonomy-sort]").value = String(itemCount + 1);
  form.querySelector("[data-taxonomy-active]").value = "true";
  form.querySelector("[data-taxonomy-description]").value = "";
}

async function saveTaxonomyRemote(kind, form) {
  const itemId = form.querySelector("[data-taxonomy-id]").value;
  const name = form.querySelector("[data-taxonomy-name]").value.trim();
  const slugInput = form.querySelector("[data-taxonomy-slug]").value.trim();
  const payload = {
    name,
    slug: slugInput || slugifyValue(name),
    description: form.querySelector("[data-taxonomy-description]").value.trim() || null,
    sort_order: Number(form.querySelector("[data-taxonomy-sort]").value || 0),
    is_active: form.querySelector("[data-taxonomy-active]").value === "true",
  };

  const path = itemId ? `/admin/taxonomies/${kind}/${itemId}` : `/admin/taxonomies/${kind}`;
  const response = await apiRequest(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  await loadAdminTaxonomiesFromApi();
  renderSuperAdminPanel();
  renderAdminSummaryMetrics();
  clearTaxonomyForm(kind);
  adminHelper.textContent = response.message;
}

function openAdminTaxonomyEditor(item = null, forcedKind = "categories") {
  if (!adminTaxonomyModal || !adminTaxonomyEditor) {
    return;
  }

  const kind = item?.kind || forcedKind;
  const itemCount = (adminTaxonomies[kind] || []).length;
  adminTaxonomyModal.classList.remove("hidden");
  adminTaxonomyModal.setAttribute("aria-hidden", "false");
  adminTaxonomyEditId.value = item ? String(item.id) : "";
  adminTaxonomyEditorKind.value = kind;
  adminTaxonomyName.value = item?.name || "";
  adminTaxonomySlug.value = item?.slug || "";
  adminTaxonomySortOrder.value = String(item?.sort_order ?? (itemCount + 1));
  adminTaxonomyStatus.value = item?.is_active === false ? "false" : "true";
  adminTaxonomyDescription.value = item?.description || "";
  adminTaxonomyModalTitle.textContent = item ? `Edit ${formatClassificationKindLabel(kind)}` : "Add Classification Item";
  adminTaxonomyModalCopy.textContent = item
    ? `Update this ${formatClassificationKindLabel(kind).toLowerCase()} for the platform classification setup.`
    : "Create a new category, genre, grade, or language for the platform.";
  adminTaxonomyEditorKind.focus();
}

function closeAdminTaxonomyEditor() {
  if (!adminTaxonomyModal || !adminTaxonomyEditor) {
    return;
  }

  adminTaxonomyModal.classList.add("hidden");
  adminTaxonomyModal.setAttribute("aria-hidden", "true");
  adminTaxonomyEditId.value = "";
  adminTaxonomyEditorKind.value = adminTaxonomyKindFilter === "all" ? "categories" : adminTaxonomyKindFilter;
  adminTaxonomyName.value = "";
  adminTaxonomySlug.value = "";
  adminTaxonomySortOrder.value = "1";
  adminTaxonomyStatus.value = "true";
  adminTaxonomyDescription.value = "";
}

async function deleteAdminTaxonomyRemote(kind, itemId) {
  const response = await apiRequest(`/admin/taxonomies/${kind}/${itemId}`, {
    method: "DELETE",
  });

  adminTaxonomies[kind] = (adminTaxonomies[kind] || []).filter((entry) => String(entry.id) !== String(itemId));
  renderAdminSummaryMetrics();
  adminHelper.textContent = response.message;
}

async function moveAdminTaxonomyRemote(kind, itemId, direction) {
  const items = [...(adminTaxonomies[kind] || [])].sort((first, second) => {
    const orderCompare = Number(first.sort_order || 0) - Number(second.sort_order || 0);
    if (orderCompare !== 0) {
      return orderCompare;
    }
    return String(first.name || "").localeCompare(String(second.name || ""));
  });

  const currentIndex = items.findIndex((entry) => String(entry.id) === String(itemId));
  if (currentIndex === -1) {
    return;
  }

  const swapIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
  if (swapIndex < 0 || swapIndex >= items.length) {
    return;
  }

  const currentItem = items[currentIndex];
  const swapItem = items[swapIndex];

  await Promise.all([
    apiRequest(`/admin/taxonomies/${kind}/${currentItem.id}`, {
      method: "POST",
      body: JSON.stringify({
        slug: currentItem.slug,
        name: currentItem.name,
        description: currentItem.description || null,
        sort_order: Number(swapItem.sort_order ?? 0),
        is_active: currentItem.is_active,
      }),
    }),
    apiRequest(`/admin/taxonomies/${kind}/${swapItem.id}`, {
      method: "POST",
      body: JSON.stringify({
        slug: swapItem.slug,
        name: swapItem.name,
        description: swapItem.description || null,
        sort_order: Number(currentItem.sort_order ?? 0),
        is_active: swapItem.is_active,
      }),
    }),
  ]);

  await loadAdminTaxonomiesFromApi();
  renderAdminSummaryMetrics();
  adminHelper.textContent = `${formatClassificationKindLabel(kind)} order updated.`;
}

function setAuthMessage(message, isError = false) {
  if (!authHelper) {
    return;
  }
  authHelper.textContent = message;
  authHelper.classList.toggle("is-error", Boolean(isError));
}

function setSignupMessage(message, isError = false) {
  if (!signupHelper) {
    return;
  }
  signupHelper.textContent = message;
  signupHelper.classList.toggle("is-error", Boolean(isError));
}

function syncAuthEntryCopy() {
  if (entryMode === "admin") {
    setAuthMessage("Sign in here with an Admin or Super Admin account to open the admin console.");
    return;
  }
  if (entryMode === "creator") {
    setAuthMessage("Sign in here with a Creator account to open the creator workspace.");
    return;
  }
  setAuthMessage("Sign in once here. Viewer, creator, advertiser, admin, and super admin accounts will automatically open the correct workspace.");
}

function openSignupFlow() {
  authForm?.classList.add("hidden");
  signupForm?.classList.remove("hidden");
  setSignupMessage("This sign-up flow is only for normal viewer accounts. Your email is validated and the account is activated immediately for now.");
}

function closeSignupFlow() {
  signupForm?.classList.add("hidden");
  authForm?.classList.remove("hidden");
  setSignupMessage("This sign-up flow is only for normal viewer accounts. Your email is validated and the account is activated immediately for now.");
  syncAuthEntryCopy();
}

function refreshMetrics() {
  const totalWish = movies.reduce((sum, movie) => sum + movie.wishCount, 0);
  const totalReserve = movies.reduce((sum, movie) => sum + movie.reserveCount, 0);

  metricTitles.textContent = String(movies.length);
  metricWish.textContent = formatNumber(totalWish);
  metricRevenue.textContent = formatRevenueFromCounts(totalReserve);
}

function syncSpotlight(movie) {
  setText(spotlightTitle, movie.title);
  setText(spotlightMeta, `${movie.genre} - Releases ${movie.releaseDate}`);
  setText(spotlightCopy, movie.description);
  setText(spotlightWish, formatNumber(movie.wishCount));
  setText(spotlightReserve, formatNumber(movie.reserveCount));
  setText(spotlightRevenue, movie.revenue);
}

function renderMovieGrid() {
  const stageMovies = getStageMovies(activeStage);

  if (!movies.length) {
    selectedMovieId = "";
    movieGrid.innerHTML = `<div class="admin-movie-empty">No titles available yet. New titles added from Admin will appear here once they are approved.</div>`;
    return;
  }

  if (!stageMovies.some((movie) => movie.id === selectedMovieId)) {
    selectedMovieId = stageMovies[0]?.id || movies[0]?.id || "";
  }

  if (!stageMovies.length) {
    movieGrid.innerHTML = `<div class="admin-movie-empty">No titles are available in this section yet.</div>`;
    return;
  }

  movieGrid.innerHTML = stageMovies
    .map((movie) => {
      const activeClass = movie.id === selectedMovieId ? " is-active" : "";
      const effectiveStage = getViewerEffectiveStage(movie);
      const statusChip = effectiveStage === "released" ? "NOW OPEN" : effectiveStage === "library" ? "VAULT READY" : "COMING SOON";

      return `
        <article class="movie-card${activeClass}" data-movie-id="${movie.id}">
          <div class="poster-frame">
            ${
              getRandomPosterForMovie(movie, "vertical")
                ? `<img class="poster-art" src="${getRandomPosterForMovie(movie, "vertical")}" alt="${movie.title} poster" loading="lazy" onerror="this.onerror=null;this.src='/media/posters/no-poster.svg';">`
                : `<div class="poster-art poster-art-fallback" style="background:${buildPosterStyle(movie)}"></div>`
            }
            <div class="poster-noise"></div>
            <div class="poster-overlay"></div>
            <div class="poster-hover-glow" aria-hidden="true"></div>
            <div class="poster-top">
              <span class="coming-chip">${statusChip}</span>
            </div>
            <div class="poster-play-cue" aria-hidden="true">
              <span class="poster-play-ring">
                <span class="poster-play-triangle"></span>
              </span>
            </div>
          </div>
          <div class="movie-info">
            <h3 class="movie-title">${movie.title}</h3>
            <div class="movie-meta">
              <span class="genre">${movie.genre}</span>
            </div>
            <div class="movie-actions-row">
              ${getMovieCardActionMarkup(movie)}
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function syncDetailPanel() {
  const movie = getSelectedMovie();
  if (!movie) {
    setText(spotlightTitle, "Cine Vault");
    setText(spotlightMeta, "No featured title yet");
    setText(spotlightCopy, "Your approved titles will appear here once you start adding them from the admin panel.");
    setText(spotlightWish, "0");
    setText(spotlightReserve, "0");
    setText(spotlightRevenue, "$0K");
    return;
  }

  syncSpotlight(movie);
}

function getRandomItem(items) {
  if (!Array.isArray(items) || !items.length) {
    return null;
  }
  return items[Math.floor(Math.random() * items.length)] || items[0] || null;
}

function getRandomPosterForMovie(movie, orientation = "vertical") {
  const detail = viewerMovieDetails.get(movie?.id || "");
  const posters = detail?.posters || [];
  const orientedPosters = posters.filter((item) => item.orientation === orientation);
  const fallbackPosters = posters.filter((item) => item.orientation !== orientation);
  const selectedPoster = getRandomItem(orientedPosters) || getRandomItem(fallbackPosters);

  if (selectedPoster?.url) {
    return toAssetUrl(selectedPoster.url);
  }

  return movie?.poster ? toAssetUrl(movie.poster) : "";
}

async function prefetchStageMovieDetails(stage = activeStage) {
  const stageMovies = getStageMovies(stage).filter((movie) => movie?.id && !viewerMovieDetails.has(movie.id));
  if (!stageMovies.length) {
    return;
  }

  await Promise.all(
    stageMovies.map((movie) =>
      loadMovieDetailsFromApi(movie.id).catch(() => null)
    )
  );
}

function renderViewerDetailPage(detail) {
  const movie = detail?.item || getSelectedMovie();
  const posters = detail?.posters || [];
  const horizontalPosters = posters.filter((item) => item.orientation === "horizontal");
  const heroPoster = getRandomItem(horizontalPosters) || getRandomItem(posters);
  const effectiveStage = getViewerEffectiveStage(movie);
  const effectiveStageLabel = buildStageName(effectiveStage);

  viewerDetailState = {
    movieId: movie?.id || "",
    item: movie || null,
    posters,
    trailers: detail?.trailers || [],
    gallery: detail?.gallery || [],
    music: detail?.music || [],
    content: detail?.content || [],
  };

  if (!movie) {
    if (viewerTitleDetailPage) {
      viewerTitleDetailPage.classList.add("hidden");
    }
    return;
  }

  if (viewerTitleDetailPage) {
    viewerTitleDetailPage.classList.remove("hidden");
  }
  if (catalogHero) {
    catalogHero.classList.add("hidden");
  }
  if (movieGridSection) {
    movieGridSection.classList.add("hidden");
  }

  if (viewerTitleBackdrop) {
    const backgroundUrl = heroPoster?.url || movie.poster || "/media/posters/no-poster.svg";
    viewerTitleBackdrop.style.backgroundImage = `url("${toAssetUrl(backgroundUrl)}")`;
  }

  if (detailPosterImage) {
    detailPosterImage.src = movie.poster ? toAssetUrl(movie.poster) : "/media/posters/no-poster.svg";
    detailPosterImage.alt = `${movie.title} poster`;
  }

  setText(detailTitle, movie.title);
  setText(detailCaption, movie.titleCaption || "No caption added.");
  setText(detailStagePill, effectiveStageLabel);
  setText(
    detailStage,
    effectiveStage === "released" && movie.passwordPublishAt
      ? `Released from ${formatViewerUploadDateTime(movie.passwordPublishAt)}`
      : `${effectiveStageLabel} - ${movie.countdown}`
  );
  setText(detailDescription, movie.description || "Story details will appear here soon.");
  setText(detailCategory, movie.titleCategory || "Not set");
  setText(detailGenre, movie.genre || "Not set");
  setText(detailReleaseDate, movie.releaseDate && movie.releaseDate !== "TBA" ? movie.releaseDate : "Coming Soon");
  setText(detailUploadDateTime, formatViewerUploadDateTime(movie.deliveryStartAt));
  setText(detailReleaseDateTime, formatViewerUploadDateTime(movie.passwordPublishAt));
  setText(detailStarsRequired, `${movie.starsRequired || 1} Star${Number(movie.starsRequired || 1) === 1 ? "" : "s"}`);
  setText(detailExpected, `${movie.expectedStars || 0} Star${Number(movie.expectedStars || 0) === 1 ? "" : "s"}`);
  const targetProgressPercent = getTargetProgressPercent(movie);
  if (detailTargetProgressFill) {
    detailTargetProgressFill.style.width = `${targetProgressPercent}%`;
  }
  setText(detailTargetProgressLabel, `${targetProgressPercent}%`);
  renderViewerCastCredits(movie);
  renderViewerDownloadLinks(movie);

  if (detailWishButton) {
    const hideWishButton = effectiveStage === "released";
    detailWishButton.classList.toggle("hidden", hideWishButton);
    if (!hideWishButton) {
      detailWishButton.disabled = isMovieWished(movie);
      detailWishButton.classList.toggle("is-active", isMovieWished(movie));
      const icon = detailWishButton.querySelector(".wish-watch-icon");
      const label = detailWishButton.querySelector("span:last-child");
      if (icon) {
        icon.innerHTML = isMovieWished(movie) ? "&#10003;" : "&#9825;";
      }
      if (label) {
        label.textContent = isMovieWished(movie) ? "In Wishlist" : "Wish 2 Watch";
      }
    }
  }
  if (detailReserveButton) {
    const alreadyReserved = movie.viewerReservationStatus === "blocked" || movie.viewerReservationStatus === "fulfilled";
    const reserveEnabled = Boolean(movie.reserveEnabled) && effectiveStage !== "released";
    const buyNowEnabled = isMovieBuyReady(movie);
    const hideReserveButton = movie.viewerReservationStatus === "fulfilled" && (effectiveStage === "released" || effectiveStage === "library");
    detailReserveButton.classList.toggle("hidden", hideReserveButton);
    detailReserveButton.disabled = hideReserveButton || (!reserveEnabled && !buyNowEnabled) || alreadyReserved;
    detailReserveButton.classList.toggle("is-active", alreadyReserved && !hideReserveButton);
    detailReserveButton.classList.toggle("is-blinking", (reserveEnabled || buyNowEnabled) && !alreadyReserved && !hideReserveButton);
    detailReserveButton.textContent = movie.viewerReservationStatus === "fulfilled"
      ? "Watch Now"
      : movie.viewerReservationStatus === "blocked"
        ? "Reserved"
        : buyNowEnabled
          ? "Buy Now"
          : reserveEnabled
            ? "Reserve Now"
            : "Reserve Not Started";
  }
  if (detailPostersButton) {
    detailPostersButton.disabled = posters.length === 0;
  }
  if (detailTrailersButton) {
    detailTrailersButton.disabled = !viewerDetailState.trailers.length;
  }
  if (detailGalleryButton) {
    detailGalleryButton.disabled = !viewerDetailState.gallery.length;
  }
  if (detailMusicButton) {
    detailMusicButton.disabled = !viewerDetailState.music.length;
  }
  const canPlayLocalContent = canViewerPlayLocalContent(movie);
  if (detailContentButton) {
    detailContentButton.disabled = !canPlayLocalContent;
  }
  if (detailWatchNowButton) {
    detailWatchNowButton.classList.toggle("hidden", !canPlayLocalContent);
    detailWatchNowButton.disabled = !canPlayLocalContent;
  }
  if (detailPosterPlayButton) {
    detailPosterPlayButton.classList.toggle("hidden", !canPlayLocalContent);
    detailPosterPlayButton.disabled = !canPlayLocalContent;
  }
}

function showViewerCatalogPage() {
  if (catalogHero) {
    catalogHero.classList.remove("hidden");
  }
  if (movieGridSection) {
    movieGridSection.classList.remove("hidden");
  }
  if (viewerTitleDetailPage) {
    viewerTitleDetailPage.classList.add("hidden");
  }
}

async function openViewerDetailPage(movieId, { syncHash = true, forceReload = false } = {}) {
  if (!movieId) {
    return;
  }

  const movie = movies.find((entry) => entry.id === movieId);
  if (!movie) {
    return;
  }

  selectedMovieId = movieId;
  renderMovieGrid();
  syncDetailPanel();

  const detail = await loadMovieDetailsFromApi(movieId, { force: forceReload });
  renderViewerDetailPage(detail);

  if (syncHash && window.location.hash !== getViewerDetailHash(movieId)) {
    window.location.hash = getViewerDetailHash(movieId);
  }
}

async function openViewerPlayPage(movieId) {
  await openViewerDetailPage(movieId);
  if (viewerTitleDetailPage) {
    viewerTitleDetailPage.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function closeViewerDetailPage({ syncHash = true } = {}) {
  viewerDetailState = {
    movieId: "",
    item: null,
    posters: [],
    trailers: [],
    gallery: [],
    music: [],
    content: [],
  };
  showViewerCatalogPage();
  if (syncHash && window.location.hash) {
    history.pushState("", document.title, `${window.location.pathname}${window.location.search}`);
  }
}

function canViewerPlayLocalContent(movie) {
  return Boolean(movie && isViewerCollectionMovie(movie));
}

function isWebPlayableMainContentExtension(fileNameOrExtension) {
  const lowerValue = String(fileNameOrExtension || "").toLowerCase();
  return lowerValue.endsWith(".mp4") || lowerValue.endsWith(".m4v") || lowerValue.endsWith(".webm");
}

function guessLocalContentMime(manifest) {
  const extension = String(manifest?.files?.[0]?.source_extension || "").toLowerCase();
  if (extension === ".mp4" || extension === ".m4v") {
    return "video/mp4";
  }
  if (extension === ".webm") {
    return "video/webm";
  }
  return "";
}

function formatLocalContentStatus(movie) {
  if (!movie) {
    return "No title selected.";
  }
  if (!viewerDetailState.content.length) {
    return "No content package is linked to this title yet.";
  }
  if (!movie.releasePasscode) {
    return "Release passcode is not published yet.";
  }
  return "Your downloaded content can be linked once and then played from this browser.";
}

async function verifyDirectoryPermission(handle) {
  if (!handle || typeof handle.queryPermission !== "function") {
    return false;
  }
  const readState = await handle.queryPermission({ mode: "read" });
  if (readState === "granted") {
    return true;
  }
  const requestedState = await handle.requestPermission({ mode: "read" });
  return requestedState === "granted";
}

function promptLocalContentFiles() {
  return new Promise((resolve, reject) => {
    if (!viewerLocalContentInput) {
      reject(new Error("This browser does not support local content linking here."));
      return;
    }

    const onChange = () => {
      viewerLocalContentInput.removeEventListener("change", onChange);
      const files = Array.from(viewerLocalContentInput.files || []);
      viewerLocalContentInput.value = "";
      if (!files.length) {
        reject(new Error("No content files were selected."));
        return;
      }
      resolve(files);
    };

    viewerLocalContentInput.addEventListener("change", onChange, { once: true });
    viewerLocalContentInput.click();
  });
}

async function chooseLocalContentSource(movieId) {
  if (window.showDirectoryPicker) {
    const handle = await window.showDirectoryPicker({ mode: "read" });
    try {
      await saveStoredLocalContentHandle(movieId, handle);
    } catch {
      // Browsers may decline persistent handle storage even though the folder can still be read now.
    }
    return { kind: "directory", value: handle, persisted: true };
  }

  const files = await promptLocalContentFiles();
  return { kind: "files", value: files, persisted: false };
}

async function resolveStoredLocalContentSource(movieId) {
  const handle = await getStoredLocalContentHandle(movieId);
  if (!handle) {
    return null;
  }

  try {
    const granted = await verifyDirectoryPermission(handle);
    if (!granted) {
      await deleteStoredLocalContentHandle(movieId);
      return null;
    }
    return { kind: "directory", value: handle, persisted: true };
  } catch {
    await deleteStoredLocalContentHandle(movieId);
    return null;
  }
}

async function findChunkFileInDirectory(directoryHandle, fileName) {
  try {
    return await directoryHandle.getFileHandle(fileName);
  } catch {
    // Fall through to recursive search when the file is inside a nested extracted folder.
  }

  for await (const entry of directoryHandle.values()) {
    if (entry.kind === "file" && entry.name === fileName) {
      return entry;
    }
    if (entry.kind === "directory") {
      const nested = await findChunkFileInDirectory(entry, fileName);
      if (nested) {
        return nested;
      }
    }
  }

  return null;
}

async function readChunkFileFromSource(source, fileName) {
  if (source.kind === "directory") {
    const fileHandle = await findChunkFileInDirectory(source.value, fileName);
    if (!fileHandle) {
      throw new Error(`Missing content chunk "${fileName}" in the selected folder.`);
    }
    return fileHandle.getFile();
  }

  const matched = source.value.find((file) => file.name === fileName || String(file.webkitRelativePath || "").endsWith(`/${fileName}`));
  if (!matched) {
    throw new Error(`Missing content chunk "${fileName}".`);
  }
  return matched;
}

async function decryptLocalContentChunk(chunkFile, fileMeta, manifest, password) {
  const fileBytes = new Uint8Array(await chunkFile.arrayBuffer());
  const salt = Uint8Array.from(atob(fileMeta.salt), (value) => value.charCodeAt(0));
  const nonce = Uint8Array.from(atob(fileMeta.nonce), (value) => value.charCodeAt(0));
  const aad = Uint8Array.from(atob(fileMeta.aad), (value) => value.charCodeAt(0));
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveKey"]
  );
  const key = await crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt,
      iterations: Number(manifest?.encryption?.iterations || 390000),
      hash: "SHA-256",
    },
    keyMaterial,
    {
      name: "AES-GCM",
      length: 256,
    },
    false,
    ["decrypt"]
  );

  const decrypted = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: nonce,
      additionalData: aad,
      tagLength: 128,
    },
    key,
    fileBytes
  );

  return new Uint8Array(decrypted);
}

function clearViewerLocalContentPlayback() {
  if (viewerLocalContentPlaybackUrl) {
    URL.revokeObjectURL(viewerLocalContentPlaybackUrl);
    viewerLocalContentPlaybackUrl = "";
  }
}

async function primeViewerContentVideoPlayback() {
  if (!viewerAssetModalBody) {
    return;
  }

  const contentVideo = viewerAssetModalBody.querySelector(".viewer-content-video");
  if (!contentVideo) {
    return;
  }

  contentVideo.defaultMuted = false;
  contentVideo.muted = false;
  contentVideo.volume = 1;

  try {
    await contentVideo.play();
  } catch {
    // The video is already opened from a user action, so leaving it paused is fine if the browser still blocks autoplay.
  }
}

function renderViewerContentModalBody(movie, statusMarkup, videoMarkup = "") {
  if (!viewerAssetModalBody) {
    return;
  }
  const safeVideoMarkup = videoMarkup || "";
  viewerAssetModalBody.innerHTML = [
    '<div class="viewer-content-modal">',
    '<p class="viewer-content-modal-copy">Link the extracted downloaded chunk folder once, then play this title locally from your browser.</p>',
    '<div class="viewer-content-modal-status">',
    `<strong>${escapeHtml(movie.title)}</strong>`,
    `<span>${escapeHtml(statusMarkup)}</span>`,
    "</div>",
    '<div class="viewer-content-modal-actions">',
    '<button type="button" class="primary-btn" data-viewer-content-action="play">Play Now</button>',
    '<button type="button" class="ghost-btn" data-viewer-content-action="link">Choose Downloaded Folder</button>',
    '<button type="button" class="ghost-btn" data-viewer-content-action="files">Choose Chunk Files</button>',
    "</div>",
    safeVideoMarkup,
    '<p class="viewer-content-help">For this web version, the folder should contain the extracted VCNR content chunk files after download.</p>',
    "</div>",
  ].join("");
}

async function playMovieFromLocalContent(movie, source) {
  const manifest = await loadMovieContentManifest(movie.id);
  if (!manifest?.files?.length) {
    throw new Error("Content manifest is not available for this title yet.");
  }
  const sourceExtension = String(manifest.files?.[0]?.source_extension || "").toLowerCase();
  if (!isWebPlayableMainContentExtension(sourceExtension)) {
    throw new Error(`This website player supports MP4 or WebM main content. The uploaded source is ${sourceExtension || "an unsupported format"}, so please re-upload it in MP4, M4V, or WebM for browser playback.`);
  }
  if (!movie.releasePasscode) {
    throw new Error("Release passcode is not published yet.");
  }

  clearViewerLocalContentPlayback();
  renderViewerContentModalBody(movie, "Opening your local encrypted content package...");

  const orderedFiles = [...manifest.files].sort((left, right) => {
    if (Number(left.source_index || 0) !== Number(right.source_index || 0)) {
      return Number(left.source_index || 0) - Number(right.source_index || 0);
    }
    return Number(left.chunk_index || 0) - Number(right.chunk_index || 0);
  });

  const parts = [];
  for (let index = 0; index < orderedFiles.length; index += 1) {
    const fileMeta = orderedFiles[index];
    renderViewerContentModalBody(movie, `Decrypting local chunk ${index + 1} of ${orderedFiles.length}...`);
    const chunkFile = await readChunkFileFromSource(source, fileMeta.name);
    const decryptedChunk = await decryptLocalContentChunk(chunkFile, fileMeta, manifest, movie.releasePasscode);
    parts.push(decryptedChunk);
  }

  const blob = new Blob(parts, { type: guessLocalContentMime(manifest) });
  viewerLocalContentPlaybackUrl = URL.createObjectURL(blob);
  renderViewerContentModalBody(
    movie,
    "Local content is linked and ready to watch.",
    `<div class="viewer-content-video-shell"><video class="viewer-content-video" controls playsinline preload="metadata" src="${viewerLocalContentPlaybackUrl}"></video></div>`
  );
  await primeViewerContentVideoPlayback();
}

async function openViewerContentPlayback(movie, preferredSource = null) {
  if (!movie) {
    throw new Error("No title is selected.");
  }
  if (!canViewerPlayLocalContent(movie)) {
    throw new Error("This title is not ready for local playback yet.");
  }

  viewerAssetCarouselState = {
    kind: "content",
    title: `${movie.title} Content`,
    items: [],
    index: 0,
  };
  viewerAssetModalTitle.textContent = `${movie.title} Content`;
  viewerAssetModal.classList.remove("hidden");
  viewerAssetModal.setAttribute("aria-hidden", "false");
  renderViewerContentModalBody(movie, formatLocalContentStatus(movie));

  if (!viewerDetailState.content.length || !movie.releasePasscode) {
    return;
  }

  const source = preferredSource || await resolveStoredLocalContentSource(movie.id);
  if (!source) {
    return;
  }

  try {
    await playMovieFromLocalContent(movie, source);
  } catch (error) {
    renderViewerContentModalBody(movie, error.message || "Local playback could not be started.");
  }
}

function renderViewerAssetCarousel() {
  if (!viewerAssetModalBody || !viewerAssetModalTitle) {
    return;
  }

  const { kind, title, items } = viewerAssetCarouselState;
  const total = items.length;

  viewerAssetModalTitle.textContent = title || "Media Viewer";

  if (!total) {
    viewerAssetModalBody.innerHTML = `<div class="viewer-asset-empty">No media available yet.</div>`;
    return;
  }

  if (viewerAssetCarouselState.index < 0) {
    viewerAssetCarouselState.index = total - 1;
  }
  if (viewerAssetCarouselState.index >= total) {
    viewerAssetCarouselState.index = 0;
  }

  const asset = items[viewerAssetCarouselState.index];
  let mediaMarkup = "";

  if (kind === "posters") {
    mediaMarkup = `
      <a class="viewer-carousel-poster-link" href="${toAssetUrl(asset.url)}" target="_blank" rel="noreferrer">
        <img class="viewer-carousel-poster" src="${toAssetUrl(asset.url)}" alt="Poster image" loading="lazy">
      </a>
    `;
  } else if (kind === "trailers" || kind === "gallery") {
    mediaMarkup = `
      <video controls preload="metadata" class="viewer-media-player viewer-carousel-video" src="${toAssetUrl(asset.url)}"></video>
    `;
  } else if (kind === "music") {
    mediaMarkup = `
      <div class="viewer-carousel-audio-shell">
        <div class="viewer-audio-icon viewer-carousel-audio-icon">&#9835;</div>
        <audio controls preload="metadata" class="viewer-audio-player viewer-carousel-audio-player" src="${toAssetUrl(asset.url)}"></audio>
      </div>
    `;
  }

  viewerAssetModalBody.innerHTML = `
    <div class="viewer-carousel-shell">
      <button type="button" class="viewer-carousel-nav viewer-carousel-nav-prev" data-viewer-carousel-nav="prev" aria-label="Previous media">&#8249;</button>
      <div class="viewer-carousel-stage">
        ${mediaMarkup}
      </div>
      <button type="button" class="viewer-carousel-nav viewer-carousel-nav-next" data-viewer-carousel-nav="next" aria-label="Next media">&#8250;</button>
    </div>
    <div class="viewer-carousel-footer">
      <span class="viewer-carousel-counter">${viewerAssetCarouselState.index + 1} / ${total}</span>
      <div class="viewer-carousel-dots">
        ${items.map((_, index) => `
          <button
            type="button"
            class="viewer-carousel-dot${index === viewerAssetCarouselState.index ? " is-active" : ""}"
            data-viewer-carousel-index="${index}"
            aria-label="Show media ${index + 1}"
          ></button>
        `).join("")}
      </div>
    </div>
  `;
}

function openViewerAssetModal(kind) {
  if (!viewerAssetModal || !viewerAssetModalBody || !viewerAssetModalTitle) {
    return;
  }

  const movieTitle = viewerDetailState.item?.title || "Title";
  const items = kind === "posters"
    ? (viewerDetailState.posters || [])
    : kind === "trailers"
      ? (viewerDetailState.trailers || [])
      : kind === "gallery"
        ? (viewerDetailState.gallery || [])
      : (viewerDetailState.music || []);

  viewerAssetCarouselState = {
    kind,
    title: kind === "posters" ? `${movieTitle} Posters` : kind === "trailers" ? `${movieTitle} Trailer` : kind === "gallery" ? `${movieTitle} Gallery` : `${movieTitle} Music`,
    items,
    index: 0,
  };

  renderViewerAssetCarousel();
  viewerAssetModal.classList.remove("hidden");
  viewerAssetModal.setAttribute("aria-hidden", "false");
}

function closeViewerAssetModal() {
  if (!viewerAssetModal || !viewerAssetModalBody) {
    return;
  }
  clearViewerLocalContentPlayback();
  viewerAssetCarouselState = {
    kind: "",
    title: "",
    items: [],
    index: 0,
  };
  viewerAssetModal.classList.add("hidden");
  viewerAssetModal.setAttribute("aria-hidden", "true");
  viewerAssetModalBody.innerHTML = "";
}

function selectMovie(movieId) {
  selectedMovieId = movieId;
  renderMovieGrid();
  syncDetailPanel();
}

function setStage(stage) {
  activeStage = stage;
  closeViewerDetailPage({ syncHash: false });
  stageTabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.stage === stage);
  });
  stripStageLinks.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.stage === stage);
  });
  refreshViewerStageHeader();
  renderMovieGrid();
  syncDetailPanel();
  prefetchStageMovieDetails(stage)
    .then(() => {
      if (activeStage === stage) {
        renderMovieGrid();
      }
    })
    .catch(() => {});
}

function applyUpdatedMovie(updatedMovie) {
  movies = movies.map((entry) => (entry.id === updatedMovie.id ? updatedMovie : entry));
  if (viewerMovieDetails.has(updatedMovie.id)) {
    const cached = viewerMovieDetails.get(updatedMovie.id);
    if (cached) {
      cached.item = { ...cached.item, ...updatedMovie };
      viewerMovieDetails.set(updatedMovie.id, cached);
      if (viewerDetailState.movieId === updatedMovie.id) {
        renderViewerDetailPage(cached);
      }
    }
  }
  refreshMetrics();
  refreshViewerStageHeader();
  renderMovieGrid();
  syncDetailPanel();
}

function openViewerWishModal(movieId) {
  const movie = movies.find((entry) => entry.id === movieId);
  if (!movie || !viewerWishModal) {
    return;
  }
  activeWishMovieId = movieId;
  if (viewerWishModalMovie) {
    viewerWishModalMovie.textContent = movie.title;
  }
  viewerWishModal.classList.remove("hidden");
  viewerWishModal.setAttribute("aria-hidden", "false");
}

function closeViewerWishModal() {
  activeWishMovieId = "";
  if (!viewerWishModal) {
    return;
  }
  viewerWishModal.classList.add("hidden");
  viewerWishModal.setAttribute("aria-hidden", "true");
}

function openViewerReserveModal(movieId) {
  const movie = movies.find((entry) => entry.id === movieId);
  if (!movie || !viewerReserveModal) {
    return;
  }
  activeReserveMovieId = movieId;
  activeReserveAction = isMovieBuyReady(movie) ? "buy" : "reserve";
  if (viewerReserveModalMovie) {
    viewerReserveModalMovie.textContent = movie.title;
  }
  const reserveStars = Number(movie.reserveStarPrice || movie.starsRequired || 0);
  const reserveTitle = document.getElementById("viewerReserveModalTitle");
  if (viewerReserveModalCopy) {
    viewerReserveModalCopy.textContent = activeReserveAction === "buy"
      ? `${reserveStars} star${reserveStars === 1 ? "" : "s"} will be deducted now and this title will be added to your owned list for this device. Please confirm.`
      : `${reserveStars} star${reserveStars === 1 ? "" : "s"} will be blocked until the movie release date. It will be refunded if the movie is not released or fails to achieve the target stars. Please confirm.`;
  }
  if (reserveTitle) {
    reserveTitle.textContent = activeReserveAction === "buy" ? "Confirm your purchase" : "Confirm your reservation";
  }
  if (viewerReserveConfirmButton) {
    viewerReserveConfirmButton.textContent = activeReserveAction === "buy" ? "Confirm Buy Now" : "Confirm Reserve Now";
  }
  viewerReserveModal.classList.remove("hidden");
  viewerReserveModal.setAttribute("aria-hidden", "false");
}

function closeViewerReserveModal() {
  activeReserveMovieId = "";
  activeReserveAction = "reserve";
  if (!viewerReserveModal) {
    return;
  }
  viewerReserveModal.classList.add("hidden");
  viewerReserveModal.setAttribute("aria-hidden", "true");
}

async function submitMovieInterest(movieId, kind, wishMode = "") {
  const movie = movies.find((entry) => entry.id === movieId);
  if (!movie) {
    setStatus("No title is available yet.");
    return;
  }
  const payload = kind === "wish" ? { kind, wish_mode: wishMode } : { kind };
  const response = await apiRequest(`/movies/${movie.id}/interest`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  const updatedMovie = normalizeMovie(response.item);
  applyUpdatedMovie(updatedMovie);
  if (viewerDetailState.movieId === movie.id) {
    try {
      const refreshedDetail = await loadMovieDetailsFromApi(movie.id, { force: true });
      renderViewerDetailPage(refreshedDetail);
    } catch {
      renderViewerDetailPage({ item: updatedMovie });
    }
  }
  if ((kind === "reserve" || kind === "buy") && viewerSessionProfile) {
    await loadViewerSessionFromApi();
    renderAccountView();
  }
  renderMovieGrid();
  syncDetailPanel();
  setStatus(response.message);
  return updatedMovie;
}

function renderPublishQueue() {
  const markup = publishQueue
    .map(
      (item) => `
        <article class="queue-item" data-queue-id="${item.id}">
          <span>${buildStageLabel(item.stage)} - ${item.status}</span>
          <strong>${item.title}</strong>
          <p>${item.note}</p>
          <div class="button-row">
            <button type="button" class="ghost-btn" data-queue-status="Published">Mark Published</button>
            <button type="button" class="ghost-btn" data-queue-status="Needs Changes">Needs Changes</button>
          </div>
        </article>
      `
    )
    .join("");

  if (producerQueue) {
    producerQueue.innerHTML = markup;
  }
  if (adminReviewList) {
    adminReviewList.innerHTML = markup;
  }
  renderAdminSummaryMetrics();
}

function getAdminDeliveryQueueStatusLabel(status) {
  const normalized = String(status || "").trim().toLowerCase();
  return {
    accepted: "Accepted",
    queued: "Queued",
    slot_granted: "Slot Granted",
    downloading: "Downloading",
    downloaded: "Downloaded",
    failed: "Failed",
  }[normalized] || (normalized ? normalized.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()) : "Unknown");
}

function renderAdminDeliveryQueueItemsGrid(state) {
  if (!Array.isArray(state?.items) || !state.items.length) {
    return `<div class="admin-user-empty">No delivery queue records matched this title and filters.</div>`;
  }

  const rows = state.items
    .map((item) => {
      const statusLabel = getAdminDeliveryQueueStatusLabel(item.status);
      const fifoLabel = item.fifo_position ? `#${item.fifo_position}` : "-";
      const qualityLabel = item.quality_label || item.quality_code || "No quality";
      const queueLabel = item.queue_position ? `Queue #${item.queue_position}` : "Active/Waiting";
      const networkLabel = [
        item.wifi_only ? "Wi-Fi" : "Any",
        item.charging_only ? "Charging" : "",
        item.auto_download ? "Auto" : "Manual",
      ].filter(Boolean).join(" / ");
      const progressLabel = item.download_completed_at
        ? `Completed ${formatAdminDateTimeDisplay(item.download_completed_at)}`
        : item.download_started_at
          ? `Started ${formatAdminDateTimeDisplay(item.download_started_at)}`
          : item.slot_expires_at
            ? `Slot till ${formatAdminDateTimeDisplay(item.slot_expires_at)}`
            : queueLabel;

      return `
        <div class="admin-delivery-queue-row" role="row">
          <span role="cell">${escapeHtml(fifoLabel)}</span>
          <span role="cell">
            <strong>${escapeHtml(item.user_name || "Unknown user")}</strong>
            <small>${escapeHtml(item.user_email || "Unknown email")}</small>
          </span>
          <span role="cell">${escapeHtml(qualityLabel)}</span>
          <span role="cell">${escapeHtml(String(item.stars_required || 0))}</span>
          <span role="cell"><mark>${escapeHtml(statusLabel)}</mark></span>
          <span role="cell">${escapeHtml(item.device_label || "Pending app settings")}</span>
          <span role="cell">${escapeHtml(networkLabel)}</span>
          <span role="cell">${escapeHtml(formatAdminDateTimeDisplay(item.accepted_at))}</span>
          <span role="cell">
            ${escapeHtml(progressLabel)}
            ${item.last_error ? `<small class="queue-item-error">${escapeHtml(item.last_error)}</small>` : ""}
          </span>
        </div>
      `;
    })
    .join("");

  return `
    <div class="admin-delivery-queue-grid" role="table" aria-label="Delivery queue records">
      <div class="admin-delivery-queue-row admin-delivery-queue-head" role="row">
        <span role="columnheader">FIFO</span>
        <span role="columnheader">User</span>
        <span role="columnheader">Quality</span>
        <span role="columnheader">Stars</span>
        <span role="columnheader">Status</span>
        <span role="columnheader">Device</span>
        <span role="columnheader">Network</span>
        <span role="columnheader">Accepted</span>
        <span role="columnheader">Progress</span>
      </div>
      ${rows}
    </div>
  `;
}

function renderAdminDeliveryQueueView() {
  if (!adminDeliveryQueueMovieTitle || !adminDeliveryQueueMovieSubtitle || !adminDeliveryQueueSummary || !adminDeliveryQueueList) {
    return;
  }

  const state = adminDeliveryQueueState;
  if (!adminDeliveryQueueMovieId || !state) {
    adminDeliveryQueueMovieTitle.textContent = "Open a title queue from the library";
    adminDeliveryQueueMovieSubtitle.textContent = "Select a title row and open its queue to review device transfers, status, and progress.";
    adminDeliveryQueueSummary.innerHTML = `<div class="admin-user-empty">Select a title row to load its delivery queue.</div>`;
    adminDeliveryQueueList.innerHTML = `<div class="admin-user-empty">No delivery queue is loaded yet.</div>`;
    if (adminDeliveryQueueCount) {
      adminDeliveryQueueCount.textContent = "0";
    }
    return;
  }

  const totalPages = Math.max(1, Math.ceil((state.total || 0) / (state.page_size || 1)));
  const summaryCards = [
    { label: "Accepted", value: state.summary?.accepted || 0, copy: "Users who accepted the download settings." },
    { label: "Queued", value: state.summary?.queued || 0, copy: "Waiting for an active slot." },
    { label: "Slot Granted", value: state.summary?.slot_granted || 0, copy: "Ready to download now." },
    { label: "Downloading", value: state.summary?.downloading || 0, copy: "Currently transferring chunks." },
    { label: "Downloaded", value: state.summary?.downloaded || 0, copy: "Encrypted package saved on device." },
    { label: "Failed", value: state.summary?.failed || 0, copy: "Needs attention or retry." },
  ];

  adminDeliveryQueueMovieTitle.textContent = `${state.movie_title || "Title"} delivery queue`;
  adminDeliveryQueueMovieSubtitle.textContent = `Showing ${state.total || 0} records for this title. Page ${state.page || 1} of ${totalPages}.`;
  if (adminDeliveryQueueCount) {
    adminDeliveryQueueCount.textContent = String(state.total || 0);
  }
  if (adminDeliveryQueueSearch && adminDeliveryQueueSearch.value !== adminDeliveryQueueSearchTerm) {
    adminDeliveryQueueSearch.value = adminDeliveryQueueSearchTerm;
  }
  if (adminDeliveryQueueStatus && adminDeliveryQueueStatus.value !== adminDeliveryQueueStatusFilter) {
    adminDeliveryQueueStatus.value = adminDeliveryQueueStatusFilter;
  }

  adminDeliveryQueueSummary.innerHTML = summaryCards
    .map(
      (card) => `
        <article class="admin-summary-card">
          <span>${escapeHtml(card.label)}</span>
          <strong>${escapeHtml(String(card.value))}</strong>
          <p>${escapeHtml(card.copy)}</p>
        </article>
      `
    )
    .join("");

  const itemsMarkup = Array.isArray(state.items) && state.items.length
    ? state.items
        .map((item) => {
          const statusLabel = getAdminDeliveryQueueStatusLabel(item.status);
          const fifoLabel = item.fifo_position ? `FIFO #${item.fifo_position}` : "FIFO";
          const queueLabel = item.queue_position ? `Queue #${item.queue_position}` : "Active";
          const qualityLabel = item.quality_label || item.quality_code || "No quality";
          const timingParts = [
            `Accepted ${formatAdminDateTimeDisplay(item.accepted_at)}`,
            item.download_started_at ? `Started ${formatAdminDateTimeDisplay(item.download_started_at)}` : "",
            item.download_completed_at ? `Completed ${formatAdminDateTimeDisplay(item.download_completed_at)}` : "",
          ].filter(Boolean);
          const networkLabel = [
            item.wifi_only ? "Wi-Fi only" : "Any network",
            item.charging_only ? "Charging only" : "",
            item.auto_download ? "Auto" : "Manual",
          ].filter(Boolean).join(" • ");
          return `
            <article class="queue-item">
              <span>${escapeHtml(fifoLabel)} • ${escapeHtml(statusLabel)}${item.queue_position ? ` • ${escapeHtml(queueLabel)}` : ""}</span>
              <strong>${escapeHtml(item.user_name || "Unknown user")} · ${escapeHtml(qualityLabel)}</strong>
              <p>${escapeHtml(item.user_email || "Unknown email")}</p>
              <p>${escapeHtml(item.device_label || "Pending app settings")} · ${escapeHtml(networkLabel)}</p>
              <p>${escapeHtml(`${item.stars_required || 0} star${Number(item.stars_required || 0) === 1 ? "" : "s"}`)} · ${escapeHtml(timingParts.join(" • ") || "Waiting for queue updates")}</p>
              ${item.last_error ? `<p class="queue-item-error">${escapeHtml(item.last_error)}</p>` : ""}
            </article>
          `;
        })
        .join("")
    : `<div class="admin-user-empty">No delivery queue records matched this title and filters.</div>`;

  adminDeliveryQueueList.innerHTML = `
    ${renderAdminDeliveryQueueItemsGrid(state)}
    <div class="admin-table-footer">
      <p class="admin-table-footnote">Showing ${(state.page - 1) * state.page_size + 1}-${Math.min(state.page * state.page_size, state.total || 0)} of ${state.total || 0} records</p>
      <div class="admin-pagination">
        <button type="button" class="ghost-btn" data-admin-delivery-queue-page="prev" ${state.page <= 1 ? "disabled" : ""}>Previous</button>
        <span class="admin-page-indicator">Page ${state.page || 1} of ${totalPages}</span>
        <button type="button" class="ghost-btn" data-admin-delivery-queue-page="next" ${state.page >= totalPages ? "disabled" : ""}>Next</button>
      </div>
    </div>
  `;
}

async function loadAdminDeliveryQueueFromApi(movieId, { page = 1, status = adminDeliveryQueueStatusFilter, search = adminDeliveryQueueSearchTerm } = {}) {
  if (!movieId) {
    adminDeliveryQueueMovieId = "";
    adminDeliveryQueueState = null;
    renderAdminDeliveryQueueView();
    return;
  }

  const params = new URLSearchParams();
  params.set("page", String(Math.max(1, page)));
  params.set("page_size", String(adminDeliveryQueuePageSize));
  if (status && status !== "all") {
    params.set("status", status);
  }
  if (search) {
    params.set("search", search);
  }

  const response = await apiRequest(`/admin/movies/${movieId}/delivery-queue?${params.toString()}`);
  adminDeliveryQueueMovieId = response.movie_id || movieId;
  adminDeliveryQueuePage = response.page || 1;
  adminDeliveryQueuePageSize = response.page_size || adminDeliveryQueuePageSize;
  adminDeliveryQueueStatusFilter = status;
  adminDeliveryQueueSearchTerm = search;
  adminDeliveryQueueState = response;
  renderAdminDeliveryQueueView();
}

function openAdminDeliveryQueueForMovie(movieId) {
  const selectedMovie = adminMovies.find((movie) => movie.id === movieId);
  if (!selectedMovie) {
    adminHelper.textContent = "Select a title first to load its delivery queue.";
    return;
  }
  setAdminPanel("delivery-queue");
  adminHelper.textContent = "";
  loadAdminDeliveryQueueFromApi(movieId).catch((error) => {
    adminHelper.textContent = error.message;
  });
}

if (adminDeliveryQueueSearch) {
  adminDeliveryQueueSearch.addEventListener("input", () => {
    adminDeliveryQueueSearchTerm = adminDeliveryQueueSearch.value;
    if (!adminDeliveryQueueMovieId) {
      renderAdminDeliveryQueueView();
      return;
    }
    adminDeliveryQueuePage = 1;
    loadAdminDeliveryQueueFromApi(adminDeliveryQueueMovieId, {
      page: 1,
      status: adminDeliveryQueueStatusFilter,
      search: adminDeliveryQueueSearchTerm,
    }).catch((error) => {
      adminHelper.textContent = error.message;
    });
  });
}

if (adminDeliveryQueueStatus) {
  adminDeliveryQueueStatus.addEventListener("change", () => {
    adminDeliveryQueueStatusFilter = adminDeliveryQueueStatus.value;
    if (!adminDeliveryQueueMovieId) {
      renderAdminDeliveryQueueView();
      return;
    }
    adminDeliveryQueuePage = 1;
    loadAdminDeliveryQueueFromApi(adminDeliveryQueueMovieId, {
      page: 1,
      status: adminDeliveryQueueStatusFilter,
      search: adminDeliveryQueueSearchTerm,
    }).catch((error) => {
      adminHelper.textContent = error.message;
    });
  });
}

if (adminDeliveryQueueRefresh) {
  adminDeliveryQueueRefresh.addEventListener("click", () => {
    if (!adminDeliveryQueueMovieId) {
      renderAdminDeliveryQueueView();
      return;
    }
    loadAdminDeliveryQueueFromApi(adminDeliveryQueueMovieId, {
      page: adminDeliveryQueuePage,
      status: adminDeliveryQueueStatusFilter,
      search: adminDeliveryQueueSearchTerm,
    }).catch((error) => {
      adminHelper.textContent = error.message;
    });
  });
}

if (adminDeliveryQueueList) {
  adminDeliveryQueueList.addEventListener("click", (event) => {
    const pageButton = event.target.closest("[data-admin-delivery-queue-page]");
    if (!pageButton || !adminDeliveryQueueMovieId) {
      return;
    }
    const nextPage = pageButton.dataset.adminDeliveryQueuePage === "next" ? adminDeliveryQueuePage + 1 : adminDeliveryQueuePage - 1;
    loadAdminDeliveryQueueFromApi(adminDeliveryQueueMovieId, {
      page: nextPage,
      status: adminDeliveryQueueStatusFilter,
      search: adminDeliveryQueueSearchTerm,
    }).catch((error) => {
      adminHelper.textContent = error.message;
    });
  });
}

function renderAdminMovieList() {
  if (!adminMovieList) {
    return;
  }

  const { filteredMovies, pagedMovies, totalPages, startIndex } = getProcessedAdminMovies();

  if (!filteredMovies.length) {
    adminMovieList.innerHTML = `<div class="admin-movie-empty">No titles matched your current search or filter.</div>`;
    renderAdminSummaryMetrics();
    return;
  }

  adminMovieList.innerHTML = `
    <div class="admin-movie-table-head">
      <span></span>
      <span>Stage</span>
      <span>Status</span>
      <span>Release Date</span>
      <span>Wish Online</span>
      <span>Wish Theatre</span>
      <span>Reserve</span>
      <span>Actions</span>
    </div>
    ${pagedMovies.map((movie) => `
      <article class="admin-movie-row" data-admin-movie-id="${movie.id}">
        <div class="admin-movie-main">
          ${
            `<img class="admin-movie-thumb" src="${toAssetUrl(movie.poster)}" alt="${escapeHtml(movie.title)} poster" loading="lazy" onerror="this.onerror=null;this.src='/media/posters/no-poster.svg';">`
          }
          <div>
            <strong>${escapeHtml(movie.title)}</strong>
            <p>${escapeHtml(movie.titleCaption || "No caption added.")}</p>
            ${buildAdminPricingSummaryMarkup(movie)}
          </div>
        </div>
        <div>
          <span class="admin-stage-badge admin-stage-cell${movie.archived ? " is-archived" : ""}">${escapeHtml(getAdminMovieStageLabel(movie))}</span>
        </div>
        <div>
          <span class="admin-stage-badge admin-approval-badge ${getApprovalStatusClass(movie.approvalStatus)}">${escapeHtml(movie.approvalStatusLabel)}</span>
          <span class="admin-release-plan-note">${escapeHtml(formatReleaseDecisionLabel(movie.releaseDecision))}</span>
        </div>
        <div class="admin-release-date-cell">${escapeHtml(formatAdminReleaseDate(movie.releaseDate))}</div>
        <div class="admin-movie-count">${escapeHtml(movie.wishOnlineCount ?? 0)}</div>
        <div class="admin-movie-count">${escapeHtml(movie.wishTheatreCount ?? 0)}</div>
        <div class="admin-movie-reserve-cell">
          <div class="admin-movie-count">${escapeHtml(movie.reserveCount ?? 0)}</div>
          <span class="admin-reserve-status-badge${movie.reserveEnabled ? " is-active" : " is-inactive"}">${movie.reserveEnabled ? "Reserve Active" : "Reserve Off"}</span>
        </div>
        <div class="admin-movie-actions">
          <div class="admin-movie-actions-top">
            <button type="button" class="icon-btn" data-admin-movie-action="edit" title="Edit title" aria-label="Edit title">&#9998;</button>
            <button type="button" class="icon-btn admin-movie-action-posters" data-admin-movie-action="posters" title="Upload posters" aria-label="Upload posters" ${movie.archived ? "disabled" : ""}>&#128247;</button>
            <button type="button" class="icon-btn admin-movie-action-trailer" data-admin-movie-action="trailer" title="Upload trailer" aria-label="Upload trailer" ${movie.archived ? "disabled" : ""}>&#127909;</button>
            <button type="button" class="icon-btn admin-movie-action-gallery" data-admin-movie-action="gallery" title="Upload gallery" aria-label="Upload gallery" ${movie.archived ? "disabled" : ""}>&#127748;</button>
            <button type="button" class="icon-btn admin-movie-action-music" data-admin-movie-action="music" title="Upload music" aria-label="Upload music" ${movie.archived ? "disabled" : ""}>&#9835;</button>
            <button type="button" class="icon-btn" data-admin-movie-action="delivery-queue" title="Open delivery queue" aria-label="Open delivery queue">&#9201;</button>
            <button type="button" class="icon-btn danger" data-admin-movie-action="archive" title="Archive title" aria-label="Archive title" ${movie.archived ? "disabled" : ""}>&#128465;</button>
          </div>
          <div class="admin-movie-actions-bottom">
            <button type="button" class="icon-btn admin-movie-action-approve" data-admin-movie-action="approve" title="Approve title" aria-label="Approve title" ${canApproveMovie(movie) ? "" : "disabled"}>&#10003;</button>
            <button type="button" class="icon-btn" data-admin-movie-action="pricing-targets" title="Pricing and targets" aria-label="Pricing and targets" ${movie.archived ? "disabled" : ""}>&#127919;</button>
            <button type="button" class="icon-btn admin-movie-action-reserve-start${movie.reserveEnabled ? " is-active" : ""}" data-admin-movie-action="reserve-start" title="${movie.reserveEnabled ? "Stop Reserve Now" : "Start Reserve Now"}" aria-label="${movie.reserveEnabled ? "Stop Reserve Now" : "Start Reserve Now"}" ${canToggleReserve(movie) ? "" : "disabled"}>${movie.reserveEnabled ? "&#9733;" : "&#9734;"}</button>
            <button type="button" class="icon-btn admin-movie-action-content" data-admin-movie-action="content" data-admin-content-open="${movie.id}" onclick="window.openAdminContentUploadForMovie('${movie.id}')" title="Upload main content" aria-label="Upload main content" ${movie.archived ? "disabled" : ""}>&#127916;</button>
            <button type="button" class="icon-btn admin-movie-action-release-main" data-admin-movie-action="release-main-content" data-admin-release-main-open="${movie.id}" onclick="window.openAdminReleaseMainContentForMovie('${movie.id}')" title="Release main content" aria-label="Release main content" ${movie.archived ? "disabled" : ""}>&#9654;</button>
          </div>
        </div>
        <div class="admin-movie-upload-start-row">${escapeHtml(formatAdminUploadStartLabel(movie.deliveryStartAt))}</div>
      </article>
    `).join("")}
    <div class="admin-table-footer">
      <p class="admin-table-footnote">Showing ${startIndex + 1}-${startIndex + pagedMovies.length} of ${filteredMovies.length} titles</p>
      <div class="admin-pagination">
        <button type="button" class="ghost-btn" data-admin-library-page="prev" ${adminLibraryPage <= 1 ? "disabled" : ""}>Previous</button>
        <span class="admin-page-indicator">Page ${adminLibraryPage} of ${totalPages}</span>
        <button type="button" class="ghost-btn" data-admin-library-page="next" ${adminLibraryPage >= totalPages ? "disabled" : ""}>Next</button>
      </div>
    </div>
  `;
  renderAdminSummaryMetrics();
}

function renderAdminArchiveMovieList() {
  if (!adminArchiveMovieList) {
    return;
  }

  const archivedMovies = getProcessedArchivedMovies();
  if (!archivedMovies.length) {
    adminArchiveMovieList.innerHTML = `<div class="admin-movie-empty">No archived titles yet.</div>`;
    return;
  }

  adminArchiveMovieList.innerHTML = `
    <div class="admin-movie-table-head admin-archive-table-head">
      <span></span>
      <span>Last Stage</span>
      <span>Status</span>
      <span>Release Date</span>
      <span>Wish Online</span>
      <span>Wish Theatre</span>
      <span>Reserve</span>
      <span>Actions</span>
    </div>
    ${archivedMovies.map((movie) => `
      <article class="admin-movie-row admin-archive-row" data-admin-archive-movie-id="${movie.id}">
        <div class="admin-movie-main">
          <img class="admin-movie-thumb" src="${toAssetUrl(movie.poster)}" alt="${escapeHtml(movie.title)} poster" loading="lazy" onerror="this.onerror=null;this.src='/media/posters/no-poster.svg';">
          <div>
            <strong>${escapeHtml(movie.title)}</strong>
            <p>${escapeHtml(movie.titleCaption || "Archived title")}</p>
          </div>
        </div>
        <div>
          <span class="admin-stage-badge is-archived">${escapeHtml(movie.stageLabel || buildStageLabel(movie.stage))}</span>
        </div>
        <div>
          <span class="admin-stage-badge is-archived">Archived</span>
        </div>
        <div class="admin-release-date-cell">${escapeHtml(formatAdminReleaseDate(movie.releaseDate))}</div>
        <div class="admin-movie-count">${escapeHtml(movie.wishOnlineCount ?? 0)}</div>
        <div class="admin-movie-count">${escapeHtml(movie.wishTheatreCount ?? 0)}</div>
        <div class="admin-movie-count">${escapeHtml(movie.reserveCount ?? 0)}</div>
        <div class="admin-movie-actions admin-archive-actions">
          <button type="button" class="icon-btn admin-archive-action-restore" data-admin-archive-action="restore" title="Restore title" aria-label="Restore title">&#8634;</button>
          <button type="button" class="icon-btn danger admin-archive-action-delete" data-admin-archive-action="delete" title="Delete permanently" aria-label="Delete permanently">&#128465;</button>
        </div>
      </article>
    `).join("")}
  `;
  renderAdminSummaryMetrics();
}

function renderAdminLibraryOptions() {
  if (adminLibraryCategory) {
    const categoryOptions = (adminTaxonomies.categories || [])
      .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`)
      .join("");
    adminLibraryCategory.innerHTML = `<option value="" selected>Select Category</option>${categoryOptions}`;
  }

  if (adminLibraryGenre) {
    adminLibraryGenre.innerHTML = (adminTaxonomies.genres || [])
      .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`)
      .join("");
  }
}

function setMultiSelectValues(selectElement, values) {
  if (!selectElement) {
    return;
  }

  const normalizedValues = new Set(values.map((value) => String(value).trim()).filter(Boolean));
  Array.from(selectElement.options).forEach((option) => {
    option.selected = normalizedValues.has(option.value);
  });
}

function getSelectedMultiValues(selectElement) {
  if (!selectElement) {
    return [];
  }
  return Array.from(selectElement.selectedOptions).map((option) => option.value.trim()).filter(Boolean);
}

function getMovieById(movieId) {
  return adminMovies.find((movie) => movie.id === movieId) || null;
}

function updateMovieCollections(updatedMovie) {
  adminMovies = adminMovies.map((movie) => (movie.id === updatedMovie.id ? updatedMovie : movie));

  const viewerIndex = movies.findIndex((movie) => movie.id === updatedMovie.id);
  if (updatedMovie.archived || !isViewerVisibleStatus(updatedMovie.approvalStatus)) {
    movies = movies.filter((movie) => movie.id !== updatedMovie.id);
  } else if (viewerIndex >= 0) {
    movies = movies.map((movie) => (movie.id === updatedMovie.id ? updatedMovie : movie));
  } else {
    movies = [updatedMovie, ...movies];
  }
}

function removeMovieFromCollections(movieId) {
  adminMovies = adminMovies.filter((movie) => movie.id !== movieId);
  movies = movies.filter((movie) => movie.id !== movieId);

  if (selectedMovieId === movieId) {
    selectedMovieId = movies[0]?.id || "";
  }
}

function openAdminReleaseMainContentModal(movie) {
  if (!adminReleaseMainContentModal || !adminReleaseMainContentMovieId || !movie) {
    return;
  }

  adminReleaseMainContentMovieId.value = movie.id;
  if (adminReleaseMainContentCopy) {
    adminReleaseMainContentCopy.textContent = `Schedule the release for "${movie.title}" and paste the passcode that viewers will use when the movie opens.`;
  }
  if (adminReleaseMainContentDateTime) {
    adminReleaseMainContentDateTime.value = toDateTimeLocalValue(movie.passwordPublishAt);
  }
  if (adminReleaseMainContentPasscode) {
    adminReleaseMainContentPasscode.value = movie.releasePasscode || "";
  }
  adminReleaseMainContentModal.classList.remove("hidden");
  adminReleaseMainContentModal.setAttribute("aria-hidden", "false");
}

function closeAdminReleaseMainContentModal() {
  if (!adminReleaseMainContentModal || !adminReleaseMainContentMovieId) {
    return;
  }

  adminReleaseMainContentModal.classList.add("hidden");
  adminReleaseMainContentModal.setAttribute("aria-hidden", "true");
  adminReleaseMainContentMovieId.value = "";
  if (adminReleaseMainContentDateTime) {
    adminReleaseMainContentDateTime.value = "";
  }
  if (adminReleaseMainContentPasscode) {
    adminReleaseMainContentPasscode.value = "";
  }
}

function buildApprovalPosterAssetUrl(movieId, value) {
  if (!movieId || !value || value === "Not set") {
    return "";
  }

  if (String(value).startsWith("media/")) {
    return toAssetUrl(value);
  }

  const normalized = String(value).trim();
  const orientation = normalized.toLowerCase().startsWith("horizontal:") ? "horizontal" : "vertical";
  const fileName = normalized.includes(":") ? normalized.split(":").slice(1).join(":").trim() : normalized;
  if (!fileName) {
    return "";
  }
  return `/media/library/${encodeURIComponent(movieId)}/posters/${orientation}/${encodeURIComponent(fileName)}`;
}

function renderApprovalPosterValue(movieId, value, label) {
  const assetUrl = buildApprovalPosterAssetUrl(movieId, value);
  if (!assetUrl) {
    return `<p>${escapeHtml(value || "Not set")}</p>`;
  }

  return `
    <a class="admin-approval-thumb-link" href="${escapeHtml(assetUrl)}" target="_blank" rel="noreferrer" title="Open ${escapeHtml(label)} in full size">
      <img class="admin-approval-thumb-image" src="${escapeHtml(assetUrl)}" alt="${escapeHtml(label)}" loading="lazy" onerror="this.onerror=null;this.src='/media/posters/no-poster.svg';">
      <span>${escapeHtml(value || label)}</span>
    </a>
  `;
}

function renderAdminApprovalReview(review) {
  const movieId = review?.item?.id || "";
  if (adminApprovalDiffList) {
    const changes = review.changes || [];
    adminApprovalDiffList.innerHTML = changes.length
      ? changes.map((change) => `
        <article class="admin-approval-diff-card">
          <span class="admin-approval-diff-label">${escapeHtml(change.label)}</span>
          <div class="admin-approval-diff-values">
            <div>
              <strong>Current</strong>
              ${change.field === "poster"
                ? renderApprovalPosterValue(movieId, change.current_value, `${change.label} current`)
                : `<p>${escapeHtml(change.current_value || "Not set")}</p>`}
            </div>
            <div>
              <strong>Pending</strong>
              ${change.field === "poster"
                ? renderApprovalPosterValue(movieId, change.pending_value, `${change.label} pending`)
                : `<p>${escapeHtml(change.pending_value || "Not set")}</p>`}
            </div>
          </div>
        </article>
      `).join("")
      : `<div class="admin-movie-empty">No field changes are waiting for approval.</div>`;
  }

  if (adminApprovalAssetList) {
    const assetChanges = review.asset_changes || [];
    adminApprovalAssetList.innerHTML = assetChanges.length
      ? assetChanges.map((change) => `
        <article class="admin-approval-asset-card">
          <div class="admin-approval-asset-header">
            <strong>${escapeHtml(change.label)}</strong>
            <span>${escapeHtml(`${(change.added_items || []).length} added / ${(change.removed_items || []).length} removed`)}</span>
          </div>
          <div class="admin-approval-asset-grid">
            <div>
              <strong>Current</strong>
              ${change.kind === "posters"
                ? `
                  <div class="admin-approval-thumb-grid">
                    ${(change.current_items || []).length
                      ? (change.current_items || []).map((item) => renderApprovalPosterValue(movieId, item, `${change.label} current`)).join("")
                      : `<p>None</p>`}
                  </div>
                `
                : `<p>${escapeHtml((change.current_items || []).join(", ") || "None")}</p>`}
            </div>
            <div>
              <strong>Pending</strong>
              ${change.kind === "posters"
                ? `
                  <div class="admin-approval-thumb-grid">
                    ${(change.pending_items || []).length
                      ? (change.pending_items || []).map((item) => renderApprovalPosterValue(movieId, item, `${change.label} pending`)).join("")
                      : `<p>None</p>`}
                  </div>
                `
                : `<p>${escapeHtml((change.pending_items || []).join(", ") || "None")}</p>`}
            </div>
          </div>
        </article>
      `).join("")
      : `<div class="admin-movie-empty">No poster, trailer, music, or content file changes are waiting for approval.</div>`;
  }
}

async function openAdminApprovalReviewModal(movie) {
  if (!adminApprovalModal || !adminApprovalMovieId || !movie) {
    return;
  }

  adminApprovalMovieId.value = movie.id;
  adminApprovalReview = null;
  if (adminApprovalCopy) {
    adminApprovalCopy.textContent = `Checking the current live version and the pending updates for "${movie.title}".`;
  }
  if (adminApprovalDiffList) {
    adminApprovalDiffList.innerHTML = `<div class="admin-movie-empty">Loading title changes...</div>`;
  }
  if (adminApprovalAssetList) {
    adminApprovalAssetList.innerHTML = `<div class="admin-movie-empty">Loading media changes...</div>`;
  }
  adminApprovalModal.classList.remove("hidden");
  adminApprovalModal.setAttribute("aria-hidden", "false");

  const review = await apiRequest(`/admin/movies/${movie.id}/approval-review`);
  adminApprovalReview = review;
  if (adminApprovalApproveButton) {
    adminApprovalApproveButton.disabled = !review.has_pending_changes;
  }
  if (adminApprovalCopy) {
    adminApprovalCopy.textContent = review.has_pending_changes
      ? `Review the differences for "${review.item.title}" before approving this version for viewers.`
      : `No pending differences were found for "${review.item.title}". You can close this window.`;
  }
  renderAdminApprovalReview(review);
}

function closeAdminApprovalReviewModal() {
  if (!adminApprovalModal || !adminApprovalMovieId) {
    return;
  }

  adminApprovalModal.classList.add("hidden");
  adminApprovalModal.setAttribute("aria-hidden", "true");
  adminApprovalMovieId.value = "";
  adminApprovalReview = null;
  if (adminApprovalDiffList) {
    adminApprovalDiffList.innerHTML = "";
  }
  if (adminApprovalAssetList) {
    adminApprovalAssetList.innerHTML = "";
  }
  if (adminApprovalApproveButton) {
    adminApprovalApproveButton.disabled = false;
  }
}

function openAdminPosterUploadModal(movie) {
  if (!adminPosterUploadModal || !adminPosterMovieId || !movie) {
    return;
  }

  adminPosterMovieId.value = movie.id;
  if (adminPosterUploadPreview) {
    adminPosterUploadPreview.classList.add("hidden");
    adminPosterUploadPreview.textContent = "";
  }
  if (adminPosterFiles) {
    adminPosterFiles.value = "";
  }
  adminPosterCarouselIndex = 0;
  if (adminPosterAssetList) {
    adminPosterAssetList.innerHTML = `<div class="admin-media-empty">Loading posters...</div>`;
  }
  adminPosterUploadModal.classList.remove("hidden");
  adminPosterUploadModal.setAttribute("aria-hidden", "false");
  loadAdminMediaAssets(movie.id, "posters").catch((error) => {
    if (adminPosterAssetList) {
      adminPosterAssetList.innerHTML = `<div class="admin-media-empty">${escapeHtml(error.message)}</div>`;
    }
  });
}

function closeAdminPosterUploadModal() {
  if (!adminPosterUploadModal || !adminPosterMovieId) {
    return;
  }

  adminPosterUploadModal.classList.add("hidden");
  adminPosterUploadModal.setAttribute("aria-hidden", "true");
  adminPosterMovieId.value = "";
  if (adminPosterFiles) {
    adminPosterFiles.value = "";
  }
  if (adminPosterUploadPreview) {
    adminPosterUploadPreview.classList.add("hidden");
    adminPosterUploadPreview.textContent = "";
  }
  if (adminPosterAssetList) {
    adminPosterAssetList.innerHTML = "";
  }
  adminPosterAssets = [];
  adminPosterCarouselIndex = 0;
}

function openAdminTrailerUploadModal(movie) {
  if (!adminTrailerUploadModal || !adminTrailerMovieId || !movie) {
    return;
  }

  adminTrailerMovieId.value = movie.id;
  if (adminTrailerFile) {
    adminTrailerFile.value = "";
  }
  adminTrailerCarouselIndex = 0;
  if (adminTrailerAssetList) {
    adminTrailerAssetList.innerHTML = `<div class="admin-media-empty">Loading trailers...</div>`;
  }
  adminTrailerUploadModal.classList.remove("hidden");
  adminTrailerUploadModal.setAttribute("aria-hidden", "false");
  loadAdminMediaAssets(movie.id, "trailer").catch((error) => {
    if (adminTrailerAssetList) {
      adminTrailerAssetList.innerHTML = `<div class="admin-media-empty">${escapeHtml(error.message)}</div>`;
    }
  });
}

function closeAdminTrailerUploadModal() {
  if (!adminTrailerUploadModal || !adminTrailerMovieId) {
    return;
  }

  adminTrailerUploadModal.classList.add("hidden");
  adminTrailerUploadModal.setAttribute("aria-hidden", "true");
  adminTrailerMovieId.value = "";
  if (adminTrailerFile) {
    adminTrailerFile.value = "";
  }
  if (adminTrailerAssetList) {
    adminTrailerAssetList.innerHTML = "";
  }
  adminTrailerAssets = [];
  adminTrailerCarouselIndex = 0;
}

function openAdminGalleryUploadModal(movie) {
  if (!adminGalleryUploadModal || !adminGalleryMovieId || !movie) {
    return;
  }

  adminGalleryMovieId.value = movie.id;
  if (adminGalleryFile) {
    adminGalleryFile.value = "";
  }
  adminGalleryCarouselIndex = 0;
  if (adminGalleryAssetList) {
    adminGalleryAssetList.innerHTML = `<div class="admin-media-empty">Loading gallery files...</div>`;
  }
  adminGalleryUploadModal.classList.remove("hidden");
  adminGalleryUploadModal.setAttribute("aria-hidden", "false");
  loadAdminMediaAssets(movie.id, "gallery").catch((error) => {
    if (adminGalleryAssetList) {
      adminGalleryAssetList.innerHTML = `<div class="admin-media-empty">${escapeHtml(error.message)}</div>`;
    }
  });
}

function closeAdminGalleryUploadModal() {
  if (!adminGalleryUploadModal || !adminGalleryMovieId) {
    return;
  }

  adminGalleryUploadModal.classList.add("hidden");
  adminGalleryUploadModal.setAttribute("aria-hidden", "true");
  adminGalleryMovieId.value = "";
  if (adminGalleryFile) {
    adminGalleryFile.value = "";
  }
  if (adminGalleryAssetList) {
    adminGalleryAssetList.innerHTML = "";
  }
  adminGalleryAssets = [];
  adminGalleryCarouselIndex = 0;
}

function openAdminMusicUploadModal(movie) {
  if (!adminMusicUploadModal || !adminMusicMovieId || !movie) {
    return;
  }

  adminMusicMovieId.value = movie.id;
  if (adminMusicFile) {
    adminMusicFile.value = "";
  }
  adminMusicCarouselIndex = 0;
  if (adminMusicAssetList) {
    adminMusicAssetList.innerHTML = `<div class="admin-media-empty">Loading music files...</div>`;
  }
  adminMusicUploadModal.classList.remove("hidden");
  adminMusicUploadModal.setAttribute("aria-hidden", "false");
  loadAdminMediaAssets(movie.id, "music").catch((error) => {
    if (adminMusicAssetList) {
      adminMusicAssetList.innerHTML = `<div class="admin-media-empty">${escapeHtml(error.message)}</div>`;
    }
  });
}

function closeAdminMusicUploadModal() {
  if (!adminMusicUploadModal || !adminMusicMovieId) {
    return;
  }

  adminMusicUploadModal.classList.add("hidden");
  adminMusicUploadModal.setAttribute("aria-hidden", "true");
  adminMusicMovieId.value = "";
  if (adminMusicFile) {
    adminMusicFile.value = "";
  }
  if (adminMusicAssetList) {
    adminMusicAssetList.innerHTML = "";
  }
  adminMusicAssets = [];
  adminMusicCarouselIndex = 0;
}

function clearAdminContentUploadPreview() {
  if (adminContentUploadPreview) {
    adminContentUploadPreview.classList.add("hidden");
    adminContentUploadPreview.textContent = "";
  }
}

function renderAdminContentUploadPreview() {
  if (!adminContentUploadPreview) {
    return;
  }
  const files = Array.from(adminContentFiles?.files || []);
  if (!files.length) {
    clearAdminContentUploadPreview();
    return;
  }
  adminContentUploadPreview.classList.remove("hidden");
  adminContentUploadPreview.innerHTML = `
    <strong>${files.length} chunk file${files.length === 1 ? "" : "s"} selected</strong>
    <ul class="admin-content-preview-list">
      ${files.map((file) => `<li>${escapeHtml(file.name)} • ${formatBytes(file.size)}</li>`).join("")}
    </ul>
  `;
}

async function openAdminContentQualityUploadModal(movie) {
  if (!adminContentUploadModal || !adminContentMovieId || !movie) {
    return;
  }

  const selectedMovie = adminMovies.find((item) => item.id === movie.id) || movie;
  const selectedUploadStartAt = selectedMovie.deliveryStartAt || "";
  adminContentMovieId.value = movie.id;
  setAdminLibraryUploadStartAtDisplay(selectedMovie.title, selectedUploadStartAt);
  setAdminContentUploadStartAtDisplay(selectedUploadStartAt);
  if (adminContentFiles) {
    adminContentFiles.value = "";
  }
  if (adminContentPassword) {
    adminContentPassword.value = "";
  }
  clearAdminContentUploadPreview();
  if (adminContentAssetList) {
    adminContentAssetList.innerHTML = `<div class="admin-media-empty">Loading content chunks...</div>`;
  }
  adminContentUploadModal.classList.remove("hidden");
  adminContentUploadModal.setAttribute("aria-hidden", "false");

  const latestMovie = await refreshAdminContentDeliveryStart(movie.id).catch(() => null);
  const resolvedMovie = latestMovie || selectedMovie;
  const resolvedUploadStartAt = resolvedMovie.deliveryStartAt || selectedUploadStartAt;
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = resolvedUploadStartAt ? formatAdminDateForInput(resolvedUploadStartAt) : "";
  }
  setAdminLibraryUploadStartAtDisplay(resolvedMovie.title, resolvedUploadStartAt);
  setAdminContentUploadStartAtDisplay(resolvedUploadStartAt);

  loadAdminContentQualityAssets(movie.id).catch((error) => {
    if (adminContentAssetList) {
      adminContentAssetList.innerHTML = `<div class="admin-media-empty">${escapeHtml(error.message)}</div>`;
    }
  });
}

function closeAdminContentQualityUploadModal() {
  if (!adminContentUploadModal || !adminContentMovieId) {
    return;
  }

  adminContentUploadModal.classList.add("hidden");
  adminContentUploadModal.setAttribute("aria-hidden", "true");
  adminContentMovieId.value = "";
  if (adminContentFiles) {
    adminContentFiles.value = "";
  }
  if (adminContentPassword) {
    adminContentPassword.value = "";
  }
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = "";
  }
  if (adminContentAssetList) {
    adminContentAssetList.innerHTML = "";
  }
  clearAdminContentUploadPreview();
  setAdminContentUploadStartAtDisplay("");
}

function clearAdminContentPreviewUrls() {
  for (const objectUrl of adminContentPreviewUrls.values()) {
    URL.revokeObjectURL(objectUrl);
  }
  adminContentPreviewUrls = new Map();
}

function setAdminContentUploadSummary(message, tone = "neutral") {
  if (!adminContentUploadPreview) {
    return;
  }
  if (!message) {
    adminContentUploadPreview.classList.add("hidden");
    adminContentUploadPreview.textContent = "";
    return;
  }
  adminContentUploadPreview.classList.remove("hidden");
  adminContentUploadPreview.dataset.tone = tone;
  adminContentUploadPreview.textContent = message;
}

function setAdminLibraryUploadStartAtDisplay(movieTitle, uploadStartAt) {
  if (!adminLibraryUploadStartAtDisplay) {
    return;
  }
  const titlePart = movieTitle ? `${movieTitle} - ` : "";
  const timePart = formatAdminDateTimeDisplay(uploadStartAt);
  adminLibraryUploadStartAtDisplay.textContent = `Upload Start Date Time - ${titlePart}${timePart}`;
}

function setAdminContentUploadStartAtDisplay(uploadStartAt) {
  if (!adminContentUploadStartAtDisplay) {
    return;
  }
  adminContentUploadStartAtDisplay.textContent = uploadStartAt
    ? `Saved ${formatAdminDateTimeDisplay(uploadStartAt)}`
    : "Not set";
}

async function refreshAdminContentDeliveryStart(movieId) {
  const response = await apiRequest(`/movies/${movieId}/details`);
  const movie = normalizeMovie(response.item);
  updateMovieCollections(movie);
  if (movie.deliveryStartAt) {
    setAdminLibraryUploadStartAtDisplay(movie.title, movie.deliveryStartAt);
    setAdminContentUploadStartAtDisplay(movie.deliveryStartAt);
    if (adminContentUploadStartAt) {
      adminContentUploadStartAt.value = formatAdminDateForInput(movie.deliveryStartAt);
    }
  }
  return movie;
}

function updateAdminContentScheduleState(isComplete) {
  if (!adminContentUploadStartAt) {
    return;
  }
  adminContentUploadStartAt.disabled = !isComplete;
}

function normalizeAdminContentQualityItem(item) {
  return {
    qualityCode: item?.qualityCode ?? item?.quality_code ?? "",
    qualityLabel: item?.qualityLabel ?? item?.quality_label ?? "",
    starsRequired: item?.starsRequired ?? item?.stars_required ?? 0,
    uploaded: Boolean(item?.uploaded ?? false),
    sourceName: item?.sourceName ?? item?.source_name ?? null,
    sourceExtension: item?.sourceExtension ?? item?.source_extension ?? null,
    chunkCount: item?.chunkCount ?? item?.chunk_count ?? 0,
    uploadedAt: item?.uploadedAt ?? item?.uploaded_at ?? null,
  };
}

function renderAdminContentQualityPreview(card) {
  const qualityCode = card?.dataset.adminContentQualityCode || "";
  const fileInput = card?.querySelector("[data-admin-content-file-input]");
  const preview = card?.querySelector("[data-admin-content-file-preview]");
  const file = fileInput?.files?.[0];
  if (!preview || !fileInput) {
    return;
  }

  const existingUrl = adminContentPreviewUrls.get(qualityCode);
  if (existingUrl) {
    URL.revokeObjectURL(existingUrl);
    adminContentPreviewUrls.delete(qualityCode);
  }

  if (!file) {
    preview.innerHTML = `<div class="admin-content-preview-placeholder">Choose a file to preview it here.</div>`;
    preview.classList.add("hidden");
    return;
  }

  const objectUrl = URL.createObjectURL(file);
  adminContentPreviewUrls.set(qualityCode, objectUrl);
  preview.classList.remove("hidden");

  if (isWebPlayableMainContentExtension(file.name)) {
    preview.innerHTML = `
      <video controls playsinline preload="metadata" src="${escapeHtml(objectUrl)}"></video>
      <div class="admin-content-preview-meta">
        <strong>${escapeHtml(file.name)}</strong>
        <span>${escapeHtml(formatBytes(file.size))}</span>
      </div>
    `;
  } else {
    preview.innerHTML = `
      <div class="admin-content-preview-placeholder">
        ${escapeHtml(file.name)} is selected. This browser preview supports MP4, M4V, and WebM files.
      </div>
      <div class="admin-content-preview-meta">
        <strong>${escapeHtml(file.name)}</strong>
        <span>${escapeHtml(formatBytes(file.size))}</span>
      </div>
    `;
  }
}

function renderAdminContentQualityAssets(container, items, isComplete) {
  if (!container) {
    return;
  }

  clearAdminContentPreviewUrls();
  const normalizedItems = Array.isArray(items) ? items.map(normalizeAdminContentQualityItem) : [];
  adminContentQualityState = {
    movieId: adminContentMovieId?.value.trim() || "",
    items: normalizedItems,
    isComplete: Boolean(isComplete),
  };

  updateAdminContentScheduleState(adminContentQualityState.isComplete);
  if (!adminContentQualityState.items.length) {
    setAdminContentUploadSummary("No title qualities are configured for this title.", "warning");
    container.innerHTML = `<div class="admin-media-empty">No title qualities are configured for this title.</div>`;
    return;
  }

  const uploadedCount = adminContentQualityState.items.filter((item) => item.uploaded).length;
  const totalCount = adminContentQualityState.items.length;
  const summaryMessage = adminContentQualityState.isComplete
    ? `All ${totalCount} title qualities are uploaded. You can now set a future start time.`
    : `${uploadedCount} of ${totalCount} title qualities uploaded. Finish the remaining cards before setting a future start time.`;
  setAdminContentUploadSummary(summaryMessage, adminContentQualityState.isComplete ? "success" : "warning");

  container.innerHTML = adminContentQualityState.items.map((item) => {
    const statusLabel = item.uploaded
      ? `Uploaded${item.chunkCount ? ` · ${item.chunkCount} chunk${item.chunkCount === 1 ? "" : "s"}` : ""}`
      : "Missing";
    const statusClass = item.uploaded ? "is-uploaded" : "is-missing";
    const existingFileLabel = item.uploaded
      ? `${escapeHtml(item.sourceName || item.qualityLabel)}${item.sourceExtension ? ` ${escapeHtml(item.sourceExtension)}` : ""}`
      : "No file uploaded yet";
    return `
      <article class="admin-content-quality-card ${statusClass}" data-admin-content-quality-card="${escapeHtml(item.qualityCode)}">
        <div class="admin-content-quality-card-header">
          <div>
            <h3>${escapeHtml(item.qualityLabel)}</h3>
          </div>
        </div>
        <p class="admin-content-quality-file">${escapeHtml(existingFileLabel)}</p>
        <label class="field admin-content-quality-field">
          <span>Select file for ${escapeHtml(item.qualityLabel)}</span>
          <input
            type="file"
            accept=".mp4,.m4v,.webm,video/mp4,video/webm"
            data-admin-content-file-input
            data-admin-content-quality-code="${escapeHtml(item.qualityCode)}"
          >
        </label>
        <div class="admin-content-preview hidden" data-admin-content-file-preview>
          <div class="admin-content-preview-placeholder">Choose a file to preview it here.</div>
        </div>
        <label class="field admin-content-quality-field">
          <span>Passcode for encryption</span>
          <div class="admin-content-password-row">
            <input type="text" placeholder="Enter passcode" data-admin-content-password>
            <button type="button" class="ghost-btn" data-admin-content-generate-password>Generate Strong Password</button>
          </div>
        </label>
        <div class="admin-content-quality-actions">
          <button type="button" class="primary-btn" data-admin-content-upload-button data-admin-content-quality-code="${escapeHtml(item.qualityCode)}">Upload ${escapeHtml(item.qualityLabel)}</button>
          <button type="button" class="icon-btn danger" data-admin-content-delete-button data-admin-content-quality-code="${escapeHtml(item.qualityCode)}" ${item.uploaded ? "" : "disabled"} aria-label="Delete ${escapeHtml(item.qualityLabel)}" title="Delete ${escapeHtml(item.qualityLabel)}">&#128465;</button>
        </div>
      </article>
    `;
  }).join("");
}

async function loadAdminContentQualityAssets(movieId) {
  const response = await apiRequest(`/admin/movies/${movieId}/assets/content`);
  renderAdminContentQualityAssets(adminContentAssetList, response.items || [], response.is_complete);
}

function openAdminContentUploadModal(movie) {
  if (!adminContentUploadModal || !adminContentMovieId || !movie) {
    return;
  }

  clearAdminContentPreviewUrls();
  adminContentMovieId.value = movie.id;
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = "";
  }
  updateAdminContentScheduleState(false);
  setAdminContentUploadSummary("Loading title qualities...", "neutral");
  if (adminContentAssetList) {
    adminContentAssetList.innerHTML = `<div class="admin-media-empty">Loading title qualities...</div>`;
  }
  adminContentUploadModal.classList.remove("hidden");
  adminContentUploadModal.setAttribute("aria-hidden", "false");
  loadAdminContentQualityAssets(movie.id).catch((error) => {
    setAdminContentUploadSummary(error.message, "danger");
    if (adminContentAssetList) {
      adminContentAssetList.innerHTML = `<div class="admin-media-empty">${escapeHtml(error.message)}</div>`;
    }
  });
}

function closeAdminContentUploadModal() {
  if (!adminContentUploadModal || !adminContentMovieId) {
    return;
  }

  adminContentUploadModal.classList.add("hidden");
  adminContentUploadModal.setAttribute("aria-hidden", "true");
  adminContentMovieId.value = "";
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = "";
    adminContentUploadStartAt.disabled = true;
  }
  if (adminContentAssetList) {
    adminContentAssetList.innerHTML = "";
  }
  setAdminContentUploadSummary("");
  clearAdminContentPreviewUrls();
  adminContentQualityState = {
    movieId: "",
    items: [],
    isComplete: false,
  };
}

async function uploadAdminMovieContentQualityRemote(movieId, qualityCode, file, password) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("password", password);
  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/content/${encodeURIComponent(qualityCode)}`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = "";
  }
  await loadAdminContentQualityAssets(movieId);
  adminHelper.textContent = response.message;
}

async function scheduleAdminMovieContentRemote(movieId, uploadStartAt) {
  const formData = new FormData();
  formData.append("upload_start_at", uploadStartAt || "");
  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/content`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadAdminContentQualityAssets(movieId);
  setAdminContentUploadSummary(response.message, "success");
  const scheduledMovie = normalizeMovie(response.item);
  setAdminLibraryUploadStartAtDisplay(scheduledMovie.title, scheduledMovie.deliveryStartAt || uploadStartAt);
  setAdminContentUploadStartAtDisplay(scheduledMovie.deliveryStartAt || uploadStartAt);
  adminHelper.textContent = response.message;
}

async function deleteAdminContentQualityRemote(movieId, qualityCode) {
  const response = await apiDeleteRequest(`/admin/movies/${movieId}/assets/content/${encodeURIComponent(qualityCode)}`);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadAdminContentQualityAssets(movieId);
  const selectedMovie = adminMovies.find((movie) => movie.id === movieId);
  setAdminLibraryUploadStartAtDisplay(selectedMovie?.title || "", "");
  setAdminContentUploadStartAtDisplay("");
  adminHelper.textContent = response.message;
}

window.openAdminContentUploadForMovie = function openAdminContentUploadForMovie(movieId) {
  const selectedMovie = adminMovies.find((movie) => movie.id === movieId);
  if (selectedMovie && !selectedMovie.archived) {
    openAdminContentQualityUploadModal(selectedMovie);
  }
};

window.openAdminReleaseMainContentForMovie = function openAdminReleaseMainContentForMovie(movieId) {
  const selectedMovie = adminMovies.find((movie) => movie.id === movieId);
  if (selectedMovie && !selectedMovie.archived) {
    openAdminReleaseMainContentModal(selectedMovie);
  }
};

function classifyPosterFile(file) {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();

    image.onload = () => {
      const orientation = image.naturalWidth >= image.naturalHeight ? "horizontal" : "vertical";
      URL.revokeObjectURL(objectUrl);
      resolve({
        file,
        orientation,
        width: image.naturalWidth,
        height: image.naturalHeight,
      });
    };

    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error(`Unable to read image dimensions for ${file.name}.`));
    };

    image.src = objectUrl;
  });
}

function renderAdminPosterCarousel(items) {
  if (!adminPosterAssetList) {
    return;
  }

  adminPosterAssets = items || [];
  if (!adminPosterAssets.length) {
    adminPosterCarouselIndex = 0;
    adminPosterAssetList.innerHTML = `<div class="admin-media-empty">No posters uploaded yet.</div>`;
    return;
  }

  adminPosterCarouselIndex = Math.max(0, Math.min(adminPosterCarouselIndex, adminPosterAssets.length - 1));
  const activePoster = adminPosterAssets[adminPosterCarouselIndex];
  const imageUrl = `${toAssetUrl(activePoster.url || activePoster.path)}?asset=${encodeURIComponent(activePoster.name)}`;

  adminPosterAssetList.innerHTML = `
    <div class="admin-poster-stage">
      <button type="button" class="icon-btn admin-poster-arrow left" data-admin-poster-nav="prev" aria-label="Previous poster" ${adminPosterAssets.length <= 1 ? "disabled" : ""}>&#8249;</button>
      <button type="button" class="icon-btn admin-poster-arrow right" data-admin-poster-nav="next" aria-label="Next poster" ${adminPosterAssets.length <= 1 ? "disabled" : ""}>&#8250;</button>
      <div class="admin-poster-slide">
        <button type="button" class="icon-btn danger admin-poster-delete" data-admin-media-delete="posters" data-admin-media-name="${escapeHtml(activePoster.name)}" title="Delete poster" aria-label="Delete poster">&#128465;</button>
        <a href="${escapeHtml(imageUrl)}" target="_blank" rel="noreferrer" title="Open full size poster">
          <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(activePoster.name)}" loading="eager" decoding="async">
        </a>
      </div>
    </div>
    <div class="admin-poster-meta">
      <span>${escapeHtml(activePoster.name)}</span>
      <span>${adminPosterCarouselIndex + 1} / ${adminPosterAssets.length} • ${escapeHtml(activePoster.orientation || "poster")} • Click image to open full size</span>
    </div>
  `;
}

function renderAdminMediaCarousel(kind, items) {
  const container = kind === "trailer" ? adminTrailerAssetList : kind === "gallery" ? adminGalleryAssetList : adminMusicAssetList;
  if (!container) {
    return;
  }

  if (kind === "trailer") {
    adminTrailerAssets = items || [];
    if (!adminTrailerAssets.length) {
      adminTrailerCarouselIndex = 0;
      container.innerHTML = `<div class="admin-media-empty">No trailers uploaded yet.</div>`;
      return;
    }
    adminTrailerCarouselIndex = Math.max(0, Math.min(adminTrailerCarouselIndex, adminTrailerAssets.length - 1));
  } else if (kind === "gallery") {
    adminGalleryAssets = items || [];
    if (!adminGalleryAssets.length) {
      adminGalleryCarouselIndex = 0;
      container.innerHTML = `<div class="admin-media-empty">No gallery files uploaded yet.</div>`;
      return;
    }
    adminGalleryCarouselIndex = Math.max(0, Math.min(adminGalleryCarouselIndex, adminGalleryAssets.length - 1));
  } else {
    adminMusicAssets = items || [];
    if (!adminMusicAssets.length) {
      adminMusicCarouselIndex = 0;
      container.innerHTML = `<div class="admin-media-empty">No music uploaded yet.</div>`;
      return;
    }
    adminMusicCarouselIndex = Math.max(0, Math.min(adminMusicCarouselIndex, adminMusicAssets.length - 1));
  }

  const assetList = kind === "trailer" ? adminTrailerAssets : kind === "gallery" ? adminGalleryAssets : adminMusicAssets;
  const activeIndex = kind === "trailer" ? adminTrailerCarouselIndex : kind === "gallery" ? adminGalleryCarouselIndex : adminMusicCarouselIndex;
  const activeAsset = assetList[activeIndex];
  const mediaUrl = `${toAssetUrl(activeAsset.url || activeAsset.path)}?asset=${encodeURIComponent(activeAsset.name)}`;
  const mediaMarkup = kind === "trailer" || kind === "gallery"
    ? `<video src="${escapeHtml(mediaUrl)}" controls preload="metadata"></video>`
    : `<audio src="${escapeHtml(mediaUrl)}" controls preload="metadata"></audio>`;

  container.innerHTML = `
    <div class="admin-media-stage">
      <button type="button" class="icon-btn admin-media-arrow left" data-admin-media-nav="${escapeHtml(kind)}-prev" aria-label="Previous ${escapeHtml(kind)}" ${assetList.length <= 1 ? "disabled" : ""}>&#8249;</button>
      <button type="button" class="icon-btn admin-media-arrow right" data-admin-media-nav="${escapeHtml(kind)}-next" aria-label="Next ${escapeHtml(kind)}" ${assetList.length <= 1 ? "disabled" : ""}>&#8250;</button>
      <div class="admin-media-slide">
        <button type="button" class="icon-btn danger admin-media-delete" data-admin-media-delete="${escapeHtml(kind)}" data-admin-media-name="${escapeHtml(activeAsset.name)}" title="Delete ${escapeHtml(kind)}" aria-label="Delete ${escapeHtml(kind)}">&#128465;</button>
        ${mediaMarkup}
      </div>
    </div>
    <div class="admin-media-meta">
      <span>${escapeHtml(activeAsset.name)}</span>
      <span>${activeIndex + 1} / ${assetList.length} • ${escapeHtml(kind)} file</span>
    </div>
  `;
}

function renderAdminMediaAssets(container, items, kind) {
  if (!container) {
    return;
  }

  if (kind === "posters") {
    renderAdminPosterCarousel(items);
    return;
  }

  if (kind === "trailer" || kind === "gallery" || kind === "music") {
    renderAdminMediaCarousel(kind, items);
    return;
  }

  if (kind === "content") {
    if (!items.length) {
      container.innerHTML = `<div class="admin-media-empty">No content chunks uploaded yet.</div>`;
      return;
    }

    container.innerHTML = items.map((item, index) => `
      <article class="admin-media-card admin-content-card">
        <div class="admin-media-card-header">
          <div class="admin-media-card-copy">
            <strong>${escapeHtml(item.name)}</strong>
            <p>Chunk ${index + 1} • Encrypted main content piece</p>
          </div>
          <button
            type="button"
            class="icon-btn danger"
            data-admin-media-delete="content"
            data-admin-media-name="${escapeHtml(item.name)}"
            title="Delete chunk"
            aria-label="Delete chunk"
          >&#128465;</button>
        </div>
        <div class="admin-content-chip">Chunk file</div>
      </article>
    `).join("");
    return;
  }

  if (!items.length) {
    container.innerHTML = `<div class="admin-media-empty">No ${kind} uploaded yet.</div>`;
    return;
  }

  container.innerHTML = items.map((item) => {
    const previewMarkup = kind === "posters"
      ? `<img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.name)}" loading="lazy">`
      : kind === "music"
        ? `<audio src="${escapeHtml(item.url)}" controls preload="metadata"></audio>`
        : `<video src="${escapeHtml(item.url)}" controls preload="metadata"></video>`;

    const metaLine = kind === "posters"
      ? `${escapeHtml(item.orientation || "")} poster`
      : `${escapeHtml(kind)} file`;

    return `
      <article class="admin-media-card">
        <div class="admin-media-card-header">
          <div class="admin-media-card-copy">
            <strong>${escapeHtml(item.name)}</strong>
            <p>${metaLine}</p>
          </div>
          <button
            type="button"
            class="icon-btn danger"
            data-admin-media-delete="${escapeHtml(kind)}"
            data-admin-media-name="${escapeHtml(item.name)}"
            title="Delete file"
            aria-label="Delete file"
          >&#128465;</button>
        </div>
        ${previewMarkup}
      </article>
    `;
  }).join("");
}

async function loadAdminMediaAssets(movieId, kind) {
  const response = await apiRequest(`/admin/movies/${movieId}/assets/${kind}`);
  const items = response.items || [];
  if (kind === "posters") {
    renderAdminMediaAssets(adminPosterAssetList, items, "posters");
  } else if (kind === "trailer") {
    renderAdminMediaAssets(adminTrailerAssetList, items, "trailer");
  } else if (kind === "gallery") {
    renderAdminMediaAssets(adminGalleryAssetList, items, "gallery");
  } else if (kind === "music") {
    renderAdminMediaAssets(adminMusicAssetList, items, "music");
  } else if (kind === "content") {
    renderAdminMediaAssets(adminContentAssetList, items, "content");
  }
}

function openAdminLibraryEditor(movie = null) {
  if (!adminLibraryModal || !adminLibraryEditor) {
    return;
  }

  const isEditing = Boolean(movie);
  renderAdminLibraryOptions();
  adminLibraryModal.classList.remove("hidden");
  adminLibraryModal.setAttribute("aria-hidden", "false");
  adminLibraryEditId.value = movie?.id || "";
  adminLibraryCategory.value = movie?.titleCategory || "";
  adminLibraryTitle.value = movie?.title || "";
  adminLibraryCaption.value = movie?.titleCaption || "";
  setMultiSelectValues(adminLibraryGenre, String(movie?.genre || "").split(","));
  adminLibraryMovieStage.value = movie?.stage || "upcoming";
  adminLibraryExpectedDate.value = formatAdminDateForInput(movie?.releaseDate);
  renderAdminCastCreditRows(movie?.castCredits || []);
  adminLibraryDescription.value = movie?.description || "";
  adminLibraryModalTitle.textContent = isEditing ? "Edit Title" : "Add New Title";
  adminLibraryModalCopy.textContent = isEditing
    ? "Update title details, release placement, and forecast information."
    : "Create a title record for the app library and place it in the correct section.";
  adminLibraryTitle.focus();
}

function closeAdminLibraryEditor() {
  if (!adminLibraryModal || !adminLibraryEditor) {
    return;
  }

  adminLibraryModal.classList.add("hidden");
  adminLibraryModal.setAttribute("aria-hidden", "true");
  adminLibraryEditId.value = "";
  adminLibraryCategory.value = "";
  adminLibraryTitle.value = "";
  adminLibraryCaption.value = "";
  setMultiSelectValues(adminLibraryGenre, []);
  adminLibraryMovieStage.value = "upcoming";
  adminLibraryExpectedDate.value = "";
  renderAdminCastCreditRows([]);
  adminLibraryDescription.value = "";
}

function openAdminPricingTargetsModal(movie) {
  if (!adminPricingTargetsModal || !adminPricingTargetsMovieId || !movie) {
    return;
  }

  adminPricingTargetsMovieId.value = movie.id;
  if (adminPricingTargetsCopy) {
    adminPricingTargetsCopy.textContent = `Set online quality pricing, theatre stars, and target stars for "${movie.title}".`;
  }
  if (adminPricingTheatreStars) {
    adminPricingTheatreStars.value = String(movie.starsRequiredTheatre ?? 3);
  }
  if (adminPricingTargetStars) {
    adminPricingTargetStars.value = String(movie.expectedStars ?? 0);
  }
  renderAdminPricingRows(movie.onlinePricingOptions || []);
  adminPricingTargetsModal.classList.remove("hidden");
  adminPricingTargetsModal.setAttribute("aria-hidden", "false");
}

function closeAdminPricingTargetsModal() {
  if (!adminPricingTargetsModal || !adminPricingTargetsMovieId) {
    return;
  }
  adminPricingTargetsModal.classList.add("hidden");
  adminPricingTargetsModal.setAttribute("aria-hidden", "true");
  adminPricingTargetsMovieId.value = "";
  if (adminPricingTheatreStars) {
    adminPricingTheatreStars.value = "3";
  }
  if (adminPricingTargetStars) {
    adminPricingTargetStars.value = "";
  }
  renderAdminPricingRows([]);
}

function legacyRenderAdminUserList() {
  if (!adminUserList) {
    return;
  }

  const searchTerm = adminUserSearchTerm.trim().toLowerCase();
  const filteredUsers = adminUsers.filter((user) => {
    if (!searchTerm) {
      return true;
    }

    return [
      user.name,
      user.email,
      user.role,
      user.status,
    ].some((value) => String(value || "").toLowerCase().includes(searchTerm));
  });

  if (!filteredUsers.length) {
    adminUserList.innerHTML = `<div class="admin-user-empty">No users matched your search.</div>`;
    renderAdminSummaryMetrics();
    return;
  }

  adminUserList.innerHTML = `
    <div class="admin-user-table-head">
      <span>User</span>
      <span>Role</span>
      <span>Status</span>
      <span>Reward Points</span>
      <span>Actions</span>
    </div>
    ${filteredUsers
    .map(
      (user) => `
        <article class="admin-user-row" data-admin-user-id="${user.id}">
          <div class="admin-user-main">
            <strong>${escapeHtml(user.name)}</strong>
            <p>${escapeHtml(user.email)}</p>
          </div>
          <div>
            <span class="admin-user-badge role">${escapeHtml(formatRoleLabel(user.role))}</span>
          </div>
          <div>
            <span class="admin-user-badge status-${escapeHtml(user.status)}">${escapeHtml(user.status)}</span>
          </div>
            <div class="admin-user-points-cell">${escapeHtml(user.points)} pts</div>
          <div class="admin-user-row-actions">
            <button type="button" class="icon-btn" data-admin-user-action="edit" title="Edit user">✎</button>
            <button type="button" class="icon-btn danger" data-admin-user-action="delete" title="Disable user">🗑</button>
          </div>
        </article>
      `
    )
    .join("")}
  `;
  renderAdminSummaryMetrics();
}

function legacyOpenAdminUserEditor(user = null) {
  if (!adminUserEditor) {
    return;
  }

  const isEditing = Boolean(user);
  adminUserEditor.classList.remove("hidden");
  adminUserEditId.value = user?.id || "";
  adminUserName.value = user?.name || "";
  adminUserEmail.value = user?.email || "";
  adminUserPassword.value = "";
  adminUserRole.value = user?.role === "producer" ? "creator" : (user?.role || "viewer");
  adminUserStatus.value = user?.status || "active";
  adminUserPoints.value = String(user?.points ?? 0);
  adminUserName.disabled = isEditing;
  adminUserEmail.disabled = isEditing;
  adminUserPoints.disabled = isEditing;
  adminUserPassword.parentElement?.classList.toggle("hidden", isEditing);
  if (isEditing) {
    adminUserRole.focus();
  } else {
    adminUserName.focus();
  }
}

function legacyCloseAdminUserEditor() {
  if (!adminUserEditor) {
    return;
  }

  adminUserEditor.classList.add("hidden");
  adminUserEditId.value = "";
  adminUserName.value = "";
  adminUserEmail.value = "";
  adminUserPassword.value = "";
  adminUserRole.value = "viewer";
  adminUserStatus.value = "active";
  adminUserPoints.value = "0";
  adminUserName.disabled = false;
  adminUserEmail.disabled = false;
  adminUserPoints.disabled = false;
  adminUserPassword.parentElement?.classList.remove("hidden");
}

async function updateQueueStatusRemote(queueId, status) {
  const response = await apiRequest(`/admin/review-queue/${queueId}/status`, {
    method: "POST",
    body: JSON.stringify({ status }),
  });

  publishQueue = publishQueue.map((item) => (item.id === queueId ? { ...response.item } : item));
  renderPublishQueue();
  await loadAdminSummaryFromApi();
  adminHelper.textContent = response.message;
}

async function updateAdminMovieStageRemote(movieId, stage) {
  const response = await apiRequest(`/admin/movies/${movieId}/stage`, {
    method: "POST",
    body: JSON.stringify({ stage }),
  });

  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadPlatformSummaryFromApi();
  adminHelper.textContent = response.message;
}

async function updateAdminMovieDetailsRemote(movieId, payload) {
  const response = await apiRequest(`/admin/movies/${movieId}/details`, {
    method: "POST",
    body: JSON.stringify({
      title_category: payload.titleCategory,
      title: payload.title,
      title_caption: payload.titleCaption,
      genre: payload.genre,
      cast_credits: payload.castCredits,
      story_line: payload.storyLine,
      release_date: payload.expectedDate || null,
    }),
  });

  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  adminHelper.textContent = response.message;
}

async function updateAdminMoviePricingConfigRemote(movieId, payload) {
  const response = await apiRequest(`/admin/movies/${movieId}/pricing-config`, {
    method: "POST",
    body: JSON.stringify({
      online_pricing_options: payload.onlinePricingOptions.map((item, index) => ({
        quality_code: item.qualityCode,
        quality_label: item.qualityLabel,
        stars_required: item.starsRequired,
        sort_order: Number.isFinite(item.sortOrder) ? item.sortOrder : index,
      })),
      stars_required_theatre: payload.starsRequiredTheatre,
      expected_stars: payload.expectedStars,
    }),
  });

  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  adminHelper.textContent = response.message;
  closeAdminPricingTargetsModal();
}

async function createAdminMovieRemote(payload) {
  const response = await apiRequest("/admin/movies", {
    method: "POST",
    body: JSON.stringify({
      title_category: payload.titleCategory,
      title: payload.title,
      title_caption: payload.titleCaption,
      genre: payload.genre,
      cast_credits: payload.castCredits,
      story_line: payload.storyLine,
      release_date: payload.expectedDate || null,
      stage: payload.stage,
    }),
  });

  const createdMovie = normalizeMovie(response.item);
  adminMovies = [createdMovie, ...adminMovies];
  if (isViewerVisibleStatus(createdMovie.approvalStatus)) {
    movies = [createdMovie, ...movies];
  }
  adminLibraryPage = 1;
  refreshMetrics();
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadPlatformSummaryFromApi();
  await loadAdminSummaryFromApi();
  closeAdminLibraryEditor();
  adminHelper.textContent = response.message;
}

async function updateAdminStarPricingRemote(payload) {
  const response = await apiRequest("/admin/star-pricing", {
    method: "PUT",
    body: JSON.stringify({
      price_inr: payload.priceInr,
      price_usd: payload.priceUsd,
      price_eur: payload.priceEur,
      effective_from: payload.effectiveFrom || null,
    }),
  });

  adminStarPricingState = response;
  applyAdminStarPricing(response);
  await loadAdminSummaryFromApi();
  if (adminStarPricingFeedback) {
    adminStarPricingFeedback.textContent = "Star pricing updated and saved successfully.";
    adminStarPricingFeedback.style.color = "var(--accent-color)";
  }
  adminHelper.textContent = "Star pricing saved for newly created titles.";
}

async function archiveAdminMovieRemote(movieId) {
  const response = await apiRequest(`/admin/movies/${movieId}/archive`, {
    method: "POST",
  });

  closeAdminDeleteDialog();
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  if (!movies.some((movie) => movie.id === selectedMovieId)) {
    selectedMovieId = movies[0]?.id || "";
  }
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadPlatformSummaryFromApi();
  await loadAdminSummaryFromApi();
  adminHelper.textContent = response.message;
}

async function restoreAdminMovieRemote(movieId) {
  const response = await apiRequest(`/admin/movies/${movieId}/restore`, {
    method: "POST",
  });

  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadPlatformSummaryFromApi();
  await loadAdminSummaryFromApi();
  adminHelper.textContent = `${response.message} Super Admin approval remains required before viewer-facing publish.`;
}

async function deleteArchivedAdminMovieRemote(movieId) {
  const response = await apiDeleteRequest(`/admin/movies/${movieId}`);
  closeAdminDeleteDialog();
  removeMovieFromCollections(movieId);
  await Promise.all([
    loadMoviesFromApi(),
    loadAdminMoviesFromApi(),
    loadPlatformSummaryFromApi(),
    loadAdminSummaryFromApi(),
  ]);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  adminHelper.textContent = response.message;
}

async function reviewAdminMovieApprovalRemote(movieId, action = "approve") {
  const response = await apiRequest(`/admin/movies/${movieId}/approval`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });

  closeAdminApprovalReviewModal();
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  await loadPlatformSummaryFromApi();
  await loadAdminSummaryFromApi();
  adminHelper.textContent = response.message;
}

async function updateAdminMovieReleaseMainContentRemote(movieId, payload) {
  const response = await apiRequest(`/admin/movies/${movieId}/release-main-content`, {
    method: "POST",
    body: JSON.stringify({
      release_date_time: payload.releaseDateTime,
      release_passcode: payload.releasePasscode,
    }),
  });

  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  closeAdminReleaseMainContentModal();
  adminHelper.textContent = response.message;
}

async function uploadAdminMoviePostersRemote(movieId, files) {
  const classifiedFiles = await Promise.all(files.map((file) => classifyPosterFile(file)));
  const formData = new FormData();
  classifiedFiles.forEach((item) => {
    formData.append("files", item.file);
    formData.append("orientations", item.orientation);
  });

  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/posters`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  if (adminPosterFiles) {
    adminPosterFiles.value = "";
  }
  if (adminPosterUploadPreview) {
    adminPosterUploadPreview.classList.add("hidden");
    adminPosterUploadPreview.textContent = "";
  }
  await loadAdminMediaAssets(movieId, "posters");
  adminHelper.textContent = `${response.message} Super Admin approval remains required before viewer-facing publish.`;
}

async function uploadAdminMovieTrailerRemote(movieId, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/trailer`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  if (adminTrailerFile) {
    adminTrailerFile.value = "";
  }
  await loadAdminMediaAssets(movieId, "trailer");
  adminHelper.textContent = `${response.message} Super Admin approval remains required before viewer-facing publish.`;
}

async function uploadAdminMovieGalleryRemote(movieId, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/gallery`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  if (adminGalleryFile) {
    adminGalleryFile.value = "";
  }
  await loadAdminMediaAssets(movieId, "gallery");
  adminHelper.textContent = `${response.message} Super Admin approval remains required before viewer-facing publish.`;
}

async function uploadAdminMovieMusicRemote(movieId, file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/music`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  if (adminMusicFile) {
    adminMusicFile.value = "";
  }
  await loadAdminMediaAssets(movieId, "music");
  adminHelper.textContent = `${response.message} Super Admin approval remains required before viewer-facing publish.`;
}

async function uploadAdminMovieContentRemote(movieId, files, password, uploadStartAt) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file);
  });
  formData.append("password", password);
  formData.append("upload_start_at", uploadStartAt || "");

  const response = await apiUploadRequest(`/admin/movies/${movieId}/assets/content`, formData);
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  if (adminContentFiles) {
    adminContentFiles.value = "";
  }
  if (adminContentPassword) {
    adminContentPassword.value = "";
  }
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = "";
  }
  clearAdminContentUploadPreview();
  await loadAdminMediaAssets(movieId, "content");
  adminHelper.textContent = response.message;
}

async function startAdminMovieReserveRemote(movieId) {
  const response = await apiRequest(`/admin/movies/${movieId}/reserve-start`, {
    method: "POST",
  });

  closeAdminDeleteDialog();
  const updatedMovie = normalizeMovie(response.item);
  updateMovieCollections(updatedMovie);
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  renderMovieGrid();
  syncDetailPanel();
  adminHelper.textContent = response.message;
}

async function deleteAdminMediaAssetRemote(movieId, kind, assetName) {
  const response = await apiDeleteRequest(`/admin/movies/${movieId}/assets/${kind}/${encodeURIComponent(assetName)}`);
  await loadAdminMediaAssets(movieId, kind);
  adminHelper.textContent = response.message;
}

async function deleteAdminContentFolderRemote(movieId) {
  const response = await apiDeleteRequest(`/admin/movies/${movieId}/assets/content-folder`);
  await Promise.all([
    loadMoviesFromApi(),
    loadAdminMoviesFromApi(),
  ]);
  await loadAdminContentQualityAssets(movieId);
  if (adminContentUploadStartAt) {
    adminContentUploadStartAt.value = "";
    adminContentUploadStartAt.disabled = true;
  }
  renderMovieGrid();
  syncDetailPanel();
  renderAdminMovieList();
  renderAdminArchiveMovieList();
  adminHelper.textContent = response.message;
}

async function legacyUpdateAdminUserRemote(userId, role, status) {
  const response = await apiRequest(`/admin/users/${userId}`, {
    method: "POST",
    body: JSON.stringify({ role, status }),
  });

  adminUsers = adminUsers.map((user) => (user.id === userId ? { ...response.item } : user));
  renderAdminUserList();
  adminHelper.textContent = response.message;
}

async function legacyCreateAdminUserRemote(payload) {
  const response = await apiRequest("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  adminUsers = [response.item, ...adminUsers];
  renderAdminUserList();
  renderSuperAdminPanel();
  closeAdminUserEditor();
  adminHelper.textContent = response.message;
}

async function legacyDeleteAdminUserRemote(userId) {
  const response = await apiRequest(`/admin/users/${userId}`, {
    method: "DELETE",
  });

  closeAdminDeleteDialog();
  await loadAdminUsersFromApi();
  renderAdminUserList();
  renderSuperAdminPanel();
  adminHelper.textContent = response.message;
}

function setStatus(message, isError = false) {
  if (!statusText) {
    return;
  }
  statusText.textContent = message;
  statusText.style.color = isError ? "#ffd5d5" : "";
}

function setMetadata(value = "") {
  if (!metadataPanel) {
    return;
  }
  metadataPanel.textContent = value;
}

function setLiveState(isLive) {
  if (!liveBadge) {
    return;
  }
  liveBadge.textContent = isLive ? "LIVE" : "OFFLINE";
  liveBadge.style.background = isLive ? "rgba(126, 215, 178, 0.18)" : "rgba(255, 255, 255, 0.08)";
  liveBadge.style.color = isLive ? "#dcfff0" : "#f6f1db";
}

function resetVideoSource() {
  if (!video) {
    return;
  }
  video.pause();
  video.removeAttribute("src");
  video.load();

  if (activeObjectUrl) {
    URL.revokeObjectURL(activeObjectUrl);
    activeObjectUrl = null;
  }

  activeMediaSource = null;
}

function destroyCurrentStream() {
  if (hlsInstance) {
    hlsInstance.destroy();
    hlsInstance = null;
  }

  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
  }

  if (activeReader) {
    activeReader.cancel();
    activeReader = null;
  }

  stopped = true;
  resetVideoSource();
  setLiveState(false);
}

async function startPlayback() {
  if (!video) {
    return;
  }
  try {
    await video.play();
    setLiveState(true);
  } catch {
    setStatus("Screening media is ready. Press play if the browser blocked autoplay.");
    setLiveState(true);
  }
}

function setMode(mode) {
  if (!modeTabs.length || !modePanels.length) {
    return;
  }
  modeTabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.mode === mode);
  });

  modePanels.forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.panel === mode);
  });

  setMetadata("");
  setStatus(
    mode === "stream"
      ? "Enter a live stream URL to begin screening."
      : "Choose a VCNR file or URL, enter its passcode, and unlock playback."
  );
}

function basename(value) {
  try {
    const url = new URL(value, window.location.href);
    const parts = url.pathname.split("/");
    return decodeURIComponent(parts[parts.length - 1] || "sample.vcnr");
  } catch {
    return "sample.vcnr";
  }
}

function showSample(url) {
  if (!sampleLabel || !sampleBox) {
    return;
  }
  sampleUrl = new URL(url, window.location.href).href;
  sampleLabel.textContent = `Load ${basename(sampleUrl)} from this hosted player.`;
  sampleBox.classList.remove("hidden");
}

function loadSampleFile() {
  if (!sampleUrl || !vcnrFileInput || !vcnrUrlInput) {
    return;
  }

  vcnrFileInput.value = "";
  vcnrUrlInput.value = sampleUrl;
  setStatus(`Sample file loaded: ${basename(sampleUrl)}. Enter the passcode and press Unlock And Play.`);
}

function prefillSharedUrl() {
  if (!vcnrUrlInput) {
    return;
  }
  const pageUrl = new URL(window.location.href);
  let sharedUrl = pageUrl.searchParams.get("url");

  if (!sharedUrl && pageUrl.hash.startsWith("#url=")) {
    sharedUrl = decodeURIComponent(pageUrl.hash.slice(5));
  }

  if (sharedUrl && !vcnrUrlInput.value.trim()) {
    vcnrUrlInput.value = sharedUrl;
    setStatus("Shared VCNR URL loaded. Enter the passcode and press Unlock And Play.");
  }
}

async function probeSampleFile() {
  const pageUrl = new URL(window.location.href);
  const configuredSample = pageUrl.searchParams.get("sample");

  if (configuredSample) {
    showSample(configuredSample);
    return;
  }

  try {
    const response = await fetch(new URL(SAMPLE_CONFIG_PATH, pageUrl).href, {
      cache: "no-store",
    });

    if (!response.ok) {
      return;
    }

    const config = await response.json();
    if (config && typeof config.sample === "string" && config.sample.trim()) {
      showSample(config.sample.trim());
      return;
    }
  } catch {
    // Ignore missing or invalid config files.
  }

  try {
    const defaultSample = new URL("media/sample.vcnr", pageUrl).href;
    const response = await fetch(defaultSample, {
      method: "HEAD",
      cache: "no-store",
    });

    if (response.ok) {
      showSample(defaultSample);
    }
  } catch {
    // Ignore when no hosted sample exists.
  }
}

function loadStream(streamUrl) {
  if (!video) {
    return;
  }
  destroyCurrentStream();
  stopped = false;

  if (!streamUrl) {
    setStatus("Please enter a valid live stream URL.", true);
    return;
  }

  if (window.Hls && window.Hls.isSupported()) {
    hlsInstance = new window.Hls({
      enableWorker: true,
      lowLatencyMode: true,
    });

    hlsInstance.loadSource(streamUrl);
    hlsInstance.attachMedia(video);

    hlsInstance.on(window.Hls.Events.MANIFEST_PARSED, () => {
      setStatus("Live screening stream loaded. Connecting player...");
      startPlayback();
    });

    hlsInstance.on(window.Hls.Events.ERROR, (_, data) => {
      if (data.fatal) {
        setStatus("The stream could not be played. Check the URL or stream availability.", true);
        setLiveState(false);
      }
    });

    return;
  }

  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = streamUrl;
    video.addEventListener(
      "loadedmetadata",
      () => {
        setStatus("Native HLS playback is ready.");
        startPlayback();
      },
      { once: true }
    );
    return;
  }

  setStatus("This browser does not support HLS playback.", true);
}

function u32Pair(first, second) {
  const bytes = new Uint8Array(8);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, first, false);
  view.setUint32(4, second, false);
  return bytes;
}

async function appendBuffer(sourceBuffer, bytes, description) {
  if (stopped) {
    throw new Error("Playback stopped.");
  }

  await new Promise((resolve, reject) => {
    const cleanup = () => {
      sourceBuffer.removeEventListener("updateend", onSuccess);
      sourceBuffer.removeEventListener("error", onFailure);
    };

    const onSuccess = () => {
      cleanup();
      resolve();
    };

    const onFailure = () => {
      cleanup();
      reject(new Error(`Browser rejected the ${description}.`));
    };

    sourceBuffer.addEventListener("updateend", onSuccess, { once: true });
    sourceBuffer.addEventListener("error", onFailure, { once: true });

    try {
      sourceBuffer.appendBuffer(bytes);
    } catch (error) {
      cleanup();
      reject(error);
    }
  });
}

async function openVcnrInput() {
  const file = vcnrFileInput.files?.[0];
  const url = vcnrUrlInput.value.trim();

  if (file) {
    return file.stream();
  }

  if (!url) {
    throw new Error("Choose a VCNR file or enter its URL.");
  }

  activeAbortController = new AbortController();

  let response;
  try {
    response = await fetch(url, {
      signal: activeAbortController.signal,
      cache: "no-store",
      mode: "cors",
    });
  } catch (error) {
    if (error && error.name === "AbortError") {
      throw new Error("Playback stopped.");
    }
    if (window.location.protocol === "https:" && url.toLowerCase().startsWith("http://")) {
      throw new Error("This page uses HTTPS, so the VCNR URL must use HTTPS too.");
    }
    throw new Error("Browser could not download the VCNR URL. Check the address and confirm the file server allows CORS.");
  }

  if (!response.ok || !response.body) {
    throw new Error(`VCNR server returned HTTP ${response.status}.`);
  }

  return response.body;
}

async function createSourceBuffer(mime) {
  if (!("MediaSource" in window)) {
    throw new Error("This browser does not support Media Source playback.");
  }

  if (!MediaSource.isTypeSupported(mime)) {
    throw new Error(`This browser does not support the VCNR codec: ${mime}`);
  }

  const mediaSource = new MediaSource();
  activeMediaSource = mediaSource;
  activeObjectUrl = URL.createObjectURL(mediaSource);
  video.src = activeObjectUrl;

  await new Promise((resolve, reject) => {
    mediaSource.addEventListener("sourceopen", resolve, { once: true });
    mediaSource.addEventListener("error", () => reject(new Error("Media player failed.")), { once: true });
  });

  return mediaSource.addSourceBuffer(mime);
}

async function playMemoryFallback(parts) {
  resetVideoSource();
  const blob = new Blob(parts, { type: "video/mp4" });
  activeObjectUrl = URL.createObjectURL(blob);
  video.src = activeObjectUrl;

  await new Promise((resolve, reject) => {
    const cleanup = () => {
      video.removeEventListener("loadedmetadata", onLoaded);
      video.removeEventListener("error", onFailed);
    };

    const onLoaded = () => {
      cleanup();
      resolve();
    };

    const onFailed = () => {
      cleanup();
      reject(new Error("This browser could not decode the decrypted H.264/AAC video."));
    };

    video.addEventListener("loadedmetadata", onLoaded, { once: true });
    video.addEventListener("error", onFailed, { once: true });
  });

  setStatus("Compatibility mode: decrypted in memory and ready to play.");
  startPlayback();
}

async function playVcnr() {
  destroyCurrentStream();
  stopped = false;

  try {
    if (!passcodeInput.value) {
      throw new Error("Enter the VCNR passcode.");
    }

    setStatus("Opening VCNR stream...");
    activeReader = new ExactReader(await openVcnrInput());

    const magic = await activeReader.readExact(8);
    if (!magic.every((value, index) => value === MAGIC[index])) {
      throw new Error("This is not a browser-compatible VCNR v3 file.");
    }

    const version = await activeReader.uint32();
    const headerLength = await activeReader.uint32();
    if (version !== VERSION || headerLength > MAX_HEADER) {
      throw new Error("Unsupported or damaged VCNR file.");
    }

    const salt = await activeReader.readExact(16);
    const headerBytes = await activeReader.readExact(headerLength);
    const header = JSON.parse(new TextDecoder().decode(headerBytes));
    setMetadata(JSON.stringify(header, null, 2));

    setStatus("Deriving encryption key...");
    const keyMaterial = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(passcodeInput.value),
      "PBKDF2",
      false,
      ["deriveKey"]
    );

    const key = await crypto.subtle.deriveKey(
      {
        name: "PBKDF2",
        hash: "SHA-256",
        salt,
        iterations: header.kdf_iterations,
      },
      keyMaterial,
      { name: "AES-GCM", length: 256 },
      false,
      ["decrypt"]
    );

    const headerHash = new Uint8Array(await crypto.subtle.digest("SHA-256", headerBytes));
    const mp4Assembler = new FragmentedMp4Assembler();
    let sourceBuffer = null;
    let memoryFallback = [];
    let mseDisabled = false;
    let mediaAppended = false;
    let expectedId = 0;

    while (!stopped) {
      const chunkId = await activeReader.uint32();
      if (chunkId === END_MARKER) {
        break;
      }

      const plainLength = await activeReader.uint32();
      const nonce = await activeReader.readExact(12);
      const cipherLength = await activeReader.uint32();

      if (
        chunkId !== expectedId ||
        plainLength > 1024 * 1024 ||
        cipherLength !== plainLength + 16 ||
        cipherLength > MAX_CIPHER
      ) {
        throw new Error("Invalid or missing VCNR media chunk.");
      }

      const cipher = await activeReader.readExact(cipherLength);
      const aad = joinBytes(headerHash, u32Pair(VERSION, chunkId));

      let plain;
      try {
        plain = new Uint8Array(
          await crypto.subtle.decrypt(
            { name: "AES-GCM", iv: nonce, additionalData: aad, tagLength: 128 },
            key,
            cipher
          )
        );
      } catch {
        throw new Error("Wrong passcode or damaged VCNR file.");
      }

      if (memoryFallback) {
        memoryFallback.push(plain);
      }

      if (mseDisabled) {
        expectedId += 1;
        setStatus(`Compatibility mode: decrypting chunk ${expectedId}/${header.chunk_count}...`);
        continue;
      }

      const segments = mp4Assembler.push(plain);

      for (const segment of segments) {
        if (!sourceBuffer) {
          const mime = mimeFromInitializationSegment(segment);
          setStatus(`Opening browser decoder: ${mime}`);
          try {
            sourceBuffer = await createSourceBuffer(mime);
            await appendBuffer(sourceBuffer, segment, "MP4 initialization segment");
            memoryFallback = null;
          } catch {
            mseDisabled = true;
            sourceBuffer = null;
            resetVideoSource();
            setStatus("Media Source initialization was rejected. Switching to compatibility mode...");
            break;
          }
          continue;
        }

        await appendBuffer(sourceBuffer, segment, `MP4 media fragment ${mp4Assembler.fragmentCount}`);
        if (!mediaAppended) {
          mediaAppended = true;
          setStatus("Passcode accepted. Streaming video...");
          startPlayback();
        }
      }

      expectedId += 1;
      setStatus(`Streaming encrypted chunk ${expectedId}/${header.chunk_count}...`);
    }

    if (!stopped && expectedId !== header.chunk_count) {
      throw new Error("VCNR stream ended before all chunks arrived.");
    }

    if (mseDisabled) {
      await playMemoryFallback(memoryFallback);
    } else {
      const finalSegments = mp4Assembler.push(new Uint8Array(0), true);
      for (const segment of finalSegments) {
        if (!sourceBuffer) {
          const mime = mimeFromInitializationSegment(segment);
          sourceBuffer = await createSourceBuffer(mime);
          await appendBuffer(sourceBuffer, segment, "MP4 initialization segment");
        } else {
          await appendBuffer(sourceBuffer, segment, "final MP4 media fragment");
        }
      }

      if (!stopped && !mp4Assembler.fragmentCount) {
        throw new Error("VCNR contains no playable fragmented MP4 media.");
      }

      if (!stopped && activeMediaSource?.readyState === "open") {
        activeMediaSource.endOfStream();
        setStatus("Video fully buffered.");
      }
    }
  } finally {
    activeAbortController = null;
    activeReader = null;
  }
}

navViewTriggers.forEach((trigger) => {
  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    const nextView = trigger.dataset.navView;
    if (nextView) {
      if (nextView === "account") {
        if (!viewerSessionProfile) {
          setView("auth");
          return;
        }
        activeAccountEntry = trigger.dataset.accountPanelTarget === "movies" ? "collection" : "account";
        renderAccountView();
        setAccountPanel(trigger.dataset.accountPanelTarget || "profile");
        setView("account");
        return;
      }
      setView(nextView);
    }
  });
});

if (authForm) {
  authForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!authEmail.value.trim() || !authPassword.value.trim()) {
      setAuthMessage("Enter both email and password to continue.", true);
      return;
    }

    try {
      const response = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: authEmail.value.trim(),
          password: authPassword.value.trim(),
        }),
      });
      saveSessionToken(response.token);
      await loadViewerSessionFromApi();
      setAuthMessage(response.message);
      if (entryMode === "admin" && response.next_view !== "admin") {
        clearSessionToken();
        setAuthMessage("This portal is only for admin and super admin accounts.", true);
        return;
      }
      if (entryMode === "creator" && !["producer", "viewer"].includes(response.next_view)) {
        clearSessionToken();
        setAuthMessage("This portal is only for creator accounts.", true);
        return;
      }
      setView(response.next_view === "producer" ? "viewer" : response.next_view);
      if (response.next_view === "admin") {
        setAdminSession(response.role, authEmail.value.trim());
        setAdminPanel(response.role === "super_admin" ? "super-admin" : "users");
        await Promise.all([
          loadAdminSummaryFromApi(),
          loadAdminStarPricingFromApi(),
          loadAdminMoviesFromApi(),
          loadAdminUsersFromApi(),
          loadAdminTaxonomiesFromApi(),
        ]);
        renderAdminMovieList();
        renderAdminArchiveMovieList();
        renderAdminUserList();
        renderSuperAdminPanel();
      } else {
        setAdminSession("", "");
      }
    } catch (error) {
      setAuthMessage(error.message, true);
    }
  });
}

if (signupForm) {
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!signupName.value.trim() || !signupEmail.value.trim() || !signupPassword.value.trim() || !signupConfirmPassword.value.trim()) {
      setSignupMessage("Complete all sign-up fields to continue.", true);
      return;
    }

    if (signupPassword.value !== signupConfirmPassword.value) {
      setSignupMessage("Password and confirm password must match.", true);
      return;
    }

    try {
      const response = await apiRequest("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          name: signupName.value.trim(),
          email: signupEmail.value.trim(),
          password: signupPassword.value.trim(),
        }),
      });

      saveSessionToken(response.token);
      await loadViewerSessionFromApi();
      authEmail.value = signupEmail.value.trim();
      authPassword.value = signupPassword.value.trim();
      setSignupMessage(response.message);
      closeSignupFlow();
      setView("viewer");
    } catch (error) {
      setSignupMessage(error.message, true);
    }
  });
}

if (openSignupButton) {
  openSignupButton.addEventListener("click", () => {
    openSignupFlow();
  });
}

if (closeSignupButton) {
  closeSignupButton.addEventListener("click", () => {
    closeSignupFlow();
  });
}

if (guestEntryButton) {
  guestEntryButton.addEventListener("click", () => {
    clearSessionToken();
    closeSignupFlow();
    setView("viewer");
  });
}

if (viewerAccountButton) {
  viewerAccountButton.addEventListener("click", () => {
    if (!viewerSessionProfile) {
      setView("auth");
      return;
    }
    activeAccountEntry = "account";
    renderAccountView();
    setAccountPanel("profile");
    setView("account");
  });
}

if (accountBackButton) {
  accountBackButton.addEventListener("click", () => {
    setView("viewer");
  });
}

accountPanelTriggers.forEach((trigger) => {
  trigger.addEventListener("click", () => {
    setAccountPanel(trigger.dataset.accountPanelTarget);
  });
});

if (accountCopyReferralButton) {
  accountCopyReferralButton.addEventListener("click", async () => {
    const referralCode = accountReferralCode?.textContent?.trim() || "";
    if (!referralCode) {
      return;
    }
    try {
      await navigator.clipboard.writeText(referralCode);
      if (accountCopyReferralButton) {
        accountCopyReferralButton.textContent = "Copied";
        window.setTimeout(() => {
          accountCopyReferralButton.textContent = "Copy";
        }, 1500);
      }
    } catch {
      // ignore clipboard failures for now
    }
  });
}

if (viewerAccountSignoutButton) {
  viewerAccountSignoutButton.addEventListener("click", handleViewerSignout);
}

function handleAdminSignout() {
  clearSessionToken();
  closeViewerDetailPage({ syncHash: false });
  closeViewerAssetModal();
  closeSignupFlow();
  setAdminSession("", "");
  setView("auth");
}

if (adminSignoutButton) {
  adminSignoutButton.addEventListener("click", handleAdminSignout);
}

if (adminSignoutSidebarButton) {
  adminSignoutSidebarButton.addEventListener("click", handleAdminSignout);
}

if (adminHeaderSignoutButton) {
  adminHeaderSignoutButton.addEventListener("click", handleAdminSignout);
}

stageTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    setStage(tab.dataset.stage);
  });
});

stripStageLinks.forEach((tab) => {
  tab.addEventListener("click", () => {
    setView("viewer");
    setStage(tab.dataset.stage);
  });
});

if (movieGrid) {
  movieGrid.addEventListener("click", async (event) => {
    const playButton = event.target.closest("[data-movie-card-play]");
    if (playButton) {
      const movieId = playButton.dataset.movieCardPlay;
      if (movieId) {
        try {
          await openViewerPlayPage(movieId);
        } catch (error) {
          setStatus(error.message, true);
        }
      }
      return;
    }

    const detailsButton = event.target.closest("[data-movie-card-details]");
    if (detailsButton) {
      const movieId = detailsButton.dataset.movieCardDetails;
      if (movieId) {
        try {
          await openViewerDetailPage(movieId);
        } catch (error) {
          setStatus(error.message, true);
        }
      }
      return;
    }

    const reserveButton = event.target.closest("[data-movie-card-reserve]");
    if (reserveButton) {
      const movieId = reserveButton.dataset.movieCardReserve;
      if (movieId) {
        const movie = movies.find((entry) => entry.id === movieId);
        const buyingNow = isMovieBuyReady(movie);
        if (!viewerSessionProfile) {
          setView("auth");
          setAuthMessage(buyingNow ? "Sign in to buy this title." : "Sign in to reserve this title.", true);
          return;
        }
        if (!movie || (!movie.reserveEnabled && !buyingNow)) {
          return;
        }
        if (movie.viewerReservationStatus === "blocked" || movie.viewerReservationStatus === "fulfilled") {
          setStatus(`"${movie.title}" is already in your account.`, true);
          return;
        }
        selectMovie(movieId);
        openViewerReserveModal(movieId);
      }
      return;
    }

    const wishButton = event.target.closest("[data-movie-card-wish]");
    if (wishButton) {
      const movieId = wishButton.dataset.movieCardWish;
      if (movieId) {
        const movie = movies.find((entry) => entry.id === movieId);
        if (!viewerSessionProfile) {
          setView("auth");
          setAuthMessage("Sign in to add titles to your wishlist.", true);
          return;
        }
        if (!isMovieWished(movie)) {
          selectMovie(movieId);
          openViewerWishModal(movieId);
        }
      }
      return;
    }

    const card = event.target.closest("[data-movie-id]");
    if (!card) {
      return;
    }

    try {
      await openViewerDetailPage(card.dataset.movieId);
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

document.querySelectorAll("[data-viewer-asset-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeViewerAssetModal();
  });
});

document.querySelectorAll("[data-viewer-wish-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeViewerWishModal();
  });
});

document.querySelectorAll("[data-viewer-reserve-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeViewerReserveModal();
  });
});

if (viewerAssetModalBody) {
  viewerAssetModalBody.addEventListener("click", (event) => {
    const contentActionButton = event.target.closest("[data-viewer-content-action]");
    if (contentActionButton) {
      const movie = viewerDetailState.item;
      if (!movie) {
        return;
      }

      const action = contentActionButton.dataset.viewerContentAction || "";
      Promise.resolve()
        .then(async () => {
          if (action === "play") {
            const storedSource = await resolveStoredLocalContentSource(movie.id);
            if (storedSource) {
              await playMovieFromLocalContent(movie, storedSource);
              return;
            }
            const chosenSource = await chooseLocalContentSource(movie.id);
            await playMovieFromLocalContent(movie, chosenSource);
            return;
          }

          if (action === "link") {
            const chosenSource = await chooseLocalContentSource(movie.id);
            await playMovieFromLocalContent(movie, chosenSource);
            return;
          }

          if (action === "files") {
            const chosenFiles = await promptLocalContentFiles();
            await playMovieFromLocalContent(movie, { kind: "files", value: chosenFiles, persisted: false });
          }
        })
        .catch((error) => {
          renderViewerContentModalBody(movie, error.message || "Local playback could not be started.");
        });
      return;
    }

    const navButton = event.target.closest("[data-viewer-carousel-nav]");
    if (navButton) {
      viewerAssetCarouselState.index += navButton.dataset.viewerCarouselNav === "next" ? 1 : -1;
      renderViewerAssetCarousel();
      return;
    }

    const dotButton = event.target.closest("[data-viewer-carousel-index]");
    if (dotButton) {
      viewerAssetCarouselState.index = Number(dotButton.dataset.viewerCarouselIndex || 0);
      renderViewerAssetCarousel();
    }
  });
}

if (viewerTitleBackButton) {
  viewerTitleBackButton.addEventListener("click", () => {
    closeViewerDetailPage();
  });
}

window.addEventListener("hashchange", async () => {
  const movieId = getMovieIdFromHash();
  if (!movieId) {
    closeViewerDetailPage({ syncHash: false });
    return;
  }

  try {
    await openViewerDetailPage(movieId, { syncHash: false });
  } catch (error) {
    setStatus(error.message, true);
    closeViewerDetailPage({ syncHash: false });
  }
});

if (detailWishButton) {
  detailWishButton.addEventListener("click", async () => {
    const movie = getSelectedMovie();
    if (!movie) {
      return;
    }
    if (!viewerSessionProfile) {
      setView("auth");
      setAuthMessage("Sign in to add titles to your wishlist.", true);
      return;
    }
    if (!isMovieWished(movie)) {
      openViewerWishModal(movie.id);
    }
  });
}

if (detailReserveButton) {
  detailReserveButton.addEventListener("click", async () => {
    const selectedMovie = getSelectedMovie();
    if (!selectedMovie) {
      setStatus("No title is available yet.", true);
      return;
    }
    const buyingNow = isMovieBuyReady(selectedMovie);
    if (!viewerSessionProfile) {
      setView("auth");
      setAuthMessage(buyingNow ? "Sign in to buy this title." : "Sign in to reserve this title.", true);
      return;
    }
    if (!selectedMovie.reserveEnabled && !buyingNow) {
      setStatus("This title is not open for reserve or purchase yet.", true);
      return;
    }
    if (selectedMovie.viewerReservationStatus === "blocked" || selectedMovie.viewerReservationStatus === "fulfilled") {
      setStatus(`"${selectedMovie.title}" is already in your account.`, true);
      return;
    }
    openViewerReserveModal(selectedMovie.id);
  });
}

if (detailPostersButton) {
  detailPostersButton.addEventListener("click", () => {
    openViewerAssetModal("posters");
  });
}

if (detailTrailersButton) {
  detailTrailersButton.addEventListener("click", () => {
    openViewerAssetModal("trailers");
  });
}

if (detailGalleryButton) {
  detailGalleryButton.addEventListener("click", () => {
    openViewerAssetModal("gallery");
  });
}

if (viewerWishModal) {
  viewerWishModal.addEventListener("click", async (event) => {
    const choiceButton = event.target.closest("[data-viewer-wish-mode]");
    if (!choiceButton || !activeWishMovieId) {
      return;
    }
    try {
      await submitMovieInterest(activeWishMovieId, "wish", choiceButton.dataset.viewerWishMode || "");
      closeViewerWishModal();
    } catch (error) {
      setStatus(error.message, true);
      if (error.message === "Sign in is required.") {
        setView("auth");
        setAuthMessage("Sign in to add titles to your wishlist.", true);
      }
    }
  });
}

if (viewerReserveConfirmButton) {
  viewerReserveConfirmButton.addEventListener("click", async () => {
    if (!activeReserveMovieId) {
      return;
    }
    try {
      const purchasedMovie = await submitMovieInterest(activeReserveMovieId, activeReserveAction === "buy" ? "buy" : "reserve");
      closeViewerReserveModal();
      if (activeReserveAction === "buy" && purchasedMovie) {
        try {
          await downloadMovieContentPackage(
            purchasedMovie.id,
            `${purchasedMovie.title || "title"}-content.zip`
          );
        } catch (error) {
          setStatus(error.message || "Purchase succeeded, but the download could not be started automatically.", true);
        }
      }
    } catch (error) {
      setStatus(error.message, true);
      if (error.message === "Sign in is required.") {
        closeViewerReserveModal();
        setView("auth");
        setAuthMessage(activeReserveAction === "buy" ? "Sign in to buy this title." : "Sign in to reserve this title.", true);
      }
    }
  });
}

if (detailMusicButton) {
  detailMusicButton.addEventListener("click", () => {
    openViewerAssetModal("music");
  });
}

if (detailContentButton) {
  detailContentButton.addEventListener("click", async () => {
    try {
      await openViewerContentPlayback(viewerDetailState.item);
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

if (detailWatchNowButton) {
  detailWatchNowButton.addEventListener("click", async () => {
    try {
      await openViewerContentPlayback(viewerDetailState.item);
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

if (detailPosterPlayButton) {
  detailPosterPlayButton.addEventListener("click", async () => {
    try {
      await openViewerContentPlayback(viewerDetailState.item);
    } catch (error) {
      setStatus(error.message, true);
    }
  });
}

if (detailDownloadAction) {
  detailDownloadAction.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-download-movie-id]");
    if (!button) {
      return;
    }

    const movieId = button.dataset.downloadMovieId || "";
    const suggestedName = button.dataset.downloadFilename || "title-content.zip";
    button.disabled = true;
    const previousLabel = button.textContent;
    button.textContent = "Preparing...";
    try {
      await downloadMovieContentPackage(movieId, suggestedName);
    } catch (error) {
      setStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = previousLabel;
    }
  });
}

if (adminOpenViewer) {
  adminOpenViewer.addEventListener("click", () => {
    window.location.href = "/";
  });
}

if (adminArchiveNavLink) {
  adminArchiveNavLink.addEventListener("click", () => {
    setAdminPanel("library");
    adminArchiveSection?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

adminPanelTriggers.forEach((trigger) => {
  trigger.addEventListener("click", () => {
    setAdminPanel(trigger.dataset.adminPanelTarget);
  });
});

if (adminReviewList) {
  adminReviewList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-queue-status]");
    const card = event.target.closest("[data-queue-id]");
    if (!button || !card) {
      return;
    }

    try {
      await updateQueueStatusRemote(card.dataset.queueId, button.dataset.queueStatus);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (superAdminTaxonomyGrid) {
  superAdminTaxonomyGrid.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-taxonomy-edit-kind]");
    if (editButton) {
      fillTaxonomyForm(editButton.dataset.taxonomyEditKind, editButton.dataset.taxonomyEditId);
      return;
    }

    const clearButton = event.target.closest("[data-taxonomy-clear]");
    if (clearButton) {
      clearTaxonomyForm(clearButton.dataset.taxonomyClear);
    }
  });

  superAdminTaxonomyGrid.addEventListener("input", (event) => {
    const nameInput = event.target.closest("[data-taxonomy-name]");
    if (!nameInput) {
      return;
    }
    const form = nameInput.closest("[data-taxonomy-form]");
    if (!form) {
      return;
    }
    const slugField = form.querySelector("[data-taxonomy-slug]");
    if (slugField && !slugField.value.trim()) {
      slugField.value = slugifyValue(nameInput.value);
    }
  });

  superAdminTaxonomyGrid.addEventListener("submit", async (event) => {
    const formElement = event.target.closest("[data-taxonomy-form]");
    if (!formElement) {
      return;
    }
    event.preventDefault();
    const kind = formElement.dataset.taxonomyForm;

    try {
      await saveTaxonomyRemote(kind, formElement);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (form && streamUrlInput) {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    loadStream(streamUrlInput.value.trim());
  });
}

if (modeTabs.length) {
  modeTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      setMode(tab.dataset.mode);
    });
  });
}

if (loadDemoButton && streamUrlInput) {
  loadDemoButton.addEventListener("click", () => {
    streamUrlInput.value = DEMO_STREAM_URL;
    loadStream(DEMO_STREAM_URL);
  });
}

if (sampleLoadButton) {
  sampleLoadButton.addEventListener("click", loadSampleFile);
}

if (playVcnrButton) {
  playVcnrButton.addEventListener("click", async () => {
    try {
      await playVcnr();
    } catch (error) {
      if (!stopped) {
        setStatus(error.message || "VCNR playback failed.", true);
      }
    }
  });
}

if (stopButton) {
  stopButton.addEventListener("click", () => {
    destroyCurrentStream();
    resetVideoSource();
    setStatus("Playback stopped. Enter another source to start again.");
  });
}

if (video) {
  video.addEventListener("waiting", () => {
    if (liveBadge?.textContent === "LIVE") {
      setStatus("Buffering playback...");
    }
  });

  video.addEventListener("playing", () => {
    if (liveBadge?.textContent === "LIVE") {
      setStatus("Playback is live.");
    }
  });
}

function renderAdminUserList() {
  if (!adminUserList) {
    return;
  }

  const { filteredUsers, pagedUsers, totalPages, startIndex } = getProcessedAdminUsers();

  if (!filteredUsers.length) {
    adminUserList.innerHTML = `<div class="admin-user-empty">No users matched your search.</div>`;
    renderAdminSummaryMetrics();
    return;
  }

  adminUserList.innerHTML = `
    <div class="admin-user-table-head">
      <span>User</span>
      <span>Role</span>
      <span>Status</span>
      <span>Star Balance</span>
      <span>Disc Balance</span>
      <span>Actions</span>
    </div>
    ${pagedUsers.map((user) => `
      <article class="admin-user-row" data-admin-user-id="${user.id}">
        <div class="admin-user-main">
          <strong>${escapeHtml(user.name)}</strong>
          <p>${escapeHtml(user.email)}</p>
        </div>
        <div>
          <span class="admin-user-badge role">${escapeHtml(formatRoleLabel(user.role))}</span>
        </div>
        <div>
          <span class="admin-user-badge status-${escapeHtml(user.status)}">${escapeHtml(user.status)}</span>
        </div>
        <div class="admin-user-balance-cell"><span>${escapeHtml(user.star_balance ?? 0)}</span><span class="admin-balance-icon is-star">&#9733;</span></div>
        <div class="admin-user-balance-cell"><span>${escapeHtml(user.disc_balance ?? 0)}</span><span class="admin-balance-icon is-disc">&#9678;</span></div>
        <div class="admin-user-row-actions">
          <button type="button" class="icon-btn" data-admin-user-action="edit" title="Edit user" aria-label="Edit user">&#9998;</button>
          <button type="button" class="icon-btn danger" data-admin-user-action="delete" title="Disable user" aria-label="Disable user" ${user.role === "super_admin" ? "disabled" : ""}>&#128465;</button>
        </div>
      </article>
    `).join("")}
    <div class="admin-table-footer">
      <p class="admin-table-footnote">Showing ${startIndex + 1}-${startIndex + pagedUsers.length} of ${filteredUsers.length} users</p>
      <div class="admin-pagination">
        <button type="button" class="ghost-btn" data-admin-page="prev" ${adminUserPage <= 1 ? "disabled" : ""}>Previous</button>
        <span class="admin-page-indicator">Page ${adminUserPage} of ${totalPages}</span>
        <button type="button" class="ghost-btn" data-admin-page="next" ${adminUserPage >= totalPages ? "disabled" : ""}>Next</button>
      </div>
    </div>
  `;
  renderAdminSummaryMetrics();
}

function openAdminUserEditor(user = null) {
  if (!adminUserEditor || !adminUserModal) {
    return;
  }

  const isEditing = Boolean(user);
  adminUserModal.classList.remove("hidden");
  adminUserModal.setAttribute("aria-hidden", "false");
  adminUserEditId.value = user?.id || "";
  adminUserName.value = user?.name || "";
  adminUserEmail.value = user?.email || "";
  adminUserPassword.value = "";
  adminUserRole.value = user?.role === "producer" ? "creator" : (user?.role || "viewer");
  adminUserStatus.value = user?.status || "active";
  adminUserPoints.value = String(user?.star_balance ?? 0);
  adminUserName.disabled = false;
  adminUserEmail.disabled = isEditing;
  adminUserPoints.disabled = false;
  if (adminUserModalTitle) {
    adminUserModalTitle.textContent = isEditing ? "Edit User Access" : "Add New User";
  }
  setAdminUserModalMessage(
    isEditing
      ? "Update the user's name, role, status, and current star balance."
      : "Create a new platform account with a role, status, and starting star balance."
  );
  clearAdminUserEmailError();
  adminUserPasswordField?.classList.toggle("hidden", isEditing);
  if (isEditing) {
    adminUserRole.focus();
  } else {
    adminUserName.focus();
  }
}

function closeAdminUserEditor() {
  if (!adminUserEditor || !adminUserModal) {
    return;
  }

  adminUserModal.classList.add("hidden");
  adminUserModal.setAttribute("aria-hidden", "true");
  adminUserEditId.value = "";
  adminUserName.value = "";
  adminUserEmail.value = "";
  adminUserPassword.value = "";
  adminUserRole.value = "viewer";
  adminUserStatus.value = "active";
  adminUserPoints.value = "0";
  adminUserName.disabled = false;
  adminUserEmail.disabled = false;
  adminUserPoints.disabled = false;
  clearAdminUserEmailError();
  setAdminUserModalMessage("Create a new platform account with a role, status, and starting star balance.");
  adminUserPasswordField?.classList.remove("hidden");
}

function openAdminDeleteDialog(user) {
  if (!adminDeleteDialog || !user) {
    return;
  }

  adminPendingDelete = {
    kind: "user",
    id: user.id,
  };
  if (adminDeleteCopy) {
    adminDeleteCopy.textContent = `Delete ${user.name} (${user.email}) permanently? This will remove the account, wallet balances, reservations, and related profile access from the platform.`;
  }
  if (adminDeleteKicker) {
    adminDeleteKicker.textContent = "Delete User";
  }
  if (adminDeleteTitle) {
    adminDeleteTitle.textContent = "Confirm user deletion";
  }
  if (adminDeleteConfirmButton) {
    adminDeleteConfirmButton.textContent = "Delete Permanently";
  }
  adminDeleteDialog.style.removeProperty("display");
  adminDeleteDialog.classList.remove("hidden");
  adminDeleteDialog.setAttribute("aria-hidden", "false");
}

function openAdminMovieArchiveDialog(movie) {
  if (!adminDeleteDialog || !movie) {
    return;
  }

  adminPendingDelete = {
    kind: "movie",
    id: movie.id,
  };
  if (adminDeleteCopy) {
    adminDeleteCopy.textContent = `Archive "${movie.title}" from the viewer catalog? Any viewers with blocked stars for this title will be refunded first, and then the record will move to Archive for future control and history.`;
  }
  if (adminDeleteKicker) {
    adminDeleteKicker.textContent = "Archive Title";
  }
  if (adminDeleteTitle) {
    adminDeleteTitle.textContent = "Confirm library action";
  }
  if (adminDeleteConfirmButton) {
    adminDeleteConfirmButton.textContent = "Archive Title";
  }
  adminDeleteDialog.style.removeProperty("display");
  adminDeleteDialog.classList.remove("hidden");
  adminDeleteDialog.setAttribute("aria-hidden", "false");
}

function openAdminMovieReserveToggleDialog(movie) {
  if (!adminDeleteDialog || !movie) {
    return;
  }

  const stopping = Boolean(movie.reserveEnabled);
  if (!stopping && !hasOnlinePricingOption(movie)) {
    adminHelper.textContent = "Please add at least one online movie quality with pricing before starting Reserve Now.";
    openAdminPricingTargetsModal(movie);
    return;
  }

  adminPendingDelete = {
    kind: "movie-reserve-toggle",
    id: movie.id,
  };
  if (adminDeleteCopy) {
    adminDeleteCopy.textContent = stopping
      ? `Stop Reserve Now for "${movie.title}"? New viewers will no longer be able to reserve this title, but existing blocked reservations will remain active.`
      : `Start Reserve Now for "${movie.title}"? Viewers with enough stars will be able to reserve this title and block the required stars until release or refund conditions.`;
  }
  if (adminDeleteKicker) {
    adminDeleteKicker.textContent = stopping ? "Stop Reserve Now" : "Start Reserve Now";
  }
  if (adminDeleteTitle) {
    adminDeleteTitle.textContent = "Confirm reserve action";
  }
  if (adminDeleteConfirmButton) {
    adminDeleteConfirmButton.textContent = stopping ? "Stop Reserve Now" : "Start Reserve Now";
  }
  adminDeleteDialog.style.removeProperty("display");
  adminDeleteDialog.classList.remove("hidden");
  adminDeleteDialog.setAttribute("aria-hidden", "false");
}

function openAdminMoviePermanentDeleteDialog(movie) {
  if (!adminDeleteDialog || !movie) {
    return;
  }

  adminPendingDelete = {
    kind: "archived-movie-delete",
    id: movie.id,
  };
  if (adminDeleteCopy) {
    adminDeleteCopy.textContent = `Delete "${movie.title}" permanently? This will remove the archive record and delete its related posters, trailers, music, content files, folders, and linked title data.`;
  }
  if (adminDeleteKicker) {
    adminDeleteKicker.textContent = "Permanent Delete";
  }
  if (adminDeleteTitle) {
    adminDeleteTitle.textContent = "Delete archived title forever";
  }
  if (adminDeleteConfirmButton) {
    adminDeleteConfirmButton.textContent = "Delete Permanently";
  }
  adminDeleteDialog.style.removeProperty("display");
  adminDeleteDialog.classList.remove("hidden");
  adminDeleteDialog.setAttribute("aria-hidden", "false");
}

function closeAdminDeleteDialog() {
  if (!adminDeleteDialog) {
    return;
  }

  adminPendingDelete = null;
  adminDeleteDialog.classList.add("hidden");
  adminDeleteDialog.setAttribute("aria-hidden", "true");
  adminDeleteDialog.style.display = "none";
}

async function updateAdminUserRemote(userId, name, role, status, starBalance) {
  const response = await apiRequest(`/admin/users/${userId}`, {
    method: "POST",
    body: JSON.stringify({ name, role, status, star_balance: starBalance }),
  });

  adminUsers = adminUsers.map((user) => (user.id === userId ? { ...response.item } : user));
  renderAdminUserList();
  renderSuperAdminPanel();
  adminHelper.textContent = response.message;
}

async function createAdminUserRemote(payload) {
  const response = await apiRequest("/admin/users", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      star_balance: payload.star_balance ?? 0,
    }),
  });

  adminUsers = [response.item, ...adminUsers];
  adminUserPage = 1;
  renderAdminUserList();
  renderSuperAdminPanel();
  closeAdminUserEditor();
  adminHelper.textContent = response.message;
}

async function deleteAdminUserRemote(userId) {
  const response = await apiRequest(`/admin/users/${userId}`, {
    method: "DELETE",
  });

  adminUsers = adminUsers.filter((user) => user.id !== userId);
  const optimisticTotalPages = Math.max(1, Math.ceil(adminUsers.length / ADMIN_USERS_PER_PAGE));
  adminUserPage = Math.min(adminUserPage, optimisticTotalPages);
  closeAdminDeleteDialog();
  setAdminPanel("users");
  renderAdminUserList();
  renderSuperAdminPanel();

  await loadAdminUsersFromApi();
  await loadAdminSummaryFromApi();
  const totalPages = Math.max(1, Math.ceil(adminUsers.length / ADMIN_USERS_PER_PAGE));
  adminUserPage = Math.min(adminUserPage, totalPages);
  setAdminPanel("users");
  renderAdminUserList();
  renderSuperAdminPanel();
  adminHelper.textContent = response.message;
}

if (adminUserSearch) {
  adminUserSearch.addEventListener("input", () => {
    adminUserSearchTerm = adminUserSearch.value;
    adminUserPage = 1;
    renderAdminUserList();
  });
}

if (adminUserSort) {
  adminUserSort.addEventListener("change", () => {
    adminUserSortValue = adminUserSort.value;
    adminUserPage = 1;
    renderAdminUserList();
  });
}

if (adminAddUserButton) {
  adminAddUserButton.addEventListener("click", () => {
    openAdminUserEditor();
  });
}

if (adminUserCancelButton) {
  adminUserCancelButton.addEventListener("click", () => {
    closeAdminUserEditor();
  });
}

if (adminUserEmail) {
  adminUserEmail.addEventListener("input", () => {
    clearAdminUserEmailError();
    if (!adminUserEditId.value.trim()) {
      setAdminUserModalMessage("Create a new platform account with a role, status, and starting star balance.");
    }
  });
}

document.querySelectorAll("[data-admin-modal-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminUserEditor();
  });
});

document.querySelectorAll("[data-admin-taxonomy-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminTaxonomyEditor();
  });
});

document.querySelectorAll("[data-admin-library-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminLibraryEditor();
  });
});

document.querySelectorAll("[data-admin-pricing-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminPricingTargetsModal();
  });
});

document.querySelectorAll("[data-admin-release-main-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminReleaseMainContentModal();
  });
});

document.querySelectorAll("[data-admin-approval-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminApprovalReviewModal();
  });
});

document.querySelectorAll("[data-admin-poster-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminPosterUploadModal();
  });
});

document.querySelectorAll("[data-admin-trailer-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminTrailerUploadModal();
  });
});

document.querySelectorAll("[data-admin-gallery-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminGalleryUploadModal();
  });
});

document.querySelectorAll("[data-admin-music-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminMusicUploadModal();
  });
});

document.querySelectorAll("[data-admin-content-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminContentQualityUploadModal();
  });
});

if (adminContentCancelButton) {
  adminContentCancelButton.addEventListener("click", () => {
    closeAdminContentQualityUploadModal();
  });
}

document.querySelectorAll("[data-admin-delete-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminDeleteDialog();
  });
});

if (adminDeleteCancelButton) {
  adminDeleteCancelButton.addEventListener("click", () => {
    closeAdminDeleteDialog();
  });
}

if (adminDeleteConfirmButton) {
  adminDeleteConfirmButton.addEventListener("click", async () => {
    if (!adminPendingDelete?.id) {
      return;
    }

    try {
      if (adminPendingDelete.kind === "movie") {
        await archiveAdminMovieRemote(adminPendingDelete.id);
      } else if (adminPendingDelete.kind === "movie-reserve-toggle") {
        await startAdminMovieReserveRemote(adminPendingDelete.id);
      } else if (adminPendingDelete.kind === "archived-movie-delete") {
        await deleteArchivedAdminMovieRemote(adminPendingDelete.id);
      } else {
        await deleteAdminUserRemote(adminPendingDelete.id);
      }
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminUserEditor) {
  adminUserEditor.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();

    const editId = adminUserEditId.value.trim();
    const name = adminUserName.value.trim();
    const role = adminUserRole.value;
    const status = adminUserStatus.value;
    const starBalance = Number(adminUserPoints.value || 0);

    try {
      if (editId) {
        if (!name) {
          throw new Error("Name is required.");
        }
        await updateAdminUserRemote(editId, name, role, status, starBalance);
        closeAdminUserEditor();
      } else {
        if (!adminUserName.value.trim() || !adminUserEmail.value.trim() || !adminUserPassword.value) {
          throw new Error("Name, email, and password are required for a new user.");
        }
        if (isDuplicateAdminUserEmail(adminUserEmail.value, editId)) {
          flagDuplicateAdminUserEmail();
          throw new Error("This email address already exists.");
        }
        await createAdminUserRemote({
          name: adminUserName.value.trim(),
          email: adminUserEmail.value.trim(),
          password: adminUserPassword.value,
          role,
          status,
          star_balance: starBalance,
        });
      }
    } catch (error) {
      if (String(error.message || "").toLowerCase().includes("already exists")) {
        flagDuplicateAdminUserEmail();
      }
      adminHelper.textContent = error.message;
    }
  }, true);
}

if (adminUserList) {
  adminUserList.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-admin-user-action]");
    const pageButton = event.target.closest("[data-admin-page]");

    if (actionButton || pageButton) {
      event.stopImmediatePropagation();
    }

    if (pageButton) {
      adminUserPage += pageButton.dataset.adminPage === "next" ? 1 : -1;
      renderAdminUserList();
      return;
    }

    const card = event.target.closest("[data-admin-user-id]");
    if (!actionButton || !card) {
      return;
    }

    const userId = card.dataset.adminUserId;
    const selectedUser = adminUsers.find((user) => user.id === userId);

    try {
      if (actionButton.dataset.adminUserAction === "edit" && selectedUser) {
        openAdminUserEditor(selectedUser);
      } else if (actionButton.dataset.adminUserAction === "delete" && selectedUser && selectedUser.role !== "super_admin") {
        openAdminDeleteDialog(selectedUser);
      }
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  }, true);
}

if (adminUserSort) {
  adminUserSort.value = adminUserSortValue;
}

if (adminLibrarySearch) {
  adminLibrarySearch.addEventListener("input", () => {
    adminLibrarySearchTerm = adminLibrarySearch.value;
    adminLibraryPage = 1;
    renderAdminMovieList();
    renderAdminArchiveMovieList();
  });
}

if (adminLibraryStage) {
  adminLibraryStage.addEventListener("change", () => {
    adminLibraryStageFilter = adminLibraryStage.value;
    adminLibraryPage = 1;
    renderAdminMovieList();
    renderAdminArchiveMovieList();
  });
}

if (adminLibrarySort) {
  adminLibrarySort.addEventListener("change", () => {
    adminLibrarySortValue = adminLibrarySort.value;
    adminLibraryPage = 1;
    renderAdminMovieList();
    renderAdminArchiveMovieList();
  });
  adminLibrarySort.value = adminLibrarySortValue;
}

if (adminLibraryStage) {
  adminLibraryStage.value = adminLibraryStageFilter;
}

if (adminLibraryCastCredits) {
  renderAdminCastCreditRows([]);
}

if (adminPricingOnlineRows) {
  renderAdminPricingRows([]);
}

if (adminAddLibraryButton) {
  adminAddLibraryButton.addEventListener("click", () => {
    openAdminLibraryEditor();
  });
}

if (adminStarPricingForm) {
  adminStarPricingForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      if (adminStarPricingFeedback) {
        adminStarPricingFeedback.textContent = "";
      }
      const payload = {
        priceInr: Number(adminStarPriceInr?.value || 50),
        priceUsd: Number(adminStarPriceUsd?.value || 0),
        priceEur: Number(adminStarPriceEur?.value || 0),
        effectiveFrom: adminStarPriceEffectiveFrom?.value || "",
      };
      if (!Number.isFinite(payload.priceInr) || payload.priceInr < 1) {
        throw new Error("1 Star Price - INR must be at least 1.");
      }
      if (!Number.isFinite(payload.priceUsd) || payload.priceUsd < 0) {
        throw new Error("1 Star Price - USD must be zero or higher.");
      }
      if (!Number.isFinite(payload.priceEur) || payload.priceEur < 0) {
        throw new Error("1 Star Price - EUR must be zero or higher.");
      }
      await updateAdminStarPricingRemote(payload);
    } catch (error) {
      if (adminStarPricingFeedback) {
        adminStarPricingFeedback.textContent = error instanceof Error ? error.message : "Unable to save star pricing.";
        adminStarPricingFeedback.style.color = "#ff8f7a";
      }
      adminHelper.textContent = error instanceof Error ? error.message : "Unable to save star pricing.";
    }
  });
}

if (adminLibraryCancelButton) {
  adminLibraryCancelButton.addEventListener("click", () => {
    closeAdminLibraryEditor();
  });
}

if (adminPricingTargetsCancelButton) {
  adminPricingTargetsCancelButton.addEventListener("click", () => {
    closeAdminPricingTargetsModal();
  });
}

if (adminLibraryAddCastCreditButton) {
  adminLibraryAddCastCreditButton.addEventListener("click", () => {
    appendAdminCastCreditRow();
  });
}

if (adminPricingAddOnlineRowButton) {
  adminPricingAddOnlineRowButton.addEventListener("click", () => {
    appendAdminPricingRow();
  });
}

if (adminLibraryCastCredits) {
  adminLibraryCastCredits.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-cast-credit-row]");
    if (!removeButton) {
      return;
    }

    const row = removeButton.closest("[data-cast-credit-row]");
    if (!row) {
      return;
    }

    const currentRows = readAdminCastCreditRows();
    const rowIndex = Number(row.getAttribute("data-cast-credit-row"));
    const nextRows = currentRows.filter((_, index) => index !== rowIndex);
    renderAdminCastCreditRows(nextRows);
  });
}

if (adminPricingOnlineRows) {
  adminPricingOnlineRows.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-pricing-row]");
    if (!removeButton) {
      return;
    }

    const row = removeButton.closest("[data-pricing-row]");
    if (!row) {
      return;
    }

    const currentRows = readAdminPricingRows();
    const rowIndex = Number(row.getAttribute("data-pricing-row"));
    const nextRows = currentRows.filter((_, index) => index !== rowIndex);
    renderAdminPricingRows(nextRows);
  });
}

if (adminReleaseMainContentCancelButton) {
  adminReleaseMainContentCancelButton.addEventListener("click", () => {
    closeAdminReleaseMainContentModal();
  });
}

if (adminApprovalCancelButton) {
  adminApprovalCancelButton.addEventListener("click", () => {
    closeAdminApprovalReviewModal();
  });
}

if (adminApprovalApproveButton) {
  adminApprovalApproveButton.addEventListener("click", async () => {
    const movieId = adminApprovalMovieId?.value.trim();

    try {
      if (!movieId) {
        throw new Error("Approval details are missing.");
      }
      await reviewAdminMovieApprovalRemote(movieId, "approve");
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminPosterCancelButton) {
  adminPosterCancelButton.addEventListener("click", () => {
    closeAdminPosterUploadModal();
  });
}

if (adminTrailerCancelButton) {
  adminTrailerCancelButton.addEventListener("click", () => {
    closeAdminTrailerUploadModal();
  });
}

if (adminGalleryCancelButton) {
  adminGalleryCancelButton.addEventListener("click", () => {
    closeAdminGalleryUploadModal();
  });
}

if (adminMusicCancelButton) {
  adminMusicCancelButton.addEventListener("click", () => {
    closeAdminMusicUploadModal();
  });
}

if (adminLibraryEditor) {
  adminLibraryEditor.addEventListener("submit", async (event) => {
    event.preventDefault();

    const titleCategory = adminLibraryCategory.value.trim();
    const title = adminLibraryTitle.value.trim();
    const titleCaption = adminLibraryCaption.value.trim();
    const genreValues = getSelectedMultiValues(adminLibraryGenre);
    const genre = genreValues.join(", ");
    const castCredits = readAdminCastCreditRows();
    const storyLine = adminLibraryDescription.value.trim();
    const expectedDate = formatAdminDateForApi(adminLibraryExpectedDate.value);
    const stage = adminLibraryMovieStage.value;
    const editId = adminLibraryEditId.value.trim();

    try {
      if (!titleCategory || !title || !genre || !storyLine) {
        throw new Error("Title category, title name, genre, and story line are required.");
      }

      for (const item of castCredits) {
        if (!item.role || !item.name) {
          throw new Error("Each cast row needs both a role and a name.");
        }
        if (item.link && !/^https?:\/\//i.test(item.link)) {
          throw new Error(`Link for "${item.name}" must start with http:// or https://.`);
        }
      }

      if (editId) {
        const existingMovie = adminMovies.find((movie) => movie.id === editId);
        await updateAdminMovieDetailsRemote(editId, {
          titleCategory,
          title,
          titleCaption,
          genre,
          castCredits,
          storyLine,
          expectedDate,
        });
        if (existingMovie && existingMovie.stage !== stage) {
          await updateAdminMovieStageRemote(editId, stage);
        }
        closeAdminLibraryEditor();
      } else {
        await createAdminMovieRemote({
          titleCategory,
          title,
          titleCaption,
          genre,
          castCredits,
          storyLine,
          expectedDate,
          stage,
        });
      }
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminPricingTargetsForm) {
  adminPricingTargetsForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminPricingTargetsMovieId?.value.trim() || "";
    const onlinePricingOptions = readAdminPricingRows();
    const starsRequiredTheatre = Number(adminPricingTheatreStars?.value || 0);
    const expectedStars = Number(adminPricingTargetStars?.value || 0);

    try {
      if (!movieId) {
        throw new Error("Choose a title before saving pricing.");
      }
      if (!onlinePricingOptions.length) {
        throw new Error("Add at least one online quality row.");
      }

      const seenQualities = new Set();
      for (const item of onlinePricingOptions) {
        if (!item.qualityCode) {
          throw new Error("Choose a quality for every online row.");
        }
        if (seenQualities.has(item.qualityCode)) {
          throw new Error("Each online quality can be used only once.");
        }
        seenQualities.add(item.qualityCode);
        if (!Number.isFinite(item.starsRequired) || item.starsRequired < 1 || item.starsRequired > 10) {
          throw new Error(`Stars required for ${item.qualityLabel || item.qualityCode} must be between 1 and 10.`);
        }
      }

      if (!Number.isFinite(starsRequiredTheatre) || starsRequiredTheatre < 1 || starsRequiredTheatre > 10) {
        throw new Error("Stars Required - Theatre must be between 1 and 10.");
      }

      if (!Number.isFinite(expectedStars) || expectedStars < 0) {
        throw new Error("Target Stars must be zero or higher.");
      }

      await updateAdminMoviePricingConfigRemote(movieId, {
        onlinePricingOptions,
        starsRequiredTheatre,
        expectedStars,
      });
    } catch (error) {
      adminHelper.textContent = error instanceof Error ? error.message : "Unable to save title pricing.";
    }
  });
}

if (adminPosterFiles) {
  adminPosterFiles.addEventListener("change", async () => {
    if (!adminPosterUploadPreview) {
      return;
    }

    const files = Array.from(adminPosterFiles.files || []);
    if (!files.length) {
      adminPosterUploadPreview.classList.add("hidden");
      adminPosterUploadPreview.textContent = "";
      return;
    }

    try {
      const classifiedFiles = await Promise.all(files.map((file) => classifyPosterFile(file)));
      adminPosterUploadPreview.innerHTML = classifiedFiles
        .map((item) => `${escapeHtml(item.file.name)} - ${item.width}x${item.height} - ${item.orientation}`)
        .join("<br>");
      adminPosterUploadPreview.classList.remove("hidden");
    } catch (error) {
      adminPosterUploadPreview.textContent = error.message;
      adminPosterUploadPreview.classList.remove("hidden");
    }
  });
}

if (adminReleaseMainContentForm) {
  adminReleaseMainContentForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminReleaseMainContentMovieId?.value.trim();
    const releaseDateTime = adminReleaseMainContentDateTime?.value.trim() || "";
    const releasePasscode = adminReleaseMainContentPasscode?.value.trim() || "";

    try {
      if (!movieId) {
        throw new Error("Choose a title before saving release details.");
      }
      const parsedDate = releaseDateTime ? new Date(releaseDateTime) : null;
      if (!releaseDateTime || !parsedDate || Number.isNaN(parsedDate.getTime())) {
        throw new Error("Choose a valid future release date and time.");
      }
      if (parsedDate.getTime() <= Date.now()) {
        throw new Error("Release date and time must be in the future.");
      }
      if (!releasePasscode) {
        throw new Error("Enter the release passcode.");
      }
      await updateAdminMovieReleaseMainContentRemote(movieId, {
        releaseDateTime,
        releasePasscode,
      });
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminPasswordPublishAt) {
  adminPasswordPublishAt.addEventListener("input", () => {
    if (adminReservationCloseAt) {
      adminReservationCloseAt.value = deriveReserveCloseAtValue(adminPasswordPublishAt.value);
    }
  });
}

if (adminPosterUploadForm) {
  adminPosterUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminPosterMovieId?.value.trim();
    const files = Array.from(adminPosterFiles?.files || []);

    try {
      if (!movieId || !files.length) {
        throw new Error("Please choose at least one poster image.");
      }
      await uploadAdminMoviePostersRemote(movieId, files);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminPosterAssetList) {
  adminPosterAssetList.addEventListener("click", async (event) => {
    const navButton = event.target.closest("[data-admin-poster-nav]");
    if (navButton) {
      adminPosterCarouselIndex += navButton.dataset.adminPosterNav === "next" ? 1 : -1;
      if (adminPosterCarouselIndex < 0) {
        adminPosterCarouselIndex = adminPosterAssets.length - 1;
      }
      if (adminPosterCarouselIndex >= adminPosterAssets.length) {
        adminPosterCarouselIndex = 0;
      }
      renderAdminPosterCarousel(adminPosterAssets);
      return;
    }

    const button = event.target.closest("[data-admin-media-delete]");
    if (!button) {
      return;
    }

    const movieId = adminPosterMovieId?.value.trim();
    const assetName = button.dataset.adminMediaName;

    try {
      if (!movieId || !assetName) {
        throw new Error("Media file details are missing.");
      }
      await deleteAdminMediaAssetRemote(movieId, "posters", assetName);
      adminPosterCarouselIndex = Math.max(0, adminPosterCarouselIndex - (adminPosterCarouselIndex >= adminPosterAssets.length - 1 ? 1 : 0));
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminTrailerUploadForm) {
  adminTrailerUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminTrailerMovieId?.value.trim();
    const file = adminTrailerFile?.files?.[0];

    try {
      if (!movieId || !file) {
        throw new Error("Please choose a trailer file.");
      }
      await uploadAdminMovieTrailerRemote(movieId, file);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminGalleryUploadForm) {
  adminGalleryUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminGalleryMovieId?.value.trim();
    const file = adminGalleryFile?.files?.[0];

    try {
      if (!movieId || !file) {
        throw new Error("Please choose a gallery file.");
      }
      await uploadAdminMovieGalleryRemote(movieId, file);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminTrailerAssetList) {
  adminTrailerAssetList.addEventListener("click", async (event) => {
    const navButton = event.target.closest("[data-admin-media-nav]");
    if (navButton) {
      adminTrailerCarouselIndex += navButton.dataset.adminMediaNav === "trailer-next" ? 1 : -1;
      if (adminTrailerCarouselIndex < 0) {
        adminTrailerCarouselIndex = adminTrailerAssets.length - 1;
      }
      if (adminTrailerCarouselIndex >= adminTrailerAssets.length) {
        adminTrailerCarouselIndex = 0;
      }
      renderAdminMediaCarousel("trailer", adminTrailerAssets);
      return;
    }

    const button = event.target.closest("[data-admin-media-delete]");
    if (!button) {
      return;
    }

    const movieId = adminTrailerMovieId?.value.trim();
    const assetName = button.dataset.adminMediaName;

    try {
      if (!movieId || !assetName) {
        throw new Error("Media file details are missing.");
      }
      await deleteAdminMediaAssetRemote(movieId, "trailer", assetName);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminGalleryAssetList) {
  adminGalleryAssetList.addEventListener("click", async (event) => {
    const navButton = event.target.closest("[data-admin-media-nav]");
    if (navButton) {
      adminGalleryCarouselIndex += navButton.dataset.adminMediaNav === "gallery-next" ? 1 : -1;
      if (adminGalleryCarouselIndex < 0) {
        adminGalleryCarouselIndex = adminGalleryAssets.length - 1;
      }
      if (adminGalleryCarouselIndex >= adminGalleryAssets.length) {
        adminGalleryCarouselIndex = 0;
      }
      renderAdminMediaCarousel("gallery", adminGalleryAssets);
      return;
    }

    const button = event.target.closest("[data-admin-media-delete]");
    if (!button) {
      return;
    }

    const movieId = adminGalleryMovieId?.value.trim();
    const assetName = button.dataset.adminMediaName;

    try {
      if (!movieId || !assetName) {
        throw new Error("Media file details are missing.");
      }
      await deleteAdminMediaAssetRemote(movieId, "gallery", assetName);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminMusicUploadForm) {
  adminMusicUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminMusicMovieId?.value.trim();
    const file = adminMusicFile?.files?.[0];

    try {
      if (!movieId || !file) {
        throw new Error("Please choose a music file.");
      }
      await uploadAdminMovieMusicRemote(movieId, file);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminContentDeleteFolderButton) {
  adminContentDeleteFolderButton.addEventListener("click", async () => {
    const movieId = adminContentMovieId?.value.trim();
    if (!movieId) {
      return;
    }
    if (!window.confirm("Delete the entire uploaded content chunk folder for this title?")) {
      return;
    }
    try {
      await deleteAdminContentFolderRemote(movieId);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminContentUploadForm) {
  adminContentUploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const movieId = adminContentMovieId?.value.trim();
    const uploadStartAt = adminContentUploadStartAt?.value.trim() || "";

    try {
      if (!movieId) {
        throw new Error("Please choose a title first.");
      }
      if (!adminContentQualityState.isComplete) {
        throw new Error("Upload every required title quality before setting the future start time.");
      }
      if (!uploadStartAt) {
        throw new Error("Please choose the upload future start date and time.");
      }
      await scheduleAdminMovieContentRemote(movieId, uploadStartAt);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminContentAssetList) {
  adminContentAssetList.addEventListener("change", (event) => {
    const fileInput = event.target.closest("[data-admin-content-file-input]");
    if (!fileInput) {
      return;
    }
    const card = fileInput.closest("[data-admin-content-quality-card]");
    if (card) {
      renderAdminContentQualityPreview(card);
    }
  });

  adminContentAssetList.addEventListener("click", async (event) => {
    const contentDeleteButton = event.target.closest("[data-admin-media-delete='content']");
    if (contentDeleteButton) {
      const movieId = adminContentMovieId?.value.trim();
      const assetName = contentDeleteButton.dataset.adminMediaName || "";
      if (!movieId) {
        return;
      }
      if (!window.confirm("Delete this title quality content from the server?")) {
        return;
      }
      try {
        await deleteAdminMediaAssetRemote(movieId, "content", assetName);
        if (adminContentUploadStartAt) {
          adminContentUploadStartAt.value = "";
        }
        if (adminContentUploadStartAtDisplay) {
          adminContentUploadStartAtDisplay.textContent = "Not set";
        }
      } catch (error) {
        adminHelper.textContent = error.message;
      }
      return;
    }

    const uploadButton = event.target.closest("[data-admin-content-upload-button]");
    if (uploadButton) {
      const movieId = adminContentMovieId?.value.trim();
      const qualityCode = uploadButton.dataset.adminContentQualityCode || "";
      const card = uploadButton.closest("[data-admin-content-quality-card]");
      const file = card?.querySelector("[data-admin-content-file-input]")?.files?.[0];
      const password = card?.querySelector("[data-admin-content-password]")?.value.trim() || "";
      try {
        if (!movieId) {
          throw new Error("Please choose a title first.");
        }
        if (!qualityCode) {
          throw new Error("That title quality could not be identified.");
        }
        if (!file) {
          throw new Error(`Please choose a file for ${qualityCode}.`);
        }
        if (!password) {
          throw new Error(`Please enter a passcode for ${qualityCode}.`);
        }
        if (!isWebPlayableMainContentExtension(file.name)) {
          throw new Error("For the website player, Upload Main Content accepts only MP4, M4V, or WebM files.");
        }
        await uploadAdminMovieContentQualityRemote(movieId, qualityCode, file, password);
      } catch (error) {
        adminHelper.textContent = error.message;
      }
      return;
    }

    const generateButton = event.target.closest("[data-admin-content-generate-password]");
    if (generateButton) {
      const card = generateButton.closest("[data-admin-content-quality-card]");
      const passwordInput = card?.querySelector("[data-admin-content-password]");
      if (passwordInput) {
        passwordInput.value = generateStrongPassword();
        passwordInput.focus();
        passwordInput.select();
      }
      return;
    }

    const deleteButton = event.target.closest("[data-admin-content-delete-button]");
    if (deleteButton) {
      const movieId = adminContentMovieId?.value.trim();
      const qualityCode = deleteButton.dataset.adminContentQualityCode || "";
      if (!movieId || !qualityCode) {
        return;
      }
      if (!window.confirm("Delete this title quality content from the server?")) {
        return;
      }
      try {
        await deleteAdminContentQualityRemote(movieId, qualityCode);
        if (adminContentUploadStartAt) {
          adminContentUploadStartAt.value = "";
        }
      } catch (error) {
        adminHelper.textContent = error.message;
      }
    }
  });
}

if (adminMusicAssetList) {
  adminMusicAssetList.addEventListener("click", async (event) => {
    const navButton = event.target.closest("[data-admin-media-nav]");
    if (navButton) {
      adminMusicCarouselIndex += navButton.dataset.adminMediaNav === "music-next" ? 1 : -1;
      if (adminMusicCarouselIndex < 0) {
        adminMusicCarouselIndex = adminMusicAssets.length - 1;
      }
      if (adminMusicCarouselIndex >= adminMusicAssets.length) {
        adminMusicCarouselIndex = 0;
      }
      renderAdminMediaCarousel("music", adminMusicAssets);
      return;
    }

    const button = event.target.closest("[data-admin-media-delete]");
    if (!button) {
      return;
    }

    const movieId = adminMusicMovieId?.value.trim();
    const assetName = button.dataset.adminMediaName;

    try {
      if (!movieId || !assetName) {
        throw new Error("Media file details are missing.");
      }
      await deleteAdminMediaAssetRemote(movieId, "music", assetName);
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminMovieList) {
  adminMovieList.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-admin-movie-action]");
    const pageButton = event.target.closest("[data-admin-library-page]");

    if (pageButton) {
      adminLibraryPage += pageButton.dataset.adminLibraryPage === "next" ? 1 : -1;
      renderAdminMovieList();
      return;
    }

    const card = event.target.closest("[data-admin-movie-id]");
    if (!actionButton || !card) {
      return;
    }

    const movieId = card.dataset.adminMovieId;
    const selectedMovie = adminMovies.find((movie) => movie.id === movieId);
    if (!selectedMovie) {
      return;
    }

    try {
      if (actionButton.dataset.adminMovieAction === "edit") {
        openAdminLibraryEditor(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "pricing-targets" && !selectedMovie.archived) {
        openAdminPricingTargetsModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "approve" && !selectedMovie.archived) {
        await openAdminApprovalReviewModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "release-main-content" && !selectedMovie.archived) {
        openAdminReleaseMainContentModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "reserve-start" && !selectedMovie.archived) {
        openAdminMovieReserveToggleDialog(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "posters" && !selectedMovie.archived) {
        openAdminPosterUploadModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "trailer" && !selectedMovie.archived) {
        openAdminTrailerUploadModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "gallery" && !selectedMovie.archived) {
        openAdminGalleryUploadModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "music" && !selectedMovie.archived) {
        openAdminMusicUploadModal(selectedMovie);
      } else if (actionButton.dataset.adminMovieAction === "delivery-queue") {
        openAdminDeliveryQueueForMovie(movieId);
      } else if (actionButton.dataset.adminMovieAction === "archive" && !selectedMovie.archived) {
        openAdminMovieArchiveDialog(selectedMovie);
      }
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminMovieList) {
  adminMovieList.addEventListener("click", (event) => {
    const contentButton = event.target.closest("[data-admin-movie-action=\"content\"]");
    if (!contentButton) {
      return;
    }
    const movieId = contentButton.dataset.adminContentOpen || contentButton.closest("[data-admin-movie-id]")?.dataset.adminMovieId || "";
    if (movieId && typeof window.openAdminContentUploadForMovie === "function") {
      window.openAdminContentUploadForMovie(movieId);
    }
  });
}

if (adminArchiveMovieList) {
  adminArchiveMovieList.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-admin-archive-action]");
    const card = event.target.closest("[data-admin-archive-movie-id]");
    if (!actionButton || !card) {
      return;
    }

    const movieId = card.dataset.adminArchiveMovieId;
    const selectedMovie = adminMovies.find((movie) => movie.id === movieId);
    if (!selectedMovie) {
      return;
    }

    try {
      if (actionButton.dataset.adminArchiveAction === "restore") {
        await restoreAdminMovieRemote(movieId);
      } else if (actionButton.dataset.adminArchiveAction === "delete") {
        openAdminMoviePermanentDeleteDialog(selectedMovie);
      }
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminTaxonomyKind) {
  adminTaxonomyKind.value = adminTaxonomyKindFilter;
}

if (adminTaxonomySort) {
  adminTaxonomySort.value = adminTaxonomySortValue;
}

if (adminTaxonomySearch) {
  adminTaxonomySearch.addEventListener("input", () => {
    adminTaxonomySearchTerm = adminTaxonomySearch.value;
    adminTaxonomyPage = 1;
    renderAdminTaxonomyList();
  });
}

if (adminTaxonomyKind) {
  adminTaxonomyKind.addEventListener("change", () => {
    adminTaxonomyKindFilter = adminTaxonomyKind.value;
    adminTaxonomyPage = 1;
    renderAdminTaxonomyList();
  });
}

if (adminTaxonomySort) {
  adminTaxonomySort.addEventListener("change", () => {
    adminTaxonomySortValue = adminTaxonomySort.value;
    adminTaxonomyPage = 1;
    renderAdminTaxonomyList();
  });
}

if (adminAddTaxonomyButton) {
  adminAddTaxonomyButton.addEventListener("click", () => {
    openAdminTaxonomyEditor(null, adminTaxonomyKindFilter === "all" ? "categories" : adminTaxonomyKindFilter);
  });
}

if (adminTaxonomyCancelButton) {
  adminTaxonomyCancelButton.addEventListener("click", () => {
    closeAdminTaxonomyEditor();
  });
}

document.querySelectorAll("[data-admin-taxonomy-close]").forEach((button) => {
  button.addEventListener("click", () => {
    closeAdminTaxonomyEditor();
  });
});

if (adminTaxonomyEditor) {
  adminTaxonomyEditor.addEventListener("input", (event) => {
    if (event.target === adminTaxonomyName && !adminTaxonomySlug.value.trim()) {
      adminTaxonomySlug.value = slugifyValue(adminTaxonomyName.value);
    }
  });

  adminTaxonomyEditor.addEventListener("submit", async (event) => {
    event.preventDefault();

    const itemId = adminTaxonomyEditId.value.trim();
    const kind = adminTaxonomyEditorKind.value;
    const payload = {
      name: adminTaxonomyName.value.trim(),
      slug: (adminTaxonomySlug.value.trim() || slugifyValue(adminTaxonomyName.value)).trim(),
      description: adminTaxonomyDescription.value.trim() || null,
      sort_order: Number(adminTaxonomySortOrder.value || 0),
      is_active: adminTaxonomyStatus.value === "true",
    };

    try {
      const path = itemId ? `/admin/taxonomies/${kind}/${itemId}` : `/admin/taxonomies/${kind}`;
      const response = await apiRequest(path, {
        method: "POST",
        body: JSON.stringify(payload),
      });

      await loadAdminTaxonomiesFromApi();
      renderAdminSummaryMetrics();
      closeAdminTaxonomyEditor();
      adminHelper.textContent = response.message;
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

if (adminTaxonomyList) {
  adminTaxonomyList.addEventListener("click", async (event) => {
    const pageButton = event.target.closest("[data-admin-taxonomy-page]");
    if (pageButton) {
      adminTaxonomyPage += pageButton.dataset.adminTaxonomyPage === "next" ? 1 : -1;
      renderAdminTaxonomyList();
      return;
    }

    const button = event.target.closest("[data-admin-taxonomy-action]");
    const row = event.target.closest("[data-admin-taxonomy-id]");
    if (!button || !row) {
      return;
    }

    const kind = row.dataset.adminTaxonomyKind;
    const itemId = row.dataset.adminTaxonomyId;
    const item = (adminTaxonomies[kind] || []).find((entry) => String(entry.id) === String(itemId));

    try {
      if (button.dataset.adminTaxonomyAction === "edit" && item) {
        openAdminTaxonomyEditor({ ...item, kind });
      } else if (button.dataset.adminTaxonomyAction === "delete" && item) {
        await deleteAdminTaxonomyRemote(kind, itemId);
      } else if (button.dataset.adminTaxonomyAction === "move-up" && item) {
        await moveAdminTaxonomyRemote(kind, itemId, "up");
      } else if (button.dataset.adminTaxonomyAction === "move-down" && item) {
        await moveAdminTaxonomyRemote(kind, itemId, "down");
      }
    } catch (error) {
      adminHelper.textContent = error.message;
    }
  });
}

window.setInterval(refreshTimeDrivenMovieViews, 60 * 1000);

syncAuthEntryCopy();
applyStoredAdminSession();
setStage("upcoming");
setView(entryMode === "admin" || entryMode === "creator" ? "auth" : "viewer");
setAdminPanel("users");
if (video) {
  setMode("stream");
  prefillSharedUrl();
  probeSampleFile();
}
bootstrapAppData();
if (entryMode === "admin") {
  syncAuthEntryCopy();
} else if (entryMode === "creator") {
  syncAuthEntryCopy();
}
