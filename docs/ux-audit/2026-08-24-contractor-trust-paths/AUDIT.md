# Contractor Trust Paths Audit

Date: 2026-08-24

## Scope

The signed-in contractor dashboard, storefront profile form, completion
milestones, and source-checked credential workflow in Flask and the matching
Cloudflare Worker shell.

## Finding

The trust model was already conservative, but the contractor workflow did not
explain it efficiently. The dashboard showed a self-reported insurance note
beside completion milestones without a direct route to the separate reviewed
record ledger. On the profile page, the shortcuts listed Profile details before
Credentials while the optional credential form appeared first and pushed the
essential 53-service storefront form far down the mobile page.

## Change

- Added a deterministic trust-record projection to the shared Flask and Worker
  contractor reputation contract.
- Kept completion points and source-checked records separate. Points remain
  based only on mutually confirmed Workdoe projects and do not change lead or
  bid order.
- Replaced the dashboard's self-reported insurance snapshot with an explicit
  Trust record state: no source-checked record, record source checked, or
  license source checked.
- Added direct Edit profile and Trust records actions without adding a public
  ranking, paid placement, recommendation, or generic verified-provider badge.
- Reordered both profile implementations to match the visible task sequence:
  Availability, Profile details, then optional Credentials.
- Preserved the current public-profile explanation that a source check is not a
  guarantee of skill, safety, coverage, or legal eligibility.

## Evidence

- `before-contractor-dashboard-full-mobile.png`: prior mobile dashboard with
  completion milestones followed by the self-reported insurance snapshot.
- `before-contractor-profile-full-mobile.png`: prior long-page order with the
  optional credential form before essential profile details.
- `after-contractor-dashboard-trust-paths-450x844.png`: compact mobile
  completion and trust paths with two direct actions.
- `after-contractor-profile-opening-450x844.png`: task shortcuts and readiness
  state remain visible in the first mobile viewport.
- `after-contractor-profile-details-450x844.png`: the essential storefront form
  now begins before credential submission.
- `after-contractor-dashboard-820x1180.png` and
  `after-contractor-dashboard-1280x720.png`: tablet and desktop checks without
  text or control collision.

The browser DOM confirmed the profile source order as `work-availability`,
`profile-details`, `credential-claims`. Opening Trust records from the mobile
dashboard produced the canonical
`/contractor/profile#credential-claims` URL and positioned the target at 72
pixels, below the fixed header.

## Privacy And Ranking

The new projection contains only counts already derived from current public
credential responses. It does not expose a claimed identifier, reviewer,
private note, expired or rejected claim, exact location, contact detail, or
credential source that was not already public. It adds no eligibility decision,
semantic inference, score weight, paid rank, or recommendation.

## Acceptance

All 233 tests passed in 81.728 seconds. Full Ruff passed. `pip-audit` and
`npm audit` found no known vulnerabilities; Bandit reported no medium or high
findings. The dependency provenance check passed. Cloudflare preflight returned
no warnings, and the D1 verifier used all three expected public map/photo
indexes without a table scan.

Wrangler 4.125.0 packaged 48 Python modules and 86 static assets at 920.46 KiB,
169.43 KiB gzip. The command used `--dry-run`; no deployment occurred.

## Limits

The local browser used the seeded contractor account. Production Clerk, D1,
private media, Queues, Email, Turnstile, credential operations, and legal review
remain separate live release gates. Source checking remains a dated review of a
linked public record, not a claim that Workdoe verifies contractor competence or
legal eligibility.
