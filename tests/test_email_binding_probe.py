from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    SPEC = importlib.util.spec_from_file_location(
        "diagnose_email_binding", ROOT / "scripts" / "diagnose_email_binding.py"
    )
    probe = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(probe)
finally:
    sys.path.remove(str(ROOT / "scripts"))


class EmailBindingProbeTests(unittest.TestCase):
    def test_journey_fixture_preserves_production_entrypoint_without_subclass(self):
        module = ast.parse((ROOT / "tests/native_worker/journey_entry.py").read_text())
        self.assertFalse(
            any(isinstance(node, ast.ClassDef) and node.bases for node in module.body)
        )
        assignments = {
            ast.unparse(node.targets[0]): ast.unparse(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
        }
        self.assertEqual(assignments["Default"], "entry.Default")
        self.assertEqual(assignments["production_fetch"], "entry.Default.fetch")
        self.assertEqual(assignments["Default.fetch"], "fixture_fetch")

    def test_configs_are_local_only_and_have_no_production_bindings(self):
        for language in ("python", "javascript", "python-subclass"):
            config = probe.probe_configuration(language)
            self.assertFalse(config["workers_dev"])
            self.assertEqual(config["vars"], {"PROBE_MODE": "local-only"})
            self.assertEqual(
                config["send_email"],
                [
                    {
                        "name": "EMAIL",
                        "remote": False,
                        "allowed_sender_addresses": ["sender@example.invalid"],
                        "allowed_destination_addresses": ["mailbox@example.invalid"],
                    }
                ],
            )
            self.assertEqual(
                set(config),
                {
                    "name",
                    "main",
                    "workers_dev",
                    "compatibility_date",
                    "compatibility_flags",
                    "vars",
                    "send_email",
                },
            )
        with self.assertRaises(ValueError):
            probe.probe_configuration("remote")

    def test_provider_credentials_and_profiles_are_not_inherited(self):
        environment = {
            "PATH": "fixture-path",
            "CF_API_TOKEN": "synthetic",
            "CLOUDFLARE_API_TOKEN": "synthetic",
            "CLERK_SECRET_KEY": "synthetic",  # pragma: allowlist secret - unusable fixture value, never sent.
            "WORKDOE_ADMIN_EMAIL": "synthetic",
            "WRANGLER_API_TOKEN": "synthetic",
        }
        result = probe.local_environment(environment, Path("fixture"))
        self.assertEqual(
            set(result), {"PATH", "WRANGLER_SEND_METRICS", "XDG_CONFIG_HOME"}
        )
        self.assertEqual(result["WRANGLER_SEND_METRICS"], "false")
        self.assertEqual(environment["CF_API_TOKEN"], "synthetic")

    def test_failed_python_or_control_never_becomes_ready_or_real_delivery(self):
        accepted = {"http_status": 200, "result": {"stage": "send-accepted"}}
        failed = {"http_status": 500, "result": {"stage": "binding-lookup"}}
        for javascript, python, subclass in (
            (accepted, failed, accepted),
            (failed, accepted, accepted),
            (accepted, accepted, failed),
            (None, None, None),
        ):
            result = probe.readiness(
                {
                    "javascript": javascript,
                    "python": python,
                    "python-subclass": subclass,
                }
            )
            self.assertFalse(result["native_probe_ready"])
            self.assertFalse(result["real_delivery_verified"])
        result = probe.readiness(
            {"javascript": accepted, "python": accepted, "python-subclass": accepted}
        )
        self.assertTrue(result["native_probe_ready"])
        self.assertFalse(result["real_delivery_verified"])
