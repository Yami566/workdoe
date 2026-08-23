# Workdoe Cloudflare Automation And Clerk Auth

This is the production direction for `workdoe.com`: keep users on Workdoe pages, delegate public identity to Clerk, and use Cloudflare for hosting, storage, email, bot protection, scheduled jobs, and queues.

## Decisions

- Keep `/login`, `/create-account`, and `/post-project` on `workdoe.com`; do not use hosted Clerk Account Portal redirects for public login.
- Use Clerk email-code OTP as the production login strategy.
- Keep the current local email-code flow as the fallback strategy until Clerk is live.
- Keep Workdoe roles, profiles, job permissions, match visibility, moderation, and audit history in Workdoe D1 tables.
- Store Clerk user IDs in `users.external_subject` with `users.auth_provider = 'clerk'`.
- Use Cloudflare Turnstile on the Workdoe forms that still accept unauthenticated or high-risk POSTs.

## Same-Domain Clerk Login

Clerk can support this without sending users away from Workdoe:

1. Configure a Clerk production instance for `workdoe.com`.
2. Enable email sign-up and sign-in with email verification code.
3. Mount Clerk's maintained `SignIn` component inside Workdoe's `/login`, `/create-account`, or `/post-project` page with `withSignUp: true`; do not maintain a custom Clerk OTP state machine.
4. Prefer Clerk's `signUpIfMissing` email-code flow when the selected Clerk SDK supports it, because it sends a verification step before revealing whether the account exists.
5. Configure Clerk's Frontend API proxy to `https://workdoe.com/__clerk` from the Clerk Domains page so Clerk requests stay on Workdoe's primary domain. A Clerk Frontend API CNAME is only an alternate deployment shape.
6. Verify Clerk session tokens server-side before loading a Workdoe D1 user. Use `CLERK_JWT_KEY` for networkless JWT verification where the runtime supports it.

Required production environment values:

- `WORKDOE_AUTH_PROVIDER=clerk`
- `CLERK_FRONTEND_API_URL=https://workdoe.com/__clerk`
- `CLERK_PROXY_URL=https://workdoe.com/__clerk`
- `CLERK_FAPI=https://frontend-api.clerk.dev`
- `CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_WEBHOOK_SECRET`
- `CLERK_JWT_KEY`
- `WORKDOE_SECRET_KEY`
- `WORKDOE_TURNSTILE_SITE_KEY`
- `WORKDOE_TURNSTILE_SECRET_KEY`

## Cloudflare Automation Targets

Use Workers Cron Triggers for recurring maintenance:

- `expire-login-codes`: every 15 minutes, mark stale local fallback login codes and password reset tokens unusable.
- `stale-match-reminders`: daily at 14:00 UTC, queue reminder emails for client mini bids that have been pending longer than 24 hours.
- `moderation-digest`: weekdays at 13:00 UTC, queue an admin digest for open reports, hidden media, suspended users, and unresolved audit actions.

Use Cloudflare Queues for background jobs:

- `workdoe-email`: transactional reminders, admin digests, and fallback OTP/reset emails that are not handled by Clerk.
- `workdoe-media-review`: photo metadata checks, moderation review tasks, and future image safety checks.

Use Cloudflare Email Service for Workdoe-owned transactional email:

- `no-reply@workdoe.com` for admin digests, match reminders, password reset fallback, and non-Clerk operational notices.
- Clerk should send public auth OTP emails when Clerk is the active auth provider.

## Current Scaffold

