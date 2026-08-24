# Workdoe Stabilization Release Status

Date: 2026-08-23

Status: release candidate pushed for review on
`codex/workdoe-stabilization-launch-2026-08-22`; no Cloudflare production
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
- Added a production invitation deep-link smoke gate after the controlled beta
  invitation exposed a stale Worker route. The gate uses a synthetic Clerk
  ticket, requires the Workdoe account HTML shell, and rejects development
  Clerk publishable keys without logging or replaying a real invitation token.
- Corrected mobile project-composer step transitions so Continue and Back return
  to the new step heading instead of preserving an obsolete dialog scroll
  position. Optional quote-ready questions now use a compact native disclosure,
  reopen when prior answers exist, and preserve the six-step data contract in
  both Flask and the Cloudflare Worker adapter.
- Reframed the private message inbox around conversation triage. Compact All
  and Unread views replace non-actionable summary cards, rows identify the
  other participant, and the validated server-side filter preserves private
  read markers and aggregate analytics. Flask and Worker adapters share the
  same role-aware behavior and invalid values safely return to All.
- Reframed the consumer dashboard around the project queue. All, Review, Open,
  and Closed views now fit in one mobile row; the first project begins 274
  pixels earlier in the measured 390x844 state; and Flask derives filtered
  jobs, counts, and history from one workspace query instead of repeating the
  query and loading unused profile context. The Worker exposes the same view
  and empty-state contract.
- Reframed the contractor dashboard around bid triage. All, Pending, Approved,
  and Rejected views now fit in one mobile row; the first bid begins 323 pixels
  earlier in the same-state 390x844 comparison; and Flask no longer counts all
  open projects solely for a duplicated metric. The Worker now uses the same
  primary-first order, compact bid rows, and view-aware empty-state contract,
  while milestone points, source-checked credential signals, profile context,
  and completed-work history remain intact.
- Reframed contractor profile setup around its three maintenance tasks.
  Availability, profile details, and credentials now have compact direct links;
  completed readiness details collapse; and credential claims precede the full
  53-service editor. Flask and Worker adapters share the same native disclosure,
  ordering, and anchor contract without changing credential review semantics.
- Reframed the public contractor profile around client choice and factual trust
  signals. Availability, mutually confirmed work, milestone points, and current
  source-checked record state now precede biography; service coverage uses a
  native disclosure; and profile links from client projects preserve an
  ownership-checked path back to the offer. Pending offers expose Choose,
  approved offers expose Message, and unrelated project IDs fail closed in both
  Flask and Worker adapters.
- Made contractor progress legible as a deterministic four-step milestone
  track. First finish, Steady provider, Local regular, and Proven partner now
  expose earned, current, next, and locked states; the score identifies its
  verified-project basis; and next-threshold progress uses an absolute count.
  The Flask and Worker projections remain ranking-neutral and store no new data.
- Made consumer contractor comparison more visual without inventing identity
  data. Each offer can now use the contractor's newest visible moderated
  portfolio photo, while compact factual signals preserve price, timeline,
  availability, Workdoe completion history, insurance claim, milestone state,
  and source-checked credential status. Missing photos remain absent rather
  than becoming generated avatars, and received order, permissions, and
  no-paid-ranking behavior are unchanged.
- Kept contractor work selection ahead of alert configuration. The Projects
  panel now keeps status tabs and project rows visible while family, task,
  search, sort, saved-view, and matching-email controls share one native
  disclosure with a compact state summary. The existing D1, Queue, and Email
  alert pipeline is unchanged; the Cloudflare Worker renderer now also matches
  Flask's lead-status tabs, photo facts, and accessible row labels.
- Kept approved-match conversations connected on desktop. A bounded rail lets
  participants switch among their newest 50 threads while phone and tablet
  layouts remain focused on one conversation and its visible composer. The
  Worker reuses that listing for the unread navigation count and now restores
  Flask's missing participant-only message-report disclosure through the
  existing rate-limited, Turnstile-protected moderation API.
