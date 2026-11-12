import contextlib
import importlib
import io
import json
from unittest import TestCase
from unittest.mock import patch

from test_cloudflare_release import load_workdoe_production_smoke_script


class ClerkSelfDeleteCheckTests(TestCase):
    def setUp(self):
        self.smoke = load_workdoe_production_smoke_script()
        self.module = importlib.import_module("workdoe_clerk_self_delete")

    def response(self, body, status=200, mime="application/json; charset=utf-8", *, headers=None):
        return self.smoke.FetchResult(status == 200, status, {
            "content-type": mime, "cache-control": "no-store", **(headers or {}),
        }, body_bytes=body)

    def test_only_explicit_boolean_instance_setting_is_accepted(self):
        for value, expected in ((True, "enabled"), (False, "disabled"), ("false", "unverified"),
                                (0, "unverified"), (None, "unverified")):
            with self.subTest(value=value):
                body = json.dumps({
                    "user_settings": {"actions": {"delete_self": value}},
                    "organization_settings": {"actions": {"admin_delete": not value}},
                }).encode()
                self.assertEqual(self.module.self_delete_state(self.response(body)), expected)

    def test_incomplete_ambiguous_or_untrusted_responses_do_not_pass(self):
        for response in (
            self.response(b"{}"),
            self.response(b"{"),
            self.response(b"\xff"),
            self.response(b'{"user_settings":{"actions":{"delete_self":true,"delete_self":false}}}'),
            self.response(b'{"user_settings":{"actions":{"delete_self":false}}}', 302),
            self.response(b'{"user_settings":{"actions":{"delete_self":false}}}', mime="text/html"),
            self.response(b'{"user_settings":{"actions":{"delete_self":false}}}' +
                          b" " * self.module.CLERK_ENVIRONMENT_MAX_BYTES),
            self.smoke.FetchResult(False, error="fixture-private-transport-detail"),
        ):
            with self.subTest(status=response.status_code, size=len(response.body_bytes)):
                self.assertEqual(self.module.self_delete_state(response), "unverified")

    def test_cli_reads_one_public_response_and_projects_only_the_flag(self):
        for body, exit_code in (
            (b'{"user_settings":{"actions":{"delete_self":false}},"private":"fixture-marker"}', 0),
            (b'{"user_settings":{"actions":{"delete_self":true}},"private":"fixture-marker"}', 1),
            (b'{"private":"fixture-marker"}', 2),
        ):
            with (
                self.subTest(exit_code=exit_code),
                patch.object(self.module, "fetch_url", return_value=self.response(body)) as fetch,
                contextlib.redirect_stdout(io.StringIO()) as stdout,
            ):
                self.assertEqual(self.module.main(["--live"]), exit_code)
                self.assertEqual(
                    set(json.loads(stdout.getvalue())), {"http_status", "instance_self_delete", "scope"},
                )
                self.assertNotIn("fixture-marker", stdout.getvalue())
                fetch.assert_called_once_with(
                    "https://workdoe.com/__clerk/v1/environment", method="GET", timeout=10,
                    body_limit=self.module.CLERK_ENVIRONMENT_MAX_BYTES + 1, follow_redirects=False, binary=True,
                )

    def test_stale_or_cacheable_disabled_evidence_cannot_pass(self):
        body = b'{"user_settings":{"actions":{"delete_self":false}}}'
        for headers in (
            {"cache-control": ""}, {"cache-control": "public, max-age=300"}, {"age": "0"},
            {"cf-cache-status": "HIT"}, {"cf-cache-status": "STALE"}, {"cf-cache-status": "REVALIDATED"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.module.self_delete_state(self.response(body, headers=headers)), "unverified")

    def test_live_flag_is_required(self):
        with (
            patch.object(self.module, "fetch_url") as fetch,
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            self.module.main([])
        fetch.assert_not_called()
