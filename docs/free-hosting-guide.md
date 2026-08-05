# Free Hosting and Testing Guide for VCNR_Web

This guide covers free options to host the app publicly so you can run real mobile
testing without keeping your laptop online. It is written specifically for this
project's stack:

- **FastAPI** backend (Python) served through the root `Dockerfile`
- **PostgreSQL** database
- **Frontend** served directly by FastAPI
- **Large encrypted media packages** (`.vcnr` chunks, multi-GB)

---

## Quick Decision Table

| Option | What it's for | Free tier | Best for |
|---|---|---|---|
| **Cloudflare quick tunnel** | Temporary public URL | Free, unlimited | Ad-hoc phone testing while laptop is on |
| **Render** | Stable public backend | 750 hrs/mo, sleeps after 15 min idle | Steady public URL, simple setup |
| **Koyeb** | Stable backend that stays awake | 0.1 vCPU / 512 MB, no sleep | **Mobile download testing** (no hibernation) |
| **Neon** | PostgreSQL | 0.5 GB, permanently free | Long-term free database |
| **Railway** | App hosting | ~$5 one-time credit only | Short-term trial (not indefinite free) |
| **Cloudflare R2** | Object storage for media | 10 GB storage, 1M reads/mo | Storing large `.vcnr` packages |

---

## Option 1 — Keep Using the Cloudflare Quick Tunnel (already working)

This is the fastest path and you already verified it works with your Android viewer.

```bash
cloudflared tunnel --url http://localhost:8000
```

- URL changes every time the tunnel restarts.
- Only works while the laptop is on.
- Fine for quick phone tests; not stable enough for review or longer test cycles.

---

## Option 2 — Render (recommended for a permanent public URL)

Render deploys your root `Dockerfile` directly, gives a stable HTTPS URL, and can
provision a free PostgreSQL. A `render.yaml` blueprint is already included in this
repo.

### Setup

1. Push this repo to GitHub (already at `https://github.com/kakgit/VCNR_Web`).
2. Go to <https://render.com> and sign up with GitHub.
3. Dashboard → **New +** → **Blueprint** → select `VCNR_Web`.
4. Render reads `render.yaml` and creates:
   - `vcnr-web` web service (Docker, free plan)
   - `vcnr-postgres` database (free plan)
5. In the web service **Environment** tab set:
   - `FRONTEND_ORIGIN` → `https://vcnr-web.onrender.com` (the URL Render assigned)
6. Deploy and open:
   - `https://vcnr-web.onrender.com/api/health` → should return `{"status":"ok",...}`
   - `https://vcnr-web.onrender.com/` → frontend
   - `https://vcnr-web.onrender.com/Admin/` → admin panel
   - `https://vcnr-web.onrender.com/docs` → FastAPI docs

### Free tier limits that matter

- **Sleeps after 15 min idle** → first request after sleep takes ~50s.
- **Free Postgres expires after 30 days** → use Neon (Option 4) after that.
- **Bandwidth ~100 GB/month** → a 2.5 GB package downloaded ~30 times hits the cap.
- **Disk is ephemeral** → anything written under `media/` is lost on redeploy.
  Long downloads can also be interrupted if the service restarts/sleeps mid-transfer.

---

## Option 3 — Koyeb (best for long mobile downloads)

Koyeb free tier **does not sleep**, which makes it the better choice for your
2.5 GB / 328-chunk Android download testing. A `koyeb.yaml` service definition is
included in this repo.

### Setup via dashboard

1. Sign up at <https://koyeb.com> (GitHub login).
2. **Create App** → **Deploy from GitHub** → select `VCNR_Web`.
3. Koyeb auto-detects the Dockerfile.
4. Run command: `uvicorn backend.main:app --host 0.0.0.0 --port 8000`
5. Port: `8000` / HTTP
6. Instance type: **Free**
7. Add env vars (see `koyeb.yaml`):
   - `APP_ENV=production`
   - `DATABASE_URL` → your Neon connection string (Option 4)
   - `FRONTEND_ORIGIN=https://<app-name>-<org>.koyeb.app`

### Koyeb free tier limits

- 0.1 vCPU / 512 MB RAM — enough for the FastAPI app and small uploads.
- No persistent disk on free tier → `media/` writes are lost on redeploy.
- ~100 GB monthly bandwidth cap.

---

## Option 4 — Neon (permanent free PostgreSQL)

Render's free Postgres expires after 30 days. Neon's free tier is **permanently free**
(0.5 GB), which makes it the right database for ongoing testing.

### Setup

