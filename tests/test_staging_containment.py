import io
import json
from base64 import urlsafe_b64encode
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from test_cloudflare_release import load_worker_entry_module
from worker_http_fixture import BodyStream

STAGING_HOST = "staging-drill.workdoe.com"
STAGING_URL = f"https://{STAGING_HOST}"
CLERK_HOST = "workdoe-stage-fixture.clerk.accounts.dev"
CLERK_ORIGIN = f"https://{CLERK_HOST}"


def fixture_publishable_key(host: str) -> str:
    return "pk_test_" + urlsafe_b64encode(f"{host}$".encode()).decode().rstrip("=")


STAGING_CLERK = {
    "WORKDOE_AUTH_PROVIDER": "clerk",
    "CLERK_PUBLISHABLE_KEY": fixture_publishable_key(CLERK_HOST),
    "CLERK_SECRET_KEY": "sk_test_" + "fixture-not-a-key",  # pragma: allowlist secret
}


class StagingContainmentTests(IsolatedAsyncioTestCase):
    def worker(self, **overrides):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(**({
            "WORKDOE_ENV": " Staging ",
            "WORKDOE_PUBLIC_URL": STAGING_URL,
            "WORKDOE_DOMAIN": STAGING_HOST,
        } | overrides))
        return module, worker

    async def test_staging_rejects_unreviewed_origins_before_routing(self):
        _, worker = self.worker()
        for url in (
            "http://workdoe.com/styles.css",
            "https://workdoe.com/api/jobs/open",
            "https://www.workdoe.com/health",
            "https://fixture.example.workers.dev/health",
            "https://staging-other.workdoe.com/health",
            f"{STAGING_URL}:8443/health",
            f"{STAGING_URL}@outside.invalid/health",
            f"http://{STAGING_HOST}/health",
        ):
            with self.subTest(url=url):
                response = await worker.fetch(SimpleNamespace(url=url, method="HEAD"))
                self.assertEqual((response.status, response.body), (404, ""))
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertNotIn("Location", response.headers)

    async def test_missing_mode_seals_only_on_reviewed_staging_hostname(self):
        _, worker = self.worker()
        health = SimpleNamespace(url=f"{STAGING_URL}/health", method="GET", headers={})
        response = await worker.fetch(health)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["X-Workdoe-Mode"], "sealed")
        response = await worker.fetch(SimpleNamespace(url=f"{STAGING_URL}/api/jobs/open", method="GET"))
        self.assertEqual(response.status, 503)
        worker.env.WORKDOE_DOMAIN = "workdoe.com"
        self.assertEqual((await worker.fetch(health)).status, 404)

    async def test_normal_staging_never_dispatches_mail_or_reads_misrouted_body(self):
        module, worker = self.worker(WORKDOE_WRITE_MODE="normal")
        for queue in ("workdoe-staging-email", "workdoe-email", "workdoe-media-review", "unknown"):
            with self.subTest(queue=queue):
                receipt = UnreadableReceipt()
                with (
                    patch.object(module, "process_email_queue_message", AsyncMock()) as email,
                    patch.object(module, "dispatch_media_review_message", AsyncMock()) as media,
                    patch.object(module, "record_event", AsyncMock()) as audit,
                ):
                    await worker.queue(SimpleNamespace(queue=queue, messages=[receipt]))
                email.assert_not_awaited()
                media.assert_not_awaited()
                audit.assert_not_awaited()
                if queue == "workdoe-staging-email":
                    receipt.ack.assert_called_once_with()
                    receipt.retry.assert_not_called()
                else:
                    receipt.ack.assert_not_called()
                    receipt.retry.assert_called_once_with({"delaySeconds": module.RECOVERY_RETRY_SECONDS})

    async def test_staging_cannot_call_production_proxy_webhook_or_queue_login_codes(self):
        module, worker = self.worker(
            WORKDOE_WRITE_MODE="normal",
            WORKDOE_AUTH_PROVIDER="workdoe_email_code",
            CLERK_SECRET_KEY="sk_live_" + "fixture-not-a-key",  # pragma: allowlist secret
            CLERK_WEBHOOK_SECRET="fixture-only",  # pragma: allowlist secret
            EMAIL_QUEUE=SimpleNamespace(send=AsyncMock()),
            DB=object(),
        )
        with patch.object(module, "fetch", AsyncMock()) as outbound:
            for path, method in (
                ("/__clerk/v1/environment", "GET"),
                ("/__clerk/v1/environment", "HEAD"),
                ("/clerk/webhook", "POST"),
                ("/api/auth/code/request", "POST"),
                ("/api/auth/code/verify", "POST"),
            ):
                with self.subTest(path=path, method=method):
                    response = await worker.fetch(SimpleNamespace(
                        url=STAGING_URL + path, method=method,
                        headers={"X-Workdoe-Request": "same-origin"},
                    ))
                    self.assertEqual(response.status, 404)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    if method == "HEAD":
                        self.assertEqual(response.body, "")
        outbound.assert_not_awaited()
        worker.env.EMAIL_QUEUE.send.assert_not_awaited()

    async def test_staging_never_enqueues_operator_report_mail(self):
        module, worker = self.worker(
            WORKDOE_WRITE_MODE="normal",
            WORKDOE_MARKETPLACE_EMAIL_ENABLED="true",
            EMAIL_QUEUE=SimpleNamespace(send=AsyncMock()),
        )
        with patch.object(module, "record_event_best_effort", AsyncMock()) as audit:
            queued = await module.queue_operator_report_alert(
                worker.env, report_id=1, target_type="job", target_id=2,
            )
        self.assertFalse(queued)
        worker.env.EMAIL_QUEUE.send.assert_not_awaited()
        audit.assert_not_awaited()

    async def test_staging_clerk_is_explicitly_test_only(self):
        for override in (
            {},
            {"CLERK_PUBLISHABLE_KEY": "pk_live_fixture"},
            {"CLERK_SECRET_KEY": "sk_live_" + "fixture-not-a-key"},  # pragma: allowlist secret
            {"CLERK_JWT_KEY": "unexpected static public key"},
            {"CLERK_PUBLISHABLE_KEY": fixture_publishable_key("staging.example.invalid")},
            {"CLERK_PUBLISHABLE_KEY": fixture_publishable_key("[bad")},
            {"WORKDOE_AUTH_PROVIDER": "workdoe_email_code"},
        ):
            with self.subTest(fields=override.keys()):
                settings = STAGING_CLERK | override
                _, worker = self.worker(
                    WORKDOE_WRITE_MODE="normal",
                    CLERK_FRONTEND_API_URL="https://workdoe.com/__clerk", **settings,
                )
                response = await worker.fetch(SimpleNamespace(
                    url=f"{STAGING_URL}/login?embed=1", method="GET", headers={},
                ))
                if override:
                    self.assertEqual(response.status, 503)
                    self.assertNotIn("data-clerk-publishable-key", response.body)
                else:
                    self.assertEqual(response.status, 200)
                    self.assertIn(f'src="{CLERK_ORIGIN}/npm/@clerk/', response.body)
                    self.assertIn(CLERK_ORIGIN, response.headers["Content-Security-Policy"])
                    self.assertNotIn("data-clerk-proxy-url", response.body)
                self.assertNotIn("https://workdoe.com/__clerk", response.body)

    async def test_staging_requires_verified_issuer_and_exact_authorized_party(self):
        module, worker = self.worker(**STAGING_CLERK)
        incoming = SimpleNamespace(
            url=f"{STAGING_URL}/api/auth/session",
            headers={"Authorization": "Bearer fixture"},
        )
        for claims, allowed in (
            ({"iss": CLERK_ORIGIN, "azp": STAGING_URL}, True),
            ({"iss": "https://clerk.workdoe.com", "azp": STAGING_URL}, False),
            ({"iss": CLERK_ORIGIN, "azp": "https://workdoe.com"}, False),
            ({"iss": CLERK_ORIGIN}, False),
            ({"azp": STAGING_URL}, False),
        ):
            with (
                self.subTest(claims=claims),
                patch.object(module, "verify_clerk_session_token", AsyncMock(return_value=claims)) as verify,
            ):
                if allowed:
                    self.assertEqual(await worker.verified_clerk_claims(incoming), claims)
                else:
                    with self.assertRaisesRegex(module.SessionVerificationError, "staging site"):
                        await worker.verified_clerk_claims(incoming)
                self.assertEqual(verify.await_args.kwargs["authorized_parties"], [STAGING_URL])
                self.assertEqual(verify.await_args.kwargs["jwt_key"], "")

    async def test_staging_turnstile_requires_the_exact_host_and_action(self):
        module, worker = self.worker(WORKDOE_TURNSTILE_SECRET_KEY="fixture-only")
        expected = {"success": True, "hostname": STAGING_HOST, "action": "job-post"}
        for payload, allowed in (
            (expected, True),
            ({**expected, "hostname": "workdoe.com"}, False),
            ({**expected, "hostname": "staging-other.workdoe.com"}, False),
            ({**expected, "hostname": "localhost"}, False),
            ({**expected, "action": "test"}, False),
            ({**expected, "metadata": {"result_with_testing_key": True}}, False),
            ({**expected, "success": False}, False),
        ):
            with (
                self.subTest(payload=payload),
                patch.object(module, "fetch", AsyncMock(return_value=SimpleNamespace(
                    headers={}, status=200, body=BodyStream([json.dumps(payload).encode()]),
                ))),
            ):
                request = SimpleNamespace(url=f"{STAGING_URL}/api/jobs", headers={})
                verify = module.verify_turnstile_for_request(
                    worker.env, request, {"turnstile_token": "fixture-response"}, "job-post",
                )
                if allowed:
                    self.assertEqual(await verify, expected)
                else:
                    with redirect_stdout(io.StringIO()), self.assertRaises(module.TurnstileError):
                        await verify

    async def test_sealed_staging_retries_both_lanes_before_reading_receipts(self):
        module, worker = self.worker()
        for queue in ("workdoe-staging-email", "workdoe-staging-media-review"):
            receipt = UnreadableReceipt()
            await worker.queue(SimpleNamespace(queue=queue, messages=[receipt]))
            receipt.ack.assert_not_called()
            receipt.retry.assert_called_once_with({"delaySeconds": module.RECOVERY_RETRY_SECONDS})

    async def test_normal_staging_dispatches_only_staging_media_and_skips_cron(self):
        module, worker = self.worker(WORKDOE_WRITE_MODE="normal")
        receipt = SimpleNamespace(body={})
        with (
            patch.object(module, "dispatch_media_review_message", AsyncMock()) as media,
            patch.object(module, "expire_local_auth_tokens", AsyncMock()) as expire,
        ):
            await worker.queue(SimpleNamespace(queue="workdoe-staging-media-review", messages=[receipt]))
            await worker.scheduled(SimpleNamespace(cron=module.EXPIRE_CODES_CRON), None, None)
        media.assert_awaited_once_with(worker.env, receipt, {}, "workdoe-staging-media-review")
        expire.assert_not_awaited()

    async def test_production_redirect_and_default_mode_unchanged(self):
        module, worker = self.worker(WORKDOE_ENV="production")
        self.assertEqual(module.workspace_mode(worker.env), "normal")
        response = await worker.fetch(SimpleNamespace(url="http://www.workdoe.com/styles.css", method="GET"))
        self.assertEqual(response.status, 308)
        self.assertEqual(response.headers["Location"], "https://www.workdoe.com/styles.css")


class UnreadableReceipt:
    def __init__(self):
        self.ack = Mock()
        self.retry = Mock()

    @property
    def body(self):
        raise AssertionError("Staging received a body it must never read.")
