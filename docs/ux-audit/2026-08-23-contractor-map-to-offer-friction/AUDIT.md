# Contractor Map-To-Offer Audit

Date: 2026-08-23

## Scope

This current-run audit covered the signed-in contractor journey from the
mobile and desktop lead map to project review, mini-bid submission, and return
to the selected project. The local Flask adapter was exercised at 390x844 and
1280x720. The Cloudflare Worker uses the same route, action-label, fragment,
and presentation contracts and is covered by parity tests.

## Finding

The former `View and send bid` action left the lead workspace and opened a
3,270-pixel mobile page. The form appeared well below the project detail, while
the selected project, map position, filters, and keyboard return point were no
longer available in context. This created avoidable friction at the point where
a contractor had already decided to quote.

## Correction

- `Review and bid` now opts project links into the existing audited native
  route-dialog controller.
- `/jobs/<id>` remains the canonical direct URL and no-JavaScript full-page
  fallback.
- Mobile uses a bottom sheet with the project snapshot and bid form before the
  longer brief; desktop uses a two-column review and form dialog.
- Successful Flask and Worker actions refresh the open dialog instead of
  navigating away.
- Dialog navigation resets to the project heading, preserves the route in
  browser history, and returns focus to the invoking action when closed.
- Map result rows remain map-selection controls because project routes require
  an explicit `data-dialog-title` opt-in outside an open dialog.

## Evidence

- `01-mobile-map-before.png`: map state before opening a project.
- `02-mobile-details-before.png`: selected project and former action.
- `03-mobile-full-page-bid-before.png`: former 3,270-pixel mobile page.
- `04-mobile-bid-sheet-after.png`: compact 390x844 bid sheet.
- `05-desktop-bid-dialog-after.png`: 1280x720 two-column dialog.
- `06-mobile-bid-sent-after.png`: top-aligned success state after submission.

The final browser check found a 390-pixel document width at a 390-pixel
viewport, zero horizontal overflow, an open dialog after submission, content
scroll position `0`, focus on the dialog's project landmark, and restored URL
`/leads?job_id=5` plus restored `Review and bid` focus after close. Temporary
QA bid records were removed from the local database after capture.

## Limits

This evidence is local and does not substitute for post-deployment Clerk,
Cloudflare Images, private-media, accessibility, or Core Web Vitals acceptance.
No production deployment was performed.
