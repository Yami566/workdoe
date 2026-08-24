# Project Review Editing Audit

Date: 2026-08-24

## Scope

The consumer's final project review in the direct `/jobs/new` fallback and the
same-page dashboard dialog, including summary density, correction cost,
responsive layout, focus movement, Flask and Cloudflare Worker parity, and
third-party asset provenance.

## Finding

The final review presented eight passive rows and only one Back control. A
consumer who noticed an incorrect title, work type, or area had to traverse
several steps in reverse and then move forward again. The repeated Setting,
Scope, Brief, Timing, and Budget rows also made the review longer without
creating a clearer decision.

## Change

- Consolidated the review into four task groups: Work, Project, Area, and
  Timing & budget.
- Added one compact edit control to each group. The controls jump directly to
  steps 1, 3, 4, or 5 and preserve every entered value.
- Replaced the tactical review legend with the direct question `Ready to
  post?`.
- Kept the controls hidden unless the existing progressive-enhancement
  controller is active. The server-rendered no-JavaScript form still displays
  every step and all fields in document order.
- Added the official Tabler `pencil.svg` from the already approved and pinned
  MIT-licensed 3.46.0 package. Its SHA-256 hash is enforced in the provenance
  verifier and vendored-asset tests.
- Implemented equivalent Flask template and Cloudflare Worker markup without a
  new runtime dependency or data field.

## Evidence

- `before-review-390x844.jpg`: eight passive rows before the change.
- `after-review-390x844.jpg`: four aligned editable rows in the direct mobile
  fallback.
- `after-edit-details-390x844.jpg`: one-tap return to the populated project
  details step.
- `after-review-dialog-390x844.jpg`: the intended same-page mobile dialog with
  the Post project action visible.
- `after-review-820x1180.jpg`: tablet review.
- `after-review-1280x720.jpg`: desktop review.

At each tested viewport, the document had no horizontal overflow. In the
same-page mobile path, the dialog locked background scrolling and focused the
review heading. Selecting Edit project area focused the step-four heading and
retained Washington and ZIP 20001. Closing the dialog restored the dashboard
URL, background scrolling, and focus to the originating Post a project link.

## Data, Privacy, And Accessibility

The change adds no stored or transmitted data. It reads only values already in
the current form and does not change project validation, public location
precision, media permissions, ordering, ranking, or eligibility.

Every pencil button has a visible upstream icon, a descriptive accessible
name, a matching hover title, a 44-by-44-pixel stable target, and the existing
focus-ring treatment. Summary terms and definitions remain semantic, and the
step heading receives focus after a direct edit jump.

## Acceptance

Focused Flask, Worker, asset, and provenance checks passed. All 235 tests then
passed in 81.701 seconds. The complete security and provenance gate found no
known Python or Node vulnerabilities, no medium/high Bandit or Ruff findings,
no unreviewed secret across 627 non-ignored files, and no dependency drift.

Cloudflare preflight returned no warnings. The D1 verifier loaded all 33
migrations, used the expected public map/photo indexes, and found no table
scan. Wrangler 4.125.0 packaged 48 Python modules and 87 static assets at
928.45 KiB, 170.57 KiB gzip. The command used `--dry-run`; no deployment
occurred.

## Limits

The browser used a seeded local consumer account and did not submit a project.
Production Clerk, D1, private media, Queues, Email, Turnstile, Images, legal
approval, assistive-technology testing, and Core Web Vitals remain separate
live release gates.
