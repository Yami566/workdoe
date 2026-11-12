"""Rehearse schema behavior on synthetic SQLite data, never an account operation."""

import asyncio
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from test_cloudflare_release import load_worker_entry_module

TESTS = Path(__file__).resolve().parent
MIGRATIONS = TESTS.parent / "cloudflare" / "d1" / "migrations"

# Scope groups are review prompts, not instructions to delete or export a row.
SCOPE_GROUPS = {
    "identity and private profile": {
        "users", "client_profiles", "client_saved_locations", "client_project_templates",
        "contractor_profiles", "contractor_credentials", "contractor_lead_preferences",
        "contractor_proposal_templates", "contractor_service_capabilities", "contractor_service_zones",
        "contractor_photos", "password_reset_tokens", "idempotency_requests",
    },
    "shared marketplace": {
        "jobs", "job_scope_answers", "job_photos", "job_lead_feedback", "match_requests",
        "match_completions", "match_reviews", "match_review_reports", "messages", "threads",
        "thread_reads", "repeat_provider_invitations", "contractor_lead_alert_deliveries",
        "service_policy_acknowledgements",
    },
    "indirect or partially linked": {
        "login_codes", "job_drafts", "job_draft_scope_answers", "reports",
        "automation_events", "moderation_actions",
    },
    "catalog and operator reference": {
        "categories", "service_groups", "service_types", "service_aliases", "service_zones",
        "service_zone_activations",
    },
}


