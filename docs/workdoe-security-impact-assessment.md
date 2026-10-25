# Workdoe Security Impact Assessment

Assessment date: 2026-08-17; source-license finding reviewed 2026-08-23;
status-specific production evidence refreshed 2026-10-25.

The current deployment and Clerk findings in
`workdoe-launch-readiness-2026-10-24.md` supersede this document's original
status-specific evidence. This assessment remains the engineering risk model;
the open operational, legal, and live-workflow risks below remain active until
the owner checklist is completed.

**Current beta media decision (2026-10-25):** Public project and contractor
photo uploads are disabled. `WORKDOE_MEDIA_UPLOADS_ENABLED=false`; the
production Worker has no Cloudflare Images binding and no public upload control.
References below to Cloudflare Images resizing, portfolio photos, or active
media-intake controls describe a future, separately reviewed design rather than
current beta functionality. Retained demonstration or legacy media remains
permission-scoped.

Scope: the local Flask reference app, Cloudflare Python Worker, D1 schema, R2
media routes, Clerk same-domain email-code flow, Turnstile validation,
Cloudflare Queues/Cron/Email bindings, public production responses, and release
automation in this repository.

This is an engineering assessment, not a penetration test, legal opinion, or
formal certification against OWASP ASVS or WCAG.

## Data and trust boundaries

### Account and identity data

- Email, external Clerk subject/session identifiers, Workdoe role, account
  status, and one required public business name or non-identifying handle.
  Clerk profile names and email local-parts are not used as the Workdoe public
  label. Onboarding does not collect a separate household or organization name.
- Clerk owns public identity verification; Workdoe owns role, marketplace
  authorization, and profile records.
- The browser presents a token. The Worker verifies its RS256 signature and
  time claims, then resolves the external subject to an active D1 user.

### Marketplace and communication data

- Job description, category, city/ZIP, desired date, approximate coordinates,
  optional budget bounds, status, legacy media metadata, mini bids, prices/ranges,
  availability, messages, reports, and moderation/audit records.
- Public project, bid, message, contractor-profile, and onboarding-label text
  reject common email, phone, and street-address patterns before storage. This
  deterministic guard reduces common accidental disclosures but cannot
  establish that arbitrary free text contains no personal information.
- Private consumer workspace type, label, note, reminder preference, and
  owner-scoped saved city/ZIP project areas. Workspace labels, notes, and
  saved-area labels reject common email, phone, and street-address patterns.
  Workdoe does not collect a saved street address.
- Anonymous project drafts are stored in D1/SQLite under a random-token hash,
  contain no email or photos, expire after 24 hours, and are consumed after the
  verified client posts the project. The raw token stays in an HttpOnly,
  Secure, SameSite=Lax cookie in production.
- Public responses are a limited projection. Protected D1 queries and R2 reads
  enforce ownership, role, active status, visibility, and approved-match state.
- Optional contractor websites are normalized to public HTTPS URLs and exposed
  only to the contractor owner, active administrators, or a consumer who owns a
  project that received that contractor's bid. Phone remains excluded.

### Hosted-service boundaries

- Cloudflare handles edge execution, DNS/TLS, D1, R2, Email, Queues, Turnstile,
  logs, and traces.
- Clerk handles email-code identity and browser authentication state.
- OpenStreetMap supplies public map tiles/data under its own policy.
- These are vendor and privacy boundaries even where the client libraries are
  open source.

## Security objectives

- Keep exact/contact and any retained private-media data from public and
  unmatched users.
- Prevent horizontal and vertical privilege escalation among consumer,
  contractor, and admin roles.
- Make login, signup, content creation, bidding, messaging, and reports
  resistant to automated abuse.
- Keep credentials and provider secrets out of source, logs, and public assets.
- Preserve an auditable moderation and automation history.
- Fail closed when auth, storage, database, Turnstile, or required production
  configuration is absent.

## Controls observed

- HTTPS redirect, HSTS, CSP, frame denial, MIME sniffing prevention, strict
  referrer policy, and a restrictive Permissions Policy on production pages.
- Same-domain Clerk proxy and in-page email-code UI; no hosted-login redirect.
- RS256-only Clerk token verification with Web Crypto, expiration/not-before
  checks, expected session/subject shape, and `azp` authorized-party validation
  when the claim is present.
