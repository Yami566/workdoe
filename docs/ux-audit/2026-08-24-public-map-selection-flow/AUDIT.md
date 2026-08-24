# Public Map Selection Friction Audit

Date: 2026-08-24

## Scope

Anonymous public project discovery at `/`, from a selected approximate Leaflet
pin through the route-backed same-page sign-in dialog. The same seeded two-job
DMV state was captured before and after at 390x844 and checked after the change
at 1280x720.

## Finding

Selecting a public pin already wrote `job_id` into the URL and opened a popup,
but the popup stopped at title, city/state, and budget. On the Flask entry page
there is no adjacent detail rail, so the live-region instruction that details
were available beside the map was also inaccurate. A visitor had to leave the
map context and find the corresponding result row before continuing.

## Change

- Added one popup action using the job payload's existing permission-aware URL
  and action label. Anonymous projects show Sign in; authorized contractor
  payloads retain their existing review/bid action.
- Added a project-specific accessible name and a 44-pixel minimum touch target.
- Preserved the selected `job_id`, map position, and filters in URL state.
- Reused the audited route-backed dialog controller so Sign in opens over the
  map and keeps `next=/jobs/5`; closing restores `/?job_id=5` and the popup.
- Made the live-region instruction conditional: detail-rail surfaces announce
  that details are open, while simple entry maps direct users to the popup
  action.
- Added no route, public field, inference, dependency, or exact-location value.

## Evidence

- `01-mobile-map-before.jpg`: 390x844 public map before marker selection.
- `02-mobile-marker-selected-before.jpg`: selected marker with no next action.
- `03-mobile-marker-selected-after.jpg`: selected marker with the accepted
  white-on-green 44-pixel Sign in action.
- `04-mobile-marker-sign-in-after.jpg`: same-page email-code dialog retaining
  the selected lead.
- `05-desktop-marker-selected-after.jpg`: 1280x720 popup action over the
  unchanged map-first desktop surface.
- `06-mobile-marker-before-after.jpg`: aligned selected-marker comparison used
  for visual review.

## Acceptance

Browser DOM inspection confirmed the specific accessible link name, the
permission-aware `/login?next=/jobs/5` target, truthful live status, canonical
dialog URL, selected-lead summary, and restoration to `/?job_id=5` on close.
The visual comparison confirms the action fits without obscuring project facts
or map controls and uses the intended contrast after overriding Leaflet's link
color.

## Limits

This pass did not request a real production email code, prove a production
Clerk session, or run manual screen-reader software. Exact-location and contact
redaction remain covered by the existing API/permission suite; real OTP,
assistive-technology, and production performance checks remain release gates.
