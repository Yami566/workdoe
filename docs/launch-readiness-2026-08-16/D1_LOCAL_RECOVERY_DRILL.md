# D1 Local Recovery Drill

Date: 2026-08-16

Environment: Isolated local Wrangler D1 state only. No remote or production
database command was run.

Operator: Codex

## Procedure

1. Listed pending migrations on the normal local D1 state.
2. Found and applied `0003_project_drafts_and_budgets.sql` locally.
3. Exported the current local `workdoe` D1 database to a restricted temporary
   SQL file.
4. Imported that SQL file into a separate temporary Wrangler persistence
   directory.
5. Queried the source and restored databases for schema and representative row
   counts.
6. Queried the restored `d1_migrations` table.
7. Removed the restricted temporary export and isolated restore state after the
   comparison passed.

## Result

Pass for the local export/import procedure.

Both source and restored states reported:

- 18 application/migration tables
- 4 users
- 0 jobs
- 0 match requests
- 0 messages
- 14 automation events
- 0 project drafts

The restored state recorded all three migrations:

- `0001_initial.sql`
- `0002_email_code_security.sql`
- `0003_project_drafts_and_budgets.sql`

The drill also caught stale local state before export: migration `0003` was
pending. It was applied to the local D1 instance before the successful export
and restore were repeated.

## Limits

This proves the checked-in schema can be exported and imported into an isolated
local D1 state with matching representative counts. It does not prove remote
D1 Time Travel, production backup access, an R2 backup copy, production data
volume recovery time, or owner approval procedures.
