from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router as api_router
from backend.core.config import get_settings
from backend.db import init_db

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
  CORSMiddleware,
  allow_origins=[settings.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

frontend_root = Path(__file__).resolve().parent.parent
INDEX_HTML = frontend_root / "index.html"
ADMIN_HTML = frontend_root / "admin" / "index.html"
VERSIONED_ASSETS = [
  frontend_root / "app.js",
  frontend_root / "styles.css",
]


def _asset_version() -> str:
  latest_mtime = max(int(asset.stat().st_mtime) for asset in VERSIONED_ASSETS if asset.exists())
  return str(latest_mtime)


def _render_html(file_path: Path) -> HTMLResponse:
  html = file_path.read_text(encoding="utf-8").replace("__ASSET_VERSION__", _asset_version())
  response = HTMLResponse(content=html)
  response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
  response.headers["Pragma"] = "no-cache"
  response.headers["Expires"] = "0"
  return response


@app.middleware("http")
async def apply_cache_policy(request: Request, call_next):
  response = await call_next(request)
  path = request.url.path
  if path.endswith(".js") or path.endswith(".css"):
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
  elif path.endswith(".svg") or path.endswith(".jpg") or path.endswith(".jpeg") or path.endswith(".png") or path.endswith(".webp"):
    response.headers["Cache-Control"] = "public, max-age=86400"
  return response


@app.on_event("startup")
def startup() -> None:
  init_db()


app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
def frontend_index() -> HTMLResponse:
  return _render_html(INDEX_HTML)


@app.get("/Admin", response_class=HTMLResponse)
@app.get("/Admin/", response_class=HTMLResponse)
def admin_index() -> HTMLResponse:
  return _render_html(ADMIN_HTML)


app.mount("/", StaticFiles(directory=frontend_root, html=False), name="frontend")
