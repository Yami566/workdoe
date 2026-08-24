# Workdoe Cloudflare Migration Notes

This local prototype is intentionally shaped so it can move to `workdoe.com` on Cloudflare without changing the product model.

## Target Services

- Cloudflare Workers Python: app and API logic.
- D1: structured relational data now stored in SQLite.
- Cloudflare Images: decode and transcode user uploads before storage; requires
  an Images Paid subscription for the production binding.
- R2: private job photos and contractor portfolio files.
- Clerk: same-domain public login mounted on `workdoe.com` with email-code OTP.
- Clerk Frontend API proxy: `https://workdoe.com/__clerk`, served by the Workdoe Worker so auth requests stay on the primary domain.
- Cloudflare Email Service: Workdoe-owned transactional email from `workdoe.com`.
- Cloudflare Turnstile: signup, login, job posting, and report forms.
- Workers Cron Triggers and Queues: recurring maintenance and background jobs.
- Cloudflare DNS/Registrar: attach the already-purchased `workdoe.com` domain when ready.

## Migration Shape

- Refresh Cloudflare handoff artifacts before each deployment review:

```powershell
python scripts\prepare_cloudflare_release.py
```

This verifies and copies the immutable D1 baseline when producing a handoff,
then writes:

- `cloudflare/d1/migrations/0001_initial.sql`
- `cloudflare/workdoe-cloudflare-manifest.json`
- `cloudflare/wrangler.jsonc`
- `cloudflare/.dev.vars.example`

If real D1 IDs are already present, release prep preserves them instead of replacing them with placeholders.

- Keep `0001_initial.sql` immutable. Every schema change is a new sequentially
  numbered migration; release prep hashes the entire migration chain, and
  strict preflight applies all migrations to a blank database before deploy.
- Replace local upload writes with Workdoe Worker upload routes that sanitize
  through the `IMAGES` binding and write WebP output to R2 using scoped keys:
  - `jobs/{job_id}/{uuid}.webp`
  - `contractors/{contractor_id}/{uuid}.webp`
- Keep photo buckets private. Serve files through app routes that check role, ownership, match status, and moderation status.
- Keep upload permissions route-owned: clients can upload photos only to their own jobs, admins can assist on job photos, and contractors can upload only to their own portfolio.
- Enqueue `workdoe-media-review` after each successful sanitized R2 upload and
  D1 metadata insert so moderation has an audit trail. This queue is for human
  content review and reconciliation; it is not represented as malware scanning.
- Keep the local one-time-code auth flow as a fallback while production login moves to Clerk email-code OTP.
- Link Clerk users to Workdoe rows through `users.auth_provider` and `users.external_subject`.
- Move local reset links, match reminders, and admin digests to transactional email once Cloudflare Email Service is enabled for `workdoe.com`.
- Add Turnstile verification server-side before accepting account creation, login, job posts, match requests, and reports.
- Add Cron Triggers for login-code cleanup, stale match reminders, and moderation digests.
- Add Queues for email delivery work and media review work.

For the detailed identity and automation plan, see [cloudflare-automation-auth.md](cloudflare-automation-auth.md).

## Cloudflare Worker Scaffold

The first Cloudflare-native slice lives in `cloudflare/worker/entry.py` and is configured by `cloudflare/wrangler.jsonc`.

It currently handles:

- `GET /health` and `GET /healthz` for binding checks.
- `GET /`, `GET /login`, `GET /create-account`, and `GET /post-project`, which serve a same-domain Clerk email-code entry shell with the Workdoe deer logo, live lead map/list, and no hosted-login redirect. `GET /start` remains a compatibility alias.
- `GET`/`POST`/`HEAD /__clerk/*`, which proxy Clerk Frontend API traffic through `workdoe.com`, set Clerk's required proxy headers, and use Cloudflare's `CF-Connecting-IP` value as the original client IP.
- Authenticated `GET /dashboard`, `/client/dashboard`, `/client/jobs/:job_id`, `/contractor/dashboard`, `/contractor/profile`, `/messages`, `/messages/:thread_id`, `/admin`, `/leads`, `/jobs/new`, and contractor `/jobs/:job_id` shells, which keep Clerk redirects on Workdoe after sign-in and reuse the existing D1 API data contracts.
- `GET /api/jobs/open`, which reads open jobs from D1 for the sign-in/account map and returns only public lead-card fields with approximate pins.
- `GET /api/jobs/:job_id`, which returns signed-in job detail with full ZIPs only for the owner/admin and ZIP-prefix redaction for contractors.
- `GET /api/client/jobs`, which returns an active Clerk-linked client's own job cards plus open/review/closed mini-bid counts for the dashboard.
- `GET /api/client/jobs/:job_id/requests`, which returns the owning client's pending/approved/rejected contractor mini bids for one job.
- `GET /api/contractor/leads`, which returns an active Clerk-linked contractor's filtered lead board, approximate map pins, and personal `new/sent` bid state.
- `GET /api/contractor/bids`, which returns an active Clerk-linked contractor's pending/approved/rejected mini-bid dashboard rows and message links for approved matches.
- `GET` and `POST /api/contractor/profile`, which let a Clerk-linked active contractor read/update the app-owned contractor profile row with the same local validation rules.
- `GET /api/contractor/preferences`, `POST /api/contractor/preferences/availability`, and `POST /api/contractor/preferences/lead-view`, which keep a contractor's coarse self-reported availability and owner-only saved lead view in D1 without creating an automatic ranking signal.
- `GET` and `POST /api/client/templates` plus `POST /api/client/templates/:id/delete`, which copy reusable scope only from an owned project and exclude location, date, media, bid, message, and outcome data.
- `GET` and `POST /api/contractor/credentials` plus `POST /api/contractor/credentials/:id/remove`, which let an active contractor manage only their own unconfirmed credential claims.
- `GET /contractors/:contractor_id` and `GET /api/contractors/:contractor_id`, which return a privacy-safe public contractor profile with visible portfolio photo URLs and no direct contact or R2 storage fields.
- `POST /api/jobs`, which lets a Clerk-linked client create a D1 job after server-side Turnstile validation, curated category/DMV ZIP validation, approximate coordinate derivation, and allow-listed service-scope validation; normalized quote-readiness codes are replaced through a D1 batch and the `/jobs/new` shell can then upload selected photos through the private media route.
- `POST /api/jobs/:job_id/close` and `/reopen`, which let the owning Clerk-linked client close or reopen a non-hidden job and audit the status change.
- D1 migration `0020_job_scope_answers.sql`, which adds versioned,
  queryable answer-code rows for published projects and pre-verification drafts
  without duplicating descriptions, locations, contacts, or media metadata.
- `POST /api/jobs/:job_id/request`, which lets a Clerk-linked contractor send one pending mini-bid per open job after server-side Turnstile validation and local bid-contract validation.
- `POST /api/match-requests/:request_id/approve` and `/reject`, which let the owning Clerk-linked client or admin decide a pending mini-bid; approval opens the private thread and seeds the first contractor message.
- `GET /api/messages/threads`, `GET /api/messages/threads/:thread_id`, and `POST /api/messages/threads/:thread_id`, which let matched clients and contractors list, read, and reply inside approved private threads while admins can review thread detail without replying.
- `POST /api/reports`, which lets any active Clerk-linked Workdoe user report a job, message, or contractor profile into D1 moderation review.
- `POST /api/match-requests/:request_id/review`, `POST /api/reviews/:review_id/response`, and `POST /api/reviews/:review_id/report`, which gate one structured review per participant on mutual completion, allow one recipient response, and route participant reports to moderation without adding a star score.
- `/api/admin/users/:id/:action`, `/api/admin/jobs/:id/:action`, `/api/admin/photos/job/:id/:action`, `/api/admin/photos/contractor/:id/:action`, `/api/admin/messages/:id/hide`, `/api/admin/reports/:id/resolve`, `/api/admin/reviews/:id/:action`, `/api/admin/review-reports/:id/resolve`, and `/api/admin/credentials/:id/:action`, which let active Clerk-linked admins perform allow-listed moderation and credential-review actions with D1 audit rows.
- `POST /api/media/jobs/:job_id/upload` and `POST /api/media/contractors/:contractor_id/upload`, which validate Clerk-linked ownership, image type, size, R2 key scope, and D1 metadata before queueing media review.
- `GET` and `HEAD` media routes for `/media/jobs/:photo_id` and `/media/contractors/:photo_id`, which check D1 metadata before reading the private R2 object.
- `/static/*` asset pass-through through the `ASSETS` binding.
- Cron cleanup for expired local fallback login/reset tokens.
- Daily queueing for stale mini-bid reminders.
- Weekday queueing for the moderation digest.
- Queue-consumer audit logging into `automation_events`.
- Admin visibility for recent `automation_events` so Cloudflare Cron and Queue activity can be reviewed inside the Workdoe moderation console.
- Email queue consumption through Cloudflare Email Service's `EMAIL` binding for supported Workdoe transactional messages, including fallback login codes, fallback password resets, stale mini-bid reminders, repeat-provider invitation alerts, and moderation digests.
- Event-driven matching-project fanout on the existing email queue. A new job ID is queued after publication; the consumer rechecks saved-view consent plus canonical service/zone fit, creates one deduplicated delivery row, and queues a privacy-safe contractor message without delaying publication.
- `/clerk/webhook`, which verifies Clerk/Svix signatures, updates already-linked Clerk users, suspends deleted/locked users, and audits signed events.
- `GET /api/auth/session`, which verifies a same-domain Clerk session and maps it to an already-linked Workdoe D1 user.
- `POST /api/auth/onboard`, which verifies the Clerk session again and creates the first app-owned client or contractor Workdoe row only after role choice.

