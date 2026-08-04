# M-P2P Phase-1 Build Plan

Date: July 23, 2026

## Purpose

This document turns the earlier M-P2P design direction into a concrete Phase-1 implementation plan for VCNR.

The goal of Phase 1 is to prove that one Android phone can transfer an already-downloaded VCNR title package to another Android phone without sending a full unlocked movie file.

## Phase-1 goal

Allow:

- Android to Android transfer
- same entitled viewer account on both devices
- one title at a time
- one quality at a time
- encrypted VCNR chunk transfer only
- normal server-controlled playback unlock after transfer

## Future direction after Phase 1

The long-term VCNR target is broader than same-user transfer.

Future M-P2P should support:

- user-to-user transfer between different viewers
- but only when the receiving viewer is independently entitled to that title quality
- torrent-style controlled swarm delivery where many entitled devices can source different encrypted chunks

Important platform rule:

- M-P2P transfers encrypted VCNR package bytes
- M-P2P does not transfer title ownership
- the receiving user must still be verified by the backend before playback

Do not allow in Phase 1:

- unlocked `.mp4` transfer
- cross-user sharing
- public sharing links
- iPhone support

Reason:

- same-user transfer is the safest first engineering phase
- future cross-user delivery needs stronger backend authorization rules

## Why this phase matters

This phase proves the most important product requirement first:

- VCNR files can move device-to-device
- but playback still stays protected
- and the system does not rely on creating a full open movie file

## Phase-1 boundaries

Keep the first implementation narrow:

- Android only
- same user on both phones
- local Wi-Fi first
- single transfer session at a time
- single movie and single quality per session

This avoids mixing too many hard problems at once.

## Core transfer key

All transfer sessions should stay tied to:

- `movie_id`
- `user_id`
- `quality_code`

Reason:

- delivery and reservation are already quality-specific
- each quality has different file counts and size
- star logic also depends on the selected quality

## Viewer flow

### Receiver flow

1. Viewer signs in on receiver phone.
2. Viewer opens `Transfer from Another Device`.
3. App generates a pairing code or QR session.
4. Receiver waits for sender approval.
5. Receiver receives manifest summary.
6. Receiver checks which encrypted chunks are already present locally.
7. Receiver requests only missing chunks.
8. Receiver stores transferred VCNR files in app-private storage.
9. Receiver verifies package completeness.
10. Receiver uses normal VCNR playback flow after server unlock validation.

### Sender flow

1. Viewer signs in on sender phone.
2. Viewer opens `Send Downloaded Title`.
3. App shows locally available downloaded titles.
4. Viewer selects one title and one quality.
5. Viewer enters or scans the receiver pairing code.
6. Sender waits for backend approval.
7. Sender shares manifest summary.
8. Sender transfers only the missing encrypted chunks requested by the receiver.
9. Sender marks transfer complete.

## Main screens

### Receiver app screens

- `Transfer from Another Device`
- pairing code / QR session screen
- incoming transfer progress screen
- transfer complete screen
- resume interrupted transfer screen

### Sender app screens

- `Send Downloaded Title`
- local downloaded-title list
- title-quality picker
- pairing code entry / scan screen
- outgoing transfer progress screen

## Backend responsibilities

In Phase 1, the backend should control trust and authorization only.

Backend must:

- authenticate both devices
- verify that both devices belong to the same entitled viewer account
- verify `movie_id` entitlement
- verify `quality_code` entitlement
- create a short-lived transfer session
- issue short-lived transfer tokens
- track transfer status
- keep audit history

Backend should not:

- relay the chunk file bytes during Phase 1
- create unlocked playback files

## Cross-user rule for future phases

When Phase 1 is complete, the backend should later expand to support:

- sender user ID
- receiver user ID
- receiver entitlement validation
- title-quality authorization checks
- delivery-policy approval before peer transfer starts

That means in future phases:

- any user can potentially become a delivery source
- but only entitled receivers can complete playback

## Mobile responsibilities

### Sender responsibilities

- confirm the encrypted VCNR package exists locally
- load the local manifest
- expose the available chunk list
- send only the receiver’s missing chunks

### Receiver responsibilities

- start the pairing request
- receive manifest summary
- compare local files against sender manifest
- request only missing chunks
- write received encrypted chunks into VCNR app storage
- verify package completeness before marking ready

## Storage rules

Receiver must store:

- `manifest.json`
- encrypted chunk files
- transfer state file

Receiver must not create:

- unlocked full `.mp4` output

The transferred package should remain in app-private storage, just like normal VCNR download storage.

## Playback rules

After transfer, playback should still require:

- normal release-date validation
- normal entitlement validation
- normal passcode / unlock authorization from server

Transferred encrypted chunks alone must not bypass the VCNR release gate.

