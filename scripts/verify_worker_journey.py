"""Exercise production route code against fresh local workerd/D1, never remote."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.cookiejar import CookieJar, DefaultCookiePolicy
from pathlib import Path
from urllib.parse import urlencode

from cloudflare_production_deploy import D1_STATE_SQL, d1_state_error
from cloudflare_recovery_readback import SEALED_PROBES, sealed_response_matches
from prepare_cloudflare_release import PRODUCTION_MAP_MODE
from workdoe_production_smoke import (
    ReviewedAreaMap,
    anonymous_private_routes_check,
    clerk_developer_file_check,
    discovery_files_check,
    fetch_url,
    public_map_snapshot_check,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "native_worker"
SEQUENCE_BACKUP_SQL = (
    "SELECT 'INSERT INTO sqlite_sequence(name,seq) VALUES(' || quote(name) || ',' || "
    "quote(seq) || ');' AS sql FROM sqlite_sequence "
    "WHERE name NOT GLOB '_cf_*' ORDER BY name"
)
MAX_SYNTHETIC_ACCOUNT_STATES = 1000
SYNTHETIC_ACCOUNT_SUBJECT = re.compile(r"user_native_[A-Za-z0-9_]{1,80}")
sys.path.insert(0, str(ROOT / "cloudflare" / "worker"))
try:
    from clerk_webhooks import svix_signature
    from map_tiles import AREA_MAP_ASSET
    from service_policy import SERVICE_POLICY_VERSION
finally:
    sys.path.remove(str(ROOT / "cloudflare" / "worker"))


@contextmanager
def native_workspace():
    parent = (ROOT / ".test-tmp").resolve()
    parent.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="native-journey-", dir=parent)).resolve()
    try:
        yield stage
    finally:
        if stage.parent != parent or not stage.name.startswith("native-journey-"):
            raise RuntimeError(
                "Refusing cleanup outside the isolated native workspace."
            )
        for attempt in range(30):
            try:
                shutil.rmtree(stage)
                break
            except PermissionError:
                if attempt == 29:
                    raise
                time.sleep(0.1)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def local_log_after_events(path: Path, expected: dict[str, int]) -> str:
    # Wrangler forwards local Worker logs independently of the HTTP response.
    deadline = time.monotonic() + 3
    while True:
        log = path.read_text(encoding="utf-8", errors="replace")
        if all(log.count(event) >= count for event, count in expected.items()) or time.monotonic() >= deadline:
            return log
        time.sleep(0.05)


@contextmanager
def local_worker(cli, config: Path, environment, port: int, log):
    process = subprocess.Popen(
        [
            *cli,
            "dev",
            "--local",
            "--ip",
            "127.0.0.1",
            "--port",
            str(port),
            "--config",
            str(config),
            "--persist-to",
            str(config.parent / ".wrangler" / "state"),
        ],
        cwd=config.parent,
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        yield process
    finally:
        if process.poll() is None:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                process.terminate()
        process.wait(timeout=15)


def wait_for_worker(process, read_health) -> None:
    deadline = time.monotonic() + 60
    while True:
        if process.poll() is not None:
            raise RuntimeError("Local Worker exited before readiness.")
        try:
            read_health()
            return
        except (OSError, urllib.error.URLError):
            if time.monotonic() >= deadline:
                raise RuntimeError("Local Worker did not become ready.") from None
            time.sleep(0.25)


def local_storage_arguments(args: list[str], config: Path) -> list[str]:
    allowed = any(
        args[: len(prefix)] == prefix
        for prefix in (
            ["d1", "migrations", "apply"],
            ["d1", "execute"],
            ["d1", "export"],
            ["r2", "object", "put"],
            ["r2", "object", "get"],
        )
    )
    owned_flags = {
        "--remote",
        "--config",
        "-c",
        "--cwd",
        "--env",
        "-e",
        "--env-file",
        "--profile",
        "--persist-to",
    }
    local_flags = [arg for arg in args if arg.split("=", 1)[0] == "--local"]
    if (
        not allowed
        or local_flags != ["--local"]
        or any(arg.split("=", 1)[0] in owned_flags for arg in args)
    ):
        raise ValueError(
            "The native harness only permits explicitly local storage commands."
        )
    result = [*args, "--config", str(config)]
    # Wrangler's local D1 exporter always uses this default; it has no persist-to option.
    if args[:2] != ["d1", "export"]:
        result.extend(["--persist-to", str(config.parent / ".wrangler" / "state")])
    return result


def canonical_digest(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def record_local_recovery(recovery: dict) -> Path:
    sources = [
        ROOT / "scripts" / "verify_worker_journey.py",
        *FIXTURES.glob("*.py"),
        *FIXTURES.glob("*.sql"),
        *FIXTURES.glob("*.cjs"),
        *(ROOT / "cloudflare" / "worker").rglob("*.py"),
        *(ROOT / "cloudflare" / "d1" / "migrations").glob("*.sql"),
    ]
    manifest = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sources
    }
    evidence = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "scope": "synthetic-local-only; no production restore or provider delivery",
        "source_manifest_sha256": canonical_digest(manifest),
        "source_files": manifest,
        "recovery": recovery,
    }
    output = ROOT / ".test-tmp" / "local-recovery-proof.local.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return output


def sql_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def storage_snapshot(command, config: Path) -> dict:
    def query(sql):
        results = json.loads(
            command(
                [
                    "d1",
                    "execute",
                    "native-journey",
                    "--local",
                    "--json",
                    "--command",
                    sql,
                ],
                config_path=config,
            )
        )
        require(
            all(item.get("success") for item in results), "Local snapshot query failed."
        )
        return [item["results"] for item in results]

    schema = query(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE sql IS NOT NULL AND name NOT GLOB 'sqlite_*' "
        "AND name NOT GLOB '_cf_*' ORDER BY type, name"
    )[0]
    tables = [item["name"] for item in schema if item["type"] == "table"]
    # Local schema identifiers cannot be bound; double-quote escaping is tested.
    selects = [
        f"SELECT * FROM {sql_identifier(name)}"  # nosec B608
        for name in tables
    ]
    results = query(
        ";".join(
            [
                *selects,
                "SELECT name, seq FROM sqlite_sequence WHERE name NOT GLOB '_cf_*' ORDER BY name",
                "PRAGMA quick_check",
                "PRAGMA foreign_key_check",
            ]
        )
    )
    require(len(results) == len(tables) + 3, "Local snapshot is incomplete.")
    require(results[-2] == [{"quick_check": "ok"}], "Local D1 quick_check failed.")
    require(not results[-1], "Local D1 contains foreign-key violations.")
    rows = {
        table: sorted(
            json.dumps(row, sort_keys=True, separators=(",", ":")) for row in data
        )
        for table, data in zip(tables, results[: len(tables)], strict=True)
    }
    return {"schema": schema, "rows": rows, "sequences": results[-3]}


def recovery_sql(
    schema: list[dict], data_dump: str, sequence_sql: list[str] | None = None
) -> str:
    require(
        all(item["type"] in {"table", "index", "view", "trigger"} for item in schema),
        "Recovery contains an unsupported schema object.",
    )
    early = [
        item["sql"] + ";"
        for kind in ("table", "index")
        for item in schema
        if item["type"] == kind
    ]
    late = [
        item["sql"] + ";"
        for kind in ("view", "trigger")
        for item in schema
        if item["type"] == kind
    ]
    return "\n".join(
        [
            "PRAGMA defer_foreign_keys = ON;",
            *early,
            "ANALYZE;",
            data_dump,
            *(
                ["DELETE FROM sqlite_sequence;", *sequence_sql]
                if sequence_sql is not None
                else []
            ),
            *late,
            "PRAGMA defer_foreign_keys = OFF;",
        ]
    )


def verify_local_recovery(command, stage: Path, config: Path) -> dict:
    require(
        config.parent.resolve() == stage.resolve(),
        "Recovery source is outside the isolated stage.",
    )
    settings = json.loads(config.read_text(encoding="utf-8"))
    require(
        settings.get("name") == "workdoe-native-journey-local-only"
        and settings.get("vars", {}).get("WORKDOE_ENV") == "local"
        and settings.get("d1_databases", [{}])[0].get("database_id")
        == "00000000-0000-4000-8000-000000000002",
        "Recovery must use the synthetic local fixture configuration.",
    )
    restored_root = stage / "restored"
    restored_root.mkdir()
    restored_config = restored_root / "wrangler.jsonc"
    settings["main"] = str(stage / "worker" / "journey_entry.py")
    restored_config.write_text(json.dumps(settings), encoding="utf-8")
    empty = json.loads(
        command(
            [
                "d1",
                "execute",
                "native-journey",
                "--local",
                "--json",
                "--command",
                (
                    "SELECT COUNT(*) AS tables FROM sqlite_schema WHERE type = 'table' "
                    "AND name NOT GLOB 'sqlite_*' AND name NOT GLOB '_cf_*'"
                ),
            ],
            config_path=restored_config,
        )
    )[0]["results"][0]
    require(empty["tables"] == 0, "Recovery destination is not a fresh independent D1.")
    source = storage_snapshot(command, config)
    dump = stage / "synthetic-recovery.sql"
    command(["d1", "export", "native-journey", "--local", "--output", str(dump)])
    require(dump.is_file() and dump.stat().st_size > 0, "Local export was not created.")
    data_dump = stage / "synthetic-data.sql"
    command(
        [
            "d1",
            "export",
            "native-journey",
            "--local",
            "--no-schema",
            "--output",
            str(data_dump),
        ]
    )
    sequence_results = json.loads(
        command(
            [
                "d1",
                "execute",
                "native-journey",
                "--local",
                "--json",
                "--command",
                SEQUENCE_BACKUP_SQL,
            ]
        )
    )[0]["results"]
    restore_plan = stage / "synthetic-restore.sql"
    with data_dump.open(encoding="utf-8", newline="") as exported_data:
        raw_data = exported_data.read()
    restore_plan.write_text(
        recovery_sql(
            source["schema"], raw_data, [row["sql"] for row in sequence_results]
        ),
        encoding="utf-8",
        newline="\n",
    )
    command(
        ["d1", "execute", "native-journey", "--local", "--file", str(restore_plan)],
        config_path=restored_config,
    )
    restored = storage_snapshot(command, restored_config)
    if source != restored:
        print(
            "LOCAL RECOVERY DIFFERENCE: "
            + json.dumps(
                {
                    "parts": [key for key in source if source[key] != restored[key]],
                    "tables": [
                        name
                        for name in source["rows"]
                        if source["rows"][name] != restored["rows"].get(name)
                    ],
                    "source_sequences": source["sequences"],
                    "restored_sequences": restored["sequences"],
                    "schema": [
                        {"source": before, "restored": after}
                        for before, after in zip(
                            source["schema"], restored["schema"], strict=False
                        )
                        if before != after
                    ][:3],
                },
                sort_keys=True,
            )
        )
    require(
        source == restored,
        "Restored D1 schema, data or ID sequences differ from the source.",
    )
    objects = []
    fixture_hash = hashlib.sha256(
        (ROOT / "workdoe" / "static" / "field-doe.webp").read_bytes()
    ).hexdigest()
    for index, key in enumerate(("jobs/1/native.webp", "contractors/2/native.webp")):
        backup = stage / f"media-backup-{index}.webp"
        recovered = stage / f"media-recovered-{index}.webp"
        command(
            [
                "r2",
                "object",
                "get",
                f"native-journey-media/{key}",
                "--local",
                "--file",
                str(backup),
            ]
        )
        require(
            hashlib.sha256(backup.read_bytes()).hexdigest() == fixture_hash,
            "R2 backup differs from the known synthetic image.",
        )
        command(
            [
                "r2",
                "object",
                "put",
                f"native-journey-media/{key}",
                "--local",
                "--file",
                str(backup),
                "--content-type",
                "image/webp",
            ],
            config_path=restored_config,
        )
        command(
            [
                "r2",
                "object",
                "get",
                f"native-journey-media/{key}",
                "--local",
                "--file",
                str(recovered),
            ],
            config_path=restored_config,
        )
        require(
            hashlib.sha256(recovered.read_bytes()).hexdigest() == fixture_hash,
            "Restored R2 bytes differ from the backup.",
        )
        objects.append(
            {"key": key, "sha256": fixture_hash, "size_bytes": recovered.stat().st_size}
        )
    return {
        "schema_objects": len(source["schema"]),
        "tables": len(source["rows"]),
        "migrations": len(source["rows"].get("d1_migrations", [])),
        "row_counts": {name: len(rows) for name, rows in source["rows"].items()},
        "snapshot_sha256": canonical_digest(source),
        "export_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
        "data_export_sha256": hashlib.sha256(data_dump.read_bytes()).hexdigest(),
        "restore_plan_sha256": hashlib.sha256(restore_plan.read_bytes()).hexdigest(),
        "media": objects,
    }


def verify_restored_containment(cli, stage, environment, request, command, *, thread_path, photo):
    config = stage / "restored" / "wrangler.jsonc"
    settings = json.loads(config.read_text(encoding="utf-8"))
    require(
        settings.get("name") == "workdoe-native-journey-local-only"
        and settings.get("vars", {}).get("WORKDOE_ENV") == "local"
        and settings.get("d1_databases", [{}])[0].get("database_id") == "00000000-0000-4000-8000-000000000002",
        "Containment verification requires the independent synthetic restore.",
    )
    command(
        ["d1", "execute", "native-journey", "--local", "--command", """
            INSERT INTO jobs (id, client_id, title, category, city, state, zip_code, description,
                              status, created_at, updated_at)
            VALUES (9111, 1, 'Synthetic recovery canary', 'Landscaping', 'Arlington', 'VA', '22201',
                    'Synthetic scope', 'open', '2000-01-01', '2000-01-01');
        """],
        config_path=config,
    )
    before = canonical_digest(storage_snapshot(command, config))
    public_path = "/api/jobs/open?q=Synthetic+recovery+canary"
    for mode, header in (("paused", "read-only"), ("sealed", "sealed")):
        settings["vars"]["WORKDOE_WRITE_MODE"] = mode
        config.write_text(json.dumps(settings), encoding="utf-8")
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        with (
            (stage / f"restored-{mode}-worker.log").open("w", encoding="utf-8") as log,
            local_worker(cli, config, environment, port, log) as process,
        ):
            wait_for_worker(process, lambda base_url=base: request("/health", base_url=base_url))
            _, health = request("/health", raw=True, base_url=base)
            require(health.get("X-Workdoe-Mode") == header, "Health did not report the applied recovery mode.")
            if mode == "paused":
                result = request(public_path, base_url=base)
                require(any(job["id"] == 9111 for job in result["jobs"]), "Read-only mode lost public browsing.")
            else:
                for path, status in SEALED_PROBES:
                    result = fetch_url(base + path, method="HEAD", timeout=5, body_limit=0, follow_redirects=False)
                    require(sealed_response_matches(result, status), f"Recovery readback rejected sealed HEAD {path}.")
                for path in (public_path, "/?job_id=9111"):
                    content, headers = request(path, raw=True, expected=503, base_url=base)
                    require(
                        headers.get("X-Workdoe-Mode") == "sealed" and headers.get("Cache-Control") == "no-store"
                        and b"Synthetic recovery canary" not in content and b"map-jobs-data" not in content,
                        "Sealed browsing returned restored content.",
                    )
                request("/api/auth/logout", actor="client", payload={}, expected=503, base_url=base)
            for path, options in (
                (thread_path, {"actor": "contractor"}),
                (photo, {"actor": "client", "method": "HEAD"}),
                ("/api/admin/jobs/9111/hide", {"actor": "admin", "payload": {}}),
                ("/__clerk/v1/environment", {}),
                ("/clerk/webhook", {"payload": {}}),
            ):
                content, headers = request(path, raw=True, expected=503, base_url=base, **options)
                require(
                    headers.get("X-Workdoe-Mode") == header and headers.get("Cache-Control") == "no-store"
                    and headers.get("Retry-After") == "900" and headers.get("Referrer-Policy") == "no-referrer"
                    and (options.get("method") != "HEAD" or not content),
                    "A protected recovery response missed its containment contract.",
                )
            request("/safety", raw=True, base_url=base)
            receipt = request("/__native/recovery-background", payload={}, base_url=base)
            require(receipt == {"acknowledged": [0, 0], "retried": [1, 1], "retry_delays": [900, 900]},
                    "A background handler acknowledged, lost, or incorrectly delayed a synthetic receipt.")
        require(canonical_digest(storage_snapshot(command, config)) == before,
                "A recovery mode modified the synthetic restored D1 snapshot.")


def synthetic_clerk_account_states(command, config: Path, *, restored: bool = False) -> list[dict]:
    settings = json.loads(config.read_text(encoding="utf-8"))
    values = settings.get("vars", {})
    require(
        settings.get("name") == "workdoe-native-journey-local-only" and values.get("WORKDOE_ENV") == "local"
        and settings.get("d1_databases", [{}])[0].get("database_id") == "00000000-0000-4000-8000-000000000002"
        and (not restored or values.get("WORKDOE_WRITE_MODE") == "sealed"),
        "Restriction comparison requires the isolated synthetic stores and a sealed restored copy.",
    )
    result = json.loads(command(
        ["d1", "execute", "native-journey", "--local", "--json", "--command",
         ("SELECT external_subject AS subject, status FROM users WHERE auth_provider = 'clerk' "
          "ORDER BY external_subject LIMIT 1001")], config_path=config,
    ))
    require(isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict)
            and result[0].get("success") is True and isinstance(result[0].get("results"), list),
            "Synthetic account projection did not complete.")
    return result[0]["results"]


def compare_synthetic_account_restrictions(current: list[dict], restored: list[dict]) -> dict[str, int]:
    # A per-drill key links the two projections without retaining provider subjects.
    key = secrets.token_bytes(32)

    def states(rows: list[dict]) -> dict[bytes, str]:
        require(isinstance(rows, list) and 0 < len(rows) <= MAX_SYNTHETIC_ACCOUNT_STATES,
                "Synthetic account projection is empty, incomplete, or over limit.")
        projected = {}
        for row in rows:
            require(isinstance(row, dict) and row.keys() == {"subject", "status"}
                    and isinstance(row["subject"], str) and SYNTHETIC_ACCOUNT_SUBJECT.fullmatch(row["subject"])
                    and row["status"] in ("active", "suspended"), "Invalid synthetic account projection.")
            identity = hmac.digest(key, row["subject"].encode("ascii"), "sha256")
            require(identity not in projected, "Duplicate synthetic account identity.")
            projected[identity] = row["status"]
        return projected

    source_states, restored_states = states(current), states(restored)
    source_suspended = {identity for identity, status in source_states.items() if status == "suspended"}
    restored_suspended = {identity for identity, status in restored_states.items() if status == "suspended"}
    return {
        "source_suspensions": len(source_suspended),
        "confirmed_suspended": len(source_suspended & restored_suspended),
        "restored_as_active": sum(restored_states.get(identity) == "active" for identity in source_suspended),
        "absent_from_restore": len(source_suspended - restored_states.keys()),
        "restore_only_suspensions": len(restored_suspended - source_suspended),
    }


def run_journey(
    *,
    verify_email_binding: bool = False,
    verify_recovery: bool = False,
    verify_candidate_browser: bool = False,
    verify_marketplace_email_pause: bool = False,
    area_map: bool = False,
) -> list[str]:
    if verify_email_binding and verify_marketplace_email_pause:
        raise ValueError("The marketplace email pause must be verified without a sender binding.")
    node = shutil.which("node")
    wrangler = ROOT / "node_modules" / "wrangler" / "bin" / "wrangler.js"
    if not node or not wrangler.is_file():
        raise RuntimeError(
            "Install the pinned npm dependencies before running this check."
        )
    browser_environment = {key: os.environ.get(key, "") for key in (
        "WORKDOE_PLAYWRIGHT_MODULE", "WORKDOE_CHROMIUM_EXECUTABLE",
    )}
    if verify_candidate_browser and not all(browser_environment.values()):
        raise RuntimeError("Provide the existing Playwright module and Chromium executable.")
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith(("CLOUDFLARE_", "CF_", "CLERK_", "WORKDOE_")):
            environment.pop(key)
    environment["WRANGLER_SEND_METRICS"] = "false"
    signed = json.loads(
        subprocess.check_output(
            [node, str(FIXTURES / "sign_fixtures.cjs")],
            env=environment,
            text=True,
        )
    )
    tokens = signed["tokens"]
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    checks: list[str] = []
    with native_workspace() as stage:
        environment["XDG_CONFIG_HOME"] = str(stage / "wrangler-config")
        shutil.copytree(ROOT / "cloudflare" / "worker", stage / "worker")
        shutil.copy2(
            FIXTURES / "journey_entry.py", stage / "worker" / "journey_entry.py"
        )
        (stage / "worker" / "fixture_jwks.py").write_text(
            f"ROTATION_JWK = {signed['rotation_jwk']!r}\n", encoding="utf-8",
        )
        webhook_secret = "whsec_" + base64.b64encode(os.urandom(32)).decode("ascii")  # pragma: allowlist secret - generated per-run local fixture material, not a hosted credential or committed key value.
        configuration = {
            "name": "workdoe-native-journey-local-only",
            "main": "worker/journey_entry.py",
            "workers_dev": False,
            "compatibility_date": "2026-08-23",
            "compatibility_flags": ["python_workers", "disable_python_external_sdk"],
            "assets": {
                "binding": "ASSETS",
                "directory": str(ROOT / "workdoe" / "static"),
                "run_worker_first": True,
            },
            "d1_databases": [
                {
                    "binding": "DB",
                    "database_name": "native-journey",
                    "database_id": "00000000-0000-4000-8000-000000000002",
                    "migrations_dir": str(ROOT / "cloudflare" / "d1" / "migrations"),
                }
            ],
            "r2_buckets": [{"binding": "MEDIA", "bucket_name": "native-journey-media"}],
            "ratelimits": [
                {
                    "name": "WRITE_RATE_LIMITER",
                    "namespace_id": "10002",
                    "simple": {"limit": 40, "period": 60},
                }
            ],
            "vars": {
                "WORKDOE_ENV": "local",
                "WORKDOE_AUTH_PROVIDER": "clerk",
                "WORKDOE_PUBLIC_URL": base,
                "WORKDOE_DOMAIN": "localhost",
                "WORKDOE_ENFORCE_SERVICE_ACTIVATION": "false",
                "WORKDOE_MEDIA_UPLOADS_ENABLED": "false",
                "WORKDOE_TURNSTILE_SECRET_KEY": "local-provider-fixture-only",  # pragma: allowlist secret - local stub, not a provider credential.
                "WORKDOE_SECRET_KEY": os.urandom(32).hex(),
                "CLERK_PUBLISHABLE_KEY": "pk_live_synthetic_fixture",
                "CLERK_SECRET_KEY": os.urandom(32).hex(),
                "CLERK_JWT_KEY": signed["public_key"],
                "CLERK_WEBHOOK_SECRET": webhook_secret,
            },
        }
        if area_map:
            release_vars = json.loads((ROOT / "cloudflare/wrangler.jsonc").read_text(encoding="utf-8"))["vars"]
            require(
                release_vars.get("WORKDOE_MAP_MODE") == PRODUCTION_MAP_MODE
                and not {"WORKDOE_MAP_TILE_URL", "WORKDOE_MAP_TILE_ATTRIBUTION"} & release_vars.keys(),
                "The reviewed release must select the area map without street tile settings.",
            )
            configuration["vars"]["WORKDOE_MAP_MODE"] = release_vars["WORKDOE_MAP_MODE"]
        if verify_marketplace_email_pause:
            configuration["vars"]["WORKDOE_NATIVE_EMAIL_PAUSE_FIXTURE"] = "1"
            configuration["queues"] = {
                "producers": [{"binding": "EMAIL_QUEUE", "queue": "workdoe-email", "remote": False}],
                "consumers": [{"queue": "workdoe-email", "max_batch_size": 5, "max_batch_timeout": 1}],
            }
        if verify_email_binding:
            configuration["send_email"] = [
                {
                    "name": "EMAIL",
                    "remote": False,
                    "allowed_sender_addresses": ["no-reply@workdoe.com"],
                    "allowed_destination_addresses": ["mailbox@example.invalid"],
                }
            ]
        config = stage / "wrangler.jsonc"
        config.write_text(json.dumps(configuration), encoding="utf-8")
        cli = [node, str(wrangler)]

        def command(args: list[str], *, config_path: Path = config) -> str:
            result = subprocess.run(
                [*cli, *local_storage_arguments(args, config_path)],
                cwd=config_path.parent,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            if result.returncode:
                raise RuntimeError(
                    f"Local Wrangler command failed: {result.stderr[-3000:]}"
                )
            return result.stdout

        command(["d1", "migrations", "apply", "native-journey", "--local"])
        ledger_command = [
            "d1", "execute", "native-journey", "--local", "--json", "--command", D1_STATE_SQL,
        ]
        ledger = subprocess.CompletedProcess(ledger_command, 0, command(ledger_command))
        ledger_error = d1_state_error(ROOT / "cloudflare", ledger)
        require(ledger_error is None, ledger_error or "")
        checks.append("native Wrangler D1 ledger and schema pass the reviewed release guard")
        command(
            [
                "d1",
                "execute",
                "native-journey",
                "--local",
                "--file",
                str(FIXTURES / "seed.sql"),
            ]
        )
        for key in ("jobs/1/native.webp", "contractors/2/native.webp"):
            command(
                [
                    "r2",
                    "object",
                    "put",
                    f"native-journey-media/{key}",
                    "--local",
                    "--file",
                    str(ROOT / "workdoe" / "static" / "field-doe.webp"),
                    "--content-type",
                    "image/webp",
                ]
            )
        with (
            (stage / "worker.log").open("w", encoding="utf-8") as log,
            local_worker(cli, config, environment, port, log) as process,
        ):
            try:
                local_http = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect()
                )

                def request(
                    path,
                    *,
                    actor=None,
                    payload=None,
                    expected=200,
                    marker=True,
                    method=None,
                    raw=False,
                    base_url=None,
                    extra_headers=None,
                    form_body=None,
                    cookie_opener=None,
                ):
                    headers = {"Accept": "application/json"}
                    headers.update(extra_headers or {})
                    if actor:
                        headers["Authorization"] = f"Bearer {tokens[actor]}"
                    if payload is not None:
                        headers["Content-Type"] = "application/json"
                        if marker:
                            headers["X-Workdoe-Request"] = "same-origin"
                    operation = urllib.request.Request(
                        (base_url or base) + path,
                        headers=headers,
                        data=json.dumps(payload).encode()
                        if payload is not None
                        else form_body,
                        method=method,
                    )
                    try:
                        response = (cookie_opener or local_http).open(operation, timeout=15)
                    except urllib.error.HTTPError as exc:
                        response = exc
                    with response:
                        raw_body = response.read(128 * 1024)
                        allowed = expected if isinstance(expected, tuple) else (expected,)
                        if response.status not in allowed:
                            raise AssertionError(
                                f"{path}: expected {expected}, got {response.status}: "
                                f"{raw_body[:4000].decode(errors='replace')}"
                            )
                        return (
                            (raw_body, response.headers if cookie_opener else dict(response.headers))
                            if raw
                            else json.loads(raw_body)
                        )

                def webhook(payload, *, valid=True):
                    message_id = f"msg_native_{time.time_ns()}"
                    timestamp = str(int(time.time()))
                    signature = svix_signature(
                        secret=webhook_secret, message_id=message_id,
                        timestamp=timestamp, raw_body=json.dumps(payload),
                    )
                    return request(
                        "/clerk/webhook", payload=payload, marker=False,
                        expected=202 if valid else 400,
                        extra_headers={
                            "svix-id": message_id, "svix-timestamp": timestamp,
                            "svix-signature": f"v1,{signature if valid else 'invalid'}",
                        },
                    )

                wait_for_worker(process, lambda: request("/health"))

                for route, actor in (
                    ("/?q=Arlington", None), ("/start", None), ("/login?next=/dashboard", None),
                    ("/login?embed=1", None), ("/create-account", None), ("/account", "client"),
                ):
                    for method in ("GET", "HEAD"):
                        body, headers = request(route, actor=actor, raw=True, method=method)
                        require(
                            headers.get("Referrer-Policy") == "strict-origin" and (method != "HEAD" or not body),
                            f"{route} did not preserve the Clerk referrer boundary on {method}.",
                        )
                checks.append("native public entry, embedded login and account send only origin referrers")

                if area_map:
                    reviewed = (ROOT / "workdoe/static" / AREA_MAP_ASSET.lstrip("/")).read_bytes()
                    for method in ("GET", "HEAD"):
                        body, headers = request(AREA_MAP_ASSET, raw=True, method=method)
                        headers = {key.lower(): value for key, value in headers.items()}
                        require(
                            body == (reviewed if method == "GET" else b"")
                            and headers.get("content-type") == "application/geo+json"
                            and headers.get("cache-control") == "public, max-age=31556952, immutable"
                            and headers.get("x-content-type-options") == "nosniff",
                            "Area map static bytes or delivery headers differ from the reviewed asset.",
                        )
                    for route, actor in (("/", None), ("/login", None), ("/leads", "contractor")):
                        body, headers = request(route, actor=actor, raw=True)
                        require(
                            f'data-tile-url="{AREA_MAP_ASSET}"'.encode() in body
                            and b"data-area-map-access" not in body
                            and "tile.openstreetmap.org" not in headers.get("Content-Security-Policy", ""),
                            f"{route} did not use the same-origin area map.",
                        )
                    body, _ = request("/login?embed=1", raw=True)
                    require(AREA_MAP_ASSET.encode() not in body, "Embedded login leaked the area map.")
                    missing, _ = request("/?job_id=7999", raw=True)
                    require(
                        b"<h2>Project not shown</h2>" in missing and b"Browse all projects" in missing
                        and b'data-project-detail-content data-job-id=' not in missing,
                        "An unavailable project link was replaced by a different project.",
                    )
                    login, _ = request("/login?job_id=7999", raw=True)
                    require(b'aria-label="Selected lead"' not in login, "Login named an unrelated project.")
                    ledger = json.loads((ROOT / "DEPENDENCY_PROVENANCE.json").read_text(encoding="utf-8"))
                    snapshot = public_map_snapshot_check(
                        base, 5, mode=PRODUCTION_MAP_MODE,
                        area_map=ReviewedAreaMap(AREA_MAP_ASSET, ledger["public_map_data"]["sha256"]),
                    )
                    require(snapshot.status == "ready", snapshot.summary)
                    checks.append("native area map: exact bytes, GET/HEAD headers, CSP and authenticated leads")

                notice_prefix = "/vendor/clerk-notices-v2/"
                terms, _ = request("/terms", raw=True)
                index, _ = request(notice_prefix + "notices-1", raw=True)
                require((notice_prefix + "notices-1").encode() in terms,
                        "Terms must link to the reviewed notice index.")
                for notice_name in (
                    "browser-tabs-lock-1.3.0-license.txt",
                    "tanstack-query-core-5.102.8-license.txt", "formkit-auto-animate-0.8.4-license.txt",
                    "stripe-sdk-license.txt", "zxcvbn-ts-3.0.4-license.txt",
                    "coinbase-eip712-isc-license.txt",
                    "input-otp-1.4.2-license.txt", "copy-to-clipboard-3.3.3-license.txt",
                    "qrcode-react-4.2.0-license.txt", "qrcode-generator-license.txt",
                    "core-js-3.47.0-license.txt", "crypto-js-4.2.0-license.txt",
                    "floating-ui-react-0.27.20-license.txt", "emotion-license.txt",
                ):
                    require(notice_name.encode() in index, f"The notice index must link to {notice_name}.")
                    body, headers = request(notice_prefix + notice_name, raw=True)
                    headers = {key.lower(): value for key, value in headers.items()}
                    reviewed_notice = ROOT / "workdoe/static/vendor/clerk-notices-v2" / notice_name
                    require(
                        body == reviewed_notice.read_bytes()
                        and headers.get("cache-control") == "no-store"
                        and headers.get("x-content-type-options") == "nosniff"
                        and headers.get("content-type", "").split(";", 1)[0] == "text/plain",
                        f"{notice_name} must retain its reviewed bytes and static delivery headers.",
                    )
                checks.append("native Terms and notice index serve the reviewed Clerk build notices")

                for suffix, cache in (("", "public, max-age=86400"), ("?probe=synthetic%2Bvalue", "no-store")):
                    body, headers = request(f"/static/styles.css{suffix}", method="HEAD", raw=True, expected=308)
                    headers = {key.lower(): value for key, value in headers.items()}
                    require(not body and headers.get("location") == f"{base}/styles.css{suffix}",
                            "Legacy asset redirect changed the destination or HEAD body.")
                    require(headers.get("cache-control") == cache and headers.get("referrer-policy") == "no-referrer",
                            "Legacy asset redirect did not preserve its query privacy boundary.")
                checks.append("native clean and query-bearing legacy asset redirect headers")

                proxy_headers = {"CF-Connecting-IP": "203.0.113.5"}
                for origin in (None, "https://workdoe.com", "https://www.workdoe.com", base):
                    extra_headers = proxy_headers if origin is None else proxy_headers | {"Origin": origin}
                    body, headers = request("/__clerk/v1/environment", raw=True, extra_headers=extra_headers)
                    require(
                        json.loads(body) == {"fixture": "clerk-environment"}
                        and headers.get("Access-Control-Allow-Origin") == origin,
                        "A reviewed Clerk request did not reach the provider fixture unchanged.",
                    )
                for method, origin in (
                    ("GET", "https://api.workdoe.com"),
                    ("HEAD", "https://outside.invalid"),
                    ("OPTIONS", "null"),
                    ("POST", "https://workdoe.com, https://www.workdoe.com"),
                ):
                    body, headers = request(
                        "/__clerk/v1/environment", method=method, expected=403, raw=True,
                        extra_headers=proxy_headers | {"Origin": origin},
                    )
                    require(
                        headers.get("Cache-Control") == "no-store"
                        and "Access-Control-Allow-Origin" not in headers
                        and "Access-Control-Allow-Credentials" not in headers
                        and (not body if method == "HEAD" else json.loads(body).get("ok") is False),
                        "An unreviewed browser origin passed the Clerk proxy boundary.",
                    )
                checks.append("native Clerk proxy blocks unreviewed browser origins before contacting the provider")
                forwarded = request(
                    "/__clerk/v1/client/sign_ins?fixture=a%2Fb",
                    payload={"fixture": True},
                    extra_headers=proxy_headers | {
                        "Cookie": (
                            "__client=fixture; workdoe_job_draft=fixture; __session=fixture; workdoe_session=fixture; "
                            "CF_Authorization=access-fixture; CF_AppSession=access-fixture; "
                            "combined=invalid, CF_Authorization=access-fixture"
                        ),
                        "Cf-Access-Jwt-Assertion": "access-fixture",
                    },
                )
                require(forwarded == {
                    "post": True, "query_preserved": True, "clerk_cookies_preserved": True,
                    "workdoe_cookie_forwarded": False, "access_cookie_forwarded": False, "access_header_forwarded": False,
                }, "Clerk proxy must preserve its credentials and query without Workdoe or Access credentials.")
                for path in (
                    "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.browser.js",
                    "/__clerk/npm/@clerk/ui@1.41.2/dist/signin_ui_e564da_1.41.2.js",
                    "/__clerk/npm/@clerk/ui@1.41.2/LICENSE",
                ):
                    media_type = "text/plain" if path.endswith("/LICENSE") else "application/javascript"
                    for method in ("GET", "HEAD"):
                        body, headers = request(path, method=method, raw=True, extra_headers=proxy_headers | {
                            "Accept-Encoding": "gzip", "If-None-Match": '"previous-version"', "Range": "bytes=0-5",
                        })
                        headers = {key.lower(): value for key, value in headers.items()}
                        if method == "GET" and headers.get("content-encoding") == "gzip":
                            body = gzip.decompress(body)
                        require(
                            body == (b"reviewed local asset fixture" if method == "GET" else b"")
                            and headers.get("content-type", "").startswith(media_type)
                            and "immutable" in headers.get("cache-control", "")
                            and headers.get("etag") == '"reviewed-local-asset"'
                            and "set-cookie" not in headers,
                            "Reviewed Clerk asset response lost the expected bytes or delivery headers.",
                        )
                    request(path, payload={"fixture": True}, expected=404, extra_headers=proxy_headers)
                for path in (
                    "/__clerk/npm/@clerk/clerk-js@6.40.0/dist/clerk.browser.js",
                    "/__clerk/npm/lodash@4.17.21/lodash.js",
                    "/__clerk/npm/@clerk/ui@1.41.2/package.json",
                ):
                    request(path, expected=404, extra_headers=proxy_headers)
                checks.append("native Clerk proxy strips Workdoe and Access credentials and serves reviewed package paths only")
                proxy_started = time.monotonic()
                for mode, status in (("stall", 504), ("transport", 502)):
                    body, headers = request(
                        f"/__clerk/v1/client?native-proxy-fault={mode}",
                        expected=status, raw=True, extra_headers=proxy_headers,
                        **({"payload": {"local_only": True}, "marker": False} if mode == "stall" else {}),
                    )
                    require(
                        json.loads(body) == {"ok": False, "error": "Sign-in is temporarily unavailable."}
                        and headers.get("Cache-Control") == "no-store",
                        "Clerk proxy exposed details or permitted caching for an upstream failure.",
                    )
                require(time.monotonic() - proxy_started < 5, "Clerk proxy exceeded its local fixture deadline.")
                proxy_log = local_log_after_events(stage / "worker.log", {
                    "NATIVE CLERK PROXY ABORTED": 1,
                    '"event": "clerk-proxy-upstream-failed"': 2,
                })
                require(
                    proxy_log.count("NATIVE CLERK PROXY ABORTED") == 1
                    and proxy_log.count('"event": "clerk-proxy-upstream-failed"') == 2
                    and "synthetic-clerk-transport-private-detail" not in proxy_log,
                    "Clerk proxy did not abort one stall and emit only the two redacted failure events.",
                )
                body, headers = request(
                    "/__clerk/v1/client?native-proxy-fault=stream", raw=True, extra_headers=proxy_headers,
                )
                require(
                    body == b"Synthetic streamed Clerk response."
                    and headers.get("Set-Cookie") == "__client=synthetic-clerk-cookie; Secure; HttpOnly",
                    "Clerk proxy changed the upstream cookie or interrupted a healthy streamed response.",
                )
                checks.append("native Clerk proxy aborts stalled headers, redacts transport failures and preserves streaming")
                package = "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.browser.js"
                for variant in ("html", "redirect", "scope", "revalidate"):
                    for method in ("GET", "HEAD"):
                        body, headers = request(
                            package + f"?native-package={variant}", method=method, expected=502, raw=True, extra_headers=proxy_headers,
                        )
                        require(
                            headers.get("Cache-Control") == "no-store" and headers.get("X-Content-Type-Options") == "nosniff"
                            and "Location" not in headers and "Service-Worker-Allowed" not in headers
                            and (not body if method == "HEAD" else json.loads(body).get("ok") is False)
                            and b"private-provider-fixture" not in body,
                            "An unsafe Clerk package response reached the browser.",
                        )
                for variant, expected in (("tamper", 502), ("short", 502), ("oversize", 502), ("stall-body", 504)):
                    body, headers = request(
                        package + f"?native-package={variant}", expected=expected, raw=True, extra_headers=proxy_headers,
                    )
                    require(
                        headers.get("Cache-Control") == "no-store"
                        and json.loads(body) == {"ok": False, "error": "Sign-in is temporarily unavailable."},
                        "Clerk package bytes were not verified before returning the response.",
                    )
                checks.append("native Clerk package responses enforce exact body, complete fetch and safe headers")
                for path in (
                    "/__clerk/npm/@clerk/ui@1.41.2/dist/contexts/AcceptedUserInvitations.js.map",
                    "/__clerk/npm/@clerk/ui@1.41.2/dist/composed/UserProfile/Account.d.ts",
                    "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/types/core/resources/APIKey.d.ts",
                    "/__clerk/npm/@clerk/ui@1.41.2/dist/server.js",
                    "/__clerk/npm/@clerk/ui@1.41.2/dist/common/DevOnly.js",
                    "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.native.js",
                    "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.mjs",
                ):
                    for method in ("GET", "HEAD"):
                        body, headers = request(path, method=method, expected=404, raw=True, extra_headers=proxy_headers)
                        require(
                            headers.get("Cache-Control") == "no-store"
                            and headers.get("Content-Type", "").startswith("application/json")
                            and (not body if method == "HEAD" else json.loads(body).get("ok") is False),
                            "A non-browser Clerk file passed the proxy boundary.",
                        )
                developer_files = clerk_developer_file_check(base, 5)
                require(developer_files.status == "ready", developer_files.summary)
                checks.append("native Clerk proxy denies source maps and declarations without changing browser chunks")

                request("/api/client/jobs", expected=401)
                request("/api/client/jobs", actor="contractor", expected=403)
                request("/api/client/jobs", actor="client")
                for path, actor, label in (
                    ("/client/dashboard", "contractor", "consumer"),
                    ("/contractor/dashboard", "client", "contractor"),
                ):
                    body, headers = request(path, actor=actor, expected=403, raw=True)
                    assert headers.get("Cache-Control") == "no-store"
                    assert f"Use a {label} account".encode() in body
                    assert b'href="/dashboard">Open my workspace</a>' in body
                    assert b'data-json-action="/api/auth/logout"' in body
                    assert f'data-success-url-template="/login?next={path}"'.encode() in body
                    body, headers = request(
                        path, actor=actor, method="HEAD", expected=403, raw=True
                    )
                    assert body == b""
                    assert headers.get("Cache-Control") == "no-store"
                for path, actor in (
                    ("/client/dashboard", "client"),
                    ("/contractor/dashboard", "contractor"),
                ):
                    body, headers = request(path, actor=actor, raw=True)
                    assert headers.get("Cache-Control") == "no-store"
                    assert b"Sign out and switch account" not in body
                for actor in (
                    "invalid_signature",
                    "expired",
                    "wrong_origin",
                    "pending",
                ):
                    request("/api/client/jobs", actor=actor, expected=401)
                checks.append("native RS256 authentication and role separation")
                request(
                    "/api/client/jobs", expected=401,
                    extra_headers={"Authorization": "Bearer " + "A" * 8193},
                )
                request("/api/client/jobs", actor="rotated")
                for _ in range(3):
                    request("/api/client/jobs", actor="unknown_key", expected=401)
                budget = request("/__native/clerk-jwks-budget", method="POST")
                require(budget == {"allowed": 39}, "The warm key did not avoid repeated provider lookups.")
                request("/api/client/jobs", actor="rotated")
                request("/api/client/jobs", actor="client")
                jwks_event = "NATIVE CLERK JWKS LOOKUP"
                jwks_log = local_log_after_events(stage / "worker.log", {jwks_event: 40})
                require(jwks_log.count(jwks_event) == 40, "The synthetic JWKS lookup budget was not enforced.")
                checks.append("native rotated Clerk key, bounded remote lookup, and unaffected pinned-key sign-in")
                onboard_db = ["d1", "execute", "native-journey", "--local"]
                onboard_path = "/api/auth/onboard"
                onboarding = {"role": "contractor", "display_name": "Synthetic storefront"}
                blocked_onboard = request(onboard_path, actor="onboarding_restricted", payload=onboarding, expected=400)
                require(blocked_onboard == {"ok": False, "error": "Onboarding request was not accepted."},
                        "A restricted provider identity was accepted or the denial exposed provider state.")
                blocked_session = request("/api/auth/session", actor="onboarding_restricted")
                require(blocked_session["onboarding_required"] is True and blocked_session["workdoe_user"] is None,
                        "Restricted onboarding left a Workdoe workspace linked to the session.")
                checks.append("native banned Clerk identity cannot provision a workspace")
                command([*onboard_db, "--command", """
                    CREATE TRIGGER native_fail_onboard BEFORE INSERT ON contractor_profiles
                    WHEN NEW.business_name = 'Synthetic storefront'
                    BEGIN SELECT RAISE(ABORT, 'local onboarding profile failure fixture'); END
                """])
                failed_onboard = request(onboard_path, actor="onboarding", payload=onboarding, expected=503)
                require("local onboarding profile failure fixture" not in failed_onboard["error"],
                        "A profile failure exposed a database diagnostic.")
                pending = request("/api/auth/session", actor="onboarding")
                require(pending == {"authenticated": True, "onboarding_required": True, "workdoe_user": None},
                        "Pending onboarding returned more than the navigation state or left a linked account.")
                command([*onboard_db, "--command", "DROP TRIGGER native_fail_onboard"])
                created = request(onboard_path, actor="onboarding", payload=onboarding, expected=201)
                require(created["created"] is True and created["workdoe_user"]["role"] == "contractor",
                        "The corrected onboarding retry did not create the contractor.")
                linked = request("/api/auth/session", actor="onboarding")
                require(linked == {
                    "authenticated": True, "onboarding_required": False, "workdoe_user": {"role": "contractor"},
                }, "Linked session returned more than navigation state and the current role.")
                replay = request(onboard_path, actor="onboarding", payload={**onboarding, "role": "client"})
                require(replay["created"] is False and replay["workdoe_user"] == created["workdoe_user"],
                        "An onboarding replay changed the original account or role.")
                request(onboard_path, actor="onboarding_conflict", payload=onboarding, expected=409)
                require(request("/api/auth/session", actor="onboarding_conflict")["onboarding_required"] is True,
                        "An email conflict linked a different Clerk identity.")
                # The local counter uses wall-clock windows; allow for one rollover.
                for _ in range(80):
                    _, headers = request(onboard_path, actor="onboarding_conflict", payload=onboarding,
                                         expected=(409, 429), raw=True)
                    if headers.get("Retry-After") == "60":
                        require(headers.get("Cache-Control") == "no-store", "Onboarding throttle was cacheable.")
                        break
                else:
                    raise AssertionError("The native signup limiter never denied the repeated request.")
                unaffected = request(onboard_path, actor="onboarding", payload=onboarding)
                require(unaffected["workdoe_user"] == created["workdoe_user"],
                        "An unrelated signup identity was throttled or altered.")
                onboard_counts = json.loads(command([*onboard_db, "--json", "--command", """
                    SELECT COUNT(*) AS profiles,
                        (SELECT COUNT(*) FROM automation_events WHERE event_type = 'clerk-onboarding-linked') AS audits
                    FROM contractor_profiles WHERE business_name = 'Synthetic storefront'
                """]))[0]["results"][0]
                require(onboard_counts == {"profiles": 1, "audits": 1}, "Onboarding did not write exactly one profile and audit.")
                checks.append("native D1 onboarding rollback, retry, fixed role and email-conflict isolation")
                staging = request("/__native/staging-containment", payload={})
                require(staging == {
                    "health": 200, "mode": "sealed", "sealed_jobs": 503,
                    "wrong_host": 404, "wrong_host_redirect": None, "tile_free_list": True,
                    "area_only": True, "access_map_marked": True, "unconfigured_login": 503, "proxy_blocked": 404,
                    "report_mail_blocked": True, "exact_stage_turnstile": True,
                    "acked": [0, 1, 0], "retried": [1, 0, 1], "retry_delays": [900, None, 900],
                }, f"Native staging fixture did not enforce containment: {staging!r}")
                checks.append("native staging host, seal, provider isolation, exact verification and area map")
                job = {
                    "title": "Synthetic window cleaning project for the porch and rear windows",
                    "category": "Window cleaning",
                    "service_group_slug": "cleaning-upkeep",
                    "service_slug": "window-cleaning",
                    "project_setting": "house",
                    "city": "Alexandria",
                    "state": "VA",
                    "zip_code": "22314",
                    "desired_date": (
                        datetime.now(UTC).date() + timedelta(days=30)
                    ).isoformat(),
                    "description": "Clean reachable ground-floor exterior glass and frames.",
                    "turnstile_token": "job-post",
                    "idempotency_key": "native-fixture-job-00000001",
                    "service_policy_acknowledgement": SERVICE_POLICY_VERSION,
                    "scope_height": "ground",
                }
                local_db = ["d1", "execute", "native-journey", "--local"]
                cookie_jar = CookieJar(policy=DefaultCookiePolicy(secure_protocols=("http",)))
                draft_browser = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPCookieProcessor(cookie_jar),
                )
                draft = job | {
                    "title": "Synthetic private draft", "scope_height": "ground",
                    "license_preference": "1", "cf-turnstile-response": "job-draft",
                }
                form_headers = {"Content-Type": "application/x-www-form-urlencoded", "Origin": base}

                def draft_request(fields, headers, *, expected, path="/post-project", raw_form=None):
                    return request(
                        path, expected=expected, raw=True, cookie_opener=draft_browser,
                        extra_headers=headers, form_body=urlencode(fields).encode() if raw_form is None else raw_form,
                    )

                _, saved_draft = draft_request(draft, form_headers, expected=303)
                require(
                    saved_draft["Location"] == "/create-account?intent=post-job&draft=saved"
                    and any(cookie.name == "workdoe_job_draft" for cookie in cookie_jar),
                    "The anonymous form did not save a draft and continue to account setup.",
                )
                for source in (
                    {"Origin": "https://outside.invalid", "Sec-Fetch-Site": "cross-site"},
                    {"Origin": "https://legacy.workdoe.com", "Sec-Fetch-Site": "same-site"},
                    {"Origin": "null", "Referer": base + "/post-project"},
                    {},
                ):
                    denied, headers = draft_request(
                        draft | {"title": "Synthetic foreign replacement"},
                        {"Content-Type": form_headers["Content-Type"]} | source, expected=403,
                    )
                    require(
                        b"Form not saved" in denied and b"Synthetic private draft" not in denied
                        and b"Synthetic foreign replacement" not in denied and not headers.get_all("Set-Cookie"),
                        "Foreign form response disclosed or replaced a draft.",
                    )
                malformed, headers = draft_request(
                    draft, form_headers, expected=400,
                    raw_form=urlencode(draft).replace("Synthetic+private+draft", "%FF").encode(),
                )
                require(b"Request form could not be read." in malformed and not headers.get_all("Set-Cookie"),
                        "An invalid UTF-8 form changed the draft cookie.")
                checks.append("native guest draft rejects foreign origins and malformed form bytes")
                revised = draft | {"title": "Synthetic revised draft", "scope_height": "one_story"}
                multipart = "".join(
                    f'--workdoe-fixture\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'
                    for key, value in revised.items()
                ) + "--workdoe-fixture--\r\n"
                multipart_headers = {
                    "Content-Type": "multipart/form-data; boundary=workdoe-fixture", "Referer": base + "/post-project",
                    "X-Workdoe-Dialog": "native",
                }
                command([*local_db, "--command", """
                    CREATE TRIGGER native_fail_draft BEFORE INSERT ON job_draft_scope_answers
                    BEGIN SELECT RAISE(ABORT, 'synthetic draft replacement failure'); END
                """])
                interrupted, headers = draft_request(
                    revised, multipart_headers, expected=503, path="/post-project?embed=1", raw_form=multipart.encode(),
                )
                require(
                    not headers.get_all("Set-Cookie") and headers.get("Retry-After") == "5"
                    and b"Draft save interrupted" in interrupted and b'data-project-initial-step="6"' in interrupted
                    and b"Synthetic revised draft" in interrupted and b"synthetic draft replacement failure" not in interrupted,
                    "The retry state lost the submitted brief or exposed a database diagnostic.",
                )
                recovered, _ = request("/post-project", raw=True, cookie_opener=draft_browser)
                require(b"Synthetic private draft" in recovered, "A failed transaction erased the original draft.")
                command([*local_db, "--command", "DROP TRIGGER native_fail_draft"])
                draft_request(
                    revised, multipart_headers, expected=303, path="/post-project?embed=1", raw_form=multipart.encode(),
                )
                resumed, _ = request("/jobs/new", actor="client", raw=True, cookie_opener=draft_browser)
                require(
                    b"Synthetic revised draft" in resumed and b'<option value="one_story" selected>' in resumed,
                    "The signed-in consumer could not resume the replaced draft and its scope answers.",
                )
                checks.append("native urlencoded and multipart draft save, atomic rollback, retry and resume")
                for actor in ("client", "other_client"):
                    if actor == "other_client":
                        draft_request(draft, form_headers, expected=303)
                    _, denied = request(
                        "/logout", method="POST", expected=403, raw=True, cookie_opener=draft_browser,
                        extra_headers={"Origin": "https://outside.invalid"},
                    )
                    require(not denied.get_all("Set-Cookie"), "Unmarked legacy sign-out modified browser state.")
                    _, signed_out = request(
                        "/api/auth/logout", actor=actor, payload={}, raw=True, cookie_opener=draft_browser,
                    )
                    cookie_headers = signed_out.get_all("Set-Cookie") or []
                    require(
                        len(cookie_headers) == 2 and signed_out.get("Cache-Control") == "no-store"
                        and {value.split("=", 1)[0] for value in cookie_headers} == {"__session", "workdoe_job_draft"}
                        and all("Max-Age=0" in value for value in cookie_headers)
                        and not any(cookie.name == "workdoe_job_draft" for cookie in cookie_jar),
                        "Sign-out did not send two independent expired cookies.",
                    )
                    clean, _ = request("/post-project", raw=True, cookie_opener=draft_browser)
                    require(b"Synthetic private draft" not in clean and b"Synthetic revised draft" not in clean,
                            "A signed-out shared browser still displayed the draft.")
                native_log = local_log_after_events(stage / "worker.log", {
                    "NATIVE CLERK REVOKE CANCELLED": 1,
                    '"event": "clerk-session-revoke-failed"': 1,
                })
                require(
                    "NATIVE CLERK REVOKE CANCELLED" in native_log
                    and '"event": "clerk-session-revoke-failed"' in native_log,
                    "The stalled provider call was not cancelled and reported without its details.",
                )
                draft_rows = json.loads(command([
                    *local_db, "--json", "--command",
                    "SELECT COUNT(*) AS saved FROM job_drafts WHERE consumed_at IS NULL",
                ]))[0]["results"]
                require(draft_rows == [{"saved": 2}], "Sign-out modified stored draft retention.")
                checks.append("native protected sign-out clears both cookies on success and stalled Clerk response")
                request(
                    "/api/jobs", actor="client", payload=job, marker=False, expected=403
                )
                request("/api/jobs", actor="contractor", payload=job, expected=403)
                for invalid_json in (
                    b'{"description":"\xff"}', br'{"description":"\ud800"}',
                    br'{"\udfff":"description"}', b" " * (64 * 1024),
                ):
                    invalid = request(
                        "/api/jobs", actor="client", form_body=invalid_json, expected=400,
                        extra_headers={"Content-Type": "application/json", "X-Workdoe-Request": "same-origin"},
                    )
                    require(invalid.get("ok") is False, "Invalid project JSON did not fail at the route boundary.")
                request(
                    "/api/jobs",
                    actor="client",
                    payload=dict(job, turnstile_token="invalid"),
                    expected=400,
                )
                request(
                    "/api/jobs",
                    actor="client",
                    payload=dict(job, service_policy_acknowledgement="old"),
                    expected=400,
                )
                request(
                    "/api/jobs",
                    actor="client",
                    payload=dict(
                        job, description="Clean the windows at 123 Main Street, please."
                    ),
                    expected=400,
                )
                draft_request(draft, form_headers, expected=303)

                def publish_state():
                    return json.loads(command([
                        *local_db, "--json", "--command",
                        """
                        SELECT (SELECT COUNT(*) FROM jobs) AS jobs,
                               (SELECT COUNT(*) FROM job_scope_answers) AS answers,
                               (SELECT COUNT(*) FROM service_policy_acknowledgements) AS acknowledgements,
                               (SELECT COUNT(*) FROM idempotency_requests WHERE action = 'job-create') AS receipts,
                               (SELECT COUNT(*) FROM job_drafts WHERE consumed_at IS NOT NULL) AS consumed_drafts,
                               (SELECT COUNT(*) FROM automation_events WHERE event_type = 'job-created') AS events
                        """,
                    ]))[0]["results"][0]

                before_publish = publish_state()
                for table, condition in (
                    ("job_scope_answers", ""),
                    ("automation_events", "WHEN NEW.event_type = 'job-created'"),
                ):
                    command([*local_db, "--command", f"""
                        CREATE TRIGGER native_fail_publish BEFORE INSERT ON {table}
                        {condition}
                        BEGIN SELECT RAISE(ABORT, 'synthetic project publication failure'); END
                    """])
                    failed, headers = request(
                        "/api/jobs", actor="client", payload=job, raw=True, expected=503,
                        cookie_opener=draft_browser,
                    )
                    after_failure = publish_state()
                    require(after_failure == before_publish,
                            f"Failed publication committed partial state: {after_failure}, prior: {before_publish}")
                    require(headers.get("Cache-Control") == "no-store"
                            and not headers.get_all("Set-Cookie")
                            and json.loads(failed).get("ok") is False
                            and b"synthetic project publication failure" not in failed,
                            "Failed publication exposed a diagnostic or an unsafe response.")
                    require(not request("/api/jobs/open?q=Synthetic+window+cleaning")["jobs"],
                            "A failed publication appeared on the public map.")
                    resumed, _ = request("/jobs/new", actor="client", raw=True, cookie_opener=draft_browser)
                    require(b"Synthetic private draft" in resumed, "A failed publication lost the browser draft.")
                    command([*local_db, "--command", "DROP TRIGGER native_fail_publish"])

                created_body, headers = request(
                    "/api/jobs", actor="client", payload=job, expected=201, raw=True,
                    cookie_opener=draft_browser,
                )
                require("Max-Age=0" in headers.get("Set-Cookie", "")
                        and not any(cookie.name == "workdoe_job_draft" for cookie in cookie_jar),
                        "A confirmed publication did not clear the guest draft cookie.")
                created = json.loads(created_body)
                job_id = created["job_id"]
                require(
                    job_id == 1, "Media fixtures require a fresh empty marketplace."
                )
                require(publish_state() == {key: count + 1 for key, count in before_publish.items()},
                        "Publication retry did not create one complete project and receipt.")
                checks.append("native D1 rolls back incomplete publication and retries the same request once")
                contact = "jos\u00e9@fixture.invalid"
                private_address = "123\u200bFixture Street"
                for private in (contact, "crew@\u4f8b\u3048.\u30c6\u30b9\u30c8", private_address):
                    request("/api/jobs", actor="client", payload=dict(job, description=private), expected=400)
                command([*local_db, "--command", """
                    INSERT INTO jobs (id, client_id, title, category, city, state, zip_code,
                                      description, status, created_at, updated_at)
                    VALUES (9108, 1, 'Privacy probe safe', 'Landscaping', 'Arlington', 'VA', '22201',
                            'Synthetic scope', 'open', '2000-01-01', '2000-01-01'),
                           (9109, 1, 'Privacy probe jos' || char(233) || '@fixture.invalid',
                            'Landscaping', 'Arlington', 'VA', '22201', '123' || char(8203) || 'Fixture Street',
                            'open', '2000-01-01', '2000-01-01'),
                           (9110, 1, 'Privacy probe caf' || char(233), 'Landscaping', 'Arlington', 'VA',
                            '22201', 'Synthetic scope', 'open', '2000-01-01', '2000-01-01');
                    UPDATE contractor_profiles SET business_name = 'jos' || char(233) || '@fixture.invalid',
                        insurance_status = 'Ask insurance-fixture@example.invalid',
                        license_number = '123 Credential Fixture Street'
                    WHERE user_id = 4;
                """])
                discovery = "/api/jobs/open?q=Privacy+probe&limit=1"
                first = request(discovery)
                require([row["id"] for row in first["jobs"]] == [9110]
                        and first["next_cursor"] == "djE6Mg", "Privacy filtering lost the correct cursor.")
                second = request(discovery + "&cursor=" + first["next_cursor"])
                require([row["id"] for row in second["jobs"]] == [9108] and not second["truncated"],
                        "Privacy filtering skipped a visible result after the hidden row.")
                for path in ("/?job_id=9109", "/login?next=/jobs/9109&embed=1", "/start?job_id=9109&embed=1"):
                    body, _ = request(path, raw=True)
                    require(b"@fixture.invalid" not in body, "Private project title leaked into a public page.")
                filtered = request("/api/jobs/open?" + urlencode({"q": private_address}))
                require(filtered["filters"]["q"] == "", "A direct discovery query echoed contact text.")
                detail = request("/api/jobs/9109", actor="contractor")["job"]
                require(detail["title"] == "Project" and detail["description"] == "Brief withheld.",
                        "The contractor detail payload exposed stored contact text.")
                detail_html, _ = request("/jobs/9109", actor="contractor", raw=True)
                require(b"@fixture.invalid" not in detail_html and b"Brief withheld." in detail_html,
                        "The contractor detail page exposed stored contact text.")
                owner = request("/api/jobs/9109", actor="client")["job"]
                require(contact in owner["title"] and private_address == owner["description"],
                        "The consumer lost access to the stored original.")
                profile = request("/api/contractors/4")["contractor"]
                require(profile["business_name"] == "Workdoe contractor", "A public profile disclosed contact text.")
                require(
                    not {"insurance_status", "license_number"} & profile.keys(),
                    "The public profile API exported private credential notes.",
                )
                private_profile = request("/api/contractor/profile", actor="other_contractor")["profile"]
                require(
                    private_profile["insurance_status"] == "Ask insurance-fixture@example.invalid"
                    and private_profile["license_number"] == "123 Credential Fixture Street",
                    "The profile owner lost access to their stored notes.",
                )
                command([*local_db, "--command", """
                    DELETE FROM jobs WHERE id IN (9108, 9109, 9110);
                    UPDATE contractor_profiles SET business_name = 'Other fixture contractor',
                        insurance_status = '', license_number = '' WHERE user_id = 4;
                """])
                checks.append("native contact-text privacy on writes, public pages, cursor, profile and contractor detail")
                checks.append("native public contractor API omits private notes while the owner retains access")
                command(
                    [
                        "d1",
                        "execute",
                        "native-journey",
                        "--local",
                        "--file",
                        str(FIXTURES / "media_seed.sql"),
                    ]
                )
                photo = "/media/jobs/9101"
                for path, actor in ((photo, "client"), ("/media/contractors/9201", "contractor")):
                    for method in ("GET", "HEAD"):
                        body, headers = request(path, actor=actor, method=method, raw=True, expected=403, extra_headers={
                            "Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image",
                        })
                        require(headers.get("Cross-Origin-Resource-Policy") == "same-origin"
                                and headers.get("X-Frame-Options") == "DENY"
                                and headers.get("Cache-Control") == "no-store"
                                and (method != "HEAD" or not body),
                                "A cross-origin private photo request missed its safe denial.")
                checks.append("native project and contractor photos deny authenticated cross-origin embedding")
                for method in ("GET", "HEAD"):
                    body, headers = request("/workdoe-missing-page?fixture=synthetic-stale-link", method=method,
                                            raw=True, expected=404, extra_headers={"Accept": "text/html"})
                    require(headers.get("Cache-Control") == "no-store" and headers.get("Referrer-Policy") == "no-referrer"
                            and headers.get("Content-Type", "").startswith("text/html")
                            and (not body if method == "HEAD" else b"Page not found" in body)
                            and b"synthetic-stale-link" not in body, "The missing document did not preserve its HTTP or privacy contract.")
                missing_api = request("/api/workdoe-missing-page", expected=404, extra_headers={"Accept": "text/html"})
                require(missing_api == {"ok": False, "error": "Not found."}, "Unknown API route no longer returns JSON.")
                checks.append("native missing document GET/HEAD recover without changing API errors")

                oversized_id = "9" * 4301
                unsafe_id = "9007199254740992"
                for method in ("GET", "HEAD"):
                    body, headers = request(f"/contractors/{oversized_id}", method=method, raw=True, expected=404,
                                            extra_headers={"Accept": "text/html"})
                    require(headers.get("Cache-Control") == "no-store"
                            and (not body if method == "HEAD" else b"Page not found" in body)
                            and oversized_id.encode() not in body,
                            "An oversized profile document missed the safe 404 contract.")
                for path, actor in (
                    (f"/api/contractors/{unsafe_id}", None),
                    (f"/api/jobs/{oversized_id}", None),
                    (f"/api/messages/threads/{unsafe_id}", "client"),
                ):
                    body, headers = request(path, actor=actor, raw=True, expected=404)
                    require(headers.get("Cache-Control") == "no-store" and json.loads(body).get("ok") is False,
                            "An invalid record ID missed the JSON route error.")
                _, headers = request(f"/media/jobs/{unsafe_id}", raw=True, expected=404)
                require(headers.get("Cross-Origin-Resource-Policy") == "same-origin"
                        and headers.get("Cache-Control") == "no-store",
                        "An invalid media ID changed private media headers.")
                composer, _ = request(
                    f"/jobs/new?repeat={oversized_id}&template={unsafe_id}&location=%D9%A1",
                    actor="client", raw=True,
                )
                require(b"Post a project" in composer and oversized_id.encode() not in composer,
                        "Invalid source IDs broke or were echoed by the project composer.")
                checks.append("native invalid route IDs return safe 404s and invalid source links open a usable composer")

                receipt = request("/__native/media-review", payload={})
                require(receipt == {"acknowledged": [1, 1, 1], "retried": [0, 0, 0]},
                        "The native media consumer retried an invalid input or missed a receipt.")
                review_rows = json.loads(command([
                    *local_db, "--json", "--command",
                    ("SELECT event_type, target_id, payload_json FROM automation_events "
                     "WHERE event_type = 'media-review-message-invalid' OR target_id = 26 ORDER BY event_type DESC, id"),
                ]))[0]["results"]
                require([(row["event_type"], row["target_id"]) for row in review_rows] == [
                    ("media-review-message-invalid", None), ("media-review-message-invalid", None),
                    ("media-review-message-accepted", 26),
                ] and all(json.loads(row["payload_json"]).get("reason") == "invalid-media-review" for row in review_rows[:2])
                    and all("synthetic-private-queue-" not in row["payload_json"] for row in review_rows),
                    "The native media audit retained private detail or misclassified a message.")
                checks.append("native media consumer redacts malformed and accepted receipts in local D1")

                if verify_candidate_browser:
                    subprocess.run(
                        [node, str(ROOT / "tests" / "browser" / "release_candidate_boundaries.cjs")],
                        cwd=ROOT, env=environment | browser_environment,
                        input=json.dumps({"base": base + "/", "consumerToken": tokens["client"], "hiddenLeadPhotoPath": photo}),
                        text=True, timeout=75, check=True,
                    )
                    marker = "NATIVE PHOTO ORIGIN "
                    log.flush()
                    origins = [
                        json.loads(line.split(marker, 1)[1])
                        for line in (stage / "worker.log").read_text(encoding="utf-8").splitlines()
                        if marker in line
                    ]
                    for method, site, mode, destination, status in (
                        ("GET", "same-site", "no-cors", "image", 403),
                        ("HEAD", "same-site", "no-cors", "image", 403),
                        ("GET", "same-site", "navigate", "document", 200),
                        ("GET", "same-origin", "no-cors", "image", 200),
                    ):
                        require({
                            "method": method, "site": site, "mode": mode, "destination": destination,
                            "status": status, "has_session": True,
                        } in origins, f"Missing native photo origin evidence for {method} {site} {destination}: {origins}")
                    checks.append("isolated Chromium verifies private photo origins and accessible missing-page recovery")
                request(photo, raw=True, expected=401)
                command([*local_db, "--command", "UPDATE job_photos SET content_type = 'text/html' WHERE id = 9101"])
                for method in ("GET", "HEAD"):
                    request(photo, actor="client", method=method, raw=True, expected=404)
                command([*local_db, "--command", "UPDATE job_photos SET content_type = 'image/webp' WHERE id = 9101"])
                checks.append("native retained photos reject non-image MIME metadata")
                request(photo, actor="other_client", raw=True, expected=403)
                request(photo, actor="suspended", raw=True, expected=403)
                expected_image = (
                    ROOT / "workdoe" / "static" / "field-doe.webp"
                ).read_bytes()
                for actor in ("client", "contractor", "other_contractor", "admin"):
                    content, headers = request(photo, actor=actor, raw=True)
                    require(
                        content == expected_image,
                        "Private media bytes differ from the local object.",
                    )
                    require(
                        headers.get("Cache-Control") == "private, no-store"
                        and headers.get("X-Content-Type-Options") == "nosniff"
                        and "private-source-name"
                        not in headers.get("Content-Disposition", ""),
                        "Private media cache, MIME or filename policy regressed.",
                    )
                head, _headers = request(photo, actor="client", method="HEAD", raw=True)
                require(head == b"", "HEAD returned private media bytes.")
                request("/media/jobs/9102", actor="client", raw=True, expected=404)
                request(
                    "/media/jobs/9102",
                    actor="client",
                    method="HEAD",
                    raw=True,
                    expected=404,
                )
                request("/media/jobs/9103", actor="admin", raw=True, expected=404)
                request("/media/jobs/9104", actor="client", raw=True, expected=404)
                request("/media/jobs/9104", actor="admin", raw=True)
                for actor in ("client", "contractor", "admin"):
                    detail = request("/api/jobs/1", actor=actor)
                    require(detail["photos"] and "private-source-name" not in json.dumps(detail),
                            "Project details disclosed an original upload filename.")
                local_db = ["d1", "execute", "native-journey", "--local"]
                report = {
                    "target_type": "job", "target_id": job_id, "reason": "Synthetic restricted lead report.",
                    "idempotency_key": "native-restricted-job-report-1",
                }
                command([
                    *local_db, "--command",
                    """
                    INSERT INTO idempotency_requests
                        (actor_id, action, key_hash, resource_type, status, created_at, expires_at)
                    VALUES (2, 'synthetic-expired-report', lower(hex(zeroblob(32))), 'report', 'processing',
                            '2000-01-01', '2000-01-02');
                    CREATE TRIGGER native_close_on_report_cleanup AFTER DELETE ON idempotency_requests
                    WHEN old.action = 'synthetic-expired-report'
                    BEGIN UPDATE jobs SET status = 'closed' WHERE id = 1; END;
                    """,
                ])
                request("/api/reports", actor="other_contractor", payload=report, expected=404)
                race_state = json.loads(command([
                    *local_db, "--json", "--command",
                    """
                    SELECT status, (SELECT COUNT(*) FROM reports) AS reports,
                           (SELECT COUNT(*) FROM idempotency_requests WHERE resource_type = 'report') AS receipts
                    FROM jobs WHERE id = 1
                    """,
                ]))
                require(race_state[0]["results"] == [{"status": "closed", "reports": 0, "receipts": 0}],
                        "A racing project closure permitted a report or left a reservation behind.")
                request("/api/jobs/1", actor="other_contractor", expected=404)
                command([
                    *local_db, "--command",
                    """
                    DROP TRIGGER native_close_on_report_cleanup;
                    UPDATE jobs SET status = 'open' WHERE id = 1;
                    INSERT INTO match_requests
                        (id, job_id, contractor_id, scope_note, price_range, timeline,
                         experience, availability, status, created_at, updated_at)
                    VALUES (9101, 1, 2, 'Fixture', '$50', 'Fixture', 'Fixture', 'Fixture',
                            'approved', '2000-01-01', '2000-01-01');
                    """,
                ])
                for status in ("open", "closed"):
                    if status == "closed":
                        command([*local_db, "--command", "UPDATE jobs SET status = 'closed' WHERE id = 1"])
                    for actor in ("contractor", "client", "admin"):
                        require(request("/api/jobs/1", actor=actor)["job"]["id"] == 1,
                                "A participant or moderator lost project detail access.")
                    request("/jobs/1", actor="contractor", raw=True)
                    request("/jobs/1", actor="other_contractor", raw=True, expected=404)
                    denial = request("/api/jobs/1", actor="other_contractor", expected=404)
                    require(denial == request("/api/jobs/2147483648", actor="other_contractor", expected=404),
                            "An outsider can distinguish an inaccessible project from a missing project.")
                    request("/api/reports", actor="other_contractor", payload=report, expected=404)
                    request(photo, actor="contractor", raw=True)
                    for method in ("GET", "HEAD"):
                        request(photo, actor="other_contractor", method=method, raw=True, expected=403)
                command([*local_db, "--command", "UPDATE jobs SET status = 'hidden' WHERE id = 1"])
                request("/api/jobs/1", actor="contractor", expected=404)
                for method in ("GET", "HEAD"):
                    request(photo, actor="contractor", method=method, raw=True, expected=404)
                request(photo, actor="client", raw=True)
                request(photo, actor="admin", raw=True)
                command([
                    *local_db, "--command",
                    """
                    UPDATE jobs SET status = 'closed' WHERE id = 1;
                    UPDATE match_requests SET status = 'rejected' WHERE id = 9101;
                    """,
                ])
                prior_bid = request("/api/jobs/1", actor="contractor")
                require(prior_bid["existing_request"]["status"] == "rejected" and prior_bid["photos"] == [],
                        "Prior bidders should retain their bid, without private photos.")
                request(photo, actor="contractor", raw=True, expected=403)
                command([
                    *local_db, "--command",
                    "DELETE FROM match_requests WHERE id = 9101; UPDATE jobs SET status = 'open' WHERE id = 1;",
                ])
                checks.append("native project participant access, hidden photos, and report closure race")
                request("/media/jobs", actor="admin", raw=True, expected=404)
                request("/media/contractors/9201", raw=True, expected=401)
                request(
                    "/media/contractors/9201", method="HEAD", raw=True, expected=401
                )
                request(
                    "/media/contractors/9201", actor="suspended", raw=True, expected=403
                )
                for viewer in ("client", "contractor", "other_client", "admin"):
                    request("/media/contractors/9201", actor=viewer, raw=True)
                anonymous_profile = request("/api/contractors/2")
                require(
                    anonymous_profile["contractor"]["photos"] == [],
                    "Anonymous portfolio metadata exposed",
                )
                request("/media/contractors/9202", raw=True, expected=401)
                request(
                    "/media/contractors/9202",
                    actor="other_client",
                    raw=True,
                    expected=404,
                )
                request("/media/contractors/9202", actor="contractor", raw=True)
                request("/media/contractors/9202", actor="admin", raw=True)
                request(
                    f"/api/media/jobs/{job_id}/upload",
                    actor="client",
                    payload={},
                    expected=503,
                )
                checks.append(
                    "native R2 job-photo roles, missing objects, key scoping and safe headers"
                )
                replay = request("/api/jobs", actor="client", payload=job)
                require(
                    replay["job_id"] == job_id and replay["replayed"] is True,
                    "Project replay did not return the original project.",
                )
                request(
                    f"/api/jobs/{job_id}/update",
                    actor="other_client",
                    payload=job,
                    expected=403,
                )
                checks.append(
                    "city/ZIP project creation, CSRF marker, ownership and replay"
                )
                def edit_state():
                    return [result["results"] for result in json.loads(command([
                        *local_db, "--json", "--command", """
                        SELECT * FROM jobs WHERE id = 1;
                        SELECT * FROM job_scope_answers WHERE job_id = 1 ORDER BY question_key;
                        SELECT * FROM service_policy_acknowledgements WHERE job_id = 1 ORDER BY id;
                        SELECT * FROM automation_events WHERE event_type = 'job-updated' AND target_id = 1 ORDER BY id;
                        """,
                    ]))]

                edit = job | {
                    "title": "TEST ONLY edited synthetic windows",
                    "description": "Owner-controlled beta test. No actual work is requested. Please do not bid.",
                    "scope_height": "one_story", "budget_min": "10", "budget_max": "20",
                    "desired_date": "2000-01-01",
                }
                rejected_new_date = request("/api/jobs", actor="client", payload=job | {
                    "desired_date": "2000-01-01", "preserved_desired_date": "2000-01-01",
                    "idempotency_key": "native-reject-retained-date-1",
                }, expected=400)
                require("desired_date" in rejected_new_date.get("field_errors", {}),
                        "A new post used client-supplied retained-date metadata to bypass validation.")
                command([*local_db, "--command", "UPDATE jobs SET desired_date = '2000-01-01' WHERE id = 1"])
                before_edit = edit_state()
                for table, condition in (
                    ("job_scope_answers", ""),
                    ("service_policy_acknowledgements", ""),
                    ("automation_events", "WHEN NEW.event_type = 'job-updated'"),
                ):
                    # Only these three fixed synthetic tables enter the trigger fixture.
                    command([*local_db, "--command", f"""
                        CREATE TRIGGER native_fail_edit BEFORE INSERT ON {table} {condition}
                        BEGIN SELECT RAISE(ABORT, 'synthetic edit failure'); END
                    """])
                    rejected, headers = request(
                        f"/api/jobs/{job_id}/update", actor="client", payload=edit, raw=True, expected=503,
                    )
                    require(edit_state() == before_edit, "Rejected edit committed partial project, scope or audit state.")
                    require(headers.get("Cache-Control") == "no-store" and headers.get("Retry-After") == "5"
                            and json.loads(rejected).get("ok") is False and b"synthetic edit failure" not in rejected,
                            "Failed edit exposed diagnostics or an unsafe response.")
                    command([*local_db, "--command", "DROP TRIGGER native_fail_edit"])
                invalid_edit = request(
                    f"/api/jobs/{job_id}/update", actor="client",
                    payload=edit | {"desired_date": "1999-12-31", "preserved_desired_date": "1999-12-31"}, expected=400,
                )
                require("desired_date" in invalid_edit.get("field_errors", {}) and edit_state() == before_edit,
                        "Invalid edit date did not preserve the project or expose a field error.")
                saved_edit = request(f"/api/jobs/{job_id}/update", actor="client", payload=edit)
                after_edit = edit_state()
                require(saved_edit.get("url") == f"/client/jobs/{job_id}"
                        and after_edit[0][0]["title"] == edit["title"]
                        and after_edit[0][0]["description"] == edit["description"]
                        and after_edit[0][0]["desired_date"] == "2000-01-01"
                        and after_edit[1][0]["answer_code"] == "one_story"
                        and len(after_edit[2]) == len(before_edit[2]) + 1 and len(after_edit[3]) == 1,
                        "Owner edit did not commit the complete project, scope, advisory and event.")
                edited_page, _ = request(f"/client/jobs/{job_id}/edit", actor="client", raw=True)
                require(edit["title"].encode() in edited_page and edit["description"].encode() in edited_page,
                        "Saved owner edit did not survive a fresh form read.")
                request(f"/api/jobs/{job_id}/update", actor="client", payload=job)
                checks.append("native owner edit, retained elapsed date, field errors, atomic rollback, retry and fresh form persistence")
                for route in ("/", "/api/jobs/open", "/login", "/start", "/create-account"):
                    for method in ("GET", "HEAD"):
                        body, headers = request(
                            route + ";native-path-probe=1?limit=1",
                            method=method, expected=404, raw=True,
                        )
                        require(
                            headers.get("Cache-Control") == "no-store"
                            and headers.get("Referrer-Policy") == "no-referrer"
                            and not headers.get("Location")
                            and b"native-path-probe" not in body
                            and (not body if method == "HEAD" else json.loads(body).get("ok") is False),
                            "A noncanonical public discovery path did not return a private 404.",
                        )
                checks.append("noncanonical public discovery paths rejected before routing on GET and HEAD")
                for route in ("/", "/api/jobs/open"):
                    for query, status in (
                        ("native-envelope-marker=" + "x" * 4096, 414),
                        ("native-envelope-marker=x" + "&pad=x" * 32, 400),
                    ):
                        for method in ("GET", "HEAD"):
                            body, headers = request(route + "?" + query, method=method, expected=status, raw=True)
                            require(
                                headers.get("Cache-Control") == "no-store"
                                and headers.get("Referrer-Policy") == "no-referrer"
                                and b"native-envelope-marker" not in body
                                and (method != "HEAD" or not body),
                                "Rejected discovery query was cached, echoed or included a HEAD body.",
                            )
                for method, status in (("OPTIONS", 200), ("POST", 405), ("DELETE", 405)):
                    body, headers = request(
                        "/api/jobs/open", method=method, expected=status, raw=True,
                        extra_headers={"X-Workdoe-Request": "same-origin"},
                    )
                    require(
                        headers.get("Allow") == "GET, HEAD, OPTIONS"
                        and headers.get("Cache-Control") == "no-store"
                        and "Access-Control-Allow-Origin" not in headers
                        and (not body if method == "OPTIONS" else json.loads(body).get("ok") is False),
                        "Jobs API method rejection or OPTIONS response did not match the read-only contract.",
                    )
                checks.append("public discovery rejects oversized queries and unsupported methods on local HTTP")
                anonymous_routes = anonymous_private_routes_check(base, 5)
                require(anonymous_routes.status == "ready", anonymous_routes.summary)
                checks.append("native signed-out page, detail API and private photo denial without caching")
                public = request("/api/jobs/open")
                notice_prefix = "/vendor/clerk-notices-v2/"
                notice_index = notice_prefix + "notices-1"
                terms, _ = request("/terms", raw=True)
                require(f'href="{notice_index}"'.encode() in terms, "Terms omits the reviewed notice link.")
                for asset in sorted((ROOT / "workdoe/static" / notice_prefix.strip("/")).iterdir()):
                    url = notice_prefix + asset.name.removesuffix(".html")
                    body, headers = request(url, raw=True)
                    headers = {name.lower(): value for name, value in headers.items()}
                    mime = "text/html" if asset.suffix == ".html" else "text/plain"
                    require(
                        body == asset.read_bytes() and headers.get("content-type", "").startswith(mime)
                        and headers.get("x-content-type-options") == "nosniff"
                        and headers.get("cache-control") == "no-store",
                        f"Reviewed notice not delivered intact: {asset.name}",
                    )
                for url in ("/vendor/clerk-notices/notices-1", notice_prefix + "missing-notice-release-probe.txt"):
                    _, headers = request(url, expected=404, raw=True)
                    require(headers.get("Cache-Control") == "no-store", "A missing notice was cacheable.")
                for vendor in ("leaflet", "leaflet-markercluster", "tabler-icons"):
                    _, headers = request(f"/vendor/{vendor}/LICENSE", raw=True)
                    require(
                        headers.get("Cache-Control") == "public, max-age=31556952, immutable",
                        f"Pinned {vendor} asset caching changed.",
                    )
                checks.append("native Terms link, exact software notices, no-store misses and pinned vendor caching")
                discovery = discovery_files_check(base, 5)
                require(discovery.status == "ready", discovery.summary)
                checks.append("native robots and sitemap match the reviewed crawl profile")
                command([
                    *local_db, "--command",
                    """
                    INSERT INTO jobs (id, client_id, title, category, city, state, zip_code,
                                      description, status, approx_lat, approx_lng, created_at, updated_at)
                    VALUES (9108, 1, 'Native pin check legacy', 'Landscaping', 'Arlington', 'VA', '22201',
                            'Synthetic scope', 'open', 38.881234, -77.101234, '2000-01-01', '2000-01-01'),
                           (9109, 1, 'Native pin check reviewed', 'Landscaping', 'Arlington', 'VA', '22201',
                            'Synthetic scope', 'open', 38.8871, -77.0932, '2000-01-01', '2000-01-01');
                    """,
                ])
                discovery = "/api/jobs/open?q=Native+pin+check"
                for endpoint, actor, key in (
                    (discovery, None, "jobs"),
                    ("/api/contractor/leads?q=Native+pin+check", "contractor", "map_jobs"),
                ):
                    pins = {row["id"]: (row["lat"], row["lng"]) for row in request(endpoint, actor=actor)[key]}
                    require(
                        pins == {9108: (None, None), 9109: (38.8871, -77.0932)},
                        "The legacy pin leaked or the reviewed ZIP pin disappeared.",
                    )
                area = "&north=38.95&south=38.85&east=-77.02&west=-77.2"
                bounded = request(discovery + area + "&limit=1")
                require(
                    [row["id"] for row in bounded["jobs"]] == [9109]
                    and not bounded["truncated"] and not bounded["next_cursor"],
                    "A legacy coordinate affected bounded results or cursor evidence.",
                )
                legacy_html, _ = request("/?job_id=9108&q=Native+pin+check", raw=True)
                require(
                    b"Native pin check legacy" in legacy_html and b"(no map pin)" in legacy_html
                    and b"38.881234" not in legacy_html,
                    "The initial HTML exposed a legacy coordinate or lost the project.",
                )
                command([*local_db, "--command",
                         "UPDATE jobs SET bidding_closes_at = '2000-01-01T00:00:00Z' WHERE id = 9108"])
                expired_html, _ = request("/?job_id=9108&q=Native+pin+check", raw=True)
                require(
                    [row["id"] for row in request(discovery)["jobs"]] == [9109]
                    and b"Project not shown" in expired_html and b"Native pin check legacy" not in expired_html,
                    "An expired bid window was still advertised in public discovery.",
                )
                command([*local_db, "--command",
                         "UPDATE jobs SET bidding_closes_at = '2099-01-01T00:00:00Z' WHERE id = 9108"])
                require(
                    {row["id"] for row in request(discovery)["jobs"]} == {9108, 9109},
                    "An extended bid window did not restore the project to discovery.",
                )
                command([*local_db, "--command", "DELETE FROM jobs WHERE id IN (9108, 9109)"])
                checks.append("native public and contractor maps suppress unreviewed stored pins")
                checks.append("native public map and shared links respect expired and reopened bid windows")
                long_query = urlencode({"q": job["title"].lower()})
                for path, actor in (("/api/jobs/open", None), ("/api/contractor/leads", "contractor")):
                    results = request(f"{path}?{long_query}", actor=actor)
                    require(any(str(row["id"]) == str(job_id) for row in results["jobs"]),
                            "The live-baseline hotfix did not match a long literal search.")
                html, _ = request(f"/?{long_query}", raw=True, extra_headers={"Accept": "text/html"})
                seed = html.split(b'<script id="map-jobs-data" type="application/json">', 1)[1].split(b"</script>", 1)[0]
                require(any(str(row["id"]) == str(job_id) for row in json.loads(seed)),
                        "The live-baseline HTML did not seed the long-search match.")
                no_match = request("/api/jobs/open?q=%25")
                require(not any(str(row["id"]) == str(job_id) for row in no_match["jobs"]),
                        "The live-baseline hotfix treated a percent sign as a wildcard.")
                checks.append("native live-baseline long project search and literal percent handling")
                zip_query = urlencode({"q": job["zip_code"]})
                zip_result = request(f"/api/jobs/open?{zip_query}")
                zip_html, _ = request(f"/?{zip_query}", raw=True, extra_headers={"Accept": "text/html"})
                zip_seed = zip_html.split(b'<script id="map-jobs-data" type="application/json">', 1)[1].split(b"</script>", 1)[0]
                for rows in (zip_result["jobs"], json.loads(zip_seed)):
                    matched = next((row for row in rows if str(row["id"]) == str(job_id)), None)
                    require(
                        matched is not None and "zip_code" not in matched and "description" not in matched,
                        "ZIP search lost the live project or exposed an unprojected field.",
                    )
                checks.append("native HTML and API ZIP searches agree without projecting private fields")
                bounds_query = "north=39.9&south=38.89&east=-76.9&west=-77.2"
                bounded = request(f"/api/jobs/open?limit=50&{bounds_query}")
                bounded_html, _ = request(f"/?{bounds_query}", raw=True, extra_headers={"Accept": "text/html"})
                bounded_seed = bounded_html.split(b'<script id="map-jobs-data" type="application/json">', 1)[1].split(b"</script>", 1)[0]
                require(
                    bounded["jobs"] and json.loads(bounded_seed) == bounded["jobs"]
                    and bounded["viewport"]["north"] == 39.5
                    and b'data-map-snapshot="' in bounded_html and b'name="north" value="39.5"' in bounded_html,
                    "The HTML and API diverged on bounded public results or viewport normalization.",
                )
                checks.append("native bounded HTML snapshot matches the API privacy projection and viewport")
                for payload in (public, request("/api/jobs/open?target=login")):
                    sample = next(row for row in payload["jobs"] if row["id"] == "demo-01")
                    require(
                        sample["action_label"] == "View sample"
                        and sample["url"] == sample["detail_url"] == "/?job_id=demo-01"
                        and not sample["desired_date"],
                        "A sample project still offered a live response action or date.",
                    )
                sample_html, _ = request("/?job_id=demo-01", raw=True, extra_headers={"Accept": "text/html"})
                sample_panel = sample_html.split(b'data-project-detail-content data-job-id="demo-01">', 1)[1].split(b"</article>", 1)[0]
                require(
                    b"This sample does not accept bids." in sample_panel and b"Sample timing" in sample_panel
                    and b"href=" not in sample_panel and b"<time" not in sample_panel,
                    "The sample detail HTML was not view-only.",
                )
                require(
                    any(str(row["id"]) == str(job_id) for row in public["jobs"]),
                    "Created project is missing from the public map payload.",
                )
                public_text = json.dumps(public)
                require(
                    "native.invalid" not in public_text
                    and "external_subject" not in public_text,
                    "Public map contains synthetic account identity.",
                )
                checks.append(
                    "created lead appears in public map without account identity"
                )
                bid = {
                    "scope_note": "Clean the reachable exterior glass and wipe the frames.",
                    "price_range": "$120-$180",
                    "timeline": "One morning",
                    "experience": "Experienced with routine ground-floor exterior window cleaning.",
                    "questions": "Is outdoor water available?",
                    "availability": "Weekday mornings",
                    "turnstile_token": "match-request",
                    "service_policy_acknowledgement": SERVICE_POLICY_VERSION,
                }
                request("/api/jobs/demo-01/request", actor="contractor", payload=bid, expected=404)
                checks.append("view-only sample API and detail; contractor cannot bid on a sample")
                request(
                    f"/api/jobs/{job_id}/request",
                    actor="client",
                    payload=bid,
                    expected=403,
                )
                def bid_state():
                    return json.loads(command([
                        *local_db, "--json", "--command",
                        """
                        SELECT (SELECT COUNT(*) FROM match_requests) AS bids,
                               (SELECT COUNT(*) FROM service_policy_acknowledgements
                                WHERE context = 'mini-bid') AS acknowledgements,
                               (SELECT COUNT(*) FROM automation_events
                                WHERE event_type = 'match-request-created') AS events,
                               (SELECT COUNT(*) FROM repeat_provider_invitations
                                WHERE status = 'bid_sent') AS invitations,
                               (SELECT COUNT(*) FROM automation_events
                                WHERE event_type = 'repeat-provider-invitation-bid-sent') AS invitation_events
                        """,
                    ]))[0]["results"][0]

                before_bid = bid_state()
                for table, predicate in (
                    ("service_policy_acknowledgements", "NEW.context = 'mini-bid'"),
                    ("automation_events", "NEW.event_type = 'match-request-created'"),
                ):
                    command([*local_db, "--command", f"""
                        CREATE TRIGGER native_fail_bid BEFORE INSERT ON {table} WHEN {predicate}
                        BEGIN SELECT RAISE(ABORT, 'synthetic bid persistence failure'); END
                    """])
                    failed, headers = request(
                        f"/api/jobs/{job_id}/request", actor="contractor",
                        payload=bid, raw=True, expected=503,
                    )
                    after_failure = bid_state()
                    require(after_failure == before_bid,
                            f"A failed bid left partial state: {after_failure}, prior: {before_bid}")
                    require(headers.get("Cache-Control") == "no-store"
                            and json.loads(failed).get("ok") is False
                            and b"synthetic bid persistence failure" not in failed,
                            "A failed bid leaked a database diagnostic or cacheable state.")
                    command([*local_db, "--command", "DROP TRIGGER native_fail_bid"])

                for race, restore in (
                    ("contractor", "UPDATE users SET status = 'active' WHERE id = 2"),
                    ("service", "UPDATE jobs SET service_slug = 'window-cleaning' WHERE id = 1"),
                ):
                    request(f"/api/jobs/{job_id}/request", actor="contractor", payload=bid, expected=404,
                            extra_headers={"X-Native-Bid-Race": race})
                    require(bid_state() == before_bid, f"Stale {race} information created a bid.")
                    command([*local_db, "--command", restore])
                checks.append("native bid write rejects contractor and service changes during verification")
                requested = request(
                    f"/api/jobs/{job_id}/request",
                    actor="contractor",
                    payload=bid,
                    expected=201,
                )
                match_id = requested["request_id"]
                require(bid_state() == before_bid | {"bids": 1, "acknowledgements": 1, "events": 1},
                        "A retried bid did not save one complete offer.")
                checks.append("native D1 rolls back a failed bid and allows a complete retry")
                request(
                    f"/api/jobs/{job_id}/request",
                    actor="contractor",
                    payload=bid,
                    expected=409,
                )
                request(
                    f"/api/match-requests/{match_id}/approve",
                    actor="other_client",
                    payload={},
                    expected=403,
                )
                competing = request(
                    f"/api/jobs/{job_id}/request", actor="other_contractor", payload=bid, expected=201,
                )
                rejection_path = f"/api/match-requests/{competing['request_id']}/reject"
                approval_path = f"/api/match-requests/{match_id}/approve"

                def decision_state():
                    rows = command([
                        *local_db, "--json", "--command",
                        """
                        SELECT
                          (SELECT COUNT(*) FROM match_requests WHERE status = 'pending') AS pending,
                          (SELECT COUNT(*) FROM match_requests WHERE status = 'approved') AS approved,
                          (SELECT COUNT(*) FROM match_requests WHERE status = 'rejected') AS rejected,
                          (SELECT COUNT(*) FROM threads) AS threads,
                          (SELECT COUNT(*) FROM messages) AS messages,
                          COUNT(*) AS events,
                          MAX(json_extract(payload_json, '$.closed_offer_count')) AS closed_count
                        FROM automation_events WHERE event_type IN ('match-request-approved', 'match-request-rejected')
                        """,
                    ])
                    return json.loads(rows)[0]["results"][0]

                before_decision = {
                    "pending": 2, "approved": 0, "rejected": 0, "threads": 0, "messages": 0,
                    "events": 0, "closed_count": None,
                }
                require(decision_state() == before_decision, "Expected two pending synthetic bids.")
                command([*local_db, "--command", """
                    UPDATE match_requests
                    SET scope_note = 'Ask legacy-bid-fixture@example.invalid about the screens.',
                        availability = 'Meet at 123 Bid Fixture Street.'
                    WHERE contractor_id = 2 AND status = 'pending';
                """])
                bid_review = request(f"/api/client/jobs/{job_id}/requests", actor="client")
                affected_bid = next(item for item in bid_review["requests"] if item["id"] == match_id)
                compared_bid = next(item for item in bid_review["comparison"]["offers"] if item["id"] == match_id)
                for projected in (affected_bid, compared_bid):
                    require(
                        projected["scope_note"] == projected["availability"] == "Withheld for privacy."
                        and projected["price_range"] == bid["price_range"],
                        "A consumer review projection leaked or changed retained bid terms.",
                    )
                for path in (f"/client/jobs/{job_id}", f"/contractors/2?job_id={job_id}"):
                    body, _ = request(path, actor="client", raw=True)
                    require(
                        b"Withheld for privacy." in body and b"legacy-bid-fixture@example.invalid" not in body
                        and b"123 Bid Fixture Street" not in body,
                        "A consumer page disclosed legacy bid contact text.",
                    )
                command([
                    *local_db, "--command",
                    """
                    CREATE TRIGGER native_fail_decision BEFORE INSERT ON automation_events
                    WHEN NEW.event_type IN ('match-request-approved', 'match-request-rejected')
                    BEGIN SELECT RAISE(ABORT, 'local decision audit failure fixture'); END
                    """,
                ])
                for decision_path in (rejection_path, approval_path):
                    failure = request(decision_path, actor="client", payload={}, expected=503)
                    require(
                        "local decision audit failure fixture" not in failure["error"]
                        and decision_state() == before_decision,
                        "A failed decision disclosed diagnostics or left a partial update.",
                    )
                command([*local_db, "--command", "DROP TRIGGER native_fail_decision"])
                approved = request(approval_path, actor="client", payload={})
                thread_id = approved["thread_id"]
                require(
                    request(approval_path, actor="client", payload={}) == approved
                    and decision_state() == {
                        "pending": 0, "approved": 1, "rejected": 1, "threads": 1, "messages": 1,
                        "events": 1, "closed_count": 1,
                    },
                    "The approval or its retry failed to keep one thread, starter and event.",
                )
                request(
                    f"/api/match-requests/{competing['request_id']}/approve", actor="client", payload={}, expected=409,
                )
                checks.append("native D1 rolls back failed bid decisions and creates one conversation on approval retry")
                checks.append(
                    "mini bid, duplicate rejection, owner approval and thread creation"
                )
                thread_path = f"/api/messages/threads/{thread_id}"
                request(thread_path, actor="other_contractor", expected=403)
                opening = request(thread_path, actor="client")
                require(
                    opening["thread"]["availability"] == "Withheld for privacy."
                    and opening["thread"]["price_range"] == bid["price_range"],
                    "The accepted bid summary did not preserve its privacy boundary.",
                )
                stored_terms = json.loads(command([*local_db, "--json", "--command", """
                    SELECT availability FROM match_requests
                    WHERE contractor_id = 2 AND status = 'approved';
                """]))[0]["results"]
                require(stored_terms == [{"availability": "Meet at 123 Bid Fixture Street."}],
                        "Redaction unexpectedly changed the original bid.")
                command([*local_db, "--command", """
                    UPDATE match_requests
                    SET scope_note = 'Clean the reachable exterior glass and wipe the frames.',
                        availability = 'Weekday mornings'
                    WHERE contractor_id = 2 AND status = 'approved';
                """])
                checks.append("native retained bid terms are withheld from review, comparison and matched messaging")
                opening_ids = [message["id"] for message in opening["messages"]]
                require(len(opening_ids) == 1, "The synthetic thread did not start with exactly one message.")
                for body in ({"text": "not a message"}, 42):
                    invalid = request(thread_path, actor="client", payload={"body": body}, expected=400)
                    require(invalid["field_errors"]["body"], "A malformed reply must produce a body field error.")
                message_ids = []
                for actor in ("client", "contractor"):
                    reply = {
                        "body": "Synthetic coordination message without contact details.",
                        "idempotency_key": f"native-message-{actor}-00000001",
                    }
                    if actor == "client":
                        command([
                            *local_db, "--command",
                            """
                            CREATE TRIGGER native_fail_message BEFORE INSERT ON automation_events
                            WHEN NEW.event_type = 'message-created'
                            BEGIN SELECT RAISE(ABORT, 'local message audit failure fixture'); END
                            """,
                        ])
                        failure = request(thread_path, actor=actor, payload=reply, expected=503)
                        require("local message audit failure fixture" not in failure["error"],
                                "The reply error exposed a database diagnostic.")
                        rollback = command([
                            *local_db, "--json", "--command",
                            """
                            SELECT
                                (SELECT COUNT(*) FROM messages) AS messages,
                                (SELECT COUNT(*) FROM idempotency_requests WHERE resource_type = 'message') AS receipts,
                                (SELECT last_read_message_id FROM thread_reads WHERE user_id = 1) AS read_message_id
                            """,
                        ])
                        require(json.loads(rollback)[0]["results"] == [
                            {"messages": 1, "receipts": 0, "read_message_id": opening_ids[0]},
                        ], "A failed reply left a message, receipt, or changed read marker.")
                        recipient = request(thread_path, actor="contractor")
                        require([message["id"] for message in recipient["messages"]] == opening_ids,
                                "The recipient could see a failed reply.")
                        command([*local_db, "--command", "DROP TRIGGER native_fail_message"])
                    sent = request(thread_path, actor=actor, payload=reply, expected=201)
                    message_ids.append(sent["message_id"])
                    replay = request(thread_path, actor=actor, payload=reply)
                    require(replay == sent | {"replayed": True}, "Retry did not return the original reply receipt.")
                events = command([
                    *local_db, "--json", "--command",
                    "SELECT COUNT(*) AS events FROM automation_events WHERE event_type = 'message-created'",
                ])
                require(json.loads(events)[0]["results"] == [{"events": 2}], "Reply replay duplicated an audit event.")
                sent_thread = request(thread_path, actor="client")
                require([message["id"] for message in sent_thread["messages"]] == opening_ids + message_ids,
                        "Expected exactly two new synthetic replies.")
                checks.append("native D1 reply failure rolls back and both participants can retry without duplication")
                checks.append("private two-party messaging and outsider rejection")
                # The local D1 CLI takes SQL text; the synthetic row ID is converted to an integer.
                command([
                    *local_db, "--command",
                    ("UPDATE messages SET body = 'Legacy reply: message-fixture@example.test.' "  # nosec B608
                     f"WHERE id = {int(message_ids[-1])}"),
                ])
                retained_marker = b"message-fixture@example.test"
                inbox_path = "/api/messages/threads"
                thread_page = f"/messages/{thread_id}"
                for actor in ("client", "contractor"):
                    for path in (inbox_path, thread_path, "/messages", thread_page):
                        content, headers = request(path, actor=actor, raw=True)
                        require(retained_marker not in content and b"Message withheld" in content
                                and "no-store" in headers.get("Cache-Control", ""),
                                "A participant surface disclosed or cached retained contact details.")
                    visible = request(thread_path, actor=actor)["messages"]
                    require([item["id"] for item in visible] == opening_ids + message_ids
                            and "Synthetic coordination message" in visible[-2]["body"],
                            "Withholding removed message identity or an unrelated reply.")
                for path in (thread_path, thread_page):
                    content, headers = request(path, actor="admin", raw=True)
                    require(retained_marker in content and "no-store" in headers.get("Cache-Control", ""),
                            "Authorized moderation lost the retained reply or its cache protection.")
                checks.append("retained reply contact text stays out of participant HTML and APIs")
                # This seed runs only on local D1 and interpolates an integer fixture thread ID.
                command([
                    *local_db, "--command",
                    ("WITH RECURSIVE series(n) AS (VALUES(1) UNION ALL SELECT n + 1 FROM series WHERE n < 105) "  # nosec B608
                     "INSERT INTO messages (thread_id, sender_id, body, is_hidden, created_at) "
                     f"SELECT {int(thread_id)}, 2, 'History fixture reply ' || n, "
                     "CASE WHEN n = 52 THEN 1 ELSE 0 END, datetime('now') FROM series"),
                ])
                old_api = f"{thread_path}?through={message_ids[-1]}"
                old_page = f"{thread_page}?through={message_ids[-1]}"
                unread_before = request(inbox_path, actor="client")["stats"]["unread"]
                archived = request(old_api, actor="client")
                max_cursor = request(f"{thread_path}?through=9007199254740991", actor="client")
                archive_html, _ = request(old_page, actor="client", raw=True)
                require(
                    unread_before > 0 and request(inbox_path, actor="client")["stats"]["unread"] == unread_before
                    and archived["history"]["through"] == message_ids[-1]
                    and max_cursor["history"]["through"] == 9007199254740991 and len(max_cursor["messages"]) == 50
                    and b"Latest messages" in archive_html and b'aria-label="New message"' not in archive_html,
                    "Older history changed unread state or did not offer a return to the latest view.",
                )
                request(old_api, actor="other_contractor", expected=403)
                for path in (thread_path, thread_page):
                    for query in ("through=", "through=1&through=2", "through=9007199254740992"):
                        request(f"{path}?{query}", actor="client", raw=True, expected=400)
                newest_html, _ = request(thread_page, actor="client", raw=True)
                require(newest_html.count(b'<article id="message-') == 50 and b"Older messages" in newest_html
                        and b'aria-label="New message"' in newest_html, "Latest view is not bounded and replyable.")
                for actor, expected_count in (("client", 107), ("admin", 108)):
                    history_ids, history_page = [], request(thread_path, actor=actor)
                    for _ in range(3):
                        items = history_page["messages"]
                        require(len(items) <= 50, "History returned an oversized page.")
                        ids = [item["id"] for item in items]
                        require(ids == sorted(ids), "History lost chronological order.")
                        history_ids.extend(reversed(ids))
                        cursor = history_page["history"]["next_through"]
                        if cursor is None:
                            break
                        history_page = request(f"{thread_path}?through={cursor}", actor=actor)
                    require(cursor is None and len(history_ids) == expected_count
                            and history_ids == sorted(set(history_ids), reverse=True)
                            and history_ids[-1] == opening_ids[0], "History lost replies or repeated them.")
                checks.append("bounded native history reaches all allowed replies without changing archived read state")
                if verify_candidate_browser:
                    subprocess.run(
                        [node, str(ROOT / "tests" / "browser" / "release_candidate_boundaries.cjs")],
                        cwd=ROOT, env=environment | browser_environment,
                        input=json.dumps({"base": base + "/", "consumerToken": tokens["client"], "threadPath": thread_page}),
                        text=True, timeout=75, check=True,
                    )
                    checks.append("isolated Chromium verifies keyboard access to native message history")
                request(
                    f"/api/jobs/{job_id}/close",
                    actor="client",
                    payload={
                        "reason_code": "workdoe-match",
                        "note": "Synthetic work completed.",
                    },
                )
                completion = f"/api/match-requests/{match_id}/complete"
                request(completion, actor="other_contractor", payload={}, expected=403)
                request(completion, actor="client", payload={})
                done = request(completion, actor="contractor", payload={})
                require(
                    done.get("verified") is True and bool(done.get("verified_at")),
                    "Two participant confirmations did not verify completion.",
                )
                contractor_history = request("/api/contractor/bids", actor="contractor")
                consumer_history = request("/api/client/jobs", actor="client")
                require(
                    contractor_history["completed_work"][0]["completion_state"]
                    == "verified",
                    "Contractor completed-work history lacks verified completion.",
                )
                require(
                    consumer_history["history"][0]["budget"] == "Budget open"
                    and consumer_history["stats"]["verified_completions"] == 1,
                    "Consumer history did not retain the no-budget completed project.",
                )
                checks.append("mutual completion and role history reads")
                admin_outcomes, _ = request("/admin", actor="admin", raw=True)
                require(
                    b"<span>Bid approval</span><strong>1 of 2</strong>" in admin_outcomes
                    and b"<span>Verified complete</span><strong>1</strong>" in admin_outcomes,
                    "Native admin outcomes did not count the visible bid and completion cohort.",
                )
                command([*local_db, "--command", "UPDATE jobs SET status = 'hidden' WHERE id = 1"])
                try:
                    hidden_outcomes, _ = request("/admin", actor="admin", raw=True)
                    require(
                        b"<span>Bid approval</span><strong>0 of 0</strong>" in hidden_outcomes
                        and b"<span>Verified complete</span><strong>0</strong>" in hidden_outcomes,
                        "Native admin counted the completion of a hidden project.",
                    )
                finally:
                    command([*local_db, "--command", "UPDATE jobs SET status = 'closed' WHERE id = 1"])
                checks.append("native admin bid and completion totals use the same visible cohort")
                repeat_job = job | {
                    "title": "Synthetic repeat window project",
                    "idempotency_key": "native-fixture-repeat-000001",
                    "repeat_source_job_id": job_id,
                    "repeat_match_request_id": match_id,
                }
                before_repeat = publish_state()
                command([*local_db, "--command", """
                    CREATE TRIGGER native_fail_invitation BEFORE INSERT ON automation_events
                    WHEN NEW.event_type = 'repeat-provider-invited'
                    BEGIN SELECT RAISE(ABORT, 'synthetic invitation failure'); END
                """])
                request("/api/jobs", actor="client", payload=repeat_job, expected=503)
                invites = json.loads(command([
                    *local_db, "--json", "--command", "SELECT COUNT(*) AS total FROM repeat_provider_invitations",
                ]))[0]["results"]
                require(invites == [{"total": 0}] and publish_state() == before_repeat,
                        "A failed repeat invitation left a public project or a private invitation.")
                command([*local_db, "--command", "DROP TRIGGER native_fail_invitation"])
                repeat = request("/api/jobs", actor="client", payload=repeat_job, expected=201)
                require(repeat["repeat_provider_invited"] is True
                        and request("/api/jobs", actor="client", payload=repeat_job) == repeat | {"replayed": True},
                        "Repeat publication did not create or replay the invitation.")
                invites = json.loads(command([
                    *local_db, "--json", "--command",
                    "SELECT job_id, source_job_id, source_match_request_id, contractor_id, status FROM repeat_provider_invitations",
                ]))[0]["results"]
                require(invites == [{
                    "job_id": repeat["job_id"], "source_job_id": job_id, "source_match_request_id": match_id,
                    "contractor_id": 2, "status": "pending",
                }], "The repeat publication did not keep exactly one invitation to the original contractor.")
                checks.append("native D1 repeat invitation failure rolls back the new project and retries exactly once")
                repeat_bid_path = f"/api/jobs/{repeat['job_id']}/request"
                before_repeat_bid = bid_state()
                command([*local_db, "--command", """
                    CREATE TRIGGER native_fail_repeat_bid BEFORE INSERT ON automation_events
                    WHEN NEW.event_type = 'repeat-provider-invitation-bid-sent'
                    BEGIN SELECT RAISE(ABORT, 'synthetic repeat bid audit failure'); END
                """])
                request(repeat_bid_path, actor="contractor", payload=bid, expected=503)
                require(bid_state() == before_repeat_bid, "A failed repeat bid changed the bid or invitation.")
                command([*local_db, "--command", "DROP TRIGGER native_fail_repeat_bid"])
                request(repeat_bid_path, actor="contractor", payload=bid, expected=201)
                request(repeat_bid_path, actor="contractor", payload=bid, expected=409)
                require(bid_state() == {key: value + 1 for key, value in before_repeat_bid.items()},
                        "Repeat bid retry did not save one bid, acknowledgement, event and invitation change.")
                checks.append("native repeat bid and invitation roll back and commit together")
                request(photo, actor="other_contractor", raw=True, expected=403)
                request(photo, actor="contractor", raw=True)
                request(photo, actor="client", raw=True)
                project_report = request("/api/reports", actor="contractor", payload=report, expected=201)
                replay_report = request("/api/reports", actor="contractor", payload=report)
                require(replay_report == project_report | {"replayed": True},
                        "An authorized project report did not save and replay once.")
                request(
                    f"/api/admin/reports/{project_report['report_id']}/resolve",
                    actor="admin", payload={},
                )
                reported = request(
                    "/api/reports",
                    actor="client",
                    payload={
                        "target_type": "message",
                        "target_id": message_ids[1],
                        "reason": "Synthetic moderation exercise, not a real safety report.",
                        "idempotency_key": "native-report-000000000001",
                    },
                    expected=201,
                )
                message_action = f"/api/admin/messages/{message_ids[1]}/hide"
                request(message_action, actor="client", payload={}, expected=403)
                request(message_action, actor="admin", payload={})
                moderated = request(old_api, actor="client")
                require(
                    all(
                        message["id"] != message_ids[1]
                        for message in moderated["messages"]
                    ),
                    "A hidden message remains visible to a match participant.",
                )
                admin_page, _ = request("/admin", actor="admin", raw=True)
                admin_archive, _ = request(old_page, actor="admin", raw=True)
                message_fragment = f"message-{message_ids[-1]}".encode("ascii")
                require(
                    f'{old_page}#message-{message_ids[-1]}'.encode("ascii") in admin_page
                    and b'id="' + message_fragment + b'"' in admin_archive
                    and b'class="status hidden">hidden</span>' in admin_archive,
                    "Moderator could not reach the exact hidden message from the report.",
                )
                checks.append("native report link locates the exact older hidden reply")
                request(
                    f"/api/admin/reports/{reported['report_id']}/resolve",
                    actor="admin",
                    payload={},
                )
                request("/api/admin/users/2/suspend", actor="admin", payload={})
                request("/api/contractor/bids", actor="contractor", expected=403)
                request(
                    thread_path,
                    actor="contractor",
                    payload={"body": "Not allowed."},
                    expected=403,
                )
                routine_event = {
                    "object": "event", "type": "user.updated",
                    "data": {"id": "user_native_contractor"},
                }
                webhook(routine_event, valid=False)
                webhook({"object": "event", "type": "session.created", "data": {"id": "session_native_fixture"}})
                webhook(routine_event)
                request("/api/contractor/bids", actor="contractor", expected=403)
                request("/api/contractors/2", expected=404)
                webhook(routine_event)
                request("/api/contractor/bids", actor="contractor", expected=403)
                request("/api/contractors/2", expected=404)
                request("/api/admin/users/2/activate", actor="admin", payload={})
                request("/api/contractor/bids", actor="contractor")
                webhook({
                    "object": "event", "type": "user.updated",
                    "data": {
                        "id": "user_native_webhook", "banned": True,
                        "primary_email_address_id": "email_conflict_fixture",
                        "email_addresses": [{
                            "id": "email_conflict_fixture", "email_address": "client@native.invalid",
                            "verification": {"status": "verified"},
                        }],
                    },
                })
                webhook({
                    "object": "event", "type": "user.deleted",
                    "data": {"id": "user_native_webhook"},
                })
                request("/api/admin/users/7/activate", actor="admin", payload={}, expected=503)
                counts_json = command(
                    [
                        "d1",
                        "execute",
                        "native-journey",
                        "--local",
                        "--json",
                        "--command",
                        (
                            "SELECT (SELECT COUNT(*) FROM moderation_actions) AS actions, "
                            "(SELECT COUNT(*) FROM reports WHERE status = 'resolved') AS resolved_reports, "
                            "(SELECT COUNT(*) FROM service_policy_acknowledgements WHERE context = 'project-post') AS post_acknowledgements, "
                            "(SELECT COUNT(*) FROM service_policy_acknowledgements WHERE context = 'mini-bid') AS bid_acknowledgements, "
                            "(SELECT COUNT(*) FROM match_completions WHERE verified_at IS NOT NULL) AS completions, "
                            "(SELECT status FROM users WHERE id = 7) AS webhook_status, "
                            "(SELECT COUNT(*) FROM automation_events WHERE event_type = 'clerk-webhook-rejected') AS forged_audit, "
                            "(SELECT COUNT(*) FROM automation_events WHERE event_type = 'clerk-webhook-verified' "
                            "AND json_type(payload_json, '$.sync.action') = 'text' "
                            "AND json_type(payload_json, '$.subject_id') IS NULL "
                            "AND json_type(payload_json, '$.event_id') IS NULL) AS minimized_webhook_audit, "
                            "(SELECT COUNT(*) FROM automation_events WHERE event_type = 'clerk-webhook-verified') AS webhook_audit"
                        ),
                    ]
                )
                counts = json.loads(counts_json)[0]["results"][0]
                require(
                    counts["actions"] == 5
                    and counts["resolved_reports"] == 2
                    # Two publications plus the successful edit and restoration above.
                    and counts["post_acknowledgements"] == 4
                    and counts["bid_acknowledgements"] == 3
                    and counts["completions"] == 1,
                    f"Native D1 audit, advisory or completion counts differ: {counts}",
                )
                checks.append(
                    "reporting, admin-only moderation, suspension and persisted audit records"
                )
                require(counts["webhook_status"] == "suspended", "Email conflict prevented a signed Clerk ban.")
                require(
                    counts["forged_audit"] == 0 and counts["minimized_webhook_audit"] == counts["webhook_audit"] == 4,
                    "Forged or irrelevant Clerk events reached D1, or verified audit rows retained provider IDs.",
                )
                checks.append(
                    "signed Clerk webhook verification, healthy reactivation and deleted-provider denial"
                )
                if verify_recovery:
                    recovery = verify_local_recovery(command, stage, config)
                    restored_config = stage / "restored" / "wrangler.jsonc"
                    restored_port = free_port()
                    restored_base = f"http://127.0.0.1:{restored_port}"
                    with (
                        (stage / "restored-worker.log").open(
                            "w", encoding="utf-8"
                        ) as restored_log,
                        local_worker(
                            cli,
                            restored_config,
                            environment,
                            restored_port,
                            restored_log,
                        ) as restored_process,
                    ):
                        wait_for_worker(
                            restored_process,
                            lambda: request("/health", base_url=restored_base),
                        )
                        client_history = request(
                            "/api/client/jobs", actor="client", base_url=restored_base
                        )
                        contractor_history = request(
                            "/api/contractor/bids",
                            actor="contractor",
                            base_url=restored_base,
                        )
                        require(
                            any(
                                item["id"] == job_id
                                for item in client_history["history"]
                            )
                            and contractor_history["stats"]["verified_completions"]
                            == 1,
                            "Restored histories lost the mutually completed project.",
                        )
                        request(
                            thread_path,
                            actor="other_client",
                            expected=403,
                            base_url=restored_base,
                        )
                        restored_thread = request(
                            old_api, actor="contractor", base_url=restored_base
                        )
                        require(
                            all(
                                item["id"] != message_ids[1]
                                for item in restored_thread["messages"]
                            ),
                            "Restored thread exposed a moderated message.",
                        )
                        for media_path, actor in (
                            (photo, "contractor"),
                            ("/media/contractors/9201", "client"),
                        ):
                            request(
                                media_path,
                                raw=True,
                                expected=401,
                                base_url=restored_base,
                            )
                            content, headers = request(
                                media_path,
                                actor=actor,
                                raw=True,
                                base_url=restored_base,
                            )
                            require(
                                content == expected_image
                                and headers.get("Cache-Control") == "private, no-store"
                                and headers.get("Content-Type") == "image/webp",
                                "Restored media bytes, type or privacy policy differ.",
                            )
                        request(
                            photo,
                            actor="other_contractor",
                            raw=True,
                            expected=403,
                            base_url=restored_base,
                        )
                    recovery["restored_worker_checks"] = (
                        "histories, private thread, moderated-message omission and private media"
                    )
                    verify_restored_containment(
                        cli, stage, environment, request, command, thread_path=thread_path, photo=photo,
                    )
                    recovery["containment_checks"] = (
                        "paused browsing, sealed D1 and media reads, protected writes and background handlers"
                    )
                    restored_states = synthetic_clerk_account_states(command, restored_config, restored=True)
                    before = compare_synthetic_account_restrictions(
                        synthetic_clerk_account_states(command, config), restored_states,
                    )
                    require(before["source_suspensions"] > 0 and before["restored_as_active"] == 0
                            and before["absent_from_restore"] == 0 and before["restore_only_suspensions"] == 0,
                            "The synthetic source and restore did not start with matching restrictions.")
                    webhook({
                        "object": "event", "type": "user.updated",
                        "data": {"id": "user_native_contractor", "banned": True},
                    })
                    request("/api/contractor/bids", actor="contractor", expected=403)
                    after = compare_synthetic_account_restrictions(
                        synthetic_clerk_account_states(command, config),
                        synthetic_clerk_account_states(command, restored_config, restored=True),
                    )
                    expected_restrictions = before | {
                        "source_suspensions": before["source_suspensions"] + 1, "restored_as_active": 1,
                    }
                    require(after == expected_restrictions, "Restriction comparison missed the post-snapshot synthetic ban.")
                    recovery["restriction_comparison"] = after
                    evidence_path = record_local_recovery(recovery)
                    print("LOCAL RECOVERY: " + json.dumps(recovery, sort_keys=True))
                    print(f"LOCAL RECOVERY EVIDENCE: {evidence_path}")
                    checks.append(
                        "independent local D1 export/restore and synthetic R2 byte recovery"
                    )
                    checks.append("restored Worker distinguishes read-only and sealed modes without background writes")
                    checks.append("sealed synthetic restore detects a post-snapshot account restriction by stable identity")
                eligibility = request("/__native/email-eligibility", payload={})
                require(
                    eligibility == {"accepted": 3, "opt_out_suppressed": 2, "suspension_suppressed": 3},
                    "Local native delivery did not recheck consent, access and current fields.",
                )
                checks.append("native D1 email eligibility rechecks consent and suspension with a stub sender")
                if verify_marketplace_email_pause:
                    endpoint = "/__native/marketplace-email-pause"
                    require(request(endpoint, payload={}) == {"events": []}, "Optional fanout was not paused.")
                    require(
                        request(f"{endpoint}?enqueue=1", payload={}) == {"ok": True},
                        "Could not queue synthetic receipts.",
                    )
                    deadline = time.monotonic() + 20
                    while True:
                        events = request(endpoint, payload={})["events"]
                        if len(events) >= 4 or time.monotonic() >= deadline:
                            break
                        time.sleep(0.5)
                    expected_types = {
                        "stale-match-reminder", "repeat-provider-invitation",
                        "contractor-lead-alert-fanout", "contractor-new-lead",
                    }
                    for event in events:
                        require(
                            event["event_type"] == "email-message-suppressed" and event["status"] == "processed",
                            "A synthetic receipt did not take the default-off path.",
                        )
                        payload = json.loads(event["payload_json"])
                        require(
                            set(payload) == {"type", "reason", "attempts"}
                            and payload["reason"] == "marketplace-email-paused"
                            and payload["attempts"] == 1 and payload["type"] in expected_types,
                            "Unexpected or duplicate suppression record.",
                        )
                        expected_types.remove(payload["type"])
                    require(not expected_types, "Not all four native queue events were suppressed.")
                    checks.append("real local Queue suppresses four stale optional events without an Email binding")
                if verify_email_binding:
                    for case, outcome in (
                        ("accepted", {"acked": 1, "retried": 0}),
                        ("invalid", {"acked": 1, "retried": 0}),
                        ("restricted-recipient", {"acked": 0, "retried": 1}),
                    ):
                        observed = request(f"/__native/email?case={case}", payload={})
                        require(
                            observed == outcome,
                            f"Native Email binding {case}: expected {outcome}, got {observed}.",
                        )
                    checks.append(
                        "local-only Email binding acceptance, invalid-payload acknowledgement and restricted-recipient retry"
                    )
            except Exception:
                log.flush()
                lines = (stage / "worker.log").read_text(encoding="utf-8").splitlines()
                print(
                    "\n".join(
                        line
                        for line in lines
                        if line.startswith(("[wrangler:", "Error:", "Traceback"))
                    )[-2000:]
                )
                raise
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-recovery",
        action="store_true",
        help="Additionally restore the synthetic local D1/R2 state into a fresh independent directory.",
    )
    parser.add_argument(
        "--verify-email-binding",
        action="store_true",
        help="Additionally qualify the native Email simulator; never enables remote email.",
    )
    parser.add_argument("--verify-candidate-browser", action="store_true", help="Verify release media and 404 behavior in isolated Chromium.")
    parser.add_argument("--area-map", action="store_true", help="Verify the opt-in same-origin map in the loopback Worker.")
    parser.add_argument(
        "--verify-marketplace-email-pause", action="store_true",
        help="Exercise optional-email suppression with a native local queue and no email sender.",
    )
    options = parser.parse_args()
    for check in run_journey(
        verify_email_binding=options.verify_email_binding,
        verify_recovery=options.verify_recovery,
        verify_candidate_browser=options.verify_candidate_browser,
        verify_marketplace_email_pause=options.verify_marketplace_email_pause,
        area_map=options.area_map,
    ):
        print(f"PASS: {check}")
    if not options.verify_email_binding:
        print(
            "NOT CHECKED: native Email binding (npm run test:worker:email); "
            "real provider delivery is never tested locally."
        )
