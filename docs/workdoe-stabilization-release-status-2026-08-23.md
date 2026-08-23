# Workdoe Stabilization Release Status

Date: 2026-08-23

Status: local release candidate in progress; no GitHub push or Cloudflare
deployment has been performed during this stabilization pass.

## Completed locally

- Reconciled the pre-existing working tree into a reviewable baseline commit.
- Resolved the full Ruff baseline and replaced the release-only partial scan
  with a full ordinary CI quality gate.
- Added viewport-bounded public project search, cursor pagination, normalized
  public payloads, synchronized list/map selection, URL state, and Search this
  area behavior while preserving approximate coordinates.
- Replaced iframe overlays with route-backed native dialogs, no-JavaScript page
  fallbacks, History API restoration, and keyboard-focus restoration.
- Added a versioned 53-service policy registry with risk tier, advisory text,
  emergency-disable state, and stored acknowledgement version/time.
- Simplified role navigation and contractor dashboards for desktop, tablet, and
  mobile while preserving private location and role boundaries.
- Created and visually checked an editable Figma reference/target board:
  <https://www.figma.com/design/wrHbwYR6SKJ5Nr5di9sgnE?node-id=1-2>.
- Recorded Workdoe's proprietary first-party license, exact Python runtime
  pins, official dependency sources/licenses/hashes, retained browser licenses,
  and deterministic local provenance verification.
- Added deterministic contractor completion milestones and points derived only
  from mutually confirmed Workdoe projects. The shared Flask/Worker projection
  stores no new personal data and has no ranking effect.
- Added received-order comparison filters for any current source-checked record
  and specifically for a current source-checked trade-license record. Every
  offer remains in the complete bid list and the interface does not describe a
  checked record as a guarantee.
- Added private per-participant message read markers, unread thread counts, and
  compact unread cues. Ordering and read state use immutable message IDs so
  same-second replies remain deterministic; `HEAD` requests never mark a
  thread read.
- Added count-only unread indicators to consumer and contractor desktop/mobile
  navigation. The projection does not include message bodies, caps the visible
  badge at `99+`, exposes the exact count to assistive technology, and clears
  on the same response after a participant reads a thread.
- Configured matching static assets to bypass the Python Worker and use
  Cloudflare's static asset layer directly. Dynamic pages, APIs, same-domain
  Clerk proxy routes, and private media remain Worker-controlled.
- Extended production smoke testing to require direct HTTP-to-HTTPS redirects
  for both the public entry page and a static stylesheet, preventing the asset
  optimization from weakening the HTTPS launch contract.
- Reconciled the Flask contractor lead board with the existing Worker
  map-first workspace. Contractors now get synchronized Projects, Map, and
  Details views, responsive mobile tabs, URL-preserved selection, retained
  private fit/bid/readiness signals after public map refreshes, and a direct
  bid action without reintroducing the former long-scroll dashboard.
- Reduced remaining first-viewport friction using existing templates and CSS:
  public Explore now reaches the map sooner, contractor bids precede profile
  detail, mobile consumer summaries omit redundant cards, and message threads
  keep the reply form alongside a bounded conversation list. No new runtime or
  visual dependency was introduced.
- Tightened consumer contractor choice into factual comparison cards. Duplicate
  mini-bid metrics and the three-step explanation are gone; reviewed license,
  reviewed registration, and no-reviewed-record states are distinguishable;
  and a consumer can choose a pending contractor directly from the card while
  retaining profile and full-offer access. Received order and no-paid-ranking
  behavior are unchanged.
- Added a compact approved-match summary to private message threads. Price,
  timeline, and availability come from the accepted mini bid; project links are
  role-correct; and the projection excludes exact address and contact fields.
  Flask and Worker adapters share the same message-context contract.
- Carried that approved-match context into completed consumer project history.
  Closed projects now prioritize the chosen contractor, completion state,
  contact actions, and accepted terms instead of repeating an expired bid
  window. The summary remains stable across bid-status filters in both Flask
  and Worker adapters.
- Corrected the 390x844 message-thread grid so the complete reply composer and
  Send action clear the fixed mobile task navigation without adding script or
  changing the desktop layout.
- Hardened the guarded GitHub release path to capture a D1 Time Travel bookmark,
  the active Worker deployment, a rollback version/command, release SHA and
  checksums before migrations. The workflow captures the deployed Worker state
  afterward and retains the non-user-data evidence as a pinned official GitHub
  artifact even when a later release step fails.
- Updated the generated launch handoff to reuse the already validated,
  non-secret Clerk proof for its four GitHub workflow confirmations. The actual
  deploy dispatcher still requires an intentional execute action, while the
  handoff no longer asks an operator to repeat confirmed configuration work.
  Launch-status tests now ignore operator-local evidence unless a test supplies
  it explicitly.

## Verification evidence

- Full suite: 225 tests passed in 89.840 seconds after the final first-viewport
  workflow pass.
