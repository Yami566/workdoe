from __future__ import annotations

import hashlib
import re
from ipaddress import ip_address
from urllib.parse import urlparse, urlsplit, urlunparse

from clerk_browser_files import CLERK_BROWSER_FILES
from clerk_browser_pins import CLERK_BROWSER_PINS
from json_values import JsonDataError, read_json_stream_bytes

CLERK_PROXY_PATH = "/__clerk"
DEFAULT_CLERK_FAPI = "https://frontend-api.clerk.dev"
DEFAULT_CLERK_PROXY_URL = "https://workdoe.com/__clerk"
DEFAULT_WORKDOE_PUBLIC_URL = "https://workdoe.com"
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
CLERK_BROWSER_ORIGINS = frozenset({DEFAULT_WORKDOE_PUBLIC_URL, f"https://www.{WORKDOE_PUBLIC_DOMAIN}"})
CLERK_UI_VERSION = "1.41.2"
CLERK_JS_VERSION = "6.40.1"
CLERK_UI_PACKAGE_PATH = f"/npm/@clerk/ui@{CLERK_UI_VERSION}"
CLERK_JS_PACKAGE_PATH = f"/npm/@clerk/clerk-js@{CLERK_JS_VERSION}"
CLERK_PACKAGE_PATHS = (CLERK_UI_PACKAGE_PATH, CLERK_JS_PACKAGE_PATH)
CLERK_PUBLIC_PACKAGE_PATHS = frozenset(
    f"{package}/dist/{name}" for package in CLERK_PACKAGE_PATHS for name in CLERK_BROWSER_FILES[package]
) | frozenset(f"{package}/LICENSE" for package in CLERK_PACKAGE_PATHS)
CLERK_PACKAGE_MEDIA_TYPE = re.compile(
    r'(?P<type>text/plain|text/javascript|application/javascript)(?:[ \t]*;[ \t]*charset[ \t]*=[ \t]*(?:utf-8|"utf-8"))?'
)
CLERK_PACKAGE_UNSAFE_HEADERS = ("Location", "Refresh", "Service-Worker-Allowed", "Content-Range")
CLERK_PACKAGE_REQUEST_HEADERS = frozenset({
    "accept-encoding", "if-match", "if-modified-since", "if-none-match", "if-range", "if-unmodified-since", "range",
})
CLERK_PACKAGE_RESPONSE_HEADERS = (
    "Content-Type", "Cache-Control", "ETag", "Last-Modified", "Vary",
    "Access-Control-Allow-Origin", "Access-Control-Allow-Credentials", "Cross-Origin-Resource-Policy",
)
CLERK_PACKAGE_BODY_CHUNKS = 256
CLERK_PROXY_TARGET_PATH = re.compile(r"/(?:[A-Za-z0-9_.@-]+/)*[A-Za-z0-9_.@-]*")
CLOUDFLARE_ACCESS_COOKIES = frozenset({
    "cf_authorization", "cf_binding", "cf_session", "cf_appsession", "cf_device",
})
COOKIE_OCTETS = r"[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*"
COOKIE_PAIR = re.compile(
    rf"(?P<name>[!#$%&'*+\-.^_\x60|~0-9A-Za-z]+)=(?:{COOKIE_OCTETS}|\"{COOKIE_OCTETS}\")"
)
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
PROXY_OWNED_HEADERS = {
    "clerk-proxy-url",
    "clerk-secret-key",
    "x-forwarded-for",
}


class ClerkProxyError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def is_workdoe_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == WORKDOE_PUBLIC_DOMAIN or host.endswith(f".{WORKDOE_PUBLIC_DOMAIN}")


def is_clerk_proxy_path(path: str) -> bool:
    return path == CLERK_PROXY_PATH or path.startswith(f"{CLERK_PROXY_PATH}/")


