"""Read the production recovery seal without changing traffic, queues or data."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_hosted_ingress import (
    PRODUCTION_HOSTS,
    reviewed_ingress_account,
    verify_hosted_worker_ingress,
    wrangler_oauth_access_token,
)
from cloudflare_production_deploy import (
    WORKER_D1_BINDING_STEP,
    active_worker_deployment,
    read_worker_version_metadata,
)
from cloudflare_worker_recovery import (
    ZERO_UUID,
    reviewed_d1_database_id,
    valid_worker_version,
    verify_worker_d1_binding,
    verify_worker_media_binding,
    worker_version_metadata,
)
from cloudflare_wrangler import WRANGLER_ENV_VAR, local_wrangler_candidates
from prepare_cloudflare_release import PRODUCTION_MEDIA_BUCKET, REPO_ROOT
from workdoe_production_smoke import (
    CACHED_EDGE_STATUSES,
    FetchResult,
    cache_control_directives,
    fetch_url,
    header_value,
)

SEALED_PROBES = (
    ("/health", 200), ("/api/jobs/open", 503), ("/dashboard", 503),
    ("/media/jobs/0", 503), ("/__clerk/v1/environment", 503),
)


def verify_sealed_worker(metadata: dict) -> None:
    resources = metadata.get("resources")
    bindings = resources.get("bindings") if isinstance(resources, dict) else None
    if not isinstance(bindings, list) or not bindings or any(not isinstance(item, dict) for item in bindings):
        raise ValueError("Could not verify the reviewed production Worker bindings.")
    for name, value in {"WORKDOE_WRITE_MODE": "sealed", "WORKDOE_ENV": "production"}.items():
        rows = [item for item in bindings if item.get("name") == name]
        if len(rows) != 1 or rows[0].get("type") != "plain_text" or rows[0].get("text") != value:
            raise ValueError("The serving production Worker is not explicitly sealed; no restore was attempted.")


def sealed_response_matches(result: FetchResult, status: int) -> bool:
    headers = result.headers
    cache = cache_control_directives(result)
    return (
        result.status_code == status and header_value(headers, "X-Workdoe-Mode") == "sealed"
        and "no-store" in cache and "public" not in cache
        and not any(value.startswith(("max-age=", "s-maxage=")) for value in cache)
        and not header_value(headers, "Age")
        and header_value(headers, "CF-Cache-Status").strip().upper() not in CACHED_EDGE_STATUSES
        and not header_value(headers, "Set-Cookie") and not header_value(headers, "Location")
        and (status != 503 or header_value(headers, "Referrer-Policy").lower() == "no-referrer")
    )


def verify_sealed_public_responses() -> None:
    for host in sorted(PRODUCTION_HOSTS):
        for path, status in SEALED_PROBES:
            result = fetch_url(f"https://{host}{path}", method="HEAD", timeout=8, body_limit=0, follow_redirects=False)
            if not sealed_response_matches(result, status):
                raise ValueError(f"Workdoe did not confirm a fresh sealed response for {host}{path}.")


def recovery_readback(
    root: Path, env: Mapping[str, str], *, version: str, deployment: str, allow_wrangler_oauth: bool,
) -> dict:
    if any(not valid_worker_version(value) or value == ZERO_UUID for value in (version, deployment)):
        raise ValueError("Use the reviewed serving Worker version and deployment IDs.")
    account = reviewed_ingress_account(root / "cloudflare", env)
    if (env.get(WRANGLER_ENV_VAR) or os.environ.get(WRANGLER_ENV_VAR)
            or not any(path.is_file() for path in local_wrangler_candidates(root))):
        raise ValueError("Use the repository's pinned Wrangler installation without a CLI override.")
    command_env = {
        **env, "CI": "true", "WRANGLER_SEND_METRICS": "false", "WRANGLER_WRITE_LOGS": "false",
        "WRANGLER_LOG_SANITIZE": "true",
    }
    for name in ("WRANGLER_OUTPUT_FILE_PATH", "WRANGLER_OUTPUT_FILE_DIRECTORY"):
        command_env.pop(name, None)
    if not command_env.get("CLOUDFLARE_API_TOKEN") and not allow_wrangler_oauth:
        raise ValueError("Use a reviewed Cloudflare token or explicitly allow an existing Wrangler OAuth session.")
    expected = (version, deployment)
    if active_worker_deployment(root, command_env) != expected:
        raise ValueError("The serving deployment does not match the reviewed recovery deployment.")
    raw = read_worker_version_metadata(root, version, command_env, step_name=WORKER_D1_BINDING_STEP)
    metadata = worker_version_metadata(raw, version)
    verify_sealed_worker(metadata)
    verify_worker_d1_binding(metadata, reviewed_d1_database_id(root / "cloudflare"))
    verify_worker_media_binding(metadata, PRODUCTION_MEDIA_BUCKET)
    oauth = None if command_env.get("CLOUDFLARE_API_TOKEN") else wrangler_oauth_access_token(root, command_env)
    verify_hosted_worker_ingress(account, command_env, oauth_token=oauth, require_paused_queues=True)
    verify_sealed_public_responses()
    if active_worker_deployment(root, command_env) != expected:
        raise ValueError("The serving deployment changed during recovery verification.")
    return {
        "scope": "read_only_production_recovery_containment", "containment_observed": True,
        "worker_mode": "sealed", "queues_explicitly_paused": True,
        "in_flight_work_and_other_writers": "not_verified", "restore_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Read named production metadata and anonymous HEAD responses.")
    parser.add_argument("--expected-worker-version", help="Reviewed sealed Worker version ID.")
    parser.add_argument("--expected-deployment", help="Reviewed sealed deployment ID at 100 percent traffic.")
    parser.add_argument("--allow-wrangler-oauth", action="store_true", help="Use an existing authorized Wrangler session.")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"dry_run": True, "requests_sent": False, "restore_authorized": False}))
        return 0
    try:
        report = recovery_readback(
            REPO_ROOT, os.environ, version=args.expected_worker_version or "", deployment=args.expected_deployment or "",
            allow_wrangler_oauth=args.allow_wrangler_oauth,
        )
    except ValueError as error:
        print(json.dumps({"containment_observed": False, "restore_authorized": False, "error": str(error)}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
