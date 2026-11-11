from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

WORKER_VERSION_METADATA_MAX = 131_072
WORKER_DEPLOYMENT_STATUS_MAX = 65_536
WORKER_VERSION_LIST_LIMIT = 10
ZERO_UUID = "00000000-0000-0000-0000-000000000000"

def valid_worker_version(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def worker_deployment_status(status_json: str) -> dict:
    if len(status_json) > WORKER_DEPLOYMENT_STATUS_MAX:
        raise ValueError("Worker deployment status exceeds the evidence size limit.")
    try:
        payload = json.loads(status_json)
    except (ValueError, RecursionError) as exc:
        raise ValueError("Could not parse Worker deployment status.") from exc
    return payload if isinstance(payload, dict) else {}


def single_serving_version(payload: dict) -> str:
    versions = payload.get("versions")
    if not isinstance(versions, list) or len(versions) != 1:
        raise ValueError("Worker recovery requires one active version at 100% traffic.")
    version = versions[0]
    if not isinstance(version, dict) or version.get("percentage") != 100:
        raise ValueError("Worker recovery requires one active version at 100% traffic.")
    version_id = version.get("version_id")
    if not valid_worker_version(version_id) or version_id == ZERO_UUID:
        raise ValueError("Worker deployment status has no valid version ID.")
    return version_id


def single_active_worker_version(status_json: str) -> str:
    return single_serving_version(worker_deployment_status(status_json))


def single_active_worker_deployment(status_json: str) -> tuple[str, str]:
    payload = worker_deployment_status(status_json)
    version = single_serving_version(payload)
    deployment = payload.get("id")
    if not valid_worker_version(deployment) or deployment == ZERO_UUID:
        raise ValueError("Worker deployment status has no valid deployment ID.")
    return version, deployment


def worker_traffic_evidence(status_json: str) -> dict:
    version, deployment = single_active_worker_deployment(status_json)
    return {"id": deployment, "versions": [{"version_id": version, "percentage": 100}]}


def worker_receipt_records(receipt: str) -> list[dict]:
    try:
        records = [json.loads(line) for line in receipt.splitlines() if line.strip()]
    except ValueError as exc:
        raise ValueError("Wrangler deployment receipt is not valid NDJSON.") from exc
    if any(not isinstance(record, dict) or record.get("type") == "command-failed" for record in records):
        raise ValueError("Wrangler deployment receipt does not report success.")
    return records


def uploaded_worker_version(receipt: str, worker_name: str) -> str:
    records = worker_receipt_records(receipt)
    uploads = [record for record in records if record.get("type") == "version-upload"]
    if len(uploads) != 1 or any(record.get("type") in ("deploy", "version-deploy") for record in records):
        raise ValueError("Wrangler receipt must identify exactly one upload without a deployment.")
    upload = uploads[0]
    if upload.get("version") != 1 or upload.get("worker_name") != worker_name:
        raise ValueError("Wrangler upload receipt does not identify the expected Worker.")
    if any(upload.get(field) is not None for field in ("preview_url", "preview_alias_url")):
        raise ValueError("Wrangler reported an unexpected version preview URL; stop before activation.")
    version = upload.get("version_id")
    if not valid_worker_version(version):
        raise ValueError("Wrangler deployment receipt has no valid uploaded version ID.")
    return version


def activated_worker_deployment(receipt: str, worker_name: str) -> str:
    records = worker_receipt_records(receipt)
    changes = [record for record in records if record.get("type") in ("deploy", "version-deploy", "version-upload")]
    if len(changes) != 1 or changes[0].get("type") != "version-deploy":
        raise ValueError("Wrangler activation receipt must identify exactly one version deployment.")
    activation = changes[0]
    deployment = activation.get("deployment_id")
    if (
        activation.get("version") != 1 or activation.get("worker_name") != worker_name
        or not valid_worker_version(deployment) or deployment == ZERO_UUID
    ):
        raise ValueError("Wrangler activation receipt does not identify a valid Workdoe deployment.")
    return deployment


def worker_version_metadata(metadata: str, version: str) -> dict:
    if len(metadata) > WORKER_VERSION_METADATA_MAX:
        raise ValueError("Worker version metadata exceeds the evidence size limit.")
    try:
        payload = json.loads(metadata)
    except ValueError as exc:
        raise ValueError("Could not parse Worker version metadata.") from exc
    if not isinstance(payload, dict) or payload.get("id") != version:
        raise ValueError("Worker metadata does not identify the requested version.")
    return payload


def worker_version_number(metadata: dict) -> int:
    number = metadata.get("number")
    if type(number) is not int or number < 1:
        raise ValueError("Worker metadata does not identify a valid sequential version number.")
    return number


def latest_deployable_worker_version(version_list_json: str) -> tuple[str, int]:
    error = "Could not verify the latest deployable Worker version from Wrangler."
    if len(version_list_json) > WORKER_VERSION_METADATA_MAX:
        raise ValueError(error)
    try:
        versions = json.loads(version_list_json)
    except (ValueError, RecursionError) as exc:
        raise ValueError(error) from exc
    if not isinstance(versions, list) or not 1 <= len(versions) <= WORKER_VERSION_LIST_LIMIT:
        raise ValueError(error)
    versions_by_number = {}
    version_ids = set()
    for item in versions:
        version_id = item.get("id") if isinstance(item, dict) else None
        if not valid_worker_version(version_id) or version_id == ZERO_UUID or version_id in version_ids:
            raise ValueError(error)
        number = worker_version_number(item)
        if number in versions_by_number:
            raise ValueError(error)
        versions_by_number[number] = version_id
        version_ids.add(version_id)
    latest_number = max(versions_by_number)
    return versions_by_number[latest_number], latest_number


def verify_worker_commit_tag(metadata: str, version: str, commit: str) -> dict:
    payload = worker_version_metadata(metadata, version)
    annotations = payload.get("annotations")
    if not isinstance(annotations, dict) or annotations.get("workers/tag") != commit:
        raise ValueError("Uploaded Worker version tag does not match the full reviewed commit.")
    return payload


def canonical_d1_id(value: object) -> str | None:
    normalized = value.lower() if isinstance(value, str) else ""
    return normalized if normalized != ZERO_UUID and valid_worker_version(normalized) else None


def reviewed_d1_database_id(cloudflare_dir: Path) -> str:
    from prepare_cloudflare_release import production_d1_ids

    try:
        config = json.loads((cloudflare_dir / "wrangler.jsonc").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Could not read the reviewed production D1 configuration.") from exc
    databases = config.get("d1_databases") if isinstance(config, dict) else None
    if not isinstance(databases, list) or len(databases) != 1:
        raise ValueError("The reviewed config must identify exactly one production D1 database.")
    binding = databases[0]
    if not isinstance(binding, dict) or binding.get("binding") != "DB" or binding.get("database_name") != "workdoe":
        raise ValueError("The reviewed DB binding must name the workdoe database.")
    database_id, _preview_id = production_d1_ids(config)
    return database_id


def verify_worker_d1_binding(metadata: dict, database_id: str) -> None:
    resources = metadata.get("resources")
    bindings = resources.get("bindings") if isinstance(resources, dict) else None
    matches = [binding for binding in bindings if isinstance(binding, dict) and binding.get("name") == "DB"] if isinstance(bindings, list) else []
    if len(matches) != 1 or matches[0].get("type") != "d1":
        raise ValueError("Worker metadata must identify exactly one D1 DB binding.")
    if canonical_d1_id(matches[0].get("database_id")) != database_id:
        raise ValueError("Worker D1 binding does not match the reviewed production database.")


def verify_worker_media_binding(metadata: dict, bucket_name: str) -> None:
    resources = metadata.get("resources")
    bindings = resources.get("bindings") if isinstance(resources, dict) else None
    matches = [binding for binding in bindings if isinstance(binding, dict) and binding.get("name") == "MEDIA"] if isinstance(bindings, list) else []
    if (len(matches) != 1 or matches[0].get("type") != "r2_bucket"
            or matches[0].get("bucket_name") != bucket_name
            or matches[0].get("jurisdiction") not in (None, "default")):
        raise ValueError("Worker MEDIA binding does not match the reviewed production R2 bucket.")


def verify_worker_normal_write_mode(metadata: dict) -> None:
    resources = metadata.get("resources")
    bindings = resources.get("bindings") if isinstance(resources, dict) else None
    if not isinstance(bindings, list) or not bindings or any(
        not isinstance(binding, dict)
        or not isinstance(binding.get("name"), str)
        or not binding["name"]
        for binding in bindings
    ):
        raise ValueError("Could not verify the active Worker write mode from its bindings.")
    modes = [binding for binding in bindings if binding["name"] == "WORKDOE_WRITE_MODE"]
    # Workdoe defaults to normal only when the binding is absent.
    if modes and (
        len(modes) != 1 or modes[0].get("type") != "plain_text" or modes[0].get("text") != "normal"
    ):
        raise ValueError("Active Worker write mode is paused or unverified. Stop the routine release and review containment.")


def verify_uploaded_worker_configuration(metadata: dict, cloudflare_dir: Path) -> None:
    try:
        config = json.loads((cloudflare_dir / "wrangler.jsonc").read_text(encoding="utf-8"))
        expected = {
            config["assets"]["binding"]: {"type": "assets"},
            **{item["binding"]: {"type": "d1", "database_id": item["database_id"]} for item in config["d1_databases"]},
            **{name: {"type": "secret_text"} for name in config["secrets"]["required"]},
            **{name: {"type": "plain_text", "text": value} for name, value in config["vars"].items()},
        }
        for item in config["queues"]["producers"]:
            expected[item["binding"]] = {"type": "queue", "queue_name": item["queue"]}
        for item in config["r2_buckets"]:
            expected[item["binding"]] = {"type": "r2_bucket", "bucket_name": item["bucket_name"]}
        for item in config["ratelimits"]:
            expected[item["name"]] = {"type": "ratelimit", "namespace_id": item["namespace_id"], "simple": item["simple"]}
        for item in config["send_email"]:
            expected[item["name"]] = {
                "type": "send_email",
                **{field: item.get(field) for field in (
                    "allowed_sender_addresses", "allowed_destination_addresses", "destination_address",
                )},
            }
        date = config["compatibility_date"]
        flags = sorted(config["compatibility_flags"])
        worker_first = config["assets"]["run_worker_first"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Could not read the reviewed Worker binding and runtime configuration.") from exc

    verify_worker_resources(metadata, expected, date=date, flags=flags, worker_first=worker_first)


def verify_worker_resources(metadata: dict, expected: dict, *, date: str, flags: list[str], worker_first: bool) -> None:
    resources = metadata.get("resources")
    bindings = resources.get("bindings") if isinstance(resources, dict) else None
    actual = {}
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("Uploaded Worker is missing binding metadata.")
    for item in bindings:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or name not in expected or name in actual:
            raise ValueError("Uploaded Worker has an unexpected, invalid, or duplicate binding.")
        actual[name] = item
    for name, fields in expected.items():
        if name not in actual or any(actual[name].get(key) != value for key, value in fields.items()):
            raise ValueError(f"Uploaded Worker binding {name} does not match the reviewed configuration.")

    runtime = resources.get("script_runtime")
    runtime_flags = runtime.get("compatibility_flags", []) if isinstance(runtime, dict) else None
    if (
        not isinstance(runtime_flags, list) or any(not isinstance(flag, str) for flag in runtime_flags)
        or sorted(runtime_flags) != flags or runtime.get("compatibility_date") != date
    ):
        raise ValueError("Uploaded Worker runtime compatibility does not match the reviewed configuration.")
    assets = runtime.get("assets")
    # Workdoe requires the Worker to run before serving any static asset.
    if (worker_first is not True or not isinstance(assets, dict)
            or assets.get("raw_run_worker_first") is not True or assets.get("serve_directly") is not False):
        raise ValueError("Uploaded Worker asset routing does not match the reviewed configuration.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read one Workdoe Worker deployment from stdin.")
    parser.add_argument(
        "--traffic-evidence", action="store_true",
        help="Write only the validated deployment and serving version IDs and traffic share as JSON.",
    )
    args = parser.parse_args()
    try:
        payload = sys.stdin.read(WORKER_DEPLOYMENT_STATUS_MAX + 1)
        if args.traffic_evidence:
            print(json.dumps(worker_traffic_evidence(payload), sort_keys=True))
        else:
            print(single_active_worker_version(payload))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
