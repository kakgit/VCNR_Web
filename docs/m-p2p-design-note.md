# M-P2P Design Note

Date: July 22, 2026

## Purpose

This note captures the planned `M-P2P` direction for VCNR as a future track after the current `VCNR_Web` delivery flow is stabilized and hosted publicly.

`M-P2P` here means:

- mobile-to-mobile peer-to-peer transfer
- only for protected VCNR encrypted chunk packages
- not for unlocked full movie files

## Current decision

The first phone-to-phone proof-of-concept has started inside `mobile-viewer-app`, but the next engineering step should not be more APK-only iteration.

Current decision:

- Freeze the current mobile transfer as a working proof-of-concept.
- Build and use a local simulator/harness for transfer logic first.
- Prove resume, integrity, corruption handling, and entitlement rules quickly outside the phone install loop.
- Then move the proven logic back into the mobile app.

## Current learning

The first real-phone test proved the core product idea:

- encrypted VCNR chunks can move from one phone to another
- no unlocked `.mp4` needs to be created or transferred
- playback can still happen from the VCNR protected package

The same testing also showed that repeated APK install testing is too slow for core transfer bugs. Resume and integrity should be validated with a simulator first.

## High-level M-P2P goal

Allow one mobile device to transfer already downloaded VCNR encrypted chunk packages to another entitled mobile device without sending a full unlocked movie file.

This should support:

- faster local transfer when two devices are near each other
- reduced repeated server bandwidth usage
- same entitlement and release-date protection rules
- reuse of the existing VCNR player on the receiving device

## Torrent-style direction

The better long-term model is a controlled VCNR swarm, similar to torrents, but with VCNR rules.

In this model:

- every title quality is split into many encrypted VCNR chunks
- each chunk has manifest size/hash verification
- a phone can download different missing chunks from different sources
- a phone that already has verified chunks can become a source for those chunks
- the backend works like a tracker/coordinator
- playback remains locked until server entitlement and release validation pass

This is different from public torrents because VCNR must not allow open sharing.

VCNR swarm rules:

- peers only exchange encrypted VCNR chunks
- peers never exchange unlocked `.mp4` files
- peers never exchange permanent playback secrets
- receiver must be entitled to the same `movie_id` and `quality_code`
- receiver verifies every chunk against the official manifest
- backend can revoke, throttle, audit, or disable peer-assisted delivery

This means the system behaves like torrent delivery for speed and resilience, but not like public torrent ownership or piracy.

## Long-term product direction

The future target is not limited to the same user only.

Long term, VCNR should support:

- user-to-user encrypted package transfer
- but only when the receiving user is independently entitled to that title quality

Important rule:

- transfer should move only encrypted VCNR chunks
- transfer should not transfer ownership
- playback must still require server-side entitlement and release validation for the receiving user

This means M-P2P becomes a controlled peer-assisted delivery path, not a free sharing path.

## Core rule

Only these items should move peer-to-peer:

- encrypted chunk files
- manifest/package metadata required for verification

These must not move peer-to-peer as final payloads:

- unlocked full movie `.mp4` files
- permanent playback secrets
- unrestricted raw decryption material stored for reuse outside app rules

## Recommended architecture

### Server responsibilities

- user authentication
- title entitlement verification
- release-date validation
- device authorization
- transfer session creation
- pairing approval
- passcode/license issue at playback time
- audit logging

### Sender mobile responsibilities

- prove that the title package already exists locally
- prove that the sender is the entitled logged-in user
- expose only the selected title-quality package for transfer
- send only missing encrypted chunks

### Receiver mobile responsibilities

- prove that the receiver is signed in as the same user or otherwise allowed by policy
- verify manifest integrity
- store incoming encrypted chunks in app-private storage
- resume partial transfers safely
- use the normal VCNR protected playback path after verification

## User scope by phase

### Phase 1

- same user only
- same account on both phones

Reason:

- easiest and safest way to validate transport, resume, storage, and playback flow first

### Future phases

- any user may become a transfer receiver
- but only if that receiving user is already authorized by the VCNR backend for that title quality

