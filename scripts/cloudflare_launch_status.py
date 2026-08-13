from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SECRET_LIST_PATH = REPO_ROOT / "cloudflare-secret-list.local.json"
DEFAULT_CLERK_PROXY_PROOF_PATH = REPO_ROOT / "clerk-proxy-proof.local.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_launch_plan import build_launch_plan  # noqa: E402
from cloudflare_preflight import run_preflight  # noqa: E402
from cloudflare_release_evidence import run_release_evidence  # noqa: E402
from cloudflare_resource_bootstrap import plan_payload as resource_plan_payload  # noqa: E402
from cloudflare_wrangler import (  # noqa: E402
    CLOUDFLARE_API_TOKEN_ENV_VAR,
    WRANGLER_ENV_VAR,
    cloudflare_api_token_present,
    resolved_wrangler_bin,
    wrangler_available,
)


@dataclass
class StatusPhase:
    name: str
    status: str
    summary: str
    next_command: str = ""


def first_command(step: dict) -> str:
    commands = step.get("commands") or []
    return commands[0] if commands else ""


def phase_status(plan_step: dict) -> str:
    status = str(plan_step.get("status") or "pending")
    return "ready" if status == "ready" else status


def next_pending_phase(phases: list[StatusPhase]) -> StatusPhase | None:
    for phase in phases:
        if phase.status != "ready":
            return phase
    return None


def build_launch_status(
    repo_root: Path = REPO_ROOT,
    *,
    env_file: Path | None = None,
    secret_list_json: Path | None = DEFAULT_SECRET_LIST_PATH,
    clerk_proxy_proof_json: Path | None = DEFAULT_CLERK_PROXY_PROOF_PATH,
) -> dict:
    preflight = run_preflight(repo_root)
    launch_plan = build_launch_plan(
        repo_root,
        env_file=env_file,
        secret_list_json=secret_list_json,
        clerk_proxy_proof_json=clerk_proxy_proof_json,
    )
    resource_plan = resource_plan_payload(
        repo_root,
        include_secret_probe=False,
    )
    release_evidence = run_release_evidence(
        secret_list_json=secret_list_json,
        clerk_proxy_proof_json=clerk_proxy_proof_json,
    )
    plan_steps = {step["phase"]: step for step in launch_plan["steps"]}

    local_status = "ready" if preflight.ok else "blocked"
    wrangler_bin = resolved_wrangler_bin(repo_root)
    tooling_ready = wrangler_available(repo_root)
    token_ready = cloudflare_api_token_present()
    resource_status = phase_status(plan_steps["cloudflare-resources"])
    secret_status = phase_status(plan_steps["identity-and-secrets"])
    evidence_status = "ready" if release_evidence["ok"] else "pending"
    deploy_status = phase_status(plan_steps["deploy-gate"])

    phases = [
        StatusPhase(
            name="local-artifacts",
            status=local_status,
            summary=(
                f"{len(preflight.checks)} local Cloudflare checks passed."
                if preflight.ok
                else "Local Cloudflare artifacts need attention."
            ),
            next_command="python scripts\\cloudflare_preflight.py",
        ),
        StatusPhase(
            name="local-tooling",
            status="ready" if tooling_ready else "blocked",
            summary=(
                f"Wrangler CLI is available at {wrangler_bin}."
                if tooling_ready
                else "Wrangler CLI is not available on PATH, local node_modules, or WORKDOE_WRANGLER_BIN."
            ),
            next_command="npm install",
        ),
        StatusPhase(
            name="cloudflare-token",
            status="ready" if token_ready else "pending",
            summary=(
                f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is available for local Wrangler automation."
                if token_ready
                else f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is not set; execute steps will stop before calling Wrangler."
            ),
            next_command="set CLOUDFLARE_API_TOKEN in this shell without committing it",
        ),
        StatusPhase(
            name="cloudflare-resources",
            status=resource_status,
            summary=(
                "D1 IDs are configured in Wrangler."
                if resource_plan["d1_ids_configured"]
                else "D1 production and preview IDs are still placeholders."
            ),
            next_command=first_command(plan_steps["cloudflare-resources"]),
        ),
        StatusPhase(
            name="identity-and-secrets",
            status=secret_status,
            summary=(
                "Required Worker secret names are proven from sanitized evidence."
                if secret_status == "ready"
                else "Required Clerk, Turnstile, and Workdoe secret names are not proven yet."
            ),
            next_command=first_command(plan_steps["identity-and-secrets"]),
        ),
        StatusPhase(
            name="clerk-domain-proof",
            status=phase_status(plan_steps["clerk-domain-proof"]),
            summary=(
                "Clerk Domains proof confirms https://workdoe.com/__clerk."
                if not any("Clerk" in blocker for blocker in release_evidence["blockers"])
                else "Clerk Domains proof is missing or invalid."
            ),
            next_command=first_command(plan_steps["clerk-domain-proof"]),
        ),
        StatusPhase(
            name="release-evidence",
            status=evidence_status,
            summary=(
                "Secret-name and Clerk proxy evidence are both valid."
                if release_evidence["ok"]
                else "Secret-name evidence and Clerk proxy proof must both pass."
            ),
            next_command="python scripts\\cloudflare_release_evidence.py --json",
        ),
        StatusPhase(
            name="deploy-gate",
            status=deploy_status,
            summary=(
                "Strict production readiness allows deploy."
                if deploy_status == "ready"
                else "Strict production readiness still blocks deploy."
            ),
            next_command=first_command(plan_steps["deploy-gate"]),
        ),
    ]
    current = next_pending_phase(phases)
    blockers = list(preflight.errors) + list(launch_plan["strict_blockers"]) + list(
        release_evidence["blockers"]
    )
    if not tooling_ready:
        blockers.append(
            "Wrangler CLI is not available; install Wrangler, add it to PATH, or set "
            f"`{WRANGLER_ENV_VAR}` before live Cloudflare steps."
        )
    if not token_ready:
        blockers.append(
            f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run."
        )

    return {
        "service": "workdoe",
        "domain": "workdoe.com",
        "safe_by_default": True,
        "executes_commands": False,
        "ready_to_deploy": token_ready and deploy_status == "ready" and release_evidence["ok"],
        "current_phase": current.name if current else "deploy",
        "next_command": current.next_command if current else "python scripts\\cloudflare_production_deploy.py --json",
        "phases": [asdict(phase) for phase in phases],
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(preflight.warnings + launch_plan["strict_warnings"])),
    }


