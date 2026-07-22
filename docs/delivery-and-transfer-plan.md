# Delivery and Transfer Plan

## Queue

- Keep one normalized delivery queue table instead of one table per title.
- Queue/enrollment starts only after the viewer chooses `Reserve Now` -> `Online`, selects a title quality, and accepts the download conditions.
- Use `movie_id`, `user_id`, and `quality_code` as the primary lookup path.
- Store one delivery enrollment per selected title quality, not one broad enrollment per title.
- Create or repair the delivery enrollment in the same backend transaction that records an online quality reservation, because the mobile flow only sends a quality after the viewer has accepted the download conditions.
- Treat any reservation that carries a `quality_code` as an online reservation; theatre reservations must not carry title-quality delivery data.
- Use the reserved quality's star price for blocked stars, queue display, and later download authorization.
- Allow a viewer to change the reserved online title quality before download starts; upgrade blocks the extra stars, downgrade releases the difference, and the queue moves to the new `quality_code`.
- Block title-quality changes once delivery is `slot_granted`, `downloading`, or `downloaded`; later cancellation/reset needs a separate flow.
- Show the full queue in a separate Admin Queue page, not inside `Upload Main Content`.
- Add a queue link in each title row so admins can jump straight to that title's queue.
- Keep the queue view paginated, filterable, and displayed as a data grid so large title volumes stay fast.
- A delivery slot can only fetch the manifest and chunk files for the enrollment's `quality_code`.

## Transfer

- The user signs in with the same account on both devices.
- The source device creates a pairing code or QR-based transfer session.
- The target device must already be signed in with the same user ID.
- Only encrypted chunks move between devices.
- The backend only handles pairing, authorization, and session control.
- The file bytes should not be relayed through the backend unless we later decide on a fallback.
- The current stable mobile baseline is documented in [stable-mobile-delivery-flow.md](D:/Python/VCNR_Web/docs/stable-mobile-delivery-flow.md).

## Playback

- Keep one active playback session at a time.
- Re-authorize the new device with a fresh playback passcode or license after transfer.
- Keep the entitlement attached to the account and selected title quality, not to a single device.
