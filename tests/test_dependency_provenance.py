from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "verify_dependency_provenance.py"


def load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_dependency_provenance", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DependencyProvenanceTests(unittest.TestCase):
    def test_ledger_declares_the_cross_platform_hash_policy(self):
        verifier = load_verifier()

        self.assertEqual(
            verifier.REPOSITORY_HASH_POLICY,
            {"binary": "sha256-bytes", "text": "sha256-lf"},
        )

    def test_text_hashes_are_stable_across_checkout_line_endings(self):
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "vendor.css"
            path.write_bytes(b"first\nsecond\n")
            lf_hash = verifier.sha256_file(path)
            path.write_bytes(b"first\r\nsecond\r\n")

            self.assertEqual(verifier.sha256_file(path), lf_hash)

    def test_binary_hashes_preserve_exact_bytes(self):
        verifier = load_verifier()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "vendor.png"
            content = b"binary\r\ncontent"
            path.write_bytes(content)

            self.assertEqual(
                verifier.sha256_file(path),
                hashlib.sha256(content).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
