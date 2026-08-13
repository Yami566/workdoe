from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_readiness import (  # noqa: E402
    CLERK_PROXY_PATH,
    DEFAULT_CLERK_PROXY_PROOF_PATH,
    WORKDOE_PUBLIC_DOMAIN,
    clerk_proxy_proof_error,
    valid_workdoe_clerk_proxy_url,
)


DEFAULT_PROXY_URL = f"https://{WORKDOE_PUBLIC_DOMAIN}{CLERK_PROXY_PATH}"


class ClerkProxyProofError(ValueError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_proof(
    domain: str = WORKDOE_PUBLIC_DOMAIN,
    proxy_url: str = DEFAULT_PROXY_URL,
    confirmed: bool = False,
    checked_by: str = "workdoe-operator",
    confirmed_at_utc: str | None = None,
) -> dict:
    normalized_domain = str(domain or "").strip().lower().rstrip(".")
    normalized_proxy_url = str(proxy_url or "").strip().rstrip("/")
    if normalized_domain != WORKDOE_PUBLIC_DOMAIN:
        raise ClerkProxyProofError("Clerk proxy proof domain must be workdoe.com.")
    if not valid_workdoe_clerk_proxy_url(normalized_proxy_url):
        raise ClerkProxyProofError("Clerk proxy proof must use https://workdoe.com/__clerk.")
    if confirmed is not True:
        raise ClerkProxyProofError(
            "Use --confirm only after Clerk Domains shows https://workdoe.com/__clerk."
        )
    return {
        "domain": normalized_domain,
        "frontend_api_proxy_url": normalized_proxy_url,
        "confirmed": True,
        "confirmed_at_utc": confirmed_at_utc or utc_now_iso(),
        "checked_by": str(checked_by or "workdoe-operator").strip() or "workdoe-operator",
    }


def write_proof(path: Path, proof: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dry_run_payload(output: Path, domain: str, proxy_url: str) -> dict:
    return {
        "ok": True,
        "dry_run": True,
        "executes_commands": False,
        "writes": "",
        "output": str(output),
        "domain": str(domain or "").strip(),
        "frontend_api_proxy_url": str(proxy_url or "").strip(),
        "next_step": (
            "Confirm Clerk Domains uses https://workdoe.com/__clerk, then rerun with --confirm."
        ),
    }


def confirmed_payload(output: Path, proof: dict) -> dict:
    proof_error = clerk_proxy_proof_error(output)
    return {
        "ok": not proof_error,
        "dry_run": False,
        "executes_commands": True,
        "writes": str(output),
        "proof": proof,
        "error": proof_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write non-secret proof that Clerk Domains uses the Workdoe same-domain proxy."
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Write the proof file after visually confirming Clerk Domains uses the Workdoe proxy URL.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_CLERK_PROXY_PROOF_PATH,
        help="Where to write the non-secret Clerk proxy proof JSON.",
    )
    parser.add_argument(
        "--domain",
        default=WORKDOE_PUBLIC_DOMAIN,
        help="Expected production domain. Must be workdoe.com.",
    )
    parser.add_argument(
        "--proxy-url",
        default=DEFAULT_PROXY_URL,
        help="Expected Clerk Frontend API proxy URL. Must be https://workdoe.com/__clerk.",
    )
    parser.add_argument(
        "--checked-by",
        default="workdoe-operator",
        help="Optional non-secret operator label for the proof record.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    if not args.confirm:
        payload = dry_run_payload(args.output, args.domain, args.proxy_url)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Workdoe Clerk proxy proof")
            print("Dry run: no proof file was written.")
            print(payload["next_step"])
        return 0

    try:
        proof = build_proof(
            domain=args.domain,
            proxy_url=args.proxy_url,
            confirmed=True,
            checked_by=args.checked_by,
        )
        write_proof(args.output, proof)
        payload = confirmed_payload(args.output, proof)
    except (OSError, ClerkProxyProofError) as exc:
        payload = {
            "ok": False,
            "dry_run": False,
            "executes_commands": False,
            "writes": "",
            "error": str(exc),
        }
    if args.json or not payload["ok"]:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Wrote Clerk proxy proof: {args.output}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