1. Sign up at <https://neon.tech> (GitHub login).
2. Create a new project (any region close to your test users).
3. Copy the connection string. Neon provides it as:
   `postgresql://user:password@ep-xxxx-pooler.region.aws.neon.tech/neondb?sslmode=require`
4. Your app expects the `postgresql+psycopg://` scheme. The `_normalize_database_url`
   in `backend/core/config.py` already converts `postgres://` and `postgresql://`
   automatically, so you can paste Neon's string as-is into `DATABASE_URL`.
5. `init_db()` runs on startup and creates all tables automatically.

### Verification

```bash
curl https://<your-app-url>/api/health
```

If the DB connects, admin/producer endpoints will work against the Neon database.
If DB is unreachable, non-DB endpoints still work (the app falls back to demo data),
and admin/producer routes return HTTP 503.

---

## Option 5 — Cloudflare R2 (object storage for big media)

Your real test package is ~2.5 GB. Free app tiers cannot hold many of those on
their ephemeral disks. R2 gives you **10 GB free storage + 1M reads/month** with no
egress fees — which is ideal for serving `.vcnr` chunks to phones.

### Setup

1. Sign up at <https://dash.cloudflare.com> (free account) → **R2**.
2. Create a bucket, e.g. `vcnr-media`.
3. Create an API token with **Object Read & Write** permissions.
4. Options:
   - **Public bucket**: enable the public R2.dev URL and redirect download URLs.
   - **Presigned uploads**: your backend generates presigned PUT/GET URLs.

### Integration ideas

- Upload `media/library/<movie_id>/content/*.vcnr` to R2.
- Store the manifest in Postgres (Neon) and have the backend return R2 presigned
  URLs in `/api/delivery/...` responses.
- Keep the free app server light so your 512 MB / 1 GB instance is not filled
  with media files.

---

## Comparing Render vs Koyeb for YOUR mobile tests

| Factor | Render free | Koyeb free |
|---|---|---|
| Sleeps when idle | Yes (15 min) | **No** |
| URL | `*.onrender.com` | `*.koyeb.app` |
| Build from Dockerfile | Yes | Yes |
| Health check | `/api/health` | `/api/health` |
| Free Postgres included | Yes (30-day expiry) | No (use Neon) |
| Long download safe | Risky (sleeps) | **Yes** |
| RAM | 512 MB | 512 MB |

**Recommendation:** Use **Koyeb + Neon** for mobile download testing, and keep
Render as an easy-to-setup alternative or secondary environment.

---

## Environment Variables Summary

| Variable | Required | Example |
|---|---|---|
| `APP_ENV` | yes | `production` |
| `APP_HOST` | yes | `0.0.0.0` |
| `APP_PORT` | yes | `8000` |
| `DATABASE_URL` | yes | `postgresql+psycopg://...` (Neon) |
| `FRONTEND_ORIGIN` | yes | `https://vcnr-web.onrender.com` or `https://<app>-<org>.koyeb.app` |
| `SWARM_STUN_URL` | no | `stun:stun.l.google.com:19302` |
| `SWARM_TURN_URL` | no | (optional TURN server) |
| `SWARM_TURN_USERNAME` | no | (optional) |
| `SWARM_TURN_CREDENTIAL` | no | (optional) |
| `PUBLIC_TORRENT_TRACKERS` | no | comma-separated tracker URLs |

---

## Bandwidth Budget Planning

Free tiers cap bandwidth (~100 GB/month on Render and Koyeb). A single 2.5 GB
package consumed by 10 phones = 25 GB. Budget accordingly:

| Downloads of 2.5 GB package | Bandwidth used |
|---|---|
| 1 | 2.5 GB |
| 10 | 25 GB |
| 40 | 100 GB (cap reached) |

To stay within free limits:

- Use R2 or the local cloudflared tunnel for large media transfers.
- Keep API-only traffic (login, manifest, metadata) on Render/Koyeb.
- Prefer the p2p swarm path once a phone already has chunks, reducing server egress.

---

## Troubleshooting

### App starts but `/api/admin` and `/api/producer` return 503

The database is unreachable. Check `DATABASE_URL` and that Neon/Render Postgres is
accepting connections. Non-DB endpoints continue to work with demo data.

### Download fails mid-transfer on Render

The free instance likely slept or restarted. Move to Koyeb or use a quick tunnel /
R2 for large transfers.

### First request is slow

If using Render, the instance is cold-starting after sleep. Koyeb avoids this.

### CORS errors in the mobile app

Set `FRONTEND_ORIGIN` to the exact public URL your app is calling (no trailing
slash). The backend already adds the localhost fallbacks.