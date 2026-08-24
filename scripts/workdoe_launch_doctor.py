from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

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
CLOUDFLARE_TOKEN_ACTION = "set CLOUDFLARE_API_TOKEN in this shell without committing it"
GITHUB_CLOUDFLARE_TOKEN_ACTION = "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_launch_status import build_launch_status
from cloudflare_wrangler import (
    wrangler_command,
    wrangler_env,
)
from github_release_status import (
    build_live_status as build_github_live_status,
)
from workdoe_dns_diagnostic import build_dns_diagnostic


@dataclass
class DoctorPhase:
    name: str
    status: str
    summary: str
    next_command: str = ""


def http_head_ok(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False, "Only HTTP(S) health-check URLs are allowed."
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
            status = getattr(response, "status", 0)
            return 200 <= int(status) < 400, f"HTTP {status}"
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        return False, str(exc)


def dns_check_values(diagnostic: dict, check_name: str) -> list[str]:
    for check in diagnostic.get("checks", []):
        if check.get("name") == check_name:
            return list(check.get("values") or [])
    return []


def render_dns_summary(diagnostic: dict) -> str:
    if diagnostic.get("ready"):
        nameservers = ", ".join(dns_check_values(diagnostic, "nameserver-delegation"))
        apex_addresses = ", ".join(dns_check_values(diagnostic, "apex-resolution"))
        www_addresses = ", ".join(dns_check_values(diagnostic, "www-resolution"))
        return (
            "DNS delegation, apex, www, and the Worker custom-domain policy "
            f"are ready. Nameservers: {nameservers}; apex: {apex_addresses}; www: {www_addresses}."
        )
    pending = [
        f"{check['name']}: {check['summary']}"
        for check in diagnostic.get("checks", [])
        if check.get("status") != "ready"
    ]
    return "; ".join(pending) if pending else "DNS diagnostic did not return ready checks."


def wrangler_auth_status(repo_root: Path = REPO_ROOT, timeout: float = 20.0) -> tuple[bool, str]:
    attempts = [
        ("repository-scoped", wrangler_env(repo_root)),
        ("ambient", None),
    ]
    last_output = ""
    for profile, environment in attempts:
        try:
            completed = subprocess.run(
                wrangler_command(["whoami"], repo_root),
                cwd=str(repo_root / "cloudflare"),
                env=environment,
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
        last_output = output
        output_lower = output.lower()
        if completed.returncode == 0 and "not authenticated" not in output_lower:
            if profile == "ambient":
                return (
                    True,
                    ("Wrangler is authenticated through the ambient encrypted OAuth profile; "
                    "non-interactive release automation still requires CLOUDFLARE_API_TOKEN."),
                )
            return True, "Wrangler is authenticated for live Cloudflare operations."
        if "not authenticated" not in output_lower:
            break

    if "not authenticated" in last_output.lower():
        return False, "Wrangler is not authenticated. Run `.\\node_modules\\.bin\\wrangler.cmd login`."
    first_line = next((line.strip() for line in last_output.splitlines() if line.strip()), "")
    if first_line:
        return False, f"Wrangler auth check failed: {first_line}"
    return False, "Wrangler auth check failed."


def parse_wrangler_secret_names(output: str) -> set[str]:
    start = output.find("[")
    end = output.rfind("]")
    if start < 0 or end < start:
        raise TypeError("Wrangler secret list did not return a JSON array.")
    payload = json.loads(output[start : end + 1])
    if not isinstance(payload, list):
        raise TypeError("Wrangler secret list did not return a JSON array.")
    return {
        str(item.get("name") or "").strip()
        for item in payload
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def wrangler_secret_names_status(
    repo_root: Path = REPO_ROOT,
    timeout: float = 20.0,
) -> tuple[bool, set[str], str]:
    attempts = [wrangler_env(repo_root), None]
    last_output = ""
    for environment in attempts:
        try:
            completed = subprocess.run(
                wrangler_command(["secret", "list", "--config", "wrangler.jsonc"], repo_root),
                cwd=str(repo_root / "cloudflare"),
                env=environment,
                check=False,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            return False, set(), "Wrangler CLI is not available."
        except subprocess.TimeoutExpired:
            return False, set(), "Wrangler secret-name check timed out."

        output = "\n".join(value for value in (completed.stdout, completed.stderr) if value).strip()
        last_output = output
        if completed.returncode == 0:
            try:
                names = parse_wrangler_secret_names(completed.stdout or output)
            except (ValueError, json.JSONDecodeError) as exc:
                return False, set(), f"Wrangler secret-name output was invalid: {exc}"
            return True, names, f"Wrangler returned {len(names)} production secret binding name(s)."
        if "not authenticated" not in output.lower():
            break

    first_line = next((line.strip() for line in last_output.splitlines() if line.strip()), "")
    detail = first_line or "Wrangler secret-name check failed."
    return False, set(), detail


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def cloudflare_token_missing(cloudflare: dict) -> bool:
    blockers = "\n".join(cloudflare.get("blockers") or [])
    return (
        cloudflare.get("current_phase") == "cloudflare-token"
        or "CLOUDFLARE_API_TOKEN is not set" in blockers
    )


def local_cloudflare_token_blocker(blocker: str) -> bool:
    return "CLOUDFLARE_API_TOKEN is not set" in blocker


def missing_worker_secret_names(blockers: list[str]) -> list[str]:
    prefix = "Cloudflare is missing required secret bindings:"
    for blocker in blockers:
        if blocker.startswith(prefix):
            names = {
                name.strip()
                for name in blocker[len(prefix) :].split(",")
                if name.strip() in WORKER_SECRET_NAMES
            }
            return sorted(names)
    return []


def github_release_path_ready(github) -> bool:
    return bool(
        github
        and github.live
        and github.ready
        and github.environment_ready
        and github.secrets_ready
    )


def next_actions(
    *,
    local_ok: bool,
    cloudflare: dict,
    github,
    dns_ready: bool,
    live: bool,
    wrangler_authenticated: bool | None,
    cloudflare_release_ready: bool,
    missing_secret_names: list[str] | None = None,
    dns_next_actions: list[str] | None = None,
) -> list[str]:
    actions: list[str] = []
    token_missing = cloudflare_token_missing(cloudflare)
    github_path_ready = github_release_path_ready(github)
    release_credentials_ready = not token_missing or github_path_ready
    blockers = "\n".join(cloudflare["blockers"])
    if not local_ok:
        actions.append("python run.py")

    if not live:
        actions.append("npm run launch:doctor:live")
    elif github and not github.secrets_ready:
        actions.extend(
            [
                "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
                "gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe --env production",
                "npm run github:release:status",
            ]
        )
    if live and wrangler_authenticated is False:
        actions.append(".\\node_modules\\.bin\\wrangler.cmd login")

    if token_missing and not github_path_ready:
        actions.append(cloudflare.get("next_command") or CLOUDFLARE_TOKEN_ACTION)
        if live and (not github or not github.secrets_ready):
            actions.append(GITHUB_CLOUDFLARE_TOKEN_ACTION)
    if release_credentials_ready and (
        "Wrangler D1" in blockers or cloudflare["current_phase"] == "cloudflare-resources"
    ):
        actions.extend(
            [
                ".\\node_modules\\.bin\\wrangler.cmd login"
                if not live or wrangler_authenticated is False
                else "",
                "npm run cf:resources:plan",
                "npm run cf:resources:apply",
            ]
        )
    if release_credentials_ready and "Cloudflare is missing required secret bindings" in blockers:
        secret_names = missing_secret_names if missing_secret_names is not None else WORKER_SECRET_NAMES
        actions.extend(
            [
                f".\\node_modules\\.bin\\wrangler.cmd secret put {name} --config cloudflare\\wrangler.jsonc"
                for name in secret_names
            ]
        )
        actions.append("npm run cf:secrets:evidence")
    if any("Clerk" in blocker and "proof" in blocker for blocker in cloudflare["blockers"]):
        actions.append("npm run cf:clerk:proof:confirm")
    if live and not dns_ready:
        actions.append("npm run launch:dns")
        actions.extend(dns_next_actions or [])
        actions.append("confirm workdoe.com DNS in Cloudflare")

    if cloudflare_release_ready and (not live or (github and github.ready and dns_ready)):
        actions.extend(
            [
                "npm run cf:deploy:plan",
                "npm run github:deploy:plan",
                "npm run github:deploy",
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
    secret_bindings_checked = False
    present_secret_names: set[str] = set()
    missing_secret_names: list[str] | None = None
    secret_bindings_summary = "Production secret binding names were not checked."
    if live and wrangler_authenticated:
        secret_bindings_checked, present_secret_names, secret_bindings_summary = (
            wrangler_secret_names_status(repo_root)
        )
        if secret_bindings_checked:
            missing_secret_names = sorted(set(WORKER_SECRET_NAMES) - present_secret_names)
            cloudflare = dict(cloudflare)
            cloudflare["blockers"] = [
                blocker
                for blocker in cloudflare["blockers"]
                if not blocker.startswith("Cloudflare is missing required secret bindings:")
            ]
            if missing_secret_names:
                cloudflare["blockers"].append(
                    "Cloudflare is missing required secret bindings: "
                    + ", ".join(missing_secret_names)
                )
    evidence_missing_secret_names = missing_worker_secret_names(cloudflare["blockers"])
    effective_missing_secret_names = (
        missing_secret_names
        if secret_bindings_checked and missing_secret_names is not None
        else evidence_missing_secret_names
    )
    binding_evidence_source = "live-wrangler" if secret_bindings_checked else "unavailable"
    if not secret_bindings_checked and evidence_missing_secret_names:
        binding_evidence_source = "sanitized-evidence"
        secret_bindings_summary = (
            "Live Wrangler secret-name probing requires a local API token; sanitized "
            f"evidence reports {len(WORKER_SECRET_NAMES) - len(evidence_missing_secret_names)}/"
            f"{len(WORKER_SECRET_NAMES)} required names present."
        )
    github_path_ready = github_release_path_ready(github)
    token_missing = cloudflare_token_missing(cloudflare)
    cloudflare_release_blockers = [
        blocker
        for blocker in cloudflare["blockers"]
        if not (github_path_ready and local_cloudflare_token_blocker(blocker))
    ]
    cloudflare_release_ready = (
        not cloudflare_release_blockers
        and (not token_missing or github_path_ready)
    )
    cloudflare_next_command = cloudflare["next_command"]
    if github_path_ready and token_missing:
        if effective_missing_secret_names:
            cloudflare_next_command = (
                ".\\node_modules\\.bin\\wrangler.cmd secret put "
                f"{effective_missing_secret_names[0]} --config cloudflare\\wrangler.jsonc"
            )
        elif any("Clerk" in blocker and "proof" in blocker for blocker in cloudflare_release_blockers):
            cloudflare_next_command = "npm run cf:clerk:proof:confirm"
        else:
            cloudflare_next_command = "npm run cf:deploy:plan"
    dns_ready = False
    dns_phase_summary = "DNS was not checked. Run with --live to resolve workdoe.com."
    dns_addresses: list[str] = []
    dns_diagnostic: dict | None = None
    dns_blockers: list[str] = []
    dns_next_actions: list[str] = []
    if live:
        dns_diagnostic = build_dns_diagnostic()
        dns_ready = bool(dns_diagnostic["ready"])
        dns_phase_summary = render_dns_summary(dns_diagnostic)
        dns_addresses = sorted(
            set(
                dns_check_values(dns_diagnostic, "apex-resolution")
                + dns_check_values(dns_diagnostic, "www-resolution")
            )
        )
        dns_blockers = list(dns_diagnostic.get("blockers") or [])
        dns_next_actions = list(dns_diagnostic.get("next_actions") or [])

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
            status="ready" if cloudflare_release_ready else "pending",
            summary=(
                "Cloudflare launch gate is ready to deploy."
                if cloudflare_release_ready
                else (
                    (
                        "GitHub production automation credentials are ready; "
                        "Cloudflare release evidence still has blockers. "
                        if github_path_ready and token_missing
                        else f"Cloudflare launch gate is waiting at {cloudflare['current_phase']}. "
                    )
                    + (
                        f"Worker secret evidence: {len(WORKER_SECRET_NAMES) - len(effective_missing_secret_names)}/{len(WORKER_SECRET_NAMES)} required present."
                        if effective_missing_secret_names
                        else "Direct non-interactive secret-name probing requires CLOUDFLARE_API_TOKEN; the release gate uses sanitized local evidence when present."
                    )
                )
            ),
            next_command=cloudflare_next_command,
        ),
        DoctorPhase(
            name="dns",
            status="ready" if dns_ready else ("pending" if live else "not-checked"),
            summary=dns_phase_summary,
            next_command="confirm workdoe.com DNS in Cloudflare" if live and not dns_ready else "",
        ),
    ]

    blockers = list(cloudflare_release_blockers)
    if github:
        blockers.extend(github.blockers)
    if live and wrangler_authenticated is False:
        blockers.append("Wrangler is not authenticated for live Cloudflare operations.")
    if live and not dns_ready:
        blockers.extend(f"DNS: {blocker}" for blocker in dns_blockers)
    if not local_ok:
        blockers.append(f"Local prototype is not reachable at {local_url}.")

    ready = (
        local_ok
        and (github.ready if github else True)
        and (wrangler_authenticated if live else True)
        and cloudflare_release_ready
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
            set(
                cloudflare["warnings"]
                + (list(github.warnings) if github else [])
                + (
                    [
                        "Local CLOUDFLARE_API_TOKEN is not set; the verified GitHub production environment remains the credentialed non-interactive deployment path."
                    ]
                    if github_path_ready and token_missing
                    else []
                )
            )
        ),
        "dns_addresses": dns_addresses,
        "dns": dns_diagnostic,
        "secret_bindings": {
            "checked": secret_bindings_checked,
            "source": binding_evidence_source,
            "required_count": len(WORKER_SECRET_NAMES),
            "present_count": (
                len(present_secret_names)
                if secret_bindings_checked
                else len(WORKER_SECRET_NAMES) - len(effective_missing_secret_names)
                if evidence_missing_secret_names
                else 0
            ),
            "missing": effective_missing_secret_names,
            "summary": secret_bindings_summary,
        },
        "next_actions": next_actions(
            local_ok=local_ok,
            cloudflare=cloudflare,
            github=github,
            dns_ready=dns_ready,
            live=live,
            wrangler_authenticated=wrangler_authenticated,
            cloudflare_release_ready=cloudflare_release_ready,
            missing_secret_names=effective_missing_secret_names,
            dns_next_actions=dns_next_actions,
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