def render_text(status: dict) -> str:
    lines = [
        "Workdoe Cloudflare launch status",
        f"Domain: {status['domain']}",
        f"Ready to deploy: {status['ready_to_deploy']}",
        f"Current phase: {status['current_phase']}",
        f"Next command: {status['next_command']}",
        "",
        "Phases:",
    ]
    lines.extend(
        f"- {phase['name']}: {phase['status']} - {phase['summary']}"
        for phase in status["phases"]
    )
    if status["blockers"]:
        lines.extend(["", "Blockers:"])
        lines.extend(f"- {blocker}" for blocker in status["blockers"])
    if status["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {warning}" for warning in status["warnings"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a read-only Workdoe Cloudflare launch status summary."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--secret-list-json",
        type=Path,
        default=DEFAULT_SECRET_LIST_PATH,
        help="Sanitized JSON captured by scripts\\cloudflare_secret_evidence.py.",
    )
    parser.add_argument(
        "--clerk-proxy-proof-json",
        type=Path,
        default=DEFAULT_CLERK_PROXY_PROOF_PATH,
        help="JSON proof that Clerk Domains uses https://workdoe.com/__clerk.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional .dev.vars-style file to include in strict readiness.",
    )
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when the status is not ready to deploy.",
    )
    args = parser.parse_args()
    payload = build_launch_status(
        env_file=args.env_file,
        secret_list_json=args.secret_list_json,
        clerk_proxy_proof_json=args.clerk_proxy_proof_json,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.fail_when_not_ready and not payload["ready_to_deploy"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
