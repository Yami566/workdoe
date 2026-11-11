import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from test_cloudflare_release import load_worker_entry_module

MIGRATIONS = Path(__file__).resolve().parents[1] / "cloudflare" / "d1" / "migrations"
THREAD_PATH = "/api/messages/threads/1"
REPLY = {"body": "I can start Tuesday.", "idempotency_key": "fixture-thread-reply-00001"}


class MatchTransactionTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            self.db.executescript(migration.read_text(encoding="utf-8"))
        self.db.executescript("""
            INSERT INTO users (id, email, password_hash, role, display_name, created_at)
            VALUES (1, 'client@example.invalid', '', 'client', 'Consumer', '2026-01-01'),
                   (2, 'provider@example.invalid', '', 'contractor', 'Contractor', '2026-01-01');
            INSERT INTO jobs (id, client_id, title, category, city, state, zip_code, description, created_at, updated_at)
            VALUES (1, 1, 'Mow the yard', 'Landscaping', 'Arlington', 'VA', '22201', 'Small yard',
                    '2026-01-01', '2026-01-01');
            INSERT INTO match_requests
                (id, job_id, contractor_id, scope_note, price_range, timeline, experience, availability,
                 status, created_at, updated_at)
            VALUES (1, 1, 2, 'Mowing', '$80', 'Next week', 'Lawn care', 'Tuesday',
                    'approved', '2026-01-01', '2026-01-01');
            INSERT INTO threads (id, job_id, match_request_id, client_id, contractor_id, created_at)
            VALUES (1, 1, 1, 1, 2, '2026-01-01');
        """)
        self.module = load_worker_entry_module()
        self.worker = self.module.Default()
        self.worker.env = SimpleNamespace(DB=object())
        self.worker.optional_workdoe_user = AsyncMock(return_value={"id": 1, "role": "client", "status": "active"})
        self.module.request_json_object = AsyncMock(return_value=REPLY)
        self.module.db_run = self.execute
        self.module.db_batch = self.batch
        self.interleaved_change = None

    def statement(self, sql, bindings):
        cursor = self.db.execute(sql, bindings)
        return {
            "results": [dict(row) for row in cursor.fetchall()] if cursor.description else [],
            "meta": {"changes": max(0, cursor.rowcount), "last_row_id": cursor.lastrowid},
        }

    def interleave(self, sql):
        if self.interleaved_change and sql.lstrip().startswith(self.interleaved_change[0]):
            with self.db:
                self.db.execute(self.interleaved_change[1])
            self.interleaved_change = None

    async def execute(self, _env, sql, *bindings):
        self.interleave(sql)
        with self.db:
            return self.statement(sql, bindings)

    async def batch(self, _env, commands):
        self.interleave(commands[0][0])
        with self.db:
            return [self.statement(sql, bindings) for sql, bindings in commands]

    async def send(self):
        request = SimpleNamespace(method="POST", url=f"https://workdoe.com{THREAD_PATH}", headers={})
        return await self.worker.message_threads_api(request, THREAD_PATH)

    def saved_counts(self):
        return tuple(self.db.execute("""
            SELECT (SELECT COUNT(*) FROM messages), (SELECT COUNT(*) FROM idempotency_requests),
                   (SELECT COUNT(*) FROM thread_reads), (SELECT COUNT(*) FROM automation_events)
        """).fetchone())

    def prepare_standard_bid(self):
        with self.db:
            self.db.execute("""
                INSERT INTO jobs (id, client_id, title, category, city, state, zip_code, description,
                                  service_slug, service_zone_slug, bidding_closes_at, created_at, updated_at)
                SELECT 2, client_id, 'Clean the kitchen', 'House cleaning', city, state, zip_code, description,
                       'house-cleaning', 'arlington-county-va', '2030-01-01', created_at, updated_at
                FROM jobs WHERE id = 1
            """)
        return {"id": 2, "service_slug": "house-cleaning", "service_zone_slug": "arlington-county-va"}

    async def save_standard_bid(self, job):
        return await self.module.save_match_request(
            self.worker.env, job, 2,
            {"scope_note": "Clean kitchen surfaces", "price_range": "$80", "timeline": "Next week",
             "experience": "Interior cleaning", "questions": "", "availability": "Tuesday",
             "service_policy_acknowledgement": ""},
            "2026-01-02T00:00:00+00:00",
        )

    async def test_standard_bid_and_duplicate_keep_exactly_one_event_without_advisory(self):
        job = self.prepare_standard_bid()
        request_id = await self.save_standard_bid(job)
        self.assertEqual(request_id, 2)
        self.assertIsNone(await self.save_standard_bid(job))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM service_policy_acknowledgements").fetchone()[0], 0)
        events = self.db.execute("SELECT target_id, payload_json FROM automation_events").fetchall()
        self.assertEqual([(row[0], json.loads(row[1])) for row in events], [
            (request_id, {"job_id": 2, "contractor_id": 2, "status": "pending"}),
        ])

    async def test_bid_insert_enforces_an_inactive_service_zone_when_enabled(self):
        job = self.prepare_standard_bid()
        self.worker.env.WORKDOE_ENFORCE_SERVICE_ACTIVATION = "true"
        self.assertIsNone(await self.save_standard_bid(job))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM match_requests WHERE job_id = 2").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM automation_events").fetchone()[0], 0)
        self.db.executescript("""
            INSERT INTO contractor_profiles (user_id, business_name, updated_at)
            VALUES (2, 'Fixture contractor', '2026-01-01');
            INSERT INTO contractor_service_capabilities (contractor_id, service_slug, created_at)
            VALUES (2, 'house-cleaning', '2026-01-01');
            INSERT INTO contractor_service_zones (contractor_id, zone_slug, created_at)
            VALUES (2, 'arlington-county-va', '2026-01-01');
            UPDATE service_zone_activations
            SET status = 'active', minimum_eligible_contractors = 1,
                approved_at = '2026-01-01', reviewed_at = '2026-01-01'
            WHERE service_slug = 'house-cleaning' AND zone_slug = 'arlington-county-va';
        """)
        self.assertEqual(await self.save_standard_bid(job), 2)

    async def test_audit_failure_rolls_back_and_same_key_can_retry(self):
        self.db.executescript("""
            CREATE TRIGGER fail_reply_audit BEFORE INSERT ON automation_events
            WHEN NEW.event_type = 'message-created'
            BEGIN SELECT RAISE(ABORT, 'synthetic audit failure'); END;
        """)
        try:
            failed = await self.send()
        except sqlite3.IntegrityError:
            self.assertEqual(self.saved_counts(), (0, 0, 0, 0), "a failed audit left a partial reply")
            raise
        self.assertEqual(failed.status, 503)
        self.assertNotIn("synthetic audit failure", failed.body)
        self.assertEqual(self.saved_counts(), (0, 0, 0, 0))
        self.db.execute("DROP TRIGGER fail_reply_audit")

        created = await self.send()
        replay = await self.send()
        self.assertEqual(created.status, 201)
        self.assertEqual(replay.status, 200)
        self.assertEqual(json.loads(replay.body), json.loads(created.body) | {"replayed": True})
        self.assertEqual(self.saved_counts(), (1, 1, 1, 1))
        audit = self.db.execute("SELECT payload_json FROM automation_events").fetchone()[0]
        self.assertEqual(json.loads(audit), {"message_id": json.loads(created.body)["message_id"], "sender_id": 1})

    async def test_suspension_between_read_and_insert_denies_reply(self):
        self.interleaved_change = (
            "INSERT INTO messages", "UPDATE users SET status = 'suspended' WHERE id = 1",
        )
        self.assertEqual((await self.send()).status, 409)
        self.assertIsNone(self.interleaved_change)
        self.assertEqual(self.saved_counts(), (0, 0, 0, 0))

    def prepare_decision(self, *, status="pending"):
        self.db.executescript("""
            DELETE FROM threads;
            INSERT INTO users (id, email, password_hash, role, display_name, created_at)
            VALUES (3, 'other@example.invalid', '', 'contractor', 'Other provider', '2026-01-01');
            INSERT INTO match_requests
                (id, job_id, contractor_id, scope_note, price_range, timeline, experience, availability,
                 status, created_at, updated_at)
            SELECT 2, job_id, 3, scope_note, price_range, timeline, experience, availability,
                   'pending', created_at, updated_at FROM match_requests WHERE id = 1;
        """)
        with self.db:
            self.db.execute("UPDATE match_requests SET status = ? WHERE id = 1", (status,))

    def decision_state(self):
        statuses = tuple(row[0] for row in self.db.execute("SELECT status FROM match_requests ORDER BY id"))
        counts = self.db.execute("""
            SELECT (SELECT COUNT(*) FROM threads), (SELECT COUNT(*) FROM messages),
                   (SELECT COUNT(*) FROM automation_events)
        """).fetchone()
        return (statuses, *counts)

    async def decide(self, action="approve"):
        return await self.worker.decide_match_request(
            SimpleNamespace(method="POST"), f"/api/match-requests/1/{action}",
        )

    async def test_approval_rolls_back_all_writes_and_retries_once(self):
        self.prepare_decision()
        for operation in (
            "INSERT ON threads",
            "INSERT ON messages",
            "INSERT ON automation_events",
            "UPDATE ON match_requests WHEN NEW.status = 'rejected'",
        ):
            with self.subTest(operation=operation):
                self.db.executescript(f"""
                    CREATE TRIGGER fail_decision BEFORE {operation}
                    BEGIN SELECT RAISE(ABORT, 'synthetic decision failure'); END;
                """)
                try:
                    response = await self.decide()
                except sqlite3.IntegrityError:
                    self.assertEqual(self.decision_state(), (("pending", "pending"), 0, 0, 0))
                    raise
                finally:
                    self.db.execute("DROP TRIGGER fail_decision")
                self.assertEqual(response.status, 503)
                self.assertNotIn("synthetic decision failure", response.body)
                self.assertEqual(self.decision_state(), (("pending", "pending"), 0, 0, 0))
        first = await self.decide()
        self.assertEqual(first.status, 200)
        self.assertEqual((await self.decide()).body, first.body)
        self.assertEqual((await self.decide("reject")).status, 409)
        self.assertEqual(self.decision_state(), (("approved", "rejected"), 1, 1, 1))
        event = self.db.execute("SELECT payload_json FROM automation_events").fetchone()[0]
        self.assertEqual(json.loads(event)["closed_offer_count"], 1)
        self.assertEqual(json.loads(first.body)["url"], "/messages/1")

    async def test_approval_rechecks_project_and_participant_status(self):
        self.prepare_decision()
        for change, restore in (
            ("UPDATE jobs SET status = 'hidden'", "UPDATE jobs SET status = 'open'"),
            ("UPDATE users SET status = 'suspended' WHERE id = 1", "UPDATE users SET status = 'active' WHERE id = 1"),
            ("UPDATE users SET status = 'suspended' WHERE id = 2", "UPDATE users SET status = 'active' WHERE id = 2"),
        ):
            with self.subTest(change=change):
                self.interleaved_change = ("UPDATE match_requests", change)
                self.assertEqual((await self.decide()).status, 409)
                self.assertIsNone(self.interleaved_change)
                self.assertEqual(self.decision_state(), (("pending", "pending"), 0, 0, 0))
                with self.db:
                    self.db.execute(restore)

    async def test_rejection_rolls_back_with_audit_and_never_creates_thread(self):
        self.prepare_decision()
        self.db.executescript("""
            CREATE TRIGGER fail_rejection BEFORE INSERT ON automation_events
            BEGIN SELECT RAISE(ABORT, 'synthetic rejection failure'); END;
        """)
        try:
            response = await self.decide("reject")
        except sqlite3.IntegrityError:
            self.assertEqual(self.decision_state(), (("pending", "pending"), 0, 0, 0))
            raise
        self.assertEqual(response.status, 503)
        self.assertNotIn("synthetic rejection failure", response.body)
        self.assertEqual(self.decision_state(), (("pending", "pending"), 0, 0, 0))
        self.db.execute("DROP TRIGGER fail_rejection")
        with self.db:
            self.db.execute("UPDATE jobs SET status = 'hidden'")
        rejected = await self.decide("reject")
        self.assertEqual(rejected.status, 200)
        self.assertEqual(json.loads(rejected.body)["url"], "/client/jobs/1")
        self.assertEqual((await self.decide("reject")).body, rejected.body)
        self.assertEqual(self.decision_state(), (("rejected", "pending"), 0, 0, 1))

    async def test_legacy_repair_requires_active_match_and_commits_both_writes(self):
        self.prepare_decision(status="approved")
        with self.db:
            self.db.execute("UPDATE users SET status = 'suspended' WHERE id = 2")
        self.assertEqual((await self.decide()).status, 409)
        self.assertEqual(self.decision_state(), (("approved", "pending"), 0, 0, 0))
        self.db.executescript("""
            UPDATE users SET status = 'active' WHERE id = 2;
            CREATE TRIGGER fail_repair BEFORE INSERT ON messages
            BEGIN SELECT RAISE(ABORT, 'synthetic repair failure'); END;
        """)
        failure = await self.decide()
        self.assertEqual(failure.status, 503)
        self.assertNotIn("synthetic repair failure", failure.body)
        self.assertEqual(self.decision_state(), (("approved", "pending"), 0, 0, 0))
        self.db.execute("DROP TRIGGER fail_repair")
        repaired = await self.decide()
        self.assertEqual(repaired.status, 200)
        self.assertEqual((await self.decide()).body, repaired.body)
        self.assertEqual(self.decision_state(), (("approved", "pending"), 1, 1, 0))

    async def test_lost_commit_confirmation_preserves_completed_receipt(self):
        async def lose_confirmation(env, commands):
            await self.batch(env, commands)
            raise OSError("synthetic response loss after commit")

        self.module.db_batch = lose_confirmation
        failed = await self.send()
        self.assertEqual(failed.status, 503)
        self.assertNotIn("synthetic response loss", failed.body)
        self.module.db_batch = self.batch
        replay = await self.send()
        self.assertEqual(replay.status, 200)
        self.assertTrue(json.loads(replay.body)["replayed"])
        self.assertEqual(self.saved_counts(), (1, 1, 1, 1))

    async def test_non_string_reply_body_returns_field_error_without_reservation(self):
        for value in (None, False, 0, 1, [], ["text"], {}, {"value": "text"}):
            with self.subTest(value=value):
                self.module.request_json_object.return_value = REPLY | {"body": value}
                response = await self.send()
                self.assertEqual(response.status, 400)
                self.assertTrue(json.loads(response.body)["field_errors"]["body"])
        self.assertEqual(self.saved_counts(), (0, 0, 0, 0))
