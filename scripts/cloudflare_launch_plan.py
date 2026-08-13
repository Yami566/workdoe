from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_readiness import (  # noqa: E402
    DEFAULT_CLERK_PROXY_PROOF_PATH,
    REQUIRED_SECRETS,
    REPO_ROOT,
    ZERO_UUID,
    clerk_proxy_proof_error,
    read_json,
    run_readiness,
)
from cloudflare_release_evidence import secret_evidence_error  # noqa: E402
from cloudflare_wrangler import CLOUDFLARE_API_TOKEN_ENV_VAR, cloudflare_api_token_present  # noqa: E402


@dataclass
class LaunchStep:
    phase: str
    title: str
    status: str
    why: str
    commands: list[str]


def d1_ids_are_configured(wrangler: dict) -> bool:
    d1 = (wrangler.get("d1_databases") or [{}])[0]
    return all(
        bool(d1.get(field)) and d1.get(field) != ZERO_UUID
        for field in ("database_id", "preview_database_id")
    )


def secret_names_from_plan(secret_list_json: Path | None) -> set[str]:
    if not secret_list_json:
        return set()
    data = read_json(secret_list_json)
    if isinstance(data, list):
        return {
            str(item.get("name") if isinstance(item, dict) else item)
            for item in data
            if item
        }
    if not isinstance(data, dict):
        return set()
    items = data.get("result") or data.get("secrets") or data.get("items") or []
    if isinstance(items, list):
        return {
            str(item.get("name") if isinstance(item, dict) else item)
            for item in items
            if item
        }
    return {key for key, value in data.items() if value is True}


def command_block(commands: list[str]) -> list[str]:
    return [command for command in commands if command]


