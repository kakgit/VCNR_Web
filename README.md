---
title: Cine Vault
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# Cine Vault

Cine Vault is a movie discovery, reservation, and secure screening platform. The stack direction is now:

- `JavaScript frontend` for the browser UI and VCNR playback flow
- `Python backend` for auth, publishing, admin workflows, and business logic
- `PostgreSQL` as the long-term system database

The current repo still contains the working frontend shell plus a new FastAPI backend skeleton so both sides can now evolve together.

## Current Structure

Frontend files:

- `index.html` - Phase 1 product shell
- `styles.css` - dark-mode Cine Vault UI system
- `app.js` - viewer, producer, admin, and screening interactions
- `mp4_segments.js` - fragmented MP4 reconstruction for VCNR playback
- `server.js` - simple Node static server for the current frontend

Backend files:

- `backend/main.py` - FastAPI app entrypoint
- `backend/api/routes.py` - Phase 1 API routes
- `backend/core/config.py` - environment-driven settings
- `backend/db.py` - PostgreSQL engine bootstrap
- `backend/data/demo_store.py` - demo movie and queue data until real persistence is added
- `backend/schemas.py` - request and response models

Environment and dependencies:

- `.env.example` - local environment template
- `requirements.txt` - Python backend dependencies
- `package.json` - frontend metadata and static frontend run script

## Phase 1 Backend Goals

The new Python backend is ready to grow into:

- viewer auth
- producer publishing workflows
- admin review workflows
- movie catalog APIs
- reward system APIs
- PostgreSQL-backed persistence

Current placeholder endpoints:

- `GET /api/health`
- `GET /api/platform/summary`
- `GET /api/movies`
- `POST /api/auth/login`
- `GET /api/producer/queue`
- `POST /api/producer/publish`
- `GET /api/admin/review-queue`

These are demo-safe backend placeholders, not final production logic.

## How To Run

### Frontend only

Use the current static frontend flow:

```bash
npm start
```

Then open:

```text
http://localhost:3000
```

### Python backend

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the FastAPI app:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Then open:

```text
http://localhost:8000
```

The backend currently mounts the frontend files directly, so the app can be served through FastAPI as the stack converges.

## Deployment (Render only)

Render is the sole deployment platform for `VCNR_Web`.

### One-click Render Blueprint deploy

The repo includes a root `render.yaml` blueprint that creates:

- the `vcnr-web` web service (Docker, free tier)

PostgreSQL is **no longer created on Render** — it runs on Railway
(<https://railway.com>). See `docs/free-hosting-guide.md` for the full migration.
In short: create a PostgreSQL database on Railway, enable **Public Access**
(Settings → Networking → TCP Proxy) on it, and copy the generated
`DATABASE_PUBLIC_URL` public connection string.

Deploy steps:

1. Push this repo to GitHub.
2. In the Render dashboard: **New + → Blueprint → select this repo**.
3. Render creates the web service.
4. Set `DATABASE_URL` (below) from the Railway public connection string.
5. Open `https://vcnr-web.onrender.com/api/health` (or the assigned subdomain).

### Environment variables

`FRONTEND_ORIGIN` is auto-detected from `RENDER_EXTERNAL_URL`, which Render sets
automatically. No manual frontend origin setup is needed.

The only required manual variable is:

```text
DATABASE_URL=<Railway PostgreSQL public connection string>
```

The blueprint declares this variable with `sync: false`, so you enter the value in
the Render dashboard **Environment** tab and it is never stored in git. Paste the
`DATABASE_PUBLIC_URL` that Railway generates after you enable Public Access /
TCP Proxy (see `docs/free-hosting-guide.md`). The backend's
`_normalize_database_url` accepts Railway's `postgresql://` string as-is and
rewrites the scheme for psycopg, keeping the `sslmode` query parameter.

Recommended service variables (already set by the blueprint):

```text
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
SWARM_STUN_URL=stun:stun.l.google.com:19302
```

Optional swarm connectivity:

```text
SWARM_TURN_URL=
SWARM_TURN_USERNAME=
SWARM_TURN_CREDENTIAL=
```

Optional public torrent trackers (comma-separated):

```text
PUBLIC_TORRENT_TRACKERS=udp://tracker.opentrackr.org:1337/announce,udp://open.stealth.si:80/announce
```

### Important note

The backend already calls `init_db()` on startup, so the current SQLAlchemy tables and compatibility columns will be created automatically when the database is reachable.

### Free tier caveats

- Service sleeps after 15 min idle, wakes in ~50s on first request.
- PostgreSQL runs on Railway (trial ~$5 credit, then Hobby at $5/month). Railway
  bills egress for traffic through the public TCP proxy; API traffic is small, so
  keep large media transfers on R2.

## PostgreSQL Direction

The project is now being shaped for PostgreSQL-backed data such as:

- users
- roles
- movies
- movie assets
- producer submissions
- admin approvals
- rewards and point ledgers
- bookings and secure screening access

The database connection is configured through:

- `DATABASE_URL`

Example:

```text
postgresql://postgres:postgres@altaria.proxy.rlwy.net:34062/railway?sslmode=require
```

(The backend's `_normalize_database_url` rewrites `postgresql://` to
`postgresql+psycopg://` automatically, so the Railway public string works as-is.)

## VCNR Notes

The current secure screening vault still supports:

- HLS live streams
- VCNR v3 encrypted files
- local passcode-based decryption in the browser

VCNR support follows:

- `VCNRCMP3`
- `PBKDF2-HMAC-SHA256`
- `AES-256-GCM`
- fragmented MP4 reconstruction for playback

## Recommended Next Steps

1. Push the current project snapshot to GitHub.
2. Confirm the Render web service builds from the root `Dockerfile`.
3. Confirm `DATABASE_URL` points at the Railway database and `init_db()` created the tables on startup.
4. Deploy and smoke-test `/`, `/Admin/`, `/docs`, and login.
5. Continue moving remaining demo-only flows into persistent PostgreSQL-backed paths.
