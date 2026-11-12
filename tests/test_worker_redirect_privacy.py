from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from test_cloudflare_release import load_worker_entry_module


class WorkerRedirectPrivacyTests(unittest.TestCase):
    def test_public_discovery_does_not_route_semicolon_aliases(self):
        worker = load_worker_entry_module().Default()
        worker.env = SimpleNamespace()
        worker.entry_shell = AsyncMock(side_effect=AssertionError("Entered the public board"))
        worker.public_open_jobs = AsyncMock(side_effect=AssertionError("Entered the public jobs API"))
        for route in ("/", "/api/jobs/open", "/login", "/start", "/create-account"):
            for suffix in (";", ";synthetic-route-probe=1"):
                for method in ("GET", "HEAD"):
                    url = "https://workdoe.com" + route + suffix + "?limit=1"
                    with self.subTest(url=url, method=method):
                        response = asyncio.run(worker.fetch(SimpleNamespace(method=method, url=url, headers={})))
                        self.assertEqual(response.status, 404)
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                        self.assertNotIn("Location", response.headers)
                        self.assertNotIn("synthetic-route-probe", response.body)
                        if method == "HEAD":
                            self.assertEqual(response.body, "")
        worker.entry_shell.assert_not_awaited()
        worker.public_open_jobs.assert_not_awaited()

    def test_https_upgrade_and_legacy_alias_preserve_exact_destination(self):
        worker = load_worker_entry_module().Default()
        worker.env = SimpleNamespace()
        for method, source, expected, cache_control in (
            ("GET", "http://workdoe.com/", "https://workdoe.com/", "no-store"),
            ("HEAD", "http://workdoe.com/create-account?__clerk_ticket=fake%2Bticket&next=%2Fjobs%2F1",
             "https://workdoe.com/create-account?__clerk_ticket=fake%2Bticket&next=%2Fjobs%2F1", "no-store"),
            ("POST", "http://www.workdoe.com/api/auth/session?next=%2Fdashboard",
             "https://www.workdoe.com/api/auth/session?next=%2Fdashboard", "no-store"),
            ("GET", "https://workdoe.com/static/styles.css?v=fake%2Bvalue",
             "https://workdoe.com/styles.css?v=fake%2Bvalue", "no-store"),
            ("HEAD", "https://www.workdoe.com/static/styles.css;probe=synthetic",
             "https://www.workdoe.com/styles.css;probe=synthetic", "no-store"),
            ("GET", "https://workdoe.com/static/account", "https://workdoe.com/account", "no-store"),
            ("HEAD", "https://workdoe.com/static/styles.css", "https://workdoe.com/styles.css", "public, max-age=86400"),
        ):
            with self.subTest(method=method, source=source):
                response = asyncio.run(worker.fetch(SimpleNamespace(method=method, url=source, headers={})))
                self.assertEqual((response.status, response.body), (308, ""))
                self.assertEqual(response.headers["Location"], expected)
                self.assertEqual(response.headers["Cache-Control"], cache_control)
                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
