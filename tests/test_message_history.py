from __future__ import annotations

import importlib.util
import sqlite3
import unittest
from contextlib import closing

from scripts.verify_d1_query_plan import WORKER_DIR, apply_migrations
from workdoe import message_history as flask_history


class MessageHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("worker_message_history", WORKER_DIR / "message_history.py")
        cls.worker_history = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker_history)

    def test_validates_cursors_identically_without_coercing_untrusted_values(self):
        for module in (flask_history, self.worker_history):
            self.assertIsNone(module.parse_message_through([]))
            self.assertEqual(module.parse_message_through(["42"]), 42)
            self.assertEqual(module.parse_message_through(["9007199254740991"]), 9007199254740991)
            for values in ([""], ["0"], ["-1"], ["1.0"], [" 1"], ["42", "43"], ["9007199254740992"], ["1" * 100]):
                with self.subTest(values=values), self.assertRaisesRegex(ValueError, "Invalid message history"):
                    module.parse_message_through(values)

    def test_indexed_windows_keep_messages_private_and_reachable(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            apply_migrations(db)
            # Keep this planner fixture independent of onboarding and match setup.
            db.execute("PRAGMA foreign_keys = OFF")
            db.execute("""
                INSERT INTO users (id, email, password_hash, role, display_name, created_at)
                VALUES (1, 'planner@example.test', 'test-only', 'client', 'Test member', '2026-11-09')
                """)
            db.executemany(
                "INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at) VALUES (?, 1, ?, ?, ?)",
                ((1 if index % 11 else 2, f"Reply {index}", int(index % 9 == 0), "2026-11-09")
                 for index in range(1, 181)),
            )
            for module in (flask_history, self.worker_history):
                for include_hidden in (False, True):
                    through = None
                    seen = []
                    while True:
                        sql, args = module.message_window_query(1, through, include_hidden=include_hidden)
                        fetched = db.execute(sql, args).fetchall()
                        self.assertLessEqual(len(fetched), 51)
                        page, next_through = module.message_history_page(fetched)
                        ids = [row["id"] for row in page]
                        self.assertEqual(ids, sorted(ids))
                        seen.extend(reversed(ids))
                        if next_through is None:
                            break
                        self.assertLess(next_through, ids[0])
                        through = next_through
                    expected = [index for index in range(180, 0, -1)
                                if index % 11 and (include_hidden or index % 9)]
                    self.assertEqual(seen, expected)
                    query, args = module.message_window_query(1, 90, include_hidden=include_hidden)
                    plan = [row[3] for row in db.execute(f"EXPLAIN QUERY PLAN {query}", args)]  # nosec B608 - fixed SQL.
                    indexed_ranges = [
                        detail for detail in plan
                        if "idx_messages_thread_unread" in detail and "thread_id=? AND is_hidden=? AND id<?" in detail
                    ]
                    self.assertEqual(len(indexed_ranges), 2 if include_hidden else 1, plan)
                    page, _ = module.message_history_page(db.execute(query, args).fetchall())
                    self.assertEqual(page[-1]["id"], 90 if include_hidden else 89)
