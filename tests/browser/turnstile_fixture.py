"""Render actual protected forms using only synthetic local data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloudflare/worker"))

from app_shell import (
    contractor_job_detail_html,
    job_form_html,
    layout,
    site_dialog_html,
)

client = {"id": 1, "role": "client", "status": "active"}
contractor = {"id": 2, "role": "contractor", "status": "active"}
job = {
    "id": 101, "client_id": 1, "title": "TEST ONLY: Synthetic yard work",
    "category": "Landscaping", "service_group_slug": "outdoor-yard",
    "service_slug": "lawn-mowing", "city": "Arlington", "state": "VA",
    "zip_code": "22201", "status": "open", "description": "Synthetic unsaved scope for local verification tests only.",
    "can_request_match": True,
}
edit = job_form_html(client, "synthetic-key", job=job, mode="edit", media_uploads_enabled=False)
assert site_dialog_html() in edit
pages = {
    "/client/jobs/101/edit": edit,
    "/standalone-edit": edit.replace(site_dialog_html(), "", 1),
    "/jobs/101": contractor_job_detail_html(contractor, {"job": job}, "synthetic-key"),
    "/jobs/101?embed=1": contractor_job_detail_html(contractor, {"job": job}, "synthetic-key", embedded=True),
    "/leads": layout(contractor, "/leads", "Synthetic leads", '<a href="/jobs/101" data-dialog-title="Review and bid">Open synthetic lead</a>'),
}
print(json.dumps({"pages": pages, "provider_not_tested": True}))