def clerk_proxy_origin_allowed(request_url: str, origin: str | None, *, allow_loopback: bool = False) -> bool:
    # Navigations, same-origin assets and provider probes can omit Origin.
    if origin is None or origin in CLERK_BROWSER_ORIGINS:
        return True
    if not allow_loopback:
        return False
    try:
        parsed = urlsplit(request_url)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            and parsed.username is None
            and origin == f"{parsed.scheme}://{parsed.netloc}"
        )
    except ValueError:
        return False


def normalize_https_base_url(value: str | None, default: str) -> str:
    parsed = urlparse((value or default).strip().rstrip("/"))
    if parsed.scheme != "https" or not parsed.netloc:
        parsed = urlparse(default)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def normalize_public_url(value: str | None) -> str:
    return normalize_https_base_url(value, DEFAULT_WORKDOE_PUBLIC_URL)


def normalize_proxy_url(value: str | None, public_url: str | None = None) -> str:
    raw = (value or DEFAULT_CLERK_PROXY_URL).strip().rstrip("/")
    if raw.startswith("/") and not raw.startswith("//"):
        proxy_url = normalize_public_url(public_url) + raw
    else:
        proxy_url = raw
    if proxy_url != DEFAULT_CLERK_PROXY_URL:
        raise ClerkProxyError("Clerk proxy URL must stay on https://workdoe.com/__clerk.", 503)
    return proxy_url


def normalize_fapi_url(value: str | None) -> str:
    parsed = urlparse((value or DEFAULT_CLERK_FAPI).strip().rstrip("/"))
    expected = urlparse(DEFAULT_CLERK_FAPI)
    if (
        parsed.scheme != expected.scheme
        or parsed.netloc != expected.netloc
        or parsed.path.rstrip("/")
    ):
        raise ClerkProxyError("CLERK_FAPI must be https://frontend-api.clerk.dev.", 503)
    return DEFAULT_CLERK_FAPI


def header_value(headers, name: str) -> str:
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is not None:
            return str(value)
    if isinstance(headers, dict):
        lowered = name.lower()
        for key, value in headers.items():
            if str(key).lower() == lowered:
                return str(value)
    return ""


async def verified_clerk_package(path: str, response, *, method: str) -> tuple[bytes | None, dict[str, str]]:
    pin = CLERK_BROWSER_PINS.get(path)
    status, headers = response.status, response.headers
    if pin is None or status != 200 or any(header_value(headers, name) for name in CLERK_PACKAGE_UNSAFE_HEADERS):
        raise ClerkProxyError("Unexpected Clerk package response.", status if 400 <= status <= 599 else 502)
    size, digest = pin
    encoding = header_value(headers, "Content-Encoding").strip().lower()
    length = header_value(headers, "Content-Length")
    media_type = header_value(headers, "Content-Type").strip().lower()
    match = CLERK_PACKAGE_MEDIA_TYPE.fullmatch(media_type)
    if (encoding not in {"", "identity"} or (length and length != str(size))
            or match is None or (match["type"] == "text/plain") != path.endswith("/LICENSE")):
        raise ClerkProxyError("Unexpected Clerk package headers.", 502)
    body = None
    if method == "GET":
        try:
            body = await read_json_stream_bytes(
                response.body, max_bytes=size, max_chunks=CLERK_PACKAGE_BODY_CHUNKS, label="Clerk package",
            )
        except JsonDataError as exc:
            raise ClerkProxyError("Could not read the reviewed Clerk package.", 502) from exc
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            raise ClerkProxyError("Clerk package bytes do not match the reviewed artifact.", 502)
    # Package files are public. Never copy upstream cookies or active headers onto this origin.
    delivered = {name: value for name in CLERK_PACKAGE_RESPONSE_HEADERS if (value := header_value(headers, name))}
    delivered.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"})
    return body, delivered


def clerk_request_cookies(value: str) -> str:
    kept = []
    for field in value.split(";"):
        pair = field.strip(" \t")
        match = COOKIE_PAIR.fullmatch(pair)
        # RFC 6265 excludes commas and controls. Never pass an ambiguous joined pair.
        if not match:
            continue
        name = match["name"].lower()
        if name.startswith("workdoe_") or name in CLOUDFLARE_ACCESS_COOKIES:
            continue
        kept.append(pair)
    return "; ".join(kept)


