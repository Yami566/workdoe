from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CLOUDFLARE_DIR = REPO_ROOT / "cloudflare"
DEFAULT_SECRET_LIST_PATH = REPO_ROOT / "cloudflare-secret-list.local.json"
DEFAULT_CLERK_PROXY_PROOF_PATH = REPO_ROOT / "clerk-proxy-proof.local.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_readiness import run_readiness  # noqa: E402
from cloudflare_wrangler import wrangler_command, wrangler_env  # noqa: E402


SMOKE_OUTPUT_MAX = 1200


@dataclass
class DeployStep:
    name: str
    command: list[str]
    cwd: str
    status: str = "pending"
    required: bool = True
    output_excerpt: str = ""


def build_deploy_steps(
    repo_root: Path = REPO_ROOT,
    include_smoke: bool = True,
) -> list[DeployStep]:
    cloudflare_dir = repo_root / "cloudflare"
    steps = [
        DeployStep(
            name="apply-d1-migrations",
            command=wrangler_command(["d1", "migrations", "apply", "workdoe", "--remote"], repo_root),
            cwd=str(cloudflare_dir),
        ),
        DeployStep(
            name="deploy-worker",
            command=wrangler_command(["deploy"], repo_root),
            cwd=str(cloudflare_dir),
        ),
    ]
    if include_smoke:
        steps.extend(
            [
                DeployStep(
                    name="smoke-health",
                    command=["curl.exe", "-fS", "-I", "https://workdoe.com/health"],
                    cwd=str(repo_root),
                    required=False,
                ),
                DeployStep(
                    name="smoke-public-jobs",
                    command=["curl.exe", "-fsS", "https://workdoe.com/api/jobs/open?limit=3"],
                    cwd=str(repo_root),
                    required=False,
                ),
            ]
        )
    return steps


def readiness_payload(
    repo_root: Path = REPO_ROOT,
    secret_list_json: Path | None = DEFAULT_SECRET_LIST_PATH,
    env_file: Path | None = None,
    clerk_proxy_proof_json: Path | None = DEFAULT_CLERK_PROXY_PROOF_PATH,
) -> dict:
    result = run_readiness(
        repo_root,
        strict_production=True,
        env_file=env_file,
        secret_list_json=secret_list_json,
        clerk_proxy_proof_json=clerk_proxy_proof_json,
    )
    return result.as_dict()


def plan_payload(
    repo_root: Path = REPO_ROOT,
    secret_list_json: Path | None = DEFAULT_SECRET_LIST_PATH,
    env_file: Path | None = None,
    clerk_proxy_proof_json: Path | None = DEFAULT_CLERK_PROXY_PROOF_PATH,
    include_smoke: bool = True,
    dry_run: bool = True,
) -> dict:
    readiness = readiness_payload(
        repo_root,
        secret_list_json=secret_list_json,
        env_file=env_file,
        clerk_proxy_proof_json=clerk_proxy_proof_json,
    )
    return {
        "ok": True,
        "dry_run": dry_run,
        "executes_commands": not dry_run,
        "service": "workdoe",
        "domain": "workdoe.com",
        "ready_to_deploy": bool(readiness["ready"]),
        "strict_blockers": readiness["blockers"],
        "strict_warnings": readiness["warnings"],
        "steps": [asdict(step) for step in build_deploy_steps(repo_root, include_smoke)],
    }


def run_external(step: DeployStep) -> subprocess.CompletedProcess:
    return subprocess.run(
        step.command,
        cwd=step.cwd,
        env=wrangler_env(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def command_output(completed: subprocess.CompletedProcess) -> str:
    return "\n".join(
        value for value in (completed.stdout, completed.stderr) if value
    ).strip()


def smoke_output_excerpt(completed: subprocess.CompletedProcess) -> str:
    output = command_output(completed)
    if len(output) <= SMOKE_OUTPUT_MAX:
        return output
    return output[:SMOKE_OUTPUT_MAX].rstrip() + "\n[truncated]"


def execute_steps(
    steps: list[DeployStep],
    continue_on_smoke_failure: bool = True,
) -> tuple[list[DeployStep], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for step in steps:
        try:
            completed = run_external(step)
        except OSError as exc:  # pragma: no cover - depends on operator machine PATH
            step.status = "failed"
            message = f"{step.name}: {exc}"
            if step.required or not continue_on_smoke_failure:
                errors.append(message)
            else:
                warnings.append(message)
            if step.required:
                break
            continue
        if not step.required:
            step.output_excerpt = smoke_output_excerpt(completed)
        if completed.returncode == 0:
            step.status = "done"
            continue
        detail = command_output(completed)
        step.status = "failed"
        message = f"{step.name}: {detail or 'command failed'}"
        if step.required or not continue_on_smoke_failure:
            errors.append(message)
        else:
            warnings.append(message)
        if step.required or not continue_on_smoke_failure:
            break
    return steps, errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Guard Workdoe production D1 migration and Cloudflare Worker deploy."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run migration, deploy, and smoke-check commands.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required with --execute to confirm production deployment.",
    )
    parser.add_argument(
        "--secret-list-json",
        type=Path,
        default=DEFAULT_SECRET_LIST_PATH,
        help="Sanitized JSON captured by scripts\\cloudflare_secret_evidence.py.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional .dev.vars-style file to include in strict readiness.",
    )
    parser.add_argument(
        "--clerk-proxy-proof-json",
        type=Path,
        default=DEFAULT_CLERK_PROXY_PROOF_PATH,
        help="JSON proof that Clerk Domains uses https://workdoe.com/__clerk.",
    )
    parser.add_argument(
        "--no-smoke",
        action="store_true",
        help="Skip post-deploy smoke checks.",
    )
    parser.add_argument(
        "--fail-on-smoke",
        action="store_true",
        help="Treat smoke-check failures as deployment failures.",
    )
    args = parser.parse_args()
    include_smoke = not args.no_smoke

    if not args.execute:
        payload = plan_payload(
            secret_list_json=args.secret_list_json,
            env_file=args.env_file,
            clerk_proxy_proof_json=args.clerk_proxy_proof_json,
            include_smoke=include_smoke,
            dry_run=True,
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Workdoe production deploy plan")
            print("Dry run: no commands were executed.")
            print(f"Ready to deploy: {payload['ready_to_deploy']}")
            for blocker in payload["strict_blockers"]:
                print(f"- blocker: {blocker}")
            for step in payload["steps"]:
                print(f"- {step['name']}: {' '.join(step['command'])}")
        return 0

    if not args.yes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "--execute requires --yes so production deploy is explicit.",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    readiness = readiness_payload(
        secret_list_json=args.secret_list_json,
        env_file=args.env_file,
        clerk_proxy_proof_json=args.clerk_proxy_proof_json,
    )
    if not readiness["ready"]:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Strict production readiness failed; deploy was not run.",
                    "blockers": readiness["blockers"],
                    "warnings": readiness["warnings"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    steps, errors, warnings = execute_steps(
        build_deploy_steps(include_smoke=include_smoke),
        continue_on_smoke_failure=not args.fail_on_smoke,
    )
    payload = {
        "ok": not errors,
        "dry_run": False,
        "executes_commands": True,
        "errors": errors,
        "warnings": warnings,
        "steps": [asdict(step) for step in steps],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