- Compressed the first two phone project-posting steps without changing their
  six-step contract. All six numbered work families and all six common tasks
  now fit in compact two-column icon controls; repeated family subtitles and
  internal taxonomy wording are gone; and the public mobile map gains a
  single-line heading. Flask and both Worker shells share a rotated stylesheet
  version so the accepted layout is not masked by a stale browser cache.
- Made public map pins actionable without adding a route or public field. Each
  Leaflet popup now presents the job's existing permission-aware action as a
  44-pixel same-domain control; signed-out visitors open the existing email-code
  dialog with the selected project retained, while map URL state and focus are
  restored on close. The live-region message now describes the available next
  step truthfully on both simple and detail-rail map surfaces.
- Restored project-result link semantics across Flask templates, Worker entry
  and app shells, and live map refreshes. List grouping now sits on a
  noninteractive wrapper, each unchanged anchor is announced as a link, and a
  compact Sign in, View, or Sent cue survives API replacement. The selected
  project, permission-aware URL, keyboard row navigation, dialog behavior, and
  no-JavaScript fallback are unchanged.

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
- After adding the invitation regression gate, the full suite passed 228 tests
  in 94.752 seconds. The complete security/provenance command remained clean,
  Cloudflare preflight reported no errors or warnings, D1 query-plan checks used
  both expected public indexes without a hot-table scan, and Wrangler 4.125.0
  again packaged 48 Python modules and 86 assets at 893.80 KiB / 163.74 KiB
  gzip without deploying.
- A read-only smoke run against the older live Worker correctly remained not
  ready: `/create-account` returned 404, sign-in used a Clerk development key,
  the health payload lacked the write-rate-limiter binding, and Safety, Privacy,
  and Terms returned 404. HTTPS redirects, the public jobs API, security
  headers, social share card, and same-domain Clerk asset proxy passed. These
  failures are release evidence for replacing the stale Worker, not candidate
  regressions.
- The final project-composer correction passed the 228-test suite in 88.290 seconds.
  The complete security/provenance command found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 472 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; D1 query-plan verification used both expected public
  indexes without hot-table scans; and Wrangler 4.125.0 packaged 48 Python
  modules and 86 assets at 894.04 KiB / 163.76 KiB gzip without deploying.
- Browser evidence at 390x844 measured the corrected dialog at `scrollTop: 0`,
  with the new step heading visible and the required title 250 pixels earlier.
  The optional scope panel fell from 719 to 106 pixels when closed, reopened
  normally, and responsive direct routes had zero horizontal overflow at
  390x844, 820x1180, and 1280x720. Evidence and limits are recorded in
  `docs/ux-audit/2026-08-23-project-composer-friction/`.
- The account-entry correction passed all 228 tests in 84.101 seconds. The
  complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 481 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; both expected D1 public indexes were used without a
  table scan; and Wrangler 4.125.0 packaged 48 Python modules and 86 assets at
  894.38 KiB / 163.85 KiB gzip without deploying.
- Fresh browser evidence shows that the mobile map begins 106 pixels earlier,
  sign-in and account creation switch in place while preserving the map, and
  both sheet directions keep their context-aware destination. No horizontal
  overflow appeared at 390x844, 820x1180, or 1280x720. Evidence and limits are
  recorded in `docs/ux-audit/2026-08-23-account-entry-friction/`.
- The message-inbox correction passed all 228 tests in 80.563 seconds. The
  complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 487 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; both expected D1 public indexes were used without a
  table scan; and Wrangler 4.125.0 packaged 48 Python modules and 86 assets at
  895.71 KiB / 164.20 KiB gzip without deploying.
- Current-run inbox evidence at 390x844 and 1280x720 shows zero horizontal
  overflow, role-aware counterpart labels, an active Unread view, and a
  one-viewport empty state. The same-state mobile comparison and evidence
  limits are recorded in
  `docs/ux-audit/2026-08-23-message-inbox-friction/`.
