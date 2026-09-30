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
# Released titles are priced in discs at the admin's exchange rate (default Rs 50 per
# star / Rs 0.10 per disc = 500 discs per star) instead of a hard-coded multiple.
DISCS_PER_STAR = 500


def disc_amounts(star_amounts, percent=100):
  return [amount * DISCS_PER_STAR * percent // 100 for amount in star_amounts]


class TestClient:
  """Small in-process ASGI client, avoiding optional httpx/test dependencies."""
  def __init__(self, app):
    self.app = app

  def request(self, method, path, payload=None, params=None, token=None):
    async def run():
      messages = []
      body = json.dumps(payload).encode() if payload is not None else b""
      headers = [(b"content-type", b"application/json")]
      if token:
        # Endpoints behind get_current_user only accept a Bearer header here;
        # the media endpoints also take ?token= for players that cannot set one.
        headers.append((b"authorization", f"Bearer {token}".encode()))
      request_sent = False
      response_finished = asyncio.Event()
      async def receive():
        # A real server hands the app the request body once and then keeps the
        # channel open until the client goes away. StreamingResponse runs a
        # listen_for_disconnect() task that returns on "http.disconnect" and
        # cancels the body iterator when it fires, so replaying the request body
        # forever hangs the run (the library stream / download endpoints answer
        # with a StreamingResponse) and disconnecting immediately would truncate
        # the body. Wait for the last body chunk, then disconnect.
        nonlocal request_sent
        if not request_sent:
          request_sent = True
          return {"type": "http.request", "body": body, "more_body": False}
        await response_finished.wait()
        return {"type": "http.disconnect"}
      async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
          response_finished.set()
      scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1",
        method=method, scheme="http", path=path, raw_path=path.encode(), root_path="",
        query_string=urlencode(params or {}).encode(),
        headers=headers,
        client=("127.0.0.1", 1234), server=("test", 80))
      await self.app(scope, receive, send)
      status = next(m["status"] for m in messages if m["type"] == "http.response.start")
      text = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body").decode()
      return SimpleNamespace(status_code=status, text=text, json=lambda: json.loads(text))
    return asyncio.run(run())

  def post(self, path, json, token=None):
    return self.request("POST", path, payload=json, token=token)

  def get(self, path, params=None, token=None):
    return self.request("GET", path, params=params, token=token)

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
    app.dependency_overrides[routes.require_admin_or_creator] = lambda: {"id": "test", "role": "super_admin"}
    self.app = app
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

  def put(self, path, payload):
    response = self.client.request("PUT", "/api" + path, payload=payload)
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
      ("library_paid", "library_pricing_options", [dict(quality_code="4k", quality_label="4K", discs_required=7312, sort_order=0)]),
    ):
      with self.subTest(stage=stage):
        movie_id = self.create(stage)
        saved = self.post(f"/admin/movies/{movie_id}/pricing-config", {field: options, "stars_required_theatre": 3})["item"]
        self.assertEqual(saved[field], options)
        for approved in (False, True):
          if approved:
            self.approve(movie_id)
          response = self.client.get("/api/admin/movies")
          self.assertEqual(response.status_code, 200, response.text)
          loaded = next(item for item in response.json()["items"] if item["id"] == movie_id)
          self.assertEqual(loaded[field], options)
          self.assertEqual(loaded["catalog_origin"], "upcoming" if stage == "upcoming" else "library")

  def sign_in_as_viewer(self, user_id="viewer"):
    """Viewer endpoints are auth gated, so the test client needs a signed-in viewer."""
    self.app.dependency_overrides[routes.get_current_user] = lambda: {"id": user_id, "role": "viewer"}
    self.addCleanup(self.app.dependency_overrides.pop, routes.get_current_user, None)

  def test_disc_value_drives_the_star_conversion_rate(self):
    self.sign_in_as_viewer()
    # Rs 50 per star / Rs 0.10 per disc is the shipped default: 500 discs per star.
    rate = self.client.get("/api/users/stars/conversion-rate")
    self.assertEqual(rate.status_code, 200, rate.text)
    self.assertEqual(rate.json(), {"star_price_inr": 50, "disc_price_inr": 0.10, "discs_per_star": DISCS_PER_STAR})
    # Changing only the disc value in the admin panel changes the payout immediately.
    saved = self.put("/admin/star-pricing", {"price_inr": 50, "price_usd": 0, "price_eur": 0, "disc_price_inr": 0.25})
    self.assertEqual(saved["disc_price_inr"], 0.25)
    self.assertEqual(persistence.discs_per_star_from_settings(saved), 200)
    self.assertEqual(self.client.get("/api/users/stars/conversion-rate").json()["discs_per_star"], 200)
    # A request that omits the new field keeps the stored disc price.
    kept = self.put("/admin/star-pricing", {"price_inr": 50, "price_usd": 0, "price_eur": 0})
    self.assertEqual(kept["disc_price_inr"], 0.25)
    self.put("/admin/star-pricing", {"price_inr": 50, "price_usd": 0, "price_eur": 0, "disc_price_inr": 0.10})
    self.assertEqual(self.client.get("/api/users/stars/conversion-rate").json()["discs_per_star"], DISCS_PER_STAR)

  def test_converting_stars_credits_disks_at_the_live_rate(self):
    from backend.models import UserRecord, WalletRecord
    with self.sessions() as session:
      user = persistence.create_user(session, {"name": "Viewer", "email": "convert@email.com",
        "password": "pw12345", "role": "viewer", "status": "active", "star_balance": 3})
      session.query(WalletRecord).filter(WalletRecord.user_id == user["id"]).update({"disks": 10})
      session.commit()
    self.sign_in_as_viewer(user["id"])
    result = self.client.post("/api/users/stars/convert", json={"stars": 2})
    self.assertEqual(result.status_code, 200, result.text)
    body = result.json()
    self.assertEqual(body["discs_credited"], 2 * DISCS_PER_STAR)
    self.assertEqual(body["discs_per_star"], DISCS_PER_STAR)
    self.assertEqual((body["star_balance"], body["disc_balance"]), (1, 10 + 2 * DISCS_PER_STAR))
    # The conversion is written to the ledger, not just returned by the endpoint.
    with self.sessions() as session:
      ledger = session.query(persistence.WalletTransactionRecord).filter(
        persistence.WalletTransactionRecord.user_id == user["id"],
        persistence.WalletTransactionRecord.transaction_type == "star_conversion").all()
      self.assertEqual([(row.stars_delta, row.disks_delta) for row in ledger], [(-2, 2 * DISCS_PER_STAR)])
      # The legacy points mirror stays in sync with the reduced star balance.
      self.assertEqual(session.get(UserRecord, user["id"]).points, 100)
    # Overdrawing the balance is rejected and leaves the wallet untouched.
    rejected = self.client.post("/api/users/stars/convert", json={"stars": 5})
    self.assertEqual(rejected.status_code, 400, rejected.text)
    with self.sessions() as session:
      wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user["id"]).one()
      self.assertEqual(int(wallet.disks), 10 + 2 * DISCS_PER_STAR)
      self.assertEqual(int(wallet.available_stars), 1)


  def test_lifecycle_and_exact_discount_boundaries(self):
    movie_id = self.create()
    self.post(f"/admin/movies/{movie_id}/pricing-config", {"online_pricing_options": PRICES, "stars_required_theatre": 3})
    self.approve(movie_id)
    star_prices = [5, 10, 15, 20]
    cases = [(RELEASE - timedelta(seconds=1), "upcoming", star_prices),
             (RELEASE, "released", star_prices),
             (RELEASE + timedelta(days=1), "released", star_prices)]
    # Months after release mapped to the disc-price percentage that band applies.
    for months, percent in [(1, 100), (4, 80), (6, 50), (12, 10)]:
      boundary = add_calendar_months(RELEASE, months)
      expected = disc_amounts(star_prices, percent)
      previous = self.view(movie_id, boundary - timedelta(seconds=1), "released" if months == 1 else "library")
      self.assertNotEqual([p["amount"] for p in previous["effective_pricing_options"]], expected)
      cases.append((boundary, "library", expected))
    for now, stage, amounts in cases:
      with self.subTest(now=now):
        item = self.view(movie_id, now, stage)
        self.assertEqual([p["amount"] for p in item["effective_pricing_options"]], amounts)
        self.assertEqual({p["currency"] for p in item["effective_pricing_options"]}, {"discs" if stage == "library" else "stars"})
        self.assertEqual(item["catalog_origin"], "upcoming")

  def test_direct_library_prices_are_independent_of_age(self):
    movie_id = self.create("library_paid")
    self.post(f"/admin/movies/{movie_id}/pricing-config", {"library_pricing_options": [
      dict(quality_code="4k", quality_label="4K", discs_required=7312)]})
    self.approve(movie_id)
    for months in (0, 1, 4, 6, 12, 24):
      item = self.view(movie_id, add_calendar_months(RELEASE, months), "library")
      self.assertEqual(item["effective_pricing_options"][0]["amount"], 7312)
      self.assertEqual(item["library_price_source"], "direct")

  def _create_viewer_with_discs(self, disks, email="payplay@email.com", password="pw12345"):
    from backend.models import WalletRecord
    with self.sessions() as session:
      user = persistence.create_user(session, {
        "name": "Viewer", "email": email, "password": password,
        "role": "viewer", "status": "active", "star_balance": 3,
      })
      session.query(WalletRecord).filter(WalletRecord.user_id == user["id"]).update({"disks": disks})
      session.commit()
    return user["id"], email, password

  def _library_movie_with_disc_price(self, discs=7312):
    """A published direct-Library title priced in discs, with its raw video registered."""
    from backend.models import MovieRecord
    movie_id = self.create("library_paid")
    self.post(f"/admin/movies/{movie_id}/pricing-config", {"library_pricing_options": [
      dict(quality_code="4k", quality_label="4K", discs_required=discs)]})
    self.approve(movie_id)
    with self.sessions() as session:
      session.query(MovieRecord).filter(MovieRecord.id == movie_id).update({"source_extension": ".mp4"})
      session.commit()
    return movie_id

  def test_library_pay_and_play_charges_discs_and_unlocks_for_one_week(self):
    from backend.models import LibraryAccessRecord, WalletRecord
    movie_id = self._library_movie_with_disc_price()
    user_id, _email, _password = self._create_viewer_with_discs(9000)
    self.sign_in_as_viewer(user_id)

    # Nothing is unlocked before the purchase.
    before = self.client.get(f"/api/movies/{movie_id}/library/access")
    self.assertEqual(before.status_code, 200, before.text)
    self.assertIsNone(before.json()["access"])

    purchase = self.client.post(f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "4k"})
    self.assertEqual(purchase.status_code, 200, purchase.text)
    body = purchase.json()
    window_days = persistence.LIBRARY_ACCESS_WINDOW_DAYS
    self.assertEqual(body["disc_balance"], 9000 - 7312)
    self.assertTrue(body["access"]["active"])
    self.assertEqual(body["access"]["quality_code"], "4k")
    self.assertEqual(body["access"]["quality_label"], "4K")
    self.assertEqual(body["access"]["window_days"], window_days)
    # The window is 7 days, measured from the purchase.
    self.assertLess(abs(body["access"]["seconds_remaining"] / 86400 - window_days), 0.01)

    # The charge is persisted with a ledger row, not just returned by the endpoint.
    with self.sessions() as session:
      wallet = session.query(WalletRecord).filter(WalletRecord.user_id == user_id).one()
      self.assertEqual(int(wallet.disks), 9000 - 7312)
      ledger = session.query(persistence.WalletTransactionRecord).filter(
        persistence.WalletTransactionRecord.user_id == user_id,
        persistence.WalletTransactionRecord.transaction_type == "library_unlock").all()
      self.assertEqual([row.disks_delta for row in ledger], [-7312])
      self.assertEqual(session.query(LibraryAccessRecord).count(), 1)

    # Re-confirming the same quality inside the window never charges twice.
    again = self.client.post(f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "4k"})
    self.assertEqual(again.status_code, 200, again.text)
    self.assertEqual(again.json()["disc_balance"], 9000 - 7312)
    self.assertTrue(again.json()["access"]["active"])

    # One read lists every unlock so the app can mark its Library cards.
    listed = self.client.get("/api/users/library-access")
    self.assertEqual(listed.status_code, 200, listed.text)
    self.assertEqual([item["movie_id"] for item in listed.json()["items"]], [movie_id])

  def test_expired_library_window_is_not_active_and_can_be_bought_again(self):
    from backend.models import LibraryAccessRecord
    movie_id = self._library_movie_with_disc_price(discs=100)
    user_id, _email, _password = self._create_viewer_with_discs(500)
    self.sign_in_as_viewer(user_id)
    self.client.post(f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "4k"})

    # Move the window into the past: reads must report it expired, not active.
    with self.sessions() as session:
      session.query(LibraryAccessRecord).update({"expires_at": datetime.utcnow() - timedelta(minutes=1)})
      session.commit()
    expired = self.client.get(f"/api/movies/{movie_id}/library/access").json()["access"]
    self.assertFalse(expired["active"])
    self.assertEqual(expired["status"], "expired")
    self.assertEqual(expired["seconds_remaining"], 0)

    # Buying again re-opens the window and charges the current price.
    renewed = self.client.post(f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "4k"})
    self.assertEqual(renewed.status_code, 200, renewed.text)
    self.assertTrue(renewed.json()["access"]["active"])
    self.assertEqual(renewed.json()["disc_balance"], 300)

  def test_library_purchase_rejects_an_empty_wallet_and_unknown_quality(self):
    from backend.models import WalletRecord
    movie_id = self._library_movie_with_disc_price(discs=7312)
    user_id, _email, _password = self._create_viewer_with_discs(10)
    self.sign_in_as_viewer(user_id)

    rejected = self.client.post(f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "4k"})
    self.assertEqual(rejected.status_code, 400, rejected.text)
    self.assertIn("Not enough discs", rejected.text)
    unknown = self.client.post(f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "1080p"})
    self.assertEqual(unknown.status_code, 400, unknown.text)
    with self.sessions() as session:
      self.assertEqual(int(session.query(WalletRecord).filter(WalletRecord.user_id == user_id).one().disks), 10)

  def test_library_download_needs_an_active_unlock(self):
    movie_id = self._library_movie_with_disc_price(discs=50)
    _user_id, email, password = self._create_viewer_with_discs(50, email="download@email.com")
    login = self.client.post("/api/auth/login", json={"email": email, "password": password})
    self.assertEqual(login.status_code, 200, login.text)
    token = login.json()["token"]

    # Signed in but not unlocked: the file must not be downloadable.
    blocked = self.client.get(f"/api/movies/{movie_id}/library/download", params={"token": token})
    self.assertEqual(blocked.status_code, 403, blocked.text)

    # The purchase endpoint is auth gated by the Bearer header, so a token-only
    # call would 401 and leave the title locked for the rest of this test.
    purchase = self.client.post(
      f"/api/movies/{movie_id}/library/purchase", json={"quality_code": "4k"}, token=token)
    self.assertEqual(purchase.status_code, 200, purchase.text)
    with patch.object(routes, "media_object_exists", return_value=True), \
      patch.object(routes, "verified_media_download_url", return_value=None), \
      patch.object(routes, "download_media_object", return_value=b"library-mp4-bytes"):
      streamed = self.client.get(
        f"/api/movies/{movie_id}/content/stream", params={"token": token, "quality": "4k", "direct": 1})
      self.assertEqual(streamed.status_code, 200, streamed.text)
      self.assertTrue(streamed.text.startswith("library-mp4-bytes"))
      downloaded = self.client.get(f"/api/movies/{movie_id}/library/download", params={"token": token})
      self.assertEqual(downloaded.status_code, 200, downloaded.text)
      self.assertTrue(downloaded.text.startswith("library-mp4-bytes"))

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
      dict(quality_code="4k", quality_label="4K", discs_required=1)], stars_required_theatre=3)
    with patch.object(demo_store, "MOVIES", [movie]), patch.object(demo_store, "MOVIE_CHANGE_REQUESTS", {}):
      with self.assertRaises(HTTPException) as error:
        routes.admin_update_movie_pricing_config("test", payload, db=None, _={})
      self.assertEqual(error.exception.status_code, 400)
      self.assertEqual(movie, before)
      self.assertEqual(demo_store.MOVIE_CHANGE_REQUESTS, {})


if __name__ == "__main__":
  unittest.main()
