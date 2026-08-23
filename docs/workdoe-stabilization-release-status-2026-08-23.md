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

## Verification evidence

- Full suite: 223 tests passed in 79.210 seconds after the global unread
  navigation, D1 index, and release-preflight work.
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

The final release evidence must repeat these checks after migration, Worker,
performance, accessibility, and live gates run on the final commit.

## Remaining production gates

1. Record owner/legal approval of the advisory-only service model, legal
   operator identity, policy copy, retention/deletion rules, and monitored
   support/privacy/security ownership.
2. Prove the Clerk production instance, same-domain proxy, restricted sign-up,
   email-code-only authentication, disabled passwords, express legal consent,
   webhook secret, and real code delivery.
3. Repeat dependency, secret, Bandit, migration, query-plan, and Worker checks
   on the final commit; complete live private-media, queue/email, rate-limit,
   accessibility, and agreed performance checks.
4. Take the pre-deployment D1 backup, record rollback targets, make one reviewed
   GitHub push, run one guarded Cloudflare deployment, and retain the deployed
   SHA plus strict production smoke evidence.

Workdoe is not yet approved for unrestricted public registration. The remaining
operator/legal decisions and live-service proofs cannot be replaced by local
code or automated tests.
