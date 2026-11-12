"""Read only the anonymous Clerk instance self-deletion flag."""

from __future__ import annotations

import argparse
import json

from workdoe_production_smoke import (
    CACHED_EDGE_STATUSES,
    CLERK_ENVIRONMENT_MAX_BYTES,
    CLERK_ENVIRONMENT_PATH,
    DEFAULT_BASE_URL,
    FetchResult,
    cache_control_directives,
    fetch_url,
    header_value,
)


def unique_members(pairs: list[tuple[str, object]]) -> dict:
    values = dict(pairs)
    if len(values) != len(pairs):
        raise ValueError("Ambiguous JSON response.")
    return values


def self_delete_state(response: FetchResult) -> str:
    content_type = header_value(response.headers, "Content-Type").partition(";")[0].strip().lower()
    if (
        response.status_code != 200
        or content_type != "application/json"
        or len(response.body_bytes) > CLERK_ENVIRONMENT_MAX_BYTES
        or "no-store" not in cache_control_directives(response)
        or header_value(response.headers, "Age")
        or header_value(response.headers, "CF-Cache-Status").strip().upper() in CACHED_EDGE_STATUSES
    ):
        return "unverified"
    try:
        settings = json.loads(response.body_bytes.decode("utf-8"), object_pairs_hook=unique_members)
        enabled = settings["user_settings"]["actions"]["delete_self"]
    except (KeyError, RecursionError, TypeError, ValueError):
        return "unverified"
    if enabled is True:
        return "enabled"
    if enabled is False:
        return "disabled"
    return "unverified"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Make one anonymous production GET.")
    parser.parse_args(argv)
    response = fetch_url(
        DEFAULT_BASE_URL + CLERK_ENVIRONMENT_PATH,
        method="GET",
        timeout=10,
        body_limit=CLERK_ENVIRONMENT_MAX_BYTES + 1,
        follow_redirects=False,
        binary=True,
    )
    state = self_delete_state(response)
    print(json.dumps({
        "http_status": response.status_code or None,
        "instance_self_delete": state,
        "scope": "public-instance-flag-only",
    }, sort_keys=True))
    return {"disabled": 0, "enabled": 1, "unverified": 2}[state]


if __name__ == "__main__":
    raise SystemExit(main())
