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

## Verification evidence

- Full suite: 218 tests passed in 75.834 seconds.
- Full Ruff baseline and the ordinary CI quality command passed.
- Dependency provenance passed locally and against all recorded upstream Python
  source archives on 2026-08-23.
- The complete local security gate passed: `pip-audit` found no known Python
  dependency vulnerabilities, `npm audit` found no known Node vulnerabilities,
  Bandit found no medium/high issues, Ruff passed, and the reviewed secret gate
  passed across 410 non-ignored files.
- Responsive browser evidence is stored in
  `docs/ux-audit/2026-08-23-task-navigation/` at 390x844, 820x1180, and
  1280x720.

The final release evidence must repeat these checks after migration, Worker,
performance, accessibility, and live gates run on the final commit.

## Remaining production gates

1. Record owner/legal approval of the advisory-only service model, legal
   operator identity, policy copy, retention/deletion rules, and monitored
   support/privacy/security ownership.
2. Prove the Clerk production instance, same-domain proxy, restricted sign-up,
   email-code-only authentication, disabled passwords, express legal consent,
   webhook secret, and real code delivery.
3. Complete dependency vulnerability, secret, Bandit, migration-chain, D1 query
   plan, Worker dry-run/runtime, private-media, queue/email, rate-limit,
   accessibility, and agreed performance checks on the final commit.
4. Take the pre-deployment D1 backup, record rollback targets, make one reviewed
   GitHub push, run one guarded Cloudflare deployment, and retain the deployed
   SHA plus strict production smoke evidence.

Workdoe is not yet approved for unrestricted public registration. The remaining
operator/legal decisions and live-service proofs cannot be replaced by local
code or automated tests.
