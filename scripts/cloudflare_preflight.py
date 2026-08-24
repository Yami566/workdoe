from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import py_compile
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
REQUIRED_DEV_ENV = {
    "CLERK_JWT_KEY",
    "CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_WEBHOOK_SECRET",
    "WORKDOE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SITE_KEY",
}
REQUIRED_PUBLIC_ENV = {
    "WORKDOE_AUTH_PROVIDER",
    "WORKDOE_LOGIN_MODE",
    "WORKDOE_ENFORCE_SERVICE_ACTIVATION",
}
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
CLERK_PROXY_PATH = "/__clerk"
DEFAULT_CLERK_FAPI = "https://frontend-api.clerk.dev"
REQUIRED_MIGRATION_MARKERS = {
    "CREATE TABLE IF NOT EXISTS users",
    "auth_provider TEXT NOT NULL DEFAULT 'local'",
    "external_subject TEXT",
    "CREATE TABLE IF NOT EXISTS login_codes",
    "selected_job_id INTEGER",
    "CREATE TABLE IF NOT EXISTS automation_events",
    "idx_users_auth_subject",
    "idx_login_codes_selected_job",
    "idx_automation_events_type_target",
}


def is_workdoe_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == WORKDOE_PUBLIC_DOMAIN or host.endswith(f".{WORKDOE_PUBLIC_DOMAIN}")


def valid_workdoe_clerk_frontend_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip().lower())
    return parsed.scheme == "https" and is_workdoe_domain(parsed.hostname)


def valid_workdoe_clerk_proxy_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip().lower().rstrip("/"))
    return (
        parsed.scheme == "https"
        and parsed.hostname == WORKDOE_PUBLIC_DOMAIN
        and (parsed.path == CLERK_PROXY_PATH or parsed.path.startswith(f"{CLERK_PROXY_PATH}/"))
    )


def valid_clerk_fapi_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip().lower().rstrip("/"))
    expected = urlparse(DEFAULT_CLERK_FAPI)
    return (
        parsed.scheme == expected.scheme
        and parsed.netloc == expected.netloc
        and parsed.path.rstrip("/") == ""
    )
REQUIRED_CRONS = {"*/15 * * * *", "0 14 * * *", "0 13 * * 1-5"}
REQUIRED_QUEUE_BINDINGS = {"EMAIL_QUEUE": "workdoe-email", "MEDIA_QUEUE": "workdoe-media-review"}
REQUIRED_RATE_LIMIT_BINDINGS = [
    {
        "name": "WRITE_RATE_LIMITER",
        "namespace_id": "949417",
        "simple": {"limit": 40, "period": 60},
    }
]
REQUIRED_WORKER_SECRETS = REQUIRED_DEV_ENV


