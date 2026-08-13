from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import py_compile
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
REQUIRED_PUBLIC_ENV = {"CLERK_FAPI", "CLERK_FRONTEND_API_URL", "CLERK_PROXY_URL"}
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
    manifest_path = repo_root / "cloudflare" / "workdoe-cloudflare-manifest.json"
    wrangler_path = repo_root / "cloudflare" / "wrangler.jsonc"
    dev_vars_path = repo_root / "cloudflare" / ".dev.vars.example"
    worker_path = repo_root / "cloudflare" / "worker" / "entry.py"
    app_shell_path = repo_root / "cloudflare" / "worker" / "app_shell.py"
    clerk_onboarding_path = repo_root / "cloudflare" / "worker" / "clerk_onboarding.py"
    clerk_sessions_path = repo_root / "cloudflare" / "worker" / "clerk_sessions.py"
    email_payloads_path = repo_root / "cloudflare" / "worker" / "email_payloads.py"
    admin_moderation_path = repo_root / "cloudflare" / "worker" / "admin_moderation.py"
    contractor_profiles_path = repo_root / "cloudflare" / "worker" / "contractor_profiles.py"
    contractor_public_profiles_path = repo_root / "cloudflare" / "worker" / "contractor_public_profiles.py"
    contractor_leads_path = repo_root / "cloudflare" / "worker" / "contractor_leads.py"
    contractor_bids_path = repo_root / "cloudflare" / "worker" / "contractor_bids.py"
    client_jobs_path = repo_root / "cloudflare" / "worker" / "client_jobs.py"
    client_requests_path = repo_root / "cloudflare" / "worker" / "client_requests.py"
    entry_shell_path = repo_root / "cloudflare" / "worker" / "entry_shell.py"
    clerk_proxy_path = repo_root / "cloudflare" / "worker" / "clerk_proxy.py"
    webhook_security_path = repo_root / "cloudflare" / "worker" / "clerk_webhooks.py"
    public_jobs_path = repo_root / "cloudflare" / "worker" / "public_jobs.py"
    job_details_path = repo_root / "cloudflare" / "worker" / "job_details.py"
    job_status_path = repo_root / "cloudflare" / "worker" / "job_status.py"
    job_posts_path = repo_root / "cloudflare" / "worker" / "job_posts.py"
    turnstile_path = repo_root / "cloudflare" / "worker" / "turnstile.py"
    match_requests_path = repo_root / "cloudflare" / "worker" / "match_requests.py"
    match_decisions_path = repo_root / "cloudflare" / "worker" / "match_decisions.py"
    message_threads_path = repo_root / "cloudflare" / "worker" / "message_threads.py"
    moderation_reports_path = repo_root / "cloudflare" / "worker" / "moderation_reports.py"
    media_access_path = repo_root / "cloudflare" / "worker" / "media_access.py"
    media_uploads_path = repo_root / "cloudflare" / "worker" / "media_uploads.py"
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
    static_path = repo_root / "workdoe" / "static"
    worker_actions_path = static_path / "worker-actions.js"
    clerk_entry_path = static_path / "clerk-entry.js"

    migration_sql = read_text(migration_path, errors)
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
            "D1 migration is stale. Run python scripts\\prepare_cloudflare_release.py.",
            checks,
            "D1 migration matches schema snapshot",
        )
        missing_markers = sorted(marker for marker in REQUIRED_MIGRATION_MARKERS if marker not in migration_sql)
        require(
            not missing_markers,
            errors,
            "D1 migration is missing required markers: " + ", ".join(missing_markers),
            checks,
            "D1 migration contains auth, OTP, and automation tables",
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
        routes = wrangler.get("routes", [])
        route_patterns = {route.get("pattern") for route in routes if route.get("custom_domain")}
        require(
            route_patterns == {"workdoe.com", "www.workdoe.com"},
            errors,
            "Wrangler custom domains must include workdoe.com and www.workdoe.com.",
            checks,
            "Wrangler routes both Workdoe domains",
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
            wrangler.get("vars", {}).get("WORKDOE_AUTH_PROVIDER") == "clerk"
            and wrangler.get("vars", {}).get("WORKDOE_CLERK_LOGIN_MODE")
            == "same_domain_email_code",
            errors,
            "Wrangler vars must keep Clerk same-domain email-code mode.",
            checks,
            "Wrangler keeps same-domain Clerk OTP mode",
        )
        clerk_frontend_api_url = wrangler.get("vars", {}).get("CLERK_FRONTEND_API_URL", "")
        require(
            valid_workdoe_clerk_proxy_url(clerk_frontend_api_url),
            errors,
            "Wrangler vars must set CLERK_FRONTEND_API_URL to the Workdoe /__clerk proxy URL.",
            checks,
            "Wrangler configures Workdoe Clerk proxy Frontend API URL",
        )
        require(
            wrangler.get("vars", {}).get("CLERK_PROXY_URL") == clerk_frontend_api_url
            and valid_workdoe_clerk_proxy_url(wrangler.get("vars", {}).get("CLERK_PROXY_URL", "")),
            errors,
            "Wrangler vars must set CLERK_PROXY_URL to the Workdoe /__clerk proxy URL.",
            checks,
            "Wrangler configures Clerk proxy URL",
        )
        require(
            valid_clerk_fapi_url(wrangler.get("vars", {}).get("CLERK_FAPI", "")),
            errors,
            "Wrangler vars must set CLERK_FAPI to https://frontend-api.clerk.dev.",
            checks,
            "Wrangler configures Clerk Frontend API proxy target",
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
            "Wrangler secrets.required must declare every Clerk, Turnstile, and Workdoe secret.",
            checks,
            "Wrangler requires Clerk, Turnstile, and Workdoe secrets",
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
    compile_python(clerk_onboarding_path, errors, checks, "Clerk onboarding helper compiles")
    compile_python(clerk_sessions_path, errors, checks, "Clerk session verification helper compiles")
    compile_python(clerk_proxy_path, errors, checks, "Clerk Frontend API proxy helper compiles")
    compile_python(email_payloads_path, errors, checks, "Cloudflare email payload helper compiles")
    compile_python(admin_moderation_path, errors, checks, "Cloudflare admin moderation helper compiles")
    compile_python(contractor_profiles_path, errors, checks, "Cloudflare contractor profile helper compiles")
    compile_python(contractor_public_profiles_path, errors, checks, "Cloudflare public contractor profile helper compiles")
    compile_python(contractor_leads_path, errors, checks, "Cloudflare contractor leads helper compiles")
    compile_python(contractor_bids_path, errors, checks, "Cloudflare contractor bids helper compiles")
    compile_python(client_jobs_path, errors, checks, "Cloudflare client jobs helper compiles")
    compile_python(client_requests_path, errors, checks, "Cloudflare client requests helper compiles")
    compile_python(entry_shell_path, errors, checks, "Cloudflare same-domain entry shell helper compiles")
    compile_python(public_jobs_path, errors, checks, "Cloudflare public jobs helper compiles")
    compile_python(job_details_path, errors, checks, "Cloudflare job detail helper compiles")
    compile_python(job_status_path, errors, checks, "Cloudflare job status helper compiles")
    compile_python(job_posts_path, errors, checks, "Cloudflare job posting helper compiles")
    compile_python(turnstile_path, errors, checks, "Cloudflare Turnstile helper compiles")
    compile_python(match_requests_path, errors, checks, "Cloudflare match request helper compiles")
    compile_python(match_decisions_path, errors, checks, "Cloudflare match decision helper compiles")
    compile_python(message_threads_path, errors, checks, "Cloudflare message thread helper compiles")
    compile_python(moderation_reports_path, errors, checks, "Cloudflare moderation report helper compiles")
    compile_python(media_access_path, errors, checks, "Cloudflare private media helper compiles")
    compile_python(media_uploads_path, errors, checks, "Cloudflare private media upload helper compiles")
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

    worker_source = read_text(worker_path, errors)
    app_shell_source = read_text(app_shell_path, errors)
    clerk_onboarding_source = read_text(clerk_onboarding_path, errors)
    clerk_sessions_source = read_text(clerk_sessions_path, errors)
    clerk_proxy_source = read_text(clerk_proxy_path, errors)
    email_payloads_source = read_text(email_payloads_path, errors)
    admin_moderation_source = read_text(admin_moderation_path, errors)
    contractor_profiles_source = read_text(contractor_profiles_path, errors)
    contractor_public_profiles_source = read_text(contractor_public_profiles_path, errors)
    contractor_leads_source = read_text(contractor_leads_path, errors)
    contractor_bids_source = read_text(contractor_bids_path, errors)
    client_jobs_source = read_text(client_jobs_path, errors)
    client_requests_source = read_text(client_requests_path, errors)
    entry_shell_source = read_text(entry_shell_path, errors)
    public_jobs_source = read_text(public_jobs_path, errors)
    job_details_source = read_text(job_details_path, errors)
    job_status_source = read_text(job_status_path, errors)
    job_posts_source = read_text(job_posts_path, errors)
    turnstile_source = read_text(turnstile_path, errors)
    match_requests_source = read_text(match_requests_path, errors)
    match_decisions_source = read_text(match_decisions_path, errors)
    message_threads_source = read_text(message_threads_path, errors)
    moderation_reports_source = read_text(moderation_reports_path, errors)
    media_access_source = read_text(media_access_path, errors)
    media_uploads_source = read_text(media_uploads_path, errors)
    d1_id_apply_source = read_text(d1_id_apply_path, errors)
    clerk_proxy_proof_source = read_text(clerk_proxy_proof_path, errors)
    secret_evidence_source = read_text(secret_evidence_path, errors)
    release_evidence_source = read_text(release_evidence_path, errors)
    wrangler_helper_source = read_text(wrangler_helper_path, errors)
    resource_bootstrap_source = read_text(resource_bootstrap_path, errors)
    production_deploy_source = read_text(production_deploy_path, errors)
    worker_actions_source = read_text(worker_actions_path, errors)
    clerk_entry_source = read_text(clerk_entry_path, errors)
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
                "INSERT INTO users",
                "auth_provider, external_subject",
                "INSERT INTO client_profiles",
                "INSERT INTO contractor_profiles",
                "email_conflict",
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
                "upsert_contractor_profile",
                "ON CONFLICT(user_id) DO UPDATE",
                "Use a full website URL that starts with http:// or https://.",
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
        combined_public_contractor_source = worker_source + "\n" + contractor_public_profiles_source
        missing_public_contractor_markers = [
            marker
            for marker in (
                "/api/contractors/",
                "public_contractor_profile",
                "parse_public_contractor_id",
                "can_view_public_contractor_profile",
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
                "stale-match-reminder",
                "moderation-digest",
                "env.EMAIL.send",
                "email-message-sent",
                "email-message-invalid",
                "email-message-send-failed",
                "ack_message",
                "retry_message",
                "WORKDOE_EMAIL_FROM",
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
        combined_entry_shell_source = (
            worker_source + "\n" + entry_shell_source + "\n" + clerk_entry_source + "\n" + clerk_proxy_source
        )
        missing_entry_shell_markers = [
            marker
            for marker in (
                "ENTRY_ROUTES",
                '"/login"',
                '"/start"',
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
                "/static/map.js",
                "finishSignIn",
                "node.dataset.signUpUrl",
                "Email code sign-in stays on workdoe.com.",
                "Content-Security-Policy",
                "Cache-Control",
                "https://*.tile.openstreetmap.org",
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
        combined_app_shell_source = worker_source + "\n" + app_shell_source + "\n" + worker_actions_source
        missing_app_shell_markers = [
            marker
            for marker in (
                "is_app_shell_route",
                "app_shell",
                '"/dashboard"',
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
                "contractor_job_detail_html",
                "parse_app_client_job_id",
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
        combined_public_jobs_source = worker_source + "\n" + public_jobs_source
        missing_public_jobs_markers = [
            marker
            for marker in (
                "/api/jobs/open",
                "public_open_jobs",
                "public_jobs_payload",
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
            "Cloudflare Worker creates client jobs with Turnstile and approximate pins",
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
                "INSERT INTO match_requests",
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
                "INSERT INTO threads",
                "INSERT INTO messages",
                "APPROVAL_THREAD_MESSAGE",
                "match-request-approved",
                "match-request-rejected",
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
                "report_target_exists",
                "report_target_query",
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
                "UPDATE messages SET is_hidden = 1 WHERE id = ?",
                "UPDATE reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
                "INSERT INTO moderation_actions",
                "admin-moderation-action",
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
                "self.env.MEDIA.get",
                "self.env.MEDIA.put",
                "MEDIA_QUEUE.send",
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
                "curl.exe\", \"-fS\", \"-I",
                "curl.exe\", \"-fsS",
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
                "https://workdoe.com/__clerk",
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
            "Cloudflare Clerk proxy proof helper is confirm-gated",
        )
        missing_secret_evidence_markers = [
            marker
            for marker in (
                "capture_secret_evidence",
                "dry_run",
                "--execute",
                "--yes",
                "wrangler_command",
                "\"secret\", \"list\", \"--json",
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
                "clerk_proxy_proof_error",
                "contains_values",
                "REQUIRED_SECRETS",
                "cloudflare_secret_evidence.py --execute --yes",
                "cloudflare_clerk_proxy_proof.py --confirm",
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