- Parameterized D1 statements for user-controlled values.
- Project-composer assistance is deterministic and local. The selected
  canonical service supplies an editable project-name suggestion, and the
  existing curated DMV ZIP table can fill city/state in the browser. No
  geolocation, third-party lookup, new stored field, or inferred private value
  is introduced; unknown ZIPs reveal the original required city/state inputs.
- Clerk deletion or suspension immediately removes the consumer's open projects
  from anonymous entry/public API queries and contractor lead queries. Direct
  contractor detail, unmatched private-photo access, initial bid lookup, and the
  atomic bid write also require an active project owner. Administrators retain
  access for moderation and legal/retention handling; this containment does not
  itself delete historical records.
- Service-specific scope intake accepts only allow-listed question keys and
  answer codes from a versioned Python catalog. Local writes replace the owned
  answer set inside the request transaction; the Worker uses prepared
  statements in a transactional D1 batch. Unknown keys are ignored, invalid
  codes are rejected, and the normalized tables contain no freeform narrative,
  address, ZIP, contact, media, or bid fields.
- Compact phone family/task controls are a presentation-only projection of the
  existing deterministic taxonomy. They add no field, inference, recipient,
  ranking signal, script, or storage path; Flask and Worker retain the same
  canonical service values, validation, policy acknowledgement, and fallback
  select contract.
- The public map popup action is a presentation of each job's existing
  permission-aware action label and same-domain URL. It adds no project field,
  exact-location value, contact field, identity inference, recipient, storage,
  or authorization bypass. Signed-out actions retain only the public project
  ID in the validated `next` path and use the existing same-page auth dialog.
- Semantic project-result wrappers and visible action cues are presentation
  only. They reuse existing action labels, same-domain URLs, request status,
  and public project fields; they add no endpoint, payload field, private value,
  storage, inference, ranking signal, or authorization decision. The anchor,
  not its list wrapper, remains the sole interactive element.
- Consumer project lanes filter the existing owner-scoped dashboard records in
  memory after the same role and ownership checks. They add no endpoint, query,
  stored field, public response, recipient, notification, inference, or access
  path. Legacy view aliases normalize before filtering; active, paused, and
  history rows keep their existing same-domain owner URLs and private fields.
- The controlled beta keeps all 53 curated services available with a versioned
  advisory policy. Elevated and regulated services require a current policy
  acknowledgement before a project or mini bid is stored. Service-zone
  activation records are retained for review and a future explicitly approved
  gated rollout; they cannot silently change beta publication, bidding,
  discovery, or ranking. Existing approved conversations remain available if a
  future gated market is paused.
- Mini-bid creation uses one conditional `INSERT ... SELECT` statement that
  rechecks project status, deadline, total response count, and per-contractor
  uniqueness at write time. Rejected responses still count, preventing a
  consumer from cycling through unlimited contractor effort. Bid-window
  extensions require the active owning consumer, remaining capacity, and an
  expired open project, and create an automation audit event.
- Consumer bid comparison is a read-only projection of at most four pending
  offers in received order. It exposes only protected bid terms, contractor
  display/trade labels, separately qualified self-reported profile facts,
  current source-check count, and aggregate mutually verified Workdoe history.
  It omits contact fields, addresses, ZIP, coordinates, websites, credential
  identifiers, narratives from other workflows, fit scores, recommendations,
  and paid placement. Approval remains on the full offer and reuses the existing
  owner/status-checked match-decision endpoint.
- Project closure requires a server-validated reason code and caps the optional
  owner/admin-only note at 300 characters. Reopening clears the active reason,
  note, and close timestamp while preserving an allow-listed audit event;
  automation payloads store the reason code but not the private note.
- Contractor lead-quality feedback requires an active contractor with an
  existing bid on the project. A unique `(job_id, contractor_id)` constraint
  makes the signal updateable instead of creating a spam stream. Consumers and
  other contractors do not receive the note, and no signal automatically
  changes account status, ranking, or marketplace eligibility.
- Contractor website validation rejects credentials, local and single-label
  hosts, IP literals, nonstandard ports, malformed DNS labels, and embedded
  whitespace/control characters. External links display only the hostname and
  use `noopener noreferrer nofollow external`.
