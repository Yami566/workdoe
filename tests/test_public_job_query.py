from __future__ import annotations

import importlib.util
import sqlite3
import unittest
from pathlib import Path

from workdoe import public_job_query as local_query

ROOT = Path(__file__).resolve().parents[1]
WORKER_QUERY_PATH = ROOT / "cloudflare" / "worker" / "public_job_query.py"
MIGRATIONS_DIR = ROOT / "cloudflare" / "d1" / "migrations"


def load_worker_query_module():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_worker_public_job_query_test",
        WORKER_QUERY_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PublicJobQueryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker_query = load_worker_query_module()

    def test_flask_and_worker_query_contracts_are_identical(self):
        local_source = (ROOT / "workdoe" / "public_job_query.py").read_text(
            encoding="utf-8"
        )
        worker_source = WORKER_QUERY_PATH.read_text(encoding="utf-8")
        self.assertEqual(local_source, worker_source)

    def test_viewport_parsing_clamps_queries_to_the_dmv_pilot(self):
        cases = (
            ({}, None),
            (
                {
                    "north": "39.2",
                    "south": "38.4",
                    "east": "-76.5",
                    "west": "-77.6",
                },
                {
                    "north": 39.2,
                    "south": 38.4,
                    "east": -76.5,
                    "west": -77.6,
                },
            ),
            (
                {
                    "north": "50",
                    "south": "30",
                    "east": "-70",
                    "west": "-90",
                },
                local_query.PILOT_VIEWPORT,
            ),
        )
        for params, expected in cases:
            with self.subTest(params=params):
                self.assertEqual(local_query.parse_public_viewport(params), expected)
                self.assertEqual(
                    self.worker_query.parse_public_viewport(params), expected
                )

    def test_invalid_viewports_fail_closed_in_both_runtimes(self):
        invalid = (
            {"north": "39"},
            {"north": "north", "south": "38", "east": "-76", "west": "-77"},
            {"north": "38", "south": "39", "east": "-76", "west": "-77"},
            {"north": "10", "south": "9", "east": "10", "west": "9"},
            {"north": "inf", "south": "38", "east": "-76", "west": "-77"},
        )
        for params in invalid:
            with self.subTest(params=params):
                with self.assertRaises(local_query.PublicJobQueryError):
                    local_query.parse_public_viewport(params)
                with self.assertRaises(self.worker_query.PublicJobQueryError):
                    self.worker_query.parse_public_viewport(params)

    def test_cursor_round_trip_and_invalid_values_match(self):
        for offset in (0, 1, 125, local_query.PUBLIC_CURSOR_MAX_OFFSET):
            with self.subTest(offset=offset):
                local_cursor = local_query.encode_public_cursor(offset)
                worker_cursor = self.worker_query.encode_public_cursor(offset)
                self.assertEqual(local_cursor, worker_cursor)
                self.assertEqual(local_query.parse_public_cursor(local_cursor), offset)
                self.assertEqual(
                    self.worker_query.parse_public_cursor(worker_cursor), offset
                )
        for value in ("not-a-cursor", "djI6MQ", "djE6LTE", "djE6NTAwMQ"):
            with self.subTest(value=value):
                with self.assertRaises(local_query.PublicJobQueryError):
                    local_query.parse_public_cursor(value)
                with self.assertRaises(self.worker_query.PublicJobQueryError):
                    self.worker_query.parse_public_cursor(value)

    def test_viewport_sql_and_point_filter_match(self):
        viewport = {
            "north": 39.2,
            "south": 38.4,
            "east": -76.5,
            "west": -77.6,
        }
        sql, bindings = local_query.public_viewport_sql(viewport)
        self.assertIn("jobs.approx_lat BETWEEN ? AND ?", sql)
        self.assertIn("jobs.approx_lng BETWEEN ? AND ?", sql)
        self.assertEqual(bindings, [38.4, 39.2, -77.6, -76.5])
        self.assertTrue(local_query.public_viewport_contains(viewport, 38.9, -77.0))
        self.assertFalse(local_query.public_viewport_contains(viewport, 40.0, -77.0))

    def test_d1_query_plan_uses_the_open_geo_index(self):
        connection = sqlite3.connect(":memory:")
        try:
            for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                connection.executescript(path.read_text(encoding="utf-8"))
            plan = connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT id
                FROM jobs
                WHERE status = ?
                  AND approx_lat BETWEEN ? AND ?
                  AND approx_lng BETWEEN ? AND ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                ("open", 38.0, 39.5, -78.0, -76.2, 9),
            ).fetchall()
        finally:
            connection.close()
        detail = " ".join(str(row[3]) for row in plan)
        self.assertIn("idx_jobs_open_geo", detail)


if __name__ == "__main__":
    unittest.main()
