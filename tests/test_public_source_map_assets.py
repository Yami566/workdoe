from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.cloudflare_preflight import validate_public_source_maps


class PublicSourceMapAssetsTests(unittest.TestCase):
    def check_assets(self, files: dict[str, str]) -> tuple[list[str], list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in files.items():
                asset = root / name
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_text(text, encoding="utf-8")
            errors, checks = [], []
            validate_public_source_maps(root, errors, checks)
            return errors, checks

    def test_missing_vendor_map_reference_and_ordinary_data_uri_are_allowed(self):
        errors, checks = self.check_assets({
            "vendor/vendor.js": "//# sourceMappingURL=vendor.js.map\n",
            "styles.css": "main { background: url(data:image/png;base64,Zml4dHVyZQ==); }",
            "index.html": "<title>Public page</title>",
        })
        self.assertEqual(errors, [])
        self.assertEqual(checks, ["Public assets do not ship source maps"])

    def test_blocks_nested_and_precompressed_map_files_without_reading_them(self):
        files = {"app.js.map": "fixture", "vendor/chunk.MAP.Gz": "fixture", "deep/css/a.css.map.br": "fixture"}
        errors, checks = self.check_assets(files)
        self.assertEqual(checks, [])
        for name in files:
            self.assertIn(name, errors[0])
        self.assertNotIn("fixture", errors[0])

    def test_rejects_inline_directives_without_printing_source_map_data(self):
        files = {
            "entry.mjs": "const x = 0; //# sourceMappingURL=data:application/json;base64,Zml4dHVyZQ==",
            "styles.css": "/* # sourceMappingURL = DATA:application/json,fixture */",
        }
        errors, checks = self.check_assets(files)
        self.assertEqual(checks, [])
        for name in files:
            self.assertIn(name, errors[0])
        self.assertNotIn("fixture", errors[0])
        self.assertNotIn("Zml4dHVyZQ==", errors[0])

    def test_missing_public_asset_directory_is_not_reported_as_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            errors, checks = [], []
            validate_public_source_maps(Path(directory) / "missing", errors, checks)
        self.assertEqual(checks, [])
        self.assertIn("Could not inspect", errors[0])
