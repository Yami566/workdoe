import importlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

from scripts import cloudflare_production_deploy as deploy

ingress = sys.modules[deploy.verify_hosted_worker_ingress.__module__]
legacy = importlib.import_module("cloudflare_legacy_ingress")
staging = importlib.import_module("cloudflare_staging_readback")
ACCOUNT = "a" * 32
ZONE = "c" * 32
TOKEN = "fixture-credential-not-for-output"
ENV = {"CLOUDFLARE_ACCOUNT_ID": ACCOUNT, "CLOUDFLARE_API_TOKEN": TOKEN}
DISABLED = {"enabled": False, "previews_enabled": False}
REDACTED = {"observability": {"enabled": True, "redact_query_string": True}, "logpush": False}
LEGACY_ROUTE = {"pattern": "api.workdoe.com/*", "script": "workdoe-api"}
EMAIL_QUEUE_ID = "d" * 32
MEDIA_QUEUE_ID = "e" * 32


def domain(host):
    return {"hostname": host, "service": "workdoe", "zone_name": "workdoe.com", "zone_id": ZONE,
            "enabled": True, "previews_enabled": False}


def response(result=None, *, body=None, **metadata):
    if body is None:
        body = json.dumps({"success": True, "result": result, **metadata}).encode()
    reply = io.BytesIO(body)
    reply.status = 200
    return reply


def queue_fixture(name, queue_id):
    consumer = {
        "type": "worker", "script": "workdoe", "queue_name": name, "queue_id": queue_id,
        "consumer_id": "f" * 32, "settings": {"batch_size": 10, "max_wait_time_ms": 30000, "max_retries": 5},
    }
    embedded = {key: value for key, value in consumer.items() if key not in {"queue_name", "queue_id"}}
    queue = {
        "queue_name": name, "queue_id": queue_id,
        "consumers_total_count": 1, "consumers": [embedded],
        "producers_total_count": 1, "producers": [{"type": "worker", "script": "workdoe"}],
        "settings": {},
    }
    return queue, consumer


def queue_responses(name, queue_id, *, documented=False, paused=None):
    queue, consumer = queue_fixture(name, queue_id)
    if paused is not None:
        queue["settings"]["delivery_paused"] = paused
    if documented:
        # The list can use the live shape while the direct API uses the documented spelling.
        consumer = {key: value for key, value in consumer.items() if key != "script"} | {"script_name": "workdoe"}
    page = {"page": 1, "count": 1, "total_count": 1, "total_pages": 1}
    return [response([queue], result_info=page | {"total_count": 10}), response([consumer], result_info=page)]


PAGES_PROJECT = {
    "name": "workdoe", "subdomain": "workdoe.pages.dev", "domains": ["workdoe.pages.dev"],
    "canonical_deployment": {"id": "production"}, "latest_deployment": {"id": "preview"},
}
PAGES_DEPLOYMENTS = [
    {"id": "production", "url": "https://old.workdoe.pages.dev", "aliases": None},
    {"id": "preview", "url": "https://hash.workdoe.pages.dev", "aliases": ["https://branch.workdoe.pages.dev/"]},
]
PAGES_RESULT_INFO = {"page": 1, "count": 2, "total_count": 2, "total_pages": 1}


