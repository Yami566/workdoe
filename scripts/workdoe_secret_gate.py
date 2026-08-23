from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / ".secrets.baseline"


def baseline_audit_error(baseline: Path) -> str:
    try:
        payload = json.loads(baseline.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return f"Secret baseline is unreadable or invalid JSON: {exc}"

    results = payload.get("results")
    if not isinstance(results, dict):
        return "Secret baseline results must be a JSON object."

    unaudited = 0
    confirmed_secrets = 0
    for findings in results.values():
        if not isinstance(findings, list):
            return "Secret baseline findings must be JSON arrays."
        for finding in findings:
            if not isinstance(finding, dict):
                return "Secret baseline findings must be JSON objects."
            verdict = finding.get("is_secret")
            if verdict is None:
                unaudited += 1
            elif verdict is True:
                confirmed_secrets += 1

    if confirmed_secrets:
        return (
            f"Secret baseline contains {confirmed_secrets} confirmed secret finding(s); "
            "remove the secret material before release."
        )
    if unaudited:
        return (
            f"Secret baseline contains {unaudited} unaudited finding(s). Run "
            f"`detect-secrets audit {baseline}` and review every item."
        )
    return ""


def repository_files(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or "git ls-files failed.")
    files = completed.stdout.decode("utf-8", errors="strict").split("\0")
    return sorted(
        path
        for path in files
        if path and Path(path).name != DEFAULT_BASELINE.name
    )


def run_gate(repo_root: Path, baseline: Path) -> dict:
    hook = shutil.which("detect-secrets-hook")
    if not hook:
        return {
            "ok": False,
            "error": (
                "detect-secrets-hook is not installed. Run "
                "python -m pip install -r requirements-audit.txt."
            ),
            "file_count": 0,
        }
    if not baseline.is_file():
        return {
            "ok": False,
            "error": f"Secret baseline is missing: {baseline}",
            "file_count": 0,
        }
    audit_error = baseline_audit_error(baseline)
    if audit_error:
        return {
            "ok": False,
            "error": audit_error,
            "file_count": 0,
        }

    files = repository_files(repo_root)
    completed = subprocess.run(
        [hook, "--baseline", str(baseline), *files],
        cwd=repo_root,
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )
    output = (completed.stdout + completed.stderr).strip()
    return {
        "ok": completed.returncode == 0,
        "error": "" if completed.returncode == 0 else output,
        "warnings": output.splitlines() if completed.returncode == 0 and output else [],
        "file_count": len(files),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check non-ignored Workdoe files against the reviewed secret baseline."
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="Reviewed detect-secrets baseline.",
    )
    args = parser.parse_args()
    payload = run_gate(REPO_ROOT, args.baseline.resolve())
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload["ok"]:
        print(f"Secret gate passed across {payload['file_count']} non-ignored files.")
    else:
        print(payload["error"], file=sys.stderr)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