- The consumer-dashboard correction passed all 228 tests in 81.598 seconds.
  The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 493 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; all 31 forward-only migrations and both expected D1
  public indexes passed without a hot-table scan; and Wrangler 4.125.0 packaged
  48 Python modules and 86 assets at 896.76 KiB / 164.53 KiB gzip without
  deploying.
- Current-run consumer-dashboard evidence at 390x844 and 1280x720 shows zero
  horizontal overflow, all four project states in one mobile row, a 274-pixel
  improvement in first-project position, and a one-viewport Review zero state.
  The same-state comparison and evidence limits are recorded in
  `docs/ux-audit/2026-08-23-consumer-dashboard-friction/`.
- The contractor-dashboard correction passed all 228 tests in 81.890 seconds.
  The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 499 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; all 31 forward-only migrations and both expected D1
  public indexes passed without a hot-table scan; and Wrangler 4.125.0 packaged
  48 Python modules and 86 assets at 896.26 KiB / 164.54 KiB gzip without
  deploying.
- Current-run contractor-dashboard evidence at 390x844 and 1280x720 shows zero
  horizontal overflow, all four bid states in one mobile row, a 323-pixel
  improvement in first-bid position, and a one-viewport Pending zero state.
  The same-state comparison and evidence limits are recorded in
  `docs/ux-audit/2026-08-23-contractor-dashboard-friction/`.
- The contractor-profile correction passed all 228 tests in 84.212 seconds.
  The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 505 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; all 31 forward-only migrations and both expected D1
  public indexes passed without a hot-table scan; and Wrangler 4.125.0 packaged
  48 Python modules and 86 assets at 896.84 KiB / 164.71 KiB gzip without
  deploying.
- Current-run contractor-profile evidence at 390x844 and 1280x720 shows zero
  horizontal overflow, all three task links fitting their stable columns,
  completed-readiness disclosure collapsed, and credential setup moving from
  5,834 to 868 pixels on mobile. The credential anchor clears the sticky app
  bar by 72 pixels. Same-state comparison and evidence limits are recorded in
  `docs/ux-audit/2026-08-23-contractor-profile-friction/`.
- The public contractor-choice correction passed all 228 tests in 81.460
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 514 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; all 31 forward-only migrations and both expected D1
  public indexes passed without a hot-table scan; and Wrangler 4.125.0 packaged
  48 Python modules and 86 assets at 904.76 KiB / 166.16 KiB gzip without
  deploying.
- Current-run public-profile evidence at 390x844 and 1280x720 shows zero
  horizontal overflow, moves factual trust signals 325 pixels earlier on
  mobile, and keeps the contextual project decision in the first viewport.
  Pending, approved, and unrelated project states expose only the ownership-
  appropriate Choose, Message, and back actions. Native service coverage lists
  all 10 exact DMV labels without exposing an address. Same-state comparison
  and evidence limits are recorded in
  `docs/ux-audit/2026-08-23-public-contractor-profile-friction/`.
- Kept contractor quoting inside the selected lead workspace with a native,
  route-backed bid dialog on desktop and bottom sheet on mobile. Successful
  bids refresh in place; closing restores the selected project, URL, and
  invoking-action focus. Current-run 390x844 and 1280x720 evidence, including
  the former 3,270-pixel mobile page, is recorded in
  `docs/ux-audit/2026-08-23-contractor-map-to-offer-friction/`.
- The contractor map-to-offer correction passed all 228 tests in 85.474
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed
  secret across 521 non-ignored files, and no dependency drift. Cloudflare
  preflight remained warning-free; all 31 migrations and both expected D1
  public indexes passed without a table scan; and Wrangler 4.125.0 packaged 48
  Python modules and 86 assets at 905.64 KiB / 166.39 KiB gzip without
  deploying.
