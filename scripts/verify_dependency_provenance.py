from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import sys
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO_ROOT / "DEPENDENCY_PROVENANCE.json"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TEXT_ARTIFACT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonc",
    ".md",
    ".py",
    ".sql",
    ".svg",
}
TEXT_ARTIFACT_NAMES = {"copying", "license", "notice"}
REPOSITORY_HASH_POLICY = {
    "binary": "sha256-bytes",
    "text": "sha256-lf",
}
PINNED_CLERK_BROWSER_COMPONENTS = {
    "Clerk UI": {
        "package": "@clerk/ui",
        "version": "1.41.2",
        "license": "MIT",
        "script_path": "/npm/@clerk/ui@1.41.2/dist/ui.browser.js",
    },
    "ClerkJS": {
        "package": "@clerk/clerk-js",
        "version": "6.40.1",
        "license": "MIT",
        "script_path": "/npm/@clerk/clerk-js@6.40.1/dist/clerk.browser.js",
    },
}
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def sha256_file(path: Path) -> str:
    content = path.read_bytes()
    if (
        path.suffix.casefold() in TEXT_ARTIFACT_SUFFIXES
        or path.name.casefold() in TEXT_ARTIFACT_NAMES
    ):
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def parse_requirements(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line or line.count("==") != 1:
            raise ValueError(f"{path.name}:{line_number} must use one exact == pin")
        name, version = (part.strip() for part in line.split("==", 1))
        if not name or not version:
            raise ValueError(f"{path.name}:{line_number} contains an invalid pin")
        key = name.casefold()
        if key in packages:
            raise ValueError(f"{path.name}:{line_number} duplicates {name}")
        packages[key] = version
    return packages


def validate_python_groups(payload: dict, errors: list[str]) -> None:
    for group in payload.get("python_groups", []):
        relative_path = group.get("requirements_file", "")
        requirements_path = REPO_ROOT / relative_path
        try:
            pinned = parse_requirements(requirements_path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue

        recorded: dict[str, str] = {}
        for package in group.get("packages", []):
            name = str(package.get("name", ""))
            version = str(package.get("version", ""))
            recorded[name.casefold()] = version
            digest = str(package.get("sha256", ""))
            if not SHA256_PATTERN.fullmatch(digest):
                errors.append(f"{name} {version} has an invalid upstream SHA-256")
            if not str(package.get("official_source", "")).startswith("https://"):
                errors.append(f"{name} {version} lacks an HTTPS official source")
            if not package.get("license") or not package.get("artifact"):
                errors.append(f"{name} {version} lacks license or artifact metadata")

        if pinned != recorded:
            errors.append(
                f"{relative_path} pins do not exactly match the provenance ledger: "
                f"requirements={pinned!r}, ledger={recorded!r}"
            )


def validate_node_tooling(payload: dict, errors: list[str]) -> None:
    try:
        package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Node package metadata is unreadable: {exc}")
        return

    for dependency in payload.get("node_tooling", []):
        name = str(dependency.get("name", ""))
        version = str(dependency.get("version", ""))
        declared = package.get("devDependencies", {}).get(name)
        locked = package_lock.get("packages", {}).get(f"node_modules/{name}", {})
        if declared != version:
            errors.append(f"package.json pins {name} at {declared!r}, expected {version!r}")
        if locked.get("version") != version:
            errors.append(f"package-lock.json pins {name} at {locked.get('version')!r}, expected {version!r}")
        if locked.get("integrity") != dependency.get("integrity"):
            errors.append(f"package-lock.json integrity for {name} does not match the ledger")


def validate_runtime_components(payload: dict, errors: list[str]) -> None:
    components = {
        component.get("name"): component for component in payload.get("runtime_components", [])
    }
    runtime = components.get("Cloudflare Python Workers runtime SDK")
    if not runtime:
        errors.append("The Cloudflare Python Workers runtime SDK provenance record is missing")
        return

    if runtime.get("delivery") != "bundled Cloudflare runtime component, not a repository dependency":
        errors.append("Cloudflare Python runtime SDK delivery model is not recorded accurately")
    if runtime.get("configuration") != "cloudflare/wrangler.jsonc":
        errors.append("Cloudflare Python runtime SDK config path is not recorded accurately")
    if runtime.get("external_sdk_bundled") is not False:
        errors.append("Cloudflare Python runtime SDK must not be recorded as a bundled repository dependency")
    if not str(runtime.get("official_source", "")).startswith("https://"):
        errors.append("Cloudflare Python runtime SDK lacks an HTTPS official source")
    if not runtime.get("terms_scope"):
        errors.append("Cloudflare Python runtime SDK lacks service-terms provenance")

    try:
        wrangler = json.loads(
            (REPO_ROOT / runtime["configuration"]).read_text(encoding="utf-8")
        )
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Cloudflare Python runtime SDK config is unreadable: {exc}")
        return

    required_flags = set(runtime.get("required_flags", []))
    actual_flags = set(wrangler.get("compatibility_flags", []))
    if required_flags != {"python_workers", "disable_python_external_sdk"}:
        errors.append("Cloudflare Python runtime SDK record has unexpected compatibility flags")
    if not required_flags.issubset(actual_flags):
        errors.append("Wrangler config does not preserve the bundled Python runtime SDK flags")
    if runtime.get("compatibility_date") != wrangler.get("compatibility_date"):
        errors.append("Cloudflare Python runtime SDK compatibility date does not match Wrangler config")

    entrypoint = REPO_ROOT / "cloudflare" / "worker" / "entry.py"
    try:
        entrypoint_source = entrypoint.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"Cloudflare Python Worker entrypoint is unreadable: {exc}")
        return
    if "from workers import " not in entrypoint_source:
        errors.append("Cloudflare Python Worker entrypoint no longer uses the recorded runtime SDK module")


def validate_browser_components(payload: dict, errors: list[str]) -> None:
    components = {component["name"]: component for component in payload.get("browser_components", [])}
    for component in components.values():
        license_path = REPO_ROOT / component.get("retained_license", "")
        expected_license_hash = component.get("retained_license_sha256", "")
        if not license_path.is_file():
            errors.append(f"Missing retained license: {license_path.relative_to(REPO_ROOT)}")
        elif sha256_file(license_path) != expected_license_hash:
            errors.append(f"Retained license hash changed: {license_path.relative_to(REPO_ROOT)}")
        for artifact in component.get("artifacts", []):
            artifact_path = REPO_ROOT / artifact.get("path", "")
            if not artifact_path.is_file():
                errors.append(f"Missing browser artifact: {artifact_path.relative_to(REPO_ROOT)}")
            elif sha256_file(artifact_path) != artifact.get("sha256"):
                errors.append(f"Browser artifact hash changed: {artifact_path.relative_to(REPO_ROOT)}")

    tabler = components.get("Tabler Icons")
    if not tabler:
        errors.append("The Tabler Icons provenance record is missing")
        return

    deer_path = REPO_ROOT / "workdoe" / "static" / "deer.svg"
    if sha256_file(deer_path) != tabler.get("deer_asset_sha256"):
        errors.append("Tabler-derived deer asset hash changed")

    pencil_path = (
        REPO_ROOT / "workdoe" / "static" / "vendor" / "tabler-icons" / "pencil.svg"
    )
    if not pencil_path.is_file():
        errors.append("The pinned Tabler pencil asset is missing")
    elif sha256_file(pencil_path) != tabler.get("pencil_asset_sha256"):
        errors.append("Tabler pencil asset hash changed")

    from workdoe.service_taxonomy import SERVICE_ICON_BY_SLUG

    icon_directory = REPO_ROOT / "workdoe" / "static" / "vendor" / "tabler-icons"
    icon_names = sorted(set(SERVICE_ICON_BY_SLUG.values()))
    manifest = "\n".join(
        f"{name} {sha256_file(icon_directory / name)}" for name in icon_names
    )
    manifest_hash = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    if len(icon_names) != tabler.get("service_icon_count"):
        errors.append("Tabler service icon count changed")
    if manifest_hash != tabler.get("service_icon_manifest_sha256"):
        errors.append("Tabler service icon manifest hash changed")


def validate_hosted_browser_components(payload: dict, errors: list[str]) -> None:
    components = {
        component.get("name"): component
        for component in payload.get("hosted_browser_components", [])
    }
    if set(components) != set(PINNED_CLERK_BROWSER_COMPONENTS):
        errors.append("Hosted Clerk browser component provenance is incomplete")
        return

    for name, expected in PINNED_CLERK_BROWSER_COMPONENTS.items():
        component = components[name]
        for key, value in expected.items():
            if component.get(key) != value:
                errors.append(f"{name} hosted-browser provenance has unexpected {key}")
        if not str(component.get("official_source", "")).startswith("https://"):
            errors.append(f"{name} hosted-browser provenance lacks an HTTPS official source")
        if not str(component.get("package_integrity", "")).startswith("sha512-"):
            errors.append(f"{name} hosted-browser provenance lacks an npm integrity hash")
        if component.get("delivery") != "same-domain Clerk Frontend API proxy":
            errors.append(f"{name} hosted-browser provenance has an unexpected delivery model")

    source_markers = {
        REPO_ROOT / "cloudflare" / "worker" / "entry_shell.py": (
            'CLERK_UI_VERSION = "1.41.2"',
            'CLERK_JS_VERSION = "6.40.1"',
            "clerk_ui_asset_url",
            "clerk_js_asset_url",
        ),
        REPO_ROOT / "cloudflare" / "worker" / "app_shell.py": (
            "CLERK_UI_VERSION",
            "CLERK_JS_VERSION",
        ),
        REPO_ROOT / "workdoe" / "__init__.py": (
            'CLERK_UI_VERSION = "1.41.2"',
            'CLERK_JS_VERSION = "6.40.1"',
            "def clerk_ui_script_url",
            "def clerk_js_script_url",
        ),
    }
    for path, markers in source_markers.items():
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"Clerk asset source is unreadable: {exc}")
            continue
        for marker in markers:
            if marker not in source:
                errors.append(f"Clerk asset source is missing marker: {path.name} {marker}")

    for template_name in ("account.html", "login.html", "start.html"):
        template_path = REPO_ROOT / "workdoe" / "templates" / template_name
        try:
            template = template_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"Clerk template is unreadable: {exc}")
            continue
        if "clerk_ui_script_url()" not in template or "clerk_js_script_url()" not in template:
            errors.append(f"Clerk template does not use pinned asset helpers: {template_name}")


