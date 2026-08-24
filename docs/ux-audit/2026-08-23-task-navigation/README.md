# Task navigation and contractor dashboard QA

Reviewed the role-aware task navigation and contractor dashboard in the signed-in local Flask runtime.

## Viewports

- `390x844`: fixed four-item contractor navigation; active Bids state; no horizontal overflow; bid heading remains visible in the first viewport; profile summary is compact and scannable.
- `820x1180`: task links remain in the app header; profile facts use the available width; status tabs and bid rows remain readable.
- `1280x720`: identity, profile facts, and profile action share one unframed band; bid status is visible without excessive scrolling.

## Interaction checks

- Deer logo returns home.
- Client and contractor task sets are role-specific.
- Account controls stay in the overflow menu.
- Mobile Post opens the native project dialog without leaving the map context.
- Closing the dialog restores its originating Post link, map URL state, and prior background route.
- Fixed mobile navigation clears the footer and does not cover project-dialog actions.

## Evidence

- `contractor-dashboard-390x844.png`
- `contractor-dashboard-820x1180.png`
- `contractor-dashboard-1280x720.png`
- `figma-board-render.png`

## Figma

The editable reference and responsive target board is in [Workdoe Stabilization Reference Board - 2026-08-23](https://www.figma.com/design/wrHbwYR6SKJ5Nr5di9sgnE?node-id=1-2). It uses the captured PTOwl and NuTs screens as reference evidence only and labels the accepted Workdoe targets at all three release viewports.
