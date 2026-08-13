from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WRANGLER_PATH = REPO_ROOT / "cloudflare" / "wrangler.jsonc"
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class D1IdError(ValueError):
    pass


def normalized_uuid(value: str | None) -> str:
    match = UUID_RE.fullmatch(str(value or "").strip())
    if not match:
        raise D1IdError("D1 id must be a Cloudflare UUID.")
    normalized = match.group(0).lower()
    if normalized == ZERO_UUID:
        raise D1IdError("D1 id cannot be the placeholder UUID.")
    return normalized


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise D1IdError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise D1IdError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise D1IdError(f"{path} must contain a JSON object.")
    return data


def strings_from_json(value) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(strings_from_json(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(strings_from_json(item))
        return values
    return [str(value)] if value is not None else []


def d1_ids_from_capture(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise D1IdError(f"Missing D1 output capture: {path}") from exc
    candidates: list[str] = []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        candidates.extend(strings_from_json(parsed))
    candidates.append(text)

    found: list[str] = []
    for candidate in candidates:
        for match in UUID_RE.findall(candidate):
            normalized = match.lower()
            if normalized != ZERO_UUID and normalized not in found:
                found.append(normalized)
    if not found:
        raise D1IdError(f"No non-placeholder D1 UUID found in {path}.")
    return found


def first_d1_id_from_capture(path: Path) -> str:
    return d1_ids_from_capture(path)[0]


def apply_d1_ids(
    wrangler_path: Path = DEFAULT_WRANGLER_PATH,
    database_id: str | None = None,
    preview_database_id: str | None = None,
    from_file: Path | None = None,
    preview_from_file: Path | None = None,
    use_database_for_preview: bool = False,
    dry_run: bool = False,
) -> dict:
    if from_file and not database_id:
        database_id = first_d1_id_from_capture(from_file)
    if preview_from_file and not preview_database_id:
        preview_database_id = first_d1_id_from_capture(preview_from_file)
    if use_database_for_preview and not preview_database_id:
        preview_database_id = database_id

    normalized_database_id = normalized_uuid(database_id)
    normalized_preview_database_id = normalized_uuid(preview_database_id)
    wrangler = load_json(wrangler_path)
    d1_databases = wrangler.get("d1_databases")
    if not isinstance(d1_databases, list) or not d1_databases:
        raise D1IdError("wrangler.jsonc must contain a d1_databases binding.")
    d1 = d1_databases[0]
    if not isinstance(d1, dict):
        raise D1IdError("wrangler.jsonc d1_databases[0] must be an object.")
    if d1.get("binding") != "DB":
        raise D1IdError("Workdoe expects the first D1 binding to be DB.")

    before = {
        "database_id": d1.get("database_id", ""),
        "preview_database_id": d1.get("preview_database_id", ""),
    }
    d1["database_id"] = normalized_database_id
    d1["preview_database_id"] = normalized_preview_database_id
    after = {
        "database_id": d1["database_id"],
        "preview_database_id": d1["preview_database_id"],
    }
    changed = before != after
    if changed and not dry_run:
        wrangler_path.write_text(
            json.dumps(wrangler, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {
        "ok": True,
        "path": str(wrangler_path),
        "changed": changed,
        "dry_run": dry_run,
        "before": before,
        "after": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely apply real Cloudflare D1 IDs to Workdoe wrangler.jsonc."
    )
    parser.add_argument("--wrangler", type=Path, default=DEFAULT_WRANGLER_PATH)
    parser.add_argument("--database-id")
    parser.add_argument("--preview-database-id")
    parser.add_argument("--from-file", type=Path, help="Captured output from `wrangler d1 create workdoe`.")
    parser.add_argument(
        "--preview-from-file",
        type=Path,
        help="Captured output from a preview D1 create command.",
    )
    parser.add_argument(
        "--use-database-for-preview",
        action="store_true",
        help="Use the production D1 id as preview_database_id when a separate preview id is not supplied.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = apply_d1_ids(
            wrangler_path=args.wrangler,
            database_id=args.database_id,
            preview_database_id=args.preview_database_id,
            from_file=args.from_file,
            preview_from_file=args.preview_from_file,
            use_database_for_preview=args.use_database_for_preview,
            dry_run=args.dry_run,
        )
    except D1IdError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
