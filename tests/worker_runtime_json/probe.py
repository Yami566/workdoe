from __future__ import annotations

import base64
import json

from clerk_onboarding import claims_with_verified_clerk_email
from clerk_sessions import SessionVerificationError, verify_clerk_session_token
from clerk_webhooks import (
    SvixVerificationError,
    clerk_user_sync_payload,
    svix_signature,
    verify_svix_signature,
)
from entry import OnboardingError, request_json_object, response_json_object
from json_values import JsonDataError, parse_json_value
from workers import Request, Response, WorkerEntrypoint

NOW = 1700000000


def segment(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")


async def rejects(awaitable, error_type):
    try:
        await awaitable
    except error_type:
        return True
    return False


def request_for(raw):
    return Request(
        "https://runtime.invalid/api/test",
        method="POST",
        headers={"Content-Type": "application/json", "Content-Length": str(len(raw.encode()))},
        body=raw,
    )


def verify_event(raw, *, invalid_signature=False):
    fixture = "whsec_" + base64.b64encode(b"local runtime fixture only").decode()
    signature = svix_signature(secret=fixture, message_id="msg_fixture", timestamp=str(NOW), raw_body=raw)
    return verify_svix_signature(
        secret=fixture,
        headers={
            "svix-id": "msg_fixture",
            "svix-timestamp": str(NOW),
            "svix-signature": "v1,invalid" if invalid_signature else f"v1,{signature}",
        },
        raw_body=raw,
        now=NOW,
    )


async def token_checks(checks):
    calls = []

    def forbidden_lookup(*_args):
        calls.append(True)
        raise AssertionError("Invalid input must reject before key or signature work.")

    defaults = {
        "sub": "user_synthetic_probe", "sid": "sess_synthetic_probe",
        "exp": NOW + 300, "nbf": NOW - 300, "azp": "https://workdoe.com",
    }
    for name, changes, signature in (
        ("malformed-signature", {}, "a"),
        ("expired", {"exp": 10}, "c3ludGhldGlj"),
        ("wrong-origin", {"azp": "https://untrusted.example"}, "c3ludGhldGlj"),
        ("pending", {"sts": "pending"}, "c3ludGhldGlj"),
        ("nonfinite-time", {"exp": float("inf")}, "c3ludGhldGlj"),
        ("deep-json", {}, "c3ludGhldGlj"),
        ("object-subject", {"sub": {"value": "untrusted"}}, "c3ludGhldGlj"),
    ):
        payload = segment(defaults | changes)
        if name == "deep-json":
            payload = base64.urlsafe_b64encode(b"[" * 10000 + b"0" + b"]" * 10000).decode().rstrip("=")
        token = ".".join((segment({"alg": "RS256"}), payload, signature))
        checks[f"token-{name}"] = await rejects(
            verify_clerk_session_token(
                token, jwt_key="synthetic-pem", secret_key="synthetic-key",  # pragma: allowlist secret - unusable runtime test fixture.
                authorized_parties=["https://workdoe.com"], now=NOW,
                signature_verifier=forbidden_lookup, jwks_fetcher=forbidden_lookup,
            ),
            SessionVerificationError,
        )
    for name, raw in (
        ("valid-flat", json.dumps(defaults)),
        ("valid-deep-custom", json.dumps(defaults)[:-1] + ',"metadata":' + "[" * 10000 + "0" + "]" * 10000 + "}"),
    ):
        token = ".".join((segment({"alg": "RS256"}), base64.urlsafe_b64encode(raw.encode()).decode().rstrip("="), "c3ludGhldGlj"))
        verified = await verify_clerk_session_token(
            token, jwt_key="synthetic-pem", authorized_parties=["https://workdoe.com"],
            now=NOW, signature_verifier=lambda *_args: True,
        )
        checks[f"token-{name}"] = verified["sub"] == defaults["sub"]
    checks["token-no-unexpected-lookups"] = not calls


class Default(WorkerEntrypoint):
    async def fetch(self, _request):
        checks = {}
        scope = {"scope_answers": {"access": ["ground-floor"]}, "text": 'Literal [brackets] and "quotes"', "optional": None}
        checks["api-normal-scope"] = await request_json_object(request_for(json.dumps(scope))) == scope
        text_value = {"text": "Caf\u00e9"}
        checks["api-utf8-length"] = await request_json_object(request_for(json.dumps(text_value, ensure_ascii=False))) == text_value
        paired = {"text": "\U0001d11e", "literal": r"\ud800"}
        checks["api-paired-surrogates-and-literal-escape-preserved"] = (
            await request_json_object(request_for(json.dumps(paired))) == paired
        )
        deep = '{"details":' + "[" * 3000 + "0" + "]" * 3000 + "}"
        for name, raw in (
            ("array", "[]"), ("deep", deep), ("nan", '{"value":NaN}'),
            ("overflow", '{"value":1e999}'), ("oversize", " " * 9000),
            ("lone-high-surrogate", r'{"description":"\ud800"}'),
            ("lone-low-surrogate", r'{"\udfff":"text"}'),
            ("nested-surrogate", r'{"scope":{"answers":["ok\ud800"]}}'),
        ):
            checks[f"api-{name}-rejected"] = await rejects(request_json_object(request_for(raw)), OnboardingError)

        user = {
            "id": "user_synthetic_probe", "primary_email_address_id": "id_fixture",
            "email_addresses": [{"id": "id_fixture", "email_address": "fixture@example.invalid", "verification": {"status": "verified"}}],
            "public_metadata": {"preferences": ["local"]},
        }
        decoded = await response_json_object(Response(json.dumps(user)))
        claims = claims_with_verified_clerk_email({"sub": user["id"]}, decoded)
        checks["provider-verified-email-preserved"] = claims["email_verified"] is True and claims["email"] == "fixture@example.invalid"
        success = {"success": True, "hostname": "workdoe.com", "action": "job-post", "error-codes": []}
        checks["provider-turnstile-preserved"] = await response_json_object(Response(json.dumps(success))) == success
        checks["provider-non-200-rejected"] = await rejects(
            response_json_object(Response(json.dumps(success), status=503)), JsonDataError,
        )
        for name, raw in (("array", "[]"), ("deep", deep), ("overflow", '{"value":1e999}'), ("oversize", " " * (256 * 1024 + 1))):
            checks[f"provider-{name}-rejected"] = await rejects(response_json_object(Response(raw)), JsonDataError)

        event = {"object": "event", "type": "user.updated", "data": user}
        verified = verify_event(json.dumps(event))
        sync = clerk_user_sync_payload(verified)
        checks["webhook-normal-sync"] = sync["email_verified"] == 1 and sync["status"] == "active"
        for name, raw in (
            ("array", b"[]"), ("utf8", b"\xff"), ("nan", b'{"object":"event","type":"user.updated","data":NaN}'),
            ("surrogate", br'{"object":"event","type":"user.updated","data":{"id":"\ud800"}}'),
            ("deep", b'{"object":"event","type":"user.updated","data":' + b"[" * 10000 + b"0" + b"]" * 10000 + b"}"),
        ):
            try:
                verify_event(raw)
                checks[f"webhook-{name}-rejected"] = False
            except SvixVerificationError:
                checks[f"webhook-{name}-rejected"] = True
        try:
            verify_event(b"not-json", invalid_signature=True)
            checks["webhook-signature-first"] = False
        except SvixVerificationError as exc:
            checks["webhook-signature-first"] = "does not match" in str(exc)

        depth_eight = {"value": "supported"}
        for _ in range(7):
            depth_eight = {"child": depth_eight}
        checks["decoder-depth-eight"] = parse_json_value(json.dumps(depth_eight)) == depth_eight
        try:
            parse_json_value(json.dumps({"child": depth_eight}))
            checks["decoder-depth-nine-rejected"] = False
        except JsonDataError:
            checks["decoder-depth-nine-rejected"] = True
        await token_checks(checks)
        passed = all(checks.values())
        return Response.json({"passed": passed, "check_count": len(checks), "checks": checks}, status=200 if passed else 500)
