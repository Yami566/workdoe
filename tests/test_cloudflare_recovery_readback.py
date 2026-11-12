from __future__ import annotations

import io
import json
import sys
import unittest
from unittest import mock

from scripts import cloudflare_recovery_readback as readback

VERSION = "11111111-1111-4111-8111-111111111111"
DEPLOYMENT = "22222222-2222-4222-8222-222222222222"
OTHER = "33333333-3333-4333-8333-333333333333"
ENV = {"CLOUDFLARE_ACCOUNT_ID": "a" * 32, "CLOUDFLARE_API_TOKEN": "fixture-only"}
REVIEWED = {"version": VERSION, "deployment": DEPLOYMENT, "allow_wrangler_oauth": False}


def worker_metadata(*, mode="sealed", environment="production", extra=()):
    database_id = readback.reviewed_d1_database_id(readback.REPO_ROOT / "cloudflare")
    return json.dumps({"id": VERSION, "resources": {"bindings": [
        {"name": "WORKDOE_WRITE_MODE", "type": "plain_text", "text": mode},
        {"name": "WORKDOE_ENV", "type": "plain_text", "text": environment},
        {"name": "DB", "type": "d1", "database_id": database_id},
        {"name": "MEDIA", "type": "r2_bucket", "bucket_name": "workdoe-media"},
        *extra,
    ]}})


class RecoveryReadbackTests(unittest.TestCase):
    def test_cli_defaults_to_no_network_and_never_authorizes_restore(self):
        with (
            mock.patch.object(sys, "argv", ["readback"]),
            mock.patch.object(readback, "recovery_readback") as check,
            mock.patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(readback.main(), 0)
        check.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {
            "dry_run": True, "requests_sent": False, "restore_authorized": False,
        })

    def test_invalid_or_unapproved_transport_stops_before_any_read(self):
        with mock.patch.object(readback, "active_worker_deployment") as active:
            for env, identity, error in (
                (ENV, REVIEWED | {"version": ""}, "reviewed serving"),
                (ENV, REVIEWED | {"deployment": readback.ZERO_UUID}, "reviewed serving"),
                (ENV | {"WORKDOE_WRANGLER_BIN": "override"}, REVIEWED, "pinned Wrangler"),
                ({"CLOUDFLARE_ACCOUNT_ID": "a" * 32}, REVIEWED, "existing Wrangler OAuth"),
            ):
                with (
                    self.subTest(error=error),
                    mock.patch.object(readback, "local_wrangler_candidates", return_value=[mock.Mock()]),
                    self.assertRaisesRegex(ValueError, error),
                ):
                    readback.recovery_readback(readback.REPO_ROOT, env, **identity)
        active.assert_not_called()

    def test_readback_requires_explicit_seal_before_hosted_checks(self):
        for payload in (
            worker_metadata(mode="normal"), worker_metadata(mode="paused"),
            worker_metadata(mode="seald"), worker_metadata(environment="staging"),
            worker_metadata(extra=({"name": "WORKDOE_WRITE_MODE", "type": "plain_text", "text": "sealed"},)),
            '{"id":"11111111-1111-4111-8111-111111111111","resources":{"bindings":[{}]}}',
        ):
            with (
                self.subTest(payload=payload),
                mock.patch.object(readback, "local_wrangler_candidates", return_value=[mock.Mock()]),
                mock.patch.object(readback, "active_worker_deployment", return_value=(VERSION, DEPLOYMENT)),
                mock.patch.object(readback, "read_worker_version_metadata", return_value=payload),
                mock.patch.object(readback, "verify_hosted_worker_ingress") as hosted,
                mock.patch.object(readback, "verify_sealed_public_responses") as edge,
                self.assertRaisesRegex(ValueError, "not explicitly sealed"),
            ):
                readback.recovery_readback(readback.REPO_ROOT, ENV, **REVIEWED)
            hosted.assert_not_called()
            edge.assert_not_called()

    def test_readback_requires_same_traffic_and_paused_queues_and_projects_only_scope(self):
        env = ENV | {"WRANGLER_OUTPUT_FILE_PATH": "unreviewed", "WRANGLER_OUTPUT_FILE_DIRECTORY": "unreviewed"}
        for final, error in (((VERSION, DEPLOYMENT), None), ((VERSION, OTHER), "changed during")):
            with (
                self.subTest(final=final),
                mock.patch.object(readback, "local_wrangler_candidates", return_value=[mock.Mock()]),
                mock.patch.object(readback, "active_worker_deployment", side_effect=[(VERSION, DEPLOYMENT), final]) as active,
                mock.patch.object(readback, "read_worker_version_metadata", return_value=worker_metadata()),
                mock.patch.object(readback, "verify_hosted_worker_ingress") as hosted,
                mock.patch.object(readback, "verify_sealed_public_responses") as edge,
            ):
                if error:
                    with self.assertRaisesRegex(ValueError, error):
                        readback.recovery_readback(readback.REPO_ROOT, env, **REVIEWED)
                else:
                    report = readback.recovery_readback(readback.REPO_ROOT, env, **REVIEWED)
                    self.assertTrue(report["containment_observed"])
                    self.assertFalse(report["restore_authorized"])
                    self.assertEqual(report["in_flight_work_and_other_writers"], "not_verified")
                    self.assertNotIn("fixture-only", json.dumps(report))
                child_env = active.call_args.args[1]
                self.assertFalse(any(key.startswith("WRANGLER_OUTPUT_FILE_") for key in child_env))
                self.assertEqual(child_env["CI"], "true")
                hosted.assert_called_once_with(ENV["CLOUDFLARE_ACCOUNT_ID"], child_env,
                                               oauth_token=None, require_paused_queues=True)
                edge.assert_called_once_with()
                self.assertEqual(active.call_count, 2)

    def test_public_probes_are_anonymous_head_and_reject_unsealed_or_cached_responses(self):
        sealed = {"X-Workdoe-Mode": "sealed", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}

        def respond(url, **options):
            self.assertEqual(options, {"method": "HEAD", "timeout": 8, "body_limit": 0, "follow_redirects": False})
            return mock.Mock(status_code=200 if url.endswith("/health") else 503, headers=sealed)

        with mock.patch.object(readback, "fetch_url", side_effect=respond) as fetch:
            readback.verify_sealed_public_responses()
        self.assertEqual({call.args[0] for call in fetch.call_args_list}, {
            f"https://{host}{path}" for host in ("workdoe.com", "www.workdoe.com")
            for path in ("/health", "/api/jobs/open", "/dashboard", "/media/jobs/0", "/__clerk/v1/environment")
        })
        for headers in (
            sealed | {"X-Workdoe-Mode": "read-only"}, sealed | {"Cache-Control": "no-store, public"},
            sealed | {"CF-Cache-Status": "HIT"}, sealed | {"Age": "0"},
            sealed | {"Set-Cookie": "fixture-only"}, sealed | {"Location": "https://unexpected.invalid/"},
        ):
            with (
                self.subTest(headers=headers),
                mock.patch.object(readback, "fetch_url", return_value=mock.Mock(status_code=200, headers=headers)),
                self.assertRaisesRegex(ValueError, "fresh sealed response") as caught,
            ):
                readback.verify_sealed_public_responses()
            self.assertNotIn("fixture-only", str(caught.exception))
            self.assertNotIn("unexpected.invalid", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
