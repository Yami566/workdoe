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
