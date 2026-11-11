"""Exercise discovery failures and configured/fallback budgets on disposable local bindings."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from functools import partial

from verify_worker_journey import (
    ROOT,
    NoRedirect,
    free_port,
    local_storage_arguments,
    local_worker,
    native_workspace,
    require,
    wait_for_worker,
)

BROWSE = "/?q=synthetic-outage-search"
INVITATION = "/create-account?__clerk_ticket=synthetic-outage-invitation"
JOBS = "/api/jobs/open"
DATABASE = "workdoe-native-entry-resilience"
DRAFT = "/post-project?fixture=synthetic-outage-draft"
DRAFT_COOKIE = "workdoe_job_draft=synthetic-draft-cookie"


def status_probe(opener, base: str, phase: str):
    def expect(path: str, expected: int, *, method: str = "GET", draft: bool = False):
        incoming = urllib.request.Request(
            base + path, method=method, headers={"Cookie": DRAFT_COOKIE} if draft else {},
        )
        try:
            response = opener.open(incoming, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status, headers, body = response.status, response.headers, response.read(256 * 1024)
        require(status == expected, f"{phase}: {method} {path} got {status}, expected {expected}")
        if method == "HEAD":
            require(not body, "HEAD response included a body")
        if expected in (429, 503):
            require(
                headers.get("Cache-Control") == "no-store"
                and headers.get("Retry-After") == ("5" if draft else "60")
                and headers.get("Referrer-Policy") == ("no-referrer" if draft else "strict-origin"),
                "Recovery response lost retry or privacy headers",
            )
        return headers, body
    return expect


def verify(*, browser: bool, webkit: bool) -> None:
    node = shutil.which("node")
    wrangler = ROOT / "node_modules/wrangler/bin/wrangler.js"
    if not node or not wrangler.is_file():
        raise RuntimeError("Use the pinned local Wrangler and Node installation.")
    browser_env = {
        name: os.environ[name] for name in ("WORKDOE_PLAYWRIGHT_MODULE", "WORKDOE_CHROMIUM_EXECUTABLE")
    } if browser else {}
    cli = [node, str(wrangler)]
    env = {key: value for key, value in os.environ.items() if not key.startswith(
        ("CLOUDFLARE_", "CF_", "CLERK_", "WORKDOE_", "RESEND_", "WRANGLER_"),
    )}
    env.update(CI="true", WRANGLER_SEND_METRICS="false", WRANGLER_WRITE_LOGS="false")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    with native_workspace() as stage:
        env["XDG_CONFIG_HOME"] = str(stage / "wrangler-config")
        shutil.copytree(ROOT / "cloudflare/worker", stage / "worker", ignore=shutil.ignore_patterns("__pycache__"))
        config = stage / "wrangler.jsonc"
        log_path = stage / "worker.log"
        production = json.loads((ROOT / "cloudflare/wrangler.jsonc").read_text(encoding="utf-8"))
        settings = {
            "name": "workdoe-entry-resilience-local-only",
            "main": "worker/entry.py",
            "workers_dev": False,
            "preview_urls": False,
            "compatibility_date": production["compatibility_date"],
            "compatibility_flags": production["compatibility_flags"],
            "assets": {"binding": "ASSETS", "directory": str(ROOT / "workdoe/static"), "run_worker_first": True},
            "d1_databases": [{
                "binding": "DB", "database_name": DATABASE, "remote": False,
                "database_id": "00000000-0000-4000-8000-000000000002",
                "migrations_dir": str(ROOT / "cloudflare/d1/migrations"),
            }],
            "vars": {
                "WORKDOE_ENV": "production", "WORKDOE_AUTH_PROVIDER": "clerk", "WORKDOE_MAP_MODE": "list",
                "WORKDOE_SECRET_KEY": "s" * 32,
            },
        }

        for phase in ("unconfigured", "missing-budget", "listings-down", "budget", "fallback-budget"):
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            settings["vars"].update(WORKDOE_PUBLIC_URL=base, WORKDOE_DOMAIN="localhost")
            if phase != "unconfigured":
                settings["vars"]["CLERK_PUBLISHABLE_KEY"] = "pk_live_synthetic_fixture"
            settings.pop("ratelimits", None)
            if phase in {"listings-down", "fallback-budget"}:
                settings["ratelimits"] = [{
                    "name": "WRITE_RATE_LIMITER",
                    "namespace_id": "10004" if phase == "fallback-budget" else "10002",
                    "simple": {"limit": 3 if phase == "fallback-budget" else 100000, "period": 60},
                }]
            elif phase == "budget":
                settings["ratelimits"] = [{
                    "name": "PUBLIC_DISCOVERY_RATE_LIMITER", "namespace_id": "10003",
                    "simple": {"limit": 3, "period": 60},
                }]
            config.write_text(json.dumps(settings), encoding="utf-8")
            expect_status = status_probe(opener, base, phase)

            if phase in {"budget", "fallback-budget"}:
                subprocess.run(
                    [*cli, *local_storage_arguments(["d1", "migrations", "apply", DATABASE, "--local"], config)],
                    cwd=stage, env=env, check=True, capture_output=True, timeout=120,
                )
            try:
                with log_path.open("w", encoding="utf-8") as log, local_worker(cli, config, env, port, log) as process:
                    wait_for_worker(process, partial(expect_status, "/health", 200))
                    if phase == "unconfigured":
                        for path in (BROWSE, INVITATION):
                            headers, body = expect_status(path, 503)
                            expect_status(path, 503, method="HEAD")
                            require(
                                headers.get("Content-Type", "").startswith("text/html")
                                and b"entry-unavailable-title" in body and b"<script" not in body
                                and b"synthetic-outage-" not in body,
                                "Recovery document reflected data or loaded scripts",
                            )
                        headers, body = expect_status(JOBS, 503)
                        require(headers.get_content_type() == "application/json" and not json.loads(body)["ok"],
                                "Jobs API lost its JSON failure response")
                        headers, body = expect_status(DRAFT, 503, draft=True)
                        expect_status(DRAFT, 503, method="HEAD", draft=True)
                        require(
                            b"draft-unavailable-title" in body and b"<script" not in body
                            and b"synthetic-outage-draft" not in body
                            and b"synthetic-draft-cookie" not in body and "Set-Cookie" not in headers,
                            "Draft recovery disclosed request data or changed the draft cookie",
                        )
                        if browser:
                            script = ROOT / "tests/browser/public_entry_resilience.cjs"
                            engines = ([], ["--webkit"]) if webkit else ([],)
                            for engine in engines:
                                subprocess.run(
                                    [node, str(script), *engine], cwd=ROOT, check=True, timeout=120,
                                    env=env | browser_env | {"WORKDOE_OUTAGE_PREVIEW_URL": base + "/"},
                                )
                    elif phase == "missing-budget":
                        for path in (BROWSE, JOBS):
                            expect_status(path, 503)
                            expect_status(path, 503, method="HEAD")
                        for path in ("/login?embed=1", "/login?embed=1&job_id=demo-02"):
                            _, body = expect_status(path, 200)
                            require(b"data-clerk-entry" in body and b"data-tile-url" not in body,
                                    "Missing read protection blocked generic account entry")
                        expect_status("/health", 200)
                    elif phase == "listings-down":
                        expect_status(BROWSE, 503)
                        for path in ("/login?next=/dashboard", INVITATION + "&embed=1&job_id=1"):
                            headers, body = expect_status(path, 200)
                            require(
                                b"Project listings are temporarily unavailable" in body and b"data-clerk-entry" in body
                                and b"data-dialog-fragment" in body and b"data-tile-url" not in body
                                and b"synthetic-outage-invitation" not in body,
                                "The account form did not survive the listing read failure",
                            )
                            if path.startswith(INVITATION):
                                require(headers["Referrer-Policy"] == "strict-origin", "Invitation referrer changed")
                    else:
                        expect_status(JOBS + "?north=39", 400)
                        expect_status(JOBS, 200, method="OPTIONS")
                        expect_status("/login?embed=1&job_id=demo-02", 200)
                        expect_status(BROWSE, 200)
                        expect_status(JOBS, 200)
                        expect_status(JOBS, 200, method="HEAD")
                        for path in (BROWSE, JOBS):
                            expect_status(path, 429)
                            expect_status(path, 429, method="HEAD")
                        for path in ("/login", "/login?embed=1", INVITATION + "&embed=1&job_id=1"):
                            _, body = expect_status(path, 200)
                            require(b"data-clerk-entry" in body and b"data-tile-url" not in body,
                                    "Exhausting the discovery budget blocked account entry")
                        expect_status("/health", 200)
            except Exception:
                diagnostic = "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-14:])
                print(diagnostic.encode("ascii", errors="backslashreplace").decode("ascii"))
                raise
            print(f"PASS: local entry resilience ({phase})", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true", help="Exercise the recovery pages in installed Chromium.")
    parser.add_argument("--webkit", action="store_true", help="Also use the installed Playwright WebKit build.")
    args = parser.parse_args()
    verify(browser=args.browser or args.webkit, webkit=args.webkit)