- The contractor-milestone correction passed all 229 tests in 86.301 seconds.
  The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed
  secret across 530 non-ignored files, and no dependency drift. Cloudflare
  preflight remained warning-free; all 31 migrations and both expected D1
  public indexes passed without a table scan; and Wrangler 4.125.0 packaged 48
  Python modules and 86 assets at 907.70 KiB / 166.88 KiB gzip without
  deploying.
- Current-run milestone evidence at 390x844, 820x1180, and 1280x720 shows zero
  horizontal overflow, all four fixed thresholds in one stable row, a current
  First finish state, and absolute `1 of 3` progress toward Steady provider.
  The aligned mobile before/after comparison and evidence limits are recorded
  in `docs/ux-audit/2026-08-23-contractor-milestones-friction/`.
- The visual contractor-choice correction passed all 229 tests in 83.953
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed
  secret across 539 non-ignored files, and no dependency drift. Cloudflare
  preflight remained warning-free; all 32 forward-only migrations applied;
  `EXPLAIN QUERY PLAN` used the open-job, public-job-photo, and covering
  contractor-photo indexes without a hot-table scan; and Wrangler 4.125.0
  packaged 48 Python modules and 86 assets at 909.15 KiB / 167.18 KiB gzip
  without deploying.
- Current-run contractor-choice evidence at 390x844, 820x1180, and 1280x720
  shows zero horizontal overflow, a real moderated portfolio photo with
  contractor-specific alternative text, compact comparison facts and signals,
  complete Profile, Full offer, and Choose contractor actions, and a clean
  browser console. The aligned mobile before/after comparison and evidence
  limits are recorded in
  `docs/ux-audit/2026-08-23-contractor-choice-cards/`.
- The contractor saved-alert correction passed all 229 tests in 85.768
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed
  secret across 545 non-ignored files, and no dependency drift. Cloudflare
  preflight remained warning-free; all 32 forward-only migrations and all
  three expected D1 indexes passed without a table scan; and Wrangler 4.125.0
  packaged 48 Python modules and 86 assets at 911.57 KiB / 167.70 KiB gzip
  without deploying.
- Current-run saved-alert evidence at 390x844, 820x1180, and 1280x720 shows
  project results restored to the first mobile viewport, filters and alert
  consent retained in a native disclosure, and synchronized Flask and Worker
  lead states. The aligned mobile before/after comparison and evidence limits
  are recorded in
  `docs/ux-audit/2026-08-24-contractor-saved-alert-friction/`.
- The approved-match messaging correction passed all 229 tests in 81.361
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed
  secret across 554 non-ignored files, and no dependency drift. Cloudflare
  preflight completed without warnings or errors; all 32 forward-only
  migrations and all three expected D1 indexes passed without a table scan;
  and Wrangler 4.125.0 packaged 48 Python modules and 86 assets at 915.29 KiB /
  168.33 KiB gzip without deploying.
- Current-run messaging evidence at 390x844, 820x1180, and 1280x720 shows a
  compact phone header with the complete reply action above task navigation, a
  focused tablet thread, and a desktop conversation rail that switches between
  approved matches without returning to the inbox. The aligned before/after
  comparisons, Worker moderation-parity correction, and evidence limits are
  recorded in `docs/ux-audit/2026-08-24-messaging-flow-friction/`.
- The compact project-choice correction passed all 229 tests in 79.906 seconds.
  The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 566 non-ignored files, and no dependency drift. Cloudflare preflight
  completed without warnings or errors; all 32 forward-only migrations and all
  three expected D1 indexes passed without a table scan; and Wrangler 4.125.0
  packaged 48 Python modules and 86 assets at 915.22 KiB / 168.32 KiB gzip
  without deploying.
- Current-run public map and project-composer evidence at 390x844 and 1280x720
  shows a one-line phone heading, all six numbered family choices, all six
  common tasks plus progressive disclosure, retained dialog actions, and the
  unchanged desktop map-first layout. The aligned before/after comparisons and
  evidence limits are recorded in
  `docs/ux-audit/2026-08-24-public-map-post-flow/`.
