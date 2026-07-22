from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_env_file() -> None:
  env_path = Path(__file__).resolve().parent.parent.parent / ".env"
  if not env_path.exists():
    return

  for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Settings:
  app_name: str
  app_env: str
  app_host: str
  app_port: int
  frontend_origin: str
  database_url: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  _load_env_file()
  return Settings(
    app_name=os.getenv("APP_NAME", "Cine Vault API"),
    app_env=os.getenv("APP_ENV", "development"),
    app_host=os.getenv("APP_HOST", "0.0.0.0"),
    app_port=int(os.getenv("APP_PORT", "8000")),
    frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:8000"),
    database_url=os.getenv(
      "DATABASE_URL",
      "postgresql+psycopg://postgres:postgres@localhost:5432/cineproxima",
    ),
  )
