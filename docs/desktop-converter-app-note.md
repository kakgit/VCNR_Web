# Desktop VCNR Converter App Note

## Purpose

Keep this as a future architecture note for the VCNR platform.

The idea is to build a separate desktop converter application that prepares upload-ready VCNR content packages outside the web admin panel.

## Why this is useful

- heavy media conversion is better handled on desktop than in the browser
- FFmpeg-based conversion is easier to control locally
- chunking and VCNR encryption can happen before upload
- the web admin panel stays simpler
- the server stores ready-to-deliver encrypted packages by quality
- the mobile viewer app can stay focused on download, entitlement, and protected playback

## Proposed flow

### 1. Desktop Converter App

Input:

- MP4
- MKV
- WMV
- MOV
- other supported source video files

Responsibilities:

- convert source video into required viewer qualities such as `480p`, `720p`, `1080p`
- use FFmpeg for media conversion
- split output into VCNR chunk files
- encrypt chunk files with passcode-based protection
- generate manifest files
- export a clean folder structure for upload

## 2. Web Admin Panel

Responsibilities:

- upload prepared VCNR package folders/files
- assign stars by quality
- set publish date and release timing
- manage title availability

## 3. Server

Responsibilities:

- store prepared encrypted VCNR packages by title and quality
- control release date and publish timing
- control entitlement and star-based access
- provide password or unlock authorization only after release conditions are met

## 4. VCNR Mobile Viewer App

Responsibilities:

- let the viewer select the title quality
- download only the entitled quality package after publish date
- store chunk files locally in app storage
- request password/unlock authorization from the server
- play only local protected files through the native VCNR player

## Why this architecture is better

- desktop app handles content preparation
- admin panel handles catalog and release control
- server handles entitlement and release security
- mobile app handles protected delivery and playback

This is cleaner and more scalable than trying to run the full conversion and encryption pipeline inside the web admin workflow.

## Recommended future scope for the desktop app

- source file picker
- quality profile selection
- passcode/encryption setup
- VCNR chunk generation
- manifest generation
- export/upload-ready folder structure
- optional local validation before upload

## Status

This is only a planning note for now.

The current focus remains:

- improving Android native protected playback
- validating larger movie files
- evolving `VCNR_Android_Player` toward direct native chunk playback