Webhook sync is intentionally limited to rows that already have `users.auth_provider = 'clerk'` and `users.external_subject = <Clerk user id>`. First-time role/profile creation still belongs to Workdoe's same-domain login/onboarding flow so a webhook cannot invent a client or contractor account.

Onboarding is also fail-closed: the Worker requires a verified Clerk email claim before creating the D1 `users` row. If the Clerk session template does not include that claim, configure the claim in Clerk or add a verified Clerk Backend API lookup before enabling production account creation.

The Cloudflare public jobs API intentionally mirrors the local Flask map contract: `id`, `title`, `category`, `city`, `state`, `lat`, `lng`, `url`, `action_label`, and the non-personal `license_preference` boolean. The preference is advisory only and never changes order or access. It does not return ZIP codes, descriptions, client contact fields, exact addresses, or photo storage keys before a match is approved.

The Cloudflare same-domain entry shell intentionally mirrors the local `/create-account`, `/post-project`, and `/login` direction: the lead map and lead list appear before account creation, Clerk mounts inside `workdoe.com`, email-code sign-in stays on the same site, and the shell only renders public job facts. `/post-project` carries consumer intent directly into `/jobs/new`; `/login` is kept to sign-in only and sends unlinked Clerk identities to `/create-account` with the selected job preserved so role/profile creation stays explicit.

The Cloudflare authenticated app shell closes the first post-login gap: unauthenticated app routes redirect to `/login?next=...`, `/dashboard` routes by Workdoe role, clients can reach a post-job form backed by `POST /api/jobs`, selected job photos are uploaded immediately afterward through `/api/media/jobs/:job_id/upload`, clients can review/approve/reject mini bids, close/reopen jobs, and upload private job photos at `/client/jobs/:job_id`, contractors can browse `/leads`, contractors can update `/contractor/profile`, approved matches can message through `/messages/:thread_id`, admins can operate `/admin`, and selected contractor jobs can submit mini bids through `POST /api/jobs/:job_id/request`.

The Cloudflare signed-in job detail API intentionally mirrors the local contractor lead detail contract: contractors can view non-hidden jobs, see the description and visible photo URLs, but only receive city/state plus ZIP prefix; owners and admins can see the full ZIP and hidden-photo review flags.

The Cloudflare client jobs API intentionally mirrors the local client dashboard contract: active clients can list only jobs they own, filter all/open/review/closed, and see total/pending/approved/rejected mini-bid counts without receiving contractor contact fields.

The Cloudflare client requests API intentionally mirrors the local mini-bid review contract: only the job owner or an active admin can list requests, pending bids stay reviewable, approved bids link to the private thread, and contractor emails, phone numbers, and storage fields stay out of the payload.