- Full Ruff baseline and the ordinary CI quality command passed.
- Dependency provenance passed locally and against all recorded upstream Python
  source archives on 2026-08-23.
- The complete local security gate passed: `pip-audit` found no known Python
  dependency vulnerabilities, `npm audit` found no known Node vulnerabilities,
  Bandit found no medium/high issues, Ruff passed, and the reviewed secret gate
  passed across 420 non-ignored files.
- All 31 forward-only D1 migrations apply to a blank database and to the local
  Wrangler database. `EXPLAIN QUERY PLAN` uses `idx_jobs_open_geo` and the
  covering `idx_job_photos_public_job` index without scanning either public hot
  table. Consumer and contractor unread queries use `idx_threads_client` or
  `idx_threads_contractor`, `idx_messages_thread_unread`, and the thread-read
  primary-key index without scanning `threads`.
- Wrangler 4.125.0 serves the 2026-08-23 compatibility date locally. The
  warning-free production-config dry run packaged 48 Python modules and 86
  assets at 889.92 KiB / 163.07 KiB gzip. Runtime smoke returned 200 for
  health, home, and public jobs and emitted a privacy-safe D1 event with
  `rows_read: 2`.
- A second local Worker pass served `styles.css` and pinned Leaflet JavaScript
  from the Cloudflare asset layer with ETags and `CF-Cache-Status: HIT`, while
  `/health` remained Worker-controlled with HSTS. The live pre-release domain
  currently redirects the entry and stylesheet paths on both the apex and
  `www` hosts directly to HTTPS; this check must be repeated after deployment
  because the production Worker is still the older release.
- Responsive browser evidence is stored in
  `docs/ux-audit/2026-08-23-task-navigation/` at 390x844, 820x1180, and
  1280x720.
- A repeated authenticated mobile browser pass verified zero horizontal
  overflow, canonical native-dialog URL/focus restoration, synchronized
  map/list selection, keyboard project navigation, and 44-pixel map/policy
  controls. Exact evidence and live-test limits are recorded in
  `docs/release-evidence/2026-08-23-local-browser-acceptance.md`.
- A second authenticated responsive pass at 390x844 and 820x1180 verified no
  horizontal overflow, compact milestone rendering, existing bottom
  navigation, public contractor-profile continuity, and a clean browser
  console. Flask/Worker contract tests cover the received-order and credential
  filter behavior.
- An authenticated message-state pass at 390x844 and 1280x720 verified compact
  unread metrics, separated project/participant labels, zero horizontal
  overflow, a clean console, and per-thread read-state updates.
- A final selected-browser pass at 390x844 and 1280x720 verified the shared
  navigation badge in both responsive states, exact `Messages, 2 unread`
  labeling, zero horizontal overflow, and immediate badge removal after opening
  the unread thread. The temporary visual-check message was removed afterward.
- A contractor discovery pass at 390x844, 820x1180, and 1280x720 verified the
  map-first workspace, mobile tab focus/selection, selected-job URL state,
  direct bid action, deterministic fallback selection, photo counts, and the
  absence of structured ZIP/client-email fields. Evidence is stored in
  `docs/ux-audit/2026-08-23-current-journeys/`.
- The final local security pass found no known Python or Node vulnerabilities,
  no medium/high Bandit issues, no Ruff findings, no unreviewed detected
  secrets across 453 non-ignored files, and no dependency-provenance drift.
  Cloudflare preflight, D1 query-plan verification, and the Wrangler 4.125.0
  48-module/86-asset dry run also passed at 891.77 KiB / 163.41 KiB gzip.
- A consumer-choice browser pass at 390x844 and 1280x720 verified the condensed
  received-order cards, current-license filtering, reviewed-record labels, and
  direct approval into a private message thread. Same-state before/after
  evidence is stored as captures `20` through `26` in
  `docs/ux-audit/2026-08-23-current-journeys/`; all temporary QA records were
  removed afterward. The repeated full suite passed 225 tests in 82.326
  seconds.
- An approved-match message pass at 390x844 and 1280x720 verified compact bid
  terms, the bounded message list, the always-visible composer, and the
  consumer's private View project route with browser Back restoration.
  Same-state evidence is stored as captures `27` through `32`; Flask/Worker
  privacy and route contracts pass, and the full suite passed 225 tests in
  80.480 seconds.
- A completed-project lifecycle pass at 390x844 and 1280x720 verified that the
  approved contractor and accepted terms precede project scope, closed states
  omit the expired bid window, and the corrected mobile Send action has 16
  pixels of clearance above task navigation. Current-run before/after evidence
  and limits are stored in
  `docs/ux-audit/2026-08-23-project-lifecycle/`.
- The repeated lifecycle release gate passed 225 tests in 82.538 seconds. The
  full security command found no known Python or Node vulnerabilities, no
  medium/high Bandit findings, no Ruff findings, no unreviewed detected secrets
  across 463 non-ignored files, and no provenance drift.
