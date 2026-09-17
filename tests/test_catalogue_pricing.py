"""Run: python -m unittest discover -s tests -v. No production DB or network."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import asyncio
import json
from urllib.parse import urlencode
from types import SimpleNamespace

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import persistence
from backend.api import routes
from backend.core.catalogue import add_calendar_months, catalogue_view
from backend.core.time_utils import APP_TIMEZONE
from backend.db import get_db
from backend.models import Base

RELEASE = datetime(2030, 1, 31, 18, 30, tzinfo=APP_TIMEZONE)
PRICES = [dict(quality_code=q, quality_label=q, stars_required=s, sort_order=i)
          for i, (q, s) in enumerate((("720p", 5), ("1080p", 10), ("2k", 15), ("4k", 20)))]


class TestClient:
  """Small in-process ASGI client, avoiding optional httpx/test dependencies."""
  def __init__(self, app):
    self.app = app

  def request(self, method, path, payload=None, params=None):
    async def run():
      messages = []
      body = json.dumps(payload).encode() if payload is not None else b""
      async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
      async def send(message):
        messages.append(message)
      scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
        method=method, scheme="http", path=path, raw_path=path.encode(), root_path="",
        query_string=urlencode(params or {}).encode(),
        headers=[(b"content-type", b"application/json")],
        client=("127.0.0.1", 1234), server=("test", 80))
      await self.app(scope, receive, send)
      status = next(m["status"] for m in messages if m["type"] == "http.response.start")
      text = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body").decode()
      return SimpleNamespace(status_code=status, text=text, json=lambda: json.loads(text))
    return asyncio.run(run())

  def post(self, path, json):
    return self.request("POST", path, payload=json)

  def get(self, path, params=None):
    return self.request("GET", path, params=params)

  def close(self):
    pass


class CatalogueApiTests(unittest.TestCase):
  def setUp(self):
    self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(self.engine)
    self.sessions = sessionmaker(bind=self.engine, autoflush=False)
    app = FastAPI()
    app.include_router(routes.router)
    def db():
      with self.sessions() as session:
        yield session
    app.dependency_overrides[get_db] = db
    app.dependency_overrides[routes.require_admin] = lambda: {"id": "test", "role": "super_admin"}
    # Seeding creates demo accounts and media: unrelated to these isolated tests.
    self.seed = patch.object(persistence, "ensure_seeded")
    self.seed.start()
    self.client = TestClient(app)
    for module in (persistence, routes):
      media = patch.object(module, "r2_enabled", return_value=False)
      media.start()
      self.addCleanup(media.stop)
    teaser = patch.object(routes, "_read_teaser_links", return_value=[])
    teaser.start()
    self.addCleanup(teaser.stop)

  def tearDown(self):
    self.client.close()
    self.seed.stop()
    self.engine.dispose()

  def post(self, path, payload):
    response = self.client.post("/api" + path, json=payload)
    self.assertEqual(response.status_code, 200, response.text)
    return response.json()

  def create(self, stage="upcoming"):
    item = self.post("/admin/movies", dict(stage=stage, title_category="movies", title="Test Film",
      genre="Drama", story_line="Test story", release_date=RELEASE.isoformat()))["item"]
    return item["id"]

  def approve(self, movie_id):
    self.post(f"/admin/movies/{movie_id}/approval", {"action": "approve"})

  def view(self, movie_id, now, stage):
    with patch("backend.core.catalogue.app_now", return_value=now):
      response = self.client.get("/api/movies", params={"stage": stage})
      self.assertEqual(response.status_code, 200, response.text)
      items = response.json()["items"]
      self.assertEqual([item["id"] for item in items], [movie_id])
      detail = self.client.get(f"/api/movies/{movie_id}/details")
      self.assertEqual(detail.status_code, 200, detail.text)
      self.assertEqual(detail.json()["item"], items[0])
      for other in {"upcoming", "released", "library"} - {stage}:
        self.assertEqual(self.client.get("/api/movies", params={"stage": other}).json()["items"], [])
      return items[0]

  def test_admin_pricing_save_and_reload(self):
    for stage, field, options in (
      ("upcoming", "online_pricing_options", PRICES),
      ("library", "library_pricing_options", [dict(quality_code="4k", quality_label="4K", discs_required=7312, sort_order=0)]),
    ):
      with self.subTest(stage=stage):
        movie_id = self.create(stage)
        saved = self.post(f"/admin/movies/{movie_id}/pricing-config", {field: options})["item"]
        self.assertEqual(saved[field], options)
        for approved in (False, True):
          if approved:
            self.approve(movie_id)
          response = self.client.get("/api/admin/movies")
          self.assertEqual(response.status_code, 200, response.text)
          loaded = next(item for item in response.json()["items"] if item["id"] == movie_id)
          self.assertEqual(loaded[field], options)
          self.assertEqual(loaded["catalog_origin"], stage)


  def test_lifecycle_and_exact_discount_boundaries(self):
    movie_id = self.create()
    self.post(f"/admin/movies/{movie_id}/pricing-config", {"online_pricing_options": PRICES})
    self.approve(movie_id)
    cases = [(RELEASE - timedelta(seconds=1), "upcoming", [5, 10, 15, 20]),
             (RELEASE, "released", [5, 10, 15, 20]),
             (RELEASE + timedelta(days=1), "released", [5, 10, 15, 20])]
    for months, amounts in [(1, [5000, 10000, 15000, 20000]), (4, [4000, 8000, 12000, 16000]),
                            (6, [2500, 5000, 7500, 10000]), (12, [500, 1000, 1500, 2000])]:
      boundary = add_calendar_months(RELEASE, months)
      previous = self.view(movie_id, boundary - timedelta(seconds=1), "released" if months == 1 else "library")
      self.assertNotEqual([p["amount"] for p in previous["effective_pricing_options"]], amounts)
      cases.append((boundary, "library", amounts))
    for now, stage, amounts in cases:
      with self.subTest(now=now):
        item = self.view(movie_id, now, stage)
        self.assertEqual([p["amount"] for p in item["effective_pricing_options"]], amounts)
        self.assertEqual({p["currency"] for p in item["effective_pricing_options"]}, {"discs" if stage == "library" else "stars"})
        self.assertEqual(item["catalog_origin"], "upcoming")

  def test_direct_library_prices_are_independent_of_age(self):
    movie_id = self.create("library")
    self.post(f"/admin/movies/{movie_id}/pricing-config", {"library_pricing_options": [
      dict(quality_code="4k", quality_label="4K", discs_required=7312)]})
    self.approve(movie_id)
    for months in (0, 1, 4, 6, 12, 24):
      item = self.view(movie_id, add_calendar_months(RELEASE, months), "library")
      self.assertEqual(item["effective_pricing_options"][0]["amount"], 7312)
      self.assertEqual(item["library_price_source"], "direct")

  def test_upcoming_rejects_direct_disc_override(self):
    from backend.models import MovieRecord, MovieChangeRequestRecord
    movie_id = self.create()
    def snapshot():
      with self.sessions() as session:
        movie = session.get(MovieRecord, movie_id)
        requests = session.query(MovieChangeRequestRecord).all()
        return (persistence._capture_movie_snapshot(movie), [
          (r.id, r.status, r.baseline_snapshot, r.pending_snapshot, r.updated_at) for r in requests])
    before = snapshot()
    response = self.client.post(f"/api/admin/movies/{movie_id}/pricing-config", json={
      "library_pricing_options": [dict(quality_code="4k", quality_label="4K", discs_required=1)]})
    self.assertEqual(response.status_code, 400, response.text)
    self.assertEqual(snapshot(), before)

  def test_demo_rejection_does_not_create_approval_record(self):
    from copy import deepcopy
    from backend.data import demo_store
    from backend.schemas import AdminMoviePricingConfigRequest
    from fastapi import HTTPException
    movie = dict(id="test", stage="upcoming", catalog_origin="upcoming", title="Test", online_pricing_options=PRICES)
    before = deepcopy(movie)
    payload = AdminMoviePricingConfigRequest(library_pricing_options=[
      dict(quality_code="4k", quality_label="4K", discs_required=1)])
    with patch.object(demo_store, "MOVIES", [movie]), patch.object(demo_store, "MOVIE_CHANGE_REQUESTS", {}):
      with self.assertRaises(HTTPException) as error:
        routes.admin_update_movie_pricing_config("test", payload, db=None, _={})
      self.assertEqual(error.exception.status_code, 400)
      self.assertEqual(movie, before)
      self.assertEqual(demo_store.MOVIE_CHANGE_REQUESTS, {})


if __name__ == "__main__":
  unittest.main()