This rule will stay true even in future cross-user transfer phases.

## Transport direction

### Phase-1 transport recommendation

The current direction is transport-independent.

Phase 1 may use:

- Wi-Fi internet
- mobile data internet
- direct LAN
- future WebRTC/libp2p if it avoids backend chunk storage
- normal server download fallback

Reason:

- the first goal is to prove safe encrypted package movement
- real users may not be on the same LAN
- the same transfer rules should work over any byte transport
- backend relay was useful as a lab proof, but it should not become a production path because it stores duplicate viewer chunk copies

### Libp2p direction

`libp2p` remains a possible future direction, but WebRTC should be explored first unless libp2p clearly solves a problem WebRTC does not solve.

Recommended order:

1. prove transfer logic first
2. prove resume and integrity first
3. keep Direct LAN as the same-Wi-Fi baseline
4. explore WebRTC/libp2p before `mobile-viewer-app` integration
5. ensure future device-transfer paths do not store viewer chunk copies on the backend

This reduces risk and makes debugging easier.

## Transfer logic

The basic transfer logic should be:

1. sender reads local manifest
2. receiver reads local manifest or local chunk state
3. receiver compares missing chunk names
4. receiver requests only missing chunk files
5. sender streams requested encrypted chunks
6. receiver writes chunks atomically
7. receiver updates transfer state after each successful chunk
8. receiver verifies final chunk count and manifest match

## Torrent-style upgrade path

After the simple relay/pairing proof-of-concept is stable, upgrade the model from one sender to many possible sources.

The future transfer logic should become:

1. receiver asks backend for missing chunks
2. backend returns available sources for those chunks
3. receiver chooses source per chunk
4. receiver downloads a chunk from server, relay, or another entitled device
5. receiver verifies size/hash against official manifest
6. receiver marks only verified chunks complete
7. receiver reports verified inventory back to backend
8. receiver can later source those same verified chunks to other entitled receivers

This creates a private VCNR swarm.

The swarm must remain controlled:

- no public torrent files
- no open trackers
- no `.mp4` payloads
- no playback secrets from peers
- backend entitlement is always required
- official manifest hash verification is always required

## Resume behavior

Phase 1 should support interrupted transfer resume.

If transfer stops:

- receiver keeps already transferred encrypted chunks
- receiver keeps transfer state
- next session should continue from missing chunks only

This is important for larger titles.

## Security rules

- transfer session must expire quickly
- both devices must be authenticated
- transfer must stay quality-specific
- only encrypted chunks may move
- playback unlock remains server-controlled

For future any-user transfer:

- sender trust is not enough by itself
- receiver entitlement must always be checked by backend
- peer transfer must never be treated as purchase or ownership transfer

## Recommended backend API scope

Phase-1 backend endpoints should cover:

- create receiver pairing session
- validate sender pairing code
- approve transfer session
- report transfer status
- close or expire transfer session

The backend can later be expanded with richer auditing and device history.

## Recommended implementation order

1. keep the current mobile M-P2P relay prototype as proof-of-concept
2. build local simulator tests for manifest, chunk inventory, resume, and integrity
3. validate different-user entitlement rules in the simulator
4. apply the proven rules back into the mobile app
5. verify playback from transferred VCNR package
6. only then evaluate direct LAN, WebRTC, or `libp2p`

## Testing plan

### Small-title test first

Use one smaller VCNR title first:

- shorter runtime
- smaller chunk count
- faster repeat tests

Validate:

- pairing
- chunk transfer
- resume
- package completion
- playback authorization

### Larger-title test second

After that, test one larger title:

- higher chunk count
- longer transfer time
- stronger resume requirement

Validate:

- stability
- resume after interruption
- storage correctness
- playback performance

## Known risks

- Android background restrictions
- local Wi-Fi discovery complexity
- interrupted transfer cleanup
- manifest mismatch cases
- device storage pressure

These should be treated as expected engineering risks, not as blockers to starting Phase 1.

## Immediate next step

Do not start coding M-P2P yet if current localhost title-flow validation is still incomplete.

First:

- finish the remaining core localhost features
- validate multi-title behavior
- then begin the M-P2P Phase-1 prototype

## Status

Phase-1 prototype is now working in a first real form as of July 23, 2026.

Current verified scope:

- same-user transfer works
- encrypted chunk package transfer works
- receiver playback after transfer works

Still remaining:

- stronger resume handling
- cleanup/recovery polish
- cross-user entitlement-controlled transfer
- transport cost/performance comparison

Current simulator:

- [m_p2p_simulator.py](D:/Python/VCNR_Web/tools/m_p2p_simulator.py)

Reference:

- [m-p2p-working-milestone-2026-07-23.md](D:/Python/VCNR_Web/docs/m-p2p-working-milestone-2026-07-23.md)