- The public-marker continuation correction passed all 232 tests in 79.458
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 573 non-ignored files, and no dependency drift. The secret gate now
  scans deterministic Windows-safe argument batches after the repository grew
  beyond one Windows command line; the reviewed baseline and aggregate failure
  behavior are unchanged. Cloudflare preflight remained warning-free; all 32
  forward-only migrations and all three expected D1 indexes passed without a
  table scan; and Wrangler 4.125.0 packaged 48 Python modules and 86 assets at
  915.26 KiB / 168.32 KiB gzip without deploying.
- Current-run public marker evidence at 390x844 and 1280x720 shows a specific
  white-on-green 44-pixel action, truthful selected-project announcement,
  same-page Sign in with `next=/jobs/5`, and restoration to `/?job_id=5` after
  closing. The aligned before/after comparison and evidence limits are recorded
  in `docs/ux-audit/2026-08-24-public-map-selection-flow/`.
- The semantic project-result correction passed all 232 tests in 80.055
  seconds. The complete security/provenance gate found no known Python or Node
  vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
  across 579 non-ignored files, and no dependency drift. Cloudflare preflight
  remained warning-free; all 32 forward-only migrations and all three expected
  D1 indexes passed without a table scan; and Wrangler 4.125.0 packaged 48
  Python modules and 86 assets at 915.69 KiB / 168.38 KiB gzip without
  deploying.
- Current-run public-list evidence shows both refreshed results announced as
  specific links, visible Sign in cues, same-page auth at
  `/login?next=%2Fjobs%2F5`, and focus restored to the originating result after
  close. Mobile and desktop captures plus the focused comparison are recorded
  in `docs/ux-audit/2026-08-24-public-list-continuation-flow/`.

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
- Created a 30-day application-level invitation for the account owner from the
  production Clerk Users > Invitations view. Clerk reports the invitation as
  pending through 2026-09-22. The recipient opened that invitation, but the
  older production Worker returned a JSON `Not found` response for
  `/create-account`; inspection also found that the live `/start` page still
  embeds a Clerk development publishable key. The candidate fixes both defects,
  and its production smoke now blocks a release that regresses either one. The
  separate header-level dashboard-collaborator invitation was not used.

## Remaining production gates

1. Record owner/legal approval of the advisory-only service model, legal
   operator identity, policy copy, retention/deletion rules, and monitored
   support/privacy/security ownership. The `admin@workdoe.com` route now exists,
   but received-mail evidence, a named monitor, and a response target remain.
2. Accept the pending controlled-beta application invitation and prove the
   complete Workdoe-hosted email-code journey after the reviewed candidate is
   deployed. The current production Worker cannot complete this gate because it
   lacks `/create-account` and serves an obsolete Clerk development key. The
   Clerk dashboard currently has no accepted production application users. The
   production instance, verified domain and mail DNS, same-domain proxy,
   restricted access, email-code-only settings, disabled passwords, express
   legal consent, JWT verification, and webhook configuration are evidenced.
3. Enable Cloudflare Images Paid and prove one valid sanitized upload plus one
   invalid upload rejection. Then repeat dependency, secret, Bandit, migration,
   query-plan, and Worker checks on the final commit; complete live private-media,
   queue/email, rate-limit, accessibility, and agreed Core Web Vitals checks.
   Local asset/header evidence is not a substitute for production LCP, CLS, or
   INP measurements.
4. Review and promote the candidate branch to `main`, take the pre-deployment
   D1 backup, record rollback targets, run one guarded Cloudflare deployment,
   and retain the deployed SHA plus strict production smoke evidence. The
   candidate branch push does not trigger the production deploy job.

Workdoe is not yet approved for unrestricted public registration. The remaining
operator/legal decisions and live-service proofs cannot be replaced by local
code or automated tests.
