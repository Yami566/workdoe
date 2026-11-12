from __future__ import annotations

import tempfile
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from test_cloudflare_release import load_worker_entry_module

from workdoe import create_app, public_job_query

API = "/api/jobs/open"
REJECTIONS = (
    ("pad=" + "x" * 4093, 414),
    ("&".join(f"padding{i}=x" for i in range(33)), 400),
)
METHOD_CASES = (("OPTIONS", 200), ("POST", 405), ("PUT", 405), ("DELETE", 405))


class WorkerDiscoveryRequestTests(IsolatedAsyncioTestCase):
    async def test_rejects_before_query_parsing_auth_or_discovery(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(DB=object())
        with (
            patch.object(module, "parse_qs", side_effect=AssertionError("Parsed rejected query")),
            patch.object(worker, "optional_workdoe_user", AsyncMock(side_effect=AssertionError("Loaded account"))),
            patch.object(worker, "entry_shell", AsyncMock(side_effect=AssertionError("Reached board"))),
            patch.object(worker, "public_open_jobs", AsyncMock(side_effect=AssertionError("Reached jobs API"))),
        ):
            for route in ("/", API):
                for query, status in REJECTIONS:
                    for method in ("GET", "HEAD"):
                        with self.subTest(route=route, method=method, status=status):
                            response = await worker.fetch(SimpleNamespace(
                                method=method, url=f"https://workdoe.com{route}?{query}", headers={},
                            ))
                            self.assertEqual(response.status, status)
                            self.assertEqual(response.headers["Cache-Control"], "no-store")
                            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                            self.assertNotIn(query, response.body)
                            if method == "HEAD":
                                self.assertEqual(response.body, "")
            for method, status in METHOD_CASES:
                for headers in ({}, {"X-Workdoe-Request": "same-origin"}):
                    with self.subTest(method=method, marker=bool(headers)):
                        response = await worker.fetch(SimpleNamespace(
                            method=method, url=f"https://workdoe.com{API}?pad=fixture", headers=headers,
                        ))
                        self.assertEqual(response.status, status)
                        self.assertEqual(response.headers["Allow"], "GET, HEAD, OPTIONS")
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                        if method == "OPTIONS":
                            self.assertEqual(response.body, "")

    async def test_preserves_supported_queries_and_clerk_entry(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace()
        valid_query = "q=paint%26trim&limit=12"
        with (
            patch.object(worker, "entry_shell", AsyncMock(return_value="entry")) as entry,
            patch.object(worker, "public_open_jobs", AsyncMock(return_value="api")) as api,
        ):
            for path, handler, expected in (("/", entry, "entry"), (API, api, "api")):
                request = SimpleNamespace(method="GET", url=f"https://workdoe.com{path}?{valid_query}", headers={})
                self.assertEqual(await worker.fetch(request), expected)
                handler.assert_awaited_once()
            entry.reset_mock()
            request = SimpleNamespace(
                method="GET", url="https://workdoe.com/create-account?__clerk_ticket=" + "x" * 4097, headers={},
            )
            self.assertEqual(await worker.fetch(request), "entry")
            entry.assert_awaited_once_with(request, "/create-account")


class FlaskDiscoveryRequestTests(TestCase):
    def test_rejected_requests_do_not_open_database_even_with_session(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app({
                "TESTING": True, "DATABASE": f"{root}/test.sqlite3",
                "UPLOAD_ROOT": f"{root}/uploads", "SEED_DEMO_DATA": False,
            })
            client = app.test_client()
            with client.session_transaction() as session:
                session["user_id"] = 1
            with patch("workdoe.get_db", side_effect=AssertionError("Opened database")):
                for route in ("/", API):
                    for query, status in REJECTIONS:
                        for method in ("GET", "HEAD"):
                            with self.subTest(route=route, method=method, status=status):
                                response = client.open(f"{route}?{query}", method=method)
                                self.assertEqual(response.status_code, status)
                                self.assertEqual(response.headers["Cache-Control"], "no-store")
                                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                                self.assertNotIn(query.encode(), response.data)
                                if method == "HEAD":
                                    self.assertEqual(response.data, b"")
                for method, status in METHOD_CASES:
                    with self.subTest(method=method):
                        response = client.open(API, method=method)
                        self.assertEqual(response.status_code, status)
                        self.assertEqual(response.headers["Allow"], "GET, HEAD, OPTIONS")
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                        if method == "OPTIONS":
                            self.assertEqual(response.data, b"")

    def test_query_budget_uses_encoded_bytes_and_literal_field_separators(self):
        check = public_job_query.public_query_envelope_rejection
        for value in ("q=" + "x" * 4094, b"q=" + b"x" * 4094):
            self.assertIsNone(check(value))
        self.assertIsNone(check("q=" + "\u00e9" * 2047))
        self.assertEqual(check("q=" + "\u00e9" * 2048)[0], 414)
        self.assertIsNone(check("q=" + "%26" * 80 + "&pad=1" * 31))
        self.assertEqual(check("q=x" + "&pad=1" * 32)[0], 400)
