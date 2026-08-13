from __future__ import annotations

import argparse
import json
import socket
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOMAIN = "workdoe.com"
DEFAULT_WWW_DOMAIN = "www.workdoe.com"
WRANGLER_CONFIG_PATH = REPO_ROOT / "cloudflare" / "wrangler.jsonc"
CLOUDFLARE_NS_SUFFIX = ".ns.cloudflare.com"


@dataclass
class DnsCheck:
    name: str
    status: str
    summary: str
    values: list[str] | None = None
    next_action: str = ""


def resolve_addresses(hostname: str) -> tuple[bool, list[str], str]:
    try:
        records = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        return False, [], str(exc)
    addresses = sorted({record[4][0] for record in records if record[4]})
    return bool(addresses), addresses, ""


def run_nslookup(domain: str, resolver: str = "1.1.1.1") -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["nslookup", "-type=ns", domain, resolver],
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=12,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = "\n".join(
        value for value in (completed.stdout, completed.stderr) if value
    ).strip()
    return completed.returncode == 0, output


def nameservers_from_nslookup(output: str) -> list[str]:
    nameservers: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if "nameserver =" in lowered:
            value = line.split("=", 1)[1].strip().rstrip(".").lower()
            if value:
                nameservers.add(value)
        elif lowered.startswith("nameserver:"):
            value = line.split(":", 1)[1].strip().rstrip(".").lower()
            if value:
                nameservers.add(value)
    return sorted(nameservers)


def cloudflare_nameserver_count(nameservers: list[str]) -> int:
    return sum(1 for name in nameservers if name.endswith(CLOUDFLARE_NS_SUFFIX))


def load_wrangler_routes(path: Path = WRANGLER_CONFIG_PATH) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("routes") or [])


def wrangler_custom_domains(
    path: Path = WRANGLER_CONFIG_PATH,
) -> tuple[bool, list[str], str]:
    try:
        routes = load_wrangler_routes(path)
    except (OSError, json.JSONDecodeError) as exc:
        return False, [], str(exc)
    domains = sorted(
        str(route.get("pattern", "")).strip()
        for route in routes
        if route.get("custom_domain") is True and str(route.get("pattern", "")).strip()
    )
    required = {DEFAULT_DOMAIN, DEFAULT_WWW_DOMAIN}
    return required.issubset(set(domains)), domains, ""


def build_dns_diagnostic(
    *,
    domain: str = DEFAULT_DOMAIN,
    www_domain: str = DEFAULT_WWW_DOMAIN,
    wrangler_path: Path = WRANGLER_CONFIG_PATH,
) -> dict:
    checks: list[DnsCheck] = []

    nslookup_ok, nslookup_output = run_nslookup(domain)
    nameservers = nameservers_from_nslookup(nslookup_output) if nslookup_ok else []
    cloudflare_count = cloudflare_nameserver_count(nameservers)
    if nameservers:
        ns_ready = cloudflare_count >= 2
        ns_summary = (
            f"{domain} is delegated to Cloudflare nameservers: {', '.join(nameservers)}."
            if ns_ready
            else f"{domain} nameservers are not fully Cloudflare: {', '.join(nameservers)}."
        )
    else:
        ns_ready = False
        ns_summary = f"Could not read public NS records for {domain}: {nslookup_output or 'no output'}"
    checks.append(
        DnsCheck(
            name="nameserver-delegation",
            status="ready" if ns_ready else "pending",
            summary=ns_summary,
            values=nameservers,
            next_action=(
                ""
                if ns_ready
                else "Confirm the exact Cloudflare-assigned nameservers on the domain Overview page and update the registrar if needed."
            ),
        )
    )

    apex_ok, apex_addresses, apex_error = resolve_addresses(domain)
    checks.append(
        DnsCheck(
            name="apex-resolution",
            status="ready" if apex_ok else "pending",
            summary=(
                f"{domain} resolves to {', '.join(apex_addresses)}."
                if apex_ok
                else f"{domain} does not resolve: {apex_error}"
            ),
            values=apex_addresses,
            next_action="" if apex_ok else "Deploy the Worker custom domain route and wait for DNS/certificate activation.",
        )
    )

    www_ok, www_addresses, www_error = resolve_addresses(www_domain)
    checks.append(
        DnsCheck(
            name="www-resolution",
            status="ready" if www_ok else "pending",
            summary=(
                f"{www_domain} resolves to {', '.join(www_addresses)}."
                if www_ok
                else f"{www_domain} does not resolve: {www_error}"
            ),
            values=www_addresses,
            next_action="" if www_ok else "Deploy the Worker custom domain route for www.workdoe.com or add the intended redirect record.",
        )
    )

    routes_ready, custom_domains, routes_error = wrangler_custom_domains(wrangler_path)
    checks.append(
        DnsCheck(
            name="wrangler-custom-domains",
            status="ready" if routes_ready else "pending",
            summary=(
                "Wrangler config includes custom_domain routes for workdoe.com and www.workdoe.com."
                if routes_ready
                else f"Wrangler custom-domain routes are incomplete: {routes_error or ', '.join(custom_domains)}"
            ),
            values=custom_domains,
            next_action="" if routes_ready else "Run python scripts\\prepare_cloudflare_release.py and review cloudflare\\wrangler.jsonc routes.",
        )
    )

    blockers = [
        check.summary
        for check in checks
        if check.status != "ready"
    ]
    next_actions = [
        check.next_action
        for check in checks
        if check.next_action
    ]
    if not blockers:
        next_actions.extend(
            [
                "npm run launch:doctor:live",
                "npm run github:deploy:plan",
                "npm run github:deploy",
                "npm run launch:smoke:strict",
            ]
        )
    return {
        "service": "workdoe",
        "domain": domain,
        "www_domain": www_domain,
        "ready": not blockers,
        "checks": [asdict(check) for check in checks],
        "blockers": blockers,
        "next_actions": sorted(set(next_actions)),
        "references": [
            "Cloudflare Workers Custom Domains require an active Cloudflare zone and a Worker to invoke.",
            "The checked-in Wrangler routes use custom_domain=true for workdoe.com and www.workdoe.com.",
        ],
    }


def render_text(payload: dict) -> str:
    lines = [
        "Workdoe DNS diagnostic",
        f"Domain: {payload['domain']}",
        f"Ready: {payload['ready']}",
        "",
        "Checks:",
    ]
    lines.extend(
        f"- {check['name']}: {check['status']} - {check['summary']}"
        for check in payload["checks"]
    )
    if payload["blockers"]:
        lines.extend(["", "Blockers:"])
        lines.extend(f"- {blocker}" for blocker in payload["blockers"])
    if payload["next_actions"]:
        lines.extend(["", "Next Actions:"])
        lines.extend(f"- {action}" for action in payload["next_actions"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose Workdoe DNS delegation, resolution, and Wrangler custom-domain readiness."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN, help="Apex domain.")
    parser.add_argument("--www-domain", default=DEFAULT_WWW_DOMAIN, help="www hostname.")
    parser.add_argument(
        "--wrangler-config",
        type=Path,
        default=WRANGLER_CONFIG_PATH,
        help="Wrangler JSONC config path.",
    )
    parser.add_argument(
        "--fail-when-not-ready",
        action="store_true",
        help="Exit nonzero when DNS is not ready.",
    )
    args = parser.parse_args()
    payload = build_dns_diagnostic(
        domain=args.domain,
        www_domain=args.www_domain,
        wrangler_path=args.wrangler_config,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.fail_when_not_ready and not payload["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