def headers_to_forward(headers) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    connection_fields = {field.strip().lower() for field in header_value(headers, "Connection").split(",")}
    iterable = None
    items = getattr(headers, "items", None)
    entries = getattr(headers, "entries", None)
    if callable(items):
        iterable = items()
    elif callable(entries):
        iterable = entries()
    elif isinstance(headers, dict):
        iterable = headers.items()
    else:
        try:
            iterable = iter(headers)
        except TypeError:
            iterable = ()

    for key, value in iterable:
        normalized_key = str(key)
        lowered = normalized_key.lower()
        if lowered in HOP_BY_HOP_HEADERS or lowered in PROXY_OWNED_HEADERS or lowered in connection_fields:
            continue
        if lowered.startswith("cf-"):
            continue
        value = str(value)
        if lowered == "cookie":
            value = clerk_request_cookies(value)
            if not value:
                continue
        forwarded[normalized_key] = value
    return forwarded


def clerk_proxy_target_url(request_url: str, fapi_url: str | None = None, *, method: str = "GET") -> str:
    parsed_request = urlsplit(request_url)
    if not is_clerk_proxy_path(parsed_request.path):
        raise ClerkProxyError("Unsupported Clerk proxy route.", 404)
    fapi = urlparse(normalize_fapi_url(fapi_url))
    target_path = parsed_request.path[len(CLERK_PROXY_PATH) :] or "/"
    # Reject spellings that a downstream URL parser could interpret as a different path.
    if not CLERK_PROXY_TARGET_PATH.fullmatch(target_path) or {".", ".."}.intersection(target_path.split("/")):
        raise ClerkProxyError("Unsupported Clerk proxy route.", 404)
    if target_path[1:].partition("/")[0].lower() == "npm" and (
        method not in {"GET", "HEAD"}
        or target_path not in CLERK_PUBLIC_PACKAGE_PATHS
    ):
        raise ClerkProxyError("Unsupported Clerk proxy route.", 404)
    return urlunparse(
        (
            fapi.scheme,
            fapi.netloc,
            target_path if target_path != "/" else "",
            "",
            parsed_request.query,
            "",
        )
    )


def clerk_proxy_request_plan(
    request_url: str,
    incoming_headers,
    *,
    secret_key: str,
    method: str = "GET",
    proxy_url: str | None = None,
    fapi_url: str | None = None,
    public_url: str | None = None,
) -> dict:
    if not str(secret_key or "").strip():
        raise ClerkProxyError("CLERK_SECRET_KEY is required for the Clerk proxy.", 503)
    client_ip = header_value(incoming_headers, "CF-Connecting-IP").strip()
    try:
        if "%" in client_ip:
            raise ValueError("An IP scope identifier is not a client address")
        client_ip = str(ip_address(client_ip))
    except ValueError as error:
        raise ClerkProxyError("CF-Connecting-IP must contain one client IP for the Clerk proxy.", 400) from error

    normalized_proxy_url = normalize_proxy_url(proxy_url, public_url=public_url)
    target = clerk_proxy_target_url(request_url, fapi_url=fapi_url, method=method)
    package_path = urlsplit(target).path
    headers = headers_to_forward(incoming_headers)
    if package_path in CLERK_PUBLIC_PACKAGE_PATHS:
        # Verify complete identity bytes. A partial or bodyless upstream reply cannot prove integrity.
        headers = {key: value for key, value in headers.items() if key.lower() not in CLERK_PACKAGE_REQUEST_HEADERS}
        headers["Accept-Encoding"] = "identity"
    else:
        package_path = ""
    headers["Clerk-Proxy-Url"] = normalized_proxy_url
    headers["Clerk-Secret-Key"] = str(secret_key).strip()
    headers["X-Forwarded-For"] = client_ip
    return {
        "url": target,
        "headers": headers,
        "proxy_url": normalized_proxy_url,
        "package_path": package_path,
    }
