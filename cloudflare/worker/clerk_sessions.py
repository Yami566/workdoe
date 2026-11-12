from __future__ import annotations

import asyncio
import base64
import binascii
import inspect
import json
import re
import time
from urllib.parse import urlparse

from json_values import parse_json_value, read_json_response_bytes

CLERK_BACKEND_JWKS_URL = "https://api.clerk.com/v1/jwks"
# The same session is also carried in a browser cookie; allow headroom above 4 KiB.
MAX_CLERK_SESSION_TOKEN_BYTES = 8 * 1024
MAX_CLERK_SIGNING_KEY_ID_BYTES = 256
MAX_CLERK_JWKS_BODY_BYTES = 256 * 1024
MAX_CLERK_JWKS_BODY_CHUNKS = 128
CLERK_JWKS_TIMEOUT_SECONDS = 5
CLERK_JWKS_CACHE_TTL_SECONDS = 60
CLERK_JWKS_CACHE_TIMEOUT_SECONDS = 1
JWKS_PUBLIC_RSA_FIELDS = frozenset({"kid", "kty", "n", "e", "alg", "use", "ext", "key_ops"})


class SessionVerificationError(ValueError):
    pass


def header_value(headers, name: str) -> str:
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if callable(getter):
        value = getter(name)
        if value is not None:
            return str(value)
    items = getattr(headers, "items", None)
    if callable(items):
        for key, value in items():
            if str(key).lower() == name.lower():
                return str(value)
    return ""