def download_python_artifact(path: str) -> bytes:
    host = "files.pythonhosted.org"
    current_path = path
    for _redirect in range(4):
        connection = http.client.HTTPSConnection(host, timeout=30)
        try:
            connection.request("GET", current_path)
            response = connection.getresponse()
            if response.status == 200:
                return response.read()
            if response.status not in {301, 302, 303, 307, 308}:
                raise OSError(f"HTTP {response.status}")
            location = response.getheader("Location", "")
            parsed = urllib.parse.urlsplit(location)
            if parsed.scheme and parsed.scheme != "https":
                raise OSError("redirected to a non-HTTPS URL")
            if parsed.hostname and parsed.hostname != host:
                raise OSError("redirected outside files.pythonhosted.org")
            if not parsed.path.startswith("/packages/"):
                raise OSError("redirected outside the PyPI package path")
            current_path = parsed.path
            if parsed.query:
                current_path = f"{current_path}?{parsed.query}"
        finally:
            connection.close()
    raise OSError("too many redirects")


def validate_upstream(payload: dict, errors: list[str]) -> None:
    for group in payload.get("python_groups", []):
        for package in group.get("packages", []):
            path = (
                f"/packages/source/{package['name'][0].lower()}/"
                f"{package['name']}/{package['artifact']}"
            )
            try:
                digest = hashlib.sha256(download_python_artifact(path)).hexdigest()
            except OSError as exc:
                errors.append(f"Could not retrieve {package['artifact']}: {exc}")
                continue
            if digest != package["sha256"]:
                errors.append(f"Upstream artifact hash changed: {package['artifact']}")


