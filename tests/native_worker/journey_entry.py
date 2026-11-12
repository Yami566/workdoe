"""Local-only external-provider boundary; never deployed with the application."""

import asyncio
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import entry
from clerk_browser_pins import CLERK_BROWSER_PINS
from clerk_proxy import CLERK_JS_PACKAGE_PATH, CLERK_UI_PACKAGE_PATH, DEFAULT_CLERK_FAPI
from fixture_jwks import ROTATION_JWK
from js import JSON, ReadableStream, TextEncoder
from pyodide.ffi import create_once_callable, create_proxy
from turnstile import TURNSTILE_VERIFY_URL
from workers import Response

PACKAGE_ASSETS = {
    f"{CLERK_JS_PACKAGE_PATH}/dist/clerk.browser.js",
    f"{CLERK_UI_PACKAGE_PATH}/dist/signin_ui_e564da_1.41.2.js",
    f"{CLERK_UI_PACKAGE_PATH}/LICENSE",
}
PACKAGE_BODY = b"reviewed local asset fixture"
for path in PACKAGE_ASSETS:
    CLERK_BROWSER_PINS[path] = (len(PACKAGE_BODY), hashlib.sha256(PACKAGE_BODY).hexdigest())


async def fixture_provider(url, **kwargs):
    if str(url) in {
        "https://api.clerk.com/v1/users/user_native_contractor",
        "https://api.clerk.com/v1/users/user_native_webhook",
    }:
        if kwargs.get("method") != "GET" or kwargs.get("redirect") != "manual" or "signal" not in kwargs:
            raise RuntimeError("The local activation lookup requires a cancellable GET without redirects.")
        subject = str(url).rsplit("/", 1)[-1]
        if subject == "user_native_webhook":
            return Response("{}", status=404)
        return entry.json_response({"object": "user", "id": subject, "banned": False, "locked": False})
    for name in ("onboarding", "onboarding_conflict", "onboarding_restricted"):
        subject = f"user_native_{name}"
        if str(url) != f"https://api.clerk.com/v1/users/{subject}":
            continue
        if (kwargs.get("method") != "GET" or kwargs.get("redirect") != "manual"
                or "signal" not in kwargs or not kwargs["headers"]["Authorization"].startswith("Bearer ")):
            raise RuntimeError("The local Clerk Backend User request violated its transport contract.")
        return Response(json.dumps({
            "id": subject,
            "primary_email_address_id": "native_primary",
            "banned": name == "onboarding_restricted",
            "email_addresses": [{
                "id": "native_primary", "email_address": "onboarding@native.invalid",
                "verification": {"status": "verified"},
            }],
        }), headers={"Content-Type": "application/json"})
    if str(url) in {
        "https://api.clerk.com/v1/sessions/sess_native_client/revoke",
        "https://api.clerk.com/v1/sessions/sess_native_other_client/revoke",
    }:
        if kwargs.get("method") != "POST" or kwargs.get("redirect") != "manual" or "signal" not in kwargs:
            raise RuntimeError("The local Clerk sign-out fixture requires a cancellable POST without redirects.")
        if "sess_native_other_client" in str(url):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                print("NATIVE CLERK REVOKE CANCELLED")
                raise
        return Response("{}", status=200)
    if str(url).startswith(f"{DEFAULT_CLERK_FAPI}/"):
        parsed = urlparse(str(url))
        if kwargs.get("redirect") != "manual":
            raise RuntimeError("The local Clerk proxy fixture requires manual redirects.")
        if parsed.path == "/v1/environment" and not parsed.query:
            forwarded = {key.lower(): value for key, value in kwargs["headers"].items()}
            origin = forwarded.get("origin")
            headers = {} if origin is None else {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
            }
            return entry.json_response({"fixture": "clerk-environment"}, headers=headers)
        if parsed.path == "/v1/client" and parsed.query.startswith("native-proxy-fault="):
            signal = kwargs.get("signal")
            if signal is None or signal.aborted:
                raise AssertionError("The synthetic Clerk fetch did not receive a live abort signal.")
            mode = parsed.query.partition("=")[2]
            if mode == "stall":
                if kwargs.get("method") != "POST":
                    raise AssertionError("The stall fixture requires the synthetic sign-in POST.")
                signal.addEventListener("abort", create_once_callable(lambda _event: print("NATIVE CLERK PROXY ABORTED")))
                await asyncio.sleep(30)
            if mode == "transport":
                raise OSError("synthetic-clerk-transport-private-detail")
            if mode == "stream":
                async def start(controller):
                    try:
                        await asyncio.sleep(1)
                        signal.throwIfAborted()
                        controller.enqueue(TextEncoder.new().encode("Synthetic streamed Clerk response."))
                        controller.close()
                    finally:
                        start_proxy.destroy()

                start_proxy = create_proxy(start)
                stream = ReadableStream.new(entry.javascript_object({"start": start_proxy}))
                return Response(stream, headers={"Set-Cookie": "__client=synthetic-clerk-cookie; Secure; HttpOnly"})
            raise AssertionError("Unknown synthetic Clerk transport mode or missed timeout.")
        if parsed.path == "/v1/client/sign_ins":
            headers = {key.lower(): value for key, value in kwargs["headers"].items()}
            cookies = headers.get("cookie", "")
            return entry.json_response({
                "post": kwargs["method"] == "POST",
                "query_preserved": parsed.query == "fixture=a%2Fb",
                "clerk_cookies_preserved": cookies == "__client=fixture; __session=fixture",
                "workdoe_cookie_forwarded": "workdoe_" in cookies,
                "access_cookie_forwarded": "access-fixture" in cookies,
                "access_header_forwarded": "cf-access-jwt-assertion" in headers,
            })
        if parsed.path in PACKAGE_ASSETS and kwargs["method"] in {"GET", "HEAD"}:
            forwarded = {key.lower(): value for key, value in kwargs["headers"].items()}
            if forwarded.get("accept-encoding") != "identity" or {"range", "if-none-match"} & forwarded.keys():
                raise RuntimeError("The reviewed package must use a complete, identity request.")
            mode = parse_qs(parsed.query).get("native-package", [""])[0]
            if mode == "html":
                return Response("private-provider-fixture", headers={"Content-Type": "text/html"})
            if mode == "redirect":
                return Response(None, status=302, headers={"Location": "https://outside.invalid/private-provider-fixture"})
            if mode == "scope":
                return Response("private-provider-fixture", headers={
                    "Content-Type": "application/javascript", "Service-Worker-Allowed": "/",
                })
            if mode == "revalidate":
                return Response(None, status=304, headers={"ETag": '"reviewed-local-asset"'})
            if mode == "stall-body":
                return Response(ReadableStream.new(), headers={"Content-Type": "application/javascript"})
            data = PACKAGE_BODY
            if mode == "tamper":
                data = b"X" + data[1:]
            elif mode == "oversize":
                data += b"X"
            elif mode == "short":
                data = data[:-1]
            return Response(
                None if kwargs["method"] == "HEAD" else data,
                headers={
                    "Content-Type": "text/plain" if parsed.path.endswith("/LICENSE") else "application/javascript; charset=utf-8",
                    "Cache-Control": "public, max-age=31536000, immutable",
                    "ETag": '"reviewed-local-asset"',
                    "Set-Cookie": "fixture=not-forwarded",
                },
            )
        raise RuntimeError("An unreviewed path reached the local Clerk fixture.")
    if str(url) != TURNSTILE_VERIFY_URL:
        raise RuntimeError("The native journey must not contact external providers.")
    body = json.loads(kwargs.get("body", "{}"))
    action = body.get("response", "")
    hostname = "localhost"
    if action == "stage-job-post":
        hostname = "staging-drill.workdoe.com"
        action = "job-post"
    return Response(
        json.dumps(
            {
                "success": action in {"job-draft", "job-post", "match-request"},
                "hostname": hostname,
                "action": action,
            }
        ),
        headers={"Content-Type": "application/json"},
    )