The Cloudflare contractor leads API intentionally mirrors the local lead board contract: it lists only open jobs, scopes bid status to the active contractor row, keeps approximate map pins, and omits ZIP codes, client ids, client emails, exact addresses, and photo storage keys.

The Cloudflare contractor bids API intentionally mirrors the local contractor dashboard contract: it lists only the active contractor's mini bids, filters all/pending/approved/rejected, routes approved bids to the private thread, and keeps client ids plus client contact fields out of the payload.

The Cloudflare contractor profile API intentionally mirrors the local profile form contract: only active contractor accounts can update their own profile, curated trade choices preserve Workdoe ordering, intro/website/year limits match the local app, optional websites must be public HTTPS URLs, and profile updates are audited. The profile UI shares the same seven-step readiness model as Flask; legacy contractor phone values are cleared on update rather than exposed.

The Cloudflare credential API intentionally mirrors the local claim ledger. Contractors may submit allow-listed credential types and DMV/federal/other jurisdictions but cannot mark a claim source checked, change review provenance, or delete source-checked/expired history. Active administrators may set only source-checked, needs-info, not-confirmed, or expired states. Source checks require a normalized public HTTPS link and create both moderation and automation audit records. Public profile payloads fail closed to current source-checked records and omit the stored identifier, claimed name, reviewer, and private note.

The Cloudflare public contractor profile API intentionally mirrors the local public profile contract: active profiles are public, inactive profiles require an active admin session, visible portfolio photos are linked through `/media/contractors/:photo_id`, and direct contact details plus R2 object keys stay out of the payload.

The Cloudflare moderation report API intentionally mirrors the local report form contract: only active signed-in users can report, targets are limited to jobs/messages/contractor profiles that still exist, reason notes stay under 500 characters, and the response never echoes the report reason.

The Cloudflare admin moderation dashboard and API intentionally mirror the local admin controls: active admins can review open reports, users, jobs, photos, recent messages, completed-work feedback, feedback reports, and audit history, then suspend/activate users, hide/restore jobs, photos, and reviews, hide messages, and resolve reports. Each action uses an allow-listed route and records both a `moderation_actions` row and an `admin-moderation-action` automation event.

The completed-work feedback API intentionally mirrors the local participant contract. Only an active consumer or contractor on an approved match with mutual completion can submit, and a D1 uniqueness constraint limits each reviewer to one record for that match. Only the feedback subject can respond once; either participant can report once; and hidden feedback cannot receive a response. Public/profile projections contain no client identity, contact data, ZIP/address, media, or bid terms. Review, response, and report narratives are excluded from automation-event payloads, and the feature never changes rank, eligibility, payment, or placement.

The Cloudflare job posting API intentionally mirrors the local Flask job form contract: title, curated category, city, DC/MD/VA state, 5-digit ZIP, optional future desired date, and 20-1200 character description. It requires a verified Clerk-linked client user and server-side Turnstile Siteverify before inserting into D1. It stores only approximate map coordinates from DMV ZIP/city data; exact addresses remain out of the MVP posting contract.

Project list and detail responses also compute the same six named brief-readiness
signals as the local prototype. The Worker reads only canonical service,
description length, controlled scope-answer count, coarse setting, desired date,
and budget-or-photo presence. No readiness value is persisted, and it does not
enter D1 lead ordering, service activation, match eligibility, or paid placement.

The Cloudflare client job status API intentionally mirrors the local client control contract: only the owning client can close/reopen, hidden jobs stay reserved for moderation paths, and every status change is written to `automation_events`.

The Cloudflare mini-bid API intentionally mirrors the local contractor bid form contract: scope note, price/range, timeline, relevant experience, optional questions, and availability. It requires an active contractor account, an open job, server-side Turnstile Siteverify, and no existing match request for the same contractor/job pair before inserting a pending request.

The Cloudflare mini-bid decision API intentionally mirrors the local client review contract: only the job owner or an admin can approve/reject, already-reviewed requests are rejected as conflicts, rejection returns to the client job view, and approval creates or reuses the private message thread before returning its `/messages/:thread_id` URL.

