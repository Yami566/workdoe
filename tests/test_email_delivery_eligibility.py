from __future__ import annotations

import json
import sqlite3
import unittest
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from test_cloudflare_release import ROOT, load_worker_entry_module


class EmailDeliveryEligibilityTests(unittest.IsolatedAsyncioTestCase):
    @contextmanager
    def fixture(self, kind):
        worker = load_worker_entry_module()
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            for migration in sorted((ROOT / "cloudflare/d1/migrations").glob("*.sql")):
                db.executescript(migration.read_text(encoding="utf-8"))
            now = datetime.now(UTC)
            timestamp = now.isoformat()
            future = (now + timedelta(days=3)).isoformat()
            for user_id, role in ((1, "client"), (2, "contractor")):
                db.execute(
                    """INSERT INTO users
                    (id, email, password_hash, role, display_name, email_verified, created_at)
                    VALUES (?, ?, '', ?, 'Current fixture label', 1, ?)""",
                    (user_id, f"fixture-{user_id}@example.invalid", role, timestamp),
                )
            db.execute(
                """INSERT INTO client_profiles
                (user_id, organization_name, notification_preference, email_reminder_consent_at)
                VALUES (1, 'Fixture workspace', 'email', ?)""", (timestamp,),
            )
            db.execute(
                """INSERT INTO contractor_profiles (user_id, business_name, updated_at)
                VALUES (2, 'Fixture contractor', ?)""", (timestamp,),
            )
            db.execute(
                """INSERT INTO jobs
                (id, client_id, title, category, city, state, zip_code, description,
                 service_slug, service_group_slug, service_zone_slug, bidding_closes_at,
                 created_at, updated_at)
                VALUES (1, 1, 'Current public title', 'Landscaping', 'Arlington', 'VA',
                        '22201', 'Synthetic scope.', 'lawn-mowing', 'outdoor-yard',
                        'arlington-county-va', ?, ?, ?)""", (future, timestamp, timestamp),
            )
            db.execute(
                """INSERT INTO contractor_lead_preferences
                (contractor_id, saved_at, updated_at, lead_alert_preference, lead_alert_consent_at)
                VALUES (2, ?, ?, 'email', ?)""", (timestamp, timestamp, timestamp),
            )
            db.execute(
                """INSERT INTO contractor_service_capabilities
                (contractor_id, service_slug, created_at) VALUES (2, 'lawn-mowing', ?)""",
                (timestamp,),
            )
            db.execute(
                """INSERT INTO contractor_service_zones
                (contractor_id, zone_slug, created_at) VALUES (2, 'arlington-county-va', ?)""", (timestamp,),
            )
            body = {
                "type": kind, "to": "fixture-2@example.invalid",
                "job_title": "Stale queued title", "location": "Stale queued area",
                "job_url": "https://workdoe.com/jobs/1",
            }
            if kind == "stale-match-reminder":
                db.execute(
                    """INSERT INTO match_requests
                    (id, job_id, contractor_id, scope_note, price_range, timeline,
                     experience, availability, status, created_at, updated_at)
                    VALUES (1, 1, 2, 'Fixture scope', '$100', 'One day', 'Fixture',
                            'Next week', 'pending', ?, ?)""", (timestamp, timestamp),
                )
                body.update({"to": "fixture-1@example.invalid", "match_request_id": 1})
            elif kind == "repeat-provider-invitation":
                db.execute(
                    """INSERT INTO repeat_provider_invitations
                    (id, job_id, client_id, contractor_id, service_slug, status, created_at, updated_at)
                    VALUES (1, 1, 1, 2, 'lawn-mowing', 'pending', ?, ?)""", (timestamp, timestamp),
                )
                body.update({"contractor_id": 2, "job_id": 1})
            else:
                db.execute(
                    """INSERT INTO contractor_lead_alert_deliveries
                    (id, contractor_id, job_id, status, created_at, updated_at)
                    VALUES (1, 2, 1, 'queued', ?, ?)""", (timestamp, timestamp),
                )
                body["lead_alert_delivery_id"] = 1
            db.commit()
            queries = []

            async def execute(_env, sql, *parameters):
                queries.append((sql, parameters))
                cursor = db.execute(sql, parameters)
                rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
                db.commit()
                return {"results": rows, "meta": {"changes": cursor.rowcount}}

            sender = AsyncMock(return_value={"messageId": "synthetic-receipt"})
            fixture = SimpleNamespace(
                db=db, worker=worker, body=body, queries=queries, sender=sender,
                audit=AsyncMock(), receipt=SimpleNamespace(ack=Mock(), retry=Mock(), attempts=1),
                env=SimpleNamespace(
                    WORKDOE_MARKETPLACE_EMAIL_ENABLED="true",
                    EMAIL=SimpleNamespace(send=sender), WORKDOE_SECRET_KEY="s" * 32,
                ),
            )
            with patch.object(worker, "db_run", execute), patch.object(worker, "record_event", fixture.audit):
                yield fixture

    async def deliver(self, fixture):
        await fixture.worker.process_email_queue_message(
            fixture.env, fixture.receipt, fixture.body, "workdoe-email",
        )

    def suppressed(self, fixture):
        fixture.sender.assert_not_awaited()
        fixture.receipt.ack.assert_called_once_with()
        fixture.receipt.retry.assert_not_called()
        call = fixture.audit.await_args
        self.assertEqual(call.args[1], "email-message-suppressed")
        serialized = json.dumps(call.kwargs)
        self.assertNotIn("@", serialized)
        self.assertNotIn("title", serialized)
        self.assertNotIn("location", serialized)

    async def test_opt_out_after_queueing_prevents_delivery(self):
        for kind, sql in (
            ("stale-match-reminder", "UPDATE client_profiles SET notification_preference = 'workdoe'"),
            ("contractor-new-lead", "UPDATE contractor_lead_preferences SET lead_alert_preference = 'workdoe'"),
        ):
            with self.subTest(kind=kind), self.fixture(kind) as fixture:
                fixture.db.execute(sql)
                await self.deliver(fixture)
                self.suppressed(fixture)

    async def test_hidden_closed_or_inactive_projects_never_send_queued_notices(self):
        for kind in ("stale-match-reminder", "repeat-provider-invitation", "contractor-new-lead"):
            for sql in (
                "UPDATE jobs SET status = 'hidden'",
                "UPDATE jobs SET status = 'closed'",
                "UPDATE users SET status = 'suspended' WHERE id = 1",
                "UPDATE users SET status = 'suspended' WHERE id = 2",
            ):
                with self.subTest(kind=kind, sql=sql), self.fixture(kind) as fixture:
                    fixture.db.execute(sql)
                    await self.deliver(fixture)
                    self.suppressed(fixture)

    async def test_changed_or_unverified_recipient_never_sends_to_queued_address(self):
        for kind in ("stale-match-reminder", "repeat-provider-invitation", "contractor-new-lead"):
            user_id = 1 if kind == "stale-match-reminder" else 2
            for assignment in ("email = 'changed@example.invalid'", "email_verified = 0"):
                with self.subTest(kind=kind, assignment=assignment), self.fixture(kind) as fixture:
                    fixture.db.execute(f"UPDATE users SET {assignment} WHERE id = ?", (user_id,))
                    await self.deliver(fixture)
                    self.suppressed(fixture)

    async def test_eligible_notices_use_current_public_fields_not_queued_text(self):
        for kind in ("stale-match-reminder", "repeat-provider-invitation", "contractor-new-lead"):
            with self.subTest(kind=kind), self.fixture(kind) as fixture:
                await self.deliver(fixture)
                fixture.sender.assert_awaited_once()
                email = fixture.sender.await_args.args[0]
                self.assertIn("Current public title", email["text"])
                self.assertIn("Arlington, VA", email["text"])
                self.assertNotIn("Stale queued", json.dumps(email))
                self.assertNotIn("22201", json.dumps(email))
                fixture.receipt.ack.assert_called_once_with()
                fixture.receipt.retry.assert_not_called()
                reads = [sql for sql, _ in fixture.queries if sql.lstrip().startswith("SELECT")]
                self.assertEqual(len(reads), 1)
                self.assertIn("LIMIT", reads[0])

    async def test_non_pending_bid_or_invitation_and_sent_alert_are_suppressed(self):
        for kind, sql in (
            ("stale-match-reminder", "UPDATE match_requests SET status = 'rejected'"),
            ("repeat-provider-invitation", "UPDATE repeat_provider_invitations SET status = 'declined'"),
            ("contractor-new-lead", "UPDATE contractor_lead_alert_deliveries SET status = 'sent'"),
        ):
            with self.subTest(kind=kind), self.fixture(kind) as fixture:
                fixture.db.execute(sql)
                await self.deliver(fixture)
                self.suppressed(fixture)

    async def test_saved_fit_and_consent_are_rechecked_before_lead_delivery(self):
        for sql in (
            "UPDATE contractor_lead_preferences SET lead_alert_consent_at = NULL",
            "UPDATE contractor_lead_preferences SET saved_at = NULL",
            "UPDATE contractor_lead_preferences SET availability_status = 'unavailable'",
            "UPDATE contractor_lead_preferences SET saved_query = 'not a match'",
            "UPDATE contractor_lead_preferences SET saved_category = 'Moving'",
            "UPDATE contractor_lead_preferences SET saved_service_group_slug = 'cleaning-upkeep'",
            "UPDATE contractor_lead_preferences SET saved_service_slug = 'window-cleaning'",
            "DELETE FROM contractor_service_capabilities",
            "DELETE FROM contractor_service_zones",
        ):
            with self.subTest(sql=sql), self.fixture("contractor-new-lead") as fixture:
                fixture.db.execute(sql)
                await self.deliver(fixture)
                self.suppressed(fixture)

    async def test_missing_or_invalid_references_drop_without_database_or_provider_access(self):
        for kind, field in (
            ("stale-match-reminder", "match_request_id"),
            ("repeat-provider-invitation", "contractor_id"),
            ("repeat-provider-invitation", "job_id"),
            ("contractor-new-lead", "lead_alert_delivery_id"),
        ):
            for value in (None, True, 1.5, 0, -1, "1 OR 1=1"):
                with self.subTest(kind=kind, field=field, value=value), self.fixture(kind) as fixture:
                    fixture.body[field] = value
                    await self.deliver(fixture)
                    self.suppressed(fixture)
                    self.assertEqual(fixture.queries, [])

    async def test_database_failure_never_calls_provider_or_logs_private_queue_body(self):
        with self.fixture("stale-match-reminder") as fixture:
            with patch.object(fixture.worker, "db_run", AsyncMock(side_effect=RuntimeError("private fixture data"))):
                await self.deliver(fixture)
            fixture.sender.assert_not_awaited()
            fixture.receipt.ack.assert_not_called()
            fixture.receipt.retry.assert_called_once_with()
            self.assertNotIn("private fixture data", json.dumps(fixture.audit.await_args.kwargs))

    async def test_deleted_source_or_missing_consent_is_suppressed(self):
        for kind, sql in (
            ("stale-match-reminder", "DELETE FROM match_requests"),
            ("stale-match-reminder", "UPDATE client_profiles SET email_reminder_consent_at = NULL"),
            ("repeat-provider-invitation", "DELETE FROM repeat_provider_invitations"),
            ("contractor-new-lead", "DELETE FROM contractor_lead_alert_deliveries"),
        ):
            with self.subTest(kind=kind, sql=sql), self.fixture(kind) as fixture:
                fixture.db.execute(sql)
                await self.deliver(fixture)
                self.suppressed(fixture)

    async def test_expired_window_or_existing_bid_suppresses_contractor_notices(self):
        for kind in ("repeat-provider-invitation", "contractor-new-lead"):
            for case in ("expired", "own-bid", "full", "approved"):
                with self.subTest(kind=kind, case=case), self.fixture(kind) as fixture:
                    if case == "expired":
                        fixture.db.execute("UPDATE jobs SET bidding_closes_at = '2000-01-01'")
                    else:
                        fixture.db.execute(
                            """INSERT INTO users (id, email, password_hash, role, display_name, created_at)
                            VALUES (3, 'other@example.invalid', '', 'contractor', 'Other fixture', '2000-01-01')""",
                        )
                        fixture.db.execute(
                            """INSERT INTO match_requests
                            (job_id, contractor_id, scope_note, price_range, timeline, experience,
                             availability, status, created_at, updated_at)
                            VALUES (1, ?, 'Fixture', '$100', 'One day', 'Fixture', 'Next week', ?,
                                    '2000-01-01', '2000-01-01')""",
                            (2 if case == "own-bid" else 3, "approved" if case == "approved" else "pending"),
                        )
                        if case == "full":
                            fixture.db.execute("UPDATE jobs SET bid_limit = 1")
                    await self.deliver(fixture)
                    self.suppressed(fixture)

    async def test_delivery_queries_use_indexed_reference_lookups(self):
        for kind in ("stale-match-reminder", "repeat-provider-invitation", "contractor-new-lead"):
            with self.subTest(kind=kind), self.fixture(kind) as fixture:
                query, parameters = fixture.worker.marketplace_email_delivery_query(fixture.body)
                plans = [row["detail"] for row in fixture.db.execute("EXPLAIN QUERY PLAN " + query, parameters)]
                self.assertTrue(any("SEARCH" in step for step in plans))
                self.assertFalse(any(step.startswith("SCAN ") for step in plans), plans)
                await self.deliver(fixture)
                fixture.sender.assert_awaited_once()

    async def test_legacy_private_text_is_not_copied_into_notifications(self):
        for kind in ("stale-match-reminder", "repeat-provider-invitation", "contractor-new-lead"):
            for sql in (
                "UPDATE jobs SET title = 'Call private@example.invalid'",
                "UPDATE jobs SET city = '123 Example Street'",
            ):
                with self.subTest(kind=kind, sql=sql), self.fixture(kind) as fixture:
                    fixture.db.execute(sql)
                    await self.deliver(fixture)
                    self.suppressed(fixture)
        with self.fixture("stale-match-reminder") as fixture:
            fixture.db.execute("UPDATE users SET display_name = '202-555-0173' WHERE id = 2")
            await self.deliver(fixture)
            self.suppressed(fixture)
