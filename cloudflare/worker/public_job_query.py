from __future__ import annotations

import base64
import binascii
import math

PILOT_VIEWPORT = {
    "north": 39.5,
    "south": 38.0,
    "east": -76.2,
    "west": -78.0,
}
PUBLIC_CURSOR_MAX_OFFSET = 5000
PUBLIC_VIEWPORT_KEYS = ("north", "south", "east", "west")
PUBLIC_ORDER_CLAUSES = frozenset(
    {
        "jobs.created_at DESC, jobs.id DESC",
        (
            "CASE WHEN jobs.desired_date IS NULL OR jobs.desired_date = '' THEN 1 ELSE 0 END, "
            "jobs.desired_date ASC, jobs.created_at DESC, jobs.id DESC"
        ),
        "jobs.city COLLATE NOCASE ASC, jobs.created_at DESC, jobs.id DESC",
    }
)
PUBLIC_OPEN_JOBS_SELECT = """
SELECT
    jobs.id,
    jobs.title,
    jobs.category,
    jobs.service_group_slug,
    jobs.service_slug,
    jobs.license_preference,
    jobs.city,
    jobs.state,
    jobs.description,
    jobs.approx_lat,
    jobs.approx_lng,
    jobs.created_at,
    jobs.desired_date,
    COUNT(job_photos.id) AS photo_count
FROM jobs
LEFT JOIN job_photos
  ON job_photos.job_id = jobs.id
 AND job_photos.is_hidden = 0
WHERE jobs.status = 'open'
  AND NOT EXISTS (
      SELECT 1
      FROM match_requests AS approved_request
      WHERE approved_request.job_id = jobs.id
        AND approved_request.status = 'approved'
  )
"""


class PublicJobQueryError(ValueError):
    pass


def first_query_value(params, key: str, default: str = "") -> str:
    value = params.get(key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value or default)


def parse_public_viewport(params) -> dict[str, float] | None:
    raw = {key: first_query_value(params, key).strip() for key in PUBLIC_VIEWPORT_KEYS}
    supplied = [key for key, value in raw.items() if value]
    if not supplied:
        return None
    if len(supplied) != len(PUBLIC_VIEWPORT_KEYS):
        raise PublicJobQueryError("Provide north, south, east, and west together.")
    try:
        viewport = {key: float(value) for key, value in raw.items()}
    except ValueError as exc:
        raise PublicJobQueryError("Map bounds must be numbers.") from exc
    if not all(math.isfinite(value) for value in viewport.values()):
        raise PublicJobQueryError("Map bounds must be finite numbers.")
    if viewport["north"] <= viewport["south"] or viewport["east"] <= viewport["west"]:
        raise PublicJobQueryError("Map bounds are not ordered correctly.")
    if not (-90 <= viewport["south"] <= 90 and -90 <= viewport["north"] <= 90):
        raise PublicJobQueryError("Latitude bounds are outside the valid range.")
    if not (-180 <= viewport["west"] <= 180 and -180 <= viewport["east"] <= 180):
        raise PublicJobQueryError("Longitude bounds are outside the valid range.")

    normalized = {
        "north": min(viewport["north"], PILOT_VIEWPORT["north"]),
        "south": max(viewport["south"], PILOT_VIEWPORT["south"]),
        "east": min(viewport["east"], PILOT_VIEWPORT["east"]),
        "west": max(viewport["west"], PILOT_VIEWPORT["west"]),
    }
    if normalized["north"] <= normalized["south"] or normalized["east"] <= normalized["west"]:
        raise PublicJobQueryError("That map area is outside the current DMV pilot.")
    return {key: round(value, 6) for key, value in normalized.items()}


def parse_public_cursor(value: str | None) -> int:
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        version, offset_text = decoded.split(":", 1)
        offset = int(offset_text)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise PublicJobQueryError("The project cursor is invalid.") from exc
    if version != "v1" or offset < 0 or offset > PUBLIC_CURSOR_MAX_OFFSET:
        raise PublicJobQueryError("The project cursor is invalid.")
    return offset