The Cloudflare private messaging API intentionally mirrors the local approved-thread contract: only the client and contractor on a thread can list/read/reply, admins can inspect a thread for moderation but cannot reply, hidden messages stay hidden from normal users, and responses do not expose contact emails or exact addresses.

The Cloudflare private media routes intentionally mirror the local Flask media contract:

- Job photos require a verified same-domain Clerk session linked to an active Workdoe user.
- Clients can see their own job photos, contractors can see photos on open jobs, approved matched contractors can keep access after a job closes, and admins can review hidden media.
- Contractor portfolio photos remain visible on public profiles only when the photo is not hidden and the contractor account is active; owners and admins can still review hidden or inactive-account photos after sign-in.
- R2 object keys must stay under the D1-owned prefix, such as `jobs/{job_id}/...` or `contractors/{contractor_id}/...`; traversal, absolute paths, backslashes, and owner-prefix mismatches are rejected.
- Responses use `Cache-Control: private, no-store` and never expose bucket listing routes or raw storage keys.

The Cloudflare upload routes are intentionally narrow:

- Accept only PNG, JPG/JPEG, GIF, and WebP with matching image MIME types.
- Cap files at the same 12 MB local limit.
- Require the `IMAGES` binding, decode the bytes, apply orientation, scale down
  to a 2400-by-2400 bound, discard metadata, flatten animation, and transcode to
  WebP before storage. Invalid images and unavailable sanitization fail closed.
- Write only the sanitized result through the `MEDIA` R2 binding, never the
  Cloudflare REST API; raw upload bytes are not persisted.
- Store only metadata in D1.
- Send a small `media-review` payload to `MEDIA_QUEUE`; the queue consumer validates/audits the task before acknowledging it.

Before the first production upload test, enable Cloudflare Images Paid for the
account and confirm `wrangler.jsonc` contains `"images": {"binding": "IMAGES"}`.
The binding's local low-fidelity implementation is sufficient for contract
tests; final acceptance must exercise a real transformed upload through the
deployed Worker.

Before deploy:

```powershell
python scripts\prepare_cloudflare_release.py
python scripts\cloudflare_preflight.py
python scripts\cloudflare_readiness.py
python scripts\cloudflare_launch_plan.py
python scripts\cloudflare_resource_bootstrap.py --json --no-secret-probe
python scripts\cloudflare_resource_bootstrap.py --execute --yes --no-secret-probe
```

Then copy `cloudflare/.dev.vars.example` to local secret storage for preview, and set the real Clerk, Turnstile, and Workdoe secrets in Cloudflare.
Confirm `CLERK_FRONTEND_API_URL` and `CLERK_PROXY_URL` in `cloudflare/wrangler.jsonc` are both `https://workdoe.com/__clerk`, and confirm Clerk's Domains page uses that same proxy URL before turning on production auth. In Clerk, also enable Restricted sign-up mode, set the custom sign-up URL to `https://workdoe.com/create-account`, enable email-code sign-in, disable password sign-in, and enable Legal Compliance express consent for `https://workdoe.com/terms` and `https://workdoe.com/privacy`. Invitation links then return to Workdoe with Clerk's one-time ticket and never move account creation to an off-domain page. Clerk's maintained sign-up component owns the consent checkbox. After those visual checks, write a local, non-secret proof file so strict readiness and deploy can verify the operator step:

```powershell
python scripts\cloudflare_clerk_proxy_proof.py --confirm --confirm-restricted-sign-up --confirm-email-code-only --confirm-legal-consent
```

Apply D1 migrations and deploy only after those values are set:

```powershell
python scripts\cloudflare_launch_status.py
cd cloudflare
python ..\scripts\cloudflare_secret_evidence.py --execute --yes --output ..\cloudflare-secret-list.local.json
cd ..
python scripts\cloudflare_release_evidence.py --json
python scripts\cloudflare_readiness.py --strict-production --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
python scripts\cloudflare_production_deploy.py --json --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
python scripts\cloudflare_production_deploy.py --execute --yes --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
```

