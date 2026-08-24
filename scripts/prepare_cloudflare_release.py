from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
D1_MIGRATION_RELATIVE_PATH = Path("cloudflare/d1/migrations/0001_initial.sql")
D1_MIGRATIONS_RELATIVE_PATH = D1_MIGRATION_RELATIVE_PATH.parent
MANIFEST_RELATIVE_PATH = Path("cloudflare/workdoe-cloudflare-manifest.json")
WRANGLER_RELATIVE_PATH = Path("cloudflare/wrangler.jsonc")
DEV_VARS_EXAMPLE_RELATIVE_PATH = Path("cloudflare/.dev.vars.example")
STATIC_HEADERS_RELATIVE_PATH = Path("workdoe/static/_headers")
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
D1_ID_FIELDS = ("database_id", "preview_database_id")
IMMUTABLE_D1_BASELINE_SHA256 = "dd46194b4f45811901a8fe1718a482ea286863a4a87e3bcdce66cf60967c479e"
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
REQUIRED_WORKER_SECRETS = [
    "CLERK_JWT_KEY",
    "CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_WEBHOOK_SECRET",
    "WORKDOE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SITE_KEY",
]
IMMUTABLE_STATIC_ASSET_PATHS = [
    "/styles.css",
    "/map.js",
    "/project-composer.js",
    "/vendor/*",
    "/deer.svg",
]
VERSIONED_STATIC_ASSET_FILES = [
    "styles.css",
    "map.js",
    "project-composer.js",
]


def valid_d1_id(value: str | None) -> bool:
    return bool(value and value != ZERO_UUID and UUID_RE.fullmatch(str(value)))


