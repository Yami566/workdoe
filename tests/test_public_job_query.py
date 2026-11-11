from __future__ import annotations

import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from test_cloudflare_release import load_public_job_query_module

from scripts.verify_d1_query_plan import apply_migrations, seed_planner_data
from workdoe import public_job_query as local_query

ROOT = Path(__file__).resolve().parents[1]
WORKER_QUERY_PATH = ROOT / "cloudflare" / "worker" / "public_job_query.py"
MIGRATIONS_DIR = ROOT / "cloudflare" / "d1" / "migrations"


class PublicJobQueryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker_query = load_public_job_query_module()

    def test_flask_and_worker_query_contracts_are_identical(self):
        local_source = (ROOT / "workdoe" / "public_job_query.py").read_text(
            encoding="utf-8"
        )
        worker_source = WORKER_QUERY_PATH.read_text(encoding="utf-8")
        self.assertEqual(local_source, worker_source)

    def test_literal_search_works_with_the_d1_pattern_limit(self):
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.setlimit(sqlite3.SQLITE_LIMIT_LIKE_PATTERN_LENGTH, 50)
            connection.execute("CREATE TABLE jobs (city TEXT, state TEXT, zip_code TEXT, title TEXT)")
            for title, query, expected in (
                ("L" * 80, "l" * 80, 1),
                ("\u00e9" * 26, "\u00e9" * 26, 1),
                ("%_\\" * 9, "%_\\" * 9, 1),
                ("Ordinary project", "%", 0),
                ("Ordinary project", "\x00", 0),
            ):
                with self.subTest(query=query):
                    connection.execute("DELETE FROM jobs")
                    connection.execute("INSERT INTO jobs VALUES ('Arlington', 'VA', '22201', ?)", (title,))
                    clause, bindings = self.worker_query.literal_project_search(query)
                    count = connection.execute("SELECT COUNT(*) FROM jobs WHERE 1 " + clause, bindings).fetchone()[0]
                    self.assertEqual(count, expected)

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
        self.assertEqual(bindings[:4], [38.4, 39.2, -77.6, -76.5])
        self.assertEqual(len(bindings), 6)
        self.assertEqual(sql.count("FROM json_each(?)"), 2)
        zip_pins, city_pins = (json.loads(value) for value in bindings[4:])
        self.assertIn(["VA", "22201", 38.8871, -77.0932], zip_pins)
        self.assertIn(["VA", "arlington", 38.8797, -77.1068], city_pins)
        self.assertNotIn(["MD", "21401", 38.9784, -76.4922], zip_pins)
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

    def test_public_query_excludes_unavailable_bids_before_pagination(self):
        with closing(sqlite3.connect(":memory:")) as connection:
            apply_migrations(connection)
            seed_planner_data(connection, count=11)
            connection.executemany(
                "UPDATE jobs SET bidding_closes_at = ?, bid_limit = ? WHERE id = ?",
                [
                    ("2000-01-01T00:00:00Z", 4, 11),
                    ("2099-01-01T00:00:00+00:00", 1, 9),
                    ("not a deadline", 4, 7),
                    ("2099-01-01T00:00:00+00:00", 2, 5),
                    ("", 4, 3),
                ],
            )
            connection.executemany(
                """
                INSERT INTO match_requests
                    (job_id, contractor_id, scope_note, price_range, timeline,
                     experience, availability, status, created_at, updated_at)
                VALUES (?, 2, '', '', '', '', '', 'rejected', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                [(9,), (5,)],
            )
            for query_module in (local_query, self.worker_query):
                for offset, expected in ((0, [5, 3]), (1, [3, 1])):
                    query, bindings = query_module.build_public_open_jobs_query(
                        {}, None, order_clause="jobs.created_at DESC, jobs.id DESC",
                        limit=1, cursor_offset=offset,
                    )
                    rows = connection.execute(query, bindings).fetchall()
                    self.assertEqual([row[0] for row in rows], expected)
            self.assertEqual(connection.execute("SELECT status FROM jobs WHERE id = 11").fetchone(), ("open",))


if __name__ == "__main__":
    unittest.main()