entry.fetch = fixture_provider


async def fixture_clerk_jwks(_secret_key):
    print("NATIVE CLERK JWKS LOOKUP")
    return {"keys": [ROTATION_JWK]}


entry.fetch_clerk_jwks = fixture_clerk_jwks
entry.CLERK_LOGOUT_TIMEOUT_SECONDS = 1
entry.CLERK_PROXY_RESPONSE_TIMEOUT_SECONDS = 0.5
verify_turnstile = entry.verify_turnstile_for_request


async def fixture_turnstile_with_bid_race(env, request, body, action):
    verified = await verify_turnstile(env, request, body, action)
    if action == "match-request":
        race = request.headers.get("X-Native-Bid-Race")
        if race == "contractor":
            await entry.db_run(env, "UPDATE users SET status = 'suspended' WHERE id = 2")
        elif race == "service":
            await entry.db_run(env, "UPDATE jobs SET service_slug = 'house-cleaning' WHERE id = 1")
    return verified


entry.verify_turnstile_for_request = fixture_turnstile_with_bid_race


class LocalQueueReceipt:
    attempts = 1

    def __init__(self, body, *, readable=True):
        self._body = body
        self.readable = readable
        self.acked = 0
        self.retried = 0
        self.retry_delay = None

    @property
    def body(self):
        if not self.readable:
            raise AssertionError("A staging lane read a protected receipt.")
        return self._body

    def ack(self):
        self.acked += 1

    def retry(self, options=None):
        self.retried += 1
        self.retry_delay = entry.row_value(options, "delaySeconds")


