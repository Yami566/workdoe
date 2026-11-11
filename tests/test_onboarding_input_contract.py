from __future__ import annotations

import asyncio
import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from test_cloudflare_release import (
    load_clerk_onboarding_module,
    load_worker_entry_module,
)
from worker_http_fixture import BodyStream

PROFILE = {"role": "client", "display_name": "Garden project", "company_name": ""}
BAD_TEXT = ([], ["private-value"], {}, {"private-value": "text"}, True, False, 42, 1.25)
CLAIMS = {"sub": "user_input_fixture", "sid": "sess_input_fixture"}


def request(body, *, content_type="application/json"):
    raw = json.dumps(body).encode()
    return SimpleNamespace(
        method="POST",
        headers={"Content-Type": content_type, "Content-Length": str(len(raw))},
        body=BodyStream([raw]),
    )


def provider_response(**overrides):
    raw = json.dumps(
        {
            "id": CLAIMS["sub"],
            "primary_email_address_id": "email_input_fixture",
            "email_addresses": [
                {
                    "id": "email_input_fixture",
                    "email_address": "verified@example.invalid",
                    "verification": {"status": "verified"},
                }
            ],
            **overrides,
        }
    )
    chunk = raw.encode()
    reader = SimpleNamespace(
        read=AsyncMock(side_effect=[
            SimpleNamespace(done=False, value=SimpleNamespace(byteLength=len(chunk), to_py=lambda: chunk)),
            SimpleNamespace(done=True),
        ]),
        cancel=AsyncMock(),
        releaseLock=Mock(),
    )
    return SimpleNamespace(
        ok=True,
        status=200,
        headers={},
        body=SimpleNamespace(getReader=lambda: reader),
        text=AsyncMock(return_value=raw),
    )


