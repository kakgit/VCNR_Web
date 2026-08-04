# M-P2P Working Milestone

Date: July 23, 2026

## Milestone reached

VCNR now has a working Phase-1 `M-P2P` transfer flow inside the main `mobile-viewer-app`.

This working milestone was verified with:

- two Android phones
- the same signed-in VCNR viewer account
- one selected title
- one selected title quality
- encrypted VCNR chunk transfer only
- successful playback on both phones after transfer

## What is now working

The current working flow is:

1. Receiver opens `M-P2P Transfer`.
2. Receiver generates a short pairing code.
3. Sender enters that code and starts sender flow.
4. Backend confirms same-user, same-title, same-quality pairing.
5. Sender publishes local encrypted chunk inventory.
6. Sender publishes the encrypted manifest for that title quality.
7. Sender relays encrypted chunk files through the current temporary transfer path.
8. Receiver syncs the missing encrypted chunks into the normal VCNR app storage path.
9. Receiver marks the encrypted package complete on that device.
10. Both phones can use the normal VCNR playback flow.

## Important security result

This milestone confirms the main product rule:

- the transferred package remains encrypted
- no unlocked full movie file is required for the transfer flow
- playback still stays inside the VCNR protected app path

## Current implementation scope

The current implementation is intentionally narrow:

- Android only
- same user only
- one title at a time
- one quality at a time
- temporary Cloudflare/local backend testing path
- relay-backed encrypted transfer session

This is acceptable for the current prototype stage because it proves the product behavior first.

## Current transport note

The current transfer is not yet final direct phone-to-phone transport.

For this milestone:

- pairing and transfer control are backend-managed
- encrypted chunks are relayed through the current local backend transfer session
- the result still proves protected encrypted package movement between phones

This was the fastest safe path for repeated test iterations.

## Current cleanup/completion behavior

When receiver inventory matches sender inventory:

- the transfer session moves to `completed`
- temporary relay files for that session are cleared from the backend side
- the receiver keeps the completed encrypted VCNR package locally

## What has been proven

- pairing works
- title-quality matching works
- encrypted manifest handoff works
- sender inventory publish works
- receiver missing-chunk sync works
- transferred encrypted files play successfully on the second phone

## Swarm test app milestone

The separate `VCNR_Swarm_Test` app now proves the first torrent-style delivery behavior against the VCNR backend tracker.

Verified on July 23, 2026:

- receiver resumed from a previously disconnected session at `14/43` chunks
- receiver did not restart the package from zero
- server/tracker-assisted chunk sync continued only for missing encrypted chunks
- real per-chunk progress was visible while each chunk was downloading
- chunk integrity was checked before accepting files into receiver storage
- tracker inventory was reported every `10` verified chunks
- package completed successfully at `43/43` encrypted chunks
- no `.mp4` file was created during the transfer test

Current test transport:

- backend tracker-assisted
- encrypted VCNR chunks only
- server source currently used as the real source while peer-source logic is developed
- controlled parallel download lanes, initially `3`

Next speed test:

- increase real server chunk lanes from `3` to `5`
- compare phone stability, backend stability, and completion speed
- avoid unlimited parallel downloads until we confirm safe limits on real phones and live hosting

## Swarm relay milestone

The `VCNR_Swarm_Test` app proved a peer-assisted relay flow using two phones and the VCNR backend tracker.

This milestone is now marked prototype-only. It should not be used as the production delivery direction because it stores viewer-uploaded duplicate encrypted chunk copies on the backend.

Verified on July 23, 2026:

- Phone B first downloaded the encrypted VCNR package from the server
- Phone A created a tracker session as the receiver
- Phone B pasted Phone A's tracker session id
- Phone B uploaded its verified encrypted `.vcnr` chunks into the temporary backend swarm relay
- backend accepted only chunks matching the official manifest size/hash
- Phone A discovered both `server:43` and `peer_relay:43`
- Phone A downloaded using `5` parallel lanes from `peer relay`
- Phone A completed the transfer at `43/43`