This future rule is critical:

- sender device is only a delivery source
- receiver playback rights must come from the backend, not from the sender

## Quality-specific rule

`M-P2P` should remain quality-specific, just like the queue and delivery flow.

Every transfer should be keyed by:

- `movie_id`
- `user_id`
- `quality_code`

Reason:

- each quality has different package size
- each quality can have different star pricing
- entitlement and local storage should stay exact

## Suggested transfer flow

### Manual pairing prototype

1. Receiver signs in.
2. Receiver opens a `Transfer from another device` option.
3. Receiver generates a short pairing code or QR session.
4. Sender opens `Send to another device`.
5. Sender scans or enters the pairing code.
6. Backend verifies both devices and the entitled title-quality package.
7. A transfer session is approved.
8. Sender shares manifest summary and receiver reports which chunks are missing.
9. Sender transfers only missing encrypted chunks.
10. Receiver writes chunks into app-private VCNR storage.
11. Receiver verifies package completeness.
12. Playback still requires the normal release and unlock checks before play.

### Future swarm flow

1. Receiver signs in.
2. Receiver requests delivery for `movie_id + quality_code`.
3. Backend checks entitlement and release/download policy.
4. Receiver fetches the official VCNR manifest.
5. Receiver reports its verified local chunk inventory.
6. Backend returns a list of available sources for missing chunks.
7. Receiver downloads chunks from server or entitled peer sources.
8. Receiver verifies each chunk size/hash before marking it complete.
9. Receiver periodically reports verified progress.
10. Once verified complete, receiver can also become a source for other entitled receivers.
11. Playback still requires the normal server unlock.

## Future any-user delivery rule

When M-P2P expands beyond same-user transfer, the expected flow should be:

1. sender has the encrypted VCNR package locally
2. receiver requests the same title and quality
3. backend checks whether receiver is entitled
4. if entitled, backend allows peer-assisted transfer
5. sender transfers encrypted chunks only
6. receiver still must pass normal VCNR playback unlock checks

So:

- M-P2P can reduce bandwidth and improve delivery speed
- but it must not bypass purchase, reservation, or release rules

## Transport direction

Important updated decision:

`M-P2P` should be transport-independent.

That means VCNR should not depend on only one path such as direct LAN, WebRTC, or `libp2p`.

Allowed transfer paths can include:

- mobile-data internet transfer
- Wi-Fi internet transfer
- direct LAN transfer later
- WebRTC or `libp2p` later if they give better speed/cost
- normal server download fallback

Backend relay note:

- backend relay was useful as a lab proof
- it should not become a production delivery path
- production should avoid storing viewer-uploaded duplicate chunk copies on the server

The product rule is more important than the transport rule:

- only encrypted VCNR chunks move
- the receiver must be entitled for the same `movie_id` and `quality_code`
- the receiver verifies chunk size and hashes
- playback still requires server unlock/release validation

So the final direction is better described as:

- peer-assisted encrypted delivery
- torrent-style controlled swarm delivery
- not necessarily pure direct phone-to-phone networking

Production-supported delivery paths should be:

1. official `Server -> Phone`
2. same-Wi-Fi `Phone B -> Phone A` Direct LAN
3. future WebRTC/libp2p-style device transfer if it avoids backend chunk storage

## Backend tracker responsibilities

For the torrent-style model, the backend should act like a private tracker.

The backend should know:

- which users are entitled to each `movie_id + quality_code`
- which devices have verified chunks
- which chunks each device claims to have
- when each device was last active
- whether a source is online, slow, failed, or blocked
- how much relay/server bandwidth is being used

The backend should not trust peer claims blindly.

Receiver truth comes from:

- official manifest
- local file size
- local checksum
- successful playback unlock checks

## Temporary tracker state for scale

Seeder availability should be treated as temporary live swarm state, not permanent user history.

Important scaling decision:

