from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from workdoe import (
    CLERK_PROXY_PATH,
    create_app,
    clerk_proxy_url,
    get_db,
    message_count_label,
    normalize_clerk_frontend_api_url,
    normalize_login_code_submission,
    photo_count_label,
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
        return self.client.get("/logout", follow_redirects=True)

    def one(self, sql, params=()):
        with self.app.app_context():
            return get_db().execute(sql, params).fetchone()

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
        self.assertIn(b"Your jobs and match requests", allowed.data)

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
                "photos": (BytesIO(b"fake image bytes"), "storefront.png", "image/png"),
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
        self.assertIn(b"Edit job.", edit.data)
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
                "photos": (BytesIO(b"updated image bytes"), "after.jpg", "image/jpeg"),
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

    def test_client_job_controls_only_show_relevant_status_action(self):
        job = self.one("SELECT id FROM jobs WHERE status = 'open' ORDER BY id LIMIT 1")

        self.login("client@workdoe.local", "workdoe-client")
        detail = self.client.get(f"/client/jobs/{job['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b">Close job</button>", detail.data)
        self.assertNotIn(b">Reopen job</button>", detail.data)
        self.assertIn(b'class="job-facts"', detail.data)
        self.assertIn(b"<dt>Trade</dt>", detail.data)
        self.assertIn(b"<dt>Area</dt>", detail.data)
        self.assertIn(b"<dt>Target</dt>", detail.data)
        self.assertIn(b"<dt>Photos</dt>", detail.data)

        closed = self.client.post(
            f"/client/jobs/{job['id']}/close",
            follow_redirects=True,
        )
        self.assertEqual(closed.status_code, 200)
        self.assertIn(b">Reopen job</button>", closed.data)
        self.assertNotIn(b">Close job</button>", closed.data)

        reopened = self.client.post(
            f"/client/jobs/{job['id']}/reopen",
            follow_redirects=True,
        )
        self.assertEqual(reopened.status_code, 200)
        self.assertIn(b">Close job</button>", reopened.data)
        self.assertNotIn(b">Reopen job</button>", reopened.data)

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
        self.assertIn(b'maxlength="500"', detail.data)
        self.assertIn(b'class="message-form" method="post" aria-label="New message"', detail.data)
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
        self.assertIn(b'class="lead-action-bar" aria-label="Lead actions"', detail.data)
        self.assertIn(b'href="#mini-bid">Send mini bid</a>', detail.data)
        self.assertIn(b'href="#job-details">Review details</a>', detail.data)
        self.assertIn(b'id="job-details" class="panel job-detail-panel" tabindex="-1"', detail.data)
        self.assertIn(b'id="mini-bid" class="panel bid-panel" tabindex="-1"', detail.data)
        self.assertIn(b'class="job-facts"', detail.data)
        self.assertIn(b"<dt>Trade</dt>", detail.data)
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
        self.assertIn(b'type="tel"', form.data)

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
        self.assertIn(b"Use a full website URL that starts with http:// or https://.", invalid.data)
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
                "portfolio_photos": (BytesIO(b"profile photo bytes"), "crew.webp", "image/webp"),
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
        photo = self.one(
            "SELECT * FROM contractor_photos WHERE contractor_id = ?",
            (contractor["id"],),
        )
        self.assertIsNotNone(photo)

    def test_contractor_profile_report_flow_and_admin_review(self):
        contractor = self.one("SELECT id FROM users WHERE email = ?", ("contractor@workdoe.local",))
        profile_url = f"/contractors/{contractor['id']}"

        public_profile = self.client.get(profile_url)
        self.assertEqual(public_profile.status_code, 200)
        self.assertNotIn(b"Report this profile", public_profile.data)

        self.login("client@workdoe.local", "workdoe-client")
        client_profile = self.client.get(profile_url)
        self.assertEqual(client_profile.status_code, 200)
        self.assertIn(b"Report this profile", client_profile.data)
        self.assertIn(b'value="profile"', client_profile.data)
        self.assertIn(f'value="{contractor["id"]}"'.encode("ascii"), client_profile.data)

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
        self.assertRegex(contractor_html, r"<span>Open leads</span>\s*<strong>3</strong>")
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
        self.assertRegex(client_html, r"<span>Total jobs</span>\s*<strong>3</strong>")
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
        self.assertIn("img-src 'self' data: https://*.tile.openstreetmap.org", csp)
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

        start = self.client.get("/start")
        self.assertEqual(start.status_code, 200)
        self.assertIn(b'href="/start" aria-current="page">Start</a>', start.data)

        self.login("contractor@workdoe.local", "workdoe-contractor")
        leads = self.client.get("/leads")
        self.assertEqual(leads.status_code, 200)
        self.assertIn(b'href="/leads" aria-current="page">Leads</a>', leads.data)

    def test_mobile_css_keeps_entry_header_compact_and_start_form_first(self):
        styles = (ROOT / "workdoe" / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".entry-shortcuts", styles)
        self.assertIn(".entry-shortcut", styles)
        self.assertRegex(styles, r"\.entry-shortcuts a,\s*\.entry-shortcut\s*\{[^}]*min-height: 30px;")
        mobile_rules = re.search(r"@media \(max-width: 900px\) \{(?P<body>.*)\n\}", styles, re.S)
        self.assertIsNotNone(mobile_rules)
        body = mobile_rules.group("body")
        self.assertRegex(body, r"\.brand,\s*\.main-nav\s*\{[^}]*flex: 0 1 auto;[^}]*width: 100%;")
        self.assertRegex(body, r"\.start-form-panel\s*\{[^}]*order: -1;")
        self.assertRegex(body, r"\.lead-metrics\s*\{[^}]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);")
        self.assertRegex(body, r"\.lead-filter\s*\{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);")
        self.assertRegex(body, r"\.lead-filter \.search-field\s*\{[^}]*grid-column: 1 / -1;[^}]*order: -1;")
        self.assertRegex(body, r"@media \(max-width: 520px\)\s*\{")
        self.assertRegex(body, r"\.main-nav\s*\{[^}]*display: grid;[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);")
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
        self.assertIn(b"Email me a code", login.data)
        self.assertIn(b"Admin/demo password", login.data)

        returned = self.client.post(
            "/login?next=/jobs/new",
            data={"email": "client@workdoe.local", "password": "workdoe-client"},
            follow_redirects=True,
        )
        self.assertEqual(returned.status_code, 200)
        self.assertIn(b"Post a job.", returned.data)

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
        self.assertIn(b"One-time code, same Workdoe page flow.", lead_login.data)

        new_lead_start = self.client.post(
            f"/login?next=/jobs/{job['id']}",
            data={"email": "new-contractor@example.com", "auth_action": "code"},
        )
        self.assertEqual(new_lead_start.status_code, 302)
        self.assertIn("/start?intent=find-work", new_lead_start.headers["Location"])
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
        self.assertIn(b'data-clerk-mode="signin"', login.data)
        self.assertIn(b'data-redirect-url="/jobs/new"', login.data)
        self.assertIn(b'data-session-url="/api/auth/session"', login.data)
        self.assertIn(b'data-dashboard-url="/dashboard"', login.data)
        self.assertIn(b"Email code sign-in stays on workdoe.com.", login.data)
        self.assertIn(b"https://clerk.workdoe.com/npm/@clerk/clerk-js@6", login.data)
        self.assertIn(b"/static/clerk-entry.js", login.data)
        self.assertNotIn(b'name="auth_action" value="code"', login.data)

        selected_login = client.get("/login?next=/jobs/1")
        self.assertEqual(selected_login.status_code, 200)
        self.assertIn(b'data-sign-up-url="/start?intent=find-work&amp;job_id=1"', selected_login.data)

        start = client.get("/start?intent=find-work")
        self.assertEqual(start.status_code, 200)
        self.assertIn(b'data-clerk-mode="start"', start.data)
        self.assertIn(b'data-session-url="/api/auth/session"', start.data)
        self.assertIn(b'data-onboard-url="/api/auth/onboard"', start.data)
        self.assertIn(b'data-leads-url="/leads"', start.data)

        csp = login.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self' https://clerk.workdoe.com", csp)
        self.assertIn("connect-src 'self' https://clerk.workdoe.com", csp)
        self.assertIn("img-src 'self' data: https://*.tile.openstreetmap.org https://clerk.workdoe.com", csp)
        self.assertIn("style-src-elem 'self' https://clerk.workdoe.com", csp)
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
        self.assertEqual(event_payload["email"], "casey.contractor@example.com")
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

    def test_vendored_leaflet_assets_are_pinned(self):
        expected_hashes = {
            "leaflet.css": "sha256-M3v8pcq9A7OYFbJwD+vis7ft9VkhxZzUn4jssyghIwM=",
            "leaflet.js": "sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=",
        }
        vendor_dir = ROOT / "workdoe" / "static" / "vendor" / "leaflet"

        for filename, expected in expected_hashes.items():
            canonical_bytes = (vendor_dir / filename).read_bytes().replace(b"\r\n", b"\n")
            digest = base64.b64encode(hashlib.sha256(canonical_bytes).digest())
            self.assertEqual("sha256-" + digest.decode("ascii"), expected)

        for filename in [
            "images/layers.png",
            "images/layers-2x.png",
            "images/marker-icon.png",
            "images/marker-icon-2x.png",
            "images/marker-shadow.png",
        ]:
            self.assertTrue((vendor_dir / filename).exists())

        self.assertIn("BSD 2-Clause License", (vendor_dir / "LICENSE").read_text())

    def test_contractor_lead_filters_have_clear_empty_state(self):
        self.login("contractor@workdoe.local", "workdoe-contractor")
        board = self.client.get("/leads")
        self.assertEqual(board.status_code, 200)
        self.assertIn(b'class="dashboard-metrics lead-metrics"', board.data)
        self.assertIn(b'class="filter-bar lead-filter"', board.data)
        self.assertIn(b'role="search" aria-label="Filter contractor leads"', board.data)
        self.assertIn(b'aria-controls="lead-results lead-map"', board.data)
        self.assertIn(b'class="search-field"', board.data)
        self.assertIn(b'id="lead-results" class="job-list lead-job-list" aria-label="Open leads" role="list"', board.data)
        self.assertIn(b'class="map-panel lead-map-panel"', board.data)
        self.assertLess(board.data.find(b"lead-job-list"), board.data.find(b"lead-map-panel"))
        self.assertIn(b'class="job-row link-row" role="listitem" data-job-id="', board.data)
        self.assertIn(b"row-cue", board.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=50"', board.data)
        self.assertIn(b'name="q" type="search" enterkeyhint="search"', board.data)
        self.assertIn(b'maxlength="80"', board.data)
        self.assertIn(b'name="sort"', board.data)
        self.assertIn(b'role="region"', board.data)
        self.assertIn(b'aria-describedby="lead-map-status"', board.data)
        self.assertIn(b'id="lead-map-loading"', board.data)
        self.assertIn(b'id="lead-map-status" class="sr-only" aria-live="polite"', board.data)
        self.assertIn(b"Map loading. Job list is ready.", board.data)

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

    def test_login_and_start_show_live_jobs_map(self):
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b'title="Workdoe home"', home.data)
        self.assertIn(b"brand-home-button", home.data)
        self.assertIn(b"Open jobs near you.", home.data)
        self.assertIn(b"Approximate DMV job map", home.data)
        self.assertIn(b"compact-filter", home.data)
        self.assertIn(b'role="search" aria-label="Filter open jobs"', home.data)
        self.assertIn(b'aria-controls="home-open-job-results lead-map"', home.data)
        self.assertIn(b'id="home-open-jobs" class="job-list"', home.data)
        self.assertIn(b'name="q" type="search" enterkeyhint="search"', home.data)
        self.assertIn(b'maxlength="80"', home.data)
        self.assertIn(b'name="sort"', home.data)
        self.assertIn(b'role="region"', home.data)
        self.assertIn(b'aria-describedby="lead-map-status"', home.data)
        self.assertIn(b'id="lead-map-loading"', home.data)
        self.assertIn(b'id="lead-map-status" class="sr-only" aria-live="polite"', home.data)
        self.assertIn(b"Map loading. Job list is ready.", home.data)
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
        self.assertIn(b'data-job-id="', home.data)
        self.assertIn(b'aria-label="Sign in for Power wash townhouse front steps"', home.data)
        self.assertNotIn(b"job-summary", home.data)
        self.assertNotIn(b"Small office needs evening touch-up painting", home.data)
        self.assertIn(b"Target", home.data)
        self.assertIn(b"leads near DC, Maryland, and Virginia", home.data)

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
        self.assertIn(b"Live jobs posted", login.data)
        self.assertIn(b'<nav class="entry-shortcuts" aria-label="Sign in shortcuts">', login.data)
        self.assertIn(b'href="#live-jobs">Live jobs</a>', login.data)
        self.assertIn(b'id="live-jobs" class="login-live-panel" tabindex="-1"', login.data)
        self.assertIn(b'class="entry-shortcut" href="#signin">Sign in</a>', login.data)
        self.assertIn(b"open leads", login.data)
        self.assertIn(b"compact-filter entry-filter", login.data)
        self.assertIn(b'role="search" aria-label="Filter open jobs before signing in"', login.data)
        self.assertIn(b'aria-controls="login-open-jobs lead-map"', login.data)
        self.assertIn(b'id="login-open-jobs" class="job-list login-job-list" aria-label="Open jobs at login" role="list"', login.data)
        self.assertIn(b'name="q" type="search" enterkeyhint="search"', login.data)
        self.assertIn(b'maxlength="80"', login.data)
        self.assertIn(b'name="sort"', login.data)
        self.assertIn(b'id="map-jobs-data" type="application/json"', login.data)
        self.assertNotIn(b"window.WORKDOE_JOBS", login.data)
        self.assertIn(b'data-jobs-api="/api/jobs/open?limit=6&amp;target=login"', login.data)
        self.assertIn(b'class="job-row link-row compact-lead-row"', login.data)
        self.assertIn(b'role="listitem"', login.data)
        self.assertIn(b'data-job-id="', login.data)
        self.assertIn(b'aria-label="Sign in lead Power wash townhouse front steps"', login.data)
        self.assertIn(b'href="/login?next=/jobs/', login.data)
        self.assertIn(b"Email me a code", login.data)
        self.assertIn(b"One-time code, same Workdoe page flow.", login.data)
        self.assertIn(b"Admin/demo password", login.data)
        self.assertIn(b'name="auth_action" value="password"', login.data)
        self.assertNotIn(b"Email one-time code", login.data)
        self.assertNotIn(b"Small office needs evening touch-up painting", login.data)

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
            f'aria-label="Selected lead {selected_login_job["title"]}"'.encode("utf-8"),
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
        self.assertIn(b"Choose your workspace", start.data)
        self.assertIn(b'id="live-jobs" class="login-live-panel start-live-panel" tabindex="-1"', start.data)
        self.assertIn(b'class="entry-shortcut" href="#start-account">Start</a>', start.data)
        self.assertIn(b'id="start-account" class="form-panel login-form-panel start-form-panel"', start.data)
        self.assertIn(b'<nav class="entry-shortcuts" aria-label="Start shortcuts">', start.data)
        self.assertIn(b'value="post-job" checked', start.data)
        self.assertIn(b'value="find-work"', start.data)
        self.assertIn(b"compact-filter entry-filter", start.data)
        self.assertIn(b'role="search" aria-label="Filter open jobs while starting"', start.data)
        self.assertIn(b'aria-controls="start-open-jobs lead-map"', start.data)
        self.assertIn(b'id="start-open-jobs" class="job-list login-job-list" aria-label="Open jobs while starting account" role="list"', start.data)
        self.assertIn(b'name="q" type="search" enterkeyhint="search"', start.data)
        self.assertIn(b'maxlength="80"', start.data)
        self.assertIn(b'name="sort"', start.data)
        self.assertIn(b"<h2>Start</h2>", start.data)
        self.assertIn(b'class="form-checklist auth-checklist" aria-label="Email code safeguards"', start.data)
        self.assertIn(b"Email code", start.data)
        self.assertIn(b"Same site", start.data)
        self.assertIn(b"No password", start.data)
        self.assertIn(b'aria-describedby="start-name-help"', start.data)
        self.assertIn(b"New accounts only.", start.data)
        self.assertNotIn(b'name="display_name" autocomplete="name" required', start.data)
        self.assertIn(b"Email me a code", start.data)
        self.assertNotIn(b"Use password instead", start.data)
        self.assertNotIn(b"Use demo password", start.data)
        self.assertIn(b"open leads", start.data)
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

        find_work_start = self.client.get("/start?intent=find-work")
        self.assertEqual(find_work_start.status_code, 200)
        self.assertIn(b'value="find-work" checked', find_work_start.data)

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
            f'aria-label="Selected lead {selected_job["title"]}"'.encode("utf-8"),
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
        self.assertRegex(first_job["url"], r"^/start\?intent=find-work&job_id=\d+$")
        self.assertNotIn("zip_code", first_job)
        self.assertNotIn("description", first_job)

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

    def test_map_script_announces_results_and_active_rows(self):
        script = (ROOT / "workdoe" / "static" / "map.js").read_text()
        self.assertIn("setMapStatus", script)
        self.assertIn("updateResultStatus", script)
        self.assertIn("announceActiveJob", script)
        self.assertIn("markerLabel", script)
        self.assertIn("labelMarkerElement", script)
        self.assertIn("alt: accessibleMarkerLabel", script)
        self.assertIn("title: accessibleMarkerLabel", script)
        self.assertIn('setAttribute("aria-label", label)', script)
        self.assertIn("data-map-active", script)
        self.assertIn("openPopup", script)
        self.assertIn("moveJobFocus", script)
        self.assertIn('aria-keyshortcuts", "ArrowUp ArrowDown Home End"', script)
        self.assertIn('event.key === "ArrowDown"', script)
        self.assertIn('event.key === "ArrowUp"', script)
        self.assertIn('event.key === "Home"', script)
        self.assertIn('event.key === "End"', script)
        self.assertIn("preventScroll: true", script)
        self.assertIn("No open leads match this view", script)

    def test_local_password_reset_token_flow(self):
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
        self.assertIn(b"Your jobs and match requests", login_response.data)
        self.assertIn(b'class="job-row link-row"', login_response.data)
        self.assertIn(b"row-cue", login_response.data)

    def test_start_flow_creates_client_and_lands_on_job_form(self):
        missing_name = self.client.post(
            "/start",
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
            "/start",
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
        self.assertIn(b"Post a job.", verified.data)
        user = self.one("SELECT * FROM users WHERE email = ?", ("new-client@example.com",))
        self.assertEqual(user["role"], "client")

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
            self.assertIn(b"Post a job.", verified.data)
        finally:
            self.app.config["SHOW_LOCAL_LOGIN_CODE"] = True

    def test_job_form_constraints_and_error_value_preservation(self):
        self.login("client@workdoe.local", "workdoe-client")
        form = self.client.get("/jobs/new")
        self.assertEqual(form.status_code, 200)
        self.assertIn(b'class="form-grid" method="post" enctype="multipart/form-data" aria-label="Post a job."', form.data)
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
        self.assertIn(b'aria-label="Post job"', form.data)
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

        before = self.one("SELECT COUNT(*) AS total FROM messages WHERE thread_id = ?", (thread["id"],))
        forbidden = self.client.post(
            f"/messages/{thread['id']}",
            data={"body": "Admin should not enter the conversation."},
        )
        self.assertEqual(forbidden.status_code, 403)
        after = self.one("SELECT COUNT(*) AS total FROM messages WHERE thread_id = ?", (thread["id"],))
        self.assertEqual(after["total"], before["total"])


if __name__ == "__main__":
    unittest.main()
