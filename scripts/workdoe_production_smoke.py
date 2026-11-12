from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from base64 import b64encode
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

SCRIPT_DIR = Path(__file__).resolve().parent
WORKER_DIR = SCRIPT_DIR.parent / "cloudflare" / "worker"
for source_dir in (SCRIPT_DIR, WORKER_DIR):
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

from content_privacy import contains_disallowed_personal_data, is_locality_name
from location_pins import CITY_COORDS, DMV_ZIPS
from prepare_cloudflare_release import (
    VERSIONED_STATIC_ASSET_FILES,
    versioned_asset_release_token,
)
from verify_clerk_browser_delivery import (
    FilePin,
    compare_live_files,
    pinned_archive_files,
)
from verify_dependency_provenance import (
    CLERK_BROWSER_PINS_PATH,
    CLERK_NOTICE_DIRECTORY,
    CLERK_NOTICE_INDEX,
    PINNED_CLERK_BROWSER_COMPONENTS,
    clerk_build_notice_digests,
    parse_clerk_browser_declaration,
    parse_clerk_browser_inventory,
    public_map_data_identity,
    records_by_key,
    unique_json_keys,
)

DEFAULT_DOMAIN = "workdoe.com"
DEFAULT_BASE_URL = "https://workdoe.com"
DEFAULT_TIMEOUT = 8.0
REQUIRED_HEALTH_BINDINGS = {
    "d1",
    "email_sender",
    "email_queue",
    "media_queue",
    "r2_media",
    "write_rate_limiter",
}
ENTRY_MIN_HSTS_AGE = 31_536_000
CLERK_ASSET_MAX_BYTES = 1024 * 1024
CLERK_DEVELOPER_FILE_PROBES = (
    "/__clerk/npm/@clerk/ui@1.41.2/dist/contexts/AcceptedUserInvitations.js.map",
    "/__clerk/npm/@clerk/ui@1.41.2/dist/composed/UserProfile/Account.d.ts",
    "/__clerk/npm/@clerk/ui@1.41.2/dist/server.js",
    "/__clerk/npm/@clerk/ui@1.41.2/dist/common/DevOnly.js",
    "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.native.js",
    "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.mjs",
)
CLERK_ENVIRONMENT_PATH = "/__clerk/v1/environment"
CLERK_ENVIRONMENT_MAX_BYTES = 64 * 1024
CLERK_DISABLED_AUTH_ATTRIBUTES = (
    "password", "phone_number", "username", "passkey", "web3_wallet",
)
PUBLIC_POLICY_MAX_BYTES = 100_000
# Observed public copy, not an approval or a version of user consent.
PUBLIC_POLICY_FINGERPRINTS = {
    "/safety": "5c55d1f74446e7955b72f7277ed2ce7ba9beb44c4f4b45172cf9ea5075d1da49",
    "/privacy": "c199b5b03b3eb80d5ae50a1d05b6a3cc41a9b7c2862e9aa7e9958d4dbbf3e261",
    "/terms": "ac9c96f5aa152a723eb8261f2b08d5787bfa323480af7836336af520a720f854",
}
DISCOVERY_MAX_BYTES = 4096
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
ROBOTS_REVIEWED_EXCLUSIONS = (
    "/account", "/admin", "/api/", "/client/", "/contractor/", "/create-account",
    "/jobs/", "/leads", "/login", "/media/", "/messages", "/post-project",
)
SECURITY_CONTACT_PATH = "/.well-known/security.txt"
SECURITY_CONTACT_EMAIL = "mailto:admin@workdoe.com"
SECURITY_CONTACT_MAX_BYTES = 4096
SHARE_PNG_SIZE = (1200, 630)
SHARE_PNG_HEADER = struct.Struct(">16sII")
PNG_IHDR_PREFIX = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
CLERK_PUBLISHABLE_KEY_PATTERN = re.compile(
    r'data-clerk-publishable-key=["\']([^"\']+)["\']'
)
VERSIONED_STYLESHEET_PATTERN = re.compile(
    r'<link[^>]+href=["\'](/styles\.css\?v=[^"\']+)["\'][^>]*>'
)
CLERK_INVITATION_SMOKE_TICKET = "workdoe-smoke-ticket"
CLERK_INVITATION_SMOKE_PATH = (
    f"/create-account?__clerk_status=sign_up&__clerk_ticket={CLERK_INVITATION_SMOKE_TICKET}"
)
HTTPS_REDIRECT_PATHS = ("/", "/styles.css")
PRIVATE_PROBE_ID = 9_007_199_254_740_991
PRIVATE_PAGE_PATHS = (
    "/account", "/dashboard", "/messages", "/admin", f"/jobs/{PRIVATE_PROBE_ID}",
    f"/client/jobs/{PRIVATE_PROBE_ID}", f"/messages/{PRIVATE_PROBE_ID}",
)
PRIVATE_API_PATHS = (
    "/api/client/jobs", "/api/client/locations", "/api/contractor/leads", "/api/messages/threads",
    f"/api/jobs/{PRIVATE_PROBE_ID}", f"/api/client/jobs/{PRIVATE_PROBE_ID}/requests",
    f"/api/messages/threads/{PRIVATE_PROBE_ID}",
)
PRIVATE_MEDIA_PATHS = (f"/media/jobs/{PRIVATE_PROBE_ID}", f"/media/contractors/{PRIVATE_PROBE_ID}")
PRIVATE_NO_STORE_DIRECTIVES = frozenset({"no-store", "private", "no-cache", "max-age=0"})
PRIVATE_UNCACHED_EDGE_STATUSES = frozenset({"BYPASS", "DYNAMIC", "NONE", "UNKNOWN", "NONE/UNKNOWN"})
CACHED_EDGE_STATUSES = frozenset({"HIT", "REVALIDATED", "STALE", "UPDATING"})
SAMPLE_PROJECT_SMOKE_ID = "demo-01"
SAMPLE_PROJECT_SMOKE_PATH = f"/?job_id={SAMPLE_PROJECT_SMOKE_ID}"
PUBLIC_JOB_TEXT_FIELDS = frozenset(
    {
        "title", "category", "service_group_slug", "service_slug", "service_name",
        "city", "state", "budget", "desired_date", "url", "detail_url",
        "action_label", "sample_label",
    }
)
PUBLIC_JOB_FIELDS = PUBLIC_JOB_TEXT_FIELDS | {
    "id", "license_preference", "photo_count", "lat", "lng", "is_demo",
}
PUBLIC_JOB_ZIP_PINS = {
    state: frozenset((lat, lng) for _, region, lat, lng in DMV_ZIPS.values() if region == state)
    for state in ("DC", "MD", "VA")
}
PUBLIC_JOBS_SMOKE_LIMIT = 50
PUBLIC_SEARCH_SMOKE_QUERY = "z" * 80
PUBLIC_SEARCH_SMOKE_PATH = f"/api/jobs/open?limit=1&q={PUBLIC_SEARCH_SMOKE_QUERY}"
LICENSE_NOTICE_MAX_BYTES = 8192
BUILD_NOTICE_MAX_BYTES = 16 * 1024
BUILD_NOTICE_PREFIX = f"/vendor/{CLERK_NOTICE_DIRECTORY}/"
BUILD_NOTICE_INDEX_PATH = BUILD_NOTICE_PREFIX + CLERK_NOTICE_INDEX.removesuffix(".html")
BUILD_NOTICE_CACHE_PROBES = (
    "/vendor/clerk-notices/notices-1",
    BUILD_NOTICE_PREFIX + "missing-notice-release-probe.txt",
)
VENDOR_LICENSE_PATHS = (
    "/vendor/leaflet/LICENSE",
    "/vendor/leaflet-markercluster/LICENSE",
    "/vendor/tabler-icons/LICENSE",
)
DEPENDENCY_LEDGER = Path(__file__).resolve().parents[1] / "DEPENDENCY_PROVENANCE.json"
PUBLIC_JOBS_ENVELOPE_FIELDS = frozenset({
    "count", "result_count", "demo_count", "live_count", "jobs", "next_cursor",
    "truncated", "viewport", "filters", "view", "location_privacy",
})
PUBLIC_JOBS_DEFAULT_FILTERS = {
    "category": "", "family": "", "service": "", "q": "", "sort": "newest",
}
HEALTH_FIELDS = frozenset({"ok", "service", "domain", "auth_provider", "login_mode", "bindings"})
RELEASE_ENTRY_ASSETS = {
    "/": {"styles.css", "site-dialogs.js"},
    "/login": {"styles.css", "site-dialogs.js", "clerk-entry.js"},
    "/login?embed=1": {"styles.css", "clerk-entry.js"},
    "/create-account": {"styles.css", "site-dialogs.js", "clerk-entry.js"},
    "/create-account?embed=1": {"styles.css", "clerk-entry.js"},
    "/post-project": {"styles.css", "project-composer.js"},
}
RELEASE_EMBEDDED_ENTRY_ROUTES = {"/login?embed=1", "/create-account?embed=1"}
RELEASE_CLERK_ENTRY_ROUTES = {"/login", "/create-account"} | RELEASE_EMBEDDED_ENTRY_ROUTES
CLERK_BROWSER_ENTRY_MODES = {
    "/login": "signin",
    "/create-account": "start",
    "/login?embed=1": "signin",
    "/create-account?embed=1": "start",
}
MAX_RELEASE_HTML_BYTES = 512_000
MAX_AREA_MAP_BYTES = 256 * 1024
PUBLIC_MAP_MODES = ("area", "list")
ISOLATED_CLERK_BETA_COMMIT = "a195fe609403b2c8028837a825e9d259d4f347b9"  # pragma: allowlist secret - reviewed Git commit ID.
ISOLATED_EDIT_BETA_COMMIT = "f4b9488421b03d1bbc4f17c2146a56f9f4c7409f"  # pragma: allowlist secret - reviewed Git commit ID.
ISOLATED_BETA_COMMITS = frozenset({ISOLATED_CLERK_BETA_COMMIT, ISOLATED_EDIT_BETA_COMMIT})
ISOLATED_CLERK_BETA_MAP_MODE = "isolated_clerk_beta_street"
BETA_TILE_ORIGIN = "https://tile.openstreetmap.org"
BETA_TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
AREA_MAP_ASSET_REFERENCES = {
    ("script", "/map.js"),
    ("script", "/vendor/leaflet/leaflet.js"),
    ("link", "/vendor/leaflet/leaflet.css"),
}
BETA_MAP_ASSET_REFERENCES = AREA_MAP_ASSET_REFERENCES | {
    ("link", "/vendor/leaflet-markercluster/MarkerCluster.css"),
    ("link", "/vendor/leaflet-markercluster/MarkerCluster.Default.css"),
    ("script", "/vendor/leaflet-markercluster/leaflet.markercluster.js"),
}
MAX_RELEASE_ASSET_BYTES = 2 * 1024 * 1024
MAX_RELEASE_LEDGER_BYTES = 128 * 1024
FULL_ASSET_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


class ReleaseAssetReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: dict[str, set[str]] = {}
        self.clerk_scripts: list[list[tuple[str, str | None]]] = []
        self.clerk_entries: list[list[tuple[str, str | None]]] = []
        self.has_base = False
        self.has_map = False
        self.list_mode = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and any(key == "src" and value and "/npm/@clerk/" in value for key, value in attrs):
            self.clerk_scripts.append(attrs)
        attributes = dict(attrs)
        if "data-clerk-entry" in attributes:
            self.clerk_entries.append(attrs)
        if tag == "base":
            self.has_base = True
        if tag == "body" and "market-list-only" in (attributes.get("class") or "").split():
            self.list_mode = True
        if attributes.get("id") == "lead-map":
            self.has_map = True
        source = attributes.get("src") if tag == "script" else None
        if tag == "link" and "stylesheet" in (attributes.get("rel") or "").lower().split():
            source = attributes.get("href")
        if source:
            filename = urlparse(source).path.lstrip("/")
            if filename in VERSIONED_STATIC_ASSET_FILES:
                self.assets.setdefault(filename, set()).add(source)

    def has_reviewed_clerk_scripts(self, base_url: str, *, require_integrity: bool = True) -> bool:
        if len(self.clerk_scripts) != len(PINNED_CLERK_BROWSER_COMPONENTS):
            return False
        for attrs, component in zip(self.clerk_scripts, PINNED_CLERK_BROWSER_COMPONENTS.values(), strict=True):
            attributes = dict(attrs)
            path = "/__clerk" + component["script_path"]
            integrity_ok = attributes.get("integrity") == component["script_integrity"] or (
                not require_integrity and "integrity" not in attributes
            )
            if (
                len(attributes) != len(attrs)
                or attributes.get("src") not in {path, check_url(base_url, path)}
                or not integrity_ok
                or attributes.get("crossorigin") != "anonymous"
                or attributes.get("type", "") not in {"", "text/javascript", "application/javascript"}
                or "defer" not in attributes
                or "async" in attributes
                or "nomodule" in attributes
            ):
                return False
        return True

    def has_reviewed_clerk_bootstrap(self, base_url: str, mode: str, *, require_integrity: bool) -> bool:
        if (
            self.has_base
            or len(self.clerk_entries) != 1
            or not self.has_reviewed_clerk_scripts(base_url, require_integrity=require_integrity)
        ):
            return False
        mount = dict(self.clerk_entries[0])
        ui, sdk = (dict(attrs) for attrs in self.clerk_scripts)
        proxy_urls = {"/__clerk", check_url(base_url, "/__clerk")}
        # Clerk encodes the Frontend API hostname followed by a dollar delimiter.
        encoded = b64encode(f"clerk.{DEFAULT_DOMAIN}$".encode("ascii")).decode("ascii")
        keys = {f"pk_live_{encoded}", f"pk_live_{encoded.rstrip('=')}"}
        return (
            len(mount) == len(self.clerk_entries[0])
            and mount.get("data-clerk-mode") == mode
            and mount.get("data-clerk-proxy-url") in proxy_urls
            and sdk.get("data-clerk-proxy-url") in proxy_urls
            and sdk.get("data-clerk-publishable-key") in keys
            and "data-clerk-publishable-key" not in ui
        )


