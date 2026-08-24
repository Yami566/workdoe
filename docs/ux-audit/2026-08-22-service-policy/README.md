# Service Policy Dialog QA

Date: 2026-08-22

## Scope

- Client project composer opened in the native route-backed dialog.
- Regulated `electrical` service selected through the six-step flow.
- Standard `house-cleaning` service checked as the no-advisory control.
- Responsive states checked at 1280x720, 820x1180, and 390x844.

## Evidence

- `regulated-desktop-1280x720.png`
- `regulated-tablet-820x1180.png`
- `regulated-mobile-390x844.png`

## Verified

- Regulated advisory names permits, licenses, inspections, utilities, and direct provider checks.
- Workdoe explicitly states that it does not verify provider credentials.
- The current policy acknowledgement is required and keyboard-visible.
- The project action dock remains available without covering advisory or photo controls.
- Inactive step actions stay hidden; one active Continue control is exposed.
- Standard services render no advisory and no acknowledgement checkbox.
- The live map and selected background state remain in place behind the dialog.

## Resolved During QA

- Compacted the desktop/tablet project review into two scannable columns.
- Anchored actions to the centered dialog surface on tall viewports.
- Preserved a single-column mobile reading order and touch-sized controls.
- Added explicit hidden-step action styling for focus and automation clarity.
