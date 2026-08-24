# Account Lifecycle Visibility Evidence

Date: 2026-08-24

Scope: Flask reference runtime and Cloudflare Worker candidate. This evidence
covers immediate marketplace containment after Clerk deletion or suspension;
it does not define or execute permanent data deletion.

## Enforced contract

- Public entry-shell and `GET /api/jobs/open` queries require an active project
  owner.
- Contractor lead queries require an active project owner.
- A contractor cannot open a suspended consumer's project detail or retrieve
  its private photos, including after a previously approved match.
- New mini bids require an active project owner during both the initial project
  lookup and the conditional atomic insert.
- Administrators retain project access for moderation and future approved
  retention, legal-hold, or deletion handling.

## Verification

- Flask integration coverage suspends a seeded consumer and confirms the
  project leaves the public API, home/start surfaces, contractor lead board,
  direct detail, and bid path while remaining available to an administrator.
- Flask private-media coverage confirms a contractor loses photo access when
  the project owner becomes suspended.
- Worker helper coverage confirms project detail and job-photo authorization
  fail closed for an inactive owner.
- Worker query/source contracts cover the public API, entry shell, contractor
  leads, job detail projection, private photo projection, initial bid lookup,
  and atomic bid write.
- The D1 query-plan verifier must continue to report no table scans after the
  active-owner join.
- The complete local suite passed 241 tests in 82.607 seconds after the Flask
  and Worker public-query contract was reconciled.
- The security/provenance gate passed across 681 non-ignored files with no
  Node or Python dependency vulnerability reported.
- Cloudflare preflight completed with no errors or warnings. The D1 verifier
  used `idx_jobs_open_geo`, `idx_job_photos_public_job`, and
  `idx_contractor_photos_public_contractor` and reported no table scans.
- Wrangler 4.125.0 completed a non-deploying package dry run: 49 Python modules,
  88 static assets, 942.15 KiB uploaded size, and 173.14 KiB gzip size.

## Residual decision

Owner/legal approval is still required for retention periods, deletion timing,
legal holds, backups, and treatment of approved conversations after account
suspension. This change prevents new discovery and contractor access; it is not
a substitute for that policy.
