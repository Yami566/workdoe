# Contractor Choice Card Audit

Date: 2026-08-23

## Scope

This current-run audit reviewed the owning consumer's pending-offer comparison
at `/client/jobs/4?bids=pending#mini-bids`. The local Flask adapter was checked
at 390x844, 820x1180, and 1280x720. The Cloudflare Worker renders the same
shared comparison projection and equivalent server-side card contract.

## Findings

1. **Before - contractor choice starts too late.**
   `01-mobile-comparison-entry-before.png` shows job controls, repeated ranking
   guidance, filter guidance, and no contractor identity card in the first
   mobile viewport.
2. **Before - the card reads like a report.**
   `02-mobile-offer-card-before.png` has no portfolio identity and repeats
   source-check and license facts after already stating that no reviewed record
   exists.
3. **After - choice is visual and scannable.**
   `03-mobile-comparison-after.png` places the first received-order card at 444
   pixels, includes the existing visible contractor portfolio image, and keeps
   price, timing, completion, insurance, and reviewed-record state together.
4. **After - actions remain explicit.**
   `04-mobile-card-actions-after.png` keeps Profile, Full offer, and Choose
   contractor visible as separate actions. The qualification disclaimer remains
   available through a native disclosure.
5. **Responsive result.**
   `05-tablet-comparison-after.png` and `06-desktop-comparison-after.png` preserve
   the bounded card and received-order filters. The page had no horizontal
   document overflow at any tested viewport.

`07-mobile-comparison-before-after.jpg` is the aligned same-state comparison
used to judge the visible change.

## Accessibility, Privacy, And Performance

- The portfolio image has a contractor-specific alt label and fixed dimensions;
  absent photos produce no fake avatar or placeholder art.
- Signals keep text labels and do not depend on color alone.
- The image URL contains only the visible contractor-photo ID. Stored object
  keys and original filenames remain outside the comparison projection.
- The newest visible-photo lookup uses
  `idx_contractor_photos_public_contractor`; the query-plan verifier rejects a
  contractor-photo table scan.
- Photo presence has no effect on received order, eligibility, credentials,
  or ranking.

## Limits

The screenshots do not prove production R2 delivery, real-user comprehension,
or legal sufficiency of credential wording. Those remain controlled-beta and
post-deployment acceptance checks. No production deployment was performed.
