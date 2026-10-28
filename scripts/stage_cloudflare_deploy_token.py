from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cloudflare_wrangler import MAX_API_TOKEN_FILE_BYTES, cloudflare_api_token_from_file

DEFAULT_TOKEN_PATH = REPO_ROOT / "cloudflare" / ".deploy-token"


class TokenStagingError(ValueError):
    """Raised when an operator's local-only token cannot be staged safely."""


def validate_token(token: str) -> bytes:
    if not token or any(character.isspace() for character in token):
        raise TokenStagingError("Enter exactly one Cloudflare API token with no whitespace.")
    encoded = token.encode("utf-8")
    if len(encoded) > MAX_API_TOKEN_FILE_BYTES - 1:
        raise TokenStagingError("The Cloudflare API token is unexpectedly large.")
    return encoded


def stage_token(token: str, target: Path = DEFAULT_TOKEN_PATH, *, replace: bool = False) -> int:
    """Write a validated deploy token locally without returning or printing it."""
    encoded = validate_token(token)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not replace:
        raise TokenStagingError(
            f"{target} already exists. Re-run with --replace only after confirming it is safe to replace."
        )

    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if replace else os.O_EXCL)
    try:
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "wb") as token_file:
            token_file.write(encoded)
            token_file.write(b"\n")
        os.chmod(target, 0o600)
    except OSError as exc:
        raise TokenStagingError("The Cloudflare deploy token could not be staged locally.") from exc

    # Re-read through the production helper so the deployer accepts the staged value.
    cloudflare_api_token_from_file(target)
    return len(encoded)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage a local-only Cloudflare deploy token without displaying it."
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace an existing ignored cloudflare/.deploy-token file.",
    )
    args = parser.parse_args()

    try:
        token = getpass.getpass("Paste Cloudflare deploy token (input hidden): ")
        byte_count = stage_token(token, replace=args.replace)
    except (EOFError, KeyboardInterrupt):
        print("Token staging cancelled.")
        return 1
    except TokenStagingError as exc:
        print(f"Token staging failed: {exc}")
        return 1

    print(
        f"Cloudflare deploy token staged at {DEFAULT_TOKEN_PATH} ({byte_count} bytes). "
        "The token was not displayed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
