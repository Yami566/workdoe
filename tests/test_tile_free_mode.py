from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from test_cloudflare_release import load_worker_entry_module

from workdoe import create_app, get_db
from workdoe.map_tiles import area_map_bounds, map_tile_configuration

OSM = "https://tile.openstreetmap.org"
TILE_URL = "https://tiles.example.invalid/{z}/{x}/{y}.png"
AREA_ASSET = "/dmv-area-50fe6cd3.geojson"
STAGING = "https://staging-fixture.workdoe.com"
CONTRACTOR_ROW = {
    "id": 81, "title": "Synthetic window cleaning", "description": "Clean ground-floor windows.",
    "city": "Arlington", "state": "VA", "zip_code": "22201", "category": "Window cleaning",
    "service_type_slug": "window-cleaning", "service_group_slug": "cleaning-upkeep",
    "status": "open", "bidding_closes_at": "2099-12-31T12:00:00+00:00",
}


def worker_for_mode(**overrides):
    module = load_worker_entry_module()
    worker = module.Default()
    worker.env = SimpleNamespace(**({
        "WORKDOE_ENV": "production",
        "WORKDOE_AUTH_PROVIDER": "clerk",
        "CLERK_PUBLISHABLE_KEY": "pk_live_synthetic_fixture",
        "WRITE_RATE_LIMITER": SimpleNamespace(limit=AsyncMock(return_value={"success": True})),
    } | overrides))
    return module, worker


def request(url, method="GET"):
    return SimpleNamespace(url=url, method=method, headers={})


async def render_leads(module, worker, incoming):
    with (
        patch.object(worker.env, "DB", object(), create=True),
        patch.object(worker, "optional_workdoe_user", AsyncMock(return_value={
            "id": 7, "role": "contractor", "status": "active", "display_name": "Fixture contractor",
        })),
        patch.object(module, "unread_message_count_for_user", AsyncMock(return_value=0)),
        patch.object(module, "contractor_leads_for_user", AsyncMock(return_value=[CONTRACTOR_ROW])),
        patch.object(module, "contractor_market_fit_for_user", AsyncMock(return_value={})),
        patch.object(module, "contractor_preferences_for_user", AsyncMock(return_value=None)),
    ):
        return await worker.fetch(incoming)