`scripts\cloudflare_readiness.py` is the launch doctor. It keeps regular preflight checks, then adds production-only gates for real D1 IDs, workdoe.com custom domains, same-domain Clerk email-code mode, R2/Queue/Email bindings, required secret names, sanitized evidence from `scripts\cloudflare_secret_evidence.py` that the Cloudflare Worker has every required Clerk, Turnstile, and Workdoe secret configured, and proof that Clerk Domains is pointed at `https://workdoe.com/__clerk`. It never reads or prints secret values.

`scripts\cloudflare_launch_plan.py` is the safe operator plan. It reads the same launch doctor evidence, prints the exact Cloudflare resource, Clerk domain proof, secret, migration, deploy, and smoke-check commands in order, and never executes them itself.

`scripts\cloudflare_launch_status.py` is the read-only status summary. It checks local artifacts, local Wrangler availability, D1 ID state, secret-name evidence, Clerk proxy proof, and the strict deploy gate, then prints the current phase and next command. If it reports `local-tooling`, install Wrangler and run `wrangler login` before attempting live Cloudflare resource creation. The helpers resolve Wrangler from `WORKDOE_WRANGLER_BIN`, repo-local `node_modules/.bin`, or PATH.

`scripts\cloudflare_secret_evidence.py` is the guarded secret-name evidence helper. It is dry-run by default; with `--execute --yes`, it runs `wrangler secret list --json`, strips the result down to secret names only, writes `cloudflare-secret-list.local.json`, and fails the step if any required Workdoe production secret name is missing.

`scripts\cloudflare_release_evidence.py` is the local evidence doctor. It checks `cloudflare-secret-list.local.json` and `clerk-proxy-proof.local.json` together before strict readiness so the operator can quickly see whether both proof files are valid.

`scripts\cloudflare_resource_bootstrap.py` is the guarded resource bootstrap. It is dry-run by default; with `--execute --yes`, it creates the Workdoe D1 production/preview databases, applies the returned IDs to `cloudflare/wrangler.jsonc`, and creates the R2 bucket plus email/media queues. The R2 and Queue steps are rerunnable: if Cloudflare reports that those resources already exist, the helper records the step as `done-existing` and continues.

`scripts\cloudflare_production_deploy.py` is the guarded production deploy helper. It runs strict readiness first, refuses to deploy if D1 IDs, secret-name proof, or Clerk proxy proof are missing, and only applies remote D1 migrations plus `wrangler deploy` when called with `--execute --yes`. Executable production runs cannot disable the post-deploy smoke check. Smoke checks use curl's HTTP failure mode and include capped `output_excerpt` fields in the JSON result so the operator can quickly confirm health headers and public job API output. The GitHub workflow retains that result as `production-deploy.log` beside the D1 Time Travel and Worker rollback evidence for 30 days.

`scripts\apply_cloudflare_d1_ids.py` is the D1 cutover helper. It accepts captured `wrangler d1 create` output or explicit UUIDs, validates that both `database_id` and `preview_database_id` are real non-placeholder Cloudflare UUIDs, and updates only the D1 ID fields in `cloudflare/wrangler.jsonc`.

## Production Defaults

