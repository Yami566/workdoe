# Public Project List Continuation Audit

Date: 2026-08-24

## Scope

Anonymous project results on the public marketplace, including the initial
Flask render, live `/api/jobs/open` replacement, same-page sign-in, Worker entry
shell, and signed-in contractor lead renderer. The public journey was checked
on phone and desktop using the same seeded two-project DMV state.

## Finding

Project rows were anchors with `role="listitem"`. That explicit role replaced
their native link role, so the accessibility tree exposed passive list items
even though mouse and keyboard activation still navigated. The live API refresh
also replaced the initial rows with cards that omitted the visible Sign in cue,
making the list less direct after the map loaded.

## Change

- Moved `role="listitem"` to a noninteractive wrapper and kept the unchanged
  same-domain anchor inside it.
- Preserved list grouping while restoring native link semantics and specific
  accessible names for each project.
- Added one compact cue derived from existing permission-aware state: Sign in
  on the public Flask surface, View in detail workspaces, and Sent for a
  contractor's submitted bid.
- Kept the whole card as the single action; the cue is text rather than a
  nested button or competing target.
- Applied the same markup contract to home, login, account start, contractor
  leads, Worker entry/app shells, and JavaScript-refreshed result rows.
- Rotated the shared stylesheet and map-script versions so both runtimes receive
  the accepted markup and presentation together.

## Evidence

- `01-mobile-public-list-before.jpg`: public phone list before the correction;
  cards have no visible continuation cue.
- `02-mobile-public-list-after.jpg`: refreshed phone list with compact Sign in
  cues.
- `03-mobile-list-sign-in-after.jpg`: route-backed email-code dialog retaining
  the selected project.
- `04-desktop-public-list-after.jpg`: map-first desktop surface with the same
  result cues.
- `05-mobile-list-before-after.jpg`: focused comparison of the result section.

## Acceptance

Browser DOM inspection changed both public results from `listitem` to `link`,
retained `/login?next=/jobs/5`, and exposed the visible Sign in cue after live
API replacement. Activating the first result opened the existing Sign in dialog
at `/login?next=%2Fjobs%2F5`, showed the selected lead, and closing restored
`/?job_id=5`; the originating result was marked active in the accessibility
tree. Flask and Worker contract tests reject the former anchor-level list-item
role.

## Limits

The browser pass did not request a real production email code or run manual
screen-reader software. The full-page capture utility can repeat fixed or
dynamically refreshed regions while stitching; DOM inspection confirmed only
two project links existed in the live page. Real OTP, assistive-technology, and
production performance checks remain release gates.
