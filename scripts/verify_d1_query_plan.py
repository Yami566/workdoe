from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "cloudflare" / "d1" / "migrations"
WORKER_DIR = REPO_ROOT / "cloudflare" / "worker"
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from public_job_query import build_public_open_jobs_query

EXPECTED_INDEXES = {
    "idx_contractor_photos_public_contractor",
    "idx_jobs_open_geo",
    "idx_job_photos_public_job",
}


def apply_migrations(connection: sqlite3.Connection) -> list[str]:
    paths = sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not paths:
        raise RuntimeError("No D1 migrations were found.")
    for path in paths:
        connection.executescript(path.read_text(encoding="utf-8"))
    return [path.name for path in paths]


def seed_planner_data(connection: sqlite3.Connection, count: int = 600) -> None:
    timestamp = "2026-08-23T00:00:00+00:00"
    for item_id in range(1, count + 1):
        connection.execute(
            """
            INSERT INTO users
                (id, email, password_hash, role, display_name, status,
                 email_verified, created_at)
            VALUES (?, ?, 'query-plan-only', 'client', ?, 'active', 1, ?)
            """,
            (item_id, f"planner-{item_id}@example.invalid", f"Planner {item_id}", timestamp),
        )
        latitude = 38.75 + (item_id % 100) * 0.004
        longitude = -77.25 + (item_id % 100) * 0.004
        connection.execute(
            """
            INSERT INTO jobs
                (id, client_id, title, category, city, state, zip_code,
                 description, desired_date, status, approx_lat, approx_lng,
                 created_at, updated_at)
            VALUES (?, ?, ?, 'Cleaning', 'Washington', 'DC', '20001',
                    'Planner fixture', '2026-09-01', ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                item_id,
                f"Planner job {item_id}",
                "open" if item_id % 2 else "closed",
                latitude,
                longitude,
                timestamp,
                timestamp,
            ),
        )
        if item_id % 3 == 0:
            connection.execute(
                """
                INSERT INTO job_photos
                    (job_id, uploaded_by, original_filename, stored_path,
                     content_type, size_bytes, is_hidden, created_at)
                VALUES (?, ?, 'planner.webp', ?, 'image/webp', 128, 0, ?)
                """,
                (item_id, item_id, f"planner/{item_id}.webp", timestamp),
            )
        if item_id % 4 == 0:
            connection.execute(
                """
                INSERT INTO contractor_photos
                    (contractor_id, original_filename, stored_path,
                     content_type, size_bytes, is_hidden, created_at)
                VALUES (?, 'portfolio.webp', ?, 'image/webp', 128, 0, ?)
                """,
                (item_id, f"contractors/{item_id}/portfolio.webp", timestamp),
            )
    connection.execute("ANALYZE")


def explain_public_query(connection: sqlite3.Connection) -> list[str]:
    filters = {
        "category": "",
        "family": "",
        "service": "",
        "q": "",
        "sort": "newest",
    }
    viewport = {
        "north": 39.5,
        "south": 38.0,
        "east": -76.2,
        "west": -78.0,
    }
    query, bindings = build_public_open_jobs_query(
        filters,
        viewport,
        order_clause="jobs.created_at DESC, jobs.id DESC",
        limit=24,
        cursor_offset=0,
    )
    # The builder accepts only fixed SQL fragments and an allowlisted order clause.
    rows = connection.execute(  # nosec B608
        f"EXPLAIN QUERY PLAN {query}",
        bindings,
    ).fetchall()
    return [str(row[3]) for row in rows]


def explain_contractor_photo_query(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        EXPLAIN QUERY PLAN
        SELECT contractor_photos.id
        FROM contractor_photos
        WHERE contractor_photos.contractor_id = ?
          AND contractor_photos.is_hidden = 0
        ORDER BY contractor_photos.created_at DESC,
                 contractor_photos.id DESC
        LIMIT 1
        """,
        (4,),
    ).fetchall()
    return [str(row[3]) for row in rows]


def verify_query_plan() -> dict:
    connection = sqlite3.connect(":memory:")
    try:
        migrations = apply_migrations(connection)
        seed_planner_data(connection)
        plan = explain_public_query(connection) + explain_contractor_photo_query(
            connection
        )
    finally:
        connection.close()

    used_indexes = {
        index_name
        for index_name in EXPECTED_INDEXES
        if any("USING" in detail and index_name in detail for detail in plan)
    }
    scans = [
        detail
        for detail in plan
        if detail.startswith(("SCAN jobs", "SCAN job_photos", "SCAN contractor_photos"))
    ]
    return {
        "ok": used_indexes == EXPECTED_INDEXES and not scans,
        "migration_count": len(migrations),
        "last_migration": migrations[-1],
        "expected_indexes": sorted(EXPECTED_INDEXES),
        "used_indexes": sorted(used_indexes),
        "table_scans": scans,
        "plan": plan,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the indexed D1 public-project viewport query plan."
    )
    parser.parse_args()
    result = verify_query_plan()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
