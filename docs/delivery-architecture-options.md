# Delivery Architecture Options

This note compares possible delivery architectures for VCNR after the successful native WebRTC swarm prototype.

## Current proven direction

VCNR now has a working private swarm prototype:

- backend tracker creates/assigns entitled receiver sessions
- seeders announce availability by `movie_id + quality_code`
- native Android WebRTC transfers encrypted `.vcnr` chunks
- transfer can continue while both phone screens are off
- receiver verifies each chunk against the official manifest
- no unlocked `.mp4` is created by the transfer path

This is a strong foundation, but it should not be the only delivery path.

## Option 1: Server-only delivery

Flow:

- every viewer downloads all chunks from VCNR server/object storage
- queue controls release-time load

Benefits:

- simplest to reason about
- best compatibility across all networks
- easiest support/debugging

Problems:

- highest bandwidth cost
- highest release-time server pressure
- queue can become painful for popular titles
- server becomes the main bottleneck

Use case:

- fallback path
- first seed creation
- users who cannot connect to peers

## Option 2: CDN/object storage delivery

Flow:

- encrypted `.vcnr` chunks are hosted on object storage/CDN
- app downloads directly from CDN after entitlement checks

Benefits:

- much more scalable than one backend server
- fast global delivery
- predictable operations

Problems:

- bandwidth still costs money for every download
- does not reduce traffic through user sharing
- URL signing and expiry must be handled carefully

Use case:

- production official source
- fallback for weak/no swarm coverage

## Option 3: Private WebRTC swarm

Flow:

- entitled devices announce verified chunks
- receiver asks tracker for live seeders
- encrypted chunks move phone-to-phone over WebRTC when possible
- server/CDN fills missing chunks

Benefits:

- can reduce server/CDN bandwidth significantly
- scales better during popular releases after first seeders exist
- keeps server as authority while users help distribute encrypted bytes
- good fit for large movie files

Problems:

- network reliability varies
- mobile data often needs TURN relay
- battery/notification/background service rules are complex
- needs abuse controls and seeder limits

Use case:

- primary bandwidth-saving path after entitlement is proven
- best combined with server/CDN fallback

## Option 4: TURN relay

Flow:

- WebRTC uses TURN when direct peer connection fails
- encrypted chunks are relayed through TURN infrastructure

Benefits:

- improves connectivity across mobile data and strict networks
- keeps WebRTC architecture

Problems:

- TURN bandwidth costs can approach server/CDN delivery cost
- needs proper hosted TURN infrastructure
- not supported well by simple HTTP hosting platforms

Use case:

- optional premium fallback for peer connectivity
- test only after Wi-Fi/WebRTC swarm behavior is stable

## Option 5: libp2p or custom P2P stack

Flow:

- use a lower-level P2P library for peer discovery/transport

Benefits:

- more control over swarm protocols
- possible future multi-peer routing

Problems:

- higher implementation risk on mobile
- harder debugging and app-store stability concerns
- WebRTC already solves much of the browser/mobile NAT problem

Use case:

- later research path only if WebRTC cannot meet production needs

## Recommended VCNR architecture

Use a hybrid model:

1. Official server/CDN remains the authoritative source.
2. WebRTC private swarm is attempted first when live seeders exist.
3. Receiver downloads from multiple sources over time: local, peer, server/CDN fallback.
4. Seeder availability is temporary tracker state, ideally in Redis with TTL.
5. PostgreSQL stores only permanent business data: users, titles, entitlements, reservations, purchases, completed download records, audit.
6. Seeder announcements begin after the first verified chunk, not only after full completion.
7. No peer chunk is trusted until the receiver verifies it against the official manifest.

This gives VCNR reliability plus bandwidth reduction. The system should feel simple to users: `Download Now`, `Downloading securely`, `Ready to Watch`.

## Open design choices

- Whether seeding is opt-in, automatic, or controlled by settings such as Wi-Fi only and charging only.
- Maximum simultaneous receiver assignments per seeder.
- Whether TURN is worth the cost for mobile-data peer transfer.
- Whether live tracker state should be Redis from day one or start in memory for prototype/local testing.
- How to score seeders by speed, reliability, battery/network state, and recent failures.

## Current recommendation

Do not replace the official server/CDN path. Use WebRTC swarm as a peer-assisted accelerator and cost reducer, with official server/CDN fallback always available.
