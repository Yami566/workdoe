import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PREVIEW_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
STAGING_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
RESERVED_ID = "ba816597-68ba-40a9-830e-751f44e4f54b"
RESERVED_PRODUCTION_ID = "fe8c22a8-1585-46dd-916e-2913c60d139a"
DISABLED_PREVIEW = "00000000-0000-0000-0000-000000000000"


class StagingConfigTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ("prepare_cloudflare_staging.py", "prepare_cloudflare_release.py"):
            shutil.copyfile(ROOT / "scripts" / name, scripts / name)
        self.cli = scripts / "prepare_cloudflare_staging.py"
        cloudflare = self.root / "cloudflare"
        cloudflare.mkdir()
        self.production = cloudflare / "wrangler.jsonc"
        source = json.loads((ROOT / "cloudflare/wrangler.jsonc").read_text(encoding="utf-8"))
        source["d1_databases"][0].update(database_id=PRODUCTION_ID, preview_database_id=PREVIEW_ID)
        source["routes"] = [{"pattern": "workdoe.com", "custom_domain": True}]
        source["vars"]["WORKDOE_WRITE_MODE"] = "normal"
        source["vars"]["WORKDOE_MEDIA_UPLOADS_ENABLED"] = "true"
        self.source = json.dumps(source).encode()
        self.production.write_bytes(self.source)
        self.target = cloudflare / "wrangler.staging.local.json"
        self.inventory = self.root / "d1-inventory.local.json"
        self.live_record = {"name": "workdoe", "uuid": PRODUCTION_ID}
        self.stage_record = {"name": "workdoe-staging", "uuid": STAGING_ID.upper()}

    def run_cli(self, *args):
        # Invoke only the checked-in script with local fixture input.
        return subprocess.run(  # nosec B603
            [sys.executable, "-E", "-s", "-S", str(self.cli), "--inventory", str(self.inventory), *args],
            cwd=self.root, capture_output=True, text=True, check=False, timeout=10,
        )

    def set_inventory(self, rows=None):
        self.inventory.write_text(
            json.dumps(rows if rows is not None else [self.live_record, self.stage_record]),
            encoding="utf-8-sig",
        )

    def test_generates_exact_sealed_scope_without_copying_production_settings(self):
        self.set_inventory()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(config["name"], "workdoe-staging")
        self.assertIs(config["workers_dev"], False)
        self.assertIs(config["preview_urls"], False)
        self.assertEqual(config["routes"], [])
        self.assertEqual(config["triggers"], {"crons": []})
        self.assertEqual(config["d1_databases"], [{
            "binding": "DB", "database_name": "workdoe-staging",
            "database_id": STAGING_ID, "migrations_dir": "d1/migrations",
        }])
        self.assertEqual(config["r2_buckets"], [{"binding": "MEDIA", "bucket_name": "workdoe-staging-media"}])
        self.assertEqual(config["queues"], {"producers": [
            {"binding": "EMAIL_QUEUE", "queue": "workdoe-staging-email"},
            {"binding": "MEDIA_QUEUE", "queue": "workdoe-staging-media-review"},
        ], "consumers": []})
        self.assertEqual(config["vars"], {
            "WORKDOE_ENV": "staging", "WORKDOE_DOMAIN": "staging.workdoe.com",
            "WORKDOE_PUBLIC_URL": "https://staging.workdoe.com", "WORKDOE_WRITE_MODE": "sealed",
            "WORKDOE_AUTH_PROVIDER": "clerk", "WORKDOE_MAP_MODE": "area",
            "WORKDOE_MEDIA_UPLOADS_ENABLED": "false",
        })
        for key in ("send_email", "secrets", "ratelimits", "env", "observability"):
            self.assertNotIn(key, config)
        self.assertEqual(self.production.read_bytes(), self.source)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_rejects_wrong_or_ambiguous_database_inventory_without_writing(self):
        for records in (
            {"result": [self.live_record, self.stage_record]},
            [self.stage_record],
            [self.live_record],
            [{**self.live_record, "uuid": PREVIEW_ID}, self.stage_record],
            [self.live_record, self.stage_record, self.stage_record],
            [self.live_record, {**self.stage_record, "uuid": PRODUCTION_ID.upper()}],
            [self.live_record, {**self.stage_record, "uuid": PREVIEW_ID.upper()}],
            [self.live_record, {**self.stage_record, "uuid": "00000000-0000-0000-0000-000000000000"}],
            [self.live_record, {**self.stage_record, "uuid": "workdoe-staging"}],
            [self.live_record, self.stage_record, {**self.stage_record, "name": "some-other-app"}],
        ):
            with self.subTest(records=records):
                self.set_inventory(records)
                result = self.run_cli()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.production.read_bytes(), self.source)

    def test_check_rejects_drift_and_generation_never_overwrites_a_local_config(self):
        self.set_inventory()
        self.assertEqual(self.run_cli().returncode, 0)
        config = json.loads(self.target.read_text(encoding="utf-8"))
        config["routes"] = [{"pattern": "workdoe.com", "custom_domain": True}]
        altered = json.dumps(config).encode()
        self.target.write_bytes(altered)
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.target.read_bytes(), altered)

    def reserve_preview_fixture(self):
        source = json.loads(self.source)
        source["d1_databases"][0].update(
            database_id=RESERVED_PRODUCTION_ID, preview_database_id=DISABLED_PREVIEW,
        )
        self.source = json.dumps(source).encode()
        self.production.write_bytes(self.source)
        return [
            {"name": "workdoe", "uuid": RESERVED_PRODUCTION_ID},
            {"name": "workdoe-preview", "uuid": RESERVED_ID},
        ]

    def test_reserved_target_needs_explicit_selection_and_preserves_the_seal(self):
        self.set_inventory(self.reserve_preview_fixture())
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(self.target.exists())
        result = self.run_cli("--use-reserved-preview")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(config["d1_databases"], [{
            "binding": "DB", "database_name": "workdoe-preview",
            "database_id": RESERVED_ID, "migrations_dir": "d1/migrations",
        }])
        self.assertEqual(config["vars"]["WORKDOE_WRITE_MODE"], "sealed")
        self.assertEqual(config["vars"]["WORKDOE_MEDIA_UPLOADS_ENABLED"], "false")
        self.assertEqual(config["queues"]["consumers"], [])
        self.assertEqual(config["routes"], [])
        self.assertIs(config["workers_dev"], False)
        self.assertIs(config["preview_urls"], False)
        self.assertNotIn("secrets", config)
        self.assertNotIn("send_email", config)
        self.assertEqual(self.production.read_bytes(), self.source)
        self.assertEqual(self.run_cli("--use-reserved-preview", "--check").returncode, 0)
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        self.assertNotEqual(self.run_cli("--use-reserved-preview").returncode, 0)

    def test_reserved_selection_rejects_unreviewed_identities_or_aliases_without_writes(self):
        records = self.reserve_preview_fixture()
        baseline = json.loads(self.source)
        for key, value in (
            ("preview_database_id", RESERVED_ID), ("preview_database_id", PREVIEW_ID),
            ("preview_database_id", None), ("database_id", PRODUCTION_ID),
            ("database_id", RESERVED_ID),
        ):
            source = json.loads(json.dumps(baseline))
            source["d1_databases"][0][key] = value
            original = json.dumps(source).encode()
            self.production.write_bytes(original)
            self.set_inventory(records)
            with self.subTest(key=key, value=value):
                self.assertNotEqual(self.run_cli("--use-reserved-preview").returncode, 0)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.production.read_bytes(), original)
        self.production.write_bytes(self.source)
        for rows in (
            records[:1], [records[0], {**records[1], "uuid": STAGING_ID}],
            [*records, records[1]], [*records, {"name": "elsewhere", "uuid": RESERVED_ID}],
            [*records, {"name": "workdoe-staging", "uuid": STAGING_ID}],
        ):
            self.set_inventory(rows)
            with self.subTest(rows=rows):
                self.assertNotEqual(self.run_cli("--use-reserved-preview").returncode, 0)
                self.assertFalse(self.target.exists())
                self.assertEqual(self.production.read_bytes(), self.source)

    def test_default_selection_cannot_relabel_reserved_storage_as_new_staging(self):
        self.set_inventory([self.live_record, {"name": "workdoe-staging", "uuid": RESERVED_ID}])
        self.assertNotEqual(self.run_cli().returncode, 0)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.production.read_bytes(), self.source)
