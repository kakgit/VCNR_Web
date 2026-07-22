# M-P2P Design Note

Date: July 22, 2026

## Purpose

This note captures the planned `M-P2P` direction for VCNR as a future track after the current `VCNR_Web` delivery flow is stabilized and hosted publicly.

`M-P2P` here means:

- mobile-to-mobile peer-to-peer transfer
- only for protected VCNR encrypted chunk packages
- not for unlocked full movie files

## Current decision

Do not start `M-P2P` implementation inside the main viewer flow yet.

First complete these milestones:

1. Finish the current `VCNR_Web` viewer and admin work.
2. Deploy the backend/app-support flow to Railway.
3. Test delivery and playback with a few shorter real titles, ideally around `1 hour` or less.
4. Confirm the stable direct VCNR player behavior across multiple test titles.
5. Only after that, begin the `M-P2P` prototype track.

## Why we are delaying it slightly

- The current direct download and direct VCNR playback path is now becoming stable.
- `M-P2P` adds a second delivery path and should not disturb the existing stable baseline.
- Mobile peer-to-peer behavior is harder than normal server download because of:
  - NAT/firewall restrictions
  - background limitations
  - mobile network switching
  - relay fallback needs
  - battery and Android execution policies

So the right order is:

- stabilize server delivery first
- verify with smaller real movies
- then begin `M-P2P`

## High-level M-P2P goal

Allow one mobile device to transfer already downloaded VCNR encrypted chunk packages to another entitled mobile device without sending a full unlocked movie file.

This should support:

- faster local transfer when two devices are near each other
- reduced repeated server bandwidth usage
- same entitlement and release-date protection rules
- reuse of the existing VCNR player on the receiving device

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

1. Receiver signs in.
2. Receiver opens a `Transfer from another device` option.
3. Receiver generates a short pairing code or QR session.
4. Sender opens `Send to another device`.
5. Sender scans or enters the pairing code.
6. Backend verifies both devices and the entitled title-quality package.
7. A transfer session is approved.
8. Devices connect directly if possible.
9. Sender shares manifest summary and receiver reports which chunks are missing.
10. Sender transfers only missing encrypted chunks.
11. Receiver writes chunks into app-private VCNR storage.
12. Receiver verifies package completeness.
13. Playback still requires the normal release and unlock checks before play.

## Transport direction

Current recommended research path:

- prototype with `libp2p`

Why:

- it is built for peer-to-peer networking
- it supports relay and NAT-traversal strategies
- it is a realistic starting point for mobile peer discovery and direct transfer research

Research caution:

- mobile React Native / Expo compatibility will need care
- we may need native Android support if Expo-only behavior becomes limiting
- relay fallback may still be needed in some real-world networks

## Fallback strategy

`M-P2P` should be a secondary delivery option, not the only one.

If direct peer-to-peer fails:

- fall back to normal server download
- or fall back to a server-assisted transfer mode later if needed

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

1. finish `VCNR_Web`
2. deploy to Railway
3. download a few shorter real movies for testing
4. convert/package those for VCNR tests
5. verify stable delivery and playback
6. start `M-P2P` prototype work

## Status

Planning note only.

Not yet started for implementation.
