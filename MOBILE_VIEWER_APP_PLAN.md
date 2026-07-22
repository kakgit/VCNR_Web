# Mobile Viewer App Plan

## Recommended Direction

Build one shared mobile viewer app for both Android and iOS.

Recommended starting stack:

- React Native
- Expo at the beginning for faster setup
- Existing VCNR backend APIs for auth, catalog, wallet, reserve, buy, download, and collection flows

Why this direction:

- One codebase for Android and iOS
- Faster delivery than building two separate native apps
- Easier reuse of API shapes and business rules already created for the website
- Good path to move into deeper native secure playback later

## Phase 1: Mobile Foundation

- Create the mobile app project
- Configure Android and iOS builds
- Connect to the current backend
- Set up app navigation
- Set up session handling and secure token storage
- Build base theme and reusable UI components

Initial screens:

- Login
- Home
- Up Coming
- New Released
- Wish To Watch
- Reserved
- My Collection
- Movie Details
- My Account / Wallet

## Phase 2: Viewer Actions

- Wish To Watch
- Reserve Now
- Buy Now
- Wallet star balance display
- Confirmation flows before star deduction
- Proper state sync with backend after reserve or buy

Expected behavior:

- Upcoming titles allow wish or reserve
- Released titles allow buy
- Bought titles move into My Collection
- Reserved titles move into My Collection after release conditions are met

## Phase 3: Secure Content Download

- Download encrypted chunk files to app-managed storage
- Track per-title download state
- Support pause, resume, retry, and corruption handling
- Prevent normal public file access as much as possible

Tracked states:

- Not started
- Queued
- Downloading
- Paused
- Failed
- Completed

## Phase 4: Release Unlock and Playback

- Fetch release passcode from server only after release
- Decrypt chunks inside the app
- Reconstruct playable media locally
- Play only in app-controlled player
- Enforce release date and release passcode checks

Core rules:

- No playback before release date/time
- No playback without release passcode
- No playback if required local content is missing

## Phase 5: Device and Security Controls

- Device registration
- Session and device validation
- One-device or multi-device purchase rules
- Better protection around local encrypted content
- Local database for tracking downloaded titles
- Cleanup tools for broken or stale downloads

## Phase 6: Store Readiness

- Android packaging
- iOS packaging
- App icons, splash screens, permissions
- Crash logging
- User support/error reporting hooks
- Store submission preparation

## Important Business Difference

Website:

- Good for admin flows
- Good for viewer discovery and purchase flow
- Good for proof of concept

Mobile app:

- Better place for real secure content delivery
- Better control over encrypted downloads
- Better control over local playback and device restrictions

## Practical First Build Order

1. Create project and navigation
2. Connect login and session APIs
3. Build movie listing screens
4. Build movie details page
5. Add wish, reserve, and buy flows
6. Add My Collection
7. Add encrypted download flow
8. Add local playback flow
9. Add device/security rules

## Open Discussion Items

These still need final clarification before implementation:

- React Native with Expo first, or bare React Native from day one
- One device only or multiple devices per user
- Whether extra stars are needed for extra devices
- Exact secure playback restrictions
- Background download expectations
- Offline playback rules after release
- App-first rollout order: Android first or Android and iOS together

## Delivery Model Decision

Confirmed direction:

1. Server-only mode first
2. Peer-assisted mode later
3. Even after peer-assisted mode is added, server delivery remains available as fallback

### Stage 1: Server-only mode

- Viewer app downloads encrypted chunk files directly from server
- Server remains the only delivery source
- Easier to test, secure, monitor, and bill
- Best for first mobile production release

### Stage 2: Peer-assisted mode with server fallback

- Add peer-assisted download only after server-only flow is stable
- Server remains the source of truth for:
  - access control
  - entitlement
  - manifest
  - chunk validation
  - fallback download
- If peer delivery fails, server download continues or resumes

### Long-term supported modes

- Server-only mode
- Peer-assisted mode with server fallback

### Why this order

- Lower implementation risk
- Faster first release
- Better operational control
- Easier debugging
- Easier security enforcement
- Safer way to measure real bandwidth savings before expanding P2P
