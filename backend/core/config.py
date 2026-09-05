from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _normalize_database_url(value: str) -> str:
  normalized = value.strip()
  if normalized.startswith("postgres://"):
    return "postgresql+psycopg://" + normalized[len("postgres://"):]
  if normalized.startswith("postgresql://"):
    return "postgresql+psycopg://" + normalized[len("postgresql://"):]
  return normalized


def _parse_csv_urls(value: str) -> tuple[str, ...]:
  urls: list[str] = []
  for raw in value.split(","):
    cleaned = raw.strip()
    if cleaned and cleaned not in urls:
      urls.append(cleaned)
  return tuple(urls)


def _load_env_file() -> None:
  env_path = Path(__file__).resolve().parent.parent.parent / ".env"
  if not env_path.exists():
    return

  for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    # In local/dev runs we want the checked-in .env file to win so tunnel URL
    # changes immediately affect regenerated torrent webseed metadata.
    os.environ[key.strip()] = value.strip()


def _resolve_frontend_origin() -> str:
  """Resolve the public frontend origin.

  Priority:
    1. Explicit FRONTEND_ORIGIN env var (if provided)
    2. RENDER_EXTERNAL_URL (automatically set by Render to the service URL)
    3. Local default
  """
  configured = os.getenv("FRONTEND_ORIGIN", "").strip()
  if configured:
    return configured
  render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
  if render_url:
    return render_url
  return "http://localhost:8000"


@dataclass(frozen=True)
class Settings:
  app_name: str
  app_env: str
  app_host: str
  app_port: int
  frontend_origin: str
  database_url: str
  swarm_stun_url: str
  swarm_turn_url: str
  swarm_turn_username: str
  swarm_turn_credential: str
  swarm_max_receivers_per_seeder: int
  swarm_seeder_ttl_seconds: int
  public_torrent_trackers: tuple[str, ...]
  r2_account_id: str
  r2_access_key_id: str
  r2_secret_access_key: str
  r2_bucket_name: str
  r2_public_base_url: str
  expo_access_token: str
  smtp_host: str
  smtp_port: int
  smtp_username: str
  smtp_password: str
  smtp_from_email: str
  smtp_from_name: str
  smtp_use_tls: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  _load_env_file()
  return Settings(
    app_name=os.getenv("APP_NAME", "Cine Vault API"),
    app_env=os.getenv("APP_ENV", "development"),
    app_host=os.getenv("APP_HOST", "0.0.0.0"),
    app_port=int(os.getenv("APP_PORT", "8000")),
    frontend_origin=_resolve_frontend_origin(),
    database_url=_normalize_database_url(
      os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:yHVcZRYUmMgPjiIhpEbuqxKLnadSECZr@altaria.proxy.rlwy.net:34062/railway?sslmode=require",
      )
    ),
    swarm_stun_url=os.getenv("SWARM_STUN_URL", "stun:stun.l.google.com:19302").strip(),
    swarm_turn_url=os.getenv("SWARM_TURN_URL", "").strip(),
    swarm_turn_username=os.getenv("SWARM_TURN_USERNAME", "").strip(),
    swarm_turn_credential=os.getenv("SWARM_TURN_CREDENTIAL", "").strip(),
    swarm_max_receivers_per_seeder=int(os.getenv("SWARM_MAX_RECEIVERS_PER_SEEDER", "8").strip() or "8"),
    swarm_seeder_ttl_seconds=int(os.getenv("SWARM_SEEDER_TTL_SECONDS", "300").strip() or "300"),
    public_torrent_trackers=_parse_csv_urls(
      os.getenv(
        "PUBLIC_TORRENT_TRACKERS",
        ",".join(
          [
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://open.stealth.si:80/announce",
            "udp://tracker.torrent.eu.org:451/announce",
            "udp://explodie.org:6969/announce",
            "https://tracker.opentrackr.org:443/announce",
          ]
        ),
      )
    ),
    r2_account_id=os.getenv("R2_ACCOUNT_ID", "").strip(),
    r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID", "").strip(),
    r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
    r2_bucket_name=os.getenv("R2_BUCKET_NAME", "").strip(),
    r2_public_base_url=os.getenv("R2_PUBLIC_BASE_URL", "").strip().rstrip("/"),
    expo_access_token=os.getenv("EXPO_ACCESS_TOKEN", "").strip(),
    smtp_host=os.getenv("SMTP_HOST", "").strip(),
    smtp_port=int(os.getenv("SMTP_PORT", "587").strip() or "587"),
    smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
    smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
    smtp_from_email=os.getenv("SMTP_FROM_EMAIL", "").strip(),
    smtp_from_name=(os.getenv("SMTP_FROM_NAME", "").strip() or "Cine Vault"),
    # STARTTLS on by default; set SMTP_USE_TLS=false for plain/local relays,
    # or use port 465 which is detected as implicit SSL automatically.
    smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no", "off"},
  )
