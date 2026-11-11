from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from test_cloudflare_release import load_worker_entry_module

entry = load_worker_entry_module()


class ReleaseMediaBoundariesTests(unittest.TestCase):
    def test_cross_origin_private_media_stops_before_auth_or_storage(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(DB=object(), MEDIA=object())
        worker.optional_workdoe_user = mock.AsyncMock(return_value=None)
        for path in ("/media/jobs/7", "/media/contractors/7"):
            for method in ("GET", "HEAD"):
                for site, mode, destination in (
                    ("same-site", "no-cors", "image"), ("cross-site", "cors", "empty"),
                    ("same-site", "navigate", "iframe"), ("cross-site", "navigate", "object"),
                    ("cross-site", "", ""),
                ):
                    with self.subTest(path=path, method=method, site=site, destination=destination):
                        response = asyncio.run(worker.private_media(SimpleNamespace(method=method, headers={
                            "Sec-Fetch-Site": site, "Sec-Fetch-Mode": mode, "Sec-Fetch-Dest": destination,
                        }), path))
                        self.assertEqual(response.status, 403)
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertEqual(response.headers["Cross-Origin-Resource-Policy"], "same-origin")
                        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        worker.optional_workdoe_user.assert_not_awaited()

        for site, mode, destination in (
            ("same-origin", "no-cors", "image"), ("none", "navigate", "document"),
            ("same-site", "navigate", "document"), ("cross-site", "navigate", "document"),
            ("", "", ""),
        ):
            with self.subTest(site=site, destination=destination):
                response = asyncio.run(worker.private_media(SimpleNamespace(method="GET", headers={
                    "Sec-Fetch-Site": site, "Sec-Fetch-Mode": mode, "Sec-Fetch-Dest": destination,
                }), "/media/jobs/7"))
                self.assertEqual(response.status, 401)
                self.assertEqual(response.headers["Cross-Origin-Resource-Policy"], "same-origin")
        self.assertEqual(worker.optional_workdoe_user.await_count, 5)

    def test_r2_disallows_non_image_metadata_before_get_or_head(self):
        module = load_worker_entry_module()
        worker = module.Default()
        media = SimpleNamespace(
            get=mock.AsyncMock(return_value=SimpleNamespace(body=b"Non-image fixture")),
            head=mock.AsyncMock(return_value=SimpleNamespace()),
        )
        worker.env = SimpleNamespace(MEDIA=media)
        for method in ("GET", "HEAD"):
            for content_type in (None, "", "text/html", "image/svg+xml", "image/png; charset=utf-8"):
                with self.subTest(method=method, content_type=content_type):
                    response = asyncio.run(worker.r2_media_response(
                        SimpleNamespace(method=method), "jobs/1/native.webp",
                        {"id": 1, "content_type": content_type},
                    ))
                    self.assertEqual(response.status, 404)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertNotIn("Content-Disposition", response.headers)
        media.get.assert_not_awaited()
        media.head.assert_not_awaited()

    def test_unknown_browser_pages_offer_a_private_by_default_way_back(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(DB=object())
        headers = {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document",
        }
        for method, request_headers in (("GET", headers), ("HEAD", headers), ("GET", {"Accept": "text/html"})):
            with (
                self.subTest(method=method, headers=request_headers),
                mock.patch.object(worker, "optional_workdoe_user", new=mock.AsyncMock()) as auth,
            ):
                response = asyncio.run(worker.fetch(SimpleNamespace(
                    method=method, url="https://workdoe.com/missing-test-page?private-query-fixture=secret",
                    headers=request_headers,
                )))
                auth.assert_not_awaited()
                self.assertEqual(response.status, 404)
                self.assertEqual(response.headers["Content-Type"], "text/html; charset=utf-8")
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertNotIn("Set-Cookie", response.headers)
                if method == "HEAD":
                    self.assertEqual(response.body, "")
                else:
                    self.assertIn("Page not found", response.body)
                    self.assertIn('href="/">Browse projects</a>', response.body)
                    self.assertNotIn("private-query-fixture", response.body)
                    self.assertNotIn("missing-test-page", response.body)
                    self.assertNotIn("<script", response.body)

    def test_unknown_non_page_requests_keep_the_json_not_found_contract(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace()
        for method, path, mode, dest, accept in (
            ("GET", "/missing-test-page", "", "", "application/json"),
            ("GET", "/missing-test-page", "cors", "empty", "text/html"),
            ("GET", "/missing-test-page", "navigate", "iframe", "text/html"),
            ("GET", "/missing-test-page", "", "", "text/html;q=0"),
            ("POST", "/missing-test-page", "navigate", "document", "text/html"),
            ("GET", "/api/missing-test-page", "navigate", "document", "text/html"),
            ("GET", "/media/missing-test-page", "navigate", "document", "text/html"),
            ("GET", "/missing-test-page.js", "navigate", "document", "text/html"),
        ):
            with self.subTest(method=method, path=path, mode=mode, dest=dest, accept=accept):
                response = asyncio.run(worker.fetch(SimpleNamespace(
                    method=method, url=f"https://workdoe.com{path}",
                    headers={"Accept": accept, "Sec-Fetch-Mode": mode, "Sec-Fetch-Dest": dest},
                )))
                self.assertEqual(response.status, 404)
                self.assertIn("application/json", response.headers["Content-Type"])
                self.assertEqual(json.loads(response.body), {"ok": False, "error": "Not found."})


class ReleaseQueueBoundariesTests(unittest.IsolatedAsyncioTestCase):
    async def test_media_review_rejects_malformed_fields_without_retry_or_raw_data(self):
        worker = entry.Default()
        worker.env = SimpleNamespace()
        private = "synthetic-private-review-value@example.invalid"
        base = entry.media_review_payload(
            "job", photo_id=44, owner_id=12, uploaded_by=2,
            stored_path="jobs/12/synthetic.webp", details={"content_type": "image/webp", "size_bytes": 128},
        )
        for field, value in (
            ("photo_id", private), ("photo_id", []), ("photo_id", True), ("photo_id", 2**53),
            ("owner_id", 12.5), ("uploaded_by", "2"), ("scope", [private]),
            ("stored_path", "jobs/12/../synthetic.webp"), ("stored_path", {"value": private}),
            ("content_type", [private]), ("size_bytes", "128"), ("size_bytes", 1_500_001),
            ("checks", private), ("checks", [private]), ("checks", [{"value": private}]),
        ):
            with self.subTest(field=field, value=value):
                receipt = SimpleNamespace(body=base | {field: value}, attempts=1, ack=mock.Mock(), retry=mock.Mock())

                async def audit(*_args, receipt=receipt, **_kwargs):
                    receipt.ack.assert_not_called()

                with (
                    mock.patch.object(entry, "record_event", new=mock.AsyncMock(side_effect=audit)) as record,
                    mock.patch("builtins.print") as output,
                ):
                    await worker.queue(SimpleNamespace(queue="workdoe-media-review", messages=[receipt]))
                record.assert_awaited_once()
                self.assertEqual(record.await_args.args[1], "media-review-message-invalid")
                self.assertEqual(record.await_args.kwargs["payload"], {
                    "payload_type": "dict", "payload_key_count": len(base), "reason": "invalid-media-review", "attempts": 1,
                })
                self.assertNotIn(private, json.dumps(record.await_args.kwargs))
                receipt.ack.assert_called_once_with()
                receipt.retry.assert_not_called()
                output.assert_not_called()

    async def test_media_review_keeps_minimal_audit_and_isolates_failed_receipt(self):
        worker = entry.Default()
        worker.env = SimpleNamespace()
        private = "synthetic-private-object-name.webp"
        queue = "workdoe-media-review"
        base = entry.media_review_payload(
            "contractor", photo_id=44, owner_id=12, uploaded_by=2,
            stored_path=f"contractors/12/{private}", details={"content_type": "image/webp", "size_bytes": 128},
        )
        invalid = SimpleNamespace(body=base | {"owner_id": None}, attempts=1, ack=mock.Mock(), retry=mock.Mock())
        valid = SimpleNamespace(body=base, attempts=1, ack=mock.Mock(), retry=mock.Mock())

        async def audit(_env, event_type, **_kwargs):
            if event_type == "media-review-message-invalid":
                invalid.ack.assert_not_called()
                raise OSError(private)
            invalid.retry.assert_called_once_with()
            valid.ack.assert_not_called()

        with (
            mock.patch.object(entry, "record_event", new=mock.AsyncMock(side_effect=audit)) as record,
            mock.patch("builtins.print") as output,
        ):
            await worker.queue(SimpleNamespace(queue=queue, messages=[invalid, valid]))
        invalid.ack.assert_not_called()
        invalid.retry.assert_called_once_with()
        valid.ack.assert_called_once_with()
        valid.retry.assert_not_called()
        self.assertEqual(record.await_args.args[1], "media-review-message-accepted")
        self.assertEqual(record.await_args.kwargs["target_type"], "contractor_photo")
        self.assertEqual(record.await_args.kwargs["target_id"], 44)
        self.assertEqual(record.await_args.kwargs["payload"], {
            "queue": queue, "content_type": "image/webp", "size_bytes": 128, "checks": base["checks"], "attempts": 1,
        })
        self.assertNotIn(private, repr(record.await_args_list))
        output.assert_called_once()
        self.assertNotIn(private, output.call_args.args[0])
