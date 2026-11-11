from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_cloudflare_release import (
    REPO_ROOT,
    RESERVED_STAGING_D1_ID,
    RESERVED_STAGING_D1_NAME,
    REVIEWED_PRODUCTION_D1_ID,
    WRANGLER_RELATIVE_PATH,
    production_d1_ids,
    valid_d1_id,
)

STAGING_NAME = "workdoe-staging"
STAGING_HOST = "staging.workdoe.com"
STAGING_CONFIG = Path("cloudflare/wrangler.staging.local.json")
STAGING_MEDIA_BUCKET = "workdoe-staging-media"
STAGING_EMAIL_QUEUE = "workdoe-staging-email"
STAGING_MEDIA_QUEUE = "workdoe-staging-media-review"


def d1_inventory_id(inventory: object, name: str) -> str:
    if not isinstance(inventory, list) or any(not isinstance(item, dict) for item in inventory):
        raise ValueError("Expected the JSON array from Wrangler D1 inventory.")
    matches = [item for item in inventory if item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"Inventory must contain exactly one {name} database.")
    value = matches[0].get("uuid")
    if not isinstance(value, str) or not valid_d1_id(value):
        raise ValueError(f"Inventory has no valid UUID for {name}.")
    database_id = value.lower()
    if sum(str(item.get("uuid")).lower() == database_id for item in inventory) != 1:
        raise ValueError(f"Inventory has an ambiguous UUID for {name}.")
    return database_id


def reviewed_d1_ids(production: dict) -> tuple[str, str | None]:
    return production_d1_ids(production)


def sealed_staging_config(production: dict, inventory: object, *, use_reserved_preview: bool = False) -> dict:
    production_id, preview_id = reviewed_d1_ids(production)
    if d1_inventory_id(inventory, "workdoe") != production_id:
        raise ValueError("Inventory does not match the reviewed Workdoe production D1 ID.")
    database_name = RESERVED_STAGING_D1_NAME if use_reserved_preview else STAGING_NAME
    staging_id = d1_inventory_id(inventory, database_name)
    if use_reserved_preview:
        if (production_id != REVIEWED_PRODUCTION_D1_ID or preview_id is not None
                or staging_id != RESERVED_STAGING_D1_ID):
            raise ValueError("Reserved staging requires the exact reviewed identities and disabled production preview.")
        if any(row.get("name") == STAGING_NAME for row in inventory):
            raise ValueError("Reserved staging must not compete with another named staging database.")
    elif staging_id in {production_id, preview_id, RESERVED_STAGING_D1_ID}:
        raise ValueError("Staging D1 must not reuse a production or preview ID.")

    # Share build inputs, not production routes, bindings, variables or credentials.
    return {
        "$schema": "../node_modules/wrangler/config-schema.json",
        "name": STAGING_NAME,
        "main": "worker/entry.py",
        "compatibility_date": production["compatibility_date"],
        "compatibility_flags": production["compatibility_flags"],
        "assets": {
            "binding": "ASSETS",
            "directory": "../workdoe/static",
            "run_worker_first": True,
        },
        "workers_dev": False,
        "preview_urls": False,
        "routes": [],
        "triggers": {"crons": []},
        "d1_databases": [{
            "binding": "DB",
            "database_name": database_name,
            "database_id": staging_id,
            "migrations_dir": "d1/migrations",
        }],
        "r2_buckets": [{"binding": "MEDIA", "bucket_name": STAGING_MEDIA_BUCKET}],
        "queues": {
            "producers": [
                {"binding": "EMAIL_QUEUE", "queue": STAGING_EMAIL_QUEUE},
                {"binding": "MEDIA_QUEUE", "queue": STAGING_MEDIA_QUEUE},
            ],
            "consumers": [],
        },
        "vars": {
            "WORKDOE_ENV": "staging",
            "WORKDOE_DOMAIN": STAGING_HOST,
            "WORKDOE_PUBLIC_URL": f"https://{STAGING_HOST}",
            "WORKDOE_WRITE_MODE": "sealed",
            "WORKDOE_AUTH_PROVIDER": "clerk",
            "WORKDOE_MAP_MODE": "area",
            "WORKDOE_MEDIA_UPLOADS_ENABLED": "false",
        },
    }


def prepare(repo_root: Path, inventory_path: Path, *, check: bool, use_reserved_preview: bool = False) -> Path:
    production = json.loads((repo_root / WRANGLER_RELATIVE_PATH).read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    config = sealed_staging_config(production, inventory, use_reserved_preview=use_reserved_preview)
    expected = json.dumps(config, indent=2) + "\n"
    target = repo_root / STAGING_CONFIG
    if check:
        if target.read_text(encoding="utf-8") != expected:
            raise ValueError("Local staging config differs from the sealed configuration.")
    else:
        with target.open("x", encoding="utf-8", newline="\n") as output:
            output.write(expected)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a sealed Workdoe staging config locally.")
    parser.add_argument("--inventory", type=Path, required=True, help="Reviewed Wrangler D1 inventory JSON.")
    parser.add_argument("--check", action="store_true", help="Verify the existing config without writing.")
    parser.add_argument(
        "--use-reserved-preview", action="store_true",
        help="Use only the owner-reserved, exact Workdoe preview identity after disabling its production reference.",
    )
    args = parser.parse_args()
    try:
        prepare(REPO_ROOT, args.inventory, check=args.check, use_reserved_preview=args.use_reserved_preview)
    except FileExistsError:
        parser.exit(1, "Staging config already exists; use --check to verify it without overwriting.\n")
    except (json.JSONDecodeError, KeyError, OSError, TypeError, UnicodeError):
        parser.exit(1, "Could not read valid inventory, source config or local staging config.\n")
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(f"{'Verified' if args.check else 'Created'} {STAGING_CONFIG.as_posix()} locally. No remote checks or changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
