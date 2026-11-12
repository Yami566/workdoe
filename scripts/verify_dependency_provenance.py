from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import http.client
import json
import re
import sys
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO_ROOT / "DEPENDENCY_PROVENANCE.json"
CLERK_BROWSER_PINS_PATH = "cloudflare/worker/clerk_browser_pins.py"
MAX_CLERK_BROWSER_PIN_BYTES = 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
STATIC_APPLICATION_NAME = re.compile(r"(?:\.assetsignore|_headers|[a-z0-9][a-z0-9-]*\.(?:css|js|webmanifest))")
STATIC_RASTER_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\.(?:png|webp)")
NPM_SHA512_PATTERN = re.compile(r"sha512-[A-Za-z0-9+/]{86}==")
MAP_VENDOR_DIRECTORIES = {
    "Leaflet": "leaflet",
    "Leaflet.markercluster": "leaflet-markercluster",
}
BROWSER_VENDOR_DIRECTORIES = MAP_VENDOR_DIRECTORIES | {"Tabler Icons": "tabler-icons"}
BROWSER_VENDOR_LICENSES = {
    "Leaflet": "BSD-2-Clause",
    "Leaflet.markercluster": "MIT",
    "Tabler Icons": "MIT",
}
VENDORED_BROWSER_NPM_PACKAGES = {
    "Leaflet": "leaflet",
    "Leaflet.markercluster": "leaflet.markercluster",
    "Tabler Icons": "@tabler/icons",
}
MAX_NPM_ADVISORY_BYTES = 128_000
MAX_TOOLING_ADVISORY_PINS = 256
MAX_TOOLING_ADVISORY_BYTES = 256_000
NPM_NAME_PATTERN = re.compile(r"(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*")
NPM_VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.+-]+)?")
ADVISORY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}")
CLERK_NOTICE_DIRECTORY = "clerk-notices-v2"
REVIEWED_VENDOR_ROOT_DIRECTORIES = frozenset({*BROWSER_VENDOR_DIRECTORIES.values(), CLERK_NOTICE_DIRECTORY})
REVIEWED_VENDOR_DIRECTORIES = REVIEWED_VENDOR_ROOT_DIRECTORIES | {"leaflet/images"}
CLERK_NOTICE_INDEX = "notices-1.html"
CLERK_STRIPE_ZXCVBN_NOTICES = frozenset({
    "@stripe/stripe-js", "@stripe/react-stripe-js", "@zxcvbn-ts/core", "@zxcvbn-ts/language-common",
})
CLERK_UI_NOTICE_ADDITIONS = CLERK_STRIPE_ZXCVBN_NOTICES | {"@tanstack/query-core", "@formkit/auto-animate"}
CLERK_RECENT_UI_NOTICES = frozenset({"input-otp", "copy-to-clipboard", "qrcode.react"})
CLERK_RUNTIME_NOTICE_ADDITIONS = frozenset({
    "core-js", "crypto-js", "@floating-ui/react", "@emotion/react", "@emotion/cache", "@wallet-standard/app",
})
CLERK_EIP712_NOTICE_INDEX = "cd5215d6f8f6d36335da1778141794256607e7eb5a96c08f582200b6be4a328b"  # pragma: allowlist secret
CLERK_RECENT_UI_NOTICE_INDEX = "6e025b9e5676f7c6827a6f13a837e97fba0f5e2cb7527601dba53836c87b8792"  # pragma: allowlist secret
CLERK_PREVIOUS_NOTICE_INDEX_OMISSIONS = {
    "95d9cdd331df12f04946aa49724206e433cba88f18a012860817765590de62fb": CLERK_UI_NOTICE_ADDITIONS | {"browser-tabs-lock"},
    "b90e7acc75042d98216054eb873a15a64e647751feb12596556275b86ba7c5a0": CLERK_UI_NOTICE_ADDITIONS | {"browser-tabs-lock"},
    "0d26a08931202bcfdfef2c8ef24997873a231e151357da882f09167c725833c6": CLERK_UI_NOTICE_ADDITIONS,
    "4f9d834f1f5f4e3d111cbe67789ed251ddfebe3c9f6d823c5a886e9fd7d8aaef": CLERK_UI_NOTICE_ADDITIONS,
    "a333d6028c2855fc85312279d499111700cfbd23951309ee60155c257cffd694": CLERK_STRIPE_ZXCVBN_NOTICES,
    "c90bc786b1677435c38f76bea3fb3956e4062958460710eedb8e6e5617fee6a4": frozenset(),
    CLERK_EIP712_NOTICE_INDEX: frozenset(),
    CLERK_RECENT_UI_NOTICE_INDEX: frozenset(),
}
CLERK_COINBASE_EIP712_NOTICE = {
    "parent_package": "@coinbase/wallet-sdk",
    "archive_member": "package/dist/vendor-js/eth-eip712-util/LICENSE",  # pragma: allowlist secret - public npm path.
    "license": "ISC",
    "filename": "coinbase-eip712-isc-license.txt",
}
CLERK_QR_GENERATOR_NOTICE = {
    "source_commit": "f91d2bdcc39def6c5c77178743a44f935a740992",  # pragma: allowlist secret - public commit.
    "source_path": "src/third-party/qrcodegen/LICENSE",
    "license": "MIT",
    "filename": "qrcode-generator-license.txt",
}
APACHE_LICENSE_FILE = "apache-2.0-license.txt"
CLERK_NOTICE_SOURCE_COMMIT = "8b9403b5e86b33d80eccea24b3b902b5585c07b0"
CLERK_NOTICE_INPUTS = {
    "react": ("18.3.1", "MIT", "react-18.3.1-license.txt"),
    "react-dom": ("18.3.1", "MIT", "react-18.3.1-license.txt"),
    "scheduler": ("0.23.2", "MIT", "react-18.3.1-license.txt"),
    "@base-org/account": ("2.0.1", "Apache-2.0", "base-account-2.0.1-license.txt"),
    "@coinbase/wallet-sdk": ("4.3.7", "Apache-2.0", "coinbase-wallet-4.3.7-license.txt"),
    "browser-tabs-lock": ("1.3.0", "MIT", "browser-tabs-lock-1.3.0-license.txt"),
    "@tanstack/query-core": ("5.102.8", "MIT", "tanstack-query-core-5.102.8-license.txt"),
    "@formkit/auto-animate": ("0.8.4", "MIT", "formkit-auto-animate-0.8.4-license.txt"),
    "@stripe/stripe-js": ("5.6.0", "MIT", "stripe-sdk-license.txt"),
    "@stripe/react-stripe-js": ("3.1.1", "MIT", "stripe-sdk-license.txt"),
    "@zxcvbn-ts/core": ("3.0.4", "MIT", "zxcvbn-ts-3.0.4-license.txt"),
    "@zxcvbn-ts/language-common": ("3.0.4", "MIT", "zxcvbn-ts-3.0.4-license.txt"),
    "input-otp": ("1.4.2", "MIT", "input-otp-1.4.2-license.txt"),
    "copy-to-clipboard": ("3.3.3", "MIT", "copy-to-clipboard-3.3.3-license.txt"),
    "qrcode.react": ("4.2.0", "ISC", "qrcode-react-4.2.0-license.txt"),
    "core-js": ("3.47.0", "MIT", "core-js-3.47.0-license.txt"),
    "crypto-js": ("4.2.0", "MIT", "crypto-js-4.2.0-license.txt"),
    "@floating-ui/react": ("0.27.20", "MIT", "floating-ui-react-0.27.20-license.txt"),
    "@emotion/react": ("11.11.1", "MIT", "emotion-license.txt"),
    "@emotion/cache": ("11.11.0", "MIT", "emotion-license.txt"),
    "@wallet-standard/app": ("1.1.0", "Apache-2.0", APACHE_LICENSE_FILE),
}
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
    ".txt",
}
TEXT_ARTIFACT_NAMES = {"copying", "license", "notice"}
REPOSITORY_HASH_POLICY = {
    "binary": "sha256-bytes",
    "text": "sha256-lf",
}
REQUIRED_REQUIREMENTS_FILES = {"requirements.txt", "requirements-audit.txt"}
PYTHON_WHEEL_LOCK_DIRECTORY = ".github/python"
PYTHON_WHEEL_LOCK_FILES = {"runtime.txt", "ruff.txt", "audit.txt"}
WHEEL_REQUIREMENT = re.compile(
    r'(?P<name>[a-z0-9]+(?:-[a-z0-9]+)*)==(?P<version>[0-9]+(?:\.[0-9]+)+)'
    r'(?P<windows>; platform_system == "Windows")?(?: --hash=sha256:[0-9a-f]{64}){1,2}'
)
PINNED_CLERK_BROWSER_COMPONENTS = {
    "Clerk UI": {
        "package": "@clerk/ui",
        "version": "1.41.2",
        "license": "MIT",
        "script_path": "/npm/@clerk/ui@1.41.2/dist/ui.browser.js",
        "script_integrity": "sha384-FYXAFwPN7TccH+1GBGhfSmj4kqvVseEdP5OAvO5JnZp3fArgoYkLmW0MLwnxJFUB",
        "retained_license": "licenses/clerk-ui.MIT",
        "retained_license_sha256": "b36183cf0be2cbda03d80db9b96e5aacd2879462b15fc8e4f4e179a7c91f1ca7",
    },
    "ClerkJS": {
        "package": "@clerk/clerk-js",
        "version": "6.40.1",
        "license": "MIT",
        "script_path": "/npm/@clerk/clerk-js@6.40.1/dist/clerk.browser.js",
        "script_integrity": "sha384-JcUoKGgU3fVbZOepxOhFBTSImBs/0xQTLYLqy0CLEkd2sMiA4wn5VDTC6IJYRSaj",
        "retained_license": "licenses/clerk-js.MIT",
        "retained_license_sha256": "629611a2fad128e60cc850d64b8770fcb251b0b55016a60802d70eeb32ee1b04",
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
    groups = records_by_key(
        payload.get("python_groups", []), "requirements_file", "Python inventory", errors,
    )
    expected_files = REQUIRED_REQUIREMENTS_FILES | {
        path.name for path in REPO_ROOT.glob("requirements*.txt") if path.is_file()
    }
    if set(groups) != expected_files:
        errors.append(
            "Python inventory must cover every root requirements file exactly: "
            f"expected={sorted(expected_files)!r}, recorded={sorted(groups)!r}"
        )
    for relative_path, group in groups.items():
        if relative_path not in expected_files:
            continue
        requirements_path = REPO_ROOT / relative_path
        try:
            pinned = parse_requirements(requirements_path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue

        packages = records_by_key(
            group.get("packages", []), "name", f"{relative_path} packages", errors,
            casefold=True,
        )
        recorded: dict[str, str] = {}
        for package in packages.values():
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


def parse_wheel_lock(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        match = WHEEL_REQUIREMENT.fullmatch(line)
        if not match:
            raise ValueError(f"Invalid hashed wheel pin in {path.name}")
        name = match["name"]
        if name in pins or bool(match["windows"]) != (name == "colorama"):
            raise ValueError(f"Duplicate or unexpected platform marker in {path.name}: {name}")
        pins[name] = match["version"]
    if not pins:
        raise ValueError(f"Python wheel lock is empty: {path.name}")
    return pins


def validate_python_wheel_locks(payload: dict, errors: list[str]) -> None:
    hashes = payload.get("python_wheel_locks")
    if not isinstance(hashes, dict) or set(hashes) != PYTHON_WHEEL_LOCK_FILES:
        errors.append("Python wheel inventory must cover all three verification locks")
        return
    try:
        pins = {}
        for name, expected in hashes.items():
            path = REPO_ROOT / PYTHON_WHEEL_LOCK_DIRECTORY / name
            if not isinstance(expected, str) or sha256_file(path) != expected:
                raise ValueError(f"Reviewed Python wheel lock hash changed: {name}")
            pins[name] = parse_wheel_lock(path)
        runtime = pins["runtime.txt"]
        audit = pins["audit.txt"] | pins["ruff.txt"]
        if len(runtime | audit) != sum(map(len, pins.values())) or set(pins["ruff.txt"]) != {"ruff"}:
            raise ValueError("Python wheel locks overlap or the Ruff lock is invalid")
        for source, lock in (("requirements.txt", runtime), ("requirements-audit.txt", audit)):
            if not parse_requirements(REPO_ROOT / source).items() <= lock.items():
                raise ValueError(f"Python wheel lock does not match direct pins in {source}")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))


def validate_node_tooling(payload: dict, errors: list[str]) -> None:
    try:
        package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Node package metadata is unreadable: {exc}")
        return

    if not isinstance(package, dict) or not isinstance(package_lock, dict):
        errors.append("Node package metadata must be JSON objects")
        return
    locked_packages = package_lock.get("packages")
    if (
        package_lock.get("lockfileVersion") != 3
        or not isinstance(locked_packages, dict)
        or not isinstance(locked_packages.get(""), dict)
        or any(not isinstance(entry, dict) for entry in locked_packages.values())
    ):
        errors.append("Node tooling requires a version 3 lockfile with a complete packages map")
        return
    if (REPO_ROOT / "npm-shrinkwrap.json").exists():
        errors.append("npm-shrinkwrap.json is not part of the reviewed npm install")

    review = payload.get("node_lock_review")
    canonical_lock = json.dumps(package_lock, sort_keys=True, separators=(",", ":")).encode("ascii")
    if (
        not isinstance(review, dict)
        or review.get("package_count") != len(locked_packages) - 1
        or review.get("canonical_sha256") != hashlib.sha256(canonical_lock).hexdigest()
    ):
        errors.append("The complete npm lockfile differs from the reviewed tooling inventory")
    for path, entry in locked_packages.items():
        if path and (
            not path.startswith("node_modules/")
            or entry.get("dev") is not True
            or entry.get("link")
            or not isinstance(entry.get("version"), str)
            or not str(entry.get("resolved", "")).startswith("https://registry.npmjs.org/")
            or not NPM_SHA512_PATTERN.fullmatch(str(entry.get("integrity", "")))
            or not isinstance(entry.get("license"), str)
            or not entry["license"].strip()
        ):
            errors.append(f"Locked Node entry lacks reviewed dev-only registry provenance: {path}")

    records = records_by_key(
        payload.get("node_tooling", []), "name", "Node inventory", errors,
    )
    declared = {}
    lock_root = locked_packages[""]
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        dependencies = package.get(section, {})
        if not isinstance(dependencies, dict):
            errors.append(f"package.json {section} must be an object")
            continue
        if dependencies != lock_root.get(section, {}):
            errors.append(f"package-lock.json root {section} differs from package.json")
        for name, version in dependencies.items():
            if name in declared:
                errors.append(f"Direct Node dependency appears in multiple groups: {name}")
            declared[name] = version
    if set(records) != set(declared) or "wrangler" not in records:
        errors.append(
            "Node inventory must cover every direct dependency, including Wrangler: "
            f"declared={sorted(declared)!r}, recorded={sorted(records)!r}"
        )

    for dependency in records.values():
        name = str(dependency.get("name", ""))
        version = str(dependency.get("version", ""))
        locked = locked_packages.get(f"node_modules/{name}", {})
        if declared.get(name) != version:
            errors.append(f"package.json pins {name} at {declared.get(name)!r}, expected {version!r}")
        if locked.get("version") != version:
            errors.append(f"package-lock.json pins {name} at {locked.get('version')!r}, expected {version!r}")
        if locked.get("integrity") != dependency.get("integrity"):
            errors.append(f"package-lock.json integrity for {name} does not match the ledger")
        if not str(dependency.get("integrity", "")).startswith("sha512-"):
            errors.append(f"{name} lacks an npm integrity hash")
        if not str(dependency.get("official_source", "")).startswith("https://"):
            errors.append(f"{name} lacks an HTTPS official source")
        if not dependency.get("license") or not dependency.get("purpose"):
            errors.append(f"{name} lacks license or purpose metadata")


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


def validate_static_vendor_tree(root: Path, errors: list[str]) -> bool:
    is_junction = getattr(Path, "is_junction", lambda _: False)
    pending = [root]
    directories = set()
    try:
        while pending:
            directory = pending.pop()
            for path in directory.iterdir():
                relative = path.relative_to(root).as_posix()
                if path.is_symlink() or is_junction(path):
                    errors.append(f"Invalid file type or link in the static vendor tree: {relative!r}")
                    return False
                if path.is_dir():
                    if relative not in REVIEWED_VENDOR_DIRECTORIES:
                        errors.append(f"Unreviewed static vendor directory: {relative!r}")
                        return False
                    directories.add(relative)
                    pending.append(path)
                elif directory == root or relative in REVIEWED_VENDOR_DIRECTORIES or not path.is_file():
                    errors.append(f"Invalid file type or link in the static vendor tree: {relative!r}")
                    return False
    except OSError:
        errors.append("The reviewed static vendor tree is unreadable")
        return False
    if directories != REVIEWED_VENDOR_DIRECTORIES:
        errors.append("The static vendor tree is missing reviewed directories")
        return False
    return True


def public_map_data_identity(payload: dict) -> tuple[str, str]:
    record = payload.get("public_map_data")
    if not isinstance(record, dict):
        raise TypeError("The public map data provenance record is missing")
    digest = str(record.get("sha256", ""))
    name = f"dmv-area-{digest[:8]}.geojson"
    expected_path = f"workdoe/static/{name}"
    if (
        not SHA256_PATTERN.fullmatch(digest)
        or record.get("artifact") != expected_path
        or record.get("publisher") != "U.S. Census Bureau"
        or not str(record.get("official_source", "")).startswith("https://tigerweb.geo.census.gov/")
        or not record.get("vintage")
        or record.get("license") != "U.S. government public domain"
    ):
        raise ValueError("The public map data provenance record is invalid")
    return expected_path, digest


def validate_public_map_data(payload: dict, errors: list[str]) -> None:
    try:
        expected_path, digest = public_map_data_identity(payload)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        return
    try:
        actual = hashlib.sha256((REPO_ROOT / expected_path).read_bytes()).hexdigest()
    except OSError:
        errors.append("The reviewed public map data artifact is missing")
        return
    if actual != digest:
        errors.append("The public map data artifact hash changed")
        return
    integrity = "sha256-" + base64.b64encode(bytes.fromhex(digest)).decode("ascii")
    try:
        controller = (REPO_ROOT / "workdoe/static/map.js").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        errors.append("The public map controller is unreadable")
        return
    if f'var AREA_MAP_INTEGRITY = "{integrity}";' not in controller:
        errors.append("The map controller integrity pin differs from the reviewed public map data")
    if f'var AREA_MAP_ASSET = "/{Path(expected_path).name}";' not in controller:
        errors.append("The map controller URL differs from the reviewed public map data")


def validate_static_root(payload: dict, errors: list[str]) -> bool:
    review = payload.get("static_root_review")
    if not isinstance(review, dict):
        errors.append("The public static root review is missing")
        return False
    application = review.get("application_files")
    if (
        not isinstance(application, list)
        or not application
        or any(not isinstance(name, str) or not STATIC_APPLICATION_NAME.fullmatch(name) for name in application)
        or len(application) != len(set(application))
    ):
        errors.append("The static application inventory must list unique, approved file types")
        return False

    initial_errors = len(errors)
    artwork = records_by_key(review.get("raster_assets"), "filename", "Static raster inventory", errors)
    if not artwork or any(
        not STATIC_RASTER_NAME.fullmatch(name)
        or not SHA256_PATTERN.fullmatch(str(record.get("sha256", "")))
        or not re.fullmatch(r"[0-9a-f]{40}", str(record.get("source_commit", "")))
        or not isinstance(record.get("provenance"), str)
        or not record["provenance"].strip()
        for name, record in artwork.items()
    ):
        errors.append("The static raster inventory requires a local filename, hash and source for each asset")
    if not SHA256_PATTERN.fullmatch(str(review.get("asset_ignore_sha256", ""))):
        errors.append("The static inventory requires the reviewed asset ignore hash")
    if ".assetsignore" not in application:
        errors.append("The static inventory must retain its asset ignore policy")
    if len(errors) != initial_errors:
        return False

    try:
        map_path, _ = public_map_data_identity(payload)
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
        return False
    expected = {*application, *artwork, Path(map_path).name, "deer.svg", "vendor"}
    root = REPO_ROOT / "workdoe/static"
    is_junction = getattr(Path, "is_junction", lambda _: False)
    if any(path.is_symlink() or is_junction(path) for path in (root.parent, root)):
        errors.append("The static root must not be reached through a filesystem link")
        return False
    try:
        entries = {path.name: path for path in root.iterdir()}
    except OSError:
        errors.append("The reviewed public static root is unreadable")
        return False
    if unexpected := sorted(entries.keys() - expected):
        errors.append(f"Unreviewed static asset entries: {unexpected!r}")
    if missing := sorted(expected - entries.keys()):
        errors.append(f"Reviewed static asset entries are missing: {missing!r}")
    if len(errors) != initial_errors:
        return False

    for name, path in entries.items():
        if (path.is_symlink() or is_junction(path)
                or not (path.is_dir() if name == "vendor" else path.is_file())):
            errors.append(f"Invalid file type or link in the static root: {name!r}")
    if len(errors) != initial_errors or not validate_static_vendor_tree(entries["vendor"], errors):
        return False
    try:
        if sha256_file(entries[".assetsignore"]) != review["asset_ignore_sha256"]:
            errors.append("Reviewed asset ignore policy hash changed")
    except OSError:
        errors.append("Reviewed asset ignore policy is unreadable")
    for name, record in artwork.items():
        try:
            if sha256_file(entries[name]) != record["sha256"]:
                errors.append(f"Reviewed raster asset hash changed: {name}")
        except OSError:
            errors.append(f"Reviewed raster asset is unreadable: {name}")
    return len(errors) == initial_errors


def read_service_icon_map(path: Path) -> dict[str, str]:
    source = ast.parse(path.read_text(encoding="utf-8"))
    assignments = [
        statement.value for statement in source.body
        if isinstance(statement, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "SERVICE_ICON_BY_SLUG" for target in statement.targets)
    ]
    if len(assignments) != 1 or not isinstance(assignments[0], ast.Dict):
        raise ValueError("Expected one literal service icon map.")
    pairs = zip(assignments[0].keys, assignments[0].values, strict=True)
    icons = {}
    for key, value in pairs:
        if (
            not isinstance(key, ast.Constant) or not isinstance(key.value, str) or not key.value
            or key.value in icons or not isinstance(value, ast.Constant) or not isinstance(value.value, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.svg", value.value)
        ):
            raise ValueError("Invalid literal service icon entry.")
        icons[key.value] = value.value
    if not icons:
        raise ValueError("The service icon map is empty.")
    return icons


def validate_browser_components(payload: dict, errors: list[str]) -> None:
    components = records_by_key(
        payload.get("browser_components", []), "name", "Browser inventory", errors,
    )
    if set(components) != BROWSER_VENDOR_DIRECTORIES.keys():
        errors.append("Browser inventory must contain Leaflet, Leaflet.markercluster and Tabler Icons")
    vendor_root = REPO_ROOT / "workdoe" / "static" / "vendor"
    vendor_entries = list(vendor_root.iterdir()) if vendor_root.is_dir() else []
    if {path.name for path in vendor_entries} != REVIEWED_VENDOR_ROOT_DIRECTORIES or any(
        not path.is_dir() or path.is_symlink() for path in vendor_entries
    ):
        errors.append("Browser inventory must cover every entry in the static vendor root")
    for name, component in components.items():
        if name not in BROWSER_VENDOR_DIRECTORIES:
            continue
        directory = vendor_root / BROWSER_VENDOR_DIRECTORIES[name]
        license_path = directory / "LICENSE"
        if component.get("retained_license") != license_path.relative_to(REPO_ROOT).as_posix():
            errors.append(f"{name} must retain its license in the reviewed public vendor directory")
            continue
        license_id = BROWSER_VENDOR_LICENSES[name]
        if component.get("license") != license_id:
            errors.append(f"{name} must retain its reviewed {license_id} license record")
            continue
        expected_license_hash = component.get("retained_license_sha256", "")
        if not license_path.is_file():
            errors.append(f"Missing retained license: {license_path.relative_to(REPO_ROOT)}")
        elif sha256_file(license_path) != expected_license_hash:
            errors.append(f"Retained license hash changed: {license_path.relative_to(REPO_ROOT)}")
        artifacts = records_by_key(
            component.get("artifacts", []), "path",
            f"{name} artifacts", errors,
        )
        if name in MAP_VENDOR_DIRECTORIES:
            expected_paths = {
                path.relative_to(REPO_ROOT).as_posix()
                for path in directory.rglob("*")
                if path.is_file() and path != license_path
            }
            if not expected_paths or set(artifacts) != expected_paths:
                errors.append(f"{name} artifacts must cover its complete vendor directory")
                continue
        elif artifacts:
            errors.append("Tabler artifacts must use the reviewed vendor and icon manifests")
            continue
        for artifact in artifacts.values():
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

    icon_directory = vendor_root / BROWSER_VENDOR_DIRECTORIES["Tabler Icons"]
    vendor_paths = {
        path.relative_to(icon_directory).as_posix(): path
        for path in icon_directory.rglob("*")
        if path.is_file() and path != icon_directory / "LICENSE"
    }
    vendor_hashes = {name: sha256_file(path) for name, path in vendor_paths.items()}
    vendor_manifest = "\n".join(f"{name} {vendor_hashes[name]}" for name in sorted(vendor_hashes))
    if len(vendor_hashes) != tabler.get("vendor_file_count") or (
        hashlib.sha256(vendor_manifest.encode("utf-8")).hexdigest()
        != tabler.get("vendor_manifest_sha256")
    ):
        errors.append("Tabler complete vendor manifest changed")

    pencil_path = icon_directory / "pencil.svg"
    if not pencil_path.is_file():
        errors.append("The pinned Tabler pencil asset is missing")
    elif sha256_file(pencil_path) != tabler.get("pencil_asset_sha256"):
        errors.append("Tabler pencil asset hash changed")

    try:
        local_icons = read_service_icon_map(REPO_ROOT / "workdoe/service_taxonomy.py")
        worker_icons = read_service_icon_map(REPO_ROOT / "cloudflare/worker/service_taxonomy.py")
    except (OSError, SyntaxError, ValueError):
        errors.append("Could not read the literal service icon maps")
        return
    if local_icons != worker_icons:
        errors.append("Flask and Worker service icon maps differ")
        return
    icon_names = sorted(set(local_icons.values()))
    if any(name not in vendor_hashes for name in icon_names):
        errors.append("The pinned Tabler service icon set is missing files")
        return
    manifest = "\n".join(
        f"{name} {vendor_hashes[name]}" for name in icon_names
    )
    manifest_hash = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    if len(icon_names) != tabler.get("service_icon_count"):
        errors.append("Tabler service icon count changed")
    if manifest_hash != tabler.get("service_icon_manifest_sha256"):
        errors.append("Tabler service icon manifest hash changed")


def records_by_key(
    value, key: str, label: str, errors: list[str], *, casefold: bool = False,
) -> dict[str, dict]:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array of records")
        return {}
    records: dict[str, dict] = {}
    for record in value:
        if not isinstance(record, dict) or not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f"{label} contains a record without a nonempty {key}")
            continue
        identity = record[key].casefold() if casefold else record[key]
        if identity in records:
            errors.append(f"{label} contains duplicate {key}: {identity}")
            continue
        records[identity] = record
    return records

def clerk_build_notice_digests(
    payload: dict, errors: list[str], *, allow_previous_index: bool = False,
) -> dict[str, str]:
    review = payload.get("clerk_build_notices")
    if not isinstance(review, dict) or review.get("source_commit") != CLERK_NOTICE_SOURCE_COMMIT:
        errors.append("Clerk build notice inventory must identify the reviewed source commit")
        return {}
    packages = records_by_key(review.get("packages"), "package", "Clerk build notice inputs", errors)
    index_digest = review.get("index_sha256")
    historical = isinstance(index_digest, str) and index_digest in CLERK_PREVIOUS_NOTICE_INDEX_OMISSIONS
    if historical and not allow_previous_index:
        errors.append("Current Clerk notice verification requires the current notice index")
        return {}
    omissions = frozenset()
    if historical:
        omissions = CLERK_PREVIOUS_NOTICE_INDEX_OMISSIONS[index_digest] | CLERK_RUNTIME_NOTICE_ADDITIONS
        if index_digest != CLERK_RECENT_UI_NOTICE_INDEX:
            omissions |= CLERK_RECENT_UI_NOTICES
    inputs = {name: pin for name, pin in CLERK_NOTICE_INPUTS.items() if name not in omissions}
    if packages.keys() != inputs.keys():
        errors.append("Clerk build notice inventory must list the exact reviewed packages")
        return {}
    digests = {
        CLERK_NOTICE_INDEX: index_digest,
        APACHE_LICENSE_FILE: review.get("apache_license_sha256"),
    }
    for name, (version, license_id, filename) in inputs.items():
        record = packages[name]
        digest = record.get("sha256")
        if (record.get("version"), record.get("license"), record.get("filename")) != (version, license_id, filename) or (
            not NPM_SHA512_PATTERN.fullmatch(str(record.get("package_integrity", "")))
        ):
            errors.append(f"Clerk build notice input differs from the reviewed pin: {name}")
            return {}
        if filename in digests and digests[filename] != digest:
            errors.append(f"Shared Clerk build notice has inconsistent hashes: {filename}")
            return {}
        digests[filename] = digest
    embedded = review.get("coinbase_eip712_notice")
    if historical and index_digest not in {CLERK_EIP712_NOTICE_INDEX, CLERK_RECENT_UI_NOTICE_INDEX}:
        if "coinbase_eip712_notice" in review:
            errors.append("Historical Clerk notice index must not include the later Coinbase EIP-712 notice")
            return {}
    elif (
        not isinstance(embedded, dict) or embedded.keys() != CLERK_COINBASE_EIP712_NOTICE.keys() | {"sha256"}
        or any(embedded[key] != value for key, value in CLERK_COINBASE_EIP712_NOTICE.items())
    ):
        errors.append("Clerk notice inventory must retain the reviewed Coinbase EIP-712 ISC notice")
        return {}
    else:
        digests[embedded["filename"]] = embedded["sha256"]
    if "qrcode.react" in inputs:
        qr_notice = packages["qrcode.react"].get("generator_notice")
        if (
            not isinstance(qr_notice, dict) or qr_notice.keys() != CLERK_QR_GENERATOR_NOTICE.keys() | {"sha256"}
            or any(qr_notice[key] != value for key, value in CLERK_QR_GENERATOR_NOTICE.items())
        ):
            errors.append("Clerk notice inventory must retain the reviewed QR Code Generator MIT notice")
            return {}
        digests[qr_notice["filename"]] = qr_notice["sha256"]
    if any(not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest) for digest in digests.values()):
        errors.append("Clerk build notice inventory has a malformed artifact hash")
        return {}
    return digests

def validate_clerk_build_notices(payload: dict, errors: list[str]) -> None:
    digests = clerk_build_notice_digests(payload, errors)
    if not digests:
        return
    directory = REPO_ROOT / "workdoe/static/vendor" / CLERK_NOTICE_DIRECTORY
    is_junction = getattr(Path, "is_junction", lambda _: False)
    if not directory.is_dir() or any(path.is_symlink() or is_junction(path) for path in (directory, directory.parent)):
        errors.append("Clerk build notice directory is missing or linked")
        return
    entries = {path.name: path for path in directory.iterdir()}
    if entries.keys() != digests.keys() or any(
        not path.is_file() or path.is_symlink() for path in entries.values()
    ):
        errors.append("Clerk build notice directory differs from the reviewed files")
        return
    for filename, path in entries.items():
        try:
            if sha256_file(path) != digests[filename]:
                errors.append(f"Clerk build notice hash changed: {filename}")
        except OSError:
            errors.append(f"Clerk build notice is unreadable: {filename}")


def load_clerk_browser_inventory() -> dict:
    path = REPO_ROOT / "cloudflare" / "worker" / "clerk_browser_files.py"
    return parse_clerk_browser_inventory(path.read_text(encoding="utf-8"))


def parse_clerk_browser_inventory(source: str) -> dict:
    return parse_clerk_browser_declaration(source, "CLERK_BROWSER_FILES")


def parse_clerk_browser_declaration(source: str, name: str) -> dict:
    declaration, = ast.parse(source).body
    if (
        not isinstance(declaration, ast.Assign)
        or len(declaration.targets) != 1
        or not isinstance(declaration.targets[0], ast.Name)
        or declaration.targets[0].id != name
    ):
        raise ValueError("Invalid Clerk browser inventory declaration")
    inventory = ast.literal_eval(declaration.value)
    if not isinstance(inventory, dict):
        raise TypeError("Invalid Clerk browser inventory data")
    return inventory


def load_clerk_browser_pins() -> dict:
    source = (REPO_ROOT / CLERK_BROWSER_PINS_PATH).read_text(encoding="utf-8")
    return parse_clerk_browser_declaration(source, "CLERK_BROWSER_PINS")


def validate_clerk_browser_pins(ledger: dict, inventory: dict, pins: dict) -> None:
    paths = {f"{package}/dist/{name}" for package, names in inventory.items() for name in names}
    paths.update(f"{package}/LICENSE" for package in inventory)
    if pins.keys() != paths or any(
        not isinstance(pin, tuple) or len(pin) != 2
        or type(pin[0]) is not int or not 0 < pin[0] <= MAX_CLERK_BROWSER_PIN_BYTES
        or not isinstance(pin[1], str) or not SHA256_PATTERN.fullmatch(pin[1])
        for pin in pins.values()
    ):
        raise ValueError("Clerk browser byte pins do not match the reviewed file inventory.")
    serialized = json.dumps(pins, sort_keys=True, separators=(",", ":")).encode("ascii")
    if hashlib.sha256(serialized).hexdigest() != ledger.get("clerk_browser_body_pins_sha256"):
        raise ValueError("Clerk browser byte pins do not match the provenance ledger.")


def validate_clerk_browser_filenames(components: dict, errors: list[str], *, inventory: dict | None = None) -> None:
    if inventory is None:
        try:
            inventory = load_clerk_browser_inventory()
        except (OSError, SyntaxError, ValueError, TypeError):
            errors.append("Clerk browser filename inventory is missing or invalid")
            return

    packages = {expected["script_path"].partition("/dist/")[0] for expected in PINNED_CLERK_BROWSER_COMPONENTS.values()}
    if inventory.keys() != packages:
        errors.append("Clerk browser filename inventory does not match the reviewed packages")
        return
    for name, expected in PINNED_CLERK_BROWSER_COMPONENTS.items():
        package, _, entry = expected["script_path"].partition("/dist/")
        filenames = inventory[package]
        if (
            not isinstance(filenames, tuple)
            or not all(isinstance(file, str) and re.fullmatch(r"[A-Za-z0-9_.-]+\.js", file) for file in filenames)
            or tuple(sorted(set(filenames))) != filenames
            or entry not in filenames
        ):
            errors.append(f"{name} browser filename inventory is invalid")
            continue
        digest = hashlib.sha256(("\n".join(filenames) + "\n").encode("ascii")).hexdigest()
        component = components[name]
        if component.get("browser_file_count") != len(filenames) or component.get("browser_filenames_sha256") != digest:
            errors.append(f"{name} browser filename inventory does not match its recorded count or hash")


def validate_hosted_browser_components(payload: dict, errors: list[str]) -> None:
    components = records_by_key(
        payload.get("hosted_browser_components", []), "name", "Hosted browser inventory", errors,
    )
    if set(components) != set(PINNED_CLERK_BROWSER_COMPONENTS):
        errors.append("Hosted Clerk browser component provenance is incomplete")
        return

    validate_clerk_browser_filenames(components, errors)
    try:
        validate_clerk_browser_pins(payload, load_clerk_browser_inventory(), load_clerk_browser_pins())
    except (OSError, ValueError, SyntaxError, TypeError):
        errors.append("Clerk browser byte pins are missing, invalid, or do not match the provenance ledger")

    for name, expected in PINNED_CLERK_BROWSER_COMPONENTS.items():
        component = components[name]
        for key, value in expected.items():
            if component.get(key) != value:
                errors.append(f"{name} hosted-browser provenance has unexpected {key}")
        npm_source = f"https://www.npmjs.com/package/{expected['package']}/v/{expected['version']}"
        if component.get("official_source") != npm_source:
            errors.append(f"{name} hosted-browser provenance must use its pinned official npm source")
        if not NPM_SHA512_PATTERN.fullmatch(str(component.get("package_integrity", ""))):
            errors.append(f"{name} hosted-browser provenance lacks an npm integrity hash")
        if component.get("delivery") != "same-domain Clerk Frontend API proxy":
            errors.append(f"{name} hosted-browser provenance has an unexpected delivery model")
        license_path = REPO_ROOT / expected["retained_license"]
        try:
            if sha256_file(license_path) != expected["retained_license_sha256"]:
                errors.append(f"{name} retained upstream license hash changed")
        except OSError:
            errors.append(f"{name} retained upstream license is missing or unreadable")

    integrity_markers = tuple(
        f'CLERK_{constant}_INTEGRITY = "{PINNED_CLERK_BROWSER_COMPONENTS[name]["script_integrity"]}"'
        for constant, name in (("UI", "Clerk UI"), ("JS", "ClerkJS"))
    )
    source_markers = {
        REPO_ROOT / "cloudflare" / "worker" / "clerk_proxy.py": (
            'CLERK_UI_VERSION = "1.41.2"',
            'CLERK_JS_VERSION = "6.40.1"',
            'CLERK_UI_PACKAGE_PATH = f"/npm/@clerk/ui@{CLERK_UI_VERSION}"',
            'CLERK_JS_PACKAGE_PATH = f"/npm/@clerk/clerk-js@{CLERK_JS_VERSION}"',
        ),
        REPO_ROOT / "cloudflare" / "worker" / "entry_shell.py": (
            "{CLERK_UI_PACKAGE_PATH}/dist/ui.browser.js",
            "{CLERK_JS_PACKAGE_PATH}/dist/clerk.browser.js",
            "clerk_ui_asset_url",
            "clerk_js_asset_url",
            "clerk_browser_script_tags(",
            'integrity="{CLERK_UI_INTEGRITY}"',
            'integrity="{CLERK_JS_INTEGRITY}"',
            *integrity_markers,
        ),
        REPO_ROOT / "cloudflare" / "worker" / "app_shell.py": (
            "clerk_browser_script_tags(",
        ),
        REPO_ROOT / "workdoe" / "__init__.py": (
            'CLERK_UI_VERSION = "1.41.2"',
            'CLERK_JS_VERSION = "6.40.1"',
            "def clerk_ui_script_url",
            "def clerk_js_script_url",
            *integrity_markers,
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
        if '{% include "_clerk_browser_scripts.html" %}' not in template:
            errors.append(f"Clerk template does not use pinned asset helpers: {template_name}")

    try:
        shared = (REPO_ROOT / "workdoe/templates/_clerk_browser_scripts.html").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        errors.append("Shared Clerk template is unreadable")
    else:
        if any(marker not in shared for marker in (
            "clerk_ui_script_url()", "clerk_js_script_url()",
            'integrity="{{ clerk_ui_integrity }}"', 'integrity="{{ clerk_js_integrity }}"',
        )):
            errors.append("Shared Clerk template must render both pinned scripts with integrity")


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


def validate_browser_advisories(payload: dict, errors: list[str]) -> None:
    # The lockfile audit excludes vendored assets, proxy-served SDKs, and
    # their recorded notice components. This is not a full bundle inventory.
    pins = {
        VENDORED_BROWSER_NPM_PACKAGES[component["name"]]: [component.get("version")]
        for component in payload["browser_components"]
    } | {
        component["package"]: [component["version"]]
        for component in PINNED_CLERK_BROWSER_COMPONENTS.values()
    } | {
        package: [version] for package, (version, _, _) in CLERK_NOTICE_INPUTS.items()
    } | {
        # Confirmed in Clerk UI; upstream declares MIT but the exact release has no copyright notice.
        "toggle-selection": ["1.0.6"],
    }
    if any(not isinstance(pin[0], str) or not re.fullmatch(r"[0-9]{1,7}(?:\.[0-9]{1,7}){2}", pin[0])
           for pin in pins.values()):
        errors.append("Browser advisory check requires reviewed numeric version pins")
        return
    for package, count in npm_advisory_counts(pins, errors).items():
        errors.append(f"Review {count} npm advisory record(s) for {package}@{pins[package][0]} before release")


def npm_advisory_counts(pins: dict[str, list[str]], errors: list[str]) -> dict[str, int]:
    connection = http.client.HTTPSConnection("registry.npmjs.org", timeout=15)
    try:
        connection.request(
            "POST", "/-/npm/v1/security/advisories/bulk",
            body=json.dumps(pins).encode("ascii"), headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            errors.append(f"Browser advisory registry returned HTTP {response.status}")
            return {}
        body = response.read(MAX_NPM_ADVISORY_BYTES + 1)
        if len(body) > MAX_NPM_ADVISORY_BYTES:
            errors.append("Browser advisory registry response exceeds the size limit")
            return {}
        report = json.loads(body, object_pairs_hook=unique_json_keys)
    except (OSError, http.client.HTTPException, ValueError, RecursionError):
        errors.append("Browser advisory registry could not be reached or returned invalid JSON")
        return {}
    finally:
        connection.close()

    if not isinstance(report, dict) or report.keys() - pins.keys() or any(
        not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries)
        for entries in report.values()
    ):
        errors.append("Browser advisory registry returned an unexpected report shape")
        return {}
    return {package: len(entries) for package, entries in sorted(report.items()) if entries}


def release_tooling_pins() -> list[tuple[str, str, str]]:
    packages = json.loads((REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"))["packages"]
    pins = set()
    for path, entry in packages.items():
        if not path:
            continue
        name = path.rsplit("node_modules/", 1)[-1]
        version = entry["version"]
        if (not NPM_NAME_PATTERN.fullmatch(name) or entry.get("name", name) != name
                or not NPM_VERSION_PATTERN.fullmatch(version) or len(name) > 214 or len(version) > 64):
            raise ValueError("Node advisory inventory requires named public registry pins, without aliases")
        pins.add(("npm", name, version))
    for filename in sorted(PYTHON_WHEEL_LOCK_FILES):
        pins.update(
            ("PyPI", name, version)
            for name, version in parse_wheel_lock(REPO_ROOT / PYTHON_WHEEL_LOCK_DIRECTORY / filename).items()
        )
    if not 0 < len(pins) <= MAX_TOOLING_ADVISORY_PINS:
        raise ValueError("Tooling advisory inventory is empty or exceeds the reviewed limit")
    return sorted(pins)


def unique_json_keys(pairs: list[tuple[str, object]]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate advisory response keys")
    return result


def validate_tooling_advisories(errors: list[str]) -> None:
    try:
        pins = release_tooling_pins()
    except (OSError, UnicodeError, KeyError, TypeError, ValueError):
        errors.append("Tooling advisory check could not read the reviewed npm and Python locks")
        return
    queries = [{"package": {"ecosystem": ecosystem, "name": name}, "version": version}
               for ecosystem, name, version in pins]
    connection = http.client.HTTPSConnection("api.osv.dev", timeout=15)
    try:
        connection.request(
            "POST", "/v1/querybatch",
            body=json.dumps({"queries": queries}).encode("ascii"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        response = connection.getresponse()
        if response.status != 200:
            errors.append(f"Tooling advisory registry returned HTTP {response.status}")
            return
        body = response.read(MAX_TOOLING_ADVISORY_BYTES + 1)
        if len(body) > MAX_TOOLING_ADVISORY_BYTES:
            errors.append("Tooling advisory registry response exceeds the size limit")
            return
        report = json.loads(body, object_pairs_hook=unique_json_keys)
    except (OSError, http.client.HTTPException, ValueError, RecursionError):
        errors.append("Tooling advisory registry could not be reached or returned invalid JSON")
        return
    finally:
        connection.close()

    results = report.get("results") if isinstance(report, dict) and report.keys() == {"results"} else None
    if not isinstance(results, list) or len(results) != len(pins):
        errors.append("Tooling advisory registry did not return one result per reviewed pin")
        return
    for (ecosystem, name, version), result in zip(pins, results, strict=True):
        # OSV returns results in request order. An unfinished page is not a clean result.
        if (not isinstance(result, dict) or result.keys() - {"vulns", "next_page_token"}
                or result.get("next_page_token", "") != ""):
            errors.append("Tooling advisory registry returned an invalid or incomplete result")
            return
        advisories = result.get("vulns", [])
        if not isinstance(advisories, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), str)
            or not ADVISORY_ID_PATTERN.fullmatch(item["id"])
            for item in advisories
        ):
            errors.append("Tooling advisory registry returned invalid advisory records")
            return
        if advisories:
            ids = sorted({item["id"] for item in advisories})
            errors.append(f"Review OSV records for {ecosystem} {name}@{version}: {', '.join(ids)}")


def verify(
    ledger_path: Path, *, verify_upstream: bool = False, verify_browser_advisories: bool = False,
    verify_release_advisories: bool = False,
) -> list[str]:
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
    validate_python_wheel_locks(payload, errors)
    validate_node_tooling(payload, errors)
    validate_runtime_components(payload, errors)
    if validate_static_root(payload, errors):
        validate_browser_components(payload, errors)
        validate_clerk_build_notices(payload, errors)
        validate_public_map_data(payload, errors)
    validate_hosted_browser_components(payload, errors)
    if verify_upstream and not errors:
        validate_upstream(payload, errors)
    verified_inventory = not errors
    if (verify_browser_advisories or verify_release_advisories) and verified_inventory:
        validate_browser_advisories(payload, errors)
    if verify_release_advisories and verified_inventory:
        validate_tooling_advisories(errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Workdoe dependency provenance.")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument(
        "--verify-upstream",
        action="store_true",
        help="Download recorded Python source archives and verify their SHA-256 values.",
    )
    parser.add_argument(
        "--check-browser-advisories", action="store_true",
        help="Query npm advisories for direct browser pins and the reviewed Clerk notice pins.",
    )
    parser.add_argument(
        "--check-release-advisories", action="store_true",
        help="Check known browser pins through npm and locked Node/Python tooling pins through OSV.",
    )
    args = parser.parse_args()
    errors = verify(
        args.ledger, verify_upstream=args.verify_upstream, verify_browser_advisories=args.check_browser_advisories,
        verify_release_advisories=args.check_release_advisories,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    suffix = " including upstream Python artifacts" if args.verify_upstream else ""
    if args.check_release_advisories:
        suffix += " with reviewed browser and locked Node/Python advisory checks"
    elif args.check_browser_advisories:
        suffix += " with direct browser and Clerk notice advisory checks"
    print(f"Dependency provenance verified{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
