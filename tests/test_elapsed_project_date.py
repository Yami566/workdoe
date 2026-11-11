from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

from workdoe import create_app, get_db
from workdoe.service_policy import SERVICE_POLICY_VERSION


class DateInput(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.attributes = None
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        values = dict(attributes)
        if tag == "input" and values.get("name") == "desired_date":
            self.attributes = values


class ElapsedProjectDateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.app = create_app({
            "TESTING": True, "DATABASE": str(root / "test.sqlite3"),
            "UPLOAD_ROOT": str(root / "uploads"), "SEED_DEMO_DATA": False,
            "AUTH_PROVIDER": "local", "DISABLE_CSRF": True,
        })
        self.original = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        with self.app.app_context():
            db = get_db()
            db.execute("""
                INSERT INTO users (id, email, password_hash, role, display_name, status, email_verified, created_at)
                VALUES (1, 'owner@fixture.invalid', '', 'client', 'Fixture', 'active', 1, 'before')
            """)
            db.execute("""
                INSERT INTO jobs (id, client_id, title, category, service_group_slug, service_slug,
                                  city, state, zip_code, description, desired_date, status, created_at, updated_at)
                VALUES (1, 1, 'TEST ONLY original title', 'Window cleaning', 'cleaning-upkeep',
                        'window-cleaning', 'Alexandria', 'VA', '22314', 'Original synthetic scope for testing.',
                        ?, 'open', 'before', 'before')
            """, (self.original,))
            db.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
        self.payload = {
            "title": "TEST ONLY updated title", "description": "Owner-controlled beta test. No actual work is requested.",
            "city": "Alexandria", "state": "VA", "zip_code": "22314", "desired_date": self.original,
            "service_policy_acknowledgement": SERVICE_POLICY_VERSION,
        }

    def test_owner_can_retain_the_stored_date_while_editing_other_details(self):
        page = self.client.get("/client/jobs/1/edit")
        self.assertEqual(page.status_code, 200)
        field = DateInput(page.get_data(as_text=True)).attributes
        self.assertIsNotNone(field)
        self.assertEqual(field["value"], self.original)
        self.assertNotIn("min", field, "The browser must not reject the stored date before server validation.")
        response = self.client.post("/client/jobs/1/edit", data=self.payload)
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            job = get_db().execute("SELECT * FROM jobs WHERE id = 1").fetchone()
            self.assertEqual(job["desired_date"], self.original)
            self.assertEqual(job["title"], self.payload["title"])
            self.assertEqual((job["status"], job["created_at"]), ("open", "before"))

    def test_forged_retained_dates_do_not_bypass_validation(self):
        self.payload["desired_date"] = (datetime.now(UTC).date() - timedelta(days=3)).isoformat()
        self.payload["preserved_desired_date"] = self.payload["desired_date"]
        response = self.client.post("/client/jobs/1/edit", data=self.payload)
        self.assertIn(b"Choose today or a future desired date.", response.data)
        self.assertIn(b'aria-invalid="true"', response.data)
        with self.app.app_context():
            job = get_db().execute("SELECT * FROM jobs WHERE id = 1").fetchone()
            self.assertEqual(job["desired_date"], self.original)
            self.assertEqual(job["title"], "TEST ONLY original title")

    def test_new_posts_cannot_claim_a_retained_date(self):
        payload = self.payload | {
            "category": "Window cleaning", "service_group_slug": "cleaning-upkeep",
            "service_slug": "window-cleaning", "preserved_desired_date": self.original,
        }
        response = self.client.post("/jobs/new", data=payload)
        self.assertIn(b"Choose today or a future desired date.", response.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)

    def test_an_invalid_stored_date_is_not_accepted_as_a_retained_date(self):
        with self.app.app_context():
            get_db().execute("UPDATE jobs SET desired_date = 'not-a-date' WHERE id = 1")
            get_db().commit()
        self.payload["desired_date"] = "not-a-date"
        response = self.client.post("/client/jobs/1/edit", data=self.payload)
        self.assertIn(b"Use a valid desired date.", response.data)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT title FROM jobs WHERE id = 1").fetchone()[0],
                             "TEST ONLY original title")

    def test_an_elapsed_date_can_be_cleared_or_replaced_with_a_future_date(self):
        for desired in ("", (datetime.now(UTC).date() + timedelta(days=2)).isoformat()):
            with self.subTest(desired=desired):
                with self.app.app_context():
                    get_db().execute("UPDATE jobs SET desired_date = ? WHERE id = 1", (self.original,))
                    get_db().commit()
                response = self.client.post("/client/jobs/1/edit", data=self.payload | {"desired_date": desired})
                self.assertEqual(response.status_code, 302)
                with self.app.app_context():
                    self.assertEqual(get_db().execute("SELECT desired_date FROM jobs WHERE id = 1").fetchone()[0], desired)


if __name__ == "__main__":
    unittest.main()