def parse_cookie_header(cookie_header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in (cookie_header or "").split(";"):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies


def extract_clerk_session_token(headers) -> str:
    authorization = header_value(headers, "Authorization")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token
    return parse_cookie_header(header_value(headers, "Cookie")).get("__session", "")


def base64url_decode(value: str) -> bytes:
    if not value:
        raise SessionVerificationError("JWT segment is empty.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise SessionVerificationError("JWT segment is not valid base64url.")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(
            (value + padding).encode("ascii"), altchars=b"-_", validate=True
        )
    except (binascii.Error, UnicodeError) as exc:
        raise SessionVerificationError("JWT segment is not valid base64url.") from exc


def decode_json_part(value: str) -> dict:
    try:
        decoded = base64url_decode(value).decode("utf-8")
        data = parse_json_value(decoded, max_depth=1, allow_deep_values=True)
    except ValueError as exc:
        raise SessionVerificationError("JWT segment is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise SessionVerificationError("JWT segment must be an object.")
    return data


def decode_unverified_jwt(token: str) -> tuple[dict, dict, str, bytes]:
    if len(token) > MAX_CLERK_SESSION_TOKEN_BYTES:
        raise SessionVerificationError("Session token exceeds the size limit.")
    parts = token.split(".")
    if len(parts) != 3:
        raise SessionVerificationError("Session token must be a three-part JWT.")
    header = decode_json_part(parts[0])
    claims = decode_json_part(parts[1])
    if header.get("alg") != "RS256":
        raise SessionVerificationError("Session token must use RS256.")
    if "crit" in header:
        raise SessionVerificationError("Session token has unsupported critical headers.")
    if "kid" in header and not (
        isinstance(header["kid"], str)
        and 0 < len(header["kid"]) <= MAX_CLERK_SIGNING_KEY_ID_BYTES
        and header["kid"].isascii() and header["kid"].isprintable()
    ):
        raise SessionVerificationError("Session token has an invalid signing key id.")
    signing_input = f"{parts[0]}.{parts[1]}"
    signature = base64url_decode(parts[2])
    return header, claims, signing_input, signature


def authorized_parties_from_env(env, request_url: str = "") -> list[str]:
    public_url = str(getattr(env, "WORKDOE_PUBLIC_URL", "") or "").rstrip("/")
    domain = str(getattr(env, "WORKDOE_DOMAIN", "workdoe.com") or "workdoe.com").strip()
    environment = str(getattr(env, "WORKDOE_ENV", "production") or "production").lower()
    parties = []
    if public_url:
        parties.append(public_url)
    if domain:
        parties.append(f"https://{domain}".rstrip("/"))
    if domain and not domain.startswith("www."):
        parties.append(f"https://www.{domain}".rstrip("/"))
    if environment != "production" and request_url:
        parsed = urlparse(request_url)
        if parsed.scheme in {"http", "https"} and parsed.hostname in {
            "localhost",
            "127.0.0.1",
            # Development hostname allowlist, not a socket bind address.
            "0.0.0.0",  # nosec B104
        }:
            parties.append(f"{parsed.scheme}://{parsed.netloc}".rstrip("/"))
    return sorted(set(parties))


def validate_clerk_session_claims(
    claims: dict,
    authorized_parties: list[str],
    now: int | None = None,
    clock_skew_seconds: int = 5,
) -> dict:
    now = int(time.time()) if now is None else int(now)
    subject = claims.get("sub")
    session_id = claims.get("sid")
    if not isinstance(subject, str) or not re.fullmatch(r"user_[A-Za-z0-9_-]{1,128}", subject):
        raise SessionVerificationError("Session token is missing a Clerk user subject.")
    if not isinstance(session_id, str) or not re.fullmatch(r"sess_[A-Za-z0-9_-]{1,128}", session_id):
        raise SessionVerificationError("Session token is missing a Clerk session id.")
    try:
        if any(type(claims[key]) not in {int, float} for key in ("exp", "nbf")):
            raise ValueError("Timing claims must be numeric.")
        exp = int(claims["exp"])
        nbf = int(claims["nbf"])
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise SessionVerificationError("Session token is missing valid timing claims.") from exc
    if exp < now - clock_skew_seconds:
        raise SessionVerificationError("Session token is expired.")
    if nbf > now + clock_skew_seconds:
        raise SessionVerificationError("Session token is not yet valid.")
    status = claims.get("sts")
    if status is not None and not isinstance(status, str):
        raise SessionVerificationError("Session token status is invalid.")
    if status == "pending":
        raise SessionVerificationError("Session token status is pending.")
    azp = claims.get("azp")
    if azp is not None and not isinstance(azp, str):
        raise SessionVerificationError("Session token has an invalid authorized party.")
    allowed = {party.rstrip("/") for party in authorized_parties if party}
    if azp and allowed and str(azp).rstrip("/") not in allowed:
        raise SessionVerificationError("Session token has an invalid authorized party.")
    return claims


def pem_public_key_to_der(pem_public_key: str) -> bytes:
    lines = [
        line.strip()
        for line in (pem_public_key or "").splitlines()
        if line.strip() and not line.startswith("-----")
    ]
    if not lines:
        raise SessionVerificationError("CLERK_JWT_KEY must be a PEM public key.")
    try:
        return base64.b64decode("".join(lines), validate=True)
    except Exception as exc:
        raise SessionVerificationError("CLERK_JWT_KEY is not valid PEM.") from exc


async def verify_rs256_signature_with_webcrypto(
    jwt_key: str,
    signing_input: str,
    signature: bytes,
) -> bool:
    try:
        from js import Object, Uint8Array, crypto
        from pyodide.ffi import to_js
    except Exception as exc:
        raise SessionVerificationError(
            "Web Crypto is required for Clerk session signature verification."
        ) from exc

    def js_object(value: dict):
        return to_js(value, dict_converter=Object.fromEntries)

    key_bytes = Uint8Array.new(list(pem_public_key_to_der(jwt_key)))
    data_bytes = Uint8Array.new(list(signing_input.encode("ascii")))
    signature_bytes = Uint8Array.new(list(signature))
    algorithm = js_object({"name": "RSASSA-PKCS1-v1_5", "hash": "SHA-256"})
    try:
        public_key = await crypto.subtle.importKey(
            "spki",
            key_bytes.buffer,
            algorithm,
            False,
            to_js(["verify"]),
        )
        return bool(await crypto.subtle.verify(
            algorithm,
            public_key,
            signature_bytes,
            data_bytes,
        ))
    except Exception as exc:
        raise SessionVerificationError(
            "Clerk session signature verification failed."
        ) from exc


async def fetch_clerk_jwks(secret_key: str) -> dict:
    if not str(secret_key or "").strip():
        raise SessionVerificationError("CLERK_SECRET_KEY is required for Clerk JWKS lookup.")
    try:
        from js import Object, fetch
        from pyodide.ffi import to_js
    except Exception as exc:
        raise SessionVerificationError(
            "Clerk JWKS lookup requires the Workers JavaScript runtime."
        ) from exc
    async def exchange():
        options = {
            "headers": {
                "Accept": "application/json",
                "Authorization": f"Bearer {str(secret_key).strip()}",
            },
            "redirect": "error",
        }
        try:
            from js import AbortSignal
        except ImportError:  # pragma: no cover - the JS API is only available inside Workers.
            pass
        else:
            options["signal"] = AbortSignal.timeout(int(CLERK_JWKS_TIMEOUT_SECONDS * 1000))
        response = await fetch(CLERK_BACKEND_JWKS_URL, to_js(options, dict_converter=Object.fromEntries))
        return await read_json_response_bytes(
            response, max_bytes=MAX_CLERK_JWKS_BODY_BYTES, max_chunks=MAX_CLERK_JWKS_BODY_CHUNKS,
        )

    try:
        raw = await asyncio.wait_for(exchange(), timeout=CLERK_JWKS_TIMEOUT_SECONDS)
        payload = parse_json_value(raw)
    except Exception as exc:
        raise SessionVerificationError("Clerk JWKS lookup failed.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
        raise SessionVerificationError("Clerk JWKS response is invalid.")
    return payload


def cacheable_clerk_jwks(payload) -> bool:
    if not isinstance(payload, dict) or payload.keys() != {"keys"}:
        return False
    keys = payload["keys"]
    return isinstance(keys, list) and bool(keys) and all(
        isinstance(key, dict)
        and key.keys() <= JWKS_PUBLIC_RSA_FIELDS
        and key.get("kty") == "RSA"
        and all(isinstance(key.get(name), str) and key[name] for name in ("kid", "n", "e"))
        and key.get("alg") in (None, "RS256")
        and key.get("use") in (None, "sig")
        and ("ext" not in key or type(key["ext"]) is bool)
        and ("key_ops" not in key or key["key_ops"] == ["verify"])
        for key in keys
    )


async def cached_clerk_jwks(scope: str, fetcher) -> dict:
    """Use a named edge cache only for the provider's short-lived public key set."""
    try:
        from js import Response, caches
    except ImportError:
        return await fetcher()

    cache = None
    cache_key = f"https://workdoe.com/__internal-cache/clerk-jwks/{scope}"

    async def read():
        nonlocal cache
        cache = await caches.open("workdoe-clerk-jwks-v1")
        response = await cache.match(cache_key)
        if response is None:
            return None
        raw = await read_json_response_bytes(
            response, max_bytes=MAX_CLERK_JWKS_BODY_BYTES, max_chunks=MAX_CLERK_JWKS_BODY_CHUNKS,
        )
        record = parse_json_value(raw)
        if not isinstance(record, dict) or type(record.get("expires_at")) is not int:
            return None
        now = time.time()
        if not now < record["expires_at"] <= now + CLERK_JWKS_CACHE_TTL_SECONDS:
            return None
        return record.get("jwks")

    try:
        payload = await asyncio.wait_for(read(), timeout=CLERK_JWKS_CACHE_TIMEOUT_SECONDS)
    except Exception:  # noqa: BLE001 - The cache is optional and may raise JS-backed errors.
        payload = None
    if cacheable_clerk_jwks(payload):
        return payload

    payload = await fetcher()
    if cache is not None and cacheable_clerk_jwks(payload):
        try:
            from js import Object
            from pyodide.ffi import to_js

            options = to_js(
                {"headers": {"Cache-Control": f"max-age={CLERK_JWKS_CACHE_TTL_SECONDS}"}},
                dict_converter=Object.fromEntries,
            )
            record = {"expires_at": int(time.time()) + CLERK_JWKS_CACHE_TTL_SECONDS, "jwks": payload}
            response = Response.new(json.dumps(record, separators=(",", ":")), options)
            await asyncio.wait_for(cache.put(cache_key, response), timeout=CLERK_JWKS_CACHE_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 - A failed cache write must not invalidate fresh provider keys.
            return payload
    return payload


def clerk_jwk_for_key_id(jwks: dict, key_id: str) -> dict:
    matches = [key for key in jwks.get("keys", []) if isinstance(key, dict) and key.get("kid") == key_id]
    if len(matches) != 1 or matches[0].get("kty") != "RSA":
        raise SessionVerificationError("Clerk JWKS does not identify one RSA session signing key.")
    return matches[0]


async def verify_rs256_signature_with_jwk(
    jwk: dict,
    signing_input: str,
    signature: bytes,
) -> bool:
    try:
        from js import Object, Uint8Array, crypto
        from pyodide.ffi import to_js
    except Exception as exc:
        raise SessionVerificationError(
            "Web Crypto is required for Clerk session signature verification."
        ) from exc

    algorithm = to_js(
        {"name": "RSASSA-PKCS1-v1_5", "hash": "SHA-256"},
        dict_converter=Object.fromEntries,
    )
    try:
        public_key = await crypto.subtle.importKey(
            "jwk",
            to_js(jwk, dict_converter=Object.fromEntries),
            algorithm,
            False,
            to_js(["verify"]),
        )
        return bool(
            await crypto.subtle.verify(
                algorithm,
                public_key,
                Uint8Array.new(list(signature)).buffer,
                Uint8Array.new(list(signing_input.encode("ascii"))).buffer,
            )
        )
    except Exception as exc:
        raise SessionVerificationError(
            "Clerk JWKS session signature verification failed."
        ) from exc


async def verify_clerk_session_token(
    token: str,
    jwt_key: str,
    authorized_parties: list[str],
    now: int | None = None,
    signature_verifier=None,
    secret_key: str = "",
    jwks_fetcher=None,
    jwk_signature_verifier=None,
) -> dict:
    if not token:
        raise SessionVerificationError("Session token is required.")
    header, claims, signing_input, signature = decode_unverified_jwt(token)
    # Reject invalid claims before key lookup; only a verified signature authenticates.
    validate_clerk_session_claims(claims, authorized_parties, now=now)
    verified = False
    if jwt_key:
        verifier = signature_verifier or verify_rs256_signature_with_webcrypto
        try:
            verified = verifier(jwt_key, signing_input, signature)
            if inspect.isawaitable(verified):
                verified = await verified
        except SessionVerificationError:
            verified = False
    if not verified and secret_key:
        key_id = header.get("kid")
        if not key_id:
            raise SessionVerificationError("Session token signature is invalid.")
        fetcher = jwks_fetcher or fetch_clerk_jwks
        jwks = fetcher(secret_key)
        if inspect.isawaitable(jwks):
            jwks = await jwks
        verifier = jwk_signature_verifier or verify_rs256_signature_with_jwk
        verified = verifier(
            clerk_jwk_for_key_id(jwks, key_id),
            signing_input,
            signature,
        )
        if inspect.isawaitable(verified):
            verified = await verified
    if not verified:
        raise SessionVerificationError("Session token signature is invalid.")
    return validate_clerk_session_claims(
        claims,
        authorized_parties=authorized_parties,
        now=now,
    )