- Contractor credential claims use allow-listed types, jurisdictions, states,
  and admin actions. Contractors can create and remove only unconfirmed claims;
  they cannot self-confirm, edit review provenance, or delete source-checked or
  expired audit history. Public projections fail closed to current
  `verified` records, omit identifiers and private review notes, normalize the
  source to public HTTPS, and describe the result only as `Source checked`.
- A consumer may attach one boolean license-record preference to a project,
  pre-verification draft, or reusable project template. Public and contractor
  projections expose only that boolean and advisory copy. It never filters
  bids, changes received order, affects lead fit, or represents a
  scope/jurisdiction eligibility decision; both roles are told to confirm the
  current record directly.
- Contractor availability and saved lead views use allow-listed states,
  canonical work-family slugs, categories, and sort values plus a bounded
  search string. Invalid family values are cleared from public reads and
  rejected on saved-view writes. The public profile projection receives only
  coarse self-reported availability; saved family, query, category, sort, and
  timestamps remain owner-only. No embedding or inferred classifier is stored,
  and these values do not change marketplace rank or eligibility.
- Collapsing the saved-view and alert controls is presentation-only. It adds no
  endpoint, script, storage field, recipient data, inferred preference, or
  automatic consent; the existing explicit radio choice and server-side
  validation remain authoritative.
- Contractor matching-project email is disabled by default and requires a
  saved lead view plus an explicit email preference and consent timestamp. A
  fanout rechecks active/available status, saved work-family and category/query
  fit, exact canonical service capability, exact DMV zone, open bid window, and
  absence of an existing bid. The email contains only the new title, service label,
  city/state, and same-domain project/settings links. D1 delivery rows contain
  IDs, state, and timestamps only; opting out clears consent.
- The admin service-zone pulse is a computed aggregate over canonical service,
  coarse zone, and Monday week. Its shared local/Worker helper accepts no
  account or contact field, its response omits project IDs and narratives, and
  its preflight check rejects identity/contact markers. It is read-only,
  administrator-only, excludes local demo accounts, and has no path to ranking,
  moderation, account state, or service activation. Current supply is labeled
  as current because no historical supply snapshot is retained. First-bid
  timestamps are converted to non-negative project response durations and then
  reduced to a cell median; the response contains no raw bid timestamp. Open
  reports are reduced to one boolean contribution per project without reporter
  identity, reason text, or moderation narrative. Controlled close reasons are
  grouped into Workdoe match and cancelled/no-fit counts without exposing the
  owner-only close note.
- Consumer project templates can be created only from a project owned by the
  active consumer and deleted only by the template owner. The table stores
  reusable service/scope/setting/budget fields but has no location, desired-date,
  photo, bid, message, outcome, or completion columns. Template launch restores
  blank location/date fields for explicit review in the existing composer.
- Contractor proposal templates can be created only from a mini bid submitted
  by the active contractor, are capped at six per owner, and can be read or
  deleted only under that contractor ID. D1 stores reusable wording but no
  price, client identity, project/location/contact field, media, ranking, or
  outcome. Applying a template renders escaped values and always resets price
  to blank; creation/deletion audit payloads retain IDs only, not bid content.
- Repeat-provider invitations require an active consumer, an owned closed
  project marked `workdoe-match`, an approved match, mutual completion
  verification, and an active contractor. The new project must retain the same
  canonical service. Invitation actions recheck the exact consumer or
  contractor ID, and bid conversion updates only that contractor's pending
  invitation. Closing the new project withdraws an unanswered invitation. No
  invitation bypasses service-policy acknowledgement, bid cap, deadline, duplicate-bid,
  Turnstile, or match-approval controls.
- A production repeat invitation queues one transactional email after the new
  invitation record exists. Its link validator accepts only HTTPS
  `workdoe.com/jobs/:id` URLs without query strings or fragments; the payload
  includes the new title and city/state but no consumer identity, prior ZIP,
  address, contact, scope, messages, media, or bid terms. Queue failure is
  audited and does not delete or conceal the in-product invitation.
- Route-level role/ownership checks for jobs, bids, profiles, messaging,
  reports, moderation, and media.