def verify(ledger_path: Path, *, verify_upstream: bool = False) -> list[str]:
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"Provenance ledger is unreadable: {exc}"]

    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("Unsupported provenance schema version")
    if payload.get("repository_hash_policy") != REPOSITORY_HASH_POLICY:
        errors.append("Unsupported repository artifact hash policy")
    first_party = payload.get("first_party", {})
    if first_party.get("license_status") != "proprietary":
        errors.append("Workdoe first-party code must be recorded as proprietary")
    license_path = REPO_ROOT / first_party.get("license_file", "")
    if not license_path.is_file():
        errors.append("The Workdoe proprietary LICENSE file is missing")

    validate_python_groups(payload, errors)
    validate_node_tooling(payload, errors)
    validate_runtime_components(payload, errors)
    validate_browser_components(payload, errors)
    validate_hosted_browser_components(payload, errors)
    if verify_upstream:
        validate_upstream(payload, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Workdoe dependency provenance.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument(
        "--verify-upstream",
        action="store_true",
        help="Download recorded Python source archives and verify their SHA-256 values.",
    )
    args = parser.parse_args()
    errors = verify(args.ledger, verify_upstream=args.verify_upstream)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    suffix = " including upstream Python artifacts" if args.verify_upstream else ""
    print(f"Dependency provenance verified{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