def build_launch_plan(
    repo_root: Path = REPO_ROOT,
    env_file: Path | None = None,
    secret_list_json: Path | None = None,
    clerk_proxy_proof_json: Path | None = None,
) -> dict:
    local = run_readiness(
        repo_root,
        env_file=env_file,
        secret_list_json=secret_list_json,
        clerk_proxy_proof_json=clerk_proxy_proof_json,
    )
    strict = run_readiness(
        repo_root,
        strict_production=True,
        env_file=env_file,
        secret_list_json=secret_list_json,
        clerk_proxy_proof_json=clerk_proxy_proof_json,
    )
    wrangler = read_json(repo_root / "cloudflare" / "wrangler.jsonc")
    d1_ready = d1_ids_are_configured(wrangler)
    secret_names = secret_names_from_plan(secret_list_json)
    missing_secrets = sorted(REQUIRED_SECRETS - secret_names)
    secret_error = secret_evidence_error(secret_list_json) if secret_list_json else (
        "Cloudflare secret evidence is unverified."
    )
    secrets_ready = not secret_error
    proof_error = clerk_proxy_proof_error(clerk_proxy_proof_json)
    clerk_proxy_ready = bool(clerk_proxy_proof_json) and not proof_error
    token_ready = cloudflare_api_token_present()
    strict_args = ["--strict-production"]
    strict_secret_list_path = str(secret_list_json) if secret_list_json else "cloudflare-secret-list.local.json"
    strict_proof_path = str(clerk_proxy_proof_json) if clerk_proxy_proof_json else "clerk-proxy-proof.local.json"
    strict_args.extend(["--secret-list-json", strict_secret_list_path])
    strict_args.extend(["--clerk-proxy-proof-json", strict_proof_path])
    if env_file:
        strict_args.extend(["--env-file", str(env_file)])
    release_evidence_args = [
        "--secret-list-json",
        strict_secret_list_path,
        "--clerk-proxy-proof-json",
        strict_proof_path,
    ]
    release_evidence_command = (
        "python scripts\\cloudflare_release_evidence.py --json "
        + " ".join(release_evidence_args)
    )
    strict_command = "python scripts\\cloudflare_readiness.py " + " ".join(strict_args)

    steps = [
        LaunchStep(
            phase="local-artifacts",
            title="Refresh and validate checked-in Cloudflare artifacts",
            status="ready" if local.ready else "blocked",
            why=(
                "The generated D1 migration, Wrangler config, Worker scaffold, "
                "and same-domain Clerk settings are internally consistent."
                if local.ready
                else "Local Cloudflare artifacts have blockers that must be fixed first."
            ),
            commands=command_block(
                [
                    "python scripts\\prepare_cloudflare_release.py",
                    "python scripts\\cloudflare_preflight.py",
                    "python scripts\\cloudflare_readiness.py",
                ]
            ),
        ),
        LaunchStep(
            phase="cloudflare-token",
            title="Set non-interactive Cloudflare API token",
            status="ready" if token_ready else "pending",
            why=(
                f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is available for local Wrangler automation."
                if token_ready
                else f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is required before local resource bootstrap, secret evidence capture, or production deploy can execute."
            ),
            commands=command_block(
                [
                    "set CLOUDFLARE_API_TOKEN in this shell without committing it",
                    "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
                    "gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe --env production",
                ]
            ),
        ),
        LaunchStep(
            phase="cloudflare-resources",
            title="Create Cloudflare storage and queue resources",
            status="ready" if d1_ready else ("pending" if token_ready else "blocked"),
            why=(
                "D1 production and preview IDs are present in cloudflare/wrangler.jsonc."
                if d1_ready
                else (
                    "D1 IDs are still placeholders; set the Cloudflare API token first, then create the resources and apply the returned IDs with the helper before deploy."
                    if not token_ready
                    else "D1 IDs are still placeholders; create the resources and apply the returned IDs with the helper before deploy."
                )
            ),
            commands=command_block(
                [
                    "python scripts\\cloudflare_resource_bootstrap.py --json --no-secret-probe",
                    "python scripts\\cloudflare_resource_bootstrap.py --execute --yes --no-secret-probe",
                ]
            ),
        ),
        LaunchStep(
            phase="identity-and-secrets",
            title="Configure Clerk, Turnstile, and Workdoe secrets",
            status="ready" if secrets_ready else ("pending" if token_ready else "blocked"),
            why=(
                "The supplied sanitized Wrangler secret-name evidence includes every required secret name."
                if secrets_ready
                else (
                    "Set the Cloudflare API token first; then add the Worker secrets with Wrangler and export the sanitized secret-name list."
                    if not token_ready
                    else "Secret names are not yet proven with sanitized Cloudflare evidence; add them with Wrangler and export the secret-name list."
                )
            ),
            commands=command_block(
                [
                    "cd cloudflare",
                    "wrangler secret put CLERK_PUBLISHABLE_KEY",
                    "wrangler secret put CLERK_SECRET_KEY",
                    "wrangler secret put CLERK_WEBHOOK_SECRET",
                    "wrangler secret put CLERK_JWT_KEY",
                    "wrangler secret put WORKDOE_SECRET_KEY",
                    "wrangler secret put WORKDOE_TURNSTILE_SITE_KEY",
                    "wrangler secret put WORKDOE_TURNSTILE_SECRET_KEY",
                    "python ..\\scripts\\cloudflare_secret_evidence.py --execute --yes --output ..\\cloudflare-secret-list.local.json",
                    "cd ..",
                ]
            ),
        ),
        LaunchStep(
            phase="clerk-domain-proof",
            title="Confirm Clerk same-domain proxy",
            status="ready" if clerk_proxy_ready else "pending",
            why=(
                "The supplied proof confirms Clerk Domains uses https://workdoe.com/__clerk."
                if clerk_proxy_ready
                else "Clerk Domains proof is missing; confirm the Frontend API proxy URL before production deploy."
            ),
            commands=command_block(
                [
                    "confirm Clerk Domains uses proxy URL https://workdoe.com/__clerk",
                    "python scripts\\cloudflare_clerk_proxy_proof.py --confirm",
                ]
            ),
        ),
        LaunchStep(
            phase="deploy-gate",
            title="Run the strict production gate",
            status="ready" if strict.ready else "pending",
            why=(
                "Strict readiness has enough evidence to allow migration and deploy."
                if strict.ready
                else "Strict readiness still has blockers; do not deploy until this step is ready."
            ),
            commands=command_block([release_evidence_command, strict_command]),
        ),
        LaunchStep(
            phase="migrate-and-deploy",
            title="Apply D1 migrations and deploy Workdoe",
            status="ready" if strict.ready else "blocked",
            why=(
                "Production checks are clean, so the migration/deploy commands can run."
                if strict.ready
                else "This phase stays blocked until the strict production gate passes."
            ),
            commands=command_block(
                [
                    "python scripts\\cloudflare_production_deploy.py --json --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json",
                    "python scripts\\cloudflare_production_deploy.py --execute --yes --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json",
                ]
            ),
        ),
        LaunchStep(
            phase="smoke-check",
            title="Smoke check workdoe.com after deploy",
            status="pending",
            why="Run these only after Cloudflare deployment finishes.",
            commands=command_block(
                [
                    "curl.exe -fS -I https://workdoe.com/health",
                    "curl.exe -fsS https://workdoe.com/api/jobs/open?limit=3",
                ]
            ),
        ),
    ]
    overall_status = "ready" if strict.ready else ("blocked" if not local.ready else "pending")
    token_blockers = [] if token_ready else [
        f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run."
    ]
    return {
        "service": "workdoe",
        "domain": "workdoe.com",
        "overall_status": overall_status,
        "safe_by_default": True,
        "executes_commands": False,
        "missing_secrets": missing_secrets,
        "strict_blockers": token_blockers + strict.blockers,
        "strict_warnings": strict.warnings,
        "steps": [asdict(step) for step in steps],
    }


def render_markdown(plan: dict) -> str:
    lines = [
        "# Workdoe Cloudflare Launch Plan",
        "",
        f"Domain: {plan['domain']}",
        f"Status: {plan['overall_status']}",
        "",
        "This plan is safe by default. It prints commands, but does not run them.",
    ]
    if plan["strict_blockers"]:
        lines.extend(["", "## Current Blockers"])
        lines.extend(f"- {item}" for item in plan["strict_blockers"])
    for step in plan["steps"]:
        lines.extend(
            [
                "",
                f"## {step['title']}",
                "",
                f"Status: {step['status']}",
                "",
                step["why"],
                "",
                "```powershell",
            ]
        )
        lines.extend(step["commands"])
        lines.append("```")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print the safe Cloudflare launch sequence for workdoe.com."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable launch plan JSON instead of Markdown.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional .dev.vars-style file to include in readiness gates.",
    )
    parser.add_argument(
        "--secret-list-json",
        type=Path,
        help="Optional sanitized JSON captured by scripts\\cloudflare_secret_evidence.py.",
    )
    parser.add_argument(
        "--clerk-proxy-proof-json",
        type=Path,
        help="Optional JSON proof that Clerk Domains uses https://workdoe.com/__clerk.",
    )
    args = parser.parse_args()
    plan = build_launch_plan(
        env_file=args.env_file,
        secret_list_json=args.secret_list_json,
        clerk_proxy_proof_json=args.clerk_proxy_proof_json,
    )
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(render_markdown(plan), end="")
    return 0 if plan["overall_status"] in {"ready", "pending"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
