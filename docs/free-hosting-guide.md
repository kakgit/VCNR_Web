# Free Hosting and Testing Guide for VCNR_Web

This guide covers the free options to host the app publicly so you can run real mobile
testing without keeping your laptop online. It is written specifically for this
project's stack:

- **FastAPI** backend (Python) served through the root `Dockerfile`
- **PostgreSQL** database
- **Frontend** served directly by FastAPI
- **Large encrypted media packages** (`.vcnr` chunks, multi-GB)

> **Policy:** Render is the only app deployment platform for `VCNR_Web`.
> The `render.yaml` blueprint at the repo root is the single source of deployment config.

---

## Quick Decision Table

| Option | What it's for | Free tier | Best for |
|---|---|---|---|
| **Render** | Stable public backend | 750 hrs/mo, sleeps after 15 min idle | Sole app deployment platform |
| **Railway** | PostgreSQL (managed) | Trial ~$5 credit, then Hobby $5/mo | Long-term database host outside Render (needs Public Access / TCP proxy) |
| **Cloudflare R2** | Object storage for media | 10 GB storage, 1M reads/mo | Storing large `.vcnr` packages |
| **Cloudflare quick tunnel** | Temporary public URL | Free, unlimited | Ad-hoc phone testing while laptop is on |

---

## Option 1 — Render (the only deployment platform)

Render deploys your root `Dockerfile` directly, gives a stable HTTPS URL, and is
the only app deployment platform. The `render.yaml` blueprint is already included
in this repo and is wired to auto-detect your public URL. PostgreSQL now runs on
Railway (Option 3), not on Render.

### Setup

1. Push this repo to GitHub (already at `https://github.com/kakgit/VCNR_Web`).
2. Go to <https://render.com> and sign up with GitHub.
3. Dashboard → **New +** → **Blueprint** → select `VCNR_Web`.
4. Render reads `render.yaml` and creates:
   - `vcnr-web` web service (Docker, free plan)

   PostgreSQL is **not** created on Render anymore — it runs on Railway (Option 3).
5. **No manual `FRONTEND_ORIGIN` setup is needed.** The backend reads
   `RENDER_EXTERNAL_URL` (set automatically by Render) and uses it as the
   frontend origin for CORS and webseed URLs.
6. Deploy and open:
   - `https://vcnr-web.onrender.com/api/health` → should return `{"status":"ok",...}`
   - `https://vcnr-web.onrender.com/` → frontend
   - `https://vcnr-web.onrender.com/Admin/` → admin panel
   - `https://vcnr-web.onrender.com/docs` → FastAPI docs

### Env vars set by the blueprint

| Variable | Source | Value |
|---|---|---|
| `APP_ENV` | blueprint | `production` |
| `APP_HOST` | blueprint | `0.0.0.0` |
| `APP_PORT` | blueprint | `8000` |
| `DATABASE_URL` | **manual** (`sync: false`) | Railway `DATABASE_PUBLIC_URL` (public TCP proxy) |
| `FRONTEND_ORIGIN` | **auto-detected** | `RENDER_EXTERNAL_URL` (set by Render) |
| `SWARM_STUN_URL` | blueprint | `stun:stun.l.google.com:19302` |

Optional variables you can add in the service **Environment** tab:

```text
SWARM_TURN_URL=
SWARM_TURN_USERNAME=
SWARM_TURN_CREDENTIAL=
PUBLIC_TORRENT_TRACKERS=udp://tracker.opentrackr.org:1337/announce,udp://open.stealth.si:80/announce
```

### Free tier limits that matter

- **Sleeps after 15 min idle** → first request after sleep takes ~50s.
- **PostgreSQL lives on Railway** (see Option 3) — Render only runs the web service.
- **Bandwidth ~100 GB/month** → a 2.5 GB package downloaded ~30 times hits the cap.
- **Disk is ephemeral** → anything written under `media/` is lost on redeploy.
  Long downloads can also be interrupted if the service restarts/sleeps mid-transfer.
- **750 free instance hours/month** → the free service sleeps, so this is usually not a blocker.

---

## Option 2 — Cloudflare Quick Tunnel (temporary)

This is the fastest ad-hoc path when your laptop is on and you want a public URL
without waiting for Render cold starts.

```bash
cloudflared tunnel --url http://localhost:8000
```

- URL changes every time the tunnel restarts.
- Only works while the laptop is on.
- Fine for quick phone tests; not stable enough for review or longer test cycles.
- On phones, the server field should be the full `https://...trycloudflare.com` URL.

