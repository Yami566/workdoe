from __future__ import annotations

import base64
import inspect
import json
import time


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
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def decode_json_part(value: str) -> dict:
    try:
        decoded = base64url_decode(value).decode("utf-8")
        data = json.loads(decoded)
    except Exception as exc:
        raise SessionVerificationError("JWT segment is not valid JSON.") from exc
    if not isinstance(data, dict):
        raise SessionVerificationError("JWT segment must be an object.")
    return data


def decode_unverified_jwt(token: str) -> tuple[dict, dict, str, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise SessionVerificationError("Session token must be a three-part JWT.")
    header = decode_json_part(parts[0])
    claims = decode_json_part(parts[1])
    if header.get("alg") != "RS256":
        raise SessionVerificationError("Session token must use RS256.")
    signing_input = f"{parts[0]}.{parts[1]}"
    signature = base64url_decode(parts[2])
    return header, claims, signing_input, signature


def authorized_parties_from_env(env) -> list[str]:
    public_url = str(getattr(env, "WORKDOE_PUBLIC_URL", "") or "").rstrip("/")
    domain = str(getattr(env, "WORKDOE_DOMAIN", "workdoe.com") or "workdoe.com").strip()
    parties = []
    if public_url:
        parties.append(public_url)
    if domain:
        parties.append(f"https://{domain}".rstrip("/"))
    if domain and not domain.startswith("www."):
        parties.append(f"https://www.{domain}".rstrip("/"))
    return sorted(set(parties))


def validate_clerk_session_claims(
    claims: dict,
    authorized_parties: list[str],
    now: int | None = None,
    clock_skew_seconds: int = 5,
) -> dict:
    now = int(time.time()) if now is None else int(now)
    subject = str(claims.get("sub") or "")
    session_id = str(claims.get("sid") or "")
    if not subject.startswith("user_"):
        raise SessionVerificationError("Session token is missing a Clerk user subject.")
    if not session_id.startswith("sess_"):
        raise SessionVerificationError("Session token is missing a Clerk session id.")
    try:
        exp = int(claims["exp"])
        nbf = int(claims["nbf"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionVerificationError("Session token is missing valid timing claims.") from exc
    if exp < now - clock_skew_seconds:
        raise SessionVerificationError("Session token is expired.")
    if nbf > now + clock_skew_seconds:
        raise SessionVerificationError("Session token is not yet valid.")
    if claims.get("sts") == "pending":
        raise SessionVerificationError("Session token status is pending.")
    azp = claims.get("azp")
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
    public_key = await crypto.subtle.importKey(
        "spki",
        key_bytes.buffer,
        algorithm,
        False,
        ["verify"],
    )
    return bool(
        await crypto.subtle.verify(
            algorithm,
            public_key,
            signature_bytes,
            data_bytes,
        )
    )


async def verify_clerk_session_token(
    token: str,
    jwt_key: str,
    authorized_parties: list[str],
    now: int | None = None,
    signature_verifier=None,
) -> dict:
    if not token:
        raise SessionVerificationError("Session token is required.")
    if not jwt_key:
        raise SessionVerificationError("CLERK_JWT_KEY is required.")
    _, claims, signing_input, signature = decode_unverified_jwt(token)
    verifier = signature_verifier or verify_rs256_signature_with_webcrypto
    verified = verifier(jwt_key, signing_input, signature)
    if inspect.isawaitable(verified):
        verified = await verified
    if not verified:
        raise SessionVerificationError("Session token signature is invalid.")
    return validate_clerk_session_claims(
        claims,
        authorized_parties=authorized_parties,
        now=now,
    )
