from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CLOUDFLARE_DIR = REPO_ROOT / "cloudflare"
DEFAULT_SECRET_LIST_PATH = REPO_ROOT / "cloudflare-secret-list.local.json"
DEFAULT_CLERK_PROXY_PROOF_PATH = REPO_ROOT / "clerk-proxy-proof.local.json"
DEFAULT_STAGED_API_TOKEN_PATH = REPO_ROOT / "cloudflare" / ".deploy-token"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_hosted_ingress import (
    reviewed_ingress_account,
    verify_hosted_worker_ingress,
    wrangler_oauth_access_token,
)
from cloudflare_readiness import (
    clerk_release_proof_digest,
    clerk_release_proof_error,
    run_readiness,
)
from cloudflare_worker_recovery import (
    activated_worker_deployment,
    latest_deployable_worker_version,
    reviewed_d1_database_id,
    single_active_worker_deployment,
    single_active_worker_version,
    uploaded_worker_version,
    valid_worker_version,
    verify_uploaded_worker_configuration,
    verify_worker_commit_tag,
    verify_worker_d1_binding,
    verify_worker_media_binding,
    verify_worker_normal_write_mode,
    worker_version_metadata,
    worker_version_number,
)
from cloudflare_wrangler import (
    WRANGLER_ENV_VAR,
    ambient_wrangler_env,
    cloudflare_api_token_error,
    cloudflare_api_token_from_file,
    cloudflare_api_token_present,
    local_wrangler_candidates,
    resolved_wrangler_bin,
    wrangler_command,
    wrangler_env,
)
from prepare_cloudflare_release import PRODUCTION_MAP_MODE, PRODUCTION_MEDIA_BUCKET
from verify_dependency_provenance import verify as verify_dependency_provenance
from workdoe_production_smoke import (
    DEFAULT_BASE_URL,
    DEFAULT_DOMAIN,
    DEFAULT_TIMEOUT,
    ISOLATED_BETA_COMMITS,
    ISOLATED_CLERK_BETA_COMMIT,
    ISOLATED_CLERK_BETA_MAP_MODE,
    ISOLATED_EDIT_BETA_COMMIT,
    clerk_browser_entry_check,
    clerk_environment_check,
    clerk_proxy_check,
    read_clerk_archive_pins,
)

SMOKE_JSON_MAX = 128 * 1024
RELEASE_SMOKE_SCOPE = (
    f"public_http_smoke_with_public_map_mode_{PRODUCTION_MAP_MODE}_with_clerk_package_boundary"
    "_with_clerk_developer_file_boundary_with_clerk_build_notice_delivery"
    "_with_clerk_public_auth_settings_with_redirect_privacy_with_commit_asset_parity_and_commit_bound_notices"
    "_with_clerk_browser_file_delivery"
)
ISOLATED_BETA_SMOKE_SCOPE = RELEASE_SMOKE_SCOPE.replace(
    f"_map_mode_{PRODUCTION_MAP_MODE}_", f"_map_mode_{ISOLATED_CLERK_BETA_MAP_MODE}_", 1,
)
ISOLATED_BETA_PARENT = "5900abc2272c6ab3dbced58dac01d3b1d4c60e01"  # pragma: allowlist secret - reviewed Git commit ID.
ISOLATED_BETA_PRIOR_VERSION = "8dcc09c5-5e38-4d39-9466-024cf1062473"
ISOLATED_BETA_PRIOR_DEPLOYMENT = "e5aac2e5-3e77-4254-916b-86cd7e173004"
ISOLATED_BETA_PRIOR_NUMBER = 61
ISOLATED_BETA_BASELINES = {
    ISOLATED_CLERK_BETA_COMMIT: (
        ISOLATED_BETA_PARENT, ISOLATED_BETA_PRIOR_VERSION,
        ISOLATED_BETA_PRIOR_DEPLOYMENT, ISOLATED_BETA_PRIOR_NUMBER,
    ),
    ISOLATED_EDIT_BETA_COMMIT: (
        ISOLATED_CLERK_BETA_COMMIT, "1caee132-9ee4-4dca-a666-30f8535213d2",
        "b14c5f7b-163d-4023-a43e-c4ec0a92d24e", 62,
    ),
}
ISOLATED_BETA_READINESS_INPUTS = (
    "scripts/cloudflare_readiness.py", "scripts/cloudflare_preflight.py", "scripts/prepare_cloudflare_release.py",
)
RELEASE_SMOKE_REQUIRED = (
    "dns", "http-to-https", "https-entry", "health-json", "public-jobs-api", "public-project-search",
    "public-map-snapshots", "anonymous-private-routes", "public-sample-presentation",
    "entry-security-headers", "static-asset-cache", "browser-license-notices", "public-trust-pages",
    "social-share-card", "public-security-contact", "clerk-production-key", "clerk-invitation-entry",
    "clerk-same-domain-proxy", "clerk-unpinned-package", "clerk-developer-file-boundary",
    "clerk-build-notice-delivery", "clerk-browser-entry", "clerk-public-auth-settings",
    "redirect-privacy", "commit-asset-parity", "clerk-browser-file-delivery",
)
RELEASE_SMOKE_OPTIONAL = ("public-discovery-files",)
RELEASE_INPUT_DIRS = ("cloudflare/worker", "cloudflare/d1/migrations", "workdoe/static")
RELEASE_INPUT_PATHS = (
    *RELEASE_INPUT_DIRS, "cloudflare/wrangler.jsonc", "package.json", "package-lock.json",
    "DEPENDENCY_PROVENANCE.json", "licenses", ".github/python", "requirements.txt", "requirements-audit.txt",
)
FULL_COMMIT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
D1_LEDGER_STEP = "verify-d1-migration-ledger"
D1_BETA_FINAL_STEP = "recheck-d1-schema-before-activation"
D1_PREFIX_LEDGER_STEP = "verify-d1-migration-prefix"
D1_RECOVERY_STEP = "capture-d1-recovery-point"
D1_RECOVERY_REQUIRED = "Supply a new private .json path in an existing directory with --d1-recovery-output before applying migrations."
D1_RECOVERY_CHANGED = "The saved D1 recovery receipt is missing or changed; migrations were not attempted."
D1_AFTER_APPLY_NOTICE = "D1 may already have changed. Keep the recovery receipt and review the ledger; no rollback was attempted."
D1_LEDGER_STEPS = {D1_LEDGER_STEP, D1_PREFIX_LEDGER_STEP, D1_BETA_FINAL_STEP}
D1_LEDGER_RESPONSE_MAX = 256 * 1024
D1_STATE_SQL = (
    "SELECT 'ledger' AS kind, id AS position, NULL AS type, name, "
    "NULL AS tbl_name, NULL AS sql FROM d1_migrations UNION ALL "
    "SELECT 'schema', NULL, type, name, tbl_name, sql FROM sqlite_schema "
    "WHERE sql IS NOT NULL AND name != 'd1_migrations' "
    "AND name NOT GLOB 'sqlite_*' AND name NOT GLOB '_cf_*' "
    "ORDER BY kind, position, type, name"
)
D1_BOOKMARK = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+")
WORKER_BASELINE_STEP = "verify-worker-rollback-point"
WORKER_D1_BINDING_STEP = "verify-active-worker-d1-binding"
WORKER_INHERITANCE_STEP = "verify-worker-secret-inheritance-baseline"
WORKER_UPLOAD_STEP = "upload-and-verify-worker-version"
WORKER_VERSION_STEP = "verify-uploaded-worker-metadata"
WORKER_ACTIVATE_STEP = "activate-verified-worker-version"
WORKER_BASELINE_REQUIRED = "Supply the captured active Worker UUID with --expected-worker-version."
HOSTED_INGRESS_REQUIRED = "A fresh hosted ingress, query-redaction, R2 privacy, and queue routing check is required before production writes."
DEPLOY_RECEIPT_MAX = 65_536


