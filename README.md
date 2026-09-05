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

## Deployment (Railway)

Railway is the **only** deployment platform for `VCNR_Web`. It runs both the app
(web service built from the root `Dockerfile` via `railway.json`) and the
PostgreSQL database in one project. Render is no longer used.

### One-click Railway deploy

The repo ships with a `railway.json` that tells Railway to:

- build the root `Dockerfile`
- run `uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- healthcheck at `/api/health`

Deploy steps:

1. Push this repo to GitHub.
2. Go to <https://railway.com> → **New Project** → start from an empty project.
3. Add **PostgreSQL**: **+ New → Database → PostgreSQL** and wait for it to be `RUNNING`.
4. Add the web service: **+ New → GitHub Repo** → select `VCNR_Web`.
5. In the web service **Variables** tab, set `DATABASE_URL` by picking the
   PostgreSQL service's `DATABASE_URL` via the reference picker (it becomes e.g.
   `${{Postgres.DATABASE_URL}}`). This is the private `*.railway.internal` URL and
   works without `sslmode=require`.
6. Generate a public domain: web service **Settings → Networking → Generate Domain**.
7. Open `https://<your-service>.up.railway.app/api/health` (or the assigned domain).

`FRONTEND_ORIGIN` is **auto-detected**: the backend reads `RAILWAY_PUBLIC_DOMAIN`
(set automatically once your service has a public domain) and uses it for CORS and
webseed URLs. No manual setup is needed. If you attach a custom domain, the same
auto-detection covers it.

### Port

The app binds `${PORT:-8000}`. If your domain doesn't respond immediately, open
the service **Settings → Networking** and set the service **Port** to `8000` (the
value uvicorn binds to when Railway doesn't provide `PORT`).

### Environment variables

The only required variable is:

```text
DATABASE_URL=<reference your Railway PostgreSQL service's DATABASE_URL>
```

Recommended service variables (add in the web service **Variables** tab):

```text
APP_ENV=production
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

Optional Cloudflare R2 storage (see `docs/free-hosting-guide.md`):

```text
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=vcnr-media
R2_PUBLIC_BASE_URL=https://pub-xxxxxxxxxxxx.r2.dev
```

### Important note

The backend already calls `init_db()` on startup, so the current SQLAlchemy tables
and compatibility columns are created automatically when the database is reachable.

### Cost / limits

- Railway has no permanent free tier: new accounts get a trial credit, then the
  cheapest plan is Hobby (~$5/month plus usage credit).
- Railway bills **network egress** — keep large media transfers on R2.
- The container disk is ephemeral: anything written under `media/` is lost on
  redeploy.

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
2. Confirm the Railway web service builds from the root `Dockerfile` (`railway.json`).
3. Confirm `DATABASE_URL` points at the Railway PostgreSQL service and `init_db()` created the tables on startup.
4. Deploy and smoke-test `/`, `/Admin/`, `/docs`, and login.
5. Continue moving remaining demo-only flows into persistent PostgreSQL-backed paths.
