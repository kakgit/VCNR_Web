# VCNR Swarm Test App Note

Date: July 23, 2026

## Purpose

`VCNR_Swarm_Test` is a separate Android/Expo test app for the torrent-style VCNR delivery idea.

It exists so swarm delivery can be tested without disturbing the main `mobile-viewer-app`.

## Why separate first

The swarm system has hard problems that should be isolated first:

- chunk discovery
- multiple possible sources
- resume after interruption
- corrupted chunk rejection
- verified local inventory
- background/network switching behavior
- future entitlement-controlled cross-user delivery

Testing these inside the full viewer app is too slow because every bug gets mixed with login, title details, delivery dates, player state, and APK installation.

## Version 0.1 scope

The first version is an on-device lab.

It can:

- log in to the VCNR backend
- accept `movie_id` and `quality_code`
- generate fake encrypted VCNR chunk files
- distribute chunks across simulated sources named `server`, `peer-a`, and `peer-b`
- download missing chunks into a receiver folder
- resume from already verified receiver chunks
- verify every chunk by size and MD5
- delete corrupted receiver chunks and replace them
- confirm that no `.mp4` is created

## What this proves

This proves the swarm rules before real peer networking:

- completion must be based on verified chunks, not file count alone
- receiver can safely resume from existing verified chunks
- corrupted chunks should not be trusted
- the transfer layer can be source-flexible
- the receiver package remains encrypted

## Next versions

Recommended next steps:

1. Add backend tracker APIs for chunk availability.
2. Add real device identity and entitled receiver checks.
3. Allow one test phone to publish verified chunk inventory.
4. Allow another test phone to request missing chunks.
5. Keep official server download and Direct LAN as the preferred proven transfer paths.
6. Treat backend relay as lab-only because it stores duplicate viewer chunk copies.
7. Explore WebRTC/libp2p without backend chunk storage.
8. Integrate the proven direct-transfer engine into `mobile-viewer-app` only after WebRTC/libp2p exploration.

## Local folder

- [VCNR_Swarm_Test](D:/Python/VCNR_Web/VCNR_Swarm_Test)