@dataclass
class DeployStep:
    name: str
    command: list[str]
    cwd: str
    status: str = "pending"
    required: bool = True
    output_excerpt: str = ""


def d1_ledger_step(repo_root: Path, name: str) -> DeployStep:
    return DeployStep(
        name=name,
        command=wrangler_command([
            "d1", "execute", "workdoe", "--remote", "--config", "wrangler.jsonc", "--json",
            "--command", D1_STATE_SQL,
        ], repo_root),
        cwd=str(repo_root / "cloudflare"),
    )


def build_deploy_steps(
    repo_root: Path = REPO_ROOT,
    include_smoke: bool = True,
    *,
    migrations: str = "skip",
    expected_commit: str | None = None,
    isolated_clerk_beta: bool = False,
) -> list[DeployStep]:
    if isolated_clerk_beta and (migrations != "skip" or expected_commit not in ISOLATED_BETA_COMMITS or not include_smoke):
        raise ValueError("The isolated beta requires its exact commit, no migrations, and mandatory smoke.")
    cloudflare_dir = repo_root / "cloudflare"
    steps = [d1_ledger_step(repo_root, D1_PREFIX_LEDGER_STEP if migrations == "apply" else D1_LEDGER_STEP)]
    deploy_args = ["versions", "upload", "--config", "wrangler.jsonc", "--strict"]
    has_reviewed_commit = bool(FULL_COMMIT_ID.fullmatch(expected_commit or ""))
    if has_reviewed_commit:
        deploy_args.extend(["--tag", expected_commit])
    steps.append(DeployStep(
        name=WORKER_UPLOAD_STEP,
        command=wrangler_command(deploy_args, repo_root),
        cwd=str(cloudflare_dir),
    ))
    if migrations == "apply":
        steps.append(DeployStep(
            name=D1_RECOVERY_STEP,
            command=wrangler_command(["d1", "time-travel", "info", "workdoe", "--json", "--config", "wrangler.jsonc"], repo_root),
            cwd=str(cloudflare_dir),
        ))
        steps.append(DeployStep(
            name="apply-d1-migrations",
            command=wrangler_command(["d1", "migrations", "apply", "workdoe", "--remote", "--config", "wrangler.jsonc"], repo_root),
            cwd=str(cloudflare_dir),
        ))
        steps.append(d1_ledger_step(repo_root, D1_LEDGER_STEP))
    if isolated_clerk_beta:
        steps.append(d1_ledger_step(repo_root, D1_BETA_FINAL_STEP))
    steps.append(DeployStep(
        name=WORKER_ACTIVATE_STEP,
        command=[],  # The verified version UUID is available only after upload.
        cwd=str(cloudflare_dir),
    ))
    if include_smoke:
        smoke_command = [
            sys.executable,
            *(["-I", "-B"] if isolated_clerk_beta else []),
            str((SCRIPT_DIR if isolated_clerk_beta else repo_root / "scripts") / "workdoe_production_smoke.py"),
            "--json",
            "--fail-when-not-ready",
            "--release-checkout",
            str(repo_root),
            *(["--isolated-clerk-beta"] if isolated_clerk_beta else ["--expect-public-map-mode", PRODUCTION_MAP_MODE]),
            "--verify-clerk-browser-delivery",
            "--attempts",
            "6",
            "--retry-delay",
            "5",
        ]
        if has_reviewed_commit:
            smoke_command.extend(["--asset-commit", expected_commit])
        steps.append(
            DeployStep(
                name="smoke-production",
                command=smoke_command,
                cwd=str(repo_root),
                required=True,
            )
        )
    return steps


def git_read(repo_root: Path, args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "--no-replace-objects", "--no-lazy-fetch", "-c", "core.fsmonitor=false", *args],
        cwd=repo_root, check=True, input=input_text, timeout=15,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout


def release_input_bytes_match(repo_root: Path, commit: str, *, paths_to_check: tuple[str, ...] = RELEASE_INPUT_PATHS) -> bool:
    root = repo_root.resolve()
    tree = git_read(root, ["ls-tree", "-rz", "--full-tree", commit, "--", *paths_to_check])
    paths, object_ids = [], []
    for record in filter(None, tree.split("\0")):
        metadata, name = record.split("\t", 1)
        mode, kind, object_id = metadata.split()
        path = root / name
        if (
            kind != "blob" or mode not in {"100644", "100755"} or not FULL_COMMIT_ID.fullmatch(object_id)
            or not name or "\n" in name or "\r" in name or not path.is_relative_to(root)
            or path.is_symlink() or path.resolve(strict=True) != path or not path.is_file()
        ):
            return False
        paths.append(name)
        object_ids.append(object_id)
    if not paths:
        return False
    raw_hashes = git_read(root, ["hash-object", "--no-filters", "--stdin-paths"], input_text="\n".join(paths) + "\n")
    return raw_hashes.splitlines() == object_ids


def release_source_blockers(repo_root: Path, expected_commit: str | None) -> list[str]:
    if not FULL_COMMIT_ID.fullmatch(expected_commit or ""):
        return ["Supply the full reviewed Git commit with --expected-commit."]
    try:
        root, head = git_read(repo_root, ["rev-parse", "--show-toplevel", "HEAD"]).splitlines()
        if Path(root).resolve() != repo_root.resolve() or head != expected_commit:
            return ["The release checkout does not match the reviewed Git commit."]
        tracked = git_read(repo_root, ["ls-files", "-v", "-z"])
        if any(record[0] == "S" or record[0].islower() for record in tracked.split("\0") if record):
            return ["Use a full checkout without assume-unchanged or skip-worktree index flags."]
        if git_read(repo_root, ["status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"]):
            return ["Use a clean checkout of the reviewed commit; tracked or untracked changes are present."]
        ignored = git_read(repo_root, ["ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", *RELEASE_INPUT_PATHS])
        for name in filter(None, ignored.split("\0")):
            if not (name.startswith("cloudflare/worker/") and "/__pycache__/" in name and name.endswith(".pyc")):
                return ["Remove ignored files from the reviewed release inputs before deployment."]
        if not release_input_bytes_match(repo_root, expected_commit):
            return ["Release input bytes do not match the reviewed Git commit. Use an unfiltered checkout."]
    except (OSError, ValueError, subprocess.SubprocessError):
        return ["Could not verify the reviewed Git checkout."]
    return []


