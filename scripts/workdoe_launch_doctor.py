from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_LOCAL_URL = "http://127.0.0.1:5000/start"
WORKDOE_DOMAIN = "workdoe.com"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_launch_status import build_launch_status  # noqa: E402
from github_release_status import (  # noqa: E402
    build_live_status as build_github_live_status,
)


@dataclass
class DoctorPhase:
    name: str
    status: str
    summary: str
    next_command: str = ""


def http_head_ok(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = getattr(response, "status", 0)
            return 200 <= int(status) < 400, f"HTTP {status}"
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        return False, str(exc)


def dns_lookup(domain: str = WORKDOE_DOMAIN) -> tuple[bool, list[str], str]:
    try:
        records = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        return False, [], str(exc)
    addresses = sorted({record[4][0] for record in records if record[4]})
    return bool(addresses), addresses, ""


def build_doctor(
    repo_root: Path = REPO_ROOT,
    *,
    live: bool = False,
    local_url: str = DEFAULT_LOCAL_URL,
) -> dict:
    local_ok, local_detail = http_head_ok(local_url)
    cloudflare = build_launch_status(repo_root)
    github = build_github_live_status() if live else None
    dns_ready = False
    dns_summary = "DNS was not checked. Run with --live to resolve workdoe.com."
    dns_addresses: list[str] = []
    dns_error = ""
    if live:
        dns_ready, dns_addresses, dns_error = dns_lookup()
        dns_summary = (
            f"workdoe.com resolves to {', '.join(dns_addresses)}."
            if dns_ready
            else f"workdoe.com does not resolve: {dns_error}"
        )

    phases = [
        DoctorPhase(
            name="local-prototype",
            status="ready" if local_ok else "pending",
            summary=f"{local_url} returned {local_detail}." if local_ok else f"{local_url} is not reachable: {local_detail}",
            next_command="python run.py" if not local_ok else "",
        ),
        DoctorPhase(
            name="github-release",
            status=("ready" if github and github.ready else ("pending" if live else "not-checked")),
            summary=(
                "GitHub production environment and deploy secrets are ready."
                if github and github.ready
                else (
                    "GitHub release setup still has blockers."
                    if live
                    else "GitHub release setup was not checked. Run with --live."
                )
            ),
            next_command="npm run github:release:status",
        ),
        DoctorPhase(
            name="cloudflare-release",
            status="ready" if cloudflare["ready_to_deploy"] else "pending",
            summary=(
                "Cloudflare launch gate is ready to deploy."
                if cloudflare["ready_to_deploy"]
                else f"Cloudflare launch gate is waiting at {cloudflare['current_phase']}."
            ),
            next_command=cloudflare["next_command"],
        ),
        DoctorPhase(
            name="dns",
            status="ready" if dns_ready else ("pending" if live else "not-checked"),
            summary=dns_summary,
            next_command="confirm workdoe.com DNS in Cloudflare" if live and not dns_ready else "",
        ),
    ]

    blockers = list(cloudflare["blockers"])
    if github:
        blockers.extend(github.blockers)
    if live and not dns_ready:
        blockers.append(f"workdoe.com DNS is not resolving: {dns_error}")
    if not local_ok:
        blockers.append(f"Local prototype is not reachable at {local_url}.")

    ready = (
        local_ok
        and (github.ready if github else True)
        and cloudflare["ready_to_deploy"]
        and (dns_ready if live else True)
    )
    return {
        "service": "workdoe",
        "domain": WORKDOE_DOMAIN,
        "live": live,
        "ready": ready,
        "phases": [asdict(phase) for phase in phases],
        "blockers": sorted(set(blockers)),
        "warnings": sorted(
            set(cloudflare["warnings"] + (list(github.warnings) if github else []))
        ),
        "dns_addresses": dns_addresses,
    }


def render_text(payload: dict) -> str:
    lines = [
        "Workdoe launch doctor",
        f"Domain: {payload['domain']}",
        f"Live checks: {payload['live']}",
        f"Ready: {payload['ready']}",
        "",
        "Phases:",
    ]
    lines.extend(
        f"- {phase['name']}: {phase['status']} - {phase['summary']}"
        for phase in payload["phases"]
    )
    if payload["blockers"]:
        lines.extend(["", "Blockers:"])
        lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    if payload["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in payload["warnings"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize Workdoe local, GitHub, DNS, and Cloudflare launch readiness."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--live", action="store_true", help="Run live GitHub and DNS checks.")
    parser.add_argument(
        "--local-url",
        default=DEFAULT_LOCAL_URL,
        help="Local prototype URL to check.",
    )
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when launch doctor is not ready.",
    )
    args = parser.parse_args()
    payload = build_doctor(live=args.live, local_url=args.local_url)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.fail_when_not_ready and not payload["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
