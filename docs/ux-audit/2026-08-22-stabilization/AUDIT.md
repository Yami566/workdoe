# Native Dialog Stabilization Audit

Date: 2026-08-22

## Scope

This evidence set covers the same-page authentication and project-posting flows introduced during the Workdoe stabilization release. Canonical routes remain available as full pages, while same-origin links can open their form fragment in a native `dialog` element.

## Interaction Results

- `/login`, `/create-account`, and `/post-project` open without an iframe when selected from the marketplace.
- The six-step composer advances within the dialog without navigating away from the map.
- Closing restores the selected project, filter/map URL, and keyboard focus to the invoking control.
- Browser Back closes the active dialog; Forward restores it.
- Escape closes the dialog and restores focus.
- Direct route visits and no-JavaScript form submissions remain supported.
- Fragment and full-page responses retain `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'`.
- The script loader accepts only the audited Clerk, Turnstile, project composer, email-code, and Worker action entry points.

The local browser pass did not submit a live Clerk production email code because production credentials are not present in the local test configuration. Server-side route, validation, and parity coverage remains in the automated suite; a live email-code journey is a production acceptance gate.

## Visual Evidence

- `02-native-signin-compact-desktop.png`: sign-in dialog at 1280x720.
- `03-native-project-composer-desktop.png`: project composer at 1280x720.
- `04-native-project-composer-mobile.png`: bottom-sheet composer at 390x844.
- `05-marketplace-mobile.png`: marketplace after dialog close at 390x844.
- `06-marketplace-tablet.png`: marketplace at 820x1180.
- `comparison-*.png`: prior accepted reference on the left and current implementation on the right.

The comparison pass checked spacing, typography, clipping, scroll behavior, backdrop treatment, action visibility, and map preservation. No visible overlap or clipped primary action remains at the target viewports.

## Automated Coverage

`tests/test_workdoe.py` and `tests/test_cloudflare_release.py` assert the local and Worker dialog shells, fragment markers, no-iframe contract, non-frameable security headers, URL controller hooks, focus restoration hooks, responsive sizing, and local/Worker presentation parity.