- `cloudflare/wrangler.jsonc` declares `workdoe.com` custom domains, Python Workers, D1, R2, static assets, queues, cron triggers, and observability.
- `cloudflare/wrangler.jsonc` includes `CLERK_FRONTEND_API_URL`, `CLERK_PROXY_URL`, and `CLERK_FAPI` so the in-page Clerk script uses Workdoe's same-domain `/__clerk` Frontend API proxy.
- `cloudflare/wrangler.jsonc` declares required Clerk, Turnstile, and Workdoe secrets so Wrangler blocks deploys when production auth values are missing.
- `/login`, `/create-account`, and `/post-project` now render an in-page Clerk mount when `WORKDOE_AUTH_PROVIDER=clerk`; local mode keeps the Workdoe one-time-code forms.
- The Cloudflare Worker now serves `/`, `/login`, `/create-account`, and `/post-project` as same-domain entry pages with the live lead map/list, the existing Workdoe CSS, and the same Clerk email-code mount; the pages do not send users to hosted Clerk URLs.
- The Cloudflare Worker now proxies `/__clerk/*` to Clerk's Frontend API, sets `Clerk-Proxy-Url`, `Clerk-Secret-Key`, and `X-Forwarded-For`, and derives the forwarded IP from Cloudflare's `CF-Connecting-IP` header.
- `/login` stays a lightweight same-domain sign-in page. It checks the Workdoe session bridge after Clerk signs in, opens the requested Workdoe path for linked users, and sends unlinked Clerk identities to `/create-account` with the selected job preserved.
- `/create-account` is the Workdoe onboarding page. It creates the app-owned client or contractor row only after Clerk verifies the email code and the person chooses a workspace. `/start` remains a compatibility alias.
- `cloudflare/worker/entry.py` contains the first Python Worker handlers for health checks, scheduled jobs, queue consumption, and Clerk webhook intake.
- `cloudflare/worker/clerk_sessions.py` prepares the same-domain Clerk session bridge: it extracts `__session` or bearer tokens, verifies RS256 signatures with Web Crypto, checks Clerk timing and authorized-party claims, and fails closed when verification is unavailable.
- `cloudflare/worker/email_payloads.py` renders queued login-code fallback, password-reset fallback, stale-match-reminder, and moderation-digest emails with escaped HTML, plain text, normalized recipients, Workdoe-domain reset URL enforcement, and strict payload validation.
- `cloudflare/worker/clerk_webhooks.py` verifies Clerk/Svix webhook signatures with raw-body HMAC, timestamp tolerance, and constant-time signature comparison.
- The Cloudflare Worker also serves authenticated post-login shells for `/dashboard`, `/client/dashboard`, `/client/jobs/:job_id`, `/contractor/dashboard`, `/contractor/profile`, `/messages`, `/messages/:thread_id`, `/admin`, `/leads`, `/jobs/new`, and contractor `/jobs/:job_id` routes so Clerk redirects land inside usable Workdoe pages instead of generic JSON.
- `cloudflare/worker/media_access.py` keeps private R2 photo serving testable: it parses only supported Workdoe media routes, rejects unsafe object keys, and mirrors role, ownership, match, and moderation checks before `entry.py` reads from `MEDIA`.
- `cloudflare/worker/media_uploads.py` keeps private R2 uploads testable: it validates Workdoe upload routes, image extensions, MIME types, size limits, ownership, scoped object keys, and media-review queue payloads.
- `automation_events` records cron and queue activity so background work has an audit trail before real email delivery is enabled.
- The admin console shows recent automation events beside moderation audit rows so cron, queue, email, media review, Clerk onboarding, and webhook activity can be checked from `workdoe.com`.
- `cloudflare/.dev.vars.example` lists the Clerk, Turnstile, and Workdoe secret values needed for local Wrangler previews.
- The Clerk webhook endpoint rejects unsigned or stale events, updates already-linked Clerk user rows, blocks email conflicts, and suspends deleted/locked users.
- `GET /api/auth/session` verifies a Clerk session and maps it to an already-linked D1 `users` row. If the Clerk identity is valid but no Workdoe row exists yet, it returns `onboarding_required` so `/create-account` can finish role/profile setup on Workdoe.
- `POST /api/auth/onboard` verifies the Clerk session again, requires a verified Clerk email claim, then creates the app-owned `users`, `client_profiles`, or `contractor_profiles` rows after the person chooses client or contractor.
- `GET /api/client/jobs` verifies the Clerk session, requires an active client account, lists only that client's jobs, and returns open/review/closed dashboard counts from D1.
- `GET /api/client/jobs/:job_id/requests` verifies the Clerk session, requires the owning client or active admin, lists contractor mini bids for one job, and returns review counts plus profile/message links without contractor contact fields.
- The authenticated `/jobs/new` shell submits the job through `POST /api/jobs`, then uploads any selected photos through `/api/media/jobs/:job_id/upload` before opening the client job page.
- The authenticated `/client/jobs/:job_id` shell uses those same D1 contracts and exposes close/reopen actions plus private job-photo uploads through the existing Worker routes.
- `GET /api/contractor/leads` verifies the Clerk session, requires an active contractor account, lists open leads with that contractor's `new/sent` bid state, and returns approximate map pins without client contact or ZIP fields.
- `GET /api/contractor/bids` verifies the Clerk session, requires an active contractor account, lists only that contractor's mini bids, returns pending/approved/rejected dashboard counts, and links approved bids to private message threads.
- `GET` and `POST /api/contractor/profile` verify the Clerk session, require an active contractor account, apply the local profile validation rules, upsert the D1 profile row, and audit `contractor-profile-updated`.
- `GET /contractors/:contractor_id` and `GET /api/contractors/:contractor_id` return privacy-safe public contractor profile facts and visible portfolio photo URLs; inactive profiles are visible only to active admins and direct contact fields stay out of the payload.
- `GET /api/jobs/:job_id` verifies the Clerk session, lets owners/admins see full job detail, lets active contractors inspect non-hidden leads, redacts contractor ZIPs to a prefix, and never returns R2 storage keys.
- `POST /api/jobs` verifies the Clerk session, requires an active client/admin Workdoe row, verifies Turnstile server-side, validates the local job form contract, stores approximate DMV map coordinates, and audits `job-created`.
- `POST /api/jobs/:job_id/close` and `/reopen` verify the Clerk session, require the owning active client, block hidden moderation-owned jobs, update status, and audit `job-closed` or `job-reopened`.
- `POST /api/jobs/:job_id/request` verifies the Clerk session, requires an active contractor Workdoe row, verifies Turnstile server-side, requires an open job, blocks duplicate contractor/job requests, validates the local mini-bid form contract, and audits `match-request-created`.
- `POST /api/match-requests/:request_id/approve` and `/reject` verify the Clerk session, require the job owner or admin, block already-reviewed bids, update the request status, audit the decision, and create the private message thread on approval.
- `/api/messages/threads` verifies the Clerk session, lets approved client/contractor participants list/read/reply, keeps admin review read-only, hides moderated messages from normal users, and audits `message-created`.
- `POST /api/reports` verifies the Clerk session, requires an active Workdoe account, validates job/message/profile targets, writes an open D1 report, and audits `report-created`.
- `/admin` renders the same-domain moderation console, and `/api/admin/*` moderation action routes verify the Clerk session, require an active admin account, update users/jobs/photos/messages/reports through explicit allow-listed actions, insert `moderation_actions`, and audit `admin-moderation-action`.
- The `workdoe-email` queue consumer sends only supported transactional payloads through the `EMAIL` binding, acknowledges invalid payloads after auditing them, and retries transient send failures.
- The Workdoe media routes stream from R2 only after D1 metadata checks. Job photos require a linked Clerk session; active, unhidden contractor portfolio photos can remain visible on public profile pages without exposing the R2 bucket.
- The Workdoe upload routes write images to R2 through the `MEDIA` binding and enqueue `workdoe-media-review` tasks through `MEDIA_QUEUE`; the consumer audits accepted and rejected review messages in `automation_events`.
- Clerk webhooks do not create first-time Workdoe roles or profiles. Workdoe onboarding remains the source of truth for whether someone is a client or contractor.