The incremental D1 migration `0003_project_drafts_and_budgets.sql` adds
optional budget bounds and the expiring anonymous draft table. Apply all D1
migrations before releasing the Worker; do not replace the migration history
with a new snapshot on an existing database.
Migration `0014_contractor_credentials.sql` adds the neutral claim/review ledger,
owner and review indexes, reviewer provenance, and checked/expiry timestamps.
Migration `0015_contractor_lead_preferences.sql` adds coarse contractor
availability and one private saved category/query/sort view per contractor.
Migration `0016_client_project_templates.sql` adds up to twelve owner-only
reusable scope templates without location, date, media, bid, or message fields.
Migration `0017_repeat_provider_invitations.sql` adds the private invited-back
lifecycle. It stores only relationship IDs, canonical service, state, and
timestamps; a fresh mini bid remains subject to the ordinary cap, deadline,
service activation, and approval flow. The admin payload derives invitation,
fresh-bid, pass, withdrawal, and invited-contractor verified-completion counts
from these lifecycle rows without adding analytics identifiers or copying prior
project data.
Migration `0018_contractor_lead_alerts.sql` adds default-off saved-view email
consent and a contractor/project delivery ledger. The ledger stores IDs,
delivery state, and timestamps only; project content and recipient addresses
stay outside the table.
Migration `0019_match_reviews.sql` adds completion-gated participant feedback
and one-per-participant report state. It stores match/user references,
controlled dimension codes, capped narrative/response/reason fields, moderation
state, and timestamps; it deliberately contains no contact, location, media,
or bid-term columns.
Migration `0020_job_scope_answers.sql` adds versioned, controlled project-scope
answers without narrative, contact, location, media, or bid fields.
Migration `0021_saved_lead_work_family.sql` adds one allow-listed canonical
work-family slug to each private contractor lead preference plus an index for
consented alert matching. It stores no project, identity, contact, location,
message, media, or ranking data.
Migration `0022_idempotent_marketplace_writes.sql` adds 24-hour duplicate-submit
records for project, ordinary-message, report, and media creation. It stores a
SHA-256 request-key hash, actor/action, generic resource type/ID, state, and
timestamps only. Worker browser forms create keys with Web Crypto; completed
retries return the first resource and in-flight retries fail closed with `409`.
Migration `0023_contractor_proposal_templates.sql` adds six owner-only reusable
wording templates per contractor. It stores scope, timeline, experience,
questions, and availability from an owned mini bid, but no price, project,
client, contact, location, media, ranking, message, or outcome field.
Migration `0034_project_license_preference.sql` adds the same checked boolean to
projects, anonymous drafts, and reusable consumer project templates. The field
is presentation-only: it does not filter contractors, rank bids, determine
service-zone activation, or establish legal eligibility.

- Set `WORKDOE_ENV=production`.
- Set `WORKDOE_AUTH_PROVIDER=clerk` once Clerk is ready.
- Set `CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk`.
- Set `CLERK_PROXY_URL=https://workdoe.com/__clerk`.
- Set `CLERK_FAPI=https://frontend-api.clerk.dev`.
- Set a real `WORKDOE_SECRET_KEY`.
- Set `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET`, and `CLERK_JWT_KEY`.
- Set `WORKDOE_TURNSTILE_SITE_KEY` and `WORKDOE_TURNSTILE_SECRET_KEY` to enable Turnstile on start, login, public project draft, job posting, mini-bid, and report forms.
- Keep `WORKDOE_LOGIN_MODE=same_domain_email_code` for the Cloudflare Worker; the Worker rejects redirect-style Clerk modes. The local Flask prototype uses `WORKDOE_CLERK_LOGIN_MODE` for the equivalent setting.
- `/login`, `/create-account`, and `/post-project` mount Clerk in-page when Clerk mode is enabled; they do not send users to hosted Clerk login pages.
- `/account` mounts Clerk's maintained account and security UI in-page with
  hash routing. Confirm its Account and Security sections load on
  `https://workdoe.com/account` before enabling optional passkeys.
- `cloudflare/wrangler.jsonc` declares these auth/protection names under `secrets.required`, so `wrangler deploy` should fail before production if any required value is missing.
- `workdoe/static/_headers` uses the native Workers Static Assets header
  contract. It gives immutable browser caching only to release-tokened
  first-party CSS/map/composer assets and provenance-pinned vendor/logo assets;
  unversioned application scripts retain Cloudflare revalidation. Preflight
  derives the expected first-party token from those asset bytes, rejects stale
  Flask/Worker constants or missing/unreviewed immutable rules, and production
  smoke verifies the live versioned stylesheet policy.