def isolated_beta_source_blockers(repo_root: Path, commit: str = ISOLATED_CLERK_BETA_COMMIT) -> list[str]:
    if commit not in ISOLATED_BETA_BASELINES:
        return ["The isolated beta requires an exact reviewed commit."]
    blockers = release_source_blockers(repo_root, commit)
    if blockers:
        return blockers
    try:
        parent = git_read(repo_root, ["rev-list", "--parents", "-n", "1", commit]).split()
        if parent != [commit, ISOLATED_BETA_BASELINES[commit][0]]:
            return ["The isolated beta does not have the exact reviewed serving parent."]
        if not release_input_bytes_match(repo_root, commit, paths_to_check=ISOLATED_BETA_READINESS_INPUTS):
            return ["The isolated beta readiness scripts do not match their committed bytes."]
        for directory in (repo_root, repo_root / "cloudflare"):
            if any(
                name.name != ".dev.vars.example"
                for pattern in (".env*", ".dev.vars*") for name in directory.glob(pattern)
            ):
                return ["Use an isolated beta checkout without local dotenv or dev-vars overrides."]
        if os.environ.get(WRANGLER_ENV_VAR) or Path(resolved_wrangler_bin(repo_root)) not in local_wrangler_candidates(repo_root):
            return ["The isolated beta requires the checkout's installed, lock-pinned Wrangler without a binary override."]
        lock = (repo_root / "package-lock.json").read_bytes()
        if lock != (REPO_ROOT / "package-lock.json").read_bytes():
            return ["The isolated beta tooling lock does not match the release verifier's reviewed lock."]
        installed = json.loads((repo_root / "node_modules/wrangler/package.json").read_text(encoding="utf-8"))
        if installed.get("version") != json.loads(lock)["packages"]["node_modules/wrangler"]["version"]:
            return ["The isolated beta Wrangler installation does not match its lock."]
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        return ["Could not verify isolated beta source and tooling inputs."]
    return []


def d1_recovery_target(repo_root: Path, output: Path | None) -> Path:
    if output is None:
        raise ValueError(D1_RECOVERY_REQUIRED)
    try:
        root = repo_root.resolve(strict=True)
        requested = Path(os.path.abspath(output))
        target = requested.parent.resolve(strict=True) / requested.name
        if (
            requested.suffix.lower() != ".json" or not target.parent.is_dir()
            or target.exists() or target.is_symlink()
        ):
            raise ValueError(D1_RECOVERY_REQUIRED)
    except (OSError, RuntimeError) as exc:
        raise ValueError(D1_RECOVERY_REQUIRED) from exc
    for path in {requested, target}:
        if not path.is_relative_to(root):
            continue
        if any(path.is_relative_to(root / name) for name in (*RELEASE_INPUT_PATHS, ".git")):
            raise ValueError("Keep the D1 recovery receipt outside Git metadata and release inputs.")
        try:
            git_read(root, ["check-ignore", "--quiet", "--", path.relative_to(root).as_posix()])
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("Use an out-of-checkout or Git-ignored path for the private D1 recovery receipt.") from exc
    return target


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


def isolated_beta_readiness_payload(
    repo_root: Path, secret_list_json: Path | None, clerk_proxy_proof_json: Path | None,
) -> dict:
    # Run only the old read-only preflight in its own import context, never its deploy driver.
    if error := clerk_release_proof_error(clerk_proxy_proof_json):
        return {"ready": False, "warnings": [], "blockers": [error]}
    failed = {"ready": False, "warnings": [], "blockers": ["Could not verify isolated beta strict readiness."]}
    args = [str(repo_root / ISOLATED_BETA_READINESS_INPUTS[0]), "--strict-production"]
    for flag, path in (("--secret-list-json", secret_list_json), ("--clerk-proxy-proof-json", clerk_proxy_proof_json)):
        if path is not None:
            args.extend([flag, str(path.resolve())])
    try:
        with tempfile.TemporaryDirectory(prefix="workdoe-beta-readiness-") as cache:
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-X", f"pycache_prefix={cache}", *args], cwd=repo_root,
                capture_output=True, check=False, timeout=30, encoding="utf-8",
            )
        if completed.returncode not in (0, 1) or len(completed.stdout) > SMOKE_JSON_MAX:
            return failed
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict) or any(
            not isinstance(payload.get(key), list) or any(not isinstance(value, str) for value in payload[key])
            for key in ("warnings", "blockers")
        ) or payload.get("ready") is not (not payload["blockers"]) or completed.returncode != int(not payload["ready"]):
            return failed
        return payload
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError):
        return failed


def plan_payload(
    repo_root: Path = REPO_ROOT,
    secret_list_json: Path | None = DEFAULT_SECRET_LIST_PATH,
    env_file: Path | None = None,
    clerk_proxy_proof_json: Path | None = DEFAULT_CLERK_PROXY_PROOF_PATH,
    include_smoke: bool = True,
    dry_run: bool = True,
    *,
    expected_commit: str | None = None,
    migrations: str | None = None,
    expected_worker_version: str | None = None,
    d1_recovery_output: Path | None = None,
    isolated_clerk_beta: bool = False,
) -> dict:
    if isolated_clerk_beta:
        source_blockers = isolated_beta_source_blockers(repo_root, expected_commit)
        readiness = (
            {"ready": False, "warnings": [], "blockers": []} if source_blockers
            else isolated_beta_readiness_payload(repo_root, secret_list_json, clerk_proxy_proof_json)
        )
    else:
        readiness = readiness_payload(
            repo_root, secret_list_json=secret_list_json, env_file=env_file, clerk_proxy_proof_json=clerk_proxy_proof_json,
        )
        source_blockers = release_source_blockers(repo_root, expected_commit)
    if isolated_clerk_beta and expected_worker_version != ISOLATED_BETA_BASELINES.get(expected_commit, (None, None))[1]:
        source_blockers.append("The isolated beta requires its exact reviewed serving Worker version.")
    elif not valid_worker_version(expected_worker_version):
        source_blockers.append(WORKER_BASELINE_REQUIRED)
    if migrations is None:
        source_blockers.append("Choose --migrations apply or --migrations skip before execution.")
    if migrations == "apply":
        try:
            d1_recovery_target(repo_root, d1_recovery_output)
        except ValueError as exc:
            source_blockers.append(str(exc))
    return {
        "ok": True,
        "dry_run": dry_run,
        "executes_commands": not dry_run,
        "service": "workdoe",
        "domain": "workdoe.com",
        "ready_to_deploy": bool(readiness["ready"]) and not source_blockers,
        "readiness_scope": "local_source_and_sanitized_proofs_only",
        "hosted_checks_completed": False,
        "deployment_authorization": "not_granted_by_plan",
        "public_launch_authorization": "not_granted_by_plan",
        "strict_blockers": readiness["blockers"] + source_blockers,
        "strict_warnings": readiness["warnings"],
        "release_commit": expected_commit if FULL_COMMIT_ID.fullmatch(expected_commit or "") else None,
        **({"isolated_clerk_beta": True, "checks_d1_schema_again_after_upload": True} if isolated_clerk_beta else {}),
        "checks_raw_release_input_bytes": True,
        "expected_worker_version": expected_worker_version if valid_worker_version(expected_worker_version) else None,
        "checks_uploaded_worker_identity": True,
        "checks_worker_secret_inheritance_baseline": True,
        "checks_uploaded_worker_binding_and_runtime_configuration": True,
        "verifies_upload_before_d1_migration": not isolated_clerk_beta,
        "activates_only_verified_upload": True,
        "syncs_worker_triggers_or_script_settings": False,
        "checks_active_and_uploaded_worker_d1_binding": True,
        "checks_active_worker_write_mode": True,
        "checks_live_clerk_entry_bytes_before_writes": True,
        "checks_fresh_unchanged_clerk_dashboard_proof": True,
        "checks_live_clerk_settings_before_activation": True,
        "checks_live_browser_advisories_before_writes": True,
        "checks_live_tooling_advisories_before_writes": True,
        "checks_hosted_ingress_before_writes": True,
        "checks_hosted_query_redaction_before_writes": True,
        "checks_hosted_ingress_and_query_redaction_after_activation": True,
        "checks_active_and_uploaded_worker_media_binding": True,
        "checks_hosted_r2_privacy_before_writes_and_after_activation": True,
        "checks_hosted_queue_routing_before_writes_and_after_activation": True,
        "checks_d1_application_schema": True,
        "expected_public_map_mode": ISOLATED_CLERK_BETA_MAP_MODE if isolated_clerk_beta else PRODUCTION_MAP_MODE,
        "checks_d1_recovery_receipt_before_migrations": not isolated_clerk_beta,
        "migrations": migrations or "not-selected",
        "steps": [asdict(step) for step in build_deploy_steps(
            repo_root, include_smoke, migrations=migrations or "skip", expected_commit=expected_commit,
            **({"isolated_clerk_beta": True} if isolated_clerk_beta else {}),
        )],
    }