class StagingReadbackTests(unittest.TestCase):
    production_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    preview_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    stage_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    version_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    deployment_id = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"

    def setUp(self):
        self.config = {"name": "workdoe", "compatibility_date": "2026-08-23", "compatibility_flags": ["python_workers"],
                       "d1_databases": [{
            "binding": "DB", "database_name": "workdoe", "database_id": self.production_id,
            "preview_database_id": self.preview_id,
        }]}
        self.rows = [{"name": "workdoe", "uuid": self.production_id},
                     {"name": "workdoe-preview", "uuid": self.preview_id}]

    def test_dry_run_never_reads_cloudflare_or_wrangler(self):
        with (
            mock.patch.object(sys, "argv", ["staging"]),
            mock.patch.object(staging, "staging_readback") as readback,
            mock.patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(staging.main(), 0)
        readback.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {"dry_run": True, "requests_sent": False})

        with (
            mock.patch.object(staging, "reviewed_ingress_account", return_value=ACCOUNT),
            mock.patch.object(staging, "wrangler_oauth_access_token") as auth,
            mock.patch.object(staging, "read_d1_inventory") as inventory,
            self.assertRaisesRegex(ValueError, "pinned Wrangler"),
        ):
            staging.staging_readback(Path("."), {"WORKDOE_WRANGLER_BIN": "another-cli"}, allow_wrangler_oauth=True)
        auth.assert_not_called()
        inventory.assert_not_called()

    def test_d1_counts_only_after_proving_reviewed_binding_identities(self):
        self.assertEqual(staging.d1_readback(self.config, self.rows), {
            "account_database_count": 2, "dedicated_database_present": False,
        })
        extra = {"name": "workdoe-staging", "uuid": self.stage_id}
        self.assertEqual(staging.d1_readback(self.config, self.rows + [extra]), {
            "account_database_count": 3, "dedicated_database_present": True,
        })
        for rows in (
            self.rows[:1],
            [self.rows[0], self.rows[1] | {"uuid": self.stage_id}],
            self.rows + [extra | {"uuid": self.preview_id.upper()}],
            self.rows + [extra, extra],
            self.rows + [extra | {"uuid": "invalid"}],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                staging.d1_readback(self.config, rows)

    def test_staging_metadata_reads_only_fixed_gets_and_projects_the_result(self):
        hidden = "unrelated-operator-resource"
        opener = mock.Mock()
        opener.open.side_effect = [
            response([{"queue_name": hidden}, {"queue_name": "workdoe-staging-email"}],
                     result_info=PAGES_RESULT_INFO),
            response([{"id": "workdoe"}, {"id": hidden}]),
            response({"name": "workdoe-staging-media", "storage_class": "Standard", "id": hidden}),
            response({"enabled": False, "domain": hidden}),
            response({"domains": [{"domain": hidden}]}),
        ]
        report = staging.cloudflare_readback(opener, ACCOUNT, TOKEN)
        self.assertEqual(report, {
            "staging_bucket_standard": True,
            "staging_bucket_dev_url_disabled": True,
            "staging_bucket_custom_domain_count": 1,
            "staging_email_queue_present": True,
            "staging_media_queue_present": False,
            "staging_worker_present": False,
        })
        self.assertNotIn(hidden, json.dumps(report))
        root = f"/client/v4/accounts/{ACCOUNT}"
        api_calls = [call.args[0] for call in opener.open.call_args_list]
        self.assertTrue(all(req.get_method() == "GET" and req.host == "api.cloudflare.com" for req in api_calls))
        self.assertEqual([req.selector for req in api_calls], [
            f"{root}/queues", f"{root}/workers/scripts", f"{root}/r2/buckets/workdoe-staging-media",
            f"{root}/r2/buckets/workdoe-staging-media/domains/managed",
            f"{root}/r2/buckets/workdoe-staging-media/domains/custom",
        ])

    def test_queue_absence_requires_complete_unambiguous_inventory(self):
        for partial in (
            {"result": []},
            {"result": [], "result_info": {"page": 1, "total_count": 20, "total_pages": 2}},
            {"result": [{"queue_name": "same"}] * 2, "result_info": PAGES_RESULT_INFO},
            {"result": [{"queue_name": None}], "result_info": {"page": 1, "total_count": 1}},
        ):
            with self.subTest(partial=partial), self.assertRaises(ValueError):
                staging.inventory_names(partial, "queue_name", "queue", paginated=True)

    def test_wrangler_inventory_suppresses_raw_errors_and_uses_fixed_command(self):
        with (
            mock.patch.object(staging, "wrangler_command", return_value=["wrangler", "d1", "list"]) as command,
            mock.patch.object(staging.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, TOKEN, TOKEN)) as run,
            self.assertRaises(ValueError) as caught,
        ):
            staging.read_d1_inventory(Path("."), {**ENV, "WRANGLER_OUTPUT_FILE_PATH": "unexpected"})
        command.assert_called_once_with(["d1", "list", "--json", "--config", "wrangler.jsonc"], Path("."))
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertNotIn("WRANGLER_OUTPUT_FILE_PATH", run.call_args.kwargs["env"])
        self.assertEqual(run.call_args.kwargs["env"]["WRANGLER_WRITE_LOGS"], "false")

    def seal_replies(self):
        config = staging.sealed_staging_config(self.config, self.rows + [{"name": staging.STAGING_NAME, "uuid": self.stage_id}])
        traffic = {"deployments": [{"id": self.deployment_id, "versions": [{"version_id": self.version_id, "percentage": 100}]}]}
        bindings = [
            {"type": "assets", "name": "ASSETS"}, {"type": "d1", "name": "DB", "database_id": self.stage_id},
            {"type": "r2_bucket", "name": "MEDIA", "bucket_name": staging.STAGING_MEDIA_BUCKET},
            {"type": "queue", "name": "EMAIL_QUEUE", "queue_name": staging.STAGING_EMAIL_QUEUE},
            {"type": "queue", "name": "MEDIA_QUEUE", "queue_name": staging.STAGING_MEDIA_QUEUE},
            *({"type": "plain_text", "name": name, "text": value} for name, value in config["vars"].items()),
        ]
        metadata = {"id": self.version_id, "resources": {"bindings": bindings, "script_runtime": {
            "compatibility_date": config["compatibility_date"], "compatibility_flags": config["compatibility_flags"],
            "assets": {"raw_run_worker_first": True, "serve_directly": False},
        }}}
        queues = [{
            "queue_name": name, "queue_id": queue_id, "producers_total_count": 1, "consumers_total_count": 0,
            "producers": [{"type": "worker", "script": staging.STAGING_NAME}], "consumers": [],
        } for name, queue_id in ((staging.STAGING_EMAIL_QUEUE, EMAIL_QUEUE_ID), (staging.STAGING_MEDIA_QUEUE, MEDIA_QUEUE_ID))]
        page = {"page": 1, "count": 1, "total_count": 10, "total_pages": 1}
        return config, traffic, metadata, queues, page

    def check_seal(self, config, replies):
        opener = mock.Mock()
        opener.open.side_effect = replies
        staging.verify_sealed_staging_version(opener, ACCOUNT, TOKEN, version=self.version_id, config=config)
        return [call.args[0] for call in opener.open.call_args_list]

    def test_sealed_version_reads_only_named_metadata_and_rechecks_the_active_deployment(self):
        config, traffic, metadata, queues, page = self.seal_replies()
        calls = self.check_seal(config, [
            response(traffic), response(metadata), response(DISABLED), response([]), response([]),
            response([domain("workdoe.com"), domain("www.workdoe.com")]), response([LEGACY_ROUTE]),
            response({"schedules": []}), response([queues[0]], result_info=page), response([]),
            response([queues[1]], result_info=page), response([]), response(traffic),
        ])
        self.assertTrue(all(req.host == "api.cloudflare.com" and req.get_method() == "GET" for req in calls))
        root = f"/client/v4/accounts/{ACCOUNT}"
        script = f"{root}/workers/scripts/{staging.STAGING_NAME}"
        self.assertEqual([req.selector for req in calls], [
            f"{script}/deployments", f"{script}/versions/{self.version_id}", f"{script}/subdomain",
            f"{root}/workers/domains?service={staging.STAGING_NAME}", f"{root}/workers/domains?hostname={staging.STAGING_HOST}",
            f"{root}/workers/domains?service=workdoe", f"/client/v4/zones/{ZONE}/workers/routes", f"{script}/schedules",
            f"{root}/queues?page=1&name={staging.STAGING_EMAIL_QUEUE}", f"{root}/queues/{EMAIL_QUEUE_ID}/consumers",
            f"{root}/queues?page=1&name={staging.STAGING_MEDIA_QUEUE}", f"{root}/queues/{MEDIA_QUEUE_ID}/consumers",
            f"{script}/deployments",
        ])

    def test_sealed_version_rejects_binding_runtime_and_traffic_drift(self):
        for label, error in (
            ("wrong version", "sole serving"), ("traffic split", "100%"), ("wrong response ID", "identify"),
            ("production D1", "binding DB"), ("preview D1", "binding DB"), ("production queue", "binding EMAIL_QUEUE"),
            ("secret", "unexpected"), ("duplicate", "duplicate"), ("uploads on", "MEDIA_UPLOADS_ENABLED"),
            ("unsealed", "WORKDOE_WRITE_MODE"), ("asset bypass", "asset routing"), ("private R2 elsewhere", "MEDIA binding"),
        ):
            with self.subTest(label=label):
                config, traffic, metadata, _, _ = self.seal_replies()
                active = traffic["deployments"][0]["versions"]
                bindings = metadata["resources"]["bindings"]
                if label == "wrong version":
                    active[0]["version_id"] = self.deployment_id
                elif label == "traffic split":
                    active[0]["percentage"] = 50
                elif label == "wrong response ID":
                    metadata["id"] = self.deployment_id
                elif label in ("production D1", "preview D1"):
                    bindings[1]["database_id"] = self.production_id if label == "production D1" else self.preview_id
                elif label == "production queue":
                    bindings[3]["queue_name"] = "workdoe-email"
                elif label == "secret":
                    bindings.append({"name": "RESEND_API_KEY", "type": "secret_text", "text": TOKEN})
                elif label == "duplicate":
                    bindings.append(bindings[0])
                elif label in ("uploads on", "unsealed"):
                    target = "WORKDOE_MEDIA_UPLOADS_ENABLED" if label == "uploads on" else "WORKDOE_WRITE_MODE"
                    next(binding for binding in bindings if binding["name"] == target)["text"] = "true" if label == "uploads on" else "normal"
                elif label == "asset bypass":
                    metadata["resources"]["script_runtime"]["assets"]["serve_directly"] = True
                else:
                    bindings[2]["jurisdiction"] = "eu"
                with self.assertRaisesRegex(ValueError, error) as caught:
                    self.check_seal(config, [response(traffic), response(metadata)])
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_sealed_version_rejects_ingress_cron_and_consumer_drift(self):
        config, traffic, metadata, queues, page = self.seal_replies()
        for index, result, error in (
            (2, response({"enabled": False}), "alternate|version URLs"),
            (2, response(DISABLED | {"previews_enabled": True}), "version URLs"),
            (3, response([], result_info={"total_pages": 2}), "incomplete"),
            (4, response([{"hostname": staging.STAGING_HOST, "service": TOKEN}]), "custom domains"),
            (6, response([{"pattern": "*.workdoe.com/*", "script": staging.STAGING_NAME}]), "routes"),
            (7, response({"schedules": [{"cron": "0 * * * *"}]}), "cron"),
            (8, response([queues[0] | {"consumers_total_count": 1}], result_info=page), "consumers"),
            (8, response([queues[0] | {"producers": [{"type": "worker", "script": "workdoe"}]}], result_info=page), "producer"),
            (9, response([{"type": "http_pull"}]), "consumers"),
            (9, response([], result_info={"total_count": 1}), "incomplete"),
            (10, response([queues[1] | {"queue_id": EMAIL_QUEUE_ID}], result_info=page), "producer"),
            (12, response({"deployments": [traffic["deployments"][0] | {"id": self.stage_id}]}), "changed"),
        ):
            with self.subTest(index=index, error=error):
                replies = [
                    response(traffic), response(metadata), response(DISABLED), response([]), response([]),
                    response([domain("workdoe.com"), domain("www.workdoe.com")]), response([]),
                    response({"schedules": []}), response([queues[0]], result_info=page), response([]),
                    response([queues[1]], result_info=page), response([]), response(traffic),
                ]
                replies[index] = result
                with self.assertRaisesRegex(ValueError, error) as caught:
                    self.check_seal(config, replies)
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_invalid_sealed_version_stops_before_provider_calls(self):
        with mock.patch.object(staging, "reviewed_ingress_account") as account:
            with self.assertRaisesRegex(ValueError, "version UUID"):
                staging.staging_readback(Path.cwd(), ENV, allow_wrangler_oauth=False, expected_sealed_version=TOKEN)
            account.assert_not_called()

    def test_seal_requires_all_dedicated_resources_and_private_standard_r2(self):
        clean = {
            "staging_bucket_standard": True, "staging_bucket_dev_url_disabled": True,
            "staging_bucket_custom_domain_count": 0, "staging_email_queue_present": True,
            "staging_media_queue_present": True, "staging_worker_present": True,
        }
        stage = {"name": staging.STAGING_NAME, "uuid": self.stage_id}
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(staging, "local_wrangler_candidates", return_value=[Path(__file__)]),
            mock.patch.object(staging, "read_d1_inventory", return_value=self.rows + [stage]) as inventory,
            mock.patch.object(staging, "cloudflare_readback", return_value=clean) as resources,
            mock.patch.object(staging, "verify_sealed_staging_version") as verify,
        ):
            root = Path(directory)
            config_path = root / staging.WRANGLER_RELATIVE_PATH
            config_path.parent.mkdir()
            config_path.write_text(json.dumps(self.config), encoding="utf-8")

            def run():
                return staging.staging_readback(root, ENV, allow_wrangler_oauth=False, expected_sealed_version=self.version_id)

            for field, drift in (
                ("staging_worker_present", False), ("staging_email_queue_present", False),
                ("staging_bucket_standard", False), ("staging_bucket_dev_url_disabled", False),
                ("staging_bucket_custom_domain_count", 1),
            ):
                resources.return_value = clean | {field: drift}
                with self.subTest(field=field), self.assertRaises(ValueError):
                    run()
            resources.return_value = clean
            inventory.return_value = self.rows
            with self.assertRaisesRegex(ValueError, "dedicated staging database"):
                run()
            verify.assert_not_called()

            inventory.return_value = self.rows + [stage]
            report = run()
            self.assertEqual(report["staging_seal_metadata"], "verified")
            self.assertEqual(report["hosted_acceptance"], "not_checked")
            self.assertEqual(verify.call_args.kwargs["config"]["d1_databases"][0]["database_id"], self.stage_id)
            self.assertNotIn(self.stage_id, json.dumps(report))
            self.assertNotIn(TOKEN, json.dumps(report))