production_fetch = entry.Default.fetch


async def email_eligibility_probe(env):
    timestamp = entry.utc_now()
    commands = []
    for identity, role in ((900001, "client"), (900002, "contractor")):
        commands.append((
            """INSERT INTO users
            (id, email, password_hash, role, display_name, email_verified, created_at)
            VALUES (?, ?, '', ?, 'Synthetic notice fixture', 1, ?)""",
            (identity, f"notice-{identity}@native.invalid", role, timestamp),
        ))
    commands.extend((
        ("""INSERT INTO client_profiles
            (user_id, organization_name, notification_preference, email_reminder_consent_at)
            VALUES (900001, 'Synthetic notice workspace', 'email', ?)""", (timestamp,)),
        ("""INSERT INTO contractor_profiles (user_id, business_name, updated_at)
            VALUES (900002, 'Synthetic notice contractor', ?)""", (timestamp,)),
        ("""INSERT INTO contractor_lead_preferences
            (contractor_id, saved_at, updated_at, lead_alert_preference, lead_alert_consent_at)
            VALUES (900002, ?, ?, 'email', ?)""", (timestamp, timestamp, timestamp)),
        ("""INSERT INTO contractor_service_capabilities
            (contractor_id, service_slug, created_at) VALUES (900002, 'lawn-mowing', ?)""", (timestamp,)),
        ("""INSERT INTO contractor_service_zones
            (contractor_id, zone_slug, created_at) VALUES (900002, 'arlington-county-va', ?)""", (timestamp,)),
    ))
    for identity in (900001, 900002, 900003):
        commands.append((
            """INSERT INTO jobs
            (id, client_id, title, category, city, state, zip_code, description, status,
             service_slug, service_group_slug, service_zone_slug, bidding_closes_at, created_at, updated_at)
            VALUES (?, 900001, 'Current synthetic notice', 'Landscaping', 'Arlington', 'VA',
                    '22201', 'Synthetic notice scope.', 'open', 'lawn-mowing', 'outdoor-yard',
                    'arlington-county-va', '2099-01-01', ?, ?)""", (identity, timestamp, timestamp),
        ))
    commands.extend((
        ("""INSERT INTO match_requests
            (id, job_id, contractor_id, scope_note, price_range, timeline, experience,
             availability, created_at, updated_at)
            VALUES (900001, 900001, 900002, 'Fixture', '$100', 'One day', 'Fixture', 'Next week', ?, ?)""",
         (timestamp, timestamp)),
        ("""INSERT INTO repeat_provider_invitations
            (id, job_id, client_id, contractor_id, service_slug, created_at, updated_at)
            VALUES (900002, 900002, 900001, 900002, 'lawn-mowing', ?, ?)""", (timestamp, timestamp)),
        ("""INSERT INTO contractor_lead_alert_deliveries
            (id, contractor_id, job_id, status, created_at, updated_at)
            VALUES (900003, 900002, 900003, 'queued', ?, ?)""", (timestamp, timestamp)),
    ))
    await entry.db_batch(env, commands)
    notices = [
        {"type": "stale-match-reminder", "to": "notice-900001@native.invalid", "match_request_id": 900001},
        {"type": "repeat-provider-invitation", "to": "notice-900002@native.invalid",
         "contractor_id": 900002, "job_id": 900002},
        {"type": "contractor-new-lead", "to": "notice-900002@native.invalid", "lead_alert_delivery_id": 900003},
    ]
    sent = []

    async def send(payload):
        if ("Current synthetic notice" not in payload["text"] or "Arlington, VA" not in payload["text"]
                or "22201" in json.dumps(payload) or "Stale queued" in json.dumps(payload)):
            raise AssertionError("The notice did not rehydrate only current public fields.")
        sent.append(payload)
        return {"messageId": "local-stub-only"}

    lane = SimpleNamespace(
        DB=env.DB, EMAIL=SimpleNamespace(send=send),
        WORKDOE_ENV="local", WORKDOE_MARKETPLACE_EMAIL_ENABLED="true",
    )

    async def consume(body, *, sends):
        before = len(sent)
        receipt = LocalQueueReceipt(body)
        await entry.process_email_queue_message(
            lane, receipt, {**body, "job_title": "Stale queued title", "location": "Stale queued area"},
            "workdoe-native-eligibility",
        )
        if len(sent) != before + sends or (receipt.acked, receipt.retried) != (1, 0):
            raise AssertionError("The local native notice eligibility decision was incorrect.")

    for notice in notices:
        await consume(notice, sends=1)
    await entry.db_batch(env, (
        ("UPDATE client_profiles SET notification_preference = 'workdoe' WHERE user_id = 900001", ()),
        ("UPDATE contractor_lead_preferences SET lead_alert_preference = 'workdoe' WHERE contractor_id = 900002", ()),
        ("UPDATE contractor_lead_alert_deliveries SET status = 'queued' WHERE id = 900003", ()),
    ))
    for notice in (notices[0], notices[2]):
        await consume(notice, sends=0)
    await entry.db_batch(env, (
        ("UPDATE client_profiles SET notification_preference = 'email' WHERE user_id = 900001", ()),
        ("UPDATE contractor_lead_preferences SET lead_alert_preference = 'email' WHERE contractor_id = 900002", ()),
        ("UPDATE users SET status = 'suspended' WHERE id = 900002", ()),
    ))
    for notice in notices:
        await consume(notice, sends=0)
    return {"accepted": len(sent), "opt_out_suppressed": 2, "suspension_suppressed": 3}


