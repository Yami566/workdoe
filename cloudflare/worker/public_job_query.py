from __future__ import annotations

import base64
import binascii
import json
import math

if __package__:
    from .location_pins import CITY_COORDS, DMV_ZIPS
else:
    from location_pins import CITY_COORDS, DMV_ZIPS

PILOT_VIEWPORT = {
    "north": 39.5,
    "south": 38.0,
    "east": -76.2,
    "west": -78.0,
}
PUBLIC_CURSOR_MAX_OFFSET = 5000
PUBLIC_QUERY_MAX_BYTES = 4096
PUBLIC_QUERY_MAX_FIELDS = 32
PUBLIC_DISCOVERY_API_METHODS = ("GET", "HEAD", "OPTIONS")
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
{license_projection}    jobs.city,
    jobs.state,
    jobs.zip_code,
    jobs.approx_lat,
    jobs.approx_lng,
    jobs.created_at,
    jobs.desired_date
FROM jobs
JOIN users AS clients
  ON clients.id = jobs.client_id
 AND clients.status = 'active'
WHERE jobs.status = 'open'
  AND NOT EXISTS (
      SELECT 1
      FROM match_requests AS approved_request
      WHERE approved_request.job_id = jobs.id
        AND approved_request.status = 'approved'
  )
"""
# Older open records may have no deadline; they still use the configured bid cap.
PUBLIC_BID_AVAILABILITY_SQL = """
AND (
    NULLIF(jobs.bidding_closes_at, '') IS NULL
    OR datetime(jobs.bidding_closes_at) > CURRENT_TIMESTAMP
)
AND (
    SELECT COUNT(*) FROM match_requests AS bid_slots
    WHERE bid_slots.job_id = jobs.id
) < jobs.bid_limit
"""
PUBLIC_PAGE_WITH_PHOTO_COUNTS = """
)
SELECT public_page.*,
       (SELECT COUNT(*) FROM job_photos
        WHERE job_photos.job_id = public_page.id
          AND job_photos.is_hidden = 0) AS photo_count
FROM public_page
"""


class PublicJobQueryError(ValueError):
    pass


def public_query_envelope_rejection(query: str | bytes) -> tuple[int, str] | None:
    too_long = (414, "This project search link is too long. Start a new search.")
    if len(query) > PUBLIC_QUERY_MAX_BYTES:
        return too_long
    raw = query.encode("utf-8") if isinstance(query, str) else query
    if len(raw) > PUBLIC_QUERY_MAX_BYTES:
        return too_long
    # Count separators before decoding so encoded ampersands remain values.
    if raw.count(b"&") >= PUBLIC_QUERY_MAX_FIELDS:
        return 400, "This project search link has too many filters. Start a new search."
    return None


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


def next_public_cursor(offset: int, page_count: int, *, has_more: bool) -> str:
    next_offset = offset + page_count
    if has_more and offset < next_offset <= PUBLIC_CURSOR_MAX_OFFSET:
        return encode_public_cursor(next_offset)
    return ""


def public_viewport_sql(viewport: dict[str, float] | None) -> tuple[str, list[float | str]]:
    if not viewport:
        return "", []
    zip_pins = [
        (state, zip_code, lat, lng) for zip_code, (_, state, lat, lng) in DMV_ZIPS.items()
        if public_viewport_contains(viewport, lat, lng)
    ]
    city_pins = []
    for city_state, (lat, lng) in CITY_COORDS.items():
        if public_viewport_contains(viewport, lat, lng):
            city, state = city_state.rsplit(" ", 1)
            city_pins.append((state.upper(), city, lat, lng))
    if not zip_pins and not city_pins:
        return "AND 0", []
    # Check provenance before paging so guessed bounds cannot expose a legacy pin.
    return (
        """
        AND jobs.approx_lat BETWEEN ? AND ?
        AND jobs.approx_lng BETWEEN ? AND ?
        AND (
            (jobs.state, jobs.zip_code, jobs.approx_lat, jobs.approx_lng) IN (
                SELECT json_extract(value, '$[0]'), json_extract(value, '$[1]'),
                       json_extract(value, '$[2]'), json_extract(value, '$[3]')
                FROM json_each(?)
            ) OR
            (jobs.state, lower(jobs.city), jobs.approx_lat, jobs.approx_lng) IN (
                SELECT json_extract(value, '$[0]'), json_extract(value, '$[1]'),
                       json_extract(value, '$[2]'), json_extract(value, '$[3]')
                FROM json_each(?)
            )
        )
        """,
        [
            viewport["south"],
            viewport["north"],
            viewport["west"],
            viewport["east"],
            json.dumps(zip_pins, separators=(",", ":")),
            json.dumps(city_pins, separators=(",", ":")),
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


def literal_project_search(query: str, *, include_zip: bool = True) -> tuple[str, list[str]]:
    if not query:
        return "", []
    if "\x00" in query:
        return "AND 0", []
    # D1 caps LIKE patterns at 50 bytes; search these public fields literally.
    clauses = [
        "instr(lower(jobs.city), lower(?)) > 0",
        "instr(lower(jobs.state), lower(?)) > 0",
        "instr(lower(jobs.title), lower(?)) > 0",
    ]
    if include_zip:
        clauses.append("instr(jobs.zip_code, ?) > 0")
    return "AND (" + " OR ".join(clauses) + ")", [query] * len(clauses)


def public_photo_page_sql(
    clauses: list[str], order_clause: str, *, include_license_preference: bool = True,
) -> str:
    if order_clause not in PUBLIC_ORDER_CLAUSES:
        raise PublicJobQueryError("The project sort order is invalid.")
    # Limit the eligible projects before looking up any visible photo counts.
    page_order = order_clause.replace("jobs.", "public_page.")
    license_projection = "    jobs.license_preference,\n" if include_license_preference else ""
    return "\n".join((
        "WITH public_page AS (", PUBLIC_OPEN_JOBS_SELECT.format(license_projection=license_projection), *clauses,
        PUBLIC_BID_AVAILABILITY_SQL,
        f"ORDER BY {order_clause} LIMIT ? OFFSET ?", PUBLIC_PAGE_WITH_PHOTO_COUNTS,
        f"ORDER BY {page_order}",
    ))


def build_public_open_jobs_query(
    filters: dict[str, str],
    viewport: dict[str, float] | None,
    *,
    order_clause: str,
    limit: int,
    cursor_offset: int,
    service_activation_clause: str = "",
) -> tuple[str, list[str | int | float]]:
    clauses = [service_activation_clause] if service_activation_clause else []
    bindings: list[str | int | float] = []
    if filters.get("category"):
        clauses.append("AND jobs.category = ?")
        bindings.append(filters["category"])
    if filters.get("service"):
        clauses.append("AND jobs.service_slug = ?")
        bindings.append(filters["service"])
    if filters.get("family"):
        clauses.append("AND jobs.service_group_slug = ?")
        bindings.append(filters["family"])
    search, search_bindings = literal_project_search(filters.get("q", ""))
    if search:
        clauses.append(search)
        bindings.extend(search_bindings)
    viewport_clause, viewport_bindings = public_viewport_sql(viewport)
    if viewport_clause:
        clauses.append(viewport_clause)
        bindings.extend(viewport_bindings)
    bindings.extend([limit + 1, cursor_offset])
    return public_photo_page_sql(clauses, order_clause), bindings


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