class LegacyIngressTests(unittest.TestCase):
    def test_dry_run_never_reads_cloudflare_or_pages(self):
        with (
            mock.patch.object(sys, "argv", ["legacy"]),
            mock.patch.object(legacy, "legacy_ingress_readback") as readback,
            mock.patch("sys.stdout", new_callable=io.StringIO) as output,
        ):
            self.assertEqual(legacy.main(), 0)
        readback.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {"dry_run": True, "requests_sent": False})

    def test_readback_checks_default_workers_and_pages_roots_and_assets(self):
        visible = legacy.FetchResult(True, status_code=200)
        disabled = legacy.FetchResult(False, status_code=404, headers={
            "Server": "cloudflare", "CF-Ray": "fixture-ray", "Content-Type": "text/plain; charset=UTF-8",
        })
        worker_json = legacy.FetchResult(False, status_code=404, headers={"Content-Type": "application/json"})
        for mode, worker_flags, routes in (
            ("public", {**DISABLED, "previews_enabled": True}, [LEGACY_ROUTE]),
            ("protected", DISABLED, []), ("asset-leak", DISABLED, []), ("ambiguous-block", DISABLED, []),
        ):
            def edge(url, *, method, follow_redirects, body_limit, mode=mode):
                self.assertFalse(follow_redirects)
                self.assertEqual(body_limit, 0)
                target = urlsplit(url)
                if target.netloc.endswith(".workers.dev"):
                    return worker_json if mode == "public" and target.netloc.startswith("workdoe-api.") else disabled
                if mode == "public" or (mode == "asset-leak" and target.path.endswith(".js") and method == "GET"):
                    return visible
                if mode == "ambiguous-block":
                    return legacy.FetchResult(False, status_code=403)
                return legacy.FetchResult(False, status_code=302, headers={
                    "Location": f"https://team.cloudflareaccess.com/cdn-cgi/access/login/{target.netloc}?{TOKEN}",
                })

            with (
                self.subTest(mode=mode),
                mock.patch.object(legacy.urllib.request, "build_opener") as build,
                mock.patch.object(legacy, "fetch_url", side_effect=edge) as fetch,
            ):
                opener = build.return_value.open
                opener.side_effect = [
                    response([domain("workdoe.com"), domain("www.workdoe.com")]), response(routes),
                    response(worker_flags), response([]), response(DISABLED), response({"subdomain": "fixture"}),
                    response(PAGES_PROJECT),
                    response(PAGES_DEPLOYMENTS, result_info=PAGES_RESULT_INFO),
                ]
                report = legacy.legacy_ingress_readback(ACCOUNT, ENV)
            self.assertEqual(report["readback_passed"], mode == "protected")
            self.assertEqual(report["pages_samples_contained"], mode == "protected")
            self.assertEqual(report["legacy_worker_default_matches_disabled"], mode != "public")
            self.assertEqual(report["authorized_access"], "not_evaluated")
            self.assertEqual(report["public_launch_approval"], "not_evaluated")
            self.assertEqual(report["legacy_worker_previews_enabled"], mode == "public")
            self.assertEqual(report["legacy_zone_route_present"], mode == "public")
            self.assertEqual(report["worker_default_edge_outcomes"]["workdoe-api"]["GET"], (
                "application_response" if mode == "public" else "disabled_edge_shape"
            ))
            self.assertEqual(report["worker_version_edges"], "not_probed")
            self.assertEqual(report["pages_origin_count"], 4)
            self.assertEqual(report["pages_root_probe_count"], 8)
            self.assertEqual(report["pages_asset_probe_count"], 16)
            self.assertEqual(report["pages_root_outcomes"], {
                "public": {"public_response": 8}, "ambiguous-block": {"blocked_unverified": 8},
            }.get(mode, {"access_challenge": 8}))
            if mode == "asset-leak":
                self.assertEqual(report["pages_asset_outcomes"], {"public_response": 4, "access_challenge": 12})
            self.assertNotIn(TOKEN, json.dumps(report))
            root = f"/client/v4/accounts/{ACCOUNT}"
            api_calls = [call.args[0] for call in opener.call_args_list]
            self.assertTrue(all(req.get_method() == "GET" and req.host == "api.cloudflare.com" for req in api_calls))
            self.assertEqual([req.selector for req in api_calls], [
                f"{root}/workers/domains?service=workdoe",
                f"/client/v4/zones/{ZONE}/workers/routes",
                f"{root}/workers/scripts/workdoe-api/subdomain",
                f"{root}/workers/domains?service=workdoe-api",
                f"{root}/workers/scripts/workdoe/subdomain",
                f"{root}/workers/subdomain",
                f"{root}/pages/projects/workdoe",
                f"{root}/pages/projects/workdoe/deployments?page=1&per_page=25",
            ])
            self.assertEqual(fetch.call_args_list, [
                mock.call(f"https://{worker}.fixture.workers.dev/", method=method, follow_redirects=False, body_limit=0)
                for worker in ("workdoe", "workdoe-api") for method in ("HEAD", "GET")
            ] + [
                mock.call(f"https://{host}{path}", method=method, follow_redirects=False, body_limit=0)
                for host in ("workdoe.pages.dev", "branch.workdoe.pages.dev", "hash.workdoe.pages.dev", "old.workdoe.pages.dev")
                for path in legacy.REVIEWED_PAGES_PATHS for method in ("HEAD", "GET")
            ])

    def test_malformed_or_incomplete_pages_inventory_does_not_authorize_probes(self):
        for deployment in (
            {"url": "http://hash.workdoe.pages.dev"},
            {"url": f"https://{TOKEN}.invalid"},
            {"url": "https://hash.workdoe.pages.dev:443"},
            {"url": "https://hash.workdoe.pages.dev/?query=hidden"},
            {"aliases": ["https://elsewhere.invalid"]},
            {"aliases": "https://branch.workdoe.pages.dev"},
            {"id": "production"},
        ):
            with self.subTest(deployment=deployment), self.assertRaises(ValueError) as caught:
                legacy.reviewed_pages_origins(PAGES_PROJECT, {
                    "result": [PAGES_DEPLOYMENTS[0], PAGES_DEPLOYMENTS[1] | deployment],
                    "result_info": PAGES_RESULT_INFO,
                })
            self.assertNotIn(TOKEN, str(caught.exception))
        with self.assertRaises(ValueError):
            legacy.reviewed_pages_origins(PAGES_PROJECT, {
                "result": PAGES_DEPLOYMENTS,
                "result_info": PAGES_RESULT_INFO | {"total_pages": 2},
            })
        with self.assertRaises(ValueError):
            legacy.reviewed_pages_origins(PAGES_PROJECT | {"latest_deployment": {"id": "missing"}}, {
                "result": PAGES_DEPLOYMENTS,
                "result_info": PAGES_RESULT_INFO,
            })

    def test_pages_probe_never_treats_an_unexpected_redirect_or_404_as_contained(self):
        for status, location, expected in (
            (404, "", "unverified"), (0, "", "unverified"), (503, "", "unverified"),
            (308, "https://workdoe.com/", "canonical_root_redirect"),
            (308, "https://workdoe.com/?old_query=retained", "unverified"),
            (302, "https://team.cloudflareaccess.com.invalid/cdn-cgi/access/login/", "unverified"),
            (302, "https://team.cloudflareaccess.com/dashboard", "unverified"),
            (302, "https://team.cloudflareaccess.com/cdn-cgi/access/login/other.pages.dev", "unverified"),
            (403, "https://workdoe.com/", "blocked_unverified"),
        ):
            with self.subTest(status=status, location=location):
                response = legacy.FetchResult(
                    False, status_code=status, headers={"Location": location},
                )
                self.assertEqual(legacy.pages_outcome(response, legacy.PAGES_ORIGIN), expected)

    def test_unreviewed_workers_subdomain_never_authorizes_an_edge_request(self):
        with (
            mock.patch.object(legacy, "read_cloudflare_api", return_value={"result": {"subdomain": "bad@elsewhere.invalid"}}),
            mock.patch.object(legacy, "fetch_url") as fetch,
            self.assertRaisesRegex(ValueError, "valid Workers subdomain"),
        ):
            legacy.probe_worker_defaults(object(), f"{legacy.API_ORIGIN}/accounts/{ACCOUNT}", TOKEN)
        fetch.assert_not_called()

    def test_worker_edge_response_shape_does_not_accept_generic_or_cached_404s(self):
        control = {"Content-Type": "text/plain", "Server": "cloudflare", "CF-Ray": "fixture-ray"}
        for headers, expected in (
            (control, "disabled_edge_shape"),
            (control | {"Content-Type": "application/json"}, "application_response"),
            ({"Content-Type": "text/plain"}, "unverified"),
            (control | {"Age": "5"}, "unverified"),
            (control | {"CF-Cache-Status": "HIT"}, "unverified"),
            (control | {"CF-Mitigated": "challenge"}, "unverified"),
        ):
            with self.subTest(headers=headers):
                self.assertEqual(legacy.worker_edge_outcome(legacy.FetchResult(False, 404, headers)), expected)


