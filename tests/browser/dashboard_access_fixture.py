"""Render account-role recovery with no accounts, databases or provider calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cloudflare/worker"))

from app_shell import app_shell_headers, dashboard_access_html

print(
    json.dumps(
        {
            "headers": app_shell_headers(),
            "pages": {
                "/client/dashboard": dashboard_access_html(
                    {"role": "contractor"}, "client"
                ),
                "/contractor/dashboard": dashboard_access_html(
                    {"role": "client"}, "contractor"
                ),
            },
        }
    )
)