Current relay path:

`Phone B local encrypted chunks -> backend _swarm_relay folder -> Phone A local encrypted chunks`

Current temporary backend storage:

`media/library/_swarm_relay/{session_id}/{source_id}/`

Important result:

- the relay stores encrypted `.vcnr` chunk copies only
- no unlocked `.mp4` is uploaded to the relay
- the receiver still verifies every chunk before accepting it
- this proves swarm behavior before direct LAN/WebRTC/libp2p transport is added

Production decision:

- do not integrate backend relay as a normal `mobile-viewer-app` delivery path
- keep backend relay code only as lab/prototype reference unless later removed
- production should use official server download plus direct device transfer options

Future direct transport target:

`Phone B local encrypted chunks -> Phone A local encrypted chunks`

In that future direct path, the backend should not store another copy of user chunks. It should only handle entitlement, session permission, manifest rules, source discovery, and status.

## Fresh two-phone relay test sequence

Verified again on July 24, 2026 after clearing:

- `media/library/_swarm_relay`
- `media/library/_transfer_relay`
- `VCNR_Swarm_Test` app data on both phones

Fresh test order:

1. Phone B logged in first.
2. Phone B created a receiver session.
3. Phone B used `Download Missing` to download `43/43` encrypted chunks from the server.
4. Phone A logged in.
5. Phone A created a new receiver session.
6. Phone A's tracker session id was copied.
7. Phone B pasted Phone A's tracker session id.
8. Phone B used `Seed Relay From This Phone`.
9. Phone B uploaded `43/43` verified encrypted chunks into the temporary swarm relay.
10. Phone A used `Find Sources`.
11. Phone A discovered `server:43` and `peer_relay:43`.
12. Phone A used `Download Missing`.
13. Phone A downloaded using `5` parallel lanes from `peer relay`.
14. Phone A completed `43/43`.

This confirms the clean-room test behavior:

- the first server download can create the first seeder
- a second receiver can get the same package through peer relay
- the relay source is selected ahead of server fallback
- clearing old app/server relay files does not break the flow
- this relay flow remains prototype-only because it stores duplicate viewer chunk copies on the backend

## Direct LAN milestone

Verified on July 24, 2026:

- Phone B already had the encrypted VCNR package locally
- Phone B started `Direct LAN Prototype -> Start Direct Source`
- Phone A had missing encrypted chunks
- Phone A logged in and created a tracker session only for permission and official manifest access
- Phone A used Phone B's local LAN URL and token
- Phone A first downloaded one encrypted chunk directly from Phone B
- Phone A verified that chunk using the official manifest
- Phone A then downloaded all missing chunks directly from Phone B
- direct transfer ran at local Wi-Fi speed
- no backend `_swarm_relay` upload was required for this direct path

Direct LAN path proven:

`Phone B app-private encrypted chunks -> Phone B local LAN server -> Phone A app-private encrypted chunks`

Important result:

- the backend was still used for login, tracker session, and manifest/hash rules
- chunk bytes did not need to be copied into `_swarm_relay`
- no unlocked `.mp4` was transferred
- this is the first working direct phone-to-phone encrypted chunk transfer path

Follow-up UI note:

- the first all-chunk Direct LAN run showed status flickering because all `5` parallel download callbacks updated the same status line
- the status display was updated to throttle text updates and show a calmer summary

## What is not done yet

These items still remain for future iterations:

- stronger interrupted-transfer resume handling
- better sender/receiver completion UI
- more explicit stale-session cleanup
- cross-user entitlement-controlled transfer
- WebRTC/libp2p exploration without backend chunk storage
- production transport selection between server download, direct LAN, WebRTC, and possibly libp2p

## WebRTC prototype status

Started on July 24, 2026 in the separate `VCNR_Swarm_Test` app.

Current build:

- adds native `react-native-webrtc` support to the test APK
- adds backend WebRTC signaling endpoints for offer, answer, candidates, and state
- keeps the backend as signaling-only for this path
- sends no encrypted chunk payloads through `_swarm_relay`
- tests one missing encrypted chunk over a WebRTC data channel first
- receiver verifies the chunk by official manifest size/hash before storing it

