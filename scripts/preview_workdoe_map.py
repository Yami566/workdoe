"""Serve the local marketplace with a temporary database and no external map provider."""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workdoe import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("area", "list"), default="area")
    parser.add_argument("--port", type=int, default=8897)
    args = parser.parse_args()
    with TemporaryDirectory(prefix="workdoe-map-preview-") as directory:
        root = Path(directory)
        app = create_app({
            "WORKDOE_ENV": "local", "PRODUCTION": False, "SECRET_KEY": secrets.token_hex(32),
            "AUTH_PROVIDER": "local", "CLERK_PUBLISHABLE_KEY": "", "CLERK_SECRET_KEY": "",
            "SESSION_COOKIE_SECURE": False, "SHOW_LOCAL_LOGIN_CODE": True, "SEED_DEMO_DATA": True,
            "DATABASE": str(root / "preview.sqlite3"), "UPLOAD_ROOT": str(root / "uploads"),
            "MAP_MODE": args.mode, "TURNSTILE_SITE_KEY": "", "TURNSTILE_SECRET_KEY": "",
            "ENFORCE_SERVICE_ACTIVATION": False,
        })
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
