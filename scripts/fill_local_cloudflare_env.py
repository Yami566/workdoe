from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = REPO_ROOT / "cloudflare" / ".dev.vars"

REQUIRED_KEYS = [
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
    "CLOUDFLARE_ZONE_ID",
    "WORKDOE_ENV",
    "WORKDOE_AUTH_PROVIDER",
    "WORKDOE_DOMAIN",
    "WORKDOE_PUBLIC_URL",
    "WORKDOE_LOGIN_MODE",
    "WORKDOE_ENFORCE_SERVICE_ACTIVATION",
    "CLERK_FRONTEND_API_URL",
    "CLERK_PROXY_URL",
    "CLERK_FAPI",
    "CLERK_JWT_KEY",
    "CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
    "CLERK_WEBHOOK_SECRET",
    "WORKDOE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SECRET_KEY",
    "WORKDOE_TURNSTILE_SITE_KEY",
]

DEFAULTS = {
    "WORKDOE_ENV": "production",
    "WORKDOE_AUTH_PROVIDER": "clerk",
    "WORKDOE_DOMAIN": "workdoe.com",
    "WORKDOE_PUBLIC_URL": "https://workdoe.com",
    "WORKDOE_LOGIN_MODE": "same_domain_email_code",
    "WORKDOE_ENFORCE_SERVICE_ACTIVATION": "true",
    "CLERK_FRONTEND_API_URL": "https://workdoe.com/__clerk",
    "CLERK_PROXY_URL": "https://workdoe.com/__clerk",
    "CLERK_FAPI": "https://frontend-api.clerk.dev",
}

PLACEHOLDERS = {"", "replace-me", "changeme", "todo", "set-me", "<replace-me>", "<set-me>"}


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    normalized = str(value).strip().lower()
    return normalized in PLACEHOLDERS or normalized.startswith("<") and normalized.endswith(">")


def parse_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    lines = path.read_text(encoding="utf-8").splitlines()
    current_key: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_key, current_lines
        if current_key is not None:
            values[current_key] = "\n".join(current_lines).strip()
        current_key = None
        current_lines = []

    for raw in lines:
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if current_key is not None and re.match(r"^[A-Z0-9_]+\s*=", line):
            flush()
        if "=" in line:
            key_part, value_part = line.split("=", 1)
            key = key_part.strip()
            value = value_part.strip()
            if not value:
                current_key = key
                current_lines = []
            else:
                values[key] = value.strip()
                current_key = None
                current_lines = []
        elif current_key is not None:
            current_lines.append(stripped)

    flush()
    return values


def normalize_env_value(key: str, value: str) -> str:
    value = value.strip()
    if key == "CLERK_JWT_KEY":
        return value
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    return value


def build_env_map(existing: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        candidate = existing.get(key)
        if candidate is None:
            candidate = os.environ.get(key)
        if candidate is None:
            candidate = DEFAULTS.get(key, "replace-me")
        candidate = normalize_env_value(key, str(candidate))
        merged[key] = candidate
    return merged


def write_env_file(path: Path, values: dict[str, str]) -> None:
    lines = [
        "# Local-only Cloudflare / Workdoe secrets.",
        "# This file is intentionally ignored by git and should never be committed.",
        "# Replace the placeholder values with your real values before running local Wrangler checks.",
        "",
    ]
    for key in REQUIRED_KEYS:
        value = values.get(key, "replace-me")
        if key == "CLERK_JWT_KEY" and value and value != "replace-me":
            # keep PEM block readable in the file
            if "\n" not in value:
                lines.append(f"{key}={value}")
            else:
                lines.append(f"{key}={value}")
        else:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prompt_for_missing(values: dict[str, str]) -> dict[str, str]:
    result = values.copy()
    for key in REQUIRED_KEYS:
        current = result.get(key, "")
        if not is_placeholder(current):
            continue
        if key in os.environ and not is_placeholder(os.environ.get(key)):
            result[key] = os.environ[key]
            continue
        if key in DEFAULTS and not is_placeholder(DEFAULTS[key]):
            result[key] = DEFAULTS[key]
            continue
        if key == "CLERK_JWT_KEY":
            print(f"Enter value for {key} (paste full PEM block; press Enter on empty line to keep 'replace-me'):")
            text_lines: list[str] = []
            while True:
                line = input()
                if line == "":
                    break
                text_lines.append(line)
            entered = "\n".join(text_lines).strip()
            result[key] = entered or "replace-me"
        else:
            entered = input(f"Enter value for {key} (or press Enter to leave as 'replace-me'): ").strip()
            result[key] = entered or "replace-me"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate and normalize the local Cloudflare env file.")
    parser.add_argument("--path", type=Path, default=DEFAULT_ENV_PATH, help="Path to .dev.vars file.")
    parser.add_argument("--write", action="store_true", help="Write the updated file.")
    parser.add_argument("--check", action="store_true", help="Print which required values are still missing.")
    args = parser.parse_args()

    existing = parse_dotenv(args.path)
    merged = build_env_map(existing)
    prompted = prompt_for_missing(merged) if args.write else merged
    if args.check or not args.write:
        missing = [key for key in REQUIRED_KEYS if is_placeholder(prompted.get(key))]
        print("Missing or placeholder values:")
        for key in missing:
            print(f" - {key}")
        if not missing:
            print("All required keys are set.")
        return 0

    write_env_file(args.path, prompted)
    print(f"Updated {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