class TileFreeModeTests(IsolatedAsyncioTestCase):
    def assert_tile_free(self, response):
        self.assertEqual(response.status, 200)
        self.assertIn("market-list-only", response.body)
        for marker in ("data-tile-url", "map-jobs-data", "market-map-panel", "/map.js", "/vendor/leaflet"):
            self.assertNotIn(marker, response.body)
        self.assertNotIn(OSM, response.headers["Content-Security-Policy"])
        self.assertNotIn("https://tiles.example.invalid", response.headers["Content-Security-Policy"])

    async def test_public_entry_disables_map_for_list_and_incomplete_configs(self):
        for settings in (
            {"WORKDOE_MAP_MODE": "list", "WORKDOE_MAP_TILE_URL": TILE_URL, "WORKDOE_MAP_TILE_ATTRIBUTION": "Fixture maps"},
            {"WORKDOE_MAP_TILE_URL": TILE_URL},
            {"WORKDOE_MAP_TILE_URL": "https://unsafe.invalid:8443/{z}/{x}/{y}.png", "WORKDOE_MAP_TILE_ATTRIBUTION": "Fixture"},
            {},
        ):
            _, worker = worker_for_mode(**settings)
            for path in ("/", "/login", "/create-account"):
                with self.subTest(path=path, settings=settings):
                    response = await worker.fetch(request("https://workdoe.com" + path))
                    self.assert_tile_free(response)
                    self.assertIn('name="q"', response.body)
                    head = await worker.fetch(request("https://workdoe.com" + path, "HEAD"))
                    self.assertEqual(head.body, "")
                    self.assertEqual(head.headers["Content-Security-Policy"], response.headers["Content-Security-Policy"])

    async def test_staging_can_enable_only_the_same_origin_area_map(self):
        for mode in (None, "list", "map", "area"):
            module, worker = worker_for_mode(
                WORKDOE_ENV="staging", WORKDOE_WRITE_MODE="normal", WORKDOE_PUBLIC_URL=STAGING,
                WORKDOE_DOMAIN="staging-fixture.workdoe.com", WORKDOE_MAP_MODE=mode,
                WORKDOE_MAP_TILE_URL=TILE_URL, WORKDOE_MAP_TILE_ATTRIBUTION="Fixture",
            )
            for path in ("/", "/leads"):
                with self.subTest(mode=mode, path=path):
                    incoming = request(STAGING + path)
                    response = await (worker.fetch(incoming) if path == "/" else render_leads(module, worker, incoming))
                    if mode == "area":
                        self.assertEqual(response.status, 200)
                        self.assertIn(f'data-tile-url="{AREA_ASSET}"', response.body)
                        self.assertNotIn(TILE_URL, response.body)
                        self.assertNotIn(OSM, response.headers["Content-Security-Policy"])
                        self.assertNotIn("https://tiles.example.invalid", response.headers["Content-Security-Policy"])
                    else:
                        self.assert_tile_free(response)

    async def test_area_map_uses_reviewed_asset_without_any_tile_origin(self):
        module, worker = worker_for_mode(
            WORKDOE_MAP_MODE=" Area ", WORKDOE_MAP_TILE_URL=TILE_URL,
            WORKDOE_MAP_TILE_ATTRIBUTION="Unrelated provider",
        )
        for path in ("/", "/login", "/create-account", "/leads"):
            with self.subTest(path=path):
                incoming = request("https://workdoe.com" + path)
                response = await (
                    render_leads(module, worker, incoming) if path == "/leads" else worker.fetch(incoming)
                )
                self.assertEqual(response.status, 200)
                self.assertIn(f'data-tile-url="{AREA_ASSET}"', response.body)
                self.assertIn("U.S. Census Bureau (2025 boundaries)", response.body)
                self.assertNotIn("tiles.example.invalid", response.body)
                self.assertNotIn("tiles.example.invalid", response.headers["Content-Security-Policy"])
                self.assertNotIn(OSM, response.headers["Content-Security-Policy"])
                if path == "/leads":
                    self.assertIn("Locations stay approximate, even after approval.", response.body)
        fragment = await worker.fetch(request("https://workdoe.com/login?embed=1"))
        self.assertNotIn("data-tile-url", fragment.body)
        self.assertNotIn(AREA_ASSET, fragment.body)

    async def test_street_map_pairs_the_configured_origin_with_the_rendered_url(self):
        module, worker = worker_for_mode(WORKDOE_MAP_TILE_URL=TILE_URL, WORKDOE_MAP_TILE_ATTRIBUTION="Fixture")
        for path in ("/", "/leads"):
            incoming = request("https://workdoe.com" + path)
            response = await worker.fetch(incoming) if path == "/" else await render_leads(module, worker, incoming)
            self.assertIn(f'data-tile-url="{TILE_URL}"', response.body)
            self.assertIn("https://tiles.example.invalid", response.headers["Content-Security-Policy"])
            self.assertNotIn(OSM, response.headers["Content-Security-Policy"])
        fragment = await worker.fetch(request("https://workdoe.com/login?embed=1"))
        self.assertNotIn("data-tile-url", fragment.body)
        self.assertNotIn("https://tiles.example.invalid", fragment.headers["Content-Security-Policy"])

    async def test_contractor_list_retains_filters_and_direct_detail_links(self):
        module, worker = worker_for_mode(WORKDOE_MAP_MODE="list")
        incoming = request("https://workdoe.com/leads?q=windows")
        response = await render_leads(module, worker, incoming)
        self.assert_tile_free(response)
        self.assertIn('aria-controls="lead-results"', response.body)
        self.assertIn('value="windows"', response.body)
        self.assertIn('href="/jobs/81"', response.body)
        head = await render_leads(module, worker, request(incoming.url, "HEAD"))
        self.assertEqual(head.body, "")
        self.assertEqual(head.headers["Content-Security-Policy"], response.headers["Content-Security-Policy"])


