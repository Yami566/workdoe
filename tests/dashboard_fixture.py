"""Dashboard-only fixture compatible with the deployed schema and runtime."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from test_cloudflare_release import load_worker_entry_module

from workdoe import create_app


class DashboardFixture:
    def __init__(self, root):
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE": str(root / "dashboard.sqlite3"),
                "UPLOAD_ROOT": str(root / "uploads"),
                "SEED_DEMO_DATA": False,
                "DISABLE_CSRF": True,
                "DISABLE_TURNSTILE": True,
            }
        )
        self.db = sqlite3.connect(self.app.config["DATABASE"])
        self.db.row_factory = sqlite3.Row
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat(timespec="seconds")
        for user_id, role in ((1, "client"), (2, "contractor"), (3, "client"), (4, "admin")):
            self.db.execute(
                """INSERT INTO users
                (id, email, password_hash, role, display_name, status, email_verified, created_at)
                VALUES (?, ?, '', ?, 'Fixture label', 'active', 1, ?)""",
                (user_id, f"fixture-{user_id}@example.invalid", role, timestamp),
            )
        self.db.execute(
            """INSERT INTO jobs
            (id, client_id, title, category, city, state, zip_code, description,
             status, service_slug, service_zone_slug, bid_limit, bidding_closes_at,
             created_at, updated_at)
            VALUES (1, 1, 'Fixture yard task', 'Landscaping', 'Arlington', 'VA',
                    '22201', 'Maintain the listed yard work.', 'open', 'lawn-mowing',
                    'arlington-alexandria', 4, ?, ?, ?)""",
            ((now + timedelta(days=2)).isoformat(), timestamp, timestamp),
        )
        self.db.commit()
        self.client = self.app.test_client()
        self.statements = []
        self.module = load_worker_entry_module()
        self.worker = self.module.Default()
        self.worker.env = SimpleNamespace(DB=object())

        async def execute(_env, query, *bindings):
            self.statements.append((query, bindings))
            before = self.db.total_changes
            cursor = self.db.execute(query, bindings)
            rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []
            self.db.commit()
            return {
                "results": rows,
                "meta": {
                    "changes": self.db.total_changes - before,
                    "last_row_id": cursor.lastrowid,
                },
            }

        self.module.db_run = execute