- `POST /api/jobs` rejects job creation unless the same-domain Clerk session resolves to an active Workdoe client/admin row and Turnstile Siteverify succeeds for `workdoe.com`.
- `GET /api/jobs/:job_id` rejects detail access unless the same-domain Clerk session resolves to the owner, an admin, or an active contractor viewing a non-hidden job.
- `GET /api/client/jobs` rejects dashboard access unless the same-domain Clerk session resolves to an active client and the query stays scoped to that user's jobs.
- `GET /api/client/jobs/:job_id/requests` rejects mini-bid review unless the same-domain Clerk session resolves to the owning active client or an active admin.
- `GET /api/contractor/leads` rejects lead-board access unless the same-domain Clerk session resolves to an active contractor and the query stays scoped to that contractor's bid state.
- `GET /api/contractor/bids` rejects dashboard access unless the same-domain Clerk session resolves to an active contractor and the query stays scoped to that contractor's mini bids.
- `GET` and `POST /api/contractor/profile` reject access unless the same-domain Clerk session resolves to an active contractor account.
- Contractor credential claim routes reject access unless the same-domain Clerk session resolves to the active owning contractor; source-checked and expired records remain in audit history.
- `GET /api/contractors/:contractor_id` hides inactive profiles unless the same-domain Clerk session resolves to an active admin and never returns direct contact fields.
- `POST /api/jobs/:job_id/close` and `/reopen` reject status changes unless the same-domain Clerk session resolves to the owning active client and the job is not hidden.
- `POST /api/jobs/:job_id/request` rejects mini-bids unless the same-domain Clerk session resolves to an active contractor row, the job is open, and no duplicate bid exists.
- `POST /api/match-requests/:request_id/approve` and `/reject` reject decisions unless the same-domain Clerk session resolves to the job owner or an admin and the mini-bid is still pending.
- `/api/messages/threads` routes reject access unless the same-domain Clerk session resolves to an active participant on the approved thread; admin review is read-only.
- `POST /api/reports` rejects report intake unless the same-domain Clerk session resolves to an active Workdoe user and the reported job, message, or profile exists.
- `/api/admin/*` action routes reject access unless the same-domain Clerk session resolves to an active admin, the route is allow-listed, and the moderation target still exists.
- Keep local demo account seeding disabled. Production mode fails closed if demo seeding is enabled.
- Keep secure cookies enabled. Production mode fails closed if secure cookies are disabled.
- Keep client, contractor, and admin roles separate.
- Continue showing approximate city/ZIP map pins until a client approves a match.
- Keep exact address collection out of the lead board until there is a deliberate field-level privacy design.

## Turnstile Integration

Turnstile stays disabled locally until both keys are configured. When enabled, Workdoe renders the managed widget on protected forms and validates `cf-turnstile-response` server-side before route logic runs.

## Email Sending

Cloudflare Email Sending must be onboarded for `workdoe.com` before production email delivery. The Worker uses a restricted `EMAIL` binding that can send only from `no-reply@workdoe.com`. The current queue consumer supports fallback login codes, fallback password resets, client stale-match reminders, contractor matching-project and repeat-provider invitation alerts, and the admin moderation digest. Optional bid-reminder email defaults off until the consumer selects email and saves the profile; D1 stores that consent timestamp, the scheduled query requires it, opting out clears it, and each reminder links to `https://workdoe.com/client/profile#bid-reminders`. Matching-project email also defaults off and requires a contractor to save a view and choose email; fanout additionally requires exact canonical service/zone fit and links back to `https://workdoe.com/leads#saved-lead-alerts` for opt-out. A repeat-provider alert is a single transactional notice created by a consumer's explicit new-project invitation; it contains only the new title, city/state, and an HTTPS `workdoe.com/jobs/:id` link and carries no prior project/contact data. Password reset and project links must remain on Workdoe HTTPS routes; invalid email payloads are audited and acknowledged, while transient send failures are audited and retried by Cloudflare Queues.

## Current Cloudflare References

- Python Workers: https://developers.cloudflare.com/workers/languages/python/
- D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- R2 Workers binding: https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- Turnstile server validation: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- Workers Cron Triggers: https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Cloudflare Queues: https://developers.cloudflare.com/queues/
- Cloudflare Email Service: https://developers.cloudflare.com/email-service/get-started/send-emails/
- Workers Static Assets headers: https://developers.cloudflare.com/workers/static-assets/headers/
- Clerk email-code sign-in-or-up: https://clerk.com/docs/guides/development/custom-flows/authentication/sign-in-or-up
- Clerk webhook verification: https://clerk.com/docs/reference/backend/verify-webhook
- Svix manual webhook verification: https://www.svix.com/guides/receiving/receive-webhooks-with-python-flask/
