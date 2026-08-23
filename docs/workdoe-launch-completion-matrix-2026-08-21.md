# Workdoe Launch Completion Matrix

Date: 2026-08-21

Status: current evidence record; no deployment was performed during this review

## State definitions

- **Implemented:** current Flask and Cloudflare source plus focused tests prove
  the behavior.
- **Verified locally:** the behavior was exercised in the local browser or by
  the full automated suite.
- **Production stale:** current source contains the requirement, but the live
  Worker does not yet serve that release.
- **Operator gate:** only the owner, account operator, or qualified counsel can
  provide the remaining decision or evidence.
- **Live acceptance required:** implementation exists, but a real production
  account, service, or recovery exercise is still required.

## Active-goal requirements

| Requirement | Current state | Authoritative evidence | Remaining proof |
| --- | --- | --- | --- |
| Six numbered, icon-led work families | Implemented and verified locally | `workdoe/service_taxonomy.py`, `cloudflare/worker/service_taxonomy.py`, `workdoe/templates/_service_family_filter.html`, `docs/ux-audit/2026-08-21-gamified-selection/`, `docs/ux-audit/2026-08-21-gamified-work-selector/`, and the current commercial-journey capture | Production deploy and mobile acceptance on the live Worker |
| Six common tasks per family plus more-services disclosure | Implemented and verified locally | Distinct pinned task icons and numbered choices in `workdoe/templates/_project_composer.html`, Cloudflare parity in `cloudflare/worker/app_shell.py`, and family/service taxonomy tests | Real consumer comprehension testing |
| Selected family leads to task-filtered browse or family/task-prefilled posting | Implemented and verified locally | Canonical `service` filtering in Flask and Worker entry shells/public APIs; exact-task lead-board browser evidence | Production deploy |
| Structured storage instead of uncontrolled AI categorization | Implemented | Canonical family/service slugs, task icon names, and deterministic recall aliases in SQLite and D1 migrations through `0026`; saved lead views and alert matching retain the exact task; research decision in the gamified-marketplace study | Validate DMV demand and supply before adding optional semantic retrieval |
| Public map/list of approximate projects | Implemented; older production version is live | `/api/jobs/open`, Leaflet/OpenStreetMap assets, read-only production smoke | Deploy current filters and six-family presentation |
| Consumer project posting and repeat-work profile | Implemented and browser-verified locally | Six-step composer with always-visible dialog actions, draft persistence, saved coarse locations, project templates, prior-project history, repeat-provider invitations, and `docs/ux-audit/2026-08-21-commercial-journeys/` | Real production consumer acceptance journey |
| Contractor discovery, bid, profile, and completed-work history | Implemented and browser-verified locally | Services/zones, website, intro, photos, availability, credentials, proposal templates, exact-task saved lead filters, mini bids, match completion, privacy-safe history, and current dashboard/profile captures | Real production contractor acceptance journey and eligible pilot supply |
| One permanent beta role per account | Implemented | Role checks in Flask and Worker routes; authorization tests | Production account journey with separate consumer and contractor users |
| Same-page, same-domain one-time-code sign-in | Implemented and browser-verified locally; production configuration incomplete | Compact in-place email-code dialog, Worker Clerk proxy, email-code routes, query-preserving lead sign-in test, same-domain proxy smoke check, and current journey capture | Clerk live instance, restricted sign-up/email-code proof, disabled-password proof, express legal-consent proof, and real code delivery |
| Cloudflare-managed production architecture | Implemented in source | Python Worker, immutable and chain-hashed D1 migrations verified against a blank Wrangler database, private R2, Images sanitizer, Queues, Email binding, Turnstile, rate limiter, custom domains, bounded JSON/form/webhook/upload request readers, and strict preflight | Deploy current Worker; prove Images, R2, queues, email, and rate limiter live |
| Controlled GitHub-to-Cloudflare release | Implemented and intentionally manual | GitHub production environment check, dry-run deployment scripts, guarded workflow, launch-doctor coverage that recognizes the verified GitHub credential path without requiring a duplicate local token, and generated handoffs limited to current required actions | One owner-approved dispatch after all release evidence passes |
| Competition, UX, monetization, and DMV launch research | Complete as a decision record | `docs/workdoe-dmv-gamified-marketplace-commercial-launch-study-2026-08-21.md` and cited public/official sources | Interview DMV consumers, contractors, and operators; counsel review is not replaced by desk research |
| Open-source and code provenance controls | Dependency notices implemented; Workdoe license undecided | `THIRD_PARTY_NOTICES.md`, pinned vendored-asset hashes, `requirements-audit.txt`, `.secrets.baseline` | Owner selects MIT, Apache-2.0, or proprietary status for original Workdoe code |

