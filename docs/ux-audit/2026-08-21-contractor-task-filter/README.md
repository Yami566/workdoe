# Contractor task filter review

## Scope

- Signed-in contractor lead board filtered to `outdoor-yard` and `pressure-washing`.
- Desktop viewport: 1280 x 720.
- Mobile viewport: 390 x 844, reviewed at the filter and result/map positions.

## Evidence

- `01-desktop-contractor-task.png`
- `02-mobile-contractor-task.png`
- `03-mobile-contractor-results.png`

## Findings

- The selected work family and exact task remain visible and understandable.
- Only the matching pressure-washing lead remains in the list and map.
- Status tabs preserve the task selection.
- Saved-view controls retain the task without exposing exact address data.
- The signed-out lead route preserves the validated family and task through the
  same-domain sign-in page and keeps the exact-task map/list result visible.
- First-time users from that route begin as contractors, and Clear removes the
  nested task filter instead of silently restoring it.
- Sign-in and account-page filters navigate in place; the marketplace popup
  interceptor does not open a second authentication dialog inside those pages.
- Controls and text fit at both reviewed viewports without overlap.
- Keyboard-readable labels and native select semantics remain present.

Automated checks cover invalid and cross-family task values, exact-task saved
URLs and alerts, sign-in continuity, SQLite upgrades, D1 migration markers, and
Flask/Worker rendering parity.