- Cloudflare preflight completed with no warnings. D1 query-plan verification
  used `idx_jobs_open_geo` and the covering
  `idx_job_photos_public_job` index without hot-table scans. Wrangler 4.125.0
  dry-run packaging succeeded with 48 Python modules and 86 assets at 893.80
  KiB / 163.74 KiB gzip.
- The release-recovery workflow change passed the repeated 225-test suite in
  81.921 seconds, the complete security/provenance gate, Cloudflare preflight,
  YAML parsing, and the warning-free Wrangler dry run. Read-only production
  checks also proved that the configured D1 returns a current Time Travel
  bookmark and that the active Worker exposes deployment/version metadata;
  neither command changed production state.
- After production Clerk configuration and the handoff correction, the full
  suite passed 226 tests in 79.798 seconds. `npm audit` and `pip-audit` found no
  known vulnerabilities; Bandit reported no medium/high findings; full Ruff,
  the secret gate across 463 non-ignored files, and dependency provenance all
  passed.

The final release evidence must repeat these checks after migration, Worker,
performance, accessibility, and live gates run on the final commit.

## Production configuration completed during release preparation

- Created the Workdoe Clerk production instance and replaced the Worker's
  development Clerk configuration with one coherent production key set. The
  initially exposed setup key was rotated, replaced in Cloudflare, and revoked
  in Clerk before continuing.
- Configured Clerk for Invite-only (`restricted`) beta access, email-code
  verification and sign-in, disabled password sign-up and password attachment,
  and required express consent to `https://workdoe.com/terms` and
  `https://workdoe.com/privacy`.
- Pointed Clerk sign-in, sign-up, unauthorized-sign-in, and sign-out behavior to
  Workdoe routes, including `https://workdoe.com/create-account`, and disabled
  the hosted Account Portal so authentication stays on Workdoe.
- Clerk Domains verified the Frontend API proxy at
  `https://workdoe.com/__clerk`. The Worker's production JWT verification key
  now matches that instance.
- Created `https://workdoe.com/clerk/webhook` for `user.created`,
  `user.updated`, and `user.deleted`; installed its signing secret in the
  Worker; and retained the existing linked-user-only synchronization boundary.
- Wrangler confirmed all seven required Worker secret names. The ignored,
  value-free Clerk proof and secret-name evidence pass the release evidence
  check; the deployment plan reports no strict blockers; and the live launch
  doctor reports all pre-deployment phases ready.
- Authorized Clerk's Cloudflare Domain Connect request after reviewing all five
  proposed CNAMEs. Clerk now reports the primary domain, same-domain proxy, and
  all three email records as verified. Public DNS resolves `clerk`, `accounts`,
  `clkmail`, `clk._domainkey`, and `clk2._domainkey` to the expected Clerk
  service hosts; no apex or Worker routing record was changed.
- Enabled Cloudflare Email Routing for `workdoe.com`, added the required MX,
  SPF, and DKIM records, and created an active `admin@workdoe.com` route to the
  account's existing verified owner destination. Public DNS resolves all three
  Cloudflare MX records. A received-message check and the owner's monitoring
  and response target are still operational acceptance gates.
- Confirmed in the Cloudflare dashboard that Hosted Images does not have the
  required paid subscription. Production photo upload sanitization is designed
  to fail closed until Images Paid is enabled and tested.

## Remaining production gates

1. Record owner/legal approval of the advisory-only service model, legal
   operator identity, policy copy, retention/deletion rules, and monitored
   support/privacy/security ownership. The `admin@workdoe.com` route now exists,
   but received-mail evidence, a named monitor, and a response target remain.
2. Create or invite one real controlled-beta application user and prove the
   complete Workdoe-hosted email-code journey. The Clerk dashboard currently
   has no production application users. Its header-level Invite control is for
   dashboard collaborators, so it was not used as an application invitation.
   The production instance, verified domain and mail DNS, same-domain proxy,
   restricted access, email-code-only settings, disabled passwords, express
   legal consent, JWT verification, and webhook configuration are evidenced.
3. Enable Cloudflare Images Paid and prove one valid sanitized upload plus one
   invalid upload rejection. Then repeat dependency, secret, Bandit, migration,
   query-plan, and Worker checks on the final commit; complete live private-media,
   queue/email, rate-limit, accessibility, and agreed Core Web Vitals checks.
   Local asset/header evidence is not a substitute for production LCP, CLS, or
   INP measurements.
4. Take the pre-deployment D1 backup, record rollback targets, make one reviewed
   GitHub push, run one guarded Cloudflare deployment, and retain the deployed
   SHA plus strict production smoke evidence.

Workdoe is not yet approved for unrestricted public registration. The remaining
operator/legal decisions and live-service proofs cannot be replaced by local
code or automated tests.