---

## Option 3 — Railway (PostgreSQL database)

The app stays on Render, but the database runs on **Railway** (<https://railway.com>).
Railway Postgres deploys private by default, and Render is outside Railway's private
network — so the database must be exposed with a public TCP proxy.

> **Pricing** — Railway has no permanent free tier anymore: a new account gets a
> free trial (~$5 credit), then the cheapest paid plan is **Hobby at $5/month**
> (includes a ~$5 usage credit). Traffic through the public TCP proxy bills as
> network egress, but normal API traffic is small.

### Create the database (one time, on Railway)

1. Sign in at <https://railway.com> (GitHub login).
2. **New Project** → start from an empty project.
3. **+ New → Database → PostgreSQL** (or deploy the template from
   <https://railway.com/deploy/postgres>). Wait until the service is **RUNNING**.
4. Open the PostgreSQL service → **Settings → Networking**.
5. Add **Public Access** (this creates a **TCP Proxy**). Enter the internal port
   `5432`. Railway generates a proxy host/port such as `shuttle.proxy.rlwy.net:15140`
   and populates a `DATABASE_PUBLIC_URL` variable.
6. Copy `DATABASE_PUBLIC_URL`. It looks like:
   `postgresql://postgres:...@shuttle.proxy.rlwy.net:15140/railway`

   Use the **public** URL — the default `DATABASE_URL` points at a
   `*.railway.internal` host that only resolves inside Railway and cannot be
   reached from Render.

### Switch Render to Railway

1. In Render → your `vcnr-web` service → **Environment** tab.
2. Replace `DATABASE_URL` with the `DATABASE_PUBLIC_URL` value. If the copied
   string has no `sslmode`, append `?sslmode=require` (Railway Postgres is
   SSL-enabled).
3. Redeploy / restart the service.
4. On startup `init_db()` creates all tables and compatibility columns
   automatically, so a fresh empty database works without manual SQL.

### Verify

```bash
curl https://vcnr-web.onrender.com/api/health
```

If the DB connects, admin/producer endpoints work against the Railway database.
If the DB is unreachable, non-DB endpoints still work (the app falls back to demo
data) and admin/producer routes return HTTP 503.

### Migrating existing data (recommended before switching)

If the Render database already holds real users/movies, dump and restore it once
(machine with Postgres client tools):

```bash
pg_dump --no-owner --no-acls "<RENDER_DATABASE_URL>" > dump.sql
psql "<RAILWAY_PUBLIC_URL>" < dump.sql
```

- `<RENDER_DATABASE_URL>`: Render → `vcnr-postgres` database → **Connect** tab.
- `<RAILWAY_PUBLIC_URL>`: from step 6 above.

### Remove the old Render database (last step)

After the app is verified working on Railway:

1. Update `render.yaml` (the `databases:` block is already removed and
   `DATABASE_URL` is `sync: false`), commit, and push. In the Render dashboard,
   apply the Blueprint update.
2. **Warning**: applying that update deletes the `vcnr-postgres` resource and all
   its data on Render. Do this only after you verified Railway is serving the app
   (or delete the database manually in the Render dashboard when you are ready).

---

## Option 4 — Cloudflare R2 (object storage for big media)

Your real test package is ~2.5 GB. Free app tiers cannot hold many of those on
their ephemeral disks. R2 gives you **10 GB free storage + 1M reads/month** with no
egress fees — which is ideal for serving `.vcnr` chunks to phones.

### Current implementation (already wired in)

The app now uses R2 for **admin media assets** (posters, trailers, gallery, music):

- The admin UI calls `POST /api/admin/movies/{id}/assets/presign` to get a
  presigned R2 PUT URL, uploads the file **directly to R2** (bypassing the Render
  API), then calls `POST /api/admin/movies/{id}/assets/register` to update the
  movie record.
- Media URLs returned to the viewer are R2 public URLs, so Render's ephemeral
  disk and bandwidth are not used for these files.
- The encrypted content-chunk delivery system (`.vcnr` chunks, torrent/swarm)
  intentionally stays on the local filesystem and is **not** part of this R2
  media-asset flow.

### Setup

1. Sign up at <https://dash.cloudflare.com> (free account) → **R2**.
2. Create a bucket, e.g. `vcnr-media`.
3. Create an R2 Access Key with **Object Read & Write** permissions.
4. Enable **Public access** on the bucket to get a public base URL, e.g.
   `https://pub-xxxxxxxxxxxx.r2.dev`.
5. Set these env vars on the Render service (see `.env.example`):
   ```text
   R2_ACCOUNT_ID=your-cloudflare-account-id
   R2_ACCESS_KEY_ID=your-r2-access-key-id
   R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
   R2_BUCKET_NAME=vcnr-media
   R2_PUBLIC_BASE_URL=https://pub-xxxxxxxxxxxx.r2.dev
   ```
6. **Configure CORS on the bucket** — this is REQUIRED. The admin panel runs in
   the browser and PUTs files directly to the R2 URL returned by the presign
   endpoint. Without CORS the browser blocks the upload with a
   `No 'Access-Control-Allow-Origin'` error. In the Cloudflare dashboard:
   R2 → your bucket → **Settings** → **CORS** → add a rule:
   ```json
   [
     {
       "AllowedOrigins": ["https://vcnr-web.onrender.com", "http://localhost:8000", "http://127.0.0.1:8000"],
       "AllowedMethods": ["PUT", "GET", "HEAD", "POST", "DELETE"],
       "AllowedHeaders": ["*"],
       "ExposeHeaders": ["ETag"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```
   (Or use `"AllowedOrigins": ["*"]` for public buckets. `localhost` entries
   let you test the same flow from your laptop.)
7. Redeploy. Admin media uploads now go straight to R2.

### Migrating existing local media to R2

A one-time migration script is included at `tools/migrate_media_to_r2.py`. It walks the
local `media/library/` tree and uploads existing posters, trailers, gallery, and music files
to R2 using the same object-key layout the backend expects. Run it once from the repo root
with the same R2 env vars configured.

### Integration notes

- Keep the free app server light so your instance is not filled with media files.
- The encrypted content chunks (`.vcnr`) and torrent delivery remain on local disk by design.

---

## Environment Variables Summary

| Variable | Required | Source | Example |
|---|---|---|---|
| `APP_ENV` | yes | blueprint | `production` |
| `APP_HOST` | yes | blueprint | `0.0.0.0` |
| `APP_PORT` | yes | blueprint | `8000` |
| `DATABASE_URL` | yes | manual (`sync: false` in blueprint) | Railway public proxy URL |
| `FRONTEND_ORIGIN` | no | auto-detected from `RENDER_EXTERNAL_URL` | `https://vcnr-web.onrender.com` |
| `SWARM_STUN_URL` | no | blueprint | `stun:stun.l.google.com:19302` |
| `SWARM_TURN_URL` | no | manual | (optional TURN server) |
| `SWARM_TURN_USERNAME` | no | manual | (optional) |
| `SWARM_TURN_CREDENTIAL` | no | manual | (optional) |
| `PUBLIC_TORRENT_TRACKERS` | no | manual | comma-separated tracker URLs |

> `FRONTEND_ORIGIN` no longer needs manual setup on Render. It falls back to
> `RENDER_EXTERNAL_URL` automatically. Override it only when you attach a custom
> domain different from the Render-assigned `*.onrender.com` URL.

---

## Bandwidth Budget Planning

Free tiers cap bandwidth (~100 GB/month on Render). A single 2.5 GB package consumed
by 10 phones = 25 GB. Budget accordingly:

| Downloads of 2.5 GB package | Bandwidth used |
|---|---|
| 1 | 2.5 GB |
| 10 | 25 GB |
| 40 | 100 GB (typical cap reached) |

To stay within free limits:

- Use R2 or the local cloudflared tunnel for large media transfers.
- Keep API-only traffic (login, manifest, metadata) on Render.
- Prefer the p2p swarm path once a phone already has chunks, reducing server egress.

---

## Troubleshooting

### App starts but `/api/admin` and `/api/producer` return 503

The database is unreachable. Check that `DATABASE_URL` points at Railway's public
proxy URL (host like `*.proxy.rlwy.net`, `sslmode=require`) and that Public Access
on the Railway Postgres service is still enabled. Non-DB endpoints continue to
work with demo data.

### Download fails mid-transfer

The free instance likely restarted or slept. Move large transfers to R2, or use a
quick tunnel for large transfers.

### First request is slow

The Render free instance is cold-starting after 15 min of idle sleep. This is
expected; subsequent requests are fast until the next idle period.

### CORS errors in the mobile app

On Render, `FRONTEND_ORIGIN` is auto-detected from `RENDER_EXTERNAL_URL`, so no
manual setup is needed. If you attach a custom domain, set `FRONTEND_ORIGIN` to the
exact public URL your app is calling (no trailing slash). The backend already adds
the localhost fallbacks.