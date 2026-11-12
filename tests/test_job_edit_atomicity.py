from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from test_cloudflare_release import load_worker_entry_module

ROOT = Path(__file__).resolve().parents[1]


class SQLiteStatement:
    def __init__(self, database, sql, params=()):
        self.database, self.sql, self.params = database, sql, params

    def bind(self, *params):
        return SQLiteStatement(self.database, self.sql, params)

    async def run(self):
        cursor = self.database.connection.execute(self.sql, self.params)
        rows = [dict(row) for row in cursor.fetchall()]
        if not self.database.batching:
            self.database.standalone_writes += 1
            self.database.connection.commit()
        return {"success": True, "results": rows, "meta": {"changes": max(cursor.rowcount, 0)}}


class SQLiteDatabase:
    def __init__(self, connection):
        self.connection, self.batching = connection, False
        self.batch_calls, self.standalone_writes = 0, 0

    def prepare(self, sql):
        return SQLiteStatement(self, sql)

    async def batch(self, statements):
        self.batch_calls += 1
        self.batching = True
        try:
            with self.connection:
                return [await statement.run() for statement in statements]
        finally:
            self.batching = False


class JobEditAtomicityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        for migration in sorted((ROOT / "cloudflare/d1/migrations").glob("*.sql")):
            self.db.executescript(migration.read_text(encoding="utf-8"))
        self.db.executescript("""
            INSERT INTO users (id, email, password_hash, role, display_name, status, created_at)
            VALUES (1, 'owner@fixture.invalid', '', 'client', 'Fixture owner', 'active', 'before'),
                   (2, 'other@fixture.invalid', '', 'client', 'Other fixture', 'active', 'before');
            INSERT INTO jobs (id, client_id, title, category, service_group_slug, service_slug,
                              city, state, zip_code, description, desired_date, status,
                              bidding_closes_at, created_at, updated_at)
            VALUES (1, 1, 'TEST ONLY original title', 'Window cleaning', 'cleaning-upkeep',
                    'window-cleaning', 'Alexandria', 'VA', '22314', 'Original synthetic scope for testing.',
                    '', 'open', '2099-01-01', 'before', 'before');
            INSERT INTO job_scope_answers
                (job_id, schema_version, question_key, answer_code, created_at, updated_at)
            VALUES (1, 1, 'height', 'ground', 'before', 'before');
        """)
        self.module = load_worker_entry_module()
        self.worker = self.module.Default()
        self.worker.env = SimpleNamespace(DB=SQLiteDatabase(self.db))
        self.worker.optional_workdoe_user = AsyncMock(
            return_value={"id": 1, "role": "client", "status": "active"},
        )
        self.payload = {
            "title": "TEST ONLY updated title",
            "description": "Owner-controlled beta test. No actual work is requested. Please do not bid.",
            "project_setting": "house", "city": "Alexandria", "state": "VA", "zip_code": "22314",
            "desired_date": "", "budget_min": "", "budget_max": "",
            "scope_height": "one_story",
            "service_policy_acknowledgement": self.module.service_policy("window-cleaning")["version"],
        }

    def snapshot(self):
        return {
            table: [tuple(row) for row in self.db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in ("jobs", "job_scope_answers", "service_policy_acknowledgements", "automation_events")
        }

    async def save(self, verification_effect=None):
        async def job(_env, _id):
            return dict(self.db.execute("SELECT * FROM jobs WHERE id = 1").fetchone())

        with (
            patch.object(self.module, "JS_NULL", None),
            patch.object(self.module, "job_for_detail", job),
            patch.object(self.module, "request_json_object", AsyncMock(return_value=dict(self.payload))),
            patch.object(self.module, "verify_turnstile_for_request", AsyncMock(side_effect=verification_effect)),
        ):
            return await self.worker.update_job(SimpleNamespace(method="POST"), "/api/jobs/1/update")

    async def test_owner_edit_commits_scope_advisory_and_event_together(self):
        response = await self.save()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.body)["url"], "/client/jobs/1")
        row = self.db.execute("SELECT * FROM jobs WHERE id = 1").fetchone()
        self.assertEqual(row["title"], self.payload["title"])
        self.assertEqual(row["description"], self.payload["description"])
        self.assertEqual((row["status"], row["created_at"], row["bidding_closes_at"]), ("open", "before", "2099-01-01"))
        self.assertEqual(self.db.execute("SELECT answer_code FROM job_scope_answers").fetchone()[0], "one_story")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_policy_acknowledgements").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT event_type FROM automation_events").fetchone()[0], "job-updated")
        self.assertEqual(self.worker.env.DB.batch_calls, 1)
        self.assertEqual(self.worker.env.DB.standalone_writes, 0)

    async def assert_rolls_back(self, table, condition=""):
        self.db.executescript(f"""
            CREATE TRIGGER fixture_fail_edit BEFORE INSERT ON {table} {condition}
            BEGIN SELECT RAISE(ABORT, 'synthetic edit failure'); END;
        """)
        before = self.snapshot()
        try:
            response = await self.save()
        except sqlite3.Error:
            response = None
        self.assertEqual(self.snapshot(), before, "A rejected edit committed partial state.")
        self.assertIsNotNone(response)
        self.assertEqual(response.status, 503)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotIn("synthetic edit failure", response.body)
        self.db.execute("DROP TRIGGER fixture_fail_edit")
        self.db.commit()
        self.assertEqual((await self.save()).status, 200)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM automation_events").fetchone()[0], 1)

    async def test_scope_failure_rolls_back_the_project_and_preserves_old_answers(self):
        await self.assert_rolls_back("job_scope_answers")

    async def test_advisory_failure_rolls_back_the_project_and_scope(self):
        await self.assert_rolls_back("service_policy_acknowledgements")

    async def test_event_failure_rolls_back_all_edit_records(self):
        await self.assert_rolls_back("automation_events", "WHEN NEW.event_type = 'job-updated'")

    async def test_permission_changes_during_verification_prevent_all_edit_writes(self):
        for change in (
            "UPDATE jobs SET status = 'hidden' WHERE id = 1",
            "UPDATE jobs SET client_id = 2 WHERE id = 1",
            "UPDATE users SET status = 'suspended' WHERE id = 1",
            "UPDATE users SET role = 'contractor' WHERE id = 1",
        ):
            with self.subTest(change=change):
                self.db.executescript("""
                    UPDATE jobs SET client_id = 1, status = 'open';
                    UPDATE users SET role = 'client', status = 'active' WHERE id = 1;
                """)
                before = None

                async def changed(*_args, change=change, **_kwargs):
                    nonlocal before
                    self.db.execute(change)
                    self.db.commit()
                    before = self.snapshot()

                response = await self.save(changed)
                self.assertEqual(response.status, 409)
                self.assertEqual(self.snapshot(), before)

    async def test_invalid_date_returns_field_error_without_writes(self):
        self.payload["desired_date"] = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        before = self.snapshot()
        response = await self.save()
        self.assertEqual(response.status, 400)
        self.assertIn("desired_date", json.loads(response.body)["field_errors"])
        self.assertEqual(self.snapshot(), before)

    async def test_owner_can_edit_scope_without_changing_an_elapsed_requested_date(self):
        original = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        self.db.execute("UPDATE jobs SET desired_date = ? WHERE id = 1", (original,))
        self.db.commit()
        self.payload["desired_date"] = original
        response = await self.save()
        self.assertEqual(response.status, 200, response.body)
        row = self.db.execute("SELECT * FROM jobs WHERE id = 1").fetchone()
        self.assertEqual(row["desired_date"], original)
        self.assertEqual(row["title"], self.payload["title"])
        self.assertEqual((row["status"], row["bidding_closes_at"], row["created_at"]),
                         ("open", "2099-01-01", "before"))

    async def test_a_forged_retained_date_does_not_allow_another_past_date(self):
        original = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        self.db.execute("UPDATE jobs SET desired_date = ? WHERE id = 1", (original,))
        self.db.commit()
        self.payload["desired_date"] = (datetime.now(UTC).date() - timedelta(days=3)).isoformat()
        self.payload["preserved_desired_date"] = self.payload["desired_date"]
        before = self.snapshot()
        response = await self.save()
        self.assertEqual(response.status, 400)
        self.assertIn("desired_date", json.loads(response.body)["field_errors"])
        self.assertEqual(self.snapshot(), before)

    async def test_invalid_legacy_date_is_not_exempt_from_validation(self):
        self.db.execute("UPDATE jobs SET desired_date = 'not-a-date' WHERE id = 1")
        self.db.commit()
        self.payload["desired_date"] = "not-a-date"
        before = self.snapshot()
        response = await self.save()
        self.assertEqual(response.status, 400)
        self.assertIn("desired_date", json.loads(response.body)["field_errors"])
        self.assertEqual(self.snapshot(), before)

    async def test_owner_can_clear_an_elapsed_date_or_choose_a_new_future_date(self):
        original = (datetime.now(UTC).date() - timedelta(days=2)).isoformat()
        for desired in ("", (datetime.now(UTC).date() + timedelta(days=2)).isoformat()):
            with self.subTest(desired=desired):
                self.db.execute("UPDATE jobs SET desired_date = ? WHERE id = 1", (original,))
                self.db.commit()
                self.payload["desired_date"] = desired
                response = await self.save()
                self.assertEqual(response.status, 200, response.body)
                self.assertEqual(self.db.execute("SELECT desired_date FROM jobs WHERE id = 1").fetchone()[0], desired)

    async def test_edit_with_empty_optional_scope_and_no_advisory(self):
        self.db.execute("UPDATE jobs SET service_slug = 'gardening-planting', service_group_slug = 'outdoor-yard', category = 'Landscaping'")
        self.db.commit()
        self.payload.pop("scope_height")
        self.payload["service_policy_acknowledgement"] = ""
        self.payload["service_slug"] = "electrical"
        response = await self.save()
        self.assertEqual(response.status, 200)
        self.assertEqual(self.db.execute("SELECT service_slug FROM jobs").fetchone()[0], "gardening-planting")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM job_scope_answers").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_policy_acknowledgements").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM automation_events").fetchone()[0], 1)
