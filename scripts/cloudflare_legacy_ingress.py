"""Read legacy Workdoe ingress without changing Cloudflare or invoking an auth flow."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from cloudflare_hosted_ingress import (
    API_ORIGIN,
    NoRedirectHandler,
    read_cloudflare_api,
    read_reviewed_workdoe_routes,
    read_reviewed_workdoe_zone,
    require_single_page,
    reviewed_ingress_account,
    reviewed_ingress_token,
    wrangler_oauth_access_token,
)
from workdoe_production_smoke import FetchResult, fetch_url, header_value

ROOT = Path(__file__).resolve().parents[1]
PAGES_HOST = "workdoe.pages.dev"
PAGES_ORIGIN = f"https://{PAGES_HOST}"
PAGES_ALIAS = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.workdoe\.pages\.dev")
ACCESS_TEAM = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.cloudflareaccess\.com")
ACCOUNT_SUBDOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
PAGES_PAGE_SIZE = 25
MAX_PAGES_ORIGINS = 12
CANONICAL_HOME = "https://workdoe.com/"
# All four reviewed entry points used these same files.
REVIEWED_PAGES_PATHS = ("/", "/assets/index-DVIRazpW.js", "/assets/index-gMLYGkSO.css")
VERIFIED_PAGES_OUTCOMES = {"canonical_root_redirect", "access_challenge"}


def reviewed_pages_alias(value: object) -> str:
    error = "Pages deployment metadata contains an unreviewed alias."
    if not isinstance(value, str) or len(value) > 300:
        raise ValueError(error)
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValueError(error) from exc
    if (
        parsed.scheme != "https" or not PAGES_ALIAS.fullmatch(parsed.netloc)
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        or value not in {f"https://{parsed.netloc}", f"https://{parsed.netloc}/"}
    ):
        raise ValueError(error)
    return f"https://{parsed.netloc}"


def reviewed_pages_origins(project: object, payload: dict) -> tuple[str, ...]:
    if (
        not isinstance(project, dict) or project.get("name") != "workdoe"
        or project.get("subdomain") != PAGES_HOST or project.get("domains") != [PAGES_HOST]
    ):
        raise ValueError("Pages did not confirm the exact reviewed Workdoe project and domain.")
    deployments = payload.get("result")
    info = payload.get("result_info")
    if (
        not isinstance(deployments, list) or not 1 <= len(deployments) < PAGES_PAGE_SIZE
        or not isinstance(info, dict) or not {"page", "count", "total_count", "total_pages"} <= info.keys()
    ):
        raise ValueError("Pages did not confirm a complete bounded deployment inventory.")
    require_single_page(payload, len(deployments), "Pages deployment")
    origins = {PAGES_ORIGIN}
    ids = set()
    for item in deployments:
        deployment_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(deployment_id, str) or not deployment_id or deployment_id in ids:
            raise ValueError("Pages returned incomplete or duplicate deployment identities.")
        ids.add(deployment_id)
        aliases = item.get("aliases")
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list) or len(aliases) >= MAX_PAGES_ORIGINS:
            raise ValueError("Pages deployment aliases could not be bounded.")
        origins.update(reviewed_pages_alias(value) for value in [item.get("url"), *aliases])
        if len(origins) > MAX_PAGES_ORIGINS:
            raise ValueError("Pages deployment aliases exceeded the probe limit.")
    for field in ("canonical_deployment", "latest_deployment"):
        deployment = project.get(field)
        if deployment is not None and (
            not isinstance(deployment, dict)
            or not isinstance(deployment.get("id"), str) or deployment["id"] not in ids
        ):
            raise ValueError("Pages project and deployment inventories do not agree.")
    return (PAGES_ORIGIN, *sorted(origins - {PAGES_ORIGIN}))


def pages_outcome(response: FetchResult, origin: str) -> str:
    status = response.status_code
    location = header_value(response.headers, "Location")
    if header_value(response.headers, "CF-Mitigated").lower() == "challenge" or status in {401, 403}:
        return "blocked_unverified"
    if 200 <= status < 300:
        return "public_response"
    if status in {301, 302, 303, 307, 308}:
        if location == CANONICAL_HOME:
            return "canonical_root_redirect"
        try:
            destination = urlsplit(location)
        except ValueError:
            return "unverified"
        if (
            destination.scheme == "https" and ACCESS_TEAM.fullmatch(destination.netloc)
            and destination.path == f"/cdn-cgi/access/login/{urlsplit(origin).netloc}"
            and not destination.fragment
        ):
            return "access_challenge"
    return "unverified"


def probe_pages(origins: tuple[str, ...]) -> tuple[Counter[str], Counter[str]]:
    roots: Counter[str] = Counter()
    assets: Counter[str] = Counter()
    for origin in origins:
        for path in REVIEWED_PAGES_PATHS:
            outcomes = roots if path == "/" else assets
            for method in ("HEAD", "GET"):
                result = fetch_url(origin + path, method=method, follow_redirects=False, body_limit=0)
                outcomes[pages_outcome(result, origin)] += 1
    return roots, assets


def worker_edge_outcome(response: FetchResult) -> str:
    mime = header_value(response.headers, "Content-Type").partition(";")[0].strip().lower()
    if header_value(response.headers, "CF-Mitigated").lower() == "challenge":
        return "unverified"
    if 200 <= response.status_code < 300 or (response.status_code == 404 and mime == "application/json"):
        return "application_response"
    if (
        response.status_code == 404 and mime == "text/plain"
        and header_value(response.headers, "Server").strip().lower() == "cloudflare"
        and header_value(response.headers, "CF-Ray").strip() and not header_value(response.headers, "Location")
        and not header_value(response.headers, "Age")
        and header_value(response.headers, "CF-Cache-Status").strip().upper() in {"", "DYNAMIC", "BYPASS"}
    ):
        return "disabled_edge_shape"
    return "unverified"


def probe_worker_defaults(opener, account_url: str, token: str) -> dict[str, dict[str, str]]:
    account = read_cloudflare_api(
        opener, f"{account_url}/workers/subdomain", token, description="reviewed account Workers subdomain",
    )["result"]
    subdomain = account.get("subdomain") if isinstance(account, dict) else None
    if not isinstance(subdomain, str) or not ACCOUNT_SUBDOMAIN.fullmatch(subdomain):
        raise ValueError("Cloudflare did not confirm a valid Workers subdomain for this account.")
    return {
        name: {
            method: worker_edge_outcome(fetch_url(
                f"https://{name}.{subdomain}.workers.dev/", method=method, follow_redirects=False, body_limit=0,
            )) for method in ("HEAD", "GET")
        } for name in ("workdoe", "workdoe-api")
    }


def legacy_ingress_readback(account_id: str, env: dict, *, oauth_token: str | None = None) -> dict:
    token = reviewed_ingress_token(account_id, env, oauth_token)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirectHandler())
    account_url = f"{API_ORIGIN}/accounts/{account_id}"
    zone = read_reviewed_workdoe_zone(opener, account_id, token)
    routes = read_reviewed_workdoe_routes(opener, zone, token)
    worker = read_cloudflare_api(
        opener, f"{account_url}/workers/scripts/workdoe-api/subdomain", token, description="legacy Worker URL flags",
    )["result"]
    if not isinstance(worker, dict) or any(type(worker.get(key)) is not bool for key in ("enabled", "previews_enabled")):
        raise ValueError("Cloudflare did not confirm both legacy Worker URL flags.")
    domains = read_cloudflare_api(
        opener, f"{account_url}/workers/domains?service=workdoe-api", token, description="legacy Worker custom domains",
    )
    records = domains["result"]
    if not isinstance(records, list) or any(
        not isinstance(item, dict) or item.get("service") != "workdoe-api" for item in records
    ):
        raise ValueError("Cloudflare did not confirm the legacy Worker custom-domain inventory.")
    require_single_page(domains, len(records), "legacy custom-domain")
    production = read_cloudflare_api(
        opener, f"{account_url}/workers/scripts/workdoe/subdomain", token, description="production Worker URL flags",
    )["result"]
    if not isinstance(production, dict) or production.get("enabled") is not False or production.get("previews_enabled") is not False:
        raise ValueError("The current Workdoe Worker is not a verified disabled-default control.")
    default_outcomes = probe_worker_defaults(opener, account_url, token)

    pages = f"{account_url}/pages/projects/workdoe"
    project = read_cloudflare_api(opener, pages, token, description="legacy Pages project")["result"]
    deployments = read_cloudflare_api(
        opener, f"{pages}/deployments?page=1&per_page={PAGES_PAGE_SIZE}", token, description="legacy Pages deployments",
    )
    origins = reviewed_pages_origins(project, deployments)
    roots, assets = probe_pages(origins)
    default_edges_consistent = all(
        result == "disabled_edge_shape" for outcomes in default_outcomes.values() for result in outcomes.values()
    )
    worker_default_matches_disabled = not worker["enabled"] and default_edges_consistent
    pages_samples_contained = (roots.keys() | assets.keys()) <= VERIFIED_PAGES_OUTCOMES
    return {
        "scope": "legacy_ingress_metadata_and_sampled_anonymous_edges",
        "readback_passed": not (
            not worker_default_matches_disabled or worker["previews_enabled"] or routes or records
            or not pages_samples_contained
        ),
        "legacy_worker_default_enabled": worker["enabled"],
        "legacy_worker_previews_enabled": worker["previews_enabled"],
        "legacy_worker_custom_domain_count": len(records),
        "legacy_zone_route_present": bool(routes),
        "worker_default_edge_outcomes": default_outcomes,
        "legacy_worker_default_matches_disabled": worker_default_matches_disabled,
        "worker_version_edges": "not_probed",
        "pages_origin_count": len(origins),
        "pages_root_probe_count": roots.total(),
        "pages_root_outcomes": dict(roots),
        "pages_asset_probe_count": assets.total(),
        "pages_asset_outcomes": dict(assets),
        "pages_samples_contained": pages_samples_contained,
        "authorized_access": "not_evaluated",
        "public_launch_approval": "not_evaluated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Run the read-only Cloudflare and Pages checks.")
    parser.add_argument("--allow-wrangler-oauth", action="store_true", help="Use an existing authorized Wrangler session.")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"dry_run": True, "requests_sent": False}))
        return 0
    env = os.environ.copy()
    try:
        account_id = reviewed_ingress_account(ROOT / "cloudflare", env)
        token = None
        if not env.get("CLOUDFLARE_API_TOKEN") and args.allow_wrangler_oauth:
            token = wrangler_oauth_access_token(ROOT, env)
        report = legacy_ingress_readback(account_id, env, oauth_token=token)
    except ValueError as exc:
        print(json.dumps({"readback_passed": False, "error": str(exc), "public_launch_approval": "not_evaluated"}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["readback_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
