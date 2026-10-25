# Public Surface Release-Candidate Audit

Date: 2026-10-24

Scope: a read-only local Workdoe release candidate at `127.0.0.1:5000`, using
seeded demonstration projects only. This pass did not sign in, request or enter
an email code, submit a project, upload media, or alter marketplace data.

An additional read-only production check used an already owner-authenticated
consumer browser session. It did not request or enter a code, submit a project,
upload media, or inspect private project details.

## Viewports reviewed

| Viewport | Result |
| --- | --- |
| `390x844` | Pass: the compact header, four-item bottom navigation, two-column service-family selector, map controls, and primary actions fit without overlap. |
| `820x1180` | Pass: navigation, the two-by-three service-family grid, map, filters, and results remain visible without clipping. |
| `1280x720` | Pass: desktop navigation, primary actions, service families, map pins, and map controls fit in the initial viewport without overlap. |

## Interaction evidence

- The public map provides labelled zoom controls, a privacy-safe current-map
  area description, and a DMV-view reset. The current-area action reports an
  approximate map center and explicitly states that Workdoe does not access
  device location.
- Opening **Post project** from the phone bottom navigation rendered the native
  in-place project dialog, rather than navigating or embedding an iframe. Its
  first step exposed numbered work-family radio controls, progress, Cancel, and
  Continue.
- Selecting **Cleaning** advanced to step 2 and exposed labelled task radio
  controls with Back and Continue. Closing the dialog returned to the map and
  restored keyboard focus to the original **Post** control.
- The public page exposes a skip link, semantic headings, labelled controls,
  and ordinary result links. Keyboard map zoom controls were present.
- The browser console reported no warnings or errors during this read-only
  public-surface pass.
- On production, **Post project** opened the route-backed native dialog from
  the public map. Its first step exposed the six labelled service-family radio
  controls and progress indicator; closing it restored the previously selected
  map project and focus to **Post project**.
- On production, a direct `/login` visit with an existing consumer Clerk
  session briefly showed **Checking Workdoe access...** and then opened the
  consumer Projects workspace without requesting another email code.

## Limits and remaining acceptance

This is release-candidate evidence only. It does not prove deployed production
parity, a live Clerk email-code journey, consumer and contractor workflows,
media authorization and upload limits, legal approval, retention operations,
incident response, or owner-controlled marketplace acceptance. Those gates
remain in `../../workdoe-owner-live-acceptance-checklist.md` and the controlling
`../../workdoe-launch-readiness-2026-10-24.md` record.
