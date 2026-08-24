# Project License Preference UX Audit

Date: 2026-08-24

Status: Passed local responsive review.

## Scope

- Consumer six-step project composer, including the optional preference and
  review summary.
- Contractor lead list, selected-project detail, and approximate map state.
- Responsive checks at 390x844, 820x1180, and 1280x720.
- Neutral wording: a source-checked record is not a ranking, eligibility, or
  legal-authorization decision.

## Evidence

- `composer-preference-390x844.png`: optional preference remains inside step 5
  with one checkbox target and one primary action.
- `composer-review-390x844.png`: the review summary exposes `License record
  preferred` before posting and keeps the existing advisory acknowledgement.
- `composer-review-820x1180.png` and `composer-review-1280x720.png`: the same
  review contract remains readable without horizontal overflow.
- `contractor-detail-390x844.png` and `contractor-detail-820x1180.png`: the
  selected-project view shows the preference, limitation copy, and primary bid
  action without overlap.
- `contractor-leads-1280x720.png`: list, approximate map, and selected detail
  remain synchronized; the preference appears in both decision surfaces.

## Interaction Checks

- The checkbox state carried from step 5 to step 6 as `License record
  preferred`; the unchecked server contract remains `Any provider`.
- Mobile Projects, Map, and Details tabs remained keyboard-addressable and the
  selected detail was available without leaving the lead board.
- Measured document width equaled viewport width at 390 and 1280 pixels. The
  820-pixel viewport reported a 805-pixel layout width because of the browser
  scrollbar and no horizontal overflow.
- The preference control measured about 324 by 121 pixels on the narrow phone
  state; the desktop submit control retained a 44-pixel height.
- The dynamically refreshed Flask detail initially exposed a broken icon path.
  The shared map controller now receives a server-rendered asset root; the
  recaptured icon loaded at its intrinsic 24-pixel width in phone, tablet, and
  desktop states. The Worker continues to resolve the same asset at `/vendor`.

## Safety And Product Boundary

The signal is a consumer preference only. It does not filter or rank
contractors, change received-order bid comparison, decide whether a provider
may bid, verify insurance or credentials, or represent legal authorization for
the project scope or jurisdiction.