- Completion confirmation rechecks active role, exact approved-match
  participation, approved bid state, and closed project state. Consumer and
  contractor timestamps are written independently, repeated confirmation is
  idempotent, and a project cannot reopen after either confirmation begins.
- Completed-work feedback requires the same active match participant, approved
  bid, and mutual `verified_at` state. A database uniqueness constraint permits
  one review per reviewer/match; controlled dimensions and work-again values
  reject arbitrary classification codes. Only the subject can respond, each
  participant can report once, and hidden feedback cannot receive a response.
  Review tables contain no email, phone, address, ZIP, or media fields.
- Contractor-profile review projection is limited to client-authored feedback
  from mutually verified matches and only when the profile itself is visible
  through ownership, administration, or an existing bid relationship. It
  carries the service label but no client identity, location, contact, or bid
  terms. Reviews do not alter search order, bid eligibility, account status, or
  paid placement.
- Contractor milestone labels, points, earned-state markers, and next-threshold
  progress are a deterministic presentation of the aggregate mutually verified
  completion count. The milestone track adds no stored profile field, event,
  credential inference, identity signal, eligibility change, or ranking
  weight. Flask and Worker projections are contract-tested for equality.
- Consumer offer cards may project the newest non-hidden contractor-photo ID
  through the existing permission-checked `/media/contractors/:id` route. The
  comparison never receives the R2 key or original filename, does not bypass
  photo moderation, and does not use photo presence for order, eligibility, or
  credential status. The D1 lookup is covered by a composite contractor/media
  visibility index.
- State-changing Worker API routes require the Workdoe same-origin custom
  request marker; JSON endpoints also reject non-JSON bodies. This complements
  SameSite cookies and browser preflight behavior, including multipart photo
  uploads and email-code authentication requests.
- Authenticated non-auth API writes pass through Cloudflare Workers Rate
  Limiting, keyed by the stored Workdoe user ID. The generated production
  binding permits 40 changes per 60 seconds per Cloudflare location, returns
  `429` with `Retry-After`, and fails closed when the binding is unavailable.
- Sign-out is POST-only in both the Worker and local reference app; no reviewed
  safe-method route changes session state.
- Private R2 storage with object-key prefix validation, no bucket listing,
  private/no-store media responses, and scoped D1/R2 compensating cleanup when
  metadata or queue handoff fails.
- A future media intake design requires Cloudflare Images before R2. Matching
  extension/MIME/signature input would be decoded, orientation applied, output
  bounded to 1600 pixels per side, animation flattened, and the result
  transcoded to WebP so invisible metadata is discarded. The inactive code path
  retains source-file, sanitized-result, quota, generic-filename, and
  fail-closed binding checks, but it is not enabled or a public beta promise.
- Server-side Turnstile Siteverify checks, expected hostname/action checks, and
  fail-closed production configuration.
- Curated DMV ZIP/category validation, upload MIME/extension/signature allow
  lists, a 4 MB source-file cap, and a sanitized stored-WebP cap below 1.5 MB.
- Consumer profile and saved-area routes require an active consumer role,
  scope reads/deletes by the stored owner ID, cap each account at eight areas,
  and expose only an approximate ZIP prefix in the rendered saved-area list.
- Webhook, JSON, and multipart handlers require a positive bounded request body
  length before consuming the body, protecting the Worker's 128 MB memory
  budget from unbounded input reads.
- Whole-dollar project budget validation with a fixed upper bound and
  minimum/maximum ordering checks.
- Existing account roles are authoritative during sign-in and onboarding;
  conflict-safe first-time creation preserves the stored role, conflicting
  consumer/contractor intent cannot change it, and its role profile is repaired
  idempotently.
- Native fallback email codes are HMAC-protected, attempt/rate limited, and
  consumed through one conditional D1 update before account or session
  issuance, so concurrent requests cannot reuse one OTP.
- Required Worker secret names declared outside source; `.env`, `.dev.vars`,
  local evidence, databases, and Wrangler state are ignored.
- Moderation and automation audit records; admin thread review is read-only,
  ordinary moderation rejects administrator and self account targets, and
  allow-listed feedback actions can only hide/restore a review or resolve its
  report. Automation payloads retain structured codes/booleans, never review,
  response, or report narrative.
