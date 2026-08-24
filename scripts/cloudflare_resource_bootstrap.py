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
D1_CAPTURE_PATH = REPO_ROOT / "workdoe-d1.local.txt"
D1_PREVIEW_CAPTURE_PATH = REPO_ROOT / "workdoe-preview-d1.local.txt"
SECRET_LIST_PATH = REPO_ROOT / "cloudflare-secret-list.local.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_cloudflare_d1_ids import apply_d1_ids
from cloudflare_wrangler import (
    cloudflare_api_token_error,
    cloudflare_api_token_present,
    wrangler_command,
    wrangler_env,
)
from prepare_cloudflare_release import ZERO_UUID, existing_d1_ids

IDEMPOTENT_RESOURCE_STEPS = {
    "create-r2-media-bucket",
    "create-email-queue",
    "create-media-review-queue",
}
EXISTS_ERROR_MARKERS = (
    "already exists",
    "already exist",
    "exists already",
    "name already in use",
)


@dataclass
class BootstrapStep:
    name: str
    command: list[str]
    cwd: str
    writes: str = ""
    status: str = "pending"
    required: bool = True


def wrangler_json_path(repo_root: Path = REPO_ROOT) -> Path:
    return repo_root / "cloudflare" / "wrangler.jsonc"


def d1_ready(repo_root: Path = REPO_ROOT) -> bool:
    ids = existing_d1_ids(wrangler_json_path(repo_root))
    return bool(ids.get("database_id") and ids.get("preview_database_id"))


def build_bootstrap_steps(
    repo_root: Path = REPO_ROOT,
    include_secret_probe: bool = True,
) -> list[BootstrapStep]:
    cloudflare_dir = repo_root / "cloudflare"
    d1_capture = repo_root / "workdoe-d1.local.txt"
    preview_capture = repo_root / "workdoe-preview-d1.local.txt"
    secret_list = repo_root / "cloudflare-secret-list.local.json"
    steps: list[BootstrapStep] = []

    if not d1_ready(repo_root):
        steps.extend(
            [
                BootstrapStep(
                    name="create-d1-production",
                    command=wrangler_command(["d1", "create", "workdoe"], repo_root),
                    cwd=str(cloudflare_dir),
                    writes=str(d1_capture),
                ),
                BootstrapStep(
                    name="create-d1-preview",
                    command=wrangler_command(["d1", "create", "workdoe-preview"], repo_root),
                    cwd=str(cloudflare_dir),
                    writes=str(preview_capture),
                ),
                BootstrapStep(
                    name="apply-d1-ids",
                    command=[
                        sys.executable,
                        str(repo_root / "scripts" / "apply_cloudflare_d1_ids.py"),
                        "--from-file",
                        str(d1_capture),
                        "--preview-from-file",
                        str(preview_capture),
                    ],
                    cwd=str(repo_root),
                ),
            ]
        )

    steps.extend(
        [
            BootstrapStep(
                name="create-r2-media-bucket",
                command=wrangler_command(["r2", "bucket", "create", "workdoe-media"], repo_root),
                cwd=str(cloudflare_dir),
            ),
            BootstrapStep(
                name="create-email-queue",
                command=wrangler_command(["queues", "create", "workdoe-email"], repo_root),
                cwd=str(cloudflare_dir),
            ),
            BootstrapStep(
                name="create-media-review-queue",
                command=wrangler_command(["queues", "create", "workdoe-media-review"], repo_root),
                cwd=str(cloudflare_dir),
            ),
        ]
    )
    if include_secret_probe:
        steps.append(
            BootstrapStep(
                name="capture-secret-list",
                command=[
                    sys.executable,
                    str(repo_root / "scripts" / "cloudflare_secret_evidence.py"),
                    "--execute",
                    "--yes",
                    "--output",
                    str(secret_list),
                ],
                cwd=str(repo_root),
                writes=str(secret_list),
                required=False,
            )
        )
    return steps


def command_string(command: list[str]) -> str:
    return " ".join(command)


def run_external(step: BootstrapStep) -> subprocess.CompletedProcess:
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


def completed_output(completed: subprocess.CompletedProcess) -> str:
    return "\n".join(
        value for value in (completed.stdout, completed.stderr) if value
    )


def capture_output_for_step(step: BootstrapStep, completed: subprocess.CompletedProcess) -> str:
    if step.name == "capture-secret-list":
        return ""
    return completed_output(completed)


