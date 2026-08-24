# Workdoe Consumer Dashboard Friction Audit

Date: 2026-08-23

## Overall verdict

The consumer dashboard exposed the right project history and review actions,
but profile context and aggregate metrics delayed the first real project on a
small screen. This pass keeps the existing Workdoe visual system and reduces
the first screen to one posting action, four status views, and the project
queue. Profile editing remains available from account navigation.

## Flow evidence

1. **Project access: substantially faster after correction.**
   - `01-mobile-dashboard-before.png` shows the first project beginning at 553
     pixels after a profile summary, two metric cards, and wrapped filters.
   - `02-mobile-dashboard-after.png` shows the same signed-in state with the
     first project beginning at 279 pixels.
   - `05-mobile-dashboard-before-after.png` places the two 390x844 states side
     by side. The primary work queue begins 274 pixels earlier without hiding
     any project status or posting action.

2. **Status triage: compact and consistent.**
   - All, Review, Open, and Closed remain ordinary server-rendered links with
     live counts; all four fit in one mobile row.
   - `03-mobile-review-empty-after.png` shows the zero-review state and a direct
     return to all projects in the first viewport.
   - An unknown `view` value safely normalizes to All in both runtime adapters.

3. **Responsive layout: healthy.**
   - At 390x844, the browser measured `bodyWidth: 375` and
     `documentWidth: 375`, with the filters at 231 pixels and the first project
     at 279 pixels. No horizontal overflow was detected.
   - `04-desktop-dashboard-after.png` at 1280x720 keeps the filters constrained
     to the project column; the first row begins at 277 pixels and no horizontal
     overflow was detected.

4. **Runtime parity and query work: improved.**
   - Flask and the Cloudflare Worker now expose the same All, Review, Open, and
     Closed dashboard contract and the same view-aware empty states.
   - Flask derives filtered jobs, status counts, and closed-project history from
     one project workspace query. It no longer repeats that query or loads
     profile, location, and template data solely for the removed summary strip.
   - Route-level tests protect the single workspace call and invalid-view
     fallback; Worker contract tests protect the review zero state.

## Accessibility checks

- The status selector is a labelled navigation region with `aria-current` on
  the selected view.
- The project queue is a labelled list, and each row retains a task-specific
  accessible name such as Review pending bids.
- Links and empty-state actions remain keyboard reachable without client-side
  script.
- DOM and layout checks found no horizontal overflow at 390x844 or 1280x720.

## Evidence limits

- Screenshots and browser DOM checks do not prove full screen-reader support.
- Local seeded data covered consumer All and zero-review states; automated
  tests cover filtering, normalization, role boundaries, and Worker parity.
- Production D1 latency, rows-read telemetry, and Core Web Vitals require the
  guarded post-deployment acceptance run.
