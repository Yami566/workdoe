from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
WRANGLER_ENV_VAR = "WORKDOE_WRANGLER_BIN"
WRANGLER_CONFIG_DIR = ".wrangler-config"
CLOUDFLARE_API_TOKEN_ENV_VAR = "CLOUDFLARE_API_TOKEN"
MAX_API_TOKEN_FILE_BYTES = 4096


def local_wrangler_candidates(repo_root: Path = REPO_ROOT) -> list[Path]:
    return [
        repo_root / "node_modules" / ".bin" / "wrangler.cmd",
        repo_root / "node_modules" / ".bin" / "wrangler",
        repo_root / "cloudflare" / "node_modules" / ".bin" / "wrangler.cmd",
        repo_root / "cloudflare" / "node_modules" / ".bin" / "wrangler",
    ]


def resolved_wrangler_bin(repo_root: Path = REPO_ROOT) -> str:
    explicit = os.environ.get(WRANGLER_ENV_VAR, "").strip()
    if explicit:
        return explicit
    for candidate in local_wrangler_candidates(repo_root):
        if candidate.exists():
            return str(candidate)
    return shutil.which("wrangler") or shutil.which("wrangler.cmd") or ""


def wrangler_available(repo_root: Path = REPO_ROOT) -> bool:
    return bool(resolved_wrangler_bin(repo_root))


def wrangler_command(args: list[str], repo_root: Path = REPO_ROOT) -> list[str]:
    return [resolved_wrangler_bin(repo_root) or "wrangler", *args]


def cloudflare_api_token_present(env: Mapping[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    return bool((values.get(CLOUDFLARE_API_TOKEN_ENV_VAR) or "").strip())


def cloudflare_api_token_from_file(path: Path) -> str:
    """Read one local-only deploy token without exposing its value in output."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_API_TOKEN_FILE_BYTES:
            raise ValueError
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("Cloudflare API token file is unavailable or invalid.") from exc

    values = [line for line in lines if line]
    if len(values) != 1 or any(character.isspace() for character in values[0]):
        raise ValueError("Cloudflare API token file is unavailable or invalid.")
    return values[0]


def cloudflare_api_token_error(action: str) -> str:
    return (
        f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is required to {action} in this "
        "non-interactive environment. Set it locally without committing it, "
        "or add it as the GitHub production environment secret before dispatching deploy."
    )


def wrangler_env(
    repo_root: Path = REPO_ROOT,
    api_token: str | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(repo_root / WRANGLER_CONFIG_DIR)
    if api_token:
        env[CLOUDFLARE_API_TOKEN_ENV_VAR] = api_token
    return env
