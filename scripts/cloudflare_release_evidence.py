from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SECRET_LIST_PATH = REPO_ROOT / "cloudflare-secret-list.local.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_readiness import (  # noqa: E402
    DEFAULT_CLERK_PROXY_PROOF_PATH,
    REQUIRED_SECRETS,
    clerk_proxy_proof_error,
    read_json,
    secret_names_from_json,
)


def secret_evidence_error(path: Path | None) -> str:
    if not path:
        return (
            "Cloudflare secret evidence is unverified. Run "
            "`python scripts\\cloudflare_secret_evidence.py --execute --yes`."
        )
    data = read_json(path)
    if not isinstance(data, dict) or not data:
        return f"Cloudflare secret evidence JSON is missing or invalid: {path}"
    if data.get("contains_values") is not False:
        return "Cloudflare secret evidence must be sanitized with contains_values=false."
    names = secret_names_from_json(data)
    missing = sorted(REQUIRED_SECRETS - names)
    if missing:
        return "Cloudflare secret evidence is missing required names: " + ", ".join(missing)
    return ""


def run_release_evidence(
    secret_list_json: Path | None = DEFAULT_SECRET_LIST_PATH,
    clerk_proxy_proof_json: Path | None = DEFAULT_CLERK_PROXY_PROOF_PATH,
) -> dict:
    checks: list[str] = []
    blockers: list[str] = []
    secret_error = secret_evidence_error(secret_list_json)
    if secret_error:
        blockers.append(secret_error)
    else:
        checks.append("Sanitized Cloudflare secret-name evidence is valid")

    proxy_error = clerk_proxy_proof_error(clerk_proxy_proof_json)
    if proxy_error:
        blockers.append(proxy_error)
    else:
        checks.append("Same-domain Clerk proxy release proof is valid")

    return {
        "ok": not blockers,
        "checks": checks,
        "blockers": blockers,
        "secret_list_json": str(secret_list_json) if secret_list_json else "",
        "clerk_proxy_proof_json": str(clerk_proxy_proof_json) if clerk_proxy_proof_json else "",
        "next_steps": [
            "python scripts\\cloudflare_secret_evidence.py --execute --yes",
            "python scripts\\cloudflare_clerk_proxy_proof.py --confirm",
            "python scripts\\cloudflare_release_evidence.py --json",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Workdoe local Cloudflare launch evidence before strict production readiness."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--secret-list-json",
        type=Path,
        default=DEFAULT_SECRET_LIST_PATH,
        help="Sanitized JSON captured by scripts\\cloudflare_secret_evidence.py.",
    )
    parser.add_argument(
        "--clerk-proxy-proof-json",
        type=Path,
        default=DEFAULT_CLERK_PROXY_PROOF_PATH,
        help="JSON proof that Clerk Domains uses https://workdoe.com/__clerk.",
    )
    args = parser.parse_args()
    payload = run_release_evidence(
        secret_list_json=args.secret_list_json,
        clerk_proxy_proof_json=args.clerk_proxy_proof_json,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Workdoe Cloudflare release evidence")
        print(f"Ready: {payload['ok']}")
        for blocker in payload["blockers"]:
            print(f"- blocker: {blocker}")
        for check in payload["checks"]:
            print(f"- check: {check}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