class PublicMapSnapshot(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pending: list[str] | None = None
        self.snapshots: list[str] = []
        self.invalid = False
        self.list_mode = False
        self.results_count = 0
        self.map_panels: list[bool] = []
        self.map_roots = 0
        self.tile_urls: list[str | None] = []
        self.map_attribution = ""
        self.map_assets: set[tuple[str, str]] = set()
        self.invalid_mode = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "body" and "market-list-only" in (attributes.get("class") or "").split():
            self.list_mode = True
        if "data-project-results" in attributes and "hidden" not in attributes:
            self.results_count += 1
        if ("id", "market-map-panel") in attrs:
            self.map_panels.append("hidden" in attributes)
        if attributes.get("id") == "lead-map" or "data-map" in attributes:
            self.map_roots += 1
        if any(key == "data-tile-url" for key, _ in attrs):
            self.tile_urls.append(attributes.get("data-tile-url"))
            self.map_attribution = attributes.get("data-tile-attribution") or ""
            if attributes.get("id") != "lead-map" or len(attributes) != len(attrs):
                self.invalid_mode = True
        if tag in {"script", "link"}:
            source = attributes.get("src" if tag == "script" else "href") or ""
            source_path = source.strip().partition("#")[0].partition("?")[0]
            if source_path.lstrip("/") == "map.js" or source_path.endswith("/map.js") or (
                "vendor/leaflet" in source_path
            ):
                self.map_assets.add((tag, source_path))
                if len(attributes) != len(attrs) or (
                    tag == "link" and attributes.get("rel") != "stylesheet"
                ):
                    self.invalid_mode = True
        if ("id", "map-jobs-data") not in attrs:
            return
        if (
            tag != "script" or len(attributes) != len(attrs)
            or attributes.get("type") != "application/json" or "src" in attributes
        ):
            self.invalid = True
            return
        self.pending = []

    def handle_data(self, data):
        if self.pending is not None:
            self.pending.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.pending is not None:
            self.snapshots.append("".join(self.pending))
            self.pending = None


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


@dataclass
class FetchResult:
    ok: bool
    status_code: int = 0
    headers: dict[str, str] | None = None
    body: str = ""
    error: str = ""
    elapsed_ms: int = 0
    body_bytes: bytes = b""
    header_fields: tuple[tuple[str, str], ...] = ()


@dataclass
class SmokeCheck:
    name: str
    status: str
    summary: str
    url: str = ""
    status_code: int = 0
    elapsed_ms: int = 0
    required: bool = True


def normalized_base_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Smoke-test base URL must be HTTP(S) without embedded credentials.")
    return value.rstrip("/") + "/"


def check_url(base_url: str, path: str) -> str:
    return urljoin(normalized_base_url(base_url), path.lstrip("/"))


def dns_lookup(domain: str = DEFAULT_DOMAIN) -> tuple[bool, list[str], str]:
    try:
        records = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        return False, [], str(exc)
    addresses = sorted({record[4][0] for record in records if record[4]})
    return bool(addresses), addresses, ""


def fetch_url(
    url: str,
    *,
    method: str = "GET",
    timeout: float = DEFAULT_TIMEOUT,
    body_limit: int = 20000,
    follow_redirects: bool = True,
    binary: bool = False,
) -> FetchResult:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "workdoe-production-smoke/1.0"},
    )
    opener = (
        urllib.request.build_opener()
        if follow_redirects
        else urllib.request.build_opener(NoRedirectHandler())
    )
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw_body = response.read(body_limit) if method != "HEAD" and body_limit else b""
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 0))
            return FetchResult(
                ok=200 <= status_code < 400,
                status_code=status_code,
                headers=dict(response.headers.items()),
                body="" if binary else raw_body.decode("utf-8", errors="replace"),
                elapsed_ms=elapsed_ms,
                body_bytes=raw_body if binary else b"",
                header_fields=tuple(response.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        body = ""
        with exc:
            if not binary and method != "HEAD" and body_limit:
                try:
                    body = exc.read(body_limit).decode("utf-8", errors="replace")
                except OSError:
                    body = ""
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return FetchResult(
            ok=False,
            status_code=int(exc.code),
            headers=dict(exc.headers.items()) if exc.headers else {},
            body=body,
            error=str(exc),
            elapsed_ms=elapsed_ms,
            header_fields=tuple(exc.headers.items()) if exc.headers else (),
        )
    except (OSError, urllib.error.URLError, http.client.HTTPException) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        error = "Invalid HTTP response." if isinstance(exc, http.client.HTTPException) else str(exc)
        return FetchResult(ok=False, error=error, elapsed_ms=elapsed_ms)


def https_redirect_check(domain: str, timeout: float) -> SmokeCheck:
    failures = []
    elapsed_ms = 0
    redirect_statuses = []
    redirect_hosts = (domain,) if domain.startswith("www.") else (domain, f"www.{domain}")
    for host in redirect_hosts:
        for path in HTTPS_REDIRECT_PATHS:
            http_url = f"http://{host}{path}"
            expected_location = f"https://{host}{path}"
            result = fetch_url(
                http_url,
                method="HEAD",
                timeout=timeout,
                follow_redirects=False,
            )
            elapsed_ms += result.elapsed_ms
            location = header_value(result.headers, "Location")
            if result.status_code not in {301, 302, 307, 308} or location != expected_location:
                destination = "missing" if not location else "present but not verified"
                failures.append(
                    f"{host}{path} returned HTTP {result.status_code or 'error'} "
                    f"with Location {destination}"
                )
            else:
                redirect_statuses.append(result.status_code)
    if failures:
        return SmokeCheck(
            name="http-to-https",
            status="failed",
            summary="HTTP does not redirect consistently to HTTPS: " + "; ".join(failures),
            url=f"http://{domain}/",
            elapsed_ms=elapsed_ms,
        )
    return SmokeCheck(
        name="http-to-https",
        status="ready",
        summary="Apex and www HTTP entry and static asset requests redirect directly to HTTPS.",
        url=f"http://{domain}/",
        status_code=redirect_statuses[0],
        elapsed_ms=elapsed_ms,
    )


def header_value(headers: dict[str, str] | None, name: str) -> str:
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return value
    return ""


def cache_control_directives(result: FetchResult) -> set[str]:
    return {part.strip().lower() for part in header_value(result.headers, "Cache-Control").split(",")}


def response_header_values(result: FetchResult, name: str) -> tuple[str, ...]:
    return tuple(
        value for key, value in (result.header_fields or (result.headers or {}).items())
        if key.lower() == name.lower()
    )


def unambiguous_private_no_store(fields: tuple[str, ...]) -> bool:
    if len(fields) != 1:
        return False
    parts = [part.strip(" \t").lower() for part in fields[0].split(",")]
    return len(parts) == len(set(parts)) and "no-store" in parts and PRIVATE_NO_STORE_DIRECTIVES.issuperset(parts)


def redirect_privacy_check(domain: str, timeout: float) -> SmokeCheck:
    redirect_hosts = (domain,) if domain.startswith("www.") else (domain, f"www.{domain}")
    probes = [
        (f"{host}/create-account", f"http://{host}{CLERK_INVITATION_SMOKE_PATH}",
         f"https://{host}{CLERK_INVITATION_SMOKE_PATH}")
        for host in redirect_hosts
    ]
    probes.append((f"{domain}/static/styles.css", f"https://{domain}/static/styles.css?probe=synthetic",
                   f"https://{domain}/styles.css?probe=synthetic"))
    failures = []
    elapsed_ms = 0
    for label, source, expected in probes:
        result = fetch_url(source, method="HEAD", timeout=timeout, body_limit=0, follow_redirects=False)
        elapsed_ms += result.elapsed_ms
        issues = []
        if result.status_code not in {301, 302, 307, 308} or header_value(result.headers, "Location") != expected:
            issues.append("wrong status or destination")
        cache = cache_control_directives(result)
        if "no-store" not in cache or "public" in cache:
            issues.append("missing unambiguous no-store")
        if header_value(result.headers, "Referrer-Policy").strip().lower() != "no-referrer":
            issues.append("missing no-referrer")
        edge_status = header_value(result.headers, "CF-Cache-Status").strip().upper()
        if header_value(result.headers, "Age") or edge_status in CACHED_EDGE_STATUSES:
            issues.append("cached response")
        if issues:
            failures.append(f"{label}: {', '.join(issues)}")
    return SmokeCheck(
        name="redirect-privacy",
        status="failed" if failures else "ready",
        summary="; ".join(failures) if failures else "Query-bearing redirects preserve their destinations without caching or forwarding a referrer.",
        url=f"https://{domain}/",
        elapsed_ms=elapsed_ms,
    )


def anonymous_private_routes_check(base_url: str, timeout: float) -> SmokeCheck:
    failures = []
    elapsed_ms = 0
    probes = [
        ("GET", path) for path in (*PRIVATE_PAGE_PATHS, *PRIVATE_API_PATHS, *PRIVATE_MEDIA_PATHS)
    ] + [("HEAD", path) for path in PRIVATE_MEDIA_PATHS]
    for method, path in probes:
        result = fetch_url(
            check_url(base_url, path), method=method, timeout=timeout, body_limit=0, follow_redirects=False,
        )
        elapsed_ms += result.elapsed_ms
        label = f"{method} {path}"
        location = response_header_values(result, "Location")
        if path in PRIVATE_PAGE_PATHS:
            if result.status_code not in {302, 303, 307} or location != (f"/login?next={path}",):
                failures.append(f"{label} did not redirect directly to its sign-in entry")
        elif result.status_code != 401 or location:
            failures.append(f"{label} did not directly refuse anonymous access with HTTP 401")
        if not unambiguous_private_no_store(response_header_values(result, "Cache-Control")):
            failures.append(f"{label} did not declare unambiguous no-store")
        for header in ("CDN-Cache-Control", "Cloudflare-CDN-Cache-Control"):
            override = response_header_values(result, header)
            if override and not unambiguous_private_no_store(override):
                failures.append(f"{label} indicated a conflicting CDN cache policy")
                break
        edge = response_header_values(result, "CF-Cache-Status")
        if response_header_values(result, "Age") or (
            edge and (len(edge) != 1 or edge[0].strip().upper() not in PRIVATE_UNCACHED_EDGE_STATUSES)
        ):
            failures.append(f"{label} indicated caching or ambiguous edge status")
    return SmokeCheck(
        name="anonymous-private-routes",
        status="failed" if failures else "ready",
        summary="; ".join(failures) if failures else (
            f"{len(probes)} signed-out probes refused access to private pages, APIs, and photo routes without caching."
        ),
        elapsed_ms=elapsed_ms,
    )


def browser_vendor_notice_digests(ledger: dict) -> dict[str, str]:
    records = ledger.get("browser_components")
    if not isinstance(records, list):
        raise TypeError("Notice ledger entries must be a list.")
    expected = {}
    for record in records:
        source = record.get("retained_license") if isinstance(record, dict) else None
        digest = record.get("retained_license_sha256") if isinstance(record, dict) else None
        if not isinstance(source, str) or not source.startswith("workdoe/static/"):
            raise ValueError("Unexpected notice ledger path.")
        path = source.removeprefix("workdoe/static")
        if path in expected or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Unexpected notice ledger entry.")
        expected[path] = digest
    if expected.keys() != set(VENDOR_LICENSE_PATHS):
        raise ValueError("Missing or unexpected notice ledger entries.")
    return expected


def browser_license_notices_check(
    base_url: str, timeout: float, *, reviewed_ledger: dict | None = None,
) -> SmokeCheck:
    name = "browser-license-notices"
    try:
        ledger = reviewed_ledger if reviewed_ledger is not None else json.loads(
            DEPENDENCY_LEDGER.read_text(encoding="utf-8"),
        )
        if not isinstance(ledger, dict):
            raise TypeError("Expected a notice ledger object.")
        expected = browser_vendor_notice_digests(ledger)
    except (OSError, TypeError, ValueError, RecursionError):
        return SmokeCheck(name, "failed", "Could not read the reviewed browser notice paths and hashes.")

    hosted = {
        f"/__clerk/npm/{component['package']}@{component['version']}/LICENSE":
        component["retained_license_sha256"]
        for component in PINNED_CLERK_BROWSER_COMPONENTS.values()
    }
    failures = []
    elapsed_ms = 0
    for path, digest in (expected | hosted).items():
        result = fetch_url(
            check_url(base_url, path), timeout=timeout, body_limit=LICENSE_NOTICE_MAX_BYTES + 1,
            follow_redirects=False, binary=True,
        )
        elapsed_ms += result.elapsed_ms
        if result.status_code != 200:
            failures.append(f"{path} did not return a direct HTTP 200")
        elif len(result.body_bytes) > LICENSE_NOTICE_MAX_BYTES:
            failures.append(f"{path} exceeded the notice size limit")
        else:
            body = result.body_bytes
            if path in hosted:
                mime = header_value(result.headers, "Content-Type").partition(";")[0].strip().lower()
                if mime != "text/plain":
                    failures.append(f"{path} did not return a plain-text notice")
            else:
                body = body.replace(b"\r\n", b"\n")
            if hashlib.sha256(body).hexdigest() != digest:
                failures.append(f"{path} did not match the reviewed license hash")
    return SmokeCheck(
        name=name,
        status="failed" if failures else "ready",
        summary="; ".join(failures) if failures else "All five vendored and Clerk browser notices match their reviewed hashes.",
        elapsed_ms=elapsed_ms,
    )


def parse_json_body(result: FetchResult) -> tuple[dict | None, str]:
    try:
        payload = json.loads(result.body or "{}")
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "JSON body is not an object."
    return payload, ""


def response_check(
    name: str,
    url: str,
    result: FetchResult,
    *,
    expected_summary: str,
    required: bool = True,
) -> SmokeCheck:
    if result.ok:
        return SmokeCheck(
            name=name,
            status="ready",
            summary=expected_summary,
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
            required=required,
        )
    detail = result.error or f"HTTP {result.status_code}"
    return SmokeCheck(
        name=name,
        status="failed" if required else "warning",
        summary=f"{url} failed: {detail}",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
        required=required,
    )


def health_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, "/health")
    result = fetch_url(url, timeout=timeout, follow_redirects=False)
    if not result.ok:
        return response_check(
            "health-json",
            url,
            result,
            expected_summary="Health endpoint returned HTTP success.",
        )
    if header_value(result.headers, "X-Workdoe-Mode"):
        return SmokeCheck(
            name="health-json",
            status="failed",
            summary="Worker is responding, but the marketplace is not in normal operation.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    payload, error = parse_json_body(result)
    if (
        error or not payload or payload.keys() != HEALTH_FIELDS
        or payload["ok"] is not True or payload["service"] != "workdoe-cloudflare-worker"
        or not isinstance(payload["domain"], str)
        or not re.fullmatch(r"[a-z0-9.-]{1,253}", payload["domain"])
        or payload["auth_provider"] != "clerk"
        or payload["login_mode"] != "same_domain_email_code"
        or result.status_code != 200
        or header_value(result.headers, "Content-Type").split(";", 1)[0].strip().lower() != "application/json"
    ):
        return SmokeCheck(
            name="health-json",
            status="failed",
            summary="Health endpoint did not return the reviewed Workdoe liveness response.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    bindings = payload.get("bindings") if isinstance(payload.get("bindings"), dict) else {}
    missing_bindings = sorted(
        binding for binding in REQUIRED_HEALTH_BINDINGS if bindings.get(binding) is not True
    )
    if missing_bindings or bindings.keys() != REQUIRED_HEALTH_BINDINGS:
        return SmokeCheck(
            name="health-json",
            status="failed",
            summary=(
                "Health endpoint is missing required bindings: " + ", ".join(missing_bindings)
                if missing_bindings else "Health endpoint contains unreviewed binding fields."
            ),
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="health-json",
        status="ready",
        summary="Worker liveness and binding presence passed; dependency operations are separate.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def public_job_contract_error(job: object) -> str:
    if not isinstance(job, dict):
        return "contains a non-object job record"
    is_demo = job.get("is_demo")
    if type(is_demo) is not bool:
        return "contains a record without a boolean sample flag"
    expected_fields = PUBLIC_JOB_FIELDS | ({"description"} if is_demo else set())
    # The deployed release predates taxonomy search terms in public responses.
    if "search_terms" in job:
        expected_fields = expected_fields | {"search_terms"}
    if job.keys() != expected_fields:
        # Do not echo unexpected keys or any row data into release logs.
        return "does not match the reviewed public job fields"
    text_fields = PUBLIC_JOB_TEXT_FIELDS | ({"description"} if is_demo else set())
    if not all(isinstance(job[field], str) for field in text_fields):
        return "contains a non-text value in a public text field"
    search_terms = job.get("search_terms", [])
    if not isinstance(search_terms, list) or not all(isinstance(term, str) for term in search_terms):
        return "contains invalid search terms"
    if type(job["photo_count"]) is not int or job["photo_count"] < 0 or (
        type(job["license_preference"]) is not bool
    ):
        return "contains invalid photo or preference metadata"
    if is_demo or job["lat"] is not None or job["lng"] is not None:
        for field, maximum in (("lat", 90), ("lng", 180)):
            if type(job[field]) not in (int, float) or not -maximum <= job[field] <= maximum:
                return "contains invalid map coordinates"
    job_id = job["id"]
    if is_demo:
        if not isinstance(job_id, str) or not re.fullmatch(r"demo-[0-9]+", job_id):
            return "contains an invalid sample project ID"
        if job["desired_date"]:
            return "exposes fixed desired dates for demonstration rows"
        if job["sample_label"] != "Sample project":
            return "contains a sample project without its sample label"
    elif type(job_id) is not int or job_id < 1 or job["sample_label"] != "Open project":
        return "contains invalid live project metadata"
    else:
        if job["state"] not in PUBLIC_JOB_ZIP_PINS or not is_locality_name(job["city"]):
            return "contains a live project with invalid public locality text"
        if contains_disallowed_personal_data(
            [job[field] for field in text_fields] + search_terms
        ):
            return "contains apparent direct contact or street-address text in a live project"
        if job["lat"] is not None:
            pin = (job["lat"], job["lng"])
            city_key = f"{job['city'].strip().lower()} {job['state'].lower()}"
            # ZIP pins are checked by state because the public payload deliberately omits ZIP.
            if pin != CITY_COORDS.get(city_key) and pin not in PUBLIC_JOB_ZIP_PINS[job["state"]]:
                return "contains a live map pin outside the reviewed city and ZIP catalog"
    return ""


def public_jobs_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, f"/api/jobs/open?limit={PUBLIC_JOBS_SMOKE_LIMIT}")
    result = fetch_url(url, timeout=timeout, body_limit=200000, follow_redirects=False)
    if not result.ok:
        return response_check(
            "public-jobs-api",
            url,
            result,
            expected_summary="Public jobs API returned HTTP success.",
        )
    payload, error = parse_json_body(result)
    if error or not payload:
        return SmokeCheck(
            name="public-jobs-api",
            status="failed",
            summary=f"Public jobs API did not return valid JSON: {error}",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    contract_error = public_jobs_contract_error(payload, result)
    if contract_error:
        return SmokeCheck(
            name="public-jobs-api",
            status="failed",
            summary=f"Public jobs API {contract_error}.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    jobs = payload["jobs"]
    mapped_count = sum(job["lat"] is not None for job in jobs)
    return SmokeCheck(
        name="public-jobs-api",
        status="ready",
        summary=(
            f"Public jobs API returned {len(jobs)} reviewed projects "
            f"({payload['live_count']} live, {payload['demo_count']} sample, {mapped_count} mapped); "
            "live pins match the reviewed locality catalog."
        ),
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def unique_snapshot_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("Duplicate map snapshot fields.")
    return fields


@dataclass(frozen=True)
class ReviewedAreaMap:
    path: str
    digest: str


def public_map_mode_error(
    parser: PublicMapSnapshot, result: FetchResult, mode: str, area_map: ReviewedAreaMap | None,
) -> str:
    if parser.invalid_mode or parser.results_count != 1:
        return "does not contain the expected public project results and map configuration"
    if mode == "list":
        if (
            not parser.list_mode or parser.map_panels not in ([], [True]) or parser.tile_urls or parser.map_assets
            or (not parser.map_panels and parser.map_roots)
        ):
            return "does not render list-only mode without map assets"
    elif mode == ISOLATED_CLERK_BETA_MAP_MODE:
        if (
            parser.list_mode or parser.map_panels != [False] or parser.map_roots != 1
            or parser.tile_urls != [BETA_TILE_ORIGIN + "/{z}/{x}/{y}.png"]
            or parser.map_attribution != BETA_TILE_ATTRIBUTION
            or parser.map_assets != BETA_MAP_ASSET_REFERENCES
        ):
            return "does not match the isolated beta's existing street map and source credit"
    elif (
        area_map is None or parser.list_mode or parser.map_panels != [False]
        or parser.tile_urls != [area_map.path]
        or "U.S. Census Bureau" not in parser.map_attribution
        or not AREA_MAP_ASSET_REFERENCES <= parser.map_assets
    ):
        return "does not render the reviewed first-party area map and its source credit"
    image_sources = [
        fields[1:]
        for directive in header_value(result.headers, "Content-Security-Policy").split(";")
        if (fields := directive.split()) and fields[0].lower() == "img-src"
    ]
    required_image_sources = {"'self'"}
    if mode == ISOLATED_CLERK_BETA_MAP_MODE:
        required_image_sources.add(BETA_TILE_ORIGIN)
    if (
        len(image_sources) != 1 or not required_image_sources <= set(image_sources[0])
        or not set(image_sources[0]) <= required_image_sources | {"data:", "https://img.clerk.com"}
    ):
        return "does not restrict image sources to the reviewed map and auth sources"
    return ""


def public_map_snapshot_error(
    result: FetchResult, *, mode: str | None = None, area_map: ReviewedAreaMap | None = None,
) -> str:
    if (
        not result.ok or result.status_code != 200
        or header_value(result.headers, "Content-Type").split(";", 1)[0].strip().lower() != "text/html"
        or not 0 < len(result.body_bytes) <= MAX_RELEASE_HTML_BYTES
    ):
        return "did not return bounded public HTML"
    parser = PublicMapSnapshot()
    try:
        parser.feed(result.body_bytes.decode("utf-8"))
        parser.close()
        if mode is not None and (error := public_map_mode_error(parser, result, mode, area_map)):
            return error
        if mode == "list" and not parser.map_panels:
            if parser.invalid or parser.pending is not None or parser.snapshots:
                return "contains a map snapshot without a map panel in list-only mode"
            return ""
        if parser.invalid or parser.pending is not None or len(parser.snapshots) != 1:
            return "does not contain exactly one inert map snapshot"
        jobs = json.loads(parser.snapshots[0], object_pairs_hook=unique_snapshot_fields)
    except (UnicodeError, ValueError, RecursionError):
        return "contains an invalid map snapshot"
    if not isinstance(jobs, list) or len(jobs) > PUBLIC_JOBS_SMOKE_LIMIT:
        return "contains an invalid or unbounded map snapshot"
    for job in jobs:
        if error := public_job_contract_error(job):
            return "has a map snapshot that " + error
    return ""


def public_map_snapshot_check(
    base_url: str, timeout: float, *, mode: str | None = None, area_map: ReviewedAreaMap | None = None,
) -> SmokeCheck:
    if mode not in (None, *PUBLIC_MAP_MODES, ISOLATED_CLERK_BETA_MAP_MODE) or (mode == "area") != (area_map is not None):
        raise ValueError("Expected a supported public map mode and, for area mode, a reviewed asset.")
    elapsed_ms = 0
    for path in ("/", "/login"):
        url = check_url(base_url, path)
        result = fetch_url(
            url, timeout=timeout, body_limit=MAX_RELEASE_HTML_BYTES + 1,
            follow_redirects=False, binary=True,
        )
        elapsed_ms += result.elapsed_ms
        if error := public_map_snapshot_error(result, mode=mode, area_map=area_map):
            return SmokeCheck(
                name="public-map-snapshots", status="failed",
                summary=f"Public entry {path} {error}.",
                url=url, status_code=result.status_code, elapsed_ms=elapsed_ms,
            )
    summary = "Home and sign-in map snapshots match the public jobs privacy contract."
    if area_map is not None:
        url = check_url(base_url, area_map.path)
        asset = fetch_url(
            url, timeout=timeout, body_limit=MAX_AREA_MAP_BYTES + 1,
            follow_redirects=False, binary=True,
        )
        elapsed_ms += asset.elapsed_ms
        if (
            not asset.ok or asset.status_code != 200
            or not 0 < len(asset.body_bytes) <= MAX_AREA_MAP_BYTES
            or hashlib.sha256(asset.body_bytes).hexdigest() != area_map.digest
            or header_value(asset.headers, "Content-Type").split(";", 1)[0].strip().lower() != "application/geo+json"
            or header_value(asset.headers, "X-Content-Type-Options").lower() != "nosniff"
            or not {"public", "max-age=31556952", "immutable"} <= cache_control_directives(asset)
            or {"private", "no-store", "no-cache"} & cache_control_directives(asset)
        ):
            return SmokeCheck(
                "public-map-snapshots", "failed",
                "The served area map asset did not match the reviewed bytes, MIME, or cache contract.",
                url=url, status_code=asset.status_code, elapsed_ms=elapsed_ms,
            )
        summary += " Both render the reviewed area map, and the exact immutable Census asset is available."
    elif mode == "list":
        summary = "Home and sign-in render list-only mode without map assets or external tile permissions."
    elif mode == ISOLATED_CLERK_BETA_MAP_MODE:
        summary += " Both retain the isolated beta's existing street map configuration."
    return SmokeCheck(
        name="public-map-snapshots", status="ready",
        summary=summary,
        url=check_url(base_url, "/"), status_code=200, elapsed_ms=elapsed_ms,
    )


def public_search_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, PUBLIC_SEARCH_SMOKE_PATH)
    result = fetch_url(url, timeout=timeout, body_limit=32_768, follow_redirects=False)
    problem = ""
    if not result.ok:
        problem = f"returned HTTP {result.status_code}" if result.status_code is not None else "could not be reached"
    else:
        payload, _ = parse_json_body(result)
        if payload is None:
            problem = "did not return valid JSON"
        else:
            problem = public_jobs_contract_error(payload, result, query=PUBLIC_SEARCH_SMOKE_QUERY, limit=1)
            if not problem and any(
                not any(PUBLIC_SEARCH_SMOKE_QUERY in job[field].lower() for field in ("title", "city", "state", "category"))
                for job in payload["jobs"]
            ):
                problem = "returned unrelated results for the synthetic query"
    return SmokeCheck(
        name="public-project-search",
        status="failed" if problem else "ready",
        summary=f"Public project search {problem}." if problem else "Public project search accepts an 80-character filter.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def public_jobs_contract_error(
    payload: dict, result: FetchResult, *, query: str = "", limit: int = PUBLIC_JOBS_SMOKE_LIMIT,
) -> str:
    content_type = header_value(result.headers, "Content-Type").split(";", 1)[0].strip().lower()
    if result.status_code != 200 or content_type != "application/json" or "no-store" not in cache_control_directives(result):
        return "did not return a 200 JSON response with no-store"
    # The current live release predates mapped_count; both reviewed envelopes are accepted.
    if payload.keys() - {"mapped_count"} != PUBLIC_JOBS_ENVELOPE_FIELDS:
        return "does not match the reviewed response fields"
    jobs = payload["jobs"]
    if (
        not isinstance(jobs, list) or len(jobs) > limit
        or any(type(payload[key]) is not int or payload[key] != len(jobs) for key in ("count", "result_count"))
    ):
        return "count does not match its bounded jobs list"
    if payload["location_privacy"] != "Approximate city or ZIP-level pins only.":
        return "is missing the reviewed approximate-location privacy notice"
    expected_filters = PUBLIC_JOBS_DEFAULT_FILTERS | {"q": query}
    if payload["view"] != "all" or payload["viewport"] is not None or payload["filters"] != expected_filters:
        return "contains unexpected filters or viewport"
    for job in jobs:
        if error := public_job_contract_error(job):
            return error
    sample_count = sum(job["is_demo"] for job in jobs)
    counts = {"demo_count": sample_count, "live_count": len(jobs) - sample_count}
    if any(type(payload[key]) is not int or payload[key] != count for key, count in counts.items()):
        return "has inconsistent live or sample counts"
    if "mapped_count" in payload and (
        type(payload["mapped_count"]) is not int
        or payload["mapped_count"] != sum(job["lat"] is not None for job in jobs)
    ):
        return "mapped count does not match its coordinate pairs"
    cursor = payload["next_cursor"]
    if (
        type(payload["truncated"]) is not bool or not isinstance(cursor, str)
        or payload["truncated"] != bool(cursor)
        or cursor and (sample_count or len(jobs) != limit or not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", cursor))
    ):
        return "has inconsistent pagination metadata"
    return ""


class SampleDetailSnapshot(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.selected = 0
        self.article_depth = 0
        self.inert_tags: list[str] = []
        self.text: list[str] = []
        self.has_date = False
        self.has_controls = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.inert_tags.append(tag)
        if self.inert_tags:
            return
        attributes = dict(attrs)
        if tag == "article":
            if self.article_depth:
                self.article_depth += 1
            elif (
                "data-project-detail-content" in attributes
                and attributes.get("data-job-id") == SAMPLE_PROJECT_SMOKE_ID
                and "hidden" not in attributes and attributes.get("aria-hidden") != "true"
            ):
                self.selected += 1
                self.article_depth = 1
        if self.article_depth:
            if tag == "time":
                self.has_date = True
            if tag in {"a", "button", "form", "input", "select", "textarea"} or attributes.get("role") in {"button", "link"}:
                self.has_controls = True

    def handle_endtag(self, tag):
        if self.inert_tags:
            if self.inert_tags[-1] == tag:
                self.inert_tags.pop()
        elif self.article_depth and tag == "article":
            self.article_depth -= 1

    def handle_data(self, data):
        if self.article_depth and not self.inert_tags:
            self.text.append(data)

    def failure(self) -> str:
        if self.selected != 1 or self.article_depth or self.inert_tags:
            return "The reviewed sample project detail panel is missing, ambiguous, or incomplete."
        content = " ".join(" ".join(self.text).split())
        failures = []
        if self.has_date or "Sample timing" not in content:
            failures.append("sample timing may present a fixed fixture date as a live request")
        if "Demonstration project" not in content or "This sample does not accept bids." not in content:
            failures.append("the sample label or no-bids notice is missing")
        if self.has_controls:
            failures.append("the view-only sample contains an interactive action")
        return "Sample detail: " + "; ".join(failures) + "." if failures else ""


def public_sample_presentation_check(base_url: str, timeout: float) -> SmokeCheck:
    """Verify the server-rendered detail for a view-only demonstration project."""
    name = "public-sample-presentation"
    url = check_url(base_url, SAMPLE_PROJECT_SMOKE_PATH)
    result = fetch_url(
        url, timeout=timeout, body_limit=MAX_RELEASE_HTML_BYTES + 1, follow_redirects=False, binary=True,
    )
    mime = header_value(result.headers, "Content-Type").partition(";")[0].strip().lower()
    if not result.ok or result.status_code != 200:
        failure = f"Sample project detail did not return direct HTTP 200 (received {result.status_code or 'an error'})."
    elif mime != "text/html" or len(result.body_bytes) > MAX_RELEASE_HTML_BYTES:
        failure = "Sample project detail did not return bounded HTML."
    else:
        try:
            parser = SampleDetailSnapshot()
            parser.feed(result.body_bytes.decode("utf-8"))
            parser.close()
            failure = parser.failure()
        except ValueError:
            failure = "Sample project detail did not contain readable UTF-8 HTML."
    return SmokeCheck(
        name=name,
        status="failed" if failure else "ready",
        summary=failure or "Demonstration detail is labeled as a view-only sample without response controls.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def entry_hsts_valid(value: str) -> bool:
    directives = [part.strip().lower() for part in value.split(";") if part.strip()]
    fields = {part.partition("=")[0].strip(): part for part in directives}
    if len(fields) != len(directives) or fields.keys() - {"max-age", "includesubdomains", "preload"}:
        return False
    if fields.get("includesubdomains") != "includesubdomains" or fields.get("preload", "preload") != "preload":
        return False
    match = re.fullmatch(r'max-age\s*=\s*(?:([0-9]{1,10})|"([0-9]{1,10})")', fields.get("max-age", ""))
    return bool(match and int(match[1] or match[2]) >= ENTRY_MIN_HSTS_AGE)


def entry_csp_valid(value: str) -> bool:
    directives = [part.split() for part in value.split(";") if part.strip()]
    sources = {part[0].lower(): part[1:] for part in directives}
    return (
        "," not in value and len(sources) == len(directives)
        and sources.get("default-src") == ["'self'"]
        and sources.get("frame-ancestors") == ["'none'"]
        and sources.get("base-uri") == ["'self'"]
        and sources.get("object-src") == ["'none'"]
        and sources.get("form-action") == ["'self'"]
    )


def entry_permissions_valid(value: str) -> bool:
    directives = [part.partition("=") for part in value.split(",")]
    policies = {name.strip(): policy.strip() for name, sep, policy in directives if sep}
    return len(directives) == 3 and policies == dict.fromkeys(("geolocation", "microphone", "camera"), "()")


def entry_security_errors(result: FetchResult, *, require_origin_referrer: bool) -> list[str]:
    values: dict[str, list[str]] = {}
    for name, value in result.header_fields or tuple((result.headers or {}).items()):
        values.setdefault(name.lower(), []).append(value.strip(" \t"))
    allowed_referrers = {"strict-origin"}
    if not require_origin_referrer:
        allowed_referrers.add("strict-origin-when-cross-origin")
    checks = {
        "Strict-Transport-Security": entry_hsts_valid,
        "Content-Security-Policy": entry_csp_valid,
        "X-Content-Type-Options": lambda value: value.lower() == "nosniff",
        "X-Frame-Options": lambda value: value.upper() == "DENY",
        "Permissions-Policy": entry_permissions_valid,
        "Referrer-Policy": lambda value: value.lower() in allowed_referrers,
        "Content-Type": lambda value: "," not in value and value.partition(";")[0].strip().lower() == "text/html",
    }
    errors = []
    for header, valid in checks.items():
        field = values.get(header.lower(), [])
        if len(field) != 1 or not re.fullmatch(r"[\t -~]+", field[0]) or not valid(field[0]):
            errors.append(header)
    return errors


def security_headers_check(base_url: str, timeout: float, *, require_origin_referrer: bool = False) -> SmokeCheck:
    url = check_url(base_url, "/start")
    elapsed_ms = 0
    for method in ("GET", "HEAD"):
        result = fetch_url(url, method=method, timeout=timeout, body_limit=0, follow_redirects=False)
        elapsed_ms += result.elapsed_ms
        if not result.ok or result.status_code != 200:
            detail = f"{method} did not return HTTP 200 directly."
        else:
            errors = entry_security_errors(result, require_origin_referrer=require_origin_referrer)
            if not errors:
                continue
            detail = f"{method} has missing, ambiguous or unsafe headers: " + ", ".join(errors) + "."
        return SmokeCheck("entry-security-headers", "failed", detail, url, result.status_code, elapsed_ms)
    return SmokeCheck(
        name="entry-security-headers",
        status="ready",
        summary="Entry shell returned the expected privacy and security headers on GET and HEAD.",
        url=url,
        status_code=200,
        elapsed_ms=elapsed_ms,
    )


def static_asset_cache_check(base_url: str, timeout: float) -> SmokeCheck:
    page_url = check_url(base_url, "/")
    page = fetch_url(page_url, timeout=timeout, body_limit=200000)
    if not page.ok:
        return response_check(
            "static-asset-cache",
            page_url,
            page,
            expected_summary="Homepage returned HTTP success.",
        )
    stylesheet_match = VERSIONED_STYLESHEET_PATTERN.search(page.body)
    if not stylesheet_match:
        return SmokeCheck(
            name="static-asset-cache",
            status="failed",
            summary="Homepage is missing its versioned Workdoe stylesheet URL.",
            url=page_url,
            status_code=page.status_code,
            elapsed_ms=page.elapsed_ms,
        )
    stylesheet_url = check_url(base_url, stylesheet_match.group(1))
    stylesheet = fetch_url(stylesheet_url, method="HEAD", timeout=timeout)
    if not stylesheet.ok:
        return response_check(
            "static-asset-cache",
            stylesheet_url,
            stylesheet,
            expected_summary="Versioned Workdoe stylesheet returned HTTP success.",
        )
    cache_control = header_value(stylesheet.headers, "Cache-Control").lower()
    required_cache_directives = ("public", "max-age=31556952", "immutable")
    missing_directives = [
        directive for directive in required_cache_directives if directive not in cache_control
    ]
    no_sniff = header_value(stylesheet.headers, "X-Content-Type-Options").lower()
    if missing_directives or no_sniff != "nosniff":
        details = []
        if missing_directives:
            details.append("missing " + ", ".join(missing_directives))
        if no_sniff != "nosniff":
            details.append("missing X-Content-Type-Options: nosniff")
        return SmokeCheck(
            name="static-asset-cache",
            status="failed",
            summary="Versioned static-asset policy is incomplete: " + "; ".join(details),
            url=stylesheet_url,
            status_code=stylesheet.status_code,
            elapsed_ms=page.elapsed_ms + stylesheet.elapsed_ms,
        )
    return SmokeCheck(
        name="static-asset-cache",
        status="ready",
        summary="Versioned Workdoe assets use immutable browser caching and MIME protection.",
        url=stylesheet_url,
        status_code=stylesheet.status_code,
        elapsed_ms=page.elapsed_ms + stylesheet.elapsed_ms,
    )


def committed_release_reader(repo_root: Path, commit: str) -> Callable[[str, int], bytes]:
    if not FULL_ASSET_COMMIT.fullmatch(commit):
        raise ValueError("Expected a full Git commit ID.")

    def git_read(*args: str) -> bytes:
        return subprocess.run(
            ["git", "--no-lazy-fetch", "--no-replace-objects", *args],
            cwd=repo_root, timeout=5, check=True, capture_output=True,
        ).stdout

    if git_read("rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}").strip() != commit.encode("ascii"):
        raise ValueError("The reviewed ID must resolve to that exact Git commit.")
    def read_blob(filename: str, limit: int) -> bytes:
        object_name = f"{commit}:{filename}"
        size = int(git_read("cat-file", "-s", object_name).strip())
        if not 0 < size <= limit:
            raise ValueError("A reviewed asset was empty or exceeded the size limit.")
        content = git_read("cat-file", "blob", object_name)
        if len(content) != size:
            raise ValueError("Could not read the complete reviewed asset.")
        return content

    return read_blob


def versioned_assets_from_commit(read_blob: Callable[[str, int], bytes]) -> dict[str, bytes]:
    return {
        filename: read_blob(f"workdoe/static/{filename}", MAX_RELEASE_ASSET_BYTES)
        for filename in VERSIONED_STATIC_ASSET_FILES
    }


def read_committed_assets(repo_root: Path, commit: str) -> dict[str, bytes]:
    return versioned_assets_from_commit(committed_release_reader(repo_root, commit))


@dataclass(frozen=True)
class ReviewedSmokeRelease:
    assets: dict[str, bytes]
    ledger: dict
    area_map: ReviewedAreaMap | None = None


def read_reviewed_area_map(ledger: dict, read_blob: Callable[[str, int], bytes]) -> ReviewedAreaMap:
    filename, digest = public_map_data_identity(ledger)
    asset = read_blob(filename, MAX_AREA_MAP_BYTES)
    if hashlib.sha256(asset).hexdigest() != digest:
        raise ValueError("The committed Census asset does not match the committed ledger.")
    return ReviewedAreaMap("/" + Path(filename).name, digest)


def read_committed_public_notice_ledger(
    read_blob: Callable[[str, int], bytes], *, include_build_notices: bool,
) -> dict:
    ledger = json.loads(read_blob("DEPENDENCY_PROVENANCE.json", MAX_RELEASE_LEDGER_BYTES))
    if not isinstance(ledger, dict):
        raise TypeError("Expected a dependency ledger object.")
    errors: list[str] = []
    hosted = records_by_key(ledger.get("hosted_browser_components"), "name", "Hosted browser inventory", errors)
    sdk_fields = ("package", "version", "license", "script_path")
    if errors or hosted.keys() != PINNED_CLERK_BROWSER_COMPONENTS.keys() or any(
        hosted[name].get(field) != expected[field]
        for name, expected in PINNED_CLERK_BROWSER_COMPONENTS.items()
        for field in sdk_fields
    ):
        raise ValueError("The commit does not use this checker's reviewed Clerk SDK versions.")
    notice_sets = [("workdoe/static", browser_vendor_notice_digests(ledger), LICENSE_NOTICE_MAX_BYTES)]
    if include_build_notices:
        build_notices = clerk_build_notice_digests(ledger, errors, allow_previous_index=True)
        if errors or not build_notices:
            raise ValueError("Invalid reviewed build-notice inventory.")
        notice_sets.append((f"workdoe/static{BUILD_NOTICE_PREFIX}", build_notices, BUILD_NOTICE_MAX_BYTES))
    for prefix, digests, limit in notice_sets:
        for filename, expected in digests.items():
            if hashlib.sha256(read_blob(prefix + filename, limit)).hexdigest() != expected:
                raise ValueError("A committed license notice does not match the committed ledger.")
    return ledger


def read_reviewed_smoke_release(
    repo_root: Path, commit: str, *, require_area_map: bool = False, isolated_clerk_beta: bool = False,
) -> ReviewedSmokeRelease:
    if isolated_clerk_beta and (commit not in ISOLATED_BETA_COMMITS or require_area_map):
        raise ValueError("The isolated Clerk beta profile is restricted to its exact reviewed commit.")
    read_blob = committed_release_reader(repo_root, commit)
    ledger = read_committed_public_notice_ledger(read_blob, include_build_notices=True)
    if not isolated_clerk_beta:
        for component in PINNED_CLERK_BROWSER_COMPONENTS.values():
            notice = read_blob(component["retained_license"], LICENSE_NOTICE_MAX_BYTES)
            if hashlib.sha256(notice).hexdigest() != component["retained_license_sha256"]:
                raise ValueError("A committed Clerk license differs from the reviewed upstream notice.")
    area_map = read_reviewed_area_map(ledger, read_blob) if require_area_map else None
    return ReviewedSmokeRelease(versioned_assets_from_commit(read_blob), ledger, area_map)


def checkout_asset_parity_check(
    base_url: str, timeout: float, repo_root: Path, *, asset_commit: str | None = None,
    reviewed_assets: dict[str, bytes] | None = None, expect_list_mode: bool = False,
    require_clerk_entry_integrity: bool = False,
) -> SmokeCheck:
    source = "checkout" if asset_commit is None else "commit"
    name = f"{source}-asset-parity"
    check_clerk_integrity = asset_commit is None or require_clerk_entry_integrity
    try:
        if reviewed_assets is not None:
            expected = reviewed_assets
        elif asset_commit is None:
            asset_root = repo_root / "workdoe" / "static"
            expected = {filename: (asset_root / filename).read_bytes() for filename in VERSIONED_STATIC_ASSET_FILES}
        else:
            expected = read_committed_assets(repo_root, asset_commit)
        token = versioned_asset_release_token(expected)
    except (OSError, ValueError, subprocess.SubprocessError):
        return SmokeCheck(name, "failed", f"The reviewed {source}'s versioned assets could not be read.")

    paths = {filename: f"/{filename}?v={token}" for filename in expected}
    failures = []
    elapsed_ms = 0
    for route, required in RELEASE_ENTRY_ASSETS.items():
        page = fetch_url(
            check_url(base_url, route), timeout=timeout,
            follow_redirects=False, binary=True, body_limit=MAX_RELEASE_HTML_BYTES + 1,
        )
        elapsed_ms += page.elapsed_ms
        mime = header_value(page.headers, "Content-Type").split(";", 1)[0].strip().lower()
        if page.status_code != 200 or mime != "text/html" or len(page.body_bytes) > MAX_RELEASE_HTML_BYTES:
            failures.append(f"{route} did not return a bounded HTTP 200 HTML entry page")
            continue
        references = ReleaseAssetReferences()
        try:
            references.feed(page.body_bytes.decode("utf-8"))
            references.close()
        except ValueError:
            failures.append(f"{route} has invalid HTML or asset references")
            continue
        files = required | references.assets.keys()
        # List-only entry pages and older fragments can retain inert map markup.
        inert_map = (
            (expect_list_mode and references.list_mode)
            or (asset_commit is not None and route in RELEASE_EMBEDDED_ENTRY_ROUTES)
        )
        if references.has_map and not inert_map:
            files.add("map.js")
        for filename in sorted(files):
            if references.assets.get(filename) != {paths[filename]}:
                failures.append(f"{route} did not reference only the reviewed version of {filename}")
        if (
            check_clerk_integrity and route in RELEASE_CLERK_ENTRY_ROUTES
            and not references.has_reviewed_clerk_scripts(base_url)
        ):
            failures.append(f"{route} did not declare both reviewed Clerk scripts with integrity")

    if not failures:
        for filename, content in expected.items():
            asset = fetch_url(
                check_url(base_url, paths[filename]), timeout=timeout,
                follow_redirects=False, binary=True, body_limit=len(content) + 1,
            )
            elapsed_ms += asset.elapsed_ms
            mime = header_value(asset.headers, "Content-Type").split(";", 1)[0].strip().lower()
            allowed_mimes = {"text/css"} if filename.endswith(".css") else {"text/javascript", "application/javascript"}
            if asset.status_code != 200 or mime not in allowed_mimes or asset.body_bytes != content:
                failures.append(f"{filename} did not return the reviewed bytes with its expected MIME type")

    success = (
        f"Public entries declare the pinned Clerk scripts with integrity; versioned assets match the reviewed {source}."
        if check_clerk_integrity else "Public first-party asset references and bytes match the reviewed commit."
    )
    return SmokeCheck(
        name, "failed" if failures else "ready",
        "; ".join(failures) if failures else success,
        elapsed_ms=elapsed_ms,
    )


class PolicyCopyParser(HTMLParser):
    """Read the authored policy blocks, independently of the page layout."""

    block_tags = frozenset({"h1", "h2", "h3", "h4", "h5", "h6", "p", "li"})
    skip_tags = frozenset({"nav", "script", "style", "template"})
    void_tags = frozenset({
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    })

    def __init__(self, *, include_navigation: bool = False) -> None:
        super().__init__()
        self.excluded_tags = self.skip_tags - {"nav"} if include_navigation else self.skip_tags
        self.main_count = 0
        self.in_main = False
        self.stack: list[tuple[str, bool]] = []
        self.blocks: list[tuple[str, str, list[str]]] = []
        self.block: str | None = None
        self.parts: list[str] = []
        self.links: list[str] = []
        self.document_links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        skipped = (bool(self.stack) and self.stack[-1][1]) or tag in self.excluded_tags or "hidden" in attributes
        if tag == "main" and not skipped:
            self.main_count += 1
            if self.main_count != 1 or attributes.get("id") != "main-content":
                raise ValueError("expected one main policy region")
            self.in_main = True
        if tag not in self.void_tags:
            self.stack.append((tag, skipped))
        if not skipped and tag == "a" and len(attrs) == len(attributes) and attributes.get("href"):
            self.document_links.add(attributes["href"])
        if skipped or not self.in_main:
            return
        if tag in self.block_tags:
            if self.block is not None:
                raise ValueError("unexpected nested policy blocks")
            self.block, self.parts, self.links = tag, [], []
        elif self.block is not None:
            if tag == "a":
                self.links.append(attributes.get("href") or "")
            elif tag == "br":
                self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if not self.stack or tag in self.void_tags:
            return
        open_tag, skipped = self.stack.pop()
        if tag != open_tag:
            raise ValueError("unbalanced policy document markup")
        if not skipped and tag == "main":
            self.in_main = False
        elif not skipped and tag == self.block:
            self.blocks.append((tag, " ".join("".join(self.parts).split()), self.links))
            self.block = None

    def handle_data(self, data: str) -> None:
        if self.block is not None and self.stack and not self.stack[-1][1]:
            self.parts.append(data)


def public_policy_fingerprint(html: str) -> str:
    parser = PolicyCopyParser()
    parser.feed(html)
    parser.close()
    if (
        parser.main_count != 1
        or parser.stack
        or sum(tag == "h1" and bool(copy) for tag, copy, _ in parser.blocks) != 1
        or not any(tag == "p" and copy for tag, copy, _ in parser.blocks)
    ):
        raise ValueError("missing or incomplete main policy content")
    canonical = json.dumps(parser.blocks, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def clerk_build_notices_check(
    base_url: str, timeout: float, *, reviewed_ledger: dict | None = None,
) -> SmokeCheck:
    name = "clerk-build-notice-delivery"
    errors: list[str] = []
    try:
        ledger = reviewed_ledger if reviewed_ledger is not None else json.loads(
            DEPENDENCY_LEDGER.read_text(encoding="utf-8"),
        )
        digests = clerk_build_notice_digests(
            ledger, errors, allow_previous_index=reviewed_ledger is not None,
        ) if isinstance(ledger, dict) else {}
    except (OSError, ValueError, RecursionError):
        digests = {}
    if errors or not digests:
        return SmokeCheck(name, "failed", "Could not verify the reviewed Clerk build-notice ledger.")

    terms = fetch_url(
        check_url(base_url, "/terms"), timeout=timeout, body_limit=PUBLIC_POLICY_MAX_BYTES + 1,
        follow_redirects=False, binary=True,
    )
    failures = []
    elapsed_ms = terms.elapsed_ms
    try:
        parser = PolicyCopyParser(include_navigation=True)
        if (
            terms.status_code != 200 or len(terms.body_bytes) > PUBLIC_POLICY_MAX_BYTES
            or header_value(terms.headers, "Content-Type").partition(";")[0].strip().lower() != "text/html"
        ):
            raise ValueError("Invalid Terms response.")
        parser.feed(terms.body_bytes.decode("utf-8"))
        parser.close()
        if parser.stack or BUILD_NOTICE_INDEX_PATH not in parser.document_links:
            raise ValueError("Missing notice index link.")
    except (ValueError, RecursionError):
        failures.append("/terms did not link to the reviewed software notice index")

    for filename, digest in digests.items():
        index = filename == CLERK_NOTICE_INDEX
        path = BUILD_NOTICE_INDEX_PATH if index else BUILD_NOTICE_PREFIX + filename
        expected_mime = "text/html" if index else "text/plain"
        result = fetch_url(
            check_url(base_url, path), timeout=timeout, body_limit=BUILD_NOTICE_MAX_BYTES + 1,
            follow_redirects=False, binary=True,
        )
        elapsed_ms += result.elapsed_ms
        if result.status_code != 200:
            failures.append(f"{path} did not return a direct HTTP 200")
        elif len(result.body_bytes) > BUILD_NOTICE_MAX_BYTES:
            failures.append(f"{path} exceeded the build-notice size limit")
        elif (
            header_value(result.headers, "Content-Type").partition(";")[0].strip().lower() != expected_mime
            or header_value(result.headers, "X-Content-Type-Options").strip().lower() != "nosniff"
        ):
            failures.append(f"{path} did not return the expected MIME type and nosniff")
        elif hashlib.sha256(result.body_bytes).hexdigest() != digest:
            failures.append(f"{path} did not match the reviewed build-notice bytes")
        if cache_control_directives(result) != {"no-store"}:
            failures.append(f"{path} did not return unambiguous no-store")
    for path in BUILD_NOTICE_CACHE_PROBES:
        result = fetch_url(
            check_url(base_url, path), timeout=timeout, body_limit=0, follow_redirects=False,
        )
        elapsed_ms += result.elapsed_ms
        if result.status_code != 404 or cache_control_directives(result) != {"no-store"}:
            failures.append(f"{path} did not return an uncached HTTP 404")
    return SmokeCheck(
        name, "failed" if failures else "ready",
        "; ".join(failures) if failures else (
            "Terms links to the reviewed notice index; notice bytes match and responses and misses declare no-store."
        ),
        elapsed_ms=elapsed_ms,
    )


def public_trust_pages_check(base_url: str, timeout: float) -> SmokeCheck:
    missing: list[str] = []
    elapsed_ms = 0
    for path, expected in PUBLIC_POLICY_FINGERPRINTS.items():
        url = check_url(base_url, path)
        result = fetch_url(
            url, timeout=timeout, body_limit=PUBLIC_POLICY_MAX_BYTES + 1,
            follow_redirects=False, binary=True,
        )
        elapsed_ms += result.elapsed_ms
        if not result.ok or result.status_code != 200:
            missing.append(f"{path} returned HTTP {result.status_code or 'error'}")
        elif header_value(result.headers, "Content-Type").partition(";")[0].strip().lower() != "text/html":
            missing.append(f"{path} did not return HTML")
        elif len(result.body_bytes) > PUBLIC_POLICY_MAX_BYTES:
            missing.append(f"{path} exceeded the policy response size limit")
        else:
            try:
                actual = public_policy_fingerprint(result.body_bytes.decode("utf-8"))
            except ValueError:
                missing.append(f"{path} did not contain readable UTF-8 policy markup")
            else:
                if actual != expected:
                    missing.append(f"{path} differs from the recorded policy copy or contact links")
    url = check_url(base_url, "/safety")
    if missing:
        return SmokeCheck(
            name="public-trust-pages",
            status="failed",
            summary="Required public trust pages are not ready: " + "; ".join(missing),
            url=url,
            elapsed_ms=elapsed_ms,
        )
    return SmokeCheck(
        name="public-trust-pages",
        status="ready",
        summary="Safety, Privacy Policy, and Terms of Use match the recorded public copy and contact links. Policy approval is not evaluated.",
        url=url,
        status_code=200,
        elapsed_ms=elapsed_ms,
    )


def social_share_check(base_url: str, timeout: float) -> SmokeCheck:
    page_url = check_url(base_url, "/")
    page = fetch_url(page_url, timeout=timeout, body_limit=200000)
    if not page.ok:
        return response_check(
            "social-share-card",
            page_url,
            page,
            expected_summary="Homepage share metadata returned HTTP success.",
        )
    required_markers = (
        '<meta property="og:title" content="Workdoe - a local Work Exchange">',
        '<meta property="og:image" content="https://workdoe.com/workdoe-share.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
    )
    missing = [marker for marker in required_markers if marker not in page.body]
    asset_url = check_url(base_url, "/workdoe-share.png")
    asset = fetch_url(
        asset_url, timeout=timeout, body_limit=SHARE_PNG_HEADER.size, follow_redirects=False, binary=True,
    )
    asset_type = header_value(asset.headers, "Content-Type").split(";", 1)[0].strip().lower()
    details = ["homepage metadata is incomplete"] if missing else []
    if not asset.ok or asset.status_code != 200:
        details.append(f"share image returned HTTP {asset.status_code or 'error'}")
    elif asset_type != "image/png":
        details.append("share image is not served as image/png")
    elif len(asset.body_bytes) < SHARE_PNG_HEADER.size or not asset.body_bytes.startswith(PNG_IHDR_PREFIX):
        details.append("share image has no PNG image header")
    elif SHARE_PNG_HEADER.unpack_from(asset.body_bytes)[1:] != SHARE_PNG_SIZE:
        details.append("share image dimensions do not match the metadata")
    if details:
        return SmokeCheck(
            name="social-share-card",
            status="failed",
            summary="Social share card is not ready: " + "; ".join(details),
            url=page_url,
            status_code=page.status_code,
            elapsed_ms=page.elapsed_ms + asset.elapsed_ms,
        )
    return SmokeCheck(
        name="social-share-card",
        status="ready",
        summary="Homepage share metadata and the served PNG header both specify 1200x630.",
        url=page_url,
        status_code=page.status_code,
        elapsed_ms=page.elapsed_ms + asset.elapsed_ms,
    )


def reviewed_robots_profile(body: str) -> bool:
    if not body.isascii() or any(ord(char) < 32 and char not in "\t\r\n" for char in body):
        return False
    expected = {
        ("allow", "/"), ("sitemap", f"{DEFAULT_BASE_URL}/sitemap.xml"),
        *(("disallow", path) for path in ROBOTS_REVIEWED_EXCLUSIONS),
    }
    directives = []
    for raw_line in body.splitlines():
        line = raw_line.partition("#")[0].strip()
        if line:
            key, _, value = line.partition(":")
            directives.append((key.strip().casefold(), value.strip()))
    return (
        directives[:1] == [("user-agent", "*")]
        and len(directives) == len(expected) + 1 and set(directives[1:]) == expected
    )


def reviewed_sitemap_profile(body: str) -> bool:
    # The small, fixed sitemap never uses DTDs, entities, or CDATA.
    if "<!" in body or "\0" in body:
        return False
    try:
        # Only the bounded, decoded body from discovery_files_check reaches the parser.
        root = ElementTree.fromstring(body)  # nosec B314
    except (ElementTree.ParseError, ValueError):
        return False
    expected = {DEFAULT_BASE_URL + path for path in ("/", *PUBLIC_POLICY_FINGERPRINTS)}
    if (root.tag != f"{SITEMAP_NAMESPACE}urlset" or root.attrib or len(root) != len(expected)
            or (root.text or "").strip()):
        return False
    urls = []
    for entry in root:
        if (entry.tag != f"{SITEMAP_NAMESPACE}url" or entry.attrib or len(entry) != 1
                or (entry.text or "").strip() or (entry.tail or "").strip()):
            return False
        loc = entry[0]
        if loc.tag != f"{SITEMAP_NAMESPACE}loc" or loc.attrib or len(loc) or (loc.tail or "").strip():
            return False
        urls.append((loc.text or "").strip())
    return set(urls) == expected


def discovery_files_check(base_url: str, timeout: float) -> SmokeCheck:
    issues: list[tuple[str, str, int]] = []
    elapsed_ms = 0
    profiles = (
        ("/robots.txt", "text/plain", reviewed_robots_profile),
        ("/sitemap.xml", "application/xml", reviewed_sitemap_profile),
    )
    for path, media_type, check_profile in profiles:
        result = fetch_url(
            check_url(base_url, path), timeout=timeout, body_limit=DISCOVERY_MAX_BYTES + 1,
            follow_redirects=False, binary=True,
        )
        elapsed_ms += result.elapsed_ms
        issue = ""
        if not result.ok or result.status_code != 200:
            issue = f"HTTP {result.status_code}" if result.status_code else "request failed"
        elif header_value(result.headers, "Content-Type").partition(";")[0].strip().lower() != media_type:
            issue = "unexpected content type"
        elif not 0 < len(result.body_bytes) <= DISCOVERY_MAX_BYTES:
            issue = "empty or oversized response"
        else:
            try:
                body = result.body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                issue = "invalid UTF-8"
            else:
                if not check_profile(body):
                    issue = "does not match the reviewed crawl profile"
        if issue:
            issues.append((path, issue, result.status_code))
    if issues:
        return SmokeCheck(
            name="public-discovery-files",
            status="warning",
            summary="Public discovery warning: " + "; ".join(f"{path}: {issue}" for path, issue, _ in issues),
            url=check_url(base_url, issues[0][0]),
            status_code=issues[0][2],
            elapsed_ms=elapsed_ms,
            required=False,
        )
    return SmokeCheck(
        name="public-discovery-files",
        status="ready",
        summary="robots.txt and sitemap.xml match the reviewed public crawl profile.",
        url=check_url(base_url, "/robots.txt"),
        status_code=200,
        elapsed_ms=elapsed_ms,
        required=False,
    )


def security_contact_check(base_url: str, timeout: float, *, now: datetime | None = None) -> SmokeCheck:
    url = check_url(base_url, SECURITY_CONTACT_PATH)
    if urlparse(url).scheme != "https":
        return SmokeCheck("public-security-contact", "failed", "Fetch security.txt over HTTPS.", url=url)
    result = fetch_url(url, timeout=timeout, body_limit=SECURITY_CONTACT_MAX_BYTES + 1, follow_redirects=False)
    problem = ""
    expires = ""
    if not result.ok or result.status_code != 200:
        problem = f"expected direct HTTP 200, got {result.status_code or 'a connection error'}"
    else:
        headers = Message()
        headers["Content-Type"] = header_value(result.headers, "Content-Type")
        if headers.get_content_type() != "text/plain" or headers.get_content_charset() != "utf-8":
            problem = "expected text/plain with a UTF-8 charset"
        elif len(result.body.encode("utf-8")) > SECURITY_CONTACT_MAX_BYTES or "\ufffd" in result.body:
            problem = "expected a small, valid UTF-8 file"
        else:
            fields: dict[str, list[str]] = {}
            for line in result.body.splitlines():
                name, separator, value = line.partition(":")
                if separator and not name.startswith("#"):
                    fields.setdefault(name.strip().lower(), []).append(value.strip())
            expirations = fields.get("expires", [])
            if url not in fields.get("canonical", []):
                problem = "missing the matching canonical URL"
            elif not {SECURITY_CONTACT_EMAIL, f"{DEFAULT_BASE_URL}/safety"}.issubset(fields.get("contact", [])):
                problem = "missing the published Workdoe reporting contacts"
            elif len(expirations) != 1:
                problem = "expected exactly one Expires field"
            else:
                try:
                    expiry = datetime.strptime(expirations[0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    problem = "expected the Workdoe UTC Expires timestamp format"
                else:
                    if expiry <= (now if now is not None else datetime.now(timezone.utc)):
                        problem = "the published security contact file has expired"
                    else:
                        expires = expiry.isoformat()
    return SmokeCheck(
        name="public-security-contact",
        status="failed" if problem else "ready",
        summary=f"security.txt: {problem}." if problem else f"Published security contact is current (expires {expires}).",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def clerk_proxy_check(base_url: str, timeout: float) -> SmokeCheck:
    name = "clerk-same-domain-proxy"
    elapsed_ms = 0
    for label, component in PINNED_CLERK_BROWSER_COMPONENTS.items():
        url = check_url(base_url, "/__clerk" + component["script_path"])
        result = fetch_url(
            url, timeout=timeout, follow_redirects=False, binary=True,
            body_limit=CLERK_ASSET_MAX_BYTES + 1,
        )
        elapsed_ms += result.elapsed_ms
        mime = header_value(result.headers, "Content-Type").split(";", 1)[0].strip().lower()
        content = result.body_bytes
        if (
            result.status_code != 200
            or mime not in {"text/javascript", "application/javascript"}
            or header_value(result.headers, "Content-Encoding").strip().lower() not in {"", "identity"}
            or not 0 < len(content) <= CLERK_ASSET_MAX_BYTES
            or "sha384-" + b64encode(hashlib.sha384(content).digest()).decode("ascii") != component["script_integrity"]
        ):
            return SmokeCheck(
                name, "failed", f"{label} did not return the reviewed JavaScript bytes.",
                url=url, status_code=result.status_code, elapsed_ms=elapsed_ms,
            )
    return SmokeCheck(
        name, "ready", "Both same-domain Clerk entry scripts match their reviewed integrity hashes.",
        elapsed_ms=elapsed_ms,
    )


def clerk_package_denied(result: FetchResult) -> bool:
    mime = header_value(result.headers, "Content-Type").split(";", 1)[0].strip().lower()
    return (
        result.status_code == 404 and mime == "application/json"
        and "no-store" in cache_control_directives(result)
        and not header_value(result.headers, "Location")
    )


def clerk_package_boundary_check(base_url: str, timeout: float) -> SmokeCheck:
    path = "/__clerk/npm/@clerk/clerk-js@6.40.0/dist/clerk.browser.js"
    url = check_url(base_url, path)
    result = fetch_url(url, method="HEAD", timeout=timeout, body_limit=0, follow_redirects=False)
    denied = clerk_package_denied(result)
    return SmokeCheck(
        name="clerk-unpinned-package",
        status="ready" if denied else "failed",
        summary=(
            "The previously served alternate Clerk package is denied with a non-cacheable JSON 404."
            if denied else "The alternate Clerk package did not return the expected non-cacheable JSON 404."
        ),
        url=url, status_code=result.status_code, elapsed_ms=result.elapsed_ms,
    )


def clerk_developer_file_check(base_url: str, timeout: float) -> SmokeCheck:
    public_origins = ("https://workdoe.com", "https://www.workdoe.com")
    origins = public_origins if base_url.rstrip("/") in public_origins else (base_url,)
    elapsed_ms = 0
    for origin in origins:
        for path in CLERK_DEVELOPER_FILE_PROBES:
            url = check_url(origin, path)
            result = fetch_url(url, method="HEAD", timeout=timeout, body_limit=0, follow_redirects=False)
            elapsed_ms += result.elapsed_ms
            if (
                not clerk_package_denied(result)
                or cache_control_directives(result) != {"no-store"}
                or header_value(result.headers, "Age")
                or header_value(result.headers, "CF-Cache-Status").strip().upper() not in {"", "DYNAMIC", "BYPASS"}
            ):
                return SmokeCheck(
                    "clerk-developer-file-boundary", "failed",
                    "A sampled non-browser Clerk file did not return a fresh no-store JSON 404.",
                    url=url, status_code=result.status_code, elapsed_ms=elapsed_ms,
                )
    return SmokeCheck(
        "clerk-developer-file-boundary", "ready",
        "The sampled non-browser Clerk files return fresh no-store JSON 404s on every checked host.",
        elapsed_ms=elapsed_ms,
    )


def clerk_environment_errors(environment: object) -> list[str]:
    try:
        auth = environment["auth_config"]
        display = environment["display_config"]
        settings = environment["user_settings"]
        attributes = settings["attributes"]
        signup = settings["sign_up"]
        saml = settings["saml"]
        enterprise = settings["enterprise_sso"]
        email = attributes["email_address"]
    except (KeyError, TypeError):
        return ["The Clerk environment did not contain the reviewed authentication sections."]
    if not all(isinstance(section, dict) for section in (
        auth, display, settings, attributes, signup, saml, enterprise, email,
    )):
        return ["The Clerk environment did not contain the reviewed authentication sections."]

    errors = []
    # Clerk can advertise its server-issued, single-use ticket in addition to public email codes.
    allowed_first_factors = (["email_code"], ["email_code", "ticket"], ["ticket", "email_code"])
    if (
        auth.get("test_mode") is not False
        or auth.get("password") != "off"
        or auth.get("identification_strategies") != ["email_address"]
        or auth.get("first_factors") not in allowed_first_factors
        or auth.get("email_address_verification_strategies") != ["email_code"]
        or not all(email.get(field) is True for field in (
            "enabled", "required", "used_for_first_factor", "verify_at_sign_up",
        ))
        or email.get("first_factors") != ["email_code"]
        or email.get("verifications") != ["email_code"]
    ):
        errors.append("Clerk did not advertise email-code-only sign-in and sign-up verification.")
    if (
        any(
            not isinstance(attributes.get(key), dict) or attributes[key].get("enabled") is not False
            for key in CLERK_DISABLED_AUTH_ATTRIBUTES
        )
        or any(
            not isinstance(record, dict) or record.get("used_for_first_factor") is not False
            or record.get("first_factors") != []
            for key, record in attributes.items() if key != "email_address"
        )
        or settings.get("social") != {}
        or saml.get("enabled") is not False
        or enterprise.get("enabled") is not False
        or display.get("google_one_tap_client_id") is not None
    ):
        errors.append("Clerk did not confirm that alternate public sign-in methods are disabled.")
    if signup.get("mode") != "public" or signup.get("legal_consent_enabled") is not True:
        errors.append("Clerk did not confirm open sign-up with express legal consent.")
    expected_paths = {
        "sign_in_url": "/login", "sign_up_url": "/create-account",
        "terms_url": "/terms", "privacy_policy_url": "/privacy",
    }
    if any(display.get(field) != DEFAULT_BASE_URL + path for field, path in expected_paths.items()):
        errors.append("Clerk sign-in, sign-up, Terms, or Privacy URLs differ from Workdoe's reviewed URLs.")
    return errors


def clerk_environment_check(base_url: str, timeout: float) -> SmokeCheck:
    name = "clerk-public-auth-settings"
    result = fetch_url(
        check_url(base_url, CLERK_ENVIRONMENT_PATH), timeout=timeout, follow_redirects=False,
        binary=True, body_limit=CLERK_ENVIRONMENT_MAX_BYTES + 1,
    )
    if (
        result.status_code != 200
        or not 0 < len(result.body_bytes) <= CLERK_ENVIRONMENT_MAX_BYTES
        or header_value(result.headers, "Content-Type").partition(";")[0].strip().lower() != "application/json"
        or "no-store" not in cache_control_directives(result)
        or header_value(result.headers, "Age")
        or header_value(result.headers, "CF-Cache-Status").strip().upper() in CACHED_EDGE_STATUSES
    ):
        errors = ["Clerk did not return a direct, bounded, non-cacheable JSON environment response."]
    else:
        try:
            errors = clerk_environment_errors(json.loads(result.body_bytes, object_pairs_hook=unique_json_keys))
        except (ValueError, RecursionError):
            errors = ["Clerk returned an invalid environment document."]
    return SmokeCheck(
        name, "failed" if errors else "ready",
        " ".join(errors) if errors else (
            "Clerk advertises email-code-only public sign-in and open sign-up with express consent "
            "at Workdoe's reviewed URLs. No account or policy approval was checked."
        ),
        status_code=result.status_code, elapsed_ms=result.elapsed_ms,
    )


def clerk_browser_entry_check(base_url: str, timeout: float, *, require_integrity: bool = True) -> SmokeCheck:
    name = "clerk-browser-entry"
    elapsed_ms = 0
    for path, mode in CLERK_BROWSER_ENTRY_MODES.items():
        url = check_url(base_url, path)
        result = fetch_url(
            url, timeout=timeout, follow_redirects=False, binary=True,
            body_limit=MAX_RELEASE_HTML_BYTES + 1,
        )
        elapsed_ms += result.elapsed_ms
        if (
            result.status_code != 200
            or not 0 < len(result.body_bytes) <= MAX_RELEASE_HTML_BYTES
            or header_value(result.headers, "Content-Type").partition(";")[0].strip().lower() != "text/html"
            or "no-store" not in cache_control_directives(result)
            or header_value(result.headers, "Age")
            or header_value(result.headers, "CF-Cache-Status").strip().upper() in CACHED_EDGE_STATUSES
        ):
            return SmokeCheck(
                name, "failed", f"{path} did not return direct, bounded, non-cacheable HTML.",
                url=url, status_code=result.status_code, elapsed_ms=elapsed_ms,
            )
        references = ReleaseAssetReferences()
        try:
            references.feed(result.body_bytes.decode("utf-8"))
            references.close()
            reviewed = references.has_reviewed_clerk_bootstrap(
                base_url, mode, require_integrity=require_integrity,
            )
        except ValueError:
            reviewed = False
        if not reviewed:
            return SmokeCheck(
                name, "failed", f"{path} did not declare the reviewed same-domain production Clerk configuration.",
                url=url, status_code=result.status_code, elapsed_ms=elapsed_ms,
            )
    integrity = " with integrity" if require_integrity else ""
    return SmokeCheck(
        name, "ready", f"Direct and dialog sign-in and signup declare the reviewed production Clerk proxy and scripts{integrity}.",
        elapsed_ms=elapsed_ms,
    )


def clerk_production_key_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, "/login")
    result = fetch_url(url, timeout=timeout, body_limit=200000)
    if not result.ok:
        return response_check(
            "clerk-production-key",
            url,
            result,
            expected_summary="Sign-in page returned HTTP success.",
        )
    match = CLERK_PUBLISHABLE_KEY_PATTERN.search(result.body)
    if not match:
        return SmokeCheck(
            name="clerk-production-key",
            status="failed",
            summary="Sign-in page is missing the Clerk publishable key marker.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    if not match.group(1).startswith("pk_live_"):
        return SmokeCheck(
            name="clerk-production-key",
            status="failed",
            summary="Sign-in is not using a Clerk production instance.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="clerk-production-key",
        status="ready",
        summary="Sign-in uses a Clerk production publishable key.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def clerk_invitation_entry_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, CLERK_INVITATION_SMOKE_PATH)
    result = fetch_url(url, timeout=timeout, body_limit=200000)
    if not result.ok:
        return response_check(
            "clerk-invitation-entry",
            url,
            result,
            expected_summary="Invitation account page returned HTTP success.",
        )
    content_type = header_value(result.headers, "Content-Type").lower()
    if "text/html" not in content_type or "data-clerk-entry" not in result.body:
        return SmokeCheck(
            name="clerk-invitation-entry",
            status="failed",
            summary="Invitation deep link did not return the Workdoe account HTML shell.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    match = CLERK_PUBLISHABLE_KEY_PATTERN.search(result.body)
    if not match or not match.group(1).startswith("pk_live_"):
        return SmokeCheck(
            name="clerk-invitation-entry",
            status="failed",
            summary="Invitation account page is not using a Clerk production instance.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    if (
        header_value(result.headers, "Referrer-Policy").strip().lower() not in {"strict-origin", "no-referrer"}
        or "no-store" not in cache_control_directives(result)
        or CLERK_INVITATION_SMOKE_TICKET in result.body
    ):
        return SmokeCheck(
            name="clerk-invitation-entry",
            status="failed",
            summary="Invitation page must prevent full-URL referrers, disable storage, and not echo the ticket.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="clerk-invitation-entry",
        status="ready",
        summary="Invitation links open production Clerk without storing the page or reflecting the ticket.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def build_smoke_payload(
    *,
    domain: str = DEFAULT_DOMAIN,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    verify_checkout_assets: bool = False,
    asset_commit: str | None = None,
    release_checkout: Path | None = None,
    verify_clerk_package_boundary: bool = False,
    verify_clerk_build_notices: bool = False,
    verify_clerk_environment: bool = False,
    verify_redirect_privacy: bool = False,
    expect_public_map_mode: str | None = None,
    verify_clerk_developer_files: bool = False,
    isolated_clerk_beta: bool = False,
) -> dict:
    if verify_checkout_assets and asset_commit is not None:
        raise ValueError("Choose checkout or commit asset verification, not both.")
    if isolated_clerk_beta and (
        asset_commit not in ISOLATED_BETA_COMMITS or release_checkout is None or expect_public_map_mode is not None
        or domain != DEFAULT_DOMAIN or base_url.rstrip("/") != DEFAULT_BASE_URL
    ):
        raise ValueError("The isolated Clerk beta profile requires its exact checkout and canonical Workdoe host.")
    if expect_public_map_mode not in (None, *PUBLIC_MAP_MODES):
        raise ValueError("Unknown public map mode.")
    if expect_public_map_mode == "area" and release_checkout is None:
        raise ValueError("Area mode requires an exact release checkout and commit.")
    release = None
    reviewed_assets = None
    reviewed_ledger = None
    if release_checkout is not None and asset_commit is None:
        raise ValueError("Release checkout verification requires an exact asset commit.")
    if asset_commit is not None:
        area_options = {"require_area_map": True} if expect_public_map_mode == "area" else {}
        release_options = {**area_options, **({"isolated_clerk_beta": True} if isolated_clerk_beta else {})}
        try:
            if release_checkout is not None:
                release = read_reviewed_smoke_release(release_checkout, asset_commit, **release_options)
                reviewed_assets = release.assets
                reviewed_ledger = release.ledger
            else:
                read_blob = committed_release_reader(SCRIPT_DIR.parent, asset_commit)
                reviewed_assets = versioned_assets_from_commit(read_blob)
                reviewed_ledger = read_committed_public_notice_ledger(
                    read_blob, include_build_notices=verify_clerk_build_notices,
                )
        except (OSError, TypeError, ValueError, RecursionError, subprocess.SubprocessError):
            artifacts = "versioned assets, license notices and Census data" if area_options else (
                "versioned assets and license notices"
            )
            check = SmokeCheck(
                "reviewed-release-inputs", "failed",
                f"Could not verify {artifacts} from the exact local release commit.",
            )
            return {
                "service": "workdoe",
                "domain": domain,
                "base_url": base_url.rstrip("/"),
                "ready": False,
                "readiness_scope": "reviewed_release_inputs",
                "public_launch_approval": "not_evaluated",
                "asset_commit": asset_commit,
                "checks": [asdict(check)],
                "failures": [check.summary],
            }
    if release is not None:
        verify_clerk_package_boundary = verify_clerk_developer_files = verify_clerk_build_notices = True
        verify_clerk_environment = verify_redirect_privacy = True
    if isolated_clerk_beta:
        expect_public_map_mode = ISOLATED_CLERK_BETA_MAP_MODE
    notice_options = {"reviewed_ledger": reviewed_ledger} if reviewed_ledger is not None else {}
    map_options = (
        {"mode": expect_public_map_mode, "area_map": release.area_map if release else None}
        if expect_public_map_mode else {}
    )
    dns_ready, addresses, dns_error = dns_lookup(domain)
    checks = [
        SmokeCheck(
            name="dns",
            status="ready" if dns_ready else "failed",
            summary=(
                f"{domain} resolves to {', '.join(addresses)}."
                if dns_ready
                else f"{domain} does not resolve: {dns_error}"
            ),
        ),
    ]
    checks.append(https_redirect_check(domain, timeout))
    root_url = check_url(base_url, "/")
    checks.append(
        response_check(
            "https-entry",
            root_url,
            fetch_url(root_url, method="HEAD", timeout=timeout),
            expected_summary="HTTPS entry responded successfully.",
        )
    )
    checks.extend(
        [
            health_check(base_url, timeout),
            public_jobs_check(base_url, timeout),
            public_search_check(base_url, timeout),
            public_map_snapshot_check(base_url, timeout, **map_options),
            anonymous_private_routes_check(base_url, timeout),
            public_sample_presentation_check(base_url, timeout),
            security_headers_check(base_url, timeout, require_origin_referrer=release is not None and not isolated_clerk_beta),
            static_asset_cache_check(base_url, timeout),
            browser_license_notices_check(base_url, timeout, **notice_options),
            public_trust_pages_check(base_url, timeout),
            social_share_check(base_url, timeout),
            discovery_files_check(base_url, timeout),
            security_contact_check(base_url, timeout),
            clerk_production_key_check(base_url, timeout),
            clerk_invitation_entry_check(base_url, timeout),
            clerk_proxy_check(base_url, timeout),
        ]
    )
    scope = "public_http_smoke"
    if expect_public_map_mode:
        scope += f"_with_public_map_mode_{expect_public_map_mode}"
    if verify_clerk_package_boundary:
        checks.append(clerk_package_boundary_check(base_url, timeout))
        scope += "_with_clerk_package_boundary"
    if verify_clerk_developer_files:
        checks.append(clerk_developer_file_check(base_url, timeout))
        scope += "_with_clerk_developer_file_boundary"
    if verify_clerk_build_notices:
        checks.append(clerk_build_notices_check(base_url, timeout, **notice_options))
        scope += "_with_clerk_build_notice_delivery"
    if verify_clerk_environment:
        checks.extend((clerk_browser_entry_check(base_url, timeout), clerk_environment_check(base_url, timeout)))
        scope += "_with_clerk_public_auth_settings"
    if verify_redirect_privacy:
        checks.append(redirect_privacy_check(domain, timeout))
        scope += "_with_redirect_privacy"
    if verify_checkout_assets or asset_commit is not None:
        asset_options = {"reviewed_assets": reviewed_assets} if reviewed_assets is not None else {}
        if release:
            asset_options["require_clerk_entry_integrity"] = True
        if expect_public_map_mode == "list":
            asset_options["expect_list_mode"] = True
        repo_root = release_checkout if release_checkout is not None else SCRIPT_DIR.parent
        parity = checkout_asset_parity_check(base_url, timeout, repo_root, asset_commit=asset_commit, **asset_options)
        checks.append(parity)
        scope += "_with_" + parity.name.replace("-", "_")
    if reviewed_ledger is not None:
        scope += "_and_commit_bound_notices"
    failures = [
        check.summary
        for check in checks
        if check.required and check.status != "ready"
    ]
    return {
        "service": "workdoe",
        "domain": domain,
        "base_url": base_url.rstrip("/"),
        "ready": not failures,
        "readiness_scope": scope,
        "public_launch_approval": "not_evaluated",
        **({"asset_commit": asset_commit} if asset_commit is not None else {}),
        "checks": [asdict(check) for check in checks],
        "failures": failures,
    }


def build_smoke_payload_with_retries(
    *,
    domain: str = DEFAULT_DOMAIN,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    attempts: int = 1,
    retry_delay: float = 0.0,
    verify_checkout_assets: bool = False,
    asset_commit: str | None = None,
    release_checkout: Path | None = None,
    verify_clerk_package_boundary: bool = False,
    verify_clerk_build_notices: bool = False,
    verify_clerk_environment: bool = False,
    verify_redirect_privacy: bool = False,
    expect_public_map_mode: str | None = None,
    verify_clerk_developer_files: bool = False,
    verify_clerk_browser_delivery: bool = False,
    isolated_clerk_beta: bool = False,
) -> dict:
    if isolated_clerk_beta and (
        asset_commit not in ISOLATED_BETA_COMMITS or expect_public_map_mode is not None
        or not verify_clerk_browser_delivery
    ):
        raise ValueError("The isolated Clerk beta profile requires its exact commit and full Clerk delivery verification.")
    if verify_clerk_browser_delivery and (
        release_checkout is None or asset_commit is None
        or domain != DEFAULT_DOMAIN or base_url.rstrip("/") != DEFAULT_BASE_URL
    ):
        raise ValueError("Full Clerk browser delivery verification requires the exact release commit and canonical Workdoe host.")
    total_attempts = max(1, int(attempts))
    payload: dict = {}
    for attempt in range(1, total_attempts + 1):
        payload = build_smoke_payload(
            domain=domain, base_url=base_url, timeout=timeout, verify_checkout_assets=verify_checkout_assets,
            asset_commit=asset_commit, release_checkout=release_checkout,
            verify_clerk_package_boundary=verify_clerk_package_boundary,
            verify_clerk_build_notices=verify_clerk_build_notices,
            verify_clerk_environment=verify_clerk_environment,
            verify_redirect_privacy=verify_redirect_privacy,
            **({"expect_public_map_mode": expect_public_map_mode} if expect_public_map_mode else {}),
            **({"verify_clerk_developer_files": True} if verify_clerk_developer_files else {}),
            **({"isolated_clerk_beta": True} if isolated_clerk_beta else {}),
        )
        payload["attempt"] = attempt
        payload["attempts"] = total_attempts
        if payload["ready"] or payload.get("readiness_scope") == "reviewed_release_inputs" or attempt == total_attempts:
            break
        time.sleep(max(0.0, retry_delay))
    if verify_clerk_browser_delivery and payload.get("readiness_scope") != "reviewed_release_inputs":
        # Verify the full browser inventory once, after the propagation checks pass.
        delivery_options = {"isolated_clerk_beta": True} if isolated_clerk_beta else {}
        check = clerk_browser_file_delivery_check(release_checkout, asset_commit, **delivery_options) if payload["ready"] else SmokeCheck(
            "clerk-browser-file-delivery", "failed", "Not run because the preceding required smoke checks did not pass.",
        )
        payload["readiness_scope"] += "_with_clerk_browser_file_delivery"
        payload["checks"].append(asdict(check))
        if check.status != "ready":
            payload["ready"] = False
            payload["failures"].append(check.summary)
    return payload


def isolated_beta_archive_ledger(committed_ledger: dict) -> dict:
    reviewed_ledger = json.loads(DEPENDENCY_LEDGER.read_text(encoding="utf-8"))
    errors: list[str] = []
    committed = records_by_key(committed_ledger.get("hosted_browser_components"), "name", "Beta Clerk inventory", errors)
    reviewed = records_by_key(reviewed_ledger.get("hosted_browser_components"), "name", "Clerk inventory", errors)
    fields = ("package", "version", "script_path", "license", "package_integrity")
    if errors or committed.keys() != reviewed.keys() or any(
        committed[name].get(field) != reviewed[name].get(field) for name in reviewed for field in fields
    ):
        raise ValueError("The isolated beta does not use the reviewed Clerk archives.")
    return reviewed_ledger


def read_clerk_archive_pins(repo_root: Path, commit: str, *, isolated_clerk_beta: bool = False) -> dict[str, FilePin]:
    if isolated_clerk_beta and commit not in ISOLATED_BETA_COMMITS:
        raise ValueError("The isolated Clerk beta profile requires its exact reviewed commit.")
    read_blob = committed_release_reader(repo_root, commit)
    ledger = json.loads(read_blob("DEPENDENCY_PROVENANCE.json", MAX_RELEASE_LEDGER_BYTES))
    source = read_blob("cloudflare/worker/clerk_browser_files.py", MAX_RELEASE_LEDGER_BYTES)
    if not isinstance(ledger, dict):
        raise TypeError("Invalid committed ledger.")
    inventory = parse_clerk_browser_inventory(source.decode("utf-8"))
    options = {}
    if isolated_clerk_beta:
        # The beta predates local license retention; both proxied LICENSE files must match the archive pins.
        ledger = isolated_beta_archive_ledger(ledger)
    elif "clerk_browser_body_pins_sha256" in ledger:
        pin_source = read_blob(CLERK_BROWSER_PINS_PATH, MAX_RELEASE_LEDGER_BYTES)
        options["runtime_pins"] = parse_clerk_browser_declaration(pin_source.decode("utf-8"), "CLERK_BROWSER_PINS")
    return pinned_archive_files(ledger, inventory, **options)


def clerk_browser_file_delivery_check(repo_root: Path, commit: str, *, isolated_clerk_beta: bool = False) -> SmokeCheck:
    name = "clerk-browser-file-delivery"
    try:
        pins = read_clerk_archive_pins(repo_root, commit, isolated_clerk_beta=isolated_clerk_beta)
        checked = compare_live_files(pins)
        if not pins or checked != len(pins):
            raise ValueError("Incomplete Clerk browser delivery verification.")
    except (OSError, TypeError, ValueError, SyntaxError, RecursionError, subprocess.SubprocessError):
        return SmokeCheck(name, "failed", "Could not verify all reviewed Clerk browser files against the committed archive pins.")
    return SmokeCheck(name, "ready", f"All {checked} reviewed Clerk files match the pinned npm archives on Workdoe's canonical host.")


def render_text(payload: dict) -> str:
    lines = [
        "Workdoe production smoke",
        f"Domain: {payload['domain']}",
        f"Base URL: {payload['base_url']}",
        f"Ready: {payload['ready']}",
        "Public launch approval: not evaluated by these anonymous HTTP checks.",
        "",
    ]
    if "asset_commit" in payload:
        lines.insert(3, f"Reviewed asset commit: {payload['asset_commit']}")
    if payload["failures"]:
        lines.extend(["Failures:", *(f"- {failure}" for failure in payload["failures"]), ""])
    lines.append("Checks:")
    lines.extend(
        f"- {check['name']}: {check['status']} - {check['summary']}"
        for check in payload["checks"]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Workdoe production DNS, HTTPS, API, and security-header smoke checks."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Domain to resolve.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Production base URL.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds.")
    asset_options = parser.add_mutually_exclusive_group()
    asset_options.add_argument(
        "--verify-checkout-assets", action="store_true",
        help="Require public asset references and bytes to match this reviewed checkout.",
    )
    asset_options.add_argument(
        "--asset-commit", metavar="FULL_COMMIT",
        help="Compare public assets and selected notices with one local Git commit. Use --release-checkout for strict release checks.",
    )
    parser.add_argument(
        "--release-checkout", type=Path, metavar="DIR",
        help="Use this repository's --asset-commit for assets and notices; require Clerk integrity and redirect checks.",
    )
    parser.add_argument(
        "--verify-clerk-package-boundary", action="store_true",
        help="Require the known alternate Clerk package path to be denied; do not download it.",
    )
    parser.add_argument(
        "--verify-clerk-developer-files", action="store_true",
        help="Require sampled non-browser Clerk package paths to be denied without downloading them.",
    )
    parser.add_argument(
        "--verify-clerk-build-notices", action="store_true",
        help="Require the known Clerk build notices and public Terms link; not a complete license review.",
    )
    parser.add_argument(
        "--verify-clerk-browser-delivery", action="store_true",
        help="Compare all reviewed Clerk files with the exact commit's pinned archives after other checks pass.",
    )
    parser.add_argument(
        "--verify-clerk-environment", action="store_true",
        help="Verify public Clerk auth and legal-consent settings without signing in.",
    )
    parser.add_argument(
        "--verify-redirect-privacy", action="store_true",
        help="Require synthetic query-bearing redirects to preserve HTTPS and prohibit caching and referrers.",
    )
    parser.add_argument(
        "--expect-public-map-mode", choices=PUBLIC_MAP_MODES,
        help="Require the rendered first-party area map or list-only mode; area requires --release-checkout and --asset-commit.",
    )
    parser.add_argument(
        "--isolated-clerk-beta", action="store_true",
        help="Check only the exact reviewed Clerk beta hotfix with its existing street map and full browser delivery.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        help="Maximum production smoke attempts while a new Worker propagates.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.0,
        help="Seconds to wait between production smoke attempts.",
    )
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when smoke checks are not ready.",
    )
    args = parser.parse_args()
    if args.asset_commit is not None and not FULL_ASSET_COMMIT.fullmatch(args.asset_commit):
        parser.error("--asset-commit requires a full lowercase hexadecimal Git commit ID")
    if args.release_checkout is not None and args.asset_commit is None:
        parser.error("--release-checkout requires --asset-commit")
    if args.expect_public_map_mode == "area" and args.release_checkout is None:
        parser.error("--expect-public-map-mode area requires --release-checkout and --asset-commit")
    if args.verify_clerk_browser_delivery and (
        args.release_checkout is None or args.domain != DEFAULT_DOMAIN or args.base_url.rstrip("/") != DEFAULT_BASE_URL
    ):
        parser.error("--verify-clerk-browser-delivery requires --release-checkout, --asset-commit and the canonical host")
    if args.isolated_clerk_beta and (
        args.asset_commit not in ISOLATED_BETA_COMMITS or args.expect_public_map_mode or not args.verify_clerk_browser_delivery
    ):
        parser.error("--isolated-clerk-beta requires its exact commit and --verify-clerk-browser-delivery, with no map override")
    payload = build_smoke_payload_with_retries(
        domain=args.domain,
        base_url=args.base_url,
        timeout=args.timeout,
        attempts=args.attempts,
        retry_delay=args.retry_delay,
        verify_checkout_assets=args.verify_checkout_assets,
        asset_commit=args.asset_commit,
        release_checkout=args.release_checkout,
        verify_clerk_package_boundary=args.verify_clerk_package_boundary,
        verify_clerk_build_notices=args.verify_clerk_build_notices,
        verify_clerk_environment=args.verify_clerk_environment,
        verify_redirect_privacy=args.verify_redirect_privacy,
        expect_public_map_mode=args.expect_public_map_mode,
        verify_clerk_developer_files=args.verify_clerk_developer_files,
        **({"verify_clerk_browser_delivery": True} if args.verify_clerk_browser_delivery else {}),
        **({"isolated_clerk_beta": True} if args.isolated_clerk_beta else {}),
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if (args.fail_when_not_ready or args.asset_commit is not None or args.expect_public_map_mode) and not payload["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