class HostedIngressTests(unittest.TestCase):
    def test_confirms_only_reviewed_domains_through_fixed_read_only_api(self):
        replies = [
            response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
            response([LEGACY_ROUTE]), response({**REDACTED, "tail_consumers": None}),
            response({**REDACTED, "tail_consumers": []}),
            response({"enabled": False, "domain": "bucket-fixture.r2.dev"}), response({"domains": []}),
            *queue_responses("workdoe-email", EMAIL_QUEUE_ID),
            *queue_responses("workdoe-media-review", MEDIA_QUEUE_ID, documented=True),
        ]
        with mock.patch.object(ingress.urllib.request, "build_opener") as build:
            open_response = build.return_value.open
            open_response.side_effect = replies
            ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
        proxy, redirects = build.call_args.args
        self.assertEqual(proxy.proxies, {})
        self.assertIsNone(redirects.redirect_request())
        paths = []
        for call in open_response.call_args_list:
            request = call.args[0]
            url = urlsplit(request.full_url)
            self.assertEqual((url.scheme, url.netloc, request.get_method()), ("https", "api.cloudflare.com", "GET"))
            self.assertEqual(request.get_header("Authorization"), f"Bearer {TOKEN}")
            self.assertEqual(call.kwargs, {"timeout": ingress.READ_TIMEOUT})
            paths.append((url.path, url.query))
        root = f"/client/v4/accounts/{ACCOUNT}/workers"
        bucket = f"/client/v4/accounts/{ACCOUNT}/r2/buckets/workdoe-media/domains"
        queues = f"/client/v4/accounts/{ACCOUNT}/queues"
        self.assertEqual(paths, [
            (f"{root}/scripts/workdoe/subdomain", ""), (f"{root}/domains", "service=workdoe"),
            (f"/client/v4/zones/{ZONE}/workers/routes", ""),
            (f"{root}/scripts/workdoe/script-settings", ""), (f"{root}/scripts/workdoe/settings", ""),
            (f"{bucket}/managed", ""), (f"{bucket}/custom", ""),
            (queues, "page=1&name=workdoe-email"), (f"{queues}/{EMAIL_QUEUE_ID}/consumers", ""),
            (queues, "page=1&name=workdoe-media-review"), (f"{queues}/{MEDIA_QUEUE_ID}/consumers", ""),
        ])

    def test_rejects_disabled_missing_or_unconfirmed_query_redaction(self):
        cases = (None, {}, {"enabled": True}, {"enabled": True, "redact_query_string": False},
                 {"enabled": True, "redact_query_string": "true"}, {"enabled": False, "redact_query_string": True})
        for observability in cases:
            with self.subTest(observability=observability), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = [
                    response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
                    response([]), response({"observability": observability}),
                ]
                with self.assertRaisesRegex(ValueError, "observability and request query-string redaction"):
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)

    def test_rejects_enabled_or_unconfirmed_script_previews(self):
        for settings in ({"enabled": False}, {**DISABLED, "enabled": True},
                         {**DISABLED, "previews_enabled": True}, {**DISABLED, "previews_enabled": "false"}):
            with self.subTest(settings=settings), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.return_value = response(settings)
                with self.assertRaisesRegex(ValueError, "workers.dev and version previews"):
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                build.return_value.open.assert_called_once()

    def test_rejects_custom_domain_drift_and_partial_results(self):
        apex = domain("workdoe.com")
        www = domain("www.workdoe.com")
        cases = {
            "extra": ([apex, www, domain("old.workdoe.com")], {}),
            "unexpected": ([apex, domain("old.workdoe.com")], {}),
            "duplicate": ([apex, apex], {}),
            "wrong environment": ([apex, {**www, "environment": "staging"}], {}),
            "enabled preview": ([apex, {**www, "previews_enabled": True}], {}),
            "unknown preview": ([apex, {key: value for key, value in www.items() if key != "previews_enabled"}], {}),
            "disabled custom domain": ([apex, {**www, "enabled": False}], {}),
            "more pages": ([apex, www], {"result_info": {"total_pages": 2}}),
            "unknown zone": ([apex, {**www, "zone_id": ""}], {}),
            "different zone": ([apex, {**www, "zone_id": "d" * 32}], {}),
            "zone path injection": ([apex, {**www, "zone_id": ZONE + "/elsewhere"}], {}),
        }
        for label, (domains, metadata) in cases.items():
            with self.subTest(label=label), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = [response(DISABLED), response(domains, **metadata)]
                with self.assertRaises(ValueError):
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                self.assertEqual(build.return_value.open.call_count, 2)

    def test_rejects_unreviewed_zone_routes_before_reading_telemetry(self):
        cases = (
            (None, {}),
            ([{"pattern": "preview.workdoe.com/*", "script": "workdoe"}], {}),
            ([LEGACY_ROUTE, {"pattern": "*.workdoe.com/*", "script": "workdoe"}], {}),
            ([{"pattern": "workdoe.com/login*"}], {}),
            ([{**LEGACY_ROUTE, "script": "another-worker"}], {}),
            ([LEGACY_ROUTE, LEGACY_ROUTE], {}),
            ([LEGACY_ROUTE], {"result_info": {"total_count": 2}}),
        )
        for routes, meta in cases:
            with self.subTest(routes=routes, meta=meta), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = [
                    response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
                    response(routes, **meta),
                ]
                with self.assertRaisesRegex(ValueError, "route"):
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                self.assertEqual(build.return_value.open.call_count, 3)

    def test_accepts_removed_legacy_route_and_only_builtin_log_destinations(self):
        settings = {**REDACTED, "observability": {
            **REDACTED["observability"], "logs": {"destinations": ["cloudflare"]}, "traces": {"destinations": []},
        }}
        with mock.patch.object(ingress.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = [
                response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]), response([]),
                response(settings), response({**settings, "tail_consumers": []}),
                response({"enabled": False}), response({"domains": []}),
                *queue_responses("workdoe-email", EMAIL_QUEUE_ID),
                *queue_responses("workdoe-media-review", MEDIA_QUEUE_ID),
            ]
            ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)

    def test_hosted_release_rejects_direct_bucket_access_or_unverified_metadata(self):
        hidden = "unreviewed-bucket-domain.example"
        for label, managed, custom, error in (
            ("public dev URL", response({"enabled": True, "domain": hidden}), response({"domains": []}), "R2"),
            ("public custom domain", response({"enabled": False}),
             response({"domains": [{"domain": hidden, "enabled": True}]}), "R2"),
            ("disabled but attached", response({"enabled": False}),
             response({"domains": [{"domain": hidden, "enabled": False}]}), "R2"),
            ("missing managed state", response({"domain": hidden}), response({"domains": []}), "R2"),
            ("non-boolean managed state", response({"enabled": 0}), response({"domains": []}), "R2"),
            ("missing domain list", response({"enabled": False}), response({}), "R2"),
            ("incomplete domain list", response({"enabled": False}),
             response({"domains": []}, result_info={"total_count": 1}), "incomplete"),
            ("read denied", response({"enabled": False}),
             urllib.error.HTTPError("https://api.cloudflare.com", 403, TOKEN, {}, None), "HTTP 403"),
        ):
            with self.subTest(label=label), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = [
                    response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
                    response([]), response(REDACTED), response({**REDACTED, "tail_consumers": []}),
                    managed, custom,
                ]
                with self.assertRaisesRegex(ValueError, error) as caught:
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                self.assertNotIn(hidden, str(caught.exception))
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_hosted_release_rejects_unreviewed_or_incomplete_queue_routing(self):
        name = "workdoe-email"
        queue, consumer = queue_fixture(name, EMAIL_QUEUE_ID)
        page = {"page": 1, "count": 1, "total_count": 1, "total_pages": 1}
        hidden = "unreviewed-private-queue-configuration"
        cases = (
            ("missing queue", [], page, [consumer], page),
            ("wrong queue", [queue | {"queue_name": hidden}], page, [consumer], page),
            ("ambiguous lookup", [queue], page | {"total_pages": 2}, [consumer], page),
            ("invalid queue id", [queue | {"queue_id": "not-an-id"}], page, [consumer], page),
            ("hidden extra producer", [queue | {"producers_total_count": 2}], page, [consumer], page),
            ("foreign producer", [queue | {"producers": [{"type": "worker", "script": hidden}]}], page, [consumer], page),
            ("explicitly paused", [queue | {"settings": {"delivery_paused": True}}], page, [consumer], page),
            ("absent consumer", [queue], page, [], page),
            ("extra consumer", [queue], page, [consumer, consumer], page),
            ("HTTP pull", [queue], page, [consumer | {"type": "http_pull"}], page),
            ("wrong worker", [queue], page, [consumer | {"script": hidden}], page),
            ("conflicting worker alias", [queue], page, [consumer | {"script_name": hidden}], page),
            ("swapped consumer id", [queue], page, [consumer | {"consumer_id": "0" * 31 + "1"}], page),
            ("wrong queue reference", [queue], page, [consumer | {"queue_id": MEDIA_QUEUE_ID}], page),
            ("wrong embedded reference", [queue | {"consumers": [consumer | {"queue_name": hidden}]}], page,
             [consumer], page),
            ("missing direct queue name", [queue], page,
             [{key: value for key, value in consumer.items() if key != "queue_name"}], page),
            ("dead letter queue", [queue], page, [consumer | {"dead_letter_queue": hidden}], page),
            ("retry drift", [queue], page, [consumer | {"settings": consumer["settings"] | {"max_retries": 1}}], page),
            ("retry delay drift", [queue], page, [consumer | {"settings": consumer["settings"] | {"retry_delay": 60}}], page),
            ("batch timeout drift", [queue], page,
             [consumer | {"settings": consumer["settings"] | {"max_wait_time_ms": 30}}], page),
            ("incomplete consumers", [queue], page, [consumer], page | {"total_count": 2}),
        )
        for label, rows, queue_page, consumers, consumer_page in cases:
            with self.subTest(label=label), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = [
                    response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
                    response([]), response(REDACTED), response({**REDACTED, "tail_consumers": []}),
                    response({"enabled": False}), response({"domains": []}),
                    response(rows, result_info=queue_page), response(consumers, result_info=consumer_page),
                ]
                with self.assertRaisesRegex(ValueError, "queue|consumer") as caught:
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                self.assertNotIn(hidden, str(caught.exception))
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_recovery_requires_explicit_pause_on_both_named_queues(self):
        for states in ((True, True), (True, False), (True, None), (True, "true")):
            with self.subTest(states=states):
                opener = mock.Mock()
                opener.open.side_effect = [
                    *queue_responses("workdoe-email", EMAIL_QUEUE_ID, paused=states[0]),
                    *queue_responses("workdoe-media-review", MEDIA_QUEUE_ID, paused=states[1]),
                ]
                if states == (True, True):
                    ingress.verify_hosted_queue_routing(opener, ACCOUNT, TOKEN, require_paused=True)
                    self.assertEqual(opener.open.call_count, 4)
                else:
                    with self.assertRaisesRegex(ValueError, "explicitly paused"):
                        ingress.verify_hosted_queue_routing(opener, ACCOUNT, TOKEN, require_paused=True)
                    self.assertEqual(opener.open.call_count, 3)

    def test_requires_both_telemetry_readbacks_and_never_exposes_destinations(self):
        def with_destination(channel, destinations):
            return {**REDACTED, "tail_consumers": [], "observability": {
                **REDACTED["observability"], channel: {"destinations": destinations},
            }}

        allowed = {**REDACTED, "tail_consumers": []}
        for settings in (
            {**allowed, "logpush": True}, {**allowed, "logpush": None},
            {**allowed, "tail_consumers": [{"service": TOKEN}]},
            with_destination("logs", ["cloudflare", TOKEN]), with_destination("traces", [TOKEN]),
            with_destination("logs", "cloudflare"), with_destination("traces", None),
            {**allowed, "observability": {"enabled": True, "redact_query_string": False}},
        ):
            for endpoint, telemetry in (
                ("script-settings", [settings, allowed]), ("settings", [allowed, settings]),
            ):
                with self.subTest(endpoint=endpoint, settings=settings), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                    build.return_value.open.side_effect = [
                        response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
                        response([]), *(response(item) for item in telemetry),
                    ]
                    with self.assertRaisesRegex(ValueError, "Logpush|Tail Worker|destination|redaction") as caught:
                        ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                    self.assertNotIn(TOKEN, str(caught.exception))

        with mock.patch.object(ingress.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = [
                response(DISABLED), response([domain("workdoe.com"), domain("www.workdoe.com")]),
                response([]), response(allowed), response(REDACTED),
            ]
            with self.assertRaisesRegex(ValueError, "Tail Worker"):
                ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)

    def test_errors_fail_closed_without_exposing_provider_payloads(self):
        cases = [
            (urllib.error.HTTPError("https://api.cloudflare.com", 403, TOKEN, {}, None), "HTTP 403"),
            (urllib.error.HTTPError("https://api.cloudflare.com", 302, TOKEN, {}, None), "HTTP 302"),
            (response(body=TOKEN.encode()), "not valid JSON"),
            (response(body=b"x" * (ingress.MAX_RESPONSE_BYTES + 1)), "response limit"),
            (response(body=b'{"success":false}'), "did not confirm"),
        ]
        for reply, error in cases:
            with self.subTest(error=error), mock.patch.object(ingress.urllib.request, "build_opener") as build:
                build.return_value.open.side_effect = [reply]
                with self.assertRaisesRegex(ValueError, error) as caught:
                    ingress.verify_hosted_worker_ingress(ACCOUNT, ENV)
                self.assertNotIn(TOKEN, str(caught.exception))

    def test_requires_the_reviewed_account_and_rejects_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "wrangler.jsonc"
            config.write_text('{"name":"workdoe"}', encoding="utf-8")
            self.assertEqual(ingress.reviewed_ingress_account(config.parent, ENV), ACCOUNT)
            with self.assertRaisesRegex(ValueError, "Set CLOUDFLARE_ACCOUNT_ID"):
                ingress.reviewed_ingress_account(config.parent, {})
            for name in ("CLOUDFLARE_API_BASE_URL", "WRANGLER_CI_OVERRIDE_NAME", "WRANGLER_CI_GENERATE_PREVIEW_ALIAS"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "overrides"):
                    ingress.reviewed_ingress_account(config.parent, {**ENV, name: "true"})
            config.write_text(json.dumps({"name": "workdoe", "account_id": "b" * 32}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                ingress.reviewed_ingress_account(config.parent, ENV)
        with mock.patch.object(ingress.urllib.request, "build_opener") as build:
            with self.assertRaisesRegex(ValueError, "same reviewed account"):
                ingress.verify_hosted_worker_ingress("b" * 32, ENV)
            with self.assertRaisesRegex(ValueError, "valid Cloudflare credential"):
                ingress.verify_hosted_worker_ingress(ACCOUNT, ENV, oauth_token="invalid token")
            build.assert_not_called()

    def test_oauth_token_uses_capture_and_disables_output_files(self):
        env = {"WRANGLER_OUTPUT_FILE_PATH": "unused", "WRANGLER_OUTPUT_FILE_DIRECTORY": "unused"}
        output = json.dumps({"type": "oauth", "token": TOKEN})
        with mock.patch.object(ingress.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)) as run:
            self.assertEqual(ingress.wrangler_oauth_access_token(Path.cwd(), env), TOKEN)
        self.assertEqual(run.call_args.args[0][1:], ["auth", "token", "--json", "--config", "wrangler.jsonc"])
        self.assertTrue(run.call_args.kwargs["capture_output"])
        auth_env = run.call_args.kwargs["env"]
        self.assertEqual(auth_env["WRANGLER_WRITE_LOGS"], "false")
        self.assertEqual(auth_env["CI"], "true")
        self.assertFalse(set(auth_env) & env.keys())
        for reply in (subprocess.CompletedProcess([], 1, output), subprocess.CompletedProcess([], 0, TOKEN)):
            with mock.patch.object(ingress.subprocess, "run", return_value=reply):
                with self.assertRaisesRegex(ValueError, "authorized Wrangler OAuth") as caught:
                    ingress.wrangler_oauth_access_token(Path.cwd(), env)
                self.assertNotIn(TOKEN, str(caught.exception))
