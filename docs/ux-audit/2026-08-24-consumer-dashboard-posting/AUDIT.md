# Consumer Project Composer Audit

Date: 2026-08-24

## Scope

The consumer journey from the project dashboard into the first three steps of
the six-step project composer, including Flask and Cloudflare Worker parity,
responsive dialogs, interaction cost, focus behavior, and service-specific
writing guidance.

## Finding

The first two selection steps each required a card selection followed by a
separate Continue action. That made the common pointer and touch path four taps
before a consumer could describe the work. More importantly, selecting Lawn
mowing still produced a pressure-washing title example in step three. The
unrelated example weakened confidence that the selected service would be
carried through the project brief.

## Change

- Pointer and touch selection now advance the family and service steps after a
  valid choice, reducing the common path from four taps to two.
- Keyboard users and no-JavaScript fallbacks retain the explicit Continue
  action, preserving reviewability and direct-route operation.
- Project title and description guidance is derived from the canonical service
  label. Lawn mowing now suggests `Lawn mowing project` and asks for the lawn
  mowing scope, size, condition, access, and desired outcome.
- Existing project edit forms use the same canonical service guidance instead
  of unrelated or generic examples.
- Flask and Cloudflare Worker markup, scripts, cache versions, and tests remain
  aligned. No new runtime or visual dependency was introduced.

## Evidence

- `before-client-dashboard-full-390x844.png`: consumer dashboard before entry.
- `before-posting-step-1-390x844.png`: family choice before the change.
- `before-posting-step-2-390x844.png`: service choice before the change.
- `before-posting-step-3-390x844.png`: unrelated pressure-washing guidance
  after selecting Lawn mowing.
- `after-guided-step-3-390x844.png`: corrected mobile guidance after two taps.
- `after-guided-step-3-820x1180.png`: corrected tablet dialog.
- `after-guided-step-3-1280x720.png`: corrected desktop dialog.

At 390 by 844, 820 by 1180, and 1280 by 720, the composer had no horizontal
overflow, retained a stable action area, and locked background scrolling. The
mobile pointer flow focused the step-three heading after each automatic step
change. The existing direct URLs and explicit Continue controls remain the
keyboard and no-JavaScript fallback.

## Data And Privacy

Guidance uses the already selected canonical service label only. It does not
infer, vectorize, persist, or transmit new personal data. The composer still
warns consumers not to include an exact street address, email address, or
phone number in the description, and public map/API responses remain limited
to approximate locations.

## Acceptance

Focused Flask and Worker parity tests passed for project creation, project
editing, all 59 auto-advance choices, canonical service guidance, and script
cache alignment. All 235 tests then passed in 80.454 seconds, and full Ruff
passed. The complete security and provenance gate found no known Python or Node
vulnerabilities, no medium/high Bandit or Ruff findings, no unreviewed secret
across 619 non-ignored files, and no dependency drift. Cloudflare preflight
returned no warnings; the D1 verifier loaded all 33 migrations, used every
expected public map/photo index, and found no table scan. Wrangler 4.125.0
packaged 48 Python modules and 86 assets at 927.54 KiB, 170.45 KiB gzip. The
command used `--dry-run`; no deployment occurred.

## Limits

The browser used a seeded local consumer account and did not submit a new
project. Production Clerk, D1, private media, Queues, Email, Turnstile, Images,
legal approval, assistive-technology testing, and Core Web Vitals remain
separate live release gates.