- Manual-only guarded GitHub release workflow with preflight and post-deploy
  smoke gates.
- Automated tests cover principal role, ownership, redaction, media, auth,
  Turnstile, rate limiting, moderation, two-sided completion, and release
  contracts.
- Transactional email audit events retain keyed recipient references and
  allow-listed delivery metadata instead of full queue bodies, OTPs, reset
  links, recipient addresses, subjects, or arbitrary provider results.
- A successfully delivered transactional email is explicitly acknowledged
  before its best-effort D1 audit write, so an audit outage cannot redeliver an
  OTP, reset, reminder, repeat invitation, or moderation email.
- Matching-project fanout and delivery are deduplicated by a unique
  contractor/project record. Fanout queue failure cannot block project
  publication; an email provider failure follows the existing Queue retry path.
- Report creation rechecks that the reporter can see the target; a private
  message can be reported only by an administrator or one of its approved
  thread participants.
- The selected-thread conversation rail reuses the participant-scoped thread
  listing projection and its 50-row bound. It adds no new message, identity,
  contact, address, or recipient field. The Worker report disclosure reuses the
  existing same-origin, authenticated-rate-limit, idempotency, target-visibility,
  and Turnstile controls; administrators still cannot reply.
- Message reply state is computed only inside the existing participant-scoped
  50-thread query by comparing the current participant ID with the latest
  non-hidden message sender. The response emits only `needs_reply`; it does not
  return the sender ID, create a table or event, notify another recipient,
  infer urgency or sentiment, or change ranking. The latest visible message is
  resolved once through the existing `idx_messages_thread_unread` index.
- Server-rendered marketplace output escapes user-controlled content, with a
  regression that injects script-shaped text across representative views.
- Project brief readiness is a six-field deterministic projection shared by
  local and Worker runtimes. It excludes identity, contact, exact-location,
  contractor-fit, review, bid-behavior, and payment fields; it is displayed as
  named checks and cannot alter lead rank, activation, or eligibility.
- `CLERK_WEBHOOK_SECRET` is part of the generated configuration, readiness,
  preflight, and release secret contract.

## Assessment findings

### High launch risk

1. **Updated 2026-10-24:** the current signed-in Clerk review and strict
   production smoke evidence show a production Clerk configuration, the
   same-domain Workdoe proxy, Open access, email-code sign-in/sign-up, disabled
   passwords/phone/email links, and legal-consent URLs. This removes the old
   development-key finding, but it does not prove that the newer local release
   candidate has been deployed. Rerun the strict smoke after that reviewed
   release and whenever Clerk configuration changes.
2. Production-candidate Privacy, Terms, Safety, footer-policy navigation,
   `robots.txt`, `sitemap.xml`, and `security.txt` surfaces now exist in both
   Flask and the Cloudflare Worker. Moose Bay and Company LLC is identified as
   the Virginia operator and `admin@workdoe.com` has an ordinary 1-to-5-business
   day target, but an approved retention/deletion schedule, urgent incident
   path, binding terms acceptance, and final legal review remain unresolved.
   Do not open unrestricted public account creation until the policy checklist
   is approved and the reviewed candidate routes are deployed.
3. One owner-controlled consumer email-code sign-in and session refresh have
   been proven. A separate contractor sign-in and the full two-role project,
   photo, bid, approval, message, completion, reporting, and moderation journey
   remain unproven. Automated tests verify contracts, not live delivery, D1/R2
   state, or a complete approved-match workflow with real identities.
4. Backup/restore, security incident response, credential rotation, user data
   deletion/export, and abuse escalation are documented in
   `docs/workdoe-operations-runbook.md`. The ordinary inbox owner and response
   target are recorded, but urgent escalation ownership, approved retention
   rules, and completed drill evidence are still missing.
5. The beta depends on an advisory-only service model. Counsel must approve the
   policy wording, acknowledgements, and escalation process for all 53 curated
   services before unrestricted registration. Service-zone review records are
   useful evidence for a later gate but are not a substitute for that approval.

### Medium risk

1. `admin@workdoe.com` has an owner-stated ordinary response target of 1 to 5
   business days. This is not yet evidence of a tested privacy/security/support
   response process or an urgent incident path.
2. There is no recorded independent penetration test, authenticated dynamic
   scan, or complete keyboard/screen-reader usability test.
