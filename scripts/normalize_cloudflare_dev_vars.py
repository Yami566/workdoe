from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEV_VARS_PATH = REPO_ROOT / "cloudflare" / ".dev.vars"

KEY_ALIASES = {
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "CLERK_PUBLISHABLE_KEY",
    "WORKDOE_CLERK_LOGIN_MODE": "WORKDOE_LOGIN_MODE",
}

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


def read_current(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    current_key: str | None = None
    buffer: list[str] = []

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if current_key is not None and "=" not in stripped:
            buffer.append(stripped)
            continue

        if current_key is not None and buffer:
            values[current_key] = "\n".join(buffer).strip()
            current_key = None
            buffer = []

        if "=" in stripped:
            key_part, value_part = stripped.split("=", 1)
            key = key_part.strip()
            key = KEY_ALIASES.get(key, key)
            value = value_part.strip()
            if value:
                values[key] = value
                current_key = None
                buffer = []
                if key == "CLERK_JWT_KEY":
                    current_key = key
                    buffer = [value]
                    continue
            else:
                current_key = key
                buffer = []

    if current_key is not None and buffer:
        values[current_key] = "\n".join(buffer).strip()

    return values


def normalize_value(key: str, value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    if key == "CLERK_JWT_KEY":
        return value.replace("\n", "\\n")
    return value


def write_dev_vars(path: Path, values: dict[str, str]) -> None:
    lines = [
        "# Local-only Cloudflare / Workdoe secrets.",
        "# This file is intentionally ignored by git and should never be committed.",
        "# Replace the placeholder values with your real values before running local Wrangler checks.",
        "",
    ]

    for key in REQUIRED_KEYS:
        value = values.get(key, "replace-me")
        if value == "":
            value = "replace-me"
        if key == "CLERK_JWT_KEY" and value != "replace-me":
            value = value.replace("\\n", "\n")
            value = value.replace("\n", "\\n")
        lines.append(f"{key}={normalize_value(key, value)}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    current = read_current(DEV_VARS_PATH)
    write_dev_vars(DEV_VARS_PATH, current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
