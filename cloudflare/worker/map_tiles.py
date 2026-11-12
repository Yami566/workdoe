from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

if __package__:
    from .public_job_query import PILOT_VIEWPORT
else:
    from public_job_query import PILOT_VIEWPORT

DEFAULT_MAP_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
DEFAULT_MAP_TILE_ATTRIBUTION = (
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
)
DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
AREA_MAP_ASSET = "/dmv-area-50fe6cd3.geojson"
AREA_MAP_ATTRIBUTION = "Source: U.S. Census Bureau (2025 boundaries)"


def area_map_bounds() -> list[list[float]]:
    return [
        [PILOT_VIEWPORT["south"], PILOT_VIEWPORT["west"]],
        [PILOT_VIEWPORT["north"], PILOT_VIEWPORT["east"]],
    ]


def area_map_attributes(tile_url: str, access_protected: bool) -> str:
    if tile_url != AREA_MAP_ASSET:
        return ""
    bounds = area_map_bounds()
    access = " data-area-map-access" if access_protected else ""
    return f' data-area-map-bounds="{json.dumps(bounds, separators=(",", ":"))}"{access}'


def map_tile_origin(tile_url: str | None) -> str:
    """Allow one HTTPS DNS origin, never credentials, wildcards or CSP syntax."""
    candidate = str(tile_url or "")
    if not candidate or len(candidate) > 2048:
        return ""
    if any(
        ord(char) <= 32 or ord(char) >= 127 or char in "\\\"'<>;" for char in candidate
    ):
        return ""
    remainder = candidate
    for token in ("{z}", "{x}", "{y}"):
        remainder = remainder.replace(token, "")
    if "{" in remainder or "}" in remainder:
        return ""
    try:
        parsed = urlsplit(candidate)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.netloc.lower() not in (host, host + ":443")
            or parsed.fragment
            or "." not in host
            or len(host) > 253
            or not all(DNS_LABEL.fullmatch(label) for label in host.split("."))
            or not all(token in parsed.path for token in ("{z}", "{x}", "{y}"))
        ):
            return ""
    except ValueError:
        return ""
    return "https://" + host

def map_tile_configuration(
    tile_url: str | None = None,
    tile_attribution: str | None = None,
    *,
    map_mode: str | None = None,
) -> tuple[str, str]:
    """An explicitly disabled or incomplete provider never falls back to tiles."""
    if map_mode is not None:
        mode = map_mode.strip().lower() if isinstance(map_mode, str) else ""
        if mode == "area":
            return AREA_MAP_ASSET, AREA_MAP_ATTRIBUTION
        if mode != "map":
            return "", ""
    if tile_url is None and tile_attribution is None:
        return DEFAULT_MAP_TILE_URL, DEFAULT_MAP_TILE_ATTRIBUTION
    attribution = str(tile_attribution or "").strip()
    if not map_tile_origin(tile_url) or not attribution:
        return "", ""
    return str(tile_url), attribution
