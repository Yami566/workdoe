# Contractor Opportunity Flow Audit

Date: 2026-08-24

## Scope

This current-run audit reviewed the signed-in contractor journey from the
mobile map to one selected project and the equivalent desktop
projects/map/detail workspace in the latest combined local candidate.

## Steps And Health

1. **Open the project map - healthy.** At 390x844, the map remains the default
   contractor Explore view. Two approximate pins, zoom controls, the Projects,
   Map, and Details tabs, and the four primary task destinations fit without
   horizontal overflow.
2. **Select a project - healthy.** Selecting the Washington pin updates the
   canonical URL to `/leads?job_id=4` and opens Details in one action. The
   selected view exposes the task, coarse location, budget, desired date, bid
   capacity, license preference, short scope, privacy reminder, and the
   contractor's existing bid-status action.
3. **Compare project, map, and detail - healthy.** At 1280x720, the same
   selection stays synchronized across the received lead row, approximate map
   popup, and detail rail. Project and status labels remain visible rather than
   relying on pin color or position.

## Evidence

- `01-mobile-lead-board-before.png`: accepted 390x844 map-first entry.
- `02-mobile-project-selected-before.png`: accepted 390x844 selected project.
- `03-desktop-selected-project.png`: accepted 1280x720 synchronized workspace.

Browser inspection measured a 390-pixel document and viewport width on mobile
and a 1280-pixel document and viewport width on desktop. The mobile tablist
exposes one selected tab at a time, marker buttons have project-and-location
accessible names, and the selected project URL retains only a numeric job ID.

## Decision

No visual rearrangement is justified in this state. The evidence supports
keeping the current Leaflet map/list/detail interaction and spending this batch
on the higher-risk release-evidence defect found in the guarded Cloudflare
deployment path.

## Verification

- Full Ruff: passed.
- Unit and integration suite: 239 tests passed in 82.376 seconds.
- Node and Python dependency audits, Bandit, secret, and provenance gates:
  passed across 680 non-ignored files.
- Cloudflare preflight: passed without warnings.
- D1 verification: all 34 migrations loaded; all three expected public
  map/photo indexes were used; no table scan was found.
- Wrangler 4.125.0 dry run: 49 Python modules and 88 static assets packaged at
  941.19 KiB / 172.97 KiB gzip without deploying.

## Limits

The seeded contractor had already submitted bids on both visible projects, so
the selected action reads `View bid status`; the prior audited unsubmitted-lead
dialog remains covered by route and browser tests but was not recaptured here.
Screenshots do not prove production D1 latency, Clerk authentication, tile
capacity, or real-user comprehension. No GitHub push or Cloudflare deployment
was performed.
