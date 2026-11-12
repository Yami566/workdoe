"""Verify retained Clerk build notices against reviewed upstream sources, without installing packages."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
from contextlib import closing

from verify_clerk_browser_delivery import (
    ARCHIVE_HOST,
    MAX_ARCHIVE_BYTES,
    REQUEST_TIMEOUT_SECONDS,
    DeliveryCheckError,
    fetch_identity_bytes,
    pinned_archive_members,
)
from verify_dependency_provenance import (
    CLERK_NOTICE_INDEX,
    DEFAULT_LEDGER,
    clerk_build_notice_digests,
    unique_json_keys,
    verify,
)

SOURCE_HOST = "raw.githubusercontent.com"
NOTICE_MAX_BYTES = 32 * 1024
MANIFEST_MAX_BYTES = 256 * 1024
INPUT_OTP_SOURCE = "81ccdb48c010d800b24942aa231909f0c971b1ca"  # pragma: allowlist secret - reviewed upstream Git commit.
LICENSE_TXT_PACKAGES = {"@zxcvbn-ts/core", "@zxcvbn-ts/language-common"}


def exact_release_manifest(raw: bytes, pin: dict) -> dict:
    try:
        manifest = json.loads(raw, object_pairs_hook=unique_json_keys)
    except (ValueError, RecursionError) as exc:
        raise DeliveryCheckError("A reviewed package manifest was invalid or ambiguous.") from exc
    if not isinstance(manifest, dict) or any(
        manifest.get(field) != pin[key] for field, key in (("name", "package"), ("version", "version"), ("license", "license"))
    ):
        raise DeliveryCheckError("The package name, version, or license does not match the reviewed manifest.")
    return manifest


def verify_notice_digest(content: bytes, notice: dict) -> None:
    digest = hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()
    if digest != notice["sha256"]:
        raise DeliveryCheckError(f"Upstream notice does not match the retained copy: {notice['filename']}")


def verify_git_notice(
    registry: http.client.HTTPSConnection, sources: http.client.HTTPSConnection,
    pin: dict, notice: dict, *, repo: str, commit: str, path: str,
) -> None:
    release = exact_release_manifest(fetch_identity_bytes(
        registry, f"/{pin['package']}/{pin['version']}", MANIFEST_MAX_BYTES,
    ), pin)
    dist = release.get("dist")
    if release.get("gitHead") != commit or not isinstance(dist, dict) or dist.get("integrity") != pin["package_integrity"]:
        raise DeliveryCheckError(f"npm does not tie {pin['package']} to the reviewed source commit and archive.")
    content = fetch_identity_bytes(sources, f"/{repo}/{commit}/{path}", NOTICE_MAX_BYTES)
    verify_notice_digest(content, notice)


def verify_package_notices(
    registry: http.client.HTTPSConnection, sources: http.client.HTTPSConnection,
    pin: dict, coinbase_notice: dict,
) -> set[str]:
    name, version = pin["package"], pin["version"]
    archive_path = f"/{name}/-/{name.rsplit('/', 1)[-1]}-{version}.tgz"
    raw = fetch_identity_bytes(registry, archive_path, MAX_ARCHIVE_BYTES)
    license_member = "package/LICENSE.txt" if name in LICENSE_TXT_PACKAGES else "package/LICENSE"
    requested = {"package/package.json": MANIFEST_MAX_BYTES}
    if name != "input-otp":
        requested[license_member] = NOTICE_MAX_BYTES
    if name == coinbase_notice["parent_package"]:
        requested[coinbase_notice["archive_member"]] = NOTICE_MAX_BYTES
    entries = dict(pinned_archive_members(raw, f"{name}@{version}", pin["package_integrity"], requested))
    exact_release_manifest(entries["package/package.json"], pin)

    verified = {pin["filename"]}
    if name == "input-otp":
        verify_git_notice(registry, sources, pin, pin, repo="guilhermerodz/input-otp", commit=INPUT_OTP_SOURCE, path="LICENSE")
    else:
        verify_notice_digest(entries[license_member], pin)
    if name == coinbase_notice["parent_package"]:
        verify_notice_digest(entries[coinbase_notice["archive_member"]], coinbase_notice)
        verified.add(coinbase_notice["filename"])
    if name == "qrcode.react":
        generator = pin["generator_notice"]
        verify_git_notice(
            registry, sources, pin, generator, repo="zpao/qrcode.react",
            commit=generator["source_commit"], path=generator["source_path"],
        )
        verified.add(generator["filename"])
    return verified


def verify_notice_sources(ledger: dict) -> tuple[int, int]:
    errors: list[str] = []
    digests = clerk_build_notice_digests(ledger, errors)
    if errors or not digests:
        raise DeliveryCheckError("No valid current Clerk notice inventory; no upstream requests were made.")
    review = ledger["clerk_build_notices"]
    verified: set[str] = set()
    with (
        closing(http.client.HTTPSConnection(ARCHIVE_HOST, timeout=REQUEST_TIMEOUT_SECONDS)) as registry,
        closing(http.client.HTTPSConnection(SOURCE_HOST, timeout=REQUEST_TIMEOUT_SECONDS)) as sources,
    ):
        for pin in review["packages"]:
            verified.update(verify_package_notices(registry, sources, pin, review["coinbase_eip712_notice"]))
    if verified != digests.keys() - {CLERK_NOTICE_INDEX}:
        raise DeliveryCheckError("The upstream verification did not cover every retained license file.")
    return len(review["packages"]), len(verified)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", action="store_true", required=True, help="Read public npm and GitHub artifacts over HTTPS.")
    parser.parse_args()
    try:
        errors = verify(DEFAULT_LEDGER)
        if errors:
            raise DeliveryCheckError("Local provenance failed; no upstream requests were made: " + "; ".join(errors))
        packages, files = verify_notice_sources(json.loads(DEFAULT_LEDGER.read_text(encoding="utf-8")))
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as exc:
        parser.exit(1, f"Clerk notice source check failed: {exc}\n")
    print(f"Verified {packages} pinned npm package archives and the sources of {files} retained license files.")
    print("Scope: reviewed notice sources only; not a complete compiled Clerk license or advisory clearance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
