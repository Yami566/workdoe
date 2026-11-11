"""Compare standalone Python/JavaScript local Email simulators; never send remotely."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from verify_worker_journey import (
    ROOT,
    NoRedirect,
    free_port,
    local_worker,
    native_workspace,
    require,
    wait_for_worker,
)

FIXTURES = ROOT / "tests" / "email_binding_probe"


def probe_configuration(language: str) -> dict:
    mains = {
        "python": "worker.py",
        "javascript": "control.js",
        "python-subclass": "worker_subclass.py",
    }
    if language not in mains:
        raise ValueError("Only the fixed local probe cases are supported.")
    return {
        "name": f"workdoe-email-probe-{language}-local-only",
        "main": str(FIXTURES / mains[language]),
        "workers_dev": False,
        "compatibility_date": "2026-08-23",
        "compatibility_flags": ["python_workers", "disable_python_external_sdk"],
        "vars": {"PROBE_MODE": "local-only"},
        "send_email": [
            {
                "name": "EMAIL",
                "remote": False,
                "allowed_sender_addresses": ["sender@example.invalid"],
                "allowed_destination_addresses": ["mailbox@example.invalid"],
            }
        ],
    }


def local_environment(environment: dict, stage: Path) -> dict:
    result = {
        key: value
        for key, value in environment.items()
        if not key.startswith(("CLOUDFLARE_", "CF_", "CLERK_", "WORKDOE_", "WRANGLER_"))
    }
    result["WRANGLER_SEND_METRICS"] = "false"
    result["XDG_CONFIG_HOME"] = str(stage / "wrangler-config")
    return result


def read_result(opener, port: int, *, probe: bool = False) -> dict:
    if not 1 <= port <= 65535:
        raise ValueError("Invalid local port.")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/{'probe' if probe else 'health'}",
        method="POST" if probe else "GET",
        data=b"{}" if probe else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        response = opener.open(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read(16385)
        require(len(body) <= 16384, "Local probe response exceeded its bound.")
        return {"http_status": response.status, "result": json.loads(body)}


def readiness(results: dict) -> dict:
    def accepted(result):
        return result == {
            "http_status": 200,
            "result": {"stage": "send-accepted"},
        }

    control_ready = accepted(results.get("javascript"))
    python_ready = accepted(results.get("python"))
    subclass_ready = accepted(results.get("python-subclass"))
    return {
        "control_ready": control_ready,
        "python_binding_ready": python_ready,
        "subclass_binding_ready": subclass_ready,
        "native_probe_ready": control_ready and python_ready and subclass_ready,
        "real_delivery_verified": False,
    }


def run_probe() -> dict:
    node = shutil.which("node")
    wrangler = ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    require(
        bool(node) and wrangler.is_file(),
        "Install pinned development dependencies first.",
    )
    results = {}
    with native_workspace() as stage:
        environment = local_environment(os.environ, stage)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        for language in ("javascript", "python", "python-subclass"):
            directory = stage / language
            directory.mkdir()
            config = directory / "wrangler.jsonc"
            config.write_text(
                json.dumps(probe_configuration(language)), encoding="utf-8"
            )
            port = free_port()
            with (
                (directory / "worker.log").open("w", encoding="utf-8") as log,
                local_worker(
                    [node, str(wrangler)], config, environment, port, log
                ) as process,
            ):

                def check_health(port=port):
                    health = read_result(opener, port)
                    require(
                        health == {"http_status": 200, "result": {"stage": "healthy"}},
                        "Local probe health failed.",
                    )

                wait_for_worker(process, check_health)
                results[language] = read_result(opener, port, probe=True)
    versions = {
        package: json.loads(
            (ROOT / "node_modules" / package / "package.json").read_text(
                encoding="utf-8"
            )
        )["version"]
        for package in ("wrangler", "workerd", "miniflare")
    }
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": "standalone-synthetic-local-only; no production or provider delivery",
        "versions": versions,
        "results": results,
        **readiness(results),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in (
                Path(__file__),
                FIXTURES / "worker.py",
                FIXTURES / "control.js",
                FIXTURES / "worker_subclass.py",
            )
        },
    }
    output = ROOT / ".test-tmp" / "email-binding-probe.local.json"
    output.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run_probe()
    print(json.dumps(result, sort_keys=True, indent=2))
    raise SystemExit(0 if result["native_probe_ready"] else 1)
