from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_REPOSITORY = "Yami566/workdoe"
DEFAULT_WORKFLOW = "cloudflare-deploy.yml"
DEFAULT_REF = "main"
DEFAULT_CLERK_PROXY_URL = "https://workdoe.com/__clerk"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workdoe_launch_doctor import DEFAULT_LOCAL_URL, build_doctor  # noqa: E402


@dataclass
class GitState:
    branch: str = ""
    clean: bool = False
    head_sha: str = ""
    upstream_sha: str = ""
    synced_with_upstream: bool = False
    blockers: list[str] = field(default_factory=list)


def run_text(command: list[str], cwd: Path = REPO_ROOT) -> tuple[str, str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return "", error or output or "command failed"
    return output, ""


def command_string(command: list[str]) -> str:
    return " ".join(command)


def build_git_state(
    repo_root: Path = REPO_ROOT,
    expected_branch: str = DEFAULT_REF,
) -> GitState:
    blockers: list[str] = []
    branch, branch_error = run_text(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    status, status_error = run_text(["git", "status", "--porcelain"], repo_root)
    head_sha, head_error = run_text(["git", "rev-parse", "HEAD"], repo_root)
    upstream_sha, upstream_error = run_text(["git", "rev-parse", "@{u}"], repo_root)

    for label, error in (
        ("branch", branch_error),
        ("status", status_error),
        ("HEAD", head_error),
    ):
        if error:
            blockers.append(f"Could not read local git {label}: {error}")
    if upstream_error:
        blockers.append(f"Could not read local upstream branch: {upstream_error}")

    clean = not status.strip() and not status_error
    synced_with_upstream = bool(head_sha and upstream_sha and head_sha == upstream_sha)
    if branch and branch != expected_branch:
        blockers.append(f"Local branch must be {expected_branch} before dispatch.")
    if not clean:
        blockers.append("Local worktree must be clean before dispatch.")
    if head_sha and upstream_sha and head_sha != upstream_sha:
        blockers.append("Local HEAD must match the upstream branch before dispatch.")

    return GitState(
        branch=branch,
        clean=clean,
        head_sha=head_sha,
        upstream_sha=upstream_sha,
        synced_with_upstream=synced_with_upstream,
        blockers=blockers,
    )


def dispatch_command(
    *,
    repository: str = DEFAULT_REPOSITORY,
    workflow: str = DEFAULT_WORKFLOW,
    ref: str = DEFAULT_REF,
    clerk_proxy_url: str = DEFAULT_CLERK_PROXY_URL,
) -> list[str]:
    return [
        "gh",
        "workflow",
        "run",
        workflow,
        "--repo",
        repository,
        "--ref",
        ref,
        "-f",
        "deploy=DEPLOY",
    ]


def build_dispatch_plan(
    repo_root: Path = REPO_ROOT,
    *,
    repository: str = DEFAULT_REPOSITORY,
    workflow: str = DEFAULT_WORKFLOW,
    ref: str = DEFAULT_REF,
    clerk_proxy_url: str = DEFAULT_CLERK_PROXY_URL,
    local_url: str = DEFAULT_LOCAL_URL,
) -> dict:
    doctor = build_doctor(repo_root, live=True, local_url=local_url)
    git_state = build_git_state(repo_root, expected_branch=ref)
    blockers: list[str] = []
    if not doctor["ready"]:
        blockers.append(
            "Launch doctor is not ready; resolve blockers before dispatching production deployment."
        )
        blockers.extend(doctor["blockers"])
    blockers.extend(git_state.blockers)

    command = dispatch_command(
        repository=repository,
        workflow=workflow,
        ref=ref,
        clerk_proxy_url=clerk_proxy_url,
    )
    return {
        "service": "workdoe",
        "domain": "workdoe.com",
        "safe_by_default": True,
        "executes_commands": False,
        "ready_to_dispatch": not blockers,
        "repository": repository,
        "workflow": workflow,
        "ref": ref,
        "command": command,
        "command_text": command_string(command),
        "git": asdict(git_state),
        "doctor": doctor,
        "blockers": sorted(set(blockers)),
    }


def run_dispatch(command: list[str], repo_root: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(repo_root),
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )


def completed_output(completed: subprocess.CompletedProcess) -> str:
    return "\n".join(
        value.strip()
        for value in (completed.stdout, completed.stderr)
        if value and value.strip()
    )


def render_text(payload: dict) -> str:
    lines = [
        "Workdoe GitHub deploy dispatch",
        f"Repository: {payload['repository']}",
        f"Workflow: {payload['workflow']}",
        f"Ref: {payload['ref']}",
        f"Ready to dispatch: {payload['ready_to_dispatch']}",
        f"Executes commands: {payload['executes_commands']}",
        f"Command: {payload['command_text']}",
    ]
    if payload.get("dispatch_status"):
        lines.extend(
            [
                f"Dispatch status: {payload['dispatch_status']}",
                f"Dispatch exit code: {payload['dispatch_exit_code']}",
            ]
        )
    if payload.get("dispatch_output"):
        lines.extend(["", "Dispatch Output:", payload["dispatch_output"]])
    if payload["blockers"]:
        lines.extend(["", "Blockers:"])
        lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely dispatch Workdoe's manual GitHub Cloudflare deployment workflow."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--repo", default=DEFAULT_REPOSITORY, help="GitHub owner/repo.")
    parser.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="Workflow file to dispatch.")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Branch or tag to dispatch.")
    parser.add_argument(
        "--clerk-proxy-url",
        default=DEFAULT_CLERK_PROXY_URL,
        help="Confirmed Clerk same-domain proxy URL.",
    )
    parser.add_argument(
        "--local-url",
        default=DEFAULT_LOCAL_URL,
        help="Local prototype URL checked by the launch doctor.",
    )
    parser.add_argument("--execute", action="store_true", help="Dispatch the workflow.")
    parser.add_argument("--yes", action="store_true", help="Confirm intentional dispatch.")
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when dispatch gates are not ready.",
    )
    args = parser.parse_args()

    payload = build_dispatch_plan(
        REPO_ROOT,
        repository=args.repo,
        workflow=args.workflow,
        ref=args.ref,
        clerk_proxy_url=args.clerk_proxy_url,
        local_url=args.local_url,
    )

    if args.execute:
        payload["executes_commands"] = True
        if not args.yes:
            payload["blockers"] = sorted(
                set(payload["blockers"] + ["Dispatch requires --execute and --yes."])
            )
            payload["ready_to_dispatch"] = False
        if not payload["ready_to_dispatch"]:
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                print(render_text(payload))
            return 1
        completed = run_dispatch(payload["command"], REPO_ROOT)
        payload["dispatch_exit_code"] = completed.returncode
        payload["dispatch_status"] = "done" if completed.returncode == 0 else "failed"
        payload["dispatch_output"] = completed_output(completed)
        if completed.returncode != 0:
            payload["blockers"] = sorted(
                set(payload["blockers"] + ["GitHub workflow dispatch command failed."])
            )
            payload["ready_to_dispatch"] = False

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.fail_when_not_ready and not payload["ready_to_dispatch"]:
        return 1
    return int(payload.get("dispatch_exit_code", 0))


if __name__ == "__main__":
    raise SystemExit(main())
