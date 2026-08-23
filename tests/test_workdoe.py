from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from werkzeug.security import generate_password_hash

from workdoe import (
    CLERK_PROXY_PATH,
    clerk_proxy_url,
    create_app,
    get_db,
    message_count_label,
    normalize_clerk_frontend_api_url,
    normalize_login_code_submission,
    photo_count_label,
    uploaded_file_signature_matches,
)
from workdoe.bid_comparison import bid_comparison
from workdoe.contractor_proposal_templates import PROPOSAL_TEMPLATE_LIMIT
from workdoe.pilot_metrics import pilot_cell_metrics
from workdoe.project_readiness import project_brief_readiness
from workdoe.service_activation import activation_is_live
from workdoe.service_scope import (
    clean_scope_answers,
    scope_answer_projection,
    scope_readiness,
    validate_scope_answers,
)

ROOT = Path(__file__).resolve().parents[1]


class WorkdoeFlowTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(root / "workdoe-test.sqlite3"),
                "UPLOAD_ROOT": str(root / "uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": True,
                "SECRET_KEY": "test-secret",
            }
        )
        self.client = self.app.test_client()
        self.root = root

    def tearDown(self):
        self.tempdir.cleanup()

    def test_uploaded_images_require_matching_file_signatures(self):
        png = SimpleNamespace(stream=BytesIO(b"\x89PNG\r\n\x1a\nmore"))
        self.assertTrue(uploaded_file_signature_matches(png, "png"))
        self.assertEqual(png.stream.tell(), 0)
        disguised_html = SimpleNamespace(stream=BytesIO(b"<html>not an image"))
        self.assertFalse(uploaded_file_signature_matches(disguised_html, "png"))

    def test_core_marketplace_creates_replay_from_hashed_idempotency_keys(self):
        self.login("client@workdoe.local", "workdoe-client")
        job_key = "idem-local-job-1234567890abcdef"
        job_payload = {
            "idempotency_key": job_key,
            "title": "Idempotent apartment cleaning",
            "category": "Commercial maintenance",
            "service_group_slug": "cleaning-upkeep",
            "service_slug": "house-cleaning",
            "project_setting": "apartment-condo",
            "city": "Washington",
            "state": "DC",
            "zip_code": "20003",
            "desired_date": "2026-12-01",
            "description": "Clean the kitchen, bathroom, floors, and reachable interior surfaces.",
        }
        first_job = self.client.post("/jobs/new", data=job_payload)
        replayed_job = self.client.post("/jobs/new", data=job_payload)
        self.assertEqual(first_job.status_code, 302)
        self.assertEqual(replayed_job.status_code, 302)
        self.assertEqual(first_job.headers["Location"], replayed_job.headers["Location"])
        job = self.one(
            "SELECT * FROM jobs WHERE title = ?", (job_payload["title"],)
        )
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM jobs WHERE title = ?",
                (job_payload["title"],),
            )["total"],
            1,
        )

        with self.app.app_context():
            db = get_db()
            contractor = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            match = db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', ?, 'approved', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "Complete the cleaning scope described by the consumer.",
                    "$350-$450",
                    "One day",
                    "Five years completing move and apartment cleaning work.",
                    "Next week",
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                ),
            )
            thread = db.execute(
                """
                INSERT INTO threads
                    (job_id, match_request_id, client_id, contractor_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job["id"],
                    match.lastrowid,
                    job["client_id"],
                    contractor["id"],
                    "2026-08-17T12:00:00+00:00",
                ),
            )
            db.commit()
            thread_id = int(thread.lastrowid)
            contractor_id = int(contractor["id"])

        message_key = "idem-local-message-1234567890ab"
        for _ in range(2):
            response = self.client.post(
                f"/messages/{thread_id}",
                data={
                    "idempotency_key": message_key,
                    "body": "The side entrance will be open after 9 AM.",
                },
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM messages WHERE thread_id = ? AND body = ?",
                (thread_id, "The side entrance will be open after 9 AM."),
            )["total"],
            1,
        )

        report_key = "idem-local-report-1234567890abcd"
        for _ in range(2):
            response = self.client.post(
                "/report",
                data={
                    "idempotency_key": report_key,
                    "target_type": "profile",
                    "target_id": str(contractor_id),
                    "reason": "Please review this profile statement.",
                },
                headers={"Referer": f"http://localhost/contractors/{contractor_id}"},
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM reports WHERE target_type = 'profile' AND target_id = ? AND reason = ?",
                (contractor_id, "Please review this profile statement."),
            )["total"],
            1,
        )
        records = self.all(
            "SELECT action, key_hash, resource_type, resource_id, status FROM idempotency_requests ORDER BY id"
        )
        self.assertEqual(len(records), 3)
        self.assertTrue(all(record["status"] == "completed" for record in records))
        self.assertEqual(records[0]["key_hash"], hashlib.sha256(job_key.encode()).hexdigest())
        self.assertNotIn(job_key, json.dumps([dict(record) for record in records]))

        form_page = self.client.get("/jobs/new")
        self.assertIn(b'name="idempotency_key"', form_page.data)

    def test_service_activation_requires_review_supply_and_freshness(self):
        ready = {
            "status": "active",
            "allowed_scope": "Interior cleaning.",
            "excluded_scope": "No alteration of real property.",
            "requirements_summary": "Operator review recorded.",
            "approved_at": "2026-08-17T12:00:00+00:00",
            "reviewed_at": "2026-08-17T12:00:00+00:00",
            "minimum_eligible_contractors": 3,
            "eligible_contractors": 3,
        }
        self.assertTrue(
            activation_is_live(ready, now="2026-08-17T13:00:00+00:00")
        )
        self.assertFalse(activation_is_live({**ready, "status": "candidate"}))
        self.assertFalse(activation_is_live({**ready, "eligible_contractors": 2}))
        self.assertFalse(activation_is_live({**ready, "reviewed_at": None}))
        self.assertFalse(
            activation_is_live(
                {**ready, "expires_at": "2026-08-17T12:30:00+00:00"},
                now="2026-08-17T13:00:00+00:00",
            )
        )

    def test_service_zone_gate_blocks_until_review_and_supply_are_ready(self):
        self.app.config["ENFORCE_SERVICE_ACTIVATION"] = True
        payload = {
            "title": "Clean apartment before move-out",
            "category": "Commercial maintenance",
            "service_group_slug": "cleaning-upkeep",
            "service_slug": "house-cleaning",
            "city": "Washington",
            "state": "DC",
            "zip_code": "20003",
            "desired_date": "2026-12-01",
            "description": "Clean the kitchen, bathrooms, floors, and reachable interior surfaces.",
        }
        self.login("client@workdoe.local", "workdoe-client")

        candidate = self.client.post("/jobs/new", data=payload, follow_redirects=True)
        self.assertIn(b"This service is not open in that area yet", candidate.data)
        self.assertIsNone(self.one("SELECT id FROM jobs WHERE title = ?", (payload["title"],)))

        with self.app.app_context():
            db = get_db()
            contractor_id = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()["id"]
            db.execute(
                """
                INSERT OR IGNORE INTO contractor_service_capabilities
                    (contractor_id, service_slug, created_at)
                VALUES (?, 'house-cleaning', '2026-08-17T12:00:00+00:00')
                """,
                (contractor_id,),
            )
            db.execute(
                """
                INSERT OR IGNORE INTO contractor_service_zones
                    (contractor_id, zone_slug, created_at)
                VALUES (?, 'district-of-columbia', '2026-08-17T12:00:00+00:00')
                """,
                (contractor_id,),
            )
            db.execute(
                """
                UPDATE service_zone_activations
                SET status = 'active', approved_at = ?, reviewed_at = ?,
                    minimum_eligible_contractors = 2, updated_at = ?
                WHERE service_slug = 'house-cleaning'
                  AND zone_slug = 'district-of-columbia'
                """,
                (
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                ),
            )
            db.commit()

        undersupplied = self.client.post("/jobs/new", data=payload, follow_redirects=True)
        self.assertIn(b"This service is not open in that area yet", undersupplied.data)

        with self.app.app_context():
            get_db().execute(
                """
                UPDATE service_zone_activations
                SET minimum_eligible_contractors = 1
                WHERE service_slug = 'house-cleaning'
                  AND zone_slug = 'district-of-columbia'
                """
            )
            get_db().commit()

        posted = self.client.post("/jobs/new", data=payload, follow_redirects=True)
        self.assertIn(b"Job posted", posted.data)
        job = self.one("SELECT * FROM jobs WHERE title = ?", (payload["title"],))
        self.assertEqual(job["service_zone_slug"], "district-of-columbia")

        self.logout()
        public_home = self.client.get("/")
        self.assertIn(payload["title"].encode("utf-8"), public_home.data)

        with self.app.app_context():
            get_db().execute(
                """
                UPDATE service_zone_activations SET status = 'paused'
                WHERE service_slug = 'house-cleaning'
                  AND zone_slug = 'district-of-columbia'
                """
            )
            get_db().commit()
        paused_home = self.client.get("/")
        self.assertNotIn(payload["title"].encode("utf-8"), paused_home.data)

        self.login("contractor@workdoe.local", "workdoe-contractor")
        paused_bid = self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can complete this cleaning scope carefully and on schedule.",
                "price_range": "$180-$240",
                "timeline": "One business day",
                "experience": "Three years of apartment turnover cleaning in the DMV.",
                "questions": "Is parking available?",
                "availability": "Weekday mornings",
            },
            follow_redirects=True,
        )
        self.assertIn(b"This service is not open in that area yet", paused_bid.data)
        self.assertIsNone(
            self.one(
                "SELECT id FROM match_requests WHERE job_id = ? AND contractor_id = ?",
                (job["id"], self.one("SELECT id FROM users WHERE email = ?", ("contractor@workdoe.local",))["id"]),
            )
        )

    def login(self, email, password):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def test_photo_count_label_handles_singular_and_plural_rows(self):
        self.assertEqual(photo_count_label(0), "0 photos")
        self.assertEqual(photo_count_label(1), "1 photo")
        self.assertEqual(photo_count_label("2"), "2 photos")
        self.assertEqual(photo_count_label(None), "0 photos")
        self.assertEqual(photo_count_label("bad"), "0 photos")

        with self.app.app_context():
            job = get_db().execute(
                "SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            get_db().execute(
                """
                INSERT INTO job_photos
                    (job_id, uploaded_by, original_filename, stored_path, content_type,
                     size_bytes, is_hidden, created_at)
                VALUES (?, ?, 'before.jpg', ?, 'image/jpeg', 4, 0, '2026-08-03T00:00:00+00:00')
                """,
                (job["id"], job["client_id"], f"jobs/{job['id']}/before.jpg"),
            )
            get_db().commit()

        home = self.client.get("/")
        self.assertIn(b"1 photo", home.data)
        self.assertNotIn(b"1 photos", home.data)

        login = self.client.get("/login")
        self.assertIn(b"1 photo", login.data)
        self.assertNotIn(b"1 photos", login.data)

        start = self.client.get("/start")
        self.assertIn(b"1 photo", start.data)
        self.assertNotIn(b"1 photos", start.data)

        self.login("contractor@workdoe.local", "workdoe-contractor")
        leads = self.client.get("/leads")
        self.assertIn(b"1 photo", leads.data)
        self.assertNotIn(b"1 photos", leads.data)

    def test_login_code_submission_allows_common_copy_paste_separators(self):
        self.assertEqual(normalize_login_code_submission("123456"), "123456")
        self.assertEqual(normalize_login_code_submission("123 456"), "123456")
        self.assertEqual(normalize_login_code_submission("123-456"), "123456")
        self.assertEqual(normalize_login_code_submission(" 12 34-56 "), "123456")
        self.assertEqual(normalize_login_code_submission(None), "")

    def test_clerk_frontend_api_url_stays_on_workdoe_domain(self):
        self.assertEqual(
            normalize_clerk_frontend_api_url("https://clerk.workdoe.com/"),
            "https://clerk.workdoe.com",
        )
        self.assertEqual(
            normalize_clerk_frontend_api_url("https://workdoe.com/__clerk/"),
            "https://workdoe.com/__clerk",
        )
        self.assertEqual(normalize_clerk_frontend_api_url("/__clerk/"), "/__clerk")
        self.assertEqual(
            normalize_clerk_frontend_api_url(
                "https://close-seal-34.clerk.accounts.dev/"
            ),
            "https://close-seal-34.clerk.accounts.dev",
        )
        self.assertEqual(CLERK_PROXY_PATH, "/__clerk")
        self.assertEqual(normalize_clerk_frontend_api_url("https://evilworkdoe.com"), "")
        self.assertEqual(normalize_clerk_frontend_api_url("https://workdoe.com.evil.test"), "")
        self.assertEqual(normalize_clerk_frontend_api_url("//evil.test/__clerk"), "")

    def test_message_count_label_handles_singular_and_plural_rows(self):
        self.assertEqual(message_count_label(0), "0 messages")
        self.assertEqual(message_count_label(1), "1 message")
        self.assertEqual(message_count_label("2"), "2 messages")
        self.assertEqual(message_count_label(None), "0 messages")
        self.assertEqual(message_count_label("bad"), "0 messages")

    def logout(self):
        return self.client.post("/logout", follow_redirects=True)

    def test_logout_requires_post(self):
        self.login("client@workdoe.local", "workdoe-client")
        self.assertEqual(self.client.get("/logout").status_code, 405)
        response = self.client.post("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Signed out.", response.data)

    def test_account_security_stays_inside_workdoe(self):
        anonymous = self.client.get("/account")
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/login", anonymous.headers["Location"])

        self.login("client@workdoe.local", "workdoe-client")
        local_account = self.client.get("/account")
        self.assertEqual(local_account.status_code, 200)
        self.assertIn(b"Account &amp; security", local_account.data)
        self.assertIn(b"client@workdoe.local", local_account.data)
        self.assertIn(b"One account keeps one role", local_account.data)
        self.assertIn(b'href="/client/profile"', local_account.data)
        self.assertNotIn(b"clerk-account.js", local_account.data)

        self.app.config.update(
            AUTH_PROVIDER="clerk",
            CLERK_LOGIN_MODE="same_domain_email_code",
            CLERK_PUBLISHABLE_KEY="pk_live_workdoe",
            CLERK_FRONTEND_API_URL="https://workdoe.com/__clerk",
        )
        clerk_account = self.client.get("/account")
        self.assertEqual(clerk_account.status_code, 200)
        self.assertIn(b"data-clerk-account", clerk_account.data)
        self.assertIn(b"/__clerk/npm/@clerk/clerk-js@6/dist/clerk.browser.js", clerk_account.data)
        self.assertIn(b"clerk-account.js", clerk_account.data)
        csp = clerk_account.headers["Content-Security-Policy"]
        self.assertIn("https://*.protect.clerk.com", csp)
        self.assertIn("https://img.clerk.com", csp)
        self.assertIn("worker-src 'self' blob:", csp)

    def one(self, sql, params=()):
        with self.app.app_context():
            return get_db().execute(sql, params).fetchone()

    def all(self, sql, params=()):
        with self.app.app_context():
            return get_db().execute(sql, params).fetchall()

    def assert_no_store(self, response):
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")
        self.assertIn("Cookie", response.headers.get("Vary", ""))

    def turnstile_client(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "workdoe-turnstile.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "turnstile-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": True,
                "SECRET_KEY": "test-secret",
                "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                "TURNSTILE_SECRET_KEY": "test-secret-key",
                "TURNSTILE_TEST_TOKENS": ("valid-turnstile-token",),
            }
        )
        return app.test_client()

    def test_existing_login_code_table_migrates_selected_job_id(self):
        legacy_db = self.root / "legacy-workdoe.sqlite3"
        conn = sqlite3.connect(legacy_db)
        try:
            conn.execute(
                """
                CREATE TABLE login_codes (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('client', 'contractor')),
                    display_name TEXT NOT NULL,
                    company_name TEXT DEFAULT '',
                    intent TEXT NOT NULL CHECK (intent IN ('post-job', 'find-work')),
                    code_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        migrated_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(legacy_db),
                "UPLOAD_ROOT": str(self.root / "legacy-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": False,
                "SECRET_KEY": "test-secret",
            }
        )
        self.assertIsNotNone(migrated_app)
        conn = sqlite3.connect(legacy_db)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(login_codes)")}
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(login_codes)")}
        finally:
            conn.close()
        self.assertIn("selected_job_id", columns)
        self.assertIn("idx_login_codes_selected_job", indexes)

    def test_existing_user_table_migrates_external_auth_columns(self):
        legacy_db = self.root / "legacy-users.sqlite3"
        conn = sqlite3.connect(legacy_db)
        try:
            conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('client', 'contractor', 'admin')),
                    display_name TEXT NOT NULL,
                    company_name TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        migrated_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(legacy_db),
                "UPLOAD_ROOT": str(self.root / "legacy-user-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": False,
                "SECRET_KEY": "test-secret",
            }
        )
        self.assertIsNotNone(migrated_app)
        conn = sqlite3.connect(legacy_db)
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(users)")}
        finally:
            conn.close()
        self.assertIn("auth_provider", columns)
        self.assertIn("external_subject", columns)
        self.assertIn("idx_users_auth_subject", indexes)

    def test_existing_database_migrates_automation_events(self):
        legacy_db = self.root / "legacy-automation.sqlite3"
        conn = sqlite3.connect(legacy_db)
        try:
            conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('client', 'contractor', 'admin')),
                    display_name TEXT NOT NULL,
                    company_name TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    auth_provider TEXT NOT NULL DEFAULT 'local',
                    external_subject TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

        migrated_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(legacy_db),
                "UPLOAD_ROOT": str(self.root / "legacy-automation-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": False,
                "SECRET_KEY": "test-secret",
            }
        )
        self.assertIsNotNone(migrated_app)
        conn = sqlite3.connect(legacy_db)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(automation_events)")}
        finally:
            conn.close()
        self.assertIn("automation_events", tables)
        self.assertIn("idx_automation_events_type_target", indexes)

    def test_turnstile_is_optional_until_keys_are_configured(self):
        login = self.client.get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertNotIn(b"cf-turnstile", login.data)
        self.assertNotIn(b"challenges.cloudflare.com/turnstile", login.data)

    def test_turnstile_enabled_renders_and_blocks_missing_token(self):
        client = self.turnstile_client()
        login = client.get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn(b"cf-turnstile", login.data)
        self.assertIn(b'data-sitekey="1x00000000000000000000AA"', login.data)
        self.assertIn(b"challenges.cloudflare.com/turnstile/v0/api.js", login.data)
        self.assertIn(
            "script-src 'self' https://challenges.cloudflare.com",
            login.headers["Content-Security-Policy"],
        )
        self.assertIn(
            "frame-src https://challenges.cloudflare.com",
            login.headers["Content-Security-Policy"],
        )

        blocked = client.post(
            "/login",
            data={"email": "client@workdoe.local", "password": "workdoe-client"},
        )
        self.assertEqual(blocked.status_code, 400)

        allowed = client.post(
            "/login",
            data={
                "email": "client@workdoe.local",
                "password": "workdoe-client",
                "cf-turnstile-response": "valid-turnstile-token",
            },
            follow_redirects=True,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertIn(b"Your projects", allowed.data)

    def test_client_posts_job_with_private_photo_and_contractor_can_view(self):
        self.login("client@workdoe.local", "workdoe-client")
        response = self.client.post(
            "/jobs/new",
            data={
                "title": "Clean storefront windows",
                "category": "Window cleaning",
                "city": "Alexandria",
                "state": "VA",
                "zip_code": "22314",
                "desired_date": "2026-09-01",
                "description": "Need first-floor storefront windows cleaned before reopening.",
                "photos": (
                    BytesIO(b"\x89PNG\r\n\x1a\nfake image bytes"),
                    "storefront.png",
                    "image/png",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        self.assertIn(b"Job posted", response.data)
        photo = self.one(
            """
            SELECT job_photos.*, jobs.title
            FROM job_photos
            JOIN jobs ON jobs.id = job_photos.job_id
            WHERE jobs.title = ?
            """,
            ("Clean storefront windows",),
        )
        self.assertIsNotNone(photo)

        self.logout()
        anonymous = self.client.get(f"/media/jobs/{photo['id']}")
        self.assertEqual(anonymous.status_code, 302)

        self.login("contractor@workdoe.local", "workdoe-contractor")
        allowed = self.client.get(f"/media/jobs/{photo['id']}")
        self.assertEqual(allowed.status_code, 200)
        self.assert_no_store(allowed)
        allowed.close()

    def test_client_edits_job_details_and_adds_photo(self):
        self.login("client@workdoe.local", "workdoe-client")
        new_form = self.client.get("/jobs/new")
        self.assertEqual(new_form.status_code, 200)
        self.assertIn(b'class="form-checklist" aria-label="Posting safeguards"', new_form.data)
        self.assertIn(b"City/ZIP pin", new_form.data)
        self.assertIn(b"Private photos", new_form.data)
        self.assertIn(b'list="job-city-options"', new_form.data)
        self.assertIn(b'list="job-zip-options"', new_form.data)
        self.assertIn(b'id="job-city-options"', new_form.data)
        self.assertIn(b'value="Alexandria" label="Alexandria, VA"', new_form.data)
        self.assertIn(b'id="job-zip-options"', new_form.data)
        self.assertIn(b'value="20003" label="Washington, DC"', new_form.data)

        created = self.client.post(
            "/jobs/new",
            data={
                "title": "Original patio wash",
                "category": "Power washing",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "desired_date": "2026-09-01",
                "description": "Need the patio cleaned before weekend guests arrive.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Job posted", created.data)
        job = self.one("SELECT * FROM jobs WHERE title = ?", ("Original patio wash",))
        self.assertIsNotNone(job)
        self.assertIn(b"Edit job", created.data)

        edit = self.client.get(f"/client/jobs/{job['id']}/edit")
        self.assertEqual(edit.status_code, 200)
        self.assertIn(b"Edit project", edit.data)
        self.assertIn(b'value="Original patio wash"', edit.data)
        self.assertIn(b"Save changes", edit.data)
        self.assertIn(b"Approve before chat", edit.data)

        invalid = self.client.post(
            f"/client/jobs/{job['id']}/edit",
            data={
                "title": "  Revised patio wash  ",
                "category": "Power washing",
                "city": "  Alexandria  ",
                "state": "VA",
                "zip_code": "22A",
                "desired_date": "2020-01-01",
                "description": "Need the patio cleaned before weekend guests arrive.",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Use a 5-digit DMV ZIP code.", invalid.data)
        self.assertIn(b"Choose today or a future desired date.", invalid.data)
        self.assertIn(b'value="Revised patio wash"', invalid.data)
        self.assertIn(b'value="Alexandria"', invalid.data)

        updated = self.client.post(
            f"/client/jobs/{job['id']}/edit",
            data={
                "title": "Revised patio wash",
                "category": "Window cleaning",
                "city": "Alexandria",
                "state": "VA",
                "zip_code": "22314",
                "desired_date": "2026-09-03",
                "description": "Need patio doors and exterior glass cleaned before weekend guests arrive.",
                "photos": (
                    BytesIO(b"\xff\xd8\xff\xe0updated image bytes"),
                    "after.jpg",
                    "image/jpeg",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Job updated", updated.data)
        edited = self.one("SELECT * FROM jobs WHERE id = ?", (job["id"],))
        self.assertEqual(edited["title"], "Revised patio wash")
        self.assertEqual(edited["category"], "Window cleaning")
        self.assertEqual(edited["city"], "Alexandria")
        self.assertEqual(edited["state"], "VA")
        self.assertEqual(edited["zip_code"], "22314")
        edited_photo = self.one("SELECT * FROM job_photos WHERE job_id = ?", (job["id"],))
        self.assertIsNotNone(edited_photo)

    def test_client_request_inbox_is_role_gated_and_links_pending_bids(self):
        anonymous = self.client.get("/client/requests")
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn("/login?next=/client/requests", anonymous.headers["Location"])

        self.login("contractor@workdoe.local", "workdoe-contractor")
        denied = self.client.get("/client/requests")
        self.assertEqual(denied.status_code, 403)
        self.logout()

        self.login("client@workdoe.local", "workdoe-client")
        with self.app.app_context():
            db = get_db()
            job = db.execute(
                "SELECT id FROM jobs WHERE client_id = (SELECT id FROM users WHERE email = ?) ORDER BY id LIMIT 1",
                ("client@workdoe.local",),
            ).fetchone()
            contractor = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', ?, 'pending', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "Careful project scope and site protection.",
                    "$400-$600",
                    "Two days",
                    "Five years across the DMV.",
                    "Weekday mornings",
                    "2026-08-16T12:00:00+00:00",
                    "2026-08-16T12:00:00+00:00",
                ),
            )
            db.commit()

        inbox = self.client.get("/client/requests")
        html = inbox.data.decode("utf-8")
        self.assertEqual(inbox.status_code, 200)
        self.assertIn("Bid requests", html)
        self.assertIn('href="/client/requests" aria-current="page"', html)
        self.assertIn(f'href="/client/jobs/{job["id"]}?bids=pending#mini-bids"', html)
        self.assertIn("1 pending", html)

    def test_safety_page_uses_public_facing_copy(self):
        response = self.client.get("/safety")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Share only what the job needs.", response.data)
        self.assertIn(b"Approximate locations", response.data)
        self.assertNotIn(b"MVP", response.data)
        self.assertNotIn(b"Cloudflare", response.data)
        self.assertNotIn(b"D1", response.data)

    def test_public_trust_pages_and_discovery_files_are_available(self):
        privacy = self.client.get("/privacy")
        terms = self.client.get("/terms")
        safety = self.client.get("/safety")
        self.assertEqual(privacy.status_code, 200)
        self.assertEqual(terms.status_code, 200)
        self.assertEqual(safety.status_code, 200)
        self.assertIn(b"Privacy Policy", privacy.data)
        self.assertIn(b"We do not sell personal information", privacy.data)
        self.assertIn(b"Terms of Use", terms.data)
        self.assertIn(b"Prohibited work", terms.data)
        self.assertIn(b"Workdoe is not an emergency service", safety.data)
        for response in (privacy, terms, safety):
            self.assertIn(b'href="/privacy"', response.data)
            self.assertIn(b'>Privacy</a>', response.data)
            self.assertIn(b'href="/terms"', response.data)
            self.assertIn(b'>Terms</a>', response.data)
            self.assertNotIn(b"Cloudflare", response.data)

        robots = self.client.get("/robots.txt")
        sitemap = self.client.get("/sitemap.xml")
        security = self.client.get("/.well-known/security.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertEqual(sitemap.status_code, 200)
        self.assertEqual(security.status_code, 200)
        self.assertEqual(robots.mimetype, "text/plain")
        self.assertEqual(sitemap.mimetype, "application/xml")
        self.assertIn(b"Disallow: /api/", robots.data)
        self.assertIn(b"https://workdoe.com/privacy", sitemap.data)
        self.assertNotIn(b"/client/", sitemap.data)
        self.assertIn(b"Contact: mailto:admin@workdoe.com", security.data)
        self.assertIn(b"Canonical: https://workdoe.com/.well-known/security.txt", security.data)

    def test_client_job_controls_only_show_relevant_status_action(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("client@workdoe.local", "workdoe-client")
        detail = self.client.get(f"/client/jobs/{job['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b">Close job</button>", detail.data)
        self.assertNotIn(b">Reopen job</button>", detail.data)
        self.assertIn(b'class="job-facts"', detail.data)
        self.assertIn(b"<dt>Service</dt>", detail.data)
        self.assertIn(b"<dt>Area</dt>", detail.data)
        self.assertIn(b"<dt>Target</dt>", detail.data)
        self.assertIn(b"<dt>Photos</dt>", detail.data)

        closed = self.client.post(
            f"/client/jobs/{job['id']}/close",
            data={"reason_code": "plans-changed", "note": "Timing moved."},
            follow_redirects=True,
        )
        self.assertEqual(closed.status_code, 200)
        self.assertIn(b">Reopen job</button>", closed.data)
        self.assertNotIn(b">Close job</button>", closed.data)
        self.assertIn(b"Plans changed", closed.data)
        closed_job = self.one(
            "SELECT close_reason, close_note, closed_at FROM jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertEqual(closed_job["close_reason"], "plans-changed")
        self.assertEqual(closed_job["close_note"], "Timing moved.")
        self.assertIsNotNone(closed_job["closed_at"])

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        contractor_detail = self.client.get(f"/jobs/{job['id']}")
        self.assertEqual(contractor_detail.status_code, 200)
        self.assertNotIn(b"Timing moved.", contractor_detail.data)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")

        reopened = self.client.post(
            f"/client/jobs/{job['id']}/reopen",
            follow_redirects=True,
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertIn(b">Close job</button>", reopened.data)
        self.assertNotIn(b">Reopen job</button>", reopened.data)
        reopened_job = self.one(
            "SELECT close_reason, close_note, closed_at FROM jobs WHERE id = ?",
            (job["id"],),
        )
        self.assertIsNone(reopened_job["close_reason"])
        self.assertEqual(reopened_job["close_note"], "")
        self.assertIsNone(reopened_job["closed_at"])

        with self.app.app_context():
            db = get_db()
            db.execute("UPDATE jobs SET status = 'hidden' WHERE id = ?", (job["id"],))
            db.commit()

        hidden_detail = self.client.get(f"/client/jobs/{job['id']}")
        self.assertEqual(hidden_detail.status_code, 200)
        self.assertIn(b"This job is hidden by moderation.", hidden_detail.data)
        self.assertNotIn(b">Close job</button>", hidden_detail.data)
        self.assertNotIn(b">Reopen job</button>", hidden_detail.data)

        blocked_reopen = self.client.post(f"/client/jobs/{job['id']}/reopen")
        self.assertEqual(blocked_reopen.status_code, 403)
        still_hidden = self.one("SELECT status FROM jobs WHERE id = ?", (job["id"],))
        self.assertEqual(still_hidden["status"], "hidden")

    def test_project_close_outcome_is_required_and_workdoe_match_needs_approval(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        self.login("client@workdoe.local", "workdoe-client")

        missing = self.client.post(
            f"/client/jobs/{job['id']}/close",
            follow_redirects=True,
        )
        self.assertIn(b"Choose why this project is closing", missing.data)
        self.assertEqual(
            self.one("SELECT status FROM jobs WHERE id = ?", (job["id"],))["status"],
            "open",
        )

        unmatched = self.client.post(
            f"/client/jobs/{job['id']}/close",
            data={"reason_code": "workdoe-match"},
            follow_redirects=True,
        )
        self.assertIn(b"Approve a Workdoe bid", unmatched.data)

        too_long = self.client.post(
            f"/client/jobs/{job['id']}/close",
            data={"reason_code": "plans-changed", "note": "x" * 301},
            follow_redirects=True,
        )
        self.assertIn(b"under 300 characters", too_long.data)
        self.assertEqual(
            self.one("SELECT status FROM jobs WHERE id = ?", (job["id"],))["status"],
            "open",
        )

    def test_bidder_can_record_private_lead_quality_feedback(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        contractor = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("contractor@workdoe.local",),
        )
        self.login("contractor@workdoe.local", "workdoe-contractor")

        blocked = self.client.post(
            f"/jobs/{job['id']}/quality-feedback",
            data={"reason_code": "wrong-service"},
        )
        self.assertEqual(blocked.status_code, 403)

        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, 'Scoped bid note for feedback.', '$250-$400', 'One day',
                        'Relevant field experience.', '', 'Weekday mornings', 'pending', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                ),
            )
            db.commit()

        saved = self.client.post(
            f"/jobs/{job['id']}/quality-feedback",
            data={
                "reason_code": "insufficient-detail",
                "note": "Need surface dimensions before estimating.",
            },
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn(b"Lead feedback saved", saved.data)
        self.assertIn(b"Need surface dimensions before estimating", saved.data)
        feedback = self.one(
            "SELECT * FROM job_lead_feedback WHERE job_id = ? AND contractor_id = ?",
            (job["id"], contractor["id"]),
        )
        self.assertEqual(feedback["reason_code"], "insufficient-detail")
        event = self.one(
            """
            SELECT payload_json FROM automation_events
            WHERE event_type = 'lead-quality-feedback-recorded' AND target_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (job["id"],),
        )
        self.assertNotIn("surface dimensions", event["payload_json"])

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        client_detail = self.client.get(f"/client/jobs/{job['id']}")
        self.assertEqual(client_detail.status_code, 200)
        self.assertNotIn(b"Need surface dimensions before estimating", client_detail.data)

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        admin = self.client.get("/admin")
        self.assertIn(b"Lead quality signals", admin.data)
        self.assertIn(b"Not enough detail", admin.data)
        self.assertIn(b"Need surface dimensions before estimating", admin.data)

    def test_contractor_requests_match_client_approves_and_thread_opens(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("contractor@workdoe.local", "workdoe-contractor")
        request_response = self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can handle the cleaning and protect surrounding surfaces.",
                "price_range": "$450-$650",
                "timeline": "Two business days after approval",
                "experience": "Five years of exterior cleaning work in the DMV.",
                "questions": "Is there hose access?",
                "availability": "Tuesday and Thursday afternoons",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Mini bid sent", request_response.data)
        self.assertIn(b"Your request is currently", request_response.data)
        self.assertIn(b"$450-$650", request_response.data)
        self.assertIn(b"Two business days after approval", request_response.data)
        self.assertIn(b'href="#mini-bid">View bid status</a>', request_response.data)
        self.assertIn(b"Back to leads", request_response.data)
        match = self.one("SELECT * FROM match_requests WHERE job_id = ?", (job["id"],))
        self.assertEqual(match["status"], "pending")

        board = self.client.get("/leads")
        board_html = board.data.decode("utf-8")
        self.assertIn('class="dashboard-metrics lead-metrics" aria-label="Lead board summary"', board_html)
        self.assertIn('class="lead-view-tabs" aria-label="Lead status"', board_html)
        self.assertIn('href="/leads?view=sent"', board_html)
        self.assertRegex(board_html, r"<span>New</span>\s*<strong>2</strong>")
        self.assertRegex(board_html, r"<span>Bids sent</span>\s*<strong>1</strong>")
        self.assertIn('<span class="status pending">bid pending</span>', board_html)
        self.assertIn('aria-label="Open sent bid for Power wash townhouse front steps"', board_html)
        self.assertIn('<span class="row-cue">Sent</span>', board_html)

        sent_board = self.client.get("/leads?view=sent")
        sent_html = sent_board.data.decode("utf-8")
        self.assertIn('href="/leads?view=sent" aria-current="page"', sent_html)
        self.assertIn('data-jobs-api="/api/jobs/open?limit=50&amp;view=sent"', sent_html)
        self.assertIn(b"Power wash townhouse front steps", sent_board.data)
        self.assertNotIn(b"Replace damaged fence panel", sent_board.data)

        new_board = self.client.get("/leads?view=new")
        self.assertIn(b"Replace damaged fence panel", new_board.data)
        self.assertNotIn(b"Power wash townhouse front steps", new_board.data)

        map_payload = self.client.get("/api/jobs/open").get_json()
        self.assertNotIn("request_status", map_payload["jobs"][0])
        sent_map_payload = self.client.get("/api/jobs/open?view=sent").get_json()
        self.assertEqual(sent_map_payload["count"], 1)
        self.assertEqual(sent_map_payload["view"], "sent")
        self.assertNotIn("request_status", sent_map_payload["jobs"][0])

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        review = self.client.get(f"/client/jobs/{job['id']}")
        review_html = review.data.decode("utf-8")
        self.assertIn('class="lead-action-bar client-review-bar" aria-label="Client job shortcuts"', review_html)
        self.assertIn(
            f'href="/client/jobs/{job["id"]}?bids=pending#mini-bids"',
            review_html,
        )
        self.assertIn('id="mini-bids" class="band subtle bid-review-section" tabindex="-1" aria-labelledby="mini-bids-title"', review_html)
        self.assertIn('id="mini-bids-title"', review_html)
        self.assertIn('class="dashboard-metrics compact-metrics" aria-label="Mini bid summary"', review_html)
        self.assertRegex(review_html, r"<span>Total</span>\s*<strong>1</strong>")
        self.assertRegex(review_html, r"<span>Pending</span>\s*<strong>1</strong>")
        self.assertRegex(review_html, r"<span>Approved</span>\s*<strong>0</strong>")
        self.assertIn('class="work-view-tabs bid-view-tabs" aria-label="Mini bid status"', review_html)
        self.assertIn(f'href="/client/jobs/{job["id"]}?bids=pending"', review_html)
        self.assertIn('class="job-list bid-review-list" aria-live="polite"', review_html)
        self.assertIn('class="bid-comparison"', review_html)
        self.assertIn("Compare pending offers", review_html)
        self.assertIn("Received order", review_html)
        self.assertIn("Offer 1", review_html)
        self.assertIn("Compare terms", review_html)
        self.assertIn("Open profiles", review_html)
        self.assertIn("Approve one", review_html)
        self.assertIn("Source checked", review_html)
        self.assertIn("Workdoe-completed", review_html)
        self.assertIn("Lowest price is not automatically the best fit", review_html)
        self.assertIn(f'href="#bid-title-{match["id"]}"', review_html)
        self.assertIn('class="job-row bid-row bid-review-row needs-review"', review_html)
        self.assertIn('class="bid-row-top"', review_html)
        self.assertLess(review_html.index(">Approve</button>"), review_html.index("I can handle the cleaning"))
        self.assertIn(b"class=\"profile-facts compact-facts bid-facts\"", review.data)
        self.assertIn(b"<dt>Price</dt><dd>$450-$650</dd>", review.data)
        self.assertIn(b"<dt>Timeline</dt><dd>Two business days after approval</dd>", review.data)
        self.assertIn(b"<dt>Availability</dt><dd>Tuesday and Thursday afternoons</dd>", review.data)

        pending_review = self.client.get(f"/client/jobs/{job['id']}?bids=pending")
        pending_html = pending_review.data.decode("utf-8")
        self.assertIn(
            f'href="/client/jobs/{job["id"]}?bids=pending" aria-current="page"',
            pending_html,
        )
        self.assertIn(b"$450-$650", pending_review.data)

        approval = self.client.post(
            f"/client/requests/{match['id']}/approve",
            follow_redirects=True,
        )
        self.assertIn(b"private message thread", approval.data)
        thread = self.one("SELECT * FROM threads WHERE match_request_id = ?", (match["id"],))
        self.assertIsNotNone(thread)

        repeated_approval = self.client.post(
            f"/client/requests/{match['id']}/approve",
            follow_redirects=True,
        )
        self.assertIn(b"already approved", repeated_approval.data)
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM threads WHERE match_request_id = ?",
                (match["id"],),
            )["total"],
            1,
        )
        conflicting_rejection = self.client.post(
            f"/client/requests/{match['id']}/reject",
        )
        self.assertEqual(conflicting_rejection.status_code, 409)
        still_approved = self.one("SELECT status FROM match_requests WHERE id = ?", (match["id"],))
        self.assertEqual(still_approved["status"], "approved")

        approved_review = self.client.get(f"/client/jobs/{job['id']}?bids=approved")
        approved_html = approved_review.data.decode("utf-8")
        self.assertIn(
            f'href="/client/jobs/{job["id"]}?bids=approved" aria-current="page"',
            approved_html,
        )
        self.assertRegex(approved_html, r"<span>Approved</span>\s*<strong>1</strong>")
        self.assertIn('<span class="status approved">approved</span>', approved_html)
        self.assertIn(f'href="/messages/{thread["id"]}"', approved_html)
        self.assertIn(">Message</a>", approved_html)

        with self.app.app_context():
            db = get_db()
            backup_contractor = db.execute(
                """
                INSERT INTO users
                    (email, password_hash, role, display_name, company_name,
                     status, email_verified, created_at)
                VALUES (?, ?, 'contractor', ?, ?, 'active', 1, ?)
                """,
                (
                    "backup-contractor@workdoe.local",
                    "test-hash",
                    "Backup Contractor",
                    "Backup Crew",
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            backup_contractor_id = backup_contractor.lastrowid
            db.execute(
                """
                INSERT INTO contractor_profiles
                    (user_id, business_name, trades, service_area, intro,
                     insurance_status, license_number, years_in_business,
                     website, phone, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    backup_contractor_id,
                    "Backup Crew",
                    "Exterior cleaning",
                    "DMV area",
                    "Backup review contractor profile.",
                    "",
                    "",
                    None,
                    "",
                    "",
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    job["id"],
                    backup_contractor_id,
                    "I can inspect the work and provide a careful backup bid.",
                    "$700-$900",
                    "Next week",
                    "I coordinate similar property maintenance work.",
                    "",
                    "Weekday mornings",
                    "2099-01-01T00:00:00+00:00",
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            db.commit()
        prioritized_review = self.client.get(f"/client/jobs/{job['id']}")
        prioritized_html = prioritized_review.data.decode("utf-8")
        self.assertLess(
            prioritized_html.index('<span class="status pending">pending</span>'),
            prioritized_html.index('<span class="status approved">approved</span>'),
        )

        initial_thread = self.client.get(f"/messages/{thread['id']}")
        self.assertIn(b"1 message", initial_thread.data)
        self.assertNotIn(b"1 messages", initial_thread.data)

        message = self.client.post(
            f"/messages/{thread['id']}",
            data={"body": "Thanks, can you start next week?"},
            follow_redirects=True,
        )
        self.assertIn(b"Message sent", message.data)

        threads = self.client.get("/messages")
        threads_html = threads.data.decode("utf-8")
        self.assertIn('class="dashboard-metrics compact-metrics" aria-label="Message summary"', threads_html)
        self.assertRegex(threads_html, r"<span>Threads</span>\s*<strong>1</strong>")
        self.assertRegex(threads_html, r"<span>Messages</span>\s*<strong>2</strong>")
        self.assertIn(b"2 messages", threads.data)
        self.assertNotIn(b"2 message</span>", threads.data)
        self.assertIn(b"<time datetime=", threads.data)
        self.assertIn(b"Thanks, can you start next week?", threads.data)
        self.assertIn(
            b'aria-label="Open message thread for Power wash townhouse front steps"',
            threads.data,
        )

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        approved_dashboard = self.client.get("/contractor/dashboard?bids=approved")
        approved_dashboard_html = approved_dashboard.data.decode("utf-8")
        self.assertIn(
            f'href="/messages/{thread["id"]}"'.encode("ascii"),
            approved_dashboard.data,
        )
        self.assertIn(
            'aria-label="Message about Power wash townhouse front steps"',
            approved_dashboard_html,
        )
        self.assertIn('<span class="row-cue">Message</span>', approved_dashboard_html)
        self.assertIn('<span class="status approved">approved</span>', approved_dashboard_html)

    def test_bid_pool_caps_at_four_and_rejected_bids_still_count(self):
        job = self.one("SELECT * FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        with self.app.app_context():
            db = get_db()
            db.execute(
                "UPDATE jobs SET bid_limit = 4, bidding_closes_at = ? WHERE id = ?",
                ("2099-01-01T00:00:00+00:00", job["id"]),
            )
            for index in range(4):
                contractor = db.execute(
                    """
                    INSERT INTO users
                        (email, password_hash, role, display_name, company_name,
                         status, email_verified, created_at)
                    VALUES (?, 'test-hash', 'contractor', ?, ?, 'active', 1, ?)
                    """,
                    (
                        f"bid-cap-{index}@workdoe.local",
                        f"Bid Cap Contractor {index}",
                        f"Bid Cap Crew {index}",
                        "2026-08-17T00:00:00+00:00",
                    ),
                )
                db.execute(
                    """
                    INSERT INTO match_requests
                        (job_id, contractor_id, scope_note, price_range, timeline,
                         experience, questions, availability, status, created_at, updated_at)
                    VALUES (?, ?, ?, '$400-$600', 'Two days', ?, '', 'Weekdays', ?, ?, ?)
                    """,
                    (
                        job["id"],
                        contractor.lastrowid,
                        "I can complete this scope and protect the surrounding area.",
                        "Relevant local project experience and an available crew.",
                        "rejected" if index == 0 else "pending",
                        "2026-08-17T00:00:00+00:00",
                        "2026-08-17T00:00:00+00:00",
                    ),
                )
            db.commit()

        self.login("contractor@workdoe.local", "workdoe-contractor")
        blocked = self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can complete this project and protect nearby surfaces.",
                "price_range": "$500-$700",
                "timeline": "Two business days",
                "experience": "Five years completing similar DMV projects.",
                "questions": "",
                "availability": "Weekday afternoons",
            },
            follow_redirects=True,
        )
        self.assertIn(b"full set of mini bids", blocked.data)
        self.assertIn(b"Bid pool full", blocked.data)
        self.assertIn(b"4 of 4 bids", blocked.data)
        self.assertNotIn(b'aria-label="Send mini bid"', blocked.data)
        count = self.one(
            "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
            (job["id"],),
        )
        self.assertEqual(count["total"], 4)

    def test_expired_bid_window_can_only_be_extended_by_the_owning_client(self):
        job = self.one("SELECT * FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        with self.app.app_context():
            db = get_db()
            db.execute(
                "UPDATE jobs SET bidding_closes_at = ? WHERE id = ?",
                ("2020-01-01T00:00:00+00:00", job["id"]),
            )
            db.commit()

        bid_data = {
            "scope_note": "I can complete this project and protect nearby surfaces.",
            "price_range": "$500-$700",
            "timeline": "Two business days",
            "experience": "Five years completing similar DMV projects.",
            "questions": "",
            "availability": "Weekday afternoons",
        }
        self.login("contractor@workdoe.local", "workdoe-contractor")
        expired = self.client.post(
            f"/jobs/{job['id']}/request",
            data=bid_data,
            follow_redirects=True,
        )
        self.assertIn(b"Bidding has closed", expired.data)
        self.assertEqual(
            self.client.post(f"/client/jobs/{job['id']}/extend-bids").status_code,
            403,
        )

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        detail = self.client.get(f"/client/jobs/{job['id']}")
        self.assertIn(b"Add 7 days", detail.data)
        extended = self.client.post(
            f"/client/jobs/{job['id']}/extend-bids",
            follow_redirects=True,
        )
        self.assertIn(b"Bidding extended by 7 days", extended.data)
        event = self.one(
            "SELECT * FROM automation_events WHERE event_type = 'job-bidding-extended' AND target_id = ?",
            (job["id"],),
        )
        self.assertIsNotNone(event)

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        accepted = self.client.post(
            f"/jobs/{job['id']}/request",
            data=bid_data,
            follow_redirects=True,
        )
        self.assertIn(b"Mini bid sent", accepted.data)

    def test_message_form_constraints_and_draft_preservation(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("contractor@workdoe.local", "workdoe-contractor")
        self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can handle the work and protect surrounding surfaces.",
                "price_range": "$500-$700",
                "timeline": "Two business days",
                "experience": "Several similar jobs in the DMV area.",
                "questions": "",
                "availability": "Weekday afternoons",
            },
            follow_redirects=True,
        )
        match = self.one("SELECT * FROM match_requests WHERE job_id = ?", (job["id"],))

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        self.client.post(f"/client/requests/{match['id']}/approve", follow_redirects=True)
        thread = self.one("SELECT * FROM threads WHERE match_request_id = ?", (match["id"],))

        detail = self.client.get(f"/messages/{thread['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'class="row-meta thread-meta"', detail.data)
        self.assertIn(b"1 message", detail.data)
        self.assertIn(b"<time datetime=", detail.data)
        self.assertIn(b'maxlength="1000"', detail.data)
        self.assertIn(b'<details class="message-report">', detail.data)
        self.assertIn(b"<summary>Report message</summary>", detail.data)
        self.assertIn(b"Report message reason", detail.data)
        self.assertIn(b'for="message-report-reason-', detail.data)
        self.assertIn(
            b'name="reason" maxlength="500" placeholder="Report reason" autocapitalize="sentences" spellcheck="true" enterkeyhint="send" required',
            detail.data,
        )
        self.assertIn(b'aria-label="Report message from ', detail.data)
        self.assertIn(b'class="message-form" method="post" aria-label="New message"', detail.data)
        self.assertIn(b'for="message-body"', detail.data)
        self.assertIn(b'id="message-body"', detail.data)
        self.assertIn(b"required", detail.data)
        self.assertIn(b'autocapitalize="sentences"', detail.data)
        self.assertIn(b'spellcheck="true"', detail.data)
        self.assertIn(b'enterkeyhint="send"', detail.data)
        self.assertIn(b'aria-label="Send message"', detail.data)
        self.assertIn(b"Share timing, access, or next steps.", detail.data)

        before = self.one("SELECT COUNT(*) AS total FROM messages WHERE thread_id = ?", (thread["id"],))
        oversized = "X" * 1001
        invalid = self.client.post(
            f"/messages/{thread['id']}",
            data={"body": oversized},
            follow_redirects=True,
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Keep messages under 1000 characters.", invalid.data)
        self.assertIn(b'id="message-form-errors"', invalid.data)
        self.assertIn(b'href="#message-body"', invalid.data)
        self.assertIn(b'id="message-body-error"', invalid.data)
        self.assertIn(b'aria-invalid="true"', invalid.data)
        self.assertIn(b'aria-describedby="message-body-error"', invalid.data)
        self.assertIn(("X" * 80).encode("ascii"), invalid.data)
        after = self.one("SELECT COUNT(*) AS total FROM messages WHERE thread_id = ?", (thread["id"],))
        self.assertEqual(after["total"], before["total"])

    def test_mini_bid_constraints_and_error_value_preservation(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        contractor = self.one("SELECT id FROM users WHERE email = ?", ("contractor@workdoe.local",))

        self.login("contractor@workdoe.local", "workdoe-contractor")
        detail = self.client.get(f"/jobs/{job['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b'minlength="20"', detail.data)
        self.assertIn(b'maxlength="800"', detail.data)
        self.assertIn(b'maxlength="80"', detail.data)
        self.assertIn(b'maxlength="120"', detail.data)
        self.assertIn(b'maxlength="500"', detail.data)
        self.assertIn(b"Report this lead", detail.data)
        self.assertIn(b'for="lead-report-reason"', detail.data)
        self.assertIn(
            b'id="lead-report-reason" name="reason" maxlength="500" placeholder="Why should moderation review it?" autocapitalize="sentences" spellcheck="true" enterkeyhint="send" required',
            detail.data,
        )
        self.assertIn(b'aria-label="Report lead"', detail.data)
        self.assertIn(b'class="lead-action-bar" aria-label="Lead actions"', detail.data)
        self.assertIn(b'href="#mini-bid">Send mini bid</a>', detail.data)
        self.assertIn(b'href="#job-details">Review details</a>', detail.data)
        self.assertIn(b'id="job-details" class="panel job-detail-panel" tabindex="-1"', detail.data)
        self.assertIn(b'id="mini-bid" class="panel bid-panel" tabindex="-1"', detail.data)
        self.assertIn(b'class="job-facts"', detail.data)
        self.assertIn(b"<dt>Service</dt>", detail.data)
        self.assertIn(b"<dt>Area</dt>", detail.data)
        self.assertIn(b"<dt>Target</dt>", detail.data)
        self.assertIn(b"<dt>Photos</dt>", detail.data)
        self.assertIn(b'class="stack-form bid-form"', detail.data)
        self.assertIn(b'aria-label="Send mini bid"', detail.data)
        self.assertIn(b'autocapitalize="sentences"', detail.data)
        self.assertIn(b'spellcheck="true"', detail.data)
        self.assertIn(b'enterkeyhint="next"', detail.data)
        self.assertIn(b'enterkeyhint="done"', detail.data)
        self.assertIn(b'class="bid-quick-grid"', detail.data)
        self.assertIn(b'list="bid-price-options"', detail.data)
        self.assertIn(b'list="bid-timeline-options"', detail.data)
        self.assertIn(b'list="bid-availability-options"', detail.data)
        self.assertIn(b'id="bid-price-options"', detail.data)
        self.assertIn(b'value="On-site estimate needed"', detail.data)
        self.assertIn(b'value="Two business days after approval"', detail.data)
        self.assertIn(b'value="Weekend available"', detail.data)
        self.assertIn(b'<details class="optional-field"', detail.data)
        self.assertIn(b"<summary>Questions (optional)</summary>", detail.data)
        self.assertIn(b'<button class="button full" type="submit" aria-label="Send mini bid">Send bid</button>', detail.data)
        self.assertIn(b"Send bid", detail.data)

        invalid = self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "  quick  ",
                "price_range": "  $500  ",
                "timeline": "",
                "experience": "short",
                "questions": "  Is evening access ok?  ",
                "availability": "  Tue   Thu  ",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Add at least 20 characters about the scope.", invalid.data)
        self.assertIn(b"Add a timeline.", invalid.data)
        self.assertIn(b"Add at least 20 characters about relevant experience.", invalid.data)
        self.assertIn(b'id="bid-form-errors"', invalid.data)
        self.assertIn(b'href="#bid-scope-note"', invalid.data)
        self.assertIn(b'id="bid-scope-note-error"', invalid.data)
        self.assertIn(b'href="#bid-timeline"', invalid.data)
        self.assertIn(b'id="bid-timeline-error"', invalid.data)
        self.assertIn(b'aria-invalid="true"', invalid.data)
        self.assertIn(b">quick</textarea>", invalid.data)
        self.assertIn(b'value="$500"', invalid.data)
        self.assertIn(b">Is evening access ok?</textarea>", invalid.data)
        self.assertIn(b'value="Tue Thu"', invalid.data)

        oversized_questions = self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can complete this work and protect surrounding surfaces.",
                "price_range": "$500",
                "timeline": "Two business days",
                "experience": "I have handled several similar projects around the DMV.",
                "questions": "Q" * 501,
                "availability": "Tue Thu",
            },
        )
        self.assertEqual(oversized_questions.status_code, 200)
        self.assertIn(b"Keep questions under 500 characters.", oversized_questions.data)
        self.assertIn(b'<details class="optional-field" open>', oversized_questions.data)
        self.assertIn(b'id="bid-questions-error"', oversized_questions.data)
        saved = self.one(
            "SELECT id FROM match_requests WHERE job_id = ? AND contractor_id = ?",
            (job["id"], contractor["id"]),
        )
        self.assertIsNone(saved)

    def test_consumer_profile_saved_area_and_project_prefill(self):
        client_user = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("client@workdoe.local",),
        )
        self.login("client@workdoe.local", "workdoe-client")

        profile_page = self.client.get("/client/profile")
        self.assertEqual(profile_page.status_code, 200)
        self.assertIn(b"Your profile", profile_page.data)
        self.assertIn(b"Home or household", profile_page.data)
        self.assertIn(b"Saved project areas", profile_page.data)
        self.assertIn(b"Choosing email and saving this profile records your consent", profile_page.data)
        self.assertNotIn(b'name="phone"', profile_page.data)
        initial_profile = self.one(
            "SELECT * FROM client_profiles WHERE user_id = ?",
            (client_user["id"],),
        )
        self.assertEqual(initial_profile["notification_preference"], "workdoe")
        self.assertIsNone(initial_profile["email_reminder_consent_at"])

        invalid = self.client.post(
            "/client/profile",
            data={
                "organization_name": "",
                "account_type": "unknown",
                "notification_preference": "sms",
                "profile_note": "x" * 401,
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Add a household or organization name.", invalid.data)
        self.assertIn(b"Choose the kind of consumer workspace", invalid.data)
        self.assertIn(b"Choose where Workdoe should send bid reminders", invalid.data)

        updated = self.client.post(
            "/client/profile",
            data={
                "organization_name": "  Meridian Corner Store  ",
                "account_type": "small_business",
                "notification_preference": "workdoe",
                "profile_note": "  Schedule noisy work before opening.  ",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Consumer workspace updated.", updated.data)
        profile = self.one(
            "SELECT * FROM client_profiles WHERE user_id = ?",
            (client_user["id"],),
        )
        self.assertEqual(profile["organization_name"], "Meridian Corner Store")
        self.assertEqual(profile["account_type"], "small_business")
        self.assertEqual(profile["notification_preference"], "workdoe")
        self.assertIsNone(profile["email_reminder_consent_at"])

        email_opt_in = self.client.post(
            "/client/profile",
            data={
                "organization_name": "Meridian Corner Store",
                "account_type": "small_business",
                "notification_preference": "email",
                "profile_note": "Schedule noisy work before opening.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Consumer workspace updated.", email_opt_in.data)
        opted_in_profile = self.one(
            "SELECT * FROM client_profiles WHERE user_id = ?",
            (client_user["id"],),
        )
        self.assertEqual(opted_in_profile["notification_preference"], "email")
        self.assertTrue(opted_in_profile["email_reminder_consent_at"])

        self.client.post(
            "/client/profile",
            data={
                "organization_name": "Meridian Corner Store",
                "account_type": "small_business",
                "notification_preference": "workdoe",
                "profile_note": "Schedule noisy work before opening.",
            },
        )
        opted_out_profile = self.one(
            "SELECT * FROM client_profiles WHERE user_id = ?",
            (client_user["id"],),
        )
        self.assertEqual(opted_out_profile["notification_preference"], "workdoe")
        self.assertIsNone(opted_out_profile["email_reminder_consent_at"])

        bad_area = self.client.post(
            "/client/profile/locations",
            data={"label": "", "city": "", "state": "NY", "zip_code": "12"},
        )
        self.assertEqual(bad_area.status_code, 200)
        self.assertIn(b"Add a short name for this project area.", bad_area.data)
        self.assertIn(b"Use a 5-digit ZIP code", bad_area.data)

        saved = self.client.post(
            "/client/profile/locations",
            data={
                "label": "Main shop",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Project area saved.", saved.data)
        location = self.one(
            "SELECT * FROM client_saved_locations WHERE client_id = ?",
            (client_user["id"],),
        )
        self.assertEqual(location["label"], "Main shop")
        self.assertIn(b"200xx", saved.data)

        duplicate = self.client.post(
            "/client/profile/locations",
            data={
                "label": "main SHOP",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20001",
            },
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn(b"Use a different name", duplicate.data)

        composer = self.client.get(f"/jobs/new?location={location['id']}")
        self.assertEqual(composer.status_code, 200)
        self.assertIn(b'value="Washington"', composer.data)
        self.assertIn(b'value="20003"', composer.data)
        self.assertIn(b"Start with a saved area", composer.data)

        removed = self.client.post(
            f"/client/profile/locations/{location['id']}/delete",
            follow_redirects=True,
        )
        self.assertIn(b"Saved project area removed.", removed.data)
        self.assertIsNone(
            self.one(
                "SELECT id FROM client_saved_locations WHERE id = ?",
                (location["id"],),
            )
        )

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        self.assertEqual(self.client.get("/client/profile").status_code, 403)

    def test_consumer_project_templates_copy_scope_without_location_or_date(self):
        client = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("client@workdoe.local",),
        )
        source = self.one(
            "SELECT * FROM jobs WHERE client_id = ? ORDER BY id LIMIT 1",
            (client["id"],),
        )
        self.login("client@workdoe.local", "workdoe-client")

        profile = self.client.get(
            f"/client/profile?source_job={source['id']}#project-templates"
        )
        self.assertEqual(profile.status_code, 200)
        self.assertIn(b"Project templates", profile.data)
        self.assertIn(b"Location, date, photos, bids, and messages are never copied.", profile.data)
        self.assertIn(
            f'value="{source["id"]}" selected'.encode("ascii"),
            profile.data,
        )

        saved = self.client.post(
            "/client/profile/templates",
            data={"name": "  Monthly   exterior reset  ", "source_job_id": source["id"]},
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn(b"Project template saved.", saved.data)
        self.assertIn(b"Monthly exterior reset", saved.data)
        template = self.one(
            "SELECT * FROM client_project_templates WHERE client_id = ?",
            (client["id"],),
        )
        self.assertEqual(template["source_job_id"], source["id"])
        self.assertEqual(template["title"], source["title"])
        self.assertEqual(template["description"], source["description"])
        self.assertNotIn("city", template.keys())
        self.assertNotIn("zip_code", template.keys())
        self.assertNotIn("desired_date", template.keys())
        self.assertNotIn("stored_path", template.keys())

        composer = self.client.get(f"/jobs/new?template={template['id']}")
        self.assertEqual(composer.status_code, 200)
        self.assertIn(f'value="{source["title"]}"'.encode(), composer.data)
        self.assertIn(source["description"].encode("utf-8"), composer.data)
        self.assertIn(b'id="job-city" name="city" value=""', composer.data)
        self.assertIn(b'id="job-zip-code" name="zip_code" value=""', composer.data)
        self.assertIn(b'id="job-desired-date" name="desired_date" type="date" value=""', composer.data)

        duplicate = self.client.post(
            "/client/profile/templates",
            data={"name": "monthly exterior reset", "source_job_id": source["id"]},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertIn(b"Use a different name for this project template.", duplicate.data)
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS count FROM client_project_templates WHERE client_id = ?",
                (client["id"],),
            )["count"],
            1,
        )

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        self.assertEqual(
            self.client.post(
                "/client/profile/templates",
                data={"name": "Blocked", "source_job_id": source["id"]},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"/jobs/new?template={template['id']}").status_code,
            403,
        )

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        removed = self.client.post(
            f"/client/profile/templates/{template['id']}/delete",
            follow_redirects=True,
        )
        self.assertIn(b"Project template removed.", removed.data)
        self.assertIsNone(
            self.one(
                "SELECT id FROM client_project_templates WHERE id = ?",
                (template["id"],),
            )
        )

    def test_contractor_profile_constraints_and_draft_preservation(self):
        contractor = self.one("SELECT id FROM users WHERE email = ?", ("contractor@workdoe.local",))

        self.login("contractor@workdoe.local", "workdoe-contractor")
        form = self.client.get("/contractor/profile")
        self.assertEqual(form.status_code, 200)
        self.assertIn(b'value="Rivera Exterior Care"', form.data)
        self.assertIn(b'maxlength="120"', form.data)
        self.assertIn(b'minlength="20"', form.data)
        self.assertIn(b'maxlength="900"', form.data)
        self.assertIn(b'max="100"', form.data)
        self.assertNotIn(b'type="tel"', form.data)
        self.assertIn(b"Storefront readiness", form.data)
        self.assertIn(b'aria-label="Contractor profile"', form.data)
        self.assertIn(b'for="profile-business-name"', form.data)
        self.assertIn(b'id="profile-business-name"', form.data)
        self.assertIn(b'id="profile-trades"', form.data)
        self.assertIn(b'for="profile-trade-1"', form.data)
        self.assertIn(b'enterkeyhint="next"', form.data)
        self.assertIn(b'id="profile-photos"', form.data)
        self.assertIn(b'aria-describedby="profile-photos-help"', form.data)

        invalid = self.client.post(
            "/contractor/profile",
            data={
                "business_name": "  Better Exterior Care  ",
                "trades": ["Power washing"],
                "service_area": "",
                "years_in_business": "150",
                "insurance_status": "  COI available  ",
                "license_number": "  VA-1234  ",
                "website": "ftp://example.test",
                "phone": "  (202) 555-0180  ",
                "intro": "short",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Add a service area.", invalid.data)
        self.assertIn(b"Add at least 20 characters about your business.", invalid.data)
        self.assertIn(b"Use 0 to 100 for years in business.", invalid.data)
        self.assertIn(b"Use a public HTTPS website such as https://example.com.", invalid.data)
        self.assertIn(b'id="profile-form-errors"', invalid.data)
        self.assertIn(b'href="#profile-service-area"', invalid.data)
        self.assertIn(b'href="#profile-intro"', invalid.data)
        self.assertIn(b'href="#profile-years-in-business"', invalid.data)
        self.assertIn(b'href="#profile-website"', invalid.data)
        self.assertIn(b'id="profile-service-area-error"', invalid.data)
        self.assertIn(b'id="profile-intro-error"', invalid.data)
        self.assertIn(b'id="profile-years-in-business-error"', invalid.data)
        self.assertIn(b'id="profile-website-error"', invalid.data)
        self.assertIn(b'aria-invalid="true"', invalid.data)
        self.assertIn(b'value="Better Exterior Care"', invalid.data)
        self.assertIn(b'value="COI available"', invalid.data)
        self.assertIn(b'value="150"', invalid.data)
        self.assertIn(b'value="ftp://example.test"', invalid.data)
        self.assertIn(b">short</textarea>", invalid.data)
        unchanged = self.one(
            "SELECT * FROM contractor_profiles WHERE user_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(unchanged["business_name"], "Rivera Exterior Care")

        updated = self.client.post(
            "/contractor/profile",
            data={
                "business_name": "Better Exterior Care",
                "trades": ["Power washing", "Window cleaning"],
                "service_area": "DC and Northern Virginia",
                "years_in_business": "7",
                "insurance_status": "COI available",
                "license_number": "VA-1234",
                "website": "https://better.example",
                "phone": "(202) 555-0180",
                "intro": "We handle exterior cleaning jobs around the DMV with careful site protection.",
                "portfolio_photos": (
                    BytesIO(b"RIFF\x04\x00\x00\x00WEBPprofile photo bytes"),
                    "crew.webp",
                    "image/webp",
                ),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Contractor profile updated", updated.data)
        profile = self.one(
            "SELECT * FROM contractor_profiles WHERE user_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(profile["business_name"], "Better Exterior Care")
        self.assertEqual(profile["trades"], "Power washing, Window cleaning")
        self.assertEqual(profile["service_area"], "DC and Northern Virginia")
        self.assertEqual(profile["years_in_business"], 7)
        self.assertEqual(profile["website"], "https://better.example")
        self.assertEqual(profile["phone"], "")
        photo = self.one(
            "SELECT * FROM contractor_photos WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertIsNotNone(photo)
        public_profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertIn(b"Portfolio photo 1", public_profile.data)
        self.assertNotIn(b"crew.webp", public_profile.data)
        self.assertIn(b"Visit better.example", public_profile.data)
        self.assertIn(b'rel="noopener noreferrer nofollow external"', public_profile.data)

        self.logout()
        anonymous_profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertNotIn(b"Visit better.example", anonymous_profile.data)
        self.login("client@workdoe.local", "workdoe-client")
        unrelated_profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertNotIn(b"Visit better.example", unrelated_profile.data)
        with self.app.app_context():
            db = get_db()
            job = db.execute(
                "SELECT id FROM jobs ORDER BY id LIMIT 1"
            ).fetchone()
            db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', ?, 'pending', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "Review the site, protect adjacent surfaces, and complete the wash.",
                    "$500-$700",
                    "One day",
                    "Seven years of exterior cleaning work across the DMV.",
                    "Available next week",
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                ),
            )
            db.commit()
        related_profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertIn(b"Visit better.example", related_profile.data)
        public_media = self.client.get(f"/media/contractors/{photo['id']}")
        self.assertIn(
            f"workdoe-photo-{photo['id']}".encode("ascii"),
            public_media.headers["Content-Disposition"].encode("ascii"),
        )
        self.assertNotIn(
            b"crew.webp",
            public_media.headers["Content-Disposition"].encode("ascii"),
        )
        public_media.close()

    def test_contractor_availability_and_saved_lead_view_are_owner_controlled(self):
        contractor = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("contractor@workdoe.local",),
        )
        self.login("contractor@workdoe.local", "workdoe-contractor")

        profile = self.client.get("/contractor/profile")
        self.assertEqual(profile.status_code, 200)
        self.assertIn(b'id="work-availability"', profile.data)
        self.assertIn(b"This self-reported status is shown", profile.data)

        updated = self.client.post(
            "/contractor/preferences/availability",
            data={
                "availability_status": "limited",
                "available_from": "2030-06-15",
            },
            follow_redirects=True,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertIn(b"Work availability updated.", updated.data)
        preference = self.one(
            "SELECT * FROM contractor_lead_preferences WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(preference["availability_status"], "limited")
        self.assertEqual(preference["available_from"], "2030-06-15")

        public_profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertIn(b"Taking new work from 2030-06-15", public_profile.data)
        self.assertIn(b"Self-reported", public_profile.data)

        saved = self.client.post(
            "/contractor/preferences/lead-view",
            data={
                "saved_category": "Painting",
                "saved_service_group_slug": "remodel-finish",
                "saved_service_slug": "interior-painting",
                "saved_query": "  Arlington   VA  ",
                "saved_sort": "soonest",
                "lead_alert_preference": "email",
            },
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn(b"Lead view saved.", saved.data)
        self.assertIn(b"Use saved view", saved.data)
        preference = self.one(
            "SELECT * FROM contractor_lead_preferences WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(preference["saved_query"], "Arlington VA")
        self.assertEqual(preference["saved_category"], "Painting")
        self.assertEqual(preference["saved_service_group_slug"], "remodel-finish")
        self.assertEqual(preference["saved_service_slug"], "interior-painting")
        self.assertEqual(preference["saved_sort"], "soonest")
        self.assertIsNotNone(preference["saved_at"])
        self.assertEqual(preference["lead_alert_preference"], "email")
        self.assertIsNotNone(preference["lead_alert_consent_at"])
        self.assertIn(b"Email alerts on", saved.data)
        self.assertIn(b"Interior painting", saved.data)

        invalid = self.client.post(
            "/contractor/preferences/lead-view",
            data={
                "saved_category": "Painting",
                "saved_service_group_slug": "secret-family",
                "saved_query": "Bethesda",
                "saved_sort": "soonest",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Choose a valid work family.", invalid.data)
        unchanged = self.one(
            "SELECT * FROM contractor_lead_preferences WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(unchanged["saved_category"], "Painting")
        self.assertEqual(unchanged["saved_service_group_slug"], "remodel-finish")
        self.assertEqual(unchanged["saved_service_slug"], "interior-painting")
        self.assertNotIn(b"Arlington VA", public_profile.data)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        self.assertEqual(
            self.client.post(
                "/contractor/preferences/availability",
                data={"availability_status": "available"},
            ).status_code,
            403,
        )

    def test_opted_in_contractor_gets_one_private_matching_project_alert_candidate(self):
        contractor = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("contractor@workdoe.local",),
        )
        self.login("contractor@workdoe.local", "workdoe-contractor")
        alert_preference = self.client.post(
            "/contractor/preferences/lead-view",
            data={
                "saved_category": "Power washing",
                "saved_service_group_slug": "outdoor-yard",
                "saved_service_slug": "pressure-washing",
                "saved_query": "Washington DC",
                "saved_sort": "newest",
                "lead_alert_preference": "email",
            },
            follow_redirects=True,
        )
        self.assertEqual(alert_preference.status_code, 200)
        self.assertIn(b"Email alerts on", alert_preference.data)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        matching = self.client.post(
            "/jobs/new",
            data={
                "title": "Alert test pressure wash",
                "category": "Power washing",
                "service_group_slug": "outdoor-yard",
                "service_slug": "pressure-washing",
                "project_setting": "outdoor-area",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "description": "Pressure wash the front walk while protecting nearby planting beds.",
                "desired_date": "2030-06-20",
                "budget_min": "300",
                "budget_max": "500",
            },
            follow_redirects=True,
        )
        self.assertEqual(matching.status_code, 200)
        matching_job = self.one(
            "SELECT id FROM jobs WHERE title = 'Alert test pressure wash'"
        )
        delivery = self.one(
            """
            SELECT * FROM contractor_lead_alert_deliveries
            WHERE contractor_id = ? AND job_id = ?
            """,
            (contractor["id"], matching_job["id"]),
        )
        self.assertEqual(delivery["status"], "pending")
        candidate_event = self.one(
            """
            SELECT payload_json FROM automation_events
            WHERE event_type = 'contractor-lead-alert-candidates'
              AND target_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (matching_job["id"],),
        )
        self.assertEqual(json.loads(candidate_event["payload_json"]), {"candidate_count": 1})
        self.assertNotIn("Washington", candidate_event["payload_json"])

        nonmatching = self.client.post(
            "/jobs/new",
            data={
                "title": "Alert test window clean",
                "category": "Window cleaning",
                "service_group_slug": "cleaning-upkeep",
                "service_slug": "window-cleaning",
                "project_setting": "house",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "description": "Clean exterior first-floor windows without moving interior furnishings.",
                "desired_date": "2030-06-21",
                "budget_min": "200",
                "budget_max": "400",
            },
            follow_redirects=True,
        )
        self.assertEqual(nonmatching.status_code, 200)
        nonmatching_job = self.one(
            "SELECT id FROM jobs WHERE title = 'Alert test window clean'"
        )
        self.assertIsNone(
            self.one(
                """
                SELECT id FROM contractor_lead_alert_deliveries
                WHERE contractor_id = ? AND job_id = ?
                """,
                (contractor["id"], nonmatching_job["id"]),
            )
        )

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        opted_out = self.client.post(
            "/contractor/preferences/lead-view",
            data={
                "saved_category": "Power washing",
                "saved_service_group_slug": "outdoor-yard",
                "saved_service_slug": "pressure-washing",
                "saved_query": "Washington DC",
                "saved_sort": "newest",
                "lead_alert_preference": "workdoe",
            },
            follow_redirects=True,
        )
        self.assertEqual(opted_out.status_code, 200)
        preference = self.one(
            "SELECT * FROM contractor_lead_preferences WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(preference["lead_alert_preference"], "workdoe")
        self.assertIsNone(preference["lead_alert_consent_at"])

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        admin = self.client.get("/admin")
        self.assertIn(b"Matching project alerts", admin.data)
        self.assertIn(b"Opt-in only", admin.data)
        self.assertIn(b"Recent matching alerts", admin.data)
        self.assertIn(b"Alert test pressure wash", admin.data)
        self.assertNotIn(b"20003", admin.data)

    def test_contractor_credentials_require_admin_source_review_before_public_display(self):
        contractor = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("contractor@workdoe.local",),
        )
        profile_url = f"/contractors/{contractor['id']}"

        self.login("client@workdoe.local", "workdoe-client")
        role_block = self.client.post(
            "/contractor/credentials",
            data={
                "credential_type": "trade_license",
                "jurisdiction": "VA",
                "claimed_identifier": "VA-CLIENT-1",
            },
        )
        self.assertEqual(role_block.status_code, 403)
        self.logout()

        self.login("contractor@workdoe.local", "workdoe-contractor")
        profile = self.client.get("/contractor/profile")
        self.assertIn(b"Submit a credential claim", profile.data)
        self.assertIn(b"No credential claims submitted", profile.data)

        invalid = self.client.post(
            "/contractor/credentials",
            data={
                "credential_type": "trade_license",
                "jurisdiction": "VA",
                "claimed_identifier": "VA-1234",
                "source_url": "http://registry.example/VA-1234",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Use a public HTTPS source link", invalid.data)
        self.assertIsNone(self.one("SELECT id FROM contractor_credentials"))

        submitted = self.client.post(
            "/contractor/credentials",
            data={
                "credential_type": "trade_license",
                "jurisdiction": "VA",
                "claimed_identifier": "VA-1234",
                "claimed_name": "Rivera Exterior Care",
                "source_url": "https://registry.example/VA-1234",
                "expires_at": "2027-12-31",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Credential claim sent for review", submitted.data)
        claim = self.one("SELECT * FROM contractor_credentials")
        self.assertEqual(claim["contractor_id"], contractor["id"])
        self.assertEqual(claim["status"], "self_reported")
        self.assertIsNone(claim["checked_at"])

        public_pending = self.client.get(profile_url)
        self.assertNotIn(b"Source-checked records", public_pending.data)
        self.assertNotIn(b"VA-1234", public_pending.data)

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        invalid_review_source = self.client.post(
            f"/admin/credentials/{claim['id']}/verify",
            data={
                "source_url": "http://registry.example/VA-1234",
                "expires_at": "2027-12-31",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Use a public HTTPS source link", invalid_review_source.data)
        self.assertEqual(
            self.one(
                "SELECT status FROM contractor_credentials WHERE id = ?",
                (claim["id"],),
            )["status"],
            "self_reported",
        )

        reviewed = self.client.post(
            f"/admin/credentials/{claim['id']}/verify",
            data={
                "source_url": "https://registry.example/VA-1234",
                "expires_at": "2027-12-31",
                "review_note": "Public registry record checked.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Credential review saved", reviewed.data)
        checked = self.one(
            "SELECT * FROM contractor_credentials WHERE id = ?",
            (claim["id"],),
        )
        self.assertEqual(checked["status"], "verified")
        self.assertIsNotNone(checked["checked_at"])
        self.assertIsNotNone(checked["reviewed_by"])

        self.logout()
        public_checked = self.client.get(profile_url)
        self.assertIn(b"Source-checked records", public_checked.data)
        self.assertIn(b"Trade license - Virginia", public_checked.data)
        self.assertIn(b"Public source", public_checked.data)

        self.login("contractor@workdoe.local", "workdoe-contractor")
        protected_history = self.client.post(
            f"/contractor/credentials/{claim['id']}/remove"
        )
        self.assertEqual(protected_history.status_code, 409)
        self.logout()

        self.login("admin@workdoe.local", "workdoe-admin")
        expired = self.client.post(
            f"/admin/credentials/{claim['id']}/expire",
            data={
                "source_url": "https://registry.example/VA-1234",
                "review_note": "Record is no longer current.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Credential review saved", expired.data)
        self.logout()
        public_expired = self.client.get(profile_url)
        self.assertNotIn(b"Source-checked records", public_expired.data)
        audit = self.one(
            """
            SELECT * FROM moderation_actions
            WHERE target_type = 'credential' AND target_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (claim["id"],),
        )
        self.assertEqual(audit["action_type"], "expire")

    def test_structured_contractor_profile_drives_private_market_fit(self):
        contractor = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("contractor@workdoe.local",),
        )
        self.login("contractor@workdoe.local", "workdoe-contractor")
        updated = self.client.post(
            "/contractor/profile",
            data={
                "market_fit_version": "1",
                "business_name": "Rivera Exterior Care",
                "service_slugs": ["pressure-washing", "window-cleaning"],
                "service_zone_slugs": ["district-of-columbia", "arlington-county-va"],
                "years_in_business": "5",
                "insurance_status": "Available on request",
                "license_number": "Local beta profile",
                "website": "https://rivera.example",
                "phone": "(202) 555-0180",
                "intro": "Exterior cleaning for homes and storefronts with careful site protection.",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Contractor profile updated", updated.data)
        capabilities = self.all(
            """
            SELECT service_slug
            FROM contractor_service_capabilities
            WHERE contractor_id = ?
            ORDER BY service_slug
            """,
            (contractor["id"],),
        )
        self.assertEqual(
            {row["service_slug"] for row in capabilities},
            {"pressure-washing", "window-cleaning"},
        )
        zones = self.all(
            """
            SELECT zone_slug
            FROM contractor_service_zones
            WHERE contractor_id = ?
            ORDER BY zone_slug
            """,
            (contractor["id"],),
        )
        self.assertEqual(
            {row["zone_slug"] for row in zones},
            {"district-of-columbia", "arlington-county-va"},
        )
        profile = self.one(
            "SELECT trades, service_area FROM contractor_profiles WHERE user_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(profile["trades"], "Power washing, Window cleaning")
        self.assertIn("District of Columbia", profile["service_area"])
        self.assertIn("Arlington County, VA", profile["service_area"])

        leads = self.client.get("/leads")
        self.assertIn(b"Best fit", leads.data)
        self.assertNotIn(b"22201</span>", leads.data)
        public_profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertIn(b"Pressure washing", public_profile.data)
        self.assertIn(b"Arlington", public_profile.data)

    def test_client_can_prefill_a_repeat_project_without_reusing_the_date(self):
        client = self.one("SELECT id FROM users WHERE email = ?", ("client@workdoe.local",))
        job = self.one(
            "SELECT * FROM jobs WHERE client_id = ? ORDER BY id LIMIT 1",
            (client["id"],),
        )
        with self.app.app_context():
            get_db().execute("UPDATE jobs SET status = 'closed' WHERE id = ?", (job["id"],))
            get_db().commit()

        self.login("client@workdoe.local", "workdoe-client")
        dashboard = self.client.get("/client/dashboard")
        self.assertIn(b"Post again", dashboard.data)
        self.assertIn(f"/jobs/new?repeat={job['id']}".encode("ascii"), dashboard.data)

        repeated = self.client.get(f"/jobs/new?repeat={job['id']}")
        self.assertEqual(repeated.status_code, 200)
        self.assertIn(f'value="{job["title"]}"'.encode(), repeated.data)
        self.assertIn(f'value="{job["zip_code"]}"'.encode("ascii"), repeated.data)
        self.assertIn(b'id="job-desired-date"', repeated.data)
        self.assertNotIn(
            f'value="{job["desired_date"]}"'.encode("ascii"),
            repeated.data,
        )

    def test_contractor_profile_report_flow_and_admin_review(self):
        contractor = self.one("SELECT id FROM users WHERE email = ?", ("contractor@workdoe.local",))
        profile_url = f"/contractors/{contractor['id']}"

        public_profile = self.client.get(profile_url)
        self.assertEqual(public_profile.status_code, 200)
        self.assertNotIn(b"Report this profile", public_profile.data)
        self.assertIn(
            b"Profile details are self-reported. A source-checked record means Workdoe reviewed the linked public source",
            public_profile.data,
        )

        self.login("client@workdoe.local", "workdoe-client")
        client_profile = self.client.get(profile_url)
        self.assertEqual(client_profile.status_code, 200)
        self.assertIn(b"Report this profile", client_profile.data)
        self.assertIn(b'value="profile"', client_profile.data)
        self.assertIn(f'value="{contractor["id"]}"'.encode("ascii"), client_profile.data)
        self.assertIn(b'for="profile-report-reason"', client_profile.data)
        self.assertIn(
            b'id="profile-report-reason" name="reason" maxlength="500" placeholder="Why should moderation review it?" autocapitalize="sentences" spellcheck="true" enterkeyhint="send" required',
            client_profile.data,
        )
        self.assertIn(b'aria-label="Report profile"', client_profile.data)

        sent = self.client.post(
            "/report",
            data={
                "target_type": "profile",
                "target_id": str(contractor["id"]),
                "reason": "Profile needs moderation review",
            },
            headers={"Referer": f"http://localhost{profile_url}"},
        )
        self.assertEqual(sent.status_code, 302)
        self.assertEqual(sent.headers["Location"], profile_url)
        report = self.one(
            """
            SELECT * FROM reports
            WHERE target_type = 'profile' AND target_id = ? AND reason = ?
            """,
            (contractor["id"], "Profile needs moderation review"),
        )
        self.assertIsNotNone(report)

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        own_profile = self.client.get(profile_url)
        self.assertEqual(own_profile.status_code, 200)
        self.assertNotIn(b"Report this profile", own_profile.data)

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        admin = self.client.get("/admin")
        self.assertEqual(admin.status_code, 200)
        self.assertIn(b"Profile: Rivera Exterior Care", admin.data)
        self.assertIn(f'href="{profile_url}"'.encode("ascii"), admin.data)
        self.assertIn(b">Review</a>", admin.data)

        with self.app.app_context():
            get_db().execute(
                "UPDATE users SET status = 'suspended' WHERE id = ?",
                (contractor["id"],),
            )
            get_db().commit()

        review = self.client.get(profile_url)
        self.assertEqual(review.status_code, 200)
        self.assertIn(b'class="status suspended">suspended</span>', review.data)
        self.assertNotIn(b"Report this profile", review.data)

    def test_outsider_cannot_report_a_private_message_by_id(self):
        with self.app.app_context():
            db = get_db()
            job = db.execute("SELECT id, client_id FROM jobs ORDER BY id LIMIT 1").fetchone()
            contractor = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            match = db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', ?, 'approved', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "Private matched work scope for authorization testing.",
                    "$500",
                    "Two days",
                    "Relevant local project experience for this work.",
                    "Next week",
                    "2026-08-16T12:00:00+00:00",
                    "2026-08-16T12:00:00+00:00",
                ),
            )
            thread = db.execute(
                """
                INSERT INTO threads
                    (job_id, match_request_id, client_id, contractor_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job["id"],
                    match.lastrowid,
                    job["client_id"],
                    contractor["id"],
                    "2026-08-16T12:00:00+00:00",
                ),
            )
            message = db.execute(
                """
                INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at)
                VALUES (?, ?, ?, 0, ?)
                """,
                (
                    thread.lastrowid,
                    contractor["id"],
                    "Private project scheduling details.",
                    "2026-08-16T12:01:00+00:00",
                ),
            )
            outsider = db.execute(
                """
                INSERT INTO users
                    (email, password_hash, role, display_name, company_name,
                     status, email_verified, created_at)
                VALUES (?, ?, 'client', 'Outside Client', '', 'active', 1, ?)
                """,
                (
                    "outside-client@workdoe.local",
                    generate_password_hash("outside-client-password"),
                    "2026-08-16T12:02:00+00:00",
                ),
            )
            db.execute(
                "INSERT INTO client_profiles (user_id, organization_name, phone) VALUES (?, ?, '')",
                (outsider.lastrowid, "Outside Client"),
            )
            db.commit()
            message_id = int(message.lastrowid)
            outsider_id = int(outsider.lastrowid)

        self.login("outside-client@workdoe.local", "outside-client-password")
        blocked = self.client.post(
            "/report",
            data={
                "target_type": "message",
                "target_id": str(message_id),
                "reason": "Guessed private message identifier.",
            },
            follow_redirects=True,
        )
        self.assertEqual(blocked.status_code, 200)
        self.assertIn(b"That item is no longer available to report.", blocked.data)
        self.assertIsNone(
            self.one(
                "SELECT id FROM reports WHERE reporter_id = ? AND target_type = 'message'",
                (outsider_id,),
            )
        )

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        allowed = self.client.post(
            "/report",
            data={
                "target_type": "message",
                "target_id": str(message_id),
                "reason": "Participant report for moderator review.",
            },
            follow_redirects=True,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertIn(b"Report sent to moderation.", allowed.data)
        self.assertIsNotNone(
            self.one(
                "SELECT id FROM reports WHERE reporter_id = ? AND target_type = 'message'",
                (contractor["id"],),
            )
        )

    def test_role_boundaries(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        self.login("contractor@workdoe.local", "workdoe-contractor")
        self.assertEqual(self.client.get("/client/dashboard").status_code, 403)
        self.assertEqual(self.client.get(f"/client/jobs/{job['id']}/edit").status_code, 403)
        self.logout()

        self.login("client@workdoe.local", "workdoe-client")
        self.assertEqual(self.client.get("/leads").status_code, 403)
        self.assertEqual(self.client.get("/contractor/profile").status_code, 403)
        self.logout()

        self.login("admin@workdoe.local", "workdoe-admin")
        admin = self.client.get("/admin")
        self.assertEqual(admin.status_code, 200)
        self.assertIn(
            b'class="dashboard-metrics compact-metrics" aria-label="Moderation summary"',
            admin.data,
        )
        self.assertIn(b"Open reports", admin.data)
        self.assertIn(b"Audit", admin.data)
        self.assertIn(b"Automation", admin.data)
        self.assertIn(b"No automation events yet.", admin.data)

    def test_dashboards_show_compact_work_queue_metrics(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("contractor@workdoe.local", "workdoe-contractor")
        self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can complete the work and protect nearby surfaces.",
                "price_range": "$450-$650",
                "timeline": "Within two business days",
                "experience": "Five years handling exterior jobs across the DMV.",
                "questions": "",
                "availability": "Weekday mornings",
            },
            follow_redirects=True,
        )

        contractor_dashboard = self.client.get("/contractor/dashboard")
        contractor_html = contractor_dashboard.data.decode("utf-8")
        self.assertIn('class="dashboard-metrics" aria-label="Contractor work queue"', contractor_html)
        self.assertRegex(contractor_html, r"<span>Open projects</span>\s*<strong>3</strong>")
        self.assertRegex(contractor_html, r"<span>Pending bids</span>\s*<strong>1</strong>")
        self.assertRegex(contractor_html, r"<span>Approved</span>\s*<strong>0</strong>")
        self.assertIn(
            'class="work-view-tabs bid-view-tabs" aria-label="Contractor mini bid status"',
            contractor_html,
        )
        self.assertIn('href="/contractor/dashboard?bids=pending"', contractor_html)

        contractor_pending = self.client.get("/contractor/dashboard?bids=pending")
        pending_html = contractor_pending.data.decode("utf-8")
        self.assertIn(
            'href="/contractor/dashboard?bids=pending" aria-current="page"',
            pending_html,
        )
        self.assertIn(b"Power wash townhouse front steps", contractor_pending.data)
        self.assertIn(
            b'aria-label="View mini bid for Power wash townhouse front steps"',
            contractor_pending.data,
        )
        self.assertIn(b'<span class="row-cue">View</span>', contractor_pending.data)

        contractor_approved = self.client.get("/contractor/dashboard?bids=approved")
        self.assertIn(b"No approved bids.", contractor_approved.data)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        client_dashboard = self.client.get("/client/dashboard")
        client_html = client_dashboard.data.decode("utf-8")
        self.assertIn('class="dashboard-metrics" aria-label="Client work queue"', client_html)
        self.assertRegex(client_html, r"<span>Open</span>\s*<strong>3</strong>")
        self.assertRegex(client_html, r"<span>Pending bids</span>\s*<strong>1</strong>")
        self.assertRegex(client_html, r"<span>Total projects</span>\s*<strong>3</strong>")
        self.assertIn('class="work-view-tabs" aria-label="Client job status"', client_html)
        self.assertIn('href="/client/dashboard?view=review"', client_html)
        self.assertRegex(client_html, r"<span>Needs review</span>\s*<strong>1</strong>")
        self.assertIn('href="/jobs/new"', client_html)
        self.assertIn(f'href="/client/jobs/{job["id"]}?bids=pending#mini-bids"', client_html)
        self.assertIn('class="job-row link-row needs-review"', client_html)
        self.assertIn('aria-label="Review pending bids for Power wash townhouse front steps"', client_html)
        self.assertIn('<span class="count-pill attention">1 pending</span>', client_html)
        self.assertIn('<span class="row-cue">Review bids</span>', client_html)

        review_dashboard = self.client.get("/client/dashboard?view=review")
        review_html = review_dashboard.data.decode("utf-8")
        self.assertIn('href="/client/dashboard?view=review" aria-current="page"', review_html)
        self.assertIn(b"Power wash townhouse front steps", review_dashboard.data)
        self.assertNotIn(b"Replace damaged fence panel", review_dashboard.data)
        self.assertIn(f'href="/client/jobs/{job["id"]}?bids=pending#mini-bids"', review_html)

    def test_security_headers_support_map_without_inline_scripts(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        csp = response.headers["Content-Security-Policy"]
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self'", csp)
        self.assertIn("style-src 'self'", csp)
        self.assertIn("style-src-elem 'self'", csp)
        self.assertIn("style-src-attr 'unsafe-inline'", csp)
        self.assertIn("img-src 'self' data: https://tile.openstreetmap.org", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertNotIn("unpkg.com", csp)
        self.assertNotIn("'unsafe-inline'", csp.split("script-src", 1)[1].split(";", 1)[0])
        self.assertNotIn("'unsafe-inline'", csp.split("style-src ", 1)[1].split(";", 1)[0])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn(b'class="skip-link" href="#main-content">Skip to content</a>', response.data)
        self.assertIn(b'<main id="main-content" tabindex="-1">', response.data)
        self.assertIn(
            b'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            response.data,
        )
        self.assertIn(b'<meta name="theme-color" content="#1b2b22">', response.data)
        self.assertIn(b'<link rel="canonical" href="https://workdoe.com/">', response.data)
        self.assertIn(
            b'<meta property="og:title" content="Workdoe - a local Work Exchange">',
            response.data,
        )
        self.assertIn(
            b'<meta property="og:image" content="https://workdoe.com/workdoe-share.png">',
            response.data,
        )
        self.assertIn(
            b'<meta name="twitter:card" content="summary_large_image">',
            response.data,
        )
        self.assertIn(
            b'<link rel="icon" href="/static/deer.svg" type="image/svg+xml">',
            response.data,
        )
        self.assertIn(
            b'<link rel="manifest" href="/static/site.webmanifest">',
            response.data,
        )

        manifest = self.client.get("/static/site.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        manifest_payload = json.loads(manifest.get_data(as_text=True))
        manifest.close()
        self.assertEqual(manifest_payload["name"], "Workdoe")
        self.assertEqual(manifest_payload["start_url"], "/")
        self.assertEqual(manifest_payload["theme_color"], "#1b2b22")
        self.assertEqual(manifest_payload["icons"][0]["src"], "/static/deer.svg")

        share_image = self.client.get("/static/workdoe-share.png")
        self.assertEqual(share_image.status_code, 200)
        self.assertEqual(share_image.mimetype, "image/png")
        self.assertEqual(share_image.data[:8], b"\x89PNG\r\n\x1a\n")
        share_image.close()

    def test_error_pages_are_branded_private_and_navigable(self):
        missing = self.client.get("/missing-workdoe-page")
        self.assertEqual(missing.status_code, 404)
        self.assertIn(b"<title>404 - Workdoe</title>", missing.data)
        self.assertIn(b'class="error-shell"', missing.data)
        self.assertIn(b"That page is not available or has been removed.", missing.data)
        self.assertIn(b'href="/">Back home</a>', missing.data)
        self.assertNotIn(b"Traceback", missing.data)
        self.assertEqual(missing.headers["X-Frame-Options"], "DENY")

        self.login("contractor@workdoe.local", "workdoe-contractor")
        forbidden = self.client.get("/client/dashboard")
        self.assertEqual(forbidden.status_code, 403)
        self.assertIn(b"<title>403 - Workdoe</title>", forbidden.data)
        self.assertIn(b"Access limited", forbidden.data)
        self.assertIn(b"This workspace cannot open that page.", forbidden.data)
        self.assertIn(b'href="/dashboard">Dashboard</a>', forbidden.data)
        self.assertIn(b'href="/">Back home</a>', forbidden.data)
        self.assertNotIn(b"Forbidden", forbidden.data)
        self.assert_no_store(forbidden)

    def test_bad_request_and_server_error_pages_do_not_leak_details(self):
        bad_app = create_app(
            {
                "TESTING": True,
                "PROPAGATE_EXCEPTIONS": False,
                "DATABASE": str(self.root / "workdoe-error.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "error-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": True,
                "SECRET_KEY": "test-secret",
            }
        )

        @bad_app.route("/bad-test-route")
        def bad_test_route():
            from flask import abort

            abort(400)

        @bad_app.route("/explode-test-route")
        def explode_test_route():
            from flask import abort

            abort(500, description="internal secret detail")

        bad_client = bad_app.test_client()
        bad = bad_client.get("/bad-test-route")
        self.assertEqual(bad.status_code, 400)
        self.assertIn(b"<title>400 - Workdoe</title>", bad.data)
        self.assertIn(b"Request stopped", bad.data)
        self.assertNotIn(b"Bad Request", bad.data)

        exploded = bad_client.get("/explode-test-route")
        self.assertEqual(exploded.status_code, 500)
        self.assertIn(b"<title>500 - Workdoe</title>", exploded.data)
        self.assertIn(b"Workdoe hit a server issue", exploded.data)
        self.assertNotIn(b"internal secret detail", exploded.data)
        self.assertNotIn(b"Traceback", exploded.data)

    def test_navigation_exposes_current_page_for_screen_readers(self):
        login = self.client.get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'href="/login" aria-current="page">Sign in</a>', login.data)

        create_account = self.client.get("/create-account")
        self.assertEqual(create_account.status_code, 200)
        self.assertIn(
            b'href="/create-account" aria-current="page">Create account</a>',
            create_account.data,
        )

        post_project = self.client.get("/post-project")
        self.assertEqual(post_project.status_code, 200)
        self.assertIn(b"<title>Post Project - Workdoe</title>", post_project.data)
        self.assertIn(b"<h1>What needs doing?</h1>", post_project.data)
        self.assertIn(b'aria-label="Project draft"', post_project.data)
        self.assertIn(
            b'href="/post-project" aria-current="page">Post project</a>',
            post_project.data,
        )

        self.login("contractor@workdoe.local", "workdoe-contractor")
        leads = self.client.get("/leads")
        self.assertEqual(leads.status_code, 200)
        self.assertIn(b'href="/leads" aria-current="page">Find work</a>', leads.data)

    def test_shared_accessibility_contract_is_present_on_local_pages(self):
        for path in ("/", "/login", "/create-account", "/post-project", "/safety"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.data.decode("utf-8")
                self.assertIn('<html lang="en">', html)
                self.assertIn('<a class="skip-link" href="#main-content">Skip to content</a>', html)
                self.assertIn('<nav class="main-nav" aria-label="Main navigation">', html)
                self.assertIn('<main id="main-content" tabindex="-1">', html)
                self.assertLess(html.index('class="skip-link"'), html.index('<header class="site-header">'))
                self.assertLess(html.index('<header class="site-header">'), html.index('id="main-content"'))

        styles = (ROOT / "workdoe" / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn("a:focus-visible", styles)
        self.assertIn("input:focus-visible", styles)
        self.assertIn("textarea:focus-visible", styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)

    def test_mobile_css_keeps_entry_header_visible_and_auth_first(self):
        styles = (ROOT / "workdoe" / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".entry-shortcuts", styles)
        self.assertIn(".entry-shortcut", styles)
        self.assertRegex(
            styles,
            r'\.main-nav \.button\[aria-current="page"\]\s*\{[^}]*color: #fff;[^}]*text-decoration: none;',
        )
        self.assertRegex(styles, r"\.entry-shortcuts a,\s*\.entry-shortcut\s*\{[^}]*min-height: 30px;")
        mobile_rules = re.search(r"@media \(max-width: 900px\) \{(?P<body>.*)\n\}", styles, re.DOTALL)
        self.assertIsNotNone(mobile_rules)
        body = mobile_rules.group("body")
        self.assertRegex(body, r"\.brand,\s*\.main-nav\s*\{[^}]*flex: 0 1 auto;[^}]*width: 100%;")
        self.assertRegex(body, r"\.start-form-panel\s*\{[^}]*order: -1;")
        self.assertNotRegex(body, r"\.login-live-panel,\s*\.start-live-panel\s*\{[^}]*order: -1;")
        self.assertRegex(body, r"\.lead-metrics\s*\{[^}]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);")
        self.assertRegex(body, r"\.lead-filter\s*\{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);")
        self.assertRegex(body, r"\.lead-filter \.search-field\s*\{[^}]*grid-column: 1 / -1;[^}]*order: -1;")
        self.assertRegex(body, r"@media \(max-width: 520px\)\s*\{")
        self.assertRegex(
            body,
            r"\.main-nav\s*\{[^}]*display: flex;[^}]*flex-wrap: wrap;[^}]*overflow-x: visible;",
        )
        self.assertRegex(
            body,
            r"\.main-nav a,[^}]*flex: 0 0 auto;[^}]*min-height: 44px;[^}]*white-space: nowrap;",
        )
        self.assertRegex(body, r"\.lead-filter,\s*\.compact-filter,\s*\.entry-filter\s*\{[^}]*grid-template-columns: 1fr;")
        self.assertRegex(
            body,
            r"\.lead-map-panel,\s*\.lead-map-panel #lead-map\s*\{[^}]*min-height: 300px;",
        )
        self.assertRegex(body, r"\.lead-map-panel #lead-map\s*\{[^}]*height: 300px;")

    def test_login_returns_to_safe_next_after_permission_gate(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        gated = self.client.get("/jobs/new")
        self.assertEqual(gated.status_code, 302)
        self.assertIn("/login?next=/jobs/new", gated.headers["Location"])

        login = self.client.get("/login?next=/jobs/new")
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'name="next" value="/jobs/new"', login.data)
        self.assertIn(b'name="auth_action" value="code"', login.data)
        self.assertIn(b"Email code", login.data)
        self.assertIn(b"Admin/demo password", login.data)

        returned = self.client.post(
            "/login?next=/jobs/new",
            data={"email": "client@workdoe.local", "password": "workdoe-client"},
            follow_redirects=True,
        )
        self.assertEqual(returned.status_code, 200)
        self.assertIn(b"Post a project", returned.data)

        self.logout()
        unsafe = self.client.get("/login?next=https://example.test/jobs/new")
        self.assertEqual(unsafe.status_code, 200)
        self.assertNotIn(b"example.test", unsafe.data)

        unsafe_login = self.client.post(
            "/login?next=https://example.test/jobs/new",
            data={"email": "client@workdoe.local", "password": "workdoe-client"},
        )
        self.assertEqual(unsafe_login.status_code, 302)
        self.assertEqual(unsafe_login.headers["Location"], "/dashboard")

        self.logout()
        lead_login = self.client.get(f"/login?next=/jobs/{job['id']}")
        self.assertEqual(lead_login.status_code, 200)
        self.assertIn(f'name="next" value="/jobs/{job["id"]}"'.encode("ascii"), lead_login.data)
        self.assertIn(b"Selected", lead_login.data)
        self.assertIn(b'aria-current="true"', lead_login.data)
        self.assertIn(b"is-selected", lead_login.data)
        self.assertIn(b"No password needed.", lead_login.data)

        new_lead_start = self.client.post(
            f"/login?next=/jobs/{job['id']}",
            data={"email": "new-contractor@example.com", "auth_action": "code"},
        )
        self.assertEqual(new_lead_start.status_code, 302)
        self.assertIn("/create-account?intent=find-work", new_lead_start.headers["Location"])
        self.assertIn(f"job_id={job['id']}", new_lead_start.headers["Location"])
        self.assertIn("email=new-contractor@example.com", new_lead_start.headers["Location"])

        new_lead_start_page = self.client.get(new_lead_start.headers["Location"])
        self.assertEqual(new_lead_start_page.status_code, 200)
        self.assertIn(b'value="find-work" checked', new_lead_start_page.data)
        self.assertIn(f'name="job_id" value="{job["id"]}"'.encode("ascii"), new_lead_start_page.data)
        self.assertIn(b'value="new-contractor@example.com"', new_lead_start_page.data)

        code_request = self.client.post(
            f"/login?next=/jobs/{job['id']}",
            data={"email": "contractor@workdoe.local", "auth_action": "code"},
            follow_redirects=True,
        )
        code_html = code_request.data.decode("utf-8")
        code_match = re.search(r"<strong>([0-9]{6})</strong>", code_html)
        self.assertIsNotNone(code_match)
        self.assertIn("Back to sign in", code_html)
        self.assertIn(f'href="/login?next=/jobs/{job["id"]}"', code_html)

        code_return = self.client.post(
            "/start/verify",
            data={"code": code_match.group(1)},
            follow_redirects=True,
        )
        self.assertEqual(code_return.status_code, 200)
        self.assertEqual(code_return.request.path, f"/jobs/{job['id']}")
        self.assertIn(b"Send bid", code_return.data)

        self.logout()
        contractor_return = self.client.post(
            f"/login?next=/jobs/{job['id']}",
            data={"email": "contractor@workdoe.local", "password": "workdoe-contractor"},
            follow_redirects=True,
        )
        self.assertEqual(contractor_return.status_code, 200)
        self.assertIn(b"Send bid", contractor_return.data)

        self.logout()
        client_return = self.client.post(
            f"/login?next=/jobs/{job['id']}",
            data={"email": "client@workdoe.local", "password": "workdoe-client"},
        )
        self.assertEqual(client_return.status_code, 302)
        self.assertEqual(client_return.headers["Location"], "/dashboard")

    def test_session_cookie_defaults_and_private_pages_do_not_cache(self):
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertFalse(self.app.config["SESSION_COOKIE_SECURE"])

        home = self.client.get("/")
        self.assertNotEqual(home.headers.get("Cache-Control"), "no-store")

        login = self.client.get("/login")
        self.assert_no_store(login)

        start = self.client.get("/start")
        self.assert_no_store(start)

        self.login("client@workdoe.local", "workdoe-client")
        dashboard = self.client.get("/client/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assert_no_store(dashboard)

    def test_production_mode_requires_safe_cloudflare_defaults(self):
        with self.assertRaisesRegex(RuntimeError, "WORKDOE_AUTH_PROVIDER"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "bad-auth-provider.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "bad-auth-provider-uploads"),
                    "AUTH_PROVIDER": "magic-link-ish",
                }
            )

        with self.assertRaisesRegex(RuntimeError, "WORKDOE_CLERK_LOGIN_MODE"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "bad-clerk-mode.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "bad-clerk-mode-uploads"),
                    "CLERK_LOGIN_MODE": "hosted_redirect",
                }
            )

        with self.assertRaisesRegex(RuntimeError, "WORKDOE_SECRET_KEY"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "bad-production.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "bad-production-uploads"),
                    "PRODUCTION": True,
                }
            )

        with self.assertRaisesRegex(RuntimeError, "WORKDOE_TURNSTILE_VERIFY_URL"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "bad-turnstile-url.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "bad-turnstile-url-uploads"),
                    "PRODUCTION": True,
                    "SECRET_KEY": "production-secret-for-test",
                    "SEED_DEMO_DATA": False,
                    "SESSION_COOKIE_SECURE": True,
                    "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                    "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
                    "TURNSTILE_VERIFY_URL": "file:///tmp/not-cloudflare",
                }
            )

        production_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "production.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "production-uploads"),
                "PRODUCTION": True,
                "SECRET_KEY": "production-secret-for-test",
                "SEED_DEMO_DATA": False,
                "SESSION_COOKIE_SECURE": True,
                "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
            }
        )
        self.assertTrue(production_app.config["SESSION_COOKIE_SECURE"])
        self.assertFalse(production_app.config["SEED_DEMO_DATA"])
        with production_app.app_context():
            demo = get_db().execute(
                "SELECT id FROM users WHERE email = ?",
                ("client@workdoe.local",),
            ).fetchone()
        self.assertIsNone(demo)

        with self.assertRaisesRegex(RuntimeError, "CLERK_PUBLISHABLE_KEY"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "missing-clerk.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "missing-clerk-uploads"),
                    "PRODUCTION": True,
                    "AUTH_PROVIDER": "clerk",
                    "SECRET_KEY": "production-secret-for-test",
                    "SEED_DEMO_DATA": False,
                    "SESSION_COOKIE_SECURE": True,
                    "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                    "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
                }
            )

        with self.assertRaisesRegex(RuntimeError, "CLERK_FRONTEND_API_URL"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "off-domain-clerk.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "off-domain-clerk-uploads"),
                    "PRODUCTION": True,
                    "AUTH_PROVIDER": "clerk",
                    "SECRET_KEY": "production-secret-for-test",
                    "SEED_DEMO_DATA": False,
                    "SESSION_COOKIE_SECURE": True,
                    "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                    "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
                    "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                    "CLERK_SECRET_KEY": "sk_test_workdoe",
                    "CLERK_WEBHOOK_SECRET": "whsec_workdoe",
                    "CLERK_JWT_KEY": "jwt-key-workdoe",
                    "CLERK_FRONTEND_API_URL": "https://evilworkdoe.com",
                }
            )

        with self.assertRaisesRegex(RuntimeError, "CLERK_FRONTEND_API_URL"):
            create_app(
                {
                    "TESTING": True,
                    "DATABASE": str(self.root / "development-clerk-production.sqlite3"),
                    "UPLOAD_ROOT": str(self.root / "development-clerk-production-uploads"),
                    "PRODUCTION": True,
                    "AUTH_PROVIDER": "clerk",
                    "SECRET_KEY": "production-secret-for-test",
                    "SEED_DEMO_DATA": False,
                    "SESSION_COOKIE_SECURE": True,
                    "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                    "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
                    "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                    "CLERK_SECRET_KEY": "sk_test_workdoe",
                    "CLERK_WEBHOOK_SECRET": "whsec_workdoe",
                    "CLERK_JWT_KEY": "jwt-key-workdoe",
                    "CLERK_FRONTEND_API_URL": "https://close-seal-34.clerk.accounts.dev",
                }
            )

        clerk_app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "production-clerk.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "production-clerk-uploads"),
                "PRODUCTION": True,
                "AUTH_PROVIDER": "clerk",
                "SECRET_KEY": "production-secret-for-test",
                "SEED_DEMO_DATA": False,
                "SESSION_COOKIE_SECURE": True,
                "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
                "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                "CLERK_SECRET_KEY": "sk_test_workdoe",
                "CLERK_WEBHOOK_SECRET": "whsec_workdoe",
                "CLERK_JWT_KEY": "jwt-key-workdoe",
                "CLERK_FRONTEND_API_URL": "https://clerk.workdoe.com",
            }
        )
        self.assertEqual(clerk_app.config["AUTH_PROVIDER"], "clerk")
        self.assertEqual(clerk_app.config["CLERK_LOGIN_MODE"], "same_domain_email_code")

    def test_clerk_mode_renders_same_domain_entry_mounts(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "clerk-entry.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "clerk-entry-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": True,
                "SECRET_KEY": "test-secret",
                "AUTH_PROVIDER": "clerk",
                "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                "CLERK_FRONTEND_API_URL": "https://clerk.workdoe.com",
            }
        )
        client = app.test_client()

        login = client.get("/login?next=/jobs/new")
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'data-clerk-entry', login.data)
        self.assertIn(b'Loading secure email sign-in...', login.data)
        self.assertNotIn(b'data-clerk-email-code-form', login.data)
        self.assertIn(b'data-clerk-mode="signin"', login.data)
        self.assertIn(b'data-redirect-url="/jobs/new"', login.data)
        self.assertIn(b'data-session-url="/api/auth/session"', login.data)
        self.assertIn(b'data-dashboard-url="/dashboard"', login.data)
        self.assertIn(b"No password needed. Your one-time code arrives by email.", login.data)
        self.assertIn(
            b'class="help-text clerk-entry-status" role="status" aria-live="polite" data-clerk-onboarding-message',
            login.data,
        )
        self.assertIn(b"https://clerk.workdoe.com/npm/@clerk/ui@1", login.data)
        self.assertIn(b"https://clerk.workdoe.com/npm/@clerk/clerk-js@6", login.data)
        self.assertIn(b"/static/clerk-entry.js", login.data)
        self.assertNotIn(b'name="auth_action" value="code"', login.data)

        selected_login = client.get("/login?next=/jobs/1")
        self.assertEqual(selected_login.status_code, 200)
        self.assertIn(
            b'data-sign-up-url="/create-account?intent=find-work&amp;job_id=1&amp;next=/jobs/1"',
            selected_login.data,
        )

        filtered_login = client.get(
            "/login?next=/leads%3Ffamily%3Doutdoor-yard%26service%3Dpressure-washing"
        )
        self.assertEqual(filtered_login.status_code, 200)
        self.assertIn(
            b'data-sign-up-url="/create-account?intent=find-work&amp;next=/leads?family%3Doutdoor-yard%26service%3Dpressure-washing"',
            filtered_login.data,
        )

        start = client.get("/start?intent=find-work")
        self.assertEqual(start.status_code, 200)
        self.assertIn(b'data-clerk-mode="start"', start.data)
        self.assertIn(b'data-session-url="/api/auth/session"', start.data)
        self.assertIn(b'data-onboard-url="/api/auth/onboard"', start.data)
        self.assertIn(b'data-leads-url="/leads"', start.data)
        self.assertIn(b'maxlength="120"', start.data)
        self.assertIn(
            b'class="help-text clerk-entry-status" role="status" aria-live="polite" data-clerk-onboarding-message',
            start.data,
        )

        create_account = client.get("/create-account?intent=find-work")
        self.assertEqual(create_account.status_code, 200)
        self.assertIn(b"<title>Create Account - Workdoe</title>", create_account.data)
        self.assertIn(b"Create your Workdoe account", create_account.data)
        self.assertIn(b'data-clerk-mode="start"', create_account.data)
        self.assertIn(b'data-sign-up-url="/create-account"', create_account.data)
        self.assertIn(
            b'data-redirect-url="/create-account?intent=find-work',
            create_account.data,
        )

        filtered_start = client.get(
            "/create-account?intent=find-work&next=/leads%3Ffamily%3Doutdoor-yard%26service%3Dpressure-washing"
        )
        self.assertEqual(filtered_start.status_code, 200)
        self.assertIn(
            b'data-leads-url="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            filtered_start.data,
        )
        self.assertIn(
            b'data-redirect-url="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            filtered_start.data,
        )

        csp = login.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self' https://clerk.workdoe.com", csp)
        self.assertIn("connect-src 'self' https://clerk.workdoe.com", csp)
        self.assertIn("img-src 'self' data: https://tile.openstreetmap.org https://clerk.workdoe.com", csp)
        self.assertIn(
            "style-src-elem 'self' 'unsafe-inline' https://clerk.workdoe.com",
            csp,
        )
        self.assertIn("frame-src https://clerk.workdoe.com", csp)

    def test_clerk_mode_renders_proxy_url_for_same_origin_proxy(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "clerk-proxy-entry.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "clerk-proxy-entry-uploads"),
                "DISABLE_CSRF": True,
                "SEED_DEMO_DATA": True,
                "SECRET_KEY": "test-secret",
                "AUTH_PROVIDER": "clerk",
                "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                "CLERK_FRONTEND_API_URL": "https://workdoe.com/__clerk",
            }
        )
        client = app.test_client()

        with app.app_context():
            self.assertEqual(clerk_proxy_url(), "https://workdoe.com/__clerk")

        login = client.get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'data-clerk-proxy-url="https://workdoe.com/__clerk"', login.data)
        self.assertIn(b"https://workdoe.com/__clerk/npm/@clerk/clerk-js@6", login.data)
        self.assertIn(
            "script-src 'self' https://workdoe.com",
            login.headers["Content-Security-Policy"],
        )

    def test_local_clerk_auth_api_onboards_same_site_user(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "local-clerk-api.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "local-clerk-api-uploads"),
                "SEED_DEMO_DATA": True,
                "SECRET_KEY": "test-secret",
                "AUTH_PROVIDER": "clerk",
                "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                "CLERK_FRONTEND_API_URL": "https://clerk.workdoe.com",
            }
        )
        client = app.test_client()

        anonymous = client.get("/api/auth/session")
        self.assertEqual(anonymous.status_code, 200)
        self.assertEqual(anonymous.headers["Cache-Control"], "no-store")
        anonymous_payload = anonymous.get_json()
        self.assertFalse(anonymous_payload["authenticated"])
        self.assertTrue(anonymous_payload["onboarding_required"])
        self.assertIsNone(anonymous_payload["workdoe_user"])

        invalid = client.post(
            "/api/auth/onboard",
            json={"email": "casey@example.com", "role": "installer"},
        )
        self.assertEqual(invalid.status_code, 400)

        created = client.post(
            "/api/auth/onboard",
            json={
                "email": "  Casey.Contractor@Example.com  ",
                "role": "contractor",
                "display_name": "  Casey Contractor  ",
                "company_name": "",
            },
        )
        self.assertEqual(created.status_code, 201)
        created_payload = created.get_json()
        self.assertTrue(created_payload["ok"])
        self.assertTrue(created_payload["created"])
        self.assertEqual(created_payload["workdoe_user"]["role"], "contractor")
        self.assertEqual(created_payload["workdoe_user"]["display_name"], "Casey Contractor")

        with app.app_context():
            user = get_db().execute(
                "SELECT * FROM users WHERE email = ?",
                ("casey.contractor@example.com",),
            ).fetchone()
            profile = get_db().execute(
                "SELECT * FROM contractor_profiles WHERE user_id = ?",
                (user["id"],),
            ).fetchone()
            event = get_db().execute(
                """
                SELECT * FROM automation_events
                WHERE event_type = 'clerk-onboarding-linked'
                  AND target_type = 'user'
                  AND target_id = ?
                """,
                (user["id"],),
            ).fetchone()
        self.assertEqual(user["auth_provider"], "clerk")
        self.assertTrue(user["external_subject"].startswith("local-clerk:"))
        self.assertEqual(profile["business_name"], "Casey Contractor")
        self.assertEqual(event["status"], "processed")
        event_payload = json.loads(event["payload_json"])
        self.assertEqual(event_payload["role"], "contractor")
        self.assertNotIn("email", event_payload)
        self.assertTrue(event_payload["local_bridge"])

        active = client.get("/api/auth/session")
        self.assertEqual(active.status_code, 200)
        active_payload = active.get_json()
        self.assertTrue(active_payload["authenticated"])
        self.assertFalse(active_payload["onboarding_required"])
        self.assertEqual(active_payload["workdoe_user"]["role"], "contractor")

        existing = client.post(
            "/api/auth/onboard",
            json={
                "email": "casey.contractor@example.com",
                "role": "contractor",
            },
        )
        self.assertEqual(existing.status_code, 200)
        self.assertFalse(existing.get_json()["created"])

        conflict = client.post(
            "/api/auth/onboard",
            json={"email": "client@workdoe.local", "role": "client"},
        )
        self.assertEqual(conflict.status_code, 409)

    def test_local_clerk_onboard_refuses_production_without_worker_verification(self):
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(self.root / "local-clerk-production-api.sqlite3"),
                "UPLOAD_ROOT": str(self.root / "local-clerk-production-api-uploads"),
                "PRODUCTION": True,
                "AUTH_PROVIDER": "clerk",
                "SECRET_KEY": "production-secret-for-test",
                "SEED_DEMO_DATA": False,
                "SESSION_COOKIE_SECURE": True,
                "TURNSTILE_SITE_KEY": "1x00000000000000000000AA",
                "TURNSTILE_SECRET_KEY": "production-turnstile-secret",
                "CLERK_PUBLISHABLE_KEY": "pk_test_workdoe",
                "CLERK_SECRET_KEY": "sk_test_workdoe",
                "CLERK_WEBHOOK_SECRET": "whsec_workdoe",
                "CLERK_JWT_KEY": "jwt-key-workdoe",
                "CLERK_FRONTEND_API_URL": "https://clerk.workdoe.com",
            }
        )
        response = app.test_client().post(
            "/api/auth/onboard",
            json={"email": "casey@example.com", "role": "contractor"},
        )
        self.assertEqual(response.status_code, 501)
        self.assertIn(b"Cloudflare Worker Clerk verification is required", response.data)

    def test_vendored_browser_assets_are_pinned_and_licensed(self):
        leaflet_hashes = {
            "leaflet.css": "sha256-M3v8pcq9A7OYFbJwD+vis7ft9VkhxZzUn4jssyghIwM=",
            "leaflet.js": "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
        }
        vendor_dir = ROOT / "workdoe" / "static" / "vendor" / "leaflet"

        for filename, expected in leaflet_hashes.items():
            canonical_bytes = (vendor_dir / filename).read_bytes().replace(b"\r\n", b"\n")
            digest = base64.b64encode(hashlib.sha256(canonical_bytes).digest())
            self.assertEqual("sha256-" + digest.decode("ascii"), expected)

        image_hashes = {
            "images/layers.png": "1dbbe9d028e292f36fcba8f8b3a28d5e8932754fc2215b9ac69e4cdecf5107c6",
            "images/layers-2x.png": "066daca850d8ffbef007af00b06eac0015728dee279c51f3cb6c716df7c42edf",
            "images/marker-icon.png": "574c3a5cca85f4114085b6841596d62f00d7c892c7b03f28cbfa301deb1dc437",
            "images/marker-icon-2x.png": "00179c4c1ee830d3a108412ae0d294f55776cfeb085c60129a39aa6fc4ae2528",
            "images/marker-shadow.png": "264f5c640339f042dd729062cfc04c17f8ea0f29882b538e3848ed8f10edb4da",
        }
        for filename, expected in image_hashes.items():
            self.assertEqual(hashlib.sha256((vendor_dir / filename).read_bytes()).hexdigest(), expected)

        self.assertIn("BSD 2-Clause License", (vendor_dir / "LICENSE").read_text())

        markercluster_dir = ROOT / "workdoe" / "static" / "vendor" / "leaflet-markercluster"
        markercluster_hashes = {
            "leaflet.markercluster.js": "1e4e1d22972a3926f48598e0caf14e3fe7049835d428a344fed4f9e3665b3508",
            "MarkerCluster.css": "614dea0a98ff3f4ead74f04918f6b1d1b9ba435c25b5fc23b21a394d1e3e4d87",
            "MarkerCluster.Default.css": "61258232d98d64dc2a7b1e02130d67421bc5b9bda5994eef70228ff97570c170",
        }
        for filename, expected in markercluster_hashes.items():
            self.assertEqual(
                hashlib.sha256((markercluster_dir / filename).read_bytes()).hexdigest(),
                expected,
            )
        self.assertIn("Permission is hereby granted", (markercluster_dir / "LICENSE").read_text())

        deer_root = ET.parse(ROOT / "workdoe" / "static" / "deer.svg").getroot()
        deer_paths = [node.attrib["d"] for node in deer_root.iter() if node.tag.endswith("path")]
        deer_geometry_hash = hashlib.sha256("\n".join(deer_paths).encode("utf-8")).hexdigest()
        self.assertEqual(
            deer_geometry_hash,
            "e42e5123145fcad4bf5a1b198bec2f5c10a58d05bc099d52703f496c313b79a4",
        )
        tabler_license = ROOT / "workdoe" / "static" / "vendor" / "tabler-icons" / "LICENSE"
        self.assertIn("MIT License", tabler_license.read_text(encoding="utf-8"))
        tabler_hashes = {
            "trees.svg": "9ffc31bb059b649d3995bd396f3d0f3ec59e531ffa559072a2ee6d12f5446ba0",
            "spray.svg": "bbd7c65c9e4f58f98bb8a7bc8ebfe38b4d12322576d224a22f9df8aca0efd6a9",
            "truck-delivery.svg": "6e83c8b78ef626b5326a0d27f97cb900a7ad99fc789dc64c696f7a6761dd2628",
            "tools.svg": "aac6ae77bd7d24d3819ed1ccc7262ca1b57444b541fc3dc90ee837bbbe6a6e7c",
            "paint.svg": "ab2b5b985830a0a673c0399b94420ecc7b477dc828509049d16d51eefc57672e",
            "bolt.svg": "f18f1b4476d1f1ba018219131fee671f2a7ac286c9eb3aa83ea72274e17f34e5",
        }
        for filename, expected in tabler_hashes.items():
            self.assertEqual(
                hashlib.sha256((tabler_license.parent / filename).read_bytes()).hexdigest(),
                expected,
            )
        from workdoe.service_taxonomy import (
            SERVICE_ICON_BY_SLUG,
            service_icon,
            service_slug_from_value,
        )

        self.assertEqual(service_slug_from_value("Window cleaning"), "window-cleaning")
        self.assertEqual(service_slug_from_value("  GRASS   CUTTING "), "lawn-mowing")
        self.assertEqual(service_icon("Window cleaning"), "window.svg")

        task_icon_names = sorted(set(SERVICE_ICON_BY_SLUG.values()))
        self.assertEqual(len(task_icon_names), 50)
        task_icon_manifest = "\n".join(
            f"{filename} {hashlib.sha256((tabler_license.parent / filename).read_bytes()).hexdigest()}"
            for filename in task_icon_names
        )
        self.assertEqual(
            hashlib.sha256(task_icon_manifest.encode("utf-8")).hexdigest(),
            "b52f6c73b3afb6b19df964190046fd51748cce40d15c090054909f7007e8fcfe",
        )

    def test_contractor_lead_filters_have_clear_empty_state(self):
        self.login("contractor@workdoe.local", "workdoe-contractor")
        board = self.client.get("/leads")
        self.assertEqual(board.status_code, 200)
        self.assertIn(b'class="dashboard-metrics lead-metrics"', board.data)
        self.assertIn(b'class="filter-bar lead-filter"', board.data)
        self.assertEqual(board.data.count(b'class="service-family-filter-link'), 7)
        self.assertIn(b'/static/vendor/tabler-icons/trees.svg', board.data)
        self.assertIn(b'role="search" aria-label="Filter contractor leads"', board.data)
        self.assertIn(b'aria-controls="lead-results lead-map"', board.data)
        self.assertNotIn(b'for="lead-category"', board.data)
        self.assertNotIn(b'id="lead-category" name="category"', board.data)
        self.assertIn(b'class="search-field"', board.data)
        self.assertIn(b'for="lead-search"', board.data)
        self.assertIn(b'id="lead-results" class="job-list lead-job-list" aria-label="Open leads" role="list"', board.data)
        self.assertIn(b'class="map-panel lead-map-panel"', board.data)
        self.assertLess(board.data.find(b"lead-job-list"), board.data.find(b"lead-map-panel"))
        self.assertIn(b'class="job-row link-row" role="listitem" data-job-id="', board.data)
        self.assertIn(b'class="job-service-chip"', board.data)
        self.assertIn(b'/static/vendor/tabler-icons/wash.svg', board.data)
        self.assertIn(b"row-cue", board.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=50"', board.data)
        self.assertIn(b'id="lead-search" name="q" type="search" enterkeyhint="search"', board.data)
        self.assertIn(b'maxlength="80"', board.data)
        self.assertIn(b'for="lead-sort"', board.data)
        self.assertIn(b'id="lead-sort" name="sort"', board.data)
        self.assertIn(b'role="region"', board.data)
        self.assertIn(b'aria-describedby="lead-map-status"', board.data)
        self.assertIn(b'id="lead-map-loading"', board.data)
        self.assertIn(b'id="lead-map-status" class="sr-only" aria-live="polite"', board.data)
        self.assertIn(b"Map loading. Job list is ready.", board.data)

        outdoor_board = self.client.get("/leads?family=outdoor-yard")
        self.assertEqual(outdoor_board.status_code, 200)
        self.assertIn(b'name="family" value="outdoor-yard"', outdoor_board.data)
        self.assertIn(b'for="lead-service"', outdoor_board.data)
        self.assertIn(b'id="lead-service" name="service" data-market-service', outdoor_board.data)
        self.assertIn(b'value="pressure-washing"', outdoor_board.data)
        self.assertIn(b"Power wash townhouse front steps", outdoor_board.data)
        self.assertIn(b"Replace damaged fence panel", outdoor_board.data)
        self.assertNotIn(b"Office suite touch-up painting", outdoor_board.data)
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=50&amp;family=outdoor-yard"',
            outdoor_board.data,
        )

        pressure_board = self.client.get(
            "/leads?family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(pressure_board.status_code, 200)
        self.assertIn(b'value="pressure-washing" selected', pressure_board.data)
        self.assertIn(b' name="saved_service_slug" value="pressure-washing"', pressure_board.data)
        self.assertIn(b"Power wash townhouse front steps", pressure_board.data)
        self.assertNotIn(b"Replace damaged fence panel", pressure_board.data)
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=50&amp;family=outdoor-yard&amp;service=pressure-washing"',
            pressure_board.data,
        )

        sent_empty = self.client.get("/leads?view=sent")
        self.assertEqual(sent_empty.status_code, 200)
        self.assertIn(b"No bids sent yet", sent_empty.data)
        self.assertIn(b"Show all leads", sent_empty.data)
        self.assertNotIn(b"Clear filters", sent_empty.data)

        response = self.client.get("/leads?category=Painting&q=Nowhere")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No leads match this search", response.data)
        self.assertIn(b"Clear filters", response.data)
        self.assertNotIn(b"Office suite touch-up painting", response.data)

        self.assertIn(b"category=Painting", response.data)
        self.assertIn(b"q=Nowhere", response.data)

        soonest_board = self.client.get("/leads?sort=soonest")
        self.assertEqual(soonest_board.status_code, 200)
        self.assertIn(b'value="soonest" selected', soonest_board.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=50&amp;sort=soonest"', soonest_board.data)
        self.assertLess(
            soonest_board.data.find(b"Power wash townhouse front steps"),
            soonest_board.data.find(b"Office suite touch-up painting"),
        )

        sent_board = self.client.get("/leads?view=sent&sort=soonest")
        self.assertEqual(sent_board.status_code, 200)
        self.assertIn(b"sort=soonest", sent_board.data)
        self.assertIn(b"view=sent", sent_board.data)

        long_query = "A" * 120
        capped = self.client.get(f"/leads?q={long_query}")
        self.assertEqual(capped.status_code, 200)
        self.assertIn(f'value="{"A" * 80}"'.encode("ascii"), capped.data)
        self.assertNotIn(long_query.encode("ascii"), capped.data)

    def test_task_filtered_lead_intent_survives_sign_in(self):
        gated = self.client.get(
            "/leads?family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(gated.status_code, 302)
        self.assertEqual(
            gated.headers["Location"],
            "/login?next=/leads?family%3Doutdoor-yard%26service%3Dpressure-washing",
        )

        login = self.client.get(gated.headers["Location"])
        self.assertEqual(login.status_code, 200)
        self.assertIn(b'id="login-service"', login.data)
        self.assertIn(b'value="pressure-washing" selected', login.data)
        self.assertIn(
            b'name="next" value="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            login.data,
        )

        returned = self.client.post(
            gated.headers["Location"],
            data={
                "email": "contractor@workdoe.local",
                "password": "workdoe-contractor",
            },
            follow_redirects=True,
        )
        self.assertEqual(returned.status_code, 200)
        self.assertEqual(returned.request.path, "/leads")
        self.assertEqual(returned.request.args.get("family"), "outdoor-yard")
        self.assertEqual(returned.request.args.get("service"), "pressure-washing")
        self.assertIn(b"Power wash townhouse front steps", returned.data)
        self.assertNotIn(b"Replace damaged fence panel", returned.data)

        self.logout()
        first_time = self.client.post(
            gated.headers["Location"],
            data={
                "email": "new-filtered-contractor@example.com",
                "auth_action": "code",
            },
        )
        self.assertEqual(first_time.status_code, 302)
        self.assertIn("/create-account?intent=find-work", first_time.headers["Location"])
        self.assertIn("email=new-filtered-contractor@example.com", first_time.headers["Location"])
        self.assertIn("next=/leads", first_time.headers["Location"])
        self.assertIn("family%3Doutdoor-yard", first_time.headers["Location"])
        self.assertIn("service%3Dpressure-washing", first_time.headers["Location"])

        start_page = self.client.get(first_time.headers["Location"])
        self.assertEqual(start_page.status_code, 200)
        self.assertIn(b'value="find-work" checked', start_page.data)
        self.assertIn(b'value="pressure-washing" selected', start_page.data)
        self.assertIn(
            b'name="next" value="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            start_page.data,
        )

        code_page = self.client.post(
            first_time.headers["Location"],
            data={
                "intent": "find-work",
                "next": "/leads?family=outdoor-yard&service=pressure-washing",
                "email": "new-filtered-contractor@example.com",
                "display_name": "New Filtered Contractor",
                "company_name": "",
            },
            follow_redirects=True,
        )
        code_match = re.search(rb"<strong>([0-9]{6})</strong>", code_page.data)
        self.assertIsNotNone(code_match)
        new_account = self.client.post(
            "/start/verify",
            data={"code": code_match.group(1).decode("ascii")},
            follow_redirects=True,
        )
        self.assertEqual(new_account.status_code, 200)
        self.assertEqual(new_account.request.path, "/leads")
        self.assertEqual(new_account.request.args.get("family"), "outdoor-yard")
        self.assertEqual(new_account.request.args.get("service"), "pressure-washing")
        self.assertIn(b"Power wash townhouse front steps", new_account.data)

    def test_login_and_start_show_live_jobs_map(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b'title="Workdoe home"', home.data)
        self.assertIn(b"brand-home-button", home.data)
        self.assertIn(b"Open projects near you", home.data)
        self.assertIn(b'href="/post-project">Post project</a>', home.data)
        self.assertIn(b'>Find work</a>', home.data)
        self.assertIn(b"Approximate DMV job map", home.data)
        self.assertIn(b"compact-filter", home.data)
        self.assertEqual(home.data.count(b'class="service-family-filter-link'), 7)
        self.assertIn(b'class="home-family-picker"', home.data)
        self.assertIn(b"Yard &amp; landscaping", home.data)
        self.assertLess(
            home.data.find(b'class="home-family-picker"'),
            home.data.find(b'class="home-board priority-board"'),
        )
        self.assertIn(b'/static/vendor/tabler-icons/trees.svg', home.data)
        self.assertIn(b'role="search" aria-label="Filter open jobs"', home.data)
        self.assertIn(b'aria-controls="home-open-job-results lead-map"', home.data)
        self.assertNotIn(b'id="home-service"', home.data)
        self.assertIn(b'id="home-open-jobs" class="job-list"', home.data)
        self.assertIn(b'for="home-search"', home.data)
        self.assertIn(b'name="q" type="search" id="home-search" enterkeyhint="search"', home.data)
        self.assertIn(b'maxlength="80"', home.data)
        self.assertIn(b'for="home-sort"', home.data)
        self.assertIn(b'name="sort" id="home-sort"', home.data)
        self.assertIn(b'role="region"', home.data)
        self.assertIn(b'aria-describedby="lead-map-status"', home.data)
        self.assertIn(b'id="lead-map-loading"', home.data)
        self.assertIn(b'id="lead-map-status" class="sr-only" aria-live="polite"', home.data)
        self.assertIn(b"Map loading. Job list is ready.", home.data)

        selected_lane = self.client.get("/?family=outdoor-yard")
        self.assertEqual(selected_lane.status_code, 200)
        self.assertIn(b'class="home-lane-action"', selected_lane.data)
        self.assertIn(b"Lane selected", selected_lane.data)
        self.assertIn(b'href="/post-project?family=outdoor-yard"', selected_lane.data)
        self.assertIn(b"Post in this lane", selected_lane.data)
        self.assertIn(b'for="home-service"', selected_lane.data)
        self.assertIn(b'name="service" id="home-service"', selected_lane.data)
        self.assertIn(b'value="lawn-mowing"', selected_lane.data)
        self.assertIn(b'value="pressure-washing"', selected_lane.data)
        self.assertNotIn(b'value="house-cleaning"', selected_lane.data)

        selected_task = self.client.get(
            "/?family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(selected_task.status_code, 200)
        self.assertIn(b'value="pressure-washing" selected', selected_task.data)
        self.assertIn(b"Power wash townhouse front steps", selected_task.data)
        self.assertNotIn(b"Replace damaged fence panel", selected_task.data)
        self.assertIn(b"Post this task", selected_task.data)
        self.assertIn(
            b'href="/post-project?family=outdoor-yard&amp;service=pressure-washing"',
            selected_task.data,
        )
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=8&amp;family=outdoor-yard&amp;service=pressure-washing&amp;target=login"',
            selected_task.data,
        )

        task_only = self.client.get("/?service=pressure-washing")
        self.assertEqual(task_only.status_code, 200)
        self.assertIn(b"Yard &amp; landscaping", task_only.data)
        self.assertIn(b'value="pressure-washing" selected', task_only.data)

        lane_draft = self.client.get(
            "/post-project?family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(lane_draft.status_code, 200)
        self.assertIn(b'data-project-initial-step="3"', lane_draft.data)
        self.assertIn(
            b'value="outdoor-yard" data-group-name="Yard &amp; landscaping"',
            lane_draft.data,
        )
        self.assertIn(b"checked", lane_draft.data)
        self.assertIn(
            b'name="service_slug" required', lane_draft.data
        )
        self.assertIn(b'value="pressure-washing"', lane_draft.data)
        self.assertIn(b"/api/jobs/open", home.data)
        self.assertIn(b"limit=8", home.data)
        self.assertIn(b"target=login", home.data)
        self.assertIn(b'id="map-jobs-data" type="application/json"', home.data)
        self.assertNotIn(b"window.WORKDOE_JOBS", home.data)
        self.assertIn(b"/static/vendor/leaflet/leaflet.css", home.data)
        self.assertIn(b"/static/vendor/leaflet/leaflet.js", home.data)
        self.assertNotIn(b"unpkg.com", home.data)
        self.assertIn(b'aria-controls="home-open-job-results lead-map"', home.data)
        self.assertIn(b'id="home-open-job-results" class="job-result-list" aria-label="Open job results" role="list"', home.data)
        self.assertIn(b'class="job-row link-row compact-lead-row" role="listitem"', home.data)
        self.assertIn(b'class="job-service-chip"', home.data)
        self.assertIn(b'/static/vendor/tabler-icons/wash.svg', home.data)
        self.assertIn(b'data-job-id="', home.data)
        self.assertIn(b'aria-label="Sign in for Power wash townhouse front steps"', home.data)
        self.assertNotIn(b"job-summary", home.data)
        self.assertNotIn(b"Small office needs evening touch-up painting", home.data)
        self.assertIn(b"Target", home.data)
        self.assertIn(b"near DC, Maryland, and Virginia", home.data)

        outdoor_home = self.client.get("/?family=outdoor-yard")
        self.assertEqual(outdoor_home.status_code, 200)
        self.assertIn(b'name="family" value="outdoor-yard"', outdoor_home.data)
        self.assertIn(b"Power wash townhouse front steps", outdoor_home.data)
        self.assertIn(b"Replace damaged fence panel", outdoor_home.data)
        self.assertNotIn(b"Office suite touch-up painting", outdoor_home.data)
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=8&amp;family=outdoor-yard&amp;target=login"',
            outdoor_home.data,
        )

        filtered_home = self.client.get("/?category=Painting&q=Arlington")
        self.assertEqual(filtered_home.status_code, 200)
        self.assertIn(b"Office suite touch-up painting", filtered_home.data)
        self.assertNotIn(b"Replace damaged fence panel", filtered_home.data)
        self.assertIn(b"category=Painting", filtered_home.data)

        soonest_home = self.client.get("/?sort=soonest")
        self.assertEqual(soonest_home.status_code, 200)
        self.assertIn(b'value="soonest" selected', soonest_home.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=8&amp;sort=soonest&amp;target=login"', soonest_home.data)
        self.assertLess(
            soonest_home.data.find(b"Power wash townhouse front steps"),
            soonest_home.data.find(b"Office suite touch-up painting"),
        )

        empty_home = self.client.get("/?category=Painting&q=Nowhere")
        self.assertEqual(empty_home.status_code, 200)
        self.assertIn(b"No matches", empty_home.data)
        self.assertIn(b"Clear filters", empty_home.data)
        self.assertNotIn(b"Office suite touch-up painting", empty_home.data)

        login = self.client.get("/login")
        self.assertEqual(login.status_code, 200)
        self.assertIn(b"lead-map", login.data)
        self.assertIn(b"Map loading. Job list is ready.", login.data)
        self.assertIn(b'aria-live="polite"', login.data)
        self.assertIn(b"Area scan // DMV", login.data)
        self.assertIn(b'<nav class="entry-shortcuts" aria-label="Sign in shortcuts">', login.data)
        self.assertIn(b'href="#live-jobs">Open projects</a>', login.data)
        self.assertIn(b'id="live-jobs" class="login-live-panel" tabindex="-1"', login.data)
        self.assertIn(b'class="entry-shortcut" href="#signin">Sign in</a>', login.data)
        self.assertIn(b"open projects", login.data)
        self.assertIn(b"compact-filter entry-filter", login.data)
        self.assertIn(b'role="search" aria-label="Filter open jobs before signing in"', login.data)
        self.assertIn(b'aria-controls="login-open-jobs lead-map"', login.data)
        self.assertIn(b'id="login-open-jobs" class="job-list login-job-list" aria-label="Open jobs at login" role="list"', login.data)
        self.assertNotIn(b'id="login-service"', login.data)
        self.assertIn(b'for="login-search"', login.data)
        self.assertIn(b'name="q" type="search" id="login-search" enterkeyhint="search"', login.data)
        self.assertIn(b'maxlength="80"', login.data)
        self.assertIn(b'for="login-sort"', login.data)
        self.assertIn(b'name="sort" id="login-sort"', login.data)
        self.assertIn(b'id="map-jobs-data" type="application/json"', login.data)
        self.assertNotIn(b"window.WORKDOE_JOBS", login.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=6&amp;target=login"', login.data)
        self.assertIn(b'class="job-row link-row compact-lead-row"', login.data)
        self.assertIn(b'role="listitem"', login.data)
        self.assertIn(b'data-job-id="', login.data)
        self.assertIn(b'aria-label="Sign in lead Power wash townhouse front steps"', login.data)
        self.assertIn(b'href="/login?next=/jobs/', login.data)
        self.assertIn(b"Email code", login.data)
        self.assertIn(b'for="signin-email"', login.data)
        self.assertIn(
            b'name="email" type="email" id="signin-email" inputmode="email" autocomplete="email" autocapitalize="off" autocorrect="off" spellcheck="false" required',
            login.data,
        )
        self.assertIn(b"No password needed.", login.data)
        self.assertIn(b"Admin/demo password", login.data)
        self.assertIn(b'for="signin-password"', login.data)
        self.assertIn(b'name="password" type="password" id="signin-password"', login.data)
        self.assertIn(b'name="auth_action" value="password"', login.data)
        self.assertNotIn(b"Email one-time code", login.data)
        self.assertNotIn(b"Small office needs evening touch-up painting", login.data)

        task_login = self.client.get(
            "/login?family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(task_login.status_code, 200)
        self.assertIn(b'id="login-service"', task_login.data)
        self.assertIn(b'value="pressure-washing" selected', task_login.data)
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=6&amp;family=outdoor-yard&amp;service=pressure-washing&amp;target=login"',
            task_login.data,
        )

        filtered_login = self.client.get("/login?category=Painting&q=Arlington")
        self.assertEqual(filtered_login.status_code, 200)
        self.assertIn(b"Office suite touch-up painting", filtered_login.data)
        self.assertNotIn(b"Replace damaged fence panel", filtered_login.data)
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=6&amp;category=Painting&amp;q=Arlington&amp;target=login"',
            filtered_login.data,
        )

        soonest_login = self.client.get("/login?sort=soonest")
        self.assertEqual(soonest_login.status_code, 200)
        self.assertIn(b'value="soonest" selected', soonest_login.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=6&amp;sort=soonest&amp;target=login"', soonest_login.data)
        self.assertLess(
            soonest_login.data.find(b"Power wash townhouse front steps"),
            soonest_login.data.find(b"Office suite touch-up painting"),
        )

        empty_login = self.client.get("/login?category=Painting&q=Nowhere")
        self.assertEqual(empty_login.status_code, 200)
        self.assertIn(b"No matches", empty_login.data)
        self.assertIn(b"Clear filters", empty_login.data)
        self.assertNotIn(b"Office suite touch-up painting", empty_login.data)

        selected_login_job = self.one(
            "SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC LIMIT 1"
        )
        selected_login = self.client.get(f"/login?next=/jobs/{selected_login_job['id']}")
        self.assertEqual(selected_login.status_code, 200)
        self.assertIn(b"Selected", selected_login.data)
        self.assertIn(b"is-selected", selected_login.data)
        self.assertIn(
            f'aria-label="Selected lead {selected_login_job["title"]}"'.encode(),
            selected_login.data,
        )
        self.assertIn(
            f'name="next" value="/jobs/{selected_login_job["id"]}"'.encode("ascii"),
            selected_login.data,
        )
        self.assertIn(selected_login_job["title"].encode("utf-8"), selected_login.data)

        selected_filtered_login = self.client.get(
            f"/login?next=/jobs/{selected_login_job['id']}&category=Painting&q=Arlington"
        )
        self.assertEqual(selected_filtered_login.status_code, 200)
        self.assertIn(
            f'name="next" value="/jobs/{selected_login_job["id"]}"'.encode("ascii"),
            selected_filtered_login.data,
        )
        self.assertIn(b"category=Painting", selected_filtered_login.data)

        start = self.client.get("/start")
        self.assertEqual(start.status_code, 200)
        self.assertIn(b"lead-map", start.data)
        self.assertIn(b"Map loading. Job list is ready.", start.data)
        self.assertIn(b'aria-live="polite"', start.data)
        self.assertIn(b"What brings you here?", start.data)
        self.assertIn(b'id="live-jobs" class="login-live-panel start-live-panel" tabindex="-1"', start.data)
        self.assertIn(b'class="entry-shortcut" href="#start-account">Join</a>', start.data)
        self.assertIn(b'id="start-account" class="form-panel login-form-panel start-form-panel"', start.data)
        self.assertIn(b'<nav class="entry-shortcuts" aria-label="Join shortcuts">', start.data)
        self.assertIn(b'value="post-job" checked', start.data)
        self.assertIn(b'value="find-work"', start.data)
        self.assertIn(b"compact-filter entry-filter", start.data)
        self.assertIn(b'role="search" aria-label="Filter open jobs while starting"', start.data)
        self.assertIn(b'aria-controls="start-open-jobs lead-map"', start.data)
        self.assertIn(b'id="start-open-jobs" class="job-list login-job-list" aria-label="Open jobs while starting account" role="list"', start.data)
        self.assertNotIn(b'id="start-service"', start.data)
        self.assertIn(b'for="start-search"', start.data)
        self.assertIn(b'name="q" type="search" id="start-search" enterkeyhint="search"', start.data)
        self.assertIn(b'maxlength="80"', start.data)
        self.assertIn(b'for="start-sort"', start.data)
        self.assertIn(b'name="sort" id="start-sort"', start.data)
        self.assertIn(b"<h2>Join Workdoe</h2>", start.data)
        self.assertIn(b"<strong>Consumer</strong>", start.data)
        self.assertIn(b"<strong>Contractor</strong>", start.data)
        self.assertIn(b"Email code", start.data)
        self.assertIn(b'for="start-email"', start.data)
        self.assertIn(
            b'name="email" type="email" id="start-email" inputmode="email" autocomplete="email" autocapitalize="off" autocorrect="off" spellcheck="false"',
            start.data,
        )
        self.assertNotIn(b"Same site", start.data)
        self.assertIn(b'for="start-display-name"', start.data)
        self.assertIn(b'name="display_name" id="start-display-name" autocomplete="name"', start.data)
        self.assertIn(b'aria-describedby="start-name-help"', start.data)
        self.assertIn(b'for="start-company-name"', start.data)
        self.assertIn(b'name="company_name" id="start-company-name" autocomplete="organization"', start.data)
        self.assertIn(b"New accounts only.", start.data)
        self.assertNotIn(b'name="display_name" autocomplete="name" required', start.data)
        self.assertIn(b"Email code", start.data)
        self.assertNotIn(b"Use password instead", start.data)
        self.assertNotIn(b"Use demo password", start.data)
        self.assertIn(b"open projects", start.data)
        self.assertIn(b'id="map-jobs-data" type="application/json"', start.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=6"', start.data)
        self.assertNotIn(b"window.WORKDOE_JOBS", start.data)
        self.assertNotIn(b"Three steps", start.data)
        self.assertIn(b'class="job-row link-row compact-lead-row"', start.data)
        self.assertIn(b'role="listitem"', start.data)
        self.assertIn(b'data-job-id="', start.data)
        self.assertIn(b'aria-label="Find work lead Power wash townhouse front steps"', start.data)
        self.assertIn(b"/start?intent=find-work&amp;job_id=", start.data)
        self.assertNotIn(b"Small office needs evening touch-up painting", start.data)

        create_account = self.client.get("/create-account")
        self.assertEqual(create_account.status_code, 200)
        self.assertIn(b"<title>Create Account - Workdoe</title>", create_account.data)
        self.assertIn(b"Create your Workdoe account", create_account.data)
        self.assertIn(b'class="entry-shortcut" href="#start-account">Create account</a>', create_account.data)
        self.assertIn(b'<nav class="entry-shortcuts" aria-label="Create account shortcuts">', create_account.data)
        self.assertIn(b'id="start-account" class="form-panel login-form-panel start-form-panel" method="post"', create_account.data)
        self.assertIn(b"/create-account?intent=find-work&amp;job_id=", create_account.data)

        find_work_start = self.client.get("/start?intent=find-work")
        self.assertEqual(find_work_start.status_code, 200)
        self.assertIn(b'value="find-work" checked', find_work_start.data)

        task_start = self.client.get(
            "/start?intent=find-work&family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(task_start.status_code, 200)
        self.assertIn(b'id="start-service"', task_start.data)
        self.assertIn(b'value="pressure-washing" selected', task_start.data)

        filtered_start = self.client.get("/start?intent=find-work&category=Painting&q=Arlington")
        self.assertEqual(filtered_start.status_code, 200)
        self.assertIn(b'value="find-work" checked', filtered_start.data)
        self.assertIn(b"Office suite touch-up painting", filtered_start.data)
        self.assertNotIn(b"Replace damaged fence panel", filtered_start.data)
        self.assertIn(
            b'data-jobs-api="/api/jobs/open?limit=6&amp;category=Painting&amp;q=Arlington"',
            filtered_start.data,
        )

        soonest_start = self.client.get("/start?intent=find-work&sort=soonest")
        self.assertEqual(soonest_start.status_code, 200)
        self.assertIn(b'value="soonest" selected', soonest_start.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=6&amp;sort=soonest"', soonest_start.data)
        self.assertLess(
            soonest_start.data.find(b"Power wash townhouse front steps"),
            soonest_start.data.find(b"Office suite touch-up painting"),
        )

        empty_start = self.client.get("/start?intent=find-work&category=Painting&q=Nowhere")
        self.assertEqual(empty_start.status_code, 200)
        self.assertIn(b"No matches", empty_start.data)
        self.assertIn(b"Clear filters", empty_start.data)
        self.assertNotIn(b"Office suite touch-up painting", empty_start.data)

        selected_job = self.one("SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC LIMIT 1")
        selected_start = self.client.get(f"/start?intent=find-work&job_id={selected_job['id']}")
        self.assertEqual(selected_start.status_code, 200)
        self.assertIn(b"Selected", selected_start.data)
        self.assertIn(
            f'aria-label="Selected lead {selected_job["title"]}"'.encode(),
            selected_start.data,
        )
        self.assertIn(f'name="job_id" value="{selected_job["id"]}"'.encode("ascii"), selected_start.data)
        self.assertIn(selected_job["title"].encode("utf-8"), selected_start.data)

    def test_open_jobs_api_feeds_public_map_without_exact_addresses(self):
        response = self.client.get("/api/jobs/open")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

        payload = response.get_json()
        self.assertGreaterEqual(payload["count"], 3)
        first_job = payload["jobs"][0]
        self.assertIn("lat", first_job)
        self.assertIn("lng", first_job)
        self.assertIn("url", first_job)
        self.assertEqual(first_job["action_label"], "Start")
        self.assertRegex(first_job["url"], r"^/create-account\?intent=find-work&job_id=\d+$")
        self.assertNotIn("zip_code", first_job)
        self.assertNotIn("description", first_job)

        project_form = self.client.get("/post-project")
        self.assertIn(
            b"Do not include an exact street address, email, or phone number.",
            project_form.data,
        )

        sign_in_response = self.client.get("/api/jobs/open?target=login")
        sign_in_payload = sign_in_response.get_json()
        self.assertEqual(sign_in_payload["jobs"][0]["action_label"], "Sign in")
        self.assertTrue(sign_in_payload["jobs"][0]["url"].startswith("/login?next=/jobs/"))

        limited = self.client.get("/api/jobs/open?limit=2&target=login")
        limited_payload = limited.get_json()
        self.assertEqual(limited_payload["count"], 2)
        self.assertEqual(limited_payload["jobs"][0]["action_label"], "Sign in")

        filtered = self.client.get("/api/jobs/open?category=Painting&q=Arlington")
        self.assertEqual(filtered.status_code, 200)
        filtered_payload = filtered.get_json()
        self.assertEqual(filtered_payload["count"], 1)
        self.assertEqual(filtered_payload["jobs"][0]["category"], "Painting")
        self.assertEqual(filtered_payload["jobs"][0]["city"], "Arlington")

        service_filtered = self.client.get(
            "/api/jobs/open?service=pressure-washing"
        )
        self.assertEqual(service_filtered.status_code, 200)
        service_payload = service_filtered.get_json()
        self.assertEqual(service_payload["filters"]["family"], "outdoor-yard")
        self.assertEqual(
            service_payload["filters"]["service"], "pressure-washing"
        )
        self.assertEqual(service_payload["count"], 1)
        self.assertEqual(
            service_payload["jobs"][0]["service_name"], "Pressure washing"
        )

        empty_filtered = self.client.get("/api/jobs/open?category=Painting&q=Nowhere")
        self.assertEqual(empty_filtered.status_code, 200)
        self.assertEqual(empty_filtered.get_json()["count"], 0)

        capped = self.client.get(f"/api/jobs/open?q={'A' * 120}")
        self.assertEqual(capped.status_code, 200)
        self.assertEqual(capped.get_json()["filters"]["q"], "A" * 80)

        soonest = self.client.get("/api/jobs/open?sort=soonest").get_json()
        self.assertEqual(soonest["filters"]["sort"], "soonest")
        self.assertEqual(soonest["jobs"][0]["title"], "Power wash townhouse front steps")

        city = self.client.get("/api/jobs/open?sort=city").get_json()
        self.assertEqual(city["filters"]["sort"], "city")
        self.assertEqual(city["jobs"][0]["city"], "Arlington")

        invalid_sort = self.client.get("/api/jobs/open?sort=random").get_json()
        self.assertEqual(invalid_sort["filters"]["sort"], "newest")

    def test_open_jobs_api_validates_bounds_and_pages_with_opaque_cursors(self):
        bounded = self.client.get(
            "/api/jobs/open?north=38.9&south=38.87&east=-77.08&west=-77.12"
        )
        self.assertEqual(bounded.status_code, 200)
        bounded_payload = bounded.get_json()
        self.assertEqual(bounded_payload["result_count"], 1)
        self.assertEqual(bounded_payload["jobs"][0]["city"], "Arlington")
        self.assertEqual(
            bounded_payload["viewport"],
            {"north": 38.9, "south": 38.87, "east": -77.08, "west": -77.12},
        )
        for private_key in ("zip_code", "description", "address", "email", "phone"):
            self.assertNotIn(private_key, bounded_payload["jobs"][0])

        first_page = self.client.get("/api/jobs/open?limit=1").get_json()
        self.assertEqual(first_page["result_count"], 1)
        self.assertTrue(first_page["truncated"])
        self.assertTrue(first_page["next_cursor"])
        second_page = self.client.get(
            f'/api/jobs/open?limit=1&cursor={first_page["next_cursor"]}'
        ).get_json()
        self.assertNotEqual(first_page["jobs"][0]["id"], second_page["jobs"][0]["id"])

        for query in (
            "north=39",
            "north=outside&south=38&east=-76&west=-77",
            "north=10&south=9&east=10&west=9",
            "cursor=not-a-cursor",
        ):
            with self.subTest(query=query):
                invalid = self.client.get(f"/api/jobs/open?{query}")
                self.assertEqual(invalid.status_code, 400)
                self.assertFalse(invalid.get_json()["ok"])

    def test_map_script_announces_results_and_active_rows(self):
        script = (ROOT / "workdoe" / "static" / "map.js").read_text()
        self.assertIn("setMapStatus", script)
        self.assertIn("updateResultStatus", script)
        self.assertIn("announceActiveJob", script)
        self.assertIn("markerLabel", script)
        self.assertIn("window.L.markerClusterGroup", script)
        self.assertIn("alt: label", script)
        self.assertIn("title: label", script)
        self.assertIn('setAttribute("aria-label", label)', script)
        self.assertIn("is-map-active", script)
        self.assertIn("openPopup", script)
        self.assertIn("moveJobFocus", script)
        self.assertIn('aria-keyshortcuts", "ArrowUp ArrowDown Home End"', script)
        self.assertIn('event.key === "ArrowDown"', script)
        self.assertIn('event.key === "ArrowUp"', script)
        self.assertIn('event.key === "Home"', script)
        self.assertIn('event.key === "End"', script)
        self.assertIn("preventScroll: false", script)
        self.assertIn("No matching projects", script)
        self.assertIn("Search this area", script)
        self.assertIn("map.getBounds()", script)
        self.assertIn("window.history.replaceState", script)
        self.assertIn('setOptionalParam(url, "job_id", activeJobId)', script)
        self.assertIn("https://tile.openstreetmap.org/{z}/{x}/{y}.png", script)
        self.assertIn("if (!detailContent)", script)

    def test_local_password_reset_token_flow(self):
        reset_form = self.client.get("/forgot-password")
        self.assertEqual(reset_form.status_code, 200)
        self.assertIn(
            b'name="email" type="email" inputmode="email" autocomplete="email" autocapitalize="off" autocorrect="off" spellcheck="false" required',
            reset_form.data,
        )

        response = self.client.post(
            "/forgot-password",
            data={"email": "client@workdoe.local"},
            follow_redirects=True,
        )
        html = response.data.decode("utf-8")
        match = re.search(r'href="(/reset-password/[^"]+)"', html)
        self.assertIsNotNone(match)

        reset_response = self.client.post(
            match.group(1),
            data={"password": "new-client-pass"},
            follow_redirects=True,
        )
        self.assertIn(b"Password updated", reset_response.data)

        login_response = self.login("client@workdoe.local", "new-client-pass")
        self.assertIn(b"Your projects", login_response.data)
        self.assertIn(b'class="job-row link-row"', login_response.data)
        self.assertIn(b"row-cue", login_response.data)

    def test_start_flow_creates_client_and_lands_on_job_form(self):
        missing_name = self.client.post(
            "/create-account",
            data={
                "intent": "post-job",
                "email": "new-client@example.com",
                "company_name": "New Client Household",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Add your name to create a Workdoe workspace.", missing_name.data)
        self.assertIn(b'value="new-client@example.com"', missing_name.data)
        self.assertIn(b'value="New Client Household"', missing_name.data)

        start = self.client.post(
            "/create-account",
            data={
                "intent": "post-job",
                "email": "new-client@example.com",
                "display_name": "New Client",
                "company_name": "New Client Household",
            },
            follow_redirects=True,
        )
        html = start.data.decode("utf-8")
        match = re.search(r"<strong>([0-9]{6})</strong>", html)
        self.assertIsNotNone(match)
        self.assertIn('class="form-checklist auth-checklist verify-checklist"', html)
        self.assertIn('id="verify-code" name="code"', html)
        self.assertIn('autocomplete="one-time-code"', html)
        self.assertIn('enterkeyhint="done"', html)
        self.assertIn('autocapitalize="off"', html)
        self.assertIn('autocorrect="off"', html)
        self.assertIn('spellcheck="false"', html)
        self.assertIn('pattern="[0-9 -]{6,12}"', html)
        self.assertIn('maxlength="12"', html)
        self.assertNotIn('pattern="[0-9]{6}" maxlength="6"', html)
        self.assertIn("autofocus", html)

        short_code = self.client.post(
            "/start/verify",
            data={"code": "123"},
            follow_redirects=True,
        )
        self.assertIn(b"Enter the 6-digit code.", short_code.data)
        self.assertIn(b'id="verify-code-error"', short_code.data)
        self.assertIn(b'aria-invalid="true"', short_code.data)

        wrong_code = self.client.post(
            "/start/verify",
            data={"code": "000000"},
            follow_redirects=True,
        )
        self.assertIn(b"That code did not match.", wrong_code.data)
        self.assertIn(b'id="verify-code-error"', wrong_code.data)

        verified = self.client.post(
            "/start/verify",
            data={"code": f"{match.group(1)[:3]}-{match.group(1)[3:]}"},
            follow_redirects=True,
        )
        self.assertIn(b"Post a project", verified.data)
        user = self.one("SELECT * FROM users WHERE email = ?", ("new-client@example.com",))
        self.assertEqual(user["role"], "client")
        used_code = self.one(
            "SELECT * FROM login_codes WHERE email = ? ORDER BY id DESC LIMIT 1",
            ("new-client@example.com",),
        )
        self.assertIsNotNone(used_code["used_at"])
        self.client.post("/logout")
        with self.client.session_transaction() as session_data:
            session_data["start_code_id"] = used_code["id"]
            session_data["local_login_code"] = match.group(1)
        replay = self.client.post(
            "/start/verify",
            data={"code": match.group(1)},
            follow_redirects=True,
        )
        self.assertIn(b"one-time code expired", replay.data)

    def test_post_project_entry_verifies_consumer_and_opens_project_form(self):
        drafted = self.client.post(
            "/post-project?family=outdoor-yard",
            data={
                "title": "Wash the front walk",
                "category": "Power washing",
                "service_group_slug": "outdoor-yard",
                "service_slug": "pressure-washing",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "desired_date": "2026-09-10",
                "budget_min": "450",
                "budget_max": "700",
                "description": "Clean the front walk and steps before a family gathering.",
                "scope_surface": "concrete",
                "scope_area_size": "small",
                "scope_water_access": "yes",
                "scope_height": "ground",
            },
            follow_redirects=True,
        )
        self.assertEqual(drafted.request.path, "/create-account")
        self.assertIn(b"Draft saved", drafted.data)
        self.assertNotIn(b'name="photos"', drafted.data)
        draft = self.one("SELECT * FROM job_drafts WHERE consumed_at IS NULL")
        self.assertEqual(draft["service_group_slug"], "outdoor-yard")
        self.assertEqual(draft["service_slug"], "pressure-washing")
        self.assertEqual(draft["budget_min"], 450)
        self.assertEqual(draft["budget_max"], 700)
        draft_scope = self.all(
            "SELECT question_key, answer_code FROM job_draft_scope_answers WHERE draft_id = ?",
            (draft["id"],),
        )
        self.assertEqual(len(draft_scope), 4)

        started = self.client.post(
            "/create-account?intent=post-job&draft=saved",
            data={
                "intent": "post-job",
                "email": "project-owner@example.com",
                "display_name": "Project Owner",
                "company_name": "Project Owner Household",
            },
            follow_redirects=True,
        )
        match = re.search(r"<strong>([0-9]{6})</strong>", started.data.decode("utf-8"))
        self.assertIsNotNone(match)

        verified = self.client.post(
            "/start/verify",
            data={"code": match.group(1)},
            follow_redirects=True,
        )
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.request.path, "/jobs/new")
        self.assertIn(b'<form class="form-grid" method="post"', verified.data)
        self.assertIn(b'aria-label="Post project"', verified.data)
        self.assertIn(b'value="Wash the front walk"', verified.data)
        self.assertIn(b'name="budget_min" type="number" value="450"', verified.data)
        self.assertIn(b'name="budget_max" type="number" value="700"', verified.data)
        self.assertIn(b'name="scope_surface"', verified.data)
        self.assertIn(b'value="concrete" selected', verified.data)

        posted = self.client.post(
            "/jobs/new",
            data={
                "title": "Wash the front walk",
                "category": "Power washing",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "desired_date": "2026-09-10",
                "budget_min": "450",
                "budget_max": "700",
                "description": "Clean the front walk and steps before a family gathering.",
                "scope_surface": "concrete",
                "scope_area_size": "small",
                "scope_water_access": "yes",
                "scope_height": "ground",
            },
            follow_redirects=True,
        )
        self.assertIn(b"$450-$700", posted.data)
        created = self.one("SELECT * FROM jobs WHERE title = ?", ("Wash the front walk",))
        self.assertEqual(created["budget_min"], 450)
        self.assertEqual(created["budget_max"], 700)
        created_scope = self.all(
            "SELECT question_key, answer_code FROM job_scope_answers WHERE job_id = ?",
            (created["id"],),
        )
        self.assertEqual(len(created_scope), 4)
        consumed = self.one("SELECT * FROM job_drafts WHERE id = ?", (draft["id"],))
        self.assertIsNotNone(consumed["consumed_at"])

    def test_project_budget_validation_and_permanent_account_roles(self):
        self.login("client@workdoe.local", "workdoe-client")
        invalid_budget = self.client.post(
            "/jobs/new",
            data={
                "title": "Paint the porch rail",
                "category": "Painting",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "budget_min": "900",
                "budget_max": "500",
                "description": "Prepare and repaint the porch rail with exterior paint.",
            },
        )
        self.assertIn(b"Make the budget maximum at least the minimum budget.", invalid_budget.data)
        self.logout()

        contractor_start = self.client.post(
            "/create-account",
            data={
                "intent": "post-job",
                "email": "contractor@workdoe.local",
                "display_name": "Ignored Client Name",
            },
            follow_redirects=True,
        )
        contractor_code = re.search(
            r"<strong>([0-9]{6})</strong>", contractor_start.data.decode("utf-8")
        )
        self.assertIsNotNone(contractor_code)
        contractor_verified = self.client.post(
            "/start/verify",
            data={"code": contractor_code.group(1)},
            follow_redirects=True,
        )
        self.assertEqual(contractor_verified.request.path, "/contractor/dashboard")
        contractor = self.one(
            "SELECT role FROM users WHERE email = ?", ("contractor@workdoe.local",)
        )
        self.assertEqual(contractor["role"], "contractor")
        self.assertEqual(self.client.get("/jobs/new").status_code, 403)

        self.logout()
        client_start = self.client.post(
            "/create-account",
            data={
                "intent": "find-work",
                "email": "client@workdoe.local",
                "display_name": "Ignored Contractor Name",
            },
            follow_redirects=True,
        )
        client_code = re.search(
            r"<strong>([0-9]{6})</strong>", client_start.data.decode("utf-8")
        )
        self.assertIsNotNone(client_code)
        client_verified = self.client.post(
            "/start/verify",
            data={"code": client_code.group(1)},
            follow_redirects=True,
        )
        self.assertEqual(client_verified.request.path, "/client/dashboard")
        consumer = self.one(
            "SELECT role FROM users WHERE email = ?", ("client@workdoe.local",)
        )
        self.assertEqual(consumer["role"], "client")
        self.assertEqual(self.client.get("/leads").status_code, 403)

    def test_legacy_signup_post_uses_one_time_code_instead_of_password_account(self):
        signup_get = self.client.get("/signup")
        self.assertEqual(signup_get.status_code, 302)
        self.assertEqual(signup_get.headers["Location"], "/create-account")
        signup_head = self.client.head("/signup")
        self.assertEqual(signup_head.status_code, 302)
        self.assertEqual(signup_head.headers["Location"], "/create-account")

        signup = self.client.post(
            "/signup",
            data={
                "role": "contractor",
                "email": "legacy-contractor@example.com",
                "display_name": "Legacy Contractor",
                "company_name": "Legacy Crew",
                "password": "legacy-password",
            },
            follow_redirects=True,
        )
        html = signup.data.decode("utf-8")
        match = re.search(r"<strong>([0-9]{6})</strong>", html)
        self.assertIsNotNone(match)
        self.assertIn("Use the one-time email code to finish starting.", html)
        self.assertIn("One-time code", html)
        self.assertNotIn("Create a Workdoe account", html)
        self.assertIsNone(
            self.one(
                "SELECT * FROM users WHERE email = ?",
                ("legacy-contractor@example.com",),
            )
        )

        verified = self.client.post(
            "/start/verify",
            data={"code": match.group(1)},
            follow_redirects=True,
        )
        self.assertIn(b"Work near you", verified.data)
        user = self.one(
            "SELECT * FROM users WHERE email = ?",
            ("legacy-contractor@example.com",),
        )
        self.assertEqual(user["role"], "contractor")

        self.logout()
        password_login = self.login(
            "legacy-contractor@example.com",
            "legacy-password",
        )
        self.assertIn(b"Email or password did not match.", password_login.data)
        self.assertNotIn(b"Work near you", password_login.data)

    def test_local_one_time_code_display_can_be_hidden(self):
        self.app.config["SHOW_LOCAL_LOGIN_CODE"] = False
        try:
            start = self.client.post(
                "/start",
                data={
                    "intent": "post-job",
                    "email": "hidden-code-client@example.com",
                    "display_name": "Hidden Code Client",
                    "company_name": "Hidden Code Household",
                },
                follow_redirects=True,
            )
            self.assertIn(b"One-time code", start.data)
            self.assertNotIn(b"Local prototype code", start.data)
            with self.client.session_transaction() as session_data:
                code = session_data["local_login_code"]
            verified = self.client.post(
                "/start/verify",
                data={"code": code},
                follow_redirects=True,
            )
            self.assertIn(b"Post a project", verified.data)
        finally:
            self.app.config["SHOW_LOCAL_LOGIN_CODE"] = True

    def test_job_form_constraints_and_error_value_preservation(self):
        self.login("client@workdoe.local", "workdoe-client")
        form = self.client.get("/jobs/new")
        self.assertEqual(form.status_code, 200)
        self.assertIn(b'class="form-grid" method="post" enctype="multipart/form-data" aria-label="Post a project"', form.data)
        self.assertIn(b'maxlength="90"', form.data)
        self.assertIn(b'pattern="[0-9]{5}"', form.data)
        self.assertIn(b'autocomplete="postal-code"', form.data)
        self.assertIn(b'autocapitalize="sentences"', form.data)
        self.assertIn(b'autocapitalize="words"', form.data)
        self.assertIn(b'enterkeyhint="next"', form.data)
        self.assertIn(b'enterkeyhint="done"', form.data)
        self.assertIn(b'spellcheck="false" list="job-city-options"', form.data)
        self.assertIn(b'minlength="20"', form.data)
        self.assertIn(b'aria-describedby="job-photos-help"', form.data)
        self.assertIn(b'aria-label="Post project"', form.data)
        self.assertIn(b"Approximate location stays public", form.data)

        invalid = self.client.post(
            "/jobs/new",
            data={
                "title": "  Patio refresh  ",
                "category": "Power washing",
                "city": "  Washington  ",
                "state": "DC",
                "zip_code": "20A0",
                "desired_date": "2020-01-01",
                "description": "Clean the patio before guests arrive.",
            },
            follow_redirects=True,
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Use a 5-digit DMV ZIP code.", invalid.data)
        self.assertIn(b"Choose today or a future desired date.", invalid.data)
        self.assertIn(b'id="job-form-errors"', invalid.data)
        self.assertIn(b'href="#job-zip-code"', invalid.data)
        self.assertIn(b'id="job-zip-code-error"', invalid.data)
        self.assertIn(b'aria-invalid="true"', invalid.data)
        self.assertIn(b'value="Patio refresh"', invalid.data)
        self.assertIn(b'value="Washington"', invalid.data)
        self.assertIn(b'value="200"', invalid.data)
        self.assertIn(b'value="2020-01-01"', invalid.data)

    def test_start_flow_opens_existing_contractor_without_username_or_password(self):
        selected_job = self.one("SELECT * FROM jobs WHERE status = 'open' ORDER BY created_at DESC LIMIT 1")
        start = self.client.post(
            "/start",
            data={
                "intent": "find-work",
                "job_id": str(selected_job["id"]),
                "email": "contractor@workdoe.local",
            },
            follow_redirects=True,
        )
        match = re.search(r"<strong>([0-9]{6})</strong>", start.data.decode("utf-8"))
        self.assertIsNotNone(match)

        verified = self.client.post(
            "/start/verify",
            data={"code": match.group(1)},
            follow_redirects=True,
        )
        self.assertEqual(verified.request.path, f"/jobs/{selected_job['id']}")
        self.assertIn(selected_job["title"].encode("utf-8"), verified.data)

    def test_report_redirects_stay_internal(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("contractor@workdoe.local", "workdoe-contractor")
        malformed = self.client.post(
            "/report",
            data={
                "target_type": "job",
                "target_id": "not-a-number",
                "reason": "Malformed report",
            },
            headers={"Referer": f"http://localhost/jobs/{job['id']}"},
        )
        self.assertEqual(malformed.status_code, 302)
        self.assertEqual(malformed.headers["Location"], f"/jobs/{job['id']}")
        malformed_report = self.one(
            "SELECT * FROM reports WHERE reason = ?",
            ("Malformed report",),
        )
        self.assertIsNone(malformed_report)

        oversized_reason = "R" * 501
        oversized = self.client.post(
            "/report",
            data={
                "target_type": "job",
                "target_id": str(job["id"]),
                "reason": oversized_reason,
            },
            headers={"Referer": f"http://localhost/jobs/{job['id']}"},
        )
        self.assertEqual(oversized.status_code, 302)
        self.assertEqual(oversized.headers["Location"], f"/jobs/{job['id']}")
        oversized_report = self.one(
            "SELECT * FROM reports WHERE reason = ?",
            (oversized_reason,),
        )
        self.assertIsNone(oversized_report)

        ghost = self.client.post(
            "/report",
            data={
                "target_type": "job",
                "target_id": "999999",
                "reason": "Ghost lead report",
            },
            headers={"Referer": f"http://localhost/jobs/{job['id']}"},
        )
        self.assertEqual(ghost.status_code, 302)
        self.assertEqual(ghost.headers["Location"], f"/jobs/{job['id']}")
        ghost_report = self.one(
            "SELECT * FROM reports WHERE reason = ?",
            ("Ghost lead report",),
        )
        self.assertIsNone(ghost_report)

        external = self.client.post(
            "/report",
            data={
                "target_type": "job",
                "target_id": str(job["id"]),
                "reason": "Suspicious lead details",
            },
            headers={"Referer": "https://example.test/not-workdoe"},
        )
        self.assertEqual(external.status_code, 302)
        self.assertEqual(external.headers["Location"], "/dashboard")
        report = self.one(
            "SELECT * FROM reports WHERE reason = ?",
            ("Suspicious lead details",),
        )
        self.assertIsNotNone(report)

        internal = self.client.post(
            "/report",
            data={
                "target_type": "job",
                "target_id": str(job["id"]),
                "reason": "Same origin report",
            },
            headers={"Referer": f"http://localhost/jobs/{job['id']}?source=detail"},
        )
        self.assertEqual(internal.status_code, 302)
        self.assertEqual(internal.headers["Location"], f"/jobs/{job['id']}?source=detail")

    def test_admin_can_hide_job_and_resolve_report(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")
        report = self.one("SELECT id, target_id FROM reports WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("admin@workdoe.local", "workdoe-admin")
        admin_user = self.one("SELECT id, status FROM users WHERE role = 'admin' LIMIT 1")
        protected_admin = self.client.post(
            f"/admin/users/{admin_user['id']}/suspend",
        )
        self.assertEqual(protected_admin.status_code, 400)
        unchanged_admin = self.one("SELECT status FROM users WHERE id = ?", (admin_user["id"],))
        self.assertEqual(unchanged_admin["status"], "active")
        hide_response = self.client.post(
            f"/admin/jobs/{job['id']}/hide",
            follow_redirects=True,
        )
        self.assertIn(b"Job hidden", hide_response.data)
        hide_html = hide_response.data.decode("utf-8")
        self.assertIn(
            'class="dashboard-metrics compact-metrics" aria-label="Moderation summary"',
            hide_html,
        )
        self.assertRegex(hide_html, r"<span>Open reports</span>\s*<strong>1</strong>")
        self.assertRegex(hide_html, r"<span>Hidden</span>\s*<strong>1</strong>")
        self.assertIn(f'href="/jobs/{report["target_id"]}"'.encode("ascii"), hide_response.data)
        self.assertIn(b">Review</a>", hide_response.data)
        hidden = self.one("SELECT status FROM jobs WHERE id = ?", (job["id"],))
        self.assertEqual(hidden["status"], "hidden")

        review_detail = self.client.get(f"/jobs/{report['target_id']}")
        self.assertEqual(review_detail.status_code, 200)
        self.assertIn(b"Admin review", review_detail.data)
        self.assertIn(b'href="/admin">Back to admin</a>', review_detail.data)
        self.assertNotIn(b"Report this lead", review_detail.data)

        resolve_response = self.client.post(
            f"/admin/reports/{report['id']}/resolve",
            follow_redirects=True,
        )
        self.assertIn(b"Report resolved", resolve_response.data)
        resolved = self.one("SELECT status FROM reports WHERE id = ?", (report["id"],))
        self.assertEqual(resolved["status"], "resolved")

    def test_admin_reviews_reported_message_without_reply_controls(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("contractor@workdoe.local", "workdoe-contractor")
        self.client.post(
            f"/jobs/{job['id']}/request",
            data={
                "scope_note": "I can handle the work and protect surrounding surfaces.",
                "price_range": "$500-$700",
                "timeline": "Two business days after approval",
                "experience": "Five years handling this type of local work.",
                "questions": "",
                "availability": "Weekday mornings",
            },
            follow_redirects=True,
        )
        match = self.one("SELECT * FROM match_requests WHERE job_id = ?", (job["id"],))

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        self.client.post(f"/client/requests/{match['id']}/approve", follow_redirects=True)
        thread = self.one("SELECT * FROM threads WHERE match_request_id = ?", (match["id"],))
        message = self.one(
            "SELECT id, body FROM messages WHERE thread_id = ? ORDER BY id LIMIT 1",
            (thread["id"],),
        )
        self.client.post(
            "/report",
            data={
                "target_type": "message",
                "target_id": str(message["id"]),
                "reason": "Reported message needs context",
            },
            headers={"Referer": f"http://localhost/messages/{thread['id']}"},
        )

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        hide_message = self.client.post(
            f"/admin/messages/{message['id']}/hide",
            follow_redirects=True,
        )
        self.assertIn(b"Message hidden.", hide_message.data)
        self.assertIn(
            f'action="/admin/messages/{message["id"]}/restore"'.encode("ascii"),
            hide_message.data,
        )
        hidden_message = self.one("SELECT is_hidden FROM messages WHERE id = ?", (message["id"],))
        self.assertEqual(hidden_message["is_hidden"], 1)

        admin = self.client.get("/admin")
        self.assertEqual(admin.status_code, 200)
        self.assertIn(b"Message:", admin.data)
        self.assertIn(f'href="/messages/{thread["id"]}"'.encode("ascii"), admin.data)
        self.assertIn(b">Review</a>", admin.data)

        review = self.client.get(f"/messages/{thread['id']}")
        self.assertEqual(review.status_code, 200)
        self.assertIn(message["body"].encode("utf-8"), review.data)
        self.assertIn(b'class="status hidden">hidden</span>', review.data)
        self.assertIn(b'href="/admin">Admin</a>', review.data)
        self.assertNotIn(b"New message", review.data)
        self.assertNotIn(b"Report message", review.data)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        client_thread = self.client.get(f"/messages/{thread['id']}")
        self.assertEqual(client_thread.status_code, 200)
        self.assertNotIn(message["body"].encode("utf-8"), client_thread.data)
        self.assertNotIn(b'class="status hidden">hidden</span>', client_thread.data)

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")

        restore_message = self.client.post(
            f"/admin/messages/{message['id']}/restore",
            follow_redirects=True,
        )
        self.assertIn(b"Message restored.", restore_message.data)
        restored_message = self.one("SELECT is_hidden FROM messages WHERE id = ?", (message["id"],))
        self.assertEqual(restored_message["is_hidden"], 0)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        restored_thread = self.client.get(f"/messages/{thread['id']}")
        self.assertIn(message["body"].encode("utf-8"), restored_thread.data)

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")

        before = self.one("SELECT COUNT(*) AS total FROM messages WHERE thread_id = ?", (thread["id"],))
        forbidden = self.client.post(
            f"/messages/{thread['id']}",
            data={"body": "Admin should not enter the conversation."},
        )
        self.assertEqual(forbidden.status_code, 403)
        after = self.one("SELECT COUNT(*) AS total FROM messages WHERE thread_id = ?", (thread["id"],))
        self.assertEqual(after["total"], before["total"])


    def test_entry_and_project_forms_open_in_same_origin_dialogs(self):
        home = self.client.get("/")
        self.assertIn(b'data-site-dialog', home.data)
        self.assertIn(b'src="/static/site-dialogs.js?v=workdoe-overlay-dialog"', home.data)

        direct_login = self.client.get("/login")
        self.assertEqual(direct_login.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", direct_login.headers["Content-Security-Policy"])

        embedded_login = self.client.get("/login?embed=1")
        self.assertEqual(embedded_login.status_code, 200)
        self.assertIn(b'<body class="dialog-frame-body">', embedded_login.data)
        self.assertNotIn(b'data-site-dialog', embedded_login.data)
        self.assertEqual(embedded_login.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("frame-ancestors 'self'", embedded_login.headers["Content-Security-Policy"])
        self.assertNotIn("frame-ancestors 'none'", embedded_login.headers["Content-Security-Policy"])

        embedded_post = self.client.get(
            "/post-project",
            headers={"Sec-Fetch-Dest": "iframe", "Sec-Fetch-Site": "same-origin"},
        )
        self.assertEqual(embedded_post.status_code, 200)
        self.assertIn(b'<body class="dialog-frame-body">', embedded_post.data)
        self.assertNotIn(b"What needs doing?", embedded_post.data)
        self.assertNotIn(b'aria-label="Project draft steps"', embedded_post.data)
        self.assertEqual(embedded_post.headers["X-Frame-Options"], "SAMEORIGIN")

        script = (ROOT / "workdoe" / "static" / "site-dialogs.js").read_text(encoding="utf-8")
        self.assertIn('url.origin !== window.location.origin', script)
        self.assertIn('modalPaths.indexOf(window.location.pathname) !== -1', script)
        self.assertIn('url.searchParams.set("embed", "1")', script)
        self.assertIn('modalPaths.indexOf(current.pathname) === -1', script)
        self.assertIn('dialog.dataset.dialogKind = kindFor(url)', script)
        self.assertIn('delete dialog.dataset.dialogKind', script)
        styles = (ROOT / "workdoe" / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(
            ".dialog-frame-body .login-form-panel > div:first-of-type > h1",
            styles,
        )
        self.assertRegex(
            styles,
            r'\.site-dialog\[data-dialog-kind="auth"\] \.site-dialog-surface\s*\{[^}]*height: min\(520px, calc\(100dvh - 36px\)\);',
        )
        self.assertRegex(
            styles,
            r"\.form-grid\[data-project-composer\]\s*\{[^}]*overflow: clip;",
        )
        self.assertRegex(
            styles,
            r"\.project-step-actions\s*\{[^}]*position: sticky;[^}]*bottom: 0;",
        )

    def test_role_dashboards_show_private_project_and_closed_work_history(self):
        with self.app.app_context():
            db = get_db()
            client = db.execute("SELECT id FROM users WHERE email = ?", ("client@workdoe.local",)).fetchone()
            contractor = db.execute("SELECT id FROM users WHERE email = ?", ("contractor@workdoe.local",)).fetchone()
            job = db.execute(
                """
                SELECT * FROM jobs
                WHERE client_id = ? AND status = 'open'
                ORDER BY id
                LIMIT 1
                """,
                (client["id"],),
            ).fetchone()
            db.execute(
                "UPDATE jobs SET status = 'closed', close_reason = 'workdoe-match' WHERE id = ?",
                (job["id"],),
            )
            db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', ?, 'approved', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "Washed the steps and protected the surrounding brickwork.",
                    "$450-$600",
                    "One day",
                    "Five years of exterior cleaning work.",
                    "Weekday mornings",
                    "2026-08-10T12:00:00+00:00",
                    "2026-08-10T12:00:00+00:00",
                ),
            )
            db.commit()
            title = job["title"].encode("utf-8")
            zip_code = job["zip_code"].encode("ascii")

        self.login("client@workdoe.local", "workdoe-client")
        consumer_dashboard = self.client.get("/client/dashboard")
        self.assertIn(b"Project history", consumer_dashboard.data)
        self.assertIn(b"Previous work", consumer_dashboard.data)
        self.assertIn(title, consumer_dashboard.data)

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        contractor_dashboard = self.client.get("/contractor/dashboard")
        self.assertIn(b"Matched work", contractor_dashboard.data)
        self.assertIn(b"Awaiting both confirmations", contractor_dashboard.data)
        self.assertIn(b"Washed the steps and protected the surrounding brickwork.", contractor_dashboard.data)
        self.assertIn(b"One day", contractor_dashboard.data)
        self.assertIn(b"$450-$600", contractor_dashboard.data)
        self.assertIn(b"Specific addresses stay private.", contractor_dashboard.data)
        self.assertNotIn(zip_code, contractor_dashboard.data)

    def test_approved_match_requires_both_participants_for_verified_completion(self):
        with self.app.app_context():
            db = get_db()
            client = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("client@workdoe.local",),
            ).fetchone()
            contractor = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            job = db.execute(
                """
                SELECT jobs.id
                FROM jobs
                WHERE jobs.client_id = ?
                  AND jobs.status = 'open'
                  AND NOT EXISTS (
                    SELECT 1 FROM match_requests
                    WHERE match_requests.job_id = jobs.id
                      AND match_requests.contractor_id = ?
                  )
                ORDER BY jobs.id
                LIMIT 1
                """,
                (client["id"], contractor["id"]),
            ).fetchone()
            db.execute(
                "UPDATE jobs SET status = 'closed', close_reason = 'workdoe-match' WHERE id = ?",
                (job["id"],),
            )
            cursor = db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', ?, 'approved', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "Complete the agreed exterior cleaning scope.",
                    "$400-$550",
                    "One day",
                    "Experienced with residential exterior cleaning.",
                    "Weekday mornings",
                    "2026-08-16T12:00:00+00:00",
                    "2026-08-16T12:00:00+00:00",
                ),
            )
            request_id = cursor.lastrowid
            db.commit()

        self.login("contractor@workdoe.local", "workdoe-contractor")
        first_confirmation = self.client.post(
            f"/matches/{request_id}/complete",
            follow_redirects=True,
        )
        self.assertEqual(first_confirmation.status_code, 200)
        self.assertIn(b"Waiting for the other participant", first_confirmation.data)
        completion = self.one(
            "SELECT * FROM match_completions WHERE match_request_id = ?",
            (request_id,),
        )
        self.assertIsNotNone(completion["contractor_confirmed_at"])
        self.assertIsNone(completion["client_confirmed_at"])
        self.assertIsNone(completion["verified_at"])

        repeated_confirmation = self.client.post(
            f"/matches/{request_id}/complete",
            follow_redirects=True,
        )
        self.assertEqual(repeated_confirmation.status_code, 200)
        event_count = self.one(
            """
            SELECT COUNT(*) AS total FROM automation_events
            WHERE event_type = 'match-completion-confirmed' AND target_id = ?
            """,
            (request_id,),
        )
        self.assertEqual(event_count["total"], 1)

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        final_confirmation = self.client.post(
            f"/matches/{request_id}/complete",
            follow_redirects=True,
        )
        self.assertEqual(final_confirmation.status_code, 200)
        self.assertIn(b"Work completion verified by both participants", final_confirmation.data)
        completion = self.one(
            "SELECT * FROM match_completions WHERE match_request_id = ?",
            (request_id,),
        )
        self.assertIsNotNone(completion["client_confirmed_at"])
        self.assertIsNotNone(completion["contractor_confirmed_at"])
        self.assertIsNotNone(completion["verified_at"])

        dashboard = self.client.get("/client/dashboard")
        self.assertIn(b"Verified complete", dashboard.data)
        detail = self.client.get(f"/client/jobs/{job['id']}")
        self.assertIn(b"Both participants confirmed this Workdoe project", detail.data)
        self.assertNotIn(b">Reopen job<", detail.data)

        reopen = self.client.post(
            f"/client/jobs/{job['id']}/reopen",
            follow_redirects=True,
        )
        self.assertIn(b"cannot be reopened", reopen.data)
        persisted_job = self.one("SELECT status FROM jobs WHERE id = ?", (job["id"],))
        self.assertEqual(persisted_job["status"], "closed")

        profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertIn(b"1 verified", profile.data)

    def test_completion_rejects_unapproved_or_open_projects(self):
        with self.app.app_context():
            db = get_db()
            client = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("client@workdoe.local",),
            ).fetchone()
            contractor = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            job = db.execute(
                "SELECT id FROM jobs WHERE client_id = ? AND status = 'open' ORDER BY id LIMIT 1",
                (client["id"],),
            ).fetchone()
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, 'Pending scope details.', '$300-$450', 'One day',
                        'Relevant local experience.', '', 'Next week', 'pending', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "2026-08-16T13:00:00+00:00",
                    "2026-08-16T13:00:00+00:00",
                ),
            )
            request_id = cursor.lastrowid
            if not request_id:
                request_id = db.execute(
                    "SELECT id FROM match_requests WHERE job_id = ? AND contractor_id = ?",
                    (job["id"], contractor["id"]),
                ).fetchone()["id"]
                db.execute(
                    "UPDATE match_requests SET status = 'pending' WHERE id = ?",
                    (request_id,),
                )
            db.commit()

        self.login("contractor@workdoe.local", "workdoe-contractor")
        pending = self.client.post(f"/matches/{request_id}/complete")
        self.assertEqual(pending.status_code, 409)
        with self.app.app_context():
            get_db().execute(
                "UPDATE match_requests SET status = 'approved' WHERE id = ?",
                (request_id,),
            )
            get_db().commit()
        open_job = self.client.post(f"/matches/{request_id}/complete")
        self.assertEqual(open_job.status_code, 409)

    def test_verified_match_feedback_is_structured_private_and_moderated(self):
        with self.app.app_context():
            db = get_db()
            client = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("client@workdoe.local",),
            ).fetchone()
            contractor = db.execute(
                "SELECT id FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            job = db.execute(
                """
                SELECT * FROM jobs
                WHERE client_id = ? AND status = 'open'
                ORDER BY id LIMIT 1
                """,
                (client["id"],),
            ).fetchone()
            db.execute(
                "UPDATE jobs SET status = 'closed', close_reason = 'workdoe-match' WHERE id = ?",
                (job["id"],),
            )
            cursor = db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, 'Completed verified scope.', '$400-$500', 'One day',
                        'Exterior cleaning experience.', '', 'Weekday', 'approved', ?, ?)
                """,
                (
                    job["id"],
                    contractor["id"],
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                ),
            )
            request_id = int(cursor.lastrowid)
            db.execute(
                """
                INSERT INTO match_completions
                    (match_request_id, client_confirmed_at, contractor_confirmed_at,
                     verified_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (request_id,) + ("2026-08-17T13:00:00+00:00",) * 5,
            )
            db.commit()

        client_review = {
            "communication": "met",
            "scope_accuracy": "met",
            "timeliness": "mixed",
            "work_outcome": "met",
            "would_work_again": "yes",
            "comment": "Clear communication and careful work around the brick.",
        }
        self.login("client@workdoe.local", "workdoe-client")
        created = self.client.post(
            f"/matches/{request_id}/review",
            data=client_review,
            follow_redirects=True,
        )
        self.assertEqual(created.status_code, 200)
        self.assertIn(b"Completed-work feedback recorded", created.data)
        self.assertIn(b"Consumer feedback", created.data)
        self.assertIn(b"Consumer feedback", created.data)
        review = self.one(
            "SELECT * FROM match_reviews WHERE match_request_id = ? AND reviewer_id = ?",
            (request_id, client["id"]),
        )
        self.assertEqual(review["subject_id"], contractor["id"])
        event = self.one(
            """
            SELECT payload_json FROM automation_events
            WHERE event_type = 'match-review-created' AND target_id = ?
            """,
            (review["id"],),
        )
        self.assertNotIn("careful work", event["payload_json"])

        duplicate = self.client.post(
            f"/matches/{request_id}/review",
            data=client_review,
            follow_redirects=True,
        )
        self.assertIn(b"already left feedback", duplicate.data)
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM match_reviews WHERE match_request_id = ?",
                (request_id,),
            )["total"],
            1,
        )

        profile = self.client.get(f"/contractors/{contractor['id']}")
        self.assertIn(b"Completed-work feedback", profile.data)
        self.assertIn(b"Clear communication and careful work", profile.data)
        self.assertNotIn(b"client@workdoe.local", profile.data)
        self.assertNotIn(job["zip_code"].encode("ascii"), profile.data)
        self.assertNotIn(b"star rating", profile.data.lower())

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        dashboard = self.client.get("/contractor/dashboard")
        self.assertIn(b"Consumer feedback", dashboard.data)
        contractor_review = {
            "communication": "met",
            "scope_accuracy": "met",
            "timeliness": "met",
            "work_outcome": "not_applicable",
            "would_work_again": "yes",
            "comment": "The scope and access plan were ready when the crew arrived.",
        }
        contractor_created = self.client.post(
            f"/matches/{request_id}/review",
            data=contractor_review,
            follow_redirects=True,
        )
        self.assertIn(b"Contractor feedback", contractor_created.data)
        responded = self.client.post(
            f"/reviews/{review['id']}/response",
            data={"response": "Thank you. We would be glad to help again."},
            follow_redirects=True,
        )
        self.assertIn(b"Feedback response recorded", responded.data)
        reported = self.client.post(
            f"/reviews/{review['id']}/report",
            data={"reason": "Please verify that the project details remain private."},
            follow_redirects=True,
        )
        self.assertIn(b"Feedback sent to moderation", reported.data)
        report = self.one(
            "SELECT * FROM match_review_reports WHERE review_id = ?",
            (review["id"],),
        )

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        admin = self.client.get("/admin")
        self.assertIn(b"Participant feedback", admin.data)
        self.assertIn(b"Please verify that the project details remain private", admin.data)
        hidden = self.client.post(
            f"/admin/reviews/{review['id']}/hide",
            follow_redirects=True,
        )
        self.assertIn(b"Feedback moderation updated", hidden.data)
        self.assertEqual(
            self.one("SELECT is_hidden FROM match_reviews WHERE id = ?", (review["id"],))[
                "is_hidden"
            ],
            1,
        )
        resolved = self.client.post(
            f"/admin/review-reports/{report['id']}/resolve",
            follow_redirects=True,
        )
        self.assertIn(b"Feedback report resolved", resolved.data)
        self.assertEqual(
            self.one(
                "SELECT status FROM match_review_reports WHERE id = ?",
                (report["id"],),
            )["status"],
            "resolved",
        )

    def test_verified_consumer_can_invite_prior_contractor_for_a_fresh_bid(self):
        timestamp = "2026-08-17T14:00:00+00:00"
        with self.app.app_context():
            db = get_db()
            consumer = db.execute(
                "SELECT * FROM users WHERE email = ?",
                ("client@workdoe.local",),
            ).fetchone()
            contractor = db.execute(
                "SELECT * FROM users WHERE email = ?",
                ("contractor@workdoe.local",),
            ).fetchone()
            source_job = db.execute(
                """
                INSERT INTO jobs
                    (client_id, title, category, service_group_slug, service_slug,
                     service_zone_slug, project_setting, city, state, zip_code,
                     description, desired_date, status, close_reason, closed_at,
                     approx_lat, approx_lng, bid_limit, bidding_closes_at,
                     created_at, updated_at)
                VALUES (?, 'Prior patio wash', 'Power washing', 'outdoor-yard',
                        'pressure-washing', 'district-of-columbia', 'outdoor-area',
                        'Washington', 'DC', '20003',
                        'Wash the patio and front steps without exposing exact address details.',
                        '2026-08-10', 'closed', 'workdoe-match', ?, 38.88, -76.99,
                        4, '2026-08-16T14:00:00+00:00', ?, ?)
                """,
                (consumer["id"], timestamp, timestamp, timestamp),
            )
            source_job_id = source_job.lastrowid
            source_match = db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, 'Completed the patio wash and protected nearby surfaces.',
                        '$350-$450', 'One day', 'Exterior cleaning experience.', '',
                        'Weekday mornings', 'approved', ?, ?)
                """,
                (source_job_id, contractor["id"], timestamp, timestamp),
            )
            source_match_id = source_match.lastrowid
            db.execute(
                """
                INSERT INTO match_completions
                    (match_request_id, client_confirmed_at, contractor_confirmed_at,
                     verified_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    source_match_id,
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            other_hash = generate_password_hash("other-contractor")
            other = db.execute(
                """
                INSERT INTO users
                    (email, password_hash, role, display_name, company_name,
                     status, email_verified, auth_provider, created_at)
                VALUES ('other@workdoe.local', ?, 'contractor', 'Other Contractor',
                        'Other Co', 'active', 1, 'local', ?)
                """,
                (other_hash, timestamp),
            )
            other_contractor_id = other.lastrowid
            db.commit()

        self.login("client@workdoe.local", "workdoe-client")
        dashboard = self.client.get("/client/dashboard")
        invite_url = f"/jobs/new?repeat={source_job_id}&amp;invite={source_match_id}"
        self.assertIn(b"Invite again", dashboard.data)
        self.assertIn(invite_url.encode("ascii"), dashboard.data)

        composer = self.client.get(
            f"/jobs/new?repeat={source_job_id}&invite={source_match_id}"
        )
        self.assertEqual(composer.status_code, 200)
        self.assertIn(b"can bid again", composer.data)
        self.assertIn(
            f'name="repeat_match_request_id" value="{source_match_id}"'.encode(),
            composer.data,
        )

        common = {
            "category": "Power washing",
            "service_group_slug": "outdoor-yard",
            "project_setting": "outdoor-area",
            "city": "Washington",
            "state": "DC",
            "zip_code": "20003",
            "desired_date": "2026-12-01",
            "budget_min": "350",
            "budget_max": "500",
            "description": "Wash the patio and front steps while protecting nearby surfaces.",
            "repeat_source_job_id": str(source_job_id),
            "repeat_match_request_id": str(source_match_id),
        }
        wrong_service = self.client.post(
            "/jobs/new",
            data={
                **common,
                "title": "Wrong repeat service",
                "category": "Window cleaning",
                "service_group_slug": "cleaning-upkeep",
                "service_slug": "window-cleaning",
            },
        )
        self.assertEqual(wrong_service.status_code, 200)
        self.assertIn(b"must keep the same service", wrong_service.data)
        self.assertIsNone(
            self.one("SELECT id FROM jobs WHERE title = 'Wrong repeat service'")
        )

        posted = self.client.post(
            "/jobs/new",
            data={
                **common,
                "title": "Fresh patio wash invitation",
                "service_slug": "pressure-washing",
            },
            follow_redirects=True,
        )
        self.assertIn(b"was invited to send a new mini bid", posted.data)
        invitation = self.one(
            """
            SELECT repeat_provider_invitations.*
            FROM repeat_provider_invitations
            JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
            WHERE jobs.title = 'Fresh patio wash invitation'
            """
        )
        self.assertEqual(invitation["status"], "pending")
        self.assertEqual(invitation["contractor_id"], contractor["id"])
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
                (invitation["job_id"],),
            )["total"],
            0,
        )

        consumer_decline = self.client.post(
            f"/repeat-invitations/{invitation['id']}/decline"
        )
        self.assertEqual(consumer_decline.status_code, 404)
        self.logout()
        self.login("other@workdoe.local", "other-contractor")
        unrelated_decline = self.client.post(
            f"/repeat-invitations/{invitation['id']}/decline"
        )
        self.assertEqual(unrelated_decline.status_code, 404)

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        contractor_dashboard = self.client.get("/contractor/dashboard")
        self.assertIn(b"Invited back", contractor_dashboard.data)
        self.assertIn(b"Fresh patio wash invitation", contractor_dashboard.data)
        bid = self.client.post(
            f"/jobs/{invitation['job_id']}/request",
            data={
                "scope_note": "I can repeat the verified patio washing scope and protect nearby surfaces.",
                "price_range": "$375-$475",
                "timeline": "One day",
                "experience": "I completed the prior verified Workdoe project for this consumer.",
                "questions": "Has the access route changed?",
                "availability": "Weekday mornings",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Mini bid sent", bid.data)
        updated_invitation = self.one(
            "SELECT * FROM repeat_provider_invitations WHERE id = ?",
            (invitation["id"],),
        )
        self.assertEqual(updated_invitation["status"], "bid_sent")
        self.assertEqual(
            self.one(
                "SELECT COUNT(*) AS total FROM match_requests WHERE job_id = ?",
                (invitation["job_id"],),
            )["total"],
            1,
        )

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        self.client.post(
            "/jobs/new",
            data={
                **common,
                "title": "Repeat invitation to decline",
                "service_slug": "pressure-washing",
            },
            follow_redirects=True,
        )
        decline_invitation = self.one(
            """
            SELECT repeat_provider_invitations.*
            FROM repeat_provider_invitations
            JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
            WHERE jobs.title = 'Repeat invitation to decline'
            """
        )
        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        declined = self.client.post(
            f"/repeat-invitations/{decline_invitation['id']}/decline",
            follow_redirects=True,
        )
        self.assertIn(b"Invitation declined", declined.data)
        self.assertEqual(
            self.one(
                "SELECT status FROM repeat_provider_invitations WHERE id = ?",
                (decline_invitation["id"],),
            )["status"],
            "declined",
        )

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        self.client.post(
            "/jobs/new",
            data={
                **common,
                "title": "Repeat invitation to withdraw",
                "service_slug": "pressure-washing",
            },
            follow_redirects=True,
        )
        withdraw_invitation = self.one(
            """
            SELECT repeat_provider_invitations.*
            FROM repeat_provider_invitations
            JOIN jobs ON jobs.id = repeat_provider_invitations.job_id
            WHERE jobs.title = 'Repeat invitation to withdraw'
            """
        )
        withdrawn = self.client.post(
            f"/repeat-invitations/{withdraw_invitation['id']}/withdraw",
            follow_redirects=True,
        )
        self.assertIn(b"Invitation withdrawn", withdrawn.data)
        self.assertEqual(
            self.one(
                "SELECT status FROM repeat_provider_invitations WHERE id = ?",
                (withdraw_invitation["id"],),
            )["status"],
            "withdrawn",
        )
        repeat_match = self.one(
            """
            SELECT id FROM match_requests
            WHERE job_id = ? AND contractor_id = ?
            """,
            (invitation["job_id"], contractor["id"]),
        )
        with self.app.app_context():
            db = get_db()
            db.execute(
                "UPDATE match_requests SET status = 'approved' WHERE id = ?",
                (repeat_match["id"],),
            )
            db.execute(
                """
                INSERT INTO match_completions
                    (match_request_id, client_confirmed_at, contractor_confirmed_at,
                     verified_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    repeat_match["id"],
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            db.commit()

        self.logout()
        self.login("admin@workdoe.local", "workdoe-admin")
        repeat_funnel = self.client.get("/admin")
        self.assertEqual(repeat_funnel.status_code, 200)
        self.assertIn(b"Invitation funnel", repeat_funnel.data)
        self.assertIn(b"Project-level only", repeat_funnel.data)
        self.assertIn(b"<span>Invited</span><strong>3</strong>", repeat_funnel.data)
        self.assertIn(b"<span>Fresh bids</span><strong>1</strong>", repeat_funnel.data)
        self.assertIn(b"33% of invitations", repeat_funnel.data)
        self.assertIn(b"<span>Verified repeats</span><strong>1</strong>", repeat_funnel.data)
        self.assertIn(b"100% of fresh bids", repeat_funnel.data)
        self.assertIn(b"Recent repeat invitations", repeat_funnel.data)
        self.assertIn(b"Fresh patio wash invitation", repeat_funnel.data)
        self.assertNotIn(
            b"Wash the patio and front steps without exposing exact address details",
            repeat_funnel.data,
        )
        self.assertGreater(other_contractor_id, 0)

    def test_six_step_project_composer_stores_canonical_service_bucket(self):
        self.login("client@workdoe.local", "workdoe-client")
        family_form = self.client.get("/jobs/new?family=outdoor-yard")
        self.assertEqual(family_form.status_code, 200)
        self.assertIn(b'data-project-initial-step="2"', family_form.data)
        self.assertIn(b'value="outdoor-yard"', family_form.data)
        task_form = self.client.get(
            "/jobs/new?family=outdoor-yard&service=pressure-washing"
        )
        self.assertEqual(task_form.status_code, 200)
        self.assertIn(b'data-project-initial-step="3"', task_form.data)
        self.assertIn(b'value="pressure-washing"', task_form.data)
        self.assertIn(b"checked", task_form.data)
        form = self.client.get("/jobs/new")
        self.assertEqual(form.status_code, 200)
        self.assertEqual(form.data.count(b'data-project-step="'), 6)
        self.assertEqual(form.data.count(b'class="service-family-option"'), 6)
        self.assertEqual(form.data.count(b'class="service-option"'), 53)
        self.assertEqual(form.data.count(b'class="service-option-more"'), 6)
        self.assertEqual(form.data.count(b'class="service-option-heading"'), 6)
        self.assertIn(b"Common tasks", form.data)
        self.assertIn(b"More yard &amp; landscaping services", form.data)
        self.assertIn(b'/vendor/tabler-icons/trees.svg', form.data)
        self.assertIn(b'/vendor/tabler-icons/lawn-mower.svg', form.data)
        self.assertIn(b'/vendor/tabler-icons/seedling.svg', form.data)
        self.assertIn(b'/vendor/tabler-icons/plant.svg', form.data)
        self.assertIn(b'/static/project-composer.js?v=workdoe-service-tiles', form.data)
        self.assertIn(b'name="service_group_slug"', form.data)
        self.assertIn(b'name="service_slug"', form.data)
        self.assertIn(b'name="service_choice"', form.data)
        self.assertIn(b'data-selected-service-family', form.data)
        self.assertIn(b'class="service-select-control"', form.data)
        self.assertEqual(form.data.count(b'class="project-setting-option"'), 6)
        self.assertIn(b'data-review-setting', form.data)

        from workdoe.service_taxonomy import SERVICE_ICON_BY_SLUG

        form_html = form.data.decode("utf-8")
        for service_slug, icon_name in SERVICE_ICON_BY_SLUG.items():
            service_block = form_html.split(
                f'id="service-choice-{service_slug}"', 1
            )[1].split("</label>", 1)[0]
            self.assertIn(
                f'/vendor/tabler-icons/{icon_name}',
                service_block,
                service_slug,
            )

        posted = self.client.post(
            "/jobs/new",
            data={
                "title": "Mow and edge the back lawn",
                "category": "Other",
                "service_group_slug": "outdoor-yard",
                "service_slug": "lawn-mowing",
                "project_setting": "outdoor-area",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "desired_date": "2026-12-01",
                "budget_min": "120",
                "budget_max": "180",
                "description": "Mow and edge a small fenced back lawn and remove the clippings.",
            },
            follow_redirects=True,
        )
        self.assertEqual(posted.status_code, 200)
        created = self.one(
            "SELECT * FROM jobs WHERE title = ?",
            ("Mow and edge the back lawn",),
        )
        self.assertEqual(created["service_group_slug"], "outdoor-yard")
        self.assertEqual(created["service_slug"], "lawn-mowing")
        self.assertEqual(created["project_setting"], "outdoor-area")
        self.assertEqual(created["category"], "Landscaping")
        self.assertIn(b"Lawn mowing", posted.data)
        self.assertIn(b"Outdoor area", posted.data)

        groups = self.one("SELECT COUNT(*) AS count FROM service_groups")
        services = self.one("SELECT COUNT(*) AS count FROM service_types")
        aliases = self.one("SELECT service_slug FROM service_aliases WHERE alias = 'mowing'")
        recall_alias = self.one(
            "SELECT service_slug FROM service_aliases WHERE alias = 'grass cutting'"
        )
        service_icon_row = self.one(
            "SELECT icon_name FROM service_types WHERE slug = 'lawn-mowing'"
        )
        self.assertEqual(groups["count"], 6)
        self.assertGreaterEqual(services["count"], 50)
        self.assertEqual(aliases["service_slug"], "lawn-mowing")
        self.assertEqual(recall_alias["service_slug"], "lawn-mowing")
        self.assertEqual(service_icon_row["icon_name"], "lawn-mower.svg")

    def test_service_specific_scope_answers_are_normalized_and_role_safe(self):
        raw = {
            "scope_area_size": "SMALL",
            "scope_grass_height": "6_12",
            "scope_terrain": "obstacles",
            "scope_recurrence": "one_time",
            "scope_untrusted": "street address",
        }
        answers = clean_scope_answers("lawn-mowing", raw)
        self.assertEqual(
            answers,
            {
                "area_size": "small",
                "grass_height": "6_12",
                "terrain": "obstacles",
                "recurrence": "one_time",
            },
        )
        self.assertEqual(validate_scope_answers("lawn-mowing", answers), [])
        self.assertTrue(
            validate_scope_answers("lawn-mowing", {"terrain": "<script>"})
        )
        self.assertEqual(scope_readiness("lawn-mowing", answers)["percent"], 100)
        self.assertEqual(len(scope_answer_projection("lawn-mowing", answers)), 4)

        self.login("client@workdoe.local", "workdoe-client")
        form = self.client.get("/jobs/new")
        self.assertIn(b'data-service-scope-set="lawn-mowing"', form.data)
        self.assertIn(b'name="scope_grass_height"', form.data)
        self.assertIn(b'data-review-scope', form.data)
        self.assertIn(b'data-review-brief', form.data)

        posted = self.client.post(
            "/jobs/new",
            data={
                "title": "Mow the fenced back lawn",
                "category": "Other",
                "service_group_slug": "outdoor-yard",
                "service_slug": "lawn-mowing",
                "project_setting": "outdoor-area",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "desired_date": "2026-12-01",
                "description": "Mow and edge the fenced back lawn and stage the clippings by the gate.",
                **raw,
            },
            follow_redirects=True,
        )
        self.assertEqual(posted.status_code, 200)
        self.assertIn(b"Quote-ready details", posted.data)
        self.assertIn(b"6-12 inches", posted.data)
        self.assertIn(b"Brief 5 of 6", posted.data)
        self.assertIn(b"Ready to quote", posted.data)
        job = self.one(
            "SELECT * FROM jobs WHERE title = ?", ("Mow the fenced back lawn",)
        )
        stored = self.all(
            """
            SELECT schema_version, question_key, answer_code
            FROM job_scope_answers WHERE job_id = ? ORDER BY question_key
            """,
            (job["id"],),
        )
        self.assertEqual(len(stored), 4)
        self.assertTrue(all(row["schema_version"] == 1 for row in stored))
        self.assertNotIn("street address", {row["answer_code"] for row in stored})

        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        lead = self.client.get(f"/jobs/{job['id']}")
        self.assertIn(b"Quote-ready details", lead.data)
        self.assertIn(b"Trees or obstacles", lead.data)
        self.assertIn(b"222xx", lead.data)
        self.assertNotIn(b"22201", lead.data)

    def test_project_brief_readiness_is_deterministic_and_ignores_identity_fields(self):
        row = {
            "service_slug": "lawn-mowing",
            "description": "Mow and edge the fenced back lawn and remove all clippings.",
            "project_setting": "outdoor-area",
            "desired_date": "2026-12-01",
            "budget_min": 120,
            "scope_answer_count": 4,
            "photo_count": 0,
            "email": "private@example.com",
            "exact_address": "100 Private Street",
        }
        readiness = project_brief_readiness(row)
        redacted = project_brief_readiness(
            {key: value for key, value in row.items() if key not in {"email", "exact_address"}}
        )
        self.assertEqual(readiness, redacted)
        self.assertEqual(readiness["label"], "Brief 6 of 6")
        self.assertEqual(readiness["state"], "ready")
        self.assertEqual(
            [signal["key"] for signal in readiness["signals"]],
            [
                "service",
                "description",
                "scope",
                "setting",
                "timing",
                "budget_or_photo",
            ],
        )

    def test_pilot_cell_metrics_are_aggregate_deterministic_and_privacy_safe(self):
        projects = [
            {
                "service_slug": "lawn-mowing",
                "service_zone_slug": "arlington-county-va",
                "service_name": "Lawn mowing",
                "zone_name": "Arlington County, VA",
                "created_at": "2026-08-17T13:00:00+00:00",
                "description": "Mow and edge the fenced back lawn and remove all clippings.",
                "project_setting": "outdoor-area",
                "desired_date": "2026-08-24",
                "budget_min": 120,
                "scope_answer_count": 4,
                "photo_count": 0,
                "bid_count": 2,
                "first_bid_at": "2026-08-17T13:30:00+00:00",
                "matched_count": 1,
                "verified_completion_count": 1,
                "status": "closed",
                "close_reason": "workdoe-match",
                "open_report_count": 1,
                "email": "private@example.com",
                "exact_address": "100 Private Street",
                "close_note": "Private project note",
                "report_reason": "Private report narrative",
            },
            {
                "service_slug": "lawn-mowing",
                "service_zone_slug": "arlington-county-va",
                "service_name": "Lawn mowing",
                "zone_name": "Arlington County, VA",
                "created_at": "2026-08-19T09:00:00+00:00",
                "description": "Lawn help needed.",
                "project_setting": "",
                "desired_date": "",
                "scope_answer_count": 0,
                "photo_count": 0,
                "bid_count": 1,
                "first_bid_at": "2026-08-19T10:30:00+00:00",
                "matched_count": 0,
                "verified_completion_count": 0,
                "status": "closed",
                "close_reason": "no-qualified-bid",
                "open_report_count": 0,
            },
        ]
        supply = [
            {
                "service_slug": "lawn-mowing",
                "zone_slug": "arlington-county-va",
                "current_eligible_contractors": 2,
                "minimum_eligible_contractors": 3,
                "activation_status": "candidate",
                "service_name": "Lawn mowing",
                "zone_name": "Arlington County, VA",
            },
            {
                "service_slug": "house-cleaning",
                "zone_slug": "district-of-columbia",
                "current_eligible_contractors": 4,
                "minimum_eligible_contractors": 3,
                "activation_status": "active",
                "service_name": "House cleaning",
                "zone_name": "District of Columbia",
            },
        ]
        metrics = pilot_cell_metrics(projects, supply, as_of="2026-08-17")
        redacted_metrics = pilot_cell_metrics(
            [
                {
                    key: value
                    for key, value in project.items()
                    if key
                    not in {
                        "email",
                        "exact_address",
                        "close_note",
                        "report_reason",
                    }
                }
                for project in projects
            ],
            supply,
            as_of="2026-08-17",
        )
        self.assertEqual(metrics, redacted_metrics)
        self.assertEqual(metrics["summary"]["observed_cells"], 1)
        self.assertEqual(metrics["summary"]["tracked_cells"], 2)
        self.assertEqual(metrics["summary"]["active_zero_project_cells"], 1)
        self.assertEqual(metrics["summary"]["qualified_match_rate"], 50)
        self.assertEqual(metrics["summary"]["median_first_bid_minutes"], 60)
        self.assertEqual(metrics["summary"]["median_first_bid_label"], "1 hr")
        self.assertEqual(metrics["summary"]["first_bid_samples"], 2)
        self.assertEqual(metrics["summary"]["closed_projects"], 2)
        self.assertEqual(metrics["summary"]["workdoe_match_closures"], 1)
        self.assertEqual(metrics["summary"]["no_match_or_cancelled_projects"], 1)
        self.assertEqual(metrics["summary"]["open_report_projects"], 1)
        self.assertEqual(metrics["summary"]["open_report_rate"], 50)
        cell = next(
            item for item in metrics["cells"] if item["service_slug"] == "lawn-mowing"
        )
        self.assertEqual(cell["week_start"], "2026-08-17")
        self.assertEqual(cell["brief_ready_projects"], 1)
        self.assertEqual(cell["projects_with_bids"], 2)
        self.assertEqual(cell["total_bids"], 3)
        self.assertEqual(cell["verified_completion_rate"], 100)
        self.assertEqual(cell["median_first_bid_label"], "1 hr")
        self.assertEqual(cell["closed_projects"], 2)
        self.assertEqual(cell["workdoe_close_rate"], 50)
        self.assertEqual(cell["state"], "supply-gap")
        no_demand = next(
            item
            for item in metrics["cells"]
            if item["service_slug"] == "house-cleaning"
        )
        self.assertEqual(no_demand["state"], "no-demand")
        self.assertEqual(no_demand["published_projects"], 0)
        serialized = json.dumps(metrics).lower()
        self.assertNotIn("private@example.com", serialized)
        self.assertNotIn("private street", serialized)
        self.assertNotIn("private project note", serialized)
        self.assertNotIn("private report narrative", serialized)
        self.assertNotIn("13:30:00", serialized)
        self.assertNotIn("10:30:00", serialized)

        self.login("admin@workdoe.local", "workdoe-admin")
        admin = self.client.get("/admin")
        self.assertEqual(admin.status_code, 200)
        self.assertIn(b"Service-zone pulse", admin.data)
        self.assertIn(b"Aggregate only", admin.data)
        self.assertIn(b"Median first bid", admin.data)
        self.assertIn(b"Open project reports", admin.data)
        self.assertIn(b"No tracked service-zone cells", admin.data)

    def test_contractor_proposal_templates_reuse_words_but_never_price(self):
        contractor = self.one(
            "SELECT id FROM users WHERE email = ?",
            ("contractor@workdoe.local",),
        )
        open_jobs = self.all(
            """
            SELECT * FROM jobs WHERE status = 'open' ORDER BY id
            """
        )
        self.assertGreaterEqual(len(open_jobs), 2)
        source_job = open_jobs[0]
        target_job = open_jobs[1]
        with self.app.app_context():
            db = get_db()
            source_bid_id = db.execute(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, questions, availability, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    source_job["id"],
                    contractor["id"],
                    "Protect adjacent surfaces and complete the listed exterior scope.",
                    "$480-$620",
                    "Two business days after approval",
                    "Five years completing comparable exterior projects in the DMV.",
                    "Is exterior water access available?",
                    "Weekday mornings",
                    "2026-08-17T12:00:00+00:00",
                    "2026-08-17T12:00:00+00:00",
                ),
            ).lastrowid
            db.commit()
        source_bid = self.one(
            "SELECT * FROM match_requests WHERE id = ?", (source_bid_id,)
        )
        self.assertIsNotNone(source_bid)
        self.assertIsNotNone(target_job)
        self.assertEqual(PROPOSAL_TEMPLATE_LIMIT, 6)

        self.login("contractor@workdoe.local", "workdoe-contractor")
        saved = self.client.post(
            "/contractor/proposal-templates",
            data={
                "name": "Standard exterior response",
                "source_match_request_id": source_bid["id"],
            },
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertIn(b"Proposal template saved", saved.data)
        template = self.one(
            "SELECT * FROM contractor_proposal_templates WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertEqual(template["name"], "Standard exterior response")
        self.assertEqual(template["scope_note"], source_bid["scope_note"])
        self.assertEqual(template["timeline"], source_bid["timeline"])
        self.assertNotIn(
            "price_range",
            {
                row["name"]
                for row in self.all("PRAGMA table_info(contractor_proposal_templates)")
            },
        )

        dashboard = self.client.get("/contractor/dashboard")
        self.assertIn(b"Proposal templates", dashboard.data)
        self.assertIn(b"Standard exterior response", dashboard.data)
        applied = self.client.get(
            f"/jobs/{target_job['id']}?proposal_template={template['id']}"
        )
        self.assertEqual(applied.status_code, 200)
        self.assertIn(b"Template applied", applied.data)
        self.assertIn(source_bid["scope_note"].encode("utf-8"), applied.data)
        self.assertIn(source_bid["experience"].encode("utf-8"), applied.data)
        self.assertIn(
            b'id="bid-price-range" name="price_range" value=""',
            applied.data,
        )
        self.assertIn(b'placeholder="Add a fresh estimate"', applied.data)
        self.assertNotIn(source_bid["price_range"].encode("utf-8"), applied.data)

        event = self.one(
            """
            SELECT payload_json FROM automation_events
            WHERE event_type = 'contractor-proposal-template-created'
            ORDER BY id DESC LIMIT 1
            """
        )
        self.assertNotIn(source_bid["scope_note"], event["payload_json"])
        self.assertNotIn(source_bid["price_range"], event["payload_json"])

        self.logout()
        self.login("client@workdoe.local", "workdoe-client")
        forbidden = self.client.post(
            f"/contractor/proposal-templates/{template['id']}/delete"
        )
        self.assertEqual(forbidden.status_code, 403)
        self.logout()
        self.login("contractor@workdoe.local", "workdoe-contractor")
        deleted = self.client.post(
            f"/contractor/proposal-templates/{template['id']}/delete",
            follow_redirects=True,
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertIn(b"Proposal template removed", deleted.data)
        self.assertIsNone(
            self.one(
                "SELECT id FROM contractor_proposal_templates WHERE id = ?",
                (template["id"],),
            )
        )

    def test_bid_comparison_is_received_ordered_fact_only_and_privacy_safe(self):
        rows = [
            {
                "id": 22,
                "contractor_id": 8,
                "business_name": "Later Crew",
                "trades": "House cleaning",
                "status": "pending",
                "scope_note": "Deep clean all listed rooms.",
                "price_range": "$420-$500",
                "timeline": "Two days",
                "experience": "Five years of apartment turnovers.",
                "questions": "Is parking available?",
                "availability": "Thursday",
                "years_in_business": 5,
                "insurance_status": "Policy available on request",
                "source_checked_credential_count": 1,
                "verified_work_count": 3,
                "created_at": "2026-08-17T14:00:00+00:00",
                "email": "later@example.com",
                "phone": "202-555-0100",
                "website": "https://private.example.com",
                "license_number": "PRIVATE-22",
                "exact_address": "100 Private Street",
            },
            {
                "id": 21,
                "contractor_id": 7,
                "business_name": "First Crew",
                "trades": "House cleaning",
                "status": "pending",
                "scope_note": "Clean the apartment and remove bagged waste.",
                "price_range": "$450 flat",
                "timeline": "One day",
                "experience": "Turnover cleaning across the District.",
                "questions": "",
                "availability": "Wednesday",
                "years_in_business": 0,
                "insurance_status": "",
                "source_checked_credential_count": 0,
                "verified_work_count": 0,
                "created_at": "2026-08-17T13:00:00+00:00",
            },
            {
                "id": 20,
                "contractor_id": 6,
                "business_name": "Already Matched",
                "status": "approved",
                "created_at": "2026-08-17T12:00:00+00:00",
            },
        ]
        comparison = bid_comparison(rows, "pending")
        self.assertEqual(comparison["count"], 2)
        self.assertTrue(comparison["has_multiple"])
        self.assertEqual(
            [offer["contractor_name"] for offer in comparison["offers"]],
            ["First Crew", "Later Crew"],
        )
        self.assertEqual(comparison["offers"][0]["offer_label"], "Offer 1")
        self.assertEqual(
            comparison["offers"][0]["provider_facts"][0]["value"],
            "New business",
        )
        self.assertEqual(
            comparison["offers"][1]["provider_facts"][1]["value"],
            "1 credential",
        )
        self.assertEqual(
            comparison["offers"][1]["provider_facts"][2]["value"],
            "3 projects",
        )
        self.assertEqual(bid_comparison(rows, "approved")["offers"], [])
        serialized = json.dumps(comparison).lower()
        for private_value in (
            "later@example.com",
            "202-555-0100",
            "private.example.com",
            "private-22",
            "private street",
        ):
            self.assertNotIn(private_value, serialized)


if __name__ == "__main__":
    unittest.main()
