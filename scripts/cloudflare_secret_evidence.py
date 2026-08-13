from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CLOUDFLARE_DIR = REPO_ROOT / "cloudflare"
DEFAULT_SECRET_LIST_PATH = REPO_ROOT / "cloudflare-secret-list.local.json"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_readiness import REQUIRED_SECRETS, secret_names_from_json  # noqa: E402
from cloudflare_wrangler import wrangler_command, wrangler_env  # noqa: E402


class SecretEvidenceError(ValueError):
    pass


def run_external() -> subprocess.CompletedProcess:
    return subprocess.run(
        wrangler_command(["secret", "list", "--json"], REPO_ROOT),
        cwd=str(CLOUDFLARE_DIR),
        env=wrangler_env(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def json_from_streams(stdout: str, stderr: str) -> dict | list:
    for value in (stdout, stderr):
        stripped = (value or "").strip()
        if not stripped:
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue
    raise SecretEvidenceError("Could not find valid JSON from `wrangler secret list --json`.")


def sanitized_secret_evidence(data) -> dict:
    names = sorted(secret_names_from_json(data))
    return {
        "source": "wrangler secret list --json",
        "contains_values": False,
        "result": [{"name": name} for name in names],
    }


def missing_required_secrets(data) -> list[str]:
    return sorted(REQUIRED_SECRETS - secret_names_from_json(data))


def write_secret_evidence(path: Path, evidence: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dry_run_payload(output: Path) -> dict:
    return {
        "ok": True,
        "dry_run": True,
        "executes_commands": False,
        "writes": "",
        "output": str(output),
        "command": wrangler_command(["secret", "list", "--json"], REPO_ROOT),
        "required_secret_names": sorted(REQUIRED_SECRETS),
    }


def capture_secret_evidence(output: Path, allow_missing: bool = False) -> dict:
    try:
        completed = run_external()
    except OSError as exc:
        return {
            "ok": False,
            "dry_run": False,
            "executes_commands": True,
            "writes": "",
            "error": str(exc),
        }
    if completed.returncode != 0:
        return {
            "ok": False,
            "dry_run": False,
            "executes_commands": True,
            "writes": "",
            "error": (completed.stderr or completed.stdout or "wrangler secret list failed").strip(),
        }
    try:
        raw_data = json_from_streams(completed.stdout, completed.stderr)
        evidence = sanitized_secret_evidence(raw_data)
        missing = missing_required_secrets(raw_data)
        write_secret_evidence(output, evidence)
    except (OSError, SecretEvidenceError) as exc:
        return {
            "ok": False,
            "dry_run": False,
            "executes_commands": True,
            "writes": "",
            "error": str(exc),
        }
    return {
        "ok": allow_missing or not missing,
        "dry_run": False,
        "executes_commands": True,
        "writes": str(output),
        "missing_secret_names": missing,
        "secret_names": [item["name"] for item in evidence["result"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture non-secret Cloudflare Worker secret-name evidence for Workdoe deploy gates."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run `wrangler secret list --json` and write sanitized evidence.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required with --execute so Cloudflare account access is explicit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SECRET_LIST_PATH,
        help="Where to write sanitized non-secret secret-name evidence.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Write evidence even if required Workdoe secret names are missing.",
    )
    args = parser.parse_args()

    if not args.execute:
        payload = dry_run_payload(args.output)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("Workdoe Cloudflare secret evidence")
            print("Dry run: no Cloudflare command was executed.")
            print("Run with --execute --yes after setting Worker secrets.")
        return 0

    if not args.yes:
        payload = {
            "ok": False,
            "error": "--execute requires --yes so Cloudflare account access is explicit.",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2

    payload = capture_secret_evidence(args.output, allow_missing=args.allow_missing)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
