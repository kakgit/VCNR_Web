# Mobile Public Delivery Testing Note

Date: July 22, 2026

## Related stable flow document

- See [stable-mobile-delivery-flow.md](D:/Python/VCNR_Web/docs/stable-mobile-delivery-flow.md) for the verified stable Android delivery flow baseline.

## Current working setup

- Backend is still running locally on the laptop through Uvicorn on port `8000`.
- A temporary public Cloudflare quick tunnel is being used for outside-network testing.
- Current temporary public URL:
  - `https://transmission-src-intersection-montana.trycloudflare.com`
- The mobile app should use only the base URL above.
- The app itself appends `/api` internally.

## Important tunnel behavior

- This is a free temporary `trycloudflare.com` tunnel used only for testing.
- It works only while `cloudflared` is running on the laptop.
- If the laptop restarts, sleeps, or the tunnel process stops, the URL can stop working.
- When restarted, the temporary URL may change.

## Cloudflared local install

- `cloudflared` was installed on Windows through `winget`.
- Installed executable path found during testing:
  - `C:\Program Files (x86)\cloudflared\cloudflared.exe`
- Tunnel start command used:
  - `cloudflared tunnel --url http://localhost:8000`

## Mobile app delivery progress

- `mobile-viewer-app` now supports Android background downloading through a native Android foreground service with WorkManager recovery support.
- Download can continue when:
  - screen is off
  - app is in background
  - app is removed from recent apps
- Partial downloads are tracked through:
  - `manifest.json`
  - `download-state.json`
  - encrypted chunk files inside app storage

## Verified working behavior

- Verified on July 22, 2026:
  - local Wi-Fi download works
  - resume after refresh works
  - resume after app reopen works
  - background Android download works
  - download continued after removing the app from recent apps
  - mobile data download also works through the Cloudflare quick tunnel
  - stale cancelled delivery state can be cleared after local file deletion
  - direct VCNR playback works without leaving a full `.mp4` playback file in app storage

## Real test package used

- Real movie package used for testing, not only sample clips
- Approximate size:
  - `2.5 GB`
- Duration:
  - about `2 hours`
- Chunk count:
  - `328`

## Known limitations

- Mobile data download will not work against a plain laptop LAN IP like `192.168.x.x`.
- Mobile data download only worked after exposing the backend through the public Cloudflare tunnel.
- If the tunnel is down, login and delivery from outside the home Wi-Fi will fail.
- This quick tunnel is good for testing, not for final production.

## Recommended next step

- Keep using the temporary Cloudflare quick tunnel for testing.
- Move later to one of these for stable public delivery:
  - named Cloudflare Tunnel with owned domain
  - public backend hosting such as Render or Railway
- Use the new stable delivery flow document as the working baseline for future mobile delivery changes.

## Notes for app testing

- On phones using the public tunnel, the server field should be:
  - `https://transmission-src-intersection-montana.trycloudflare.com`
- Do not manually add `/api`.
- If login fails, first verify:
  - the tunnel process is still running on the laptop
  - the public URL opens in the phone browser
  - the app is not still pointing to an old local IP
