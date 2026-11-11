from __future__ import annotations

import hashlib
import json
from unittest import TestCase
from unittest.mock import Mock, patch

from test_cloudflare_release import load_workdoe_production_smoke_script

COMMIT = "a" * 40
ORIGIN = "https://workdoe.com"


class CommitAssetSmokeTests(TestCase):
    def setUp(self):
        self.module = load_workdoe_production_smoke_script()
        self.assets = {name: f"exact {name}\n".encode() for name in self.module.VERSIONED_STATIC_ASSET_FILES}
        self.token = self.module.versioned_asset_release_token(self.assets)
        self.responses = {}
        for route, names in self.module.RELEASE_ENTRY_ASSETS.items():
            map_marker = route == "/" or route.endswith("embed=1")
            if route == "/":
                names = names | {"map.js"}
            markup = '<div id="lead-map"></div>' if map_marker else ""
            for name in names:
                url = f"/{name}?v={self.token}"
                markup += f'<link rel="stylesheet" href="{url}">' if name.endswith(".css") else f'<script src="{url}"></script>'
            self.responses[route] = self.response(markup.encode(), "text/html; charset=utf-8")
        for name, asset in self.assets.items():
            mime = "text/css" if name.endswith(".css") else "application/javascript"
            self.responses[f"/{name}?v={self.token}"] = self.response(asset, mime)

    def response(self, content, mime, status=200):
        return self.module.FetchResult(status == 200, status, {"Content-Type": mime}, body_bytes=content)

    def parity(self):
        def fetch(url, **kwargs):
            self.assertFalse(kwargs["follow_redirects"])
            self.assertTrue(kwargs["binary"])
            self.assertEqual(kwargs.get("method", "GET"), "GET")
            self.assertTrue(url.startswith(ORIGIN + "/"))
            return self.responses[url.removeprefix(ORIGIN)]

        with (
            patch.object(self.module, "read_committed_assets", return_value=self.assets) as read,
            patch.object(self.module, "fetch_url", side_effect=fetch) as requests,
        ):
            result = self.module.checkout_asset_parity_check(
                ORIGIN, 2.0, self.module.SCRIPT_DIR.parent, asset_commit=COMMIT,
            )
            read.assert_called_once_with(self.module.SCRIPT_DIR.parent, COMMIT)
        return result, requests.call_count

    def test_matches_every_entry_and_versioned_asset_byte(self):
        result, requests = self.parity()
        self.assertEqual(result.status, "ready")
        self.assertEqual(requests, len(self.module.RELEASE_ENTRY_ASSETS) + len(self.assets))

    def test_rejects_mixed_embed_reference_before_fetching_asset_bytes(self):
        route = "/login?embed=1"
        current = self.responses[route].body_bytes
        self.responses[route] = self.response(current + b'<script src="/clerk-entry.js?v=old"></script>', "text/html")
        result, requests = self.parity()
        self.assertEqual(result.status, "failed")
        self.assertIn(route, result.summary)
        self.assertEqual(requests, len(self.module.RELEASE_ENTRY_ASSETS))

    def test_rejects_wrong_bytes_mime_or_redirect_at_correct_url(self):
        name = "map.js"
        for content, mime, status in (
            (b"wrong", "application/javascript", 200),
            (self.assets[name], "text/html", 200),
            (self.assets[name], "application/javascript", 302),
        ):
            with self.subTest(mime=mime, status=status):
                self.responses[f"/{name}?v={self.token}"] = self.response(content, mime, status)
                result, _requests = self.parity()
                self.assertEqual(result.status, "failed")
                self.assertIn(name, result.summary)

    def test_unreviewed_commit_stops_before_any_network_request(self):
        with (
            patch.object(self.module, "committed_release_reader", side_effect=ValueError),
            patch.object(self.module, "fetch_url") as fetch,
            patch.object(self.module, "dns_lookup") as dns,
        ):
            result = self.module.build_smoke_payload(asset_commit=COMMIT)
        fetch.assert_not_called()
        dns.assert_not_called()
        self.assertFalse(result["ready"])
        self.assertEqual(result["asset_commit"], COMMIT)
        self.assertEqual(result["readiness_scope"], "reviewed_release_inputs")
        self.assertEqual(result["public_launch_approval"], "not_evaluated")

    def committed_notice_fixture(self):
        ledger = json.loads(self.module.DEPENDENCY_LEDGER.read_text(encoding="utf-8"))
        static = self.module.SCRIPT_DIR.parent / "workdoe" / "static"
        blobs = {f"workdoe/static/{name}": asset for name, asset in self.assets.items()}
        for path in self.module.VENDOR_LICENSE_PATHS:
            blobs["workdoe/static" + path] = (static / path[1:]).read_bytes().replace(b"\r\n", b"\n")
        for path in (static / "vendor" / self.module.CLERK_NOTICE_DIRECTORY).iterdir():
            blobs["workdoe/static" + self.module.BUILD_NOTICE_PREFIX + path.name] = path.read_bytes()
        index = "workdoe/static" + self.module.BUILD_NOTICE_PREFIX + self.module.CLERK_NOTICE_INDEX
        blobs[index] += b"\n<!-- Different, committed fixture index. -->\n"
        ledger["clerk_build_notices"]["index_sha256"] = hashlib.sha256(blobs[index]).hexdigest()
        blobs["DEPENDENCY_PROVENANCE.json"] = json.dumps(ledger).encode()
        return blobs, ledger, index

    def test_asset_commit_uses_one_ledger_for_both_notice_checks(self):
        module = self.module
        blobs, ledger, index = self.committed_notice_fixture()

        def read_blob(path, limit):
            body = blobs[path]
            self.assertLessEqual(len(body), limit)
            return body

        ready = module.SmokeCheck("fixture", "ready", "Fixture passed.")
        for include_build in (False, True):
            with (
                self.subTest(include_build=include_build),
                patch.object(module, "committed_release_reader", return_value=Mock(side_effect=read_blob)) as read,
                patch.object(module, "DEPENDENCY_LEDGER", Mock(read_text=Mock(side_effect=AssertionError))),
                patch.object(module, "dns_lookup", return_value=(True, ["192.0.2.1"], "")),
                patch.object(module, "fetch_url", return_value=module.FetchResult(ok=False, status_code=404)),
                patch.object(module, "browser_license_notices_check", return_value=ready) as vendor,
                patch.object(module, "clerk_build_notices_check", return_value=ready) as build,
                patch.object(module, "checkout_asset_parity_check", return_value=ready) as assets,
            ):
                result = module.build_smoke_payload(asset_commit=COMMIT, timeout=1, verify_clerk_build_notices=include_build)
                read.assert_called_once_with(module.SCRIPT_DIR.parent, COMMIT)
                vendor.assert_called_once_with(ORIGIN, 1, reviewed_ledger=ledger)
                if include_build:
                    build.assert_called_once_with(ORIGIN, 1, reviewed_ledger=ledger)
                else:
                    build.assert_not_called()
                paths_read = {call.args[0] for call in read.return_value.call_args_list}
                self.assertEqual(index in paths_read, include_build)
                self.assertTrue(paths_read.isdisjoint(
                    component["retained_license"] for component in module.PINNED_CLERK_BROWSER_COMPONENTS.values()
                ))
                assets.assert_called_once_with(
                    ORIGIN, 1, module.SCRIPT_DIR.parent, asset_commit=COMMIT, reviewed_assets=self.assets,
                )
                self.assertTrue(result["readiness_scope"].endswith("_and_commit_bound_notices"))
                self.assertEqual(result["public_launch_approval"], "not_evaluated")

    def test_mismatched_commit_notice_inputs_stop_before_dns_or_retry(self):
        module = self.module
        blobs, ledger, index = self.committed_notice_fixture()
        ledger["hosted_browser_components"][0]["version"] = "0.0.0"
        vendor = "workdoe/static" + module.VENDOR_LICENSE_PATHS[0]
        cases = (
            {"DEPENDENCY_PROVENANCE.json": b"[]"},
            {"DEPENDENCY_PROVENANCE.json": json.dumps(ledger).encode()},
            {vendor: b"changed vendor notice"},
            {vendor: None},
            {index: b"changed build notice index"},
        )
        for changes in cases:
            fixture = blobs | changes

            def read_blob(path, _limit, fixture=fixture):
                body = fixture.get(path)
                if body is None:
                    raise FileNotFoundError(path)
                return body

            with (
                self.subTest(paths=changes.keys()),
                patch.object(module, "committed_release_reader", return_value=read_blob),
                patch.object(module, "dns_lookup") as dns,
                patch.object(module, "fetch_url") as fetch,
                patch.object(module.time, "sleep") as sleep,
            ):
                result = module.build_smoke_payload_with_retries(
                    asset_commit=COMMIT, attempts=3, retry_delay=1, verify_clerk_build_notices=True,
                )
                self.assertFalse(result["ready"])
                self.assertEqual(result["attempt"], 1)
                self.assertEqual(result["readiness_scope"], "reviewed_release_inputs")
                dns.assert_not_called()
                fetch.assert_not_called()
                sleep.assert_not_called()

    def test_passing_http_checks_do_not_imply_launch_approval(self):
        result = {
            "domain": "workdoe.com", "base_url": ORIGIN, "ready": True, "failures": [],
            "checks": [{"name": "example", "status": "ready", "summary": "HTTP passed"}],
        }
        self.assertIn("Public launch approval: not evaluated", self.module.render_text(result))
