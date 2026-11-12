from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from contextlib import closing
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_worker_journey", ROOT / "scripts" / "verify_worker_journey.py"
)
journey = importlib.util.module_from_spec(SPEC)
with mock.patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    SPEC.loader.exec_module(journey)


class NativeJourneyHarnessTests(unittest.TestCase):
    def test_worker_context_is_local_and_reaps_only_its_own_live_process(self):
        config = Path("fixture/wrangler.jsonc")
        for exit_code in (None, 0):
            with self.subTest(exit_code=exit_code):
                process = mock.Mock(pid=321)
                process.poll.return_value = exit_code
                with (
                    mock.patch.object(
                        journey.subprocess, "Popen", return_value=process
                    ) as start,
                    mock.patch.object(journey.subprocess, "run") as stop,
                    self.assertRaisesRegex(LookupError, "test body"),
                    journey.local_worker(
                        ["node", "wrangler.js"], config, {}, 8081, None
                    ),
                ):
                    raise LookupError("test body")
                args = start.call_args.args[0]
                self.assertIn("--local", args)
                self.assertNotIn("--remote", args)
                self.assertEqual(args[args.index("--ip") + 1], "127.0.0.1")
                self.assertEqual(
                    args[args.index("--persist-to") + 1],
                    str(config.parent / ".wrangler" / "state"),
                )
                if exit_code is not None:
                    stop.assert_not_called()
                    process.terminate.assert_not_called()
                elif journey.os.name == "nt":
                    self.assertEqual(
                        stop.call_args.args[0],
                        ["taskkill", "/PID", "321", "/T", "/F"],
                    )
                    self.assertEqual(
                        start.call_args.kwargs["creationflags"],
                        journey.subprocess.CREATE_NO_WINDOW,
                    )
                else:
                    process.terminate.assert_called_once_with()
                process.wait.assert_called_once_with(timeout=15)

    def test_readiness_retries_transient_errors_without_restarting_and_is_bounded(self):
        process = mock.Mock()
        process.poll.return_value = None
        read = mock.Mock(side_effect=[urllib.error.URLError("not ready"), None])
        with mock.patch.object(journey.time, "sleep") as sleep:
            journey.wait_for_worker(process, read)
        self.assertEqual(read.call_count, 2)
        sleep.assert_called_once_with(0.25)
        process.poll.return_value = 1
        read.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "exited before readiness"):
            journey.wait_for_worker(process, read)
        read.assert_not_called()
        process.poll.return_value = None
        read.side_effect = urllib.error.URLError("not ready")
        with (
            mock.patch.object(journey.time, "monotonic", side_effect=[0, 61]),
            mock.patch.object(journey.time, "sleep") as sleep,
            self.assertRaisesRegex(RuntimeError, "did not become ready"),
        ):
            journey.wait_for_worker(process, read)
        sleep.assert_not_called()

    def test_recovery_evidence_contains_source_hashes_not_source_or_row_contents(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            (fixtures / "seed.sql").write_text("synthetic-row-body", encoding="utf-8")
            with (
                mock.patch.object(journey, "ROOT", root),
                mock.patch.object(journey, "FIXTURES", fixtures),
            ):
                script = root / "scripts" / "verify_worker_journey.py"
                script.parent.mkdir()
                script.write_text("synthetic-harness", encoding="utf-8")
                path = journey.record_local_recovery({"tables": 40})
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["recovery"], {"tables": 40})
            self.assertIn("no production restore", record["scope"])
            self.assertEqual(len(record["source_manifest_sha256"]), 64)
            self.assertEqual(len(record["source_files"]["fixtures/seed.sql"]), 64)
            self.assertNotIn("synthetic-row-body", path.read_text(encoding="utf-8"))
            self.assertEqual(path.parent, root / ".test-tmp")

    def test_storage_commands_require_one_unambiguous_local_flag(self):
        config = Path("fixture/wrangler.jsonc")
        safe = ["d1", "execute", "native-journey", "--local", "--command", "SELECT 1"]
        built = journey.local_storage_arguments(safe, config)
        self.assertIn("--persist-to", built)
        self.assertEqual(built[-1], str(config.parent / ".wrangler" / "state"))
        for args in (
            ["d1", "execute", "native-journey"],
            [*safe, "--remote"],
            [*safe, "--remote=false"],
            [*safe, "--local=false"],
            [*safe, "--local"],
            [*safe, "--profile=production"],
            [*safe, "--config=production.json"],
            ["deploy", "--local"],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                journey.local_storage_arguments(args, config)

    def test_local_export_uses_the_same_default_store_without_unsupported_flag(self):
        config = Path("fixture/wrangler.jsonc")
        args = ["d1", "export", "native-journey", "--local", "--output", "dump.sql"]
        built = journey.local_storage_arguments(args, config)
        self.assertNotIn("--persist-to", built)
        self.assertEqual(built[-2:], ["--config", str(config)])

    def test_snapshot_digest_is_canonical_and_identifiers_are_quoted(self):
        self.assertEqual(
            journey.canonical_digest({"a": 1, "b": None}),
            journey.canonical_digest({"b": None, "a": 1}),
        )
        self.assertNotEqual(
            journey.canonical_digest({"id": 1}), journey.canonical_digest({"id": 2})
        )
        self.assertEqual(
            journey.sql_identifier('a"; DROP TABLE users; --'),
            '"a""; DROP TABLE users; --"',
        )

    def test_snapshots_preserve_data_and_sequences_without_depending_on_row_order(self):
        schema = [
            {
                "type": "table",
                "name": "jobs",
                "tbl_name": "jobs",
                "sql": "CREATE TABLE jobs (id INTEGER, title TEXT)",
            }
        ]
        rows = [{"id": 2, "title": None}, {"id": 1, "title": "Synthetic scope"}]

        def command(order, sequence=3):
            def execute(args, *, config_path):
                results = (
                    [schema]
                    if "sqlite_schema" in args[-1]
                    else [
                        order,
                        [{"name": "jobs", "seq": sequence}],
                        [{"quick_check": "ok"}],
                        [],
                    ]
                )
                return json.dumps(
                    [{"success": True, "results": result} for result in results]
                )

            return execute

        first = journey.storage_snapshot(command(rows), Path("fixture/wrangler.jsonc"))
        reordered = journey.storage_snapshot(
            command(list(reversed(rows))), Path("fixture/wrangler.jsonc")
        )
        changed = journey.storage_snapshot(
            command(rows, 4), Path("fixture/wrangler.jsonc")
        )
        self.assertEqual(first, reordered)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(first["rows"]["jobs"]), 2)

    def test_snapshot_rejects_incomplete_or_corrupt_database_results(self):
        schema = [
            {
                "type": "table",
                "name": "jobs",
                "tbl_name": "jobs",
                "sql": "CREATE TABLE jobs (id INTEGER)",
            }
        ]
        for data in (
            [[], [], [{"quick_check": "damaged"}], []],
            [[], [], [{"quick_check": "ok"}], [{"table": "jobs", "rowid": 2}]],
            [[], []],
        ):

            def execute(args, *, config_path, snapshot=data):
                results = [schema] if "sqlite_schema" in args[-1] else snapshot
                return json.dumps(
                    [{"success": True, "results": result} for result in results]
                )

            with self.subTest(data=data), self.assertRaises(AssertionError):
                journey.storage_snapshot(execute, Path("fixture/wrangler.jsonc"))

    def test_restore_orders_schema_before_data_and_triggers_after_data(self):
        schema = [
            {
                "type": "trigger",
                "sql": "CREATE TRIGGER late_trigger AFTER INSERT ON jobs BEGIN SELECT 1; END",
            },
            {"type": "index", "sql": "CREATE INDEX job_idx ON jobs(id)"},
            {"type": "view", "sql": "CREATE VIEW job_view AS SELECT * FROM jobs"},
            {"type": "table", "sql": "CREATE TABLE jobs (id INTEGER, title TEXT)"},
        ]
        dump = "INSERT INTO jobs VALUES (1, 'CREATE TABLE; is scope text');"
        plan = journey.recovery_sql(schema, dump)
        expected_order = [
            "CREATE TABLE jobs",
            "CREATE INDEX job_idx",
            "ANALYZE;",
            dump,
            "CREATE VIEW job_view",
            "CREATE TRIGGER late_trigger",
        ]
        self.assertEqual(
            sorted(plan.index(item) for item in expected_order),
            [plan.index(item) for item in expected_order],
        )
        self.assertIn(dump, plan)
        self.assertTrue(plan.startswith("PRAGMA defer_foreign_keys = ON;"))
        self.assertTrue(plan.endswith("PRAGMA defer_foreign_keys = OFF;"))
        with self.assertRaises(AssertionError):
            journey.recovery_sql([{"type": "unknown", "sql": "DROP TABLE jobs"}], dump)

    def test_recovery_rejects_non_fixture_source_before_any_storage_command(self):
        with tempfile.TemporaryDirectory() as raw:
            stage = Path(raw)
            config = stage / "wrangler.jsonc"
            config.write_text(
                json.dumps(
                    {"name": "production", "vars": {"WORKDOE_ENV": "production"}}
                ),
                encoding="utf-8",
            )
            command = mock.Mock()
            with self.assertRaises(AssertionError):
                journey.verify_local_recovery(command, stage, config)
            command.assert_not_called()
            with self.assertRaises(AssertionError):
                journey.verify_local_recovery(command, stage / "elsewhere", config)
            command.assert_not_called()

    def test_restore_preserves_multiline_text_sequences_and_trigger_behavior(self):
        with (
            closing(sqlite3.connect(":memory:")) as source,
            source,
            closing(sqlite3.connect(":memory:")) as restored,
            restored,
        ):
            source.executescript(
                "CREATE TABLE parents (id INTEGER PRIMARY KEY);"
                "CREATE TABLE children (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "parent_id INTEGER REFERENCES parents(id), scope TEXT);"
                "CREATE TABLE audit (id INTEGER PRIMARY KEY, note TEXT);"
            )
            scope = "First line\r\nSecond line; quoted 'scope'"
            source.execute("INSERT INTO parents VALUES (5)")
            source.execute("INSERT INTO children VALUES (1, 5, ?)", (scope,))
            source.execute("INSERT INTO audit VALUES (77, 'Historical record')")
            source.executescript(
                "CREATE INDEX child_parent ON children(parent_id);"
                "CREATE TRIGGER record_child AFTER INSERT ON children BEGIN "
                "INSERT INTO audit(note) VALUES ('New child'); END;"
            )
            source.execute(
                "UPDATE sqlite_sequence SET seq = 500 WHERE name = 'children'"
            )
            source.commit()
            source.row_factory = sqlite3.Row
            schema = [
                dict(row)
                for row in source.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                    "WHERE name NOT GLOB 'sqlite_*' AND sql IS NOT NULL ORDER BY type, name"
                )
            ]
            sequence_sql = [
                row["sql"] for row in source.execute(journey.SEQUENCE_BACKUP_SQL)
            ]
            quoted_scope = source.execute("SELECT quote(?)", (scope,)).fetchone()[0]
            dump = (
                f"INSERT INTO children VALUES (1,5,{quoted_scope});"
                "INSERT INTO parents VALUES (5);"
                "INSERT INTO audit VALUES (77,'Historical record');"
                + "".join(sequence_sql)
            )
            plan = journey.recovery_sql(schema, dump, sequence_sql)
            restored.execute("PRAGMA foreign_keys = ON")
            restored.executescript("BEGIN;\n" + plan + "\nCOMMIT;")
            self.assertEqual(
                restored.execute("SELECT scope FROM children").fetchone()[0], scope
            )
            self.assertEqual(
                restored.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 1
            )
            self.assertEqual(
                restored.execute("SELECT name, seq FROM sqlite_sequence").fetchall(),
                [("children", 500)],
            )
            self.assertEqual(
                restored.execute("PRAGMA foreign_key_check").fetchall(), []
            )
            with self.assertRaises(sqlite3.IntegrityError):
                restored.execute("INSERT INTO children(parent_id) VALUES (999)")
            restored.rollback()
            restored.execute(
                "INSERT INTO children(parent_id,scope) VALUES (5,'After restore')"
            )
            self.assertEqual(
                restored.execute("SELECT MAX(id) FROM children").fetchone()[0], 501
            )
            self.assertEqual(
                restored.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 2
            )
        for name, connection in (("source", source), ("restored", restored)):
            with self.subTest(database=name), self.assertRaisesRegex(
                sqlite3.ProgrammingError, "closed database"
            ):
                connection.execute("SELECT 1")

    def test_recovery_does_not_replace_an_existing_restore_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            stage = Path(raw)
            config = stage / "wrangler.jsonc"
            config.write_text(
                json.dumps(
                    {
                        "name": "workdoe-native-journey-local-only",
                        "vars": {"WORKDOE_ENV": "local"},
                        "d1_databases": [
                            {"database_id": "00000000-0000-4000-8000-000000000002"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            existing = stage / "restored"
            existing.mkdir()
            sentinel = existing / "preserved.txt"
            sentinel.write_text("preserved", encoding="utf-8")
            command = mock.Mock()
            with self.assertRaises(FileExistsError):
                journey.verify_local_recovery(command, stage, config)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserved")
            command.assert_not_called()

    def test_restriction_comparison_does_not_match_a_reused_row_id(self):
        def projection(rows):
            with closing(sqlite3.connect(":memory:")) as db:
                db.row_factory = sqlite3.Row
                db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, subject TEXT UNIQUE, status TEXT)")
                db.executemany("INSERT INTO users VALUES (?, ?, ?)", rows)
                return [dict(row) for row in db.execute("SELECT subject, status FROM users")]

        current = projection([
            (1, "user_native_original", "suspended"), (2, "user_native_unchanged", "suspended"),
            (3, "user_native_missing", "suspended"),
        ])
        restored = projection([
            (9, "user_native_original", "active"), (2, "user_native_unchanged", "suspended"),
            (3, "user_native_replacement", "suspended"),
        ])
        report = journey.compare_synthetic_account_restrictions(current, restored)
        self.assertEqual(report, {
            "source_suspensions": 3, "confirmed_suspended": 1, "restored_as_active": 1,
            "absent_from_restore": 1, "restore_only_suspensions": 1,
        })
        self.assertNotIn("user_native_", json.dumps(report))

    def test_restriction_comparison_rejects_non_fixture_or_ambiguous_identities(self):
        fixture = {"subject": "user_native_fixture", "status": "suspended"}
        for rows, diagnostic in (
            ([], "incomplete"), ([fixture] * 1001, "over limit"),
            ([fixture, fixture | {"status": "active"}], "Duplicate"),
            ([fixture | {"subject": "user_live_unreviewed"}], "Invalid synthetic"),
            ([fixture | {"id": 4}], "Invalid synthetic"),
            ([fixture | {"status": "unreviewed"}], "Invalid synthetic"),
        ):
            with self.subTest(diagnostic=diagnostic), self.assertRaisesRegex(AssertionError, diagnostic):
                journey.compare_synthetic_account_restrictions([fixture], rows)

    def test_restriction_projection_requires_local_fixture_and_sealed_restore(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "wrangler.jsonc"
            config = {
                "name": "workdoe-native-journey-local-only", "vars": {"WORKDOE_ENV": "local"},
                "d1_databases": [{"database_id": "00000000-0000-4000-8000-000000000002"}],
            }
            command = mock.Mock()
            for settings in (config, config | {"vars": {"WORKDOE_ENV": "production", "WORKDOE_WRITE_MODE": "sealed"}}):
                path.write_text(json.dumps(settings), encoding="utf-8")
                with self.assertRaisesRegex(AssertionError, "sealed restored copy"):
                    journey.synthetic_clerk_account_states(command, path, restored=True)
            command.assert_not_called()
            config["vars"]["WORKDOE_WRITE_MODE"] = "sealed"
            path.write_text(json.dumps(config), encoding="utf-8")
            rows = [{"subject": "user_native_fixture", "status": "active"}]
            command.return_value = json.dumps([{"success": True, "results": rows}])
            self.assertEqual(journey.synthetic_clerk_account_states(command, path, restored=True), rows)
            arguments = command.call_args.args[0]
            self.assertIn("--local", arguments)
            self.assertNotIn("--remote", arguments)
            self.assertEqual(command.call_args.kwargs, {"config_path": path})
            self.assertTrue(arguments[-1].startswith("SELECT external_subject AS subject, status FROM users"))
            self.assertNotIn("email", arguments[-1])

    def test_checks_remain_active_and_redirects_are_refused(self):
        with self.assertRaisesRegex(AssertionError, "failed fixture"):
            journey.require(False, "failed fixture")
        self.assertIsNone(
            journey.NoRedirect().redirect_request(None, None, None, None, None, None)
        )

    def test_disposable_workspace_is_created_and_cleaned_in_test_root(self):
        with (
            tempfile.TemporaryDirectory() as raw,
            mock.patch.object(journey, "ROOT", Path(raw)),
        ):
            with journey.native_workspace() as stage:
                self.assertEqual(stage.parent, (Path(raw) / ".test-tmp").resolve())
                self.assertTrue(stage.is_dir())
            self.assertFalse(stage.exists())

    def test_cleanup_refuses_paths_outside_the_named_parent(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            preserved = root / "preserved"
            preserved.mkdir()
            with (
                mock.patch.object(journey, "ROOT", root),
                mock.patch.object(
                    journey.tempfile, "mkdtemp", return_value=str(preserved)
                ),
                self.assertRaisesRegex(RuntimeError, "Refusing cleanup"),
                journey.native_workspace(),
            ):
                pass
            self.assertTrue(preserved.is_dir())