class FlaskMapParityTests(TestCase):
    def flask_client(self, **settings):
        directory = Path(self.enterContext(TemporaryDirectory()))
        app = create_app({
            "TESTING": True, "WORKDOE_ENV": "local", "PRODUCTION": False, "AUTH_PROVIDER": "local",
            "SEED_DEMO_DATA": False, "DATABASE": str(directory / "test.sqlite3"),
            "UPLOAD_ROOT": str(directory / "uploads"), **settings,
        })
        with app.app_context():
            db = get_db()
            db.execute(
                "INSERT INTO users (id, email, password_hash, role, display_name, email_verified, created_at) "
                "VALUES (7, 'fixture@example.invalid', '', 'contractor', 'Synthetic Contractor', 1, '2026-01-01')"
            )
            db.commit()
        return app.test_client()

    def test_map_configuration_matches_worker_for_reviewed_modes(self):
        module = load_worker_entry_module()
        for mode, url, credit in (
            (None, None, None), ("area", TILE_URL, "Ignored"), ("list", TILE_URL, "Fixture"),
            ("map", TILE_URL, "Fixture"), ("map", TILE_URL, None), (" AREA ", None, None),
            ("map", "https://tiles.example.invalid:8443/{z}/{x}/{y}.png", "Fixture"),
            ("map", "/dmv-area-50fe6cd3.geojson", "Not an approved area configuration"), ("invalid", None, None),
        ):
            with self.subTest(mode=mode, url=url, credit=credit):
                self.assertEqual(
                    map_tile_configuration(url, credit, map_mode=mode),
                    module.map_tile_configuration(url, credit, map_mode=mode),
                )

    def test_area_list_and_invalid_modes_do_not_allow_external_tiles(self):
        for mode in ("area", "list", "invalid"):
            client = self.flask_client(MAP_MODE=mode, MAP_TILE_URL=TILE_URL, MAP_TILE_ATTRIBUTION="Fixture")
            with client.session_transaction() as session:
                session["user_id"] = 7
            # Direct auth views require a signed-out session.
            anon = client.application.test_client()
            for route in ("/", "/login", "/create-account", "/start", "/leads"):
                with self.subTest(mode=mode, route=route):
                    response = (client if route == "/leads" else anon).get(route)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn(OSM, response.headers["Content-Security-Policy"])
                    self.assertNotIn("tiles.example.invalid", response.headers["Content-Security-Policy"])
                    if route == "/leads":
                        self.assertIn(b"Locations stay approximate, even after approval.", response.data)
                    if mode == "area":
                        self.assertIn(f'data-tile-url="{AREA_ASSET}"'.encode(), response.data)
                        self.assertIn(f"data-area-map-bounds='{json.dumps(area_map_bounds())}'".encode(), response.data)
                        self.assertIn(b"/static/vendor/leaflet/leaflet.js", response.data)
                    else:
                        for marker in (
                            b"map-jobs-data", b"data-tile-url", b"data-area-map-bounds",
                            b"/vendor/leaflet", b"map.js", b"lead-map",
                        ):
                            self.assertNotIn(marker, response.data)
                        self.assertIn(b'role="search"', response.data)
            fragment = anon.get("/login?embed=1")
            self.assertNotIn(b"data-tile-url", fragment.data)
            self.assertNotIn(b"/vendor/leaflet", fragment.data)
            self.assertIn(b"data-dialog-fragment", fragment.data)

    def test_street_origin_matches_only_map_documents(self):
        client = self.flask_client(MAP_MODE="map", MAP_TILE_URL=TILE_URL, MAP_TILE_ATTRIBUTION="Fixture")
        for route in ("/", "/login", "/login?embed=1", "/privacy", "/api/jobs/open"):
            with self.subTest(route=route):
                response = client.get(route)
                enabled = route in ("/", "/login")
                self.assertEqual(f'data-tile-url="{TILE_URL}"'.encode() in response.data, enabled)
                self.assertNotIn(b"data-area-map-bounds", response.data)
                self.assertEqual("https://tiles.example.invalid" in response.headers["Content-Security-Policy"], enabled)
                self.assertNotIn(OSM, response.headers["Content-Security-Policy"])

    def test_flask_serves_exact_public_boundary_asset(self):
        client = self.flask_client(MAP_MODE="area")
        expected = (Path(__file__).resolve().parents[1] / "workdoe/static" / AREA_ASSET[1:]).read_bytes()
        for method in ("GET", "HEAD"):
            with client.open("/static" + AREA_ASSET, method=method) as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, expected if method == "GET" else b"")
                self.assertEqual(response.mimetype, "application/geo+json")
                self.assertEqual(response.headers["Cache-Control"], "public, max-age=31556952, immutable")
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")


async def browser_documents():
    module, worker = worker_for_mode(WORKDOE_MAP_MODE="list", CLERK_FRONTEND_API_URL="/__clerk")
    documents = {}
    for path in ("/", "/?q=cleaning", "/?job_id=demo-02", "/login", "/leads"):
        incoming = request("https://workdoe.com" + path)
        response = await render_leads(module, worker, incoming) if path == "/leads" else await worker.fetch(incoming)
        documents[path] = {"html": response.body, "csp": response.headers["Content-Security-Policy"]}
    return documents


if __name__ == "__main__":
    print(json.dumps(asyncio.run(browser_documents())))
