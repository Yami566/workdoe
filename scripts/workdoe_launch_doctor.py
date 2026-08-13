from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_LOCAL_URL = "http://127.0.0.1:5000/start"
WORKDOE_DOMAIN = "workdoe.com"
WORKER_SECRET_NAMES = [
    "CLERK_JWT_KEY",
    "CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_WEBHOOK_SECRET",
    "WORKDOE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SITE_KEY",
]

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_launch_status import build_launch_status  # noqa: E402
from github_release_status import (  # noqa: E402
    build_live_status as build_github_live_status,
)
from cloudflare_wrangler import wrangler_command, wrangler_env  # noqa: E402


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


def wrangler_auth_status(repo_root: Path = REPO_ROOT, timeout: float = 20.0) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            wrangler_command(["whoami"], repo_root),
            cwd=str(repo_root / "cloudflare"),
            env=wrangler_env(repo_root),
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return False, "Wrangler CLI is not available."
    except subprocess.TimeoutExpired:
        return False, "Wrangler auth check timed out."

    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value).strip()
    output_lower = output.lower()
    if completed.returncode == 0 and "not authenticated" not in output_lower:
        return True, "Wrangler is authenticated for live Cloudflare operations."
    if "not authenticated" in output_lower:
        return False, "Wrangler is not authenticated. Run `.\\node_modules\\.bin\\wrangler.cmd login`."
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if first_line:
        return False, f"Wrangler auth check failed: {first_line}"
    return False, "Wrangler auth check failed."


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def next_actions(
    *,
    local_ok: bool,
    cloudflare: dict,
    github,
    dns_ready: bool,
    live: bool,
    wrangler_authenticated: bool | None,
) -> list[str]:
    actions: list[str] = []
    if not local_ok:
        actions.append("python run.py")

    if not live:
        actions.append("npm run launch:doctor:live")
    elif github and not github.secrets_ready:
        actions.extend(
            [
                "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe",
                "gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe",
                "npm run github:release:status",
            ]
        )
    if live and wrangler_authenticated is False:
        actions.append(".\\node_modules\\.bin\\wrangler.cmd login")

    blockers = "\n".join(cloudflare["blockers"])
    if "Wrangler D1" in blockers or cloudflare["current_phase"] == "cloudflare-resources":
        actions.extend(
            [
                ".\\node_modules\\.bin\\wrangler.cmd login"
                if not live or wrangler_authenticated is False
                else "",
                "npm run cf:resources:plan",
                "npm run cf:resources:apply",
            ]
        )
    if "Cloudflare is missing required secret bindings" in blockers:
        actions.extend(
            [
                f".\\node_modules\\.bin\\wrangler.cmd secret put {name} --config cloudflare\\wrangler.jsonc"
                for name in WORKER_SECRET_NAMES
            ]
        )
        actions.append("npm run cf:secrets:evidence")
    if "Clerk proxy proof JSON is missing or invalid" in blockers:
        actions.append("npm run cf:clerk:proof")
    if live and not dns_ready:
        actions.append("confirm workdoe.com DNS in Cloudflare")

    if cloudflare["ready_to_deploy"] and (not live or (github and github.ready and dns_ready)):
        actions.extend(
            [
                "npm run cf:deploy:plan",
                "gh workflow run cloudflare-deploy.yml --repo Yami566/workdoe --ref main -f deploy=DEPLOY -f clerk_proxy_url=https://workdoe.com/__clerk",
            ]
        )
    else:
        actions.extend(["npm run cf:deploy:plan", "npm run launch:doctor:live"])
    return dedupe(actions)


def build_doctor(
    repo_root: Path = REPO_ROOT,
    *,
    live: bool = False,
    local_url: str = DEFAULT_LOCAL_URL,
) -> dict:
    local_ok, local_detail = http_head_ok(local_url)
    cloudflare = build_launch_status(repo_root)
    github = build_github_live_status() if live else None
    wrangler_authenticated: bool | None = None
    wrangler_summary = "Wrangler auth was not checked. Run with --live."
    if live:
        wrangler_authenticated, wrangler_summary = wrangler_auth_status(repo_root)
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
            name="wrangler-auth",
            status=(
                "ready"
                if wrangler_authenticated
                else ("pending" if live else "not-checked")
            ),
            summary=wrangler_summary,
            next_command=(
                ".\\node_modules\\.bin\\wrangler.cmd login"
                if live and wrangler_authenticated is False
                else ""
            ),
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
    if live and wrangler_authenticated is False:
        blockers.append("Wrangler is not authenticated for live Cloudflare operations.")
    if live and not dns_ready:
        blockers.append(f"workdoe.com DNS is not resolving: {dns_error}")
    if not local_ok:
        blockers.append(f"Local prototype is not reachable at {local_url}.")

    ready = (
        local_ok
        and (github.ready if github else True)
        and (wrangler_authenticated if live else True)
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
        "next_actions": next_actions(
            local_ok=local_ok,
            cloudflare=cloudflare,
            github=github,
            dns_ready=dns_ready,
            live=live,
            wrangler_authenticated=wrangler_authenticated,
        ),
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
    if payload["next_actions"]:
        lines.extend(["", "Next Actions:"])
        lines.extend(f"- {action}" for action in payload["next_actions"])
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
