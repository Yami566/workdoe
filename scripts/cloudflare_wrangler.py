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


def cloudflare_api_token_error(action: str) -> str:
    return (
        f"{CLOUDFLARE_API_TOKEN_ENV_VAR} is required to {action} in this "
        "non-interactive environment. Set it locally without committing it, "
        "or add it as the GitHub production environment secret before dispatching deploy."
    )


def wrangler_env(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(repo_root / WRANGLER_CONFIG_DIR)
    return env
