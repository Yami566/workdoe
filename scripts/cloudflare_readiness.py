from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
REQUIRED_SECRETS = {
    "WORKDOE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SITE_KEY",
}
REQUIRED_PUBLIC_VARS = {"WORKDOE_AUTH_PROVIDER", "WORKDOE_LOGIN_MODE"}
REQUIRED_QUEUES = {
    "EMAIL_QUEUE": "workdoe-email",
    "MEDIA_QUEUE": "workdoe-media-review",
}
REQUIRED_CRONS = {"*/15 * * * *", "0 14 * * *", "0 13 * * 1-5"}
PLACEHOLDERS = {"", "replace-me", "changeme", "todo", "set-me"}
WORKDOE_PUBLIC_DOMAIN = "workdoe.com"
CLERK_PROXY_PATH = "/__clerk"
DEFAULT_CLERK_FAPI = "https://frontend-api.clerk.dev"
DEFAULT_CLERK_PROXY_PROOF_PATH = REPO_ROOT / "clerk-proxy-proof.local.json"


@dataclass
class ReadinessResult:
    ready: bool
    checks: list[str]
    warnings: list[str]
    blockers: list[str]
    next_steps: list[str]

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "checks": self.checks,
            "warnings": self.warnings,
            "blockers": self.blockers,
            "next_steps": self.next_steps,
        }


def add_ok(checks: list[str], name: str) -> None:
    checks.append(name)


