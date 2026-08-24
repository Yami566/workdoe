# Contractor Saved-Alert Friction Audit

Date: 2026-08-24

## Scope

Authenticated contractor lead board at `/leads`, using the seeded contractor
account and the same two local open projects before and after the change.

## Finding

The saved-view and email-alert backend was already complete: explicit consent,
canonical service and DMV-zone matching, D1 delivery deduplication, Queue
fanout, Email Service delivery, and redacted audit events. The problem was the
presentation. On a 390x844 phone, the family carousel, search form, sort,
actions, alert radios, and explanatory copy filled the Projects panel before a
single project appeared.

## Change

- Kept All, New, and Bids sent as immediate status controls.
- Moved family, task, search, sort, saved-view, and alert controls into one
  native `details` disclosure.
- Kept the disclosure closed for an unfiltered board and open when a query
  filter is active.
- Exposed the active task, sort, and alert state in the collapsed summary.
- Kept project facts readable by wrapping them instead of truncating each fact.
- Added the missing lead-status tabs and photo count to the Cloudflare Worker
  renderer, preserving Flask/Worker behavior and copy parity.
- Removed the redundant visible View/Sent cue from refreshed rows while keeping
  a specific accessible link label.

## Evidence

- `01-mobile-projects-before.png`: 390x844 baseline; no project is visible.
- `03-mobile-projects-after-final.png`: 390x844 result; both projects are
  visible with the compact controls collapsed.
- `04-tablet-projects-after.png`: 820x1180 responsive Projects panel.
- `05-desktop-workspace-after.png`: 1280x720 list, map, and selected-project
  workspace.
- `06-mobile-projects-before-after.jpg`: aligned mobile comparison used for the
  visual review.

## Review

The after state keeps the primary work-selection task in the first phone
viewport, preserves the map-first default, and makes alert configuration
available without presenting it as a prerequisite. The native disclosure is
keyboard-operable and needs no new JavaScript or dependency.

This pass does not prove production email delivery, screen-reader behavior, or
live performance. Those remain final production acceptance gates.