async def fixture_fetch(self, request):
    parsed = urlparse(str(request.url))
    if (
        self.env.WORKDOE_ENV == "local" and parsed.hostname == "127.0.0.1"
        and parsed.path == "/media/jobs/9101" and parsed.query == "native-photo-origin=1"
        and request.method in {"GET", "HEAD"}
    ):
        response = await production_fetch(self, request)
        print("NATIVE PHOTO ORIGIN " + json.dumps({
            "method": request.method,
            "site": entry.request_header(request, "Sec-Fetch-Site"),
            "mode": entry.request_header(request, "Sec-Fetch-Mode"),
            "destination": entry.request_header(request, "Sec-Fetch-Dest"),
            "has_session": "__session=" in entry.request_header(request, "Cookie"),
            "status": response.status,
        }))
        return response
    if parsed.path not in {"/__native/email", "/__native/email-eligibility", "/__native/marketplace-email-pause",
                           "/__native/media-review", "/__native/recovery-background",
                           "/__native/staging-containment", "/__native/clerk-jwks-budget"}:
        return await production_fetch(self, request)
    if (
        request.method != "POST"
        or self.env.WORKDOE_ENV != "local"
        or parsed.hostname != "127.0.0.1"
    ):
        return entry.json_response({"ok": False}, status=404)
    if parsed.path == "/__native/email-eligibility":
        return entry.json_response(await email_eligibility_probe(self.env))
    if parsed.path == "/__native/clerk-jwks-budget":
        allowed = 0
        for _ in range(42):
            try:
                await entry.budgeted_clerk_jwks(self.env, self.env.CLERK_SECRET_KEY)
            except entry.SessionVerificationError:
                continue
            allowed += 1
        return entry.json_response({"allowed": allowed})
    if parsed.path == "/__native/marketplace-email-pause":
        if getattr(self.env, "WORKDOE_NATIVE_EMAIL_PAUSE_FIXTURE", "") != "1":
            return entry.json_response({"ok": False}, status=404)
        if parsed.query == "enqueue=1":
            for event_type in sorted(entry.OPTIONAL_MARKETPLACE_EMAIL_EVENTS):
                await entry.send_queue_json(self.env.EMAIL_QUEUE, {
                    "type": event_type, "to": "not-a-mailbox@example.invalid",
                    "job_id": 999999, "job_title": "Synthetic queue payload", "nullable": None,
                })
            return entry.json_response({"ok": True})
        events = entry.rows_from(await entry.db_run(
            self.env, "SELECT event_type, status, payload_json FROM automation_events "
            "WHERE (target_type = 'workdoe-email' AND event_type IN "
            "('email-message-suppressed', 'queue-message-invalid-json')) "
            "OR (target_type = 'job' AND event_type = 'contractor-lead-alert-fanout') ORDER BY id",
        ))
        return entry.json_response({"events": events})
    if parsed.path == "/__native/staging-containment":
        host = "staging-drill.workdoe.com"
        stage = SimpleNamespace(env=SimpleNamespace(
            WORKDOE_ENV="staging", WORKDOE_PUBLIC_URL=f"https://{host}", WORKDOE_DOMAIN=host,
        ))
        health = await production_fetch(stage, SimpleNamespace(
            url=f"https://{host}/health", method="GET", headers={},
        ))
        denied = await production_fetch(stage, SimpleNamespace(
            url=f"https://{host}/api/jobs/open", method="GET",
        ))
        alternate = await production_fetch(stage, SimpleNamespace(
            url="http://workdoe.com/styles.css", method="HEAD",
        ))
        sealed = LocalQueueReceipt(None, readable=False)
        await entry.Default.queue(stage, SimpleNamespace(queue="workdoe-staging-email", messages=[sealed]))
        stage.env.WORKDOE_WRITE_MODE = "normal"
        staged, misrouted = [LocalQueueReceipt(None, readable=False) for _ in range(2)]
        await entry.Default.queue(stage, SimpleNamespace(queue="workdoe-staging-email", messages=[staged]))
        await entry.Default.queue(stage, SimpleNamespace(queue="workdoe-email", messages=[misrouted]))
        await entry.Default.scheduled(stage, SimpleNamespace(cron=entry.EXPIRE_CODES_CRON), None, None)
        listed = await entry.Default.entry_shell(stage, SimpleNamespace(url=f"https://{host}/", method="GET"), "/")
        list_body = await listed.text()
        list_csp = listed.headers.get("content-security-policy") or ""
        tile_free = ("market-list-only" in list_body and "data-project-results" in list_body
                     and all(marker not in list_body for marker in ("data-tile-url", "/vendor/leaflet", "/map.js"))
                     and "tile.openstreetmap.org" not in list_csp)
        stage.env.WORKDOE_MAP_MODE = "area"
        area = await entry.Default.entry_shell(stage, SimpleNamespace(url=f"https://{host}/", method="GET"), "/")
        area_body = await area.text()
        area_csp = area.headers.get("content-security-policy") or ""
        stage_proxy = await production_fetch(stage, SimpleNamespace(
            url=f"https://{host}/__clerk/v1/environment", method="HEAD", headers={},
        ))
        stage_login = await entry.Default.entry_shell(
            stage, SimpleNamespace(url=f"https://{host}/login", method="GET"), "/login",
        )
        stage.env.WORKDOE_TURNSTILE_SECRET_KEY = "local-stage-fixture"  # pragma: allowlist secret
        verification_request = SimpleNamespace(headers={})
        accepted = await verify_turnstile(
            stage.env, verification_request, {"turnstile_token": "stage-job-post"}, "job-post",
        )
        try:
            await verify_turnstile(stage.env, verification_request, {"turnstile_token": "job-post"}, "job-post")
        except entry.TurnstileError:
            local_token_denied = True
        else:
            local_token_denied = False
        return entry.json_response({
            "health": health.status, "mode": health.headers.get("x-workdoe-mode"),
            "sealed_jobs": denied.status,
            "wrong_host": alternate.status, "wrong_host_redirect": alternate.headers.get("location"),
            "tile_free_list": tile_free,
            "area_only": f'data-tile-url="{entry.AREA_MAP_ASSET}"' in area_body and "tile.openstreetmap.org" not in area_csp,
            "access_map_marked": "data-area-map-access" in area_body and "data-area-map-access" not in list_body,
            "unconfigured_login": stage_login.status, "proxy_blocked": stage_proxy.status,
            "report_mail_blocked": not await entry.queue_operator_report_alert(
                stage.env, report_id=1, target_type="job", target_id=1,
            ),
            "exact_stage_turnstile": accepted["hostname"] == host and local_token_denied,
            "acked": [sealed.acked, staged.acked, misrouted.acked],
            "retried": [sealed.retried, staged.retried, misrouted.retried],
            "retry_delays": [sealed.retry_delay, staged.retry_delay, misrouted.retry_delay],
        })
    if parsed.path == "/__native/recovery-background":
        if entry.workspace_mode(self.env) == "normal":
            return entry.json_response({"ok": False}, status=404)
        await self.scheduled(SimpleNamespace(cron=entry.EXPIRE_CODES_CRON), None, None)
        receipts = [LocalQueueReceipt({}) for _ in range(2)]
        for queue, receipt in zip(("workdoe-email", "workdoe-media-review"), receipts, strict=True):
            await self.queue(SimpleNamespace(queue=queue, messages=[receipt]))
        return entry.json_response({
            "acknowledged": [receipt.acked for receipt in receipts],
            "retried": [receipt.retried for receipt in receipts],
            "retry_delays": [receipt.retry_delay for receipt in receipts],
        })
    if parsed.path == "/__native/media-review":
        base = {
            "type": "media-review", "scope": "job", "owner_id": 1, "uploaded_by": 1,
            "stored_path": "jobs/1/synthetic-private-queue-object.webp",
            "content_type": "image/webp", "size_bytes": 128, "checks": [],
        }
        receipts = [LocalQueueReceipt(JSON.parse(json.dumps(base | change))) for change in (
            {"photo_id": 24, "owner_id": "synthetic-private-queue-owner@example.invalid"},
            {"photo_id": 25, "owner_id": []},
            {"photo_id": 26},
        )]
        await self.queue(SimpleNamespace(queue="workdoe-media-review", messages=receipts))
        return entry.json_response({
            "acknowledged": [receipt.acked for receipt in receipts],
            "retried": [receipt.retried for receipt in receipts],
        })
    case = parse_qs(parsed.query).get("case", ["accepted"])[0]
    if case not in {"accepted", "invalid", "restricted-recipient"}:
        return entry.json_response({"ok": False}, status=400)
    receipt = LocalQueueReceipt(
        {
            "type": "unsupported-native-fixture"
            if case == "invalid"
            else "moderation-digest",
            "to": "denied@example.invalid"
            if case == "restricted-recipient"
            else "mailbox@example.invalid",
            "summary": {"open_reports": 0},
        }
    )
    await self.queue(SimpleNamespace(queue="workdoe-email", messages=[receipt]))
    return entry.json_response({"acked": receipt.acked, "retried": receipt.retried})


# Keep the production entrypoint's single SDK environment wrapper, not a subclass.
Default = entry.Default
Default.fetch = fixture_fetch
