from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

from test_cloudflare_release import load_worker_entry_module

entry = load_worker_entry_module()


def fetch(worker, path: str, method: str = "GET"):
    request = SimpleNamespace(method=method, url="https://workdoe.com" + path, headers={})
    return asyncio.run(worker.fetch(request))


class RecoveryContainmentTests(unittest.TestCase):
    def test_sealed_and_invalid_modes_stop_before_auth_storage_or_provider(self):
        for value in ("sealed", "seald", "", None):
            with self.subTest(value=value):
                worker = entry.Default()
                worker.env = SimpleNamespace(WORKDOE_WRITE_MODE=value, DB=object(), MEDIA=object())
                worker.optional_workdoe_user = AsyncMock(side_effect=AssertionError("Account lookup"))
                worker.clerk_frontend_api_proxy = AsyncMock(side_effect=AssertionError("Provider call"))
                with patch.object(entry, "db_run", new=AsyncMock(side_effect=AssertionError("Database access"))):
                    for path, method in (
                        ("/", "GET"), ("/api/jobs/open", "GET"), ("/api/jobs/open;alias", "GET"),
                        ("/api/auth/session", "GET"), ("/media/jobs/1", "HEAD"), ("/login", "GET"),
                        ("/__clerk/v1/environment", "GET"), ("/clerk/webhook", "POST"),
                        ("/api/admin/jobs/1/hide", "POST"), ("/logout", "POST"),
                        ("/health;alias", "GET"), ("/styles.css", "POST"),
                    ):
                        response = fetch(worker, path, method)
                        self.assertEqual(response.status, 503, (path, method))
                        self.assertEqual(response.headers["X-Workdoe-Mode"], "sealed")
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertEqual(response.headers["Retry-After"], "900")
                        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                        if method == "HEAD":
                            self.assertEqual(response.body, "")
                    health = fetch(worker, "/health")
                    self.assertEqual(health.status, 200)
                    self.assertEqual(health.headers["X-Workdoe-Mode"], "sealed")
                    self.assertEqual(json.loads(health.body)["service"], "workdoe-cloudflare-worker")
                    self.assertEqual(fetch(worker, "/safety").status, 200)
                    self.assertNotIn("<script", fetch(worker, "/").body)
                worker.optional_workdoe_user.assert_not_awaited()
                worker.clerk_frontend_api_proxy.assert_not_awaited()

    def test_pause_allows_public_browse_and_preserves_signout_guard(self):
        worker = entry.Default()
        worker.env = SimpleNamespace(WORKDOE_WRITE_MODE="paused")
        worker.entry_shell = AsyncMock(return_value=entry.Response("Public fixtures"))
        worker.public_open_jobs = AsyncMock(return_value=entry.Response("Public leads"))
        self.assertEqual(fetch(worker, "/").body, "Public fixtures")
        self.assertEqual(fetch(worker, "/api/jobs/open").body, "Public leads")
        self.assertEqual(fetch(worker, "/api/jobs/open;alias").status, 503)
        self.assertEqual(fetch(worker, "/dashboard").headers["X-Workdoe-Mode"], "read-only")
        self.assertEqual(fetch(worker, "/api/auth/logout", "POST").status, 403)
        self.assertEqual(fetch(worker, "/health").headers["X-Workdoe-Mode"], "read-only")
        worker.env = SimpleNamespace()
        self.assertNotIn("X-Workdoe-Mode", fetch(worker, "/health").headers)

    def test_containment_stops_background_handlers_and_defers_each_delivery(self):
        class Receipt:
            ack = Mock()
            retry = Mock()

            @property
            def body(self):
                raise AssertionError("Sealed queue read a body")

        for mode in ("paused", "sealed", "invalid"):
            worker = entry.Default()
            worker.env = SimpleNamespace(WORKDOE_WRITE_MODE=mode)
            receipt = Receipt()
            receipt.retry.reset_mock()
            with (
                patch.object(entry, "db_run", new=AsyncMock(side_effect=AssertionError("Database access"))),
                patch.object(entry, "process_email_queue_message", new=AsyncMock(side_effect=AssertionError("Email send"))),
            ):
                asyncio.run(worker.scheduled(SimpleNamespace(cron=entry.EXPIRE_CODES_CRON), None, None))
                for name in ("workdoe-email", "workdoe-media-review"):
                    asyncio.run(worker.queue(SimpleNamespace(queue=name, messages=[receipt])))
            self.assertEqual(receipt.retry.call_args_list, [call({"delaySeconds": 900})] * 2)
            receipt.ack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
