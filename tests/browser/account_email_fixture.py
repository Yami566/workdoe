"""Synthetic account layouts; no provider requests or real account data."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cloudflare/worker"))

from app_shell import account_security_html, privacy_page_html

from workdoe import create_app

pages = {}
with tempfile.TemporaryDirectory() as directory:
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(Path(directory) / "account.sqlite3"),
            "UPLOAD_ROOT": str(Path(directory) / "uploads"),
            "SEED_DEMO_DATA": False,
        }
    )
    client = app.test_client()
    for role in ("client", "contractor"):
        for kind, email in (
            ("normal", "consumer.alias@example.com"),
            ("long", "long" + "x" * 60 + "@example.invalid"),
        ):
            user = {"id": 1, "role": role, "email": email, "status": "active"}
            pages[f"/worker/{role}/{kind}"] = account_security_html(user)
            with closing(sqlite3.connect(app.config["DATABASE"])) as db, db:
                db.execute("DELETE FROM users")
                db.execute(
                    """INSERT INTO users
                    (id,email,password_hash,role,display_name,status,email_verified,created_at)
                    VALUES (1,?,'',?,'Synthetic label','active',1,'2026-11-01T00:00:00Z')""",
                    (email, role),
                )
            with client.session_transaction() as session:
                session["user_id"] = 1
            response = client.get("/account")
            assert response.status_code == 200
            pages[f"/flask/{role}/{kind}"] = response.get_data(as_text=True)
print(json.dumps({"pages": pages, "privacy": privacy_page_html(), "provider_ui_not_tested": True}))
