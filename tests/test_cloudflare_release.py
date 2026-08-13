from __future__ import annotations

import importlib.util
import json
import base64
import asyncio
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path


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
CLERK_ONBOARDING_PATH = ROOT / "cloudflare" / "worker" / "clerk_onboarding.py"
CLERK_SESSIONS_PATH = ROOT / "cloudflare" / "worker" / "clerk_sessions.py"
CLERK_PROXY_PATH = ROOT / "cloudflare" / "worker" / "clerk_proxy.py"
CLERK_WEBHOOKS_PATH = ROOT / "cloudflare" / "worker" / "clerk_webhooks.py"
EMAIL_PAYLOADS_PATH = ROOT / "cloudflare" / "worker" / "email_payloads.py"
ADMIN_MODERATION_PATH = ROOT / "cloudflare" / "worker" / "admin_moderation.py"
CONTRACTOR_PROFILES_PATH = ROOT / "cloudflare" / "worker" / "contractor_profiles.py"
CONTRACTOR_PUBLIC_PROFILES_PATH = ROOT / "cloudflare" / "worker" / "contractor_public_profiles.py"
CONTRACTOR_LEADS_PATH = ROOT / "cloudflare" / "worker" / "contractor_leads.py"
CONTRACTOR_BIDS_PATH = ROOT / "cloudflare" / "worker" / "contractor_bids.py"
CLIENT_JOBS_PATH = ROOT / "cloudflare" / "worker" / "client_jobs.py"
CLIENT_REQUESTS_PATH = ROOT / "cloudflare" / "worker" / "client_requests.py"
ENTRY_SHELL_PATH = ROOT / "cloudflare" / "worker" / "entry_shell.py"
PUBLIC_JOBS_PATH = ROOT / "cloudflare" / "worker" / "public_jobs.py"
JOB_DETAILS_PATH = ROOT / "cloudflare" / "worker" / "job_details.py"
JOB_STATUS_PATH = ROOT / "cloudflare" / "worker" / "job_status.py"
JOB_POSTS_PATH = ROOT / "cloudflare" / "worker" / "job_posts.py"
TURNSTILE_PATH = ROOT / "cloudflare" / "worker" / "turnstile.py"
MATCH_REQUESTS_PATH = ROOT / "cloudflare" / "worker" / "match_requests.py"
MATCH_DECISIONS_PATH = ROOT / "cloudflare" / "worker" / "match_decisions.py"
MESSAGE_THREADS_PATH = ROOT / "cloudflare" / "worker" / "message_threads.py"
MODERATION_REPORTS_PATH = ROOT / "cloudflare" / "worker" / "moderation_reports.py"
MEDIA_ACCESS_PATH = ROOT / "cloudflare" / "worker" / "media_access.py"
MEDIA_UPLOADS_PATH = ROOT / "cloudflare" / "worker" / "media_uploads.py"