## Data Migration Shape

- `users.email`: canonical email for Workdoe display, permissions, and admin search.
- `users.auth_provider`: `local` for local prototype users, `clerk` for Clerk-backed users.
- `users.external_subject`: Clerk user ID, unique per provider when present.
- `client_profiles` and `contractor_profiles`: stay app-owned so client and contractor roles remain separate.
- `login_codes` and `password_reset_tokens`: stay for local fallback and can be reduced after Clerk has run cleanly in beta.

## Implementation Order

1. Keep the current local prototype passing all tests.
2. Create the Clerk production app and configure email-code authentication.
3. Configure Clerk's Frontend API proxy URL as `https://workdoe.com/__clerk`, enable Restricted sign-up mode, set the custom sign-up URL to `https://workdoe.com/create-account`, enable email-code sign-in, and disable password sign-in. Confirm the Worker route is deployed before enabling the proxy, then write `clerk-proxy-proof.local.json` from the verified Clerk settings.
4. Run `python scripts\cloudflare_resource_bootstrap.py --json --no-secret-probe`, then `python scripts\cloudflare_resource_bootstrap.py --execute --yes --no-secret-probe` to create D1/R2/Queue resources and apply validated D1 IDs without manual editing. The R2 and Queue steps can be rerun; existing resources are reported as `done-existing`.
5. Configure the Clerk session token template to include a verified primary email claim for Workdoe onboarding, or replace that claim with a verified Clerk Backend API lookup before enabling production account creation.
6. Confirm `/login`, `/create-account`, and `/post-project` load Clerk from `CLERK_FRONTEND_API_URL` and finish onboarding through `/api/auth/session` and `/api/auth/onboard`.
7. Move SQLite to D1 and route uploads through the Workdoe Worker into R2.
8. Enable Cron Triggers and Queues from `cloudflare/wrangler.jsonc`.
9. Turn on Cloudflare Email Service for Workdoe operational mail.
10. Run a beta with local fallback auth disabled only after Clerk session verification and webhooks are stable.

## Legal Consent Boundary

Observed platform behavior: Clerk's Legal Compliance setting can require express
consent before sign-up, and its maintained `<SignUp />` component renders and
handles the checkbox. The Clerk JavaScript SDK used by that component is MIT
licensed. Workdoe therefore keeps the consent interaction inside the existing
Clerk component instead of maintaining a second custom checkbox or custom auth
flow.

