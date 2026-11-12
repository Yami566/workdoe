"""Compare reviewed Clerk browser files to pinned npm archives, without a session."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import http.client
import io
import json
import tarfile
import time
import zlib
from collections.abc import Iterator
from dataclasses import dataclass

from verify_dependency_provenance import (
    DEFAULT_LEDGER,
    MAX_CLERK_BROWSER_PIN_BYTES,
    NPM_SHA512_PATTERN,
    PINNED_CLERK_BROWSER_COMPONENTS,
    load_clerk_browser_inventory,
    load_clerk_browser_pins,
    records_by_key,
    validate_clerk_browser_filenames,
    validate_clerk_browser_pins,
    verify,
)

ARCHIVE_HOST = "registry.npmjs.org"
SERVING_HOST = "workdoe.com"
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_EXPANDED_BYTES = 32 * 1024 * 1024
MAX_FILE_BYTES = MAX_CLERK_BROWSER_PIN_BYTES
REQUEST_TIMEOUT_SECONDS = 15
PROXY_REQUEST_INTERVAL_SECONDS = 0.15
PROXY_COMPARISON_BUDGET_SECONDS = 180


class DeliveryCheckError(ValueError):
    pass


@dataclass(frozen=True)
class FilePin:
    size: int
    sha256: str


def fetch_identity_bytes(connection: http.client.HTTPSConnection, path: str, limit: int) -> bytes:
    try:
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        with connection.getresponse() as response:
            if response.status != 200:
                raise DeliveryCheckError(f"{path}: unexpected HTTP {response.status}")
            if response.getheader("Content-Encoding", "").strip().lower() not in {"", "identity"}:
                raise DeliveryCheckError(f"{path}: unexpected content encoding")
            content = response.read(limit + 1)
    except (OSError, http.client.HTTPException) as exc:
        raise DeliveryCheckError(f"{path}: transport failed") from exc
    if not 0 < len(content) <= limit:
        raise DeliveryCheckError(f"{path}: response outside the byte limit")
    return content


def pinned_archive_members(
    raw: bytes, package_path: str, expected_integrity: str, member_limits: dict[str, int],
) -> Iterator[tuple[str, bytes]]:
    if not 0 < len(raw) <= MAX_ARCHIVE_BYTES:
        raise DeliveryCheckError(f"{package_path}: archive size or pinned SHA-512 differs")
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(raw).digest()).decode("ascii")
    if integrity != expected_integrity:
        raise DeliveryCheckError(f"{package_path}: archive size or pinned SHA-512 differs")
    seen: set[str] = set()
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
            expanded = compressed.read(MAX_EXPANDED_BYTES + 1)
        if len(expanded) > MAX_EXPANDED_BYTES:
            raise DeliveryCheckError(f"{package_path}: archive exceeds the expansion limit")
        with tarfile.open(fileobj=io.BytesIO(expanded), mode="r:") as archive:
            for member in archive:
                limit = member_limits.get(member.name)
                if limit is None:
                    continue
                if member.name in seen or not member.isreg() or not 0 < member.size <= limit:
                    raise DeliveryCheckError(f"{package_path}: duplicate, non-file, or oversized archive member")
                file = archive.extractfile(member)
                if file is None:
                    raise DeliveryCheckError(f"{package_path}: missing archive member data")
                with file:
                    content = file.read(member.size + 1)
                if len(content) != member.size:
                    raise DeliveryCheckError(f"{package_path}: archive member size differs")
                seen.add(member.name)
                yield member.name, content
    except (OSError, EOFError, tarfile.TarError, zlib.error) as exc:
        raise DeliveryCheckError(f"{package_path}: could not read the pinned archive") from exc
    if seen != member_limits.keys():
        raise DeliveryCheckError(f"{package_path}: reviewed files missing from the archive")


def archive_file_pins(
    raw: bytes, package_path: str, filenames: tuple[str, ...], component: dict,
) -> dict[str, FilePin]:
    expected = {f"package/dist/{name}": f"{package_path}/dist/{name}" for name in filenames}
    license_path = f"{package_path}/LICENSE"
    entry_path = component["script_path"]
    expected["package/LICENSE"] = license_path
    pins: dict[str, FilePin] = {}
    for member, content in pinned_archive_members(
        raw, package_path, component["package_integrity"], dict.fromkeys(expected, MAX_FILE_BYTES),
    ):
        path = expected[member]
        digest = hashlib.sha256(content).hexdigest()
        if path == license_path and digest != component["retained_license_sha256"]:
            raise DeliveryCheckError(f"{path}: retained license hash differs")
        if path == entry_path:
            sri = "sha384-" + base64.b64encode(hashlib.sha384(content).digest()).decode("ascii")
            if sri != component["script_integrity"]:
                raise DeliveryCheckError(f"{path}: entry script integrity differs")
        pins[path] = FilePin(len(content), digest)
    if entry_path not in pins:
        raise DeliveryCheckError(f"{package_path}: reviewed files missing from the archive")
    return pins


def reviewed_file_pins() -> dict[str, FilePin]:
    errors = verify(DEFAULT_LEDGER)
    if errors:
        raise DeliveryCheckError("Local provenance failed; no remote requests made: " + "; ".join(errors))
    return pinned_archive_files(
        json.loads(DEFAULT_LEDGER.read_text(encoding="utf-8")), load_clerk_browser_inventory(),
        runtime_pins=load_clerk_browser_pins(),
    )


def pinned_archive_files(ledger: dict, inventory: dict, *, runtime_pins: dict | None = None) -> dict[str, FilePin]:
    errors: list[str] = []
    components = records_by_key(ledger.get("hosted_browser_components"), "name", "Hosted browser inventory", errors)
    if errors or components.keys() != PINNED_CLERK_BROWSER_COMPONENTS.keys() or any(
        any(components[name].get(key) != value for key, value in expected.items())
        or not NPM_SHA512_PATTERN.fullmatch(str(components[name].get("package_integrity", "")))
        for name, expected in PINNED_CLERK_BROWSER_COMPONENTS.items()
    ):
        raise DeliveryCheckError("The ledger does not identify the reviewed Clerk packages and archive hashes.")
    validate_clerk_browser_filenames(components, errors, inventory=inventory)
    if errors:
        raise DeliveryCheckError("The reviewed Clerk file list does not match its recorded counts and hashes.")
    if runtime_pins is not None:
        validate_clerk_browser_pins(ledger, inventory, runtime_pins)
    pins: dict[str, FilePin] = {}
    connection = http.client.HTTPSConnection(ARCHIVE_HOST, timeout=REQUEST_TIMEOUT_SECONDS)
    try:
        for component in components.values():
            name, version = component["package"], component["version"]
            package_path = f"/npm/{name}@{version}"
            archive_path = f"/{name}/-/{name.rsplit('/', 1)[1]}-{version}.tgz"
            raw = fetch_identity_bytes(connection, archive_path, MAX_ARCHIVE_BYTES)
            pins.update(archive_file_pins(raw, package_path, inventory[package_path], component))
    finally:
        connection.close()
    if runtime_pins is not None and {path: (pin.size, pin.sha256) for path, pin in pins.items()} != runtime_pins:
        raise DeliveryCheckError("The Worker Clerk byte pins differ from the reviewed npm archives.")
    return pins


def compare_live_files(pins: dict[str, FilePin]) -> int:
    connection = http.client.HTTPSConnection(SERVING_HOST, timeout=REQUEST_TIMEOUT_SECONDS)
    deadline = time.monotonic() + PROXY_COMPARISON_BUDGET_SECONDS
    checked = 0
    try:
        for path, pin in sorted(pins.items()):
            try:
                if time.monotonic() >= deadline:
                    raise DeliveryCheckError("The comparison exceeded its time budget.")
                content = fetch_identity_bytes(connection, "/__clerk" + path, pin.size)
                if time.monotonic() >= deadline:
                    raise DeliveryCheckError("The comparison exceeded its time budget.")
                if len(content) != pin.size or hashlib.sha256(content).hexdigest() != pin.sha256:
                    raise DeliveryCheckError(f"{path}: serving bytes differ from the pinned archive")
            except DeliveryCheckError as exc:
                raise DeliveryCheckError(f"Stopped after {checked} verified proxy files: {exc}") from exc
            checked += 1
            if checked < len(pins):
                time.sleep(PROXY_REQUEST_INTERVAL_SECONDS)
    finally:
        connection.close()
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compare-live", action="store_true",
        help="Also compare the reviewed public file paths on workdoe.com, sequentially and anonymously.",
    )
    args = parser.parse_args()
    try:
        pins = reviewed_file_pins()
        print(f"Pinned npm archives: {len(pins)} reviewed files, {sum(pin.size for pin in pins.values())} bytes.")
        if args.compare_live:
            checked = compare_live_files(pins)
            print(f"Public proxy: {checked} files match the pinned archives byte for byte.")
    except (OSError, ValueError, KeyError, SyntaxError, TypeError) as exc:
        parser.exit(1, f"Clerk delivery check failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
