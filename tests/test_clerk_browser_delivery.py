from __future__ import annotations

import base64
import hashlib
import importlib
import io
import json
import sys
import tarfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1] / "scripts"), *sys.path]):
    delivery = importlib.import_module("verify_clerk_browser_delivery")
    notices = importlib.import_module("verify_clerk_notice_sources")

PACKAGE = "/npm/@clerk/example@1.2.3"
LICENSE = b"Synthetic notice\n"
ENTRY = b"window.synthetic = true;\n"
CHUNK = b"window.syntheticChunk = true;\n"
MEMBERS = [
    ("package/LICENSE", LICENSE),
    ("package/dist/browser.js", ENTRY),
    ("package/dist/lazy.js", CHUNK),
    ("package/dist/server.js", b"excluded fixture"),
]


def digest_sri(content: bytes, algorithm: str) -> str:
    return algorithm + "-" + base64.b64encode(hashlib.new(algorithm, content).digest()).decode("ascii")


def fixture_archive(members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in members:
            member = tarfile.TarInfo(name)
            if content is None:
                member.type = tarfile.SYMTYPE
                member.linkname = "server.js"
                archive.addfile(member)
            else:
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
    raw = buffer.getvalue()
    return raw, {
        "package_integrity": digest_sri(raw, "sha512"),
        "retained_license_sha256": hashlib.sha256(LICENSE).hexdigest(),
        "script_integrity": digest_sri(ENTRY, "sha384"),
        "script_path": f"{PACKAGE}/dist/browser.js",
    }


class ClerkNoticeSourceTests(unittest.TestCase):
    def test_rejects_bad_inventory_before_network(self):
        ledger = json.loads(notices.DEFAULT_LEDGER.read_text(encoding="utf-8"))
        ledger["clerk_build_notices"]["packages"].pop()
        with (
            patch.object(notices.http.client, "HTTPSConnection") as connection,
            self.assertRaisesRegex(delivery.DeliveryCheckError, "no upstream requests"),
        ):
            notices.verify_notice_sources(ledger)
        connection.assert_not_called()

    def test_archive_notice_verifies_manifest_and_exact_retained_text(self):
        name = "@coinbase/wallet-sdk"
        manifest = {"name": name, "version": "4.3.7", "license": "Apache-2.0"}
        parent = b"Synthetic parent notice\n"
        member = "package/embedded/LICENSE"
        nested = b"Synthetic nested notice\n"
        coinbase = {"parent_package": name, "archive_member": member, "filename": "nested.txt",
                    "sha256": hashlib.sha256(nested).hexdigest()}
        registry, sources = Mock(), Mock()
        for manifest_bytes, nested_bytes, error in (
            (json.dumps(manifest).encode(), nested, None),
            (json.dumps(manifest | {"version": "4.3.8"}).encode(), nested, "does not match the reviewed manifest"),
            (b'{"name":"ambiguous","name":"@coinbase/wallet-sdk"}', nested, "invalid or ambiguous"),
            (json.dumps(manifest).encode(), b"Changed nested notice\n", "retained copy: nested.txt"),
        ):
            with self.subTest(error=error):
                raw, component = fixture_archive([
                    ("package/package.json", manifest_bytes), ("package/LICENSE", parent.replace(b"\n", b"\r\n")),
                    (member, nested_bytes),
                ])
                pin = {"package": name, "version": manifest["version"], "license": manifest["license"],
                       "package_integrity": component["package_integrity"], "filename": "parent.txt",
                       "sha256": hashlib.sha256(parent).hexdigest()}
                with patch.object(notices, "fetch_identity_bytes", return_value=raw) as fetch:
                    if error:
                        with self.assertRaisesRegex(delivery.DeliveryCheckError, error):
                            notices.verify_package_notices(registry, sources, pin, coinbase)
                    else:
                        self.assertEqual(notices.verify_package_notices(registry, sources, pin, coinbase), {
                            "parent.txt", "nested.txt",
                        })
                fetch.assert_called_once_with(registry, "/@coinbase/wallet-sdk/-/wallet-sdk-4.3.7.tgz", delivery.MAX_ARCHIVE_BYTES)

    def test_git_notice_fetch_requires_the_exact_registry_commit_and_archive(self):
        registry, sources = Mock(), Mock()
        pin = {"package": "input-otp", "version": "1.4.2", "license": "MIT", "package_integrity": "fixture-integrity",
               "filename": "input-otp-1.4.2-license.txt", "sha256": hashlib.sha256(LICENSE).hexdigest()}
        release = {"name": pin["package"], "version": pin["version"], "license": "MIT",
                   "gitHead": notices.INPUT_OTP_SOURCE, "dist": {"integrity": pin["package_integrity"]}}

        def verify():
            notices.verify_git_notice(
                registry, sources, pin, pin, repo="guilhermerodz/input-otp", commit=notices.INPUT_OTP_SOURCE, path="LICENSE",
            )

        for changed in ({"gitHead": "wrong"}, {"dist": {"integrity": "different archive"}}):
            with (
                self.subTest(changed=changed),
                patch.object(notices, "fetch_identity_bytes", return_value=json.dumps(release | changed).encode()) as fetch,
                self.assertRaisesRegex(delivery.DeliveryCheckError, "reviewed source commit and archive"),
            ):
                verify()
            fetch.assert_called_once_with(registry, "/input-otp/1.4.2", notices.MANIFEST_MAX_BYTES)
        with patch.object(notices, "fetch_identity_bytes", side_effect=[json.dumps(release).encode(), LICENSE]) as fetch:
            verify()
        self.assertEqual(fetch.call_args_list, [
            call(registry, "/input-otp/1.4.2", notices.MANIFEST_MAX_BYTES),
            call(sources, f"/guilhermerodz/input-otp/{notices.INPUT_OTP_SOURCE}/LICENSE", notices.NOTICE_MAX_BYTES),
        ])


class ClerkBrowserDeliveryTests(unittest.TestCase):
    def test_pins_only_reviewed_files_and_checks_entry_and_notice(self):
        raw, component = fixture_archive(MEMBERS)
        pins = delivery.archive_file_pins(raw, PACKAGE, ("browser.js", "lazy.js"), component)
        self.assertEqual(set(pins), {f"{PACKAGE}/{name}" for name in ("LICENSE", "dist/browser.js", "dist/lazy.js")})
        self.assertEqual(pins[f"{PACKAGE}/dist/lazy.js"], delivery.FilePin(len(CHUNK), hashlib.sha256(CHUNK).hexdigest()))
        for field, expected in (
            ("package_integrity", "pinned SHA-512"),
            ("script_integrity", "entry script integrity"),
            ("retained_license_sha256", "retained license hash"),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(delivery.DeliveryCheckError, expected):
                delivery.archive_file_pins(raw, PACKAGE, ("browser.js", "lazy.js"), component | {field: "bad"})

    def test_rejects_missing_duplicate_and_oversized_members(self):
        for members, message in (
            (MEMBERS[:2], "reviewed files missing"),
            (MEMBERS + [MEMBERS[2]], "duplicate"),
            (MEMBERS[:2] + [("package/dist/lazy.js", None)], "non-file"),
            (MEMBERS[:2] + [("package/dist/lazy.js", b"x" * (delivery.MAX_FILE_BYTES + 1))], "oversized"),
        ):
            with self.subTest(message=message):
                raw, component = fixture_archive(members)
                with self.assertRaisesRegex(delivery.DeliveryCheckError, message):
                    delivery.archive_file_pins(raw, PACKAGE, ("browser.js", "lazy.js"), component)
        raw, component = fixture_archive(MEMBERS)
        with (
            patch.object(delivery, "MAX_EXPANDED_BYTES", 1),
            self.assertRaisesRegex(delivery.DeliveryCheckError, "expansion limit"),
        ):
            delivery.archive_file_pins(raw, PACKAGE, ("browser.js", "lazy.js"), component)

    def test_response_does_not_follow_redirect_or_accept_encoding_or_unbounded_bytes(self):
        for status, encoding, body, message in (
            (302, "", b"x", "HTTP 302"),
            (429, "", b"x", "HTTP 429"),
            (200, "gzip", b"x", "content encoding"),
            (200, "", b"xx", "byte limit"),
        ):
            with self.subTest(status=status, encoding=encoding):
                response = Mock(status=status, getheader=Mock(return_value=encoding), read=Mock(return_value=body))
                connection = Mock()
                connection.getresponse.return_value.__enter__ = Mock(return_value=response)
                connection.getresponse.return_value.__exit__ = Mock(return_value=False)
                with self.assertRaisesRegex(delivery.DeliveryCheckError, message):
                    delivery.fetch_identity_bytes(connection, "/fixture", 1)
                connection.request.assert_called_once_with("GET", "/fixture", headers={"Accept-Encoding": "identity"})
                if status != 200 or encoding:
                    response.read.assert_not_called()
                else:
                    response.read.assert_called_once_with(2)

    def test_live_comparison_stops_on_same_size_tampering(self):
        path = f"{PACKAGE}/dist/browser.js"
        pin = delivery.FilePin(len(ENTRY), hashlib.sha256(ENTRY).hexdigest())
        pins = {path: pin, f"{PACKAGE}/dist/lazy.js": pin}
        with (
            patch.object(delivery.http.client, "HTTPSConnection") as connection,
            patch.object(delivery, "fetch_identity_bytes", return_value=b"x" * len(ENTRY)) as fetch,
            patch.object(delivery.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(delivery.DeliveryCheckError, "after 0 verified proxy files"):
                delivery.compare_live_files(pins)
            connection.assert_called_once_with("workdoe.com", timeout=delivery.REQUEST_TIMEOUT_SECONDS)
            fetch.assert_called_once_with(connection.return_value, "/__clerk" + path, len(ENTRY))
            connection.return_value.close.assert_called_once()
            sleep.assert_not_called()
            fetch.reset_mock()
            fetch.return_value = ENTRY
            self.assertEqual(delivery.compare_live_files(pins), 2)
            self.assertEqual(fetch.call_args_list, [
                call(connection.return_value, "/__clerk" + route, pin.size) for route in sorted(pins)
            ])
            sleep.assert_called_once_with(delivery.PROXY_REQUEST_INTERVAL_SECONDS)

    def test_live_request_is_opt_in_and_bad_local_provenance_never_calls_npm(self):
        with (
            patch.object(delivery, "verify", return_value=["fixture mismatch"]),
            patch.object(delivery.http.client, "HTTPSConnection") as connection,
        ):
            with self.assertRaisesRegex(delivery.DeliveryCheckError, "no remote requests"):
                delivery.reviewed_file_pins()
            connection.assert_not_called()
        with (
            patch.object(sys, "argv", ["verify_clerk_browser_delivery.py"]),
            patch.object(delivery, "reviewed_file_pins", return_value={}),
            patch.object(delivery, "compare_live_files") as live,
            patch("builtins.print"),
        ):
            self.assertEqual(delivery.main(), 0)
            live.assert_not_called()

    def test_commit_inventory_drift_stops_before_requesting_archives(self):
        ledger = json.loads(delivery.DEFAULT_LEDGER.read_text(encoding="utf-8"))
        inventory = delivery.load_clerk_browser_inventory()
        package = next(iter(inventory))
        with patch.object(delivery.http.client, "HTTPSConnection") as connection:
            with self.assertRaisesRegex(delivery.DeliveryCheckError, "file list"):
                delivery.pinned_archive_files(ledger, inventory | {package: inventory[package][:-1]})
            ledger["hosted_browser_components"][0]["package"] = "@clerk/unreviewed"
            with self.assertRaisesRegex(delivery.DeliveryCheckError, "reviewed Clerk packages"):
                delivery.pinned_archive_files(ledger, inventory)
            connection.assert_not_called()

    def test_runtime_byte_pin_drift_stops_before_requesting_archives(self):
        ledger = json.loads(delivery.DEFAULT_LEDGER.read_text(encoding="utf-8"))
        inventory = delivery.load_clerk_browser_inventory()
        pins = delivery.load_clerk_browser_pins()
        path = next(iter(pins))
        with patch.object(delivery.http.client, "HTTPSConnection") as connection:
            with self.assertRaisesRegex(ValueError, "provenance ledger"):
                delivery.pinned_archive_files(ledger, inventory, runtime_pins=pins | {path: (pins[path][0], "0" * 64)})
            pins.pop(path)
            with self.assertRaisesRegex(ValueError, "reviewed file inventory"):
                delivery.pinned_archive_files(ledger, inventory, runtime_pins=pins)
            connection.assert_not_called()

    def test_comparison_budget_stops_additional_requests(self):
        path = f"{PACKAGE}/dist/browser.js"
        pin = delivery.FilePin(len(ENTRY), hashlib.sha256(ENTRY).hexdigest())
        with (
            patch.object(delivery.http.client, "HTTPSConnection"),
            patch.object(delivery, "fetch_identity_bytes", return_value=ENTRY) as fetch,
            patch.object(delivery.time, "monotonic", side_effect=[0, 1, 2, 181]),
            patch.object(delivery.time, "sleep"),
            self.assertRaisesRegex(delivery.DeliveryCheckError, "after 1 verified proxy files.*time budget"),
        ):
            delivery.compare_live_files({path: pin, f"{PACKAGE}/dist/lazy.js": pin})
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
