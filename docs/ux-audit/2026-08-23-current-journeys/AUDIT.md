# Current Journey Audit

Date: 2026-08-23

Scope: selected-browser evidence from the current local Flask build before and
after the contractor map-first parity change. Screenshots are viewport captures
and contain only seeded local demonstration records.

## Steps

1. Public/consumer Explore, desktop: healthy structure, but the headline and
   six-family selector consume most of the 1280x720 first viewport. The map is
   only partially visible in `01-explore-desktop.jpg`.
2. Public/consumer Explore, mobile: healthy compact selector and bottom
   navigation. The map appears in the first 390x844 viewport in
   `02-explore-mobile.jpg`.
3. Consumer dashboard, desktop: healthy project queue, status tabs, and
   scannable rows in `03-consumer-dashboard-desktop.jpg`.
4. Consumer dashboard, mobile: usable and overflow-free, but profile and metric
   blocks delay the first project row in `04-consumer-dashboard-mobile.jpg`.
5. Message inbox, mobile: healthy thread separation and clear actions in
   `05-messages-mobile.jpg`; the metadata line is dense at phone width.
6. Message thread, mobile: readable message ownership and report controls in
   `06-thread-mobile.jpg`; the composer is below the conversation and not
   visible in the first viewport.
7. Contractor dashboard, mobile: points, verified completion, and profile
   signals are understandable in `07-contractor-dashboard-mobile.jpg`, but the
   first bid row remains below the first viewport.
8. Contractor lead board, mobile: `08-contractor-leads-mobile.jpg` confirms the
   largest gap. Metrics, status tabs, family cards, and filters fill the first
   viewport, leaving both projects and the map off-screen.

## Highest-impact decision

The Cloudflare Worker already has a map-first, three-panel contractor workspace
with Projects, Map, and Details mobile tabs. Reusing that first-party pattern in
Flask removes design/runtime drift, puts the map in the first mobile viewport,
reduces long-scroll friction, and avoids inventing another controller.

## Implemented result

1. `09-contractor-leads-mobile-after.jpg` puts the live map in the first
   390x844 viewport with compact Projects, Map, and Details tabs.
2. `10-contractor-projects-mobile-after.jpg` keeps filtering, saved views,
   contractor fit, bid status, bid capacity, and brief readiness in a dedicated
   scrolling Projects panel instead of stacking them above the map.
3. `11-contractor-leads-desktop-after.jpg` provides one synchronized desktop
   workspace: filters and project rows on the left, the approximate map in the
   center, and the selected project brief on the right.
4. `12-contractor-leads-tablet-after.jpg` preserves the full-height map at
   820x1180 and keeps Search this area visible without horizontal overflow.
5. `13-contractor-lead-detail-mobile-after.jpg` confirms that selecting a row
   moves directly to a bid-ready detail panel, retains the selected `job_id` in
   the URL, and does not display an exact address.
6. `14-explore-desktop-after.jpg` compresses the public heading and six service
   families into two compact rows. The live map now begins at 350 pixels in the
   1280x720 viewport instead of sitting mostly below the first screen.
7. `15-explore-mobile-after.jpg` uses a horizontal six-family task rail. The map
   begins at 495 pixels in the 390x844 viewport with zero horizontal page
   overflow; only the deliberately scrollable task rail overflows its own
   container.
8. `16-contractor-dashboard-mobile-after.jpg` moves the response queue ahead of
   reputation and profile detail. The first actual bid begins at 602 pixels and
   remains visible above the mobile task navigation.
9. `17-thread-mobile-after.jpg` and `19-thread-desktop-after.jpg` turn the thread
   into a bounded conversation workspace: messages scroll internally and the
   reply composer remains visible at both tested viewport sizes.
10. `18-consumer-dashboard-mobile-after.jpg` removes three redundant summary
    metrics on phones while retaining them in the DOM and on wider layouts. The
    first project now begins at 553 pixels and is actionable in the first
    viewport.
11. `20-consumer-comparison-desktop-before.jpg` and
    `21-consumer-comparison-mobile-before.jpg` show the former bid-decision
    flow. Repeated status metrics and a three-step instruction strip delayed
    the first contractor card, while reviewed credential signals remained
    inside dense fact tables.
12. `22-consumer-comparison-desktop-after.jpg` and
    `23-consumer-comparison-mobile-after.jpg` remove the duplicate summary
    cards and instruction strip, keep status counts in the existing tabs, and
    move the first contractor into the first mobile viewport.
13. The accepted cards distinguish license source checked, other record source
    checked, and no source-checked record states without implying that Workdoe
    guarantees credentials. Every pending card retains profile and full-offer
    access and adds a direct Choose contractor action.
14. `24-consumer-comparison-desktop-before-after.jpg` and
    `25-consumer-comparison-mobile-before-after.jpg` hold the same-state visual
    comparisons used for acceptance. `26-consumer-license-filter-mobile.jpg`
    records the license-filtered card and its direct approval action.

The implementation reuses the existing Worker workspace, Leaflet controller,
green/gray tokens, service taxonomy, and Tabler icon set. No new dependency or
third-party visual asset was introduced.

## Accessibility limits

The DOM pass confirmed named navigation, tab, map, form, list, and message
regions. The mobile tablist now has explicit panel relationships, roving
`tabindex`, and Arrow Left/Right/Home/End behavior; an interactive check moved
focus and selection from Projects to Map with Arrow Right. Project rows retain
Arrow Up/Down/Home/End controls. Route tests confirm that selected lead state is
deterministic and that structured ZIP and client email fields are absent from
the contractor workspace.

This pass does not claim complete screen-reader output, automated contrast, or
reduced-motion certification. Those remain part of the final live acceptance
profile rather than screenshot evidence.

The consumer-choice interaction pass used temporary local-only contractors and
offers. Filtering to a current source-checked trade-license record left one
comparison card; choosing that contractor followed the established approval
route and opened the private message thread. The temporary users, credentials,
offers, thread, and message were removed after capture.