def encode_public_cursor(offset: int) -> str:
    normalized = max(0, min(int(offset), PUBLIC_CURSOR_MAX_OFFSET))
    payload = base64.urlsafe_b64encode(f"v1:{normalized}".encode()).decode()
    return payload.rstrip("=")


def public_viewport_sql(viewport: dict[str, float] | None) -> tuple[str, list[float]]:
    if not viewport:
        return "", []
    return (
        (
            "AND jobs.approx_lat BETWEEN ? AND ? "
            "AND jobs.approx_lng BETWEEN ? AND ?"
        ),
        [
            viewport["south"],
            viewport["north"],
            viewport["west"],
            viewport["east"],
        ],
    )


def public_viewport_contains(viewport: dict[str, float] | None, lat, lng) -> bool:
    if not viewport:
        return True
    try:
        latitude = float(lat)
        longitude = float(lng)
    except (TypeError, ValueError):
        return False
    return (
        viewport["south"] <= latitude <= viewport["north"]
        and viewport["west"] <= longitude <= viewport["east"]
    )


def build_public_open_jobs_query(
    filters: dict[str, str],
    viewport: dict[str, float] | None,
    *,
    order_clause: str,
    limit: int,
    cursor_offset: int,
) -> tuple[str, list[str | int | float]]:
    if order_clause not in PUBLIC_ORDER_CLAUSES:
        raise PublicJobQueryError("The project sort order is invalid.")
    sql = [PUBLIC_OPEN_JOBS_SELECT]
    bindings: list[str | int | float] = []
    if filters.get("category"):
        sql.append("AND jobs.category = ?")
        bindings.append(filters["category"])
    if filters.get("service"):
        sql.append("AND jobs.service_slug = ?")
        bindings.append(filters["service"])
    if filters.get("family"):
        sql.append("AND jobs.service_group_slug = ?")
        bindings.append(filters["family"])
    if filters.get("q"):
        like = f"%{filters['q']}%"
        sql.append(
            "AND (jobs.city LIKE ? OR jobs.state LIKE ? OR jobs.zip_code LIKE ? OR jobs.title LIKE ?)"
        )
        bindings.extend([like, like, like, like])
    viewport_clause, viewport_bindings = public_viewport_sql(viewport)
    if viewport_clause:
        sql.append(viewport_clause)
        bindings.extend(viewport_bindings)
    sql.append(
        f"GROUP BY jobs.id ORDER BY {order_clause} "
        "LIMIT ? OFFSET ?"
    )
    bindings.extend([limit + 1, cursor_offset])
    return "\n".join(sql), bindings


def result_meta(result) -> dict:
    if isinstance(result, dict):
        meta = result.get("meta") or result.get("result", {}).get("meta") or {}
    else:
        meta = getattr(result, "meta", {}) or {}
    if isinstance(meta, dict):
        return meta
    return {
        key: getattr(meta, key)
        for key in (
            "rows_read",
            "rowsRead",
            "rows_written",
            "rowsWritten",
            "duration",
            "duration_ms",
            "durationMs",
        )
        if hasattr(meta, key)
    }


def first_metric(meta: dict, *keys: str):
    for key in keys:
        value = meta.get(key)
        if value is not None:
            return value
    return None


def public_query_telemetry(
    result,
    *,
    returned_rows: int,
    filters: dict[str, str],
    viewport_applied: bool,
    cursor_offset: int,
) -> dict:
    meta = result_meta(result)
    return {
        "event": "d1-public-open-jobs-query",
        "rows_read": first_metric(meta, "rows_read", "rowsRead"),
        "rows_written": first_metric(meta, "rows_written", "rowsWritten"),
        "duration_ms": first_metric(meta, "duration", "duration_ms", "durationMs"),
        "returned_rows": max(0, int(returned_rows)),
        "viewport_applied": bool(viewport_applied),
        "cursor_offset": max(0, int(cursor_offset)),
        "family": filters.get("family", ""),
        "service": filters.get("service", ""),
        "sort": filters.get("sort", "newest"),
    }
