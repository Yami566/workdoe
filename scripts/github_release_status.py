from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPOSITORY = "Yami566/workdoe"
PRODUCTION_ENVIRONMENT = "production"
REQUIRED_DEPLOY_SECRETS = {
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_API_TOKEN",
}


@dataclass
class GithubReleaseStatus:
    repository: str
    environment: str
    live: bool
    ready: bool
    environment_ready: bool
    secrets_ready: bool
    blockers: list[str]
    warnings: list[str]
    expected_deploy_branch: str = "main"
    repository_secret_names: set[str] = field(default_factory=set)
    environment_secret_names: set[str] = field(default_factory=set)


def branch_policy_names(branch_policies: dict | None) -> set[str]:
    return {
        str(item.get("name", "")).strip()
        for item in (branch_policies or {}).get("branch_policies", [])
        if item.get("type") == "branch" and str(item.get("name", "")).strip()
    }


def validate_environment(
    environment: dict | None,
    branch_policies: dict | None,
) -> tuple[bool, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not environment:
        blockers.append("GitHub production environment evidence is missing.")
        return False, blockers, warnings

    if environment.get("name") != PRODUCTION_ENVIRONMENT:
        blockers.append("GitHub production environment must be named production.")

    policy = environment.get("deployment_branch_policy") or {}
    if policy.get("custom_branch_policies") is not True:
        blockers.append("GitHub production environment must use custom branch policies.")
    if policy.get("protected_branches") is not False:
        blockers.append("GitHub production environment must not deploy every protected branch.")

    allowed_branches = branch_policy_names(branch_policies)
    if allowed_branches != {"main"}:
        blockers.append("GitHub production environment must allow only the main branch.")

    if environment.get("can_admins_bypass") is True:
        warnings.append("GitHub production environment currently allows admin bypass.")

    return not blockers, blockers, warnings


def validate_secrets(
    repository_secret_names: set[str],
    environment_secret_names: set[str] | None = None,
) -> tuple[bool, list[str]]:
    available = repository_secret_names | (environment_secret_names or set())
    missing = sorted(REQUIRED_DEPLOY_SECRETS - available)
    blockers = [
        (
            f"GitHub deployment secret {name} is missing from both repository "
            f"and {PRODUCTION_ENVIRONMENT} environment secrets."
        )
        for name in missing
    ]
    return not blockers, blockers


def build_status(
    *,
    repository: str = DEFAULT_REPOSITORY,
    environment: dict | None = None,
    branch_policies: dict | None = None,
    secret_names: set[str] | None = None,
    environment_secret_names: set[str] | None = None,
    live: bool = False,
    extra_blockers: list[str] | None = None,
) -> GithubReleaseStatus:
    environment_ready, environment_blockers, warnings = validate_environment(
        environment,
        branch_policies,
    )
    repository_secret_names = secret_names or set()
    production_secret_names = environment_secret_names or set()
    secrets_ready, secret_blockers = validate_secrets(
        repository_secret_names,
        production_secret_names,
    )
    blockers = environment_blockers + secret_blockers + list(extra_blockers or [])
    return GithubReleaseStatus(
        repository=repository,
        environment=PRODUCTION_ENVIRONMENT,
        live=live,
        ready=not blockers,
        environment_ready=environment_ready,
        secrets_ready=secrets_ready,
        blockers=blockers,
        warnings=warnings,
        repository_secret_names=repository_secret_names,
        environment_secret_names=production_secret_names,
    )


def run_json(command: list[str]) -> tuple[dict | None, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return None, (completed.stderr or completed.stdout or "command failed").strip()
    try:
        return json.loads(completed.stdout), ""
    except json.JSONDecodeError as exc:
        return None, str(exc)


def run_text(command: list[str]) -> tuple[str, str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        return "", (completed.stderr or completed.stdout or "command failed").strip()
    return completed.stdout, ""


def gh_secret_names(output: str) -> set[str]:
    names: set[str] = set()
    for line in output.splitlines():
        stripped = line.strip()
        if stripped:
            names.add(stripped.split()[0])
    return names


def build_live_status(repository: str = DEFAULT_REPOSITORY) -> GithubReleaseStatus:
    blockers: list[str] = []
    environment, env_error = run_json(
        ["gh", "api", f"repos/{repository}/environments/{PRODUCTION_ENVIRONMENT}"]
    )
    if env_error:
        blockers.append(f"Could not read GitHub production environment: {env_error}")
    branch_policies, branch_error = run_json(
        [
            "gh",
            "api",
            f"repos/{repository}/environments/{PRODUCTION_ENVIRONMENT}/deployment-branch-policies",
        ]
    )
    if branch_error:
        blockers.append(f"Could not read GitHub deployment branch policies: {branch_error}")
    secrets_output, secrets_error = run_text(["gh", "secret", "list", "--repo", repository])
    if secrets_error:
        blockers.append(f"Could not read GitHub repository secret names: {secrets_error}")
    environment_secrets_output, environment_secrets_error = run_text(
        [
            "gh",
            "secret",
            "list",
            "--repo",
            repository,
            "--env",
            PRODUCTION_ENVIRONMENT,
        ]
    )
    if environment_secrets_error:
        blockers.append(
            f"Could not read GitHub {PRODUCTION_ENVIRONMENT} environment secret names: {environment_secrets_error}"
        )

    return build_status(
        repository=repository,
        environment=environment,
        branch_policies=branch_policies,
        secret_names=gh_secret_names(secrets_output),
        environment_secret_names=gh_secret_names(environment_secrets_output),
        live=True,
        extra_blockers=blockers,
    )


def render_text(status: GithubReleaseStatus) -> str:
    lines = [
        "Workdoe GitHub release status",
        f"Repository: {status.repository}",
        f"Environment: {status.environment}",
        f"Live check: {status.live}",
        f"Ready: {status.ready}",
        f"Environment ready: {status.environment_ready}",
        f"GitHub deploy secrets ready: {status.secrets_ready}",
        f"Expected deploy branch: {status.expected_deploy_branch}",
    ]
    if status.blockers:
        lines.append("")
        lines.append("Blockers:")
        lines.extend(f"- {blocker}" for blocker in status.blockers)
    if status.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in status.warnings)
    return "\n".join(lines)


def status_payload(status: GithubReleaseStatus) -> dict:
    payload = status.__dict__.copy()
    payload["repository_secret_names"] = sorted(status.repository_secret_names)
    payload["environment_secret_names"] = sorted(status.environment_secret_names)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Workdoe GitHub production deployment environment readiness."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--live", action="store_true", help="Read current GitHub state with gh.")
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="GitHub owner/repo.")
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when the GitHub release setup is not ready.",
    )
    args = parser.parse_args()
    status = build_live_status(args.repo) if args.live else build_status(repository=args.repo)
    payload = status_payload(status)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(status))
    if args.fail_when_not_ready and not status.ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