def add_requirement(
    condition: bool,
    checks: list[str],
    blockers: list[str],
    ok_name: str,
    blocker: str,
) -> None:
    if condition:
        add_ok(checks, ok_name)
    else:
        blockers.append(blocker)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def parse_env_file(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def is_placeholder(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in PLACEHOLDERS or normalized.startswith("<") or normalized.endswith(">")


def valid_workdoe_clerk_frontend_url(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    parsed = urlparse(normalized)
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


def is_workdoe_domain(hostname: str | None) -> bool:
    host = (hostname or "").strip().lower().rstrip(".")
    return host == WORKDOE_PUBLIC_DOMAIN or host.endswith(f".{WORKDOE_PUBLIC_DOMAIN}")


def parse_secret_names(path: Path | None) -> set[str]:
    if not path:
        return set()
    data = read_json(path)
    return secret_names_from_json(data)


def secret_names_from_json(data) -> set[str]:
    if isinstance(data, list):
        return names_from_secret_items(data)
    if not isinstance(data, dict):
        return set()
    for key in ("secrets", "result", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return names_from_secret_items(value)
    return {key for key, value in data.items() if value is True}


def names_from_secret_items(items: list) -> set[str]:
    names: set[str] = set()
    for item in items:
        if isinstance(item, str):
            names.add(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("key") or item.get("binding")
            if name:
                names.add(str(name))
    return names


def clerk_proxy_proof_error(path: Path | None) -> str:
    if not path:
        return (
            "Clerk same-domain proxy proof is unverified. Confirm Clerk Domains uses "
            "https://workdoe.com/__clerk and pass --clerk-proxy-proof-json."
        )
    data = read_json(path)
    if not isinstance(data, dict) or not data:
        return f"Clerk proxy proof JSON is missing or invalid: {path}"
    if data.get("confirmed") is not True:
        return "Clerk proxy proof must include confirmed=true."
    if str(data.get("domain", "")).strip().lower() != WORKDOE_PUBLIC_DOMAIN:
        return "Clerk proxy proof domain must be workdoe.com."
    proxy_url = (
        data.get("frontend_api_proxy_url")
        or data.get("clerk_proxy_url")
        or data.get("proxy_url")
        or ""
    )
    if not valid_workdoe_clerk_proxy_url(str(proxy_url)):
        return "Clerk proxy proof must use https://workdoe.com/__clerk."
    return ""


def preflight_result(repo_root: Path, strict_production: bool) -> dict:
    sys.path.insert(0, str(repo_root / "scripts"))
    from cloudflare_preflight import run_preflight

    return run_preflight(repo_root, strict_production=strict_production).as_dict()


def command_steps() -> list[str]:
    return [
        "python scripts\\cloudflare_resource_bootstrap.py --json --no-secret-probe",
        "python scripts\\cloudflare_resource_bootstrap.py --execute --yes --no-secret-probe",
        "cd cloudflare",
        "wrangler secret put WORKDOE_SECRET_KEY",
        "wrangler secret put WORKDOE_TURNSTILE_SITE_KEY",
        "wrangler secret put WORKDOE_TURNSTILE_SECRET_KEY",
        "python ..\\scripts\\cloudflare_secret_evidence.py --execute --yes --output ..\\cloudflare-secret-list.local.json",
        "python ..\\scripts\\cloudflare_release_evidence.py --json --secret-list-json ..\\cloudflare-secret-list.local.json",
        "python ..\\scripts\\cloudflare_readiness.py --strict-production --secret-list-json ..\\cloudflare-secret-list.local.json",
        "cd ..",
        "python scripts\\cloudflare_production_deploy.py --json --secret-list-json cloudflare-secret-list.local.json",
        "python scripts\\cloudflare_production_deploy.py --execute --yes --secret-list-json cloudflare-secret-list.local.json",
    ]


def run_readiness(
    repo_root: Path = REPO_ROOT,
    strict_production: bool = False,
    env_file: Path | None = None,
    secret_list_json: Path | None = None,
    clerk_proxy_proof_json: Path | None = None,
) -> ReadinessResult:
    checks: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    next_steps = command_steps()

    preflight = preflight_result(repo_root, strict_production=strict_production)
    checks.extend(f"preflight: {name}" for name in preflight["checks"])
    warnings.extend(preflight["warnings"])
    blockers.extend(preflight["errors"])

    wrangler_path = repo_root / "cloudflare" / "wrangler.jsonc"
    wrangler = read_json(wrangler_path)
    add_requirement(
        bool(wrangler),
        checks,
        blockers,
        "Wrangler config is present",
        "Missing cloudflare/wrangler.jsonc.",
    )
    if wrangler:
        vars_map = wrangler.get("vars", {})
        d1 = (wrangler.get("d1_databases") or [{}])[0]
        add_requirement(
            d1.get("database_name") == "workdoe" and d1.get("binding") == "DB",
            checks,
            blockers,
            "D1 production database binding targets workdoe",
            "D1 binding must use database_name=workdoe and binding=DB.",
        )
        for id_field in ("database_id", "preview_database_id"):
            if d1.get(id_field) and d1.get(id_field) != ZERO_UUID:
                add_ok(checks, f"D1 {id_field} is not a placeholder")
            elif strict_production:
                blockers.append(f"D1 {id_field} must be replaced with the real Cloudflare UUID.")
            else:
                warnings.append(f"D1 {id_field} is still a placeholder.")

        routes = {route.get("pattern") for route in wrangler.get("routes", []) if route.get("custom_domain")}
        add_requirement(
            routes == {"workdoe.com", "www.workdoe.com"},
            checks,
            blockers,
            "Workdoe custom domains are configured",
            "Wrangler routes must include workdoe.com and www.workdoe.com as custom domains.",
        )
        add_requirement(
            wrangler.get("workers_dev") is False,
            checks,
            blockers,
            "workers.dev is disabled for production",
            "workers_dev must be false so production stays on workdoe.com.",
        )
        add_requirement(
            vars_map.get("WORKDOE_AUTH_PROVIDER") == "workdoe_email_code"
            and vars_map.get("WORKDOE_LOGIN_MODE") == "same_domain_email_code",
            checks,
            blockers,
            "Same-domain Workdoe email-code mode is configured",
            "WORKDOE_AUTH_PROVIDER must be workdoe_email_code and WORKDOE_LOGIN_MODE must be same_domain_email_code.",
        )
        add_requirement(
            vars_map.get("WORKDOE_PUBLIC_URL") == "https://workdoe.com"
            and vars_map.get("WORKDOE_DOMAIN") == "workdoe.com",
            checks,
            blockers,
            "Workdoe production URL vars point to workdoe.com",
            "WORKDOE_PUBLIC_URL and WORKDOE_DOMAIN must point to workdoe.com.",
        )
        r2 = (wrangler.get("r2_buckets") or [{}])[0]
        add_requirement(
            r2.get("binding") == "MEDIA" and r2.get("bucket_name") == "workdoe-media",
            checks,
            blockers,
            "Private R2 media bucket binding is configured",
            "R2 binding must be MEDIA for the workdoe-media bucket.",
        )
        producers = {
            producer.get("binding"): producer.get("queue")
            for producer in wrangler.get("queues", {}).get("producers", [])
        }
        consumers = {
            consumer.get("queue")
            for consumer in wrangler.get("queues", {}).get("consumers", [])
        }
        add_requirement(
            producers == REQUIRED_QUEUES
            and set(REQUIRED_QUEUES.values()).issubset(consumers),
            checks,
            blockers,
            "Email and media queues are configured as producers and consumers",
            "Wrangler queues must include workdoe-email and workdoe-media-review producers and consumers.",
        )
        add_requirement(
            set(wrangler.get("triggers", {}).get("crons", [])) == REQUIRED_CRONS,
            checks,
            blockers,
            "Cron automation schedule is configured",
            "Wrangler cron triggers do not match Workdoe automation.",
        )
        add_requirement(
            wrangler.get("send_email") == [
                {
                    "name": "EMAIL",
                    "allowed_sender_addresses": ["no-reply@workdoe.com"],
                }
            ],
            checks,
            blockers,
            "Cloudflare Email sender binding is restricted",
            "send_email must restrict EMAIL to no-reply@workdoe.com.",
        )
        required = set(wrangler.get("secrets", {}).get("required", []))
        add_requirement(
            required == REQUIRED_SECRETS,
            checks,
            blockers,
            "Required Turnstile and Workdoe secrets are declared",
            "Wrangler secrets.required must declare every required production secret.",
        )
        leaked = sorted(REQUIRED_SECRETS & set(vars_map))
        add_requirement(
            not leaked,
            checks,
            blockers,
            "Production secrets are not stored in vars",
            "Secret names must not be present in Wrangler vars: " + ", ".join(leaked),
        )
        if vars_map.get("WORKDOE_ADMIN_EMAIL") == "admin@workdoe.com":
            warnings.append("Confirm admin@workdoe.com is a real monitored inbox before launch.")

    worker_source = read_text(repo_root / "cloudflare" / "worker" / "entry.py")
    email_auth_source = read_text(repo_root / "cloudflare" / "worker" / "email_code_auth.py")
    worker_and_proxy_source = worker_source + "\n" + email_auth_source
    for marker, ok_name, blocker in (
        ("/api/auth/session", "Worker has session endpoint", "Worker is missing /api/auth/session."),
        ("/api/auth/code/request", "Worker has email-code request endpoint", "Worker is missing /api/auth/code/request."),
        ("/api/auth/code/verify", "Worker has email-code verification endpoint", "Worker is missing /api/auth/code/verify."),
        ("session_cookie", "Worker issues protected session cookies", "Worker is missing protected session cookies."),
        ("hash_code", "Worker protects stored sign-in codes", "Worker is missing code hashing."),
        ("entry_shell", "Worker has same-domain entry shell", "Worker is missing /login and /start same-domain entry handling."),
        ("app_shell", "Worker has authenticated app page shell", "Worker is missing authenticated post-login app page handling."),
        ("contractor_profile_page", "Worker has same-domain contractor profile page shell", "Worker is missing same-domain contractor profile page handling."),
        ("message_thread_detail_html", "Worker has same-domain message page shell", "Worker is missing same-domain message page handling."),
        ("admin_dashboard_html", "Worker has same-domain admin dashboard shell", "Worker is missing same-domain admin dashboard handling."),
        ("/api/jobs/open", "Worker has public jobs map API", "Worker is missing /api/jobs/open."),
        ("client_jobs", "Worker has client jobs dashboard API", "Worker is missing client jobs dashboard handling."),
        ("client_job_requests", "Worker has client mini-bid review API", "Worker is missing client mini-bid review handling."),
        ("contractor_leads", "Worker has contractor leads board API", "Worker is missing contractor leads board handling."),
        ("contractor_bids", "Worker has contractor mini-bid dashboard API", "Worker is missing contractor mini-bid dashboard handling."),
        ("job_detail", "Worker has privacy-safe job detail API", "Worker is missing signed-in job detail handling."),
        ("update_job_status", "Worker has client job status API", "Worker is missing client close/reopen handling."),
        ("contractor_profile_api", "Worker has contractor profile API", "Worker is missing contractor profile handling."),
        ("public_contractor_profile", "Worker has public contractor profile API", "Worker is missing public contractor profile handling."),
        ("create_job", "Worker has client job posting API", "Worker is missing client job posting handling."),
        ("create_match_request", "Worker has contractor mini-bid API", "Worker is missing contractor mini-bid handling."),
        ("decide_match_request", "Worker has client mini-bid decision API", "Worker is missing client mini-bid decision handling."),
        ("message_threads_api", "Worker has private approved-match messaging API", "Worker is missing private message thread handling."),
        ("create_report", "Worker has moderation report API", "Worker is missing moderation report handling."),
        ("admin_moderation_action", "Worker has admin moderation action API", "Worker is missing admin moderation action handling."),
        ("upload_private_media", "Worker has private R2 upload route", "Worker is missing private R2 upload handling."),
        ("private_media", "Worker has private R2 serving route", "Worker is missing private R2 serving handling."),
    ):
        add_requirement(marker in worker_and_proxy_source, checks, blockers, ok_name, blocker)

    env_values = parse_env_file(env_file)
    if env_file:
        required_env_values = REQUIRED_SECRETS | REQUIRED_PUBLIC_VARS
        missing = sorted(required_env_values - set(env_values))
        placeholders = sorted(
            key for key in required_env_values & set(env_values) if is_placeholder(env_values[key])
        )
        add_requirement(
            not missing,
            checks,
            blockers,
            "Provided env file contains all required auth config names",
            "Provided env file is missing required keys: " + ", ".join(missing),
        )
        add_requirement(
            not placeholders,
            checks,
            blockers,
            "Provided env file does not use placeholder auth config values",
            "Provided env file still has placeholder values for: " + ", ".join(placeholders),
        )
    else:
        warnings.append("No env file was provided; local Wrangler preview secret values were not checked.")

    secret_names = parse_secret_names(secret_list_json)
    if secret_list_json:
        secret_data = read_json(secret_list_json)
        missing_secret_names = sorted(REQUIRED_SECRETS - secret_names)
        add_requirement(
            not missing_secret_names,
            checks,
            blockers,
            "Cloudflare secret list contains every required secret name",
            "Cloudflare is missing required secret bindings: " + ", ".join(missing_secret_names),
        )
        if strict_production:
            add_requirement(
                isinstance(secret_data, dict) and secret_data.get("contains_values") is False,
                checks,
                blockers,
                "Cloudflare secret-name evidence is sanitized",
                "Cloudflare secret evidence must be sanitized with contains_values=false. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes`.",
            )
    elif strict_production:
        blockers.append(
            "Cloudflare secret presence is unverified. Run `python scripts\\cloudflare_secret_evidence.py --execute --yes` and pass --secret-list-json."
        )
    else:
        warnings.append("Cloudflare secret presence was not checked; pass --secret-list-json for deploy proof.")

    if clerk_proxy_proof_json:
        warnings.append("Clerk proxy proof was supplied but native Workdoe email-code auth does not use it.")

    return ReadinessResult(
        ready=not blockers,
        checks=checks,
        warnings=warnings,
        blockers=blockers,
        next_steps=next_steps,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether Workdoe Cloudflare/Clerk production launch inputs are ready."
    )
    parser.add_argument(
        "--strict-production",
        action="store_true",
        help="Treat placeholders and unverifiable Cloudflare secret state as launch blockers.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional local .dev.vars-style file to check for non-placeholder preview values.",
    )
    parser.add_argument(
        "--secret-list-json",
        type=Path,
        help="Optional sanitized JSON captured by scripts\\cloudflare_secret_evidence.py.",
    )
    parser.add_argument(
        "--clerk-proxy-proof-json",
        type=Path,
        help="Optional JSON proof that Clerk Domains uses https://workdoe.com/__clerk.",
    )
    args = parser.parse_args()
    result = run_readiness(
        strict_production=args.strict_production,
        env_file=args.env_file,
        secret_list_json=args.secret_list_json,
        clerk_proxy_proof_json=args.clerk_proxy_proof_json,
    )
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