def existing_d1_ids(wrangler_path: Path) -> dict[str, str]:
    try:
        wrangler = json.loads(wrangler_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    d1 = (wrangler.get("d1_databases") or [{}])[0]
    return {
        field: str(d1.get(field))
        for field in D1_ID_FIELDS
        if valid_d1_id(str(d1.get(field) or ""))
    }


def migration_chain_sha256(migrations_dir: Path) -> str:
    digest = hashlib.sha256()
    migration_paths = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not migration_paths:
        raise ValueError(f"No D1 migrations found in {migrations_dir}")
    for path in migration_paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def static_asset_release_token(repo_root: Path) -> str:
    digest = hashlib.sha256()
    static_root = repo_root / "workdoe" / "static"
    for filename in VERSIONED_STATIC_ASSET_FILES:
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update((static_root / filename).read_bytes())
        digest.update(b"\0")
    return f"asset-{digest.hexdigest()[:16]}"


def immutable_baseline_sql(repo_root: Path) -> str:
    migration_path = repo_root / D1_MIGRATION_RELATIVE_PATH
    migration_sql = migration_path.read_text(encoding="utf-8")
    actual_sha = hashlib.sha256(migration_sql.encode("utf-8")).hexdigest()
    if actual_sha != IMMUTABLE_D1_BASELINE_SHA256:
        raise ValueError(
            "The immutable 0001 D1 migration changed. Add a new numbered migration "
            "instead of editing or regenerating 0001_initial.sql."
        )
    return migration_sql


def build_manifest(
    migration_sql: str,
    migration_chain_sha: str,
    asset_release_token: str,
) -> dict:
    return {
        "name": "workdoe",
        "domain": "workdoe.com",
        "source_stack": [
            "Python",
            "server-rendered HTML",
            "SQLite-compatible SQL",
            "Leaflet/OpenStreetMap embed",
        ],
        "cloudflare_targets": {
            "worker": {
                "config": str(WRANGLER_RELATIVE_PATH).replace("\\", "/"),
                "main": "cloudflare/worker/entry.py",
                "dev_vars_example": str(DEV_VARS_EXAMPLE_RELATIVE_PATH).replace("\\", "/"),
                "static_asset_headers": str(STATIC_HEADERS_RELATIVE_PATH).replace("\\", "/"),
                "asset_release_token": asset_release_token,
                "versioned_static_assets": VERSIONED_STATIC_ASSET_FILES,
                "immutable_static_asset_paths": IMMUTABLE_STATIC_ASSET_PATHS,
                "custom_domains": ["workdoe.com", "www.workdoe.com"],
                "custom_domain_management": "preconfigured_outside_routine_deploys",
                "compatibility_date": "2026-08-23",
                "compatibility_flags": [
                    "python_workers",
                    "disable_python_external_sdk",
                ],
            },
            "app_runtime": {
                "service": "Cloudflare Workers Python",
                "route": "workdoe.com/*",
                "required_env": {
                    "WORKDOE_ENV": "production",
                    "WORKDOE_SECRET_KEY": "set as a secret",
                },
            },
            "identity": {
                "service": "Clerk with Cloudflare D1 role records",
                "experience": "same-domain in-page sign-in on workdoe.com",
                "primary_strategy": "email_code_otp",
                "required_env": {
                    "CLERK_JWT_KEY": "set as a secret",
                    "CLERK_PUBLISHABLE_KEY": "set as a secret",
                    "CLERK_SECRET_KEY": "set as a secret",
                    "CLERK_WEBHOOK_SECRET": "set as a secret",
                    "WORKDOE_AUTH_PROVIDER": "clerk",
                    "WORKDOE_SECRET_KEY": "set as a secret",
                },
                "domain_rules": [
                    "Mount Clerk email-code sign-in on /login and /start without redirecting off workdoe.com.",
                    "Proxy Clerk frontend requests through https://workdoe.com/__clerk.",
                    "Verify Clerk sessions in the Worker before linking D1 role records.",
                    "Keep consumer and contractor authorization in Workdoe D1.",
                ],
            },
            "database": {
                "service": "D1",
                "binding": "DB",
                "migration": str(D1_MIGRATION_RELATIVE_PATH).replace("\\", "/"),
                "migration_sha256": hashlib.sha256(migration_sql.encode("utf-8")).hexdigest(),
                "migrations_dir": str(D1_MIGRATIONS_RELATIVE_PATH).replace("\\", "/"),
                "migration_chain_sha256": migration_chain_sha,
            },
            "media": {
                "service": "Cloudflare Images and R2",
                "binding": "MEDIA",
                "images_binding": "IMAGES",
                "bucket": "workdoe-media",
                "private": True,
                "sanitization": {
                    "decode": "Cloudflare Images binding",
                    "output": "WebP",
                    "max_dimension": 2400,
                    "metadata": "discarded",
                    "animation": "flattened",
                },
                "key_prefixes": [
                    "jobs/{job_id}/",
                    "contractors/{contractor_id}/",
                ],
            },
            "email": {
                "service": "Cloudflare Email Service",
                "binding": "EMAIL",
                "from": "no-reply@workdoe.com",
                "admin_digest_to": "admin@workdoe.com",
                "uses": [
                    "stale match reminders",
                    "moderation digests",
                ],
            },
            "bot_protection": {
                "service": "Turnstile",
                "site_key_env": "WORKDOE_TURNSTILE_SITE_KEY",
                "secret_key_env": "WORKDOE_TURNSTILE_SECRET_KEY",
                "server_side_validation_required": True,
                "forms": [
                    "start",
                    "login",
                    "project draft",
                    "job posting",
                    "match request",
                    "report",
                ],
            },
            "rate_limiting": {
                "service": "Cloudflare Workers Rate Limiting",
                "bindings": [
                    {
                        "name": "WRITE_RATE_LIMITER",
                        "namespace_id": "949417",
                        "simple": {"limit": 40, "period": 60},
                    }
                ],
                "key": "authenticated Workdoe user ID",
            },
            "automation": {
                "scheduled_jobs": [
                    {
                        "name": "expire-login-codes",
                        "cron_utc": "*/15 * * * *",
                        "purpose": "mark stale local fallback login codes and reset tokens unusable",
                    },
                    {
                        "name": "stale-match-reminders",
                        "cron_utc": "0 14 * * *",
                        "purpose": "queue client reminders for pending mini bids older than 24 hours",
                    },
                    {
                        "name": "moderation-digest",
                        "cron_utc": "0 13 * * 1-5",
                        "purpose": "email admins a weekday report queue summary",
                    },
                ],
                "queues": [
                    {
                        "binding": "EMAIL_QUEUE",
                        "queue": "workdoe-email",
                        "uses": [
                            "match reminders",
                            "new matching project alerts",
                            "repeat-provider invitation alerts",
                            "admin moderation digests",
                            "local fallback OTP and reset mail",
                        ],
                    },
                    {
                        "binding": "MEDIA_QUEUE",
                        "queue": "workdoe-media-review",
                        "uses": [
                            "photo metadata checks",
                            "moderation review tasks",
                        ],
                    },
                ],
            },
        },
        "privacy_invariants": [
            "Only approximate city/ZIP map pins are public before a match is approved.",
            "Job and contractor photos stay private behind role and match checks.",
            "Exact client contact details are not exposed on the public lead board.",
            "Client, contractor, and admin role data stays compartmentalized.",
            "Clerk verifies identity; Workdoe remains the source of truth for roles, job permissions, moderation, and match visibility.",
        ],
    }


def build_wrangler_config(manifest: dict, d1_ids: dict[str, str] | None = None) -> dict:
    targets = manifest["cloudflare_targets"]
    automation = targets["automation"]
    crons = [job["cron_utc"] for job in automation["scheduled_jobs"]]
    queues = automation["queues"]
    d1_config = {
        "binding": targets["database"]["binding"],
        "database_name": "workdoe",
        "database_id": ZERO_UUID,
        "preview_database_id": ZERO_UUID,
        "migrations_dir": "d1/migrations",
    }
    for field in D1_ID_FIELDS:
        if d1_ids and valid_d1_id(d1_ids.get(field)):
            d1_config[field] = d1_ids[field]
    return {
        "$schema": "../node_modules/wrangler/config-schema.json",
        "name": "workdoe",
        "main": "worker/entry.py",
        "compatibility_date": targets["worker"]["compatibility_date"],
        "compatibility_flags": targets["worker"]["compatibility_flags"],
        "workers_dev": False,
        "assets": {
            "directory": "../workdoe/static",
            "binding": "ASSETS",
            "run_worker_first": False,
        },
        "d1_databases": [d1_config],
        "r2_buckets": [
            {
                "binding": targets["media"]["binding"],
                "bucket_name": targets["media"]["bucket"],
            }
        ],
        "images": {"binding": targets["media"]["images_binding"]},
        "send_email": [
            {
                "name": targets["email"]["binding"],
                "allowed_sender_addresses": [targets["email"]["from"]],
                "remote": True,
            }
        ],
        "ratelimits": targets["rate_limiting"]["bindings"],
        "queues": {
            "producers": [
                {"binding": queue["binding"], "queue": queue["queue"]}
                for queue in queues
            ],
            "consumers": [
                {
                    "queue": queue["queue"],
                    "max_batch_size": 10,
                    "max_batch_timeout": 30,
                    "max_retries": 5,
                }
                for queue in queues
            ],
        },
        "triggers": {"crons": crons},
        "vars": {
            "WORKDOE_ENV": "production",
            "WORKDOE_AUTH_PROVIDER": "clerk",
            "WORKDOE_DOMAIN": manifest["domain"],
            "WORKDOE_PUBLIC_URL": f"https://{manifest['domain']}",
            "WORKDOE_LOGIN_MODE": "same_domain_email_code",
            "WORKDOE_ENFORCE_SERVICE_ACTIVATION": "true",
            "WORKDOE_EMAIL_FROM": targets["email"]["from"],
            "WORKDOE_ADMIN_EMAIL": targets["email"]["admin_digest_to"],
        },
        "secrets": {
            "required": REQUIRED_WORKER_SECRETS,
        },
        "observability": {
            "enabled": True,
            "traces": {"enabled": True},
        },
    }


def build_dev_vars_example(manifest: dict) -> str:
    required_env = {}
    for target in manifest["cloudflare_targets"].values():
        if isinstance(target, dict):
            required_env.update(target.get("required_env", {}))
    bot_protection = manifest["cloudflare_targets"].get("bot_protection", {})
    for env_key in ("site_key_env", "secret_key_env"):
        if bot_protection.get(env_key):
            required_env[bot_protection[env_key]] = "replace-me"
    lines = [
        "# Copy to .dev.vars for local Wrangler previews.",
        "# Keep real production values in Cloudflare secrets, not this file.",
        "WORKDOE_ENV=production",
        "WORKDOE_AUTH_PROVIDER=clerk",
        "WORKDOE_DOMAIN=workdoe.com",
        "WORKDOE_PUBLIC_URL=https://workdoe.com",
        "WORKDOE_LOGIN_MODE=same_domain_email_code",
        "WORKDOE_ENFORCE_SERVICE_ACTIVATION=true",
    ]
    for key in sorted(required_env):
        if key in {
            "WORKDOE_ENV",
            "WORKDOE_AUTH_PROVIDER",
            "WORKDOE_LOGIN_MODE",
            "WORKDOE_ENFORCE_SERVICE_ACTIVATION",
        }:
            continue
        lines.append(f"{key}=replace-me")
    return "\n".join(lines).rstrip() + "\n"


def write_text_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def prepare_release(repo_root: Path = REPO_ROOT, output_root: Path | None = None) -> dict:
    output_root = output_root or repo_root / "cloudflare"
    migration_path = output_root / "d1" / "migrations" / "0001_initial.sql"
    manifest_path = output_root / "workdoe-cloudflare-manifest.json"
    wrangler_path = output_root / "wrangler.jsonc"
    dev_vars_example_path = output_root / ".dev.vars.example"

    migration_sql = immutable_baseline_sql(repo_root)
    chain_sha = migration_chain_sha256(repo_root / D1_MIGRATIONS_RELATIVE_PATH)
    asset_release_token = static_asset_release_token(repo_root)
    manifest = build_manifest(migration_sql, chain_sha, asset_release_token)
    manifest_json = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    d1_ids = existing_d1_ids(wrangler_path)
    wrangler_json = json.dumps(
        build_wrangler_config(manifest, d1_ids=d1_ids),
        indent=2,
        sort_keys=True,
    ) + "\n"
    dev_vars_example = build_dev_vars_example(manifest)

    migration_changed = write_text_if_changed(migration_path, migration_sql)
    manifest_changed = write_text_if_changed(manifest_path, manifest_json)
    wrangler_changed = write_text_if_changed(wrangler_path, wrangler_json)
    dev_vars_example_changed = write_text_if_changed(dev_vars_example_path, dev_vars_example)

    return {
        "migration": str(migration_path),
        "manifest": str(manifest_path),
        "wrangler": str(wrangler_path),
        "dev_vars_example": str(dev_vars_example_path),
        "migration_changed": migration_changed,
        "manifest_changed": manifest_changed,
        "wrangler_changed": wrangler_changed,
        "dev_vars_example_changed": dev_vars_example_changed,
        "migration_sha256": manifest["cloudflare_targets"]["database"]["migration_sha256"],
        "migration_chain_sha256": manifest["cloudflare_targets"]["database"][
            "migration_chain_sha256"
        ],
        "asset_release_token": asset_release_token,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare Workdoe Cloudflare D1/R2/Email/Turnstile release artifacts."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=REPO_ROOT / "cloudflare",
        help="Directory for generated Cloudflare artifacts.",
    )
    args = parser.parse_args()
    result = prepare_release(REPO_ROOT, args.output_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
