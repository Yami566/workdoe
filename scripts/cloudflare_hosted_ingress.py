"""Read production ingress, telemetry, media exposure, and queue routing without writes."""

from __future__ import annotations

import http.client
import json
import re
import subprocess
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlencode

from cloudflare_wrangler import MAX_API_TOKEN_FILE_BYTES, wrangler_command
from prepare_cloudflare_release import (
    PRODUCTION_EMAIL_QUEUE,
    PRODUCTION_MEDIA_BUCKET,
    PRODUCTION_MEDIA_QUEUE,
    PRODUCTION_QUEUE_CONSUMER_OPTIONS,
)
from workdoe_production_smoke import NoRedirectHandler

API_ORIGIN = "https://api.cloudflare.com/client/v4"
WORKER_NAME = "workdoe"
PRODUCTION_HOSTS = {"workdoe.com", "www.workdoe.com"}
REVIEWED_LEGACY_ROUTE = ("api.workdoe.com/*", "workdoe-api")
CLOUDFLARE_ID = re.compile(r"[0-9a-f]{32}")
MAX_RESPONSE_BYTES = 64 * 1024
READ_TIMEOUT = 10


def reviewed_ingress_account(cloudflare_dir: Path, env: Mapping[str, str]) -> str:
    account_id = env.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not CLOUDFLARE_ID.fullmatch(account_id):
        raise ValueError("Set CLOUDFLARE_ACCOUNT_ID to the reviewed production account ID.")
    try:
        config = json.loads((cloudflare_dir / "wrangler.jsonc").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Could not read the reviewed production Worker configuration.") from exc
    if (
        not isinstance(config, dict)
        or config.get("name") != WORKER_NAME
        or config.get("account_id", account_id) != account_id
        or config.get("compliance_region", "public") != "public"
    ):
        raise ValueError("The reviewed Worker configuration does not match the production ingress target.")
    if (
        any(env.get(name) for name in (
            "CLOUDFLARE_API_BASE_URL", "CF_API_BASE_URL", "CLOUDFLARE_BASE_URL",
            "CLOUDFLARE_API_KEY", "CF_API_KEY", "CF_API_TOKEN", "CLOUDFLARE_API_USER_SERVICE_KEY",
            "WRANGLER_CI_OVERRIDE_NAME", "CLOUDFLARE_ENV",
        ))
        or env.get("WRANGLER_API_ENVIRONMENT", "production") != "production"
        or env.get("CLOUDFLARE_COMPLIANCE_REGION", "public") != "public"
        or env.get("WRANGLER_CI_GENERATE_PREVIEW_ALIAS", "false") != "false"
    ):
        raise ValueError("Remove Wrangler target or preview overrides before verifying production ingress.")
    return account_id


def wrangler_oauth_access_token(repo_root: Path, env: Mapping[str, str]) -> str:
    # Use the documented CLI, not the credential store. Never forward its output.
    auth_env = {
        **env, "CI": "true", "WRANGLER_WRITE_LOGS": "false",
        "WRANGLER_SEND_METRICS": "false", "WRANGLER_LOG_SANITIZE": "true",
    }
    for name in ("WRANGLER_OUTPUT_FILE_PATH", "WRANGLER_OUTPUT_FILE_DIRECTORY"):
        auth_env.pop(name, None)
    error = "Could not verify the authorized Wrangler OAuth session for hosted ingress."
    try:
        completed = subprocess.run(
            wrangler_command(["auth", "token", "--json", "--config", "wrangler.jsonc"], repo_root),
            cwd=repo_root / "cloudflare", env=auth_env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", timeout=25, check=False,
        )
        if completed.returncode or len(completed.stdout) > MAX_API_TOKEN_FILE_BYTES * 2:
            raise ValueError
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise ValueError(error) from None
    if not isinstance(payload, dict) or payload.get("type") != "oauth" or not isinstance(payload.get("token"), str):
        raise ValueError(error)
    return payload["token"]


def read_cloudflare_api(
    opener, url: str, token: str, *, description: str = "Cloudflare Worker settings",
) -> dict:
    if not url.startswith(f"{API_ORIGIN}/"):
        raise ValueError("Cloudflare API reads require the official API origin.")
    request = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with opener.open(request, timeout=READ_TIMEOUT) as response:
            if response.status != 200:
                raise ValueError
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise ValueError(f"{description} returned HTTP {exc.code}.") from None
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise ValueError(f"Could not read {description}.") from exc
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(f"{description} exceeded the response limit.")
    try:
        payload = json.loads(body)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{description} were not valid JSON.") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True or "result" not in payload:
        raise ValueError(f"Cloudflare did not confirm the requested data: {description}.")
    return payload


def require_single_page(payload: dict, count: int, description: str) -> None:
    if "result_info" not in payload:
        return
    info = payload["result_info"]
    expected = {"count": count, "total_count": count, "page": 1, "total_pages": 1}
    if not isinstance(info, dict) or any(
        field in info and (type(info[field]) is not int or info[field] != value)
        for field, value in expected.items()
    ):
        raise ValueError(f"Cloudflare {description} results were incomplete or ambiguous.")


def _verify_worker_telemetry(settings: object, *, require_explicit_tail_list: bool) -> None:
    observability = settings.get("observability") if isinstance(settings, dict) else None
    if (not isinstance(observability, dict) or observability.get("enabled") is not True
            or observability.get("redact_query_string") is not True):
        raise ValueError("Cloudflare must confirm Workdoe observability and request query-string redaction are enabled.")
    if settings.get("logpush") is not False:
        raise ValueError("Cloudflare must confirm Workdoe Workers Logpush is disabled.")

    tails = settings.get("tail_consumers")
    # Script settings can omit this list; the second endpoint must confirm it is empty.
    if tails != [] and (require_explicit_tail_list or tails is not None):
        raise ValueError("Cloudflare must confirm no Workdoe Tail Worker consumers are configured.")

    for channel in ("logs", "traces"):
        options = observability.get(channel, {})
        if not isinstance(options, dict) or options.get("destinations", []) not in ([], ["cloudflare"]):
            raise ValueError("Cloudflare Workdoe logs and traces must not have unreviewed export destinations.")


def reviewed_ingress_token(account_id: str, env: Mapping[str, str], oauth_token: str | None) -> str:
    if not CLOUDFLARE_ID.fullmatch(account_id) or env.get("CLOUDFLARE_ACCOUNT_ID") != account_id:
        raise ValueError("Cloudflare ingress and Wrangler must use the same reviewed account.")
    token = env.get("CLOUDFLARE_API_TOKEN", "") if oauth_token is None else oauth_token
    if (not token or not token.isascii() or len(token) > MAX_API_TOKEN_FILE_BYTES
            or not token.isprintable() or any(char.isspace() for char in token)):
        raise ValueError("A valid Cloudflare credential is required to verify hosted ingress.")
    return token


def read_reviewed_workdoe_zone(opener, account_id: str, token: str) -> str:
    url = f"{API_ORIGIN}/accounts/{account_id}/workers/domains?{urlencode({'service': WORKER_NAME})}"
    payload = read_cloudflare_api(opener, url, token)
    domains = payload["result"]
    if not isinstance(domains, list) or len(domains) != len(PRODUCTION_HOSTS):
        raise ValueError("Cloudflare did not return exactly the two reviewed Workdoe custom domains.")
    require_single_page(payload, len(domains), "custom-domain")

    seen = set()
    zone_ids = set()
    for domain in domains:
        hostname = domain.get("hostname") if isinstance(domain, dict) else None
        if (
            not isinstance(hostname, str) or hostname not in PRODUCTION_HOSTS or hostname in seen
            or domain.get("service") != WORKER_NAME or domain.get("zone_name") != "workdoe.com"
            or domain.get("environment", "production") != "production"
            or domain.get("enabled") is not True or domain.get("previews_enabled") is not False
        ):
            raise ValueError("Cloudflare must confirm both reviewed Workdoe domains are enabled without preview routing.")
        seen.add(hostname)
        zone_id = domain.get("zone_id")
        if not isinstance(zone_id, str) or not CLOUDFLARE_ID.fullmatch(zone_id):
            raise ValueError("Cloudflare did not confirm the zone for both reviewed Workdoe domains.")
        zone_ids.add(zone_id)
    if len(zone_ids) != 1:
        raise ValueError("Cloudflare returned different zones for the reviewed Workdoe domains.")
    return zone_ids.pop()


def read_reviewed_workdoe_routes(opener, zone_id: str, token: str) -> list:
    route_payload = read_cloudflare_api(opener, f"{API_ORIGIN}/zones/{zone_id}/workers/routes", token)
    routes = route_payload["result"]
    # An exact allowlist avoids approximating Cloudflare wildcard and exclusion rules.
    if not isinstance(routes, list) or len(routes) > 1 or any(
        not isinstance(route, dict) or (route.get("pattern"), route.get("script")) != REVIEWED_LEGACY_ROUTE
        for route in routes
    ):
        raise ValueError("Cloudflare did not confirm the reviewed Worker routes in the Workdoe zone.")
    require_single_page(route_payload, len(routes), "zone Worker route")
    return routes


def read_r2_domain_state(opener, account_id: str, token: str, bucket: str) -> tuple[bool, int]:
    base = f"{API_ORIGIN}/accounts/{account_id}/r2/buckets/{bucket}/domains"
    managed = read_cloudflare_api(opener, f"{base}/managed", token, description="R2 development URL")["result"]
    if not isinstance(managed, dict) or type(managed.get("enabled")) is not bool:
        raise ValueError("Cloudflare did not confirm the R2 development URL state.")
    custom = read_cloudflare_api(opener, f"{base}/custom", token, description="R2 custom domains")
    result = custom["result"]
    if isinstance(result, dict) and isinstance(domains := result.get("domains"), list):
        require_single_page(custom, len(domains), "R2 custom-domain")
        return managed["enabled"], len(domains)
    raise ValueError("Cloudflare did not return an R2 custom-domain list.")


def reviewed_queue_consumer_id(consumer: object, name: str, queue_id: str, *, embedded: bool = False) -> str:
    if not isinstance(consumer, dict) or consumer.get("type") != "worker":
        raise ValueError(f"Workdoe queue {name} must use the reviewed Worker consumer.")
    # The live endpoint uses script; the public schema calls it script_name.
    worker_names = [consumer[key] for key in ("script", "script_name") if key in consumer]
    consumer_id = consumer.get("consumer_id")
    if (
        not worker_names or any(value != WORKER_NAME for value in worker_names)
        or consumer.get("queue_name", name if embedded else None) != name
        or consumer.get("queue_id", queue_id) != queue_id
        or not isinstance(consumer_id, str) or not CLOUDFLARE_ID.fullmatch(consumer_id)
    ):
        raise ValueError(f"Workdoe queue {name} did not confirm its reviewed consumer identity.")
    if consumer.get("dead_letter_queue") not in (None, ""):
        raise ValueError(f"Workdoe queue {name} has an unreviewed dead-letter destination.")
    settings = consumer.get("settings")
    expected = {
        "batch_size": PRODUCTION_QUEUE_CONSUMER_OPTIONS["max_batch_size"],
        "max_wait_time_ms": 1000 * PRODUCTION_QUEUE_CONSUMER_OPTIONS["max_batch_timeout"],
        "max_retries": PRODUCTION_QUEUE_CONSUMER_OPTIONS["max_retries"],
        "retry_delay": 0,
    }
    if not isinstance(settings, dict) or any(
        type(actual := settings.get(key, 0)) is not int or actual != value for key, value in expected.items()
    ):
        raise ValueError(f"Workdoe queue {name} consumer batch or retry settings differ from the reviewed configuration.")
    return consumer_id


def read_named_queue(opener, base: str, token: str, name: str) -> tuple[dict, str]:
    query = urlencode({"page": 1, "name": name})
    inventory = read_cloudflare_api(opener, f"{base}?{query}", token, description="named Workdoe queue")
    rows = inventory["result"]
    page = inventory.get("result_info")
    # total_count covers the entire account, not the filtered result.
    if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
            or rows[0].get("queue_name") != name or not isinstance(page, dict)
            or any(type(page.get(field)) is not int or page[field] != 1
                   for field in ("page", "count", "total_pages"))):
        raise ValueError(f"Could not verify one complete metadata result for Workdoe queue {name}.")
    queue = rows[0]
    queue_id = queue.get("queue_id")
    if not isinstance(queue_id, str) or not CLOUDFLARE_ID.fullmatch(queue_id):
        raise ValueError(f"Could not verify the distinct identity of Workdoe queue {name}.")
    return queue, queue_id


