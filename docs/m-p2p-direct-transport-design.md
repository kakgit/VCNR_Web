# M-P2P Direct Transport Design

Date: July 24, 2026

## Purpose

This note defines the next M-P2P direction after the working swarm relay proof.

The current relay proof uses:

`Phone B local encrypted chunks -> backend _swarm_relay folder -> Phone A local encrypted chunks`

The direct transport target is:

`Phone B local encrypted chunks -> Phone A local encrypted chunks`

In the direct target, the backend should not store another copy of user chunk files.

## What the backend should still do

Even when chunks move directly between phones, the backend remains the authority.

Backend responsibilities:

- authenticate both users
- confirm receiver entitlement for the exact `movie_id + quality_code`
- confirm sender is allowed to source that title quality
- issue a short-lived transfer session
- provide the official manifest and chunk hashes
- coordinate discovery and connection setup
- track transfer status and failures
- provide normal server download fallback when direct transfer fails
- keep playback unlock/release rules server-controlled

The backend should not trust peer claims by themselves.

Receiver completion must still require:

- official manifest
- local encrypted file exists
- local file size matches manifest
- local checksum matches manifest

## What the phones should transfer

Allowed direct payload:

- encrypted `.vcnr` chunk files
- minimal chunk metadata needed for transfer routing

Not allowed as direct payload:

- unlocked `.mp4`
- permanent passcodes
- permanent decryption keys
- ownership or purchase state

The transfer must remain a delivery shortcut, not a rights transfer.

## Recommended transport order

Use a transport-flexible design instead of betting everything on one protocol.

Priority order:

1. Already verified local chunks
2. Same Wi-Fi direct LAN transfer
3. WebRTC data channel for different networks
4. Libp2p only if it gives better discovery/reliability than WebRTC
5. Normal server download fallback

This order keeps the app reliable while still reducing server bandwidth when direct paths work.

## Production transport decision

The backend relay path is prototype-only.

It should not be integrated into `mobile-viewer-app` as a normal production delivery option because it creates extra viewer-uploaded chunk copies on the VCNR server.

Production-supported paths should be:

- official `Server -> Phone` download
- same-Wi-Fi `Phone B -> Phone A` Direct LAN transfer
- future WebRTC/libp2p-style transfer if it can move encrypted chunks without storing another full viewer copy on the backend

Production backend storage rule:

- the backend stores official producer/admin title packages
- the backend should not store duplicate viewer-seeded packages
- any temporary signaling data must be short-lived and should not include encrypted chunk payloads

## Direct LAN prototype

The first direct prototype should be same-Wi-Fi Android-to-Android.

Seeder phone:

- opens a temporary local HTTP server inside the app
- exposes only one approved transfer session
- serves only requested encrypted chunk files
- rejects unknown movie ids, quality codes, session ids, and chunk names
- shuts down after transfer completion or timeout

Receiver phone:

- asks backend for direct LAN candidates
- receives seeder local URL and short-lived source token
- requests missing chunks from seeder
- verifies each chunk before storing
- reports verified inventory back to backend
- falls back to normal server download if direct LAN fails

Direct LAN test path:

`Phone B app-private VCNR chunks -> Phone B temporary local server -> Phone A app-private VCNR chunks`

No backend chunk copy should be created in this path.

## WebRTC prototype

WebRTC should be evaluated after same-Wi-Fi direct LAN.

Backend responsibilities for WebRTC:

- create transfer session
- exchange offers/answers/candidates
- verify both sides remain entitled
- expire signaling data quickly

Phones:

- open a WebRTC data channel
- send encrypted chunks over the channel
- receiver verifies and stores chunks

WebRTC is useful when phones are not on the same Wi-Fi, but it may need STUN/TURN. TURN can create server bandwidth cost, so it should be compared against the backend relay cost.

Production preference:

- STUN-only WebRTC is preferred when it works because the backend does not carry chunk bytes
- TURN should be treated carefully because it relays traffic, but it normally does not store chunk copies
- if TURN cost is too high, fallback should be normal server download rather than persistent backend relay storage

## WebRTC prototype build start

Started on July 24, 2026 inside `VCNR_Swarm_Test`.

Backend signaling added:

- `POST /api/movies/{movie_id}/swarm/webrtc/offer`
- `POST /api/movies/{movie_id}/swarm/webrtc/answer`
- `POST /api/movies/{movie_id}/swarm/webrtc/candidate`
- `GET /api/movies/{movie_id}/swarm/webrtc/state`

Backend signaling stores only:

- SDP offer
- SDP answer
- receiver ICE candidates
- sender ICE candidates

Backend signaling does not store:

- encrypted `.vcnr` chunk payloads
- unlocked `.mp4` files
- release passcodes or permanent keys

First test target:

`Phone B app-private encrypted chunk -> WebRTC data channel -> Phone A app-private encrypted chunk`

The first app build transfers one requested missing chunk, then verifies it against the official VCNR manifest before accepting it.

Verified on July 24, 2026:

- Phone A started `Start WebRTC Receiver`
- backend accepted and stored the receiver SDP offer
- Phone B started `Start WebRTC Seeder`
- backend exchanged signaling metadata only
- Phone B sent one encrypted chunk over the WebRTC data channel
- Phone A received and verified that chunk successfully
- no backend `_swarm_relay` copy was needed for the chunk payload

Confirmed WebRTC path:

`Phone B app-private encrypted chunk -> WebRTC data channel -> Phone A app-private encrypted chunk`

Next WebRTC step:

- test the all-missing-chunk WebRTC receiver loop added after the first one-chunk proof
- keep per-chunk manifest verification before storing
- keep backend signaling-only
- compare WebRTC speed and reliability against Direct LAN

All-missing-chunk build behavior:

- Phone A requests the first missing chunk after the WebRTC data channel opens
- Phone B sends that encrypted chunk in small data-channel parts
- Phone A writes it to a temporary file
- Phone A verifies file size/checksum against the official manifest
- Phone A moves it into receiver storage only after verification
- Phone A then requests the next missing chunk
- the loop continues until receiver inventory reaches `expected_chunk_count`

Verified all-missing-chunk WebRTC transfer on July 24, 2026:

- Phone A completed at `43/43`
- all encrypted chunks were transferred over the WebRTC data channel
- each received chunk was verified before being accepted
- backend remained signaling-only for this WebRTC payload path
- no `_swarm_relay` backend chunk copy was required

Confirmed WebRTC all-chunk path:

`Phone B app-private encrypted chunks -> WebRTC data channel -> Phone A app-private encrypted chunks`

This gives VCNR three proven delivery paths:

- official server download
- same-Wi-Fi Direct LAN
- WebRTC direct data-channel transfer

## WebRTC foreground service screen-off test

Tested on July 24, 2026 with a foreground notification, partial CPU wake lock, and high-performance Wi-Fi lock around the React Native WebRTC prototype.

Result:

- both phones show the foreground transfer notification
- transfer works while both screens are on and both app screens are active
- if either phone screen turns off, the WebRTC transfer pauses
- transfer resumes after both phones wake and both app screens become active again
- receiver completion can stop the receiver notification
- sender notification now receives a receiver completion signal, but true background transfer still needs native ownership of the transfer loop

Conclusion:

The current foreground service wrapper is not enough because the WebRTC data-channel loop still runs in the React Native JavaScript runtime. Android can keep the service alive, but it can still pause/throttle the JS/WebRTC work when the app is backgrounded or the screen is off.

Production direction:

- move the actual transfer engine into Android native foreground service
- keep React Native as UI/progress/control only
- native service should own connection, chunk send/receive, file verification, resume, notification progress, network-change recovery, wake lock, and Wi-Fi lock
- until this is done, WebRTC P2P should be treated as foreground-active-screen only

## Native background Direct LAN engine milestone

Verified on July 24, 2026 in `VCNR_Swarm_Test`.

What was built:

- Android native foreground seeder service
- Android native foreground receiver service
- CPU wake lock and Wi-Fi lock while transfer is active
- native socket serving of encrypted chunks from app-private storage
- native receiver download loop
- native file writing into app-private receiver storage
- native MD5/size verification before accepting each chunk
- React Native screen reduced to control/status only

Test result:

- encrypted chunks transferred within a few seconds on the same Wi-Fi
- transfer continued even when phone screens were off
- receiver completed and verified the files
- no unlocked `.mp4` file was created
- this confirms the native foreground service architecture is correct for background-capable transfer

Confirmed native Direct LAN path:

`Phone B native foreground source -> same-Wi-Fi socket -> Phone A native foreground receiver`

Important boundary:

This proves the native background transfer engine, but it is still same-Wi-Fi/LAN only. It does not solve mobile-data or different-network transfer.

Next internet/mobile-data phase:

- move from LAN socket to native WebRTC/TURN or another live internet transport
- keep backend signaling-only where possible
- if TURN is required, TURN should relay encrypted chunk bytes live but not store viewer chunk files
- reuse the native receiver verification and foreground-service progress model proven here

## Libp2p note

Libp2p can still be explored, but it should not be the first direct transport unless it clearly reduces complexity.

Reasons to be careful:

- React Native support can be uneven
- NAT traversal still needs relay infrastructure in many real mobile networks
- mobile battery and background limits matter
- debugging can be slower than WebRTC or simple LAN HTTP

Best use for libp2p later:

- peer identity
- source discovery
- swarm routing
- future multi-source chunk scheduling

## Security rules

Every direct transfer session must be:

- short-lived
- scoped to one `movie_id`
- scoped to one `quality_code`
- scoped to approved sender and receiver devices
- revocable by backend
- unable to expose files outside the app-private VCNR package folder

Every chunk request must be checked against:

- session id
- source token
- chunk name safety
- official manifest membership
- receiver missing inventory

## Product behavior

The user-facing flow should not expose transport complexity.

User sees:

- `Download from nearby device`
- `Use server fallback if needed`
- progress and source summary

Internal app decides:

- direct LAN
- WebRTC
- server

## Next implementation step

Before integrating into `mobile-viewer-app`, complete direct LAN plus WebRTC/libp2p exploration in `VCNR_Swarm_Test`.

Direct LAN build is now proven. Next suggested build:

1. Keep Direct LAN as the same-Wi-Fi baseline.
2. Add WebRTC signaling endpoints to the backend.
3. Add WebRTC sender/receiver mode to `VCNR_Swarm_Test`.
4. Transfer one encrypted chunk over WebRTC data channel.
5. Expand WebRTC to all missing chunks.
6. Compare WebRTC against Direct LAN for reliability and speed.
7. Evaluate libp2p only if it solves a problem WebRTC does not solve.

Success criteria:

- Phone A receives at least one encrypted chunk directly from Phone B without `_swarm_relay`.
- Phone A verifies the direct chunk by manifest size/hash.
- `_swarm_relay` remains empty during the direct LAN test.
- Receiver can still fall back to normal server download if direct transfer fails.

## Related notes

- [m-p2p-working-milestone-2026-07-23.md](D:/Python/VCNR_Web/docs/m-p2p-working-milestone-2026-07-23.md)
- [m-p2p-design-note.md](D:/Python/VCNR_Web/docs/m-p2p-design-note.md)
- [m-p2p-swarm-test-app-note.md](D:/Python/VCNR_Web/docs/m-p2p-swarm-test-app-note.md)
