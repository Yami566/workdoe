# D1 And Worker Verification

Date: 2026-08-23

Scope: local release-candidate evidence only. No production migration or deploy
was performed.

## Query plan

The verifier applies all 31 forward-only D1 migrations to an in-memory SQLite
database, seeds deterministic project/photo records, runs `ANALYZE`, and uses
the Worker's exact public-query builder with `EXPLAIN QUERY PLAN`.

Observed plan:

```text
SEARCH jobs USING INDEX idx_jobs_open_geo (status=? AND approx_lat>? AND approx_lat<?)
SEARCH job_photos USING COVERING INDEX idx_job_photos_public_job (job_id=? AND is_hidden=?) LEFT-JOIN
USE TEMP B-TREE FOR GROUP BY
USE TEMP B-TREE FOR ORDER BY
```

There was no `SCAN jobs` or `SCAN job_photos`. The remaining temporary B-trees
serve grouping and selectable sort orders; beta telemetry will determine
whether further specialization is justified. Run the evidence again with:

```powershell
npm run cf:d1:query-plan
```

The global unread-navigation query was also checked for both marketplace roles.
Its role-specific plans use the covering `idx_threads_client` or
`idx_threads_contractor` index, `idx_messages_thread_unread`, and the
`thread_reads` primary-key index. Neither plan scans `threads`.

This follows Cloudflare's guidance to use multi-column indexes for recurring
predicates and joins, verify them with `EXPLAIN QUERY PLAN`, and inspect rows
read rather than only rows returned:
<https://developers.cloudflare.com/d1/best-practices/use-indexes/>.

## Runtime smoke

- Wrangler: 4.125.0, pinned with npm integrity and license provenance.
- Compatibility date: 2026-08-23.
- Local D1: migrations through `0031_thread_nav_indexes.sql` applied.
- Worker dry run: 48 Python modules and 86 assets, 889.92 KiB upload / 163.07
  KiB gzip, with all configured bindings resolved and no config warnings.
- `GET /health`: 200 with HSTS.
- `GET /`: 200 with HSTS and CSP.
- Bounded `GET /api/jobs/open`: 200 with `Cache-Control: no-store` and normalized
  DMV viewport.
- Incomplete viewport: 400 with a bounded validation error.

The bounded public query emitted this structured cost shape:

```json
{
  "event": "d1-public-open-jobs-query",
  "rows_read": 2,
  "rows_written": 0,
  "returned_rows": 0,
  "viewport_applied": false,
  "cursor_offset": 0,
  "family": "",
  "service": "",
  "sort": "newest"
}
```

Search text and viewport coordinates are deliberately excluded from logs.
Production rows-read monitoring remains a live-acceptance gate. Cloudflare D1
exposes per-query row counts through result metadata and account analytics:
<https://developers.cloudflare.com/d1/observability/metrics-analytics/>.
