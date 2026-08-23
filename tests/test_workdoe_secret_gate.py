from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
