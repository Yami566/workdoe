from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from urllib.parse import urljoin


DEFAULT_DOMAIN = "workdoe.com"
DEFAULT_BASE_URL = "https://workdoe.com"
DEFAULT_TIMEOUT = 8.0
REQUIRED_SECURITY_HEADERS = {
    "Content-Security-Policy": ("default-src 'self'", "frame-ancestors 'none'"),
    "X-Content-Type-Options": ("nosniff",),
    "X-Frame-Options": ("DENY",),
    "Referrer-Policy": ("strict-origin-when-cross-origin",),
    "Permissions-Policy": ("geolocation=(), microphone=(), camera=()",),
}


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
        with urllib.request.urlopen(request, timeout=timeout) as response:
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
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when smoke checks are not ready.",
    )
    args = parser.parse_args()
    payload = build_smoke_payload(
        domain=args.domain,
        base_url=args.base_url,
        timeout=args.timeout,
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
