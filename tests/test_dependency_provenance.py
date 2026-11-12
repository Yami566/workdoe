from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "verify_dependency_provenance.py"
WHEEL_LOCKS = tuple(f".github/python/{group}.txt" for group in ("runtime", "ruff", "audit"))


def load_verifier():
    spec = importlib.util.spec_from_file_location(
        "verify_dependency_provenance", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DependencyProvenanceTests(unittest.TestCase):
    def test_python_license_inventory_must_cover_both_direct_groups(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        for missing in ([], ledger["python_groups"][:1]):
            with self.subTest(group_count=len(missing)):
                errors = []
                verifier.validate_python_groups(ledger | {"python_groups": missing}, errors)
                self.assertTrue(any("must cover every root requirements file" in error for error in errors))

    def test_wheel_locks_reject_unreviewed_bytes_and_stale_inputs(self):
        verifier = load_verifier()
        cases = {
            "incomplete inventory": "must cover all three verification locks",
            "edited wheel hash": "wheel lock hash changed: ruff.txt",
            "unpinned wheel": "Invalid hashed wheel pin in ruff.txt",
            "stale root version": "does not match direct pins in requirements.txt",
            "missing Windows marker": "unexpected platform marker in runtime.txt",
        }
        for change, expected in cases.items():
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
                for relative in (*WHEEL_LOCKS, "requirements.txt", "requirements-audit.txt"):
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / relative, path)
                runtime, ruff, _ = (root / relative for relative in WHEEL_LOCKS)
                if change == "incomplete inventory":
                    del ledger["python_wheel_locks"]["ruff.txt"]
                elif change == "edited wheel hash":
                    ruff.write_bytes(ruff.read_bytes() + b"# synthetic edit\n")
                elif change == "unpinned wheel":
                    ruff.write_text("ruff==0.16.4\n", encoding="utf-8")
                    ledger["python_wheel_locks"][ruff.name] = verifier.sha256_file(ruff)
                elif change == "stale root version":
                    (root / "requirements.txt").write_text("blinker==1.8.2\n", encoding="utf-8")
                else:
                    text = runtime.read_text(encoding="utf-8").replace('; platform_system == "Windows"', "")
                    runtime.write_text(text, encoding="utf-8")
                    ledger["python_wheel_locks"][runtime.name] = verifier.sha256_file(runtime)
                errors = []
                with patch.object(verifier, "REPO_ROOT", root):
                    verifier.validate_python_wheel_locks(ledger, errors)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(expected, errors[0])

    def test_complete_npm_lock_review_catches_transitive_changes_and_shadow_lock(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        package = (ROOT / "package.json").read_bytes()
        lock_path = ROOT / "package-lock.json"
        for change in ("reformat", "version", "integrity", "license", "dev", "install-script", "add", "remove", "shadow"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                lock = json.loads(lock_path.read_text(encoding="utf-8"))
                entries = lock["packages"]
                transitive = "node_modules/miniflare"
                if change == "version":
                    entries[transitive]["version"] = "0.0.1"
                elif change == "integrity":
                    entries[transitive]["integrity"] = f"sha512-{'A' * 86}=="
                elif change == "license":
                    entries[transitive]["license"] = "GPL-3.0-only"
                elif change == "dev":
                    entries[transitive]["dev"] = False
                elif change == "install-script":
                    entries[transitive]["hasInstallScript"] = True
                elif change == "add":
                    entries["node_modules/extra"] = entries[transitive].copy()
                elif change == "remove":
                    del entries[transitive]
                elif change == "shadow":
                    (root / "npm-shrinkwrap.json").write_text("{}", encoding="utf-8")
                (root / "package.json").write_bytes(package)
                (root / "package-lock.json").write_text(json.dumps(lock, indent=4, sort_keys=True), encoding="utf-8")
                with patch.object(verifier, "REPO_ROOT", root):
                    errors = []
                    verifier.validate_node_tooling(ledger, errors)
                if change == "reformat":
                    self.assertEqual(errors, [])
                elif change == "shadow":
                    self.assertEqual(errors, ["npm-shrinkwrap.json is not part of the reviewed npm install"])
                else:
                    self.assertIn("The complete npm lockfile differs from the reviewed tooling inventory", errors)
                    if change == "dev":
                        self.assertTrue(any("dev-only registry provenance" in error for error in errors))

    def test_complete_npm_lock_review_cannot_be_omitted(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        ledger.pop("node_lock_review", None)
        errors = []
        verifier.validate_node_tooling(ledger, errors)
        self.assertEqual(errors, ["The complete npm lockfile differs from the reviewed tooling inventory"])

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

    def test_ledger_records_the_bundled_cloudflare_python_runtime_sdk(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))

        errors: list[str] = []
        verifier.validate_runtime_components(ledger, errors)

        self.assertEqual(errors, [])

    def test_ledger_pins_hosted_clerk_browser_components(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))

        errors: list[str] = []
        verifier.validate_hosted_browser_components(ledger, errors)

        self.assertEqual(errors, [])

        ledger["hosted_browser_components"][0]["script_integrity"] = "sha384-" + "A" * 64
        verifier.validate_hosted_browser_components(ledger, errors)
        self.assertEqual(errors, ["Clerk UI hosted-browser provenance has unexpected script_integrity"])

    def test_clerk_browser_filename_inventory_rejects_unrecorded_files(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        components = {row["name"]: row for row in ledger["hosted_browser_components"]}
        relative = Path("cloudflare/worker/clerk_browser_files.py")
        source = (ROOT / relative).read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            verifier.REPO_ROOT = Path(directory)
            candidate = verifier.REPO_ROOT / relative
            candidate.parent.mkdir(parents=True)
            candidate.write_text(source.replace(
                '        "ui.shared.browser.js",', '        "ui.shared.browser.js",\n        "unrecorded.js",',
            ), encoding="utf-8")
            errors: list[str] = []
            verifier.validate_clerk_browser_filenames(components, errors)
            self.assertEqual(errors, ["Clerk UI browser filename inventory does not match its recorded count or hash"])

    def test_clerk_historical_notice_index_must_match_its_exact_previous_scope(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        review = ledger["clerk_build_notices"]
        del review["coinbase_eip712_notice"]
        review["packages"] = [
            row for row in review["packages"]
            if row["package"] not in (verifier.CLERK_STRIPE_ZXCVBN_NOTICES | verifier.CLERK_RECENT_UI_NOTICES
                                      | verifier.CLERK_RUNTIME_NOTICE_ADDITIONS)
        ]
        review["index_sha256"] = "a333d6028c2855fc85312279d499111700cfbd23951309ee60155c257cffd694"

        errors: list[str] = []
        historical = verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True)
        self.assertEqual(errors, [])
        self.assertIn("formkit-auto-animate-0.8.4-license.txt", historical)
        self.assertNotIn("stripe-sdk-license.txt", historical)
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors), {})
        self.assertTrue(errors)

        errors.clear()
        review["index_sha256"] = "0" * 64
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
        self.assertTrue(errors)

    def test_clerk_notice_inventory_pins_embedded_isc_notice_and_predecessor(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        review = ledger["clerk_build_notices"]
        record = review["coinbase_eip712_notice"]
        errors: list[str] = []
        digests = verifier.clerk_build_notice_digests(ledger, errors)
        self.assertEqual(errors, [])
        self.assertEqual(digests["coinbase-eip712-isc-license.txt"], record["sha256"])

        for changes in (
            {"license": "MIT"}, {"parent_package": "unrelated"},
            {"archive_member": "package/LICENSE"}, {"filename": "../unreviewed.txt"},
        ):
            with self.subTest(changes=changes):
                review["coinbase_eip712_notice"] = record | changes
                errors.clear()
                self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
                self.assertTrue(errors)

        del review["coinbase_eip712_notice"]
        errors.clear()
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
        self.assertTrue(errors)
        # The exact public index digest from the predecessor.
        review["packages"] = [
            row for row in review["packages"]
            if row["package"] not in verifier.CLERK_RECENT_UI_NOTICES | verifier.CLERK_RUNTIME_NOTICE_ADDITIONS
        ]
        review["index_sha256"] = "c90bc786b1677435c38f76bea3fb3956e4062958460710eedb8e6e5617fee6a4"  # pragma: allowlist secret
        errors.clear()
        old = verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True)
        self.assertEqual(errors, [])
        self.assertNotIn("coinbase-eip712-isc-license.txt", old)
        self.assertIn("stripe-sdk-license.txt", old)
        review["coinbase_eip712_notice"] = record
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
        self.assertTrue(errors)
        errors.clear()
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors), {})
        self.assertTrue(errors)

    def test_clerk_notice_inventory_requires_qr_generator_and_limits_previous_index(self):
        verifier = load_verifier()
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        review = ledger["clerk_build_notices"]
        qr = next(row for row in review["packages"] if row["package"] == "qrcode.react")
        generator = qr.pop("generator_notice")

        errors: list[str] = []
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors), {})
        self.assertIn("QR Code Generator MIT notice", errors[0])
        qr["generator_notice"] = generator | {"source_path": "LICENSE"}
        errors.clear()
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors), {})
        self.assertIn("QR Code Generator MIT notice", errors[0])
        qr["generator_notice"] = generator
        errors.clear()
        current = verifier.clerk_build_notice_digests(ledger, errors)
        self.assertEqual(errors, [])
        self.assertEqual(current[generator["filename"]], generator["sha256"])

        review["index_sha256"] = verifier.CLERK_EIP712_NOTICE_INDEX
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
        self.assertIn("exact reviewed packages", errors[0])
        review["packages"] = [
            row for row in review["packages"]
            if row["package"] not in verifier.CLERK_RECENT_UI_NOTICES | verifier.CLERK_RUNTIME_NOTICE_ADDITIONS
        ]
        errors.clear()
        historical = verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True)
        self.assertEqual(errors, [])
        self.assertEqual(set(current) - set(historical), {
            "input-otp-1.4.2-license.txt", "copy-to-clipboard-3.3.3-license.txt",
            "qrcode-react-4.2.0-license.txt", "qrcode-generator-license.txt",
            "core-js-3.47.0-license.txt", "crypto-js-4.2.0-license.txt",
            "floating-ui-react-0.27.20-license.txt", "emotion-license.txt",
        })
        self.assertIn("coinbase-eip712-isc-license.txt", historical)
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors), {})
        self.assertIn("requires the current notice index", errors[0])

    def test_clerk_historical_ui_index_keeps_its_exact_qr_and_coinbase_notices(self):
        verifier = load_verifier()
        ledger = json.loads(verifier.DEFAULT_LEDGER.read_text(encoding="utf-8"))
        review = ledger["clerk_build_notices"]
        packages = review["packages"]
        errors = []
        current = verifier.clerk_build_notice_digests(ledger, errors)
        self.assertEqual(errors, [])
        review["index_sha256"] = verifier.CLERK_RECENT_UI_NOTICE_INDEX
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
        self.assertIn("exact reviewed packages", errors[0])
        review["packages"] = [row for row in packages if row["package"] not in verifier.CLERK_RUNTIME_NOTICE_ADDITIONS]
        errors.clear()
        historical = verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True)
        self.assertEqual(errors, [])
        self.assertEqual(set(current) - set(historical), {
            "core-js-3.47.0-license.txt", "crypto-js-4.2.0-license.txt",
            "floating-ui-react-0.27.20-license.txt", "emotion-license.txt",
        })
        self.assertTrue({"coinbase-eip712-isc-license.txt", "qrcode-generator-license.txt"} <= historical.keys())
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors), {})
        self.assertIn("requires the current notice index", errors[0])
        qr = next(row for row in review["packages"] if row["package"] == "qrcode.react")
        del qr["generator_notice"]
        errors.clear()
        self.assertEqual(verifier.clerk_build_notice_digests(ledger, errors, allow_previous_index=True), {})
        self.assertIn("QR Code Generator MIT notice", errors[0])

    def test_reviewed_static_inventory_rejects_extra_or_changed_files(self):
        ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
        cases = {
            "unreviewed.js.map": "Unreviewed static asset entries",
            "vendor/leaflet/extra.js": "complete vendor directory",
            "vendor/tabler-icons/extra.svg": "complete vendor manifest",
            "vendor/leaflet/images/extra/file.txt": "Unreviewed static vendor directory",
            ".assetsignore": "asset ignore policy hash changed",
            "workdoe-share.png": "Reviewed raster asset hash changed",
            "dmv-area-50fe6cd3.geojson": "public map data artifact hash changed",
            "map.js": "map controller integrity pin differs",
        }
        for name, diagnostic in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                verifier = load_verifier()
                verifier.REPO_ROOT = Path(directory)
                static = verifier.REPO_ROOT / "workdoe/static"
                shutil.copytree(ROOT / "workdoe/static", static)
                for filename in ("workdoe/service_taxonomy.py", "cloudflare/worker/service_taxonomy.py"):
                    dest = verifier.REPO_ROOT / filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / filename, dest)
                changed = static / name
                changed.parent.mkdir(parents=True, exist_ok=True)
                changed.write_bytes(b"synthetic unexpected bytes")
                errors = []
                if verifier.validate_static_root(ledger, errors):
                    verifier.validate_browser_components(ledger, errors)
                    verifier.validate_public_map_data(ledger, errors)
                self.assertTrue(any(diagnostic in error for error in errors), errors)


    def test_browser_advisory_check_is_opt_in_and_sends_only_reviewed_pins(self):
        verifier = load_verifier()
        with patch.object(verifier.http.client, "HTTPSConnection") as connect:
            self.assertEqual(verifier.verify(verifier.DEFAULT_LEDGER), [])
            connect.assert_not_called()
            response = connect.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b"{}"
            self.assertEqual(verifier.verify(verifier.DEFAULT_LEDGER, verify_browser_advisories=True), [])
        connect.assert_called_once_with("registry.npmjs.org", timeout=15)
        request = connect.return_value.request.call_args
        self.assertEqual(request.args, ("POST", "/-/npm/v1/security/advisories/bulk"))
        self.assertEqual(request.kwargs["headers"], {"Content-Type": "application/json"})
        self.assertEqual(json.loads(request.kwargs["body"]), {
            "leaflet": ["1.9.4"], "leaflet.markercluster": ["1.5.3"], "@tabler/icons": ["3.46.0"],
            "@clerk/ui": ["1.41.2"], "@clerk/clerk-js": ["6.40.1"],
            "react": ["18.3.1"], "react-dom": ["18.3.1"], "scheduler": ["0.23.2"],
            "@base-org/account": ["2.0.1"], "@coinbase/wallet-sdk": ["4.3.7"],
            "browser-tabs-lock": ["1.3.0"], "@tanstack/query-core": ["5.102.8"],
            "@formkit/auto-animate": ["0.8.4"], "@stripe/stripe-js": ["5.6.0"],
            "@stripe/react-stripe-js": ["3.1.1"], "@zxcvbn-ts/core": ["3.0.4"],
            "@zxcvbn-ts/language-common": ["3.0.4"],
            "input-otp": ["1.4.2"], "copy-to-clipboard": ["3.3.3"],
            "qrcode.react": ["4.2.0"], "toggle-selection": ["1.0.6"],
            "core-js": ["3.47.0"], "crypto-js": ["4.2.0"], "@floating-ui/react": ["0.27.20"],
            "@emotion/react": ["11.11.1"], "@emotion/cache": ["11.11.0"], "@wallet-standard/app": ["1.1.0"],
        })
        response.read.assert_called_once_with(verifier.MAX_NPM_ADVISORY_BYTES + 1)
        connect.return_value.close.assert_called_once()

    def test_browser_advisory_check_does_not_report_failure_or_matches_as_clear(self):
        verifier = load_verifier()
        marker = "untrusted-advisory-metadata-not-for-output"
        for status, body, expected in (
            (302, b"{}", "HTTP 302"),
            (503, b"{}", "HTTP 503"),
            (200, b"not JSON", "invalid JSON"),
            (200, b" " * (verifier.MAX_NPM_ADVISORY_BYTES + 1), "size limit"),
            (200, b"[]", "report shape"),
            (200, b'{"not-requested": []}', "report shape"),
            (200, b'{"leaflet": null}', "report shape"),
            (200, b'{"leaflet": [{"id": 1}], "leaflet": []}', "invalid JSON"),
            (200, json.dumps({"@clerk/clerk-js": [{"title": marker}]}).encode(), "@clerk/clerk-js@6.40.1"),
            (200, json.dumps({"browser-tabs-lock": [{"title": marker}]}).encode(), "browser-tabs-lock@1.3.0"),
        ):
            with self.subTest(status=status, expected=expected), patch.object(verifier.http.client, "HTTPSConnection") as connect:
                response = connect.return_value.getresponse.return_value
                response.status = status
                response.read.return_value = body
                errors = verifier.verify(verifier.DEFAULT_LEDGER, verify_browser_advisories=True)
                self.assertEqual(len(errors), 1)
                self.assertIn(expected, errors[0])
                self.assertNotIn(marker, errors[0])

    def test_release_advisory_check_covers_complete_tooling_and_known_browser_pins(self):
        verifier = load_verifier()
        pins = verifier.release_tooling_pins()
        self.assertEqual(sum(ecosystem == "npm" for ecosystem, _, _ in pins), 91)
        self.assertEqual(sum(ecosystem == "PyPI" for ecosystem, _, _ in pins), 40)
        self.assertIn(("npm", "wrangler", "4.152.0"), pins)
        self.assertIn(("PyPI", "pip-audit", "2.9.0"), pins)
        self.assertTrue(any(ecosystem == "PyPI" and name == "colorama" for ecosystem, name, _ in pins))
        with patch.object(verifier.http.client, "HTTPSConnection") as connect:
            connect.return_value.getresponse.return_value.status = 200
            connect.return_value.getresponse.return_value.read.side_effect = (
                b"{}", json.dumps({"results": [{} for _ in pins]}).encode(),
            )
            self.assertEqual(verifier.verify(verifier.DEFAULT_LEDGER, verify_release_advisories=True), [])
        self.assertEqual([call.args[0] for call in connect.call_args_list], ["registry.npmjs.org", "api.osv.dev"])
        request = connect.return_value.request.call_args
        self.assertEqual(request.args, ("POST", "/v1/querybatch"))
        self.assertEqual(request.kwargs["headers"], {"Content-Type": "application/json", "Accept": "application/json"})
        self.assertEqual(json.loads(request.kwargs["body"]), {"queries": [
            {"package": {"ecosystem": ecosystem, "name": name}, "version": version} for ecosystem, name, version in pins
        ]})
        connect.return_value.getresponse.return_value.read.assert_called_with(verifier.MAX_TOOLING_ADVISORY_BYTES + 1)

    def test_release_advisories_fail_closed_on_partial_or_untrusted_tooling_results(self):
        verifier = load_verifier()
        pins = [("PyPI", "jinja2", "3.1.4"), ("npm", "wrangler", "4.152.0")]
        for status, body, diagnostic in (
            (302, b"{}", "HTTP 302"),
            (503, b"{}", "HTTP 503"),
            (200, b" " * (verifier.MAX_TOOLING_ADVISORY_BYTES + 1), "size limit"),
            (200, b'{"results": [{}, {}], "results": []}', "invalid JSON"),
            (200, b'{"results": [{}]}', "one result per reviewed pin"),
            (200, b'{"results": [{}, {"next_page_token": "opaque"}]}', "incomplete result"),
            (200, b'{"results": [{"vulns": [{"id": "private diagnostic"}]}, {}]}', "invalid advisory records"),
            (200, b'{"results": [{}, {"vulns": [{"id": "GHSA-1234-5678-9012"}]}]}',
             "npm wrangler@4.152.0: GHSA-1234-5678-9012"),
        ):
            with (
                self.subTest(diagnostic=diagnostic),
                patch.object(verifier, "release_tooling_pins", return_value=pins),
                patch.object(verifier.http.client, "HTTPSConnection") as connect,
            ):
                response = connect.return_value.getresponse.return_value
                response.status = status
                response.read.return_value = body
                errors = []
                verifier.validate_tooling_advisories(errors)
                self.assertEqual(len(errors), 1)
                self.assertIn(diagnostic, errors[0])
                self.assertNotIn("private diagnostic", errors[0])
                connect.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
