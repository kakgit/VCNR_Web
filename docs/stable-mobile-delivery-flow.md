# Stable Mobile Delivery Flow

Date: July 22, 2026

## Purpose

This document records the currently stable VCNR mobile delivery flow that has been verified in the Android viewer app.

## Stable delivery flow

1. The viewer logs in to the mobile app.
2. The viewer opens the reserved title and reaches the `Content Delivery` screen.
3. The app reads the title manifest for the selected `quality_code`.
4. The app checks the delivery schedule and user download settings.
5. If the `Download From` date has already passed and auto download is enabled, the app starts or resumes encrypted chunk download automatically.
6. If auto download is disabled, the viewer can start manually with `Download Now` or `Resume Download`.
7. Downloaded files are stored inside the app's private Android storage, not as a playable `.mp4` file.
8. The app keeps `manifest.json`, `download-state.json`, and the encrypted chunk files so it can resume safely after interruption.
9. When all encrypted chunks are present, the app enables local playback through the VCNR player.
10. The VCNR player reads directly from the VCNR package path and does not create a full unlocked movie file for playback.

## What is now working reliably

- Local Wi-Fi delivery works.
- Mobile-data delivery works when the backend is exposed through a Cloudflare tunnel.
- Download resumes after app reopen.
- Download resumes after removing the app from recent apps and logging back in.
- Download can continue while the app is in background.
- Download can survive temporary network changes and continue again after recovery.
- Local file detection works after relogin.
- If local encrypted files were deleted, the app can clear stale background state and start again correctly.
- The player opens from the VCNR chunk package path with no `.mp4` playback copy created in app storage.

## Android implementation summary

- Foreground download is handled by a native Android foreground service.
- Scheduled recovery and background checks are still supported through WorkManager.
- Background progress is persisted so the React Native screen can recover the real state after reopening.
- Delivery is keyed by:
  - `movie_id`
  - `user_id`
  - `quality_code`

## Current storage behavior

- Encrypted chunks are stored under the app's internal files area.
- The package remains private to the app.
- A full decrypted movie file is not created for the stable VCNR direct-stream path.
- Because app-private storage is used, the files are not meant to be casually browsed by the user from normal phone file managers.

## Viewer-facing behavior

- If the release time has not arrived yet, the app waits for the schedule.
- If the release time has passed and auto download is on, the app should start or resume automatically.
- If the network is interrupted, the app can continue from the existing downloaded chunk count instead of restarting from zero.
- If the viewer deletes downloaded files, the app should rebuild state from what is actually present on device.

## Testing baseline used

- Title: `Super Man`
- Quality tested: `1080p Full HD`
- Approximate package size: `2.5 GB`
- Approximate duration: `2 hours`
- Chunk count: `328`

## Known testing dependency

- Outside the home Wi-Fi, the mobile app must use a public backend URL, not a laptop LAN IP.
- For current testing this public URL is provided by a temporary Cloudflare quick tunnel.
- That quick tunnel URL can change whenever the tunnel process is restarted.

## Recommended next steps

- Keep this as the current stable delivery baseline for `mobile-viewer-app`.
- Reuse the same flow while integrating the VCNR direct player everywhere a downloaded title is opened.
- Later replace the temporary Cloudflare quick tunnel with a stable named domain or hosted backend.