3. Production currently shows demonstration projects and reports zero live
   public jobs. This is accurately labeled, but it is not evidence of a viable
   live marketplace or moderation load.
4. OpenStreetMap's public tile service has an availability/usage-policy
   boundary. Attribution is present, but a production growth plan should avoid
   assuming unlimited capacity or an SLA.
5. The future Cloudflare Images design provides managed decode and WebP
   re-encoding before R2 storage, with metadata removal, animation flattening,
   and fixed dimension bounds. It is currently disabled, is not a
   malware-scanning claim, and must not be enabled without a separate media
   policy, cost, moderation, and live valid/invalid-upload acceptance review.
6. Project creation, ordinary messages, reports, and media uploads now accept a
   durable 24-hour application idempotency key. The Worker browser client uses
   Web Crypto, D1/SQLite store only a SHA-256 hash plus generic resource
   references, completed retries replay the original resource, and concurrent
   in-flight retries return `409` with `Retry-After`. Keep monitoring for stale
   `processing` records: a crash between the resource write and completion can
   require operator reconciliation, but it fails closed instead of creating a
   duplicate. Native clients must reuse one key for every retry of the same
   logical operation.
7. Structured lead-quality feedback can be inaccurate, retaliatory, or
   correlated with protected or sensitive inferences. Keep it operational,
   sample it with project context, never expose it as a public score, and do not
   automate suspension or ranking from a single signal during the pilot.
8. Source checks remain a human operating process. A stale, compromised, or
   incomplete registry can make a dated lookup misleading, and one credential
   may not authorize the scope or jurisdiction of a particular project. Any
   future gated rollout therefore requires an assigned reviewer, recheck
   cadence, escalation path, and counsel-approved public wording; no source-checked
   label may be treated as a legal or safety guarantee.
   The project-level preference increases the chance that users overread the
   signal, so copy and contract tests must continue to describe it as a
   preference and prohibit any ranking, gate, or Workdoe eligibility claim.
9. Completion-gated reviews can still be retaliatory, collusive, mistaken, or
    discriminatory. Mutual completion proves a marketplace relationship, not
    factual accuracy. Keep a staffed report/moderation process, apply the same
    publication rules to positive and negative sentiment, prohibit incentives
    tied to sentiment, and do not derive ranking, suspension, or payment action
    from a review during the controlled beta.

### Low risk and polish

1. `sitemap.xml`, a deliberate `robots.txt`, and `.well-known/security.txt`
   are preflight-gated and passed the current live smoke check. The security
   contact's monitored status remains unproven. A conventional `favicon.ico`
   remains optional because the shipped SVG icon is linked explicitly.
2. Leaflet map controls and markers satisfy the WCAG 2.2 24 CSS pixel
   target-size minimum but remain below Workdoe's preferred 44 pixel target.
   The full job list is the primary equivalent interaction path.

## Tool evidence

- Python dependency audit: clean after upgrading Flask 3.1.2 to 3.1.3 to
  resolve GHSA-68rp-wp8r-4726 / CVE-2026-27205 in the local reference app.
- npm dependency audit: no known vulnerabilities.
- Bandit 1.9.4: zero high and zero medium findings after URL-scheme/Turnstile
  endpoint hardening and replacement or annotation of allowlisted SQL and
  development-host construction. Remaining low findings are reviewed local
  tooling, subprocess argument arrays, secret-name labels, and the local-only
  development key.
- Tracked secret-pattern scan: matches were deliberate redaction fixtures in
  tests; no tracked credential value was identified.
- Strict production smoke: DNS, HTTPS, public API, security headers, same-domain
  Clerk proxy assets, trust pages, discovery files, and the social share card
  passed in the 2026-10-24 evidence. This verifies the current deployed
  perimeter, not the un-deployed local release candidate or the owner-controlled
  marketplace workflow.

## Residual risk and decision

The engineering baseline is suitable for a limited, supervised beta while the
remaining owner checklist is completed. It is not ready for unrestricted public
account creation until all high-risk findings are closed, the reviewed local
candidate is released, and the live two-role workflow is recorded. Security
review must be repeated after material auth, payments, exact-location,
contractor-verification, or data-retention changes.