## Verification run

The 2026-08-21 local verification produced:

- 207 unit/integration tests passing;
- all 26 numbered migrations applying to a blank local D1 database through
  Wrangler, plus the independent SQLite migration-chain check passing;
- strict Cloudflare production preflight passing;
- the production Worker bundle dry run completing with all configured D1, R2,
  Images, Queue, Email, rate-limiter, asset, and environment bindings resolved;
- `pip-audit` reporting no known vulnerabilities in `requirements.txt`;
- `npm audit` reporting zero known vulnerabilities;
- Bandit reporting zero medium or high findings after fixed SQL statements
  replaced allow-listed dynamic identifiers;
- the public project-draft Worker route rejecting missing, unsupported, or
  oversized request bodies before calling `request.formData()`;
- `detect-secrets-hook` passing against the reviewed non-secret baseline;
- Python compilation, JavaScript syntax, and Git diff checks passing.
- current public, project-composer, email-code entry, contractor dashboard/profile,
  and consumer dashboard/history states captured and inspected in
  `docs/ux-audit/2026-08-21-commercial-journeys/`.
- the final entry selector and project task selector captured in
  `docs/ux-audit/2026-08-21-gamified-work-selector/`; browser checks found six
  visible family tiles, 53 task cards using 50 task-specific icons, and no
  broken images.

The secret baseline findings were reviewed as test-only credentials,
dependency-integrity hashes, secret-variable names, or deliberately invalid URL
fixtures. Ignored local Cloudflare/Wrangler state and `.dev.vars` are excluded
from the repository gate and must never be committed.

## Live production result

Read-only checks against `https://workdoe.com` prove:

- HTTPS, DNS, apex and `www`, public jobs, entry security headers, social share
  metadata, and the Workdoe same-domain Clerk asset proxy are healthy;
- the deployed `/health` response lacks the `write_rate_limiter` binding;
- the deployed `/safety`, `/privacy`, and `/terms` routes return 404;
- the deployed sign-in uses a Clerk development instance;
- the current live Worker is therefore older than the launch-candidate source.

The current read-only launch doctor also confirms that the GitHub `production`
environment and its Cloudflare deploy secret names are ready, DNS is ready, and
Wrangler identity is authenticated. The missing local `CLOUDFLARE_API_TOKEN` is
now correctly a warning for this GitHub release path, not a launch blocker. The
remaining technical release evidence is specific: add `CLERK_WEBHOOK_SECRET`,
refresh the sanitized Worker secret-name evidence, and record the production
Clerk proxy, restricted-sign-up, email-code-only, and legal-consent proof.

## Gates that code cannot honestly close

1. Configure a Clerk production instance, add `CLERK_WEBHOOK_SECRET`, confirm
   restricted sign-up, email-code-only access, and Clerk Legal express consent
   to the Workdoe Terms and Privacy URLs, then record the non-secret proof.
2. Name the legal operator and monitored support/privacy/security owner; approve
   age, prohibited-work, retention/deletion, contractor-status, and policy copy.
3. Select Workdoe's own source license posture.
4. Approve each service/jurisdiction pair with legal/safety evidence and at
   least three eligible contractors plus an operational backup.
5. Prove real production consumer, contractor, admin, email, media, queue,
   backup/restore, rollback, incident, accessibility, and usability journeys.
6. Run one guarded deployment, rerun strict production smoke, and retain the
   resulting evidence before inviting the controlled beta cohort.

## Commercial recommendation

Launch free and invite-only in a small set of operationally bounded services:
interior cleaning, move cleaning, packing/unpacking, in-home lifting, and
freestanding furniture assembly. Keep exterior, hauling/disposal, wall
attachment, property alteration, and licensed trades inactive until their
service-zone records pass the evidence and supply gates.

Do not launch pay-per-lead. First establish valid-post, qualified-bid,
approval, verified-completion, repeat-use, report-resolution, and support-cost
evidence. The earliest responsible revenue experiments are optional contractor
workflow tools that do not change organic eligibility, or a plainly disclosed
fixed success fee after Workdoe has payment, refund, and verified-booking
operations.
