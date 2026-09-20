# Deployment Guide for VCNR_Web (Railway)

This guide covers running the app publicly on **Railway**, which now hosts both the
web service and the PostgreSQL database in a single project. Render is no longer
used.

The stack:

- **FastAPI** backend (Python) served through the root `Dockerfile` via `railway.json`
- **PostgreSQL** database (Railway managed)
- **Frontend** served directly by FastAPI, so one public URL serves everything
- **Large encrypted media packages** (`.vcnr` chunks, multi-GB) — keep these on R2

---

## Architecture

| Component | Host | Notes |
|---|---|---|
| Web service (FastAPI + frontend) | Railway (Docker image from root `Dockerfile`) | `railway.json` sets the build/start/healthcheck |
| PostgreSQL | Railway (managed DB service) | web service uses its `DATABASE_URL` via variable reference |
| Large media (`.vcnr`, posters, trailers) | Cloudflare R2 | optional; avoids Railway egress costs |

> **Pricing** — Railway has no permanent free tier. A new account gets a free trial
> (~$5 credit); after that the cheapest plan is **Hobby at ~$5/month** (includes a
> usage credit). Railway bills **network egress**, so route large media through R2.

---

## One-time setup

1. Sign in at <https://railway.com> (GitHub login).
2. **New Project** → start from an **empty project**.
3. Add the database: **+ New → Database → PostgreSQL** and wait until it is
   `RUNNING`. A PostgreSQL service named e.g. `Postgres` is created.
4. Add the web service: **+ New → GitHub Repo** → select `kakgit/VCNR_Web`.
   Railway auto-detects the root `Dockerfile` and the repo's `railway.json`.

### Connect the database

In the web service **Variables** tab:

1. Add a variable `DATABASE_URL`.
2. Use the **reference picker** (`Add Reference`) and select the PostgreSQL
   service's `DATABASE_URL`. The value becomes an unexpanded reference such as
   `${{Postgres.DATABASE_URL}}`, which Railway resolves at deploy time to the
   private `*.railway.internal` connection string.

This is the private URL that works only inside the Railway project — no
`sslmode=require` needed, and no public TCP proxy required because the app and the
database live in the same private network.

> ⚠️ Do **not** paste the value directly as literal text. If the reference is
> stored literally (unresolved `${{...}}`), or the variable is empty, the app now
> **will not crash** — it degrades to the graceful "database unavailable"
> behavior (admin/producer routes return 503) until the variable is fixed. A clear
> `[db] Unusable DATABASE_URL ...` warning is printed in the logs.

### Public URL

In the web service **Settings → Networking → Generate Domain**. You get a URL like
`https://<service>.up.railway.app`.

The backend auto-detects `RAILWAY_PUBLIC_DOMAIN` and uses it for CORS, torrent
webseed URLs, and email links — so **no** manual `FRONTEND_ORIGIN` is needed
(you may set it explicitly for a custom domain).

### Port

The app binds `${PORT:-8000}`. If the domain does not respond, open the web
service **Settings → Networking** and set the service **Port** to `8000` (when
Railway doesn't inject a `PORT` variable, uvicorn listens on 8000).

---

## Verify

```bash
curl https://<your-service>.up.railway.app/api/health
curl https://<your-service>.up.railway.app/api/producer/queue   # reads the Railway DB
curl https://<your-service>.up.railway.app/                     # frontend
curl https://<your-service>.up.railway.app/Admin/               # admin panel
curl https://<your-service>.up.railway.app/docs                 # FastAPI docs
```

`init_db()` runs on startup, so all SQLAlchemy tables and compatibility columns
are created automatically in a fresh database.

---

## Environment variables

| Variable | Required | Source | Notes |
|---|---|---|---|
| `DATABASE_URL` | **yes** | reference to PostgreSQL service | private `*.railway.internal` URL |
| `APP_ENV` | recommended | manual | `production` |
| `SWARM_STUN_URL` | no | manual | `stun:stun.l.google.com:19302` |
| `SWARM_TURN_URL` / `USERNAME` / `CREDENTIAL` | no | manual | optional TURN for cross-NAT WebRTC |
| `PUBLIC_TORRENT_TRACKERS` | no | manual | comma-separated tracker URLs |
---

## Cloudflare R2 (large media)

Admin media assets (posters, trailers, gallery, music) are uploaded directly to R2
via presigned URLs. Setup:

1. Sign up at <https://dash.cloudflare.com> → **R2** → create a bucket (e.g. `vcnr-media`).
2. Create an **R2 Access Key** with Object Read & Write.
3. Enable **Public access** on the bucket to get `https://pub-xxx.r2.dev`.
4. Set these on the web service **Variables** tab:
   ```text
   R2_ACCOUNT_ID=your-cloudflare-account-id
   R2_ACCESS_KEY_ID=your-r2-access-key-id
   R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
   R2_BUCKET_NAME=vcnr-media
   R2_PUBLIC_BASE_URL=https://pub-xxxxxxxxxxxx.r2.dev
   ```
5. **CORS on the bucket is required** (the admin panel PUTs files directly to R2).
   R2 → bucket → **Settings → CORS** → add:
   ```json
   [
     {
       "AllowedOrigins": ["https://<your-service>.up.railway.app", "http://localhost:8000", "http://127.0.0.1:8000"],
       "AllowedMethods": ["PUT", "GET", "HEAD", "POST", "DELETE"],
       "AllowedHeaders": ["*"],
       "ExposeHeaders": ["ETag"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
   (Or use `"AllowedOrigins": ["*"]` for a public bucket.)

The encrypted content-chunk delivery (`.vcnr`, torrent/swarm) stays on the local
filesystem by design.

---

## Troubleshooting

### App crashes on startup: "Could not parse SQLAlchemy URL from given URL string"

Caused by an empty / malformed / literal-unresolved `DATABASE_URL` (e.g. the
variable value is literally `${{Postgres.DATABASE_URL}}` because the reference
picker wasn't used, or the referenced service was renamed).

The backend is now hardened so this **cannot crash the server** anymore — it
falls back safely, boots, and DB routes return 503. To actually fix the DB:

1. Web service → **Variables** → `DATABASE_URL`.
2. Delete the literal value and re-add it **via the reference picker** → choose
   the PostgreSQL service's `DATABASE_URL`.
3. Redeploy. Check the logs for `[db] Unusable DATABASE_URL` while it recovers.

### App starts but `/api/admin` and `/api/producer` return 503

The database is unreachable. Confirm `DATABASE_URL` resolves to the private
`*.railway.internal` URL and that the PostgreSQL service is `RUNNING`. Non-DB
endpoints keep working with demo data.

### First request is slow

The free/Hobby instance cold-starts after idle sleep; the first request may take
~30–60s.

### CORS errors in the mobile app

`FRONTEND_ORIGIN` is auto-detected from `RAILWAY_PUBLIC_DOMAIN`, so no manual
setup is needed. If you attach a custom domain, set `FRONTEND_ORIGIN` to the exact
public URL (no trailing slash). The backend already adds the `localhost` fallbacks.

---

## Cost / limits

- No permanent free tier: trial credit, then Hobby (~$5/month + usage credit).
- Billing for **egress** through the public domain — keep large media transfers on R2.
- Container disk is **ephemeral**: anything written under `media/` is lost on
  redeploy; use R2 for anything that must persist.
- **Stopping Render**: delete the old Render app + its database in the Render
  dashboard once the Railway deployment is verified.