def is_existing_resource_failure(
    step: BootstrapStep, completed: subprocess.CompletedProcess
) -> bool:
    if step.name not in IDEMPOTENT_RESOURCE_STEPS:
        return False
    output = completed_output(completed).lower()
    return any(marker in output for marker in EXISTS_ERROR_MARKERS)


def execute_steps(
    steps: list[BootstrapStep],
    continue_on_failure: bool = False,
) -> tuple[list[BootstrapStep], list[str]]:
    errors: list[str] = []
    for step in steps:
        if step.name == "apply-d1-ids":
            try:
                apply_d1_ids(
                    wrangler_path=Path(step.cwd) / "cloudflare" / "wrangler.jsonc",
                    from_file=D1_CAPTURE_PATH,
                    preview_from_file=D1_PREVIEW_CAPTURE_PATH,
                )
            except Exception as exc:  # noqa: BLE001 - CLI integrations raise heterogeneous errors.
                step.status = "failed"
                errors.append(f"{step.name}: {exc}")
                if not continue_on_failure:
                    break
            else:
                step.status = "done"
            continue

        try:
            completed = run_external(step)
        except OSError as exc:  # pragma: no cover - depends on operator machine PATH
            step.status = "failed"
            errors.append(f"{step.name}: {exc}")
            if step.required and not continue_on_failure:
                break
            continue
        if completed.returncode == 0:
            output = capture_output_for_step(step, completed)
            if step.writes and output:
                Path(step.writes).write_text(output, encoding="utf-8")
            step.status = "done"
            continue
        if is_existing_resource_failure(step, completed):
            step.status = "done-existing"
            continue
        stderr = (completed.stderr or completed.stdout or "").strip()
        step.status = "failed"
        errors.append(f"{step.name}: {stderr or 'command failed'}")
        if step.required and not continue_on_failure:
            break
    return steps, errors


def plan_payload(
    repo_root: Path = REPO_ROOT,
    include_secret_probe: bool = True,
    dry_run: bool = True,
) -> dict:
    ids = existing_d1_ids(wrangler_json_path(repo_root))
    steps = build_bootstrap_steps(repo_root, include_secret_probe=include_secret_probe)
    return {
        "ok": True,
        "dry_run": dry_run,
        "executes_commands": not dry_run,
        "service": "workdoe",
        "domain": "workdoe.com",
        "d1_ids_configured": bool(ids.get("database_id") and ids.get("preview_database_id")),
        "d1_database_id": ids.get("database_id", ZERO_UUID),
        "d1_preview_database_id": ids.get("preview_database_id", ZERO_UUID),
        "steps": [asdict(step) for step in steps],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap Workdoe Cloudflare resources with a dry-run default."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run Wrangler commands instead of printing the plan.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required with --execute to confirm this may create Cloudflare resources.",
    )
    parser.add_argument(
        "--no-secret-probe",
        action="store_true",
        help="Skip sanitized Cloudflare secret-name evidence capture.",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue after non-zero Wrangler commands.",
    )
    args = parser.parse_args()
    include_secret_probe = not args.no_secret_probe

    if not args.execute:
        payload = plan_payload(include_secret_probe=include_secret_probe, dry_run=True)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Workdoe Cloudflare resource bootstrap plan")
            print("Dry run: no commands were executed.")
            for step in payload["steps"]:
                suffix = f" > {step['writes']}" if step["writes"] else ""
                print(f"- {step['name']}: {command_string(step['command'])}{suffix}")
        return 0

    if not args.yes:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "--execute requires --yes so Cloudflare resource creation is explicit.",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    if not cloudflare_api_token_present():
        payload = {
            "ok": False,
            "dry_run": False,
            "executes_commands": False,
            "errors": [
                cloudflare_api_token_error(
                    "create Workdoe Cloudflare D1, R2, and Queue resources"
                )
            ],
            "steps": [
                asdict(step)
                for step in build_bootstrap_steps(include_secret_probe=include_secret_probe)
            ],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    steps = build_bootstrap_steps(include_secret_probe=include_secret_probe)
    executed_steps, errors = execute_steps(steps, continue_on_failure=args.continue_on_failure)
    payload = {
        "ok": not errors,
        "dry_run": False,
        "executes_commands": True,
        "errors": errors,
        "steps": [asdict(step) for step in executed_steps],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