def load_release_script():
    spec = importlib.util.spec_from_file_location("prepare_cloudflare_release", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
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
    spec = importlib.util.spec_from_file_location("public_jobs", PUBLIC_JOBS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_entry_shell_module():
    load_public_jobs_module()
    spec = importlib.util.spec_from_file_location("entry_shell", ENTRY_SHELL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_app_shell_module():
    load_job_posts_module()
    spec = importlib.util.spec_from_file_location("app_shell", APP_SHELL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_job_details_module():
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
    spec = importlib.util.spec_from_file_location("job_posts", JOB_POSTS_PATH)
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


def load_contractor_profiles_module():
    spec = importlib.util.spec_from_file_location("contractor_profiles", CONTRACTOR_PROFILES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_public_profiles_module():
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
    spec = importlib.util.spec_from_file_location("client_jobs", CLIENT_JOBS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_client_requests_module():
    spec = importlib.util.spec_from_file_location("client_requests", CLIENT_REQUESTS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_leads_module():
    spec = importlib.util.spec_from_file_location("contractor_leads", CONTRACTOR_LEADS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_contractor_bids_module():
    spec = importlib.util.spec_from_file_location("contractor_bids", CONTRACTOR_BIDS_PATH)
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

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["domain"], "workdoe.com")
            self.assertEqual(
                manifest["cloudflare_targets"]["worker"]["main"],
                "cloudflare/worker/entry.py",
            )
            self.assertEqual(manifest["cloudflare_targets"]["identity"]["service"], "Clerk")
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["primary_strategy"],
                "email_code_otp",
            )
            self.assertIn(
                "CLERK_SECRET_KEY",
                manifest["cloudflare_targets"]["identity"]["required_env"],
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["required_env"][
                    "CLERK_FRONTEND_API_URL"
                ],
                "https://workdoe.com/__clerk",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["required_env"][
                    "CLERK_PROXY_URL"
                ],
                "https://workdoe.com/__clerk",
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["identity"]["required_env"]["CLERK_FAPI"],
                "https://frontend-api.clerk.dev",
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
            self.assertEqual(manifest["cloudflare_targets"]["media"]["service"], "R2")
            self.assertTrue(
                manifest["cloudflare_targets"]["bot_protection"][
                    "server_side_validation_required"
                ]
            )
            self.assertEqual(
                manifest["cloudflare_targets"]["database"]["migration_sha256"],
                result["migration_sha256"],
            )

            wrangler = json.loads(wrangler_path.read_text(encoding="utf-8"))
            self.assertEqual(wrangler["name"], "workdoe")
            self.assertEqual(wrangler["main"], "worker/entry.py")
            self.assertEqual(wrangler["compatibility_flags"], ["python_workers"])
            self.assertFalse(wrangler["workers_dev"])
            self.assertEqual(
                {route["pattern"] for route in wrangler["routes"]},
                {"workdoe.com", "www.workdoe.com"},
            )
            self.assertTrue(all(route["custom_domain"] for route in wrangler["routes"]))
            self.assertEqual(wrangler["d1_databases"][0]["binding"], "DB")
            self.assertEqual(
                wrangler["d1_databases"][0]["migrations_dir"],
                "d1/migrations",
            )
            self.assertEqual(wrangler["r2_buckets"][0]["binding"], "MEDIA")
            self.assertEqual(wrangler["assets"]["binding"], "ASSETS")
            self.assertEqual(
                {producer["binding"] for producer in wrangler["queues"]["producers"]},
                {"EMAIL_QUEUE", "MEDIA_QUEUE"},
            )
            self.assertEqual(
                set(wrangler["triggers"]["crons"]),
                {"*/15 * * * *", "0 14 * * *", "0 13 * * 1-5"},
            )
            self.assertEqual(wrangler["vars"]["WORKDOE_AUTH_PROVIDER"], "clerk")
            self.assertEqual(
                wrangler["vars"]["WORKDOE_CLERK_LOGIN_MODE"],
                "same_domain_email_code",
            )
            self.assertEqual(
                wrangler["vars"]["CLERK_FRONTEND_API_URL"],
                "https://workdoe.com/__clerk",
            )
            self.assertEqual(wrangler["vars"]["CLERK_PROXY_URL"], "https://workdoe.com/__clerk")
            self.assertEqual(wrangler["vars"]["CLERK_FAPI"], "https://frontend-api.clerk.dev")
            self.assertEqual(wrangler["vars"]["WORKDOE_EMAIL_FROM"], "no-reply@workdoe.com")
            self.assertEqual(wrangler["vars"]["WORKDOE_ADMIN_EMAIL"], "admin@workdoe.com")
            self.assertEqual(
                wrangler["send_email"],
                [
                    {
                        "name": "EMAIL",
                        "allowed_sender_addresses": ["no-reply@workdoe.com"],
                    }
                ],
            )
            required_env_names = {
                "CLERK_PUBLISHABLE_KEY",
                "CLERK_SECRET_KEY",
                "CLERK_WEBHOOK_SECRET",
                "CLERK_JWT_KEY",
                "WORKDOE_SECRET_KEY",
                "WORKDOE_TURNSTILE_SITE_KEY",
                "WORKDOE_TURNSTILE_SECRET_KEY",
            }
            self.assertEqual(set(wrangler["secrets"]["required"]), required_env_names)
            self.assertFalse(required_env_names & set(wrangler["vars"]))
            self.assertTrue(wrangler["observability"]["enabled"])

            dev_vars_example = dev_vars_example_path.read_text(encoding="utf-8")
            self.assertIn("CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk", dev_vars_example)
            self.assertIn("CLERK_PROXY_URL=https://workdoe.com/__clerk", dev_vars_example)
            self.assertIn("CLERK_FAPI=https://frontend-api.clerk.dev", dev_vars_example)
            for env_name in required_env_names:
                self.assertIn(f"{env_name}=replace-me", dev_vars_example)

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
            "CLERK_PUBLISHABLE_KEY",
            "CLERK_SECRET_KEY",
            "CLERK_WEBHOOK_SECRET",
            "CLERK_JWT_KEY",
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
        self.assertIn("create-d1-production", names)
        self.assertIn("create-d1-preview", names)
        self.assertIn("apply-d1-ids", names)
        self.assertIn("create-r2-media-bucket", names)
        self.assertIn("create-email-queue", names)
        self.assertIn("create-media-review-queue", names)
        self.assertIn("capture-secret-list", names)
        d1_step = next(step for step in payload["steps"] if step["name"] == "create-d1-production")
        self.assertIn("wrangler", Path(d1_step["command"][0]).name.lower())
        self.assertEqual(d1_step["command"][1:], ["d1", "create", "workdoe"])
        self.assertTrue(d1_step["writes"].endswith("workdoe-d1.local.txt"))
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
            self.assertIn("CLERK_JWT_KEY", missing["missing_secret_names"])

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

    def test_cloudflare_release_evidence_validates_secret_and_clerk_proofs_together(self):
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
            self.assertIn("Clerk same-domain proxy proof is valid", result["checks"])

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

    def test_cloudflare_production_deploy_is_dry_run_by_default(self):
        module = load_production_deploy_script()
        payload = module.plan_payload(ROOT)
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["executes_commands"])
        self.assertEqual(payload["service"], "workdoe")
        self.assertEqual(payload["domain"], "workdoe.com")
        self.assertFalse(payload["ready_to_deploy"])
        self.assertIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            payload["strict_blockers"],
        )
        self.assertIn(
            "Clerk proxy proof JSON is missing or invalid: "
            + str(ROOT / "clerk-proxy-proof.local.json"),
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
                "smoke-health",
                "smoke-public-jobs",
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
            ["curl.exe", "-fS", "-I", "https://workdoe.com/health"],
        )
        self.assertEqual(
            payload["steps"][3]["command"],
            ["curl.exe", "-fsS", "https://workdoe.com/api/jobs/open?limit=3"],
        )

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
        try:
            sys.argv = [
                "cloudflare_production_deploy.py",
                "--execute",
                "--yes",
                "--json",
                "--no-smoke",
            ]
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(module.main(), 1)
            payload = json.loads(stdout.getvalue())
        finally:
            sys.argv = original_argv
        self.assertFalse(payload["ok"])
        self.assertIn("Strict production readiness failed", payload["error"])
        self.assertIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            payload["blockers"],
        )
        self.assertIn(
            "Clerk proxy proof JSON is missing or invalid: "
            + str(ROOT / "clerk-proxy-proof.local.json"),
            payload["blockers"],
        )

    def test_cloudflare_production_deploy_records_capped_smoke_output(self):
        module = load_production_deploy_script()
        steps = [
            module.DeployStep(
                name="smoke-health",
                command=["curl.exe", "-fS", "-I", "https://workdoe.com/health"],
                cwd=str(ROOT),
                required=False,
            ),
            module.DeployStep(
                name="smoke-public-jobs",
                command=["curl.exe", "-fsS", "https://workdoe.com/api/jobs/open?limit=3"],
                cwd=str(ROOT),
                required=False,
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
        self.assertEqual([step.status for step in executed], ["done", "done"])
        self.assertIn("HTTP/2 200 OK", executed[0].output_excerpt)

        long_result = type(
            "LongSmokeResult",
            (),
            {"returncode": 0, "stdout": "x" * (module.SMOKE_OUTPUT_MAX + 20), "stderr": ""},
        )()
        self.assertTrue(module.smoke_output_excerpt(long_result).endswith("[truncated]"))

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
            with self.assertRaisesRegex(
                module.ClerkProxyProofError,
                "https://workdoe.com/__clerk",
            ):
                module.build_proof(
                    proxy_url="https://clerk.workdoe.com",
                    confirmed=True,
                )

            proof = module.build_proof(
                confirmed=True,
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
            self.assertEqual(saved["checked_by"], "release-test")

    def test_cloudflare_worker_entrypoint_covers_automation_handlers(self):
        entrypoint = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("class Default(WorkerEntrypoint)", entrypoint)
        self.assertIn("async def scheduled(self, controller, env, ctx):", entrypoint)
        self.assertIn("async def queue(self, batch):", entrypoint)
        self.assertIn("def json_response", entrypoint)
        self.assertIn("handle_clerk_webhook", entrypoint)
        self.assertIn("CLERK_WEBHOOK_SECRET is required", entrypoint)
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
        self.assertIn("ENTRY_ROUTES", entrypoint)
        self.assertIn("entry_shell", entrypoint)
        self.assertIn("build_entry_shell_html", entrypoint)
        self.assertIn("entry_shell_jobs", entrypoint)
        self.assertIn("Entry pages accept GET only.", entrypoint)
        self.assertIn("is_app_shell_route", entrypoint)
        self.assertIn("app_shell", entrypoint)
        self.assertIn("dashboard_path_for_user", entrypoint)
        self.assertIn("admin_dashboard_html", entrypoint)
        self.assertIn("admin_dashboard_payload", entrypoint)
        self.assertIn("client_dashboard_html", entrypoint)
        self.assertIn("client_job_detail_html", entrypoint)
        self.assertIn("lead_board_html", entrypoint)
        self.assertIn("job_form_html", entrypoint)
        self.assertIn("contractor_profile_html", entrypoint)
        self.assertIn("public_contractor_profile_html", entrypoint)
        self.assertIn("contractor_job_detail_html", entrypoint)
        self.assertIn("message_threads_html", entrypoint)
        self.assertIn("message_thread_detail_html", entrypoint)
        self.assertIn("parse_app_client_job_id", entrypoint)
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
        self.assertIn("job_post_payload", entrypoint)
        self.assertIn("verify_turnstile_for_request", entrypoint)
        self.assertIn("WORKDOE_TURNSTILE_SECRET_KEY", entrypoint)
        self.assertIn("job-created", entrypoint)
        self.assertIn("create_match_request", entrypoint)
        self.assertIn("parse_match_request_job_id", entrypoint)
        self.assertIn("match_request_payload", entrypoint)
        self.assertIn("Only contractor accounts can send mini bids.", entrypoint)
        self.assertIn("match-request-created", entrypoint)
        self.assertIn("decide_match_request", entrypoint)
        self.assertIn("parse_match_decision_path", entrypoint)
        self.assertIn("can_decide_match_request", entrypoint)
        self.assertIn("ensure_thread_for_match", entrypoint)
        self.assertIn("APPROVAL_THREAD_MESSAGE", entrypoint)
        self.assertIn("match-request-approved", entrypoint)
        self.assertIn("match-request-rejected", entrypoint)
        self.assertIn("/api/messages/threads", entrypoint)
        self.assertIn("message_threads_api", entrypoint)
        self.assertIn("message_thread_summary", entrypoint)
        self.assertIn("can_view_thread", entrypoint)
        self.assertIn("can_send_thread_message", entrypoint)
        self.assertIn("message_body_payload", entrypoint)
        self.assertIn("message-created", entrypoint)
        self.assertIn("/api/reports", entrypoint)
        self.assertIn("create_report", entrypoint)
        self.assertIn("report_payload", entrypoint)
        self.assertIn("report_target_exists", entrypoint)
        self.assertIn("report-created", entrypoint)
        self.assertIn("/api/admin/", entrypoint)
        self.assertIn("admin_moderation_action", entrypoint)
        self.assertIn("parse_admin_moderation_path", entrypoint)
        self.assertIn("can_admin_moderate", entrypoint)
        self.assertIn("admin_update_statement", entrypoint)
        self.assertIn("insert_moderation_action", entrypoint)
        self.assertIn("admin-moderation-action", entrypoint)
        self.assertIn("/api/auth/session", entrypoint)
        self.assertIn("verify_clerk_session_token", entrypoint)
        self.assertIn("onboarding_required", entrypoint)
        self.assertIn("auth_provider = 'clerk'", entrypoint)
        self.assertIn("external_subject = ?", entrypoint)
        self.assertIn("/api/auth/onboard", entrypoint)
        self.assertIn("onboarding_payload", entrypoint)
        self.assertIn("INSERT INTO users", entrypoint)
        self.assertIn("INSERT INTO client_profiles", entrypoint)
        self.assertIn("INSERT INTO contractor_profiles", entrypoint)
        self.assertIn("email_conflict", entrypoint)
        self.assertIn("clerk-onboarding-linked", entrypoint)
        self.assertIn("/api/contractor/profile", entrypoint)
        self.assertIn("contractor_profile_api", entrypoint)
        self.assertIn("contractor_profile_payload", entrypoint)
        self.assertIn("can_update_contractor_profile", entrypoint)
        self.assertIn("upsert_contractor_profile", entrypoint)
        self.assertIn("contractor-profile-updated", entrypoint)
        self.assertIn("/api/contractors/", entrypoint)
        self.assertIn("public_contractor_profile", entrypoint)
        self.assertIn("parse_public_contractor_id", entrypoint)
        self.assertIn("can_view_public_contractor_profile", entrypoint)
        self.assertIn("public_contractor_for_profile", entrypoint)
        self.assertIn("visible_contractor_profile_photos", entrypoint)
        self.assertIn("env.EMAIL.send", entrypoint)
        self.assertIn("process_email_queue_message", entrypoint)
        self.assertIn("email-message-sent", entrypoint)
        self.assertIn("email-message-invalid", entrypoint)
        self.assertIn("email-message-send-failed", entrypoint)
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
        self.assertIn("MEDIA_QUEUE.send", entrypoint)
        self.assertIn("media-uploaded", entrypoint)
        self.assertIn("media-review-queued", entrypoint)
        self.assertIn("process_media_review_queue_message", entrypoint)
        self.assertIn("media-review-message-accepted", entrypoint)

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
            with self.subTest(key=key):
                with self.assertRaises(module.MediaAccessError):
                    module.safe_media_key(key, "jobs/12")

        admin = {"id": 1, "role": "admin", "status": "active"}
        client = {"id": 2, "role": "client", "status": "active"}
        contractor = {"id": 3, "role": "contractor", "status": "active"}
        suspended = {"id": 4, "role": "contractor", "status": "suspended"}
        job_photo = {
            "client_id": 2,
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
        self.assertEqual(
            module.upload_http_metadata(details)["cacheControl"],
            "private, no-store",
        )
        for filename, mime, size in (
            ("photo.svg", "image/svg+xml", 200),
            ("photo.jpg", "image/png", 200),
            ("photo.webp", "image/webp", module.MAX_UPLOAD_BYTES + 1),
            ("photo.gif", "image/gif", 0),
        ):
            with self.subTest(filename=filename, mime=mime, size=size):
                with self.assertRaises(module.MediaUploadError):
                    module.safe_upload_metadata(filename, mime, size)

        key = module.build_r2_upload_key("job", 12, "png")
        self.assertRegex(key, r"^jobs/12/[0-9a-f]{32}\.png$")

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
        with self.assertRaises(module.MediaUploadError):
            module.validated_media_review_payload({**payload, "stored_path": "jobs/13/bad.png"})

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
        self.assertEqual(reminder["to"]["email"], "client@example.com")
        self.assertEqual(reminder["from"]["email"], "no-reply@workdoe.com")
        self.assertIn("Mini bid waiting", reminder["subject"])
        self.assertIn("&lt;Paint lobby&gt;", reminder["html"])
        self.assertNotIn("<script>", reminder["html"])
        self.assertIn("Sign in to Workdoe", reminder["text"])

        login_code = module.build_email_message(
            {
                "type": "login-code",
                "to": " Contractor@Example.com ",
                "code": "123456",
                "intent": "find work",
                "expires_minutes": "10",
            }
        )
        self.assertEqual(login_code["to"]["email"], "contractor@example.com")
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
        self.assertEqual(digest["to"]["email"], "admin@workdoe.com")
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

    def test_clerk_onboarding_helper_requires_verified_email_and_role(self):
        module = load_clerk_onboarding_module()
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
                "q": ["  Arlington   VA  "],
                "sort": ["soonest"],
            }
        )
        self.assertEqual(
            filters,
            {"category": "Painting", "q": "Arlington VA", "sort": "soonest"},
        )
        self.assertEqual(
            module.public_job_filters_from_query(
                {"category": ["Unknown"], "q": ["A" * 120], "sort": ["bad"]}
            ),
            {"category": "", "q": "A" * 80, "sort": "newest"},
        )

        payload = module.public_jobs_payload(
            [
                {
                    "id": 9,
                    "title": "Paint stairwell",
                    "category": "Painting",
                    "city": "Arlington",
                    "state": "VA",
                    "zip_code": "22201",
                    "description": "Do not expose this in the public map API.",
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

    def test_cloudflare_entry_shell_mounts_same_domain_clerk_and_live_jobs(self):
        module = load_entry_shell_module()
        self.assertEqual(module.normalize_intent(None, "/login"), "find-work")
        self.assertEqual(module.normalize_intent(None, "/start"), "post-job")
        self.assertEqual(module.photo_count_label(1), "1 photo")
        self.assertEqual(module.photo_count_label("2"), "2 photos")
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
        self.assertIn("<title>Start - Workdoe</title>", html)
        self.assertIn('href="/static/styles.css"', html)
        self.assertIn('href="/static/vendor/leaflet/leaflet.css"', html)
        self.assertIn('src="/static/vendor/leaflet/leaflet.js"', html)
        self.assertIn('src="/static/map.js"', html)
        self.assertIn('src="/static/clerk-entry.js"', html)
        self.assertIn("data-clerk-entry", html)
        self.assertIn('data-clerk-mode="start"', html)
        self.assertIn('data-session-url="/api/auth/session"', html)
        self.assertIn('data-onboard-url="/api/auth/onboard"', html)
        self.assertIn('data-selected-job-id="9"', html)
        self.assertIn('data-clerk-publishable-key="pk_test_workdoe"', html)
        self.assertIn("Email code sign-in stays on workdoe.com.", html)
        self.assertIn('id="live-jobs" class="login-live-panel start-live-panel" tabindex="-1"', html)
        self.assertIn('class="entry-shortcut" href="#start-account">Start</a>', html)
        self.assertIn('id="start-account" class="form-panel login-form-panel start-form-panel clerk-entry-panel"', html)
        self.assertIn('<nav class="entry-shortcuts" aria-label="Start shortcuts">', html)
        self.assertIn('class="job-list login-job-list" aria-label="Open jobs while signing in" role="list"', html)
        self.assertIn("/api/jobs/open?limit=18&amp;target=start", html)
        self.assertIn("Paint &lt;stairwell&gt;", html)
        self.assertIn('role="listitem"', html)
        self.assertIn('aria-label="Selected lead Paint &lt;stairwell&gt;"', html)
        self.assertIn("1 photo", html)
        self.assertNotIn("1 photos", html)
        self.assertIn("Selected", html)
        self.assertNotIn("private@example.com", html)
        self.assertNotIn("22201", html)

        marker = '<script id="map-jobs-data" type="application/json">'
        data = html.split(marker, 1)[1].split("</script>", 1)[0]
        self.assertNotIn("&quot;", data)
        parsed = json.loads(data)
        self.assertEqual(parsed[0]["url"], "/start?intent=find-work&job_id=9")
        self.assertEqual(parsed[0]["action_label"], "Start")

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
            'data-sign-up-url="/start?intent=find-work&amp;job_id=9"',
            login_html,
        )
        self.assertIn('data-session-url="/api/auth/session"', login_html)
        self.assertIn('class="entry-shortcut" href="#signin">Sign in</a>', login_html)
        self.assertIn('id="signin" class="form-panel login-form-panel start-form-panel clerk-entry-panel"', login_html)
        self.assertIn('<nav class="entry-shortcuts" aria-label="Sign in shortcuts">', login_html)
        self.assertIn('class="job-list login-job-list" aria-label="Open jobs while signing in" role="list"', login_html)
        self.assertIn("/api/jobs/open?limit=18&amp;target=login", login_html)
        self.assertIn('href="/login?next=/jobs/9"', login_html)
        self.assertIn('role="listitem"', login_html)
        self.assertIn('aria-label="Selected lead Paint &lt;stairwell&gt;"', login_html)
        self.assertIn("1 photo", login_html)
        self.assertNotIn("1 photos", login_html)
        self.assertIn("Welcome back", login_html)
        self.assertIn("Selected", login_html)
        self.assertNotIn("data-clerk-display-name", login_html)

        headers = module.shell_headers("https://clerk.workdoe.com")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(
            "script-src 'self' https://clerk.workdoe.com",
            headers["Content-Security-Policy"],
        )
        self.assertIn(
            "https://*.tile.openstreetmap.org",
            headers["Content-Security-Policy"],
        )
        proxy_headers = module.shell_headers("/__clerk")
        self.assertIn("script-src 'self';", proxy_headers["Content-Security-Policy"])
        self.assertIn("connect-src 'self';", proxy_headers["Content-Security-Policy"])
        self.assertIn("frame-src 'self'", proxy_headers["Content-Security-Policy"])
        self.assertNotIn("/__clerk", proxy_headers["Content-Security-Policy"])

        proxy_html = module.build_entry_shell_html(
            "/login",
            {},
            rows,
            "pk_test_workdoe",
            "https://workdoe.com/__clerk",
        )
        self.assertIn('data-clerk-proxy-url="https://workdoe.com/__clerk"', proxy_html)
        self.assertIn("https://workdoe.com/__clerk/npm/@clerk/clerk-js@6", proxy_html)

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
        client = {"id": 8, "role": "client", "status": "active", "display_name": "Client"}
        contractor = {"id": 7, "role": "contractor", "status": "active", "display_name": "Crew"}
        admin = {"id": 1, "role": "admin", "status": "active", "display_name": "Admin"}
        self.assertTrue(module.is_app_shell_route("/dashboard"))
        self.assertTrue(module.is_app_shell_route("/client/jobs/12"))
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
        self.assertEqual(module.dashboard_path_for_user(client), "/client/dashboard")
        self.assertEqual(module.dashboard_path_for_user(contractor), "/contractor/dashboard")

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
                "stats": {"open_jobs": 1, "pending_requests": 2, "total_jobs": 1},
            },
        )
        self.assertIn("Client Dashboard - Workdoe", client_html)
        self.assertIn("/client/jobs/12?bids=pending#mini-bids", client_html)
        self.assertIn('aria-label="Review pending bids for Power wash steps"', client_html)
        self.assertIn("Review bids", client_html)
        self.assertNotIn("private@example.com", client_html)

        contractor_dashboard_html = module.contractor_dashboard_html(
            contractor,
            {
                "bids": [
                    {
                        "title": "Power wash steps",
                        "category": "Power washing",
                        "city": "Arlington",
                        "state": "VA",
                        "scope_note": "Careful exterior cleaning.",
                        "url": "/messages/5",
                        "row_cue": "Message",
                        "status": "approved",
                    }
                ],
                "stats": {"pending_requests": 0, "approved_requests": 1, "total_requests": 1},
            },
        )
        self.assertIn('aria-label="Message about Power wash steps"', contractor_dashboard_html)
        self.assertIn('<span class="row-cue">Message</span>', contractor_dashboard_html)

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
        self.assertIn('aria-label="Post a job."', form_html)
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
        self.assertIn('enterkeyhint="done"', form_html)
        self.assertIn('aria-describedby="job-photos-help"', form_html)
        self.assertIn('id="job-photos-help"', form_html)
        self.assertIn('aria-label="Post job"', form_html)
        self.assertIn('src="/static/worker-actions.js"', form_html)
        self.assertIn('class="cf-turnstile"', form_html)
        self.assertIn('data-sitekey="turnstile-site-key"', form_html)
        self.assertIn("Post job", form_html)

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
        self.assertIn('id="profile-intro"', profile_html)
        self.assertIn('enterkeyhint="done"', profile_html)
        self.assertIn('name="trades" value="Power washing" checked', profile_html)
        self.assertIn('name="portfolio_photo"', profile_html)
        self.assertIn('id="profile-photos"', profile_html)
        self.assertIn('aria-describedby="profile-photos-help"', profile_html)
        self.assertIn('id="profile-photos-help"', profile_html)
        self.assertIn('href="/contractors/7"', profile_html)
        self.assertIn('src="/static/worker-actions.js"', profile_html)
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
                    "photos": [{"id": 4, "url": "/media/contractors/4", "original_filename": "crew.webp"}],
                    "email": "contractor@example.com",
                }
            },
        )
        self.assertIn("Doe Exterior Care - Workdoe", public_profile_html)
        self.assertIn("/media/contractors/4", public_profile_html)
        self.assertIn("private Workdoe message thread", public_profile_html)
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
                    }
                ],
                "stats": {"threads": 1, "messages": 2},
            },
        )
        self.assertIn("Messages - Workdoe", messages_html)
        self.assertEqual(module.message_count_label(1), "1 message")
        self.assertEqual(module.message_count_label("2"), "2 messages")
        self.assertIn('href="/messages/5"', messages_html)
        self.assertIn('aria-label="Open message thread for Window cleaning"', messages_html)
        self.assertIn("2 messages", messages_html)
        self.assertIn("Tuesday works.", messages_html)
        self.assertNotIn("private@example.com", messages_html)

        thread_html = module.message_thread_detail_html(
            client,
            {
                "thread": {
                    "id": 5,
                    "title": "Window cleaning",
                    "category": "Window cleaning",
                    "city": "Arlington",
                    "state": "VA",
                    "client_name": "Avery Client",
                    "contractor_name": "Doe Exterior Care",
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
            },
            can_reply=True,
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
        self.assertIn('src="/static/worker-actions.js"', thread_html)
        self.assertIn("1 message", thread_html)
        self.assertNotIn("1 messages", thread_html)
        self.assertIn("Can you start Tuesday?", thread_html)

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
                "messages": [{"id": 9, "thread_id": 5, "sender_email": "crew@example.com", "job_title": "Window cleaning", "body": "Can start Tuesday.", "is_hidden": 0}],
                "actions": [{"action_type": "hide", "target_type": "message", "target_id": 9, "notes": "Hidden by admin.", "created_at": "2026-08-03T12:00:00+00:00"}],
                "automation_events": [{"event_type": "stale-match-reminder", "target_type": "match_request", "target_id": 4, "status": "queued", "created_at": "2026-08-03T13:00:00+00:00"}],
            },
        )
        self.assertIn("Admin - Workdoe", admin_html)
        self.assertIn("Moderation console", admin_html)
        self.assertIn("<span>Automation</span><strong>4</strong>", admin_html)
        self.assertIn("stale-match-reminder", admin_html)
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
                    }
                ],
            },
        )
        self.assertIn('id="lead-map"', lead_html)
        self.assertEqual(module.photo_count_label(1), "1 photo")
        self.assertEqual(module.photo_count_label(None), "0 photos")
        self.assertIn('src="/static/map.js"', lead_html)
        self.assertIn('class="job-list lead-job-list" aria-label="Open leads" role="list"', lead_html)
        self.assertIn('role="listitem"', lead_html)
        self.assertIn('data-job-id="21"', lead_html)
        self.assertIn('aria-label="View Clean windows"', lead_html)
        self.assertIn("1 photo", lead_html)
        self.assertNotIn("1 photos", lead_html)
        self.assertIn("Ground-floor exterior glass.", lead_html)
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
                "stats": {"pending": 1, "approved": 1, "total": 2},
                "view_links": [
                    {"value": "all", "label": "All", "url": "/client/jobs/12#mini-bids"},
                    {"value": "pending", "label": "Pending", "url": "/client/jobs/12?bids=pending#mini-bids"},
                ],
            },
        )
        self.assertIn("Power wash steps - Workdoe", client_job_html)
        self.assertIn("Job controls", client_job_html)
        self.assertIn('data-json-action="/api/jobs/12/close"', client_job_html)
        self.assertIn('aria-label="Close Power wash steps"', client_job_html)
        self.assertIn('aria-describedby="job-status-form-status"', client_job_html)
        self.assertIn('id="job-status-form-status"', client_job_html)
        self.assertIn('data-file-action="/api/media/jobs/12/upload"', client_job_html)
        self.assertIn('aria-label="Upload job photo"', client_job_html)
        self.assertIn('for="job-photo-upload"', client_job_html)
        self.assertIn('id="job-photo-upload"', client_job_html)
        self.assertIn('name="photo"', client_job_html)
        self.assertIn("Upload photo", client_job_html)
        self.assertIn('data-json-action="/api/match-requests/31/approve"', client_job_html)
        self.assertIn('aria-label="Approve mini bid from Doe Exterior Care"', client_job_html)
        self.assertIn('aria-describedby="match-request-31-approve-status"', client_job_html)
        self.assertIn('id="match-request-31-approve-status"', client_job_html)
        self.assertIn('data-json-action="/api/match-requests/31/reject"', client_job_html)
        self.assertIn('aria-label="Reject mini bid from Doe Exterior Care"', client_job_html)
        self.assertIn('aria-describedby="match-request-31-reject-status"', client_job_html)
        self.assertIn('id="match-request-31-reject-status"', client_job_html)
        self.assertIn('href="/messages/5"', client_job_html)
        self.assertIn('src="/static/worker-actions.js"', client_job_html)
        self.assertNotIn("contractor@example.com", client_job_html)

        headers = module.app_shell_headers(include_map=True, include_turnstile=True)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("https://*.tile.openstreetmap.org", headers["Content-Security-Policy"])
        self.assertIn("https://challenges.cloudflare.com", headers["Content-Security-Policy"])

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
        entrypoint = (ROOT / "cloudflare" / "worker" / "entry.py").read_text(encoding="utf-8")
        self.assertIn('"field_errors": exc.field_errors', entrypoint)

        clerk_script = (ROOT / "workdoe" / "static" / "clerk-entry.js").read_text(encoding="utf-8")
        self.assertIn("finishSignIn", clerk_script)
        self.assertIn("node.dataset.signUpUrl", clerk_script)
        self.assertIn("clerkUserEmail", clerk_script)
        self.assertIn("onboardPayload.email = email", clerk_script)

    def test_cloudflare_contractor_leads_helper_matches_lead_board_contract(self):
        module = load_contractor_leads_module()
        self.assertEqual(module.parse_contractor_lead_limit("999"), 50)
        self.assertEqual(module.parse_contractor_lead_limit("0"), 1)
        self.assertEqual(module.normalize_contractor_lead_view("sent"), "sent")
        self.assertEqual(module.normalize_contractor_lead_view("bad"), "all")
        filters = module.contractor_lead_filters_from_query(
            {
                "category": ["Painting"],
                "q": ["  Arlington   VA  "],
                "sort": ["soonest"],
            }
        )
        self.assertEqual(
            filters,
            {"category": "Painting", "q": "Arlington VA", "sort": "soonest"},
        )
        self.assertEqual(
            module.contractor_lead_filters_from_query(
                {"category": ["Unknown"], "q": ["A" * 120], "sort": ["bad"]}
            ),
            {"category": "", "q": "A" * 80, "sort": "newest"},
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
                "created_at": "2026-08-02T12:00:00+00:00",
                "approx_lat": None,
                "approx_lng": None,
                "photo_count": None,
                "request_status": None,
            },
        ]
        payload = module.contractor_leads_payload(rows, filters=filters, view="sent")
        self.assertEqual(payload["view"], "sent")
        self.assertEqual(payload["stats"]["all_jobs"], 2)
        self.assertEqual(payload["stats"]["visible_jobs"], 1)
        self.assertEqual(payload["stats"]["new_jobs"], 1)
        self.assertEqual(payload["stats"]["sent_bids"], 1)
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["jobs"][0]["url"], "/jobs/12")
        self.assertEqual(payload["jobs"][0]["request_status"], "pending")
        self.assertFalse(payload["jobs"][0]["can_request_match"])
        self.assertEqual(payload["map_jobs"][0]["action_label"], "Sent")
        self.assertEqual(payload["count"], 1)
        self.assertNotIn("zip_code", payload["jobs"][0])
        self.assertNotIn("client_id", payload["jobs"][0])
        self.assertNotIn("client_email", payload["jobs"][0])

        new_payload = module.contractor_leads_payload(rows, filters=filters, view="new")
        self.assertEqual(len(new_payload["jobs"]), 1)
        self.assertEqual(new_payload["jobs"][0]["id"], 13)
        self.assertEqual(new_payload["count"], 0)

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
        self.assertEqual(pending_payload["bids"][0]["row_cue"], "View")

    def test_cloudflare_client_jobs_helper_matches_dashboard_counts(self):
        module = load_client_jobs_module()
        self.assertEqual(module.normalize_client_job_view("review"), "review")
        self.assertEqual(module.normalize_client_job_view("bad"), "all")
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
                "pending_count": 0,
                "approved_count": 0,
                "rejected_count": 1,
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
        self.assertEqual(payload["stats"]["total_jobs"], 2)
        self.assertEqual(payload["stats"]["visible_jobs"], 1)
        self.assertEqual(payload["stats"]["open_jobs"], 1)
        self.assertEqual(payload["stats"]["closed_jobs"], 1)
        self.assertEqual(payload["stats"]["pending_requests"], 2)
        self.assertEqual(payload["stats"]["approved_requests"], 1)
        self.assertEqual(payload["stats"]["rejected_requests"], 1)
        self.assertNotIn("client_id", payload["jobs"][0])
        self.assertNotIn("client_email", payload["jobs"][0])

        all_payload = module.client_jobs_payload(rows, "all")
        self.assertEqual(all_payload["jobs"][1]["url"], "/client/jobs/13")
        self.assertEqual(all_payload["jobs"][1]["row_cue"], "Review")
        self.assertFalse(all_payload["jobs"][1]["needs_review"])

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
        self.assertEqual(payload["stats"], {"visible": 1, "total": 3, "pending": 1, "approved": 1, "rejected": 1})
        self.assertEqual(len(payload["requests"]), 1)
        request_payload = payload["requests"][0]
        self.assertEqual(request_payload["contractor_name"], "Doe Exterior Care")
        self.assertEqual(request_payload["profile_url"], "/contractors/7")
        self.assertTrue(request_payload["can_approve"])
        self.assertTrue(request_payload["needs_review"])
        self.assertEqual(request_payload["row_cue"], "Review")
        self.assertNotIn("email", request_payload)
        self.assertNotIn("phone", request_payload)

        approved_payload = module.client_job_requests_payload(job, rows, "approved")
        approved = approved_payload["requests"][0]
        self.assertEqual(approved["thread_url"], "/messages/5")
        self.assertEqual(approved["row_cue"], "Message")
        self.assertFalse(approved["can_approve"])
        self.assertEqual(approved["trades"], "Contractor profile")

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
            "title": "Clean storefront windows",
            "category": "Window cleaning",
            "city": "Arlington",
            "state": "VA",
            "zip_code": "22201",
            "description": "Clean front and side windows before opening.",
            "desired_date": "2026-09-01",
            "status": "open",
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
        self.assertFalse(module.can_view_job_detail(suspended, job))

        contractor_payload = module.job_detail_payload(contractor, job, photos=photos)
        contractor_job = contractor_payload["job"]
        self.assertEqual(contractor_job["area_label"], "Arlington, VA 222xx")
        self.assertEqual(contractor_job["zip_prefix"], "222xx")
        self.assertTrue(contractor_job["can_request_match"])
        self.assertNotIn("zip_code", contractor_job)
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
        self.assertEqual(owner_payload["photos"][0]["is_hidden"], 0)
        with self.assertRaisesRegex(module.JobDetailError, "Unsupported"):
            module.parse_job_detail_id("/api/jobs/0")

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
        with self.assertRaisesRegex(module.JobStatusError, "Unsupported"):
            module.parse_job_status_path("/api/jobs/42/delete")

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
        self.assertIn("Use a full website URL that starts with http:// or https://.", invalid.exception.errors)
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
            ["Use a full website URL that starts with http:// or https://."],
        )

    def test_cloudflare_public_contractor_profile_helper_keeps_contact_private(self):
        module = load_contractor_public_profiles_module()
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
            "stored_path": "contractors/42/private.webp",
        }
        inactive_contractor = {**public_contractor, "status": "suspended"}
        admin = {"id": 1, "role": "admin", "status": "active"}
        client = {"id": 8, "role": "client", "status": "active"}
        self.assertTrue(module.can_view_public_contractor_profile(None, public_contractor))
        self.assertTrue(module.can_view_public_contractor_profile(client, public_contractor))
        self.assertFalse(module.can_view_public_contractor_profile(client, inactive_contractor))
        self.assertTrue(module.can_view_public_contractor_profile(admin, inactive_contractor))

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
        self.assertNotIn("stored_path", contractor["photos"][0])
        admin_payload = module.public_contractor_profile_payload(inactive_contractor, [], admin)
        self.assertEqual(admin_payload["contractor"]["status"], "suspended")

    def test_cloudflare_job_post_payload_matches_local_validation_contract(self):
        module = load_job_posts_module()
        payload = module.job_post_payload(
            {
                "title": "  Clean storefront windows  ",
                "category": "Window cleaning",
                "city": " Alexandria ",
                "state": "va",
                "zip_code": "22314-0010",
                "desired_date": "2026-09-01",
                "description": "Need first-floor storefront windows cleaned before opening.",
            },
            today=module.date(2026, 8, 3),
        )
        self.assertEqual(payload["title"], "Clean storefront windows")
        self.assertEqual(payload["state"], "VA")
        self.assertEqual(payload["zip_code"], "22314")
        self.assertEqual(payload["approx_lat"], 38.8048)
        self.assertEqual(payload["approx_lng"], -77.0469)
        self.assertEqual(
            payload["location_privacy"],
            "Approximate city or ZIP-level pins only.",
        )

        with self.assertRaises(module.JobPostError) as invalid:
            module.job_post_payload(
                {
                    "title": "",
                    "category": "Mystery",
                    "city": "",
                    "state": "PA",
                    "zip_code": "22A",
                    "desired_date": "2020-01-01",
                    "description": "Too short",
                },
                today=module.date(2026, 8, 3),
            )
        self.assertIn("Add a job title.", invalid.exception.errors)
        self.assertIn("Choose a curated category.", invalid.exception.errors)
        self.assertIn("Use DC, MD, or VA for the first DMV beta.", invalid.exception.errors)
        self.assertIn("Use a 5-digit DMV ZIP code.", invalid.exception.errors)
        self.assertIn("Choose today or a future desired date.", invalid.exception.errors)
        self.assertEqual(invalid.exception.field_errors["title"], ["Add a job title."])
        self.assertEqual(invalid.exception.field_errors["category"], ["Choose a curated category."])
        self.assertEqual(
            invalid.exception.field_errors["state"],
            ["Use DC, MD, or VA for the first DMV beta."],
        )
        self.assertEqual(
            invalid.exception.field_errors["city"],
            ["Add the city so the lead can be mapped approximately."],
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
            }
        )
        self.assertEqual(
            payload["scope_note"],
            "I can clean the windows and protect nearby surfaces.",
        )
        self.assertEqual(payload["price_range"], "$450 - $650")
        self.assertEqual(payload["timeline"], "Two business days after approval")
        self.assertEqual(payload["availability"], "Tuesday and Thursday afternoons")

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
                "client_name": "Avery Client",
                "contractor_name": "Doe Powerwash",
                "last_message": "Can you start Tuesday?",
                "message_count": 2,
                "client_email": "private@example.com",
            }
        )
        self.assertEqual(summary["url"], "/messages/42")
        self.assertEqual(summary["message_count"], 2)
        self.assertNotIn("client_email", summary)
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
            module.parse_admin_moderation_path("/api/admin/reports/9/resolve"),
            {"target_type": "report", "target_id": 9, "action": "resolve"},
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
        self.assertEqual(
            module.admin_target_query("message"),
            "SELECT 1 FROM messages WHERE id = ? LIMIT 1",
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
        self.assertIn("Wrangler keeps same-domain Clerk OTP mode", result.checks)
        self.assertIn("Wrangler configures Workdoe Clerk proxy Frontend API URL", result.checks)
        self.assertIn("Wrangler configures Clerk proxy URL", result.checks)
        self.assertIn("Wrangler configures Clerk Frontend API proxy target", result.checks)
        self.assertIn(
            "Wrangler requires Clerk, Turnstile, and Workdoe secrets",
            result.checks,
        )
        self.assertIn("Wrangler keeps required secret names out of vars", result.checks)
        self.assertIn("Cloudflare Worker Python compiles", result.checks)
        self.assertIn("Cloudflare authenticated app shell helper compiles", result.checks)
        self.assertIn("Clerk onboarding helper compiles", result.checks)
        self.assertIn("Clerk session verification helper compiles", result.checks)
        self.assertIn("Clerk Frontend API proxy helper compiles", result.checks)
        self.assertIn("Cloudflare email payload helper compiles", result.checks)
        self.assertIn("Cloudflare admin moderation helper compiles", result.checks)
        self.assertIn("Cloudflare contractor profile helper compiles", result.checks)
        self.assertIn("Cloudflare public contractor profile helper compiles", result.checks)
        self.assertIn("Cloudflare client jobs helper compiles", result.checks)
        self.assertIn("Cloudflare client requests helper compiles", result.checks)
        self.assertIn("Cloudflare same-domain entry shell helper compiles", result.checks)
        self.assertIn("Cloudflare job detail helper compiles", result.checks)
        self.assertIn("Cloudflare job status helper compiles", result.checks)
        self.assertIn("Wrangler configures Workdoe transactional email vars", result.checks)
        self.assertIn("Wrangler restricts Cloudflare Email sender binding", result.checks)
        self.assertIn("Cloudflare job posting helper compiles", result.checks)
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
            "Cloudflare Worker creates client jobs with Turnstile and approximate pins",
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
            "Cloudflare Clerk proxy proof helper is confirm-gated",
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
        self.assertIn(
            "Wrangler D1 database_id is still the placeholder UUID.",
            result.warnings,
        )
        self.assertIn(
            "Wrangler D1 preview_database_id is still the placeholder UUID.",
            result.warnings,
        )

    def test_cloudflare_preflight_strict_blocks_placeholder_resource_ids(self):
        module = load_preflight_script()
        result = module.run_preflight(ROOT, strict_production=True)
        self.assertFalse(result.ok)
        self.assertIn(
            "Wrangler D1 database_id is still the placeholder UUID.",
            result.errors,
        )

    def test_cloudflare_readiness_doctor_separates_local_and_production_readiness(self):
        module = load_readiness_script()
        local = module.run_readiness(ROOT)
        self.assertTrue(local.ready, local.blockers)
        self.assertIn("Wrangler config is present", local.checks)
        self.assertIn("Same-domain Clerk email-code mode is configured", local.checks)
        self.assertIn("Clerk Frontend API URL uses Workdoe same-origin proxy", local.checks)
        self.assertIn("Clerk proxy URL matches the Workdoe Frontend API URL", local.checks)
        self.assertIn("Clerk proxy target is the official Frontend API", local.checks)
        self.assertIn("Worker has same-domain Clerk entry shell", local.checks)
        self.assertIn("Worker has Workdoe Clerk Frontend API proxy", local.checks)
        self.assertIn("Worker sets Clerk proxy headers", local.checks)
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
        self.assertIn(
            "Clerk same-domain proxy proof was not checked; pass --clerk-proxy-proof-json for deploy proof.",
            local.warnings,
        )
        self.assertIn("wrangler secret put CLERK_SECRET_KEY", local.next_steps)
        self.assertIn(
            "python ..\\scripts\\cloudflare_clerk_proxy_proof.py --confirm --output ..\\clerk-proxy-proof.local.json",
            local.next_steps,
        )
        self.assertIn(
            "python ..\\scripts\\cloudflare_release_evidence.py --json --secret-list-json ..\\cloudflare-secret-list.local.json --clerk-proxy-proof-json ..\\clerk-proxy-proof.local.json",
            local.next_steps,
        )

        strict = module.run_readiness(ROOT, strict_production=True)
        self.assertFalse(strict.ready)
        self.assertIn(
            "Cloudflare secret presence is unverified. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes` and pass --secret-list-json.",
            strict.blockers,
        )
        self.assertIn(
            "Wrangler D1 database_id is still the placeholder UUID.",
            strict.blockers,
        )
        self.assertIn(
            "Clerk same-domain proxy proof is unverified. Confirm Clerk Domains uses https://workdoe.com/__clerk and pass --clerk-proxy-proof-json.",
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
                + "\nCLERK_FAPI=https://frontend-api.clerk.dev",
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
            self.assertIn("Provided env file uses Workdoe same-origin Clerk proxy", result.checks)
            self.assertIn("Provided env file Clerk proxy URL matches Frontend API URL", result.checks)
            self.assertIn("Provided env file Clerk proxy target is official", result.checks)
            self.assertIn("Cloudflare secret list contains every required secret name", result.checks)
            self.assertIn("Clerk same-domain proxy is confirmed in Clerk Domains", result.checks)
            self.assertEqual(module.clerk_proxy_proof_error(proxy_proof_path), "")

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
                    }
                ),
                encoding="utf-8",
            )

            env_path.write_text("CLERK_SECRET_KEY=replace-me\n", encoding="utf-8")
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
                + "\nCLERK_FAPI=https://frontend-api.clerk.dev",
                encoding="utf-8",
            )
            off_domain = module.run_readiness(
                ROOT,
                env_file=env_path,
                secret_list_json=secret_list_path,
                clerk_proxy_proof_json=proxy_proof_path,
            )
            self.assertFalse(off_domain.ready)
            self.assertIn(
                "Provided env file CLERK_FRONTEND_API_URL must be an https Workdoe /__clerk proxy URL.",
                off_domain.blockers,
            )

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
        self.assertEqual(phases["cloudflare-resources"]["status"], "blocked")
        self.assertEqual(phases["identity-and-secrets"]["status"], "blocked")
        self.assertEqual(phases["clerk-domain-proof"]["status"], "pending")
        self.assertEqual(phases["deploy-gate"]["status"], "pending")
        self.assertEqual(phases["migrate-and-deploy"]["status"], "blocked")
        self.assertIn(
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
            phases["cloudflare-token"]["commands"],
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe",
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
        self.assertIn(
            'test "${{ inputs.clerk_proxy_url }}" = "https://workdoe.com/__clerk"',
            workflow,
        )
        self.assertIn("Check Cloudflare credentials are configured", workflow)
        self.assertIn('test -n "$CLOUDFLARE_API_TOKEN"', workflow)
        self.assertIn("Print guarded deploy plan", workflow)

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
            "GitHub repository is missing deployment secret CLOUDFLARE_ACCOUNT_ID.",
            status.blockers,
        )
        self.assertIn("GitHub production environment currently allows admin bypass.", status.warnings)

        ready = module.build_status(
            environment=environment,
            branch_policies=branch_policies,
            secret_names=set(module.REQUIRED_DEPLOY_SECRETS),
        )
        self.assertTrue(ready.ready)

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
        self.assertIn("clerk_proxy_url=https://workdoe.com/__clerk", plan["command"])
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

    def test_workdoe_launch_handoff_renders_redacted_operator_checklist(self):
        module = load_workdoe_launch_handoff_script()
        original_doctor = module.build_doctor
        original_dispatch = module.build_dispatch_plan
        try:
            doctor_payload = {
                "ready": False,
                "blockers": [
                    "GitHub repository is missing deployment secret CLOUDFLARE_API_TOKEN.",
                    "CLOUDFLARE_API_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456",
                    "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
                    f"Clerk proxy proof JSON is missing or invalid: {ROOT}\\clerk-proxy-proof.local.json",
                ],
                "next_actions": [
                    "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe",
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
            module.build_dispatch_plan = lambda repo_root=ROOT, local_url=module.DEFAULT_LOCAL_URL: dispatch_payload
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
            "GitHub repository is missing deployment secret CLOUDFLARE_API_TOKEN.",
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
        self.assertIn("DNS And Domain Activation", groups)
        self.assertIn("Final Deployment And Smoke", groups)
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe",
            groups["GitHub Deployment Secrets"],
        )
        self.assertIn(
            "set CLOUDFLARE_API_TOKEN in this shell without committing it",
            groups["Cloudflare Account And Resources"],
        )
        self.assertIn("npm run launch:dns", groups["DNS And Domain Activation"])
        self.assertIn("npm run launch:smoke:strict", groups["Final Deployment And Smoke"])
        self.assertIn("# Workdoe Launch Handoff", markdown)
        self.assertIn("Status: Blocked before production dispatch", markdown)
        self.assertIn("This private local handoff", markdown)
        self.assertIn("### GitHub Deployment Secrets", markdown)
        self.assertIn("### Cloudflare Account And Resources", markdown)
        self.assertIn("### Final Deployment Gate", markdown)
        self.assertIn("### DNS And Domain Activation", markdown)
        self.assertIn("### Final Deployment And Smoke", markdown)
        self.assertIn("GitHub repository is missing deployment secret CLOUDFLARE_API_TOKEN.", markdown)
        self.assertIn("gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe", markdown)
        self.assertIn("npm run launch:dns", markdown)
        self.assertIn("npm run github:deploy:plan", markdown)
        self.assertIn("npm run launch:smoke:strict", markdown)
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
                        "next_command": "npm run cf:clerk:proof",
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
                "workdoe.com nameserver = ada.ns.cloudflare.com\n"
                "workdoe.com nameserver = bob.ns.cloudflare.com\n",
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
        original_dns_lookup = module.dns_lookup
        original_fetch_url = module.fetch_url
        try:
            module.dns_lookup = lambda domain="workdoe.com": (
                True,
                ["203.0.113.10"],
                "",
            )

            def fake_fetch(url, *, method="GET", timeout=module.DEFAULT_TIMEOUT, body_limit=20000):
                headers = {}
                body = ""
                status_code = 200
                if url.endswith("/start"):
                    headers = {
                        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "Referrer-Policy": "strict-origin-when-cross-origin",
                        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
                    }
                elif url.endswith("/health"):
                    body = json.dumps(
                        {
                            "ok": True,
                            "service": "workdoe-cloudflare-worker",
                            "bindings": {"d1": True},
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
        self.assertEqual(checks["https-entry"]["status"], "ready")
        self.assertEqual(checks["health-json"]["status"], "ready")
        self.assertEqual(checks["public-jobs-api"]["status"], "ready")
        self.assertEqual(checks["entry-security-headers"]["status"], "ready")

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

    def test_workdoe_launch_doctor_combines_release_blockers(self):
        module = load_workdoe_launch_doctor_script()
        github_status = load_github_release_status_script().GithubReleaseStatus(
            repository="Yami566/workdoe",
            environment="production",
            live=False,
            ready=False,
            environment_ready=True,
            secrets_ready=False,
            blockers=["GitHub repository is missing deployment secret CLOUDFLARE_API_TOKEN."],
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
            "GitHub repository is missing deployment secret CLOUDFLARE_API_TOKEN.",
            payload["blockers"],
        )
        self.assertEqual(payload["phases"][1]["status"], "not-checked")
        self.assertEqual(payload["phases"][2]["name"], "wrangler-auth")
        self.assertEqual(payload["phases"][2]["status"], "not-checked")
        self.assertEqual(payload["phases"][-1]["status"], "not-checked")
        self.assertIn("npm run launch:doctor:live", payload["next_actions"])
        self.assertIn("npm run cf:resources:plan", payload["next_actions"])
        self.assertIn(
            "GitHub repository is missing deployment secret CLOUDFLARE_API_TOKEN.",
            live_payload["blockers"],
        )
        self.assertIn(
            "gh secret set CLOUDFLARE_API_TOKEN --repo Yami566/workdoe",
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

    def test_cloudflare_launch_status_summarizes_next_safe_action(self):
        module = load_launch_status_script()
        original_wrangler_available = module.wrangler_available
        original_resolved_wrangler_bin = module.resolved_wrangler_bin
        original_token_present = module.cloudflare_api_token_present
        try:
            module.wrangler_available = lambda repo_root=ROOT: True
            module.resolved_wrangler_bin = lambda repo_root=ROOT: "wrangler"
            module.cloudflare_api_token_present = lambda: False
            status = module.build_launch_status(ROOT)
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
        self.assertEqual(phases["cloudflare-resources"]["status"], "blocked")
        self.assertEqual(phases["identity-and-secrets"]["status"], "blocked")
        self.assertEqual(phases["clerk-domain-proof"]["status"], "pending")
        self.assertEqual(phases["release-evidence"]["status"], "pending")
        self.assertIn(
            "D1 database_id must be replaced with the real Cloudflare UUID.",
            status["blockers"],
        )
        self.assertIn(
            "CLOUDFLARE_API_TOKEN is not set; local Cloudflare resource bootstrap, secret evidence, and deploy execute commands cannot run.",
            status["blockers"],
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
        self.assertEqual(status["current_phase"], "cloudflare-resources")
        self.assertFalse(status["ready_to_deploy"])

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


if __name__ == "__main__":
    unittest.main()
