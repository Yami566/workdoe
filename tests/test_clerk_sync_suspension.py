from __future__ import annotations

import base64
import json
import secrets
import sqlite3
import time
import unittest
from contextlib import closing, contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest import mock

from test_cloudflare_release import (
    ROOT,
    load_clerk_webhooks_module,
    load_worker_entry_module,
)
from worker_http_fixture import BodyStream


def event(event_type="user.updated", *, email="fixture-2@example.invalid", **flags):
    data = {"id": "user_fixture_contractor", **flags}
    if email:
        data.update({
            "primary_email_address_id": "email_fixture",
            "email_addresses": [{"id": "email_fixture", "email_address": email,
                                 "verification": {"status": "verified"}}],
        })
    return {"object": "event", "type": event_type, "data": data}


class ClerkSyncSuspensionTests(unittest.IsolatedAsyncioTestCase):
    @contextmanager
    def fixture(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            for migration in sorted((ROOT / "cloudflare" / "d1" / "migrations").glob("*.sql")):
                db.executescript(migration.read_text(encoding="utf-8"))
            timestamp = datetime.now(UTC).isoformat(timespec="seconds")
            for user_id, role in ((1, "client"), (2, "contractor"), (3, "client"), (4, "admin"), (5, "contractor")):
                db.execute(
                    """INSERT INTO users
                    (id, email, password_hash, role, display_name, status, email_verified,
                     auth_provider, external_subject, created_at)
                    VALUES (?, ?, '', ?, 'Fixture label', 'active', 1, ?, ?, ?)""",
                    (user_id, f"fixture-{user_id}@example.invalid", role,
                     "clerk" if user_id == 2 else "local",
                     "user_fixture_contractor" if user_id == 2 else None, timestamp),
                )
            db.execute(
                """INSERT INTO jobs
                (id, client_id, title, category, city, state, zip_code, description,
                 status, bidding_closes_at, created_at, updated_at)
                VALUES (1, 1, 'Fixture task', 'Landscaping', 'Arlington', 'VA', '22201',
                        'Synthetic work scope.', 'open', ?, ?, ?)""",
                ((datetime.now(UTC) + timedelta(days=2)).isoformat(), timestamp, timestamp),
            )
            db.commit()
            fixture = SimpleNamespace(db=db, timestamp=timestamp, statements=[], prefix="", change=None, interleaved=0)
            fixture.module = load_worker_entry_module()
            fixture.worker = SimpleNamespace(env=SimpleNamespace(DB=object()))

            async def execute(_env, sql, *bindings, commit=True):
                fixture.statements.append((sql, bindings))
                if fixture.change and " ".join(sql.split()).startswith(fixture.prefix):
                    change, fixture.change = fixture.change, None
                    db.execute(*change)
                    db.commit()
                    fixture.interleaved += 1
                before = db.total_changes
                cursor = db.execute(sql, bindings)
                rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
                if commit:
                    db.commit()
                return {"results": rows, "meta": {"changes": db.total_changes - before, "last_row_id": cursor.lastrowid}}

            async def execute_batch(env, commands):
                with db:
                    return [await execute(env, sql, *bindings, commit=False) for sql, bindings in commands]

            def pending():
                db.execute(
                    """INSERT INTO match_requests
                    (id, job_id, contractor_id, scope_note, price_range, timeline, experience,
                     availability, status, created_at, updated_at)
                    VALUES (1, 1, 2, 'Fixture scope', '$100', 'One day', 'Fixture experience',
                            'Next week', 'pending', ?, ?)""", (timestamp, timestamp),
                )
                db.commit()

            fixture.module.db_run = execute
            fixture.module.db_batch = execute_batch
            fixture.pending = pending
            fixture.count = lambda _table: db.execute("SELECT COUNT(*) FROM match_requests").fetchone()[0]
            yield fixture

    def user(self, fixture):
        return dict(fixture.db.execute("SELECT * FROM users WHERE id = 2").fetchone())

    async def sync(self, fixture, payload):
        return await fixture.module.sync_linked_clerk_user(fixture.worker.env, payload)

    def webhook_request(self, fixture, raw, *, body=None, length=None, valid=True):
        fixture_key = "whsec_" + base64.b64encode(secrets.token_bytes(24)).decode("ascii")
        fixture.worker.env.CLERK_WEBHOOK_SECRET = fixture_key
        fixture.worker.env.WORKDOE_ENV = "local"
        message_id = "msg_synthetic_fixture"
        timestamp = str(int(time.time()))
        signature = load_clerk_webhooks_module().svix_signature(
            secret=fixture_key, message_id=message_id, timestamp=timestamp, raw_body=raw,
        )
        return SimpleNamespace(
            method="POST", body=body if body is not None else BodyStream([raw]),
            headers={
                "Content-Length": str(len(raw) if length is None else length),
                "svix-id": message_id, "svix-timestamp": timestamp,
                "svix-signature": f"v1,{signature if valid else 'invalid'}",
            },
        )

    async def test_webhook_rejects_bounds_and_bad_signatures_without_database_access(self):
        with self.fixture() as fixture:
            raw = json.dumps(event()).encode()
            handler = fixture.module.Default.handle_clerk_webhook
            chunks = fixture.module.MAX_CLERK_WEBHOOK_BODY_CHUNKS
            non_ascii_signature = self.webhook_request(fixture, raw)
            non_ascii_signature.headers["svix-signature"] = "v1,caf\u00e9"
            for label, request, status, canceled in (
                ("oversized header", self.webhook_request(
                    fixture, raw, length=fixture.module.MAX_CLERK_WEBHOOK_BODY_BYTES + 1,
                ), 413, False),
                ("longer than declared", self.webhook_request(fixture, raw, length=len(raw) - 1), 400, True),
                ("shorter than declared", self.webhook_request(fixture, raw, length=len(raw) + 1), 400, False),
                ("too many chunks", self.webhook_request(fixture, raw, body=BodyStream([b""] * chunks)), 400, True),
                ("stalled", self.webhook_request(fixture, raw, body=BodyStream([], stall=True)), 408, True),
                ("bad signature", self.webhook_request(fixture, raw, valid=False), 400, False),
                ("non-ASCII signature", non_ascii_signature, 400, False),
                ("signed malformed data", self.webhook_request(
                    fixture, b'{"object":"event","type":"user.deleted","data":null}',
                ), 400, False),
            ):
                with self.subTest(label=label), mock.patch.object(fixture.module, "CLERK_WEBHOOK_BODY_TIMEOUT_SECONDS", 0.05):
                    response = await handler(fixture.worker, request)
                    self.assertEqual(response.status, status)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(request.body.released, status != 413)
                    self.assertEqual(request.body.canceled, canceled)
                    self.assertFalse(fixture.statements)
            self.assertEqual(self.user(fixture)["status"], "active")

    async def test_webhook_verifies_original_bytes_and_keeps_provider_identity_out_of_audit(self):
        with self.fixture() as fixture:
            fixture.pending()
            payload = {**event("user.deleted", email=""), "id": "evt_private_fixture"}
            payload["data"]["private_metadata"] = {"fixture": "caf\u00e9@example.invalid"}
            raw = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
            request = self.webhook_request(fixture, raw, body=BodyStream([raw[:37], raw[37:]]))
            handler = fixture.module.Default.handle_clerk_webhook
            response = await handler(fixture.worker, request)
            self.assertEqual(response.status, 202)
            self.assertEqual(self.user(fixture)["status"], "suspended")
            self.assertEqual(fixture.count("match_requests"), 1)
            [audit] = fixture.db.execute("""
                SELECT event_type, target_type, payload_json FROM automation_events
                WHERE event_type = 'clerk-webhook-verified'
            """).fetchall()
            self.assertEqual((audit["event_type"], audit["target_type"]), ("clerk-webhook-verified", "user.deleted"))
            self.assertEqual(json.loads(audit["payload_json"]), {"sync": {"action": "status-updated", "user_id": 2}})
            self.assertEqual(tuple(fixture.db.execute("""
                SELECT target_id, payload_json FROM automation_events WHERE event_type = 'clerk-provider-restriction'
            """).fetchone()), (2, "{}"))

            fixture.statements.clear()
            raw = json.dumps(event("session.created")).encode()
            response = await handler(fixture.worker, self.webhook_request(fixture, raw))
            self.assertEqual(response.status, 202)
            self.assertFalse(fixture.statements)

    async def test_routine_webhook_never_reactivates_local_suspension(self):
        for event_type in ("user.updated", "user.created"):
            for email in ("fixture-2@example.invalid", ""):
                with self.subTest(event_type=event_type, email_present=bool(email)), self.fixture() as fixture:
                    fixture.db.execute("UPDATE users SET status = 'suspended' WHERE id = 2")
                    fixture.db.commit()
                    await self.sync(fixture, event(event_type, email=email))
                    self.assertEqual(self.user(fixture)["status"], "suspended")

    async def test_provider_disabling_events_still_suspend_active_account(self):
        for payload in (event("user.deleted", email=""), event(banned=True), event(locked=True), event(disabled=True)):
            with self.subTest(event_type=payload["type"], flags=payload["data"]), self.fixture() as fixture:
                await self.sync(fixture, payload)
                self.assertEqual(self.user(fixture)["status"], "suspended")

    async def test_clerk_reactivation_requires_exact_unrestricted_provider_identity(self):
        subject = "user_fixture_contractor"
        healthy = {"object": "user", "id": subject, "banned": False, "locked": False}
        with self.fixture() as fixture:
            env = fixture.worker.env
            env.CLERK_SECRET_KEY = "fixture-only"  # pragma: allowlist secret - mocked provider key.
            verify = fixture.module.clerk_reactivation_failure
            with mock.patch.object(fixture.module, "fetch_clerk_user", return_value=healthy) as fetch:
                self.assertIsNone(await verify(env, subject))
                self.assertEqual((await verify(env, "user_fixture/elsewhere"))[0], 409)
                fetch.assert_awaited_once_with(subject, env.CLERK_SECRET_KEY)
            for response in (healthy | {"id": "user_other"}, healthy | {"banned": True},
                             healthy | {"locked": True}, healthy | {"disabled": "false"}, {"id": subject}):
                with mock.patch.object(fixture.module, "fetch_clerk_user", return_value=response):
                    self.assertEqual((await verify(env, subject))[0], 409)
            with mock.patch.object(fixture.module, "fetch_clerk_user", side_effect=TimeoutError("private fixture")):
                code, message = await verify(env, subject)
                self.assertEqual(code, 503)
                self.assertNotIn("private fixture", message)

    async def test_reactivation_cannot_overwrite_a_new_provider_restriction(self):
        with self.fixture() as fixture:
            env = fixture.worker.env
            module = fixture.module
            env.CLERK_SECRET_KEY = "fixture-only"  # pragma: allowlist secret - mocked provider key.
            fixture.worker.optional_workdoe_user = mock.AsyncMock(return_value={
                "id": 4, "role": "admin", "status": "active",
            })
            handler = module.Default.admin_moderation_action
            request = SimpleNamespace(method="POST")
            self.assertEqual((await handler(fixture.worker, request, "/api/admin/users/2/suspend")).status, 200)

            async def restrict_during_lookup(subject, _key):
                await self.sync(fixture, event("user.deleted", email=""))
                return {"object": "user", "id": subject, "banned": False, "locked": False}

            with mock.patch.object(module, "fetch_clerk_user", side_effect=restrict_during_lookup):
                response = await handler(fixture.worker, request, "/api/admin/users/2/activate")
            self.assertEqual(response.status, 409)
            self.assertEqual(self.user(fixture)["status"], "suspended")
            self.assertEqual(fixture.db.execute("""
                SELECT COUNT(*) FROM moderation_actions WHERE target_id = 2 AND action_type = 'activate'
            """).fetchone()[0], 0)

    async def test_provider_restriction_rolls_back_if_its_receipt_cannot_be_written(self):
        with self.fixture() as fixture:
            fixture.db.executescript("""
                CREATE TRIGGER test_restriction_receipt_failure BEFORE INSERT ON automation_events
                WHEN NEW.event_type = 'clerk-provider-restriction'
                BEGIN SELECT RAISE(ABORT, 'synthetic receipt failure'); END;
            """)
            with self.assertRaises(sqlite3.IntegrityError):
                await self.sync(fixture, event(banned=True))
            self.assertEqual(self.user(fixture)["status"], "active")

    async def test_reordered_or_duplicate_routine_events_cannot_undo_provider_suspension(self):
        for disabling in (event("user.deleted", email=""), event(banned=True), event(locked=True)):
            for routine in (event(), event("user.created", email="")):
                with self.subTest(disabling=disabling["type"], routine=routine["type"]), self.fixture() as fixture:
                    await self.sync(fixture, disabling)
                    await self.sync(fixture, routine)
                    await self.sync(fixture, routine)
                    self.assertEqual(self.user(fixture)["status"], "suspended")

    async def test_email_conflict_does_not_block_disabling_event(self):
        for flags in ({"banned": True}, {"locked": True}, {"disabled": True}, {"deprovisioned": True}):
            with self.subTest(flags=flags), self.fixture() as fixture:
                response = await self.sync(fixture, event(email="fixture-1@example.invalid", **flags))
                user = self.user(fixture)
                self.assertEqual(user["status"], "suspended")
                self.assertEqual(user["email"], "fixture-2@example.invalid")
                self.assertEqual(response["reason"], "email-conflict")

    async def test_interleaved_moderation_is_not_overwritten_by_profile_sync(self):
        for email in ("fixture-2@example.invalid", ""):
            with self.subTest(email_present=bool(email)), self.fixture() as fixture:
                fixture.prefix = "UPDATE users"
                fixture.change = ("UPDATE users SET status = 'suspended' WHERE id = 2", ())
                await self.sync(fixture, event(email=email))
                self.assertEqual(fixture.interleaved, 1)
                self.assertEqual(self.user(fixture)["status"], "suspended")

    async def test_changed_identity_link_is_not_touched_after_lookup(self):
        for changed_link in ("auth_provider = 'local'", "external_subject = 'user_other_fixture'"):
            with self.subTest(changed_link=changed_link), self.fixture() as fixture:
                fixture.prefix = "UPDATE users"
                fixture.change = (f"UPDATE users SET {changed_link} WHERE id = 2", ())
                response = await self.sync(fixture, event(email="new@example.invalid", banned=True))
                user = self.user(fixture)
                self.assertEqual(fixture.interleaved, 1)
                self.assertEqual(user["status"], "active")
                self.assertEqual(user["email"], "fixture-2@example.invalid")
                self.assertEqual(response, {"action": "skipped", "reason": "identity-link-changed"})

    async def test_unlinked_and_unsupported_events_do_not_modify_users(self):
        for payload in (event("session.created"), {"type": "user.deleted", "data": {"id": "user_unlinked"}}):
            with self.subTest(payload=payload), self.fixture() as fixture:
                before = self.user(fixture)
                response = await self.sync(fixture, payload)
                self.assertIn(response["action"], {"ignored", "skipped"})
                self.assertEqual(self.user(fixture), before)
                self.assertFalse(any(sql.strip().startswith("UPDATE") for sql, _ in fixture.statements))

    async def test_relink_between_status_and_email_writes_keeps_new_identity_untouched(self):
        with self.fixture() as fixture:
            fixture.prefix = "UPDATE users SET email"
            fixture.change = ("UPDATE users SET external_subject = 'user_new_fixture' WHERE id = 2", ())
            response = await self.sync(fixture, event(email="changed@example.invalid"))
            user = self.user(fixture)
            self.assertEqual(fixture.interleaved, 1)
            self.assertEqual((user["external_subject"], user["email"], user["status"]),
                             ("user_new_fixture", "fixture-2@example.invalid", "active"))
            self.assertEqual(response, {"action": "skipped", "reason": "identity-link-changed"})

    async def test_email_uniqueness_race_cannot_roll_back_provider_suspension(self):
        with self.fixture() as fixture:
            fixture.prefix = "UPDATE users SET email"
            fixture.change = ("UPDATE users SET email = 'changed@example.invalid' WHERE id = 3", ())
            with self.assertRaises(sqlite3.IntegrityError):
                await self.sync(fixture, event(email="changed@example.invalid", banned=True))
            self.assertEqual(fixture.interleaved, 1)
            user = self.user(fixture)
            self.assertEqual((user["status"], user["email"]), ("suspended", "fixture-2@example.invalid"))

    async def test_explicit_admin_activation_remains_available(self):
        with self.fixture() as fixture:
            await self.sync(fixture, event("user.deleted", email=""))
            action = {"target_type": "user", "target_id": 2, "action": "activate"}
            sql, params, _, _ = fixture.module.admin_update_statement(action, fixture.timestamp)
            fixture.db.execute(sql, params)
            fixture.db.commit()
            await self.sync(fixture, event())
            self.assertEqual(self.user(fixture)["status"], "active")

    async def test_active_profile_email_sync_and_conflict_behavior_are_preserved(self):
        with self.fixture() as fixture:
            response = await self.sync(fixture, event(email="updated@example.invalid"))
            self.assertEqual(response, {"action": "updated", "user_id": 2})
            user = self.user(fixture)
            self.assertEqual((user["email"], user["email_verified"], user["status"]), ("updated@example.invalid", 1, "active"))
            response = await self.sync(fixture, event(email="fixture-1@example.invalid"))
            self.assertEqual(response["reason"], "email-conflict")
            self.assertEqual(self.user(fixture), user)

    async def test_delete_event_disables_without_erasing_marketplace_or_identity_data(self):
        with self.fixture() as fixture:
            fixture.pending()
            before = self.user(fixture)
            bid = dict(fixture.db.execute("SELECT * FROM match_requests WHERE id = 1").fetchone())
            response = await self.sync(fixture, event("user.deleted", email=""))
            after = self.user(fixture)
            self.assertEqual(response, {"action": "status-updated", "user_id": 2})
            self.assertEqual(after, {**before, "status": "suspended"})
            self.assertEqual(dict(fixture.db.execute("SELECT * FROM match_requests WHERE id = 1").fetchone()), bid)
            self.assertEqual(fixture.db.execute("SELECT client_id FROM jobs WHERE id = 1").fetchone()[0], 1)
            self.assertFalse(any(sql.strip().startswith("DELETE") for sql, _ in fixture.statements))
