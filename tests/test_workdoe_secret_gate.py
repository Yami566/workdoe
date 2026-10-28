from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "workdoe_secret_gate.py"


def load_secret_gate_module():
    spec = importlib.util.spec_from_file_location("workdoe_secret_gate_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class WorkdoeSecretGateTests(unittest.TestCase):
    def setUp(self):
        self.module = load_secret_gate_module()

    def write_baseline(self, root: Path, finding: dict) -> Path:
        baseline = root / ".secrets.baseline"
        baseline.write_text(
            json.dumps(
                {
                    "version": "1.5.0",
                    "plugins_used": [],
                    "results": {"example.py": [finding]},
                }
            ),
            encoding="utf-8",
        )
        return baseline

    def test_baseline_audit_requires_explicit_false_positive_verdicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            finding = {
                "type": "Secret Keyword",
                "filename": "example.py",
                "hashed_secret": "review-me",  # pragma: allowlist secret
                "line_number": 1,
            }
            baseline = self.write_baseline(root, finding)
            self.assertIn("1 unaudited finding", self.module.baseline_audit_error(baseline))

            baseline = self.write_baseline(root, {**finding, "is_secret": True})
            self.assertIn("1 confirmed secret finding", self.module.baseline_audit_error(baseline))

            baseline = self.write_baseline(root, {**finding, "is_secret": False})
            self.assertEqual(self.module.baseline_audit_error(baseline), "")

    def test_baseline_audit_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / ".secrets.baseline"
            baseline.write_text("not-json", encoding="utf-8")
            self.assertIn("invalid JSON", self.module.baseline_audit_error(baseline))

    def test_file_arguments_are_batched_without_reordering_or_omission(self):
        files = ["one.py", "two-long.py", "three.py", "four-long.py"]
        batches = self.module.file_argument_batches(files, max_chars=20)

        self.assertGreater(len(batches), 1)
        self.assertEqual([path for batch in batches for path in batch], files)
        self.assertTrue(
            all(
                len(batch) == 1 or sum(len(path) + 3 for path in batch) <= 20
                for batch in batches
            )
        )

    def test_command_path_keeps_repository_baseline_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / ".secrets.baseline"

            self.assertEqual(self.module.command_path(baseline, root), ".secrets.baseline")
            self.assertEqual(
                self.module.command_path(root.parent / "external.json", root),
                str(root.parent / "external.json"),
            )

    def test_baseline_fingerprints_normalize_repository_path_separators(self):
        fingerprints = self.module.baseline_fingerprints(
            {
                "results": {
                    "tests\\example.py": [
                        {
                            "filename": "tests\\example.py",
                            "type": "Secret Keyword",
                            "hashed_secret": "reviewed-hash",  # pragma: allowlist secret
                        }
                    ]
                }
            }
        )

        self.assertEqual(
            fingerprints,
            {("tests/example.py", "Secret Keyword", "reviewed-hash")},
        )

    def test_secret_scan_never_mutates_the_reviewed_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = self.write_baseline(
                root,
                {
                    "type": "Secret Keyword",
                    "filename": "example.py",
                    "hashed_secret": "reviewed-hash",  # pragma: allowlist secret
                    "line_number": 1,
                    "is_secret": False,
                },
            )
            original = baseline.read_text(encoding="utf-8")

            def move_reviewed_finding(command, **_kwargs):
                scan_baseline = root / command[2]
                payload = json.loads(scan_baseline.read_text(encoding="utf-8"))
                payload["results"]["example.py"][0]["line_number"] = 2
                scan_baseline.write_text(json.dumps(payload), encoding="utf-8")
                return mock.Mock(returncode=1, stdout="", stderr="baseline updated")

            with (
                mock.patch.object(
                    self.module.shutil,
                    "which",
                    return_value="detect-secrets-hook",
                ),
                mock.patch.object(
                    self.module,
                    "repository_files",
                    return_value=["example.py"],
                ),
                mock.patch.object(self.module.subprocess, "run", side_effect=move_reviewed_finding),
            ):
                payload = self.module.run_gate(root, baseline)

            self.assertTrue(payload["ok"])
            self.assertEqual(baseline.read_text(encoding="utf-8"), original)

    def test_secret_scan_rejects_a_new_candidate_without_mutating_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = self.write_baseline(
                root,
                {
                    "type": "Secret Keyword",
                    "filename": "example.py",
                    "hashed_secret": "reviewed-hash",  # pragma: allowlist secret
                    "line_number": 1,
                    "is_secret": False,
                },
            )
            original = baseline.read_text(encoding="utf-8")

            def add_candidate(command, **_kwargs):
                scan_baseline = root / command[2]
                payload = json.loads(scan_baseline.read_text(encoding="utf-8"))
                payload["results"]["new.py"] = [
                    {
                        "type": "Secret Keyword",
                        "filename": "new.py",
                        "hashed_secret": "new-hash",  # pragma: allowlist secret
                    }
                ]
                scan_baseline.write_text(json.dumps(payload), encoding="utf-8")
                return mock.Mock(returncode=1, stdout="", stderr="candidate found")

            with (
                mock.patch.object(
                    self.module.shutil,
                    "which",
                    return_value="detect-secrets-hook",
                ),
                mock.patch.object(
                    self.module,
                    "repository_files",
                    return_value=["new.py"],
                ),
                mock.patch.object(self.module.subprocess, "run", side_effect=add_candidate),
            ):
                payload = self.module.run_gate(root, baseline)

            self.assertFalse(payload["ok"])
            self.assertIn("new.py", payload["error"])
            self.assertEqual(baseline.read_text(encoding="utf-8"), original)

    def test_secret_scan_fails_when_any_batch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / ".secrets.baseline"
            baseline.write_text(
                json.dumps({"version": "1.5.0", "plugins_used": [], "results": {}}),
                encoding="utf-8",
            )
            passed = mock.Mock(returncode=0, stdout="", stderr="")
            failed = mock.Mock(returncode=1, stdout="", stderr="secret found")

            with (
                mock.patch.object(
                    self.module.shutil,
                    "which",
                    return_value="detect-secrets-hook",
                ),
                mock.patch.object(
                    self.module,
                    "repository_files",
                    return_value=["one.py", "two.py"],
                ),
                mock.patch.object(
                    self.module,
                    "file_argument_batches",
                    return_value=[["one.py"], ["two.py"]],
                ),
                mock.patch.object(
                    self.module.subprocess,
                    "run",
                    side_effect=[passed, failed],
                ),
            ):
                payload = self.module.run_gate(root, baseline)

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["file_count"], 2)
            self.assertIn("secret found", payload["error"])


if __name__ == "__main__":
    unittest.main()
