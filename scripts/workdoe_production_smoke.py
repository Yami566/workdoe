from __future__ import annotations

import argparse
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse


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
REQUIRED_SECURITY_HEADERS = {
    "Strict-Transport-Security": ("max-age=", "includeSubDomains"),
    "Content-Security-Policy": ("default-src 'self'", "frame-ancestors 'none'"),
    "X-Content-Type-Options": ("nosniff",),
    "X-Frame-Options": ("DENY",),
    "Referrer-Policy": ("strict-origin-when-cross-origin",),
    "Permissions-Policy": ("geolocation=(), microphone=(), camera=()",),
}
CLERK_ASSET_PATH = "/__clerk/npm/@clerk/clerk-js@6/dist/clerk.browser.js"
PUBLIC_TRUST_PAGES = {
    "/safety": "Share only what the job needs.",
    "/privacy": "Privacy Policy",
    "/terms": "Terms of Use",
}
OPTIONAL_DISCOVERY_PATHS = (
    "/robots.txt",
    "/sitemap.xml",
    "/.well-known/security.txt",
)
CLERK_PUBLISHABLE_KEY_PATTERN = re.compile(
    r'data-clerk-publishable-key=["\']([^"\']+)["\']'
)


@dataclass
class FetchResult:
    ok: bool
    status_code: int = 0
    headers: dict[str, str] | None = None
    body: str = ""
    error: str = ""
    elapsed_ms: int = 0


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
) -> FetchResult:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "workdoe-production-smoke/1.0"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            body = ""
            if method != "HEAD":
                body = response.read(body_limit).decode("utf-8", errors="replace")
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            status_code = int(getattr(response, "status", 0))
            return FetchResult(
                ok=200 <= status_code < 400,
                status_code=status_code,
                headers=dict(response.headers.items()),
                body=body,
                elapsed_ms=elapsed_ms,
            )
    except urllib.error.HTTPError as exc:
        body = ""
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
        )
    except (OSError, urllib.error.URLError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return FetchResult(ok=False, error=str(exc), elapsed_ms=elapsed_ms)


def header_value(headers: dict[str, str] | None, name: str) -> str:
    for key, value in (headers or {}).items():
        if key.lower() == name.lower():
            return value
    return ""


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
    result = fetch_url(url, timeout=timeout)
    if not result.ok:
        return response_check(
            "health-json",
            url,
            result,
            expected_summary="Health endpoint returned HTTP success.",
        )
    payload, error = parse_json_body(result)
    if error or not payload or payload.get("ok") is not True:
        return SmokeCheck(
            name="health-json",
            status="failed",
            summary=f"Health endpoint did not return ok=true JSON: {error or payload}",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    bindings = payload.get("bindings") if isinstance(payload.get("bindings"), dict) else {}
    missing_bindings = sorted(
        binding for binding in REQUIRED_HEALTH_BINDINGS if bindings.get(binding) is not True
    )
    if missing_bindings:
        return SmokeCheck(
            name="health-json",
            status="failed",
            summary="Health endpoint is missing required bindings: "
            + ", ".join(missing_bindings),
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="health-json",
        status="ready",
        summary=f"Health endpoint ok for {payload.get('service', 'workdoe')}.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def public_jobs_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, "/api/jobs/open?limit=3")
    result = fetch_url(url, timeout=timeout)
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
    jobs = payload.get("jobs")
    if not isinstance(payload.get("count"), int) or not isinstance(jobs, list):
        return SmokeCheck(
            name="public-jobs-api",
            status="failed",
            summary="Public jobs API is missing integer count or jobs list.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    if "location_privacy" not in payload:
        return SmokeCheck(
            name="public-jobs-api",
            status="failed",
            summary="Public jobs API is missing the location privacy notice.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="public-jobs-api",
        status="ready",
        summary=f"Public jobs API returned {payload['count']} visible map leads.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def security_headers_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, "/start")
    result = fetch_url(url, method="HEAD", timeout=timeout)
    if not result.ok:
        return response_check(
            "entry-security-headers",
            url,
            result,
            expected_summary="Entry shell returned HTTP success.",
        )
    missing: list[str] = []
    for header, required_values in REQUIRED_SECURITY_HEADERS.items():
        value = header_value(result.headers, header)
        if not value:
            missing.append(header)
            continue
        for required_value in required_values:
            if required_value not in value:
                missing.append(f"{header} missing {required_value}")
    if missing:
        return SmokeCheck(
            name="entry-security-headers",
            status="failed",
            summary="Entry shell is missing required security headers: " + ", ".join(missing),
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="entry-security-headers",
        status="ready",
        summary="Entry shell returned the expected privacy and security headers.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
    )


def public_trust_pages_check(base_url: str, timeout: float) -> SmokeCheck:
    missing: list[str] = []
    elapsed_ms = 0
    for path, marker in PUBLIC_TRUST_PAGES.items():
        url = check_url(base_url, path)
        result = fetch_url(url, timeout=timeout, body_limit=100000)
        elapsed_ms += result.elapsed_ms
        if not result.ok:
            missing.append(f"{path} returned HTTP {result.status_code or 'error'}")
        elif marker not in result.body:
            missing.append(f"{path} is missing its page marker")
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
        summary="Safety, Privacy Policy, and Terms of Use are publicly available.",
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
    asset = fetch_url(asset_url, method="HEAD", timeout=timeout)
    asset_type = header_value(asset.headers, "Content-Type").lower()
    if missing or not asset.ok or "image/png" not in asset_type:
        details = []
        if missing:
            details.append("homepage metadata is incomplete")
        if not asset.ok:
            details.append(f"share image returned HTTP {asset.status_code or 'error'}")
        elif "image/png" not in asset_type:
            details.append("share image is not served as image/png")
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
        summary="Homepage share metadata declares 1200x630 and its PNG asset is available.",
        url=page_url,
        status_code=page.status_code,
        elapsed_ms=page.elapsed_ms + asset.elapsed_ms,
    )


def discovery_files_check(base_url: str, timeout: float) -> SmokeCheck:
    missing: list[str] = []
    elapsed_ms = 0
    for path in OPTIONAL_DISCOVERY_PATHS:
        result = fetch_url(check_url(base_url, path), method="HEAD", timeout=timeout)
        elapsed_ms += result.elapsed_ms
        if not result.ok:
            missing.append(path)
    if missing:
        return SmokeCheck(
            name="public-discovery-files",
            status="warning",
            summary="Optional public discovery files are absent: " + ", ".join(missing),
            url=check_url(base_url, missing[0]),
            elapsed_ms=elapsed_ms,
            required=False,
        )
    return SmokeCheck(
        name="public-discovery-files",
        status="ready",
        summary="robots.txt, sitemap.xml, and security.txt are available.",
        url=check_url(base_url, "/robots.txt"),
        status_code=200,
        elapsed_ms=elapsed_ms,
        required=False,
    )


def clerk_proxy_check(base_url: str, timeout: float) -> SmokeCheck:
    url = check_url(base_url, CLERK_ASSET_PATH)
    result = fetch_url(url, timeout=timeout)
    if not result.ok:
        return response_check(
            "clerk-same-domain-proxy",
            url,
            result,
            expected_summary="Same-domain Clerk asset proxy returned HTTP success.",
        )
    content_type = header_value(result.headers, "Content-Type").lower()
    if "javascript" not in content_type or not result.body.strip():
        return SmokeCheck(
            name="clerk-same-domain-proxy",
            status="failed",
            summary="Clerk proxy did not return a non-empty JavaScript asset.",
            url=url,
            status_code=result.status_code,
            elapsed_ms=result.elapsed_ms,
        )
    return SmokeCheck(
        name="clerk-same-domain-proxy",
        status="ready",
        summary="Clerk sign-in assets are served through workdoe.com.",
        url=url,
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
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


def build_smoke_payload(
    *,
    domain: str = DEFAULT_DOMAIN,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
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
            security_headers_check(base_url, timeout),
            public_trust_pages_check(base_url, timeout),
            social_share_check(base_url, timeout),
            discovery_files_check(base_url, timeout),
            clerk_production_key_check(base_url, timeout),
            clerk_proxy_check(base_url, timeout),
        ]
    )
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
) -> dict:
    total_attempts = max(1, int(attempts))
    payload: dict = {}
    for attempt in range(1, total_attempts + 1):
        payload = build_smoke_payload(domain=domain, base_url=base_url, timeout=timeout)
        payload["attempt"] = attempt
        payload["attempts"] = total_attempts
        if payload["ready"] or attempt == total_attempts:
            break
        time.sleep(max(0.0, retry_delay))
    return payload


def render_text(payload: dict) -> str:
    lines = [
        "Workdoe production smoke",
        f"Domain: {payload['domain']}",
        f"Base URL: {payload['base_url']}",
        f"Ready: {payload['ready']}",
        "",
        "Checks:",
    ]
    lines.extend(
        f"- {check['name']}: {check['status']} - {check['summary']}"
        for check in payload["checks"]
    )
    if payload["failures"]:
        lines.extend(["", "Failures:"])
        lines.extend(f"- {failure}" for failure in payload["failures"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Workdoe production DNS, HTTPS, API, and security-header smoke checks."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Domain to resolve.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Production base URL.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="HTTP timeout seconds.")
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
    payload = build_smoke_payload_with_retries(
        domain=args.domain,
        base_url=args.base_url,
        timeout=args.timeout,
        attempts=args.attempts,
        retry_delay=args.retry_delay,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.fail_when_not_ready and not payload["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