def verify_hosted_queue_routing(opener, account_id: str, token: str, *, require_paused: bool = False) -> None:
    base = f"{API_ORIGIN}/accounts/{account_id}/queues"
    seen = set()
    for name in (PRODUCTION_EMAIL_QUEUE, PRODUCTION_MEDIA_QUEUE):
        queue, queue_id = read_named_queue(opener, base, token, name)
        if queue_id in seen:
            raise ValueError(f"Could not verify the distinct identity of Workdoe queue {name}.")
        seen.add(queue_id)
        producers = queue.get("producers")
        consumers = queue.get("consumers")
        settings = queue.get("settings")
        if not isinstance(settings, dict) or settings.get("delivery_paused", False) is not require_paused:
            expected = "explicitly paused" if require_paused else "not paused"
            raise ValueError(f"Could not confirm Workdoe queue {name} delivery is {expected}.")
        if (
            type(queue.get("producers_total_count")) is not int or queue["producers_total_count"] != 1
            or not isinstance(producers, list) or len(producers) != 1 or not isinstance(producers[0], dict)
            or producers[0].get("type") != "worker" or producers[0].get("script") != WORKER_NAME
            or type(queue.get("consumers_total_count")) is not int or queue["consumers_total_count"] != 1
            or not isinstance(consumers, list) or len(consumers) != 1
        ):
            raise ValueError(f"Workdoe queue {name} does not have only the reviewed Worker producer and consumer.")
        listed_id = reviewed_queue_consumer_id(consumers[0], name, queue_id, embedded=True)
        direct = read_cloudflare_api(opener, f"{base}/{queue_id}/consumers", token, description="Workdoe queue consumers")
        consumers = direct["result"]
        if not isinstance(consumers, list) or len(consumers) != 1:
            raise ValueError(f"Workdoe queue {name} must have exactly one consumer.")
        require_single_page(direct, 1, "Workdoe queue consumer")
        if reviewed_queue_consumer_id(consumers[0], name, queue_id) != listed_id:
            raise ValueError(f"Workdoe queue {name} consumer metadata changed during verification.")


