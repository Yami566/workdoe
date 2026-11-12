import importlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
with mock.patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    release = importlib.import_module("prepare_cloudflare_release")
    bootstrap = importlib.import_module("cloudflare_resource_bootstrap")
    launch = importlib.import_module("cloudflare_launch_plan")
    recovery = importlib.import_module("cloudflare_worker_recovery")
    readback = importlib.import_module("cloudflare_staging_readback")
    apply_ids = importlib.import_module("apply_cloudflare_d1_ids")


class StagingReservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cloudflare = self.root / "cloudflare"
        self.cloudflare.mkdir()
        self.path = self.cloudflare / "wrangler.jsonc"
        self.config = json.loads((ROOT / "cloudflare/wrangler.jsonc").read_text(encoding="utf-8"))
        self.path.write_text(json.dumps(self.config), encoding="utf-8")

    def test_reserved_identity_is_detached_and_production_verification_stays_exact(self):
        self.assertEqual(release.production_d1_ids(self.config), (release.REVIEWED_PRODUCTION_D1_ID, None))
        self.assertEqual(self.config["d1_databases"][0]["preview_database_id"], release.ZERO_UUID)
        self.assertEqual(recovery.reviewed_d1_database_id(self.cloudflare), release.REVIEWED_PRODUCTION_D1_ID)
        metadata = {"resources": {"bindings": [{
            "name": "DB", "type": "d1", "database_id": release.RESERVED_STAGING_D1_ID,
        }]}}
        with self.assertRaisesRegex(ValueError, "does not match"):
            recovery.verify_worker_d1_binding(metadata, release.REVIEWED_PRODUCTION_D1_ID)

    def test_identity_guard_rejects_missing_invalid_shared_and_reserved_targets(self):
        baseline = self.config["d1_databases"][0]
        cases = [
            {**baseline, "database_id": release.RESERVED_STAGING_D1_ID.upper()},
            {**baseline, "preview_database_id": release.RESERVED_STAGING_D1_ID.upper()},
            {**baseline, "preview_database_id": baseline["database_id"]},
            {key: value for key, value in baseline.items() if key != "preview_database_id"},
        ]
        for key in ("database_id", "preview_database_id"):
            cases.extend({**baseline, key: value} for value in (None, False, "", "not-a-uuid", [], {}))
        for binding in cases:
            config = self.config | {"d1_databases": [binding]}
            self.path.write_text(json.dumps(config), encoding="utf-8")
            with self.subTest(binding=binding):
                with self.assertRaises(ValueError):
                    release.production_d1_ids(config)
                with self.assertRaises(ValueError):
                    recovery.reviewed_d1_database_id(self.cloudflare)
                self.assertFalse(launch.d1_ids_are_configured(config))
                self.assertFalse(bootstrap.d1_ready(self.root))

    def test_disabled_preview_is_ready_without_planning_another_database_creation(self):
        self.assertTrue(launch.d1_ids_are_configured(self.config))
        self.assertTrue(bootstrap.d1_ready(self.root))
        report = bootstrap.plan_payload(self.root, include_secret_probe=False)
        self.assertTrue(report["d1_ids_configured"])
        self.assertEqual(report["d1_database_id"], release.REVIEWED_PRODUCTION_D1_ID)
        self.assertEqual(report["d1_preview_database_id"], release.ZERO_UUID)
        self.assertFalse({"create-d1-production", "create-d1-preview", "apply-d1-ids"} & {
            step["name"] for step in report["steps"]
        })

    def test_bootstrap_refuses_unsafe_existing_binding_instead_of_creating_replacements(self):
        baseline = self.config["d1_databases"][0]
        for preview in (None, release.RESERVED_STAGING_D1_ID, baseline["database_id"]):
            source = self.config | {"d1_databases": [baseline | {"preview_database_id": preview}]}
            self.path.write_text(json.dumps(source), encoding="utf-8")
            with self.subTest(preview=preview), self.assertRaisesRegex(ValueError, "refusing resource creation"):
                bootstrap.plan_payload(self.root, include_secret_probe=False)

    def test_bootstrap_does_not_misreport_an_execution_error_as_no_commands(self):
        with (
            mock.patch.object(sys, "argv", ["bootstrap", "--execute", "--yes", "--json"]),
            mock.patch.object(bootstrap, "cloudflare_api_token_present", return_value=True),
            mock.patch.object(bootstrap, "build_bootstrap_steps", return_value=[]),
            mock.patch.object(bootstrap, "execute_steps", side_effect=ValueError("synthetic execution error")),
            mock.patch("sys.stdout", new_callable=io.StringIO) as output,
            self.assertRaisesRegex(ValueError, "synthetic execution error"),
        ):
            bootstrap.main()
        self.assertEqual(output.getvalue(), "")

    def test_release_generation_preserves_disabled_preview_and_refuses_reserved_alias(self):
        manifest = json.loads((ROOT / "cloudflare/workdoe-cloudflare-manifest.json").read_text(encoding="utf-8"))
        ids = release.existing_d1_ids(self.path)
        generated = release.build_wrangler_config(manifest, ids)
        self.assertEqual(generated["d1_databases"], self.config["d1_databases"])
        for key in ("database_id", "preview_database_id"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "reserved staging"):
                release.build_wrangler_config(manifest, ids | {key: release.RESERVED_STAGING_D1_ID})

    def test_id_apply_refuses_reserved_or_shared_targets_before_changing_file(self):
        original = self.path.read_bytes()
        for primary, preview in (
            (release.RESERVED_STAGING_D1_ID, "11111111-1111-4111-8111-111111111111"),
            (release.REVIEWED_PRODUCTION_D1_ID, release.RESERVED_STAGING_D1_ID),
            (release.REVIEWED_PRODUCTION_D1_ID, release.REVIEWED_PRODUCTION_D1_ID),
        ):
            with self.subTest(primary=primary, preview=preview), self.assertRaises(apply_ids.D1IdError):
                apply_ids.apply_d1_ids(self.path, database_id=primary, preview_database_id=preview)
            self.assertEqual(self.path.read_bytes(), original)
        self.path.write_text(json.dumps(self.config | {
            "d1_databases": self.config["d1_databases"] * 2,
        }), encoding="utf-8")
        duplicate = self.path.read_bytes()
        with self.assertRaises(apply_ids.D1IdError):
            apply_ids.apply_d1_ids(self.path, database_id=release.REVIEWED_PRODUCTION_D1_ID, disable_preview=True)
        self.assertEqual(self.path.read_bytes(), duplicate)

    def test_reserved_readback_requires_explicit_selection_and_does_not_claim_initialization(self):
        inventory = [
            {"name": "workdoe", "uuid": release.REVIEWED_PRODUCTION_D1_ID},
            {"name": release.RESERVED_STAGING_D1_NAME, "uuid": release.RESERVED_STAGING_D1_ID},
        ]
        self.assertEqual(readback.d1_readback(self.config, inventory), {
            "account_database_count": 2, "dedicated_database_present": False,
        })
        selected = readback.d1_readback(self.config, inventory, use_reserved_preview=True)
        self.assertEqual(selected, {
            "account_database_count": 2, "dedicated_database_present": False,
            "selected_staging_database_present": True, "staging_database_source": "reserved_preview",
        })
        self.assertNotIn("data_contents", selected)
        self.assertNotIn("schema", selected)
        drift = self.config | {"d1_databases": [self.config["d1_databases"][0] | {
            "preview_database_id": "11111111-1111-4111-8111-111111111111",
        }]}
        with self.assertRaises(ValueError):
            readback.d1_readback(drift, inventory, use_reserved_preview=True)

    def test_id_apply_supports_explicit_disable_without_implicit_or_conflicting_target(self):
        source = self.config | {"d1_databases": [self.config["d1_databases"][0] | {
            "preview_database_id": "11111111-1111-4111-8111-111111111111",
        }]}
        self.path.write_text(json.dumps(source), encoding="utf-8")
        report = apply_ids.apply_d1_ids(
            self.path, database_id=release.REVIEWED_PRODUCTION_D1_ID, disable_preview=True,
        )
        self.assertTrue(report["changed"])
        changed = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(release.production_d1_ids(changed), (release.REVIEWED_PRODUCTION_D1_ID, None))
        original = self.path.read_bytes()
        for arguments in (
            {"preview_database_id": release.RESERVED_STAGING_D1_ID},
            {"preview_from_file": Path("unread-fixture")}, {"use_database_for_preview": True},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(apply_ids.D1IdError):
                apply_ids.apply_d1_ids(
                    self.path, database_id=release.REVIEWED_PRODUCTION_D1_ID, disable_preview=True, **arguments,
                )
            self.assertEqual(self.path.read_bytes(), original)
