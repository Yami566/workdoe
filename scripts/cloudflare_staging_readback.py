"""Read only staging resource metadata for the reviewed Workdoe account."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlencode

from cloudflare_hosted_ingress import (
    API_ORIGIN,
    NoRedirectHandler,
    read_cloudflare_api,
    read_named_queue,
    read_r2_domain_state,
    read_reviewed_workdoe_routes,
    read_reviewed_workdoe_zone,
    require_single_page,
    reviewed_ingress_account,
    reviewed_ingress_token,
    wrangler_oauth_access_token,
)
from cloudflare_worker_recovery import (
    ZERO_UUID,
    single_active_worker_deployment,
    valid_worker_version,
    verify_worker_media_binding,
    verify_worker_resources,
)
from cloudflare_wrangler import (
    WRANGLER_ENV_VAR,
    local_wrangler_candidates,
    wrangler_command,
)
from prepare_cloudflare_release import REPO_ROOT, WRANGLER_RELATIVE_PATH, valid_d1_id
from prepare_cloudflare_staging import (
    STAGING_EMAIL_QUEUE,
    STAGING_HOST,
    STAGING_MEDIA_BUCKET,
    STAGING_MEDIA_QUEUE,
    STAGING_NAME,
    d1_inventory_id,
    reviewed_d1_ids,
    sealed_staging_config,
)


def read_d1_inventory(root: Path, env: Mapping[str, str]) -> object:
    # The pinned Wrangler command traverses all pages. Never print its raw output.
    command_env = {
        **env, "CI": "true", "WRANGLER_WRITE_LOGS": "false",
        "WRANGLER_SEND_METRICS": "false", "WRANGLER_LOG_SANITIZE": "true",
    }
    for name in ("WRANGLER_OUTPUT_FILE_PATH", "WRANGLER_OUTPUT_FILE_DIRECTORY"):
        command_env.pop(name, None)
    try:
        # The caller requires the local install and rejects executable overrides.
        result = subprocess.run(  # nosec B603
            wrangler_command(["d1", "list", "--json", "--config", "wrangler.jsonc"], root),
            cwd=root / "cloudflare", env=command_env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
        )
        if result.returncode or len(result.stdout) > 1024 * 1024:
            raise ValueError
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError, RecursionError):
        raise ValueError("Could not verify the account's Wrangler D1 inventory.") from None


def d1_readback(production: dict, inventory: object, *, use_reserved_preview: bool = False) -> dict:
    production_id, preview_id = reviewed_d1_ids(production)
    if (
        not isinstance(inventory, list)
        or any(not isinstance(row, dict) or not isinstance(row.get("name"), str)
               or not row["name"] or not isinstance(row.get("uuid"), str)
               or not valid_d1_id(row["uuid"]) for row in inventory)
    ):
        raise ValueError("Wrangler did not return valid D1 resource metadata.")
    if len({row["name"] for row in inventory}) != len(inventory) or len(
        {row["uuid"].lower() for row in inventory}
    ) != len(inventory):
        raise ValueError("Wrangler D1 inventory contains duplicate resource metadata.")
    if (d1_inventory_id(inventory, "workdoe") != production_id
            or (preview_id is not None and d1_inventory_id(inventory, "workdoe-preview") != preview_id)):
        raise ValueError("Wrangler D1 inventory does not match the reviewed production and preview IDs.")
    staging_present = any(row["name"] == STAGING_NAME for row in inventory)
    report = {"account_database_count": len(inventory), "dedicated_database_present": staging_present}
    if use_reserved_preview:
        sealed_staging_config(production, inventory, use_reserved_preview=True)
        report.update(selected_staging_database_present=True, staging_database_source="reserved_preview")
    return report


def inventory_names(payload: dict, key: str, label: str, *, paginated: bool = False) -> set[str]:
    rows = payload["result"]
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get(key), str) or not row[key] for row in rows
    ):
        raise ValueError(f"Cloudflare did not return valid {label} metadata.")
    if paginated and (not isinstance(payload.get("result_info"), dict)
                      or not {"page", "total_count"} <= payload["result_info"].keys()):
        raise ValueError(f"Cloudflare did not confirm complete {label} inventory.")
    require_single_page(payload, len(rows), label)
    names = {row[key] for row in rows}
    if len(names) != len(rows):
        raise ValueError(f"Cloudflare returned ambiguous {label} names.")
    return names


def cloudflare_readback(opener, account_id: str, token: str) -> dict:
    account_url = f"{API_ORIGIN}/accounts/{account_id}"

    def read(path: str, label: str) -> dict:
        return read_cloudflare_api(opener, account_url + path, token, description=label)

    queues = inventory_names(read("/queues", "queue inventory"), "queue_name", "queue", paginated=True)
    workers = inventory_names(read("/workers/scripts", "Worker inventory"), "id", "Worker")
    if "workdoe" not in workers:
        raise ValueError("Cloudflare did not confirm the reviewed production Worker in this account.")
    bucket_path = f"/r2/buckets/{STAGING_MEDIA_BUCKET}"
    bucket = read(bucket_path, "staging R2 bucket")["result"]
    if (not isinstance(bucket, dict) or bucket.get("name") != STAGING_MEDIA_BUCKET
            or bucket.get("storage_class") not in ("Standard", "InfrequentAccess")):
        raise ValueError("Cloudflare did not confirm the named staging R2 bucket and its storage class.")
    dev_enabled, custom_domains = read_r2_domain_state(opener, account_id, token, STAGING_MEDIA_BUCKET)
    return {
        "staging_bucket_standard": bucket["storage_class"] == "Standard",
        "staging_bucket_dev_url_disabled": not dev_enabled,
        "staging_bucket_custom_domain_count": custom_domains,
        "staging_email_queue_present": STAGING_EMAIL_QUEUE in queues,
        "staging_media_queue_present": STAGING_MEDIA_QUEUE in queues,
        "staging_worker_present": STAGING_NAME in workers,
    }


def verify_sealed_queue_routing(opener, account_url: str, token: str) -> None:
    base = f"{account_url}/queues"
    seen = set()
    for name in (STAGING_EMAIL_QUEUE, STAGING_MEDIA_QUEUE):
        queue, queue_id = read_named_queue(opener, base, token, name)
        producers = queue.get("producers")
        if (queue_id in seen or type(queue.get("producers_total_count")) is not int
                or queue["producers_total_count"] != 1 or not isinstance(producers, list) or len(producers) != 1
                or not isinstance(producers[0], dict) or producers[0].get("type") != "worker"
                or producers[0].get("script") != STAGING_NAME
                or type(queue.get("consumers_total_count")) is not int or queue["consumers_total_count"] != 0
                or queue.get("consumers") != []):
            raise ValueError(f"Staging queue {name} must have only the staging producer and no consumers.")
        seen.add(queue_id)
        payload = read_cloudflare_api(opener, f"{base}/{queue_id}/consumers", token, description="staging queue consumers")
        if payload["result"] != []:
            raise ValueError(f"Staging queue {name} must have no consumers.")
        require_single_page(payload, 0, "staging queue consumer")


def verify_sealed_staging_version(opener, account_id: str, token: str, *, version: str, config: dict) -> None:
    account_url = f"{API_ORIGIN}/accounts/{account_id}"
    script = f"/workers/scripts/{STAGING_NAME}"

    def read(path: str, label: str) -> dict:
        return read_cloudflare_api(opener, account_url + path, token, description=label)

    def serving() -> tuple[str, str]:
        result = read(f"{script}/deployments", "staging deployment metadata")["result"]
        deployments = result.get("deployments") if isinstance(result, dict) else None
        if not isinstance(deployments, list) or not deployments or not isinstance(deployments[0], dict):
            raise ValueError("Could not confirm an active staging deployment.")
        # The pinned Wrangler status command also uses the first deployment returned by this endpoint.
        return single_active_worker_deployment(json.dumps(deployments[0]))

    initial = serving()
    if initial[0] != version:
        raise ValueError("The reviewed staging version is not the sole serving version.")
    metadata = read(f"{script}/versions/{version}", "staging version metadata")["result"]
    if not isinstance(metadata, dict) or metadata.get("id") != version:
        raise ValueError("Cloudflare did not identify the reviewed staging version.")
    expected = {
        "ASSETS": {"type": "assets"},
        "DB": {"type": "d1", "database_id": config["d1_databases"][0]["database_id"]},
        "MEDIA": {"type": "r2_bucket", "bucket_name": STAGING_MEDIA_BUCKET},
        "EMAIL_QUEUE": {"type": "queue", "queue_name": STAGING_EMAIL_QUEUE},
        "MEDIA_QUEUE": {"type": "queue", "queue_name": STAGING_MEDIA_QUEUE},
        **{name: {"type": "plain_text", "text": value} for name, value in config["vars"].items()},
    }
    verify_worker_resources(
        metadata, expected, date=config["compatibility_date"], flags=sorted(config["compatibility_flags"]),
        worker_first=config["assets"]["run_worker_first"],
    )
    verify_worker_media_binding(metadata, STAGING_MEDIA_BUCKET)

    urls = read(f"{script}/subdomain", "staging alternate URL settings")["result"]
    if not isinstance(urls, dict) or urls.get("enabled") is not False or urls.get("previews_enabled") is not False:
        raise ValueError("Cloudflare must confirm staging workers.dev and version URLs are disabled.")
    for selector in ({"service": STAGING_NAME}, {"hostname": STAGING_HOST}):
        domains = read(f"/workers/domains?{urlencode(selector)}", "staging custom domains")
        if domains["result"] != []:
            raise ValueError("Sealed staging must have no attached custom domains.")
        require_single_page(domains, 0, "staging custom-domain")
    zone_id = read_reviewed_workdoe_zone(opener, account_id, token)
    read_reviewed_workdoe_routes(opener, zone_id, token)

    schedules = read(f"{script}/schedules", "staging cron schedules")["result"]
    if not isinstance(schedules, dict) or schedules.get("schedules") != []:
        raise ValueError("Cloudflare must confirm staging has no cron schedules.")
    verify_sealed_queue_routing(opener, account_url, token)
    if serving() != initial:
        raise ValueError("The serving staging deployment changed during verification.")


def staging_readback(
    root: Path, env: Mapping[str, str], *, allow_wrangler_oauth: bool, expected_sealed_version: str | None = None,
    use_reserved_preview: bool = False,
) -> dict:
    if expected_sealed_version is not None and (
        not valid_worker_version(expected_sealed_version) or expected_sealed_version == ZERO_UUID
    ):
        raise ValueError("Use the reviewed sealed staging Worker version UUID.")
    account_id = reviewed_ingress_account(root / "cloudflare", env)
    if env.get(WRANGLER_ENV_VAR) or not any(path.is_file() for path in local_wrangler_candidates(root)):
        raise ValueError("Use the repository's pinned Wrangler installation without a CLI override.")
    oauth = (wrangler_oauth_access_token(root, env)
             if allow_wrangler_oauth and not env.get("CLOUDFLARE_API_TOKEN") else None)
    token = reviewed_ingress_token(account_id, env, oauth)
    try:
        production = json.loads((root / WRANGLER_RELATIVE_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        raise ValueError("Could not verify the reviewed Workdoe D1 configuration.") from None
    inventory = read_d1_inventory(root, env)
    d1 = d1_readback(production, inventory, use_reserved_preview=use_reserved_preview)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler())
    resources = cloudflare_readback(opener, account_id, token)
    if expected_sealed_version is not None:
        if not (d1.get("selected_staging_database_present", d1["dedicated_database_present"])
                and resources["staging_worker_present"]
                and resources["staging_email_queue_present"] and resources["staging_media_queue_present"]):
            raise ValueError("The dedicated staging database, Worker and both queues must exist before seal verification.")
        if not (resources["staging_bucket_standard"] and resources["staging_bucket_dev_url_disabled"]
                and resources["staging_bucket_custom_domain_count"] == 0):
            raise ValueError("Sealed staging requires the private Standard R2 bucket without public URLs.")
        verify_sealed_staging_version(
            opener, account_id, token, version=expected_sealed_version,
            config=sealed_staging_config(production, inventory, use_reserved_preview=use_reserved_preview),
        )
    return {
        "scope": "read_only_named_staging_resource_metadata",
        "workers_plan": "not_verified",
        "data_contents": "not_checked",
        "hosted_acceptance": "not_checked",
        "staging_seal_metadata": "verified" if expected_sealed_version else "not_checked",
        **d1,
        **resources,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Query Cloudflare resource metadata without changes.")
    parser.add_argument("--allow-wrangler-oauth", action="store_true", help="Use an existing authorized Wrangler session.")
    parser.add_argument("--expected-sealed-version", help="Verify the reviewed serving sealed staging version UUID.")
    parser.add_argument("--use-reserved-preview", action="store_true", help="Select only the reviewed reserved staging D1 identity.")
    args = parser.parse_args()
    if args.expected_sealed_version is not None and not args.live:
        parser.error("--expected-sealed-version requires --live.")
    if not args.live:
        print(json.dumps({"dry_run": True, "requests_sent": False}))
        return 0
    try:
        report = staging_readback(
            REPO_ROOT, os.environ, allow_wrangler_oauth=args.allow_wrangler_oauth,
            expected_sealed_version=args.expected_sealed_version,
            use_reserved_preview=args.use_reserved_preview,
        )
    except ValueError as exc:
        print(json.dumps({"readback_passed": False, "error": str(exc)}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