Release decision: the non-secret Clerk proof is invalid unless an operator
confirms express consent is enabled for `https://workdoe.com/terms` and
`https://workdoe.com/privacy`. This proves configuration, not legal approval.
Workdoe still needs an owner-approved policy version, change-notice rule, and a
decision about when existing users must re-accept revised documents.

## Secret Setup

Do not put real auth values in `cloudflare/wrangler.jsonc`. Set them with Wrangler or the Cloudflare dashboard:

```powershell
cd cloudflare
wrangler secret put CLERK_PUBLISHABLE_KEY
wrangler secret put CLERK_SECRET_KEY
wrangler secret put CLERK_WEBHOOK_SECRET
wrangler secret put CLERK_JWT_KEY
wrangler secret put WORKDOE_SECRET_KEY
wrangler secret put WORKDOE_TURNSTILE_SITE_KEY
wrangler secret put WORKDOE_TURNSTILE_SECRET_KEY
```

The Worker config requires these names before deploy. Public-looking keys such as the Clerk publishable key and Turnstile site key are still declared as required bindings so local preview and production have the same environment shape.

Before production deploy, export the secret-name list and run the launch doctor:

```powershell
python scripts\cloudflare_launch_status.py
cd cloudflare
python ..\scripts\cloudflare_secret_evidence.py --execute --yes --output ..\cloudflare-secret-list.local.json
cd ..
python scripts\cloudflare_clerk_proxy_proof.py --confirm --confirm-restricted-sign-up --confirm-email-code-only --confirm-legal-consent
python scripts\cloudflare_release_evidence.py --json
python scripts\cloudflare_readiness.py --strict-production --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
python scripts\cloudflare_production_deploy.py --json --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
python scripts\cloudflare_production_deploy.py --execute --yes --secret-list-json cloudflare-secret-list.local.json --clerk-proxy-proof-json clerk-proxy-proof.local.json
```

This verifies the required secret names without exposing secret values, and verifies that Clerk was explicitly checked for the same-domain Frontend API proxy, Restricted sign-up, email-code-only access, and Legal Compliance express consent to Workdoe's Terms and Privacy URLs. Clerk's maintained sign-up component owns the checkbox; Workdoe does not implement a parallel custom consent control.
`cloudflare_launch_status.py` is read-only and safe to rerun between each step; it reports the current phase and the next command without touching Cloudflare.

For the approved GitHub-to-Cloudflare release path, `workdoe_launch_doctor.py --live`
accepts a verified GitHub `production` environment with both Cloudflare deploy
secret names as the noninteractive deployment credential. A second token does
not need to be copied into the local shell. Wrangler's encrypted OAuth profile
can still prove the signed-in account, but current noninteractive `secret list`
calls require `CLOUDFLARE_API_TOKEN`; when that probe is unavailable, the doctor
uses the sanitized secret-name evidence and reports only the missing binding
names. Secret values are never read or printed.

## Email Service Setup

`cloudflare/wrangler.jsonc` declares:

- `send_email` binding `EMAIL`.
- `allowed_sender_addresses = ["no-reply@workdoe.com"]`.
- `WORKDOE_EMAIL_FROM=no-reply@workdoe.com`.
- `WORKDOE_ADMIN_EMAIL=admin@workdoe.com`.

Before production deploy, onboard `workdoe.com` in Cloudflare Email Sending and replace `WORKDOE_ADMIN_EMAIL` with the real admin inbox. The queue consumer supports `login-code`, `password-reset`, `stale-match-reminder`, and `moderation-digest`; Clerk should continue sending public auth OTP emails while Clerk is the active auth provider.

## References Checked

- Cloudflare Python Workers: https://developers.cloudflare.com/workers/languages/python/
- Cloudflare Workers Cron Triggers: https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Cloudflare D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- Cloudflare R2 Workers API: https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- Cloudflare Email Service: https://developers.cloudflare.com/email-service/get-started/send-emails/
- Cloudflare required Worker secrets: https://developers.cloudflare.com/changelog/post/2026-03-24-secrets-config-property/
- Clerk custom sign-in-or-up email code flow: https://clerk.com/docs/guides/development/custom-flows/authentication/sign-in-or-up
- Clerk Legal Compliance: https://clerk.com/docs/guides/secure/legal-compliance
- Clerk JavaScript SDK source and MIT license: https://github.com/clerk/javascript
- Clerk JavaScript SignIn component mounting: https://clerk.com/docs/js-frontend/reference/components/authentication/sign-in
- Clerk production deployment DNS: https://clerk.com/docs/guides/development/deployment/production
- Clerk Frontend API proxying: https://clerk.com/docs/guides/dashboard/dns-domains/proxy-fapi
- Clerk webhook verification: https://clerk.com/docs/reference/backend/verify-webhook
- Svix manual webhook verification: https://www.svix.com/guides/receiving/receive-webhooks-with-python-flask/