- Do not store every `user_id + movie_id + quality_code + chunk_id` row forever.
- Permanent storage should keep business facts such as entitlement, reservation, purchase, and completed download status.
- Live swarm storage should keep only currently available seeders.
- A phone can announce as soon as it has one or more verified encrypted chunks.
- The announcement should include `movie_id`, `quality_code`, device id/label, and a compact list/bitmap of verified chunk numbers.
- The announcement should expire automatically, for example after `5-10` minutes unless refreshed.
- When the app comes online again, it scans local verified `.vcnr` chunks and re-announces current availability.
- If the app closes, network drops, battery policy blocks seeding, or heartbeat stops, the seeder disappears from the live tracker automatically.

Recommended production storage split:

- PostgreSQL: permanent business data and audit records.
- Redis or another TTL-capable cache: live seeder availability, chunk bitmaps, heartbeat timestamps, and temporary WebRTC assignment state.

This keeps the tracker closer to a live torrent-style `who is online now?` board instead of a huge permanent chunk ownership database.

Example live seeder record:

```text
seeder_id
user_id
movie_id
quality_code
verified_chunk_bitmap_or_compact_json
last_seen_at
expires_at
current_assignment_count
```

## Chunk source selection

When a receiver needs chunks, it can use a priority order:

1. already verified local files
2. nearby/fast peer source if available
3. normal server download

The receiver should download missing chunks in parallel only within safe mobile limits. It should avoid too many simultaneous downloads because Android memory, battery, and network switching can make the app unstable.

## Swarm safety rules

- A source can upload only chunks that match the official manifest.
- A receiver never marks a chunk complete until local verification passes.
- If a source sends corrupted or incomplete chunks repeatedly, backend can reduce trust or block it.
- A receiver should never complete from file count alone.
- Completion requires all expected manifest chunks verified locally.

## Fallback strategy

`M-P2P` should be a secondary delivery option, not the only one.

If one transfer path fails:

- use another transport path
- fall back to normal server download

This keeps the product reliable even when peer networking is blocked.

## Storage and security direction

- received VCNR files should stay in app-private storage
- the receiver should not get a prebuilt playable `.mp4`
- playback should still happen through the VCNR protected player path
- server-side release timing and entitlement rules should still control actual playback authorization

## Testing sequence for M-P2P

Before full integration into the main app, validate in this order:

1. Peer discovery between two Android phones.
2. Session pairing and authorization.
3. Small encrypted test package transfer.
4. Resume after interruption.
5. Multi-chunk integrity verification.
6. Playback from transferred VCNR package.
7. Fallback to server download when peer transfer fails.

## Immediate roadmap after this note

The current working order is:

1. keep the current mobile relay transfer as proof-of-concept
2. test transfer logic in the local simulator
3. prove resume, corruption rejection, and cross-user entitlement behavior
4. apply the proven logic back into `mobile-viewer-app`
5. only then continue deeper real-phone testing

## Status

Prototype started and working in Phase 1 as of July 23, 2026.

Current working scope:

- same user on both Android phones
- quality-specific encrypted VCNR transfer
- successful transfer and playback validation completed

See the current milestone note:

- [m-p2p-working-milestone-2026-07-23.md](D:/Python/VCNR_Web/docs/m-p2p-working-milestone-2026-07-23.md)

Local simulator:

- [m_p2p_simulator.py](D:/Python/VCNR_Web/tools/m_p2p_simulator.py)

Separate swarm test app:

- [m-p2p-swarm-test-app-note.md](D:/Python/VCNR_Web/docs/m-p2p-swarm-test-app-note.md)
- [VCNR_Swarm_Test](D:/Python/VCNR_Web/VCNR_Swarm_Test)

## Related build plan

- See [m-p2p-phase-1-build-plan.md](D:/Python/VCNR_Web/docs/m-p2p-phase-1-build-plan.md) for the concrete Phase-1 execution plan.
- See [m-p2p-direct-transport-design.md](D:/Python/VCNR_Web/docs/m-p2p-direct-transport-design.md) for the direct LAN/WebRTC/libp2p direction after the relay proof.
- See [delivery-architecture-options.md](D:/Python/VCNR_Web/docs/delivery-architecture-options.md) for the hybrid server/CDN/WebRTC swarm architecture comparison.
