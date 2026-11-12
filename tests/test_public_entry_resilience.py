from __future__ import annotations

import json
import re
from html import unescape
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from test_tile_free_mode import CONTRACTOR_ROW, TILE_URL, request, worker_for_mode

BASE = "https://workdoe.com"
TICKET = "fixture-invitation"


class PublicEntryResilienceTests(IsolatedAsyncioTestCase):
    async def test_public_reads_fall_back_to_declared_binding_with_a_distinct_anonymous_key(self):
        limiter = AsyncMock(return_value={"success": True})
        module, worker = worker_for_mode(DB=object(), WRITE_RATE_LIMITER=SimpleNamespace(limit=limiter))
        with patch.object(module, "db_run", AsyncMock(return_value={"results": []})) as rows:
            page = await worker.fetch(request(f"{BASE}/"))
            api = await worker.fetch(request(f"{BASE}/api/jobs/open"))
        self.assertEqual((page.status, api.status, rows.await_count), (200, 200, 2))
        self.assertEqual(limiter.await_count, 2)
        self.assertTrue(all(call.args == ({"key": "public-discovery"},) for call in limiter.await_args_list))

    async def test_missing_public_and_fallback_bindings_fail_closed_outside_local_development(self):
        for environment in ("production", " PrOdUcTiOn ", "staging", "", "unrecognized"):
            with self.subTest(environment=environment):
                module, worker = worker_for_mode(
                    WORKDOE_ENV=environment, DB=object(), WRITE_RATE_LIMITER=None,
                )
                with patch.object(module, "db_run", AsyncMock()) as rows:
                    response = await worker.public_open_jobs(request(f"{BASE}/api/jobs/open"))
                self.assertEqual(response.status, 503)
                self.assertEqual(response.headers["Retry-After"], "60")
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                rows.assert_not_awaited()
        for environment in ("local", "development", "test"):
            with self.subTest(environment=environment):
                module, worker = worker_for_mode(WORKDOE_ENV=environment, WRITE_RATE_LIMITER=None)
                self.assertIsNone(await module.public_discovery_limit_status(worker.env))

    async def test_dedicated_binding_takes_precedence_and_fallback_refusals_do_not_read_d1(self):
        fallback = AsyncMock(return_value={"success": False})
        dedicated = AsyncMock(return_value={"success": True})
        module, worker = worker_for_mode(
            DB=object(), WRITE_RATE_LIMITER=SimpleNamespace(limit=fallback),
            PUBLIC_DISCOVERY_RATE_LIMITER=SimpleNamespace(limit=dedicated),
        )
        self.assertIsNone(await module.public_discovery_limit_status(worker.env))
        dedicated.assert_awaited_once()
        fallback.assert_not_awaited()
        for result, expected in (({"success": False}, 429), ({}, 503), (RuntimeError("private fixture"), 503)):
            with self.subTest(expected=expected, result=type(result)):
                limiter = AsyncMock(side_effect=result) if isinstance(result, Exception) else AsyncMock(return_value=result)
                module, worker = worker_for_mode(DB=object(), WRITE_RATE_LIMITER=SimpleNamespace(limit=limiter))
                with patch.object(module, "db_run", AsyncMock()) as rows:
                    response = await worker.fetch(request(f"{BASE}/api/jobs/open"))
                self.assertEqual(response.status, expected)
                self.assertNotIn("private fixture", response.body)
                rows.assert_not_awaited()

    async def test_missing_clerk_config_returns_script_free_head_and_get_without_d1(self):
        module, worker = worker_for_mode(DB=object(), CLERK_PUBLISHABLE_KEY="")
        with patch.object(module, "db_run", AsyncMock()) as lookup:
            url = f"{BASE}/create-account?__clerk_ticket={TICKET}"
            get = await worker.fetch(request(url))
            head = await worker.fetch(request(url, "HEAD"))
        lookup.assert_not_awaited()
        self.assertEqual((get.status, head.status, head.body), (503, 503, ""))
        self.assertEqual(get.headers, head.headers)
        self.assertEqual(get.headers["Referrer-Policy"], "strict-origin")
        self.assertEqual(get.headers["Retry-After"], "60")
        self.assertEqual(get.headers["Cache-Control"], "no-store")
        self.assertIn('href="/">Browse projects', get.body)
        self.assertIn("Sign-in temporarily unavailable", get.body)
        self.assertNotIn("<script", get.body)
        self.assertNotIn(TICKET, get.body)

    async def test_failed_listings_do_not_render_samples_or_block_account_entry(self):
        module, worker = worker_for_mode(
            DB=object(), WORKDOE_MAP_TILE_URL=TILE_URL, WORKDOE_MAP_TILE_ATTRIBUTION="Fixture",
        )
        broken = AsyncMock(side_effect=RuntimeError("database-error-fixture"))
        with patch.object(module, "db_run", broken):
            board = await worker.fetch(request(f"{BASE}/?q=search-marker"))
            board_head = await worker.fetch(request(f"{BASE}/", "HEAD"))
            direct = await worker.fetch(request(f"{BASE}/login?next=/dashboard"))
            embedded = await worker.fetch(request(f"{BASE}/create-account?embed=1&job_id=1&__clerk_ticket={TICKET}"))
        self.assertEqual(broken.await_count, 4)
        self.assertEqual((board.status, board_head.status, board_head.body), (503, 503, ""))
        self.assertIn("Projects temporarily unavailable", board.body)
        self.assertIn('href="/login">Sign in', board.body)
        self.assertNotIn("search-marker", board.body)
        for response in (board, direct, embedded):
            self.assertNotIn("database-error-fixture", response.body)
            self.assertNotIn("map-jobs-data", response.body)
            self.assertNotIn("data-tile-url", response.body)
            self.assertNotIn("/vendor/leaflet", response.body)
            self.assertNotIn("tiles.example.invalid", response.headers["Content-Security-Policy"])
        for response in (direct, embedded):
            self.assertEqual(response.status, 200)
            self.assertIn("Project listings are temporarily unavailable", response.body)
            self.assertIn("data-dialog-fragment", response.body)
            self.assertIn("data-clerk-entry", response.body)
            self.assertNotIn("sample-data-note", response.body)
        self.assertIn('data-redirect-url="/dashboard"', direct.body)
        self.assertEqual(embedded.headers["Referrer-Policy"], "strict-origin")
        self.assertNotIn(TICKET, embedded.body)

    async def test_budget_protects_d1_without_blocking_generic_or_sample_dialog(self):
        for result, expected in (({"success": False}, 429), ({}, 503), (RuntimeError("fixture"), 503)):
            with self.subTest(status=expected, result=type(result)):
                limiter = (
                    AsyncMock(side_effect=result) if isinstance(result, RuntimeError) else AsyncMock(return_value=result)
                )
                module, worker = worker_for_mode(
                    DB=object(), PUBLIC_DISCOVERY_RATE_LIMITER=SimpleNamespace(limit=limiter),
                )
                with patch.object(module, "db_run", AsyncMock(return_value={"results": []})) as db_lookup:
                    invalid = await worker.fetch(request(f"{BASE}/api/jobs/open?north=39"))
                    options = await worker.fetch(request(f"{BASE}/api/jobs/open", "OPTIONS"))
                    self.assertEqual((invalid.status, options.status), (400, 200))
                    limiter.assert_not_awaited()
                    for path in ("/", "/api/jobs/open"):
                        get = await worker.fetch(request(BASE + path))
                        head = await worker.fetch(request(BASE + path, "HEAD"))
                        self.assertEqual((get.status, head.status, head.body), (expected, expected, ""))
                        self.assertEqual(get.headers, head.headers)
                        self.assertEqual(get.headers["Retry-After"], "60")
                        self.assertEqual(get.headers["Cache-Control"], "no-store")
                        if path.startswith("/api"):
                            self.assertFalse(json.loads(get.body)["ok"])
                    direct = await worker.fetch(request(f"{BASE}/login"))
                    self.assertEqual(direct.status, 200)
                    self.assertIn("Project listings are temporarily unavailable", direct.body)
                    self.assertEqual(limiter.await_count, 5)
                    for suffix in ("", "&job_id=demo-02", "&job_id=" + "9" * 4301, "&job_id=\u00b2"):
                        modal = await worker.fetch(request(f"{BASE}/login?embed=1{suffix}"))
                        self.assertEqual(modal.status, 200)
                        self.assertIn("data-clerk-entry", modal.body)
                        self.assertNotIn("Project listings are temporarily unavailable", modal.body)
                    self.assertEqual(limiter.await_count, 5)
                    self.assertTrue(all(call.args == ({"key": "public-discovery"},) for call in limiter.await_args_list))
                    db_lookup.assert_not_awaited()

    async def test_allowing_budget_preserves_query_and_samples(self):
        limiter = AsyncMock(return_value={"success": True})
        module, worker = worker_for_mode(DB=object(), PUBLIC_DISCOVERY_RATE_LIMITER=SimpleNamespace(limit=limiter))
        with patch.object(module, "db_run", AsyncMock(return_value={"results": []})) as rows:
            response = await worker.fetch(request(f"{BASE}/"))
        rows.assert_awaited_once()
        limiter.assert_awaited_once_with({"key": "public-discovery"})
        self.assertEqual(response.status, 200)
        self.assertIn("Sample listings are not active requests.", response.body)

    async def test_page_and_api_use_one_equivalent_bounded_query_each(self):
        module, worker = worker_for_mode(DB=object(), WORKDOE_MAP_MODE="area")
        rows = [
            CONTRACTOR_ROW | {"id": n, "title": f"Fixture window cleaning {n}", "license_preference": 1}
            for n in range(1, 54)
        ]
        rows[1]["title"] = "private@fixture.invalid"
        with patch.object(module, "db_run", AsyncMock(return_value={"results": rows})) as read:
            area = "north=39.9&south=38.85&east=-77&west=-77.2"
            response = await worker.fetch(request(f"{BASE}/?{area}"))
            read.assert_awaited_once()
            api = json.loads((await worker.fetch(request(f"{BASE}/api/jobs/open?limit=50&{area}"))).body)
        self.assertEqual(read.await_count, 2)
        self.assertEqual(read.await_args_list[0], read.await_args_list[1])
        marker = '<script id="map-jobs-data" type="application/json">'
        jobs = json.loads(response.body.split(marker, 1)[1].split("</script>", 1)[0])
        self.assertEqual(jobs, api["jobs"])
        self.assertEqual(len(jobs), 50)
        self.assertTrue(api["next_cursor"])
        self.assertNotIn("private@fixture.invalid", response.body)
        self.assertTrue(all("zip_code" not in job and "description" not in job for job in jobs))
        self.assertEqual(api["viewport"]["north"], 39.5)
        snapshot = json.loads(unescape(re.search(r'data-map-snapshot="([^"]+)"', response.body)[1]))
        self.assertEqual(snapshot, {"viewport": api["viewport"], "truncated": True})
        self.assertIn('data-project-truncation>More projects', response.body)
        self.assertIn('name="north" value="39.5"', response.body)

    async def test_invalid_page_bounds_recover_without_weakening_api_validation(self):
        module, worker = worker_for_mode(DB=object(), WORKDOE_MAP_MODE="area")
        with patch.object(module, "db_run", AsyncMock(return_value={"results": []})) as read:
            response = await worker.fetch(request(f"{BASE}/?north=39.5"))
            api = await worker.fetch(request(f"{BASE}/api/jobs/open?north=39.5"))
        self.assertEqual((response.status, api.status), (200, 400))
        read.assert_awaited_once()
        self.assertNotIn('name="north"', response.body)
        self.assertIn('data-map-snapshot="{&quot;viewport&quot;:null', response.body)