def verify_hosted_worker_ingress(
    account_id: str, env: Mapping[str, str], *, oauth_token: str | None = None, require_paused_queues: bool = False,
) -> None:
    """Require the reviewed ingress and managed-resource boundaries before release writes."""
    token = reviewed_ingress_token(account_id, env, oauth_token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler())
    script_base = f"{API_ORIGIN}/accounts/{account_id}/workers/scripts/{WORKER_NAME}"
    subdomain = read_cloudflare_api(opener, f"{script_base}/subdomain", token)["result"]
    if not isinstance(subdomain, dict) or subdomain.get("enabled") is not False or subdomain.get("previews_enabled") is not False:
        raise ValueError("Cloudflare must confirm both workers.dev and version previews are disabled.")

    zone_id = read_reviewed_workdoe_zone(opener, account_id, token)
    read_reviewed_workdoe_routes(opener, zone_id, token)

    # Uploaded versions and local config cannot prove non-versioned settings.
    for endpoint in ("script-settings", "settings"):
        settings = read_cloudflare_api(opener, f"{script_base}/{endpoint}", token)["result"]
        _verify_worker_telemetry(settings, require_explicit_tail_list=endpoint == "settings")

    r2_dev_enabled, r2_custom_domains = read_r2_domain_state(opener, account_id, token, PRODUCTION_MEDIA_BUCKET)
    if r2_dev_enabled or r2_custom_domains:
        raise ValueError("Workdoe R2 must have its development URL disabled and no attached custom domains.")

    verify_hosted_queue_routing(opener, account_id, token, require_paused=require_paused_queues)
