from __future__ import annotations

import ast
import asyncio
import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from tests.test_cloudflare_release import load_worker_entry_module


class WorkerProjectStatusRaceTests(unittest.TestCase):
    def test_adapters_use_equivalent_guarded_lifecycle_statements(self):
        root = Path(__file__).resolve().parents[1]

        def statements(path, status_method):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            output = []
            for name, prefix in (
                (status_method, "UPDATE jobs SET status ="),
                (
                    "confirm_match_completion",
                    "UPDATE match_completions SET client_confirmed_at = CASE",
                ),
            ):
                method = next(
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == name
                )
                output.append(
                    next(
                        " ".join(node.value.split())
                        for node in ast.walk(method)
                        if isinstance(node, ast.Constant)
                        and isinstance(node.value, str)
                        and " ".join(node.value.split()).startswith(prefix)
                    )
                )
            return output

        self.assertEqual(
            statements(root / "cloudflare/worker/entry.py", "update_job_status"),
            statements(root / "workdoe/__init__.py", "client_job_status"),
        )

    def test_completion_write_rechecks_current_project_match_and_actor(self):
        for role in ("client", "contractor"):
            for change in (
                "reopened",
                "hidden",
                "close-reason",
                "rejected",
                "suspended",
            ):
                with (
                    self.subTest(role=role, change=change),
                    closing(sqlite3.connect(":memory:")) as db,
                ):
                    db.row_factory = sqlite3.Row
                    db.executescript(
                        """
                        CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT, status TEXT);
                        INSERT INTO users VALUES (1, 'client', 'active'), (2, 'contractor', 'active');
                        CREATE TABLE jobs (id INTEGER PRIMARY KEY, client_id INTEGER, status TEXT, close_reason TEXT);
                        INSERT INTO jobs VALUES (1, 1, 'closed', 'workdoe-match');
                        CREATE TABLE match_requests (id INTEGER PRIMARY KEY, job_id INTEGER, contractor_id INTEGER, status TEXT);
                        INSERT INTO match_requests VALUES (1, 1, 2, 'approved');
                        CREATE TABLE match_completions (
                            match_request_id INTEGER PRIMARY KEY, client_confirmed_at TEXT,
                            contractor_confirmed_at TEXT, verified_at TEXT, created_at TEXT, updated_at TEXT
                        );
                        INSERT INTO match_completions VALUES (1, NULL, NULL, NULL, 'before', 'before');
                        """
                    )
                    module = load_worker_entry_module()
                    worker = module.Default()
                    worker.env = SimpleNamespace(DB=object())
                    actor_id = 1 if role == "client" else 2
                    events = []
                    interleaved = []

                    async def actor(_request, actor_id=actor_id, role=role):
                        return {"id": actor_id, "role": role, "status": "active"}

                    async def match(_env, _request_id, db=db):
                        return dict(
                            db.execute(
                                """
                            SELECT match_completions.*, match_requests.status AS match_status,
                                   match_requests.contractor_id, jobs.id AS job_id, jobs.client_id,
                                   jobs.status AS job_status, jobs.close_reason
                            FROM match_completions
                            JOIN match_requests ON match_requests.id = match_completions.match_request_id
                            JOIN jobs ON jobs.id = match_requests.job_id
                            """
                            ).fetchone()
                        )

                    async def event(_env, name, events=events, **_kwargs):
                        events.append(name)

                    async def run(
                        _env,
                        query,
                        *params,
                        db=db,
                        change=change,
                        actor_id=actor_id,
                        interleaved=interleaved,
                    ):
                        if (
                            query.lstrip().startswith("UPDATE match_completions")
                            and not interleaved
                        ):
                            interleaved.append(True)
                            if change in {"reopened", "hidden"}:
                                db.execute(
                                    "UPDATE jobs SET status = ?",
                                    ("open" if change == "reopened" else "hidden",),
                                )
                            elif change == "close-reason":
                                db.execute(
                                    "UPDATE jobs SET close_reason = 'plans-changed'"
                                )
                            elif change == "rejected":
                                db.execute(
                                    "UPDATE match_requests SET status = 'rejected'"
                                )
                            else:
                                db.execute(
                                    "UPDATE users SET status = 'suspended' WHERE id = ?",
                                    (actor_id,),
                                )
                        cursor = db.execute(query, params)
                        return {
                            "results": [dict(row) for row in cursor.fetchall()],
                            "meta": {"changes": max(cursor.rowcount, 0)},
                        }

                    worker.optional_workdoe_user = actor
                    module.match_for_completion = match
                    module.record_event = event
                    module.db_run = run
                    response = asyncio.run(
                        worker.confirm_match_completion(
                            SimpleNamespace(method="POST"),
                            "/api/match-requests/1/complete",
                        )
                    )
                    self.assertEqual(interleaved, [True])
                    self.assertEqual(response.status, 409)
                    self.assertFalse(json.loads(response.body)["ok"])
                    current = db.execute("SELECT * FROM match_completions").fetchone()
                    self.assertIsNone(current["client_confirmed_at"])
                    self.assertIsNone(current["contractor_confirmed_at"])
                    self.assertIsNone(current["verified_at"])
                    self.assertEqual(current["updated_at"], "before")
                    self.assertEqual(events, [])

    def test_status_write_rechecks_current_moderation_owner_and_account_state(self):
        for action, change in (
            ("close", "hidden"),
            ("reopen", "hidden"),
            ("close", "suspended"),
            ("reopen", "new-owner"),
            ("close", "updated"),
            ("reopen", "completion"),
            ("close", "completion"),
        ):
            with (
                self.subTest(action=action, change=change),
                closing(sqlite3.connect(":memory:")) as db,
            ):
                db.row_factory = sqlite3.Row
                db.executescript(
                    """
                    CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT, status TEXT);
                    INSERT INTO users VALUES (1, 'client', 'active');
                    CREATE TABLE jobs (
                        id INTEGER PRIMARY KEY, client_id INTEGER, status TEXT,
                        bidding_closes_at TEXT, bid_limit INTEGER,
                        close_reason TEXT, close_note TEXT, closed_at TEXT, updated_at TEXT
                    );
                    CREATE TABLE match_requests (id INTEGER PRIMARY KEY, job_id INTEGER, status TEXT);
                    CREATE TABLE match_completions (
                        match_request_id INTEGER, client_confirmed_at TEXT, contractor_confirmed_at TEXT
                    );
                    CREATE TABLE repeat_provider_invitations (
                        id INTEGER PRIMARY KEY, job_id INTEGER, status TEXT,
                        responded_at TEXT, updated_at TEXT
                    );
                    INSERT INTO repeat_provider_invitations VALUES (1, 1, 'pending', NULL, 'before');
                    """
                )
                db.execute(
                    "INSERT INTO jobs VALUES (1, 1, ?, '2099-01-01', 5, NULL, '', NULL, 'before')",
                    ("open" if action == "close" else "closed",),
                )
                module = load_worker_entry_module()
                worker = module.Default()
                worker.env = SimpleNamespace(DB=object())
                events = []
                changed = False

                async def client(_request):
                    return {"id": 1, "role": "client", "status": "active"}

                async def job(_env, _job_id, db=db):
                    return dict(
                        db.execute("SELECT * FROM jobs WHERE id = 1").fetchone()
                    )

                async def body(_request, **_kwargs):
                    return {"reason_code": "plans-changed", "note": ""}

                async def event(_env, name, events=events, **_kwargs):
                    events.append(name)

                async def run(_env, query, *params, db=db, change=change):
                    nonlocal changed
                    if query.lstrip().startswith("UPDATE jobs") and not changed:
                        changed = True
                        if change == "hidden":
                            db.execute("UPDATE jobs SET status = 'hidden' WHERE id = 1")
                        elif change == "suspended":
                            db.execute(
                                "UPDATE users SET status = 'suspended' WHERE id = 1"
                            )
                        elif change == "new-owner":
                            db.execute("UPDATE jobs SET client_id = 2 WHERE id = 1")
                        elif change == "updated":
                            db.execute(
                                "UPDATE jobs SET updated_at = 'newer' WHERE id = 1"
                            )
                        else:
                            db.execute(
                                "INSERT INTO match_requests VALUES (1, 1, 'approved')"
                            )
                            db.execute(
                                "INSERT INTO match_completions VALUES (1, 'newer', NULL)"
                            )
                    cursor = db.execute(query, params)
                    return {
                        "results": [dict(row) for row in cursor.fetchall()],
                        "meta": {"changes": max(cursor.rowcount, 0)},
                    }

                worker.optional_workdoe_user = client
                module.job_for_detail = job
                module.request_json_object = body
                module.record_event = event
                module.db_run = run
                response = asyncio.run(
                    worker.update_job_status(
                        SimpleNamespace(method="POST"), f"/api/jobs/1/{action}"
                    )
                )
                self.assertTrue(changed)
                self.assertEqual(response.status, 409)
                self.assertFalse(json.loads(response.body)["ok"])
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                current = dict(db.execute("SELECT * FROM jobs WHERE id = 1").fetchone())
                self.assertEqual(
                    current["status"],
                    "hidden"
                    if change == "hidden"
                    else ("open" if action == "close" else "closed"),
                )
                self.assertEqual(
                    current["updated_at"], "newer" if change == "updated" else "before"
                )
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM repeat_provider_invitations"
                    ).fetchone()[0],
                    "pending",
                )
                self.assertEqual(events, [])
