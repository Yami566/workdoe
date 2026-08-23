# Workdoe Contractor Dashboard Friction Audit

Date: 2026-08-23

## Overall verdict

The contractor dashboard contained the right bid, milestone, credential, and
completed-work data, but duplicate metrics and a second queue heading delayed
the actual bids. The Cloudflare Worker also placed reputation and profile
detail ahead of the bid queue. This pass keeps the existing Workdoe visual
system and makes the first screen action, status, and bid focused in both
runtimes.

## Flow evidence

1. **Bid access: substantially faster after correction.**
   - `01-mobile-dashboard-before.jpg` records the prior same-state 390x844
     dashboard. The first bid began at 602 pixels after four metric cards, a
     repeated section heading, and a wrapped status filter.
   - `02-mobile-dashboard-after.png` shows the same seeded contractor state
     with the first bid beginning at 279 pixels.
   - `05-mobile-dashboard-before-after.png` places those states side by side.
     The first bid begins 323 pixels earlier without removing any bid status,
     milestone, credential, profile, or completed-work data.

2. **Bid triage: compact and reversible.**
   - All, Pending, Approved, and Rejected remain ordinary server-rendered links
     with live counts; all four fit in one mobile row without text overflow.
   - `03-mobile-pending-empty-after.png` shows the zero-pending state, a direct
     return to all bids, and earned progress in the same viewport.
   - The all-bids state keeps each project title, service, coarse city/state,
     status, and next action visible without exposing an exact address.

3. **Responsive layout: healthy.**
   - At 390x844, the browser measured `bodyWidth: 375` and
     `documentWidth: 375`, with the filters at 231 pixels, the first bid at 279
     pixels, and earned progress at 683 pixels. No horizontal overflow was
     detected.
   - `04-desktop-dashboard-after.png` at 1280x720 keeps the four filters in one
     row, begins the first bid at 277 pixels, and begins earned progress at 542
     pixels. `bodyWidth: 1265` matched `documentWidth: 1265`.

4. **Runtime parity and query work: improved.**
   - Flask and the Cloudflare Worker now use the same header, four-state
     filter, compact bid rows, view-aware zero states, and primary-first order.
   - Flask no longer runs an open-project count query solely to repeat the lead
     count on this dashboard. Project discovery remains available through the
     Browse projects action and the map-first lead board.
   - Milestone points and source-checked credential signals remain directly
     below the bid queue and continue to have no ranking effect.

## Accessibility checks

- The bid queue is a labelled region; its status selector is labelled
  navigation with `aria-current="page"` on the selected view.
- Each bid retains a task-specific accessible name such as Message about or
  View mini bid for the project title.
- Filters, rows, and empty-state return links remain keyboard reachable without
  client-side script.
- DOM and layout checks found no horizontal overflow at 390x844 or 1280x720.

## Evidence limits

- Screenshots and browser DOM checks do not prove complete screen-reader output.
- Local seeded data covered the all-bids and zero-pending states; automated
  tests cover other status views, role boundaries, Worker parity, credential
  signals, completion points, and location privacy.
- Production D1 latency, live rows-read telemetry, and Core Web Vitals require
  the guarded post-deployment acceptance run.
