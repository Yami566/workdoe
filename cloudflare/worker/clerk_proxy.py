from __future__ import annotations

from urllib.parse import urlparse, urlunparse

CLERK_PROXY_PATH = "/__clerk"
DEFAULT_CLERK_FAPI = "https://frontend-api.clerk.dev"
DEFAULT_CLERK_PROXY_URL = "https://workdoe.com/__clerk"
DEFAULT_WORKDOE_PUBLIC_URL = "https://workdoe.com"
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
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
    normalized = "/" + (path or "").strip("/")
    return normalized == CLERK_PROXY_PATH or normalized.startswith(f"{CLERK_PROXY_PATH}/")


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
    parsed = urlparse(proxy_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname != WORKDOE_PUBLIC_DOMAIN
        or not is_clerk_proxy_path(parsed.path)
    ):
        raise ClerkProxyError("Clerk proxy URL must stay on https://workdoe.com/__clerk.", 503)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


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


def headers_to_forward(headers) -> dict[str, str]:
    forwarded: dict[str, str] = {}
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
        if lowered in HOP_BY_HOP_HEADERS or lowered in PROXY_OWNED_HEADERS:
            continue
        if lowered.startswith("cf-"):
            continue
        forwarded[normalized_key] = str(value)
    return forwarded


def clerk_proxy_target_url(request_url: str, fapi_url: str | None = None) -> str:
    parsed_request = urlparse(request_url)
    if not is_clerk_proxy_path(parsed_request.path):
        raise ClerkProxyError("Unsupported Clerk proxy route.", 404)
    fapi = urlparse(normalize_fapi_url(fapi_url))
    suffix = parsed_request.path[len(CLERK_PROXY_PATH) :]
    target_path = suffix if suffix.startswith("/") else f"/{suffix.lstrip('/')}"
    if target_path == "/":
        target_path = ""
    return urlunparse(
        (
            fapi.scheme,
            fapi.netloc,
            fapi.path.rstrip("/") + target_path,
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
    proxy_url: str | None = None,
    fapi_url: str | None = None,
    public_url: str | None = None,
) -> dict:
    if not str(secret_key or "").strip():
        raise ClerkProxyError("CLERK_SECRET_KEY is required for the Clerk proxy.", 503)
    client_ip = header_value(incoming_headers, "CF-Connecting-IP")
    if not client_ip:
        raise ClerkProxyError("CF-Connecting-IP is required for the Clerk proxy.", 400)

    normalized_proxy_url = normalize_proxy_url(proxy_url, public_url=public_url)
    headers = headers_to_forward(incoming_headers)
    headers["Clerk-Proxy-Url"] = normalized_proxy_url
    headers["Clerk-Secret-Key"] = str(secret_key).strip()
    headers["X-Forwarded-For"] = client_ip
    return {
        "url": clerk_proxy_target_url(request_url, fapi_url=fapi_url),
        "headers": headers,
        "proxy_url": normalized_proxy_url,
    }
