from __future__ import annotations

import asyncio
import base64
import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "prepare_cloudflare_release.py"
PREFLIGHT_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_preflight.py"
READINESS_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_readiness.py"
LAUNCH_PLAN_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_launch_plan.py"
LAUNCH_STATUS_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_launch_status.py"
WRANGLER_HELPER_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_wrangler.py"
CLERK_PROXY_PROOF_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_clerk_proxy_proof.py"
SECRET_EVIDENCE_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_secret_evidence.py"
RELEASE_EVIDENCE_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_release_evidence.py"
D1_ID_APPLY_SCRIPT_PATH = ROOT / "scripts" / "apply_cloudflare_d1_ids.py"
RESOURCE_BOOTSTRAP_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_resource_bootstrap.py"
PRODUCTION_DEPLOY_SCRIPT_PATH = ROOT / "scripts" / "cloudflare_production_deploy.py"
GITHUB_RELEASE_STATUS_SCRIPT_PATH = ROOT / "scripts" / "github_release_status.py"
GITHUB_DEPLOY_DISPATCH_SCRIPT_PATH = ROOT / "scripts" / "github_deploy_dispatch.py"
WORKDOE_LAUNCH_DOCTOR_SCRIPT_PATH = ROOT / "scripts" / "workdoe_launch_doctor.py"
WORKDOE_LAUNCH_HANDOFF_SCRIPT_PATH = ROOT / "scripts" / "workdoe_launch_handoff.py"
WORKDOE_DNS_DIAGNOSTIC_SCRIPT_PATH = ROOT / "scripts" / "workdoe_dns_diagnostic.py"
WORKDOE_PRODUCTION_SMOKE_SCRIPT_PATH = ROOT / "scripts" / "workdoe_production_smoke.py"
APP_SHELL_PATH = ROOT / "cloudflare" / "worker" / "app_shell.py"
ASSET_RELEASE_PATH = ROOT / "cloudflare" / "worker" / "asset_release.py"
CLERK_ONBOARDING_PATH = ROOT / "cloudflare" / "worker" / "clerk_onboarding.py"
CLERK_SESSIONS_PATH = ROOT / "cloudflare" / "worker" / "clerk_sessions.py"
CLERK_PROXY_PATH = ROOT / "cloudflare" / "worker" / "clerk_proxy.py"
CLERK_WEBHOOKS_PATH = ROOT / "cloudflare" / "worker" / "clerk_webhooks.py"
EMAIL_PAYLOADS_PATH = ROOT / "cloudflare" / "worker" / "email_payloads.py"
EMAIL_CODE_AUTH_PATH = ROOT / "cloudflare" / "worker" / "email_code_auth.py"
ADMIN_MODERATION_PATH = ROOT / "cloudflare" / "worker" / "admin_moderation.py"
CONTRACTOR_PROFILES_PATH = ROOT / "cloudflare" / "worker" / "contractor_profiles.py"
CONTRACTOR_REPUTATION_PATH = ROOT / "cloudflare" / "worker" / "contractor_reputation.py"
CONTRACTOR_CREDENTIALS_PATH = ROOT / "cloudflare" / "worker" / "contractor_credentials.py"
CONTRACTOR_PREFERENCES_PATH = ROOT / "cloudflare" / "worker" / "contractor_preferences.py"
CONTRACTOR_PROPOSAL_TEMPLATES_PATH = (
    ROOT / "cloudflare" / "worker" / "contractor_proposal_templates.py"
)
CLIENT_PROFILES_PATH = ROOT / "cloudflare" / "worker" / "client_profiles.py"
CLIENT_PROJECT_TEMPLATES_PATH = ROOT / "cloudflare" / "worker" / "client_project_templates.py"
CONTRACTOR_PUBLIC_PROFILES_PATH = ROOT / "cloudflare" / "worker" / "contractor_public_profiles.py"
CONTRACTOR_LEADS_PATH = ROOT / "cloudflare" / "worker" / "contractor_leads.py"
CONTRACTOR_BIDS_PATH = ROOT / "cloudflare" / "worker" / "contractor_bids.py"
CLIENT_JOBS_PATH = ROOT / "cloudflare" / "worker" / "client_jobs.py"
CLIENT_REQUESTS_PATH = ROOT / "cloudflare" / "worker" / "client_requests.py"
BID_COMPARISON_PATH = ROOT / "cloudflare" / "worker" / "bid_comparison.py"
ENTRY_SHELL_PATH = ROOT / "cloudflare" / "worker" / "entry_shell.py"
PUBLIC_JOBS_PATH = ROOT / "cloudflare" / "worker" / "public_jobs.py"
PUBLIC_JOB_QUERY_PATH = ROOT / "cloudflare" / "worker" / "public_job_query.py"
DEMO_PROJECTS_PATH = ROOT / "cloudflare" / "worker" / "demo_projects.py"
JOB_DETAILS_PATH = ROOT / "cloudflare" / "worker" / "job_details.py"
JOB_STATUS_PATH = ROOT / "cloudflare" / "worker" / "job_status.py"
JOB_POSTS_PATH = ROOT / "cloudflare" / "worker" / "job_posts.py"
SERVICE_TAXONOMY_PATH = ROOT / "cloudflare" / "worker" / "service_taxonomy.py"
SERVICE_SCOPE_PATH = ROOT / "cloudflare" / "worker" / "service_scope.py"
SERVICE_POLICY_PATH = ROOT / "cloudflare" / "worker" / "service_policy.py"
PROJECT_READINESS_PATH = ROOT / "cloudflare" / "worker" / "project_readiness.py"
PILOT_METRICS_PATH = ROOT / "cloudflare" / "worker" / "pilot_metrics.py"
SERVICE_ACTIVATION_PATH = ROOT / "cloudflare" / "worker" / "service_activation.py"
MARKET_FIT_PATH = ROOT / "cloudflare" / "worker" / "market_fit.py"
TURNSTILE_PATH = ROOT / "cloudflare" / "worker" / "turnstile.py"
MATCH_REQUESTS_PATH = ROOT / "cloudflare" / "worker" / "match_requests.py"
MATCH_DECISIONS_PATH = ROOT / "cloudflare" / "worker" / "match_decisions.py"
MATCH_COMPLETIONS_PATH = ROOT / "cloudflare" / "worker" / "match_completions.py"
MATCH_REVIEWS_PATH = ROOT / "cloudflare" / "worker" / "match_reviews.py"
REPEAT_PROVIDER_INVITATIONS_PATH = (
    ROOT / "cloudflare" / "worker" / "repeat_provider_invitations.py"
)
MESSAGE_THREADS_PATH = ROOT / "cloudflare" / "worker" / "message_threads.py"
MODERATION_REPORTS_PATH = ROOT / "cloudflare" / "worker" / "moderation_reports.py"
MEDIA_ACCESS_PATH = ROOT / "cloudflare" / "worker" / "media_access.py"
MEDIA_UPLOADS_PATH = ROOT / "cloudflare" / "worker" / "media_uploads.py"
REQUEST_SECURITY_PATH = ROOT / "cloudflare" / "worker" / "request_security.py"
IDEMPOTENCY_PATH = ROOT / "cloudflare" / "worker" / "idempotency.py"
WORKER_ENTRY_PATH = ROOT / "cloudflare" / "worker" / "entry.py"


def load_worker_entry_module():
    workers_stub = ModuleType("workers")

    class StubResponse:
        def __init__(self, body="", status=200, headers=None):
            self.body = body
            self.status = status
            self.headers = headers or {}

    class StubWorkerEntrypoint:
        pass

    async def stub_fetch(*args, **kwargs):
        raise RuntimeError("Network fetch is not available in unit tests.")

    workers_stub.Response = StubResponse
    workers_stub.WorkerEntrypoint = StubWorkerEntrypoint
    workers_stub.fetch = stub_fetch
    previous_workers = sys.modules.get("workers")
    worker_dir = str(WORKER_ENTRY_PATH.parent)
    sys.modules["workers"] = workers_stub
    sys.path.insert(0, worker_dir)
    try:
        spec = importlib.util.spec_from_file_location(
            "cloudflare_worker_entry_test",
            WORKER_ENTRY_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(worker_dir)
        if previous_workers is None:
            sys.modules.pop("workers", None)
        else:
            sys.modules["workers"] = previous_workers


def load_repeat_provider_invitations_module():
    spec = importlib.util.spec_from_file_location(
        "repeat_provider_invitations",
        REPEAT_PROVIDER_INVITATIONS_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_idempotency_module():
    spec = importlib.util.spec_from_file_location("idempotency", IDEMPOTENCY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_match_reviews_module():
    spec = importlib.util.spec_from_file_location("match_reviews", MATCH_REVIEWS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_release_script():
    spec = importlib.util.spec_from_file_location("prepare_cloudflare_release", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_asset_release_module():
    spec = importlib.util.spec_from_file_location("asset_release", ASSET_RELEASE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_preflight_script():
    spec = importlib.util.spec_from_file_location("cloudflare_preflight", PREFLIGHT_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_readiness_script():
    spec = importlib.util.spec_from_file_location("cloudflare_readiness", READINESS_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_launch_plan_script():
    spec = importlib.util.spec_from_file_location("cloudflare_launch_plan", LAUNCH_PLAN_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_launch_status_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_launch_status",
        LAUNCH_STATUS_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_wrangler_helper_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_wrangler",
        WRANGLER_HELPER_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_clerk_proxy_proof_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_clerk_proxy_proof",
        CLERK_PROXY_PROOF_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_secret_evidence_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_secret_evidence",
        SECRET_EVIDENCE_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_release_evidence_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_release_evidence",
        RELEASE_EVIDENCE_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_d1_id_apply_script():
    spec = importlib.util.spec_from_file_location("apply_cloudflare_d1_ids", D1_ID_APPLY_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_resource_bootstrap_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_resource_bootstrap",
        RESOURCE_BOOTSTRAP_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_production_deploy_script():
    spec = importlib.util.spec_from_file_location(
        "cloudflare_production_deploy",
        PRODUCTION_DEPLOY_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_github_release_status_script():
    spec = importlib.util.spec_from_file_location(
        "github_release_status",
        GITHUB_RELEASE_STATUS_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_github_deploy_dispatch_script():
    load_workdoe_launch_doctor_script()
    spec = importlib.util.spec_from_file_location(
        "github_deploy_dispatch",
        GITHUB_DEPLOY_DISPATCH_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_workdoe_launch_doctor_script():
    spec = importlib.util.spec_from_file_location(
        "workdoe_launch_doctor",
        WORKDOE_LAUNCH_DOCTOR_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_workdoe_launch_handoff_script():
    load_github_deploy_dispatch_script()
    spec = importlib.util.spec_from_file_location(
        "workdoe_launch_handoff",
        WORKDOE_LAUNCH_HANDOFF_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_workdoe_dns_diagnostic_script():
    spec = importlib.util.spec_from_file_location(
        "workdoe_dns_diagnostic",
        WORKDOE_DNS_DIAGNOSTIC_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_workdoe_production_smoke_script():
    spec = importlib.util.spec_from_file_location(
        "workdoe_production_smoke",
        WORKDOE_PRODUCTION_SMOKE_SCRIPT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_clerk_webhooks_module():
    spec = importlib.util.spec_from_file_location("clerk_webhooks", CLERK_WEBHOOKS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_clerk_sessions_module():
    spec = importlib.util.spec_from_file_location("clerk_sessions", CLERK_SESSIONS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_clerk_onboarding_module():
    spec = importlib.util.spec_from_file_location("clerk_onboarding", CLERK_ONBOARDING_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_clerk_proxy_module():
    spec = importlib.util.spec_from_file_location("clerk_proxy", CLERK_PROXY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_admin_moderation_module():
    spec = importlib.util.spec_from_file_location("admin_moderation", ADMIN_MODERATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_public_jobs_module():
    load_job_posts_module()
    spec = importlib.util.spec_from_file_location("public_jobs", PUBLIC_JOBS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_public_job_query_module():
    spec = importlib.util.spec_from_file_location("public_job_query", PUBLIC_JOB_QUERY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_demo_projects_module():
    load_service_taxonomy_module()
    spec = importlib.util.spec_from_file_location("demo_projects", DEMO_PROJECTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_entry_shell_module():
    load_asset_release_module()
    load_public_jobs_module()
    spec = importlib.util.spec_from_file_location("entry_shell", ENTRY_SHELL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_app_shell_module():
    load_asset_release_module()
    load_job_posts_module()
    load_match_reviews_module()
    load_market_fit_module()
    load_client_profiles_module()
    load_client_project_templates_module()
    load_contractor_profiles_module()
    load_contractor_credentials_module()
    load_contractor_preferences_module()
    load_entry_shell_module()
    load_service_activation_module()
    spec = importlib.util.spec_from_file_location("app_shell", APP_SHELL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_job_details_module():
    load_job_posts_module()
    load_project_readiness_module()
    spec = importlib.util.spec_from_file_location("job_details", JOB_DETAILS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_job_status_module():
    spec = importlib.util.spec_from_file_location("job_status", JOB_STATUS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_job_posts_module():
    load_service_taxonomy_module()
    load_service_policy_module()
    load_service_scope_module()
    spec = importlib.util.spec_from_file_location("job_posts", JOB_POSTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_service_taxonomy_module():
    spec = importlib.util.spec_from_file_location("service_taxonomy", SERVICE_TAXONOMY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_service_scope_module():
    load_service_taxonomy_module()
    spec = importlib.util.spec_from_file_location("service_scope", SERVICE_SCOPE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_service_policy_module():
    load_service_taxonomy_module()
    spec = importlib.util.spec_from_file_location("service_policy", SERVICE_POLICY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_project_readiness_module():
    spec = importlib.util.spec_from_file_location(
        "project_readiness", PROJECT_READINESS_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_pilot_metrics_module():
    load_project_readiness_module()
    spec = importlib.util.spec_from_file_location("pilot_metrics", PILOT_METRICS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_service_activation_module():
    spec = importlib.util.spec_from_file_location("service_activation", SERVICE_ACTIVATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_market_fit_module():
    load_service_taxonomy_module()
    spec = importlib.util.spec_from_file_location("market_fit", MARKET_FIT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_turnstile_module():
    spec = importlib.util.spec_from_file_location("turnstile", TURNSTILE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_match_requests_module():
    spec = importlib.util.spec_from_file_location("match_requests", MATCH_REQUESTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_match_decisions_module():
    spec = importlib.util.spec_from_file_location("match_decisions", MATCH_DECISIONS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_message_threads_module():
    load_contractor_reputation_module()
    spec = importlib.util.spec_from_file_location("message_threads", MESSAGE_THREADS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_moderation_reports_module():
    spec = importlib.util.spec_from_file_location("moderation_reports", MODERATION_REPORTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_email_payloads_module():
    spec = importlib.util.spec_from_file_location("email_payloads", EMAIL_PAYLOADS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_email_code_auth_module():
    spec = importlib.util.spec_from_file_location("email_code_auth", EMAIL_CODE_AUTH_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_profiles_module():
    load_market_fit_module()
    spec = importlib.util.spec_from_file_location("contractor_profiles", CONTRACTOR_PROFILES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_credentials_module():
    spec = importlib.util.spec_from_file_location(
        "contractor_credentials", CONTRACTOR_CREDENTIALS_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_reputation_module():
    spec = importlib.util.spec_from_file_location(
        "contractor_reputation", CONTRACTOR_REPUTATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_preferences_module():
    load_service_taxonomy_module()
    spec = importlib.util.spec_from_file_location(
        "contractor_preferences", CONTRACTOR_PREFERENCES_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_client_profiles_module():
    spec = importlib.util.spec_from_file_location("client_profiles", CLIENT_PROFILES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_client_project_templates_module():
    spec = importlib.util.spec_from_file_location(
        "client_project_templates", CLIENT_PROJECT_TEMPLATES_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_proposal_templates_module():
    spec = importlib.util.spec_from_file_location(
        "contractor_proposal_templates", CONTRACTOR_PROPOSAL_TEMPLATES_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_public_profiles_module():
    load_market_fit_module()
    load_contractor_profiles_module()
    load_contractor_credentials_module()
    load_contractor_reputation_module()
    load_contractor_preferences_module()
    spec = importlib.util.spec_from_file_location(
        "contractor_public_profiles",
        CONTRACTOR_PUBLIC_PROFILES_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_client_jobs_module():
    load_job_posts_module()
    load_project_readiness_module()
    spec = importlib.util.spec_from_file_location("client_jobs", CLIENT_JOBS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_client_requests_module():
    load_job_posts_module()
    load_match_completions_module()
    load_bid_comparison_module()
    spec = importlib.util.spec_from_file_location("client_requests", CLIENT_REQUESTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_bid_comparison_module():
    load_contractor_reputation_module()
    spec = importlib.util.spec_from_file_location(
        "bid_comparison", BID_COMPARISON_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_leads_module():
    load_job_posts_module()
    load_market_fit_module()
    load_project_readiness_module()
    spec = importlib.util.spec_from_file_location("contractor_leads", CONTRACTOR_LEADS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_bids_module():
    load_match_completions_module()
    load_contractor_reputation_module()
    spec = importlib.util.spec_from_file_location("contractor_bids", CONTRACTOR_BIDS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_match_completions_module():
    spec = importlib.util.spec_from_file_location(
        "match_completions",
        MATCH_COMPLETIONS_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_media_access_module():
    spec = importlib.util.spec_from_file_location("media_access", MEDIA_ACCESS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_media_uploads_module():
    spec = importlib.util.spec_from_file_location("media_uploads", MEDIA_UPLOADS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_request_security_module():
    spec = importlib.util.spec_from_file_location("request_security", REQUEST_SECURITY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def jwt_segment(data: dict) -> str:
    encoded = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def fake_session_token(
    payload: dict | None = None,
    header: dict | None = None,
    signature: bytes = b"workdoe-signature",
) -> str:
    token_header = header or {"alg": "RS256", "typ": "JWT", "kid": "kid_workdoe"}
    token_payload = {
        "sub": "user_workdoe_123",
        "sid": "sess_workdoe_123",
        "exp": 1700000300,
        "nbf": 1699999700,
        "azp": "https://workdoe.com",
    }
    token_payload.update(payload or {})
    return ".".join(
        [
            jwt_segment(token_header),
            jwt_segment(token_payload),
            base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        ]
    )


class CloudflareReleasePrepTests(unittest.TestCase):
    def test_cloudflare_idempotency_contract_hashes_retry_keys_and_scopes_resources(self):
        module = load_idempotency_module()
        key = "idem-cloudflare-1234567890abcdef"
        self.assertEqual(module.normalize_idempotency_key(key), key)
        self.assertEqual(len(module.idempotency_key_hash(key)), 64)
        self.assertNotEqual(module.idempotency_key_hash(key), key)
        self.assertEqual(
            module.idempotency_action("message-create", 42),
            "message-create:42",
        )
        self.assertEqual(
            module.idempotency_resource_type("contractor_photo"),
            "contractor_photo",
        )
        with self.assertRaises(module.IdempotencyError):
            module.normalize_idempotency_key("short", required=True)
        with self.assertRaises(module.IdempotencyError):
            module.normalize_idempotency_key("x" * 20 + " unsafe", required=True)
        with self.assertRaises(module.IdempotencyError):
            module.idempotency_action("message-create", 0)

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0022_idempotent_marketplace_writes.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS idempotency_requests", migration)
        self.assertIn("UNIQUE(actor_id, action, key_hash)", migration)
        self.assertIn("CHECK (length(key_hash) = 64)", migration)
        for private_field in ("email", "description", "body", "reason", "stored_path"):
            self.assertNotIn(private_field, migration.lower())

        worker_actions = (ROOT / "workdoe" / "static" / "worker-actions.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("window.crypto.randomUUID", worker_actions)
        self.assertIn('"Idempotency-Key": requestKey', worker_actions)
        self.assertIn('uploadData.append("idempotency_key"', worker_actions)
        entry = WORKER_ENTRY_PATH.read_text(encoding="utf-8")
        self.assertIn("async def begin_idempotent_request", entry)
        self.assertIn("async def complete_idempotent_request", entry)
        self.assertIn('"job-create"', entry)
        self.assertIn('idempotency_action("message-create", thread_id)', entry)
        self.assertIn('idempotency_action(f"media-upload-{scope}", owner_id)', entry)

        entry_module = load_worker_entry_module()
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(migration)

        async def fake_db_run(_env, sql, *params):
            before = connection.total_changes
            cursor = connection.execute(sql, params)
            rows = (
                [dict(row) for row in cursor.fetchall()]
                if sql.lstrip().upper().startswith("SELECT")
                else []
            )
            connection.commit()
            return {
                "results": rows,
                "meta": {
                    "changes": connection.total_changes - before,
                    "last_row_id": cursor.lastrowid,
                },
            }

        entry_module.db_run = fake_db_run
        reserved = asyncio.run(
            entry_module.begin_idempotent_request(
                SimpleNamespace(), 8, "job-create", "job", key
            )
        )
        self.assertEqual(reserved["state"], "reserved")
        processing = asyncio.run(
            entry_module.begin_idempotent_request(
                SimpleNamespace(), 8, "job-create", "job", key
            )
        )
        self.assertEqual(processing["state"], "processing")
        self.assertEqual(entry_module.idempotency_conflict_response(processing).status, 409)
        asyncio.run(
            entry_module.complete_idempotent_request(
                SimpleNamespace(), 8, reserved, 99
            )
        )
        replay = asyncio.run(
            entry_module.begin_idempotent_request(
                SimpleNamespace(), 8, "job-create", "job", key
            )
        )
        self.assertEqual(replay["state"], "replay")
        self.assertEqual(replay["resource_id"], 99)
        stored = connection.execute(
            "SELECT key_hash, resource_type, status FROM idempotency_requests"
        ).fetchone()
        self.assertEqual(stored["key_hash"], module.idempotency_key_hash(key))
        self.assertEqual(stored["resource_type"], "job")
        self.assertEqual(stored["status"], "completed")
        connection.close()

    def test_worker_same_origin_write_marker_policy(self):
        module = load_request_security_module()
        self.assertTrue(
            module.same_origin_api_write_allowed("GET", "/api/client/jobs", "")
        )
        self.assertTrue(
            module.same_origin_api_write_allowed("POST", "/post-project", "")
        )
        self.assertTrue(
            module.same_origin_api_write_allowed(
                "POST", "/api/jobs", module.WORKDOE_REQUEST_MARKER
            )
        )
        self.assertFalse(module.same_origin_api_write_allowed("POST", "/api/jobs", ""))
        self.assertFalse(
            module.same_origin_api_write_allowed(
                "POST", "/api/media/jobs/12/upload", "cross-site"
            )
        )
        self.assertTrue(
            module.authenticated_write_rate_limit_required(
                "POST", "/api/messages/threads/1"
            )
        )
        self.assertTrue(
            module.authenticated_write_rate_limit_required("POST", "/api/reports")
        )
        self.assertFalse(
            module.authenticated_write_rate_limit_required("GET", "/api/reports")
        )
        self.assertFalse(
            module.authenticated_write_rate_limit_required(
                "POST", "/api/auth/logout"
            )
        )
        self.assertEqual(
            module.authenticated_write_rate_limit_key(17),
            "workdoe-user:17",
        )
        with self.assertRaises(ValueError):
            module.authenticated_write_rate_limit_key(0)

    def test_release_prep_writes_d1_migration_and_manifest(self):
        module = load_release_script()
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "cloudflare"
            result = module.prepare_release(ROOT, output_root)

            migration = Path(result["migration"])
            manifest_path = Path(result["manifest"])
            wrangler_path = Path(result["wrangler"])
            dev_vars_example_path = Path(result["dev_vars_example"])
            self.assertTrue(migration.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(wrangler_path.exists())
            self.assertTrue(dev_vars_example_path.exists())

            migration_sql = migration.read_text(encoding="utf-8")
            self.assertIn("PRAGMA foreign_keys = ON;", migration_sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS login_codes", migration_sql)
            self.assertIn("CREATE TABLE IF NOT EXISTS automation_events", migration_sql)
            self.assertIn("auth_provider TEXT NOT NULL DEFAULT 'local'", migration_sql)
            self.assertIn("external_subject TEXT", migration_sql)
            self.assertIn("idx_users_auth_subject", migration_sql)
            self.assertIn("selected_job_id INTEGER", migration_sql)
            self.assertIn("idx_login_codes_selected_job", migration_sql)
            self.assertIn("idx_automation_events_type_target", migration_sql)
            self.assertNotIn("CREATE TABLE IF NOT EXISTS contractor_lead_preferences", migration_sql)
            self.assertNotIn("CREATE TABLE IF NOT EXISTS idempotency_requests", migration_sql)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["domain"], "workdoe.com")
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["main"],
                "cloudflare/worker/entry.py",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["service"],
                "Clerk with Cloudflare D1 role records",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["primary_strategy"],
                "email_code_otp",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["required_env"][
                    "WORKDOE_AUTH_PROVIDER"
                ],
                "clerk",
            )
            self.assertIn(
                "WORKDOE_SECRET_KEY",
                manifest["cloudflare_targets"]["identity"]["required_env"],
            )
            self.assertIn(
                "expire-login-codes",
                {
                    job["name"]
                    for job in manifest["cloudflare_targets"]["automation"]["scheduled_jobs"]
                },
            )
            self.assertIn(
                "EMAIL_QUEUE",
                {
                    queue["binding"]
                    for queue in manifest["cloudflare_targets"]["automation"]["queues"]
                },
            )
            self.assertEqual(manifest["cloudflare_targets"]["database"]["service"], "D1")
            self.assertEqual(
                manifest["cloudflare_targets"]["media"]["service"],
                "Cloudflare Images and R2",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["media"]["images_binding"],
                "IMAGES",
            )
            self.assertTrue(
                manifest["cloudflare_targets"]["bot_protection"][
                    "server_side_validation_required"
                ]
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["database"]["migration_sha256"],
                result["migration_sha256"],
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["database"]["migration_chain_sha256"],
                result["migration_chain_sha256"],
            )
            self.assertEqual(
                result["asset_release_token"],
                module.static_asset_release_token(ROOT),
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["asset_release_token"],
                result["asset_release_token"],
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["versioned_static_assets"],
                ["styles.css", "map.js", "project-composer.js"],
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["database"]["migrations_dir"],
                "cloudflare/d1/migrations",
            )

            wrangler = json.loads(wrangler_path.read_text(encoding="utf-8"))
            self.assertEqual(wrangler["name"], "workdoe")
            self.assertEqual(wrangler["main"], "worker/entry.py")
            self.assertEqual(
                wrangler["compatibility_flags"],
                ["python_workers", "disable_python_external_sdk"],
            )
            self.assertFalse(wrangler["workers_dev"])
            self.assertNotIn("routes", wrangler)
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["custom_domains"],
                ["workdoe.com", "www.workdoe.com"],
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["static_asset_headers"],
                "workdoe/static/_headers",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["immutable_static_asset_paths"],
                [
                    "/styles.css",
                    "/map.js",
                    "/project-composer.js",
                    "/vendor/*",
                    "/deer.svg",
                ],
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["custom_domain_management"],
                "preconfigured_outside_routine_deploys",
            )
            self.assertEqual(wrangler["d1_databases"][0]["binding"], "DB")

            self.assertEqual(
                wrangler["d1_databases"][0]["migrations_dir"],
                "d1/migrations",
            )
            self.assertEqual(wrangler["r2_buckets"][0]["binding"], "MEDIA")
            self.assertEqual(wrangler["images"], {"binding": "IMAGES"})
            self.assertEqual(
                wrangler["ratelimits"],
                [
                    {
                        "name": "WRITE_RATE_LIMITER",
                        "namespace_id": "949417",
                        "simple": {"limit": 40, "period": 60},
                    }
                ],
            )
            self.assertEqual(wrangler["assets"]["binding"], "ASSETS")
            self.assertFalse(wrangler["assets"]["run_worker_first"])
            self.assertEqual(
                {producer["binding"] for producer in wrangler["queues"]["producers"]},
                {"EMAIL_QUEUE", "MEDIA_QUEUE"},
            )
            self.assertEqual(
                set(wrangler["triggers"]["crons"]),
                {"*/15 * * * *", "0 14 * * *", "0 13 * * 1-5"},
            )
            self.assertEqual(
                wrangler["vars"]["WORKDOE_AUTH_PROVIDER"],
                "clerk",
            )
            self.assertEqual(
                wrangler["vars"]["WORKDOE_LOGIN_MODE"],
                "same_domain_email_code",
            )
            self.assertEqual(
                wrangler["vars"]["WORKDOE_ENFORCE_SERVICE_ACTIVATION"],
                "true",
            )
            self.assertEqual(wrangler["vars"]["WORKDOE_EMAIL_FROM"], "no-reply@workdoe.com")
            self.assertEqual(wrangler["vars"]["WORKDOE_ADMIN_EMAIL"], "admin@workdoe.com")
            self.assertEqual(
                wrangler["send_email"],
                [
                    {
                        "name": "EMAIL",
                        "allowed_sender_addresses": ["no-reply@workdoe.com"],
                        "remote": True,
                    }
                ],
            )
            required_env_names = {
                "CLERK_JWT_KEY",
                "CLERK_PUBLISHABLE_KEY",
                "CLERK_SECRET_KEY",
                "CLERK_WEBHOOK_SECRET",
                "WORKDOE_SECRET_KEY",
                "WORKDOE_TURNSTILE_SITE_KEY",
                "WORKDOE_TURNSTILE_SECRET_KEY",
            }
            self.assertEqual(set(wrangler["secrets"]["required"]), required_env_names)
            self.assertFalse(required_env_names & set(wrangler["vars"]))
            self.assertTrue(wrangler["observability"]["enabled"])

            headers_text = (ROOT / "workdoe" / "static" / "_headers").read_text(
                encoding="utf-8"
            )
            rules = load_preflight_script().parse_static_header_rules(headers_text)
            self.assertEqual(rules["/*"]["x-content-type-options"], "nosniff")
            for path in manifest["cloudflare_targets"]["worker"][
                "immutable_static_asset_paths"
            ]:
                self.assertEqual(
                    rules[path]["cache-control"],
                    "public, max-age=31556952, immutable",
                )
            self.assertNotIn("cache-control", rules["/*"])

            dev_vars_example = dev_vars_example_path.read_text(encoding="utf-8")
            self.assertIn("WORKDOE_AUTH_PROVIDER=clerk", dev_vars_example)
            self.assertIn("WORKDOE_LOGIN_MODE=same_domain_email_code", dev_vars_example)
            self.assertIn("WORKDOE_ENFORCE_SERVICE_ACTIVATION=true", dev_vars_example)
            for env_name in required_env_names:
                self.assertIn(f"{env_name}=replace-me", dev_vars_example)

    def test_static_asset_release_token_is_content_derived_and_shared(self):
        release_module = load_release_script()
        preflight_module = load_preflight_script()
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            static_root = repo_root / "workdoe" / "static"
            static_root.mkdir(parents=True)
            for filename in release_module.VERSIONED_STATIC_ASSET_FILES:
                (static_root / filename).write_bytes(f"reviewed:{filename}".encode())

            first_token = release_module.static_asset_release_token(repo_root)
            (static_root / "map.js").write_bytes(b"reviewed:map.js:changed")
            second_token = release_module.static_asset_release_token(repo_root)

        expected_token = release_module.static_asset_release_token(ROOT)
        worker_token = load_asset_release_module().ASSET_RELEASE_TOKEN
        from workdoe.asset_release import ASSET_RELEASE_TOKEN as flask_token

        self.assertRegex(first_token, r"^asset-[0-9a-f]{16}$")
        self.assertNotEqual(first_token, second_token)
        self.assertEqual(worker_token, expected_token)
        self.assertEqual(flask_token, expected_token)
        self.assertTrue(
            preflight_module.asset_release_token_matches(
                f'ASSET_RELEASE_TOKEN = "{expected_token}"',
                expected_token,
            )
        )
        self.assertFalse(
            preflight_module.asset_release_token_matches(
                'ASSET_RELEASE_TOKEN = "asset-stale"',
                expected_token,
            )
        )

    def test_fresh_d1_database_accepts_complete_migration_chain(self):
        migrations_dir = ROOT / "cloudflare" / "d1" / "migrations"
        migration_paths = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
        self.assertEqual(len(migration_paths), 34)

        connection = sqlite3.connect(":memory:")
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            for path in migration_paths:
                with self.subTest(migration=path.name):
                    connection.executescript(path.read_text(encoding="utf-8"))

            preference_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(contractor_lead_preferences)"
                )
            }
            self.assertIn("lead_alert_preference", preference_columns)
            self.assertIn("saved_service_group_slug", preference_columns)
            self.assertIn("saved_service_slug", preference_columns)
            job_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(jobs)")
            }
            self.assertIn("budget_min", job_columns)
            self.assertIn("service_group_slug", job_columns)
            self.assertIn("service_slug", job_columns)
            thread_read_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(thread_reads)")
            }
            self.assertEqual(
                thread_read_columns,
                {"thread_id", "user_id", "last_read_message_id", "last_read_at"},
            )
            job_indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(jobs)")
            }
            photo_indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(job_photos)")
            }
            contractor_photo_indexes = {
                row[1]
                for row in connection.execute("PRAGMA index_list(contractor_photos)")
            }
            thread_indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(threads)")
            }
            self.assertIn("idx_jobs_open_geo", job_indexes)
            self.assertIn("idx_job_photos_public_job", photo_indexes)
            self.assertIn(
                "idx_contractor_photos_public_contractor",
                contractor_photo_indexes,
            )
            self.assertIn("idx_threads_client", thread_indexes)
            self.assertIn("idx_threads_contractor", thread_indexes)
            client_unread_plan = " ".join(
                row[3]
                for row in connection.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT COUNT(*)
                    FROM threads
                    JOIN messages ON messages.thread_id = threads.id
                    LEFT JOIN thread_reads
                      ON thread_reads.thread_id = threads.id
                     AND thread_reads.user_id = ?
                    WHERE threads.client_id = ?
                      AND messages.is_hidden = 0
                      AND messages.sender_id != ?
                      AND messages.id > COALESCE(
                          thread_reads.last_read_message_id,
                          0
                      )
                    """,
                    (1, 1, 1),
                )
            )
            contractor_unread_plan = " ".join(
                row[3]
                for row in connection.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT COUNT(*)
                    FROM threads
                    JOIN messages ON messages.thread_id = threads.id
                    LEFT JOIN thread_reads
                      ON thread_reads.thread_id = threads.id
                     AND thread_reads.user_id = ?
                    WHERE threads.contractor_id = ?
                      AND messages.is_hidden = 0
                      AND messages.sender_id != ?
                      AND messages.id > COALESCE(
                          thread_reads.last_read_message_id,
                          0
                      )
                    """,
                    (1, 1, 1),
                )
            )
            self.assertIn("idx_threads_client", client_unread_plan)
            self.assertIn("idx_threads_contractor", contractor_unread_plan)
            self.assertIn("idx_messages_thread_unread", client_unread_plan)
            self.assertIn("idx_messages_thread_unread", contractor_unread_plan)
            self.assertNotIn("SCAN threads", client_unread_plan)
            self.assertNotIn("SCAN threads", contractor_unread_plan)
            message_listing_plan = " ".join(
                row[3]
                for row in connection.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT threads.id, last_visible.body,
                           last_visible.created_at,
                           last_visible.sender_id
                    FROM threads
                    JOIN jobs ON jobs.id = threads.job_id
                    JOIN users AS client ON client.id = threads.client_id
                    JOIN users AS contractor ON contractor.id = threads.contractor_id
                    LEFT JOIN messages AS last_visible
                      ON last_visible.id = (
                          SELECT messages.id FROM messages
                          WHERE messages.thread_id = threads.id
                            AND messages.is_hidden = 0
                          ORDER BY messages.id DESC
                          LIMIT 1
                      )
                    WHERE threads.client_id = ? OR threads.contractor_id = ?
                    ORDER BY COALESCE(last_visible.created_at, threads.created_at) DESC,
                             COALESCE(last_visible.id, 0) DESC
                    LIMIT 50
                    """,
                    (1, 1),
                )
            )
            self.assertIn("idx_threads_client", message_listing_plan)
            self.assertIn("idx_threads_contractor", message_listing_plan)
            self.assertIn("idx_messages_thread_unread", message_listing_plan)
            self.assertNotIn("SCAN threads", message_listing_plan)
            self.assertNotIn("SCAN messages", message_listing_plan)
            self.assertFalse(connection.execute("PRAGMA foreign_key_check").fetchall())
        finally:
            connection.close()

    def test_release_guards_immutable_baseline_and_duplicate_migrations(self):
        release_module = load_release_script()
        preflight_module = load_preflight_script()
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            migrations_dir = repo_root / "cloudflare" / "d1" / "migrations"
            migrations_dir.mkdir(parents=True)
            (migrations_dir / "0001_initial.sql").write_text(
                "CREATE TABLE example (id INTEGER PRIMARY KEY);\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "immutable 0001"):
                release_module.immutable_baseline_sql(repo_root)

            (migrations_dir / "0002_duplicate.sql").write_text(
                "ALTER TABLE example ADD COLUMN id INTEGER;\n",
                encoding="utf-8",
            )
            errors: list[str] = []
            checks: list[str] = []
            preflight_module.validate_fresh_d1_migration_chain(
                migrations_dir,
                errors,
                checks,
            )
            self.assertTrue(errors)
            self.assertIn("0002_duplicate.sql", errors[0])
            self.assertNotIn(
                "Fresh D1 database accepts the complete migration chain",
                checks,
            )

    def test_release_prep_preserves_real_d1_ids(self):
        module = load_release_script()
        database_id = "11111111-1111-4111-8111-111111111111"
        preview_database_id = "22222222-2222-4222-8222-222222222222"
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "cloudflare"
            output_root.mkdir(parents=True)
            (output_root / "wrangler.jsonc").write_text(
                json.dumps(
                    {
                        "d1_databases": [
                            {
                                "binding": "DB",
                                "database_name": "workdoe",
                                "database_id": database_id,
                                "preview_database_id": preview_database_id,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            result = module.prepare_release(ROOT, output_root)
            wrangler = json.loads(Path(result["wrangler"]).read_text(encoding="utf-8"))
        self.assertEqual(wrangler["d1_databases"][0]["database_id"], database_id)
        self.assertEqual(
            wrangler["d1_databases"][0]["preview_database_id"],
            preview_database_id,
        )

    def test_cloudflare_d1_id_helper_updates_wrangler_safely(self):
        module = load_d1_id_apply_script()
        database_id = "33333333-3333-4333-8333-333333333333"
        preview_database_id = "44444444-4444-4444-8444-444444444444"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            wrangler_path = tmp_path / "wrangler.jsonc"
            wrangler_path.write_text(
                (ROOT / "cloudflare" / "wrangler.jsonc").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            d1_output = tmp_path / "workdoe-d1.txt"
            d1_output.write_text(f"database_id = {database_id}\n", encoding="utf-8")
            preview_output = tmp_path / "workdoe-preview-d1.json"
            preview_output.write_text(
                json.dumps({"result": {"uuid": preview_database_id}}),
                encoding="utf-8",
            )
            result = module.apply_d1_ids(
                wrangler_path=wrangler_path,
                from_file=d1_output,
                preview_from_file=preview_output,
            )
            wrangler = json.loads(wrangler_path.read_text(encoding="utf-8"))

        self.assertTrue(result["changed"])
        self.assertEqual(wrangler["d1_databases"][0]["database_id"], database_id)
        self.assertEqual(
            wrangler["d1_databases"][0]["preview_database_id"],
            preview_database_id,
        )
        self.assertEqual(set(wrangler["secrets"]["required"]), {
            "CLERK_JWT_KEY",
            "CLERK_PUBLISHABLE_KEY",
            "CLERK_SECRET_KEY",
            "CLERK_WEBHOOK_SECRET",
            "WORKDOE_SECRET_KEY",
            "WORKDOE_TURNSTILE_SITE_KEY",
            "WORKDOE_TURNSTILE_SECRET_KEY",
        })
        with self.assertRaisesRegex(module.D1IdError, "placeholder"):
            module.normalized_uuid(module.ZERO_UUID)

    def test_cloudflare_resource_bootstrap_is_dry_run_by_default(self):
        module = load_resource_bootstrap_script()
        payload = module.plan_payload(ROOT)
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["executes_commands"])
        self.assertEqual(payload["service"], "workdoe")
        self.assertEqual(payload["domain"], "workdoe.com")
        names = [step["name"] for step in payload["steps"]]
        self.assertNotIn("create-d1-production", names)
        self.assertNotIn("create-d1-preview", names)
        self.assertNotIn("apply-d1-ids", names)
        self.assertIn("create-r2-media-bucket", names)
        self.assertIn("create-email-queue", names)
        self.assertIn("create-media-review-queue", names)
        self.assertIn("capture-secret-list", names)
        secret_step = next(step for step in payload["steps"] if step["name"] == "capture-secret-list")
        self.assertIn("cloudflare_secret_evidence.py", " ".join(secret_step["command"]))
        self.assertIn("--execute", secret_step["command"])
        self.assertIn("--yes", secret_step["command"])

    def test_cloudflare_resource_bootstrap_skips_d1_when_ids_are_configured(self):
        module = load_resource_bootstrap_script()
        wrangler = json.loads((ROOT / "cloudflare" / "wrangler.jsonc").read_text(encoding="utf-8"))
        wrangler["d1_databases"][0]["database_id"] = "11111111-2222-4333-8444-555555555555"
        wrangler["d1_databases"][0]["preview_database_id"] = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            cloudflare_dir = repo_root / "cloudflare"
            cloudflare_dir.mkdir()
            (cloudflare_dir / "wrangler.jsonc").write_text(
                json.dumps(wrangler),
                encoding="utf-8",
            )
            payload = module.plan_payload(repo_root)
        names = [step["name"] for step in payload["steps"]]
        self.assertTrue(payload["d1_ids_configured"])
        self.assertNotIn("create-d1-production", names)
        self.assertNotIn("create-d1-preview", names)
        self.assertNotIn("apply-d1-ids", names)
        self.assertIn("create-r2-media-bucket", names)

    def test_cloudflare_resource_bootstrap_requires_execute_confirmation(self):
        module = load_resource_bootstrap_script()
        original_argv = sys.argv
        try:
            sys.argv = ["cloudflare_resource_bootstrap.py", "--execute", "--json"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 2)
        finally:
            sys.argv = original_argv

    def test_cloudflare_resource_bootstrap_requires_api_token_before_execute(self):
        module = load_resource_bootstrap_script()
        original_argv = sys.argv
        original_token = os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        original_execute_steps = module.execute_steps
        try:
            module.execute_steps = lambda *args, **kwargs: self.fail("execute_steps should not run")
            sys.argv = [
                "cloudflare_resource_bootstrap.py",
                "--execute",
                "--yes",
                "--json",
                "--no-secret-probe",
            ]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(module.main(), 1)
            payload = json.loads(output.getvalue())
        finally:
            module.execute_steps = original_execute_steps
            sys.argv = original_argv
            if original_token is not None:
                os.environ["CLOUDFLARE_API_TOKEN"] = original_token

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["executes_commands"])
        self.assertIn("CLOUDFLARE_API_TOKEN is required", payload["errors"][0])
        self.assertIn("D1, R2, and Queue resources", payload["errors"][0])

    def test_cloudflare_wrangler_helpers_decode_cli_output_as_utf8(self):
        captured_kwargs = []

        class WranglerResult:
            returncode = 1
            stdout = ""
            stderr = "Cloudflare error"

        def fake_run(*args, **kwargs):
            captured_kwargs.append(kwargs)
            return WranglerResult()

        bootstrap_module = load_resource_bootstrap_script()
        deploy_module = load_production_deploy_script()
        secret_module = load_secret_evidence_script()
        original_bootstrap_run = bootstrap_module.subprocess.run
        original_deploy_run = deploy_module.subprocess.run
        original_secret_run = secret_module.subprocess.run
        try:
            bootstrap_module.subprocess.run = fake_run
            deploy_module.subprocess.run = fake_run
            secret_module.subprocess.run = fake_run
            bootstrap_module.run_external(
                bootstrap_module.BootstrapStep(
                    name="create-d1-production",
                    command=["wrangler", "d1", "create", "workdoe"],
                    cwd=str(ROOT / "cloudflare"),
                )
            )
            deploy_module.run_external(
                deploy_module.DeployStep(
                    name="deploy-worker",
                    command=["wrangler", "deploy"],
                    cwd=str(ROOT / "cloudflare"),
                )
            )
            secret_module.run_external()
        finally:
            bootstrap_module.subprocess.run = original_bootstrap_run
            deploy_module.subprocess.run = original_deploy_run
            secret_module.subprocess.run = original_secret_run

        self.assertEqual(len(captured_kwargs), 3)
        for kwargs in captured_kwargs:
            self.assertEqual(kwargs["encoding"], "utf-8")
            self.assertEqual(kwargs["errors"], "replace")

    def test_cloudflare_resource_bootstrap_treats_existing_r2_and_queues_as_done(self):
        module = load_resource_bootstrap_script()
        steps = [
            module.BootstrapStep(
                name="create-r2-media-bucket",
                command=["wrangler", "r2", "bucket", "create", "workdoe-media"],
                cwd=str(ROOT / "cloudflare"),
            ),
            module.BootstrapStep(
                name="create-email-queue",
                command=["wrangler", "queues", "create", "workdoe-email"],
                cwd=str(ROOT / "cloudflare"),
            ),
        ]

        class ExistingResourceResult:
            returncode = 1
            stdout = ""
            stderr = "A resource with this name already exists."

        original_run_external = module.run_external
        try:
            module.run_external = lambda step: ExistingResourceResult()
            executed, errors = module.execute_steps(steps)
        finally:
            module.run_external = original_run_external

        self.assertEqual(errors, [])
        self.assertEqual([step.status for step in executed], ["done-existing", "done-existing"])

    def test_cloudflare_resource_bootstrap_captures_successful_stderr_output(self):
        module = load_resource_bootstrap_script()
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "d1-output.txt"
            step = module.BootstrapStep(
                name="create-d1-production",
                command=["wrangler", "d1", "create", "workdoe"],
                cwd=str(ROOT / "cloudflare"),
                writes=str(capture_path),
            )

            class StderrSuccessResult:
                returncode = 0
                stdout = ""
                stderr = "database_id = 11111111-2222-4333-8444-555555555555"

            original_run_external = module.run_external
            try:
                module.run_external = lambda step: StderrSuccessResult()
                executed, errors = module.execute_steps([step])
            finally:
                module.run_external = original_run_external

            self.assertEqual(errors, [])
            self.assertEqual(executed[0].status, "done")
            self.assertEqual(
                capture_path.read_text(encoding="utf-8"),
                "database_id = 11111111-2222-4333-8444-555555555555",
            )

    def test_cloudflare_resource_bootstrap_delegates_secret_list_capture_to_sanitized_helper(self):
        module = load_resource_bootstrap_script()
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "secret-list.json"
            capture_path.write_text(
                json.dumps(
                    {
                        "source": "wrangler secret list --json",
                        "contains_values": False,
                        "result": [{"name": "CLERK_SECRET_KEY"}],
                    }
                ),
                encoding="utf-8",
            )
            step = module.BootstrapStep(
                name="capture-secret-list",
                command=[
                    sys.executable,
                    str(ROOT / "scripts" / "cloudflare_secret_evidence.py"),
                    "--execute",
                    "--yes",
                    "--output",
                    str(capture_path),
                ],
                cwd=str(ROOT),
                writes=str(capture_path),
                required=False,
            )

            class HelperSuccessResult:
                returncode = 0
                stdout = '{"ok": true, "writes": "secret-list.json"}'
                stderr = "wrangler warning: using production environment"

            original_run_external = module.run_external
            try:
                module.run_external = lambda step: HelperSuccessResult()
                executed, errors = module.execute_steps([step])
            finally:
                module.run_external = original_run_external

            self.assertEqual(errors, [])
            self.assertEqual(executed[0].status, "done")
            captured = capture_path.read_text(encoding="utf-8")
            self.assertEqual(json.loads(captured)["result"][0]["name"], "CLERK_SECRET_KEY")
            self.assertFalse(json.loads(captured)["contains_values"])
            self.assertNotIn("warning", captured)
            self.assertNotIn('"ok"', captured)

    def test_cloudflare_secret_evidence_helper_sanitizes_and_validates_names(self):
        module = load_secret_evidence_script()
        readiness = load_readiness_script()
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "cloudflare-secret-list.local.json"
            dry_run = module.dry_run_payload(output_path)
            self.assertTrue(dry_run["ok"])
            self.assertTrue(dry_run["dry_run"])
            self.assertFalse(dry_run["executes_commands"])
            self.assertFalse(output_path.exists())
            self.assertEqual(
                dry_run["command"][-4:],
                ["secret", "list", "--format", "json"],
            )

            complete_payload = {
                "result": [
                    {"name": name, "created_on": "2026-08-03T20:00:00Z"}
                    for name in sorted(readiness.REQUIRED_SECRETS)
                ]
            }

            class CompleteSecretListResult:
                returncode = 0
                stdout = json.dumps(complete_payload)
                stderr = "wrangler warning: using production environment"

            original_run_external = module.run_external
            try:
                module.run_external = lambda: CompleteSecretListResult()
                captured = module.capture_secret_evidence(output_path)
            finally:
                module.run_external = original_run_external

            self.assertTrue(captured["ok"], captured)
            self.assertTrue(captured["executes_commands"])
            self.assertEqual(captured["missing_secret_names"], [])
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(saved["contains_values"])
            self.assertEqual(
                {item["name"] for item in saved["result"]},
                readiness.REQUIRED_SECRETS,
            )
            self.assertNotIn("created_on", output_path.read_text(encoding="utf-8"))
            self.assertNotIn("warning", output_path.read_text(encoding="utf-8"))

            missing_payload = {"result": [{"name": "CLERK_SECRET_KEY"}]}

            class MissingSecretListResult:
                returncode = 0
                stdout = json.dumps(missing_payload)
                stderr = ""

            try:
                module.run_external = lambda: MissingSecretListResult()
                missing = module.capture_secret_evidence(output_path)
            finally:
                module.run_external = original_run_external
            self.assertFalse(missing["ok"])
            self.assertIn("WORKDOE_SECRET_KEY", missing["missing_secret_names"])

    def test_cloudflare_secret_evidence_requires_execute_confirmation(self):
        module = load_secret_evidence_script()
        original_argv = sys.argv
        try:
            sys.argv = ["cloudflare_secret_evidence.py", "--execute", "--json"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 2)
        finally:
            sys.argv = original_argv

    def test_cloudflare_secret_evidence_requires_api_token_before_execute(self):
        module = load_secret_evidence_script()
        original_argv = sys.argv
        original_token = os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        original_run_external = module.run_external
        try:
            module.run_external = lambda: self.fail("run_external should not run")
            sys.argv = ["cloudflare_secret_evidence.py", "--execute", "--yes", "--json"]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(module.main(), 1)
            payload = json.loads(output.getvalue())
        finally:
            module.run_external = original_run_external
            sys.argv = original_argv
            if original_token is not None:
                os.environ["CLOUDFLARE_API_TOKEN"] = original_token

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["executes_commands"])
        self.assertIn("CLOUDFLARE_API_TOKEN is required", payload["error"])
        self.assertIn("secret-name evidence", payload["error"])

    def test_cloudflare_release_evidence_validates_secret_names_and_clerk_proxy(self):
        module = load_release_evidence_script()
        readiness = load_readiness_script()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            secret_path = tmp_path / "cloudflare-secret-list.local.json"
            proof_path = tmp_path / "clerk-proxy-proof.local.json"
            secret_path.write_text(
                json.dumps(
                    {
                        "source": "wrangler secret list --json",
                        "contains_values": False,
                        "result": [
                            {"name": name}
                            for name in sorted(readiness.REQUIRED_SECRETS)
                        ],
                    }
                ),
                encoding="utf-8",
            )
            proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            result = module.run_release_evidence(
                secret_list_json=secret_path,
                clerk_proxy_proof_json=proof_path,
            )
            self.assertTrue(result["ok"], result)
            self.assertIn("Sanitized Cloudflare secret-name evidence is valid", result["checks"])
            self.assertIn(
                "Same-domain Clerk proxy release proof is valid",
                result["checks"],
            )

            secret_path.write_text(
                json.dumps(
                    {
                        "contains_values": True,
                        "result": [{"name": "CLERK_SECRET_KEY"}],
                    }
                ),
                encoding="utf-8",
            )
            invalid = module.run_release_evidence(
                secret_list_json=secret_path,
                clerk_proxy_proof_json=proof_path,
            )
            self.assertFalse(invalid["ok"])
            self.assertIn(
                "Cloudflare secret evidence must be sanitized with contains_values=false.",
                invalid["blockers"],
            )
            self.assertIn(
                "python scripts\\cloudflare_clerk_proxy_proof.py --confirm "
                "--confirm-restricted-sign-up --confirm-email-code-only --confirm-legal-consent",
                invalid["next_steps"],
            )

    def test_cloudflare_production_deploy_is_dry_run_by_default(self):
        module = load_production_deploy_script()
        with tempfile.TemporaryDirectory() as tmp:
            payload = module.plan_payload(
                ROOT,
                secret_list_json=Path(tmp) / "missing-secret-evidence.json",
            )
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["executes_commands"])
        self.assertEqual(payload["service"], "workdoe")
        self.assertEqual(payload["domain"], "workdoe.com")
        self.assertFalse(payload["ready_to_deploy"])
        self.assertNotIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            payload["strict_blockers"],
        )
        self.assertIn(
            "Cloudflare secret evidence must be sanitized with contains_values=false. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes`.",
            payload["strict_blockers"],
        )
        names = [step["name"] for step in payload["steps"]]
        self.assertEqual(
            names,
            [
                "apply-d1-migrations",
                "deploy-worker",
                "smoke-production",
            ],
        )
        migration_command = payload["steps"][0]["command"]
        self.assertIn("wrangler", Path(migration_command[0]).name.lower())
        self.assertEqual(
            migration_command[1:],
            ["d1", "migrations", "apply", "workdoe", "--remote"],
        )
        deploy_command = payload["steps"][1]["command"]
        self.assertIn("wrangler", Path(deploy_command[0]).name.lower())
        self.assertEqual(deploy_command[1:], ["deploy"])
        self.assertEqual(
            payload["steps"][2]["command"],
            [
                sys.executable,
                str(ROOT / "scripts" / "workdoe_production_smoke.py"),
                "--fail-when-not-ready",
                "--attempts",
                "6",
                "--retry-delay",
                "5",
            ],
        )
        self.assertTrue(payload["steps"][2]["required"])

    def test_cloudflare_production_deploy_requires_execute_confirmation(self):
        module = load_production_deploy_script()
        original_argv = sys.argv
        try:
            sys.argv = ["cloudflare_production_deploy.py", "--execute", "--json"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 2)
        finally:
            sys.argv = original_argv

    def test_cloudflare_production_deploy_blocks_when_strict_readiness_fails(self):
        module = load_production_deploy_script()
        original_argv = sys.argv
        with tempfile.TemporaryDirectory() as tmp:
            try:
                sys.argv = [
                    "cloudflare_production_deploy.py",
                    "--execute",
                    "--yes",
                    "--json",
                    "--secret-list-json",
                    str(Path(tmp) / "missing-secret-evidence.json"),
                ]
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(module.main(), 1)
                payload = json.loads(stdout.getvalue())
            finally:
                sys.argv = original_argv
        self.assertFalse(payload["ok"])
        self.assertIn("Strict production readiness failed", payload["error"])
        self.assertIn(
            "Cloudflare secret evidence must be sanitized with contains_values=false. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes`.",
            payload["blockers"],
        )

    def test_cloudflare_production_deploy_records_capped_smoke_output(self):
        module = load_production_deploy_script()
        steps = [
            module.DeployStep(
                name="smoke-production",
                command=[sys.executable, "scripts/workdoe_production_smoke.py"],
                cwd=str(ROOT),
                required=True,
            ),
        ]

        class SmokeResult:
            returncode = 0
            stdout = "HTTP/2 200 OK\ncache-control: no-store"
            stderr = ""

        original_run_external = module.run_external
        try:
            module.run_external = lambda step: SmokeResult()
            executed, errors, warnings = module.execute_steps(steps)
        finally:
            module.run_external = original_run_external

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual([step.status for step in executed], ["done"])
        self.assertIn("HTTP/2 200 OK", executed[0].output_excerpt)

        long_result = type(
            "LongSmokeResult",
            (),
            {"returncode": 0, "stdout": "x" * (module.SMOKE_OUTPUT_MAX + 20), "stderr": ""},
        )()
        self.assertTrue(module.smoke_output_excerpt(long_result).endswith("[truncated]"))

    def test_cloudflare_production_deploy_rejects_smoke_bypass(self):
        module = load_production_deploy_script()
        original_argv = sys.argv
        try:
            sys.argv = [
                "cloudflare_production_deploy.py",
                "--execute",
                "--yes",
                "--json",
                "--no-smoke",
            ]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(module.main(), 2)
            payload = json.loads(output.getvalue())
        finally:
            sys.argv = original_argv

        self.assertFalse(payload["ok"])
        self.assertEqual(
            payload["error"],
            "Production execution requires the post-deploy smoke check.",
        )

    def test_cloudflare_production_deploy_requires_api_token_after_readiness(self):
        module = load_production_deploy_script()
        original_argv = sys.argv
        original_token = os.environ.pop("CLOUDFLARE_API_TOKEN", None)
        original_readiness_payload = module.readiness_payload
        original_execute_steps = module.execute_steps
        try:
            module.readiness_payload = lambda *args, **kwargs: {
                "ready": True,
                "blockers": [],
                "warnings": ["Confirm admin@workdoe.com is monitored."],
            }
            module.execute_steps = lambda *args, **kwargs: self.fail("execute_steps should not run")
            sys.argv = ["cloudflare_production_deploy.py", "--execute", "--yes", "--json"]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(module.main(), 1)
            payload = json.loads(output.getvalue())
        finally:
            module.execute_steps = original_execute_steps
            module.readiness_payload = original_readiness_payload
            sys.argv = original_argv
            if original_token is not None:
                os.environ["CLOUDFLARE_API_TOKEN"] = original_token

        self.assertFalse(payload["ok"])
        self.assertFalse(payload["executes_commands"])
        self.assertIn("CLOUDFLARE_API_TOKEN is required", payload["error"])
        self.assertIn("deploy the Cloudflare Worker", payload["error"])

    def test_cloudflare_clerk_proxy_proof_helper_is_confirm_gated(self):
        module = load_clerk_proxy_proof_script()
        readiness = load_readiness_script()
        package_scripts = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))[
            "scripts"
        ]
        self.assertNotIn("--confirm", package_scripts["cf:clerk:proof"])
        self.assertIn("--confirm", package_scripts["cf:clerk:proof:confirm"])
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "clerk-proxy-proof.local.json"
            dry_run = module.dry_run_payload(
                output_path,
                "workdoe.com",
                "https://workdoe.com/__clerk",
            )
            self.assertTrue(dry_run["ok"])
            self.assertTrue(dry_run["dry_run"])
            self.assertFalse(dry_run["executes_commands"])
            self.assertFalse(output_path.exists())

            with self.assertRaisesRegex(module.ClerkProxyProofError, "Use --confirm"):
                module.build_proof(confirmed=False)
            with self.assertRaisesRegex(module.ClerkProxyProofError, "Restricted sign-up"):
                module.build_proof(confirmed=True)
            with self.assertRaisesRegex(
                module.ClerkProxyProofError,
                "https://workdoe.com/__clerk",
            ):
                module.build_proof(
                    proxy_url="https://clerk.workdoe.com",
                    confirmed=True,
                )
            with self.assertRaisesRegex(module.ClerkProxyProofError, "Legal requires express consent"):
                module.build_proof(
                    confirmed=True,
                    restricted_sign_up_mode=True,
                    email_code_sign_in=True,
                    password_sign_in_disabled=True,
                )
            with self.assertRaisesRegex(module.ClerkProxyProofError, "Terms URL"):
                module.build_proof(
                    confirmed=True,
                    restricted_sign_up_mode=True,
                    email_code_sign_in=True,
                    password_sign_in_disabled=True,
                    express_legal_consent=True,
                    terms_url="https://example.com/terms",
                )

            proof = module.build_proof(
                confirmed=True,
                restricted_sign_up_mode=True,
                email_code_sign_in=True,
                password_sign_in_disabled=True,
                express_legal_consent=True,
                checked_by="release-test",
                confirmed_at_utc="2026-08-03T20:00:00Z",
            )
            module.write_proof(output_path, proof)
            self.assertEqual(readiness.clerk_proxy_proof_error(output_path), "")
            confirmed = module.confirmed_payload(output_path, proof)
            self.assertTrue(confirmed["ok"])
            self.assertFalse(confirmed["dry_run"])
            self.assertTrue(confirmed["executes_commands"])
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["domain"], "workdoe.com")
            self.assertEqual(saved["frontend_api_proxy_url"], "https://workdoe.com/__clerk")
            self.assertTrue(saved["restricted_sign_up_mode"])
            self.assertTrue(saved["email_code_sign_in"])
            self.assertTrue(saved["password_sign_in_disabled"])
            self.assertEqual(saved["custom_sign_up_url"], "https://workdoe.com/create-account")
            self.assertTrue(saved["express_legal_consent"])
            self.assertEqual(saved["terms_url"], "https://workdoe.com/terms")
            self.assertEqual(saved["privacy_url"], "https://workdoe.com/privacy")
            self.assertEqual(saved["checked_by"], "release-test")

    def test_cloudflare_worker_entrypoint_covers_automation_handlers(self):
        entrypoint = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("class Default(WorkerEntrypoint)", entrypoint)
        self.assertIn("async def scheduled(self, controller, env, ctx):", entrypoint)
        self.assertIn("async def queue(self, batch):", entrypoint)
        self.assertIn("def json_response", entrypoint)
        self.assertIn("authenticated_write_rate_limit_response", entrypoint)
        self.assertIn("WRITE_RATE_LIMITER", entrypoint)
        self.assertIn("status=429", entrypoint)
        self.assertIn('"Retry-After": "60"', entrypoint)
        self.assertIn("Request body must include Content-Length.", entrypoint)
        self.assertIn("async def request_form_data", entrypoint)
        self.assertIn("Request body must use form encoding.", entrypoint)
        self.assertIn("Image uploads must include Content-Length.", entrypoint)
        self.assertIn("handle_clerk_webhook", entrypoint)
        self.assertIn("CLERK_WEBHOOK_SECRET is required", entrypoint)
        self.assertIn("MAX_CLERK_WEBHOOK_BODY_BYTES", entrypoint)
        self.assertIn("Webhook requests must include Content-Length.", entrypoint)
        self.assertIn("Webhook request body is too large.", entrypoint)
        self.assertIn("verify_svix_signature", entrypoint)
        self.assertIn("clerk-webhook-rejected", entrypoint)
        self.assertIn("clerk-webhook-verified", entrypoint)
        self.assertIn("sync_linked_clerk_user", entrypoint)
        self.assertIn("email-conflict", entrypoint)
        self.assertIn("no-linked-workdoe-user", entrypoint)
        self.assertIn("expire_local_auth_tokens", entrypoint)
        self.assertIn("queue_stale_match_reminders", entrypoint)
        self.assertIn("queue_moderation_digest", entrypoint)
        self.assertIn("automation_events", entrypoint)
        self.assertIn("/api/jobs/open", entrypoint)

        self.assertIn("public_open_jobs", entrypoint)
        self.assertIn("public_job_filters_from_query", entrypoint)
        self.assertIn("public_jobs_payload", entrypoint)
        self.assertIn("jobs.status = 'open'", entrypoint)
        self.assertIn("jobs.zip_code LIKE ?", entrypoint)
        self.assertIn("Cache-Control", entrypoint)
        self.assertIn("public_https_redirect_url", entrypoint)
        self.assertIn("PUBLIC_HTTPS_HOSTS", entrypoint)
        self.assertIn("Strict-Transport-Security", entrypoint)
        self.assertIn("is_static_asset_path", entrypoint)
        self.assertIn('"/workdoe-share.png"', entrypoint)
        self.assertIn("ENTRY_ROUTES", entrypoint)
        self.assertIn("/create-account", entrypoint)
        self.assertIn("/post-project", entrypoint)
        self.assertIn("entry_shell", entrypoint)
        self.assertIn("build_entry_shell_html", entrypoint)
        self.assertIn("entry_shell_jobs", entrypoint)
        self.assertIn("Entry pages accept GET only.", entrypoint)
        self.assertIn("clerk_production_configuration_ready", entrypoint)
        self.assertIn("Clerk production authentication is not configured.", entrypoint)
        self.assertIn("is_app_shell_route", entrypoint)
        self.assertIn("app_shell", entrypoint)
        self.assertIn("dashboard_path_for_user", entrypoint)
        self.assertIn("admin_dashboard_html", entrypoint)
        self.assertIn("admin_dashboard_payload", entrypoint)
        self.assertIn("client_dashboard_html", entrypoint)
        self.assertIn("client_request_inbox_html", entrypoint)
        self.assertIn("client_job_detail_html", entrypoint)
        self.assertIn("lead_board_html", entrypoint)
        self.assertIn("job_form_html", entrypoint)
        self.assertIn("contractor_profile_html", entrypoint)
        self.assertIn("public_contractor_profile_html", entrypoint)
        self.assertIn("contractor_job_detail_html", entrypoint)
        self.assertIn("message_threads_html", entrypoint)
        self.assertIn("message_thread_detail_html", entrypoint)
        self.assertIn("parse_app_client_job_id", entrypoint)
        self.assertIn("parse_app_client_job_edit_id", entrypoint)
        self.assertIn("parse_app_contractor_id", entrypoint)
        self.assertIn("parse_app_thread_id", entrypoint)
        self.assertIn("contractor_profile_page", entrypoint)
        self.assertIn("message_threads_for_user", entrypoint)
        self.assertIn("message_threads_listing_payload", entrypoint)
        self.assertIn("/client/jobs/", entrypoint)
        self.assertIn("/contractors/", entrypoint)
        self.assertIn("/messages/", entrypoint)
        self.assertIn("App pages accept GET only.", entrypoint)
        self.assertIn("/api/client/jobs", entrypoint)
        self.assertIn("client_jobs", entrypoint)
        self.assertIn("client_jobs_for_user", entrypoint)
        self.assertIn("client_jobs_payload", entrypoint)
        self.assertIn("can_view_client_jobs", entrypoint)
        self.assertIn("Only active client accounts can view client jobs.", entrypoint)
        self.assertIn("/api/client/jobs/", entrypoint)
        self.assertIn("client_job_requests", entrypoint)
        self.assertIn("client_requests_for_job", entrypoint)
        self.assertIn("client_job_requests_payload", entrypoint)
        self.assertIn("can_view_client_job_requests", entrypoint)
        self.assertIn("Only the owning client can review mini bids for this job.", entrypoint)
        self.assertIn("/api/contractor/leads", entrypoint)
        self.assertIn("contractor_leads", entrypoint)
        self.assertIn("contractor_leads_for_user", entrypoint)
        self.assertIn("contractor_leads_payload", entrypoint)
        self.assertIn("can_view_contractor_leads", entrypoint)
        self.assertIn("Only active contractor accounts can view leads.", entrypoint)
        self.assertIn("/api/contractor/bids", entrypoint)
        self.assertIn("contractor_bids", entrypoint)
        self.assertIn("contractor_bids_for_user", entrypoint)
        self.assertIn("contractor_bids_payload", entrypoint)
        self.assertIn("can_view_contractor_bids", entrypoint)
        self.assertIn("Only active contractor accounts can view mini bids.", entrypoint)
        self.assertIn("job_detail", entrypoint)
        self.assertIn("parse_job_detail_id", entrypoint)
        self.assertIn("can_view_job_detail", entrypoint)
        self.assertIn("job_detail_payload", entrypoint)
        self.assertIn("job_photos_for_detail", entrypoint)
        self.assertIn("contractor_request_for_job", entrypoint)
        self.assertIn("update_job_status", entrypoint)
        self.assertIn("parse_job_status_path", entrypoint)
        self.assertIn("can_update_job_status", entrypoint)
        self.assertIn("job_status_response", entrypoint)
        self.assertIn("job-closed", entrypoint)
        self.assertIn("job-reopened", entrypoint)
        self.assertIn("Hidden jobs cannot be changed by clients.", entrypoint)
        self.assertIn("/api/jobs", entrypoint)
        self.assertIn("create_job", entrypoint)
        self.assertIn("update_job", entrypoint)
        self.assertIn("job_post_payload", entrypoint)
        self.assertIn("parse_job_update_id", entrypoint)
        self.assertIn("can_update_job", entrypoint)
        self.assertIn("verify_turnstile_for_request", entrypoint)
        self.assertIn("WORKDOE_TURNSTILE_SECRET_KEY", entrypoint)
        self.assertIn("job-created", entrypoint)
        self.assertIn("job-updated", entrypoint)
        self.assertIn("create_match_request", entrypoint)
        self.assertIn("parse_match_request_job_id", entrypoint)
        self.assertIn("match_request_payload", entrypoint)
        self.assertIn("Only contractor accounts can send mini bids.", entrypoint)
        self.assertIn("match-request-created", entrypoint)
        self.assertIn("INSERT OR IGNORE INTO match_requests", entrypoint)
        self.assertIn("AND jobs.status = 'open'", entrypoint)
        self.assertIn("decide_match_request", entrypoint)
        self.assertIn("parse_match_decision_path", entrypoint)
        self.assertIn("can_decide_match_request", entrypoint)
        self.assertIn("ensure_thread_for_match", entrypoint)
        self.assertIn("APPROVAL_THREAD_MESSAGE", entrypoint)
        self.assertIn("match-request-approved", entrypoint)
        self.assertIn("match-request-rejected", entrypoint)
        self.assertIn("INSERT OR IGNORE INTO threads", entrypoint)
        self.assertIn("/api/messages/threads", entrypoint)
        self.assertIn("message_threads_api", entrypoint)
        self.assertIn("message_threads_listing_payload", entrypoint)
        self.assertIn("can_view_thread", entrypoint)
        self.assertIn("can_send_thread_message", entrypoint)
        self.assertIn("message_body_payload", entrypoint)
        self.assertIn("message-created", entrypoint)
        self.assertIn("/api/reports", entrypoint)
        self.assertIn("create_report", entrypoint)
        self.assertIn("report_payload", entrypoint)
        self.assertIn("report_target_visible_to_user", entrypoint)
        self.assertIn("JOIN threads ON threads.id = messages.thread_id", entrypoint)
        self.assertIn("report-created", entrypoint)
        self.assertIn("/api/admin/", entrypoint)
        self.assertIn("admin_moderation_action", entrypoint)
        self.assertIn("parse_admin_moderation_path", entrypoint)
        self.assertIn("can_admin_moderate", entrypoint)
        self.assertIn("admin_update_statement", entrypoint)
        self.assertIn("insert_moderation_action", entrypoint)
        self.assertIn("admin-moderation-action", entrypoint)
        self.assertIn(
            "Admin account status must be changed through the operator recovery process.",
            entrypoint,
        )
        self.assertIn("/api/auth/session", entrypoint)
        self.assertIn("verify_clerk_session_token", entrypoint)
        self.assertIn("onboarding_required", entrypoint)
        self.assertIn("auth_provider = 'clerk'", entrypoint)
        self.assertIn("external_subject = ?", entrypoint)
        self.assertIn("/api/auth/onboard", entrypoint)
        self.assertIn("onboarding_payload", entrypoint)
        self.assertIn("https://api.clerk.com/v1/users/", entrypoint)
        self.assertIn("claims_with_verified_clerk_email", entrypoint)
        self.assertIn("https://api.clerk.com/v1/sessions/", entrypoint)
        self.assertIn("clerk-session-revoke-failed", entrypoint)
        self.assertIn("login_code_consume_result", entrypoint)
        self.assertIn("AND expires_at >= ?", entrypoint)
        self.assertIn("AND attempt_count < ?", entrypoint)
        self.assertIn("ensure_role_profile", entrypoint)
        self.assertIn(
            "__session=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax",
            entrypoint,
        )
        self.assertIn("INSERT OR IGNORE INTO users", entrypoint)
        self.assertIn("INSERT OR IGNORE INTO client_profiles", entrypoint)
        self.assertIn("INSERT OR IGNORE INTO contractor_profiles", entrypoint)
        self.assertIn("A Workdoe account already uses this email.", entrypoint)
        self.assertIn("clerk-onboarding-linked", entrypoint)
        self.assertIn("/api/contractor/profile", entrypoint)
        self.assertIn("contractor_profile_api", entrypoint)
        self.assertIn("contractor_profile_payload", entrypoint)
        self.assertIn("can_update_contractor_profile", entrypoint)
        self.assertIn("upsert_contractor_profile", entrypoint)
        self.assertIn("contractor-profile-updated", entrypoint)
        self.assertIn("/api/client/profile", entrypoint)
        self.assertIn("client_profile_api", entrypoint)
        self.assertIn("can_update_client_profile", entrypoint)
        self.assertIn("upsert_client_profile", entrypoint)
        self.assertIn("client-profile-updated", entrypoint)
        self.assertIn("/api/client/locations", entrypoint)
        self.assertIn("client_saved_locations_api", entrypoint)
        self.assertIn("WHERE id = ? AND client_id = ?", entrypoint)
        self.assertIn("client-saved-location-created", entrypoint)
        self.assertIn("client-saved-location-deleted", entrypoint)
        self.assertIn("client_profiles.notification_preference", entrypoint)
        self.assertIn("client_profiles.email_reminder_consent_at IS NOT NULL", entrypoint)
        self.assertIn("client/profile#bid-reminders", entrypoint)
        self.assertIn("/api/contractors/", entrypoint)
        self.assertIn("public_contractor_profile", entrypoint)
        self.assertIn("parse_public_contractor_id", entrypoint)
        self.assertIn("can_view_public_contractor_profile", entrypoint)
        self.assertIn("public_contractor_for_profile", entrypoint)
        self.assertIn("visible_contractor_profile_photos", entrypoint)
        self.assertIn("env.EMAIL.send", entrypoint)
        self.assertIn("self.env.EMAIL_QUEUE.send", entrypoint)
        self.assertIn("process_email_queue_message", entrypoint)
        self.assertIn("email-message-sent", entrypoint)
        self.assertIn("email-message-invalid", entrypoint)
        self.assertIn("email-message-send-failed", entrypoint)
        self.assertIn("record_event_best_effort", entrypoint)
        self.assertIn("ack_message", entrypoint)
        self.assertIn("retry_message", entrypoint)
        self.assertIn("/media/jobs/", entrypoint)
        self.assertIn("/media/contractors/", entrypoint)
        self.assertIn("private_job_photo", entrypoint)
        self.assertIn("private_contractor_photo", entrypoint)
        self.assertIn("safe_media_key", entrypoint)
        self.assertIn("can_view_job_photo", entrypoint)
        self.assertIn("can_view_contractor_photo", entrypoint)
        self.assertIn("self.env.MEDIA.get", entrypoint)
        self.assertIn("private, no-store", entrypoint)
        self.assertIn("/api/media/jobs/", entrypoint)
        self.assertIn("/api/media/contractors/", entrypoint)
        self.assertIn("request.formData", entrypoint)
        self.assertIn("self.env.MEDIA.put", entrypoint)
        self.assertIn("self.env.MEDIA.delete", entrypoint)
        self.assertIn("MEDIA_QUEUE.send", entrypoint)
        self.assertIn("media-uploaded", entrypoint)
        self.assertIn("rollback_media_upload", entrypoint)
        self.assertIn("metadata_cleanup", entrypoint)
        self.assertIn("object_cleanup", entrypoint)
        self.assertIn("media-review-queued", entrypoint)
        self.assertIn("process_media_review_queue_message", entrypoint)
        self.assertIn("media-review-message-accepted", entrypoint)

    def test_cloudflare_form_reader_bounds_public_project_drafts(self):
        module = load_worker_entry_module()

        class StubRequest:
            def __init__(self, headers):
                self.headers = headers
                self.form_calls = 0

            async def formData(self):
                self.form_calls += 1
                return {"service_slug": "lawn-mowing"}

        missing_length = StubRequest(
            {"Content-Type": "application/x-www-form-urlencoded"}
        )
        with self.assertRaisesRegex(
            module.OnboardingError,
            "Request body must include Content-Length",
        ):
            asyncio.run(module.request_form_data(missing_length, max_bytes=128))
        self.assertEqual(missing_length.form_calls, 0)

        oversized = StubRequest(
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "129",
            }
        )
        with self.assertRaisesRegex(module.OnboardingError, "too large"):
            asyncio.run(module.request_form_data(oversized, max_bytes=128))
        self.assertEqual(oversized.form_calls, 0)

        wrong_type = StubRequest(
            {"Content-Type": "text/plain", "Content-Length": "20"}
        )
        with self.assertRaisesRegex(module.OnboardingError, "form encoding"):
            asyncio.run(module.request_form_data(wrong_type, max_bytes=128))
        self.assertEqual(wrong_type.form_calls, 0)

        accepted = StubRequest(
            {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Content-Length": "64",
            }
        )
        parsed = asyncio.run(module.request_form_data(accepted, max_bytes=128))
        self.assertEqual(parsed["service_slug"], "lawn-mowing")
        self.assertEqual(accepted.form_calls, 1)

    def test_successful_email_is_acked_before_best_effort_audit(self):
        entrypoint = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(
            encoding="utf-8"
        )
        start = entrypoint.index("async def process_email_queue_message")
        end = entrypoint.index("\n\nasync def process_media_review_queue_message", start)
        consumer = entrypoint[start:end]
        send_index = consumer.index("result = await env.EMAIL.send(email_message)")
        ack_index = consumer.rindex("ack_message(message)")
        audit_index = consumer.index('"email-message-sent"', ack_index)
        self.assertLess(send_index, ack_index)
        self.assertLess(ack_index, audit_index)

    def test_cloudflare_media_access_helper_keeps_r2_routes_private(self):
        module = load_media_access_module()
        self.assertEqual(module.media_scope_from_path("/media/jobs/12"), ("job", 12))
        self.assertEqual(
            module.media_scope_from_path("/media/contractors/7"),
            ("contractor", 7),
        )
        with self.assertRaises(module.MediaAccessError):
            module.media_scope_from_path("/media/jobs/0")
        with self.assertRaises(module.MediaAccessError):
            module.media_scope_from_path("/media/jobs/../../secret")

        self.assertEqual(
            module.safe_media_key("jobs/12/photo.webp", "jobs/12"),
            "jobs/12/photo.webp",
        )
        unsafe_keys = [
            "/jobs/12/photo.webp",
            "jobs/12/../photo.webp",
            "jobs\\12\\photo.webp",
            "jobs/13/photo.webp",
            "jobs/12//photo.webp",
        ]
        for key in unsafe_keys:
            with self.subTest(key=key), self.assertRaises(module.MediaAccessError):
                module.safe_media_key(key, "jobs/12")

        admin = {"id": 1, "role": "admin", "status": "active"}
        client = {"id": 2, "role": "client", "status": "active"}
        contractor = {"id": 3, "role": "contractor", "status": "active"}
        suspended = {"id": 4, "role": "contractor", "status": "suspended"}
        job_photo = {
            "client_id": 2,
            "client_status": "active",
            "status": "open",
            "is_hidden": 0,
            "has_approved_match": 0,
        }
        self.assertTrue(module.can_view_job_photo(admin, {**job_photo, "is_hidden": 1}))
        self.assertTrue(module.can_view_job_photo(client, job_photo))
        self.assertTrue(module.can_view_job_photo(contractor, job_photo))
        self.assertFalse(module.can_view_job_photo(None, job_photo))
        self.assertFalse(module.can_view_job_photo(suspended, job_photo))
        self.assertFalse(
            module.can_view_job_photo(
                contractor,
                {**job_photo, "status": "closed", "has_approved_match": 0},
            )
        )
        self.assertFalse(
            module.can_view_job_photo(
                contractor,
                {
                    **job_photo,
                    "client_status": "suspended",
                    "has_approved_match": 1,
                },
            )
        )
        self.assertTrue(
            module.can_view_job_photo(
                contractor,
                {**job_photo, "status": "closed", "has_approved_match": 1},
            )
        )

        public_photo = {"contractor_id": 3, "status": "active", "is_hidden": 0}
        hidden_photo = {"contractor_id": 3, "status": "active", "is_hidden": 1}
        inactive_photo = {"contractor_id": 3, "status": "suspended", "is_hidden": 0}
        self.assertTrue(module.can_view_contractor_photo(None, public_photo))
        self.assertFalse(module.can_view_contractor_photo(None, hidden_photo))
        self.assertFalse(module.can_view_contractor_photo(None, inactive_photo))
        self.assertTrue(module.can_view_contractor_photo(contractor, hidden_photo))
        self.assertTrue(module.can_view_contractor_photo(admin, inactive_photo))

    def test_cloudflare_media_upload_helper_validates_r2_uploads_and_review_payloads(self):
        module = load_media_uploads_module()
        self.assertEqual(
            module.media_upload_scope_from_path("/api/media/jobs/12/upload"),
            ("job", 12),
        )
        self.assertEqual(
            module.media_upload_scope_from_path("/api/media/contractors/7/upload"),
            ("contractor", 7),
        )
        with self.assertRaises(module.MediaUploadError):
            module.media_upload_scope_from_path("/api/media/jobs/0/upload")

        details = module.safe_upload_metadata(
            "../Storefront Window.PNG",
            "image/png",
            "4096",
        )
        self.assertEqual(details["original_filename"], "Storefront Window.PNG")
        self.assertEqual(details["extension"], "png")
        self.assertEqual(details["content_type"], "image/png")
        self.assertEqual(details["size_bytes"], 4096)
        self.assertTrue(
            module.image_signature_matches("png", b"\x89PNG\r\n\x1a\nmore")
        )
        self.assertTrue(module.image_signature_matches("jpg", b"\xff\xd8\xff\xe0more"))
        self.assertTrue(module.image_signature_matches("gif", b"GIF89amore"))
        self.assertTrue(
            module.image_signature_matches("webp", b"RIFF\x04\x00\x00\x00WEBP")
        )
        self.assertFalse(module.image_signature_matches("png", b"<html>"))
        self.assertFalse(module.image_signature_matches("webp", b"RIFFbad-data"))
        self.assertEqual(
            module.upload_http_metadata(details)["cacheControl"],
            "private, no-store",
        )
        self.assertEqual(
            module.upload_http_metadata(details)["contentDisposition"],
            'inline; filename="workdoe-upload.png"',
        )
        for filename, mime, size in (
            ("photo.svg", "image/svg+xml", 200),
            ("photo.jpg", "image/png", 200),
            ("photo.webp", "image/webp", module.MAX_UPLOAD_BYTES + 1),
            ("photo.gif", "image/gif", 0),
        ):
            with self.subTest(
                filename=filename, mime=mime, size=size
            ), self.assertRaises(module.MediaUploadError):
                module.safe_upload_metadata(filename, mime, size)

        key = module.build_r2_upload_key("job", 12, "png")
        self.assertRegex(key, r"^jobs/12/[0-9a-f]{32}\.png$")

        transform_options = []
        output_options = []

        class FakeImageFile:
            def stream(self):
                return "fresh-upload-stream"

        class FakeImageResponse:
            ok = True

            async def arrayBuffer(self):
                return SimpleNamespace(byteLength=8192)

        class FakeImageResult:
            def response(self):
                return FakeImageResponse()

        class FakeTransformer:
            def transform(self, options):
                transform_options.append(options)
                return self

            async def output(self, options):
                output_options.append(options)
                return FakeImageResult()

        class FakeImagesBinding:
            async def info(self, stream):
                self.info_stream = stream
                return {"width": 4032, "height": 3024}

            def input(self, stream):
                self.input_stream = stream
                return FakeTransformer()

        binding = FakeImagesBinding()
        sanitized = asyncio.run(
            module.sanitize_uploaded_image(binding, FakeImageFile(), lambda value: value)
        )
        self.assertEqual(binding.info_stream, "fresh-upload-stream")
        self.assertEqual(binding.input_stream, "fresh-upload-stream")
        self.assertEqual(
            transform_options,
            [{"width": 2400, "height": 2400, "fit": "scale-down", "metadata": "none"}],
        )
        self.assertEqual(
            output_options,
            [{"format": "image/webp", "quality": 82, "anim": False}],
        )
        sanitized_details = module.sanitized_upload_details(details, sanitized)
        self.assertEqual(sanitized_details["extension"], "webp")
        self.assertEqual(sanitized_details["content_type"], "image/webp")
        self.assertEqual(sanitized_details["size_bytes"], 8192)
        self.assertEqual(sanitized_details["source_width"], 4032)
        self.assertEqual(sanitized_details["source_height"], 3024)
        self.assertEqual(sanitized_details["sanitization"], "cloudflare-images-webp")

        class InvalidImagesBinding(FakeImagesBinding):
            async def info(self, stream):
                raise ValueError("decode failed")

        with self.assertRaisesRegex(module.MediaUploadError, "could not be decoded"):
            asyncio.run(
                module.sanitize_uploaded_image(
                    InvalidImagesBinding(),
                    FakeImageFile(),
                    lambda value: value,
                )
            )

        job_sql, job_params = module.media_metadata_delete_statement(
            "job",
            9,
            4,
            "jobs/4/workdoe.jpg",
        )
        self.assertEqual(
            job_sql,
            "DELETE FROM job_photos WHERE id = ? AND job_id = ? AND stored_path = ?",
        )
        self.assertEqual(job_params, (9, 4, "jobs/4/workdoe.jpg"))
        contractor_sql, contractor_params = module.media_metadata_delete_statement(
            "contractor",
            11,
            7,
            "contractors/7/workdoe.webp",
        )
        self.assertEqual(
            contractor_sql,
            "DELETE FROM contractor_photos WHERE id = ? AND contractor_id = ? AND stored_path = ?",
        )
        self.assertEqual(
            contractor_params,
            (11, 7, "contractors/7/workdoe.webp"),
        )
        with self.assertRaisesRegex(module.MediaUploadError, "cleanup identifiers"):
            module.media_metadata_delete_statement("job", 0, 4, "jobs/4/workdoe.jpg")

        js_stub = ModuleType("js")

        class FakeUint8Array:
            @staticmethod
            def new(value):
                return SimpleNamespace(to_py=lambda: list(value))

        class FakeFile:
            def __init__(self, content):
                self.content = content

            def slice(self, start, end):
                content = self.content[start:end]
                return SimpleNamespace(arrayBuffer=lambda: async_bytes(content))

        async def async_bytes(value):
            return value

        js_stub.Uint8Array = FakeUint8Array
        previous_js = sys.modules.get("js")
        sys.modules["js"] = js_stub
        try:
            asyncio.run(
                module.validate_uploaded_file_signature(
                    FakeFile(b"\x89PNG\r\n\x1a\nmore"),
                    "png",
                )
            )
            with self.assertRaisesRegex(module.MediaUploadError, "does not match"):
                asyncio.run(
                    module.validate_uploaded_file_signature(
                        FakeFile(b"<html>"),
                        "png",
                    )
                )
        finally:
            if previous_js is None:
                sys.modules.pop("js", None)
            else:
                sys.modules["js"] = previous_js

        client = {"id": 2, "role": "client", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        contractor = {"id": 3, "role": "contractor", "status": "active"}
        suspended = {"id": 4, "role": "client", "status": "suspended"}
        job = {"id": 12, "client_id": 2, "status": "open"}
        self.assertTrue(module.can_upload_job_photo(client, job))
        self.assertTrue(module.can_upload_job_photo(admin, job))
        self.assertFalse(module.can_upload_job_photo(contractor, job))
        self.assertFalse(module.can_upload_job_photo(suspended, job))
        self.assertTrue(
            module.can_upload_contractor_photo(contractor, {"contractor_id": 3})
        )
        self.assertFalse(module.can_upload_contractor_photo(client, {"contractor_id": 3}))

        payload = module.media_review_payload(
            "job",
            photo_id=44,
            owner_id=12,
            uploaded_by=2,
            stored_path=key,
            details=details,
        )
        validated = module.validated_media_review_payload(payload)
        self.assertEqual(validated["scope"], "job")
        self.assertEqual(validated["photo_id"], 44)
        self.assertEqual(
            validated["checks"],
            [
                "cloudflare-images-decode",
                "metadata-stripped",
                "animation-flattened",
                "moderation",
            ],
        )
        with self.assertRaises(module.MediaUploadError):
            module.validated_media_review_payload({**payload, "stored_path": "jobs/13/bad.png"})

    def test_cloudflare_media_upload_rollback_cleans_d1_and_r2(self):
        module = load_worker_entry_module()
        deleted_metadata = []

        class FakeMedia:
            def __init__(self):
                self.deleted = []

            async def delete(self, key):
                self.deleted.append(key)

        worker = module.Default()
        worker.env = SimpleNamespace(MEDIA=FakeMedia())

        async def delete_metadata(scope, owner_id, photo_id, key):
            deleted_metadata.append((scope, owner_id, photo_id, key))

        worker.delete_media_metadata = delete_metadata
        result = asyncio.run(
            worker.rollback_media_upload(
                "job",
                12,
                44,
                "jobs/12/workdoe.png",
            )
        )
        self.assertEqual(result["metadata_cleanup"], "deleted")
        self.assertEqual(result["object_cleanup"], "deleted")
        self.assertEqual(
            deleted_metadata,
            [("job", 12, 44, "jobs/12/workdoe.png")],
        )
        self.assertEqual(worker.env.MEDIA.deleted, ["jobs/12/workdoe.png"])

        no_artifacts = asyncio.run(worker.rollback_media_upload("job", 12, None, ""))
        self.assertEqual(no_artifacts["metadata_cleanup"], "not-created")
        self.assertEqual(no_artifacts["object_cleanup"], "not-created")

    def test_cloudflare_public_trust_routes_serve_get_head_and_discovery_types(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace()

        class Request:
            def __init__(self, method):
                self.method = method

        privacy = asyncio.run(worker.public_trust_page(Request("GET"), "/privacy"))
        terms_head = asyncio.run(worker.public_trust_page(Request("HEAD"), "/terms"))
        rejected = asyncio.run(worker.public_trust_page(Request("POST"), "/privacy"))
        self.assertEqual(privacy.status, 200)
        self.assertIn("<h1>Privacy Policy</h1>", privacy.body)
        self.assertEqual(terms_head.status, 200)
        self.assertEqual(terms_head.body, "")
        self.assertEqual(rejected.status, 405)

        robots = asyncio.run(
            worker.public_discovery_file(Request("GET"), "/robots.txt")
        )
        sitemap = asyncio.run(
            worker.public_discovery_file(Request("GET"), "/sitemap.xml")
        )
        security = asyncio.run(
            worker.public_discovery_file(
                Request("GET"), "/.well-known/security.txt"
            )
        )
        self.assertEqual(robots.status, 200)
        self.assertEqual(robots.headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("Disallow: /api/", robots.body)
        self.assertEqual(sitemap.headers["Content-Type"], "application/xml; charset=utf-8")
        self.assertIn("https://workdoe.com/privacy", sitemap.body)
        self.assertIn("Contact: mailto:admin@workdoe.com", security.body)

    def test_cloudflare_signed_in_project_draft_preserves_selected_family(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(DB=object())

        async def signed_in_client(_request):
            return {"id": 12, "role": "client", "status": "active"}

        worker.optional_workdoe_user = signed_in_client
        request = SimpleNamespace(
            method="GET",
            url="https://workdoe.com/post-project?family=outdoor-yard",
        )
        response = asyncio.run(worker.public_job_draft(request))

        self.assertEqual(response.status, 303)
        self.assertEqual(response.headers["Location"], "/jobs/new?family=outdoor-yard")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_cloudflare_repeated_match_decisions_are_idempotent_or_conflict(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace()
        repaired = []

        async def no_existing_thread(env, request_id):
            return None

        async def repair_thread(env, match, created_at):
            repaired.append((match["id"], created_at))
            return 77

        module.existing_thread_id_for_match = no_existing_thread
        module.ensure_thread_for_match = repair_thread
        approved_match = {
            "id": 42,
            "job_id": 12,
            "client_id": 8,
            "contractor_id": 7,
            "status": "approved",
        }
        repeated = asyncio.run(
            worker.existing_match_decision_response(
                approved_match,
                42,
                requested_status="approved",
            )
        )
        self.assertEqual(repeated.status, 200)
        self.assertEqual(json.loads(repeated.body)["thread_id"], 77)
        self.assertEqual(repaired[0][0], 42)

        conflicting = asyncio.run(
            worker.existing_match_decision_response(
                approved_match,
                42,
                requested_status="rejected",
            )
        )
        self.assertEqual(conflicting.status, 409)
        self.assertEqual(json.loads(conflicting.body)["status"], "approved")

    def test_cloudflare_approval_closes_other_pending_offers(self):
        module = load_worker_entry_module()
        worker = module.Default()
        worker.env = SimpleNamespace(DB=object())
        calls = []
        events = []

        async def signed_in_client(_request):
            return {"id": 8, "role": "client", "status": "active"}

        async def pending_match(_env, _request_id):
            return {
                "id": 42,
                "job_id": 12,
                "client_id": 8,
                "contractor_id": 7,
                "status": "pending",
            }

        async def fake_db_run(_env, query, *bindings):
            calls.append((query, bindings))
            changes = 2 if "AND id != ?" in query else 1
            return {"meta": {"changes": changes}}

        async def create_thread(_env, _match, _created_at):
            return 77

        async def capture_event(_env, event_type, **kwargs):
            events.append((event_type, kwargs))

        worker.optional_workdoe_user = signed_in_client
        module.match_request_for_decision = pending_match
        module.db_run = fake_db_run
        module.ensure_thread_for_match = create_thread
        module.record_event = capture_event

        response = asyncio.run(
            worker.decide_match_request(
                SimpleNamespace(method="POST"),
                "/api/match-requests/42/approve",
            )
        )
        payload = json.loads(response.body)
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["status"], "approved")
        self.assertEqual(payload["thread_id"], 77)
        self.assertIn("approved_request.status = 'approved'", calls[0][0])
        self.assertIn("AND id != ?", calls[1][0])
        self.assertEqual(calls[1][1][1:], (12, 42))
        self.assertEqual(
            events[0][1]["payload"]["closed_offer_count"],
            2,
        )

    def test_cloudflare_email_payloads_are_transactional_and_sanitized(self):
        module = load_email_payloads_module()
        reminder = module.build_email_message(
            {
                "type": "stale-match-reminder",
                "to": " Client@Example.com ",
                "job_title": "<Paint lobby>",
                "location": "Arlington, VA",
                "contractor_name": "Jordan <script>",
            },
            from_email="no-reply@workdoe.com",
        )
        self.assertEqual(reminder["to"], "client@example.com")
        self.assertEqual(reminder["from"], "no-reply@workdoe.com")
        self.assertIn("Mini bid waiting", reminder["subject"])
        self.assertIn("&lt;Paint lobby&gt;", reminder["html"])
        self.assertNotIn("<script>", reminder["html"])
        self.assertIn("Sign in to Workdoe", reminder["text"])
        self.assertIn(
            "https://workdoe.com/client/profile#bid-reminders",
            reminder["text"],
        )
        self.assertIn("Manage bid reminder emails", reminder["html"])

        repeat_invitation = module.build_email_message(
            {
                "type": "repeat-provider-invitation",
                "to": " Contractor@Example.com ",
                "job_title": "<Fresh patio wash>",
                "location": "Washington, DC",
                "job_url": "https://workdoe.com/jobs/61",
                "consumer_name": "Must not appear",
                "prior_address": "Must not appear",
                "prior_bid": "$1",
            }
        )
        self.assertEqual(repeat_invitation["to"], "contractor@example.com")
        self.assertIn("New Workdoe project invitation", repeat_invitation["subject"])
        self.assertIn("&lt;Fresh patio wash&gt;", repeat_invitation["html"])
        self.assertIn("https://workdoe.com/jobs/61", repeat_invitation["text"])
        self.assertIn("fresh mini bid", repeat_invitation["text"])
        self.assertNotIn("Must not appear", repeat_invitation["text"])
        self.assertNotIn("$1", repeat_invitation["html"])

        new_lead = module.build_email_message(
            {
                "type": "contractor-new-lead",
                "to": "contractor@example.com",
                "job_title": "<Front walk wash>",
                "service_name": "Pressure washing",
                "location": "Washington, DC",
                "job_url": "https://workdoe.com/jobs/72",
                "settings_url": "https://workdoe.com/leads#saved-lead-alerts",
                "client_email": "must-not-appear@example.com",
                "zip_code": "20003",
                "description": "Private scope must not appear",
            }
        )
        self.assertIn("New matching Workdoe project", new_lead["subject"])
        self.assertIn("&lt;Front walk wash&gt;", new_lead["html"])
        self.assertIn("Pressure washing", new_lead["text"])
        self.assertIn("https://workdoe.com/jobs/72", new_lead["text"])
        self.assertIn("Manage matching project emails", new_lead["html"])
        self.assertNotIn("must-not-appear", new_lead["text"])
        self.assertNotIn("20003", new_lead["html"])
        self.assertNotIn("Private scope", new_lead["text"])

        login_code = module.build_email_message(
            {
                "type": "login-code",
                "to": " Contractor@Example.com ",
                "code": "123456",
                "intent": "find work",
                "expires_minutes": "10",
            }
        )
        self.assertEqual(login_code["to"], "contractor@example.com")
        self.assertIn("Workdoe sign-in code", login_code["subject"])
        self.assertIn("123456", login_code["text"])
        self.assertIn("find work", login_code["html"])
        self.assertIn("ignore this email", login_code["text"])

        reset = module.build_email_message(
            {
                "type": "password-reset",
                "to": "client@example.com",
                "reset_url": "https://workdoe.com/reset-password/token_123",
                "expires_minutes": 30,
            }
        )
        self.assertIn("Reset your Workdoe password", reset["subject"])
        self.assertIn("https://workdoe.com/reset-password/token_123", reset["text"])
        self.assertIn("expires in 30 minutes", reset["html"])

        digest = module.build_email_message(
            {
                "type": "moderation-digest",
                "summary": {
                    "open_reports": "2",
                    "hidden_job_photos": 1,
                    "hidden_contractor_photos": None,
                    "hidden_messages": "bad",
                    "suspended_users": 3,
                },
            },
            admin_email="admin@workdoe.com",
        )
        self.assertEqual(digest["to"], "admin@workdoe.com")
        self.assertIn("Open reports: 2", digest["text"])
        self.assertIn("Hidden messages", digest["html"])

        with self.assertRaisesRegex(module.EmailPayloadError, "Unsupported"):
            module.build_email_message({"type": "newsletter", "to": "client@example.com"})
        with self.assertRaisesRegex(module.EmailPayloadError, "recipient"):
            module.build_email_message({"type": "stale-match-reminder", "to": "nope"})
        with self.assertRaisesRegex(module.EmailPayloadError, "6-digit"):
            module.build_email_message(
                {"type": "login-code", "to": "client@example.com", "code": "12345"}
            )
        with self.assertRaisesRegex(module.EmailPayloadError, "workdoe.com"):
            module.build_email_message(
                {
                    "type": "password-reset",
                    "to": "client@example.com",
                    "reset_url": "https://evil.example/reset-password/token_123",
                }
            )
        with self.assertRaisesRegex(module.EmailPayloadError, "workdoe.com"):
            module.build_email_message(
                {
                    "type": "stale-match-reminder",
                    "to": "client@example.com",
                    "preferences_url": "https://evil.example/client/profile#bid-reminders",
                }
            )
        with self.assertRaisesRegex(module.EmailPayloadError, "workdoe.com"):
            module.build_email_message(
                {
                    "type": "repeat-provider-invitation",
                    "to": "contractor@example.com",
                    "job_url": "https://evil.example/jobs/61",
                }
            )
        with self.assertRaisesRegex(module.EmailPayloadError, "one Workdoe project"):
            module.build_email_message(
                {
                    "type": "repeat-provider-invitation",
                    "to": "contractor@example.com",
                    "job_url": "https://workdoe.com/jobs/61?address=private",
                }
            )
        with self.assertRaisesRegex(module.EmailPayloadError, "workdoe.com"):
            module.build_email_message(
                {
                    "type": "contractor-new-lead",
                    "to": "contractor@example.com",
                    "job_url": "https://evil.example/jobs/72",
                }
            )
        with self.assertRaisesRegex(module.EmailPayloadError, "Workdoe lead alerts"):
            module.build_email_message(
                {
                    "type": "contractor-new-lead",
                    "to": "contractor@example.com",
                    "job_url": "https://workdoe.com/jobs/72",
                    "settings_url": "https://workdoe.com/leads?email=on#saved-lead-alerts",
                }
            )

    def test_cloudflare_email_audit_metadata_redacts_authentication_material(self):
        module = load_email_payloads_module()
        payload = {
            "type": "login-code",
            "to": "Person@Example.com",
            "code": "123456",
            "reset_url": "https://workdoe.com/reset-password/private-token",
            "text": "private message body",
        }
        metadata = module.email_audit_metadata(payload, "s" * 32)
        serialized = json.dumps(metadata, sort_keys=True)

        self.assertEqual(metadata["type"], "login-code")
        self.assertTrue(metadata["recipient_present"])
        self.assertEqual(len(metadata["recipient_hash"]), 64)
        self.assertNotIn("person@example.com", serialized.lower())
        self.assertNotIn("123456", serialized)
        self.assertNotIn("private-token", serialized)
        self.assertNotIn("private message body", serialized)

    def test_cloudflare_repeat_invitation_email_queue_is_audited_and_non_blocking(self):
        module = load_worker_entry_module()
        sent = []
        events = []

        async def fake_db_run(_env, _sql, *_params):
            return {"results": [{"email": "contractor@example.com"}]}

        async def fake_record_event_best_effort(
            _env,
            event_type,
            target_type="",
            target_id=None,
            payload=None,
            status="queued",
        ):
            events.append(
                {
                    "event_type": event_type,
                    "target_type": target_type,
                    "target_id": target_id,
                    "payload": payload or {},
                    "status": status,
                }
            )
            return True

        class EmailQueue:
            async def send(self, payload):
                sent.append(payload)

        module.db_run = fake_db_run
        module.record_event_best_effort = fake_record_event_best_effort
        env = SimpleNamespace(EMAIL_QUEUE=EmailQueue(), WORKDOE_SECRET_KEY="s" * 32)
        queued = asyncio.run(
            module.queue_repeat_provider_invitation_email(
                env,
                contractor_id=22,
                job_id=61,
                job_title="Fresh patio wash",
                city="Washington",
                state="DC",
            )
        )
        self.assertTrue(queued)
        self.assertEqual(sent[0]["type"], "repeat-provider-invitation")
        self.assertEqual(sent[0]["job_url"], "https://workdoe.com/jobs/61")
        self.assertEqual(sent[0]["location"], "Washington, DC")
        self.assertEqual(events[0]["event_type"], "repeat-provider-invitation-email")
        self.assertIn("recipient_hash", events[0]["payload"])
        self.assertNotIn("to", events[0]["payload"])
        self.assertNotIn("job_title", events[0]["payload"])

        class FailingEmailQueue:
            async def send(self, _payload):
                raise RuntimeError("queue unavailable")

        events.clear()
        failed_env = SimpleNamespace(
            EMAIL_QUEUE=FailingEmailQueue(),
            WORKDOE_SECRET_KEY="s" * 32,
        )
        queued = asyncio.run(
            module.queue_repeat_provider_invitation_email(
                failed_env,
                contractor_id=22,
                job_id=62,
                job_title="Fresh patio wash",
                city="Washington",
                state="DC",
            )
        )
        self.assertFalse(queued)
        self.assertEqual(
            events[0]["event_type"],
            "repeat-provider-invitation-email-queue-failed",
        )
        self.assertEqual(events[0]["status"], "failed")
        self.assertEqual(events[0]["payload"], {"error_type": "RuntimeError"})

    def test_cloudflare_new_lead_alert_fanout_is_fit_bound_and_redacted(self):
        module = load_worker_entry_module()
        sent = []
        db_calls = []
        events = []

        async def fake_db_run(_env, sql, *params):
            db_calls.append((sql, params))
            if "FROM jobs" in sql and "contractor_lead_preferences" in sql:
                return {
                    "results": [
                        {
                            "job_id": 72,
                            "job_title": "Front walk wash",
                            "category": "Power washing",
                            "service_slug": "pressure-washing",
                            "city": "Washington",
                            "state": "DC",
                            "contractor_id": 22,
                            "contractor_email": "contractor@example.com",
                            "delivery_id": None,
                            "delivery_status": None,
                        }
                    ]
                }
            if "SELECT id, status" in sql:
                return {"results": [{"id": 91, "status": "pending"}]}
            return {"meta": {"changes": 1}}

        async def fake_record_event_best_effort(
            _env,
            event_type,
            target_type="",
            target_id=None,
            payload=None,
            status="queued",
        ):
            events.append(
                {
                    "event_type": event_type,
                    "target_type": target_type,
                    "target_id": target_id,
                    "payload": payload or {},
                    "status": status,
                }
            )
            return True

        class EmailQueue:
            async def send(self, payload):
                sent.append(payload)

        module.db_run = fake_db_run
        module.record_event_best_effort = fake_record_event_best_effort
        env = SimpleNamespace(EMAIL_QUEUE=EmailQueue(), WORKDOE_SECRET_KEY="s" * 32)
        queued_count = asyncio.run(
            module.process_contractor_lead_alert_fanout(env, 72)
        )
        self.assertEqual(queued_count, 1)
        self.assertEqual(sent[0]["type"], "contractor-new-lead")
        self.assertEqual(sent[0]["job_url"], "https://workdoe.com/jobs/72")
        self.assertEqual(sent[0]["location"], "Washington, DC")
        self.assertEqual(sent[0]["service_name"], "Pressure washing")
        self.assertEqual(sent[0]["lead_alert_delivery_id"], 91)
        serialized = json.dumps(sent[0], sort_keys=True)
        self.assertNotIn("zip", serialized.lower())
        self.assertNotIn("client", serialized.lower())
        self.assertNotIn("description", serialized.lower())
        self.assertTrue(
            any("contractor_service_capabilities" in sql for sql, _params in db_calls)
        )
        self.assertTrue(
            any("contractor_service_zones" in sql for sql, _params in db_calls)
        )
        self.assertEqual(events[0]["event_type"], "contractor-new-lead-email")
        self.assertIn("recipient_hash", events[0]["payload"])
        self.assertNotIn("to", events[0]["payload"])

        result = module.email_send_result_summary(
            {
                "messageId": "provider-message-1",
                "delivered": True,
                "permanent_bounces": ["private@example.com"],
                "debug": {"authorization": "secret"},
            }
        )
        self.assertEqual(result["messageId"], "provider-message-1")
        self.assertTrue(result["delivered"])
        self.assertEqual(result["permanent_bounce_count"], 1)
        self.assertNotIn("private@example.com", json.dumps(result))
        self.assertNotIn("authorization", result)

        entrypoint = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('payload={"body": body', entrypoint)
        self.assertNotIn('"to": email_message.get("to")', entrypoint)
        self.assertNotIn('"subject": email_message.get("subject")', entrypoint)

    def test_clerk_onboarding_helper_requires_verified_email_and_role(self):
        module = load_clerk_onboarding_module()
        trusted_claims = module.claims_with_verified_clerk_email(
            {"sub": "user_123", "sid": "sess_123"},
            {
                "primary_email_address_id": "idn_123",
                "email_addresses": [
                    {
                        "id": "idn_123",
                        "email_address": "Verified@Example.com",
                        "verification": {"status": "verified"},
                    }
                ],
            },
        )
        self.assertEqual(trusted_claims["email"], "verified@example.com")
        self.assertIs(trusted_claims["email_verified"], True)
        with self.assertRaisesRegex(module.OnboardingError, "verified Clerk email"):
            module.claims_with_verified_clerk_email(
                {"sub": "user_123"},
                {
                    "email_addresses": [
                        {
                            "id": "idn_bad",
                            "email_address": "bad@example.com",
                            "verification": {"status": "unverified"},
                        }
                    ]
                },
            )
        payload = module.onboarding_payload(
            {
                "sub": "user_workdoe_123",
                "email": " Contractor@Workdoe.com ",
                "email_verified": True,
            },
            {
                "role": " Contractor ",
                "display_name": "  Jordan   Rivera  ",
                "company_name": "  Rivera   Exterior Care  ",
            },
        )
        self.assertEqual(
            payload,
            {
                "email": "contractor@workdoe.com",
                "role": "contractor",
                "display_name": "Jordan Rivera",
                "company_name": "Rivera Exterior Care",
            },
        )

        fallback = module.onboarding_payload(
            {"primary_email": "client@workdoe.com", "name": "Avery Client"},
            {"role": "client"},
        )
        self.assertEqual(fallback["display_name"], "Avery Client")
        self.assertEqual(fallback["company_name"], "Avery Client")

        with self.assertRaisesRegex(module.OnboardingError, "email"):
            module.onboarding_payload({"sub": "user_123"}, {"role": "client"})
        with self.assertRaisesRegex(module.OnboardingError, "verified"):
            module.onboarding_payload(
                {"email": "client@workdoe.com", "email_verified": False},
                {"role": "client"},
            )
        with self.assertRaisesRegex(module.OnboardingError, "Role"):
            module.onboarding_payload(
                {"email": "client@workdoe.com"},
                {"role": "admin"},
            )

    def test_clerk_session_helper_extracts_and_validates_session_tokens(self):
        module = load_clerk_sessions_module()
        source = CLERK_SESSIONS_PATH.read_text(encoding="utf-8")
        self.assertIn('to_js(["verify"])', source)
        self.assertIn("Clerk session signature verification failed.", source)
        dev_env = SimpleNamespace(
            WORKDOE_ENV="development",
            WORKDOE_PUBLIC_URL="https://workdoe.com",
            WORKDOE_DOMAIN="workdoe.com",
        )
        self.assertIn(
            "http://127.0.0.1:8792",
            module.authorized_parties_from_env(
                dev_env,
                "http://127.0.0.1:8792/api/auth/session",
            ),
        )
        production_env = SimpleNamespace(
            WORKDOE_ENV="production",
            WORKDOE_PUBLIC_URL="https://workdoe.com",
            WORKDOE_DOMAIN="workdoe.com",
        )
        self.assertNotIn(
            "http://127.0.0.1:8792",
            module.authorized_parties_from_env(
                production_env,
                "http://127.0.0.1:8792/api/auth/session",
            ),
        )
        token = fake_session_token()
        self.assertEqual(
            module.extract_clerk_session_token(
                {"Authorization": f"Bearer {token}", "Cookie": "__session=ignored"}
            ),
            token,
        )
        self.assertEqual(
            module.extract_clerk_session_token({"Cookie": f"theme=dark; __session={token}"}),
            token,
        )

        header, claims, signing_input, signature = module.decode_unverified_jwt(token)
        self.assertEqual(header["alg"], "RS256")
        self.assertEqual(claims["sub"], "user_workdoe_123")
        self.assertTrue(signing_input.count(".") == 1)
        self.assertEqual(signature, b"workdoe-signature")
        validated = module.validate_clerk_session_claims(
            claims,
            authorized_parties=["https://workdoe.com"],
            now=1700000000,
        )
        self.assertEqual(validated["sid"], "sess_workdoe_123")

    def test_clerk_session_helper_fails_closed_for_bad_claims_or_signatures(self):
        module = load_clerk_sessions_module()
        token = fake_session_token()

        async def accepts_signature(jwt_key, signing_input, signature):
            return jwt_key == "pem-key" and signature == b"workdoe-signature"

        verified = asyncio.run(
            module.verify_clerk_session_token(
                token,
                jwt_key="pem-key",
                authorized_parties=["https://workdoe.com"],
                now=1700000000,
                signature_verifier=accepts_signature,
            )
        )
        self.assertEqual(verified["sub"], "user_workdoe_123")

        async def rejects_signature(jwt_key, signing_input, signature):
            return False

        with self.assertRaisesRegex(module.SessionVerificationError, "signature"):
            asyncio.run(
                module.verify_clerk_session_token(
                    token,
                    jwt_key="pem-key",
                    authorized_parties=["https://workdoe.com"],
                    now=1700000000,
                    signature_verifier=rejects_signature,
                )
            )
        with self.assertRaisesRegex(module.SessionVerificationError, "RS256"):
            module.decode_unverified_jwt(fake_session_token(header={"alg": "none"}))
        with self.assertRaisesRegex(module.SessionVerificationError, "expired"):
            module.validate_clerk_session_claims(
                {"sub": "user_workdoe_123", "sid": "sess_workdoe_123", "exp": 10, "nbf": 1},
                authorized_parties=["https://workdoe.com"],
                now=1700000000,
            )
        with self.assertRaisesRegex(module.SessionVerificationError, "authorized party"):
            module.validate_clerk_session_claims(
                {
                    "sub": "user_workdoe_123",
                    "sid": "sess_workdoe_123",
                    "exp": 1700000300,
                    "nbf": 1699999700,
                    "azp": "https://evil.example",
                },
                authorized_parties=["https://workdoe.com"],
                now=1700000000,
            )
        with self.assertRaisesRegex(module.SessionVerificationError, "pending"):
            module.validate_clerk_session_claims(
                {
                    "sub": "user_workdoe_123",
                    "sid": "sess_workdoe_123",
                    "exp": 1700000300,
                    "nbf": 1699999700,
                    "sts": "pending",
                },
                authorized_parties=["https://workdoe.com"],
                now=1700000000,
            )

    def test_cloudflare_public_jobs_payload_matches_map_privacy_contract(self):
        module = load_public_jobs_module()
        self.assertEqual(module.parse_public_limit("999"), 50)
        self.assertEqual(module.parse_public_limit("0"), 1)
        self.assertEqual(module.parse_public_limit("bad"), 24)
        self.assertEqual(module.normalize_public_sort("random"), "newest")
        filters = module.public_job_filters_from_query(
            {
                "category": ["Painting"],
                "family": ["remodel-finish"],
                "service": ["interior-painting"],
                "q": ["  Arlington   VA  "],
                "sort": ["soonest"],
            }
        )
        self.assertEqual(
            filters,
            {
                "category": "Painting",
                "family": "remodel-finish",
                "service": "interior-painting",
                "q": "Arlington VA",
                "sort": "soonest",
            },
        )
        self.assertEqual(
            module.public_job_filters_from_query(
                {
                    "category": ["Unknown"],
                    "family": ["unknown-family"],
                    "q": ["A" * 120],
                    "sort": ["bad"],
                }
            ),
            {
                "category": "",
                "family": "",
                "service": "",
                "q": "A" * 80,
                "sort": "newest",
            },
        )
        self.assertEqual(
            module.public_job_filters_from_query(
                {"service": ["pressure-washing"]}
            ),
            {
                "category": "",
                "family": "outdoor-yard",
                "service": "pressure-washing",
                "q": "",
                "sort": "newest",
            },
        )
        self.assertEqual(
            module.public_job_filters_from_query(
                {
                    "family": ["cleaning-upkeep"],
                    "service": ["pressure-washing"],
                }
            )["service"],
            "",
        )

        payload = module.public_jobs_payload(
            [
                {
                    "id": 9,
                    "title": "Paint stairwell",
                    "category": "Painting",
                    "service_group_slug": "remodel-finish",
                    "service_slug": "interior-painting",
                    "city": "Arlington",
                    "state": "VA",
                    "zip_code": "22201",
                    "description": "Paint the stairwell walls and trim.",
                    "license_preference": 1,
                    "client_email": "client@example.com",
                    "approx_lat": 38.8871,
                    "approx_lng": -77.0932,
                },
                {
                    "id": 10,
                    "title": "Missing map pin",
                    "category": "Painting",
                    "city": "Fairfax",
                    "state": "VA",
                    "approx_lat": None,
                    "approx_lng": None,
                },
            ],
            filters=filters,
            target="login",
        )
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["view"], "all")
        self.assertEqual(
            payload["location_privacy"],
            "Approximate city or ZIP-level pins only.",
        )
        job = payload["jobs"][0]
        self.assertEqual(job["action_label"], "Sign in")
        self.assertEqual(job["url"], "/login?next=/jobs/9")
        self.assertNotIn("zip_code", job)
        self.assertNotIn("description", job)
        self.assertNotIn("client_email", job)
        self.assertEqual(job["service_group_slug"], "remodel-finish")
        self.assertEqual(job["service_name"], "Interior painting")
        self.assertTrue(job["license_preference"])

        sample = module.public_job_payload(
            {
                "id": "demo-1",
                "is_demo": True,
                "title": "Sample project",
                "description": "Controlled sample description.",
            }
        )
        self.assertEqual(sample["description"], "Controlled sample description.")
        app_shell_source = APP_SHELL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "Do not include an exact street address, email, or phone number.",
            app_shell_source,
        )

    def test_cloudflare_public_job_query_is_indexed_and_emits_safe_cost_telemetry(self):
        module = load_public_job_query_module()
        filters = {
            "category": "Painting",
            "family": "remodel-finish",
            "service": "interior-painting",
            "q": "Arlington private search",
            "sort": "newest",
        }
        viewport = {
            "north": 39.5,
            "south": 38.0,
            "east": -76.2,
            "west": -78.0,
        }
        query, bindings = module.build_public_open_jobs_query(
            filters,
            viewport,
            order_clause="jobs.created_at DESC, jobs.id DESC",
            limit=24,
            cursor_offset=48,
        )
        self.assertIn("jobs.approx_lat BETWEEN ? AND ?", query)
        self.assertIn("jobs.approx_lng BETWEEN ? AND ?", query)
        self.assertIn("JOIN users AS clients", query)
        self.assertIn("clients.status = 'active'", query)
        self.assertIn("approved_request.status = 'approved'", query)
        self.assertEqual(bindings[-2:], [25, 48])
        with self.assertRaisesRegex(module.PublicJobQueryError, "sort order"):
            module.build_public_open_jobs_query(
                filters,
                viewport,
                order_clause="jobs.created_at DESC; DROP TABLE jobs",
                limit=24,
                cursor_offset=0,
            )

        telemetry = module.public_query_telemetry(
            {
                "meta": {
                    "rows_read": 31,
                    "rows_written": 0,
                    "duration": 1.25,
                }
            },
            returned_rows=24,
            filters=filters,
            viewport_applied=True,
            cursor_offset=48,
        )
        self.assertEqual(telemetry["rows_read"], 31)
        self.assertEqual(telemetry["returned_rows"], 24)
        self.assertTrue(telemetry["viewport_applied"])
        serialized = json.dumps(telemetry, sort_keys=True)
        self.assertNotIn("Arlington private search", serialized)
        self.assertNotIn("north", serialized)

        completed = subprocess.run(
            [sys.executable, "scripts/verify_d1_query_plan.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        plan = json.loads(completed.stdout)
        self.assertEqual(
            plan["used_indexes"],
            [
                "idx_contractor_photos_public_contractor",
                "idx_job_photos_public_job",
                "idx_jobs_open_geo",
            ],
        )
        self.assertEqual(plan["table_scans"], [])
        self.assertEqual(
            plan["last_migration"],
            "0034_project_license_preference.sql",
        )

    def test_cloudflare_suspended_client_projects_fail_closed(self):
        source = WORKER_ENTRY_PATH.read_text(encoding="utf-8")

        entry_jobs = source[
            source.index("async def entry_shell_jobs") : source.index(
                "\n\nasync def contractor_leads_for_user"
            )
        ]
        contractor_leads = source[
            source.index("async def contractor_leads_for_user") : source.index(
                "\n\nasync def contractor_bids_for_user"
            )
        ]
        create_match = source[
            source.index("    async def create_match_request") : source.index(
                "\n    async def decide_match_request"
            )
        ]
        private_photo = source[
            source.index("    async def private_job_photo") : source.index(
                "\n    async def private_contractor_photo"
            )
        ]
        job_detail = source[
            source.index("async def job_for_detail") : source.index(
                "\n\nasync def job_photos_for_detail"
            )
        ]

        for query_block in (entry_jobs, contractor_leads):
            with self.subTest(query=query_block.splitlines()[0]):
                self.assertIn("JOIN users AS clients", query_block)
                self.assertIn("clients.status = 'active'", query_block)
        self.assertIn("JOIN users AS clients", create_match)
        self.assertIn("AND clients.status = 'active'", create_match)
        self.assertIn("AND EXISTS (", create_match)
        self.assertIn("clients.status AS client_status", private_photo)
        self.assertIn("users.status AS client_status", job_detail)

    def test_demo_projects_are_realistic_labeled_and_filterable(self):
        module = load_demo_projects_module()
        projects = module.demo_projects_for_filters({})
        self.assertEqual(len(projects), 15)
        self.assertEqual(len({project["id"] for project in projects}), 15)
        for project in projects:
            self.assertTrue(project["id"].startswith("demo-"))
            self.assertTrue(project["is_demo"])
            self.assertTrue(project["title"])
            self.assertTrue(project["category"])
            self.assertTrue(project["budget"])
            self.assertTrue(project["description"])
            self.assertIsInstance(project["approx_lat"], float)
            self.assertIsInstance(project["approx_lng"], float)
            self.assertNotIn("address", project)
            self.assertNotIn("email", project)
        painting = module.demo_projects_for_filters({"category": "Painting"})
        self.assertEqual(len(painting), 1)
        self.assertEqual(painting[0]["city"], "Columbia")
        arlington = module.demo_projects_for_filters({"q": "Arlington"})
        self.assertEqual(len(arlington), 1)
        self.assertEqual(arlington[0]["category"], "Window cleaning")
        outdoor = module.demo_projects_for_filters({"family": "outdoor-yard"})
        self.assertEqual(len(outdoor), 5)
        self.assertTrue(
            all(project["service_group_slug"] == "outdoor-yard" for project in outdoor)
        )
        pressure_washing = module.demo_projects_for_filters(
            {"family": "outdoor-yard", "service": "pressure-washing"}
        )
        self.assertTrue(pressure_washing)
        self.assertTrue(
            all(
                project["service_slug"] == "pressure-washing"
                for project in pressure_washing
            )
        )
        limited_samples = module.guest_project_rows([], {}, limit=1)
        self.assertEqual(len(limited_samples), 1)
        self.assertEqual(limited_samples[0]["id"], "demo-01")
        combined = module.guest_project_rows(
            [{"id": 42, "title": "Live project"}],
            {},
            limit=3,
        )
        self.assertEqual([project["id"] for project in combined], [42, "demo-01", "demo-02"])
        self.assertEqual(module.guest_project_rows([], {}, limit=0), [])

    def test_cloudflare_entry_shell_mounts_same_domain_clerk_and_live_jobs(self):
        module = load_entry_shell_module()
        self.assertEqual(module.normalize_intent(None, "/login"), "find-work")
        self.assertEqual(module.normalize_intent(None, "/start"), "post-job")
        self.assertIn("/post-project", module.ENTRY_ROUTES)
        self.assertEqual(
            module.entry_redirect_url("/post-project", {}, "post-job", ""),
            "/jobs/new",
        )
        self.assertEqual(
            module.entry_redirect_url(
                "/post-project",
                {
                    "family": ["outdoor-yard"],
                    "service": ["pressure-washing"],
                },
                "post-job",
                "",
            ),
            "/jobs/new?family=outdoor-yard&service=pressure-washing",
        )
        filtered_lead_params = {
            "next": ["/leads?family=outdoor-yard&service=pressure-washing"]
        }
        self.assertEqual(
            module.entry_job_filters(filtered_lead_params)["service"],
            "pressure-washing",
        )
        self.assertEqual(
            module.entry_redirect_url(
                "/login",
                filtered_lead_params,
                "find-work",
                "",
            ),
            "/leads?family=outdoor-yard&service=pressure-washing",
        )
        self.assertEqual(
            module.entry_sign_up_url("/login", "", filtered_lead_params),
            "/create-account?intent=find-work&next=%2Fleads%3Ffamily%3Doutdoor-yard%26service%3Dpressure-washing",
        )
        self.assertEqual(
            module.entry_clear_url("/login", filtered_lead_params),
            "/login?next=%2Fleads",
        )
        self.assertEqual(module.photo_count_label(1), "1 photo")
        self.assertEqual(module.photo_count_label("2"), "2 photos")
        self.assertTrue(module.is_production_clerk_publishable_key("pk_live_workdoe"))
        self.assertFalse(module.is_production_clerk_publishable_key("pk_test_workdoe"))
        self.assertFalse(module.is_production_clerk_publishable_key(""))
        self.assertEqual(
            module.normalize_clerk_frontend_api_url("http://bad.example"),
            "https://workdoe.com/__clerk",
        )
        self.assertEqual(
            module.normalize_clerk_frontend_api_url("https://evilworkdoe.com"),
            "https://workdoe.com/__clerk",
        )
        self.assertEqual(
            module.normalize_clerk_frontend_api_url("https://workdoe.com/__clerk/"),
            "https://workdoe.com/__clerk",
        )
        self.assertEqual(module.normalize_clerk_frontend_api_url("/__clerk/"), "/__clerk")
        development_key = (
            "pk_test_Y2xvc2Utc2VhbC0zNC5jbGVyay5hY2NvdW50cy5kZXYk"
        )
        self.assertEqual(
            module.clerk_development_frontend_api_url(development_key),
            "https://close-seal-34.clerk.accounts.dev",
        )
        self.assertEqual(module.clerk_development_frontend_api_url("pk_live_workdoe"), "")
        self.assertEqual(module.clerk_development_frontend_api_url("pk_test_invalid"), "")

        rows = [
            {
                "id": 9,
                "title": "Paint <stairwell>",
                "category": "Painting",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "client_email": "private@example.com",
                "desired_date": "2026-09-01",
                "approx_lat": 38.8871,
                "approx_lng": -77.0932,
                "photo_count": 1,
            }
        ]
        html = module.build_entry_shell_html(
            "/start",
            {"intent": ["find-work"], "job_id": ["9"]},
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        map_script = (ROOT / "workdoe" / "static" / "map.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("<title>Join Workdoe</title>", html)
        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            html,
        )
        self.assertIn('<meta name="theme-color" content="#1b2b22">', html)
        self.assertIn('<link rel="canonical" href="https://workdoe.com/">', html)
        self.assertIn(
            '<meta property="og:title" content="Workdoe - a local Work Exchange">',
            html,
        )
        self.assertIn(
            '<meta property="og:image" content="https://workdoe.com/workdoe-share.png">',
            html,
        )
        self.assertIn('<meta property="og:image:width" content="1200">', html)
        self.assertIn('<meta property="og:image:height" content="630">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn('<link rel="icon" href="/deer.svg" type="image/svg+xml">', html)
        self.assertIn('<link rel="manifest" href="/site.webmanifest">', html)
        self.assertIn(
            f'href="/styles.css?v={module.ASSET_RELEASE_TOKEN}"', html
        )
        self.assertIn('href="/vendor/leaflet/leaflet.css"', html)
        self.assertIn('href="/vendor/leaflet-markercluster/MarkerCluster.css"', html)
        self.assertIn('src="/vendor/leaflet/leaflet.js"', html)
        self.assertIn('src="/vendor/leaflet-markercluster/leaflet.markercluster.js"', html)
        self.assertIn(f'src="/map.js?v={module.ASSET_RELEASE_TOKEN}"', html)
        self.assertIn('getAttribute("data-asset-root")', map_script)
        self.assertIn("assetRoot + '/vendor/tabler-icons/home-check.svg\"", map_script)
        self.assertIn('src="/clerk-entry.js"', html)
        self.assertIn("data-clerk-entry", html)
        self.assertIn("Loading secure email sign-in...", html)
        self.assertNotIn("data-clerk-email-code-form", html)
        self.assertNotIn('id="clerk-captcha"', html)
        self.assertIn("@clerk/ui@1/dist/ui.browser.js", html)
        self.assertIn('data-clerk-mode="start"', html)
        self.assertIn('data-session-url="/api/auth/session"', html)
        self.assertIn('data-onboard-url="/api/auth/onboard"', html)
        self.assertIn('data-selected-job-id="9"', html)
        self.assertIn('maxlength="120"', html)
        self.assertIn(
            'class="help-text clerk-entry-status" role="status" aria-live="polite" data-clerk-onboarding-message',
            html,
        )
        self.assertIn('data-clerk-publishable-key="pk_test_workdoe"', html)
        self.assertIn("No password needed. Your one-time code arrives by email.", html)
        self.assertIn("<strong>Consumer</strong>", html)
        self.assertIn("<strong>Contractor</strong>", html)
        self.assertIn('class="market-workspace"', html)
        self.assertIn('class="market-filter-rail"', html)
        self.assertIn('class="market-map-stage"', html)
        self.assertIn('id="start-account" class="market-detail-rail market-auth-rail"', html)
        self.assertIn('data-mobile-panel-target="details">Account</button>', html)
        self.assertIn('data-project-results aria-label="Available projects" role="list"', html)
        self.assertIn("/api/jobs/open?limit=50&amp;target=start", html)
        self.assertIn("Paint &lt;stairwell&gt;", html)
        self.assertIn('class="job-service-chip"', html)
        self.assertIn('/vendor/tabler-icons/paint.svg', html)
        self.assertIn('role="listitem"', html)
        self.assertIn('class="project-result-item" role="listitem"', html)
        self.assertIn('aria-label="View details for Paint &lt;stairwell&gt;"', html)
        self.assertIn('class="project-result-action">View</span>', html)
        self.assertNotIn('class="project-result is-map-active" role="listitem"', html)
        self.assertIn('data-job-id="9"', html)
        self.assertIn("Selected", html)
        self.assertNotIn("private@example.com", html)
        self.assertNotIn("22201", html)
        family_html = module.build_entry_shell_html(
            "/",
            {
                "family": ["outdoor-yard"],
                "service": ["pressure-washing"],
                "q": ["Arlington"],
            },
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertEqual(family_html.count('class="service-family-filter-link'), 7)
        self.assertIn('href="/?q=Arlington&amp;family=outdoor-yard"', family_html)
        self.assertIn(
            "/api/jobs/open?limit=50&amp;target=start&amp;family=outdoor-yard&amp;service=pressure-washing&amp;q=Arlington",
            family_html,
        )
        self.assertIn('/vendor/tabler-icons/trees.svg', family_html)
        self.assertIn('class="market-lane-action"', family_html)
        self.assertIn("Lane selected", family_html)
        self.assertIn('id="market-service" data-market-service', family_html)
        self.assertIn('value="pressure-washing" selected', family_html)
        self.assertNotIn('value="house-cleaning"', family_html)
        self.assertIn(
            'href="/post-project?family=outdoor-yard&amp;service=pressure-washing"',
            family_html,
        )
        self.assertIn("Post this task", family_html)

        marker = '<script id="map-jobs-data" type="application/json">'
        data = html.split(marker, 1)[1].split("</script>", 1)[0]
        self.assertNotIn("&quot;", data)
        parsed = json.loads(data)
        self.assertEqual(parsed[0]["url"], "/create-account?intent=find-work&job_id=9")
        self.assertEqual(parsed[0]["action_label"], "Create account to respond")

        create_account_html = module.build_entry_shell_html(
            "/create-account",
            {"intent": ["post-job"]},
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn("<title>Create Account - Workdoe</title>", create_account_html)
        self.assertIn("Create your Workdoe account", create_account_html)
        self.assertIn('href="/create-account?intent=post-job" aria-current="page">Create account</a>', create_account_html)
        self.assertIn('data-redirect-url="/jobs/new"', create_account_html)
        self.assertIn("One account keeps one role during beta.", create_account_html)
        self.assertIn('data-sign-up-url="/create-account"', create_account_html)
        self.assertIn("Already have an account?", create_account_html)
        self.assertIn('href="/login?next=%2Fjobs%2Fnew">Sign in</a>', create_account_html)

        post_project_html = module.build_entry_shell_html(
            "/post-project",
            {},
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn("<title>Post Project - Workdoe</title>", post_project_html)
        self.assertIn("Post a project", post_project_html)
        self.assertIn(
            'href="/post-project" aria-current="page">Post project</a>',
            post_project_html,
        )
        self.assertIn('data-clerk-mode="start"', post_project_html)
        self.assertIn('data-redirect-url="/jobs/new"', post_project_html)
        self.assertIn('data-post-job-url="/jobs/new"', post_project_html)

        task_post_html = module.build_entry_shell_html(
            "/post-project",
            {
                "family": ["outdoor-yard"],
                "service": ["pressure-washing"],
            },
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn(
            'data-redirect-url="/jobs/new?family=outdoor-yard&amp;service=pressure-washing"',
            task_post_html,
        )
        self.assertIn(
            'data-post-job-url="/jobs/new?family=outdoor-yard&amp;service=pressure-washing"',
            task_post_html,
        )

        login_html = module.build_entry_shell_html(
            "/login",
            {"next": ["/jobs/9"]},
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn("<title>Sign in - Workdoe</title>", login_html)
        self.assertIn('data-clerk-mode="signin"', login_html)
        self.assertIn('data-redirect-url="/jobs/9"', login_html)
        self.assertIn(
            'data-sign-up-url="/create-account?intent=find-work&amp;job_id=9&amp;next=%2Fjobs%2F9"',
            login_html,
        )
        self.assertIn('data-session-url="/api/auth/session"', login_html)
        self.assertIn('id="signin" class="market-detail-rail market-auth-rail"', login_html)
        self.assertIn('data-mobile-panel-target="details">Account</button>', login_html)
        self.assertIn('data-project-results aria-label="Available projects" role="list"', login_html)
        self.assertIn("/api/jobs/open?limit=50&amp;target=login", login_html)
        self.assertIn('data-redirect-url="/jobs/9"', login_html)
        self.assertIn('role="listitem"', login_html)
        self.assertIn('data-job-id="9"', login_html)
        self.assertIn("Welcome back", login_html)
        self.assertIn("New to Workdoe?", login_html)
        self.assertIn(
            'href="/create-account?intent=find-work&amp;job_id=9&amp;next=%2Fjobs%2F9">Create account</a>',
            login_html,
        )
        self.assertIn("Selected", login_html)
        self.assertIn(
            'class="help-text clerk-entry-status" role="status" aria-live="polite" data-clerk-onboarding-message',
            login_html,
        )
        self.assertNotIn("data-clerk-display-name", login_html)

        filtered_login_html = module.build_entry_shell_html(
            "/login",
            filtered_lead_params,
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn(
            'data-redirect-url="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            filtered_login_html,
        )
        self.assertIn(
            'data-sign-up-url="/create-account?intent=find-work&amp;next=%2Fleads%3Ffamily%3Doutdoor-yard%26service%3Dpressure-washing"',
            filtered_login_html,
        )
        self.assertIn('value="pressure-washing" selected', filtered_login_html)
        self.assertIn(
            'data-clear-market-url="/login?next=%2Fleads"',
            filtered_login_html,
        )

        filtered_start_html = module.build_entry_shell_html(
            "/create-account",
            {
                "intent": ["find-work"],
                **filtered_lead_params,
            },
            rows,
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn(
            'data-leads-url="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            filtered_start_html,
        )
        self.assertIn(
            'data-redirect-url="/leads?family=outdoor-yard&amp;service=pressure-washing"',
            filtered_start_html,
        )

        headers = module.shell_headers("https://clerk.workdoe.com")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(
            headers["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains",
        )
        self.assertIn(
            "script-src 'self' https://clerk.workdoe.com",
            headers["Content-Security-Policy"],
        )
        self.assertIn(
            "https://tile.openstreetmap.org",
            headers["Content-Security-Policy"],
        )
        proxy_headers = module.shell_headers(
            "/__clerk", clerk_publishable_key="pk_live_workdoe"
        )
        self.assertIn(
            "script-src 'self' https://challenges.cloudflare.com https://*.protect.clerk.com;",
            proxy_headers["Content-Security-Policy"],
        )
        self.assertIn(
            "connect-src 'self' https://challenges.cloudflare.com https://*.protect.clerk.com",
            proxy_headers["Content-Security-Policy"],
        )
        self.assertIn("frame-src 'self'", proxy_headers["Content-Security-Policy"])
        self.assertIn("https://img.clerk.com", proxy_headers["Content-Security-Policy"])
        self.assertNotIn("/__clerk", proxy_headers["Content-Security-Policy"])

        proxy_html = module.build_entry_shell_html(
            "/login",
            {},
            rows,
            "pk_test_workdoe",
            "https://workdoe.com/__clerk",
        )
        self.assertIn('data-clerk-proxy-url="https://workdoe.com/__clerk"', proxy_html)
        self.assertIn("https://workdoe.com/__clerk/npm/@clerk/ui@1", proxy_html)
        self.assertIn("https://workdoe.com/__clerk/npm/@clerk/clerk-js@6", proxy_html)

        development_html = module.build_entry_shell_html(
            "/login",
            {},
            rows,
            development_key,
            "https://workdoe.com/__clerk",
        )
        self.assertNotIn("data-clerk-proxy-url", development_html)
        self.assertIn(
            "https://close-seal-34.clerk.accounts.dev/npm/@clerk/ui@1",
            development_html,
        )
        self.assertIn(
            "https://close-seal-34.clerk.accounts.dev/npm/@clerk/clerk-js@6",
            development_html,
        )
        development_headers = module.shell_headers(
            "https://workdoe.com/__clerk",
            clerk_publishable_key=development_key,
        )
        development_csp = development_headers["Content-Security-Policy"]
        self.assertIn("https://close-seal-34.clerk.accounts.dev", development_csp)
        self.assertIn("https://*.protect.clerk.com", development_csp)
        self.assertIn("https://challenges.cloudflare.com", development_csp)
        self.assertIn("https://img.clerk.com", development_csp)
        self.assertIn("style-src 'self' 'unsafe-inline'", development_csp)
        self.assertIn("worker-src 'self' blob:", development_csp)

    def test_cloudflare_clerk_proxy_plans_same_origin_fapi_requests(self):
        module = load_clerk_proxy_module()
        self.assertTrue(module.is_clerk_proxy_path("/__clerk"))
        self.assertTrue(module.is_clerk_proxy_path("/__clerk/v1/client"))
        self.assertFalse(module.is_clerk_proxy_path("/clerk/v1/client"))
        self.assertEqual(
            module.normalize_proxy_url("/__clerk", public_url="https://workdoe.com"),
            "https://workdoe.com/__clerk",
        )

        plan = module.clerk_proxy_request_plan(
            "https://workdoe.com/__clerk/v1/client?foo=bar",
            {
                "Accept": "application/json",
                "Origin": "https://workdoe.com",
                "CF-Connecting-IP": "203.0.113.10",
                "X-Forwarded-For": "198.51.100.99",
                "Host": "workdoe.com",
            },
            secret_key="sk_live_workdoe",
            proxy_url="https://workdoe.com/__clerk",
            fapi_url="https://frontend-api.clerk.dev",
        )
        self.assertEqual(
            plan["url"],
            "https://frontend-api.clerk.dev/v1/client?foo=bar",
        )
        self.assertEqual(plan["headers"]["Accept"], "application/json")
        self.assertEqual(plan["headers"]["Origin"], "https://workdoe.com")
        self.assertEqual(plan["headers"]["Clerk-Proxy-Url"], "https://workdoe.com/__clerk")
        self.assertEqual(plan["headers"]["Clerk-Secret-Key"], "sk_live_workdoe")
        self.assertEqual(plan["headers"]["X-Forwarded-For"], "203.0.113.10")
        self.assertNotIn("Host", plan["headers"])

        with self.assertRaisesRegex(module.ClerkProxyError, "CLERK_FAPI"):
            module.clerk_proxy_request_plan(
                "https://workdoe.com/__clerk/v1/client",
                {"CF-Connecting-IP": "203.0.113.10"},
                secret_key="sk_live_workdoe",
                proxy_url="https://workdoe.com/__clerk",
                fapi_url="https://attacker.example",
            )
        with self.assertRaisesRegex(module.ClerkProxyError, "CLERK_FAPI"):
            module.clerk_proxy_request_plan(
                "https://workdoe.com/__clerk/v1/client",
                {"CF-Connecting-IP": "203.0.113.10"},
                secret_key="sk_live_workdoe",
                proxy_url="https://workdoe.com/__clerk",
                fapi_url="https://frontend-api.clerk.dev/extra",
            )

        with self.assertRaisesRegex(module.ClerkProxyError, "CF-Connecting-IP"):
            module.clerk_proxy_request_plan(
                "https://workdoe.com/__clerk/v1/client",
                {},
                secret_key="sk_live_workdoe",
                proxy_url="https://workdoe.com/__clerk",
            )
        with self.assertRaisesRegex(module.ClerkProxyError, "workdoe.com/__clerk"):
            module.normalize_proxy_url("https://evilworkdoe.com/__clerk")

    def test_cloudflare_app_shell_renders_post_login_workflows(self):
        module = load_app_shell_module()
        entry_module = load_worker_entry_module()
        client = {
            "id": 8,
            "role": "client",
            "status": "active",
            "display_name": "Client",
            "unread_message_count": 1,
        }
        contractor = {
            "id": 7,
            "role": "contractor",
            "status": "active",
            "display_name": "Crew",
            "unread_message_count": 1,
        }
        admin = {"id": 1, "role": "admin", "status": "active", "display_name": "Admin"}
        self.assertTrue(module.is_app_shell_route("/dashboard"))
        self.assertTrue(module.is_app_shell_route("/account"))
        self.assertTrue(module.is_app_shell_route("/client/jobs/12"))
        self.assertTrue(module.is_app_shell_route("/client/jobs/12/edit"))
        self.assertTrue(module.is_app_shell_route("/client/requests"))
        self.assertTrue(module.is_app_shell_route("/messages/5"))
        self.assertTrue(module.is_app_shell_route("/jobs/42"))
        self.assertFalse(module.is_app_shell_route("/api/jobs/open"))
        self.assertTrue(module.is_public_contractor_profile_route("/contractors/7"))
        self.assertFalse(module.is_public_contractor_profile_route("/api/contractors/7"))
        self.assertEqual(module.app_login_url("/leads"), "/login?next=/leads")
        self.assertEqual(
            module.app_login_url("/client/jobs/12?bids=pending"),
            "/login?next=/client/jobs/12%3Fbids%3Dpending",
        )
        self.assertEqual(
            entry_module.auth_redirect_for_user(
                contractor,
                "/leads?family=outdoor-yard&service=pressure-washing",
            ),
            "/leads?family=outdoor-yard&service=pressure-washing",
        )
        self.assertEqual(
            entry_module.auth_redirect_for_user(
                client,
                "/jobs/new?family=outdoor-yard&service=pressure-washing",
            ),
            "/jobs/new?family=outdoor-yard&service=pressure-washing",
        )
        self.assertEqual(module.dashboard_path_for_user(client), "/client/dashboard")
        self.assertEqual(module.dashboard_path_for_user(contractor), "/contractor/dashboard")
        self.assertEqual(module.dashboard_path_for_user({"role": ""}), "/create-account")
        anonymous_nav = module.nav_links(None, "/post-project")
        self.assertIn(
            'href="/post-project" aria-current="page">Post project</a>',
            anonymous_nav,
        )
        self.assertNotIn('href="/jobs/new">Post project</a>', anonymous_nav)
        client_nav = module.nav_links(client, "/client/dashboard")
        self.assertIn('href="/client/dashboard" aria-current="page">Profile</a>', client_nav)
        self.assertIn('aria-label="Messages, 1 unread"', client_nav)
        self.assertIn('<span class="nav-unread-count" aria-hidden="true">1</span>', client_nav)
        self.assertIn(
            '<span class="nav-unread-count" aria-hidden="true">99+</span>',
            module.nav_links(
                {**client, "unread_message_count": 100},
                "/client/dashboard",
            ),
        )
        self.assertIn('<details class="account-menu">', client_nav)
        self.assertIn('href="/account">Account settings</a>', client_nav)
        self.assertIn('data-json-action="/api/auth/logout"', client_nav)
        self.assertIn('class="nav-link-button"', client_nav)
        self.assertNotIn('href="/logout"', client_nav)
        contractor_mobile_nav = module.mobile_task_nav_html(contractor, "/leads")
        self.assertIn('aria-label="Primary tasks"', contractor_mobile_nav)
        self.assertIn('href="/leads" aria-current="page"', contractor_mobile_nav)
        self.assertIn("<span>Explore</span>", contractor_mobile_nav)
        self.assertIn("<span>Bids</span>", contractor_mobile_nav)
        self.assertIn("<span>Messages</span>", contractor_mobile_nav)
        self.assertIn('aria-label="Messages, 1 unread"', contractor_mobile_nav)
        self.assertIn('<span class="nav-unread-count" aria-hidden="true">1</span>', contractor_mobile_nav)
        self.assertIn("<span>Profile</span>", contractor_mobile_nav)
        self.assertEqual(module.parse_app_client_job_edit_id("/client/jobs/12/edit"), 12)
        self.assertEqual(module.parse_app_client_job_edit_id("/client/jobs/12"), 0)

        safety_html = module.safety_page_html()
        self.assertIn("Safety - Workdoe", safety_html)
        self.assertIn("Share only what the job needs.", safety_html)
        self.assertIn('href="/safety" aria-current="page"', safety_html)
        self.assertIn('href="/login">Sign in</a>', safety_html)
        self.assertNotIn('href="/logout"', safety_html)
        self.assertNotIn("Cloudflare", safety_html)
        self.assertNotIn("MVP", safety_html)

        privacy_html = module.privacy_page_html()
        terms_html = module.terms_page_html()
        self.assertIn("Privacy Policy - Workdoe", privacy_html)
        self.assertIn("We do not sell personal information", privacy_html)
        self.assertIn("Terms of Use - Workdoe", terms_html)
        self.assertIn("Prohibited work", terms_html)
        self.assertIn('href="/privacy" aria-current="page"', privacy_html)
        self.assertIn('href="/terms" aria-current="page"', terms_html)
        self.assertIn('href="/privacy">Privacy</a>', safety_html)
        self.assertIn("Disallow: /api/", module.public_robots_txt())
        self.assertIn("https://workdoe.com/privacy", module.public_sitemap_xml())
        self.assertNotIn("/client/", module.public_sitemap_xml())
        self.assertIn(
            "Canonical: https://workdoe.com/.well-known/security.txt",
            module.public_security_txt(),
        )

        client_html = module.client_dashboard_html(
            client,
            {
                "jobs": [
                    {
                        "id": 12,
                        "title": "Power wash steps",
                        "category": "Power washing",
                        "city": "Arlington",
                        "state": "VA",
                        "description": "Townhouse front steps.",
                        "status": "open",
                        "pending_count": 2,
                        "needs_review": True,
                        "url": "/client/jobs/12?bids=pending#mini-bids",
                        "row_cue": "Review bids",
                        "client_email": "private@example.com",
                    }
                ],
                "view": "active",
                "view_links": [
                    {
                        "value": "active",
                        "label": "Active",
                        "url": "/client/dashboard",
                    },
                    {
                        "value": "review",
                        "label": "Bids",
                        "url": "/client/dashboard?view=review",
                    },
                    {
                        "value": "paused",
                        "label": "Paused",
                        "url": "/client/dashboard?view=paused",
                    },
                    {
                        "value": "history",
                        "label": "History",
                        "url": "/client/dashboard?view=history",
                    },
                ],
                "stats": {
                    "active_jobs": 1,
                    "open_jobs": 1,
                    "review_jobs": 1,
                    "paused_jobs": 0,
                    "history_jobs": 0,
                    "closed_jobs": 0,
                    "pending_requests": 2,
                    "total_jobs": 1,
                },
            },
        )
        self.assertIn("Projects - Workdoe", client_html)
        self.assertIn("Consumer workspace", client_html)
        self.assertIn(
            '<nav class="work-view-tabs client-job-tabs" aria-label="Client job status">',
            client_html,
        )
        self.assertIn(
            '<a class="work-view-tab is-active" href="/client/dashboard" aria-current="page"><span>Active</span><strong>1</strong></a>',
            client_html,
        )
        self.assertIn(
            '<a class="work-view-tab" href="/client/dashboard?view=review"><span>Bids</span><strong>1</strong></a>',
            client_html,
        )
        self.assertNotIn('aria-label="Client work queue"', client_html)
        self.assertIn("/client/jobs/12?bids=pending#mini-bids", client_html)
        self.assertIn('aria-label="Review pending bids for Power wash steps"', client_html)
        self.assertIn("Review bids", client_html)
        self.assertNotIn("private@example.com", client_html)

        review_empty_html = module.client_dashboard_html(
            client,
            {
                "jobs": [],
                "view": "review",
                "view_links": [
                    {
                        "value": "active",
                        "label": "Active",
                        "url": "/client/dashboard",
                    },
                    {
                        "value": "review",
                        "label": "Bids",
                        "url": "/client/dashboard?view=review",
                    },
                    {
                        "value": "paused",
                        "label": "Paused",
                        "url": "/client/dashboard?view=paused",
                    },
                    {
                        "value": "history",
                        "label": "History",
                        "url": "/client/dashboard?view=history",
                    },
                ],
                "stats": {
                    "active_jobs": 1,
                    "open_jobs": 1,
                    "review_jobs": 0,
                    "paused_jobs": 0,
                    "history_jobs": 0,
                    "closed_jobs": 0,
                    "pending_requests": 0,
                    "total_jobs": 1,
                },
            },
        )
        self.assertIn(
            '<a class="work-view-tab is-active" href="/client/dashboard?view=review" '
            'aria-current="page"><span>Bids</span><strong>0</strong></a>',
            review_empty_html,
        )
        self.assertIn("No bids to review", review_empty_html)
        self.assertIn('href="/client/dashboard">Active projects</a>', review_empty_html)

        paused_html = module.client_dashboard_html(
            client,
            {
                "jobs": [
                    {
                        "id": 13,
                        "title": "Repair garden gate",
                        "category": "Fence work",
                        "city": "Washington",
                        "state": "DC",
                        "description": "Paused until next month.",
                        "status": "hidden",
                        "row_cue": "Manage",
                        "bid_window": {
                            "state": "closed",
                            "usage_label": "0 of 4 bids",
                            "availability_label": "Project closed",
                        },
                    }
                ],
                "view": "paused",
                "stats": {"active_jobs": 1, "paused_jobs": 1},
            },
        )
        self.assertIn('<span class="status hidden">paused</span>', paused_html)
        self.assertIn("Not accepting bids", paused_html)
        self.assertIn('aria-label="Manage Repair garden gate"', paused_html)
        self.assertIn('<span class="row-cue">Manage</span>', paused_html)
        self.assertNotIn("Project closed", paused_html)

        request_inbox_html = module.client_request_inbox_html(
            client,
            {
                "jobs": [
                    {
                        "id": 12,
                        "title": "Power wash steps",
                        "category": "Power washing",
                        "city": "Arlington",
                        "state": "VA",
                        "description": "Townhouse front steps.",
                        "status": "open",
                        "pending_count": 2,
                        "review_url": "/client/jobs/12?bids=pending#mini-bids",
                    }
                ],
                "stats": {"pending_requests": 2, "review_jobs": 1, "approved_requests": 0},
            },
        )
        self.assertIn("Bid Requests - Workdoe", request_inbox_html)
        self.assertIn(
            'href="/client/dashboard" aria-current="page">Profile</a>',
            request_inbox_html,
        )
        self.assertIn("2 pending", request_inbox_html)
        self.assertIn("/client/jobs/12?bids=pending#mini-bids", request_inbox_html)

        contractor_dashboard_html = module.contractor_dashboard_html(
            contractor,
            {
                "profile": {
                    "business_name": "Rivera Exterior Care",
                    "trades": "Power washing",
                    "service_area": "DMV area",
                    "insurance_status": "Available on request",
                    "intro": "Exterior maintenance for local homes.",
                },
                "bids": [
                    {
                        "id": 31,
                        "title": "Power wash steps",
                        "category": "Power washing",
                        "city": "Arlington",
                        "state": "VA",
                        "scope_note": "Careful exterior cleaning.",
                        "price_range": "$450-$650",
                        "timeline": "Two business days",
                        "url": "/messages/5",
                        "row_cue": "Message",
                        "status": "approved",
                    }
                ],
                "view": "all",
                "view_links": [
                    {"value": "all", "label": "All", "url": "/contractor/dashboard"},
                    {
                        "value": "approved",
                        "label": "Approved",
                        "url": "/contractor/dashboard?bids=approved",
                    },
                ],
                "stats": {
                    "visible_requests": 1,
                    "pending_requests": 0,
                    "approved_requests": 1,
                    "total_requests": 1,
                },
                "reputation": {
                    "level_label": "New to Workdoe",
                    "completion_points": 0,
                    "verified_completions": 0,
                    "method_label": "100 points per mutually confirmed Workdoe project",
                    "progress_value": 0,
                    "progress_max": 1,
                    "next_milestone": {"remaining": 1, "label": "First finish"},
                    "milestones": [
                        {
                            "label": "First finish",
                            "threshold": 1,
                            "earned": False,
                            "state": "next",
                        },
                        {
                            "label": "Steady provider",
                            "threshold": 3,
                            "earned": False,
                            "state": "locked",
                        },
                    ],
                    "credential_signals": [],
                    "trust_record": {
                        "state": "license-source-checked",
                        "label": "1 license source checked",
                        "qualifier": "Current public record",
                    },
                },
            },
        )
        self.assertIn("Rivera Exterior Care", contractor_dashboard_html)
        self.assertIn('aria-label="Contractor profile summary"', contractor_dashboard_html)
        self.assertIn('aria-label="Contractor mini bid status"', contractor_dashboard_html)
        self.assertIn("Browse projects", contractor_dashboard_html)
        self.assertNotIn('aria-label="Contractor work queue"', contractor_dashboard_html)
        self.assertNotIn("dashboard-metrics", contractor_dashboard_html)
        self.assertLess(
            contractor_dashboard_html.find('aria-label="Contractor mini bids"'),
            contractor_dashboard_html.find('class="work-progress"'),
        )
        self.assertLess(
            contractor_dashboard_html.find('aria-label="Contractor mini bids"'),
            contractor_dashboard_html.find('aria-label="Contractor profile summary"'),
        )
        self.assertIn('href="/contractor/dashboard" aria-current="page"', contractor_dashboard_html)
        self.assertIn('aria-label="Message about Power wash steps"', contractor_dashboard_html)
        self.assertIn('<span class="row-cue">Message</span>', contractor_dashboard_html)
        self.assertIn('class="job-row link-row contractor-bid-row is-approved"', contractor_dashboard_html)
        self.assertIn('aria-describedby="contractor-bid-terms-31"', contractor_dashboard_html)
        self.assertIn('id="contractor-bid-terms-31"', contractor_dashboard_html)
        self.assertIn('aria-label="Your submitted bid terms"', contractor_dashboard_html)
        self.assertIn("<small>Estimate</small><strong>$450-$650</strong>", contractor_dashboard_html)
        self.assertIn("<small>Timing</small><strong>Two business days</strong>", contractor_dashboard_html)
        self.assertIn('class="milestone-track" aria-label="Verified completion milestones"', contractor_dashboard_html)
        self.assertIn('class="milestone-step is-next"', contractor_dashboard_html)
        self.assertIn("0 verified projects", contractor_dashboard_html)
        self.assertIn("<dt>Trust record</dt>", contractor_dashboard_html)
        self.assertIn("1 license source checked", contractor_dashboard_html)
        self.assertIn('href="/contractor/profile#credential-claims">Trust records</a>', contractor_dashboard_html)
        self.assertIn('/vendor/tabler-icons/sparkles.svg', contractor_dashboard_html)
        self.assertNotIn('/static/vendor/tabler-icons/sparkles.svg', contractor_dashboard_html)

        contractor_empty_html = module.contractor_dashboard_html(
            contractor,
            {
                "bids": [],
                "view": "approved",
                "view_links": [
                    {"value": "all", "label": "All", "url": "/contractor/dashboard"},
                    {
                        "value": "approved",
                        "label": "Approved",
                        "url": "/contractor/dashboard?bids=approved",
                    },
                ],
                "stats": {"approved_requests": 0, "total_requests": 1},
            },
        )
        self.assertIn("No approved bids.", contractor_empty_html)
        self.assertIn('href="/contractor/dashboard">All bids</a>', contractor_empty_html)

        form_html = module.job_form_html(client, site_key="turnstile-site-key")
        self.assertIn('data-json-action="/api/jobs"', form_html)
        self.assertIn(
            'data-upload-after-json-template="/api/media/jobs/{job_id}/upload"',
            form_html,
        )
        self.assertIn('name="photos" type="file"', form_html)
        self.assertIn("multiple", form_html)
        self.assertIn('class="form-checklist" aria-label="Posting safeguards"', form_html)
        self.assertIn("City/ZIP pin", form_html)
        self.assertIn('aria-label="Post a project."', form_html)
        self.assertIn('for="job-title"', form_html)
        self.assertIn('id="job-title"', form_html)
        self.assertIn('autocapitalize="sentences"', form_html)
        self.assertIn('enterkeyhint="next"', form_html)
        self.assertIn('for="job-city"', form_html)
        self.assertIn('list="job-city-options"', form_html)
        self.assertIn('id="job-city-options"', form_html)
        self.assertIn('value="Washington"', form_html)
        self.assertIn('autocomplete="postal-code"', form_html)
        self.assertIn('list="job-zip-options"', form_html)
        self.assertIn('id="job-zip-options"', form_html)
        self.assertIn('value="20003"', form_html)
        self.assertIn('name="budget_min" type="number"', form_html)
        self.assertIn('name="budget_max" type="number"', form_html)
        self.assertIn('enterkeyhint="done"', form_html)
        self.assertIn('aria-describedby="job-photos-help"', form_html)
        self.assertIn('id="job-photos-help"', form_html)
        self.assertIn('aria-label="Post project"', form_html)
        self.assertIn('src="/worker-actions.js"', form_html)
        self.assertIn('class="cf-turnstile"', form_html)
        self.assertIn('data-sitekey="turnstile-site-key"', form_html)
        self.assertIn("Post project", form_html)
        family_form_html = module.job_form_html(
            client,
            job={"service_group_slug": "outdoor-yard"},
        )
        self.assertIn('data-project-initial-step="2"', family_form_html)
        task_form_html = module.job_form_html(
            client,
            job={
                "service_group_slug": "outdoor-yard",
                "service_slug": "pressure-washing",
                "category": "Power washing",
            },
        )
        self.assertIn('data-project-initial-step="3"', task_form_html)
        self.assertIn('placeholder="Pressure washing project"', task_form_html)
        self.assertIn(
            "Describe the pressure washing scope, size, current condition, access, and desired outcome.",
            task_form_html,
        )
        family_draft_html = module.public_job_draft_html(
            {"service_group_slug": "outdoor-yard"}
        )
        self.assertIn('data-project-initial-step="2"', family_draft_html)
        task_draft_html = module.public_job_draft_html(
            {
                "service_group_slug": "outdoor-yard",
                "service_slug": "pressure-washing",
                "category": "Power washing",
            }
        )
        self.assertIn('data-project-initial-step="3"', task_draft_html)
        selected_composer = module.project_composer_fields_html(
            {
                "service_group_slug": "outdoor-yard",
                "service_slug": "pressure-washing",
                "category": "Power washing",
                "scope_answers": {"surface": "concrete"},
            },
            include_photos=False,
            submit_label="Continue",
            cancel_url="/",
        )
        self.assertIn('<details class="service-option-more" open>', selected_composer)
        self.assertIn(
            '<details class="service-scope-panel" data-service-scope-set="pressure-washing" open>',
            selected_composer,
        )
        self.assertIn('class="service-scope-body"', selected_composer)
        self.assertIn("Add details", selected_composer)

        draft_html = module.public_job_draft_html(
            {
                "title": "Wash the front walk",
                "category": "Power washing",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "budget_min": "450",
                "budget_max": "700",
                "description": "Clean the walk and steps before a family gathering.",
            },
            [],
            "turnstile-site-key",
        )
        self.assertIn('action="/post-project"', draft_html)
        self.assertIn('aria-label="Project draft"', draft_html)
        self.assertIn('value="Wash the front walk"', draft_html)
        self.assertIn('value="450"', draft_html)
        self.assertIn('data-action="job-draft"', draft_html)
        self.assertNotIn('name="photos"', draft_html)
        self.assertNotIn('src="/worker-actions.js"', draft_html)

        edit_form_html = module.job_form_html(
            client,
            site_key="turnstile-site-key",
            job={
                "id": 12,
                "title": "Power wash steps",
                "category": "Power washing",
                "service_slug": "pressure-washing",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "description": "Townhouse front steps and patio.",
                "desired_date": "2026-09-01",
                "budget_min": 450,
                "budget_max": 700,
            },
            mode="edit",
        )
        self.assertIn("Edit Project - Workdoe", edit_form_html)
        self.assertIn('data-json-action="/api/jobs/12/update"', edit_form_html)
        self.assertIn('value="Power wash steps"', edit_form_html)
        self.assertIn('placeholder="Pressure washing project"', edit_form_html)
        self.assertIn(
            "Describe the pressure washing scope, size, current condition, access, and desired outcome.",
            edit_form_html,
        )
        self.assertIn("<strong>Pressure washing</strong>", edit_form_html)
        self.assertIn('name="service_slug" value="pressure-washing"', edit_form_html)
        self.assertIn('<option value="VA" selected>', edit_form_html)
        self.assertIn('value="22201"', edit_form_html)
        self.assertIn('name="budget_min" type="number" value="450"', edit_form_html)
        self.assertIn('name="budget_max" type="number" value="700"', edit_form_html)
        self.assertIn("Townhouse front steps and patio.", edit_form_html)
        self.assertIn("Save changes", edit_form_html)

        profile_html = module.contractor_profile_html(
            contractor,
            {
                "business_name": "Doe Exterior Care",
                "trades": "Power washing, Window cleaning",
                "service_area": "DC and Northern Virginia",
                "intro": "Careful exterior cleaning for storefronts and homes.",
                "insurance_status": "COI available",
                "license_number": "VA-1234",
                "years_in_business": 7,
                "website": "https://doe.example",
                "phone": "(202) 555-0100",
            },
            [{"id": 4, "original_filename": "crew.webp"}],
        )
        self.assertIn('data-json-action="/api/contractor/profile"', profile_html)
        self.assertIn('data-file-action="/api/media/contractors/7/upload"', profile_html)
        self.assertIn('aria-label="Contractor profile"', profile_html)
        self.assertIn('aria-label="Upload portfolio photo"', profile_html)
        self.assertIn('aria-describedby="profile-upload-status"', profile_html)
        self.assertIn('for="profile-business-name"', profile_html)
        self.assertIn('id="profile-business-name"', profile_html)
        self.assertIn('id="profile-trades"', profile_html)
        self.assertIn('for="profile-trade-1"', profile_html)
        self.assertIn('id="profile-service-area"', profile_html)
        self.assertIn('id="profile-years-in-business"', profile_html)
        self.assertIn('inputmode="numeric"', profile_html)
        self.assertIn('id="profile-website"', profile_html)
        self.assertIn('autocomplete="url"', profile_html)
        self.assertIn("Storefront readiness", profile_html)
        self.assertIn("7 of 7 ready", profile_html)
        self.assertIn('class="profile-task-links" aria-label="Profile tasks"', profile_html)
        self.assertIn('href="#work-availability"', profile_html)
        self.assertIn('href="#profile-details"', profile_html)
        self.assertIn('href="#credential-claims"', profile_html)
        self.assertIn('<summary class="profile-readiness-head">', profile_html)
        self.assertNotIn("<details open>", profile_html)
        self.assertIn('id="profile-details"', profile_html)
        self.assertLess(
            profile_html.find('id="profile-details"'),
            profile_html.find('id="credential-claims"'),
        )
        self.assertNotIn('id="profile-phone"', profile_html)
        self.assertIn('id="profile-intro"', profile_html)
        self.assertIn('enterkeyhint="done"', profile_html)
        self.assertIn(
            'name="service_slugs" value="pressure-washing" checked',
            profile_html,
        )
        self.assertIn(
            'name="service_zone_slugs" value="district-of-columbia" checked',
            profile_html,
        )
        self.assertIn('name="portfolio_photo"', profile_html)
        self.assertIn('id="profile-photos"', profile_html)
        self.assertIn('aria-describedby="profile-photos-help"', profile_html)
        self.assertIn('id="profile-photos-help"', profile_html)
        self.assertIn('href="/contractors/7"', profile_html)
        self.assertIn('src="/worker-actions.js"', profile_html)
        self.assertNotIn("contractor@example.com", profile_html)

        public_profile_html = module.public_contractor_profile_html(
            client,
            {
                "contractor": {
                    "id": 7,
                    "business_name": "Doe Exterior Care",
                    "trades": "Power washing",
                    "service_area": "DMV",
                    "intro": "Careful exterior cleaning.",
                    "insurance_status": "COI available",
                    "license_number": "Not listed",
                    "years_in_business": 7,
                    "contact_policy": "Clients approve a contractor's mini bid before a private Workdoe message thread opens.",
                    "photos": [{"id": 4, "url": "/media/contractors/4"}],
                    "availability": {
                        "status": "available",
                        "label": "Available for new work",
                    },
                    "verified_completions": 2,
                    "reputation": {
                        "level_label": "First finish",
                        "completion_points": 200,
                        "method_label": "100 points per mutually confirmed Workdoe project",
                        "progress_value": 1,
                        "progress_max": 3,
                        "next_milestone": {
                            "remaining": 1,
                            "label": "Steady provider",
                        },
                        "credential_signals": [],
                    },
                    "choice_context": {
                        "job_id": 12,
                        "job_title": "Power wash steps",
                        "request_id": 31,
                        "price_range": "$450-$650",
                        "timeline": "Two days",
                        "availability": "Tuesday",
                        "status": "pending",
                        "back_url": "/client/jobs/12#mini-bids",
                        "can_choose": True,
                        "thread_url": "",
                    },
                    "email": "contractor@example.com",
                }
            },
        )
        self.assertIn("Doe Exterior Care - Workdoe", public_profile_html)
        self.assertIn("/media/contractors/4", public_profile_html)
        self.assertIn("Portfolio photo", public_profile_html)
        self.assertNotIn("crew.webp", public_profile_html)
        self.assertIn("private Workdoe message thread", public_profile_html)
        self.assertIn("Work history and records", public_profile_html)
        self.assertLess(
            public_profile_html.find("Work history and records"),
            public_profile_html.find("<h2>About</h2>"),
        )
        self.assertIn("No current source-checked record is shown.", public_profile_html)
        self.assertIn('href="/client/jobs/12#mini-bids"', public_profile_html)
        self.assertIn(
            'data-json-action="/api/match-requests/31/approve"',
            public_profile_html,
        )
        self.assertIn(
            'data-inline-dialog-open="choose-profile-contractor"',
            public_profile_html,
        )
        self.assertIn('id="choose-profile-contractor"', public_profile_html)
        self.assertIn("Confirm contractor", public_profile_html)
        self.assertIn("$450-$650", public_profile_html)
        self.assertIn("Two days", public_profile_html)
        self.assertIn("Tuesday", public_profile_html)
        self.assertNotIn('href="/leads">Back to leads</a>', public_profile_html)
        self.assertIn(
            "Profile details are self-reported. A source-checked record means Workdoe reviewed the linked public source",
            public_profile_html,
        )
        self.assertNotIn("contractor@example.com", public_profile_html)

        messages_html = module.message_threads_html(
            client,
            {
                "threads": [
                    {
                        "id": 5,
                        "url": "/messages/5",
                        "title": "Window cleaning",
                        "category": "Window cleaning",
                        "city": "Arlington",
                        "state": "VA",
                        "client_name": "Avery Client",
                        "contractor_name": "Doe Exterior Care",
                        "last_message": "Tuesday works.",
                        "message_count": 2,
                        "unread_count": 1,
                        "needs_reply": True,
                    }
                ],
                "view": "all",
                "stats": {
                    "threads": 1,
                    "messages": 2,
                    "unread": 1,
                    "unread_threads": 1,
                    "reply_threads": 1,
                },
            },
        )
        self.assertIn("Messages - Workdoe", messages_html)
        self.assertEqual(module.message_count_label(1), "1 message")
        self.assertEqual(module.message_count_label("2"), "2 messages")
        self.assertEqual(
            module.datetime_label("2026-08-16T14:00:00+00:00"),
            "Aug 16, 2:00 PM",
        )
        self.assertIn('href="/messages/5"', messages_html)
        self.assertIn(
            'aria-label="Open message thread for Window cleaning, 2 messages, 1 unread"',
            messages_html,
        )
        self.assertIn("2 messages", messages_html)
        self.assertIn('<span class="unread-chip">1 new</span>', messages_html)
        self.assertIn("1 unread", messages_html)
        self.assertIn(
            '<nav class="work-view-tabs message-view-tabs" aria-label="Message thread view">',
            messages_html,
        )
        self.assertIn(
            '<a class="work-view-tab is-active" href="/messages" aria-current="page"><span>All</span><strong>1</strong></a>',
            messages_html,
        )
        self.assertIn(
            '<a class="work-view-tab" href="/messages?view=reply"><span>Needs reply</span><strong>1</strong></a>',
            messages_html,
        )
        self.assertIn(
            '<a class="work-view-tab" href="/messages?view=unread"><span>Unread</span><strong>1</strong></a>',
            messages_html,
        )
        self.assertIn("<strong>Doe Exterior Care</strong>", messages_html)
        self.assertNotIn("Avery Client and Doe Exterior Care", messages_html)
        self.assertNotIn("message-metrics", messages_html)
        self.assertIn('class="message-thread-list"', messages_html)
        self.assertNotIn('class="button secondary compact">Read</span>', messages_html)
        self.assertIn("Tuesday works.", messages_html)
        self.assertNotIn("private@example.com", messages_html)

        unread_empty_html = module.message_threads_html(
            client,
            {
                "threads": [],
                "view": "unread",
                "stats": {
                    "threads": 1,
                    "messages": 2,
                    "unread": 0,
                    "unread_threads": 0,
                },
            },
        )
        self.assertIn("No unread messages", unread_empty_html)
        self.assertIn('href="/messages">View all messages</a>', unread_empty_html)

        thread_html = module.message_thread_detail_html(
            client,
            {
                "thread": {
                    "id": 5,
                    "job_id": 12,
                    "title": "Window cleaning",
                    "category": "Window cleaning",
                    "city": "Arlington",
                    "state": "VA",
                    "price_range": "$450-$650",
                    "timeline": "Two business days",
                    "availability": "Tuesday morning",
                    "client_name": "Avery Client",
                    "contractor_name": "Doe Exterior Care",
                    "provider": {
                        "id": 7,
                        "name": "Doe Exterior Care",
                        "profile_url": "/contractors/7?job_id=12",
                        "reputation": {
                            "level_label": "Steady provider",
                            "verified_completions": 3,
                            "trust_record": {
                                "state": "license-source-checked",
                                "label": "1 license source checked",
                            },
                            "ranking_effect": "none",
                        },
                    },
                },
                "messages": [
                    {
                        "id": 9,
                        "sender_id": 8,
                        "sender_name": "Avery Client",
                        "body": "Can you start Tuesday?",
                        "is_hidden": 0,
                        "created_at": "2026-08-03T12:00:00+00:00",
                    }
                ],
                "inbox_threads": [
                    {
                        "id": 5,
                        "title": "Window cleaning",
                        "client_name": "Avery Client",
                        "contractor_name": "Doe Exterior Care",
                        "last_message": "Can you start Tuesday?",
                        "unread_count": 0,
                    }
                ],
            },
            can_reply=True,
            site_key="turnstile-site-key",
        )
        self.assertIn("Message Thread - Workdoe", thread_html)
        self.assertIn('class="message mine"', thread_html)
        self.assertIn('data-json-action="/api/messages/threads/5"', thread_html)
        self.assertIn('aria-label="New message"', thread_html)
        self.assertIn('aria-describedby="message-reply-status"', thread_html)
        self.assertIn('for="message-body"', thread_html)
        self.assertIn('id="message-body"', thread_html)
        self.assertIn('id="message-reply-status"', thread_html)
        self.assertIn('autocapitalize="sentences"', thread_html)
        self.assertIn('spellcheck="true"', thread_html)
        self.assertIn('enterkeyhint="send"', thread_html)
        self.assertIn('aria-label="Send message"', thread_html)
        self.assertIn('class="message-workspace"', thread_html)
        self.assertIn('class="message-inbox-rail" aria-label="Conversations"', thread_html)
        self.assertIn('aria-label="Approved match conversations"', thread_html)
        self.assertIn('href="/messages/5" aria-current="page"', thread_html)
        self.assertIn("With Doe Exterior Care", thread_html)
        self.assertIn('class="message-shell thread-message-shell"', thread_html)
        self.assertIn('class="message-list thread-message-list"', thread_html)
        self.assertIn('aria-label="Approved match summary"', thread_html)
        self.assertIn('href="/client/jobs/12">View project</a>', thread_html)
        self.assertIn("<dt>Price</dt><dd>$450-$650</dd>", thread_html)
        self.assertIn("<dt>Timeline</dt><dd>Two business days</dd>", thread_html)
        self.assertIn("<dt>Availability</dt><dd>Tuesday morning</dd>", thread_html)
        self.assertIn("Chosen provider", thread_html)
        self.assertIn(
            'href="/contractors/7?job_id=12">Doe Exterior Care</a>',
            thread_html,
        )
        self.assertIn("Steady provider - 3 completed projects", thread_html)
        self.assertIn("1 license source checked", thread_html)
        self.assertIn("Public-source status only", thread_html)
        self.assertNotIn("claimed_identifier", thread_html)
        self.assertIn('src="/worker-actions.js"', thread_html)
        self.assertIn('data-json-action="/api/reports"', thread_html)
        self.assertIn('name="target_type" value="message"', thread_html)
        self.assertIn('name="target_id" value="9"', thread_html)
        self.assertIn('aria-label="Report message from Avery Client"', thread_html)
        self.assertIn('data-sitekey="turnstile-site-key"', thread_html)
        self.assertIn('src="https://challenges.cloudflare.com/turnstile/v0/api.js"', thread_html)
        self.assertIn("1 message", thread_html)
        self.assertNotIn("1 messages", thread_html)
        self.assertIn("Can you start Tuesday?", thread_html)
        contractor_thread_html = module.message_thread_detail_html(
            contractor,
            {
                "thread": {
                    "id": 5,
                    "job_id": 12,
                    "title": "Window cleaning",
                    "price_range": "$450-$650",
                    "timeline": "Two business days",
                    "availability": "Tuesday morning",
                },
                "messages": [],
            },
            can_reply=True,
        )
        self.assertIn('href="/jobs/12">View project</a>', contractor_thread_html)
        self.assertNotIn("client@example.com", contractor_thread_html)

        admin_html = module.admin_dashboard_html(
            admin,
            {
                "stats": {
                    "open_reports": 1,
                    "suspended_users": 1,
                    "hidden_content": 2,
                    "audit_actions": 3,
                    "automation_events": 4,
                },
                "repeat_work_metrics": {
                    "invitations_created": 3,
                    "invitations_pending": 0,
                    "invitations_bid_sent": 1,
                    "invitations_declined": 1,
                    "invitations_withdrawn": 1,
                    "verified_repeat_projects": 1,
                    "invitation_bid_rate": 33,
                    "verified_repeat_rate": 100,
                },
                "repeat_invitations": [
                    {
                        "id": 8,
                        "job_id": 61,
                        "project_title": "Fresh patio wash invitation",
                        "contractor_name": "Rivera Exterior Care",
                        "city": "Washington",
                        "state": "DC",
                        "status": "bid_sent",
                        "verified_complete": 1,
                    }
                ],
                "lead_alert_metrics": {
                    "opted_in_contractors": 4,
                    "pending_alerts": 1,
                    "queued_alerts": 2,
                    "sent_alerts": 8,
                    "failed_alerts": 0,
                },
                "recent_lead_alerts": [
                    {
                        "id": 91,
                        "job_id": 72,
                        "project_title": "Front walk wash",
                        "contractor_name": "Rivera Exterior Care",
                        "city": "Washington",
                        "state": "DC",
                        "status": "sent",
                    }
                ],
                "reports": [
                    {
                        "id": 4,
                        "target_type": "message",
                        "target_id": 9,
                        "reason": "Needs review",
                        "reporter_email": "client@example.com",
                        "message_thread_id": 5,
                        "message_job_title": "Window cleaning",
                    }
                ],
                "users": [
                    {"id": 7, "display_name": "Crew", "email": "crew@example.com", "role": "contractor", "status": "active"},
                    {"id": 1, "display_name": "Admin", "email": "admin@example.com", "role": "admin", "status": "active"},
                ],
                "jobs": [
                    {"id": 12, "title": "Power wash steps", "category": "Power washing", "city": "Arlington", "state": "VA", "status": "open"}
                ],
                "photos": [{"id": 2, "original_filename": "steps.jpg", "title": "Power wash steps", "is_hidden": 0}],
                "contractor_photos": [{"id": 3, "original_filename": "crew.webp", "business_name": "Doe Exterior Care", "is_hidden": 1}],
                "messages": [
                    {"id": 9, "thread_id": 5, "sender_email": "crew@example.com", "job_title": "Window cleaning", "body": "Can start Tuesday.", "is_hidden": 0},
                    {"id": 10, "thread_id": 5, "sender_email": "client@example.com", "job_title": "Window cleaning", "body": "Moderated message.", "is_hidden": 1},
                ],
                "actions": [{"action_type": "hide", "target_type": "message", "target_id": 9, "notes": "Hidden by admin.", "created_at": "2026-08-03T12:00:00+00:00"}],
                "automation_events": [{"event_type": "stale-match-reminder", "target_type": "match_request", "target_id": 4, "status": "queued", "created_at": "2026-08-03T13:00:00+00:00"}],
            },
        )
        self.assertIn("Admin - Workdoe", admin_html)
        self.assertIn("Moderation console", admin_html)
        self.assertIn("<span>Automation</span><strong>4</strong>", admin_html)
        self.assertIn("stale-match-reminder", admin_html)
        self.assertIn("Invitation funnel", admin_html)
        self.assertIn("Project-level only", admin_html)
        self.assertIn("<span>Invited</span><strong>3</strong>", admin_html)
        self.assertIn("33% of invitations", admin_html)
        self.assertIn("Recent repeat invitations", admin_html)
        self.assertIn("Fresh patio wash invitation", admin_html)
        self.assertIn('href="/jobs/61"', admin_html)
        self.assertIn("Matching project alerts", admin_html)
        self.assertIn("Opt-in only", admin_html)
        self.assertIn("<span>Contractors on</span><strong>4</strong>", admin_html)
        self.assertIn("Recent matching alerts", admin_html)
        self.assertIn("Front walk wash", admin_html)
        self.assertIn('href="/jobs/72"', admin_html)
        self.assertEqual(module.dom_id_fragment("/api/admin/reports/4/resolve"), "api-admin-reports-4-resolve")
        self.assertIn('data-json-action="/api/admin/reports/4/resolve"', admin_html)
        self.assertIn('aria-label="Resolve"', admin_html)
        self.assertIn('aria-describedby="admin-action-api-admin-reports-4-resolve-status"', admin_html)
        self.assertIn('id="admin-action-api-admin-reports-4-resolve-status"', admin_html)
        self.assertIn('data-json-action="/api/admin/users/7/suspend"', admin_html)
        self.assertIn('data-json-action="/api/admin/jobs/12/hide"', admin_html)
        self.assertIn('data-json-action="/api/admin/photos/job/2/hide"', admin_html)
        self.assertIn('data-json-action="/api/admin/photos/contractor/3/restore"', admin_html)
        self.assertIn('data-json-action="/api/admin/messages/9/hide"', admin_html)
        self.assertIn('data-json-action="/api/admin/messages/10/restore"', admin_html)
        self.assertIn('href="/messages/5"', admin_html)
        self.assertNotIn("/api/admin/summary", admin_html)

        lead_html = module.lead_board_html(
            contractor,
            {
                "jobs": [
                    {
                        "id": 21,
                        "title": "Clean windows",
                        "category": "Window cleaning",
                        "city": "Alexandria",
                        "state": "VA",
                        "description": "Ground-floor exterior glass.",
                        "license_preference": True,
                        "photo_count": 1,
                        "row_cue": "View",
                        "url": "/jobs/21",
                        "zip_code": "22314",
                    }
                ],
                "map_jobs": [
                    {
                        "id": 21,
                        "title": "Clean windows",
                        "category": "Window cleaning",
                        "city": "Alexandria",
                        "state": "VA",
                        "lat": 38.8048,
                        "lng": -77.0469,
                        "url": "/jobs/21",
                        "action_label": "View",
                        "license_preference": True,
                    }
                ],
                "filters": {
                    "family": "cleaning-upkeep",
                    "service": "window-cleaning",
                    "category": "Window cleaning",
                    "q": "Alexandria",
                    "sort": "newest",
                },
                "view": "all",
                "stats": {
                    "visible_jobs": 1,
                    "all_jobs": 1,
                    "new_jobs": 1,
                    "sent_bids": 0,
                },
                "view_links": [
                    {"value": "all", "label": "All", "url": "/leads"},
                    {"value": "new", "label": "New", "url": "/leads?view=new"},
                    {"value": "sent", "label": "Sent", "url": "/leads?view=sent"},
                ],
                "preferences": {
                    "has_saved_lead_view": True,
                    "saved_category": "Window cleaning",
                    "saved_service_group_slug": "cleaning-upkeep",
                    "saved_service_slug": "window-cleaning",
                    "saved_service_label": "Window cleaning",
                    "saved_family_label": "Cleaning & upkeep",
                    "saved_query": "Alexandria",
                    "saved_sort": "newest",
                    "lead_alert_preference": "email",
                    "lead_alert_enabled": True,
                },
                "saved_lead_view_url": "/leads?family=cleaning-upkeep&service=window-cleaning&category=Window+cleaning&q=Alexandria",
            },
        )
        self.assertIn('id="lead-map"', lead_html)
        self.assertEqual(module.photo_count_label(1), "1 photo")
        self.assertEqual(module.photo_count_label(None), "0 photos")
        self.assertIn(
            f'src="/map.js?v={module.ASSET_RELEASE_TOKEN}"',
            lead_html,
        )
        self.assertIn('class="market-workspace signed-in-market-workspace"', lead_html)
        self.assertIn('id="lead-results" class="project-results" data-project-results aria-label="Open leads" role="list"', lead_html)
        self.assertIn('class="market-map-stage"', lead_html)
        self.assertIn('class="market-detail-rail"', lead_html)
        self.assertIn('leaflet.markercluster.js', lead_html)
        self.assertIn('class="lead-view-tabs" aria-label="Lead status"', lead_html)
        self.assertIn('<span>Bids sent</span><strong>0</strong>', lead_html)
        self.assertIn('<details class="lead-tools" open>', lead_html)
        self.assertIn("Filters &amp; alerts", lead_html)
        self.assertIn("Window cleaning / Newest", lead_html)
        self.assertIn('class="lead-tools-alert-state is-on">Email on</span>', lead_html)
        self.assertIn("License preferred", lead_html)
        self.assertIn(
            "Preference only. Confirm whether your license covers this work and jurisdiction.",
            lead_html,
        )
        self.assertIn('role="listitem"', lead_html)
        self.assertIn('class="project-result-item" role="listitem"', lead_html)
        self.assertIn('class="project-result-action">View</span>', lead_html)
        self.assertNotIn('class="project-result is-map-active" role="listitem"', lead_html)
        self.assertIn('data-job-id="21"', lead_html)
        self.assertIn('aria-label="View Clean windows"', lead_html)
        self.assertIn('<span>1 photo</span>', lead_html)
        self.assertIn('class="job-service-chip"', lead_html)
        self.assertIn('/vendor/tabler-icons/window.svg', lead_html)
        self.assertIn("Ground-floor exterior glass.", lead_html)
        self.assertIn('data-dialog-title="Review and bid"', lead_html)
        self.assertIn(">Review and bid</a>", lead_html)
        self.assertIn('id="saved-lead-alerts"', lead_html)
        self.assertIn('name="lead_alert_preference"', lead_html)
        self.assertEqual(lead_html.count('class="service-family-filter-link'), 7)
        self.assertIn('/vendor/tabler-icons/spray.svg', lead_html)
        self.assertIn('name="family" value="cleaning-upkeep"', lead_html)
        self.assertIn('id="market-service" name="service" data-market-service', lead_html)
        self.assertIn('value="window-cleaning" selected', lead_html)
        self.assertIn(
            'name="saved_service_group_slug" value="cleaning-upkeep"',
            lead_html,
        )
        self.assertIn(
            'name="saved_service_slug" value="window-cleaning"',
            lead_html,
        )
        self.assertIn("Window cleaning near Alexandria", lead_html)
        self.assertIn('value="email" checked', lead_html)
        self.assertIn("Email alerts on", lead_html)
        self.assertIn("your services and DMV zones", lead_html)
        self.assertNotIn("22314", lead_html)
        marker = '<script id="map-jobs-data" type="application/json">'
        parsed = json.loads(lead_html.split(marker, 1)[1].split("</script>", 1)[0])
        self.assertEqual(parsed[0]["url"], "/jobs/21")

        detail_html = module.contractor_job_detail_html(
            contractor,
            {
                "job": {
                    "id": 21,
                    "title": "Clean windows",
                    "category": "Window cleaning",
                    "area_label": "Alexandria, VA 223xx",
                    "description": "Ground-floor exterior glass.",
                    "status": "open",
                    "can_request_match": True,
                    "location_privacy": "Contractors see city/state and ZIP prefix only.",
                },
                "photos": [],
            },
            site_key="turnstile-site-key",
        )
        self.assertIn('data-json-action="/api/jobs/21/request"', detail_html)
        self.assertIn('aria-label="Send mini bid"', detail_html)
        self.assertIn('aria-describedby="bid-form-status"', detail_html)
        self.assertIn('id="bid-form-status"', detail_html)
        self.assertIn('id="bid-scope-note"', detail_html)
        self.assertIn('placeholder="Work included, assumptions, access needs."', detail_html)
        self.assertIn('autocapitalize="sentences"', detail_html)
        self.assertIn('spellcheck="true"', detail_html)
        self.assertIn('enterkeyhint="next"', detail_html)
        self.assertIn('list="bid-price-options"', detail_html)
        self.assertIn('list="bid-timeline-options"', detail_html)
        self.assertIn('list="bid-availability-options"', detail_html)
        self.assertIn('id="bid-price-options"', detail_html)
        self.assertIn('value="On-site estimate needed"', detail_html)
        self.assertIn('value="Two business days after approval"', detail_html)
        self.assertIn('value="Weekend available"', detail_html)
        self.assertIn('id="bid-questions"', detail_html)
        self.assertIn('enterkeyhint="done"', detail_html)
        self.assertIn("Send bid", detail_html)
        self.assertIn("223xx", detail_html)

        embedded_detail_html = module.contractor_job_detail_html(
            contractor,
            {
                "job": {
                    "id": 21,
                    "title": "Clean windows",
                    "category": "Window cleaning",
                    "area_label": "Alexandria, VA 223xx",
                    "description": "Ground-floor exterior glass.",
                    "desired_date": "2026-09-15",
                    "budget": "$300-$450",
                    "status": "open",
                    "can_request_match": True,
                    "location_privacy": "Contractors see city/state and ZIP prefix only.",
                },
                "photos": [],
            },
            site_key="turnstile-site-key",
            embedded=True,
        )
        self.assertIn('<body class="dialog-fragment-body">', embedded_detail_html)
        self.assertNotIn("data-site-dialog", embedded_detail_html)
        self.assertIn("data-dialog-fragment data-bid-flow", embedded_detail_html)
        self.assertIn('class="dialog-project-snapshot"', embedded_detail_html)
        self.assertIn("$300-$450", embedded_detail_html)

        client_job_html = module.client_job_detail_html(
            client,
            {
                "job": {
                    "id": 12,
                    "title": "Power wash steps",
                    "category": "Power washing",
                    "area_label": "Arlington, VA 22201",
                    "description": "Townhouse front steps.",
                    "desired_date": "2026-08-14",
                    "status": "open",
                    "bid_window": {
                        "state": "open",
                        "availability_label": "2 bid spots open",
                        "usage_label": "2 of 4 bids",
                        "deadline_label": "Aug 30 at 5:00 PM UTC",
                        "used": 2,
                        "limit": 4,
                        "is_expired": False,
                        "can_extend": False,
                    },
                },
                "photos": [{"id": 2, "url": "/media/jobs/2", "original_filename": "steps.jpg"}],
            },
            {
                "view": "pending",
                "requests": [
                    {
                        "id": 31,
                        "job_id": 12,
                        "contractor_name": "Doe Exterior Care",
                        "trades": "Power washing",
                        "status": "pending",
                        "scope_note": "I can protect surrounding surfaces.",
                        "price_range": "$450-$650",
                        "timeline": "Two days",
                        "experience": "Five years in the DMV.",
                        "questions": "Is there hose access?",
                        "availability": "Tuesday",
                        "can_approve": True,
                    },
                    {
                        "id": 32,
                        "job_id": 12,
                        "contractor_name": "Approved Crew",
                        "trades": "Exterior cleaning",
                        "status": "approved",
                        "scope_note": "Ready to coordinate.",
                        "price_range": "$300-$450",
                        "timeline": "Friday",
                        "experience": "Storefront team.",
                        "availability": "Friday",
                        "thread_url": "/messages/5",
                    },
                ],
                "approved_request": {
                    "id": 32,
                    "contractor_id": 10,
                    "contractor_name": "Approved Crew",
                    "price_range": "$300-$450",
                    "timeline": "Friday",
                    "availability": "Friday",
                    "thread_url": "/messages/5",
                    "profile_url": "/contractors/10",
                    "completion_state": "awaiting",
                    "completion_label": "Awaiting both confirmations",
                },
                "stats": {"pending": 1, "approved": 1, "total": 2},
                "comparison": {
                    "order_label": "Received order",
                    "count": 1,
                    "offers": [
                        {
                            "id": 31,
                            "offer_label": "Offer 1",
                            "contractor_name": "Doe Exterior Care",
                            "trades": "Power washing",
                            "profile_url": "/contractors/7",
                            "profile_photo_url": "/media/contractors/4",
                            "price_range": "$450-$650",
                            "timeline": "Two days",
                            "availability": "Tuesday",
                            "scope_note": "I can protect surrounding surfaces.",
                            "experience": "Five years in the DMV.",
                            "questions": "Is there hose access?",
                            "reputation": {
                                "level_label": "First finish",
                                "completion_points": 100,
                                "credential_signals": [
                                    {
                                        "label": "License source checked",
                                        "qualifier": "Current public record",
                                    }
                                ],
                            },
                            "provider_facts": [
                                {
                                    "key": "years-active",
                                    "label": "Years active",
                                    "value": "5 years",
                                    "qualifier": "Self-reported",
                                },
                                {
                                    "key": "source-checked",
                                    "label": "Source checked",
                                    "value": "1 credential",
                                    "qualifier": "Current records",
                                },
                                {
                                    "key": "workdoe-completed",
                                    "label": "Workdoe-completed",
                                    "value": "2 projects",
                                    "qualifier": "Both sides confirmed",
                                },
                                {
                                    "key": "insurance",
                                    "label": "Insurance",
                                    "value": "Self-reported",
                                    "qualifier": "Not verified by Workdoe",
                                },
                            ],
                        }
                    ],
                },
                "view_links": [
                    {"value": "all", "label": "All", "url": "/client/jobs/12#mini-bids"},
                    {"value": "pending", "label": "Pending", "url": "/client/jobs/12?bids=pending#mini-bids"},
                ],
            },
        )
        self.assertIn("Power wash steps - Workdoe", client_job_html)
        self.assertIn(
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            client_job_html,
        )
        self.assertIn('<meta name="theme-color" content="#1b2b22">', client_job_html)
        self.assertIn('<link rel="canonical" href="https://workdoe.com/">', client_job_html)
        self.assertIn(
            '<meta property="og:image" content="https://workdoe.com/workdoe-share.png">',
            client_job_html,
        )
        self.assertIn('<link rel="icon" href="/deer.svg" type="image/svg+xml">', client_job_html)
        self.assertIn('<link rel="manifest" href="/site.webmanifest">', client_job_html)
        self.assertIn("Job controls", client_job_html)
        self.assertIn('aria-label="Bid availability"', client_job_html)
        self.assertIn('aria-labelledby="approved-match-title"', client_job_html)
        self.assertIn('href="/contractors/10">Profile</a>', client_job_html)
        self.assertIn('href="/client/jobs/12/edit"', client_job_html)
        self.assertIn('data-json-action="/api/jobs/12/close"', client_job_html)
        self.assertIn('aria-label="Close Power wash steps"', client_job_html)
        self.assertIn('aria-describedby="job-status-form-status"', client_job_html)
        self.assertIn('id="job-status-form-status"', client_job_html)
        self.assertIn('data-inline-dialog-open="close-job-dialog"', client_job_html)
        self.assertIn("Where did this project land?", client_job_html)
        self.assertIn('value="workdoe-match"', client_job_html)
        self.assertIn('data-file-action="/api/media/jobs/12/upload"', client_job_html)
        self.assertIn('aria-label="Upload job photo"', client_job_html)
        self.assertIn('for="job-photo-upload"', client_job_html)
        self.assertIn('id="job-photo-upload"', client_job_html)
        self.assertIn('name="photo"', client_job_html)
        self.assertIn("Upload photo", client_job_html)
        self.assertIn('data-json-action="/api/match-requests/31/approve"', client_job_html)
        self.assertIn('data-inline-dialog-open="choose-contractor-31"', client_job_html)
        self.assertIn('id="choose-contractor-31"', client_job_html)
        self.assertIn('aria-label="Choose Doe Exterior Care"', client_job_html)
        self.assertIn('aria-describedby="choose-contractor-31-status"', client_job_html)
        self.assertIn('id="choose-contractor-31-status"', client_job_html)
        self.assertIn("closes the other pending offers", client_job_html)
        self.assertIn('data-json-action="/api/match-requests/31/reject"', client_job_html)
        self.assertIn('aria-label="Reject mini bid from Doe Exterior Care"', client_job_html)
        self.assertIn('aria-describedby="comparison-reject-31-status"', client_job_html)
        self.assertIn('id="comparison-reject-31-status"', client_job_html)
        self.assertIn('href="/messages/5"', client_job_html)
        self.assertIn("Contractor choice", client_job_html)
        self.assertIn("Compare offers", client_job_html)
        self.assertIn("Received order", client_job_html)
        self.assertNotIn('class="selection-path"', client_job_html)
        self.assertIn("Work and reviewed-record signals", client_job_html)
        self.assertIn("License source checked", client_job_html)
        self.assertIn("Workdoe-completed", client_job_html)
        self.assertIn(
            'class="bid-contractor-photo" src="/media/contractors/4"',
            client_job_html,
        )
        self.assertIn('alt="Doe Exterior Care portfolio"', client_job_html)
        self.assertIn('src="/vendor/tabler-icons/sparkles.svg"', client_job_html)
        self.assertNotIn('src="/static/vendor/tabler-icons/sparkles.svg"', client_job_html)
        self.assertIn('class="bid-card-offer"', client_job_html)
        self.assertIn("Offer details", client_job_html)
        self.assertIn("I can protect surrounding surfaces.", client_job_html)
        self.assertIn("Five years in the DMV.", client_job_html)
        self.assertIn("Is there hose access?", client_job_html)
        self.assertNotIn('href="#bid-title-31"', client_job_html)
        self.assertNotIn('id="bid-title-31"', client_job_html)
        self.assertIn("no paid ranking", client_job_html)
        self.assertIn(
            'data-json-action="/api/match-requests/31/approve"', client_job_html
        )
        self.assertIn('data-success-url-template="/client/jobs/12"', client_job_html)
        self.assertIn('aria-label="Choose Doe Exterior Care"', client_job_html)
        self.assertIn('aria-describedby="choose-contractor-31-status"', client_job_html)
        self.assertIn('id="choose-contractor-31-status"', client_job_html)
        self.assertIn(">Choose contractor</button>", client_job_html)
        self.assertIn('src="/worker-actions.js"', client_job_html)
        self.assertNotIn("contractor@example.com", client_job_html)

        headers = module.app_shell_headers(include_map=True, include_turnstile=True)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(
            headers["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains",
        )
        self.assertIn("https://tile.openstreetmap.org", headers["Content-Security-Policy"])
        self.assertIn("https://challenges.cloudflare.com", headers["Content-Security-Policy"])

        account_html = module.account_security_html(
            {**client, "email": "client@example.com"},
            clerk_publishable_key="pk_live_workdoe",
            clerk_frontend_api_url="https://workdoe.com/__clerk",
        )
        self.assertIn("Account &amp; security", account_html)
        self.assertIn("client@example.com", account_html)
        self.assertIn('data-clerk-account', account_html)
        self.assertIn('src="/clerk-account.js"', account_html)
        self.assertIn("@clerk/ui@1/dist/ui.browser.js", account_html)
        self.assertIn('data-clerk-proxy-url="https://workdoe.com/__clerk"', account_html)
        self.assertNotIn("accounts.workdoe.com", account_html)
        account_headers = module.app_shell_headers(
            include_clerk=True,
            clerk_publishable_key="pk_live_workdoe",
            clerk_frontend_api_url="https://workdoe.com/__clerk",
        )
        account_csp = account_headers["Content-Security-Policy"]
        self.assertIn("https://*.protect.clerk.com", account_csp)
        self.assertIn("https://img.clerk.com", account_csp)
        self.assertIn("worker-src 'self' blob:", account_csp)
        clerk_account_script = (ROOT / "workdoe" / "static" / "clerk-account.js").read_text(encoding="utf-8")
        self.assertIn('mountUserProfile(node, { routing: "hash" })', clerk_account_script)
        self.assertIn("telemetry: false", clerk_account_script)
        self.assertIn("window.__internal_ClerkUICtor", clerk_account_script)

        script = (ROOT / "workdoe" / "static" / "worker-actions.js").read_text(encoding="utf-8")
        self.assertIn("[data-json-action]", script)
        self.assertIn("[data-file-action]", script)
        self.assertIn("credentials: \"include\"", script)
        self.assertIn("new FormData(form)", script)
        self.assertIn("data-upload-after-json-template", form_html)
        self.assertIn("uploadFilesAfterJson", script)
        self.assertIn("value instanceof File", script)
        self.assertIn("uploadData.append(\"photo\"", script)
        self.assertIn("Array.isArray(data[key])", script)
        self.assertIn("\"Content-Type\": \"application/json\"", script)
        self.assertIn('"X-Workdoe-Request": "same-origin"', script)
        self.assertIn("[data-form-status]", script)
        self.assertIn("payload.field_errors", script)
        self.assertIn("showFieldErrors", script)
        self.assertIn("clearFieldErrors", script)
        self.assertIn("setSubmitting", script)
        self.assertIn("data-worker-field-error", script)
        self.assertIn("aria-invalid", script)
        self.assertIn("aria-busy", script)
        self.assertIn("Fix highlighted fields.", script)
        self.assertIn("return hasErrors", script)
        self.assertIn("delete node.dataset.originalDescribedby", script)
        self.assertIn("scrollIntoView", script)
        self.assertIn("details.open = true", script)
        self.assertIn("control.name === field", script)
        self.assertNotIn("CSS.escape", script)
        for shell_html in (form_html, profile_html, detail_html, thread_html, client_job_html):
            with self.subTest(page_title=shell_html.split("<title>", 1)[-1].split("</title>", 1)[0]):
                self.assertIn('<html lang="en">', shell_html)
                self.assertIn('<a class="skip-link" href="#main-content">Skip to content</a>', shell_html)
                self.assertIn('<nav class="main-nav" aria-label="Primary">', shell_html)
                self.assertIn('id="main-content"', shell_html)
                self.assertIn('tabindex="-1"', shell_html)
                self.assertLess(shell_html.index('class="skip-link"'), shell_html.index('<header class="site-header">'))
                self.assertLess(shell_html.index('<header class="site-header">'), shell_html.index('id="main-content"'))
        entrypoint = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(encoding="utf-8")
        self.assertIn('"field_errors": exc.field_errors', entrypoint)
        self.assertIn('environment != "production" and result_action == "test"', entrypoint)
        self.assertIn('row_value(metadata, "result_with_testing_key", False)', entrypoint)
        self.assertIn('allowed_hosts.update({"localhost", "127.0.0.1", "0.0.0.0"})', entrypoint)

        clerk_script = (ROOT / "workdoe" / "static" / "clerk-entry.js").read_text(encoding="utf-8")
        self.assertIn("finishSignIn", clerk_script)
        self.assertIn("node.dataset.signUpUrl", clerk_script)
        self.assertIn("clerkUserEmail", clerk_script)
        self.assertIn("onboardPayload.email = email", clerk_script)
        self.assertIn("window.__internal_ClerkUICtor", clerk_script)
        self.assertIn("window.Clerk.mountSignIn", clerk_script)
        self.assertIn("withSignUp: true", clerk_script)
        self.assertIn("forceRedirectUrl: returnUrl", clerk_script)
        self.assertIn("signUpForceRedirectUrl: returnUrl", clerk_script)
        self.assertIn("window.sessionStorage.setItem", clerk_script)
        self.assertIn("PROFILE_STATE_MAX_AGE_MS", clerk_script)
        self.assertIn('routing: "hash"', clerk_script)
        self.assertNotIn("window.Clerk.client.signIn", clerk_script)
        self.assertNotIn("window.Clerk.client.signUp", clerk_script)
        self.assertNotIn("prepareFirstFactor", clerk_script)
        self.assertNotIn("attemptFirstFactor", clerk_script)
        self.assertNotIn("prepareEmailAddressVerification", clerk_script)
        self.assertNotIn("attemptEmailAddressVerification", clerk_script)
        self.assertNotIn("Math.random", clerk_script)
        self.assertIn('"X-Workdoe-Request": "same-origin"', clerk_script)
        email_code_script = (ROOT / "workdoe" / "static" / "email-code-entry.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('"X-Workdoe-Request": "same-origin"', email_code_script)
        styles = (ROOT / "workdoe" / "static" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(".clerk-entry-status", styles)

    def test_cloudflare_app_shell_escapes_marketplace_content(self):
        module = load_app_shell_module()
        hostile = '<script>alert("workdoe")</script>'
        escaped = "&lt;script&gt;alert(&quot;workdoe&quot;)&lt;/script&gt;"
        client = {"id": 8, "role": "client", "status": "active", "display_name": hostile}
        contractor = {"id": 7, "role": "contractor", "status": "active", "display_name": hostile}
        admin = {"id": 1, "role": "admin", "status": "active", "display_name": "Admin"}

        rendered = [
            module.client_dashboard_html(
                client,
                {
                    "jobs": [
                        {
                            "id": 12,
                            "title": hostile,
                            "category": hostile,
                            "city": hostile,
                            "state": "VA",
                            "description": hostile,
                            "status": "open",
                            "url": "/client/jobs/12",
                            "row_cue": hostile,
                        }
                    ],
                    "stats": {},
                },
            ),
            module.contractor_profile_html(
                contractor,
                {
                    "business_name": hostile,
                    "trades": "Painting",
                    "service_area": hostile,
                    "intro": hostile,
                    "insurance_status": hostile,
                    "license_number": hostile,
                    "website": "",
                    "phone": "",
                },
                [{"id": 4, "original_filename": hostile}],
            ),
            module.message_thread_detail_html(
                client,
                {
                    "thread": {
                        "id": 5,
                        "title": hostile,
                        "category": hostile,
                        "city": hostile,
                        "state": "VA",
                        "client_name": hostile,
                        "contractor_name": hostile,
                    },
                    "messages": [
                        {
                            "id": 9,
                            "sender_id": 7,
                            "sender_name": hostile,
                            "body": hostile,
                            "created_at": "2026-08-16T12:00:00+00:00",
                        }
                    ],
                },
                can_reply=True,
            ),
            module.admin_dashboard_html(
                admin,
                {
                    "stats": {},
                    "reports": [
                        {
                            "id": 4,
                            "target_type": "job",
                            "target_id": 12,
                            "reason": hostile,
                            "reporter_email": hostile,
                            "job_title": hostile,
                        }
                    ],
                    "users": [],
                    "jobs": [],
                    "photos": [],
                    "contractor_photos": [],
                    "messages": [],
                    "actions": [],
                    "automation_events": [],
                },
            ),
        ]

        for html in rendered:
            self.assertNotIn(hostile, html)
            self.assertIn(escaped, html)

    def test_cloudflare_contractor_leads_helper_matches_lead_board_contract(self):
        module = load_contractor_leads_module()
        self.assertEqual(module.parse_contractor_lead_limit("999"), 50)
        self.assertEqual(module.parse_contractor_lead_limit("0"), 1)
        self.assertEqual(module.normalize_contractor_lead_view("sent"), "sent")
        self.assertEqual(module.normalize_contractor_lead_view("bad"), "all")
        filters = module.contractor_lead_filters_from_query(
            {
                "category": ["Painting"],
                "family": ["remodel-finish"],
                "service": ["interior-painting"],
                "q": ["  Arlington   VA  "],
                "sort": ["soonest"],
            }
        )
        self.assertEqual(
            filters,
            {
                "category": "Painting",
                "family": "remodel-finish",
                "service": "interior-painting",
                "q": "Arlington VA",
                "sort": "soonest",
            },
        )
        self.assertEqual(
            module.contractor_lead_filters_from_query(
                {
                    "category": ["Unknown"],
                    "family": ["unknown-family"],
                    "service": ["unknown-task"],
                    "q": ["A" * 120],
                    "sort": ["bad"],
                }
            ),
            {"category": "", "family": "", "service": "", "q": "A" * 80, "sort": "newest"},
        )
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        client = {"id": 8, "role": "client", "status": "active"}
        suspended = {"id": 7, "role": "contractor", "status": "suspended"}
        self.assertTrue(module.can_view_contractor_leads(contractor))
        self.assertFalse(module.can_view_contractor_leads(client))
        self.assertFalse(module.can_view_contractor_leads(suspended))

        rows = [
            {
                "id": 12,
                "title": "Power wash steps",
                "category": "Power washing",
                "service_group_slug": "outdoor-yard",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "description": "Townhouse front steps need cleaning.",
                "desired_date": "2026-09-01",
                "created_at": "2026-08-03T12:00:00+00:00",
                "approx_lat": 38.8871,
                "approx_lng": -77.0932,
                "photo_count": 2,
                "request_status": "pending",
                "client_id": 8,
                "client_email": "private@example.com",
                "license_preference": 1,
            },
            {
                "id": 13,
                "title": "Clean storefront windows",
                "category": "Window cleaning",
                "service_group_slug": "cleaning-upkeep",
                "service_slug": "window-cleaning",
                "city": "Alexandria",
                "state": "VA",
                "zip_code": "22314",
                "description": "Ground-floor windows before opening.",
                "desired_date": "",
                "created_at": "2026-08-02T12:00:00+00:00",
                "approx_lat": None,
                "approx_lng": None,
                "photo_count": None,
                "request_status": None,
            },
        ]
        payload = module.contractor_leads_payload(
            rows,
            filters=filters,
            view="sent",
            service_slugs=["pressure-washing"],
            service_zone_slugs=["arlington-county-va"],
        )
        self.assertEqual(payload["view"], "sent")
        self.assertEqual(payload["stats"]["all_jobs"], 2)
        self.assertEqual(payload["stats"]["visible_jobs"], 1)
        self.assertEqual(payload["stats"]["new_jobs"], 1)
        self.assertEqual(payload["stats"]["sent_bids"], 1)
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["url"], "/jobs/12")
        self.assertEqual(payload["jobs"][0]["request_status"], "pending")
        self.assertFalse(payload["jobs"][0]["can_request_match"])
        self.assertEqual(payload["jobs"][0]["fit_label"], "Best fit")
        self.assertEqual(payload["jobs"][0]["fit_score"], 3)
        self.assertTrue(payload["jobs"][0]["license_preference"])
        self.assertTrue(payload["map_jobs"][0]["license_preference"])
        self.assertEqual(payload["map_jobs"][0]["action_label"], "View bid status")
        self.assertEqual(payload["map_jobs"][0]["description"], "Townhouse front steps need cleaning.")
        self.assertEqual(payload["map_jobs"][0]["desired_date"], "2026-09-01")
        self.assertFalse(payload["map_jobs"][0]["is_demo"])
        self.assertEqual(payload["count"], 1)
        self.assertNotIn("zip_code", payload["jobs"][0])
        self.assertNotIn("client_id", payload["jobs"][0])
        self.assertNotIn("client_email", payload["jobs"][0])
        self.assertEqual(payload["jobs"][0]["service_group_slug"], "outdoor-yard")

        new_payload = module.contractor_leads_payload(rows, filters=filters, view="new")
        self.assertEqual(len(new_payload["jobs"]), 1)
        self.assertEqual(new_payload["jobs"][0]["id"], 13)
        self.assertEqual(new_payload["count"], 0)

    def test_cloudflare_contractor_preferences_are_deterministic_and_private(self):
        module = load_contractor_preferences_module()
        availability = module.availability_payload(
            {"availability_status": "limited", "available_from": "2030-06-15"}
        )
        self.assertEqual(
            availability,
            {"availability_status": "limited", "available_from": "2030-06-15"},
        )
        saved = module.saved_lead_view_payload(
            {
                "saved_category": "Painting",
                "saved_service_group_slug": "remodel-finish",
                "saved_service_slug": "interior-painting",
                "saved_query": "  Arlington   VA  ",
                "saved_sort": "soonest",
            },
            categories={"Painting", "Plumbing"},
            sorts={"newest", "soonest", "city"},
            families={"remodel-finish", "home-systems"},
        )
        self.assertEqual(
            saved,
            {
                "saved_category": "Painting",
                "saved_service_group_slug": "remodel-finish",
                "saved_service_slug": "interior-painting",
                "saved_query": "Arlington VA",
                "saved_sort": "soonest",
                "lead_alert_preference": "workdoe",
            },
        )
        row = {
            **availability,
            **saved,
            "saved_at": "2026-08-17T12:00:00+00:00",
            "updated_at": "2026-08-17T12:00:00+00:00",
        }
        response = module.contractor_preferences_response(row)
        self.assertTrue(response["has_saved_lead_view"])
        self.assertEqual(
            module.saved_lead_view_url(row),
            "/leads?family=remodel-finish&service=interior-painting&category=Painting&q=Arlington+VA&sort=soonest",
        )
        self.assertEqual(
            response["availability"]["label"],
            "Taking new work from 2030-06-15",
        )
        consented = module.saved_lead_view_payload(
            {
                "saved_category": "Painting",
                "saved_service_group_slug": "remodel-finish",
                "saved_service_slug": "interior-painting",
                "saved_query": "Arlington VA",
                "saved_sort": "soonest",
                "lead_alert_preference": "email",
            },
            categories={"Painting"},
            sorts={"soonest"},
            families={"remodel-finish"},
        )
        consented_response = module.contractor_preferences_response(
            {
                **consented,
                "saved_at": "2026-08-17T12:00:00+00:00",
                "lead_alert_consent_at": "2026-08-17T12:00:00+00:00",
            }
        )
        self.assertTrue(consented_response["lead_alert_enabled"])
        self.assertEqual(consented_response["lead_alert_preference"], "email")
        self.assertEqual(
            module.contractor_preferences_response(consented)["lead_alert_preference"],
            "workdoe",
        )
        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0018_contractor_lead_alerts.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN lead_alert_preference", migration)
        self.assertIn("ADD COLUMN lead_alert_consent_at", migration)
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS contractor_lead_alert_deliveries",
            migration,
        )
        self.assertIn("UNIQUE(contractor_id, job_id)", migration)
        self.assertNotIn("zip_code", migration)
        self.assertNotIn("client_email", migration)
        family_migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0021_saved_lead_work_family.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN saved_service_group_slug", family_migration)
        self.assertIn("idx_contractor_lead_preferences_family", family_migration)
        self.assertNotIn("zip_code", family_migration)
        task_migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0025_saved_lead_task.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN saved_service_slug", task_migration)
        self.assertIn("idx_contractor_lead_preferences_service", task_migration)
        self.assertNotIn("zip_code", task_migration)
        with self.assertRaises(module.ContractorPreferenceError):
            module.saved_lead_view_payload(
                {
                    "saved_service_group_slug": "home-systems",
                    "saved_service_slug": "interior-painting",
                    "saved_sort": "newest",
                },
                categories={"Painting"},
                sorts={"newest"},
                families={"remodel-finish", "home-systems"},
            )
        with self.assertRaises(module.ContractorPreferenceError):
            module.saved_lead_view_payload(
                {
                    "saved_category": "Unknown",
                    "saved_service_group_slug": "unknown-family",
                    "saved_sort": "paid-first",
                },
                categories={"Painting"},
                sorts={"newest"},
                families={"remodel-finish"},
            )

        public_profiles = load_contractor_public_profiles_module()
        payload = public_profiles.public_contractor_profile_payload(
            {
                "id": 7,
                "status": "active",
                "business_name": "Doe Exterior Care",
                **availability,
            },
            [],
            None,
            availability={**availability, "saved_query": "private search"},
        )
        contractor = payload["contractor"]
        self.assertEqual(contractor["availability"]["status"], "limited")
        self.assertNotIn("saved_query", contractor)
        self.assertNotIn("private search", json.dumps(payload))

    def test_cloudflare_consumer_project_templates_copy_only_reusable_scope(self):
        module = load_client_project_templates_module()
        request = module.project_template_request_payload(
            {"name": "  Monthly   exterior reset  ", "source_job_id": "17"}
        )
        self.assertEqual(
            request,
            {"name": "Monthly exterior reset", "source_job_id": 17},
        )
        with self.assertRaises(module.ProjectTemplateError):
            module.project_template_request_payload(
                {"name": "", "source_job_id": "another-client"}
            )
        row = {
            "id": 4,
            "name": "Monthly exterior reset",
            "source_job_id": 17,
            "service_group_slug": "outdoor-yard",
            "service_slug": "pressure-washing",
            "category": "Power washing",
            "title": "Wash storefront entrance",
            "description": "Clean the entrance and protect adjacent surfaces.",
            "project_setting": "business",
            "license_preference": 1,
            "budget_min": 450,
            "budget_max": 700,
            "city": "Private city must not copy",
            "zip_code": "99999",
            "desired_date": "2030-01-01",
            "stored_path": "private/object.webp",
        }
        response = module.project_template_response(row)
        self.assertEqual(response["use_url"], "/jobs/new?template=4")
        self.assertNotIn("city", response)
        self.assertNotIn("zip_code", response)
        self.assertNotIn("desired_date", response)
        self.assertNotIn("stored_path", response)
        self.assertEqual(response["license_preference"], 1)
        form = module.project_template_job_form(row)
        self.assertEqual(form["city"], "")
        self.assertEqual(form["zip_code"], "")
        self.assertEqual(form["desired_date"], "")
        self.assertEqual(form["title"], "Wash storefront entrance")
        self.assertEqual(form["license_preference"], "1")

        shell = load_app_shell_module()
        html = shell.client_profile_html(
            {"id": 8, "role": "client", "status": "active", "display_name": "Client"},
            {
                "organization_name": "Main Street Shop",
                "account_type": "small-business",
                "notification_preference": "workdoe",
                "profile_note": "",
            },
            [],
            [response],
            [{"id": 17, "title": "Wash storefront entrance", "status": "closed"}],
            17,
        )
        self.assertIn('data-json-action="/api/client/templates"', html)
        self.assertIn('value="17" selected', html)
        self.assertIn("Location, date, photos, bids, and messages are never copied.", html)
        self.assertIn('href="/jobs/new?template=4"', html)
        self.assertNotIn("Private city must not copy", html)

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0016_client_project_templates.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS client_project_templates", migration)
        self.assertIn("UNIQUE(client_id, name)", migration)
        self.assertNotIn("zip_code", migration)
        self.assertNotIn("desired_date", migration)
        self.assertNotIn("photo", migration)

    def test_cloudflare_contractor_proposal_templates_require_a_fresh_price(self):
        module = load_contractor_proposal_templates_module()
        request = module.proposal_template_request_payload(
            {"name": "  Exterior   standard  ", "source_match_request_id": "41"}
        )
        self.assertEqual(
            request,
            {"name": "Exterior standard", "source_match_request_id": 41},
        )
        with self.assertRaises(module.ProposalTemplateError):
            module.proposal_template_request_payload(
                {"name": "", "source_match_request_id": "another-contractor"}
            )
        row = {
            "id": 7,
            "name": "Exterior standard",
            "source_match_request_id": 41,
            "scope_note": "Protect adjacent surfaces and clean the work area.",
            "price_range": "$900-$1,200",
            "timeline": "Two business days",
            "experience": "Five similar storefront projects completed.",
            "questions": "Is exterior water access available?",
            "availability": "Weekday mornings",
            "email": "private@example.com",
            "exact_address": "123 Private Street",
        }
        response = module.proposal_template_response(row)
        self.assertNotIn("price_range", response)
        self.assertNotIn("email", response)
        self.assertNotIn("exact_address", response)
        form = module.proposal_template_bid_form(row)
        self.assertEqual(form["price_range"], "")
        self.assertEqual(form["timeline"], "Two business days")
        self.assertEqual(
            module.parse_proposal_template_delete_path(
                "/api/contractor/proposal-templates/7/delete"
            ),
            7,
        )
        with self.assertRaises(module.ProposalTemplateError):
            module.parse_proposal_template_delete_path(
                "/api/contractor/proposal-templates/not-a-number/delete"
            )

        shell = load_app_shell_module()
        dashboard_html = shell.contractor_dashboard_html(
            {"id": 8, "role": "contractor", "status": "active"},
            {
                "profile": {"business_name": "Doe Exterior Care"},
                "stats": {},
                "proposal_templates": [response],
                "proposal_template_limit": 6,
            },
        )
        self.assertIn('id="proposal-templates"', dashboard_html)
        self.assertIn("Exterior standard", dashboard_html)
        self.assertIn(
            'data-json-action="/api/contractor/proposal-templates/7/delete"',
            dashboard_html,
        )
        self.assertIn("requires a fresh price", dashboard_html)
        self.assertNotIn("$900-$1,200", dashboard_html)

        detail_html = shell.contractor_job_detail_html(
            {"id": 8, "role": "contractor", "status": "active"},
            {
                "job": {
                    "id": 41,
                    "title": "Wash storefront entrance",
                    "category": "Power washing",
                    "area_label": "Arlington, VA 222xx",
                    "description": "Clean the entrance and protect adjacent surfaces.",
                    "status": "open",
                    "can_request_match": True,
                    "location_privacy": "Contractors see city/state and ZIP prefix only.",
                },
                "photos": [],
                "proposal_templates": [response],
                "proposal_template_limit": 6,
                "proposal_template_name_max_length": 60,
                "selected_proposal_template": response,
                "bid_form": form,
            },
            site_key="turnstile-site-key",
        )
        self.assertIn("Template applied", detail_html)
        self.assertIn("Exterior standard", detail_html)
        self.assertIn("add a project-specific price", detail_html)
        self.assertIn('placeholder="Add a fresh estimate"', detail_html)
        self.assertIn(
            "Protect adjacent surfaces and clean the work area.", detail_html
        )
        self.assertNotIn("$900-$1,200", detail_html)

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0023_contractor_proposal_templates.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS contractor_proposal_templates", migration)
        self.assertIn("UNIQUE(contractor_id, name)", migration)
        for forbidden in ("price_range", "email", "phone", "address", "zip_code", "media"):
            self.assertNotIn(forbidden, migration)

    def test_cloudflare_contractor_bids_helper_matches_dashboard_contract(self):
        module = load_contractor_bids_module()
        self.assertEqual(module.normalize_contractor_bid_view("approved"), "approved")
        self.assertEqual(module.normalize_contractor_bid_view("bad"), "all")
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        client = {"id": 8, "role": "client", "status": "active"}
        suspended = {"id": 7, "role": "contractor", "status": "suspended"}
        self.assertTrue(module.can_view_contractor_bids(contractor))
        self.assertFalse(module.can_view_contractor_bids(client))
        self.assertFalse(module.can_view_contractor_bids(suspended))

        rows = [
            {
                "id": 21,
                "job_id": 12,
                "title": "Power wash steps",
                "category": "Power washing",
                "city": "Arlington",
                "state": "VA",
                "scope_note": "I can handle the cleaning and protect surfaces.",
                "price_range": "$450-$650",
                "timeline": "Two business days",
                "availability": "Tuesday",
                "status": "pending",
                "created_at": "2026-08-03T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "thread_id": None,
                "client_id": 8,
                "client_email": "private@example.com",
            },
            {
                "id": 22,
                "job_id": 13,
                "title": "Clean storefront windows",
                "category": "Window cleaning",
                "city": "Alexandria",
                "state": "VA",
                "scope_note": "Experienced storefront crew available.",
                "price_range": "$300-$450",
                "timeline": "Next week",
                "availability": "Friday",
                "status": "approved",
                "created_at": "2026-08-02T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "thread_id": 5,
            },
            {
                "id": 23,
                "job_id": 14,
                "title": "Paint office trim",
                "category": "Painting",
                "city": "Washington",
                "state": "DC",
                "scope_note": "Interior trim work with low-VOC products.",
                "price_range": "$700-$900",
                "timeline": "Three days",
                "availability": "Next month",
                "status": "rejected",
                "created_at": "2026-08-01T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "thread_id": None,
            },
        ]
        payload = module.contractor_bids_payload(rows, "approved")
        self.assertEqual(payload["view"], "approved")
        self.assertEqual(len(payload["bids"]), 1)
        bid = payload["bids"][0]
        self.assertEqual(bid["url"], "/messages/5")
        self.assertEqual(bid["thread_url"], "/messages/5")
        self.assertEqual(bid["job_url"], "/jobs/13")
        self.assertEqual(bid["row_cue"], "Message")
        self.assertEqual(payload["stats"]["total_requests"], 3)
        self.assertEqual(payload["stats"]["visible_requests"], 1)
        self.assertEqual(payload["stats"]["pending_requests"], 1)
        self.assertEqual(payload["stats"]["approved_requests"], 1)
        self.assertEqual(payload["stats"]["rejected_requests"], 1)
        self.assertNotIn("client_id", bid)
        self.assertNotIn("client_email", bid)

        pending_payload = module.contractor_bids_payload(rows, "pending")
        self.assertEqual(pending_payload["bids"][0]["url"], "/jobs/12")
        self.assertEqual(pending_payload["bids"][0]["row_cue"], "Details")

        all_payload = module.contractor_bids_payload(rows, "all")
        self.assertEqual(
            [bid["status"] for bid in all_payload["bids"]],
            ["approved", "pending", "rejected"],
        )
        self.assertEqual(all_payload["bids"][0]["price_range"], "$300-$450")
        self.assertEqual(all_payload["bids"][0]["timeline"], "Next week")

    def test_cloudflare_client_jobs_helper_matches_dashboard_counts(self):
        module = load_client_jobs_module()
        self.assertEqual(module.normalize_client_job_view("review"), "review")
        self.assertEqual(module.normalize_client_job_view("bad"), "active")
        self.assertEqual(module.normalize_client_job_view("all"), "active")
        self.assertEqual(module.normalize_client_job_view("open"), "active")
        self.assertEqual(module.normalize_client_job_view("closed"), "history")
        client = {"id": 8, "role": "client", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        suspended = {"id": 8, "role": "client", "status": "suspended"}
        self.assertTrue(module.can_view_client_jobs(client))
        self.assertFalse(module.can_view_client_jobs(admin))
        self.assertFalse(module.can_view_client_jobs(suspended))

        rows = [
            {
                "id": 12,
                "title": "Power wash steps",
                "category": "Power washing",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "description": "Townhouse front steps need cleaning.",
                "desired_date": "2026-09-01",
                "status": "open",
                "created_at": "2026-08-03T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "request_count": 3,
                "pending_count": 2,
                "approved_count": 1,
                "rejected_count": None,
                "client_id": 8,
                "client_email": "private@example.com",
            },
            {
                "id": 13,
                "title": "Clean storefront windows",
                "category": "Window cleaning",
                "city": "Alexandria",
                "state": "VA",
                "zip_code": "22314",
                "description": "Ground-floor windows before opening.",
                "desired_date": "",
                "status": "closed",
                "created_at": "2026-08-02T12:00:00+00:00",
                "updated_at": "2026-08-02T12:00:00+00:00",
                "request_count": 1,
                "pending_count": 2,
                "approved_count": 0,
                "rejected_count": 1,
            },
            {
                "id": 14,
                "title": "Repair a garden gate",
                "category": "Fence work",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
                "description": "Keep this project paused until next month.",
                "desired_date": "",
                "status": "hidden",
                "created_at": "2026-08-01T12:00:00+00:00",
                "updated_at": "2026-08-01T12:00:00+00:00",
                "request_count": 0,
                "pending_count": 0,
                "approved_count": 0,
                "rejected_count": 0,
            },
        ]
        payload = module.client_jobs_payload(rows, "review")
        self.assertEqual(payload["view"], "review")
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["url"], "/client/jobs/12?bids=pending#mini-bids")
        self.assertEqual(payload["jobs"][0]["detail_url"], "/client/jobs/12")
        self.assertEqual(payload["jobs"][0]["review_url"], "/client/jobs/12?bids=pending#mini-bids")
        self.assertEqual(payload["jobs"][0]["row_cue"], "Review bids")
        self.assertTrue(payload["jobs"][0]["needs_review"])
        self.assertEqual(payload["stats"]["total_jobs"], 3)
        self.assertEqual(payload["stats"]["visible_jobs"], 1)
        self.assertEqual(payload["stats"]["active_jobs"], 1)
        self.assertEqual(payload["stats"]["open_jobs"], 1)
        self.assertEqual(payload["stats"]["paused_jobs"], 1)
        self.assertEqual(payload["stats"]["history_jobs"], 1)
        self.assertEqual(payload["stats"]["closed_jobs"], 1)
        self.assertEqual(payload["stats"]["pending_requests"], 4)
        self.assertEqual(payload["stats"]["approved_requests"], 1)
        self.assertEqual(payload["stats"]["rejected_requests"], 1)
        self.assertNotIn("client_id", payload["jobs"][0])
        self.assertNotIn("client_email", payload["jobs"][0])

        legacy_all_payload = module.client_jobs_payload(rows, "all")
        self.assertEqual(legacy_all_payload["view"], "active")
        self.assertEqual([job["id"] for job in legacy_all_payload["jobs"]], [12])

        paused_payload = module.client_jobs_payload(rows, "paused")
        self.assertEqual(paused_payload["jobs"][0]["url"], "/client/jobs/14")
        self.assertEqual(paused_payload["jobs"][0]["row_cue"], "Manage")
        self.assertFalse(paused_payload["jobs"][0]["needs_review"])

        history_payload = module.client_jobs_payload(rows, "history")
        self.assertEqual(history_payload["jobs"][0]["url"], "/client/jobs/13")
        self.assertEqual(history_payload["jobs"][0]["row_cue"], "Review")
        self.assertEqual(
            [item["value"] for item in history_payload["view_links"]],
            ["active", "review", "paused", "history"],
        )

    def test_cloudflare_client_requests_helper_matches_review_contract(self):
        module = load_client_requests_module()
        self.assertEqual(module.parse_client_job_requests_path("/api/client/jobs/42/requests"), 42)
        with self.assertRaisesRegex(module.ClientRequestError, "Unsupported"):
            module.parse_client_job_requests_path("/api/client/jobs/0/requests")
        self.assertEqual(module.normalize_client_request_view("pending"), "pending")
        self.assertEqual(module.normalize_client_request_view("bad"), "all")
        client = {"id": 8, "role": "client", "status": "active"}
        other_client = {"id": 9, "role": "client", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        suspended = {"id": 8, "role": "client", "status": "suspended"}
        job = {"id": 42, "client_id": 8, "title": "Clean storefront windows", "status": "open"}
        self.assertTrue(module.can_view_client_job_requests(client, job))
        self.assertTrue(module.can_view_client_job_requests(admin, job))
        self.assertFalse(module.can_view_client_job_requests(other_client, job))
        self.assertFalse(module.can_view_client_job_requests(contractor, job))
        self.assertFalse(module.can_view_client_job_requests(suspended, job))

        rows = [
            {
                "id": 31,
                "job_id": 42,
                "contractor_id": 7,
                "display_name": "Jordan Doe",
                "company_name": "Doe Exterior",
                "business_name": "Doe Exterior Care",
                "trades": "Power washing, Window cleaning",
                "status": "pending",
                "scope_note": "I can protect surrounding surfaces and handle this safely.",
                "price_range": "$450-$650",
                "timeline": "Two business days",
                "experience": "Five years of exterior cleaning in the DMV.",
                "questions": "Is there hose access?",
                "availability": "Tuesday",
                "years_in_business": 5,
                "insurance_status": "Policy available on request",
                "source_checked_credential_count": 1,
                "source_checked_license_count": 1,
                "verified_work_count": 2,
                "profile_photo_id": 4,
                "created_at": "2026-08-03T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "thread_id": None,
                "email": "contractor@example.com",
                "phone": "(202) 555-0199",
            },
            {
                "id": 32,
                "job_id": 42,
                "contractor_id": 10,
                "display_name": "Alex Crew",
                "company_name": "Alex Crew LLC",
                "business_name": "",
                "trades": "",
                "status": "approved",
                "scope_note": "Storefront crew ready to coordinate details.",
                "price_range": "$300-$450",
                "timeline": "Next week",
                "experience": "Experienced storefront team.",
                "questions": "",
                "availability": "Friday",
                "created_at": "2026-08-02T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "thread_id": 5,
            },
            {
                "id": 33,
                "job_id": 42,
                "contractor_id": 11,
                "display_name": "Backup Contractor",
                "company_name": "",
                "business_name": "Backup Crew",
                "trades": "Exterior cleaning",
                "status": "rejected",
                "scope_note": "Backup bid.",
                "price_range": "$700-$900",
                "timeline": "Later",
                "experience": "Backup crew.",
                "questions": "",
                "availability": "Weekdays",
                "created_at": "2026-08-01T12:00:00+00:00",
                "updated_at": "2026-08-03T12:00:00+00:00",
                "thread_id": None,
            },
        ]
        payload = module.client_job_requests_payload(job, rows, "pending")
        self.assertEqual(payload["view"], "pending")
        self.assertEqual(payload["job"]["url"], "/client/jobs/42")
        self.assertEqual(
            payload["approved_request"]["contractor_name"], "Alex Crew LLC"
        )
        self.assertEqual(payload["approved_request"]["thread_url"], "/messages/5")
        self.assertNotIn("email", payload["approved_request"])
        self.assertNotIn("phone", payload["approved_request"])
        self.assertEqual(
            payload["stats"],
            {
                "visible": 1,
                "total": 3,
                "pending": 1,
                "approved": 1,
                "rejected": 1,
                "verified": 0,
            },
        )
        self.assertEqual(len(payload["requests"]), 1)
        request_payload = payload["requests"][0]
        self.assertEqual(request_payload["contractor_name"], "Doe Exterior Care")
        self.assertEqual(request_payload["profile_url"], "/contractors/7?job_id=42")
        self.assertTrue(request_payload["can_approve"])
        self.assertTrue(request_payload["needs_review"])
        self.assertEqual(request_payload["row_cue"], "Review")
        self.assertNotIn("email", request_payload)
        self.assertNotIn("phone", request_payload)
        self.assertEqual(payload["comparison"]["count"], 1)
        self.assertEqual(
            payload["comparison"]["offers"][0]["contractor_name"],
            "Doe Exterior Care",
        )
        self.assertEqual(
            payload["comparison"]["offers"][0]["profile_photo_url"],
            "/media/contractors/4",
        )
        self.assertEqual(
            payload["comparison"]["offers"][0]["provider_facts"][1]["value"],
            "1 credential",
        )
        self.assertEqual(
            payload["comparison"]["offers"][0]["provider_facts"][2]["value"],
            "1 record",
        )
        self.assertEqual(
            payload["comparison"]["offers"][0]["provider_facts"][3]["value"],
            "2 projects",
        )
        license_payload = module.client_job_requests_payload(
            job,
            rows,
            "pending",
            "license-checked",
        )
        self.assertEqual(license_payload["comparison"]["count"], 1)
        self.assertIn(
            "credentials=license-checked",
            license_payload["comparison"]["credential_filter_options"][2]["url"],
        )
        self.assertEqual(len(license_payload["requests"]), 1)
        comparison_json = json.dumps(payload["comparison"]).lower()
        self.assertNotIn("contractor@example.com", comparison_json)
        self.assertNotIn("202) 555", comparison_json)

        approved_payload = module.client_job_requests_payload(job, rows, "approved")
        approved = approved_payload["requests"][0]
        self.assertEqual(approved["thread_url"], "/messages/5")
        self.assertEqual(approved["row_cue"], "Message")
        self.assertFalse(approved["can_approve"])
        self.assertEqual(approved["trades"], "Contractor profile")
        self.assertEqual(approved_payload["comparison"]["offers"], [])

    def test_cloudflare_bid_comparison_matches_local_received_order_contract(self):
        worker = load_bid_comparison_module()
        from workdoe.bid_comparison import bid_comparison

        rows = [
            {
                "id": 42,
                "contractor_id": 9,
                "business_name": "Second Offer",
                "trades": "Moving",
                "status": "pending",
                "price_range": "$700-$850",
                "timeline": "Friday",
                "availability": "Friday morning",
                "scope_note": "Two movers and one truck.",
                "experience": "Local apartment moves.",
                "questions": "Freight elevator?",
                "years_in_business": 4,
                "insurance_status": "Available",
                "source_checked_credential_count": 1,
                "source_checked_license_count": 1,
                "verified_work_count": 2,
                "profile_photo_id": 14,
                "created_at": "2026-08-17T14:00:00+00:00",
                "email": "private@example.com",
                "exact_address": "100 Private Street",
            },
            {
                "id": 41,
                "contractor_id": 8,
                "business_name": "First Offer",
                "trades": "Moving",
                "status": "pending",
                "price_range": "$750 flat",
                "timeline": "Thursday",
                "availability": "Thursday morning",
                "scope_note": "Three movers and one truck.",
                "experience": "DMV residential moving.",
                "questions": "",
                "years_in_business": None,
                "insurance_status": "",
                "source_checked_credential_count": 0,
                "source_checked_license_count": 0,
                "verified_work_count": 0,
                "created_at": "2026-08-17T13:00:00+00:00",
            },
        ]
        local_result = bid_comparison(rows, "pending", job_id=42)
        worker_result = worker.bid_comparison(rows, "pending", job_id=42)
        self.assertEqual(worker_result, local_result)
        self.assertEqual(
            [offer["contractor_name"] for offer in worker_result["offers"]],
            ["First Offer", "Second Offer"],
        )
        self.assertEqual(
            worker_result["offers"][0]["profile_url"],
            "/contractors/8?job_id=42",
        )
        self.assertEqual(
            worker_result["offers"][1]["profile_photo_url"],
            "/media/contractors/14",
        )
        self.assertEqual(
            worker_result["offers"][0]["scope_note"],
            "Three movers and one truck.",
        )
        self.assertEqual(
            worker_result["offers"][1]["questions"],
            "Freight elevator?",
        )
        self.assertNotIn("private@example.com", json.dumps(worker_result))
        self.assertNotIn("Private Street", json.dumps(worker_result))
        worker_filtered = worker.bid_comparison(rows, "pending", "license-checked")
        self.assertEqual(worker_filtered["count"], 1)
        self.assertEqual(worker_filtered["offers"][0]["contractor_name"], "Second Offer")

    def test_cloudflare_contractor_reputation_matches_local_contract(self):
        worker = load_contractor_reputation_module()
        from workdoe.contractor_reputation import (
            contractor_match_provider,
            contractor_reputation,
        )

        self.assertEqual(
            worker.contractor_reputation(10, 2, 1),
            contractor_reputation(10, 2, 1),
        )
        reputation = worker.contractor_reputation(10, 2, 1)
        self.assertEqual(reputation["completion_points"], 1000)
        self.assertEqual(reputation["level_label"], "Local regular")
        self.assertEqual(reputation["progress_value"], 10)
        self.assertEqual(reputation["progress_max"], 25)
        self.assertEqual(reputation["trust_record"]["label"], "1 license source checked")
        self.assertEqual(
            [milestone["state"] for milestone in reputation["milestones"]],
            ["earned", "earned", "current", "next"],
        )
        self.assertEqual(reputation["ranking_effect"], "none")
        self.assertEqual(
            worker.contractor_match_provider(7, "Doe Powerwash", 42, 10, 2, 1),
            contractor_match_provider(7, "Doe Powerwash", 42, 10, 2, 1),
        )
        provider = worker.contractor_match_provider(
            7,
            "Doe Powerwash",
            42,
            verified_completions=10,
            source_checked_credentials=2,
            source_checked_licenses=1,
        )
        self.assertEqual(provider["profile_url"], "/contractors/7?job_id=42")
        self.assertEqual(provider["reputation"]["ranking_effect"], "none")
        self.assertNotIn("claimed_identifier", json.dumps(provider))

    def test_cloudflare_job_detail_payload_redacts_contractor_location(self):
        module = load_job_details_module()
        self.assertEqual(module.parse_job_detail_id("/api/jobs/42"), 42)
        self.assertEqual(module.zip_prefix("22201"), "222xx")
        client = {"id": 8, "role": "client", "status": "active"}
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        suspended = {"id": 9, "role": "contractor", "status": "suspended"}
        job = {
            "id": 42,
            "client_id": 8,
            "client_status": "active",
            "title": "Clean storefront windows",
            "category": "Window cleaning",
            "city": "Arlington",
            "state": "VA",
            "zip_code": "22201",
            "description": "Clean front and side windows before opening.",
            "desired_date": "2026-09-01",
            "status": "open",
            "close_reason": "plans-changed",
            "close_note": "Timing moved.",
            "closed_at": "2026-08-17T12:00:00+00:00",
            "license_preference": 1,
        }
        photos = [
            {
                "id": 5,
                "original_filename": "front-window.jpg",
                "is_hidden": 0,
                "stored_path": "jobs/42/private-key.jpg",
            }
        ]
        self.assertTrue(module.can_view_job_detail(client, job))
        self.assertTrue(module.can_view_job_detail(contractor, job))
        self.assertTrue(module.can_view_job_detail(admin, {**job, "status": "hidden"}))
        self.assertFalse(module.can_view_job_detail(contractor, {**job, "status": "hidden"}))
        self.assertFalse(
            module.can_view_job_detail(
                contractor,
                {**job, "client_status": "suspended"},
            )
        )
        self.assertFalse(module.can_view_job_detail(suspended, job))

        contractor_payload = module.job_detail_payload(contractor, job, photos=photos)
        contractor_job = contractor_payload["job"]
        self.assertEqual(contractor_job["area_label"], "Arlington, VA 222xx")
        self.assertEqual(contractor_job["zip_prefix"], "222xx")
        self.assertTrue(contractor_job["can_request_match"])
        self.assertTrue(contractor_job["license_preference"])
        self.assertNotIn("zip_code", contractor_job)
        self.assertNotIn("close_note", contractor_job)
        self.assertNotIn("stored_path", contractor_payload["photos"][0])
        self.assertNotIn("is_hidden", contractor_payload["photos"][0])

        requested_payload = module.job_detail_payload(
            contractor,
            job,
            photos=photos,
            existing_request={
                "id": 11,
                "status": "approved",
                "scope_note": "I can do this work safely.",
                "price_range": "$300-$450",
                "timeline": "Next week",
                "availability": "Tuesday",
                "thread_id": 3,
                "client_id": 8,
            },
        )
        self.assertFalse(requested_payload["job"]["can_request_match"])
        self.assertEqual(requested_payload["existing_request"]["thread_url"], "/messages/3")
        self.assertNotIn("client_id", requested_payload["existing_request"])

        owner_payload = module.job_detail_payload(client, job, photos=photos)
        self.assertEqual(owner_payload["viewer"], "owner")
        self.assertEqual(owner_payload["job"]["zip_code"], "22201")
        self.assertEqual(owner_payload["job"]["close_note"], "Timing moved.")
        self.assertEqual(owner_payload["photos"][0]["is_hidden"], 0)
        with self.assertRaisesRegex(module.JobDetailError, "Unsupported"):
            module.parse_job_detail_id("/api/jobs/0")

    def test_cloudflare_bid_window_rules_are_deterministic(self):
        module = load_job_posts_module()
        open_window = module.bid_window(
            {
                "status": "open",
                "bid_limit": 4,
                "request_count": 2,
                "bidding_closes_at": "2026-08-24T12:00:00+00:00",
            },
            now="2026-08-17T12:00:00+00:00",
        )
        self.assertTrue(open_window["accepting"])
        self.assertEqual(open_window["remaining"], 2)
        self.assertEqual(open_window["usage_label"], "2 of 4 bids")

        full_window = module.bid_window(
            {
                "status": "open",
                "bid_limit": 4,
                "request_count": 4,
                "bidding_closes_at": "2026-08-24T12:00:00+00:00",
            },
            now="2026-08-17T12:00:00+00:00",
        )
        self.assertFalse(full_window["accepting"])
        self.assertEqual(full_window["state"], "full")

        expired_window = module.bid_window(
            {
                "status": "open",
                "request_count": 1,
                "bidding_closes_at": "2026-08-16T12:00:00+00:00",
            },
            now="2026-08-17T12:00:00+00:00",
        )
        self.assertFalse(expired_window["accepting"])
        self.assertTrue(expired_window["can_extend"])
        self.assertEqual(
            module.extended_bidding_closes_at(
                "2026-08-16T12:00:00+00:00",
                "2026-08-17T12:00:00+00:00",
            ),
            "2026-08-24T12:00:00+00:00",
        )

        matched_window = module.bid_window(
            {
                "status": "open",
                "bid_limit": 4,
                "request_count": 1,
                "has_approved_match": 1,
                "bidding_closes_at": "2026-08-24T12:00:00+00:00",
            },
            now="2026-08-17T12:00:00+00:00",
        )
        self.assertFalse(matched_window["accepting"])
        self.assertFalse(matched_window["can_extend"])
        self.assertEqual(matched_window["state"], "matched")
        self.assertEqual(matched_window["availability_label"], "Contractor chosen")

    def test_cloudflare_job_status_helper_matches_client_control_contract(self):
        module = load_job_status_module()
        self.assertEqual(module.parse_job_status_path("/api/jobs/42/close"), (42, "close", "closed"))
        self.assertEqual(module.parse_job_status_path("/api/jobs/42/reopen"), (42, "reopen", "open"))
        client = {"id": 8, "role": "client", "status": "active"}
        other_client = {"id": 9, "role": "client", "status": "active"}
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        suspended_owner = {"id": 8, "role": "client", "status": "suspended"}
        job = {"id": 42, "client_id": 8, "status": "open"}
        self.assertTrue(module.can_update_job_status(client, job))
        self.assertFalse(module.can_update_job_status(other_client, job))
        self.assertFalse(module.can_update_job_status(contractor, job))
        self.assertFalse(module.can_update_job_status(admin, job))
        self.assertFalse(module.can_update_job_status(suspended_owner, job))
        self.assertEqual(module.job_status_event_type("closed"), "job-closed")
        self.assertEqual(module.job_status_event_type("open"), "job-reopened")
        self.assertEqual(
            module.job_status_response(42, "closed"),
            {"ok": True, "job_id": 42, "status": "closed", "url": "/client/jobs/42"},
        )
        self.assertEqual(
            module.validate_project_close_payload(
                {"reason_code": "plans-changed", "note": "Schedule moved."},
                has_approved_match=False,
            ),
            {"reason_code": "plans-changed", "note": "Schedule moved."},
        )
        with self.assertRaisesRegex(module.JobStatusError, "Approve a Workdoe bid"):
            module.validate_project_close_payload(
                {"reason_code": "workdoe-match"},
                has_approved_match=False,
            )
        self.assertEqual(
            module.validate_project_close_payload(
                {"reason_code": "workdoe-match"},
                has_approved_match=True,
            )["reason_code"],
            "workdoe-match",
        )
        match_request = {"job_id": 42, "contractor_id": 7}
        self.assertTrue(
            module.can_submit_lead_quality_feedback(contractor, job, match_request)
        )
        self.assertFalse(
            module.can_submit_lead_quality_feedback(
                contractor,
                {**job, "status": "hidden"},
                match_request,
            )
        )
        self.assertEqual(
            module.parse_job_quality_feedback_path("/api/jobs/42/quality-feedback"),
            42,
        )
        self.assertEqual(
            module.validate_lead_quality_payload(
                {"reason_code": "insufficient-detail", "note": "Need dimensions."}
            ),
            {"reason_code": "insufficient-detail", "note": "Need dimensions."},
        )
        with self.assertRaisesRegex(module.JobStatusError, "Unsupported"):
            module.parse_job_status_path("/api/jobs/42/delete")

    def test_cloudflare_consumer_profile_helper_supports_private_recurring_workspaces(self):
        module = load_client_profiles_module()
        profile = module.client_profile_payload(
            {
                "organization_name": "  Meridian Corner Store  ",
                "account_type": "small_business",
                "notification_preference": "workdoe",
                "profile_note": "  Schedule noisy work before opening.  ",
            }
        )
        self.assertEqual(profile["organization_name"], "Meridian Corner Store")
        self.assertEqual(profile["account_type"], "small_business")
        self.assertEqual(profile["notification_preference"], "workdoe")
        self.assertEqual(
            module.client_profile_response(
                {"notification_preference": "email", "email_reminder_consent_at": None}
            )["notification_preference"],
            "workdoe",
        )
        self.assertEqual(
            module.client_profile_response(
                {
                    "notification_preference": "email",
                    "email_reminder_consent_at": "2026-08-17T14:00:00+00:00",
                }
            )["notification_preference"],
            "email",
        )

        location = module.saved_location_payload(
            {
                "label": " Main shop ",
                "city": " Washington ",
                "state": "dc",
                "zip_code": "20003",
            }
        )
        self.assertEqual(
            location,
            {
                "label": "Main shop",
                "city": "Washington",
                "state": "DC",
                "zip_code": "20003",
            },
        )
        self.assertEqual(
            module.parse_saved_location_delete_path(
                "/api/client/locations/17/delete"
            ),
            17,
        )
        with self.assertRaises(module.SavedLocationError):
            module.saved_location_payload(
                {"label": "Shop", "city": "Washington", "state": "NY", "zip_code": "12"}
            )

        client = {"role": "client", "status": "active"}
        contractor = {"role": "contractor", "status": "active"}
        self.assertTrue(module.can_update_client_profile(client))
        self.assertFalse(module.can_update_client_profile(contractor))

    def test_cloudflare_consumer_profile_shell_and_saved_location_prefill(self):
        module = load_app_shell_module()
        user = {"id": 4, "role": "client", "status": "active"}
        profile_html = module.client_profile_html(
            user,
            {
                "organization_name": "Meridian Corner Store",
                "account_type": "small_business",
                "notification_preference": "email",
                "profile_note": "Schedule work before opening.",
            },
            [
                {
                    "id": 17,
                    "label": "Main shop",
                    "city": "Washington",
                    "state": "DC",
                    "zip_code": "20003",
                }
            ],
        )
        self.assertIn("/api/client/profile", profile_html)
        self.assertIn("/api/client/locations", profile_html)
        self.assertIn("/api/client/locations/17/delete", profile_html)
        self.assertIn("200xx", profile_html)
        self.assertIn("records your consent", profile_html)
        self.assertIn('id="bid-reminders"', profile_html)
        self.assertNotIn("name=\"phone\"", profile_html)

        composer_html = module.job_form_html(
            user,
            job={"city": "Washington", "state": "DC", "zip_code": "20003"},
            saved_locations=[{"id": 17, "label": "Main shop"}],
        )
        self.assertIn("Start with a saved area", composer_html)
        self.assertIn("/jobs/new?location=17", composer_html)
        self.assertIn('value="Washington"', composer_html)
        self.assertIn('value="20003"', composer_html)

    def test_cloudflare_contractor_profile_helper_matches_local_validation_contract(self):
        module = load_contractor_profiles_module()
        profile = module.contractor_profile_payload(
            {
                "business_name": "  Better Exterior Care  ",
                "trades": ["Window cleaning", "Unknown", "Power washing"],
                "service_area": "  DC and Northern Virginia  ",
                "years_in_business": "7",
                "insurance_status": "  COI available  ",
                "license_number": "  VA-1234  ",
                "website": " https://better.example ",
                "phone": "  (202) 555-0180  ",
                "intro": "We handle exterior cleaning jobs around the DMV with careful site protection.",
            }
        )
        self.assertEqual(profile["business_name"], "Better Exterior Care")
        self.assertEqual(profile["trades"], "Power washing, Window cleaning")
        self.assertEqual(profile["service_area"], "DC and Northern Virginia")
        self.assertEqual(profile["years_in_business_value"], 7)
        self.assertEqual(profile["insurance_status"], "COI available")
        self.assertEqual(profile["website"], "https://better.example")
        self.assertNotIn("phone", profile)
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        client = {"id": 8, "role": "client", "status": "active"}
        suspended = {"id": 7, "role": "contractor", "status": "suspended"}
        self.assertTrue(module.can_update_contractor_profile(contractor))
        self.assertFalse(module.can_update_contractor_profile(client))
        self.assertFalse(module.can_update_contractor_profile(suspended))

        response = module.contractor_profile_response({**profile, "updated_at": "2026-08-03T12:00:00+00:00"})
        self.assertEqual(response["business_name"], "Better Exterior Care")
        self.assertNotIn("user_id", response)
        self.assertNotIn("email", response)

        structured = module.contractor_profile_payload(
            {
                "market_fit_version": "1",
                "business_name": "Better Exterior Care",
                "service_slugs": ["pressure-washing", "window-cleaning", "unknown"],
                "service_zone_slugs": ["district-of-columbia", "arlington-county-va"],
                "years_in_business": "7",
                "insurance_status": "COI available",
                "license_number": "VA-1234",
                "website": "https://better.example",
                "phone": "(202) 555-0180",
                "intro": "We handle exterior cleaning jobs around the DMV with careful site protection.",
            }
        )
        self.assertEqual(
            structured["service_slugs"],
            ["pressure-washing", "window-cleaning"],
        )
        self.assertEqual(
            structured["service_zone_slugs"],
            ["district-of-columbia", "arlington-county-va"],
        )
        self.assertEqual(structured["trades"], "Power washing, Window cleaning")
        self.assertIn("Arlington County, VA", structured["service_area"])

        with self.assertRaises(module.ContractorProfileError) as invalid:
            module.contractor_profile_payload(
                {
                    "business_name": "",
                    "trades": [],
                    "service_area": "",
                    "years_in_business": "150",
                    "website": "ftp://example.test",
                    "intro": "short",
                }
            )
        self.assertIn("Add a business name.", invalid.exception.errors)
        self.assertIn("Choose at least one trade.", invalid.exception.errors)
        self.assertIn("Add a service area.", invalid.exception.errors)
        self.assertIn("Add at least 20 characters about your business.", invalid.exception.errors)
        self.assertIn("Use 0 to 100 for years in business.", invalid.exception.errors)
        self.assertIn("Use a public HTTPS website such as https://example.com.", invalid.exception.errors)
        self.assertEqual(
            invalid.exception.field_errors["business_name"],
            ["Add a business name."],
        )
        self.assertEqual(invalid.exception.field_errors["trades"], ["Choose at least one trade."])
        self.assertEqual(invalid.exception.field_errors["service_area"], ["Add a service area."])
        self.assertEqual(
            invalid.exception.field_errors["intro"],
            ["Add at least 20 characters about your business."],
        )
        self.assertEqual(
            invalid.exception.field_errors["years_in_business"],
            ["Use 0 to 100 for years in business."],
        )
        self.assertEqual(
            invalid.exception.field_errors["website"],
            ["Use a public HTTPS website such as https://example.com."],
        )

        for unsafe_website in (
            "http://example.com",
            "https://localhost",
            "https://127.0.0.1",
            "https://user:pass@example.com",
            "https://example.com:8443",
        ):
            with self.subTest(unsafe_website=unsafe_website):
                unsafe = {**profile, "website": unsafe_website}
                self.assertIn(
                    "Use a public HTTPS website such as https://example.com.",
                    module.validate_contractor_profile_payload(unsafe),
                )

    def test_cloudflare_public_contractor_profile_helper_keeps_contact_private(self):
        module = load_contractor_public_profiles_module()
        from workdoe.contractor_public_profiles import contractor_choice_context

        self.assertEqual(module.parse_public_contractor_id("/api/contractors/42"), 42)
        with self.assertRaisesRegex(module.ContractorPublicProfileError, "Unsupported"):
            module.parse_public_contractor_id("/api/contractors/0")

        public_contractor = {
            "id": 42,
            "display_name": "Jordan Doe",
            "company_name": "Doe Exterior",
            "business_name": "Doe Exterior Care",
            "trades": "Power washing, Window cleaning",
            "service_area": "DC and Northern Virginia",
            "intro": "Exterior care crew focused on storefronts and townhouse entries.",
            "insurance_status": "COI available",
            "license_number": "VA-1234",
            "years_in_business": 6,
            "updated_at": "2026-08-03T12:00:00+00:00",
            "status": "active",
            "email": "private@example.com",
            "phone": "(202) 555-0199",
            "website": "https://www.doe-exterior.example/work",
            "stored_path": "contractors/42/private.webp",
        }
        inactive_contractor = {**public_contractor, "status": "suspended"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        client = {"id": 8, "role": "client", "status": "active"}
        self.assertTrue(module.can_view_public_contractor_profile(None, public_contractor))
        self.assertTrue(module.can_view_public_contractor_profile(client, public_contractor))
        self.assertFalse(module.can_view_public_contractor_profile(client, inactive_contractor))
        self.assertTrue(module.can_view_public_contractor_profile(admin, inactive_contractor))
        self.assertFalse(module.can_view_contractor_website(None, 42))
        self.assertFalse(module.can_view_contractor_website(client, 42))
        self.assertTrue(module.can_view_contractor_website(client, 42, True))
        self.assertTrue(module.can_view_contractor_website(admin, 42))
        self.assertTrue(
            module.can_view_contractor_website(
                {"id": 42, "role": "contractor", "status": "active"},
                42,
            )
        )
        relationship = {
            "job_id": 12,
            "job_title": "Power wash steps",
            "client_id": 8,
            "contractor_id": 42,
            "request_id": 31,
            "price_range": "$450-$650",
            "timeline": "Two days",
            "availability": "Tuesday",
            "status": "pending",
            "thread_id": None,
        }
        expected_choice = contractor_choice_context(client, 42, relationship)
        self.assertEqual(
            module.contractor_choice_context(client, 42, relationship),
            expected_choice,
        )
        self.assertEqual(expected_choice["back_url"], "/client/jobs/12#mini-bids")
        self.assertTrue(expected_choice["can_choose"])
        self.assertEqual(expected_choice["price_range"], "$450-$650")
        self.assertEqual(expected_choice["timeline"], "Two days")
        self.assertEqual(expected_choice["availability"], "Tuesday")
        self.assertIsNone(
            module.contractor_choice_context(
                {"id": 9, "role": "client", "status": "active"},
                42,
                relationship,
            )
        )

        payload = module.public_contractor_profile_payload(
            public_contractor,
            [
                {
                    "id": 7,
                    "original_filename": "crew.webp",
                    "created_at": "2026-08-03T12:01:00+00:00",
                    "stored_path": "contractors/42/crew.webp",
                }
            ],
            client,
        )
        contractor = payload["contractor"]
        self.assertEqual(contractor["business_name"], "Doe Exterior Care")
        self.assertEqual(contractor["photos"][0]["url"], "/media/contractors/7")
        self.assertNotIn("status", contractor)
        self.assertNotIn("email", contractor)
        self.assertNotIn("phone", contractor)
        self.assertNotIn("website", contractor)
        self.assertNotIn("original_filename", contractor["photos"][0])
        self.assertNotIn("stored_path", contractor["photos"][0])
        admin_payload = module.public_contractor_profile_payload(inactive_contractor, [], admin)
        self.assertEqual(admin_payload["contractor"]["status"], "suspended")
        related_payload = module.public_contractor_profile_payload(
            public_contractor,
            [],
            client,
            website_visible=True,
        )
        self.assertEqual(
            related_payload["contractor"]["website"],
            "https://www.doe-exterior.example/work",
        )
        self.assertEqual(
            related_payload["contractor"]["website_label"],
            "doe-exterior.example",
        )
        self.assertNotIn("phone", related_payload["contractor"])

    def test_cloudflare_contractor_credentials_fail_closed_and_publish_only_current_records(self):
        module = load_contractor_credentials_module()
        claim = module.contractor_credential_claim_payload(
            {
                "credential_type": "trade_license",
                "jurisdiction": "va",
                "claimed_identifier": "  VA-1234  ",
                "claimed_name": " Rivera Exterior Care ",
                "source_url": "https://registry.example/VA-1234",
                "expires_at": "2027-12-31",
            }
        )
        self.assertEqual(claim["jurisdiction"], "VA")
        self.assertEqual(claim["claimed_identifier"], "VA-1234")
        self.assertEqual(claim["source_url"], "https://registry.example/VA-1234")

        for unsafe_source in (
            "http://registry.example/VA-1234",
            "https://localhost/record",
            "https://127.0.0.1/record",
            "https://user:pass@registry.example/record",
        ):
            with self.subTest(unsafe_source=unsafe_source), self.assertRaises(
                module.ContractorCredentialError
            ):
                module.contractor_credential_claim_payload(
                    {**claim, "source_url": unsafe_source}
                )

        with self.assertRaises(module.ContractorCredentialError):
            module.contractor_credential_review_payload(
                {"source_url": "", "expires_at": "2027-12-31"},
                "verify",
            )
        with self.assertRaises(module.ContractorCredentialError):
            module.contractor_credential_review_payload(
                {"source_url": "https://registry.example/record"},
                "pending",
            )

        reviewed = module.contractor_credential_review_payload(
            {
                "source_url": "https://registry.example/VA-1234",
                "expires_at": "2027-12-31",
                "review_note": "Public registry checked.",
            },
            "verify",
        )
        self.assertEqual(reviewed["status"], "verified")

        base = {
            "id": 8,
            **claim,
            "checked_at": "2026-08-17T14:00:00+00:00",
            "review_note": "Private admin note",
            "created_at": "2026-08-17T13:00:00+00:00",
            "updated_at": "2026-08-17T14:00:00+00:00",
        }
        pending = {**base, "status": "self_reported"}
        current = {**base, "status": "verified"}
        expired = {**base, "status": "verified", "expires_at": "2025-01-01"}
        public = module.public_credential_responses([pending, current, expired])
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0]["status_label"], "Source checked")
        self.assertNotIn("claimed_identifier", public[0])
        self.assertNotIn("review_note", public[0])
        private = module.credential_response(current, include_private=True)
        self.assertEqual(private["claimed_identifier"], "VA-1234")
        self.assertEqual(
            module.parse_contractor_credential_remove_path(
                "/api/contractor/credentials/8/remove"
            ),
            8,
        )

        public_profile_module = load_contractor_public_profiles_module()
        profile_payload = public_profile_module.public_contractor_profile_payload(
            {
                "id": 42,
                "business_name": "Rivera Exterior Care",
                "status": "active",
            },
            [],
            None,
            credentials=[pending, current, expired],
        )
        self.assertEqual(len(profile_payload["contractor"]["credentials"]), 1)

        admin_module = load_admin_moderation_module()
        self.assertEqual(
            admin_module.parse_admin_moderation_path(
                "/api/admin/credentials/8/verify"
            ),
            {"target_type": "credential", "target_id": 8, "action": "verify"},
        )

    def test_cloudflare_job_post_payload_matches_local_validation_contract(self):
        module = load_job_posts_module()
        valid_form = {
            "title": "  Clean storefront windows  ",
            "category": "Window cleaning",
            "project_setting": "business-space",
            "city": " Alexandria ",
            "state": "va",
            "zip_code": "22314-0010",
            "desired_date": "2026-09-01",
            "description": "Need first-floor storefront windows cleaned before opening.",
            "budget_min": "500",
            "budget_max": "900",
            "license_preference": "1",
            "service_policy_acknowledgement": "2026-08-22",
        }
        payload = module.job_post_payload(valid_form, today=module.date(2026, 8, 3))
        self.assertEqual(payload["title"], "Clean storefront windows")
        self.assertEqual(payload["state"], "VA")
        self.assertEqual(payload["zip_code"], "22314")
        self.assertEqual(payload["approx_lat"], 38.8048)
        self.assertEqual(payload["approx_lng"], -77.0469)
        self.assertEqual(payload["budget_min"], "500")
        self.assertEqual(payload["budget_max"], "900")
        self.assertEqual(payload["project_setting"], "business-space")
        self.assertEqual(payload["license_preference"], "1")
        self.assertEqual(module.project_setting_label(payload["project_setting"]), "Business or office")
        self.assertEqual(module.budget_label(payload), "$500-$900")
        self.assertEqual(
            payload["location_privacy"],
            "Approximate city or ZIP-level pins only.",
        )

        with self.assertRaises(module.JobPostError) as missing_policy:
            module.job_post_payload(
                {
                    key: value
                    for key, value in valid_form.items()
                    if key != "service_policy_acknowledgement"
                },
                today=module.date(2026, 8, 3),
            )
        self.assertEqual(
            missing_policy.exception.field_errors[
                "service_policy_acknowledgement"
            ],
            ["Confirm the current service safety advisory."],
        )

        with self.assertRaises(module.JobPostError) as invalid:
            module.job_post_payload(
                {
                    "title": "",
                    "category": "Mystery",
                    "project_setting": "private-address-record",
                    "city": "",
                    "state": "PA",
                    "zip_code": "22A",
                    "desired_date": "2020-01-01",
                    "description": "Too short",
                    "budget_min": "900",
                    "budget_max": "500",
                },
                today=module.date(2026, 8, 3),
            )
        self.assertIn("Add a job title.", invalid.exception.errors)
        self.assertIn("Choose a curated category.", invalid.exception.errors)
        self.assertIn("Choose a listed project setting.", invalid.exception.errors)
        self.assertIn("Use DC, MD, or VA for the first DMV beta.", invalid.exception.errors)
        self.assertIn("Use a 5-digit DMV ZIP code.", invalid.exception.errors)
        self.assertIn("Choose today or a future desired date.", invalid.exception.errors)
        self.assertEqual(invalid.exception.field_errors["title"], ["Add a job title."])
        self.assertEqual(invalid.exception.field_errors["category"], ["Choose a curated category."])
        self.assertEqual(
            invalid.exception.field_errors["project_setting"],
            ["Choose a listed project setting."],
        )
        self.assertEqual(
            invalid.exception.field_errors["state"],
            ["Use DC, MD, or VA for the first DMV beta."],
        )
        self.assertEqual(
            invalid.exception.field_errors["city"],
            ["Add the city so the lead can be mapped approximately."],
        )
        self.assertIn(
            "Make the budget maximum at least the minimum budget.",
            invalid.exception.errors,
        )

        self.assertEqual(
            invalid.exception.field_errors["zip_code"],
            ["Use a 5-digit DMV ZIP code."],
        )
        self.assertEqual(
            invalid.exception.field_errors["desired_date"],
            ["Choose today or a future desired date."],
        )
        self.assertEqual(
            invalid.exception.field_errors["description"],
            ["Add at least 20 characters about the work."],
        )

        owner = {"id": 8, "role": "client", "status": "active"}
        other = {"id": 9, "role": "client", "status": "active"}
        job = {"id": 12, "client_id": 8, "status": "open"}
        self.assertEqual(module.parse_job_update_id("/api/jobs/12/update"), 12)
        with self.assertRaises(module.JobPostError):
            module.parse_job_update_id("/api/jobs/12")
        self.assertTrue(module.can_update_job(owner, job))
        self.assertFalse(module.can_update_job(other, job))
        self.assertFalse(module.can_update_job(owner, {**job, "status": "hidden"}))

    def test_cloudflare_service_policy_registry_matches_flask_and_release_schema(self):
        from workdoe.service_policy import (
            EMERGENCY_DISABLED_SERVICES as LOCAL_DISABLED_SERVICES,
        )
        from workdoe.service_policy import (
            SERVICE_POLICY_REGISTRY as LOCAL_POLICY_REGISTRY,
        )
        from workdoe.service_policy import (
            SERVICE_POLICY_VERSION as LOCAL_POLICY_VERSION,
        )

        worker_policy = load_service_policy_module()
        self.assertEqual(worker_policy.SERVICE_POLICY_VERSION, LOCAL_POLICY_VERSION)
        self.assertEqual(worker_policy.SERVICE_POLICY_REGISTRY, LOCAL_POLICY_REGISTRY)
        self.assertEqual(worker_policy.EMERGENCY_DISABLED_SERVICES, frozenset())
        self.assertEqual(LOCAL_DISABLED_SERVICES, frozenset())
        self.assertEqual(len(worker_policy.SERVICE_POLICY_REGISTRY), 53)
        self.assertEqual(
            worker_policy.service_policy_error("electrical", "stale-policy"),
            "Confirm the current service safety advisory.",
        )
        self.assertEqual(
            worker_policy.service_policy_error("electrical", LOCAL_POLICY_VERSION),
            "",
        )

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0028_service_policy_acknowledgements.sql"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS service_policy_acknowledgements",
            migration,
        )
        self.assertIn("idx_service_policy_ack_user", migration)
        self.assertIn("idx_service_policy_ack_resource", migration)

        entrypoint = WORKER_ENTRY_PATH.read_text(encoding="utf-8")
        create_job = entrypoint[
            entrypoint.index("    async def create_job") : entrypoint.index(
                "    async def update_job"
            )
        ]
        self.assertLess(
            create_job.index("await record_service_policy_acknowledgement("),
            create_job.index("await complete_idempotent_request("),
        )
        app_shell = APP_SHELL_PATH.read_text(encoding="utf-8")
        self.assertIn("Workdoe does not verify provider credentials.", app_shell)
        self.assertIn("Confirm before updating", app_shell)

    def test_cloudflare_account_roles_are_permanent_and_budget_migration_is_incremental(self):
        auth = load_email_code_auth_module()
        self.assertEqual(auth.fixed_account_role("client", "contractor"), "client")
        self.assertEqual(auth.fixed_account_role("contractor", "client"), "contractor")
        self.assertEqual(auth.fixed_account_role(None, "contractor"), "contractor")

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0003_project_drafts_and_budgets.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE jobs ADD COLUMN budget_min INTEGER;", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS job_drafts", migration)
        self.assertIn("token_hash TEXT NOT NULL UNIQUE", migration)
        self.assertNotIn("email", migration.lower())

    def test_cloudflare_turnstile_helper_builds_safe_siteverify_payloads(self):
        module = load_turnstile_module()
        token = module.turnstile_token_from_payload(
            {"cf-turnstile-response": " token_123 "}
        )
        self.assertEqual(token, "token_123")
        payload = module.siteverify_payload(
            secret="secret-key",
            token=token,
            remoteip="203.0.113.10",
            idempotency_key="idem_123",
        )
        self.assertEqual(payload["secret"], "secret-key")
        self.assertEqual(payload["response"], "token_123")
        self.assertEqual(payload["remoteip"], "203.0.113.10")
        self.assertEqual(payload["idempotency_key"], "idem_123")
        self.assertTrue(
            module.turnstile_result_allowed(
                {"success": True, "hostname": "workdoe.com"},
                {"workdoe.com", "www.workdoe.com"},
            )
        )
        self.assertFalse(
            module.turnstile_result_allowed(
                {"success": True, "hostname": "evil.example"},
                {"workdoe.com", "www.workdoe.com"},
            )
        )
        with self.assertRaisesRegex(module.TurnstileError, "required"):
            module.turnstile_token_from_payload({})
        with self.assertRaisesRegex(module.TurnstileError, "too long"):
            module.turnstile_token_from_payload({"turnstile_token": "x" * 2049})

    def test_cloudflare_match_request_payload_matches_local_bid_contract(self):
        module = load_match_requests_module()
        self.assertEqual(module.parse_match_request_job_id("/api/jobs/42/request"), 42)
        payload = module.match_request_payload(
            {
                "scope_note": " I can clean the windows and protect nearby surfaces. ",
                "price_range": "  $450 - $650  ",
                "timeline": " Two business days after approval ",
                "experience": " Five years of exterior cleaning work in the DMV. ",
                "questions": " Is there hose access? ",
                "availability": " Tuesday and Thursday afternoons ",
                "service_policy_acknowledgement": "2026-08-22",
            }
        )
        self.assertEqual(
            payload["scope_note"],
            "I can clean the windows and protect nearby surfaces.",
        )
        self.assertEqual(payload["price_range"], "$450 - $650")
        self.assertEqual(payload["timeline"], "Two business days after approval")
        self.assertEqual(payload["availability"], "Tuesday and Thursday afternoons")
        self.assertEqual(payload["service_policy_acknowledgement"], "2026-08-22")

        with self.assertRaises(module.MatchRequestError) as invalid:
            module.match_request_payload(
                {
                    "scope_note": "Too short",
                    "price_range": "",
                    "timeline": "",
                    "experience": "Also short",
                    "questions": "Q" * 501,
                    "availability": "",
                }
            )
        self.assertIn("Add at least 20 characters about the scope.", invalid.exception.errors)
        self.assertIn("Add a price or range.", invalid.exception.errors)
        self.assertIn("Add a timeline.", invalid.exception.errors)
        self.assertIn(
            "Add at least 20 characters about relevant experience.",
            invalid.exception.errors,
        )
        self.assertIn("Keep questions under 500 characters.", invalid.exception.errors)
        self.assertIn("Add availability.", invalid.exception.errors)
        self.assertEqual(
            invalid.exception.field_errors["scope_note"],
            ["Add at least 20 characters about the scope."],
        )
        self.assertEqual(invalid.exception.field_errors["price_range"], ["Add a price or range."])
        self.assertEqual(invalid.exception.field_errors["timeline"], ["Add a timeline."])
        self.assertEqual(
            invalid.exception.field_errors["experience"],
            ["Add at least 20 characters about relevant experience."],
        )
        self.assertEqual(
            invalid.exception.field_errors["questions"],
            ["Keep questions under 500 characters."],
        )
        self.assertEqual(invalid.exception.field_errors["availability"], ["Add availability."])
        with self.assertRaisesRegex(module.MatchRequestError, "Unsupported"):
            module.parse_match_request_job_id("/api/jobs/0/request")

    def test_cloudflare_match_decision_helper_matches_client_review_contract(self):
        module = load_match_decisions_module()
        self.assertEqual(
            module.parse_match_decision_path("/api/match-requests/42/approve"),
            (42, "approve", "approved"),
        )
        self.assertEqual(
            module.parse_match_decision_path("/api/match-requests/42/reject"),
            (42, "reject", "rejected"),
        )
        client = {"id": 8, "role": "client", "status": "active"}
        other_client = {"id": 9, "role": "client", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        suspended_admin = {"id": 2, "role": "admin", "status": "suspended"}
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        match = {"id": 42, "job_id": 12, "client_id": 8, "contractor_id": 7}
        self.assertTrue(module.can_decide_match_request(client, match))
        self.assertTrue(module.can_decide_match_request(admin, match))
        self.assertFalse(module.can_decide_match_request(other_client, match))
        self.assertFalse(module.can_decide_match_request(contractor, match))
        self.assertFalse(module.can_decide_match_request(suspended_admin, match))
        self.assertEqual(module.d1_change_count({"meta": {"changes": 1}}), 1)
        self.assertEqual(
            module.d1_change_count({"result": {"meta": {"changes": "0"}}}),
            0,
        )
        self.assertEqual(
            module.d1_change_count(SimpleNamespace(meta=SimpleNamespace(changes=1))),
            1,
        )
        self.assertEqual(module.d1_change_count({"meta": {"changes": "bad"}}), 0)

        approved = module.match_decision_response(
            42,
            "approved",
            job_id=12,
            thread_id=5,
        )
        self.assertEqual(approved["url"], "/messages/5")
        self.assertEqual(approved["thread_id"], 5)
        rejected = module.match_decision_response(42, "rejected", job_id=12)
        self.assertEqual(rejected["url"], "/client/jobs/12")
        self.assertNotIn("client_id", rejected)
        with self.assertRaisesRegex(module.MatchDecisionError, "Unsupported"):
            module.parse_match_decision_path("/api/match-requests/42/delete")

    def test_cloudflare_message_thread_helper_matches_local_messaging_contract(self):
        module = load_message_threads_module()
        self.assertEqual(module.parse_thread_id("/api/messages/threads/42"), 42)
        self.assertEqual(module.normalize_message_thread_view("reply"), "reply")
        self.assertEqual(module.normalize_message_thread_view("unread"), "unread")
        self.assertEqual(module.normalize_message_thread_view("invalid"), "all")
        client = {"id": 8, "role": "client", "status": "active"}
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        other_client = {"id": 9, "role": "client", "status": "active"}
        suspended = {"id": 10, "role": "contractor", "status": "suspended"}
        thread = {"id": 42, "job_id": 12, "client_id": 8, "contractor_id": 7}
        self.assertTrue(module.can_view_thread(client, thread))
        self.assertTrue(module.can_view_thread(contractor, thread))
        self.assertTrue(module.can_view_thread(admin, thread))
        self.assertFalse(module.can_view_thread(other_client, thread))
        self.assertFalse(module.can_view_thread(suspended, thread))
        self.assertTrue(module.can_send_thread_message(client, thread))
        self.assertTrue(module.can_send_thread_message(contractor, thread))
        self.assertFalse(module.can_send_thread_message(admin, thread))

        self.assertEqual(
            module.message_body_payload({"body": "  Can you start Tuesday?  "}),
            "Can you start Tuesday?",
        )
        with self.assertRaisesRegex(module.MessageThreadError, "Write a message") as blank:
            module.message_body_payload({"body": "   "})
        self.assertEqual(blank.exception.field_errors["body"], ["Write a message before sending."])
        with self.assertRaisesRegex(module.MessageThreadError, "1000") as oversized:
            module.message_body_payload({"body": "x" * 1001})
        self.assertEqual(oversized.exception.field_errors["body"], ["Keep messages under 1000 characters."])

        summary = module.message_thread_summary(
            {
                "id": 42,
                "job_id": 12,
                "title": "Window cleaning",
                "category": "Window cleaning",
                "city": "Arlington",
                "state": "VA",
                "price_range": "$450-$650",
                "timeline": "Two business days",
                "availability": "Tuesday morning",
                "client_name": "Avery Client",
                "contractor_id": 7,
                "contractor_name": "Doe Powerwash",
                "verified_completion_count": 3,
                "source_checked_credential_count": 2,
                "source_checked_license_count": 1,
                "last_message": "Can you start Tuesday?",
                "last_message_id": 9,
                "last_sender_id": 7,
                "message_count": 2,
                "unread_count": 1,
                "client_email": "private@example.com",
            },
            viewer_id=8,
        )
        self.assertEqual(summary["url"], "/messages/42")
        self.assertEqual(summary["message_count"], 2)
        self.assertEqual(summary["unread_count"], 1)
        self.assertTrue(summary["has_unread"])
        self.assertTrue(summary["needs_reply"])
        self.assertEqual(summary["price_range"], "$450-$650")
        self.assertEqual(summary["timeline"], "Two business days")
        self.assertEqual(summary["availability"], "Tuesday morning")
        self.assertEqual(summary["provider"]["name"], "Doe Powerwash")
        self.assertEqual(
            summary["provider"]["profile_url"],
            "/contractors/7?job_id=12",
        )
        self.assertEqual(
            summary["provider"]["reputation"]["level_label"],
            "Steady provider",
        )
        self.assertEqual(
            summary["provider"]["reputation"]["trust_record"]["label"],
            "1 license source checked",
        )
        self.assertEqual(summary["provider"]["reputation"]["ranking_effect"], "none")
        self.assertNotIn("client_email", summary)
        self.assertNotIn("last_sender_id", summary)
        self.assertNotIn("claimed_identifier", json.dumps(summary))
        listing_rows = [
            summary,
            {
                **summary,
                "id": 43,
                "message_count": 4,
                "unread_count": 0,
                "needs_reply": False,
            },
        ]
        unread_listing = module.message_threads_listing_payload(listing_rows, "unread")
        self.assertEqual(unread_listing["view"], "unread")
        self.assertEqual([thread["id"] for thread in unread_listing["threads"]], [42])
        self.assertEqual(unread_listing["stats"]["threads"], 2)
        self.assertEqual(unread_listing["stats"]["messages"], 6)
        self.assertEqual(unread_listing["stats"]["unread"], 1)
        self.assertEqual(unread_listing["stats"]["unread_threads"], 1)
        self.assertEqual(unread_listing["stats"]["reply_threads"], 1)
        reply_listing = module.message_threads_listing_payload(listing_rows, "reply")
        self.assertEqual(reply_listing["view"], "reply")
        self.assertEqual([thread["id"] for thread in reply_listing["threads"]], [42])
        invalid_listing = module.message_threads_listing_payload(listing_rows, "invalid")
        self.assertEqual(invalid_listing["view"], "all")
        self.assertEqual(len(invalid_listing["threads"]), 2)
        detail = module.thread_detail_payload(
            summary,
            [
                {
                    "id": 5,
                    "sender_id": 7,
                    "display_name": "Doe Powerwash",
                    "body": "Yes, Tuesday works.",
                    "is_hidden": 0,
                    "created_at": "2026-08-03T12:00:00+00:00",
                }
            ],
        )
        self.assertEqual(detail["messages"][0]["body"], "Yes, Tuesday works.")
        read_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0030_thread_reads.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS thread_reads", read_migration)
        self.assertIn("PRIMARY KEY (thread_id, user_id)", read_migration)
        self.assertIn("last_read_message_id INTEGER NOT NULL DEFAULT 0", read_migration)
        self.assertIn("idx_messages_thread_unread", read_migration)
        self.assertNotIn("body", read_migration.lower())
        nav_index_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0031_thread_nav_indexes.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("idx_threads_client", nav_index_migration)
        self.assertIn("idx_threads_contractor", nav_index_migration)
        worker_source = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'if request.method != "HEAD" and row_value(user, "role") != "admin":',
            worker_source,
        )
        with self.assertRaisesRegex(module.MessageThreadError, "Unsupported"):
            module.parse_thread_id("/api/messages/threads/0")

    def test_cloudflare_moderation_report_helper_matches_local_report_contract(self):
        module = load_moderation_reports_module()
        report = module.report_payload(
            {
                "target_type": " Job ",
                "target_id": "42",
                "reason": "  This lead includes suspicious contact instructions.  ",
            }
        )
        self.assertEqual(report["target_type"], "job")
        self.assertEqual(report["target_id"], 42)
        self.assertEqual(report["reason"], "This lead includes suspicious contact instructions.")
        self.assertEqual(
            module.report_target_query("profile"),
            "SELECT 1 FROM contractor_profiles WHERE user_id = ? LIMIT 1",
        )
        active_user = {"id": 8, "role": "client", "status": "active"}
        suspended_user = {"id": 9, "role": "contractor", "status": "suspended"}
        self.assertTrue(module.can_create_report(active_user))
        self.assertFalse(module.can_create_report(suspended_user))
        self.assertFalse(module.can_create_report(None))

        response = module.report_response(12, report)
        self.assertEqual(response["status"], "open")
        self.assertEqual(response["message"], "Report sent to moderation.")
        self.assertNotIn("reason", response)

        for payload in (
            {"target_type": "job", "target_id": "0", "reason": "Missing id."},
            {"target_type": "invoice", "target_id": "42", "reason": "Wrong target."},
            {"target_type": "message", "target_id": "42", "reason": "   "},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(module.ModerationReportError) as invalid:
                    module.report_payload(payload)
                self.assertIn("Choose what to report and include a reason.", invalid.exception.errors)

        with self.assertRaises(module.ModerationReportError) as too_long:
            module.report_payload(
                {"target_type": "profile", "target_id": "7", "reason": "x" * 501}
            )
        self.assertIn("Keep report notes under 500 characters.", too_long.exception.errors)

    def test_cloudflare_admin_moderation_helper_matches_local_admin_actions(self):
        module = load_admin_moderation_module()
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/users/42/suspend"),
            {"target_type": "user", "target_id": 42, "action": "suspend"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/jobs/12/restore"),
            {"target_type": "job", "target_id": 12, "action": "restore"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/photos/job/5/hide"),
            {"target_type": "job_photo", "target_id": 5, "action": "hide"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/photos/contractor/6/restore"),
            {"target_type": "contractor_photo", "target_id": 6, "action": "restore"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/messages/8/hide"),
            {"target_type": "message", "target_id": 8, "action": "hide"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/messages/8/restore"),
            {"target_type": "message", "target_id": 8, "action": "restore"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/reports/9/resolve"),
            {"target_type": "report", "target_id": 9, "action": "resolve"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/reviews/10/hide"),
            {"target_type": "match_review", "target_id": 10, "action": "hide"},
        )
        self.assertEqual(
            module.parse_admin_moderation_path("/api/admin/review-reports/11/resolve"),
            {
                "target_type": "match_review_report",
                "target_id": 11,
                "action": "resolve",
            },
        )
        with self.assertRaisesRegex(module.AdminModerationError, "Unsupported"):
            module.parse_admin_moderation_path("/api/admin/users/42/delete")

        admin = {"id": 1, "role": "admin", "status": "active"}
        client = {"id": 2, "role": "client", "status": "active"}
        suspended_admin = {"id": 3, "role": "admin", "status": "suspended"}
        self.assertTrue(module.can_admin_moderate(admin))
        self.assertFalse(module.can_admin_moderate(client))
        self.assertFalse(module.can_admin_moderate(suspended_admin))

        sql, params, notes, state = module.admin_update_statement(
            {"target_type": "job", "target_id": 12, "action": "hide"},
            "2026-08-03T12:00:00+00:00",
        )
        self.assertEqual(sql, "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?")
        self.assertEqual(params, ["hidden", "2026-08-03T12:00:00+00:00", 12])
        self.assertEqual(notes, "Set job status to hidden.")
        self.assertEqual(state, "hidden")

        user_sql, user_params, user_notes, user_state = module.admin_update_statement(
            {"target_type": "user", "target_id": 42, "action": "activate"},
            "2026-08-03T12:00:00+00:00",
        )
        self.assertEqual(user_sql, "UPDATE users SET status = ? WHERE id = ?")
        self.assertEqual(user_params, ["active", 42])
        self.assertEqual(user_notes, "Set user status to active.")
        self.assertEqual(user_state, "active")

        message_sql, message_params, message_notes, message_state = module.admin_update_statement(
            {"target_type": "message", "target_id": 8, "action": "restore"},
            "2026-08-03T12:00:00+00:00",
        )
        self.assertEqual(message_sql, "UPDATE messages SET is_hidden = ? WHERE id = ?")
        self.assertEqual(message_params, [0, 8])
        self.assertEqual(message_notes, "Set message hidden=0.")
        self.assertEqual(message_state, "visible")

        report_sql, report_params, report_notes, report_state = module.admin_update_statement(
            {"target_type": "report", "target_id": 9, "action": "resolve"},
            "2026-08-03T12:00:00+00:00",
        )
        self.assertEqual(
            report_sql,
            "UPDATE reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
        )
        self.assertEqual(report_params, ["2026-08-03T12:00:00+00:00", 9])
        self.assertEqual(report_notes, "Marked report resolved.")
        self.assertEqual(report_state, "resolved")
        review_sql, review_params, review_notes, review_state = (
            module.admin_update_statement(
                {"target_type": "match_review", "target_id": 10, "action": "hide"},
                "2026-08-03T12:00:00+00:00",
            )
        )
        self.assertEqual(
            review_sql,
            "UPDATE match_reviews SET is_hidden = ?, updated_at = ? WHERE id = ?",
        )
        self.assertEqual(review_params, [1, "2026-08-03T12:00:00+00:00", 10])
        self.assertEqual(review_notes, "Set completed-work feedback hidden=1.")
        self.assertEqual(review_state, "hidden")
        review_report_sql, review_report_params, review_report_notes, review_report_state = (
            module.admin_update_statement(
                {
                    "target_type": "match_review_report",
                    "target_id": 11,
                    "action": "resolve",
                },
                "2026-08-03T12:00:00+00:00",
            )
        )
        self.assertEqual(
            review_report_sql,
            "UPDATE match_review_reports SET status = 'resolved', resolved_at = ? WHERE id = ?",
        )
        self.assertEqual(
            review_report_params,
            ["2026-08-03T12:00:00+00:00", 11],
        )
        self.assertEqual(
            review_report_notes,
            "Marked completed-work feedback report resolved.",
        )
        self.assertEqual(review_report_state, "resolved")
        self.assertEqual(
            module.admin_target_query("message"),
            "SELECT 1 FROM messages WHERE id = ? LIMIT 1",
        )
        self.assertEqual(
            module.admin_target_query("match_review"),
            "SELECT 1 FROM match_reviews WHERE id = ? LIMIT 1",
        )
        response = module.admin_moderation_response(
            {"target_type": "message", "target_id": 8, "action": "hide"},
            "hidden",
        )
        self.assertEqual(response["url"], "/admin")
        self.assertEqual(response["state"], "hidden")

    def test_clerk_webhook_signature_helper_accepts_signed_events(self):
        module = load_clerk_webhooks_module()
        secret = "whsec_" + base64.b64encode(b"workdoe-webhook-secret").decode("ascii")
        message_id = "msg_workdoe_123"
        timestamp = "1700000000"
        raw_body = json.dumps(
            {
                "object": "event",
                "id": "evt_workdoe_123",
                "type": "user.created",
                "data": {"id": "user_workdoe_123"},
            },
            separators=(",", ":"),
        )
        signature = module.svix_signature(
            secret=secret,
            message_id=message_id,
            timestamp=timestamp,
            raw_body=raw_body,
        )
        event = module.verify_svix_signature(
            secret=secret,
            headers={
                "svix-id": message_id,
                "svix-timestamp": timestamp,
                "svix-signature": f"v1,{signature}",
            },
            raw_body=raw_body,
            now=1700000000,
        )
        self.assertEqual(event["type"], "user.created")
        self.assertEqual(event["data"]["id"], "user_workdoe_123")

    def test_clerk_webhook_signature_helper_rejects_bad_events(self):
        module = load_clerk_webhooks_module()
        secret = "whsec_" + base64.b64encode(b"workdoe-webhook-secret").decode("ascii")
        message_id = "msg_workdoe_123"
        timestamp = "1700000000"
        raw_body = '{"object":"event","type":"user.updated","data":{"id":"user_123"}}'
        signature = module.svix_signature(
            secret=secret,
            message_id=message_id,
            timestamp=timestamp,
            raw_body=raw_body,
        )
        headers = {
            "svix-id": message_id,
            "svix-timestamp": timestamp,
            "svix-signature": f"v1,{signature}",
        }

        with self.assertRaisesRegex(module.SvixVerificationError, "does not match"):
            module.verify_svix_signature(
                secret=secret,
                headers=headers,
                raw_body='{"object":"event","type":"user.updated","data":{"id":"user_456"}}',
                now=1700000000,
            )
        with self.assertRaisesRegex(module.SvixVerificationError, "outside"):
            module.verify_svix_signature(
                secret=secret,
                headers=headers,
                raw_body=raw_body,
                now=1700001000,
            )
        with self.assertRaisesRegex(module.SvixVerificationError, "Missing"):
            module.verify_svix_signature(
                secret=secret,
                headers={"svix-id": message_id},
                raw_body=raw_body,
                now=1700000000,
            )

    def test_clerk_webhook_sync_payload_for_linked_user_events(self):
        module = load_clerk_webhooks_module()
        payload = module.clerk_user_sync_payload(
            {
                "object": "event",
                "type": "user.updated",
                "data": {
                    "id": "user_workdoe_123",
                    "primary_email_address_id": "email_primary",
                    "email_addresses": [
                        {
                            "id": "email_secondary",
                            "email_address": "old@example.com",
                            "verification": {"status": "verified"},
                        },
                        {
                            "id": "email_primary",
                            "email_address": " Contractor@Workdoe.com ",
                            "verification": {"status": "verified"},
                        },
                    ],
                    "banned": False,
                    "locked": False,
                },
            }
        )
        self.assertTrue(payload["syncable"])
        self.assertEqual(payload["clerk_user_id"], "user_workdoe_123")
        self.assertEqual(payload["email"], "contractor@workdoe.com")
        self.assertEqual(payload["email_verified"], 1)
        self.assertEqual(payload["status"], "active")

        deleted = module.clerk_user_sync_payload(
            {
                "object": "event",
                "type": "user.deleted",
                "data": {"id": "user_workdoe_123"},
            }
        )
        self.assertTrue(deleted["syncable"])
        self.assertEqual(deleted["status"], "suspended")

        unsupported = module.clerk_user_sync_payload(
            {
                "object": "event",
                "type": "session.created",
                "data": {"id": "sess_workdoe_123"},
            }
        )
        self.assertFalse(unsupported["syncable"])
        self.assertEqual(unsupported["reason"], "unsupported-event")

    def test_cloudflare_preflight_passes_local_artifacts_with_placeholder_warnings(self):
        module = load_preflight_script()
        self.assertTrue(module.valid_workdoe_clerk_proxy_url("https://workdoe.com/__clerk"))
        self.assertFalse(module.valid_workdoe_clerk_proxy_url("https://clerk.workdoe.com"))
        self.assertFalse(module.valid_workdoe_clerk_proxy_url("https://evilworkdoe.com"))
        self.assertTrue(module.valid_clerk_fapi_url("https://frontend-api.clerk.dev"))
        self.assertFalse(module.valid_clerk_fapi_url("https://frontend-api.clerk.dev/extra"))
        result = module.run_preflight(ROOT)
        self.assertTrue(result.ok, result.errors)
        self.assertIn("Wrangler enables Python Workers", result.checks)
        self.assertIn(
            "D1 unread-navigation queries are indexed for both marketplace roles",
            result.checks,
        )
        self.assertIn("Wrangler keeps Clerk same-domain OTP mode", result.checks)
        self.assertIn(
            "Wrangler requires Clerk, Workdoe, and Turnstile secrets",
            result.checks,
        )
        self.assertIn("Wrangler keeps required secret names out of vars", result.checks)
        self.assertIn(
            "Manifest records the Cloudflare static-asset headers policy",
            result.checks,
        )
        self.assertIn("Cloudflare static assets disable MIME sniffing", result.checks)
        self.assertIn(
            "Cloudflare caches versioned and integrity-pinned assets immutably",
            result.checks,
        )
        self.assertIn(
            "Cloudflare immutable caching stays on reviewed asset paths",
            result.checks,
        )
        self.assertIn("Cloudflare Worker Python compiles", result.checks)
        self.assertIn(
            "Pilot metrics cover response, closure, and report health without private fields",
            result.checks,
        )
        self.assertIn("Cloudflare authenticated app shell helper compiles", result.checks)
        self.assertIn("Clerk onboarding helper compiles", result.checks)
        self.assertIn("Clerk session verification helper compiles", result.checks)
        self.assertIn("Cloudflare email-code auth helper compiles", result.checks)
        self.assertIn(
            "Cloudflare native email codes are rate-limited and consumed atomically",
            result.checks,
        )
        self.assertIn("Clerk Frontend API proxy helper compiles", result.checks)
        self.assertIn("Cloudflare email payload helper compiles", result.checks)
        self.assertIn("Cloudflare admin moderation helper compiles", result.checks)
        self.assertIn("Cloudflare contractor profile helper compiles", result.checks)
        self.assertIn(
            "Cloudflare contractor proposal-template helper compiles",
            result.checks,
        )
        self.assertIn("Cloudflare public contractor profile helper compiles", result.checks)
        self.assertIn("Cloudflare client jobs helper compiles", result.checks)
        self.assertIn("Cloudflare client requests helper compiles", result.checks)
        self.assertIn("Cloudflare same-domain entry shell helper compiles", result.checks)
        self.assertIn("Cloudflare job detail helper compiles", result.checks)
        self.assertIn("Cloudflare job status helper compiles", result.checks)
        self.assertIn("Wrangler configures Workdoe transactional email vars", result.checks)
        self.assertIn("Wrangler restricts Cloudflare Email sender binding", result.checks)
        self.assertIn("Cloudflare job posting helper compiles", result.checks)
        self.assertIn(
            "Cloudflare Worker redacts transactional email audit metadata",
            result.checks,
        )
        self.assertIn(
            "Cloudflare public contractor profiles redact upload filenames",
            result.checks,
        )
        self.assertIn("Cloudflare project draft helper compiles", result.checks)
        self.assertIn("D1 project draft and budget migration is incremental", result.checks)
        self.assertIn(
            "D1 contractor proposal templates exclude price and location",
            result.checks,
        )
        self.assertIn(
            "Contractor proposal templates stay owner-only and require a fresh price",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker preserves an expiring pre-verification project draft",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker preserves visual task selection and native fallback",
            result.checks,
        )
        self.assertIn("Cloudflare Turnstile helper compiles", result.checks)
        self.assertIn("Cloudflare match request helper compiles", result.checks)
        self.assertIn("Cloudflare match decision helper compiles", result.checks)
        self.assertIn("Cloudflare message thread helper compiles", result.checks)
        self.assertIn("Cloudflare moderation report helper compiles", result.checks)
        self.assertIn(
            "Cloudflare Worker maps verified Clerk sessions to Workdoe users",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker creates role-owned Workdoe users after Clerk verification",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker lets contractors update their profiles",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker exposes privacy-safe contractor profiles",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker exposes signed-in contractor lead board data",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker exposes contractor mini-bid dashboard data",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker exposes client job dashboard data",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker exposes client mini-bid review data",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker serves same-domain Clerk entry pages",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker serves authenticated post-login app pages",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker serves public trust pages and discovery files",
            result.checks,
        )
        self.assertIn(
            "D1 email reminders require affirmative consent",
            result.checks,
        )
        self.assertIn("Cloudflare contractor leads helper compiles", result.checks)
        self.assertIn("Cloudflare contractor bids helper compiles", result.checks)
        self.assertIn("Cloudflare public jobs helper compiles", result.checks)
        self.assertIn("Cloudflare launch plan helper compiles", result.checks)
        self.assertIn("Cloudflare launch status helper compiles", result.checks)
        self.assertIn("Cloudflare Wrangler resolver helper compiles", result.checks)
        self.assertIn("Cloudflare Clerk proxy proof helper compiles", result.checks)
        self.assertIn("Cloudflare secret evidence helper compiles", result.checks)
        self.assertIn("Cloudflare release evidence helper compiles", result.checks)
        self.assertIn("Cloudflare D1 ID apply helper compiles", result.checks)
        self.assertIn("Cloudflare resource bootstrap helper compiles", result.checks)
        self.assertIn("Cloudflare production deploy helper compiles", result.checks)
        self.assertIn("GitHub deploy dispatch helper compiles", result.checks)
        self.assertIn("Workdoe launch handoff helper compiles", result.checks)
        self.assertIn("Workdoe DNS diagnostic helper compiles", result.checks)
        self.assertIn("Workdoe production smoke helper compiles", result.checks)
        self.assertIn(
            "Cloudflare Worker sends and audits queued transactional emails",
            result.checks,
        )
        self.assertIn("Cloudflare Worker verifies and syncs linked Clerk users", result.checks)
        self.assertIn(
            "Cloudflare Worker exposes privacy-preserving public jobs API",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker exposes privacy-safe signed-in job details",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker lets clients close and reopen their jobs",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker creates and edits client jobs with Turnstile and owner checks",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker creates contractor mini bids with Turnstile and duplicate checks",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker lets clients approve or reject mini bids and open threads",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker supports private approved-match messaging",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker accepts signed-in moderation reports",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Worker supports admin moderation actions",
            result.checks,
        )
        self.assertIn(
            "Cloudflare D1 ID helper safely updates Wrangler IDs",
            result.checks,
        )
        self.assertIn(
            "Cloudflare resource bootstrap is dry-run gated",
            result.checks,
        )
        self.assertIn(
            "Cloudflare production deploy is strict-readiness gated",
            result.checks,
        )
        self.assertIn(
            "Cloudflare Clerk controlled-beta proof helper is confirm-gated",
            result.checks,
        )
        self.assertIn(
            "Cloudflare secret evidence helper is dry-run gated",
            result.checks,
        )
        self.assertIn(
            "Cloudflare release evidence helper validates local proof files",
            result.checks,
        )
        self.assertIn("Clerk webhook signature helper compiles", result.checks)
        self.assertNotIn(
            "Wrangler D1 database_id is still the placeholder UUID.",
            result.warnings,
        )

    def test_cloudflare_preflight_strict_blocks_placeholder_resource_ids(self):
        module = load_preflight_script()
        result = module.run_preflight(ROOT, strict_production=True)
        self.assertTrue(result.ok, result.errors)

    def test_cloudflare_readiness_doctor_separates_local_and_production_readiness(self):
        module = load_readiness_script()
        local = module.run_readiness(ROOT)
        self.assertTrue(local.ready, local.blockers)
        self.assertIn("Wrangler config is present", local.checks)
        self.assertIn("Same-domain Clerk email-code mode is configured", local.checks)
        self.assertIn("Worker has email-code request endpoint", local.checks)
        self.assertIn("Worker has email-code verification endpoint", local.checks)
        self.assertIn("Worker issues protected session cookies", local.checks)
        self.assertIn("Worker has authenticated app page shell", local.checks)
        self.assertIn("Worker has same-domain contractor profile page shell", local.checks)
        self.assertIn("Worker has same-domain message page shell", local.checks)
        self.assertIn("Worker has same-domain admin dashboard shell", local.checks)
        self.assertIn("Worker has client jobs dashboard API", local.checks)
        self.assertIn("Worker has client mini-bid review API", local.checks)
        self.assertIn("Worker has contractor leads board API", local.checks)
        self.assertIn("Worker has contractor mini-bid dashboard API", local.checks)
        self.assertIn("Worker has privacy-safe job detail API", local.checks)
        self.assertIn("Worker has client job status API", local.checks)
        self.assertIn("Worker has contractor profile API", local.checks)
        self.assertIn("Worker has public contractor profile API", local.checks)
        self.assertIn("Worker has client job posting API", local.checks)
        self.assertIn("Worker has contractor mini-bid API", local.checks)
        self.assertIn("Worker has client mini-bid decision API", local.checks)
        self.assertIn("Worker has private approved-match messaging API", local.checks)
        self.assertIn("Worker has moderation report API", local.checks)
        self.assertIn("Worker has admin moderation action API", local.checks)
        self.assertIn("Worker has private R2 upload route", local.checks)
        self.assertIn("Worker has private R2 serving route", local.checks)
        self.assertIn("Cloudflare secret presence was not checked; pass --secret-list-json for deploy proof.", local.warnings)
        self.assertIn("wrangler secret put WORKDOE_SECRET_KEY", local.next_steps)
        self.assertIn(
            "python ..\\scripts\\cloudflare_clerk_proxy_proof.py --confirm --confirm-restricted-sign-up --confirm-email-code-only --confirm-legal-consent --output ..\\clerk-proxy-proof.local.json",
            local.next_steps,
        )
        for command in (
            "python ..\\scripts\\cloudflare_release_evidence.py",
            "python ..\\scripts\\cloudflare_readiness.py",
            "python scripts\\cloudflare_production_deploy.py --json",
            "python scripts\\cloudflare_production_deploy.py --execute --yes",
        ):
            matching = [step for step in local.next_steps if step.startswith(command)]
            self.assertEqual(len(matching), 1, command)
            self.assertIn("--clerk-proxy-proof-json", matching[0])

        strict = module.run_readiness(ROOT, strict_production=True)
        self.assertFalse(strict.ready)
        self.assertIn(
            "Cloudflare secret presence is unverified. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes` and pass --secret-list-json.",
            strict.blockers,
        )
        self.assertNotIn(
            "Wrangler D1 database_id is still the placeholder UUID.",
            strict.blockers,
        )

    def test_cloudflare_readiness_doctor_validates_secret_exports_and_env_files(self):
        module = load_readiness_script()
        self.assertTrue(module.valid_workdoe_clerk_proxy_url("https://workdoe.com/__clerk"))
        self.assertFalse(module.valid_workdoe_clerk_proxy_url("https://clerk.workdoe.com"))
        self.assertFalse(module.valid_workdoe_clerk_proxy_url("https://evilworkdoe.com"))
        self.assertFalse(module.valid_workdoe_clerk_proxy_url("https://workdoe.com.evil.test"))
        self.assertTrue(module.valid_clerk_fapi_url("https://frontend-api.clerk.dev"))
        self.assertFalse(module.valid_clerk_fapi_url("https://frontend-api.clerk.dev/extra"))
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_path = tmp_path / ".dev.vars"
            env_path.write_text(
                "\n".join(
                    f"{key}=real-{key.lower()}"
                    for key in sorted(module.REQUIRED_SECRETS)
                )
                + "\nCLERK_FRONTEND_API_URL=https://workdoe.com/__clerk"
                + "\nCLERK_PROXY_URL=https://workdoe.com/__clerk"
                + "\nCLERK_FAPI=https://frontend-api.clerk.dev"
                + "\nWORKDOE_AUTH_PROVIDER=clerk"
                + "\nWORKDOE_LOGIN_MODE=same_domain_email_code"
                + "\nWORKDOE_ENFORCE_SERVICE_ACTIVATION=true",
                encoding="utf-8",
            )
            secret_list_path = tmp_path / "secret-list.json"
            secret_list_path.write_text(
                json.dumps(
                    {
                        "source": "wrangler secret list --json",
                        "contains_values": False,
                        "result": [{"name": key} for key in sorted(module.REQUIRED_SECRETS)],
                    }
                ),
                encoding="utf-8",
            )
            proxy_proof_path = tmp_path / "clerk-proxy-proof.json"
            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            result = module.run_readiness(
                ROOT,
                env_file=env_path,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertTrue(result.ready, result.blockers)
            self.assertIn("Provided env file contains all required auth config names", result.checks)
            self.assertIn("Provided env file does not use placeholder auth config values", result.checks)
            self.assertIn("Cloudflare secret list contains every required secret name", result.checks)
            self.assertIn("Same-domain Clerk proxy proof is present", result.checks)

            strict_with_sanitized_evidence = module.run_readiness(
                ROOT,
                strict_production=True,
                env_file=env_path,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertIn(
                "Cloudflare secret-name evidence is sanitized",
                strict_with_sanitized_evidence.checks,
            )

            raw_secret_list_path = tmp_path / "raw-secret-list.json"
            raw_secret_list_path.write_text(
                json.dumps({"result": [{"name": key} for key in sorted(module.REQUIRED_SECRETS)]}),
                encoding="utf-8",
            )
            strict_with_raw_evidence = module.run_readiness(
                ROOT,
                strict_production=True,
                env_file=env_path,
                secret_list_json=raw_secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertIn(
                "Cloudflare secret evidence must be sanitized with contains_values=false. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes`.",
                strict_with_raw_evidence.blockers,
            )

            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://clerk.workdoe.com",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            bad_proxy_proof = module.run_readiness(
                ROOT,
                env_file=env_path,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertFalse(bad_proxy_proof.ready)
            self.assertIn(
                "Clerk proxy proof must use https://workdoe.com/__clerk.",
                bad_proxy_proof.blockers,
            )

            proxy_proof_path.write_text("{not-json", encoding="utf-8")
            self.assertEqual(
                module.clerk_proxy_proof_error(proxy_proof_path),
                f"Clerk proxy proof JSON is missing or invalid: {proxy_proof_path}",
            )

            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )

            env_path.write_text("WORKDOE_SECRET_KEY=replace-me\n", encoding="utf-8")
            missing = module.run_readiness(
                ROOT,
                env_file=env_path,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertFalse(missing.ready)
            self.assertTrue(
                any("Provided env file is missing required keys" in item for item in missing.blockers)
            )
            self.assertTrue(
                any("placeholder values" in item for item in missing.blockers)
            )

            env_path.write_text(
                "\n".join(
                    f"{key}=real-{key.lower()}"
                    for key in sorted(module.REQUIRED_SECRETS)
                )
                + "\nCLERK_FRONTEND_API_URL=https://evilworkdoe.com"
                + "\nCLERK_PROXY_URL=https://evilworkdoe.com"
                + "\nCLERK_FAPI=https://frontend-api.clerk.dev"
                + "\nWORKDOE_AUTH_PROVIDER=clerk"
                + "\nWORKDOE_LOGIN_MODE=same_domain_email_code"
                + "\nWORKDOE_ENFORCE_SERVICE_ACTIVATION=true",
                encoding="utf-8",
            )
            off_domain = module.run_readiness(
                ROOT,
                env_file=env_path,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertTrue(off_domain.ready, off_domain.blockers)
            self.assertIn("Same-domain Clerk proxy proof is present", off_domain.checks)

    def test_cloudflare_launch_plan_prints_safe_operator_sequence(self):
        module = load_launch_plan_script()
        original_token_present = module.cloudflare_api_token_present
        try:
            module.cloudflare_api_token_present = lambda: False
            plan = module.build_launch_plan(ROOT)
        finally:
            module.cloudflare_api_token_present = original_token_present
        self.assertEqual(plan["service"], "workdoe")
        self.assertEqual(plan["domain"], "workdoe.com")
        self.assertEqual(plan["overall_status"], "pending")
        self.assertTrue(plan["safe_by_default"])
        self.assertFalse(plan["executes_commands"])
        phases = {step["phase"]: step for step in plan["steps"]}
        self.assertEqual(phases["local-artifacts"]["status"], "ready")
        self.assertEqual(phases["cloudflare-token"]["status"], "pending")
        self.assertEqual(phases["cloudflare-resources"]["status"], "ready")
        self.assertEqual(phases["identity-and-secrets"]["status"], "blocked")
        self.assertEqual(phases["clerk-domain-proof"]["status"], "pending")
        self.assertEqual(phases["deploy-gate"]["status"], "pending")
        self.assertEqual(phases["migrate-and-deploy"]["status"], "blocked")
        self.assertIn(
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
            phases["cloudflare-token"]["commands"],
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
            phases["cloudflare-token"]["commands"],
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe --env production",
            phases["cloudflare-token"]["commands"],
        )
        self.assertIn(
            "python scripts\\cloudflare_resource_bootstrap.py --json --no-secret-probe",
            phases["cloudflare-resources"]["commands"],
        )
        self.assertIn(
            "python scripts\\cloudflare_resource_bootstrap.py --execute --yes --no-secret-probe",
            phases["cloudflare-resources"]["commands"],
        )
        self.assertIn(
            "wrangler secret put CLERK_SECRET_KEY",
            phases["identity-and-secrets"]["commands"],
        )
        self.assertIn(
            "python ..\\scripts\\cloudflare_secret_evidence.py --execute --yes --output ..\\cloudflare-secret-list.local.json",
            phases["identity-and-secrets"]["commands"],
        )
        self.assertEqual(phases["identity-and-secrets"]["commands"][-1], "cd ..")
        self.assertIn(
            "python scripts\\cloudflare_readiness.py --strict-production --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json",
            phases["deploy-gate"]["commands"],
        )
        self.assertIn(
            "python scripts\\cloudflare_release_evidence.py --json --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json",
            phases["deploy-gate"]["commands"],
        )
        self.assertIn(
            "python scripts\\cloudflare_production_deploy.py --json --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json",
            phases["migrate-and-deploy"]["commands"],
        )
        self.assertIn(
            "python scripts\\cloudflare_production_deploy.py --execute --yes --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json",
            phases["migrate-and-deploy"]["commands"],
        )
        self.assertIn(
            "python scripts\\cloudflare_clerk_proxy_proof.py --confirm",
            phases["clerk-domain-proof"]["commands"][1],
        )
        rendered = module.render_markdown(plan)
        self.assertIn("Workdoe Cloudflare Launch Plan", rendered)
        self.assertIn("This plan is safe by default.", rendered)
        self.assertIn("cloudflare_secret_evidence.py --execute --yes", rendered)
        self.assertIn("cloudflare_release_evidence.py --json", rendered)
        self.assertIn("Set non-interactive Cloudflare API token", rendered)
        self.assertIn("Confirm Clerk same-domain proxy", rendered)
        self.assertIn("https://workdoe.com/__clerk", rendered)
        self.assertIn("curl.exe -fS -I https://workdoe.com/health", rendered)
        self.assertIn("curl.exe -fsS https://workdoe.com/api/jobs/open?limit=3", rendered)

    def test_cloudflare_launch_plan_accepts_secret_list_and_clerk_proxy_evidence(self):
        module = load_launch_plan_script()
        readiness = load_readiness_script()
        with tempfile.TemporaryDirectory() as tmp:
            secret_list_path = Path(tmp) / "secret-list.json"
            secret_list_path.write_text(
                json.dumps(
                    {
                        "source": "wrangler secret list --json",
                        "contains_values": False,
                        "result": [{"name": key} for key in sorted(readiness.REQUIRED_SECRETS)],
                    }
                ),
                encoding="utf-8",
            )
            proxy_proof_path = Path(tmp) / "clerk-proxy-proof.json"
            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            plan = module.build_launch_plan(
                ROOT,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
        phases = {step["phase"]: step for step in plan["steps"]}
        self.assertEqual(phases["identity-and-secrets"]["status"], "ready")
        self.assertEqual(phases["clerk-domain-proof"]["status"], "ready")
        self.assertEqual(plan["missing_secrets"], [])

    def test_cloudflare_launch_plan_requires_sanitized_secret_evidence(self):
        module = load_launch_plan_script()
        readiness = load_readiness_script()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_secret_list_path = tmp_path / "raw-secret-list.json"
            raw_secret_list_path.write_text(
                json.dumps(
                    {
                        "contains_values": True,
                        "result": [{"name": key} for key in sorted(readiness.REQUIRED_SECRETS)],
                    }
                ),
                encoding="utf-8",
            )
            proxy_proof_path = tmp_path / "clerk-proxy-proof.json"
            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            original_token_present = module.cloudflare_api_token_present
            try:
                module.cloudflare_api_token_present = lambda: True
                plan = module.build_launch_plan(
                    ROOT,
                    secret_list_json=raw_secret_list_path,
                    clerk_proxy_proof_json=proxy_proof_path,
                )
            finally:
                module.cloudflare_api_token_present = original_token_present
        phases = {step["phase"]: step for step in plan["steps"]}
        self.assertEqual(phases["identity-and-secrets"]["status"], "pending")
        self.assertEqual(plan["missing_secrets"], [])
        self.assertIn(
            "Cloudflare secret evidence must be sanitized with contains_values=false. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes`.",
            plan["strict_blockers"],
        )

    def test_github_cloudflare_workflow_is_manual_deploy_guarded(self):
        workflow = (ROOT / ".github" / "workflows" / "cloudflare-deploy.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Validate manual deploy confirmation", workflow)
        self.assertIn('test "${{ github.ref }}" = "refs/heads/main"', workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn('test "${{ inputs.deploy }}" = "DEPLOY"', workflow)
        self.assertIn('test "${{ inputs.clerk_proxy_confirmed }}" = "true"', workflow)
        self.assertIn('test "${{ inputs.restricted_signup_confirmed }}" = "true"', workflow)
        self.assertIn('test "${{ inputs.email_code_only_confirmed }}" = "true"', workflow)
        self.assertIn('test "${{ inputs.legal_consent_confirmed }}" = "true"', workflow)
        self.assertNotIn("inputs.clerk_proxy_url", workflow)
        self.assertIn("Check Cloudflare credentials are configured", workflow)
        self.assertIn('test -n "$CLOUDFLARE_API_TOKEN"', workflow)
        self.assertIn("Print guarded deploy plan", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("concurrency:", workflow)
        self.assertIn("Validate Cloudflare Worker bundle", workflow)
        self.assertIn("Record operator-confirmed Clerk release proof", workflow)
        self.assertIn("npm run cf:clerk:proof:confirm", workflow)
        self.assertIn("npm run security:all", workflow)
        self.assertIn("wrangler deploy --dry-run", workflow)
        self.assertIn("Smoke test Cloudflare Worker runtime", workflow)
        self.assertIn("wrangler d1 migrations apply workdoe --local", workflow)
        self.assertIn("http://127.0.0.1:8787/health", workflow)
        self.assertIn("Verify current main release candidate", workflow)
        self.assertIn("url: https://workdoe.com", workflow)
        self.assertIn("Capture pre-deployment recovery point", workflow)
        self.assertIn("wrangler d1 time-travel info workdoe", workflow)
        self.assertIn("wrangler deployments status --json", workflow)
        self.assertIn("worker-rollback-version.txt", workflow)
        self.assertIn("worker-rollback-command.txt", workflow)
        self.assertIn("Capture deployed Worker state", workflow)
        self.assertIn("production-deploy.log", workflow)
        self.assertIn(
            'npm run cf:deploy 2>&1 | tee "$evidence_dir/production-deploy.log"',
            workflow,
        )
        self.assertIn("Retain release recovery evidence", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("retention-days: 30", workflow)
        self.assertLess(
            workflow.index("Capture pre-deployment recovery point"),
            workflow.index("Deploy guarded production release"),
        )
        self.assertLess(
            workflow.index("Deploy guarded production release"),
            workflow.index("Capture deployed Worker state"),
        )
        self.assertIn(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7",
            workflow,
        )
        self.assertIn(
            "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6",
            workflow,
        )
        self.assertIn(
            "actions/setup-node@a0853c24544627f65ddf259abe73b1d18a591444 # v5",
            workflow,
        )
        self.assertIn(
            "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1",
            workflow,
        )

    def test_release_quality_and_provenance_gates_are_pinned(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        audit_requirements = (ROOT / "requirements-audit.txt").read_text(
            encoding="utf-8"
        )
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "cloudflare-deploy.yml").read_text(
            encoding="utf-8"
        )
        provenance = json.loads(
            (ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8")
        )
        license_notice = (ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertIn("ruff==0.16.4", audit_requirements)
        self.assertEqual(package["scripts"]["lint"], "ruff check .")
        self.assertIn("ruff check .", package["scripts"]["security:python"])
        self.assertEqual(
            package["scripts"]["provenance:verify"],
            "python scripts/verify_dependency_provenance.py",
        )
        self.assertIn("python -m pip install ruff==0.16.4", workflow)
        self.assertIn("npm run provenance:verify", workflow)
        self.assertIn("npm run lint", workflow)
        self.assertIn("npm run cf:d1:query-plan", workflow)
        self.assertIn("Ruff 0.16.4", notices)
        self.assertIn("Ruff is distributed under the MIT License", notices)
        self.assertEqual(provenance["first_party"]["license_status"], "proprietary")
        self.assertEqual(provenance["first_party"]["license_file"], "LICENSE")
        self.assertIn("Workdoe Proprietary License Notice", license_notice)

        completed = subprocess.run(
            [sys.executable, "scripts/verify_dependency_provenance.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Dependency provenance verified.", completed.stdout)

    def test_github_release_status_validates_environment_policy_and_secret_names(self):
        module = load_github_release_status_script()
        environment = {
            "name": "production",
            "can_admins_bypass": True,
            "deployment_branch_policy": {
                "protected_branches": False,
                "custom_branch_policies": True,
            },
        }
        branch_policies = {
            "branch_policies": [{"name": "main", "type": "branch"}],
        }
        status = module.build_status(
            environment=environment,
            branch_policies=branch_policies,
            secret_names={"CLOUDFLARE_API_TOKEN"},
        )
        self.assertFalse(status.ready)
        self.assertTrue(status.environment_ready)
        self.assertFalse(status.secrets_ready)
        self.assertIn(
            "GitHub deployment secret CLOUDFLARE_ACCOUNT_ID is missing from both repository and production environment secrets.",
            status.blockers,
        )
        self.assertIn("GitHub production environment currently allows admin bypass.", status.warnings)

        ready = module.build_status(
            environment=environment,
            branch_policies=branch_policies,
            secret_names=set(module.REQUIRED_DEPLOY_SECRETS),
        )
        self.assertTrue(ready.ready)

        environment_secret_ready = module.build_status(
            environment=environment,
            branch_policies=branch_policies,
            environment_secret_names=set(module.REQUIRED_DEPLOY_SECRETS),
        )
        self.assertTrue(environment_secret_ready.ready)
        self.assertTrue(environment_secret_ready.secrets_ready)
        payload = module.status_payload(environment_secret_ready)
        self.assertEqual(
            payload["environment_secret_names"],
            sorted(module.REQUIRED_DEPLOY_SECRETS),
        )
        json.dumps(payload)

        calls = []
        original_run_json = module.run_json
        original_run_text = module.run_text
        try:
            module.run_json = lambda command: (
                environment
                if command[-1].endswith("/production")
                else branch_policies,
                "",
            )

            def fake_run_text(command):
                calls.append(command)
                if "--env" in command:
                    return "\n".join(sorted(module.REQUIRED_DEPLOY_SECRETS)), ""
                return "", ""

            module.run_text = fake_run_text
            live_ready = module.build_live_status()
        finally:
            module.run_json = original_run_json
            module.run_text = original_run_text
        self.assertTrue(live_ready.secrets_ready)
        self.assertTrue(
            any("--env" in command and "production" in command for command in calls)
        )

        too_broad = module.build_status(
            environment={
                "name": "production",
                "deployment_branch_policy": {
                    "protected_branches": True,
                    "custom_branch_policies": False,
                },
            },
            branch_policies={"branch_policies": [{"name": "develop", "type": "branch"}]},
            secret_names=set(module.REQUIRED_DEPLOY_SECRETS),
        )
        self.assertFalse(too_broad.environment_ready)
        self.assertIn(
            "GitHub production environment must allow only the main branch.",
            too_broad.blockers,
        )

    def test_github_deploy_dispatch_requires_ready_doctor_and_synced_main(self):
        module = load_github_deploy_dispatch_script()
        original_doctor = module.build_doctor
        original_git_state = module.build_git_state
        try:
            module.build_doctor = lambda repo_root=ROOT, live=True, local_url=module.DEFAULT_LOCAL_URL: {
                "ready": False,
                "blockers": ["D1 database_id must be replaced with the real Cloudflare UUID."],
            }
            module.build_git_state = lambda repo_root=ROOT, expected_branch="main": module.GitState(
                branch="main",
                clean=True,
                head_sha="abc123",
                upstream_sha="abc123",
                synced_with_upstream=True,
            )
            plan = module.build_dispatch_plan(ROOT)

            module.build_doctor = lambda repo_root=ROOT, live=True, local_url=module.DEFAULT_LOCAL_URL: {
                "ready": True,
                "blockers": [],
            }
            module.build_git_state = lambda repo_root=ROOT, expected_branch="main": module.GitState(
                branch="feature/workdoe",
                clean=False,
                head_sha="abc123",
                upstream_sha="def456",
                synced_with_upstream=False,
                blockers=[
                    "Local branch must be main before dispatch.",
                    "Local worktree must be clean before dispatch.",
                    "Local HEAD must match the upstream branch before dispatch.",
                ],
            )
            git_blocked_plan = module.build_dispatch_plan(ROOT)
        finally:
            module.build_doctor = original_doctor
            module.build_git_state = original_git_state

        self.assertFalse(plan["ready_to_dispatch"])
        self.assertIn(
            "Launch doctor is not ready; resolve blockers before dispatching production deployment.",
            plan["blockers"],
        )
        self.assertIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            plan["blockers"],
        )
        self.assertEqual(plan["command"][0:4], ["gh", "workflow", "run", "cloudflare-deploy.yml"])
        self.assertIn("--ref", plan["command"])
        self.assertIn("deploy=DEPLOY", plan["command"])
        self.assertIn("clerk_proxy_confirmed=false", plan["command"])
        self.assertIn("restricted_signup_confirmed=false", plan["command"])
        self.assertIn("email_code_only_confirmed=false", plan["command"])
        self.assertIn("legal_consent_confirmed=false", plan["command"])
        confirmed_command = module.dispatch_command(
            clerk_proxy_confirmed=True,
            restricted_signup_confirmed=True,
            email_code_only_confirmed=True,
            legal_consent_confirmed=True,
        )
        self.assertIn("clerk_proxy_confirmed=true", confirmed_command)
        self.assertIn("restricted_signup_confirmed=true", confirmed_command)
        self.assertIn("email_code_only_confirmed=true", confirmed_command)
        self.assertIn("legal_consent_confirmed=true", confirmed_command)
        self.assertNotIn("clerk_proxy_url=https://workdoe.com/__clerk", plan["command"])
        self.assertFalse(git_blocked_plan["ready_to_dispatch"])
        self.assertIn("Local branch must be main before dispatch.", git_blocked_plan["blockers"])
        self.assertIn("Local worktree must be clean before dispatch.", git_blocked_plan["blockers"])
        self.assertIn(
            "Local HEAD must match the upstream branch before dispatch.",
            git_blocked_plan["blockers"],
        )

    def test_github_deploy_dispatch_execute_requires_yes(self):
        module = load_github_deploy_dispatch_script()
        original_plan = module.build_dispatch_plan
        original_argv = sys.argv
        try:
            module.build_dispatch_plan = lambda *args, **kwargs: {
                "service": "workdoe",
                "domain": "workdoe.com",
                "safe_by_default": True,
                "executes_commands": False,
                "ready_to_dispatch": True,
                "repository": "Yami566/workdoe",
                "workflow": "cloudflare-deploy.yml",
                "ref": "main",
                "clerk_proxy_url": "https://workdoe.com/__clerk",
                "command": ["gh", "workflow", "run", "cloudflare-deploy.yml"],
                "command_text": "gh workflow run cloudflare-deploy.yml",
                "git": {},
                "doctor": {},
                "blockers": [],
            }
            sys.argv = ["github_deploy_dispatch.py", "--execute", "--json"]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(module.main(), 1)
            payload = json.loads(stdout.getvalue())
        finally:
            module.build_dispatch_plan = original_plan
            sys.argv = original_argv

        self.assertFalse(payload["ready_to_dispatch"])
        self.assertTrue(payload["executes_commands"])
        self.assertIn("Dispatch requires --execute and --yes.", payload["blockers"])

    def test_github_deploy_dispatch_execute_requires_clerk_confirmations(self):
        module = load_github_deploy_dispatch_script()
        original_plan = module.build_dispatch_plan
        original_run_dispatch = module.run_dispatch
        original_argv = sys.argv
        try:
            module.build_dispatch_plan = lambda *args, **kwargs: {
                "service": "workdoe",
                "domain": "workdoe.com",
                "safe_by_default": True,
                "executes_commands": False,
                "ready_to_dispatch": False,
                "repository": "Yami566/workdoe",
                "workflow": "cloudflare-deploy.yml",
                "ref": "main",
                "operator_confirmations": {
                    "clerk_proxy_confirmed": False,
                    "restricted_signup_confirmed": False,
                    "email_code_only_confirmed": False,
                    "legal_consent_confirmed": False,
                },
                "command": ["gh", "workflow", "run", "cloudflare-deploy.yml"],
                "command_text": "gh workflow run cloudflare-deploy.yml",
                "git": {},
                "doctor": {},
                "blockers": [
                    "Dispatch requires explicit confirmation of the Clerk same-domain proxy, restricted sign-up, email-code-only sign-in, and express legal consent settings."
                ],
            }
            module.run_dispatch = lambda *args, **kwargs: self.fail(
                "run_dispatch should not run without Clerk confirmations"
            )
            sys.argv = [
                "github_deploy_dispatch.py",
                "--execute",
                "--yes",
                "--json",
            ]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(module.main(), 1)
            payload = json.loads(stdout.getvalue())
        finally:
            module.run_dispatch = original_run_dispatch
            module.build_dispatch_plan = original_plan
            sys.argv = original_argv

        self.assertFalse(payload["ready_to_dispatch"])
        self.assertIn(
            "Dispatch requires explicit confirmation of the Clerk same-domain proxy, restricted sign-up, email-code-only sign-in, and express legal consent settings.",
            payload["blockers"],
        )

    def test_workdoe_launch_handoff_renders_redacted_operator_checklist(self):
        module = load_workdoe_launch_handoff_script()
        original_doctor = module.build_doctor
        original_dispatch = module.build_dispatch_plan
        try:
            doctor_payload = {
                "ready": False,
                "blockers": [
                    "GitHub deployment secret CLOUDFLARE_API_TOKEN is missing from both repository and production environment secrets.",
                    "CLOUDFLARE_API_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456",
                    "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
                    f"Clerk proxy proof JSON is missing or invalid: {ROOT}\\clerk-proxy-proof.local.json",
                ],
                "next_actions": [
                    "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
                    "set CLOUDFLARE_API_TOKEN in this shell without committing it",
                    "npm run cf:resources:apply",
                ],
                "phases": [
                    {
                        "name": "github-release",
                        "status": "pending",
                        "summary": "GitHub release setup still has blockers.",
                        "next_command": "npm run github:release:status",
                    },
                    {
                        "name": "dns",
                        "status": "pending",
                        "summary": "workdoe.com does not resolve.",
                        "next_command": "confirm workdoe.com DNS in Cloudflare",
                    },
                ],
            }
            dispatch_payload = {
                "ready_to_dispatch": False,
                "repository": "Yami566/workdoe",
                "workflow": "cloudflare-deploy.yml",
                "ref": "main",
                "command_text": (
                    "gh workflow run cloudflare-deploy.yml --repo Yami566/workdoe "
                    "--ref main -f deploy=DEPLOY -f clerk_proxy_url=https://workdoe.com/__clerk"
                ),
                "git": {
                    "branch": "main",
                    "clean": True,
                    "synced_with_upstream": True,
                },
                "blockers": [
                    "Launch doctor is not ready; resolve blockers before dispatching production deployment."
                ],
            }
            module.build_doctor = lambda repo_root=ROOT, live=True, local_url=module.DEFAULT_LOCAL_URL: doctor_payload
            module.build_dispatch_plan = lambda repo_root=ROOT, local_url=module.DEFAULT_LOCAL_URL, **kwargs: dispatch_payload
            payload = module.build_handoff_payload(ROOT)
            markdown = module.render_markdown(payload)
            shareable_payload = module.build_handoff_payload(ROOT, shareable=True)
            shareable_markdown = module.render_markdown(shareable_payload)
        finally:
            module.build_doctor = original_doctor
            module.build_dispatch_plan = original_dispatch

        self.assertFalse(payload["ready"])
        self.assertFalse(payload["safe_to_share"])
        self.assertFalse(payload["shareable"])
        self.assertFalse(payload["contains_secret_values"])
        self.assertTrue(payload["contains_machine_paths"])
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", json.dumps(payload))
        blocker_groups = {
            group["name"]: group["blockers"]
            for group in payload["blocker_groups"]
        }
        self.assertIn("GitHub Deployment Secrets", blocker_groups)
        self.assertIn("Cloudflare Account And Resources", blocker_groups)
        self.assertIn("Final Deployment Gate", blocker_groups)
        self.assertIn(
            "GitHub deployment secret CLOUDFLARE_API_TOKEN is missing from both repository and production environment secrets.",
            blocker_groups["GitHub Deployment Secrets"],
        )
        self.assertIn(
            "Launch doctor is not ready; resolve blockers before dispatching production deployment.",
            blocker_groups["Final Deployment Gate"],
        )
        self.assertIn(
            "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
            blocker_groups["Cloudflare Account And Resources"],
        )
        groups = {group["name"]: group["actions"] for group in payload["action_groups"]}
        self.assertIn("GitHub Deployment Secrets", groups)
        self.assertIn("Cloudflare Account And Resources", groups)
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
            groups["GitHub Deployment Secrets"],
        )
        self.assertNotIn(
            "gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe --env production",
            groups["GitHub Deployment Secrets"],
        )
        self.assertIn(
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
            groups["Cloudflare Account And Resources"],
        )
        self.assertNotIn("npm run cf:resources:plan", groups["Cloudflare Account And Resources"])
        self.assertIn("npm run cf:resources:apply", groups["Cloudflare Account And Resources"])
        self.assertNotIn("Worker Secrets And Clerk", groups)
        self.assertNotIn("DNS And Domain Activation", groups)
        self.assertNotIn("Final Deployment And Smoke", groups)
        self.assertIn("# Workdoe Launch Handoff", markdown)
        self.assertIn("Status: Blocked before production dispatch", markdown)
        self.assertIn("This private local handoff", markdown)
        self.assertIn("## Required Next Actions", markdown)
        self.assertIn("### GitHub Deployment Secrets", markdown)
        self.assertIn("### Cloudflare Account And Resources", markdown)
        self.assertIn("### Final Deployment Gate", markdown)
        self.assertIn(
            "GitHub deployment secret CLOUDFLARE_API_TOKEN is missing from both repository and production environment secrets.",
            markdown,
        )
        self.assertIn("gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production", markdown)
        self.assertNotIn("gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe --env production", markdown)
        self.assertNotIn("npm run cf:resources:plan", markdown)
        self.assertNotIn("npm run cf:secrets:evidence", markdown)
        self.assertNotIn("npm run launch:dns", markdown)
        self.assertIn("npm run github:deploy:plan", markdown)
        self.assertNotIn("npm run launch:smoke:strict", markdown)
        self.assertIn("cloudflare-secret-list.local.json", markdown)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", markdown)
        self.assertIn("CLOUDFLARE_API_TOKEN=<redacted>", markdown)
        self.assertTrue(shareable_payload["safe_to_share"])
        self.assertTrue(shareable_payload["shareable"])
        self.assertFalse(shareable_payload["contains_secret_values"])
        self.assertFalse(shareable_payload["contains_machine_paths"])
        self.assertIn(module.LOCAL_WORKSPACE_PLACEHOLDER, json.dumps(shareable_payload))
        self.assertNotIn(str(ROOT), str(shareable_payload))
        self.assertNotIn(str(ROOT), shareable_markdown)
        self.assertIn("This handoff is generated from local and live release gates", shareable_markdown)

    def test_workdoe_launch_handoff_reuses_valid_clerk_proof_confirmations(self):
        module = load_workdoe_launch_handoff_script()
        original_doctor = module.build_doctor
        original_dispatch = module.build_dispatch_plan
        original_proof_error = module.clerk_proxy_proof_error
        captured_confirmations = {}
        try:
            module.build_doctor = lambda *args, **kwargs: {
                "ready": True,
                "blockers": [],
                "next_actions": [],
                "phases": [],
            }

            def fake_dispatch(*args, **kwargs):
                captured_confirmations.update(
                    {
                        key: kwargs[key]
                        for key in (
                            "clerk_proxy_confirmed",
                            "restricted_signup_confirmed",
                            "email_code_only_confirmed",
                            "legal_consent_confirmed",
                        )
                    }
                )
                return {
                    "ready_to_dispatch": True,
                    "repository": "Yami566/workdoe",
                    "workflow": "cloudflare-deploy.yml",
                    "ref": "main",
                    "command_text": "gh workflow run cloudflare-deploy.yml",
                    "git": {
                        "branch": "main",
                        "clean": True,
                        "synced_with_upstream": True,
                    },
                    "blockers": [],
                }

            module.build_dispatch_plan = fake_dispatch
            module.clerk_proxy_proof_error = lambda path: ""
            payload = module.build_handoff_payload(
                ROOT,
                clerk_proxy_proof_json=ROOT / "clerk-proxy-proof.local.json",
            )
        finally:
            module.build_doctor = original_doctor
            module.build_dispatch_plan = original_dispatch
            module.clerk_proxy_proof_error = original_proof_error

        self.assertEqual(
            captured_confirmations,
            {
                "clerk_proxy_confirmed": True,
                "restricted_signup_confirmed": True,
                "email_code_only_confirmed": True,
                "legal_consent_confirmed": True,
            },
        )
        self.assertEqual(
            payload["dispatch"]["operator_confirmations"],
            captured_confirmations,
        )

    def test_workdoe_launch_handoff_write_uses_private_or_shareable_default_output(self):
        module = load_workdoe_launch_handoff_script()
        original_doctor = module.build_doctor
        original_dispatch = module.build_dispatch_plan
        original_default_output = module.DEFAULT_OUTPUT
        original_shareable_output = module.DEFAULT_SHAREABLE_OUTPUT
        original_argv = sys.argv
        try:
            doctor_payload = {
                "ready": False,
                "blockers": [
                    f"Clerk proxy proof JSON is missing or invalid: {ROOT}\\clerk-proxy-proof.local.json"
                ],
                "next_actions": [],
                "phases": [
                    {
                        "name": "clerk-proxy",
                        "status": "pending",
                        "summary": "Clerk proxy proof is still pending.",
                        "next_command": "npm run cf:clerk:proof:confirm",
                    },
                ],
            }
            dispatch_payload = {
                "ready_to_dispatch": False,
                "repository": "Yami566/workdoe",
                "workflow": "cloudflare-deploy.yml",
                "ref": "main",
                "command_text": "gh workflow run cloudflare-deploy.yml --repo Yami566/workdoe",
                "git": {
                    "branch": "main",
                    "clean": True,
                    "synced_with_upstream": True,
                },
                "blockers": [],
            }
            module.build_doctor = lambda *args, **kwargs: doctor_payload
            module.build_dispatch_plan = lambda *args, **kwargs: dispatch_payload
            with tempfile.TemporaryDirectory() as tempdir:
                temp_path = Path(tempdir)
                private_output = temp_path / "workdoe-launch-handoff.local.md"
                shareable_output = temp_path / "workdoe-launch-handoff.shareable.local.md"
                module.DEFAULT_OUTPUT = private_output
                module.DEFAULT_SHAREABLE_OUTPUT = shareable_output

                sys.argv = ["workdoe_launch_handoff.py", "--write"]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(module.main(), 0)

                self.assertTrue(private_output.exists())
                self.assertFalse(shareable_output.exists())
                self.assertIn(str(ROOT), private_output.read_text(encoding="utf-8"))

                sys.argv = ["workdoe_launch_handoff.py", "--shareable", "--write"]
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(module.main(), 0)

                self.assertTrue(shareable_output.exists())
                shareable_markdown = shareable_output.read_text(encoding="utf-8")
                self.assertIn(module.LOCAL_WORKSPACE_PLACEHOLDER, shareable_markdown)
                self.assertNotIn(str(ROOT), shareable_markdown)
        finally:
            module.build_doctor = original_doctor
            module.build_dispatch_plan = original_dispatch
            module.DEFAULT_OUTPUT = original_default_output
            module.DEFAULT_SHAREABLE_OUTPUT = original_shareable_output
            sys.argv = original_argv

    def test_workdoe_dns_diagnostic_accepts_cloudflare_delegation_and_routes(self):
        module = load_workdoe_dns_diagnostic_script()
        original_nslookup = module.run_nslookup
        original_resolve = module.resolve_addresses
        original_routes = module.wrangler_custom_domains
        try:
            module.run_nslookup = lambda domain, resolver="1.1.1.1": (
                True,
                ("workdoe.com nameserver = ada.ns.cloudflare.com\n"
                "workdoe.com nameserver = bob.ns.cloudflare.com\n"),
            )
            module.resolve_addresses = lambda hostname: (
                True,
                ["203.0.113.10"] if hostname == "workdoe.com" else ["203.0.113.11"],
                "",
            )
            module.wrangler_custom_domains = lambda path=module.WRANGLER_CONFIG_PATH: (
                True,
                ["workdoe.com", "www.workdoe.com"],
                "",
            )
            payload = module.build_dns_diagnostic()
        finally:
            module.run_nslookup = original_nslookup
            module.resolve_addresses = original_resolve
            module.wrangler_custom_domains = original_routes

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["blockers"], [])
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertEqual(checks["nameserver-delegation"]["status"], "ready")
        self.assertEqual(checks["apex-resolution"]["status"], "ready")
        self.assertEqual(checks["www-resolution"]["status"], "ready")
        self.assertEqual(checks["wrangler-custom-domains"]["status"], "ready")
        self.assertIn("npm run launch:smoke:strict", payload["next_actions"])

    def test_workdoe_dns_diagnostic_reports_pending_dns(self):
        module = load_workdoe_dns_diagnostic_script()
        original_nslookup = module.run_nslookup
        original_resolve = module.resolve_addresses
        original_routes = module.wrangler_custom_domains
        try:
            module.run_nslookup = lambda domain, resolver="1.1.1.1": (
                True,
                "workdoe.com nameserver = ns1.example.net\n",
            )
            module.resolve_addresses = lambda hostname: (
                False,
                [],
                "mock resolution failure",
            )
            module.wrangler_custom_domains = lambda path=module.WRANGLER_CONFIG_PATH: (
                False,
                ["workdoe.com"],
                "",
            )
            payload = module.build_dns_diagnostic()
        finally:
            module.run_nslookup = original_nslookup
            module.resolve_addresses = original_resolve
            module.wrangler_custom_domains = original_routes

        self.assertFalse(payload["ready"])
        self.assertIn(
            "workdoe.com nameservers are not fully Cloudflare: ns1.example.net.",
            payload["blockers"],
        )
        self.assertIn("workdoe.com does not resolve: mock resolution failure", payload["blockers"])
        self.assertIn(
            "www.workdoe.com does not resolve: mock resolution failure",
            payload["blockers"],
        )
        self.assertIn(
            "Confirm the exact Cloudflare-assigned nameservers",
            module.render_text(payload),
        )

    def test_workdoe_production_smoke_accepts_ready_public_contract(self):
        module = load_workdoe_production_smoke_script()
        asset_release_token = load_release_script().static_asset_release_token(ROOT)
        original_dns_lookup = module.dns_lookup
        original_fetch_url = module.fetch_url
        try:
            module.dns_lookup = lambda domain="workdoe.com": (
                True,
                ["203.0.113.10"],
                "",
            )

            def fake_fetch(
                url,
                *,
                method="GET",
                timeout=module.DEFAULT_TIMEOUT,
                body_limit=20000,
                follow_redirects=True,
            ):
                headers = {}
                body = ""
                status_code = 200
                if url.startswith("http://"):
                    status_code = 308
                    headers = {"Location": url.replace("http://", "https://", 1)}
                elif url.endswith("/login"):
                    body = '<div data-clerk-publishable-key="pk_live_workdoe"></div>'
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                elif "/create-account?__clerk_status=sign_up" in url:
                    body = (
                        '<main data-clerk-entry="sign-up"></main>'
                        '<script data-clerk-publishable-key="pk_live_workdoe"></script>'
                    )
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                elif url.endswith("/start"):
                    headers = {
                        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "Referrer-Policy": "strict-origin-when-cross-origin",
                        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
                    }
                elif "/styles.css?v=" in url:
                    headers = {
                        "Content-Type": "text/css; charset=utf-8",
                        "Cache-Control": "public, max-age=31556952, immutable",
                        "X-Content-Type-Options": "nosniff",
                    }
                elif url.endswith("/health"):
                    body = json.dumps(
                        {
                            "ok": True,
                            "service": "workdoe-cloudflare-worker",
                            "bindings": {
                                "d1": True,
                                "email_sender": True,
                                "email_queue": True,
                                "media_queue": True,
                                "r2_media": True,
                                "write_rate_limiter": True,
                            },
                        }
                    )
                    headers = {"Content-Type": "application/json; charset=utf-8"}
                elif url.endswith("/api/jobs/open?limit=3"):
                    body = json.dumps(
                        {
                            "count": 1,
                            "jobs": [{"id": 1, "title": "Window cleaning"}],
                            "filters": {},
                            "location_privacy": "Approximate city or ZIP-level pins only.",
                        }
                    )
                    headers = {"Content-Type": "application/json; charset=utf-8"}
                elif url.endswith("/safety"):
                    body = "<h1>Safety</h1><p>Share only what the job needs.</p>"
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                elif url.endswith("/privacy"):
                    body = "<h1>Privacy Policy</h1>"
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                elif url.endswith("/terms"):
                    body = "<h1>Terms of Use</h1>"
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                elif url.endswith("/workdoe-share.png"):
                    headers = {"Content-Type": "image/png"}
                elif url.rstrip("/") == "https://workdoe.com":
                    body = (
                        f'<link rel="stylesheet" href="/styles.css?v={asset_release_token}">'
                        '<meta property="og:title" content="Workdoe - a local Work Exchange">'
                        '<meta property="og:image" content="https://workdoe.com/workdoe-share.png">'
                        '<meta property="og:image:width" content="1200">'
                        '<meta property="og:image:height" content="630">'
                        '<meta name="twitter:card" content="summary_large_image">'
                    )
                    headers = {"Content-Type": "text/html; charset=utf-8"}
                elif url.endswith(module.CLERK_ASSET_PATH):
                    body = "window.Clerk = window.Clerk || {};"
                    headers = {"Content-Type": "application/javascript; charset=utf-8"}
                return module.FetchResult(
                    ok=True,
                    status_code=status_code,
                    headers=headers,
                    body=body,
                    elapsed_ms=12,
                )

            module.fetch_url = fake_fetch
            payload = module.build_smoke_payload()
        finally:
            module.dns_lookup = original_dns_lookup
            module.fetch_url = original_fetch_url

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["failures"], [])
        checks = {check["name"]: check for check in payload["checks"]}
        self.assertEqual(checks["dns"]["status"], "ready")
        self.assertEqual(checks["http-to-https"]["status"], "ready")
        self.assertEqual(checks["https-entry"]["status"], "ready")
        self.assertEqual(checks["health-json"]["status"], "ready")
        self.assertEqual(checks["public-jobs-api"]["status"], "ready")
        self.assertEqual(checks["entry-security-headers"]["status"], "ready")
        self.assertEqual(checks["static-asset-cache"]["status"], "ready")
        self.assertEqual(checks["public-trust-pages"]["status"], "ready")
        self.assertEqual(checks["social-share-card"]["status"], "ready")
        self.assertEqual(checks["public-discovery-files"]["status"], "ready")
        self.assertEqual(checks["clerk-production-key"]["status"], "ready")
        self.assertEqual(checks["clerk-invitation-entry"]["status"], "ready")
        self.assertEqual(checks["clerk-same-domain-proxy"]["status"], "ready")

    def test_workdoe_production_smoke_rejects_unversioned_or_revalidated_stylesheet(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            def fake_fetch(url, **kwargs):
                if url.rstrip("/") == "https://workdoe.com":
                    return module.FetchResult(
                        ok=True,
                        status_code=200,
                        headers={"Content-Type": "text/html; charset=utf-8"},
                        body='<link rel="stylesheet" href="/styles.css?v=release-1">',
                        elapsed_ms=4,
                    )
                return module.FetchResult(
                    ok=True,
                    status_code=200,
                    headers={
                        "Content-Type": "text/css; charset=utf-8",
                        "Cache-Control": "public, max-age=0, must-revalidate",
                        "X-Content-Type-Options": "nosniff",
                    },
                    elapsed_ms=4,
                )

            module.fetch_url = fake_fetch
            check = module.static_asset_cache_check(
                "https://workdoe.com",
                module.DEFAULT_TIMEOUT,
            )
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "failed")
        self.assertIn("max-age=31556952", check.summary)
        self.assertIn("immutable", check.summary)

    def test_workdoe_production_smoke_rejects_static_asset_without_https_redirect(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            def fake_fetch(url, **kwargs):
                if url.endswith("/styles.css"):
                    return module.FetchResult(
                        ok=True,
                        status_code=200,
                        headers={"Content-Type": "text/css"},
                        elapsed_ms=4,
                    )
                return module.FetchResult(
                    ok=False,
                    status_code=308,
                    headers={"Location": url.replace("http://", "https://", 1)},
                    elapsed_ms=4,
                )

            module.fetch_url = fake_fetch
            check = module.https_redirect_check("workdoe.com", module.DEFAULT_TIMEOUT)
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "failed")
        self.assertIn("workdoe.com/styles.css returned HTTP 200", check.summary)

    def test_workdoe_production_smoke_rejects_missing_public_trust_page(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            def fake_fetch(url, **kwargs):
                if url.endswith("/privacy"):
                    return module.FetchResult(ok=False, status_code=404, elapsed_ms=4)
                markers = {
                    "/safety": "Share only what the job needs.",
                    "/terms": "Terms of Use",
                }
                body = next((value for path, value in markers.items() if url.endswith(path)), "")
                return module.FetchResult(
                    ok=True,
                    status_code=200,
                    headers={"Content-Type": "text/html; charset=utf-8"},
                    body=body,
                    elapsed_ms=4,
                )

            module.fetch_url = fake_fetch
            check = module.public_trust_pages_check(
                "https://workdoe.com",
                module.DEFAULT_TIMEOUT,
            )
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "failed")
        self.assertIn("/privacy returned HTTP 404", check.summary)

    def test_workdoe_production_smoke_warns_on_missing_discovery_files(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            module.fetch_url = lambda *args, **kwargs: module.FetchResult(
                ok=False,
                status_code=404,
                elapsed_ms=3,
            )
            check = module.discovery_files_check(
                "https://workdoe.com",
                module.DEFAULT_TIMEOUT,
            )
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "warning")
        self.assertFalse(check.required)
        self.assertIn("/.well-known/security.txt", check.summary)

    def test_workdoe_production_smoke_rejects_clerk_development_key(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            module.fetch_url = lambda *args, **kwargs: module.FetchResult(
                ok=True,
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body='<div data-clerk-publishable-key="pk_test_workdoe"></div>',
                elapsed_ms=7,
            )
            check = module.clerk_production_key_check(
                "https://workdoe.com",
                module.DEFAULT_TIMEOUT,
            )
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "failed")
        self.assertIn("not using a Clerk production instance", check.summary)

    def test_workdoe_production_smoke_rejects_missing_invitation_route(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            module.fetch_url = lambda *args, **kwargs: module.FetchResult(
                ok=False,
                status_code=404,
                headers={"Content-Type": "application/json; charset=utf-8"},
                body='{"ok": false, "error": "Not found."}',
                elapsed_ms=7,
            )
            check = module.clerk_invitation_entry_check(
                "https://workdoe.com",
                module.DEFAULT_TIMEOUT,
            )
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "failed")
        self.assertIn("HTTP 404", check.summary)

    def test_workdoe_production_smoke_rejects_invitation_development_key(self):
        module = load_workdoe_production_smoke_script()
        original_fetch_url = module.fetch_url
        try:
            module.fetch_url = lambda *args, **kwargs: module.FetchResult(
                ok=True,
                status_code=200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                body=(
                    '<main data-clerk-entry="sign-up"></main>'
                    '<script data-clerk-publishable-key="pk_test_workdoe"></script>'
                ),
                elapsed_ms=7,
            )
            check = module.clerk_invitation_entry_check(
                "https://workdoe.com",
                module.DEFAULT_TIMEOUT,
            )
        finally:
            module.fetch_url = original_fetch_url

        self.assertEqual(check.status, "failed")
        self.assertIn("not using a Clerk production instance", check.summary)

    def test_workdoe_production_smoke_reports_dns_and_header_failures(self):
        module = load_workdoe_production_smoke_script()
        original_dns_lookup = module.dns_lookup
        original_fetch_url = module.fetch_url
        try:
            module.dns_lookup = lambda domain="workdoe.com": (
                False,
                [],
                "mock dns failure",
            )
            module.fetch_url = lambda *args, **kwargs: module.FetchResult(
                ok=True,
                status_code=200,
                headers={},
                body=json.dumps({"ok": True, "service": "workdoe-cloudflare-worker"}),
                elapsed_ms=7,
            )
            payload = module.build_smoke_payload()
        finally:
            module.dns_lookup = original_dns_lookup
            module.fetch_url = original_fetch_url

        self.assertFalse(payload["ready"])
        self.assertIn("workdoe.com does not resolve: mock dns failure", payload["failures"])
        self.assertIn(
            "Entry shell is missing required security headers:",
            "\n".join(payload["failures"]),
        )
        rendered = module.render_text(payload)
        self.assertIn("Workdoe production smoke", rendered)
        self.assertIn("Ready: False", rendered)

    def test_workdoe_production_smoke_retries_transient_release_failures(self):
        module = load_workdoe_production_smoke_script()
        original_build = module.build_smoke_payload
        original_sleep = module.time.sleep
        calls = []
        try:
            def fake_build(**kwargs):
                calls.append(kwargs)
                return {
                    "service": "workdoe",
                    "domain": "workdoe.com",
                    "base_url": "https://workdoe.com",
                    "ready": len(calls) >= 2,
                    "checks": [],
                    "failures": [] if len(calls) >= 2 else ["Clerk proxy is propagating."],
                }

            module.build_smoke_payload = fake_build
            module.time.sleep = lambda seconds: calls.append({"sleep": seconds})
            payload = module.build_smoke_payload_with_retries(
                attempts=3,
                retry_delay=5,
            )
        finally:
            module.build_smoke_payload = original_build
            module.time.sleep = original_sleep

        self.assertTrue(payload["ready"])
        self.assertEqual(payload["attempt"], 2)
        self.assertEqual(payload["attempts"], 3)
        self.assertEqual(calls[1], {"sleep": 5})

    def test_workdoe_launch_doctor_combines_release_blockers(self):
        module = load_workdoe_launch_doctor_script()
        github_status = load_github_release_status_script().GithubReleaseStatus(
            repository="Yami566/workdoe",
            environment="production",
            live=False,
            ready=False,
            environment_ready=True,
            secrets_ready=False,
            blockers=[
                "GitHub deployment secret CLOUDFLARE_API_TOKEN is missing from both repository and production environment secrets."
            ],
            warnings=[],
        )
        original_head_ok = module.http_head_ok
        original_cloudflare = module.build_launch_status
        original_github_live = module.build_github_live_status
        original_wrangler_auth = module.wrangler_auth_status
        original_dns_diagnostic = module.build_dns_diagnostic
        try:
            module.http_head_ok = lambda url: (True, "HTTP 200")
            module.build_launch_status = lambda repo_root=ROOT: {
                "ready_to_deploy": False,
                "current_phase": "cloudflare-resources",
                "next_command": "python scripts\\cloudflare_resource_bootstrap.py --json --no-secret-probe",
                "blockers": ["D1 database_id must be replaced with the real Cloudflare UUID."],
                "warnings": ["Confirm admin@workdoe.com is a real monitored inbox before launch."],
            }
            module.wrangler_auth_status = lambda repo_root=ROOT: (
                False,
                "Wrangler is not authenticated. Run `.\\node_modules\\.bin\\wrangler.cmd login`.",
            )
            module.build_dns_diagnostic = lambda: {
                "ready": False,
                "checks": [
                    {
                        "name": "nameserver-delegation",
                        "status": "ready",
                        "summary": "workdoe.com is delegated to Cloudflare nameservers: ada.ns.cloudflare.com, bob.ns.cloudflare.com.",
                        "values": ["ada.ns.cloudflare.com", "bob.ns.cloudflare.com"],
                    },
                    {
                        "name": "apex-resolution",
                        "status": "pending",
                        "summary": "workdoe.com does not resolve: mock dns failure",
                        "values": [],
                        "next_action": "Deploy the Worker custom domain route and wait for DNS/certificate activation.",
                    },
                    {
                        "name": "www-resolution",
                        "status": "pending",
                        "summary": "www.workdoe.com does not resolve: mock dns failure",
                        "values": [],
                        "next_action": "Deploy the Worker custom domain route for www.workdoe.com or add the intended redirect record.",
                    },
                ],
                "blockers": [
                    "workdoe.com does not resolve: mock dns failure",
                    "www.workdoe.com does not resolve: mock dns failure",
                ],
                "next_actions": [
                    "Deploy the Worker custom domain route and wait for DNS/certificate activation.",
                    "Deploy the Worker custom domain route for www.workdoe.com or add the intended redirect record.",
                ],
            }
            payload = module.build_doctor(ROOT)
            module.build_github_live_status = lambda: github_status
            live_payload = module.build_doctor(ROOT, live=True)
        finally:
            module.http_head_ok = original_head_ok
            module.build_launch_status = original_cloudflare
            module.build_github_live_status = original_github_live
            module.wrangler_auth_status = original_wrangler_auth
            module.build_dns_diagnostic = original_dns_diagnostic

        self.assertFalse(payload["ready"])
        self.assertEqual(payload["phases"][0]["name"], "local-prototype")
        self.assertIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            payload["blockers"],
        )
        self.assertNotIn(
            "GitHub deployment secret CLOUDFLARE_API_TOKEN is missing from both repository and production environment secrets.",
            payload["blockers"],
        )
        self.assertEqual(payload["phases"][1]["status"], "not-checked")
        self.assertEqual(payload["phases"][2]["name"], "wrangler-auth")
        self.assertEqual(payload["phases"][2]["status"], "not-checked")
        self.assertEqual(payload["phases"][-1]["status"], "not-checked")
        self.assertIn("npm run launch:doctor:live", payload["next_actions"])
        self.assertIn("npm run cf:resources:plan", payload["next_actions"])
        self.assertIn(
            "GitHub deployment secret CLOUDFLARE_API_TOKEN is missing from both repository and production environment secrets.",
            live_payload["blockers"],
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
            live_payload["next_actions"],
        )
        self.assertIn(
            ".\\node_modules\\.bin\\wrangler.cmd login",
            live_payload["next_actions"],
        )
        self.assertIn(
            "Wrangler is not authenticated for live Cloudflare operations.",
            live_payload["blockers"],
        )
        live_phases = {phase["name"]: phase for phase in live_payload["phases"]}
        self.assertEqual(live_phases["wrangler-auth"]["status"], "pending")
        self.assertIn(
            "DNS: workdoe.com does not resolve: mock dns failure",
            live_payload["blockers"],
        )
        self.assertIn(
            "apex-resolution: workdoe.com does not resolve: mock dns failure",
            live_phases["dns"]["summary"],
        )
        self.assertFalse(live_payload["dns"]["ready"])
        self.assertIn(
            "Deploy the Worker custom domain route and wait for DNS/certificate activation.",
            live_payload["next_actions"],
        )
        self.assertIn("confirm workdoe.com DNS in Cloudflare", live_payload["next_actions"])

    def test_workdoe_launch_doctor_detects_ambient_encrypted_wrangler_login(self):
        module = load_workdoe_launch_doctor_script()
        original_run = module.subprocess.run
        calls = []

        def fake_run(command, **kwargs):
            calls.append({"command": command, "env": kwargs.get("env")})
            if len(calls) == 1:
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="You are not authenticated. Please run wrangler login.",
                )
            return SimpleNamespace(
                returncode=0,
                stdout="You are logged in with an OAuth Token.",
                stderr="",
            )

        try:
            module.subprocess.run = fake_run
            ready, summary = module.wrangler_auth_status(ROOT)
        finally:
            module.subprocess.run = original_run

        self.assertTrue(ready)
        self.assertEqual(len(calls), 2)
        self.assertIn("XDG_CONFIG_HOME", calls[0]["env"])
        self.assertIsNone(calls[1]["env"])
        self.assertIn("ambient encrypted OAuth profile", summary)
        self.assertIn("CLOUDFLARE_API_TOKEN", summary)

    def test_workdoe_launch_doctor_reads_only_secret_binding_names(self):
        module = load_workdoe_launch_doctor_script()
        original_run = module.subprocess.run
        calls = []

        def fake_run(command, **kwargs):
            calls.append({"command": command, "env": kwargs.get("env")})
            if len(calls) == 1:
                return SimpleNamespace(
                    returncode=1,
                    stdout="",
                    stderr="You are not authenticated. Please run wrangler login.",
                )
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    [
                        {"name": "CLERK_SECRET_KEY", "type": "secret_text"},
                        {"name": "WORKDOE_SECRET_KEY", "type": "secret_text"},
                    ]
                ),
                stderr="",
            )

        try:
            module.subprocess.run = fake_run
            ready, names, summary = module.wrangler_secret_names_status(ROOT)
        finally:
            module.subprocess.run = original_run

        self.assertTrue(ready)
        self.assertEqual(names, {"CLERK_SECRET_KEY", "WORKDOE_SECRET_KEY"})
        self.assertIn("2 production secret binding name", summary)
        self.assertEqual(calls[1]["command"][-4:], ["secret", "list", "--config", "wrangler.jsonc"])
        self.assertIsNone(calls[1]["env"])

    def test_workdoe_launch_doctor_prioritizes_cloudflare_token_phase(self):
        module = load_workdoe_launch_doctor_script()
        original_head_ok = module.http_head_ok
        original_cloudflare = module.build_launch_status
        try:
            module.http_head_ok = lambda url: (True, "HTTP 200")
            module.build_launch_status = lambda repo_root=ROOT: {
                "ready_to_deploy": False,
                "current_phase": "cloudflare-token",
                "next_command": "set CLOUDFLARE_API_TOKEN in this shell without committing it",
                "blockers": [
                    "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
                    "Cloudflare is missing required secret bindings: CLERK_SECRET_KEY",
                    "Wrangler D1 database_id is still the placeholder UUID.",
                ],
                "warnings": [],
            }
            payload = module.build_doctor(ROOT)
        finally:
            module.http_head_ok = original_head_ok
            module.build_launch_status = original_cloudflare

        self.assertFalse(payload["ready"])
        self.assertIn(
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
            payload["next_actions"],
        )
        self.assertNotIn("npm run cf:resources:apply", payload["next_actions"])
        self.assertFalse(
            any("wrangler.cmd secret put" in action for action in payload["next_actions"])
        )

    def test_workdoe_launch_doctor_uses_ready_github_release_credentials(self):
        module = load_workdoe_launch_doctor_script()
        github_status = load_github_release_status_script().GithubReleaseStatus(
            repository="Yami566/workdoe",
            environment="production",
            live=True,
            ready=True,
            environment_ready=True,
            secrets_ready=True,
            blockers=[],
            warnings=[],
        )
        original_head_ok = module.http_head_ok
        original_cloudflare = module.build_launch_status
        original_github_live = module.build_github_live_status
        original_wrangler_auth = module.wrangler_auth_status
        original_wrangler_secrets = module.wrangler_secret_names_status
        original_dns_diagnostic = module.build_dns_diagnostic
        try:
            module.http_head_ok = lambda url: (True, "HTTP 200")
            module.build_launch_status = lambda repo_root=ROOT: {
                "ready_to_deploy": False,
                "current_phase": "cloudflare-token",
                "next_command": "set CLOUDFLARE_API_TOKEN in this shell without committing it",
                "blockers": [
                    "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
                    "Cloudflare is missing required secret bindings: CLERK_WEBHOOK_SECRET",
                    "Clerk proxy proof JSON is missing or invalid: clerk-proxy-proof.local.json",
                ],
                "warnings": [],
            }
            module.build_github_live_status = lambda: github_status
            module.wrangler_auth_status = lambda repo_root=ROOT: (
                True,
                "Wrangler is authenticated through the ambient encrypted OAuth profile.",
            )
            module.wrangler_secret_names_status = lambda repo_root=ROOT: (
                False,
                set(),
                "Noninteractive secret listing requires CLOUDFLARE_API_TOKEN.",
            )
            module.build_dns_diagnostic = lambda: {
                "ready": True,
                "checks": [],
                "blockers": [],
                "next_actions": [],
            }
            payload = module.build_doctor(ROOT, live=True)
        finally:
            module.http_head_ok = original_head_ok
            module.build_launch_status = original_cloudflare
            module.build_github_live_status = original_github_live
            module.wrangler_auth_status = original_wrangler_auth
            module.wrangler_secret_names_status = original_wrangler_secrets
            module.build_dns_diagnostic = original_dns_diagnostic

        self.assertFalse(payload["ready"])
        self.assertFalse(
            any("CLOUDFLARE_API_TOKEN is not set" in blocker for blocker in payload["blockers"])
        )
        self.assertNotIn(
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
            payload["next_actions"],
        )
        self.assertFalse(payload["secret_bindings"]["checked"])
        self.assertEqual(payload["secret_bindings"]["source"], "sanitized-evidence")
        self.assertEqual(payload["secret_bindings"]["present_count"], 6)
        self.assertEqual(payload["secret_bindings"]["missing"], ["CLERK_WEBHOOK_SECRET"])
        self.assertIn(
            ".\\node_modules\\.bin\\wrangler.cmd secret put CLERK_WEBHOOK_SECRET --config cloudflare\\wrangler.jsonc",
            payload["next_actions"],
        )
        self.assertFalse(
            any(
                "wrangler.cmd secret put CLERK_SECRET_KEY" in action
                for action in payload["next_actions"]
            )
        )
        self.assertIn("npm run cf:clerk:proof:confirm", payload["next_actions"])
        cloudflare_phase = next(
            phase for phase in payload["phases"] if phase["name"] == "cloudflare-release"
        )
        self.assertEqual(cloudflare_phase["status"], "pending")
        self.assertIn("GitHub production automation credentials are ready", cloudflare_phase["summary"])
        self.assertIn("6/7 required present", cloudflare_phase["summary"])
        self.assertIn("CLERK_WEBHOOK_SECRET", cloudflare_phase["next_command"])
        self.assertTrue(
            any("verified GitHub production environment" in warning for warning in payload["warnings"])
        )

    def test_cloudflare_wrangler_resolver_accepts_env_or_local_binary(self):
        module = load_wrangler_helper_script()
        original_env = os.environ.get(module.WRANGLER_ENV_VAR)
        try:
            os.environ[module.WRANGLER_ENV_VAR] = "C:\\Tools\\wrangler.cmd"
            self.assertEqual(module.resolved_wrangler_bin(ROOT), "C:\\Tools\\wrangler.cmd")
            self.assertEqual(
                module.wrangler_command(["deploy"], ROOT),
                ["C:\\Tools\\wrangler.cmd", "deploy"],
            )
        finally:
            if original_env is None:
                os.environ.pop(module.WRANGLER_ENV_VAR, None)
            else:
                os.environ[module.WRANGLER_ENV_VAR] = original_env

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            local_bin = repo_root / "node_modules" / ".bin" / "wrangler.cmd"
            local_bin.parent.mkdir(parents=True)
            local_bin.write_text("@echo off\n", encoding="utf-8")
            self.assertEqual(module.resolved_wrangler_bin(repo_root), str(local_bin))
            self.assertTrue(module.wrangler_available(repo_root))
            env = module.wrangler_env(repo_root)
            self.assertEqual(env["XDG_CONFIG_HOME"], str(repo_root / ".wrangler-config"))
            self.assertFalse(module.cloudflare_api_token_present({}))
            self.assertTrue(module.cloudflare_api_token_present({"CLOUDFLARE_API_TOKEN": "token"}))
            self.assertIn(
                "CLOUDFLARE_API_TOKEN is required",
                module.cloudflare_api_token_error("run Workdoe launch automation"),
            )
            self.assertIn(
                "GitHub production environment secret",
                module.cloudflare_api_token_error("run Workdoe launch automation"),
            )

    def test_cloudflare_launch_status_summarizes_next_safe_action(self):
        module = load_launch_status_script()
        original_wrangler_available = module.wrangler_available
        original_resolved_wrangler_bin = module.resolved_wrangler_bin
        original_token_present = module.cloudflare_api_token_present
        try:
            module.wrangler_available = lambda repo_root=ROOT: True
            module.resolved_wrangler_bin = lambda repo_root=ROOT: "wrangler"
            module.cloudflare_api_token_present = lambda: False
            status = module.build_launch_status(
                ROOT,
                secret_list_json=None,
                clerk_proxy_proof_json=None,
            )
        finally:
            module.wrangler_available = original_wrangler_available
            module.resolved_wrangler_bin = original_resolved_wrangler_bin
            module.cloudflare_api_token_present = original_token_present
        self.assertEqual(status["service"], "workdoe")
        self.assertEqual(status["domain"], "workdoe.com")
        self.assertTrue(status["safe_by_default"])
        self.assertFalse(status["executes_commands"])
        self.assertFalse(status["ready_to_deploy"])
        self.assertEqual(status["current_phase"], "cloudflare-token")
        self.assertEqual(
            status["next_command"],
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
        )
        phases = {phase["name"]: phase for phase in status["phases"]}
        self.assertEqual(phases["local-artifacts"]["status"], "ready")
        self.assertEqual(phases["local-tooling"]["status"], "ready")
        self.assertEqual(phases["cloudflare-token"]["status"], "pending")
        self.assertEqual(phases["cloudflare-resources"]["status"], "ready")
        self.assertEqual(phases["identity-and-secrets"]["status"], "blocked")
        self.assertEqual(phases["clerk-domain-proof"]["status"], "pending")
        self.assertEqual(phases["release-evidence"]["status"], "pending")
        self.assertNotIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            status["blockers"],
        )
        self.assertIn(
            "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
            status["blockers"],
        )
        self.assertIn(
            "Confirm Cloudflare Images Paid is active and complete one live valid-image plus invalid-image upload test before enabling public uploads.",
            status["warnings"],
        )
        rendered = module.render_text(status)
        self.assertIn("Workdoe Cloudflare launch status", rendered)
        self.assertIn("Current phase: cloudflare-token", rendered)
        self.assertIn("Next command: set CLOUDFLARE_API_TOKEN in this shell without committing it", rendered)

    def test_cloudflare_launch_status_reports_missing_wrangler(self):
        module = load_launch_status_script()
        original_wrangler_available = module.wrangler_available
        original_resolved_wrangler_bin = module.resolved_wrangler_bin
        original_token_present = module.cloudflare_api_token_present
        try:
            module.wrangler_available = lambda repo_root=ROOT: False
            module.resolved_wrangler_bin = lambda repo_root=ROOT: ""
            module.cloudflare_api_token_present = lambda: False
            status = module.build_launch_status(ROOT)
        finally:
            module.wrangler_available = original_wrangler_available
            module.resolved_wrangler_bin = original_resolved_wrangler_bin
            module.cloudflare_api_token_present = original_token_present
        phases = {phase["name"]: phase for phase in status["phases"]}
        self.assertEqual(status["current_phase"], "local-tooling")
        self.assertEqual(status["next_command"], "npm install")
        self.assertEqual(phases["local-tooling"]["status"], "blocked")
        self.assertIn(
            "Wrangler CLI is not available; install Wrangler, add it to PATH, or set `WORKDOE_WRANGLER_BIN` before live Cloudflare steps.",
            status["blockers"],
        )

    def test_cloudflare_launch_status_accepts_sanitized_evidence(self):
        module = load_launch_status_script()
        readiness = load_readiness_script()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            secret_list_path = tmp_path / "cloudflare-secret-list.local.json"
            secret_list_path.write_text(
                json.dumps(
                    {
                        "source": "wrangler secret list --json",
                        "contains_values": False,
                        "result": [{"name": key} for key in sorted(readiness.REQUIRED_SECRETS)],
                    }
                ),
                encoding="utf-8",
            )
            proxy_proof_path = tmp_path / "clerk-proxy-proof.local.json"
            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            original_wrangler_available = module.wrangler_available
            original_resolved_wrangler_bin = module.resolved_wrangler_bin
            original_token_present = module.cloudflare_api_token_present
            try:
                module.wrangler_available = lambda repo_root=ROOT: True
                module.resolved_wrangler_bin = lambda repo_root=ROOT: "wrangler"
                module.cloudflare_api_token_present = lambda: True
                status = module.build_launch_status(
                    ROOT,
                    secret_list_json=secret_list_path,
                    clerk_proxy_proof_json=proxy_proof_path,
                )
            finally:
                module.wrangler_available = original_wrangler_available
                module.resolved_wrangler_bin = original_resolved_wrangler_bin
                module.cloudflare_api_token_present = original_token_present
        phases = {phase["name"]: phase for phase in status["phases"]}
        self.assertEqual(phases["cloudflare-token"]["status"], "ready")
        self.assertEqual(phases["identity-and-secrets"]["status"], "ready")
        self.assertEqual(phases["clerk-domain-proof"]["status"], "ready")
        self.assertEqual(phases["release-evidence"]["status"], "ready")
        self.assertEqual(status["current_phase"], "deploy")
        self.assertTrue(status["ready_to_deploy"])

    def test_cloudflare_launch_status_keeps_raw_secret_evidence_unready(self):
        module = load_launch_status_script()
        readiness = load_readiness_script()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            raw_secret_list_path = tmp_path / "raw-secret-list.json"
            raw_secret_list_path.write_text(
                json.dumps(
                    {
                        "contains_values": True,
                        "result": [{"name": key} for key in sorted(readiness.REQUIRED_SECRETS)],
                    }
                ),
                encoding="utf-8",
            )
            proxy_proof_path = tmp_path / "clerk-proxy-proof.local.json"
            proxy_proof_path.write_text(
                json.dumps(
                    {
                        "domain": "workdoe.com",
                        "frontend_api_proxy_url": "https://workdoe.com/__clerk",
                        "confirmed": True,
                        "restricted_sign_up_mode": True,
                        "email_code_sign_in": True,
                        "password_sign_in_disabled": True,
                        "custom_sign_up_url": "https://workdoe.com/create-account",
                        "express_legal_consent": True,
                        "terms_url": "https://workdoe.com/terms",
                        "privacy_url": "https://workdoe.com/privacy",
                    }
                ),
                encoding="utf-8",
            )
            original_wrangler_available = module.wrangler_available
            original_resolved_wrangler_bin = module.resolved_wrangler_bin
            original_token_present = module.cloudflare_api_token_present
            try:
                module.wrangler_available = lambda repo_root=ROOT: True
                module.resolved_wrangler_bin = lambda repo_root=ROOT: "wrangler"
                module.cloudflare_api_token_present = lambda: True
                status = module.build_launch_status(
                    ROOT,
                    secret_list_json=raw_secret_list_path,
                    clerk_proxy_proof_json=proxy_proof_path,
                )
            finally:
                module.wrangler_available = original_wrangler_available
                module.resolved_wrangler_bin = original_resolved_wrangler_bin
                module.cloudflare_api_token_present = original_token_present
        phases = {phase["name"]: phase for phase in status["phases"]}
        self.assertIn(phases["identity-and-secrets"]["status"], {"pending", "blocked"})
        self.assertIn(
            "Required Clerk, Turnstile, and Workdoe secret names are not proven yet.",
            phases["identity-and-secrets"]["summary"],
        )

    def test_cloudflare_launch_status_exit_code_is_human_friendly_by_default(self):
        module = load_launch_status_script()
        original_argv = sys.argv
        try:
            sys.argv = ["cloudflare_launch_status.py", "--json"]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(module.main(), 0)
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload["ready_to_deploy"])

            sys.argv = [
                "cloudflare_launch_status.py",
                "--json",
                "--fail-when-not-ready",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(module.main(), 1)
        finally:
            sys.argv = original_argv

    def test_launch_docs_prefer_github_production_environment_secrets(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "production environment secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`",
            readme,
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe --env production",
            readme,
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_ACCOUNT_ID --repo Yami566/workdoe --env production",
            readme,
        )
        self.assertNotIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe\n",
            readme,
        )
        helper = (ROOT / "scripts" / "cloudflare_wrangler.py").read_text(encoding="utf-8")
        self.assertIn("GitHub production environment secret", helper)


    def test_cloudflare_dialog_shell_and_work_history_match_local_contract(self):
        entry_shell = load_entry_shell_module()
        embedded_entry = entry_shell.build_entry_shell_html(
            "/login",
            {"embed": ["1"]},
            [],
            "pk_test_workdoe",
            "https://clerk.workdoe.com",
        )
        self.assertIn('class="market-entry-body dialog-fragment-body"', embedded_entry)
        self.assertNotIn('src="/map.js"', embedded_entry)
        self.assertNotIn("data-site-dialog", embedded_entry)
        frame_headers = entry_shell.shell_headers("https://clerk.workdoe.com")
        self.assertEqual(frame_headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", frame_headers["Content-Security-Policy"])
        native_dialog = entry_shell.site_dialog_html()
        self.assertIn('<dialog class="site-dialog"', native_dialog)
        self.assertIn("data-site-dialog-content", native_dialog)
        self.assertNotIn("iframe", native_dialog)

        app_shell = load_app_shell_module()
        client = {"id": 4, "role": "client", "status": "active"}
        embedded_form = app_shell.job_form_html(client, embedded=True)
        self.assertIn('<body class="dialog-fragment-body">', embedded_form)
        self.assertNotIn("data-site-dialog", embedded_form)
        self.assertNotIn('aria-label="Posting safeguards"', embedded_form)
        embedded_draft = app_shell.public_job_draft_html(embedded=True)
        self.assertNotIn("What needs doing?", embedded_draft)
        self.assertNotIn('aria-label="Project draft steps"', embedded_draft)
        app_headers = app_shell.app_shell_headers()
        self.assertEqual(app_headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", app_headers["Content-Security-Policy"])
        self.assertIn("data-dialog-fragment", embedded_form)
        self.assertIn("data-dialog-fragment", embedded_draft)

        client_jobs = load_client_jobs_module()
        client_payload = client_jobs.client_jobs_payload(
            [
                {
                    "id": 12,
                    "title": "Wash front steps",
                    "category": "Power washing",
                    "city": "Washington",
                    "state": "DC",
                    "zip_code": "20003",
                    "description": "Cleaned the walk and steps.",
                    "status": "closed",
                }
            ],
            "history",
        )
        self.assertEqual(len(client_payload["history"]), 1)
        self.assertEqual(client_payload["view"], "history")
        self.assertEqual(
            [item["value"] for item in client_payload["view_links"]],
            ["active", "review", "paused", "history"],
        )
        self.assertEqual(client_payload["history"][0]["repeat_url"], "/jobs/new?repeat=12")
        client_html = app_shell.client_dashboard_html(client, client_payload)
        self.assertIn("Private record", client_html)
        self.assertIn("Completed work", client_html)
        self.assertIn("Cleaned the walk and steps.", client_html)
        self.assertIn("Post again", client_html)
        self.assertIn("/jobs/new?repeat=12", client_html)

        contractor_bids = load_contractor_bids_module()
        contractor_payload = contractor_bids.contractor_bids_payload(
            [
                {
                    "id": 31,
                    "job_id": 12,
                    "title": "Wash front steps",
                    "category": "Power washing",
                    "city": "Washington",
                    "state": "DC",
                    "job_status": "closed",
                    "close_reason": "workdoe-match",
                    "status": "approved",
                    "scope_note": "Washed the steps and protected nearby brickwork.",
                    "price_range": "$450-$600",
                    "timeline": "One day",
                    "availability": "Weekday mornings",
                }
            ],
            "all",
        )
        self.assertEqual(len(contractor_payload["completed_work"]), 1)
        contractor_html = app_shell.contractor_dashboard_html(
            {"id": 7, "role": "contractor", "status": "active"},
            contractor_payload,
        )
        self.assertIn("Matched work", contractor_html)
        self.assertIn("Awaiting both confirmations", contractor_html)
        self.assertIn('class="completed-work-disclosure"', contractor_html)
        self.assertIn(
            'aria-label="View project record for Wash front steps"', contractor_html
        )
        self.assertLess(
            contractor_html.find("Project record"),
            contractor_html.find("Washed the steps and protected nearby brickwork."),
        )
        self.assertIn("Washed the steps and protected nearby brickwork.", contractor_html)
        self.assertIn("Specific addresses stay private.", contractor_html)
        self.assertNotIn("20003", contractor_html)

    def test_cloudflare_completion_contract_requires_two_match_participants(self):
        module = load_match_completions_module()
        client = {"id": 8, "role": "client", "status": "active"}
        contractor = {"id": 7, "role": "contractor", "status": "active"}
        outsider = {"id": 9, "role": "contractor", "status": "active"}
        match = {
            "match_request_id": 31,
            "client_id": 8,
            "contractor_id": 7,
            "match_status": "approved",
            "job_status": "closed",
            "close_reason": "workdoe-match",
            "client_confirmed_at": "",
            "contractor_confirmed_at": "",
            "verified_at": "",
        }

        self.assertEqual(
            module.parse_match_completion_path("/api/match-requests/31/complete"),
            31,
        )
        self.assertEqual(module.validate_completion_confirmation(client, match), "client")
        self.assertEqual(
            module.validate_completion_confirmation(contractor, match),
            "contractor",
        )
        with self.assertRaises(module.MatchCompletionError) as forbidden:
            module.validate_completion_confirmation(outsider, match)
        self.assertEqual(forbidden.exception.status, 403)
        with self.assertRaises(module.MatchCompletionError) as open_project:
            module.validate_completion_confirmation(
                contractor,
                {**match, "job_status": "open"},
            )
        self.assertEqual(open_project.exception.status, 409)
        with self.assertRaises(module.MatchCompletionError) as pending_match:
            module.validate_completion_confirmation(
                client,
                {**match, "match_status": "pending"},
            )
        self.assertEqual(pending_match.exception.status, 409)

        contractor_signal = {
            **match,
            "contractor_confirmed_at": "2026-08-16T12:00:00+00:00",
        }
        self.assertEqual(
            module.completion_label(contractor_signal, "client"),
            "Contractor confirmed - confirm completion",
        )
        verified = {
            **contractor_signal,
            "client_confirmed_at": "2026-08-16T12:05:00+00:00",
            "verified_at": "2026-08-16T12:05:00+00:00",
        }
        self.assertEqual(module.completion_state(verified), "verified")
        self.assertTrue(module.completion_response(verified)["verified"])

        migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0008_match_completions.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS match_completions", migration)
        self.assertIn("match_request_id INTEGER PRIMARY KEY", migration)
        self.assertIn("client_confirmed_at", migration)
        self.assertIn("contractor_confirmed_at", migration)
        self.assertIn("verified_at", migration)

        entrypoint = WORKER_ENTRY_PATH.read_text(encoding="utf-8")
        self.assertIn("async def confirm_match_completion", entrypoint)
        self.assertIn('"match-completion-confirmed"', entrypoint)
        self.assertIn("A project with completion confirmation cannot be reopened.", entrypoint)

    def test_cloudflare_six_step_taxonomy_and_incremental_d1_migration(self):
        job_posts = load_job_posts_module()
        worker_scope = load_service_scope_module()
        worker_taxonomy = load_service_taxonomy_module()
        worker_market_fit = load_market_fit_module()
        from workdoe.market_fit import DMV_SERVICE_ZONES
        from workdoe.service_taxonomy import (
            SERVICE_ALIASES,
            SERVICE_GROUPS,
            SERVICE_ICON_BY_SLUG,
        )

        self.assertEqual(worker_taxonomy.SERVICE_GROUPS, SERVICE_GROUPS)
        self.assertEqual(worker_taxonomy.SERVICE_ALIASES, SERVICE_ALIASES)
        self.assertEqual(worker_taxonomy.SERVICE_ICON_BY_SLUG, SERVICE_ICON_BY_SLUG)
        self.assertEqual(worker_market_fit.DMV_SERVICE_ZONES, DMV_SERVICE_ZONES)
        payload = job_posts.job_post_payload(
            {
                "title": "Mow and edge the back lawn",
                "category": "Other",
                "service_group_slug": "outdoor-yard",
                "service_slug": "lawn-mowing",
                "project_setting": "outdoor-area",
                "city": "Arlington",
                "state": "VA",
                "zip_code": "22201",
                "desired_date": "2026-12-01",
                "description": "Mow and edge a small fenced back lawn and remove the clippings.",
                "budget_min": "120",
                "budget_max": "180",
                "scope_area_size": "small",
                "scope_grass_height": "6_12",
                "scope_terrain": "obstacles",
                "scope_recurrence": "one_time",
            },
            today=job_posts.date(2026, 8, 16),
        )
        self.assertEqual(payload["service_group_slug"], "outdoor-yard")
        self.assertEqual(payload["service_slug"], "lawn-mowing")
        self.assertEqual(payload["category"], "Landscaping")
        self.assertEqual(payload["project_setting"], "outdoor-area")
        self.assertEqual(len(payload["scope_answers"]), 4)
        self.assertEqual(
            worker_scope.scope_readiness("lawn-mowing", payload["scope_answers"])[
                "percent"
            ],
            100,
        )

        app_shell = load_app_shell_module()
        html = app_shell.job_form_html({"id": 4, "role": "client", "status": "active"})
        self.assertEqual(html.count('data-project-step="'), 6)
        self.assertEqual(html.count('class="service-family-option"'), 6)
        self.assertEqual(html.count('class="service-option"'), 53)
        self.assertEqual(html.count('class="service-option-more"'), 6)
        self.assertEqual(html.count('class="service-option-heading"'), 6)
        self.assertIn("Common tasks", html)
        self.assertIn("Pick the closest fit. You can change it before posting.", html)
        self.assertIn("Choose one task. Add details next.", html)
        self.assertIn("Project name", html)
        self.assertIn('<span class="optional-label">Suggested</span>', html)
        self.assertIn("data-project-location-match", html)
        self.assertIn('data-city="Washington" data-state="DC"', html)
        self.assertLess(
            html.index('<label for="job-zip-code">'),
            html.index('<label for="job-city">'),
        )
        self.assertIn("More yard &amp; landscaping services", html)
        self.assertIn(
            f'src="/project-composer.js?v={app_shell.ASSET_RELEASE_TOKEN}"',
            html,
        )
        self.assertIn('/vendor/tabler-icons/trees.svg', html)
        self.assertIn('/vendor/tabler-icons/lawn-mower.svg', html)
        self.assertIn('/vendor/tabler-icons/seedling.svg', html)
        self.assertIn('/vendor/tabler-icons/plant.svg', html)
        self.assertIn(
            f'href="/styles.css?v={app_shell.ASSET_RELEASE_TOKEN}"',
            html,
        )
        self.assertIn('name="service_choice"', html)
        self.assertEqual(html.count('data-project-choice-advance'), 59)
        self.assertEqual(html.count('data-project-jump-step='), 4)
        self.assertIn('aria-label="Edit project details"', html)
        self.assertIn('/vendor/tabler-icons/pencil.svg', html)
        self.assertIn('data-selected-service-family', html)
        self.assertIn('class="service-select-control"', html)
        self.assertEqual(html.count('class="project-setting-option"'), 6)
        self.assertIn('data-review-setting', html)
        self.assertIn('name="license_preference" type="checkbox" value="1"', html)
        self.assertIn('data-review-license', html)
        self.assertIn("Workdoe source check only.", html)
        self.assertIn('data-service-scope-set="lawn-mowing"', html)
        self.assertIn('name="scope_grass_height"', html)
        self.assertIn('data-review-scope', html)
        self.assertIn('data-review-brief', html)

        for service_slug, icon_name in SERVICE_ICON_BY_SLUG.items():
            service_block = html.split(
                f'id="service-choice-{service_slug}"', 1
            )[1].split("</label>", 1)[0]
            self.assertIn(
                f'/vendor/tabler-icons/{icon_name}',
                service_block,
                service_slug,
            )
            self.assertNotIn("<small>", service_block, service_slug)

        worker_readiness = load_project_readiness_module()
        from workdoe.project_readiness import project_brief_readiness

        readiness_row = {
            "service_slug": "lawn-mowing",
            "description": "Mow and edge the fenced back lawn and remove all clippings.",
            "project_setting": "outdoor-area",
            "desired_date": "2026-12-01",
            "budget_max": 180,
            "scope_answer_count": 4,
            "photo_count": 0,
        }
        self.assertEqual(
            worker_readiness.project_brief_readiness(readiness_row),
            project_brief_readiness(readiness_row),
        )

        scope_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0020_job_scope_answers.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS job_scope_answers", scope_migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS job_draft_scope_answers", scope_migration)
        self.assertIn("question_key, answer_code, schema_version", scope_migration)
        self.assertNotIn("email", scope_migration.lower())
        self.assertNotIn("address", scope_migration.lower())

        migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0004_service_taxonomy.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS service_groups", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS service_types", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS service_aliases", migration)
        self.assertIn("ALTER TABLE jobs ADD COLUMN service_slug", migration)
        self.assertIn("idx_jobs_service_status", migration)

        labels_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0024_service_family_labels.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("UPDATE service_groups", labels_migration)
        self.assertIn("Yard & landscaping", labels_migration)
        self.assertIn("Plumbing & systems", labels_migration)

        aliases_icons_migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0026_service_aliases_and_icons.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE service_types ADD COLUMN icon_name TEXT", aliases_icons_migration)
        self.assertIn("'grass cutting', 'lawn-mowing'", aliases_icons_migration)
        self.assertIn("'kitchen renovation', 'kitchen-remodel'", aliases_icons_migration)
        self.assertIn("WHEN 'lawn-mowing' THEN 'lawn-mower.svg'", aliases_icons_migration)

        market_fit_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0006_contractor_market_fit.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS service_zones", market_fit_migration)
        self.assertIn("contractor_service_capabilities", market_fit_migration)
        self.assertIn("contractor_service_zones", market_fit_migration)
        self.assertIn("idx_contractor_capabilities_service", market_fit_migration)

        client_profile_migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0007_client_profiles_and_saved_locations.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN account_type", client_profile_migration)
        self.assertIn("ADD COLUMN notification_preference", client_profile_migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS client_saved_locations", client_profile_migration)
        self.assertIn("idx_client_saved_locations_owner", client_profile_migration)

        completion_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0008_match_completions.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS match_completions", completion_migration)
        self.assertIn("idx_match_completions_verified", completion_migration)

        bid_window_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0009_bid_windows.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN bid_limit", bid_window_migration)
        self.assertIn("ADD COLUMN bidding_closes_at", bid_window_migration)
        self.assertIn("idx_jobs_bidding_window", bid_window_migration)

        single_match_migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0033_single_approved_match.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("idx_match_requests_one_approved_per_job", single_match_migration)
        self.assertIn("WHERE status = 'approved'", single_match_migration)

        project_license_preference_migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0034_project_license_preference.sql"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            project_license_preference_migration.count(
                "ADD COLUMN license_preference INTEGER NOT NULL DEFAULT 0"
            ),
            3,
        )
        self.assertEqual(
            project_license_preference_migration.count(
                "CHECK (license_preference IN (0, 1))"
            ),
            3,
        )

        project_outcomes_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0010_project_outcomes.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN close_reason", project_outcomes_migration)
        self.assertIn("ADD COLUMN close_note", project_outcomes_migration)
        self.assertIn("ADD COLUMN closed_at", project_outcomes_migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS job_lead_feedback", project_outcomes_migration)
        self.assertIn("idx_job_lead_feedback_reason", project_outcomes_migration)

        service_activation_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0011_service_zone_activations.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN service_zone_slug", service_activation_migration)
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS service_zone_activations",
            service_activation_migration,
        )
        self.assertIn("minimum_eligible_contractors", service_activation_migration)
        self.assertIn("idx_service_zone_activations_status", service_activation_migration)

        project_settings_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0012_project_settings.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE jobs ADD COLUMN project_setting", project_settings_migration)
        self.assertIn(
            "ALTER TABLE job_drafts ADD COLUMN project_setting",
            project_settings_migration,
        )

        reminder_consent_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0013_email_reminder_consent.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN email_reminder_consent_at", reminder_consent_migration)
        self.assertIn("notification_preference = 'workdoe'", reminder_consent_migration)

        credential_migration = (
            ROOT / "cloudflare" / "d1" / "migrations" / "0014_contractor_credentials.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS contractor_credentials", credential_migration)
        self.assertIn("reviewed_by INTEGER REFERENCES users", credential_migration)
        self.assertIn("idx_contractor_credentials_review", credential_migration)

    def test_cloudflare_repeat_provider_invitation_contract_is_private_and_role_bound(self):
        module = load_repeat_provider_invitations_module()
        consumer = {"id": 11, "role": "client", "status": "active"}
        contractor = {"id": 22, "role": "contractor", "status": "active"}
        source = {
            "source_job_id": 31,
            "source_match_request_id": 41,
            "client_id": 11,
            "contractor_id": 22,
            "source_job_status": "closed",
            "close_reason": "workdoe-match",
            "match_status": "approved",
            "verified_at": "2026-08-17T12:00:00+00:00",
            "contractor_status": "active",
            "contractor_name": "Verified Contractor",
            "service_slug": "pressure-washing",
            "category": "Power washing",
        }
        normalized = module.validate_repeat_invitation_source(consumer, source)
        self.assertEqual(normalized["contractor_id"], 22)
        module.validate_repeat_invitation_service(normalized, "pressure-washing")
        with self.assertRaises(module.RepeatProviderInvitationError):
            module.validate_repeat_invitation_service(normalized, "window-cleaning")

        invitation = {
            "id": 51,
            "job_id": 61,
            "source_job_id": 31,
            "source_match_request_id": 41,
            "client_id": 11,
            "contractor_id": 22,
            "status": "pending",
            "service_slug": "pressure-washing",
            "project_title": "Wash the patio",
            "category": "Power washing",
            "city": "Washington",
            "state": "DC",
            "exact_address": "Must never leave storage",
            "phone": "202-555-0100",
        }
        response = module.repeat_invitation_response(invitation)
        self.assertEqual(response["status_label"], "Waiting for contractor")
        self.assertNotIn("exact_address", response)
        self.assertNotIn("phone", response)
        module.validate_invitation_action(contractor, invitation, "decline")
        module.validate_invitation_action(consumer, invitation, "withdraw")
        with self.assertRaises(module.RepeatProviderInvitationError):
            module.validate_invitation_action(consumer, invitation, "decline")
        self.assertEqual(
            module.parse_invitation_action_path(
                "/api/repeat-invitations/51/withdraw"
            ),
            (51, "withdraw"),
        )

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0017_repeat_provider_invitations.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS repeat_provider_invitations", migration)
        self.assertIn("source_match_request_id", migration)
        self.assertNotIn("address", migration.lower())
        self.assertNotIn("message", migration.lower())
        self.assertNotIn("photo", migration.lower())

        entry_source = WORKER_ENTRY_PATH.read_text(encoding="utf-8")
        shell_source = APP_SHELL_PATH.read_text(encoding="utf-8")
        self.assertIn("respond_repeat_invitation", entry_source)
        self.assertIn("repeat-provider-invitation-bid-sent", entry_source)
        self.assertIn('"request_id": request_id', entry_source)
        self.assertIn("repeat-invitation-banner", shell_source)
        self.assertIn("Invited back", shell_source)

    def test_cloudflare_match_review_contract_is_completion_gated_and_private(self):
        module = load_match_reviews_module()
        client = {"id": 11, "role": "client", "status": "active"}
        contractor = {"id": 22, "role": "contractor", "status": "active"}
        verified_match = {
            "id": 41,
            "job_id": 31,
            "client_id": 11,
            "contractor_id": 22,
            "match_status": "approved",
            "verified_at": "2026-08-17T12:00:00+00:00",
        }
        self.assertEqual(
            module.validate_review_eligibility(client, verified_match),
            "client",
        )
        self.assertEqual(
            module.validate_review_eligibility(contractor, verified_match),
            "contractor",
        )
        self.assertEqual(module.review_subject_id("client", verified_match), 22)
        self.assertEqual(module.review_subject_id("contractor", verified_match), 11)
        self.assertEqual(
            module.parse_match_review_create_path("/api/match-requests/41/review"),
            41,
        )
        self.assertEqual(
            module.parse_match_review_action_path("/api/reviews/51/response"),
            (51, "response"),
        )
        self.assertEqual(
            module.parse_match_review_action_path("/api/reviews/51/report"),
            (51, "report"),
        )

        values = module.validate_review_payload(
            {
                "communication": "met",
                "scope_accuracy": "mixed",
                "timeliness": "met",
                "work_outcome": "met",
                "would_work_again": "yes",
                "comment": "  Clear updates and careful work.  ",
            }
        )
        self.assertEqual(values["comment"], "Clear updates and careful work.")
        self.assertEqual(values["scope_accuracy"], "mixed")

        review = {
            "id": 51,
            "match_request_id": 41,
            "reviewer_id": 11,
            "subject_id": 22,
            "reviewer_role": "client",
            **values,
            "response": "",
            "response_at": "",
            "created_at": "2026-08-17T12:30:00+00:00",
            "verified_at": "2026-08-17T12:00:00+00:00",
            "is_hidden": 0,
        }
        response = module.review_response(review)
        self.assertTrue(response["verified_project"])
        self.assertEqual(response["communication_label"], "Met expectations")
        self.assertNotIn("reviewer_id", response)
        self.assertNotIn("subject_id", response)
        self.assertEqual(
            module.validate_review_response(contractor, review, "Thank you for the clear scope."),
            "Thank you for the clear scope.",
        )
        self.assertEqual(
            module.validate_review_report(client, review, "Please review this wording."),
            "Please review this wording.",
        )

        with self.assertRaisesRegex(module.MatchReviewError, "must confirm"):
            module.validate_review_eligibility(
                client,
                {**verified_match, "verified_at": None},
            )
        with self.assertRaisesRegex(module.MatchReviewError, "already left"):
            module.validate_review_eligibility(client, verified_match, review)
        with self.assertRaisesRegex(module.MatchReviewError, "participants"):
            module.validate_review_eligibility(
                {"id": 99, "role": "client", "status": "active"},
                verified_match,
            )
        with self.assertRaisesRegex(module.MatchReviewError, "recipient"):
            module.validate_review_response(client, review, "Not allowed")

        migration = (
            ROOT
            / "cloudflare"
            / "d1"
            / "migrations"
            / "0019_match_reviews.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS match_reviews", migration)
        self.assertIn("UNIQUE(match_request_id, reviewer_id)", migration)
        self.assertIn("CREATE TABLE IF NOT EXISTS match_review_reports", migration)
        for forbidden_column in ("email", "address", "zip_code", "phone", "photo"):
            self.assertNotIn(forbidden_column, migration.lower())

        entry_source = WORKER_ENTRY_PATH.read_text(encoding="utf-8")
        self.assertIn("create_match_review", entry_source)
        self.assertIn("match_review_action", entry_source)
        self.assertIn("INSERT OR IGNORE INTO match_reviews", entry_source)
        self.assertIn('"has_comment": bool(values["comment"])', entry_source)
        self.assertIn('payload = {"reporter_role": row_value(user, "role")}', entry_source)
        self.assertNotIn('payload={"comment": values["comment"]}', entry_source)
        self.assertNotIn('payload={"reason": reason}', entry_source)

    def test_cloudflare_match_review_shell_covers_both_participants_and_admin(self):
        module = load_app_shell_module()
        client = {"id": 11, "role": "client", "status": "active", "display_name": "Client"}
        contractor = {
            "id": 22,
            "role": "contractor",
            "status": "active",
            "display_name": "Crew",
        }
        review = {
            "id": 51,
            "match_request_id": 41,
            "reviewer_id": 11,
            "subject_id": 22,
            "reviewer_role": "client",
            "communication": "met",
            "communication_label": "Met expectations",
            "scope_accuracy": "met",
            "scope_accuracy_label": "Met expectations",
            "timeliness": "mixed",
            "timeliness_label": "Mixed",
            "work_outcome": "met",
            "work_outcome_label": "Met expectations",
            "would_work_again": "yes",
            "would_work_again_label": "Yes",
            "comment": "Clear updates and careful work.",
            "response": "",
            "created_at": "2026-08-17T12:30:00+00:00",
            "verified_at": "2026-08-17T12:00:00+00:00",
            "is_hidden": False,
            "service_name": "Power washing",
        }
        contractor_html = module.contractor_dashboard_html(
            contractor,
            {
                "bids": [],
                "completed_work": [
                    {
                        "id": 41,
                        "title": "Wash the front steps",
                        "category": "Power washing",
                        "city": "Washington",
                        "state": "DC",
                        "scope_note": "Wash the masonry steps.",
                        "timeline": "One day",
                        "price_range": "$300-$400",
                        "availability": "This week",
                        "completion_state": "verified",
                        "completion_label": "Workdoe-completed",
                        "verified_at": "2026-08-17T12:00:00+00:00",
                        "url": "/messages/5",
                    }
                ],
                "reviews_by_request": {41: {"client": review}},
                "stats": {},
            },
        )
        self.assertIn("Leave completed-work feedback", contractor_html)
        self.assertIn("Scope, accepted terms and 1 feedback note", contractor_html)
        self.assertIn(
            'aria-label="View project record for Wash the front steps"',
            contractor_html,
        )
        self.assertIn('data-json-action="/api/match-requests/41/review"', contractor_html)
        self.assertIn('data-json-action="/api/reviews/51/response"', contractor_html)
        self.assertIn('data-json-action="/api/reviews/51/report"', contractor_html)
        self.assertIn("does not create a star score", contractor_html)

        client_html = module.client_job_detail_html(
            client,
            {
                "job": {
                    "id": 31,
                    "title": "Wash the front steps",
                    "service_name": "Power washing",
                    "category": "Power washing",
                    "area_label": "Washington, DC 20003",
                    "status": "closed",
                    "close_reason": "workdoe-match",
                },
                "photos": [],
            },
            {
                "requests": [
                    {
                        "id": 41,
                        "status": "approved",
                        "contractor_name": "Doe Exterior Care",
                        "verified_at": "2026-08-17T12:00:00+00:00",
                        "completion_state": "verified",
                        "completion_label": "Workdoe-completed",
                    }
                ],
                "approved_request": {
                    "id": 41,
                    "contractor_id": 22,
                    "contractor_name": "Doe Exterior Care",
                    "price_range": "$300-$400",
                    "timeline": "One day",
                    "availability": "This week",
                    "thread_url": "/messages/5",
                    "profile_url": "/contractors/22",
                    "verified_at": "2026-08-17T12:00:00+00:00",
                    "completion_state": "verified",
                    "completion_label": "Workdoe-completed",
                },
                "reviews_by_request": {41: {}},
                "stats": {"approved": 1, "verified": 1, "total": 1},
            },
        )
        self.assertIn('aria-labelledby="approved-match-title"', client_html)
        self.assertIn('href="/messages/5">Message</a>', client_html)
        self.assertIn('href="/contractors/22">Profile</a>', client_html)
        self.assertIn("<dt>Price</dt><dd>$300-$400</dd>", client_html)
        self.assertIn("<dt>Timeline</dt><dd>One day</dd>", client_html)
        self.assertNotIn('aria-label="Bid availability"', client_html)
        self.assertIn("Leave completed-work feedback", client_html)
        self.assertIn('data-json-action="/api/match-requests/41/review"', client_html)

        filtered_closed_html = module.client_job_detail_html(
            client,
            {
                "job": {
                    "id": 31,
                    "title": "Wash the front steps",
                    "service_name": "Power washing",
                    "area_label": "Washington, DC 20003",
                    "status": "closed",
                    "close_reason": "workdoe-match",
                },
                "photos": [],
            },
            {
                "requests": [],
                "approved_request": {
                    "id": 41,
                    "contractor_id": 22,
                    "contractor_name": "Doe Exterior Care",
                    "profile_url": "/contractors/22",
                    "contractor_confirmed_at": "2026-08-17T11:00:00+00:00",
                    "completion_state": "contractor-confirmed",
                    "completion_label": "Contractor confirmed - confirm completion",
                },
                "stats": {"approved": 1, "verified": 0, "total": 1},
            },
        )
        self.assertIn("Contractor confirmed - confirm completion", filtered_closed_html)
        self.assertNotIn("Reopen job", filtered_closed_html)

        public_html = module.public_contractor_profile_html(
            client,
            {
                "contractor": {
                    "id": 22,
                    "business_name": "Doe Exterior Care",
                    "trades": "Power washing",
                    "service_area": "DMV",
                    "intro": "Careful exterior cleaning.",
                    "completed_work_reviews": [review],
                }
            },
        )
        self.assertIn("Completed-work feedback", public_html)
        self.assertIn("Consumer feedback", public_html)
        self.assertIn("No star score or paid ranking", public_html)
        self.assertNotIn("client@example.com", public_html)
        self.assertNotIn("20003", public_html)

        admin_html = module.admin_dashboard_html(
            {"id": 1, "role": "admin", "status": "active", "display_name": "Admin"},
            {
                "stats": {},
                "match_review_metrics": {
                    "total_reviews": 1,
                    "client_reviews": 1,
                    "contractor_reviews": 0,
                    "responses": 0,
                    "open_reports": 1,
                    "hidden_reviews": 0,
                },
                "match_review_reports": [
                    {
                        "id": 61,
                        "project_title": "Wash the front steps",
                        "reporter_email": "client@example.com",
                        "reason": "Review wording",
                    }
                ],
                "recent_match_reviews": [
                    {
                        "id": 51,
                        "project_title": "Wash the front steps",
                        "reviewer_role": "client",
                        "reviewer_email": "client@example.com",
                        "subject_email": "contractor@example.com",
                        "is_hidden": 0,
                    }
                ],
            },
        )
        self.assertIn("Participant feedback", admin_html)
        self.assertIn('data-json-action="/api/admin/reviews/51/hide"', admin_html)
        self.assertIn(
            'data-json-action="/api/admin/review-reports/61/resolve"',
            admin_html,
        )

    def test_cloudflare_pilot_metrics_match_local_contract_and_render_privately(self):
        worker_metrics = load_pilot_metrics_module()
        from workdoe.pilot_metrics import pilot_cell_metrics

        projects = [
            {
                "service_slug": "house-cleaning",
                "service_zone_slug": "district-of-columbia",
                "service_name": "House cleaning",
                "zone_name": "District of Columbia",
                "created_at": "2026-08-17T13:00:00+00:00",
                "description": "Deep clean a two-bedroom apartment before the next tenant arrives.",
                "project_setting": "inside-home",
                "desired_date": "2026-08-22",
                "budget_max": 350,
                "scope_answer_count": 3,
                "photo_count": 0,
                "bid_count": 3,
                "first_bid_at": "2026-08-17T13:45:00+00:00",
                "matched_count": 1,
                "verified_completion_count": 0,
                "status": "closed",
                "close_reason": "no-qualified-bid",
                "open_report_count": 1,
                "email": "private@example.com",
                "exact_address": "100 Private Street",
                "close_note": "Private project note",
                "report_reason": "Private report narrative",
            }
        ]
        supply = [
            {
                "service_slug": "house-cleaning",
                "zone_slug": "district-of-columbia",
                "current_eligible_contractors": 4,
                "minimum_eligible_contractors": 3,
                "activation_status": "active",
            }
        ]
        local = pilot_cell_metrics(projects, supply, as_of="2026-08-17")
        worker = worker_metrics.pilot_cell_metrics(
            projects, supply, as_of="2026-08-17"
        )
        self.assertEqual(worker, local)
        self.assertEqual(worker["cells"][0]["state"], "matched")
        self.assertEqual(worker["summary"]["median_first_bid_minutes"], 45)
        self.assertEqual(worker["summary"]["median_first_bid_label"], "45 min")
        self.assertEqual(worker["summary"]["no_match_or_cancelled_projects"], 1)
        self.assertEqual(worker["summary"]["open_report_projects"], 1)
        self.assertNotIn("private@example.com", json.dumps(worker))
        self.assertNotIn("Private project note", json.dumps(worker))
        self.assertNotIn("Private report narrative", json.dumps(worker))

        app_shell = load_app_shell_module()
        html = app_shell.admin_dashboard_html(
            {"id": 1, "role": "admin", "status": "active", "display_name": "Admin"},
            {
                "stats": {},
                "pilot_metrics": worker,
                "marketplace_metrics": {},
                "repeat_work_metrics": {},
                "lead_alert_metrics": {},
                "match_review_metrics": {},
            },
        )
        self.assertIn("Service-zone pulse", html)
        self.assertIn("Aggregate only", html)
        self.assertIn("House cleaning", html)
        self.assertIn("Current supply", html)
        self.assertIn("Median first bid", html)
        self.assertIn("45 min", html)
        self.assertIn("Open project reports", html)
        self.assertNotIn("private@example.com", html)
        self.assertNotIn("100 Private Street", html)

    def test_cloudflare_service_zone_activation_fails_closed(self):
        module = load_service_activation_module()
        ready = {
            "status": "active",
            "allowed_scope": "Interior cleaning.",
            "excluded_scope": "No alteration of real property.",
            "requirements_summary": "Operator review recorded.",
            "approved_at": "2026-08-17T12:00:00+00:00",
            "reviewed_at": "2026-08-17T12:00:00+00:00",
            "minimum_eligible_contractors": 3,
            "eligible_contractors": 3,
        }
        self.assertTrue(
            module.activation_is_live(ready, now="2026-08-17T13:00:00+00:00")
        )
        self.assertFalse(module.activation_is_live({**ready, "status": "paused"}))
        self.assertFalse(module.activation_is_live({**ready, "eligible_contractors": 2}))
        self.assertFalse(module.activation_is_live({**ready, "approved_at": None}))
        self.assertFalse(
            module.activation_is_live(
                {**ready, "expires_at": "2026-08-17T12:30:00+00:00"},
                now="2026-08-17T13:00:00+00:00",
            )
        )


if __name__ == "__main__":
    unittest.main()
