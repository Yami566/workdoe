from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import tempfile
from html.parser import HTMLParser
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

from test_cloudflare_release import (
    load_app_shell_module,
    load_workdoe_production_smoke_script,
)
from test_tile_free_mode import request, worker_for_mode

from workdoe import create_app, get_db

BASE = "https://workdoe.com"
PROXY = "/__clerk"
ROUTES = ("/login", "/login?embed=1", "/create-account", "/create-account?embed=1")
FIXTURE_USER = {"id": 1, "role": "client", "display_name": "Fixture", "email": "fixture@example.invalid"}


class ClerkScriptTags(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.scripts = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "script" and any(key == "src" and "/npm/@clerk/" in (value or "") for key, value in attrs):
            self.scripts.append(attrs)


def assert_reviewed_tags(test, html, pins):
    scripts = ClerkScriptTags(html).scripts
    test.assertEqual(len(scripts), 2)
    for attributes, pin in zip(scripts, pins.values(), strict=True):
        attrs = dict(attributes)
        test.assertEqual(len(attrs), len(attributes))
        test.assertEqual(attrs["src"], PROXY + pin["script_path"])
        test.assertEqual(attrs["integrity"], pin["script_integrity"])
        test.assertEqual(attrs["crossorigin"], "anonymous")
        test.assertIn("defer", attrs)
        test.assertNotIn("async", attrs)
    test.assertEqual(dict(scripts[1])["data-clerk-proxy-url"], PROXY)


class WorkerClerkEntryIntegrityTests(IsolatedAsyncioTestCase):
    async def test_direct_dialog_and_account_share_the_reviewed_pins(self):
        _, worker = worker_for_mode(CLERK_FRONTEND_API_URL=PROXY)
        pins = load_workdoe_production_smoke_script().PINNED_CLERK_BROWSER_COMPONENTS
        for route in ROUTES:
            with self.subTest(route=route):
                response = await worker.fetch(request(BASE + route))
                self.assertEqual(response.status, 200)
                assert_reviewed_tags(self, response.body, pins)
                self.assertIn("data-clerk-load-fallback", response.body)
        response = await worker.fetch(request(BASE + "/"))
        self.assertEqual(ClerkScriptTags(response.body).scripts, [])
        account = load_app_shell_module().account_security_html(FIXTURE_USER, "pk_live_synthetic_fixture", PROXY)
        assert_reviewed_tags(self, account, pins)

    async def test_signup_retry_preserves_destination_without_repeating_invitation_ticket(self):
        _, worker = worker_for_mode(CLERK_FRONTEND_API_URL=PROXY)
        response = await worker.fetch(request(
            BASE + "/create-account?intent=find-work&next=%2Fleads&embed=1&__clerk_ticket=synthetic-retry-ticket",
        ))
        self.assertEqual(response.status, 200)
        self.assertIn(
            'href="/create-account?next=%2Fleads&amp;intent=find-work" data-dialog-bypass>Try again',
            response.body,
        )
        self.assertNotIn("synthetic-retry-ticket", response.body)


class FlaskClerkEntryIntegrityTests(TestCase):
    def test_direct_dialog_and_account_use_the_reviewed_shared_partial(self):
        pins = load_workdoe_production_smoke_script().PINNED_CLERK_BROWSER_COMPONENTS
        with tempfile.TemporaryDirectory() as root:
            app = create_app({
                "TESTING": True, "DATABASE": f"{root}/test.sqlite3", "UPLOAD_ROOT": f"{root}/uploads",
                "SEED_DEMO_DATA": False, "AUTH_PROVIDER": "clerk", "CLERK_LOGIN_MODE": "same_domain_email_code",
                "CLERK_PUBLISHABLE_KEY": "pk_live_synthetic_fixture", "CLERK_FRONTEND_API_URL": PROXY,
            })
            client = app.test_client()
            for route in ROUTES:
                with self.subTest(route=route):
                    response = client.get(route)
                    self.assertEqual(response.status_code, 200)
                    assert_reviewed_tags(self, response.get_data(as_text=True), pins)
                    self.assertIn(b"data-clerk-load-fallback", response.data)
            with app.app_context():
                db = get_db()
                db.execute(
                    """
                    INSERT INTO users (id, email, password_hash, role, display_name, status, email_verified, created_at)
                    VALUES (1, 'fixture@example.invalid', '', 'client', 'Fixture', 'active', 1, '2026-01-01')
                    """
                )
                db.commit()
            with client.session_transaction() as session:
                session["user_id"] = 1
            response = client.get("/account")
            self.assertEqual(response.status_code, 200)
            assert_reviewed_tags(self, response.get_data(as_text=True), pins)

    def test_proxy_smoke_rejects_same_url_mismatched_bytes_and_redirect(self):
        smoke = load_workdoe_production_smoke_script()
        content = b"window.clerkFixture = true;"
        digest = "sha384-" + base64.b64encode(hashlib.sha384(content).digest()).decode("ascii")
        pins = {name: {**pin, "script_integrity": digest} for name, pin in smoke.PINNED_CLERK_BROWSER_COMPONENTS.items()}
        for status, encoding, body in ((200, "", b"changed"), (302, "", content), (200, "gzip", content)):
            with self.subTest(status=status, encoding=encoding):
                with (
                    patch.object(smoke, "PINNED_CLERK_BROWSER_COMPONENTS", pins),
                    patch.object(smoke, "fetch_url", side_effect=[
                        smoke.FetchResult(True, 200, {"Content-Type": "text/javascript"}, body_bytes=content),
                        smoke.FetchResult(
                            True, status, {"Content-Type": "text/javascript", "Content-Encoding": encoding},
                            body_bytes=body,
                        ),
                    ]) as fetch,
                ):
                    check = smoke.clerk_proxy_check(BASE, 2)
                self.assertEqual(check.status, "failed")
                self.assertEqual(fetch.call_count, 2)
                self.assertTrue(all(
                    call.kwargs["binary"] and not call.kwargs["follow_redirects"] for call in fetch.call_args_list
                ))


async def browser_documents():
    _, worker = worker_for_mode(CLERK_FRONTEND_API_URL=PROXY, WORKDOE_MAP_MODE="area")
    docs = {}
    for route in ("/", *ROUTES):
        response = await worker.fetch(request(BASE + route))
        docs[route] = {"html": response.body, "csp": response.headers["Content-Security-Policy"]}
    context = await worker.fetch(request(BASE + "/create-account?embed=1&job_id=demo-02&draft=saved"))
    flask_docs = {}
    with tempfile.TemporaryDirectory() as directory:
        app = create_app({
            "TESTING": True, "DATABASE": f"{directory}/layout.sqlite3", "UPLOAD_ROOT": f"{directory}/uploads",
            "SEED_DEMO_DATA": False, "AUTH_PROVIDER": "clerk", "CLERK_LOGIN_MODE": "same_domain_email_code",
            "CLERK_PUBLISHABLE_KEY": "pk_live_synthetic_fixture", "CLERK_FRONTEND_API_URL": PROXY,
            "MAP_MODE": "area",
        })
        for route in ROUTES:
            response = app.test_client().get(route)
            flask_docs[route] = {"html": response.get_data(as_text=True), "csp": response.headers["Content-Security-Policy"]}
    return {
        "documents": docs, "flask_documents": flask_docs,
        "context_document": {"html": context.body, "csp": context.headers["Content-Security-Policy"]},
        "pins": load_workdoe_production_smoke_script().PINNED_CLERK_BROWSER_COMPONENTS,
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(browser_documents())))