def run_external(
    step: DeployStep,
    deploy_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        step.command,
        cwd=step.cwd,
        env=deploy_env or wrangler_env(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30 if step.name in D1_LEDGER_STEPS | {
            D1_RECOVERY_STEP, WORKER_BASELINE_STEP, WORKER_D1_BINDING_STEP, WORKER_VERSION_STEP,
            WORKER_INHERITANCE_STEP,
            WORKER_ACTIVATE_STEP,
        } else None,
    )


def worker_metadata_response(step: DeployStep, deploy_env: dict[str, str], failure: str) -> str:
    try:
        response = run_external(step, deploy_env=deploy_env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(failure) from exc
    if response.returncode:
        raise ValueError(failure)
    return response.stdout


def active_worker_status(repo_root: Path, deploy_env: dict[str, str]) -> str:
    step = DeployStep(
        name=WORKER_BASELINE_STEP,
        command=wrangler_command(["deployments", "status", "--json", "--config", "wrangler.jsonc"], repo_root),
        cwd=str(repo_root / "cloudflare"),
    )
    return worker_metadata_response(step, deploy_env, "Could not read current production Worker deployment status.")


def active_worker_version(repo_root: Path, deploy_env: dict[str, str]) -> str:
    return single_active_worker_version(active_worker_status(repo_root, deploy_env))


def active_worker_deployment(repo_root: Path, deploy_env: dict[str, str]) -> tuple[str, str]:
    return single_active_worker_deployment(active_worker_status(repo_root, deploy_env))


def worker_baseline_blockers(repo_root: Path, expected_version: str, deploy_env: dict[str, str]) -> list[str]:
    try:
        active = active_worker_version(repo_root, deploy_env)
    except ValueError as exc:
        return [str(exc)]
    if active != expected_version:
        return ["Active Worker version no longer matches the captured rollback point. Review and recapture before deploying."]
    return []


def read_worker_version_metadata(
    repo_root: Path, version: str, deploy_env: dict[str, str], *, step_name: str,
) -> str:
    step = DeployStep(
        name=step_name,
        command=wrangler_command(["versions", "view", version, "--json", "--config", "wrangler.jsonc"], repo_root),
        cwd=str(repo_root / "cloudflare"),
    )
    return worker_metadata_response(step, deploy_env, "Could not read the reviewed Worker version metadata.")


def release_input_check(
    repo_root: Path, commit: str, version: str, database_id: str, deploy_env: dict[str, str],
) -> Callable[[], list[str]]:
    remote_preconditions_verified = False
    baseline = ISOLATED_BETA_BASELINES.get(commit)
    isolated = baseline is not None

    def check() -> list[str]:
        nonlocal remote_preconditions_verified
        if isolated:
            blockers = isolated_beta_source_blockers(repo_root, commit)
            if not blockers:
                try:
                    if (version != baseline[1]
                        or active_worker_deployment(repo_root, deploy_env) != baseline[1:3]):
                        blockers = ["The isolated beta's exact serving deployment changed. Stop and review a new baseline."]
                except ValueError as exc:
                    blockers = [str(exc)]
        else:
            blockers = release_source_blockers(repo_root, commit) or worker_baseline_blockers(repo_root, version, deploy_env)
        if blockers or remote_preconditions_verified:
            return blockers
        try:
            raw = read_worker_version_metadata(repo_root, version, deploy_env, step_name=WORKER_D1_BINDING_STEP)
            metadata = worker_version_metadata(raw, version)
            verify_worker_d1_binding(metadata, database_id)
            verify_worker_normal_write_mode(metadata)
            verify_worker_media_binding(metadata, PRODUCTION_MEDIA_BUCKET)
            if isolated:
                verify_worker_commit_tag(raw, version, baseline[0])
                if worker_version_number(metadata) != baseline[3]:
                    raise ValueError("The isolated beta's reviewed serving Worker version number changed.")
                verify_uploaded_worker_configuration(metadata, repo_root / "cloudflare")
        except ValueError as exc:
            return [str(exc)]
        # The serving baseline can predate SRI; its bytes must still match the reviewed pins.
        for label, probe, options in (
            ("browser entry", clerk_browser_entry_check, {"require_integrity": commit == ISOLATED_EDIT_BETA_COMMIT}),
            ("configuration", clerk_environment_check, {}),
            ("integrity", clerk_proxy_check, {}),
        ):
            result = probe(DEFAULT_BASE_URL, DEFAULT_TIMEOUT, **options)
            if result.status != "ready":
                return [f"Pre-deployment Clerk {label} check failed: {result.summary} No release writes were attempted."]
        remote_preconditions_verified = True
        return []

    return check


def clerk_proof_guard(path: Path | None, reviewed_digest: str) -> list[str]:
    try:
        if clerk_release_proof_digest(path) != reviewed_digest:
            return ["Clerk dashboard proof changed after release review. Stop and review the new evidence."]
    except ValueError as exc:
        return [str(exc)]
    return []


def check_clerk_before_activation() -> None:
    result = clerk_environment_check(DEFAULT_BASE_URL, DEFAULT_TIMEOUT)
    if result.status != "ready":
        raise ValueError(f"Pre-activation Clerk settings check failed: {result.summary} No traffic switch was attempted.")


def read_worker_receipt(path: Path, operation: str) -> str:
    try:
        with path.open(encoding="utf-8") as receipt_file:
            receipt = receipt_file.read(DEPLOY_RECEIPT_MAX + 1)
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read the Wrangler {operation} receipt.") from exc
    if len(receipt) > DEPLOY_RECEIPT_MAX:
        raise ValueError(f"Wrangler {operation} receipt exceeds the size limit.")
    return receipt


def upload_and_verify_worker(
    step: DeployStep, deploy_env: dict[str, str], expected_commit: str, previous_version: str | None,
    *, expected_database_id: str | None = None,
) -> str:
    repo_root = Path(step.cwd).parent
    version_list_step = DeployStep(
        name=WORKER_INHERITANCE_STEP,
        command=wrangler_command(["versions", "list", "--json", "--config", "wrangler.jsonc"], repo_root),
        cwd=step.cwd,
    )
    latest, previous_number = latest_deployable_worker_version(worker_metadata_response(
        version_list_step, deploy_env, "Could not read the Workdoe version list before upload.",
    ))
    if latest != previous_version:
        raise ValueError("The latest deployable Worker is not the reviewed serving version. Stop before upload and review secret inheritance.")
    with tempfile.TemporaryDirectory(prefix="workdoe-worker-release-") as directory:
        receipt_path = Path(directory) / "wrangler.ndjson"
        response = run_external(step, deploy_env={**deploy_env, "WRANGLER_OUTPUT_FILE_PATH": str(receipt_path)})
        if response.returncode:
            raise ValueError("Wrangler did not report a successful Worker version upload.")
        receipt = read_worker_receipt(receipt_path, "upload")
    version = uploaded_worker_version(receipt, "workdoe")
    step.output_excerpt = f"Wrangler uploaded Worker version {version}; traffic activation has not been attempted."
    if version == previous_version:
        raise ValueError("Wrangler returned the previous active Worker version, not a new release.")
    metadata = verify_worker_commit_tag(
        read_worker_version_metadata(repo_root, version, deploy_env, step_name=WORKER_VERSION_STEP),
        version, expected_commit,
    )
    # Wrangler's list omits non-deployable versions; a gap also catches a racing upload.
    if worker_version_number(metadata) != previous_number + 1:
        raise ValueError("The upload is not the immediate successor of the reviewed serving version. Stop before activation and review secret inheritance.")
    if expected_database_id is not None:
        verify_worker_d1_binding(metadata, expected_database_id)
    verify_worker_normal_write_mode(metadata)
    verify_uploaded_worker_configuration(metadata, Path(step.cwd))
    verify_worker_media_binding(metadata, PRODUCTION_MEDIA_BUCKET)
    step.output_excerpt = f"Verified inactive Worker version {version}; traffic activation has not been attempted."
    return version


def activate_worker_version(
    step: DeployStep, deploy_env: dict[str, str], version: str, previous_version: str | None,
) -> str:
    repo_root = Path(step.cwd).parent
    with tempfile.TemporaryDirectory(prefix="workdoe-worker-activation-") as directory:
        # Do not let a traffic switch reconcile unrelated hosted settings or triggers.
        activation_config = Path(directory) / "activation.jsonc"
        activation_config.write_text(json.dumps({"name": "workdoe"}), encoding="utf-8")
        activation = DeployStep(
            name=WORKER_ACTIVATE_STEP,
            command=wrangler_command(
                ["versions", "deploy", f"{version}@100%", "--yes", "--config", str(activation_config)], repo_root,
            ),
            cwd=step.cwd,
        )
        step.output_excerpt = f"Verified uploaded Worker version {version}; traffic activation requested."
        receipt_path = Path(directory) / "wrangler.ndjson"
        result = run_external(activation, deploy_env={**deploy_env, "WRANGLER_OUTPUT_FILE_PATH": str(receipt_path)})
        if result.returncode:
            raise ValueError("Wrangler did not report successful Worker traffic activation.")
        deployment = activated_worker_deployment(read_worker_receipt(receipt_path, "activation"), "workdoe")
    for attempt in range(3):
        active, active_deployment = active_worker_deployment(repo_root, deploy_env)
        if active == version:
            if active_deployment != deployment:
                raise ValueError("The Wrangler activation receipt is not the active deployment.")
            break
        if active != previous_version or attempt == 2:
            raise ValueError("The uploaded Worker version is not the only active version at 100% traffic.")
        time.sleep(2)
    step.output_excerpt = f"Verified deployment {deployment} of Worker version {version} at 100% with the reviewed commit tag."
    return deployment


def schema_signature(rows) -> list[tuple[str, str, str, str]]:
    return sorted(
        (kind, name, table, sql.replace("\r\n", "\n"))
        for kind, name, table, sql in rows
    )


def d1_state_error(
    cloudflare_dir: Path, completed: subprocess.CompletedProcess, *, allow_prefix: bool = False,
) -> str | None:
    if completed.returncode:
        return "Could not read the production D1 migration ledger and schema."
    if len(completed.stdout) > D1_LEDGER_RESPONSE_MAX:
        return "Production D1 migration ledger and schema response exceeds the size limit."
    try:
        payload = json.loads(completed.stdout)
        if not isinstance(payload, list) or len(payload) != 1:
            raise ValueError
        result = payload[0]
        if not isinstance(result, dict) or result.get("success") is not True or not isinstance(result.get("results"), list):
            raise ValueError
        applied = []
        schema = []
        for row in result["results"]:
            if not isinstance(row, dict) or set(row) != {"kind", "position", "type", "name", "tbl_name", "sql"}:
                raise ValueError
            if not isinstance(row["name"], str) or not row["name"]:
                raise ValueError
            if row["kind"] == "ledger" and type(row["position"]) is int and row["position"] > 0:
                if any(row[key] is not None for key in ("type", "tbl_name", "sql")):
                    raise ValueError
                applied.append(row["name"])
            elif row["kind"] == "schema" and row["position"] is None:
                if row["type"] not in ("index", "table", "trigger", "view") or not all(
                    isinstance(row[key], str) and row[key] for key in ("tbl_name", "sql")
                ):
                    raise ValueError
                schema.append((row["type"], row["name"], row["tbl_name"], row["sql"]))
            else:
                raise ValueError
    except ValueError:
        return "Unexpected response from the production D1 migration ledger and schema."
    migrations = sorted(path for path in (cloudflare_dir / "d1" / "migrations").glob("*.sql") if path.is_file())
    names = [path.name for path in migrations]
    if allow_prefix:
        if not applied or applied != names[:len(applied)]:
            return "Production D1 migration history is not a nonempty ordered prefix of the reviewed checkout."
    elif not names or applied != names:
        return "Production D1 migration names or order do not match the reviewed checkout."
    try:
        with closing(sqlite3.connect(":memory:")) as connection:
            for migration in migrations[:len(applied)]:
                connection.executescript(migration.read_text(encoding="utf-8"))
            # An empty local ledger makes the same query return only schema rows.
            connection.execute("CREATE TABLE d1_migrations (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            expected = schema_signature(row[2:] for row in connection.execute(D1_STATE_SQL))
    except (OSError, UnicodeError, sqlite3.Error):
        return "Could not reconstruct the reviewed D1 application schema."
    if not expected or schema_signature(schema) != expected:
        return "Production D1 application schema does not match the reviewed migration state."
    return None


def save_d1_recovery_point(
    output: Path, completed: subprocess.CompletedProcess, commit: str | None, previous: str | None,
    *, database_id: str | None = None,
) -> bytes:
    if completed.returncode or len(completed.stdout) > 4096:
        raise ValueError("Could not read a bounded production D1 Time Travel response.")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as exc:
        raise ValueError("Production D1 Time Travel did not return a valid bookmark.") from exc
    bookmark = payload.get("bookmark") if isinstance(payload, dict) else None
    if not isinstance(bookmark, str) or not 16 <= len(bookmark) <= 128 or not D1_BOOKMARK.fullmatch(bookmark):
        raise ValueError("Production D1 Time Travel did not return a valid bookmark.")
    contents = (json.dumps({
        "bookmark": bookmark,
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "database": "workdoe",
        "database_id": database_id,
        "release_commit": commit,
        "previous_worker_version": previous,
    }, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as receipt:
            receipt.write(contents)
            receipt.flush()
            os.fsync(receipt.fileno())
    except OSError as exc:
        raise ValueError("Could not save a new private D1 recovery receipt; do not reuse or overwrite an existing receipt.") from exc
    return contents


def d1_recovery_receipt_matches(output: Path | None, contents: bytes | None) -> bool:
    if output is None or contents is None:
        return False
    try:
        if output.resolve(strict=True) != output or not output.is_file():
            return False
        with output.open("rb") as receipt:
            return receipt.read(len(contents) + 1) == contents
    except (OSError, RuntimeError):
        return False


def command_output(completed: subprocess.CompletedProcess) -> str:
    return "\n".join(
        value for value in (completed.stdout, completed.stderr) if value
    ).strip()


def release_smoke_result(completed: subprocess.CompletedProcess, expected_commit: str | None) -> tuple[bool, str]:
    invalid = (False, "No valid production smoke report for the reviewed commit.")
    output = completed.stdout
    if not FULL_COMMIT_ID.fullmatch(expected_commit or "") or not output or len(output) > SMOKE_JSON_MAX:
        return invalid
    try:
        report = json.loads(output)
    except (ValueError, RecursionError):
        return invalid
    if not isinstance(report, dict) or any(report.get(key) != value for key, value in {
        "service": "workdoe",
        "domain": DEFAULT_DOMAIN,
        "base_url": DEFAULT_BASE_URL,
        "asset_commit": expected_commit,
        "public_launch_approval": "not_evaluated",
    }.items()):
        return invalid
    checks = report.get("checks")
    if report.get("readiness_scope") == "reviewed_release_inputs":
        if (
            completed.returncode == 1 and report.get("ready") is False and isinstance(checks, list)
            and len(checks) == 1 and isinstance(checks[0], dict)
            and checks[0].get("name") == "reviewed-release-inputs"
            and checks[0].get("status") == "failed" and checks[0].get("required") is True
        ):
            return False, "Failed: reviewed-release-inputs."
        return invalid
    names = RELEASE_SMOKE_REQUIRED + RELEASE_SMOKE_OPTIONAL
    scope = ISOLATED_BETA_SMOKE_SCOPE if expected_commit in ISOLATED_BETA_COMMITS else RELEASE_SMOKE_SCOPE
    if report.get("readiness_scope") != scope or not isinstance(checks, list) or len(checks) != len(names):
        return invalid
    results = {}
    for check in checks:
        if not isinstance(check, dict):
            return invalid
        name = check.get("name")
        if not isinstance(name, str) or name not in names or name in results:
            return invalid
        required = name in RELEASE_SMOKE_REQUIRED
        if check.get("required") is not required or check.get("status") not in (
            "ready", "failed" if required else "warning",
        ):
            return invalid
        results[name] = check
    failures = []
    warnings = []
    # Only allowlisted IDs and numeric HTTP codes enter the release receipt.
    for name in names:
        check = results[name]
        if check["status"] == "ready":
            continue
        code = check.get("status_code")
        label = f"{name} (HTTP {code})" if type(code) is int and 100 <= code <= 599 else name
        (failures if check["required"] else warnings).append(label)
    ready = not failures
    if report.get("ready") is not ready or completed.returncode != int(not ready):
        return invalid
    summary = f"Failed: {', '.join(failures)}." if failures else "All required commit-bound public smoke checks passed."
    if warnings:
        summary += f" Warning: {', '.join(warnings)}."
    return ready, summary


def observe_worker_version(repo_root: Path, deploy_env: dict[str, str]) -> str | None:
    try:
        return active_worker_version(repo_root, deploy_env)
    except ValueError:
        return None


def worker_traffic_note(active: str | None, previous: str | None, verified: str | None) -> str:
    if active is None:
        state = "Could not confirm a single active Worker at 100% traffic."
    elif active == previous:
        state = f"Observed the pre-release Worker {active} at 100% traffic."
    elif active == verified:
        state = f"Observed the verified release Worker {active} at 100% traffic, but release checks did not finish."
    else:
        state = f"Observed a different Worker {active} at 100% traffic; its release identity was not verified."
    return f"{state} Review traffic and D1 state before retrying or rolling back. No rollback was attempted."


def execute_steps(
    steps: list[DeployStep],
    deploy_env: dict[str, str] | None = None,
    *,
    check_source: Callable[[], list[str]] | None = None,
    check_hosted_ingress: Callable[[], None] | None = None,
    check_clerk_settings: Callable[[], None] | None = None,
    expected_commit: str | None = None,
    previous_worker_version: str | None = None,
    d1_recovery_output: Path | None = None,
    expected_database_id: str | None = None,
) -> tuple[list[DeployStep], list[str], list[str]]:
    if expected_commit in ISOLATED_BETA_COMMITS and (
        previous_worker_version != ISOLATED_BETA_BASELINES[expected_commit][1] or expected_database_id is None
        or check_source is None or check_hosted_ingress is None
        or [step.name for step in steps] != [
            D1_LEDGER_STEP, WORKER_UPLOAD_STEP, D1_BETA_FINAL_STEP, WORKER_ACTIVATE_STEP, "smoke-production",
        ]
    ):
        return steps, ["The isolated beta requires the exact guarded no-migration sequence."], []
    errors: list[str] = []
    warnings: list[str] = []
    uploaded_version = None
    activated_version = None
    deployment_id = None
    recovery_receipt = None
    prefix_verified = False
    migration_completed = False
    schema_verified = False
    migration_step = next((step for step in steps if step.name == "apply-d1-migrations"), None)
    migration_planned = migration_step is not None

    def require_hosted_ingress() -> None:
        if check_hosted_ingress is None:
            raise ValueError(HOSTED_INGRESS_REQUIRED)
        check_hosted_ingress()

    if migration_step is not None:
        try:
            d1_recovery_output = d1_recovery_target(Path(migration_step.cwd).parent, d1_recovery_output)
        except ValueError as exc:
            steps[0].status = "failed"
            errors.append(f"{steps[0].name}: {exc}")
            return steps, errors, warnings
    for step in steps:
        if (step.name in {D1_RECOVERY_STEP, D1_PREFIX_LEDGER_STEP} and d1_recovery_output is None) or (
            step.name == "apply-d1-migrations" and recovery_receipt is None
        ):
            step.status = "failed"
            errors.append(f"{step.name}: {D1_RECOVERY_REQUIRED}")
            break
        if step.name == "apply-d1-migrations" and not prefix_verified:
            step.status = "failed"
            errors.append(f"{step.name}: Verify the production D1 migration prefix before applying migrations.")
            break
        if step.name in {D1_RECOVERY_STEP, "apply-d1-migrations"} and not uploaded_version:
            step.status = "failed"
            errors.append(f"{step.name}: A verified inactive Worker upload is required before D1 migration.")
            break
        if step.name == WORKER_UPLOAD_STEP and not (prefix_verified if migration_planned else schema_verified):
            step.status = "failed"
            errors.append(f"{step.name}: Verify the reviewed D1 migration state before uploading.")
            break
        if step.name == WORKER_ACTIVATE_STEP and (not schema_verified or not uploaded_version):
            step.status = "failed"
            errors.append(f"{step.name}: Verify the complete D1 ledger and schema and the inactive Worker before activation.")
            if migration_completed:
                errors.append(D1_AFTER_APPLY_NOTICE)
            break
        if check_source is not None and step.name in D1_LEDGER_STEPS | {"apply-d1-migrations", WORKER_UPLOAD_STEP, WORKER_ACTIVATE_STEP}:
            blockers = check_source()
            if blockers:
                step.status = "failed"
                errors.extend(f"{step.name}: {blocker}" for blocker in blockers)
                if migration_completed:
                    errors.append(D1_AFTER_APPLY_NOTICE)
                break
        if step.name == "apply-d1-migrations" and not d1_recovery_receipt_matches(d1_recovery_output, recovery_receipt):
            step.status = "failed"
            errors.append(f"{step.name}: {D1_RECOVERY_CHANGED}")
            break
        if step.name == "apply-d1-migrations":
            try:
                require_hosted_ingress()
            except ValueError as exc:
                step.status = "failed"
                errors.append(f"{step.name}: {exc} Migrations were not attempted.")
                break
        if step.name in {WORKER_UPLOAD_STEP, WORKER_ACTIVATE_STEP}:
            release_env = deploy_env or wrangler_env(REPO_ROOT)
            try:
                if step.name == WORKER_UPLOAD_STEP:
                    if not FULL_COMMIT_ID.fullmatch(expected_commit or "") or not valid_worker_version(previous_worker_version):
                        raise ValueError("Upload requires the reviewed full commit and the captured active Worker version.")
                    require_hosted_ingress()
                    uploaded_version = upload_and_verify_worker(
                        step, release_env, expected_commit, previous_worker_version,
                        expected_database_id=expected_database_id,
                    )
                else:
                    if check_source is None:
                        blockers = worker_baseline_blockers(Path(step.cwd).parent, previous_worker_version, release_env)
                        if blockers:
                            raise ValueError("Pre-activation check failed: " + " ".join(blockers))
                    require_hosted_ingress()
                    if check_clerk_settings is not None:
                        check_clerk_settings()
                    deployment_id = activate_worker_version(step, release_env, uploaded_version, previous_worker_version)
                    activated_version = uploaded_version
                    try:
                        require_hosted_ingress()
                    except ValueError as exc:
                        raise ValueError(f"Post-activation hosted ingress and privacy verification failed: {exc}") from exc
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                step.status = "failed"
                detail = str(exc) if isinstance(exc, ValueError) else "Could not complete or verify the Worker release step."
                active = observe_worker_version(Path(step.cwd).parent, release_env)
                errors.append(f"{step.name}: {detail} {worker_traffic_note(active, previous_worker_version, uploaded_version)}")
                if migration_completed:
                    errors.append(D1_AFTER_APPLY_NOTICE)
                break
            step.status = "done"
            continue
        try:
            completed = (
                run_external(step, deploy_env=deploy_env)
                if deploy_env is not None
                else run_external(step)
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            step.status = "failed"
            if step.name == D1_RECOVERY_STEP:
                errors.append(f"{step.name}: Could not retrieve the production D1 recovery point.")
                break
            if step.name == "apply-d1-migrations":
                errors.append(f"{step.name}: Could not complete D1 migrations. {D1_AFTER_APPLY_NOTICE}")
                break
            if step.name == "smoke-production":
                detail = "Could not complete production smoke testing."
                if activated_version:
                    active = observe_worker_version(Path(step.cwd), deploy_env or wrangler_env(REPO_ROOT))
                    detail += " " + worker_traffic_note(active, previous_worker_version, activated_version)
                errors.append(f"{step.name}: {detail}")
                break
            detail = "Could not read the production D1 migration ledger and schema." if step.name in D1_LEDGER_STEPS else str(exc)
            if step.name == D1_LEDGER_STEP and migration_completed:
                detail += " " + D1_AFTER_APPLY_NOTICE
            message = f"{step.name}: {detail}"
            if step.required:
                errors.append(message)
            else:
                warnings.append(message)
            if step.required:
                break
            continue
        if step.name == D1_RECOVERY_STEP and d1_recovery_output is not None:
            try:
                recovery_receipt = save_d1_recovery_point(
                    d1_recovery_output, completed, expected_commit, previous_worker_version,
                    database_id=expected_database_id,
                )
            except ValueError as exc:
                step.status = "failed"
                errors.append(f"{step.name}: {exc}")
                break
            step.status = "done"
            step.output_excerpt = "Saved a fresh production D1 Time Travel bookmark before migration."
            continue
        if step.name in D1_LEDGER_STEPS:
            prefix = step.name == D1_PREFIX_LEDGER_STEP
            error = d1_state_error(Path(step.cwd), completed, allow_prefix=prefix)
            if error:
                step.status = "failed"
                if migration_completed:
                    error += " " + D1_AFTER_APPLY_NOTICE
                errors.append(f"{step.name}: {error}")
                break
            if prefix:
                prefix_verified = True
            else:
                schema_verified = True
            step.status = "done"
            step.output_excerpt = "D1 migration ledger and application schema match the reviewed migration state."
            continue
        if step.name == "apply-d1-migrations":
            if completed.returncode:
                step.status = "failed"
                errors.append(f"{step.name}: Wrangler did not report migration success. {D1_AFTER_APPLY_NOTICE}")
                break
            migration_completed = True
            schema_verified = False
            step.status = "done"
            continue
        if step.name == "smoke-production":
            smoke_ready, step.output_excerpt = release_smoke_result(completed, expected_commit)
            if activated_version:
                try:
                    active, active_deployment = active_worker_deployment(Path(step.cwd), deploy_env or wrangler_env(REPO_ROOT))
                except ValueError:
                    active = active_deployment = None
                if not smoke_ready or active != activated_version or active_deployment != deployment_id:
                    step.status = "failed"
                    details = [step.output_excerpt] if not smoke_ready else []
                    if active is None:
                        details.append("Could not recheck the verified Worker deployment after smoke testing.")
                    elif active != activated_version or active_deployment != deployment_id:
                        details.append("The verified Worker deployment changed during smoke testing.")
                    note = worker_traffic_note(active, previous_worker_version, activated_version)
                    errors.append("\n".join([f"{step.name}: {note}", *details]))
                    break
            if not smoke_ready:
                step.status = "failed"
                errors.append(f"{step.name}: {step.output_excerpt}")
                break
        if completed.returncode == 0:
            step.status = "done"
            continue
        detail = step.output_excerpt or command_output(completed)
        step.status = "failed"
        message = f"{step.name}: {detail or 'command failed'}"
        if step.required:
            errors.append(message)
        else:
            warnings.append(message)
        if step.required:
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
    parser.add_argument("--expected-commit", help="Full Git commit ID approved for this production release.")
    parser.add_argument("--expected-worker-version", help="Previously captured UUID for the Worker version serving all traffic.")
    parser.add_argument(
        "--isolated-clerk-beta-checkout", "--isolated-beta-checkout", type=Path, metavar="DIR",
        help="Use an exact reviewed isolated beta checkout; requires --migrations skip and its reviewed serving version.",
    )
    parser.add_argument(
        "--migrations", choices=("apply", "skip"),
        help="Apply remote D1 migrations or verify the ledger without applying migrations.",
    )
    parser.add_argument(
        "--d1-recovery-output", type=Path,
        help="New private JSON receipt required for --migrations apply. Use an existing directory outside the checkout or an ignored path outside release inputs.",
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
        "--api-token-file",
        type=Path,
        help=(
            "Optional ignored local file containing exactly one Cloudflare API token. "
            "Its value is never printed or written to release evidence."
        ),
    )
    parser.add_argument(
        "--use-staged-api-token-if-present",
        action="store_true",
        help=(
            "Use cloudflare/.deploy-token when it is present; otherwise preserve "
            "the current CLOUDFLARE_API_TOKEN environment behavior."
        ),
    )
    parser.add_argument(
        "--allow-wrangler-oauth",
        action="store_true",
        help="Allow an existing Wrangler OAuth session for owner-run releases only.",
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
        help="Omit smoke from a dry-run plan; production execution always includes it.",
    )
    args = parser.parse_args()
    include_smoke = not args.no_smoke
    isolated = args.isolated_clerk_beta_checkout is not None
    release_root = args.isolated_clerk_beta_checkout.resolve() if isolated else REPO_ROOT
    profile_options = {"isolated_clerk_beta": True} if isolated else {}
    if isolated and (
        args.expected_commit not in ISOLATED_BETA_COMMITS
        or args.expected_worker_version != ISOLATED_BETA_BASELINES[args.expected_commit][1]
        or args.migrations != "skip" or not include_smoke or args.d1_recovery_output is not None or args.env_file is not None
    ):
        parser.error("The isolated beta requires its exact commit and serving version, --migrations skip, and mandatory smoke.")
    if args.expected_commit in ISOLATED_BETA_COMMITS and not isolated:
        parser.error("Use --isolated-beta-checkout for an exact reviewed isolated beta commit.")

    if args.execute and not include_smoke:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "Production execution requires the post-deploy smoke check.",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    if not args.execute:
        payload = plan_payload(
            **({"repo_root": release_root} if isolated else {}),
            secret_list_json=args.secret_list_json,
            env_file=args.env_file,
            clerk_proxy_proof_json=args.clerk_proxy_proof_json,
            include_smoke=include_smoke,
            dry_run=True,
            expected_commit=args.expected_commit,
            migrations=args.migrations,
            expected_worker_version=args.expected_worker_version,
            d1_recovery_output=args.d1_recovery_output,
            **profile_options,
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Workdoe production deploy plan")
            print("Dry run: no deployment commands were executed.")
            print(f"Local technical checks passed: {payload['ready_to_deploy']}")
            print("This plan does not grant deployment or public-launch approval; hosted checks have not run.")
            print("Execution also requires a current browser dependency advisory check; dry run does not query npm.")
            if isolated:
                print("Traffic activates only after the final schema check. The isolated beta never applies migrations.")
            else:
                print("Upload verification precedes D1 changes. Traffic activates only after the final schema check.")
            print("Worker triggers and script settings are not synced.")
            if payload["expected_worker_version"]:
                print(f"Required active Worker version: {payload['expected_worker_version']}")
            for blocker in payload["strict_blockers"]:
                print(f"- blocker: {blocker}")
            for step in payload["steps"]:
                command = " ".join(step["command"]) or "Activate the verified version at 100% after schema verification."
                print(f"- {step['name']}: {command}")
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

    source_blockers = isolated_beta_source_blockers(release_root, args.expected_commit) if isolated else release_source_blockers(REPO_ROOT, args.expected_commit)
    if not valid_worker_version(args.expected_worker_version):
        source_blockers.append(WORKER_BASELINE_REQUIRED)
    if args.migrations is None:
        source_blockers.append("Choose --migrations apply or --migrations skip before execution.")
    if args.migrations == "apply":
        try:
            args.d1_recovery_output = d1_recovery_target(REPO_ROOT, args.d1_recovery_output)
        except ValueError as exc:
            source_blockers.append(str(exc))
    if source_blockers:
        print(json.dumps({"ok": False, "executes_commands": False, "error": source_blockers[0], "blockers": source_blockers}))
        return 2

    readiness = (
        isolated_beta_readiness_payload(release_root, args.secret_list_json, args.clerk_proxy_proof_json) if isolated
        else readiness_payload(
            secret_list_json=args.secret_list_json, env_file=args.env_file, clerk_proxy_proof_json=args.clerk_proxy_proof_json,
        )
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

    dependency_errors = verify_dependency_provenance(
        REPO_ROOT / "DEPENDENCY_PROVENANCE.json", verify_release_advisories=True,
    )
    if dependency_errors:
        print(json.dumps({
            "ok": False,
            "executes_commands": False,
            "error": "Dependency release gate failed; deploy was not run.",
            "blockers": dependency_errors,
            "warnings": readiness["warnings"],
        }, indent=2, sort_keys=True))
        return 1
    if isolated:
        try:
            pins = read_clerk_archive_pins(release_root, args.expected_commit, isolated_clerk_beta=True)
            if len(pins) != 202:
                raise ValueError("Incomplete inventory")
        except (OSError, TypeError, ValueError, SyntaxError, RecursionError, subprocess.SubprocessError):
            print(json.dumps({"ok": False, "executes_commands": False, "error": "Could not verify the isolated beta's 202 Clerk archive pins."}))
            return 1

    try:
        if args.api_token_file is not None:
            api_token = cloudflare_api_token_from_file(args.api_token_file)
        elif args.use_staged_api_token_if_present and DEFAULT_STAGED_API_TOKEN_PATH.is_file():
            api_token = cloudflare_api_token_from_file(DEFAULT_STAGED_API_TOKEN_PATH)
        else:
            api_token = None
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "dry_run": False,
                    "executes_commands": False,
                    "error": str(exc),
                    "warnings": readiness["warnings"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    deploy_env = wrangler_env(REPO_ROOT, api_token=api_token)
    use_oauth = not cloudflare_api_token_present(deploy_env)
    if use_oauth and (not args.allow_wrangler_oauth or deploy_env.get("GITHUB_ACTIONS") == "true"):
        print(
            json.dumps(
                {
                    "ok": False,
                    "dry_run": False,
                    "executes_commands": False,
                    "error": cloudflare_api_token_error(
                        "verify hosted ingress and deploy the Cloudflare Worker"
                    ),
                    "warnings": readiness["warnings"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    if use_oauth:
        deploy_env = {**ambient_wrangler_env(), "CI": "true"}
    if isolated:
        deploy_env.update({"CI": "true", "WRANGLER_WRITE_LOGS": "false", "WRANGLER_SEND_METRICS": "false"})
        for name in ("WRANGLER_OUTPUT_FILE_PATH", "WRANGLER_OUTPUT_FILE_DIRECTORY"):
            deploy_env.pop(name, None)

    source_blockers = isolated_beta_source_blockers(release_root, args.expected_commit) if isolated else release_source_blockers(REPO_ROOT, args.expected_commit)
    if source_blockers:
        print(json.dumps({"ok": False, "executes_commands": False, "error": source_blockers[0], "blockers": source_blockers}))
        return 2

    try:
        cloudflare_dir = release_root / "cloudflare" if isolated else CLOUDFLARE_DIR
        database_id = reviewed_d1_database_id(cloudflare_dir)
        account_id = reviewed_ingress_account(cloudflare_dir, deploy_env)
        reviewed_clerk_proof = clerk_release_proof_digest(args.clerk_proxy_proof_json)
    except ValueError as exc:
        print(json.dumps({"ok": False, "executes_commands": False, "error": str(exc)}))
        return 2

    check_release_inputs = release_input_check(
        release_root, args.expected_commit, args.expected_worker_version, database_id, deploy_env,
    )

    def check_source_and_clerk_proof() -> list[str]:
        return clerk_proof_guard(args.clerk_proxy_proof_json, reviewed_clerk_proof) or check_release_inputs()

    def check_clerk_activation() -> None:
        check_clerk_before_activation()
        if blockers := clerk_proof_guard(args.clerk_proxy_proof_json, reviewed_clerk_proof):
            raise ValueError(blockers[0])

    def check_hosted_ingress() -> None:
        if use_oauth:
            verify_hosted_worker_ingress(
                account_id, deploy_env, oauth_token=wrangler_oauth_access_token(release_root, deploy_env),
            )
        else:
            verify_hosted_worker_ingress(account_id, deploy_env)

    steps, errors, warnings = execute_steps(
        build_deploy_steps(
            **({"repo_root": release_root} if isolated else {}),
            include_smoke=include_smoke, migrations=args.migrations, expected_commit=args.expected_commit,
            **profile_options,
        ),
        deploy_env=deploy_env,
        check_source=check_source_and_clerk_proof,
        check_hosted_ingress=check_hosted_ingress,
        check_clerk_settings=check_clerk_activation,
        expected_commit=args.expected_commit,
        previous_worker_version=args.expected_worker_version,
        d1_recovery_output=args.d1_recovery_output,
        expected_database_id=database_id,
    )
    payload = {
        "ok": not errors,
        "dry_run": False,
        "executes_commands": True,
        "browser_dependency_gate": "passed",
        "tooling_dependency_gate": "passed",
        "release_commit": args.expected_commit,
        "expected_worker_version": args.expected_worker_version,
        "migrations": args.migrations,
        "errors": errors,
        "warnings": warnings,
        "steps": [asdict(step) for step in steps],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