class OnboardingInputContractTests(unittest.IsolatedAsyncioTestCase):
    def worker(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(DB=object(), WORKDOE_ENV="local", CLERK_SECRET_KEY="local-fixture-only")
        worker.verified_clerk_claims = AsyncMock(return_value=CLAIMS)
        return module, worker

    async def test_worker_rejects_nontext_profile_fields_before_user_lookup(self):
        module, worker = self.worker()
        for field in PROFILE:
            for value in BAD_TEXT:
                with self.subTest(field=field, value=value):
                    with (
                        patch.object(
                            module, "fetch", AsyncMock(return_value=provider_response())
                        ) as fetch,
                        patch.object(
                            module, "db_run", AsyncMock(return_value={"results": []})
                        ) as db,
                    ):
                        response = await worker.auth_onboard(
                            request({**PROFILE, field: value})
                        )
                    self.assertEqual(response.status, 400)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(
                        json.loads(response.body),
                        {"ok": False, "error": "Onboarding request was not accepted."},
                    )
                    fetch.assert_not_awaited()
                    db.assert_not_awaited()

    async def test_worker_rejects_bad_envelope_before_user_lookup(self):
        module, worker = self.worker()
        for body, content_type in (([], "application/json"), (PROFILE, "text/plain")):
            with self.subTest(content_type=content_type, body=body):
                with (
                    patch.object(
                        module, "fetch", AsyncMock(return_value=provider_response())
                    ) as fetch,
                    patch.object(
                        module, "db_run", AsyncMock(return_value={"results": []})
                    ) as db,
                ):
                    response = await worker.auth_onboard(
                        request(body, content_type=content_type)
                    )
                self.assertEqual(response.status, 400)
                fetch.assert_not_awaited()
                db.assert_not_awaited()

    async def test_invalid_profile_does_not_consume_limiter_or_call_clerk(self):
        for overrides in (
            {"role": "admin"}, {"display_name": "  "},
            {"company_name": "private@example.invalid"},
            {"display_name": "100 Private Street Services"},
        ):
            module, worker = self.worker()
            limiter = AsyncMock(return_value={"success": True})
            worker.env.WRITE_RATE_LIMITER = SimpleNamespace(limit=limiter)
            with (
                self.subTest(fields=overrides),
                patch.object(module, "fetch", AsyncMock(return_value=provider_response())) as fetch,
                patch.object(module, "provision_clerk_account", AsyncMock()) as provision,
            ):
                response = await worker.auth_onboard(request(PROFILE | overrides))
                self.assertEqual(response.status, 400)
                limiter.assert_not_awaited()
                fetch.assert_not_awaited()
                provision.assert_not_awaited()

    async def test_production_onboarding_denies_before_provider_lookup_when_limited(self):
        for mode, expected in (("over-limit", 429), ("binding-error", 503), ("missing-binding", 503)):
            module, worker = self.worker()
            worker.env.WORKDOE_ENV = "production"
            limiter = AsyncMock(return_value={"success": False})
            if mode == "binding-error":
                limiter.side_effect = RuntimeError("private diagnostic")
            if mode != "missing-binding":
                worker.env.WRITE_RATE_LIMITER = SimpleNamespace(limit=limiter)
            with (
                self.subTest(mode=mode),
                patch.object(module, "fetch", AsyncMock(return_value=provider_response())) as fetch,
                patch.object(module, "provision_clerk_account", AsyncMock()) as provision,
            ):
                result = await worker.auth_onboard(request(PROFILE | {"email": "caller@example.invalid"}))
                self.assertEqual(result.status, expected)
                self.assertEqual(result.headers["Cache-Control"], "no-store")
                self.assertEqual(result.headers.get("Retry-After"), "60" if expected == 429 else None)
                self.assertNotIn("private diagnostic", result.body)
                fetch.assert_not_awaited()
                provision.assert_not_awaited()
            if mode != "missing-binding":
                digest = hashlib.sha256(CLAIMS["sub"].encode()).hexdigest()
                limiter.assert_awaited_once_with({"key": f"clerk-onboard:{digest}"})

    async def test_worker_still_authenticates_before_reading_profile(self):
        module, worker = self.worker()
        worker.verified_clerk_claims.side_effect = module.SessionVerificationError(
            "Synthetic rejection"
        )
        incoming = request(PROFILE)
        with (
            patch.object(module, "fetch", AsyncMock()) as fetch,
            patch.object(module, "db_run", AsyncMock()) as db,
        ):
            response = await worker.auth_onboard(incoming)
        self.assertEqual(response.status, 401)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("Synthetic rejection", response.body)
        self.assertFalse(incoming.body.opened)
        fetch.assert_not_awaited()
        db.assert_not_awaited()

    async def test_clerk_lookup_times_out_waiting_for_headers_or_body_before_d1(self):
        async def stall(*_args, **_options):
            await asyncio.Event().wait()

        for stage in ("headers", "body"):
            module, worker = self.worker()
            response = provider_response()
            reader = response.body.getReader()
            if stage == "body":
                reader.read = AsyncMock(side_effect=stall)
            transport = AsyncMock(side_effect=stall) if stage == "headers" else AsyncMock(return_value=response)
            with (
                self.subTest(stage=stage),
                patch.object(module, "CLERK_USER_LOOKUP_TIMEOUT_SECONDS", 0.01, create=True),
                patch.object(module, "fetch", transport),
                patch.object(module, "provision_clerk_account", AsyncMock()) as provision,
            ):
                result = await asyncio.wait_for(worker.auth_onboard(request(PROFILE)), timeout=0.5)
                self.assertEqual(result.status, 503)
                self.assertEqual(result.headers["Cache-Control"], "no-store")
                provision.assert_not_awaited()
                response.text.assert_not_awaited()
                if stage == "body":
                    reader.cancel.assert_awaited_once()
                    reader.releaseLock.assert_called_once()

    async def test_clerk_lookup_rejects_oversize_before_converting_or_writing(self):
        module, worker = self.worker()
        response = provider_response()
        reader = response.body.getReader()
        convert = Mock(side_effect=AssertionError("Oversize chunk must not be converted"))
        reader.read = AsyncMock(return_value=SimpleNamespace(
            done=False, value=SimpleNamespace(byteLength=256 * 1024 + 1, to_py=convert),
        ))
        with (
            patch.object(module, "fetch", AsyncMock(return_value=response)),
            patch.object(module, "provision_clerk_account", AsyncMock()) as provision,
        ):
            result = await worker.auth_onboard(request(PROFILE))
        self.assertEqual(result.status, 503)
        provision.assert_not_awaited()
        convert.assert_not_called()
        response.text.assert_not_awaited()
        reader.cancel.assert_awaited_once()
        reader.releaseLock.assert_called_once()

    async def test_worker_keeps_provider_identity_and_existing_role_authoritative(self):
        module, worker = self.worker()
        worker.env.WORKDOE_ENV = "production"
        limiter = AsyncMock(return_value={"success": True})
        worker.env.WRITE_RATE_LIMITER = SimpleNamespace(limit=limiter)

        async def after_limiter(*_args, **_options):
            limiter.assert_awaited_once()
            return provider_response()

        linked = {
            "id": 17,
            "role": "contractor",
            "display_name": "Existing storefront",
            "company_name": "Storefront",
            "status": "active",
        }
        with (
            patch.object(
                module, "fetch", AsyncMock(side_effect=after_limiter)
            ) as fetch,
            patch.object(
                module,
                "provision_clerk_account",
                AsyncMock(return_value=(linked, False)),
            ) as provision,
        ):
            response = await worker.auth_onboard(
                request(
                    {
                        **PROFILE,
                        "email": "untrusted@example.invalid",
                        "company_name": None,
                    }
                )
            )
        self.assertEqual(response.status, 200)
        self.assertEqual(
            json.loads(response.body)["workdoe_user"]["role"], "contractor"
        )
        self.assertFalse(json.loads(response.body)["created"])
        self.assertEqual(
            fetch.await_args.args[0],
            "https://api.clerk.com/v1/users/user_input_fixture",
        )
        provision.assert_awaited_once()
        self.assertEqual(provision.await_args.args[1], CLAIMS["sub"])
        self.assertEqual(provision.await_args.args[2]["email"], "verified@example.invalid")

    async def test_worker_session_only_returns_navigation_state_and_role(self):
        module, worker = self.worker()
        request = SimpleNamespace(method="GET")
        linked = {
            "id": 17, "role": "contractor", "status": "active",
            "display_name": "Private label", "company_name": "Private company",
        }
        for rows, expected_status, payload in (
            ([], 200, {"authenticated": True, "onboarding_required": True, "workdoe_user": None}),
            ([linked], 200, {
                "authenticated": True, "onboarding_required": False, "workdoe_user": {"role": "contractor"},
            }),
            ([linked | {"status": "suspended"}], 403, {
                "authenticated": False, "error": "Workdoe account is not active.",
            }),
        ):
            with (
                self.subTest(status=expected_status, rows=len(rows)),
                patch.object(module, "db_run", AsyncMock(return_value={"results": rows})) as db,
            ):
                response = await worker.auth_session(request)
                self.assertEqual(response.status, expected_status)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(json.loads(response.body), payload)
                self.assertIn("SELECT role, status", db.await_args.args[1])
                self.assertEqual(db.await_args.args[2:], (CLAIMS["sub"],))

    async def test_worker_rejects_a_secondary_email_or_mismatched_user_before_d1(self):
        module, worker = self.worker()
        for overrides in (
            {"primary_email_address_id": None},
            {"primary_email_address_id": "missing_address"},
            {"primary_email_address_id": True},
            {"id": "user_other_fixture"},
            {"id": None},
        ):
            with (
                self.subTest(fields=overrides),
                patch.object(module, "fetch", AsyncMock(return_value=provider_response(**overrides))),
                patch.object(module, "db_run", AsyncMock(return_value={"results": []})) as db,
            ):
                response = await worker.auth_onboard(request(PROFILE))
                self.assertEqual(response.status, 400)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(json.loads(response.body), {"ok": False, "error": "Onboarding request was not accepted."})
                db.assert_not_awaited()

    async def test_worker_rejects_disabled_or_malformed_provider_account_before_provisioning(self):
        for flag in ("banned", "locked", "disabled", "deprovisioned"):
            for state in (True, "true", 0, None):
                module, worker = self.worker()
                with (
                    self.subTest(flag=flag, state=state),
                    patch.object(module, "fetch", AsyncMock(return_value=provider_response(**{flag: state}))) as fetch,
                    patch.object(
                        module, "provision_clerk_account",
                        AsyncMock(return_value=({"id": 21, "status": "active"}, True)),
                    ) as provision,
                ):
                    response = await worker.auth_onboard(request(PROFILE))
                    self.assertEqual(response.status, 400)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(json.loads(response.body), {"ok": False, "error": "Onboarding request was not accepted."})
                    fetch.assert_awaited_once()
                    provision.assert_not_awaited()

    def test_pure_helper_rejects_nontext_profile_fields(self):
        module = load_clerk_onboarding_module()
        for field in PROFILE:
            for value in BAD_TEXT:
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaises(module.OnboardingError),
                ):
                    module.onboarding_profile({**PROFILE, field: value})

    def test_valid_profile_normalization_and_null_optional_company_are_preserved(self):
        module = load_clerk_onboarding_module()
        self.assertEqual(
            module.onboarding_payload(
                {"email": " Verified@Example.invalid ", "email_verified": True},
                module.onboarding_profile({
                    "role": " Client ",
                    "display_name": " Garden   project ",
                    "company_name": None,
                }),
            ),
            {
                "email": "verified@example.invalid",
                "role": "client",
                "display_name": "Garden project",
                "company_name": "Garden project",
            },
        )