This is not yet the final production transfer path. It is the next lab step after Direct LAN so we can decide whether WebRTC is reliable enough before integrating M-P2P into `mobile-viewer-app`.

Verified on July 24, 2026:

- Phone A clicked `Start WebRTC Receiver`
- Phone A showed `WebRTC receiver offer published`
- Phone B clicked `Start WebRTC Seeder`
- Phone B showed that it sent one chunk file
- Phone A verified and received one encrypted chunk file

This proves the first WebRTC no-relay payload path:

`Phone B local encrypted chunk -> WebRTC data channel -> Phone A local encrypted chunk`

Important result:

- backend only handled signaling metadata
- chunk bytes did not go through `_swarm_relay`
- receiver still accepted the chunk only after official manifest verification

All-chunk WebRTC result verified on July 24, 2026:

- receiver completed at `43/43`
- WebRTC transferred all missing encrypted chunks
- the backend stayed signaling-only for payload transfer
- no duplicate viewer chunk package was stored in `_swarm_relay`
- this proves a second direct phone-to-phone path in addition to Direct LAN

Current proven production-candidate paths:

- official `Server -> Phone`
- same-Wi-Fi `Phone B -> Phone A Direct LAN`
- WebRTC `Phone B -> Phone A data channel`

## Native background transfer milestone

Verified on July 24, 2026 after the JavaScript/WebRTC foreground-service wrapper test failed to continue with screen off.

Confirmed result:

- Android native foreground source service can seed encrypted chunks
- Android native foreground receiver service can download encrypted chunks
- transfer continues when phone screens are off
- each received chunk is size/hash verified before acceptance
- no `.mp4` file is created during transfer
- React Native is now only the control/status screen for this native Direct LAN path

This proves the architecture needed for VCNR mobile background transfer:

`native foreground service owns transfer -> React Native displays status`

Important boundary:

The confirmed native path is same-Wi-Fi Direct LAN. The next major milestone is internet/mobile-data transfer using native WebRTC/TURN or another live transport that avoids storing viewer chunk copies on the backend.

## Recommended next order

1. keep official `Server -> Phone` and native same-Wi-Fi `Phone B -> Phone A Direct LAN` as proven paths
2. build internet/mobile-data transfer using native WebRTC/TURN or equivalent live transport
3. verify no backend chunk copies are created for future device-transfer paths
4. improve mobile transfer UI and recovery using the proven native service rules
5. only then integrate M-P2P into `mobile-viewer-app`

## Important direction update

The term `M-P2P` now means peer-assisted encrypted delivery, not only pure direct phone-to-phone networking.

This is intentional because real users may be on:

- mobile data
- home Wi-Fi
- different networks
- networks that block direct peer connections

So the final transfer layer should be transport-flexible, but it should avoid backend storage of viewer-uploaded chunk copies.

Production acceptable paths:

- official server download
- direct LAN
- WebRTC/libp2p-style transfer if it does not store duplicate viewer chunk payloads on the backend

VCNR's security rules must always hold:

- receiver is entitled
- selected `quality_code` matches
- encrypted chunks are verified by manifest size/hash
- playback still needs server unlock
- no open `.mp4` file is transferred

## Local simulator

A first local simulator has been added:

- [m_p2p_simulator.py](D:/Python/VCNR_Web/tools/m_p2p_simulator.py)

It tests:

- same-user complete transfer
- interrupted transfer resume
- different entitled user transfer
- different non-entitled user rejection
- corrupted chunk rejection

## Related files

- [m-p2p-design-note.md](D:/Python/VCNR_Web/docs/m-p2p-design-note.md)
- [m-p2p-phase-1-build-plan.md](D:/Python/VCNR_Web/docs/m-p2p-phase-1-build-plan.md)
- [future-cleanup.md](D:/Python/VCNR_Web/docs/future-cleanup.md)
