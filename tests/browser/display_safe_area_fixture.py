"""Render the serving Worker views with sample records for a loopback browser."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloudflare" / "worker"))

from app_shell import app_shell_headers, lead_board_html, public_job_draft_html
from demo_projects import guest_project_rows
from entry_shell import build_entry_shell_html, entry_job_filters, shell_headers
from map_tiles import AREA_MAP_ASSET, DEFAULT_MAP_TILE_URL
from public_jobs import public_jobs_payload

rows = guest_project_rows([{
    "id": 7001, "title": "Synthetic unpinned project", "category": "Window cleaning",
    "city": "Arlington", "state": "VA", "zip_code": "22201",
    "approx_lat": 38.881234, "approx_lng": -77.101234,
}])
payload = public_jobs_payload(rows, {})
lead_jobs = [
    job if job.get("is_demo") else {
        **job, "url": f"/jobs/{job['id']}", "detail_url": f"/jobs/{job['id']}",
        "action_label": "Review and bid", "description": "Synthetic scope for the contractor board.",
    }
    for job in payload["jobs"]
]
area = {"map_mode": "area"} if "--area-map" in sys.argv else {}
access_map = "--access-area-map" in sys.argv
if access_map:
    area["access_protected_map"] = True
tile_url = AREA_MAP_ASSET if area else DEFAULT_MAP_TILE_URL
direct_area_auth = "--direct-area-auth" in sys.argv
shared_pages = {
    f"/?job_id={identifier}": {
        "html": build_entry_shell_html("/", {"job_id": [identifier]}, rows, "", "", **area),
        "headers": shell_headers("", map_tile_url=tile_url),
    }
    for identifier in ("7001", "7999")
} if "--shared-project" in sys.argv else {}
zip_params = {"q": ["22201"]}
zip_rows = [row for row in rows if row["id"] == 7001]
zip_payload = public_jobs_payload(zip_rows, entry_job_filters(zip_params))
snapshot = "--server-map-snapshot" in sys.argv
viewport = {"north": 39.5, "south": 38.8, "east": -77.0, "west": -77.4}
bounded_rows = guest_project_rows([], viewport=viewport)
bounded_url = "/?north=39.9&south=38.8&east=-77&west=-77.4"
bounded_form_url = "/?" + urlencode(viewport | {"q": "", "sort": "newest"})
bounded_family_params = {"family": ["outdoor-yard"]}
bounded_family_url = bounded_url + "&family=outdoor-yard"
snapshot_pages = {
    route: {
        "html": build_entry_shell_html(
            "/", params, guest_project_rows([], entry_job_filters(params), viewport=viewport), "", "",
            page_snapshot={"viewport": viewport, "truncated": False}, **area,
        ),
        "headers": shell_headers("", map_tile_url=tile_url),
    }
    for route, params in ((bounded_url, {}), (bounded_form_url, {}), (bounded_family_url, bounded_family_params))
} if snapshot else {}


def auth_page(path: str, direct: bool) -> dict:
    if direct:
        return {
            "html": build_entry_shell_html(path, {}, rows, "", "/__clerk", **area),
            "headers": shell_headers("/__clerk", map_tile_url=tile_url),
        }
    return {
        "html": build_entry_shell_html(path, {"embed": ["1"]}, [], "", ""),
        "headers": shell_headers(""),
    }


print(json.dumps({
    "pages": {
        **shared_pages,
        **snapshot_pages,
        "/?q=22201": {
            "html": build_entry_shell_html("/", zip_params, zip_rows, "", "", **area),
            "headers": shell_headers("", map_tile_url=tile_url),
        },
        "/": {
            "html": build_entry_shell_html(
                "/", {}, rows, "", "",
                page_snapshot={"viewport": None, "truncated": True} if snapshot else None, **area,
            ),
            "headers": shell_headers("", map_tile_url=tile_url),
        },
        "/leads": {
            "html": lead_board_html(
                {"id": 1, "role": "contractor", "status": "active"},
                {"jobs": lead_jobs, "map_jobs": lead_jobs},
                **area,
            ),
            "headers": app_shell_headers(include_map=True, map_tile_url=tile_url),
        },
        "/login": auth_page("/login", access_map or direct_area_auth),
        "/create-account": auth_page("/create-account", direct_area_auth),
        "/post-project": {
            "html": public_job_draft_html(embedded=True),
            "headers": app_shell_headers(),
        },
    },
    "jobs": payload,
    "zip_jobs": zip_payload,
    "bounded_url": bounded_url,
    "bounded_family_url": bounded_family_url,
    "bounded_ids": [row["id"] for row in bounded_rows],
}))