@dataclass
class PreflightResult:
    checks: list[str]
    warnings: list[str]
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def load_release_module():
    script_path = REPO_ROOT / "scripts" / "prepare_cloudflare_release.py"
    spec = importlib.util.spec_from_file_location("prepare_cloudflare_release", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_json(path: Path, errors: list[str]) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing file: {path}")
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
    return {}


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        errors.append(f"Missing file: {path}")
    return ""


def add_ok(checks: list[str], name: str) -> None:
    checks.append(name)


def require(condition: bool, errors: list[str], message: str, checks: list[str], ok_name: str) -> None:
    if condition:
        add_ok(checks, ok_name)
    else:
        errors.append(message)


def compile_python(path: Path, errors: list[str], checks: list[str], ok_name: str) -> None:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            cfile = Path(tmp) / f"{path.stem}.pyc"
            py_compile.compile(str(path), cfile=str(cfile), doraise=True)
        add_ok(checks, ok_name)
    except py_compile.PyCompileError as exc:
        errors.append(f"{ok_name} failed: {exc.msg}")


def validate_fresh_d1_migration_chain(
    migrations_dir: Path,
    errors: list[str],
    checks: list[str],
) -> None:
    migration_paths = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not migration_paths:
        errors.append(f"No D1 migrations found in {migrations_dir}.")
        return
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for path in migration_paths:
            try:
                connection.executescript(path.read_text(encoding="utf-8"))
            except sqlite3.Error as exc:
                errors.append(
                    f"Fresh D1 migration chain fails at {path.name}: {exc}"
                )
                return
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            errors.append(
                "Fresh D1 migration chain leaves foreign-key errors: "
                + repr(foreign_key_errors[:5])
            )
            return
        add_ok(checks, "Fresh D1 database accepts the complete migration chain")
    finally:
        connection.close()


def run_preflight(repo_root: Path = REPO_ROOT, strict_production: bool = False) -> PreflightResult:
    checks: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    release_module = load_release_module()
    with tempfile.TemporaryDirectory() as tmp:
        generated = release_module.prepare_release(repo_root, Path(tmp) / "cloudflare")
        generated_migration = Path(generated["migration"]).read_text(encoding="utf-8")
        generated_manifest = json.loads(Path(generated["manifest"]).read_text(encoding="utf-8"))
        generated_wrangler = json.loads(Path(generated["wrangler"]).read_text(encoding="utf-8"))
        generated_dev_vars = Path(generated["dev_vars_example"]).read_text(encoding="utf-8")

    migration_path = repo_root / "cloudflare" / "d1" / "migrations" / "0001_initial.sql"
    migrations_dir = migration_path.parent
    project_draft_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0003_project_drafts_and_budgets.sql"
    )
    service_taxonomy_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0004_service_taxonomy.sql"
    )
    taxonomy_catchall_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0005_taxonomy_catchall.sql"
    )
    contractor_market_fit_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0006_contractor_market_fit.sql"
    )
    client_profile_migration_path = (
        repo_root
        / "cloudflare"
        / "d1"
        / "migrations"
        / "0007_client_profiles_and_saved_locations.sql"
    )
    match_completion_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0008_match_completions.sql"
    )
    bid_window_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0009_bid_windows.sql"
    )
    project_outcomes_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0010_project_outcomes.sql"
    )
    service_activation_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0011_service_zone_activations.sql"
    )
    project_settings_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0012_project_settings.sql"
    )
    email_reminder_consent_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0013_email_reminder_consent.sql"
    )
    contractor_credentials_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0014_contractor_credentials.sql"
    )
    contractor_preferences_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0015_contractor_lead_preferences.sql"
    )
    client_project_templates_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0016_client_project_templates.sql"
    )
    repeat_provider_invitations_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0017_repeat_provider_invitations.sql"
    )
    contractor_lead_alerts_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0018_contractor_lead_alerts.sql"
    )
    match_reviews_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0019_match_reviews.sql"
    )
    job_scope_answers_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0020_job_scope_answers.sql"
    )
    saved_lead_family_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0021_saved_lead_work_family.sql"
    )
    idempotency_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0022_idempotent_marketplace_writes.sql"
    )
    contractor_proposal_templates_migration_path = (
        repo_root
        / "cloudflare"
        / "d1"
        / "migrations"
        / "0023_contractor_proposal_templates.sql"
    )
    service_family_labels_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0024_service_family_labels.sql"
    )
    saved_lead_task_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0025_saved_lead_task.sql"
    )
    service_aliases_icons_migration_path = (
        repo_root
        / "cloudflare"
        / "d1"
        / "migrations"
        / "0026_service_aliases_and_icons.sql"
    )
    public_job_viewport_index_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0027_public_job_viewport_index.sql"
    )
    public_job_photo_index_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0029_public_job_photo_index.sql"
    )
    thread_nav_indexes_migration_path = (
        repo_root / "cloudflare" / "d1" / "migrations" / "0031_thread_nav_indexes.sql"
    )
    contractor_choice_photo_index_migration_path = (
        repo_root
        / "cloudflare"
        / "d1"
        / "migrations"
        / "0032_contractor_choice_photo_index.sql"
    )
    single_approved_match_migration_path = (
        repo_root
        / "cloudflare"
        / "d1"
        / "migrations"
        / "0033_single_approved_match.sql"
    )
    project_license_preference_migration_path = (
        repo_root
        / "cloudflare"
        / "d1"
        / "migrations"
        / "0034_project_license_preference.sql"
    )
    manifest_path = repo_root / "cloudflare" / "workdoe-cloudflare-manifest.json"
    wrangler_path = repo_root / "cloudflare" / "wrangler.jsonc"
    dev_vars_path = repo_root / "cloudflare" / ".dev.vars.example"
    worker_path = repo_root / "cloudflare" / "worker" / "entry.py"
    app_shell_path = repo_root / "cloudflare" / "worker" / "app_shell.py"
    clerk_onboarding_path = repo_root / "cloudflare" / "worker" / "clerk_onboarding.py"
    clerk_sessions_path = repo_root / "cloudflare" / "worker" / "clerk_sessions.py"
    email_code_auth_path = repo_root / "cloudflare" / "worker" / "email_code_auth.py"
    email_payloads_path = repo_root / "cloudflare" / "worker" / "email_payloads.py"
    admin_moderation_path = repo_root / "cloudflare" / "worker" / "admin_moderation.py"
    contractor_profiles_path = repo_root / "cloudflare" / "worker" / "contractor_profiles.py"
    contractor_reputation_path = (
        repo_root / "cloudflare" / "worker" / "contractor_reputation.py"
    )
    local_contractor_reputation_path = repo_root / "workdoe" / "contractor_reputation.py"
    contractor_credentials_path = repo_root / "cloudflare" / "worker" / "contractor_credentials.py"
    contractor_preferences_path = repo_root / "cloudflare" / "worker" / "contractor_preferences.py"
    client_project_templates_path = repo_root / "cloudflare" / "worker" / "client_project_templates.py"
    contractor_proposal_templates_path = (
        repo_root / "cloudflare" / "worker" / "contractor_proposal_templates.py"
    )
    client_profiles_path = repo_root / "cloudflare" / "worker" / "client_profiles.py"
    contractor_public_profiles_path = repo_root / "cloudflare" / "worker" / "contractor_public_profiles.py"
    contractor_leads_path = repo_root / "cloudflare" / "worker" / "contractor_leads.py"
    contractor_bids_path = repo_root / "cloudflare" / "worker" / "contractor_bids.py"
    client_jobs_path = repo_root / "cloudflare" / "worker" / "client_jobs.py"
    client_requests_path = repo_root / "cloudflare" / "worker" / "client_requests.py"
    bid_comparison_path = repo_root / "cloudflare" / "worker" / "bid_comparison.py"
    repeat_provider_invitations_path = (
        repo_root / "cloudflare" / "worker" / "repeat_provider_invitations.py"
    )
    entry_shell_path = repo_root / "cloudflare" / "worker" / "entry_shell.py"
    clerk_proxy_path = repo_root / "cloudflare" / "worker" / "clerk_proxy.py"
    webhook_security_path = repo_root / "cloudflare" / "worker" / "clerk_webhooks.py"
    public_jobs_path = repo_root / "cloudflare" / "worker" / "public_jobs.py"
    public_job_query_path = repo_root / "cloudflare" / "worker" / "public_job_query.py"
    job_details_path = repo_root / "cloudflare" / "worker" / "job_details.py"
    job_status_path = repo_root / "cloudflare" / "worker" / "job_status.py"
    job_posts_path = repo_root / "cloudflare" / "worker" / "job_posts.py"
    service_taxonomy_path = repo_root / "cloudflare" / "worker" / "service_taxonomy.py"
    service_scope_path = repo_root / "cloudflare" / "worker" / "service_scope.py"
    project_readiness_path = repo_root / "cloudflare" / "worker" / "project_readiness.py"
    pilot_metrics_path = repo_root / "cloudflare" / "worker" / "pilot_metrics.py"
    service_activation_path = repo_root / "cloudflare" / "worker" / "service_activation.py"
    market_fit_path = repo_root / "cloudflare" / "worker" / "market_fit.py"
    match_completions_path = repo_root / "cloudflare" / "worker" / "match_completions.py"
    match_reviews_path = repo_root / "cloudflare" / "worker" / "match_reviews.py"
    job_drafts_path = repo_root / "cloudflare" / "worker" / "job_drafts.py"
    turnstile_path = repo_root / "cloudflare" / "worker" / "turnstile.py"
    match_requests_path = repo_root / "cloudflare" / "worker" / "match_requests.py"
    match_decisions_path = repo_root / "cloudflare" / "worker" / "match_decisions.py"
    message_threads_path = repo_root / "cloudflare" / "worker" / "message_threads.py"
    moderation_reports_path = repo_root / "cloudflare" / "worker" / "moderation_reports.py"
    media_access_path = repo_root / "cloudflare" / "worker" / "media_access.py"
    media_uploads_path = repo_root / "cloudflare" / "worker" / "media_uploads.py"
    request_security_path = repo_root / "cloudflare" / "worker" / "request_security.py"
    idempotency_path = repo_root / "cloudflare" / "worker" / "idempotency.py"
    launch_plan_path = repo_root / "scripts" / "cloudflare_launch_plan.py"
    launch_status_path = repo_root / "scripts" / "cloudflare_launch_status.py"
    wrangler_helper_path = repo_root / "scripts" / "cloudflare_wrangler.py"
    clerk_proxy_proof_path = repo_root / "scripts" / "cloudflare_clerk_proxy_proof.py"
    secret_evidence_path = repo_root / "scripts" / "cloudflare_secret_evidence.py"
    release_evidence_path = repo_root / "scripts" / "cloudflare_release_evidence.py"
    d1_id_apply_path = repo_root / "scripts" / "apply_cloudflare_d1_ids.py"
    resource_bootstrap_path = repo_root / "scripts" / "cloudflare_resource_bootstrap.py"
    production_deploy_path = repo_root / "scripts" / "cloudflare_production_deploy.py"
    github_release_status_path = repo_root / "scripts" / "github_release_status.py"
    github_deploy_dispatch_path = repo_root / "scripts" / "github_deploy_dispatch.py"
    workdoe_launch_doctor_path = repo_root / "scripts" / "workdoe_launch_doctor.py"
    workdoe_launch_handoff_path = repo_root / "scripts" / "workdoe_launch_handoff.py"
    workdoe_dns_diagnostic_path = repo_root / "scripts" / "workdoe_dns_diagnostic.py"
    workdoe_production_smoke_path = repo_root / "scripts" / "workdoe_production_smoke.py"
    static_path = repo_root / "workdoe" / "static"
    worker_actions_path = static_path / "worker-actions.js"
    project_composer_path = static_path / "project-composer.js"
    clerk_entry_path = static_path / "clerk-entry.js"
    clerk_account_path = static_path / "clerk-account.js"
    email_code_entry_path = static_path / "email-code-entry.js"

    migration_sql = read_text(migration_path, errors)
    project_draft_migration_sql = read_text(project_draft_migration_path, errors)
    service_taxonomy_migration_sql = read_text(service_taxonomy_migration_path, errors)
    taxonomy_catchall_migration_sql = read_text(taxonomy_catchall_migration_path, errors)
    contractor_market_fit_migration_sql = read_text(
        contractor_market_fit_migration_path,
        errors,
    )
    client_profile_migration_sql = read_text(client_profile_migration_path, errors)
    match_completion_migration_sql = read_text(match_completion_migration_path, errors)
    bid_window_migration_sql = read_text(bid_window_migration_path, errors)
    project_outcomes_migration_sql = read_text(project_outcomes_migration_path, errors)
    service_activation_migration_sql = read_text(service_activation_migration_path, errors)
    project_settings_migration_sql = read_text(project_settings_migration_path, errors)
    email_reminder_consent_migration_sql = read_text(
        email_reminder_consent_migration_path,
        errors,
    )
    contractor_credentials_migration_sql = read_text(
        contractor_credentials_migration_path,
        errors,
    )
    contractor_preferences_migration_sql = read_text(
        contractor_preferences_migration_path,
        errors,
    )
    client_project_templates_migration_sql = read_text(
        client_project_templates_migration_path,
        errors,
    )
    repeat_provider_invitations_migration_sql = read_text(
        repeat_provider_invitations_migration_path,
        errors,
    )
    contractor_lead_alerts_migration_sql = read_text(
        contractor_lead_alerts_migration_path,
        errors,
    )
    match_reviews_migration_sql = read_text(match_reviews_migration_path, errors)
    job_scope_answers_migration_sql = read_text(
        job_scope_answers_migration_path, errors
    )
    saved_lead_family_migration_sql = read_text(
        saved_lead_family_migration_path, errors
    )
    idempotency_migration_sql = read_text(idempotency_migration_path, errors)
    contractor_proposal_templates_migration_sql = read_text(
        contractor_proposal_templates_migration_path,
        errors,
    )
    service_family_labels_migration_sql = read_text(
        service_family_labels_migration_path,
        errors,
    )
    saved_lead_task_migration_sql = read_text(
        saved_lead_task_migration_path,
        errors,
    )
    service_aliases_icons_migration_sql = read_text(
        service_aliases_icons_migration_path,
        errors,
    )
    public_job_viewport_index_migration_sql = read_text(
        public_job_viewport_index_migration_path,
        errors,
    )
    public_job_photo_index_migration_sql = read_text(
        public_job_photo_index_migration_path,
        errors,
    )
    thread_nav_indexes_migration_sql = read_text(
        thread_nav_indexes_migration_path,
        errors,
    )
    contractor_choice_photo_index_migration_sql = read_text(
        contractor_choice_photo_index_migration_path,
        errors,
    )
    single_approved_match_migration_sql = read_text(
        single_approved_match_migration_path,
        errors,
    )
    project_license_preference_migration_sql = read_text(
        project_license_preference_migration_path,
        errors,
    )
    manifest = read_json(manifest_path, errors)
    wrangler = read_json(wrangler_path, errors)
    dev_vars = read_text(dev_vars_path, errors)
    if wrangler:
        existing_d1_ids = release_module.existing_d1_ids(wrangler_path)
        if existing_d1_ids:
            generated_wrangler = release_module.build_wrangler_config(
                generated_manifest,
                d1_ids=existing_d1_ids,
            )

    if migration_sql:
        require(
            migration_sql == generated_migration,
            errors,
            "D1 immutable baseline differs from the release source.",
            checks,
            "D1 immutable baseline is preserved",
        )
        require(
            hashlib.sha256(migration_sql.encode("utf-8")).hexdigest()
            == release_module.IMMUTABLE_D1_BASELINE_SHA256,
            errors,
            "D1 0001_initial.sql changed. Add a new numbered migration instead.",
            checks,
            "D1 baseline hash is locked",
        )
    validate_fresh_d1_migration_chain(migrations_dir, errors, checks)
    if project_draft_migration_sql:
        missing_project_draft_migration_markers = [
            marker
            for marker in (
                "ALTER TABLE jobs ADD COLUMN budget_min INTEGER",
                "ALTER TABLE jobs ADD COLUMN budget_max INTEGER",
                "CREATE TABLE IF NOT EXISTS job_drafts",
                "token_hash TEXT NOT NULL UNIQUE",
                "expires_at TEXT NOT NULL",
                "idx_job_drafts_expires",
            )
            if marker not in project_draft_migration_sql
        ]
        require(
            not missing_project_draft_migration_markers,
            errors,
            "D1 project draft migration is incomplete: "
            + ", ".join(missing_project_draft_migration_markers),
            checks,
            "D1 project draft and budget migration is incremental",
        )
        missing_markers = sorted(marker for marker in REQUIRED_MIGRATION_MARKERS if marker not in migration_sql)
        require(
            not missing_markers,
            errors,
            "D1 migration is missing required markers: " + ", ".join(missing_markers),
            checks,
            "D1 migration contains auth, OTP, and automation tables",
        )
    if service_taxonomy_migration_sql:
        missing_service_taxonomy_markers = [
            marker
            for marker in (
                "CREATE TABLE IF NOT EXISTS service_groups",
                "CREATE TABLE IF NOT EXISTS service_types",
                "CREATE TABLE IF NOT EXISTS service_aliases",
                "ALTER TABLE jobs ADD COLUMN service_group_slug",
                "ALTER TABLE jobs ADD COLUMN service_slug",
                "ALTER TABLE job_drafts ADD COLUMN service_slug",
                "idx_jobs_service_status",
            )
            if marker not in service_taxonomy_migration_sql
        ]
        require(
            not missing_service_taxonomy_markers,
            errors,
            "D1 service taxonomy migration is incomplete: "
            + ", ".join(missing_service_taxonomy_markers),
            checks,
            "D1 service taxonomy migration is incremental",
        )
    if taxonomy_catchall_migration_sql:
        require(
            all(
                marker in taxonomy_catchall_migration_sql
                for marker in ("other-service", "UPDATE jobs", "UPDATE job_drafts")
            ),
            errors,
            "D1 taxonomy catch-all migration is incomplete.",
            checks,
            "D1 taxonomy catch-all preserves legacy Other records",
        )
    if service_family_labels_migration_sql:
        require(
            all(
                marker in service_family_labels_migration_sql
                for marker in (
                    "UPDATE service_groups",
                    "Yard & landscaping",
                    "Cleaning",
                    "Handyman & repairs",
                    "Remodeling",
                    "Plumbing & systems",
                )
            ),
            errors,
            "D1 service-family label migration is incomplete.",
            checks,
            "D1 service-family labels preserve canonical slugs",
        )
    if contractor_market_fit_migration_sql:
        require(
            all(
                marker in contractor_market_fit_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS service_zones",
                    "contractor_service_capabilities",
                    "contractor_service_zones",
                    "idx_contractor_capabilities_service",
                )
            ),
            errors,
            "D1 contractor market-fit migration is incomplete.",
            checks,
            "D1 contractor market-fit migration is incremental",
        )
    if client_profile_migration_sql:
        require(
            all(
                marker in client_profile_migration_sql
                for marker in (
                    "ADD COLUMN account_type",
                    "ADD COLUMN notification_preference",
                    "CREATE TABLE IF NOT EXISTS client_saved_locations",
                    "idx_client_saved_locations_owner",
                )
            ),
            errors,
            "D1 consumer-profile migration is incomplete.",
            checks,
            "D1 consumer-profile migration is incremental",
        )
    if match_completion_migration_sql:
        require(
            all(
                marker in match_completion_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS match_completions",
                    "match_request_id INTEGER PRIMARY KEY",
                    "client_confirmed_at",
                    "contractor_confirmed_at",
                    "verified_at",
                    "idx_match_completions_verified",
                )
            ),
            errors,
            "D1 match-completion migration is incomplete.",
            checks,
            "D1 two-sided match-completion migration is incremental",
        )
    if bid_window_migration_sql:
        require(
            all(
                marker in bid_window_migration_sql
                for marker in (
                    "ADD COLUMN bid_limit",
                    "ADD COLUMN bidding_closes_at",
                    "UPDATE jobs",
                    "idx_jobs_bidding_window",
                )
            ),
            errors,
            "D1 bid-window migration is incomplete.",
            checks,
            "D1 bid cap and deadline migration is incremental",
        )
    if project_outcomes_migration_sql:
        require(
            all(
                marker in project_outcomes_migration_sql
                for marker in (
                    "ADD COLUMN close_reason",
                    "ADD COLUMN close_note",
                    "ADD COLUMN closed_at",
                    "CREATE TABLE IF NOT EXISTS job_lead_feedback",
                    "authorization-concern",
                    "idx_job_lead_feedback_reason",
                )
            ),
            errors,
            "D1 project-outcome migration is incomplete.",
            checks,
            "D1 project and lead-quality outcome migration is incremental",
        )
    if service_activation_migration_sql:
        require(
            all(
                marker in service_activation_migration_sql
                for marker in (
                    "ADD COLUMN service_zone_slug",
                    "CREATE TABLE IF NOT EXISTS service_zone_activations",
                    "minimum_eligible_contractors",
                    "approved_at",
                    "reviewed_at",
                    "idx_service_zone_activations_status",
                    "'candidate'",
                )
            ),
            errors,
            "D1 service-zone activation migration is incomplete.",
            checks,
            "D1 service-zone activation migration fails closed",
        )
    if project_settings_migration_sql:
        require(
            all(
                marker in project_settings_migration_sql
                for marker in (
                    "ALTER TABLE jobs ADD COLUMN project_setting",
                    "ALTER TABLE job_drafts ADD COLUMN project_setting",
                    "NOT NULL DEFAULT ''",
                )
            ),
            errors,
            "D1 project-setting migration is incomplete.",
            checks,
            "D1 project-setting migration is incremental",
        )
    if email_reminder_consent_migration_sql:
        require(
            all(
                marker in email_reminder_consent_migration_sql
                for marker in (
                    "ADD COLUMN email_reminder_consent_at",
                    "notification_preference = 'workdoe'",
                    "email_reminder_consent_at = NULL",
                )
            ),
            errors,
            "D1 email-reminder consent migration is incomplete.",
            checks,
            "D1 email reminders require affirmative consent",
        )
    if contractor_credentials_migration_sql:
        require(
            all(
                marker in contractor_credentials_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS contractor_credentials",
                    "reviewed_by INTEGER REFERENCES users",
                    "checked_at TEXT",
                    "expires_at TEXT",
                    "idx_contractor_credentials_review",
                )
            ),
            errors,
            "D1 contractor-credential migration is incomplete.",
            checks,
            "D1 contractor credentials retain review provenance",
        )
    if contractor_preferences_migration_sql:
        require(
            all(
                marker in contractor_preferences_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS contractor_lead_preferences",
                    "availability_status IN ('available', 'limited', 'unavailable')",
                    "saved_query TEXT NOT NULL DEFAULT ''",
                    "saved_sort IN ('newest', 'soonest', 'city')",
                    "idx_contractor_lead_preferences_availability",
                )
            ),
            errors,
            "D1 contractor-preference migration is incomplete.",
            checks,
            "D1 contractor preferences preserve private saved views",
        )
    if client_project_templates_migration_sql:
        require(
            all(
                marker in client_project_templates_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS client_project_templates",
                    "client_id INTEGER NOT NULL REFERENCES users",
                    "source_job_id INTEGER REFERENCES jobs",
                    "UNIQUE(client_id, name)",
                    "idx_client_project_templates_owner",
                )
            )
            and all(
                forbidden not in client_project_templates_migration_sql
                for forbidden in ("zip_code", "desired_date", "stored_path")
            ),
            errors,
            "D1 consumer project-template migration is incomplete or stores private/stale fields.",
            checks,
            "D1 project templates exclude location, date, and media paths",
        )
    if contractor_proposal_templates_migration_sql:
        require(
            all(
                marker in contractor_proposal_templates_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS contractor_proposal_templates",
                    "contractor_id INTEGER NOT NULL REFERENCES users",
                    "source_match_request_id INTEGER REFERENCES match_requests",
                    "UNIQUE(contractor_id, name)",
                    "idx_contractor_proposal_templates_owner",
                )
            )
            and all(
                forbidden not in contractor_proposal_templates_migration_sql
                for forbidden in (
                    "price_range",
                    "email",
                    "phone",
                    "address",
                    "zip_code",
                    "stored_path",
                    "media",
                )
            ),
            errors,
            "D1 contractor proposal-template migration is incomplete or stores price/private fields.",
            checks,
            "D1 contractor proposal templates exclude price and location",
        )
    if repeat_provider_invitations_migration_sql:
        require(
            all(
                marker in repeat_provider_invitations_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS repeat_provider_invitations",
                    "source_match_request_id",
                    "contractor_id INTEGER NOT NULL REFERENCES users",
                    "'bid_sent'",
                    "idx_repeat_provider_invitations_contractor",
                )
            )
            and all(
                forbidden not in repeat_provider_invitations_migration_sql.lower()
                for forbidden in ("address", "message", "photo", "phone")
            ),
            errors,
            "D1 repeat-provider invitation migration is incomplete or stores private fields.",
            checks,
            "D1 repeat-provider invitations store lifecycle references only",
        )
    if contractor_lead_alerts_migration_sql:
        require(
            all(
                marker in contractor_lead_alerts_migration_sql
                for marker in (
                    "ADD COLUMN lead_alert_preference",
                    "ADD COLUMN lead_alert_consent_at",
                    "CREATE TABLE IF NOT EXISTS contractor_lead_alert_deliveries",
                    "UNIQUE(contractor_id, job_id)",
                    "idx_contractor_lead_alert_deliveries_status",
                )
            )
            and all(
                forbidden not in contractor_lead_alerts_migration_sql.lower()
                for forbidden in (
                    "client_email",
                    "zip_code",
                    "description",
                    "message",
                    "bid",
                )
            ),
            errors,
            "D1 contractor lead-alert migration is incomplete or stores project content.",
            checks,
            "D1 contractor lead alerts store consent and delivery state only",
        )
    if match_reviews_migration_sql:
        require(
            all(
                marker in match_reviews_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS match_reviews",
                    "UNIQUE(match_request_id, reviewer_id)",
                    "CREATE TABLE IF NOT EXISTS match_review_reports",
                    "UNIQUE(review_id, reporter_id)",
                    "idx_match_reviews_subject",
                    "idx_match_review_reports_status",
                )
            )
            and all(
                forbidden not in match_reviews_migration_sql.lower()
                for forbidden in ("email", "address", "zip_code", "phone", "photo")
            ),
            errors,
            "D1 completed-work feedback migration is incomplete or stores contact/location data.",
            checks,
            "D1 completed-work feedback is participant-bound and location-free",
        )
    if job_scope_answers_migration_sql:
        require(
            all(
                marker in job_scope_answers_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS job_scope_answers",
                    "CREATE TABLE IF NOT EXISTS job_draft_scope_answers",
                    "PRIMARY KEY (job_id, question_key)",
                    "PRIMARY KEY (draft_id, question_key)",
                    "question_key, answer_code, schema_version",
                )
            )
            and all(
                forbidden not in job_scope_answers_migration_sql.lower()
                for forbidden in (
                    "email",
                    "address",
                    "zip_code",
                    "description",
                    "phone",
                    "free_text",
                )
            ),
            errors,
            "D1 quote-readiness migration is incomplete or stores sensitive/freeform fields.",
            checks,
            "D1 quote-readiness answers are normalized and location-free",
        )
    if saved_lead_family_migration_sql:
        require(
            all(
                marker in saved_lead_family_migration_sql
                for marker in (
                    "ADD COLUMN saved_service_group_slug",
                    "idx_contractor_lead_preferences_family",
                )
            )
            and all(
                forbidden not in saved_lead_family_migration_sql.lower()
                for forbidden in ("email", "address", "zip_code", "phone", "description")
            ),
            errors,
            "D1 saved lead-family migration is incomplete or stores project/contact data.",
            checks,
            "D1 saved lead family stores one canonical taxonomy slug only",
        )
    if saved_lead_task_migration_sql:
        require(
            all(
                marker in saved_lead_task_migration_sql
                for marker in (
                    "ADD COLUMN saved_service_slug",
                    "idx_contractor_lead_preferences_service",
                )
            )
            and all(
                forbidden not in saved_lead_task_migration_sql.lower()
                for forbidden in ("email", "address", "zip_code", "phone", "description")
            ),
            errors,
            "D1 saved lead-task migration is incomplete or stores project/contact data.",
            checks,
            "D1 saved lead task stores one canonical taxonomy slug only",
        )
    if service_aliases_icons_migration_sql:
        require(
            all(
                marker in service_aliases_icons_migration_sql
                for marker in (
                    "ALTER TABLE service_types ADD COLUMN icon_name TEXT",
                    "WHEN 'lawn-mowing' THEN 'lawn-mower.svg'",
                    "('grass cutting', 'lawn-mowing')",
                    "('kitchen renovation', 'kitchen-remodel')",
                    "('plumber', 'plumbing')",
                )
            )
            and all(
                forbidden not in service_aliases_icons_migration_sql.lower()
                for forbidden in ("email", "address", "zip_code", "phone", "description")
            ),
            errors,
            "D1 service icon and recall-alias migration is incomplete or stores private data.",
            checks,
            "D1 task icons and recall aliases stay canonical and location-free",
        )
    if public_job_viewport_index_migration_sql and public_job_photo_index_migration_sql:
        require(
            "idx_jobs_open_geo" in public_job_viewport_index_migration_sql
            and "ON jobs(status, approx_lat, approx_lng" in public_job_viewport_index_migration_sql
            and "idx_job_photos_public_job" in public_job_photo_index_migration_sql
            and "ON job_photos(job_id, is_hidden)" in public_job_photo_index_migration_sql
            and "PRAGMA optimize" in public_job_photo_index_migration_sql,
            errors,
            "D1 public project indexes are missing or incomplete.",
            checks,
            "D1 public project map and visible-photo queries are indexed",
        )
    if thread_nav_indexes_migration_sql:
        require(
            all(
                marker in thread_nav_indexes_migration_sql
                for marker in (
                    "idx_threads_client",
                    "ON threads(client_id, id)",
                    "idx_threads_contractor",
                    "ON threads(contractor_id, id)",
                    "PRAGMA optimize",
                )
            ),
            errors,
            "D1 unread-navigation indexes are missing or incomplete.",
            checks,
            "D1 unread-navigation queries are indexed for both marketplace roles",
        )
    if contractor_choice_photo_index_migration_sql:
        require(
            all(
                marker in contractor_choice_photo_index_migration_sql
                for marker in (
                    "idx_contractor_photos_public_contractor",
                    "ON contractor_photos(contractor_id, is_hidden, created_at DESC, id DESC)",
                    "PRAGMA optimize",
                )
            ),
            errors,
            "D1 contractor-choice photo index is missing or incomplete.",
            checks,
            "D1 contractor comparison photo lookup is indexed",
        )
    if single_approved_match_migration_sql:
        require(
            all(
                marker in single_approved_match_migration_sql
                for marker in (
                    "idx_match_requests_one_approved_per_job",
                    "ON match_requests(job_id)",
                    "WHERE status = 'approved'",
                    "PRAGMA optimize",
                )
            ),
            errors,
            "D1 single-approved-match index is missing or incomplete.",
            checks,
            "D1 enforces one approved contractor per project",
        )
    if project_license_preference_migration_sql:
        require(
            project_license_preference_migration_sql.count(
                "ADD COLUMN license_preference INTEGER NOT NULL DEFAULT 0"
            )
            == 3
            and project_license_preference_migration_sql.count(
                "CHECK (license_preference IN (0, 1))"
            )
            == 3,
            errors,
            "D1 project license-preference migration is missing a compatible table or boolean check.",
            checks,
            "D1 stores the neutral license-record preference on projects, drafts, and templates",
        )
    if idempotency_migration_sql:
        require(
            all(
                marker in idempotency_migration_sql
                for marker in (
                    "CREATE TABLE IF NOT EXISTS idempotency_requests",
                    "CHECK (length(key_hash) = 64)",
                    "UNIQUE(actor_id, action, key_hash)",
                    "idx_idempotency_requests_expiry",
                )
            )
            and all(
                forbidden not in idempotency_migration_sql.lower()
                for forbidden in (
                    "email",
                    "address",
                    "zip_code",
                    "phone",
                    "description",
                    "message_body",
                    "report_reason",
                    "stored_path",
                )
            ),
            errors,
            "D1 idempotency migration is incomplete or stores marketplace/contact content.",
            checks,
            "D1 idempotency records store hashed request keys and generic references only",
        )

    if manifest:
        expected_sha = hashlib.sha256(migration_sql.encode("utf-8")).hexdigest() if migration_sql else ""
        actual_sha = (
            manifest.get("cloudflare_targets", {})
            .get("database", {})
            .get("migration_sha256")
        )
        require(
            bool(expected_sha and actual_sha == expected_sha),
            errors,
            "Manifest migration_sha256 does not match the checked-in D1 migration.",
            checks,
            "Manifest D1 migration hash matches",
        )
        expected_chain_sha = release_module.migration_chain_sha256(migrations_dir)
        actual_chain_sha = (
            manifest.get("cloudflare_targets", {})
            .get("database", {})
            .get("migration_chain_sha256")
        )
        require(
            bool(expected_chain_sha and actual_chain_sha == expected_chain_sha),
            errors,
            "Manifest migration_chain_sha256 does not match the checked-in D1 chain.",
            checks,
            "Manifest D1 migration-chain hash matches",
        )
        require(
            manifest == generated_manifest,
            errors,
            "Cloudflare manifest is stale. Run python scripts\\prepare_cloudflare_release.py.",
            checks,
            "Cloudflare manifest matches release generator",
        )
        require(
            manifest.get("domain") == "workdoe.com",
            errors,
            "Cloudflare manifest domain must be workdoe.com.",
            checks,
            "Manifest uses workdoe.com",
        )

    if wrangler:
        require(
            wrangler == generated_wrangler,
            errors,
            "Wrangler config is stale. Run python scripts\\prepare_cloudflare_release.py.",
            checks,
            "Wrangler config matches release generator",
        )
        require(
            "python_workers" in set(wrangler.get("compatibility_flags", [])),
            errors,
            "Wrangler config must include the python_workers compatibility flag.",
            checks,
            "Wrangler enables Python Workers",
        )
        require(
            "disable_python_external_sdk"
            in set(wrangler.get("compatibility_flags", [])),
            errors,
            (
                "Wrangler config must use the bundled Python Workers SDK until "
                "Workdoe adopts the pywrangler package toolchain."
            ),
            checks,
            "Wrangler uses the bundled Python Workers SDK",
        )
        require(
            not wrangler.get("routes"),
            errors,
            "Routine Wrangler deploys must not mutate the preconfigured Workdoe custom domains.",
            checks,
            "Wrangler preserves preconfigured Workdoe custom domains",
        )
        d1_binding = (wrangler.get("d1_databases") or [{}])[0]
        require(
            d1_binding.get("binding") == "DB" and d1_binding.get("migrations_dir") == "d1/migrations",
            errors,
            "Wrangler D1 binding must be DB with migrations_dir d1/migrations.",
            checks,
            "Wrangler D1 binding is configured",
        )
        for id_field in ("database_id", "preview_database_id"):
            if d1_binding.get(id_field) == ZERO_UUID:
                message = f"Wrangler D1 {id_field} is still the placeholder UUID."
                if strict_production:
                    errors.append(message)
                else:
                    warnings.append(message)
        r2_binding = (wrangler.get("r2_buckets") or [{}])[0]
        require(
            r2_binding.get("binding") == "MEDIA" and r2_binding.get("bucket_name") == "workdoe-media",
            errors,
            "Wrangler R2 binding must be MEDIA for workdoe-media.",
            checks,
            "Wrangler R2 media bucket is configured",
        )
        require(
            wrangler.get("images") == {"binding": "IMAGES"},
            errors,
            "Wrangler Images binding must be configured as IMAGES.",
            checks,
            "Wrangler Cloudflare Images sanitizer binding is configured",
        )
        require(
            wrangler.get("ratelimits") == REQUIRED_RATE_LIMIT_BINDINGS,
            errors,
            "Wrangler must configure the authenticated WRITE_RATE_LIMITER binding.",
            checks,
            "Wrangler authenticated write rate limiter is configured",
        )
        producer_map = {
            producer.get("binding"): producer.get("queue")
            for producer in wrangler.get("queues", {}).get("producers", [])
        }
        require(
            producer_map == REQUIRED_QUEUE_BINDINGS,
            errors,
            "Wrangler queue producers must bind EMAIL_QUEUE and MEDIA_QUEUE.",
            checks,
            "Wrangler queue producers are configured",
        )
        crons = set(wrangler.get("triggers", {}).get("crons", []))
        require(
            crons == REQUIRED_CRONS,
            errors,
            "Wrangler cron triggers do not match the Workdoe automation plan.",
            checks,
            "Wrangler cron triggers match automation plan",
        )
        require(
            wrangler.get("vars", {}).get("WORKDOE_AUTH_PROVIDER")
            == "clerk"
            and wrangler.get("vars", {}).get("WORKDOE_LOGIN_MODE")
            == "same_domain_email_code",
            errors,
            "Wrangler vars must keep Clerk same-domain email-code mode.",
            checks,
            "Wrangler keeps Clerk same-domain OTP mode",
        )
        require(
            wrangler.get("vars", {}).get("WORKDOE_ENFORCE_SERVICE_ACTIVATION") == "true",
            errors,
            "Wrangler must enforce reviewed service-zone launch gates.",
            checks,
            "Wrangler enforces service-zone launch gates",
        )
        require(
            wrangler.get("vars", {}).get("WORKDOE_EMAIL_FROM") == "no-reply@workdoe.com"
            and wrangler.get("vars", {}).get("WORKDOE_ADMIN_EMAIL") == "admin@workdoe.com",
            errors,
            "Wrangler vars must include Workdoe email sender and admin digest recipient.",
            checks,
            "Wrangler configures Workdoe transactional email vars",
        )
        send_bindings = wrangler.get("send_email", [])
        require(
            send_bindings == [
                {
                    "name": "EMAIL",
                    "allowed_sender_addresses": ["no-reply@workdoe.com"],
                    "remote": True,
                }
            ],
            errors,
            "Wrangler send_email binding must restrict EMAIL to no-reply@workdoe.com.",
            checks,
            "Wrangler restricts Cloudflare Email sender binding",
        )
        required_secrets = set(wrangler.get("secrets", {}).get("required", []))
        require(
            required_secrets == REQUIRED_WORKER_SECRETS,
            errors,
            "Wrangler secrets.required must declare the Clerk, Workdoe, and Turnstile secrets.",
            checks,
            "Wrangler requires Clerk, Workdoe, and Turnstile secrets",
        )
        leaked_secret_vars = sorted(required_secrets & set(wrangler.get("vars", {})))
        require(
            not leaked_secret_vars,
            errors,
            "Wrangler vars must not contain required secret names: "
            + ", ".join(leaked_secret_vars),
            checks,
            "Wrangler keeps required secret names out of vars",
        )
        require(
            wrangler.get("observability", {}).get("enabled") is True,
            errors,
            "Wrangler observability must be enabled.",
            checks,
            "Wrangler observability is enabled",
        )
        asset_dir = wrangler.get("assets", {}).get("directory")
        if asset_dir:
            asset_path = (wrangler_path.parent / asset_dir).resolve()
            require(
                asset_path == static_path.resolve() and asset_path.exists(),
                errors,
                "Wrangler ASSETS directory must resolve to workdoe/static.",
                checks,
                "Wrangler static assets path exists",
            )
        require(
            wrangler.get("assets", {}).get("run_worker_first") is False,
            errors,
            "Wrangler must serve matching static assets directly from Cloudflare's asset layer.",
            checks,
            "Wrangler bypasses the Worker for matching static assets",
        )

    if dev_vars:
        require(
            dev_vars == generated_dev_vars,
            errors,
            ".dev.vars.example is stale. Run python scripts\\prepare_cloudflare_release.py.",
            checks,
            ".dev.vars.example matches release generator",
        )
        missing_env = sorted(
            env_name
            for env_name in REQUIRED_DEV_ENV | REQUIRED_PUBLIC_ENV
            if f"{env_name}=" not in dev_vars
        )
        require(
            not missing_env,
            errors,
            ".dev.vars.example is missing required env names: " + ", ".join(missing_env),
            checks,
            ".dev.vars.example lists Clerk, Turnstile, and app secrets",
        )

    compile_python(worker_path, errors, checks, "Cloudflare Worker Python compiles")
    compile_python(app_shell_path, errors, checks, "Cloudflare authenticated app shell helper compiles")
    compile_python(
        service_activation_path,
        errors,
        checks,
        "Cloudflare service-zone activation helper compiles",
    )
    compile_python(clerk_onboarding_path, errors, checks, "Clerk onboarding helper compiles")
    compile_python(clerk_sessions_path, errors, checks, "Clerk session verification helper compiles")
    compile_python(email_code_auth_path, errors, checks, "Cloudflare email-code auth helper compiles")
    compile_python(clerk_proxy_path, errors, checks, "Clerk Frontend API proxy helper compiles")
    compile_python(email_payloads_path, errors, checks, "Cloudflare email payload helper compiles")
    compile_python(admin_moderation_path, errors, checks, "Cloudflare admin moderation helper compiles")
    compile_python(contractor_profiles_path, errors, checks, "Cloudflare contractor profile helper compiles")
    compile_python(
        contractor_reputation_path,
        errors,
        checks,
        "Cloudflare contractor reputation helper compiles",
    )
    compile_python(contractor_credentials_path, errors, checks, "Cloudflare contractor credential helper compiles")
    compile_python(contractor_preferences_path, errors, checks, "Cloudflare contractor preference helper compiles")
    compile_python(client_project_templates_path, errors, checks, "Cloudflare consumer project-template helper compiles")
    compile_python(
        contractor_proposal_templates_path,
        errors,
        checks,
        "Cloudflare contractor proposal-template helper compiles",
    )
    compile_python(client_profiles_path, errors, checks, "Cloudflare consumer profile helper compiles")
    compile_python(contractor_public_profiles_path, errors, checks, "Cloudflare public contractor profile helper compiles")
    compile_python(contractor_leads_path, errors, checks, "Cloudflare contractor leads helper compiles")
    compile_python(contractor_bids_path, errors, checks, "Cloudflare contractor bids helper compiles")
    compile_python(client_jobs_path, errors, checks, "Cloudflare client jobs helper compiles")
    compile_python(client_requests_path, errors, checks, "Cloudflare client requests helper compiles")
    compile_python(
        bid_comparison_path,
        errors,
        checks,
        "Cloudflare received-order bid comparison helper compiles",
    )
    compile_python(
        repeat_provider_invitations_path,
        errors,
        checks,
        "Cloudflare repeat-provider invitation helper compiles",
    )
    compile_python(entry_shell_path, errors, checks, "Cloudflare same-domain entry shell helper compiles")
    compile_python(public_jobs_path, errors, checks, "Cloudflare public jobs helper compiles")
    compile_python(
        public_job_query_path,
        errors,
        checks,
        "Cloudflare public job query helper compiles",
    )
    compile_python(job_details_path, errors, checks, "Cloudflare job detail helper compiles")
    compile_python(job_status_path, errors, checks, "Cloudflare job status helper compiles")
    compile_python(job_posts_path, errors, checks, "Cloudflare job posting helper compiles")
    compile_python(service_taxonomy_path, errors, checks, "Cloudflare service taxonomy helper compiles")
    compile_python(service_scope_path, errors, checks, "Cloudflare service scope helper compiles")
    compile_python(
        project_readiness_path,
        errors,
        checks,
        "Cloudflare project brief readiness helper compiles",
    )
    compile_python(
        pilot_metrics_path,
        errors,
        checks,
        "Cloudflare service-zone pilot metrics helper compiles",
    )
    compile_python(market_fit_path, errors, checks, "Cloudflare contractor market-fit helper compiles")
    compile_python(job_drafts_path, errors, checks, "Cloudflare project draft helper compiles")
    compile_python(turnstile_path, errors, checks, "Cloudflare Turnstile helper compiles")
    compile_python(match_requests_path, errors, checks, "Cloudflare match request helper compiles")
    compile_python(match_decisions_path, errors, checks, "Cloudflare match decision helper compiles")
    compile_python(match_completions_path, errors, checks, "Cloudflare match completion helper compiles")
    compile_python(match_reviews_path, errors, checks, "Cloudflare match review helper compiles")
    compile_python(message_threads_path, errors, checks, "Cloudflare message thread helper compiles")
    compile_python(moderation_reports_path, errors, checks, "Cloudflare moderation report helper compiles")
    compile_python(media_access_path, errors, checks, "Cloudflare private media helper compiles")
    compile_python(media_uploads_path, errors, checks, "Cloudflare private media upload helper compiles")
    compile_python(request_security_path, errors, checks, "Cloudflare same-origin request helper compiles")
    compile_python(idempotency_path, errors, checks, "Cloudflare idempotency helper compiles")
    compile_python(launch_plan_path, errors, checks, "Cloudflare launch plan helper compiles")
    compile_python(launch_status_path, errors, checks, "Cloudflare launch status helper compiles")
    compile_python(wrangler_helper_path, errors, checks, "Cloudflare Wrangler resolver helper compiles")
    compile_python(clerk_proxy_proof_path, errors, checks, "Cloudflare Clerk proxy proof helper compiles")
    compile_python(secret_evidence_path, errors, checks, "Cloudflare secret evidence helper compiles")
    compile_python(release_evidence_path, errors, checks, "Cloudflare release evidence helper compiles")
    compile_python(d1_id_apply_path, errors, checks, "Cloudflare D1 ID apply helper compiles")
    compile_python(resource_bootstrap_path, errors, checks, "Cloudflare resource bootstrap helper compiles")
    compile_python(production_deploy_path, errors, checks, "Cloudflare production deploy helper compiles")
    compile_python(github_release_status_path, errors, checks, "GitHub release status helper compiles")
    compile_python(github_deploy_dispatch_path, errors, checks, "GitHub deploy dispatch helper compiles")
    compile_python(workdoe_launch_doctor_path, errors, checks, "Workdoe launch doctor helper compiles")
    compile_python(workdoe_launch_handoff_path, errors, checks, "Workdoe launch handoff helper compiles")
    compile_python(workdoe_dns_diagnostic_path, errors, checks, "Workdoe DNS diagnostic helper compiles")
    compile_python(workdoe_production_smoke_path, errors, checks, "Workdoe production smoke helper compiles")

    worker_source = read_text(worker_path, errors)
    app_shell_source = read_text(app_shell_path, errors)
    clerk_onboarding_source = read_text(clerk_onboarding_path, errors)
    clerk_sessions_source = read_text(clerk_sessions_path, errors)
    email_code_auth_source = read_text(email_code_auth_path, errors)
    clerk_proxy_source = read_text(clerk_proxy_path, errors)
    email_payloads_source = read_text(email_payloads_path, errors)
    admin_moderation_source = read_text(admin_moderation_path, errors)
    contractor_profiles_source = read_text(contractor_profiles_path, errors)
    contractor_reputation_source = read_text(contractor_reputation_path, errors)
    local_contractor_reputation_source = read_text(
        local_contractor_reputation_path,
        errors,
    )
    contractor_credentials_source = read_text(contractor_credentials_path, errors)
    contractor_preferences_source = read_text(contractor_preferences_path, errors)
    client_project_templates_source = read_text(client_project_templates_path, errors)
    contractor_proposal_templates_source = read_text(
        contractor_proposal_templates_path,
        errors,
    )
    client_profiles_source = read_text(client_profiles_path, errors)
    contractor_public_profiles_source = read_text(contractor_public_profiles_path, errors)
    contractor_leads_source = read_text(contractor_leads_path, errors)
    contractor_bids_source = read_text(contractor_bids_path, errors)
    client_jobs_source = read_text(client_jobs_path, errors)
    client_requests_source = read_text(client_requests_path, errors)
    entry_shell_source = read_text(entry_shell_path, errors)
    public_jobs_source = read_text(public_jobs_path, errors)
    public_job_query_source = read_text(public_job_query_path, errors)
    job_details_source = read_text(job_details_path, errors)
    job_status_source = read_text(job_status_path, errors)
    job_posts_source = read_text(job_posts_path, errors)
    job_drafts_source = read_text(job_drafts_path, errors)
    turnstile_source = read_text(turnstile_path, errors)
    match_requests_source = read_text(match_requests_path, errors)
    match_decisions_source = read_text(match_decisions_path, errors)
    match_completions_source = read_text(match_completions_path, errors)
    match_reviews_source = read_text(match_reviews_path, errors)
    message_threads_source = read_text(message_threads_path, errors)
    moderation_reports_source = read_text(moderation_reports_path, errors)
    media_access_source = read_text(media_access_path, errors)
    media_uploads_source = read_text(media_uploads_path, errors)
    request_security_source = read_text(request_security_path, errors)
    idempotency_source = read_text(idempotency_path, errors)
    d1_id_apply_source = read_text(d1_id_apply_path, errors)
    clerk_proxy_proof_source = read_text(clerk_proxy_proof_path, errors)
    secret_evidence_source = read_text(secret_evidence_path, errors)
    release_evidence_source = read_text(release_evidence_path, errors)
    wrangler_helper_source = read_text(wrangler_helper_path, errors)
    resource_bootstrap_source = read_text(resource_bootstrap_path, errors)
    production_deploy_source = read_text(production_deploy_path, errors)
    worker_actions_source = read_text(worker_actions_path, errors)
    project_composer_source = read_text(project_composer_path, errors)
    project_readiness_source = read_text(project_readiness_path, errors)
    pilot_metrics_source = read_text(pilot_metrics_path, errors)
    bid_comparison_source = read_text(bid_comparison_path, errors)
    clerk_entry_source = read_text(clerk_entry_path, errors)
    clerk_account_source = read_text(clerk_account_path, errors)
    email_code_entry_source = read_text(email_code_entry_path, errors)
    if contractor_reputation_source and local_contractor_reputation_source:
        require(
            contractor_reputation_source == local_contractor_reputation_source,
            errors,
            "Flask and Worker contractor reputation projections must remain byte-identical.",
            checks,
            "Flask and Worker contractor reputation projections match",
        )
        require(
            all(
                marker in contractor_reputation_source
                for marker in (
                    "COMPLETION_POINTS = 100",
                    '"ranking_effect": "none"',
                    "verified_completions",
                    "source_checked_licenses",
                )
            ),
            errors,
            "Contractor reputation must remain completion-derived and ranking-neutral.",
            checks,
            "Contractor reputation is deterministic and ranking-neutral",
        )
    if idempotency_source and worker_source and worker_actions_source:
        require(
            all(
                marker in idempotency_source
                for marker in (
                    "hashlib.sha256",
                    "IDEMPOTENCY_KEY_MAX_LENGTH = 128",
                    "IDEMPOTENCY_RESOURCE_TYPES",
                )
            )
            and all(
                marker in worker_source
                for marker in (
                    "begin_idempotent_request",
                    "complete_idempotent_request",
                    '"job-create"',
                    'idempotency_action("message-create", thread_id)',
                    'idempotency_action(f"media-upload-{scope}", owner_id)',
                )
            )
            and all(
                marker in worker_actions_source
                for marker in (
                    "window.crypto.randomUUID",
                    '"Idempotency-Key"',
                    'uploadData.append("idempotency_key"',
                )
            ),
            errors,
            "Core marketplace creates must use hashed durable idempotency keys from the browser through D1.",
            checks,
            "Cloudflare project, message, report, and media creates are idempotent",
        )
    if public_jobs_source and contractor_leads_source and contractor_preferences_source:
        require(
            all(
                marker in source
                for source in (public_jobs_source, contractor_leads_source)
                for marker in ('"family"', "GROUP_BY_SLUG", '"service_group_slug"')
            )
            and all(
                marker in contractor_preferences_source
                for marker in (
                    '"saved_service_group_slug"',
                    '"saved_family_label"',
                )
            ),
            errors,
            "Discovery family filtering must use validated canonical service-group slugs in public, contractor, and saved-view contracts.",
            checks,
            "Discovery family filters reuse the canonical six-family taxonomy",
        )
    if project_readiness_source:
        missing_readiness_markers = [
            marker
            for marker in (
                "PROJECT_BRIEF_SIGNAL_TOTAL = 6",
                "MIN_SCOPE_ANSWER_COUNT = 2",
                '"budget_or_photo"',
            )
            if marker not in project_readiness_source
        ]
        forbidden_readiness_markers = [
            marker
            for marker in ("email", "exact_address", "phone", "fit_score")
            if marker in project_readiness_source.lower()
        ]
        require(
            not missing_readiness_markers and not forbidden_readiness_markers,
            errors,
            "Project brief readiness must remain a six-signal, non-identity check.",
            checks,
            "Project brief readiness is deterministic and excludes identity/ranking fields",
        )
    if pilot_metrics_source:
        missing_pilot_metrics_markers = [
            marker
            for marker in (
                "pilot_cell_metrics",
                "service_zone_slug",
                "qualified_match_rate",
                "current_eligible_contractors",
                "first_bid_minutes",
                "median_first_bid_minutes",
                "no_match_or_cancelled_projects",
                "open_report_projects",
            )
            if marker not in pilot_metrics_source
        ]
        forbidden_pilot_metrics_markers = [
            marker
            for marker in (
                "email",
                "exact_address",
                "phone",
                "client_id",
                "close_note",
                "report_reason",
            )
            if marker in pilot_metrics_source.lower()
        ]
        require(
            not missing_pilot_metrics_markers and not forbidden_pilot_metrics_markers,
            errors,
            "Pilot metrics must remain aggregate service-zone-week operations only.",
            checks,
            "Pilot metrics cover response, closure, and report health without private fields",
        )
    if bid_comparison_source:
        missing_bid_comparison_markers = [
            marker
            for marker in (
                "MAX_COMPARISON_OFFERS = 4",
                '"Received order"',
                '"provider_facts"',
                '"source_checked_credential_count"',
                '"verified_work_count"',
            )
            if marker not in bid_comparison_source
        ]
        forbidden_bid_comparison_markers = [
            marker
            for marker in (
                "email",
                "phone",
                "exact_address",
                "website",
                "license_number",
                "fit_score",
            )
            if marker in bid_comparison_source.lower()
        ]
        require(
            not missing_bid_comparison_markers
            and not forbidden_bid_comparison_markers,
            errors,
            "Bid comparison must remain received-order facts without contact, credential identifiers, or scores.",
            checks,
            "Bid comparison is bounded, explainable, and excludes identity/contact/ranking fields",
        )
    if worker_source:
        missing_worker_markers = [
            marker
            for marker in (
                "verify_svix_signature",
                "sync_linked_clerk_user",
                "no-linked-workdoe-user",
                "email-conflict",
            )
            if marker not in worker_source
        ]
        require(
            not missing_worker_markers,
            errors,
            "Cloudflare Worker is missing Clerk sync markers: "
            + ", ".join(missing_worker_markers),
            checks,
            "Cloudflare Worker verifies and syncs linked Clerk users",
        )
        missing_webhook_request_markers = [
            marker
            for marker in (
                "MAX_CLERK_WEBHOOK_BODY_BYTES",
                "Webhook requests must include Content-Length.",
                "Webhook request body is too large.",
            )
            if marker not in worker_source
        ]
        require(
            not missing_webhook_request_markers,
            errors,
            "Cloudflare Worker is missing bounded Clerk webhook request controls: "
            + ", ".join(missing_webhook_request_markers),
            checks,
            "Cloudflare Worker bounds signed Clerk webhook payloads",
        )
        combined_request_security_source = f"{worker_source}\n{request_security_source}\n{worker_actions_source}\n{clerk_entry_source}\n{email_code_entry_source}"
        missing_request_security_markers = [
            marker
            for marker in (
                "same_origin_api_write_allowed",
                "WORKDOE_REQUEST_HEADER",
                '"X-Workdoe-Request": "same-origin"',
                "Request body must use application/json.",
                "Request body must use form encoding.",
                "Request body must include Content-Length.",
                "async def request_form_data",
                "max_bytes=MAX_JOB_POST_BODY_BYTES",
                "Image uploads must include Content-Length.",
                'if request.method != "POST":',
            )
            if marker not in combined_request_security_source
        ]
        require(
            not missing_request_security_markers,
            errors,
            "Cloudflare Worker is missing same-origin API write protections: "
            + ", ".join(missing_request_security_markers),
            checks,
            "Cloudflare Worker requires same-origin markers for API writes",
        )
        missing_write_rate_limit_markers = [
            marker
            for marker in (
                "authenticated_write_rate_limit_required",
                "authenticated_write_rate_limit_key",
                "WRITE_RATE_LIMITER",
                "limiter.limit",
                "Retry-After",
                "status=429",
                "write_rate_limiter",
            )
            if marker not in combined_request_security_source
        ]
        require(
            not missing_write_rate_limit_markers,
            errors,
            "Cloudflare Worker is missing authenticated write rate-limit markers: "
            + ", ".join(missing_write_rate_limit_markers),
            checks,
            "Cloudflare Worker rate-limits authenticated writes by user ID",
        )
        combined_native_auth_source = worker_source + "\n" + email_code_auth_source
        missing_native_auth_markers = [
            marker
            for marker in (
                "request_auth_code",
                "verify_auth_code",
                "MAX_CODE_ATTEMPTS",
                "login_code_consume_result",
                "AND used_at IS NULL",
                "AND expires_at >= ?",
                "AND attempt_count < ?",
                "d1_change_count",
                "ensure_role_profile",
                "INSERT OR IGNORE INTO users",
                "HttpOnly; Secure; SameSite=Lax",
            )
            if marker not in combined_native_auth_source
        ]
        require(
            not missing_native_auth_markers,
            errors,
            "Cloudflare Worker is missing atomic email-code controls: "
            + ", ".join(missing_native_auth_markers),
            checks,
            "Cloudflare native email codes are rate-limited and consumed atomically",
        )
        combined_session_source = worker_source + "\n" + clerk_sessions_source
        missing_session_markers = [
            marker
            for marker in (
                "/api/auth/session",
                "extract_clerk_session_token",
                "verify_clerk_session_token",
                "CLERK_JWT_KEY",
                "authorized_parties",
                "auth_provider = 'clerk'",
                "external_subject = ?",
                "onboarding_required",
                "Web Crypto",
                "Session token not verified.",
            )
            if marker not in combined_session_source
        ]
        require(
            not missing_session_markers,
            errors,
            "Cloudflare Worker is missing Clerk session auth markers: "
            + ", ".join(missing_session_markers),
            checks,
            "Cloudflare Worker maps verified Clerk sessions to Workdoe users",
        )
        combined_onboarding_source = worker_source + "\n" + clerk_onboarding_source
        missing_onboarding_markers = [
            marker
            for marker in (
                "/api/auth/onboard",
                "onboarding_payload",
                "A verified Clerk email claim is required.",
                "Role must be client or contractor.",
                "INSERT OR IGNORE INTO users",
                "auth_provider, external_subject",
                "INSERT OR IGNORE INTO client_profiles",
                "INSERT OR IGNORE INTO contractor_profiles",
                "A Workdoe account already uses this email.",
                "ensure_role_profile",
                "clerk-onboarding-linked",
            )
            if marker not in combined_onboarding_source
        ]
        require(
            not missing_onboarding_markers,
            errors,
            "Cloudflare Worker is missing Clerk onboarding markers: "
            + ", ".join(missing_onboarding_markers),
            checks,
            "Cloudflare Worker creates role-owned Workdoe users after Clerk verification",
        )
        combined_contractor_profile_source = worker_source + "\n" + contractor_profiles_source
        missing_contractor_profile_markers = [
            marker
            for marker in (
                "/api/contractor/profile",
                "contractor_profile_api",
                "contractor_profile_payload",
                "can_update_contractor_profile",
                "contractor_profile_readiness",
                "upsert_contractor_profile",
                "ON CONFLICT(user_id) DO UPDATE",
                "Use a public HTTPS website such as https://example.com.",
                "normalized_profile_website",
                "contractor-profile-updated",
                "Only active contractor accounts can update profiles.",
            )
            if marker not in combined_contractor_profile_source
        ]
        require(
            not missing_contractor_profile_markers,
            errors,
            "Cloudflare Worker is missing contractor profile API markers: "
            + ", ".join(missing_contractor_profile_markers),
            checks,
            "Cloudflare Worker lets contractors update their profiles",
        )
        combined_credential_source = (
            worker_source
            + "\n"
            + contractor_credentials_source
            + "\n"
            + admin_moderation_source
            + "\n"
            + contractor_public_profiles_source
            + "\n"
            + app_shell_source
        )
        missing_credential_markers = [
            marker
            for marker in (
                "/api/contractor/credentials",
                "contractor_credentials_api",
                "contractor_credential_claim_payload",
                "Only active contractor accounts can manage credential claims.",
                "admin-credential-review",
                "/api/admin/credentials/",
                "public_credential_responses",
                "Source-checked and expired records remain in the audit history.",
            )
            if marker not in combined_credential_source
        ]
        require(
            not missing_credential_markers,
            errors,
            "Cloudflare Worker is missing contractor credential controls: "
            + ", ".join(missing_credential_markers),
            checks,
            "Cloudflare Worker publishes only reviewed contractor credentials",
        )
        combined_preference_source = (
            worker_source
            + "\n"
            + contractor_preferences_source
            + "\n"
            + contractor_public_profiles_source
            + "\n"
            + app_shell_source
        )
        missing_preference_markers = [
            marker
            for marker in (
                "/api/contractor/preferences/availability",
                "/api/contractor/preferences/lead-view",
                "contractor_preferences_api",
                "Only active contractor accounts can update work preferences.",
                "saved_lead_view_payload",
                "availability_response",
                "self_reported",
            )
            if marker not in combined_preference_source
        ]
        require(
            not missing_preference_markers,
            errors,
            "Cloudflare Worker is missing contractor preference controls: "
            + ", ".join(missing_preference_markers),
            checks,
            "Cloudflare Worker keeps saved lead views owner-only",
        )
        combined_template_source = (
            worker_source
            + "\n"
            + client_project_templates_source
            + "\n"
            + app_shell_source
        )
        missing_template_markers = [
            marker
            for marker in (
                "/api/client/templates",
                "client_project_templates_api",
                "WHERE jobs.id = ? AND jobs.client_id = ?",
                "DELETE FROM client_project_templates WHERE id = ? AND client_id = ?",
                "project_template_job_form",
                "Location, date, photos, bids, and messages are never copied.",
            )
            if marker not in combined_template_source
        ]
        require(
            not missing_template_markers,
            errors,
            "Cloudflare Worker is missing private consumer project-template controls: "
            + ", ".join(missing_template_markers),
            checks,
            "Cloudflare Worker keeps reusable project scope owner-only",
        )
        combined_proposal_template_source = (
            worker_source
            + "\n"
            + contractor_proposal_templates_source
            + "\n"
            + app_shell_source
        )
        missing_proposal_template_markers = [
            marker
            for marker in (
                "/api/contractor/proposal-templates",
                "contractor_proposal_templates_api",
                "FROM match_requests",
                "WHERE id = ? AND contractor_id = ?",
                "DELETE FROM contractor_proposal_templates",
                "proposal_template_bid_form",
                '\"price_range\": \"\"',
                "fresh price",
            )
            if marker not in combined_proposal_template_source
        ]
        require(
            not missing_proposal_template_markers,
            errors,
            "Cloudflare Worker is missing owner-only contractor proposal-template controls: "
            + ", ".join(missing_proposal_template_markers),
            checks,
            "Contractor proposal templates stay owner-only and require a fresh price",
        )
        combined_client_profile_source = worker_source + "\n" + client_profiles_source
        missing_client_profile_markers = [
            marker
            for marker in (
                "/api/client/profile",
                "client_profile_api",
                "can_update_client_profile",
                "upsert_client_profile",
                "/api/client/locations",
                "client_saved_locations_api",
                "WHERE id = ? AND client_id = ?",
                "SAVED_LOCATION_LIMIT",
                "client_profiles.notification_preference",
            )
            if marker not in combined_client_profile_source
        ]
        require(
            not missing_client_profile_markers,
            errors,
            "Cloudflare Worker is missing consumer profile API markers: "
            + ", ".join(missing_client_profile_markers),
            checks,
            "Cloudflare Worker protects consumer profiles and saved project areas",
        )
        combined_public_contractor_source = worker_source + "\n" + contractor_public_profiles_source
        missing_public_contractor_markers = [
            marker
            for marker in (
                "/api/contractors/",
                "public_contractor_profile",
                "parse_public_contractor_id",
                "can_view_public_contractor_profile",
                "can_view_contractor_website",
                "contractor_has_client_bid_relationship",
                "website_visible",
                "public_contractor_for_profile",
                "visible_contractor_profile_photos",
                "Clients approve a contractor's mini bid before a private Workdoe message thread opens.",
                "WHERE contractor_id = ?",
                "AND is_hidden = 0",
                "/media/contractors/",
                "Contractor profile not found.",
            )
            if marker not in combined_public_contractor_source
        ]
        require(
            not missing_public_contractor_markers,
            errors,
            "Cloudflare Worker is missing public contractor profile API markers: "
            + ", ".join(missing_public_contractor_markers),
            checks,
            "Cloudflare Worker exposes privacy-safe contractor profiles",
        )
        require(
            "original_filename" not in contractor_public_profiles_source,
            errors,
            "Public contractor profile payloads must not expose original upload filenames.",
            checks,
            "Cloudflare public contractor profiles redact upload filenames",
        )
        combined_contractor_leads_source = worker_source + "\n" + contractor_leads_source
        missing_contractor_lead_markers = [
            marker
            for marker in (
                "/api/contractor/leads",
                "contractor_leads",
                "contractor_leads_for_user",
                "contractor_leads_payload",
                "can_view_contractor_leads",
                "Only active contractor accounts can view leads.",
                "match_requests.contractor_id = ?",
                "jobs.status = 'open'",
                "request_status",
                "new_jobs",
                "sent_bids",
                "Approximate city or ZIP-level pins only until a client approves a match.",
            )
            if marker not in combined_contractor_leads_source
        ]
        require(
            not missing_contractor_lead_markers,
            errors,
            "Cloudflare Worker is missing contractor leads API markers: "
            + ", ".join(missing_contractor_lead_markers),
            checks,
            "Cloudflare Worker exposes signed-in contractor lead board data",
        )
        combined_contractor_bids_source = worker_source + "\n" + contractor_bids_source
        missing_contractor_bid_markers = [
            marker
            for marker in (
                "/api/contractor/bids",
                "contractor_bids",
                "contractor_bids_for_user",
                "contractor_bids_payload",
                "can_view_contractor_bids",
                "Only active contractor accounts can view mini bids.",
                "WHERE match_requests.contractor_id = ?",
                "pending_requests",
                "approved_requests",
                "rejected_requests",
                "thread_url",
                "row_cue",
            )
            if marker not in combined_contractor_bids_source
        ]
        require(
            not missing_contractor_bid_markers,
            errors,
            "Cloudflare Worker is missing contractor bids API markers: "
            + ", ".join(missing_contractor_bid_markers),
            checks,
            "Cloudflare Worker exposes contractor mini-bid dashboard data",
        )
        combined_completion_source = worker_source + "\n" + match_completions_source
        missing_completion_markers = [
            marker
            for marker in (
                "/api/match-requests/",
                "/complete",
                "confirm_match_completion",
                "validate_completion_confirmation",
                "Only match participants can confirm completion.",
                "Only an approved match can be completed.",
                "Close the project before confirming completion.",
                "INSERT OR IGNORE INTO match_completions",
                "match-completion-confirmed",
                "A project with completion confirmation cannot be reopened.",
            )
            if marker not in combined_completion_source
        ]
        require(
            not missing_completion_markers,
            errors,
            "Cloudflare Worker is missing match completion markers: "
            + ", ".join(missing_completion_markers),
            checks,
            "Cloudflare Worker verifies completion through both match participants",
        )
        combined_match_review_source = (
            worker_source + "\n" + match_reviews_source + "\n" + app_shell_source
        )
        missing_match_review_markers = [
            marker
            for marker in (
                "/api/match-requests/",
                "/review",
                "/api/reviews/",
                "create_match_review",
                "match_review_action",
                "validate_review_eligibility",
                "Both participants must confirm completion before leaving feedback.",
                "INSERT OR IGNORE INTO match_reviews",
                "INSERT OR IGNORE INTO match_review_reports",
                '"has_comment": bool(values["comment"])',
                'payload = {"reporter_role": row_value(user, "role")}',
                "Leave completed-work feedback",
                "Feedback does not create a star score or change marketplace rank.",
                "No star score or paid ranking is created.",
            )
            if marker not in combined_match_review_source
        ]
        require(
            not missing_match_review_markers,
            errors,
            "Cloudflare Worker is missing completed-work feedback markers: "
            + ", ".join(missing_match_review_markers),
            checks,
            "Cloudflare Worker gates structured feedback on verified completion",
        )
        combined_client_jobs_source = worker_source + "\n" + client_jobs_source
        missing_client_jobs_markers = [
            marker
            for marker in (
                "/api/client/jobs",
                "client_jobs",
                "client_jobs_for_user",
                "client_jobs_payload",
                "can_view_client_jobs",
                "Only active client accounts can view client jobs.",
                "WHERE jobs.client_id = ?",
                "pending_count",
                "approved_count",
                "rejected_count",
                "needs_review",
                "review_jobs",
            )
            if marker not in combined_client_jobs_source
        ]
        require(
            not missing_client_jobs_markers,
            errors,
            "Cloudflare Worker is missing client jobs API markers: "
            + ", ".join(missing_client_jobs_markers),
            checks,
            "Cloudflare Worker exposes client job dashboard data",
        )
        combined_client_requests_source = worker_source + "\n" + client_requests_source
        missing_client_request_markers = [
            marker
            for marker in (
                "/api/client/jobs/",
                "/requests",
                "client_job_requests",
                "client_requests_for_job",
                "client_job_requests_payload",
                "can_view_client_job_requests",
                "Only the owning client can review mini bids for this job.",
                "WHERE match_requests.job_id = ?",
                "pending",
                "approved",
                "rejected",
                "profile_url",
                "thread_url",
                "needs_review",
            )
            if marker not in combined_client_requests_source
        ]
        require(
            not missing_client_request_markers,
            errors,
            "Cloudflare Worker is missing client request review API markers: "
            + ", ".join(missing_client_request_markers),
            checks,
            "Cloudflare Worker exposes client mini-bid review data",
        )
        combined_email_source = worker_source + "\n" + email_payloads_source
        missing_email_markers = [
            marker
            for marker in (
                "build_email_message",
                "login-code",
                "password-reset",
                "contractor-new-lead",
                "contractor-lead-alert-fanout",
                "repeat-provider-invitation",
                "stale-match-reminder",
                "moderation-digest",
                "env.EMAIL.send",
                "email-message-sent",
                "email-message-invalid",
                "email-message-send-failed",
                "email_audit_metadata",
                "recipient_hash",
                "email_send_result_summary",
                "record_event_best_effort",
                "ack_message",
                "retry_message",
                "WORKDOE_EMAIL_FROM",
                "email_reminder_consent_at IS NOT NULL",
                "Manage bid reminder emails",
                "client/profile#bid-reminders",
                "lead_alert_consent_at IS NOT NULL",
                "contractor_service_capabilities",
                "contractor_service_zones",
                "Manage matching project emails",
                "leads#saved-lead-alerts",
            )
            if marker not in combined_email_source
        ]
        require(
            not missing_email_markers,
            errors,
            "Cloudflare Worker is missing Email Service queue markers: "
            + ", ".join(missing_email_markers),
            checks,
            "Cloudflare Worker sends and audits queued transactional emails",
        )
        email_consumer_start = worker_source.find(
            "async def process_email_queue_message"
        )
        email_consumer_end = worker_source.find(
            "\n\nasync def process_media_review_queue_message",
            email_consumer_start,
        )
        email_consumer_source = worker_source[email_consumer_start:email_consumer_end]
        email_send_index = email_consumer_source.find(
            "result = await env.EMAIL.send(email_message)"
        )
        email_ack_index = email_consumer_source.rfind("ack_message(message)")
        email_audit_index = email_consumer_source.find(
            '"email-message-sent"', email_ack_index
        )
        require(
            email_send_index >= 0
            and email_ack_index > email_send_index
            and email_audit_index > email_ack_index,
            errors,
            "A successfully delivered email must be acknowledged before its "
            "best-effort audit write.",
            checks,
            "Successful queued email delivery cannot be retried by an audit failure",
        )
        exposed_email_audit_markers = [
            marker
            for marker in (
                'payload={"body": body',
                '"to": email_message.get("to")',
                '"subject": email_message.get("subject")',
            )
            if marker in worker_source
        ]
        require(
            not exposed_email_audit_markers,
            errors,
            "Cloudflare Worker must not copy email queue bodies, recipients, or subjects "
            "into D1 automation events: " + ", ".join(exposed_email_audit_markers),
            checks,
            "Cloudflare Worker redacts transactional email audit metadata",
        )
        combined_entry_shell_source = (
            worker_source + "\n" + entry_shell_source + "\n" + clerk_entry_source + "\n" + clerk_proxy_source
        )
        missing_entry_shell_markers = [
            marker
            for marker in (
                "ENTRY_ROUTES",
                '"/login"',
                '"/start"',
                '"/post-project"',
                "/__clerk",
                "clerk_frontend_api_proxy",
                "clerk_proxy_request_plan",
                "Clerk-Proxy-Url",
                "Clerk-Secret-Key",
                "X-Forwarded-For",
                "CF-Connecting-IP",
                "entry_shell",
                "build_entry_shell_html",
                "entry_shell_jobs",
                "data-clerk-entry",
                "data-clerk-proxy-url",
                "CLERK_SIGNIN_MODE",
                "CLERK_START_MODE",
                "/api/auth/session",
                "/api/auth/onboard",
                "/api/jobs/open?",
                "ENTRY_JOB_LIMIT",
                "/map.js",
                "finishSignIn",
                "node.dataset.signUpUrl",
                "@clerk/ui@1/dist/ui.browser.js",
                "window.__internal_ClerkUICtor",
                "window.Clerk.mountSignIn",
                "withSignUp: true",
                "signUpForceRedirectUrl: returnUrl",
                "No password needed. Your one-time code arrives by email.",
                "Content-Security-Policy",
                "Cache-Control",
                "https://tile.openstreetmap.org",
            )
            if marker not in combined_entry_shell_source
        ]
        require(
            not missing_entry_shell_markers,
            errors,
            "Cloudflare Worker is missing same-domain entry shell markers: "
            + ", ".join(missing_entry_shell_markers),
            checks,
            "Cloudflare Worker serves same-domain Clerk entry pages",
        )
        legacy_clerk_entry_markers = [
            marker
            for marker in (
                "window.Clerk.client.signIn",
                "window.Clerk.client.signUp",
                "prepareFirstFactor",
                "attemptFirstFactor",
                "prepareEmailAddressVerification",
                "attemptEmailAddressVerification",
            )
            if marker in clerk_entry_source
        ]
        require(
            not legacy_clerk_entry_markers,
            errors,
            "Clerk entry flow still contains legacy custom authentication calls: "
            + ", ".join(legacy_clerk_entry_markers),
            checks,
            "Clerk entry uses maintained prebuilt components",
        )
        combined_app_shell_source = (
            worker_source
            + "\n"
            + app_shell_source
            + "\n"
            + entry_shell_source
            + "\n"
            + worker_actions_source
            + "\n"
            + clerk_account_source
        )
        missing_app_shell_markers = [
            marker
            for marker in (
                "is_app_shell_route",
                "app_shell",
                '"/dashboard"',
                '"/account"',
                '"/create-account"',
                '"/admin"',
                '"/client/dashboard"',
                '"/client/jobs/"',
                '"/contractor/profile"',
                '"/contractors/"',
                '"/contractor/dashboard"',
                '"/messages"',
                '"/messages/"',
                '"/leads"',
                '"/jobs/new"',
                "dashboard_path_for_user",
                "admin_dashboard_html",
                "admin_dashboard_payload",
                "/api/admin/reports/",
                "/api/admin/users/",
                "/api/admin/jobs/",
                "/api/admin/messages/",
                "client_dashboard_html",
                "client_job_detail_html",
                "client_request_inbox_html",
                "contractor_dashboard_html",
                "contractor_profile_html",
                "contractor_profile_page",
                "public_contractor_profile_html",
                "is_public_contractor_profile_route",
                "message_threads_html",
                "message_thread_detail_html",
                "message_threads_for_user",
                "message_threads_listing_payload",
                "lead_board_html",
                "job_form_html",
                "safety_page_html",
                "privacy_page_html",
                "terms_page_html",
                "public_robots_txt",
                "public_sitemap_xml",
                "public_security_txt",
                '"/privacy"',
                '"/terms"',
                '"/robots.txt"',
                '"/sitemap.xml"',
                '"/.well-known/security.txt"',
                "contractor_job_detail_html",
                "parse_app_client_job_id",
                "parse_app_client_job_edit_id",
                "parse_app_contractor_id",
                "parse_app_thread_id",
                "/api/match-requests/",
                "/api/messages/threads/",
                "/api/jobs/{job_id}/close",
                "/api/jobs/{job_id}/reopen",
                "/api/media/jobs/{job_id}/upload",
                "data-json-action",
                "data-file-action",
                "data-upload-after-json-template",
                "data-success-url-template",
                "worker-actions.js",
                "account_security_html",
                "clerk-account.js",
                "mountUserProfile",
                'routing: "hash"',
                "@clerk/ui@1/dist/ui.browser.js",
                "window.__internal_ClerkUICtor",
                "https://*.protect.clerk.com",
                "https://img.clerk.com",
                "worker-src 'self' blob:",
                "credentials: \"include\"",
                "new FormData(form)",
                "uploadFilesAfterJson",
                "value instanceof File",
                "uploadData.append(\"photo\"",
                "\"Content-Type\": \"application/json\"",
                "App pages accept GET only.",
            )
            if marker not in combined_app_shell_source
        ]
        require(
            not missing_app_shell_markers,
            errors,
            "Cloudflare Worker is missing authenticated app shell markers: "
            + ", ".join(missing_app_shell_markers),
            checks,
            "Cloudflare Worker serves authenticated post-login app pages",
        )
        public_trust_markers = (
            "privacy_page_html",
            "terms_page_html",
            "public_robots_txt",
            "public_sitemap_xml",
            "public_security_txt",
            '"/privacy"',
            '"/terms"',
            '"/robots.txt"',
            '"/sitemap.xml"',
            '"/.well-known/security.txt"',
            "admin@workdoe.com",
            "Workdoe is not an emergency service",
        )
        missing_public_trust_markers = [
            marker for marker in public_trust_markers if marker not in combined_app_shell_source
        ]
        require(
            not missing_public_trust_markers,
            errors,
            "Cloudflare Worker is missing public trust surfaces: "
            + ", ".join(missing_public_trust_markers),
            checks,
            "Cloudflare Worker serves public trust pages and discovery files",
        )
        missing_task_picker_markers = [
            marker
            for marker in (
                'class="service-option"',
                'class="service-select-control"',
                "data-service-option-group",
                "workdoe-message-provider-v1",
                "serviceChoices",
                "syncServiceChoices",
                "serviceSelect.value = choice.value",
            )
            if marker not in app_shell_source + "\n" + project_composer_source
        ]
        require(
            not missing_task_picker_markers,
            errors,
            "Cloudflare Worker is missing guided task-picker fallback markers: "
            + ", ".join(missing_task_picker_markers),
            checks,
            "Cloudflare Worker preserves visual task selection and native fallback",
        )
        combined_public_jobs_source = (
            worker_source + "\n" + public_jobs_source + "\n" + public_job_query_source
        )
        missing_public_jobs_markers = [
            marker
            for marker in (
                "/api/jobs/open",
                "public_open_jobs",
                "public_jobs_payload",
                "build_public_open_jobs_query(",
                "public_query_telemetry(",
                "next_cursor=next_cursor",
                "jobs.status = 'open'",
                "jobs.zip_code LIKE ?",
                "Approximate city or ZIP-level pins only.",
                "Cache-Control",
            )
            if marker not in combined_public_jobs_source
        ]
        require(
            not missing_public_jobs_markers,
            errors,
            "Cloudflare Worker is missing public jobs API markers: "
            + ", ".join(missing_public_jobs_markers),
            checks,
            "Cloudflare Worker exposes privacy-preserving public jobs API",
        )
        combined_job_detail_source = worker_source + "\n" + job_details_source
        missing_job_detail_markers = [
            marker
            for marker in (
                "job_detail",
                "parse_job_detail_id",
                "can_view_job_detail",
                "job_detail_payload",
                "zip_prefix",
                "contractor_request_for_job",
                "job_photos_for_detail",
                "Contractors see city/state and ZIP prefix only",
                "is_hidden = 0",
            )
            if marker not in combined_job_detail_source
        ]
        require(
            not missing_job_detail_markers,
            errors,
            "Cloudflare Worker is missing privacy-safe job detail API markers: "
            + ", ".join(missing_job_detail_markers),
            checks,
            "Cloudflare Worker exposes privacy-safe signed-in job details",
        )
        combined_job_status_source = worker_source + "\n" + job_status_source
        missing_job_status_markers = [
            marker
            for marker in (
                "update_job_status",
                "parse_job_status_path",
                "can_update_job_status",
                "job_status_response",
                "UPDATE jobs",
                "Hidden jobs cannot be changed by clients.",
                "job-closed",
                "job-reopened",
                "Only the owning client can update this job.",
            )
            if marker not in combined_job_status_source
        ]
        require(
            not missing_job_status_markers,
            errors,
            "Cloudflare Worker is missing client job status API markers: "
            + ", ".join(missing_job_status_markers),
            checks,
            "Cloudflare Worker lets clients close and reopen their jobs",
        )
        combined_job_post_source = worker_source + "\n" + job_posts_source + "\n" + turnstile_source
        missing_job_post_markers = [
            marker
            for marker in (
                "/api/jobs",
                "create_job",
                "job_post_payload",
                "verify_turnstile_for_request",
                "WORKDOE_TURNSTILE_SECRET_KEY",
                "TURNSTILE_VERIFY_URL",
                "turnstile_result_allowed",
                "Only client accounts can post jobs.",
                "INSERT INTO jobs",
                "job-created",
                "update_job",
                "parse_job_update_id",
                "can_update_job",
                'endswith("/update")',
                "UPDATE jobs",
                "job-updated",
                "Approximate city or ZIP-level pins only.",
            )
            if marker not in combined_job_post_source
        ]
        require(
            not missing_job_post_markers,
            errors,
            "Cloudflare Worker is missing job posting API markers: "
            + ", ".join(missing_job_post_markers),
            checks,
            "Cloudflare Worker creates and edits client jobs with Turnstile and owner checks",
        )
        combined_project_draft_source = (
            worker_source + "\n" + app_shell_source + "\n" + job_drafts_source
        )
        missing_project_draft_markers = [
            marker
            for marker in (
                'path == "/post-project"',
                "public_job_draft",
                "job_draft_for_request",
                "save_job_draft_record",
                "consume_job_draft_record",
                "job_draft_token_hash",
                "HttpOnly; Secure; SameSite=Lax",
                'action="/post-project"',
                'turnstile_html(site_key, "job-draft")',
                "Photos stay private and can be added after email verification.",
            )
            if marker not in combined_project_draft_source
        ]
        require(
            not missing_project_draft_markers,
            errors,
            "Cloudflare Worker is missing project draft handoff markers: "
            + ", ".join(missing_project_draft_markers),
            checks,
            "Cloudflare Worker preserves an expiring pre-verification project draft",
        )
        combined_match_request_source = worker_source + "\n" + match_requests_source + "\n" + turnstile_source
        missing_match_request_markers = [
            marker
            for marker in (
                "create_match_request",
                "parse_match_request_job_id",
                "match_request_payload",
                "Only contractor accounts can send mini bids.",
                "You already requested a match for this job.",
                "INSERT OR IGNORE INTO match_requests",
                "AND jobs.status = 'open'",
                "d1_change_count",
                "match-request-created",
                "match-request",
                "WORKDOE_TURNSTILE_SECRET_KEY",
            )
            if marker not in combined_match_request_source
        ]
        require(
            not missing_match_request_markers,
            errors,
            "Cloudflare Worker is missing match request API markers: "
            + ", ".join(missing_match_request_markers),
            checks,
            "Cloudflare Worker creates contractor mini bids with Turnstile and duplicate checks",
        )
        combined_match_decision_source = worker_source + "\n" + match_decisions_source
        missing_match_decision_markers = [
            marker
            for marker in (
                "decide_match_request",
                "parse_match_decision_path",
                "can_decide_match_request",
                "This mini bid has already been reviewed.",
                "UPDATE match_requests",
                "ensure_thread_for_match",
                "INSERT OR IGNORE INTO threads",
                "INSERT INTO messages",
                "APPROVAL_THREAD_MESSAGE",
                "match-request-approved",
                "match-request-rejected",
                "d1_change_count",
                "AND status = 'pending'",
                "existing_match_decision_response",
            )
            if marker not in combined_match_decision_source
        ]
        require(
            not missing_match_decision_markers,
            errors,
            "Cloudflare Worker is missing match decision API markers: "
            + ", ".join(missing_match_decision_markers),
            checks,
            "Cloudflare Worker lets clients approve or reject mini bids and open threads",
        )
        combined_message_source = worker_source + "\n" + message_threads_source
        missing_message_markers = [
            marker
            for marker in (
                "/api/messages/threads",
                "message_threads_api",
                "parse_thread_id",
                "can_view_thread",
                "can_send_thread_message",
                "message_body_payload",
                "Keep messages under 1000 characters.",
                "INSERT INTO messages",
                "message-created",
                "Only matched clients and contractors can list threads.",
                "AND messages.is_hidden = 0",
            )
            if marker not in combined_message_source
        ]
        require(
            not missing_message_markers,
            errors,
            "Cloudflare Worker is missing private message API markers: "
            + ", ".join(missing_message_markers),
            checks,
            "Cloudflare Worker supports private approved-match messaging",
        )
        combined_report_source = worker_source + "\n" + moderation_reports_source
        missing_report_markers = [
            marker
            for marker in (
                "/api/reports",
                "create_report",
                "report_payload",
                "report_target_visible_to_user",
                "report_target_query",
                "JOIN threads ON threads.id = messages.thread_id",
                "INSERT INTO reports",
                "report-created",
                "Choose what to report and include a reason.",
                "Keep report notes under 500 characters.",
                "That item is no longer available to report.",
                "Only active accounts can send reports.",
            )
            if marker not in combined_report_source
        ]
        require(
            not missing_report_markers,
            errors,
            "Cloudflare Worker is missing moderation report API markers: "
            + ", ".join(missing_report_markers),
            checks,
            "Cloudflare Worker accepts signed-in moderation reports",
        )
        combined_admin_source = worker_source + "\n" + admin_moderation_source
        missing_admin_markers = [
            marker
            for marker in (
                "/api/admin/",
                "admin_moderation_action",
                "parse_admin_moderation_path",
                "can_admin_moderate",
                "Only active admins can moderate Workdoe.",
                "admin_update_statement",
                "UPDATE users SET status = ? WHERE id = ?",
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                "UPDATE job_photos SET is_hidden = ? WHERE id = ?",
                "UPDATE contractor_photos SET is_hidden = ? WHERE id = ?",
                "UPDATE messages SET is_hidden = ? WHERE id = ?",
                "UPDATE reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
                "UPDATE match_reviews SET is_hidden = ?, updated_at = ? WHERE id = ?",
                "UPDATE match_review_reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
                "INSERT INTO moderation_actions",
                "admin-moderation-action",
                "Admin account status must be changed through the operator recovery process.",
            )
            if marker not in combined_admin_source
        ]
        require(
            not missing_admin_markers,
            errors,
            "Cloudflare Worker is missing admin moderation API markers: "
            + ", ".join(missing_admin_markers),
            checks,
            "Cloudflare Worker supports admin moderation actions",
        )
        combined_media_source = worker_source + "\n" + media_access_source + "\n" + media_uploads_source
        missing_media_markers = [
            marker
            for marker in (
                "/media/jobs/",
                "/media/contractors/",
                "/api/media/jobs/",
                "/api/media/contractors/",
                "safe_media_key",
                "can_view_job_photo",
                "can_view_contractor_photo",
                "can_upload_job_photo",
                "can_upload_contractor_photo",
                "safe_upload_metadata",
                "validate_uploaded_file_signature",
                "image_signature_matches",
                "sanitize_uploaded_image",
                "SANITIZED_IMAGE_EXTENSION",
                "cloudflare-images-webp",
                "metadata-stripped",
                "animation-flattened",
                "self.env.IMAGES",
                "self.env.MEDIA.get",
                "self.env.MEDIA.put",
                "self.env.MEDIA.delete",
                "MEDIA_QUEUE.send",
                "rollback_media_upload",
                "media_metadata_delete_statement",
                "metadata_cleanup",
                "object_cleanup",
                "process_media_review_queue_message",
                "Private Workdoe media",
                "is_hidden",
                "private, no-store",
                "has_approved_match",
                "MAX_UPLOAD_BYTES",
                "Content-Length",
                "media-uploaded",
                "media-review-queued",
                "media-review-message-accepted",
            )
            if marker not in combined_media_source
        ]
        require(
            not missing_media_markers,
            errors,
            "Cloudflare Worker is missing private R2 media markers: "
            + ", ".join(missing_media_markers),
            checks,
            "Cloudflare Worker uploads and serves private R2 media with permission checks",
        )
        missing_d1_apply_markers = [
            marker
            for marker in (
                "apply_d1_ids",
                "preview_from_file",
                "database_id",
                "preview_database_id",
                "D1 id cannot be the placeholder UUID.",
                "wrangler.jsonc must contain a d1_databases binding.",
            )
            if marker not in d1_id_apply_source
        ]
        require(
            not missing_d1_apply_markers,
            errors,
            "Cloudflare D1 ID helper is missing safety markers: "
            + ", ".join(missing_d1_apply_markers),
            checks,
            "Cloudflare D1 ID helper safely updates Wrangler IDs",
        )
        missing_bootstrap_markers = [
            marker
            for marker in (
                "build_bootstrap_steps",
                "dry_run",
                "--execute",
                "--yes",
                "create-d1-production",
                "create-d1-preview",
                "apply_d1_ids",
                "wrangler_command",
                "capture-secret-list",
                "cloudflare_secret_evidence.py",
                "--output",
                "capture_output_for_step",
                "executes_commands",
                "done-existing",
            )
            if marker not in resource_bootstrap_source
        ]
        require(
            not missing_bootstrap_markers,
            errors,
            "Cloudflare resource bootstrap helper is missing safety markers: "
            + ", ".join(missing_bootstrap_markers),
            checks,
            "Cloudflare resource bootstrap is dry-run gated",
        )
        missing_deploy_markers = [
            marker
            for marker in (
                "build_deploy_steps",
                "strict_production=True",
                "--execute",
                "--yes",
                "ready_to_deploy",
                "DEFAULT_CLERK_PROXY_PROOF_PATH",
                "--clerk-proxy-proof-json",
                "clerk_proxy_proof_json",
                "wrangler_command",
                "\"d1\", \"migrations\", \"apply\", \"workdoe\", \"--remote",
                "\"deploy",
                "workdoe_production_smoke.py",
                "--fail-when-not-ready",
                "Strict production readiness failed; deploy was not run.",
                "executes_commands",
                "output_excerpt",
                "SMOKE_OUTPUT_MAX",
            )
            if marker not in production_deploy_source
        ]
        require(
            not missing_deploy_markers,
            errors,
            "Cloudflare production deploy helper is missing safety markers: "
            + ", ".join(missing_deploy_markers),
            checks,
            "Cloudflare production deploy is strict-readiness gated",
        )
        missing_clerk_proxy_proof_markers = [
            marker
            for marker in (
                "build_proof",
                "dry_run",
                "--confirm",
                "--confirm-restricted-sign-up",
                "--confirm-email-code-only",
                "--confirm-legal-consent",
                "https://workdoe.com/__clerk",
                "https://workdoe.com/create-account",
                "restricted_sign_up_mode",
                "password_sign_in_disabled",
                "express_legal_consent",
                "https://workdoe.com/terms",
                "https://workdoe.com/privacy",
                "clerk_proxy_proof_error",
                "executes_commands",
            )
            if marker not in clerk_proxy_proof_source
        ]
        require(
            not missing_clerk_proxy_proof_markers,
            errors,
            "Cloudflare Clerk proxy proof helper is missing safety markers: "
            + ", ".join(missing_clerk_proxy_proof_markers),
            checks,
            "Cloudflare Clerk controlled-beta proof helper is confirm-gated",
        )
        missing_secret_evidence_markers = [
            marker
            for marker in (
                "capture_secret_evidence",
                "dry_run",
                "--execute",
                "--yes",
                "wrangler_command",
                "\"secret\", \"list\", \"--format\", \"json\"",
                "sanitized_secret_evidence",
                "contains_values",
                "REQUIRED_SECRETS",
                "executes_commands",
            )
            if marker not in secret_evidence_source
        ]
        require(
            not missing_secret_evidence_markers,
            errors,
            "Cloudflare secret evidence helper is missing safety markers: "
            + ", ".join(missing_secret_evidence_markers),
            checks,
            "Cloudflare secret evidence helper is dry-run gated",
        )
        missing_release_evidence_markers = [
            marker
            for marker in (
                "run_release_evidence",
                "secret_evidence_error",
                "contains_values",
                "REQUIRED_SECRETS",
                "cloudflare_secret_evidence.py --execute --yes",
            )
            if marker not in release_evidence_source
        ]
        require(
            not missing_release_evidence_markers,
            errors,
            "Cloudflare release evidence helper is missing safety markers: "
            + ", ".join(missing_release_evidence_markers),
            checks,
            "Cloudflare release evidence helper validates local proof files",
        )
        missing_wrangler_helper_markers = [
            marker
            for marker in (
                "WORKDOE_WRANGLER_BIN",
                "local_wrangler_candidates",
                "resolved_wrangler_bin",
                "wrangler_available",
                "wrangler_command",
                "shutil.which",
                "node_modules",
            )
            if marker not in wrangler_helper_source
        ]
        require(
            not missing_wrangler_helper_markers,
            errors,
            "Cloudflare Wrangler resolver helper is missing safety markers: "
            + ", ".join(missing_wrangler_helper_markers),
            checks,
            "Cloudflare Wrangler resolver supports env, local, and PATH installs",
        )

    compile_python(
        webhook_security_path,
        errors,
        checks,
        "Clerk webhook signature helper compiles",
    )

    return PreflightResult(checks=checks, warnings=warnings, errors=errors)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Workdoe Cloudflare release artifacts without deploying."
    )
    parser.add_argument(
        "--strict-production",
        action="store_true",
        help="Treat placeholder Cloudflare resource IDs as deployment-blocking errors.",
    )
    args = parser.parse_args()
    result = run_preflight(strict_production=args.strict_production)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