class AccountRequestScopeTests(TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            self.db.executescript(migration.read_text(encoding="utf-8"))
        self.db.executescript((TESTS / "native_worker" / "seed.sql").read_text(encoding="utf-8"))
        self.db.executescript((TESTS / "fixtures" / "account_request_scope.sql").read_text(encoding="utf-8"))
        self.assertEqual(self.values("PRAGMA foreign_keys"), [1])
        self.assertEqual(self.values("PRAGMA foreign_key_check"), [])

    def values(self, statement, parameters=()):
        return [row[0] for row in self.db.execute(statement, parameters)]

    def test_every_migrated_application_table_has_a_scope_class(self):
        tables = self.values("""
            SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT GLOB 'sqlite_*'
        """)
        self.assertCountEqual(tables, [table for tables in SCOPE_GROUPS.values() for table in tables])

    def test_consumer_delete_would_remove_shared_content_but_leave_indirect_records(self):
        self.db.execute("DELETE FROM users WHERE id = ?", (1,))
        self.assertEqual(self.values("SELECT id FROM jobs ORDER BY id"), [2, 3])
        self.assertEqual(self.values("SELECT id FROM threads ORDER BY id"), [2, 3])
        self.assertEqual(self.values("SELECT id FROM match_requests WHERE contractor_id = 2"), [3])
        self.assertEqual(self.values("SELECT id FROM messages WHERE sender_id = 2"), [6])
        self.assertEqual(self.values("SELECT match_request_id FROM match_completions ORDER BY match_request_id"), [2, 3])
        self.assertEqual(self.values("SELECT id FROM service_policy_acknowledgements"), [])
        self.assertEqual(self.values("SELECT id FROM job_photos"), [])
        self.assertEqual(self.values("SELECT id FROM contractor_photos"), [1])

        self.assertEqual(self.values("SELECT id FROM reports WHERE status = 'open' ORDER BY id"), [1, 2, 4])
        self.assertEqual(self.values("SELECT target_id FROM moderation_actions WHERE target_type = 'job'"), [1])
        self.assertEqual(self.values("SELECT target_id FROM automation_events WHERE target_type = 'user'"), [1])
        self.assertEqual(self.values("SELECT id FROM login_codes WHERE email = ?", ("client@native.invalid",)), [1])
        self.assertEqual(self.values("SELECT selected_job_id FROM login_codes WHERE id = 2"), [None])
        self.assertEqual(self.values("SELECT id FROM job_drafts"), [1])
        self.assertEqual(self.values("SELECT draft_id FROM job_draft_scope_answers"), [1])
        self.assertEqual(self.values("PRAGMA foreign_key_check"), [])

    def test_contractor_delete_would_remove_both_parties_messages_without_deleting_their_projects(self):
        self.db.execute("DELETE FROM users WHERE id = ?", (2,))
        self.assertEqual(self.values("SELECT id FROM jobs ORDER BY id"), [1, 2, 3])
        self.assertEqual(self.values("SELECT id FROM threads"), [2])
        self.assertEqual(self.values("SELECT id FROM match_requests"), [2])
        self.assertEqual(self.values("SELECT id FROM messages ORDER BY id"), [3, 4])
        self.assertEqual(self.values("SELECT id FROM reports ORDER BY id"), [3, 4])
        self.assertEqual(self.values("SELECT id FROM contractor_photos"), [])
        self.assertEqual(self.values("SELECT id FROM job_photos"), [1])
        self.assertEqual(self.values("SELECT id FROM service_policy_acknowledgements"), [1])
        self.assertEqual(self.values("PRAGMA foreign_key_check"), [])

    def test_pre_delete_snapshot_would_restore_identity_content_and_media_references(self):
        with sqlite3.connect(":memory:", isolation_level=None) as snapshot:
            self.addCleanup(snapshot.close)
            self.db.backup(snapshot)
            self.db.execute("DELETE FROM users WHERE id = ?", (1,))
            self.assertEqual(self.values("SELECT id FROM users WHERE id = 1"), [])
            self.assertEqual(self.values("SELECT id FROM job_photos WHERE job_id = 1"), [])
            snapshot.backup(self.db)
        self.assertEqual(self.values("SELECT status FROM users WHERE id = 1"), ["active"])
        self.assertEqual(self.values("SELECT id FROM messages WHERE thread_id = 1 ORDER BY id"), [1, 2])
        self.assertEqual(self.values("SELECT stored_path FROM job_photos WHERE job_id = 1"), [
            "jobs/1/account-request-fixture.webp",
        ])
        self.assertEqual(self.values("PRAGMA foreign_key_check"), [])

    def test_numeric_account_id_alone_cannot_identify_an_erasure_replay_target(self):
        highest_id = self.values("SELECT MAX(id) FROM users")[0]
        self.assertEqual(highest_id, 7)
        self.db.execute("DELETE FROM users WHERE id = ?", (highest_id,))
        new_account = self.db.execute("""
            INSERT INTO users (email, password_hash, role, display_name, auth_provider, external_subject, created_at)
            VALUES ('replacement@native.invalid', '', 'contractor', 'Replacement fixture',
                    'clerk', 'user_native_replacement', '2000-01-02')
        """)
        self.assertEqual(new_account.lastrowid, highest_id)
        self.assertEqual(self.values("SELECT external_subject FROM users WHERE id = ?", (highest_id,)), [
            "user_native_replacement",
        ])

    def test_draft_expiry_denies_resume_but_does_not_purge_rows(self):
        worker = load_worker_entry_module()
        token = "account-request-fixture"
        env = SimpleNamespace(WORKDOE_SECRET_KEY="s" * 32)
        incoming = SimpleNamespace(headers={"Cookie": f"workdoe_job_draft={token}"})
        token_hash = worker.job_draft_token_hash(token, env.WORKDOE_SECRET_KEY)
        self.db.execute("UPDATE job_drafts SET token_hash = ? WHERE id = 1", (token_hash,))
        plans = []

        async def read_fixture(_env, sql, *parameters):
            self.assertTrue(sql.strip().startswith("SELECT"))
            plans.append([row["detail"] for row in self.db.execute("EXPLAIN QUERY PLAN " + sql, parameters)])
            return {"success": True, "results": [dict(row) for row in self.db.execute(sql, parameters)]}

        with (
            patch.object(worker, "db_run", read_fixture),
            patch.object(worker, "utc_now", return_value="2026-11-09"),
        ):
            self.assertIsNone(asyncio.run(worker.job_draft_for_request(env, incoming)))
            self.assertEqual(self.values("SELECT id FROM job_drafts"), [1])
            self.assertEqual(self.values("SELECT draft_id FROM job_draft_scope_answers"), [1])
            self.assertEqual(len(plans), 1)
            self.db.execute("UPDATE job_drafts SET expires_at = '2099-01-01' WHERE id = 1")
            draft = asyncio.run(worker.job_draft_for_request(env, incoming))
            self.assertEqual(draft["id"], 1)
            self.assertEqual(draft["scope_answers"], {"fixture-question": "fixture-answer"})
            self.assertEqual(len(plans), 2)
            self.assertTrue(any("SEARCH draft USING INDEX" in step and "token_hash=?" in step for step in plans[-1]))
            self.assertTrue(any("SEARCH job_draft_scope_answers USING INDEX" in step for step in plans[-1]))
