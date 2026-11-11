import asyncio
import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_cloudflare_release import load_worker_entry_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_d1_query_plan import apply_migrations, seed_planner_data


class PublicPhotoPageTests(unittest.TestCase):
    def setUp(self):
        self.worker = load_worker_entry_module()
        self.db = self.enterContext(closing(sqlite3.connect(":memory:")))
        self.db.row_factory = sqlite3.Row
        apply_migrations(self.db)
        seed_planner_data(self.db, count=15)
        self.db.execute("UPDATE users SET status = 'suspended' WHERE id = 15")
        self.db.execute("UPDATE jobs SET description = 'Not part of the public projection' WHERE id = 9")
        self.db.execute("UPDATE jobs SET license_preference = 1 WHERE id = 9")
        self.db.execute("""
            INSERT INTO job_photos (job_id, uploaded_by, original_filename, stored_path,
                                    content_type, size_bytes, is_hidden, created_at)
            VALUES (9, 9, 'hidden.webp', 'fixture/hidden.webp', 'image/webp', 32, 1, '2026-08-23')
        """)

    def run_page(self, *, sort="newest", offset=0, filters=None, viewport=None):
        query, bindings = self.worker.build_public_open_jobs_query(
            filters or {}, viewport, order_clause=self.worker.public_job_order_clause(sort),
            limit=2, cursor_offset=offset,
        )
        self.assertLess(query.index("LIMIT ? OFFSET ?"), query.index("SELECT COUNT(*) FROM job_photos"))
        return [dict(row) for row in self.db.execute(query, bindings)]  # nosec B608 - tested parameterized builder.

    def test_all_orders_count_visible_photos_only_after_the_stable_page(self):
        for sort in ("newest", "soonest", "city"):
            with self.subTest(sort=sort):
                first = self.run_page(sort=sort)
                second = self.run_page(sort=sort, offset=2)
                self.assertEqual([row["id"] for row in first], [13, 11, 9])
                self.assertEqual([row["id"] for row in second], [9, 7, 5])
                self.assertEqual([row["photo_count"] for row in first], [0, 0, 1])
                self.assertEqual(first[2]["license_preference"], 1)
                self.assertTrue(all("description" not in row for row in first + second))

    def test_public_api_and_entry_board_find_zip_without_projecting_it(self):
        async def execute(_env, query, *bindings):
            return {"results": [dict(row) for row in self.db.execute(query, bindings)]}  # nosec B608

        with patch.object(self.worker, "db_run", execute):
            filters = self.worker.entry_job_filters({"q": ["20001"]})
            entry, _, _ = asyncio.run(self.worker.read_public_project_page(
                SimpleNamespace(), filters, None, limit=50, source="test",
            ))
        self.assertEqual([row["id"] for row in entry[:3]], [13, 11, 9])
        api = self.run_page(filters={"q": "20001"})
        self.assertEqual([row["id"] for row in api], [13, 11, 9])
        for row in entry + api:
            public = self.worker.public_jobs_payload([row], {"q": "20001"})["jobs"][0]
            self.assertNotIn("zip_code", public)
            self.assertNotIn("description", public)

    def test_bounds_keep_the_reviewed_pin_and_reject_in_bounds_unreviewed_pins(self):
        self.db.execute("UPDATE jobs SET approx_lat = 38.9101, approx_lng = -77.0171 WHERE id = 9")
        self.db.execute("UPDATE jobs SET approx_lat = 38.9111, approx_lng = -77.0171 WHERE id = 11")
        page = self.run_page(viewport={"north": 38.92, "south": 38.90, "east": -77.00, "west": -77.03})
        self.assertEqual([(row["id"], row["photo_count"]) for row in page], [(9, 1)])

    def test_existing_activation_gate_applies_to_both_discovery_sources(self):
        async def execute(_env, query, *bindings):
            return {"results": [dict(row) for row in self.db.execute(query, bindings)]}  # nosec B608

        filters = self.worker.entry_job_filters({"q": ["Planner job 9"]})

        def read(flag, source):
            env = SimpleNamespace(WORKDOE_ENFORCE_SERVICE_ACTIVATION=flag)
            return asyncio.run(self.worker.read_public_project_page(
                env, filters, None, limit=50, source=source,
            ))[0]

        with patch.object(self.worker, "db_run", execute):
            for source in ("page", "api"):
                with self.subTest(source=source):
                    self.assertEqual([row["id"] for row in read("false", source)], [9])
                    self.assertEqual(read("true", source), [])
