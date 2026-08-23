# Workdoe Public Contractor Profile Friction Audit

Date: 2026-08-23

## Overall verdict

The public contractor profile now supports the client decision instead of
behaving like a detached biography page. Current Workdoe completions,
availability, milestone points, and source-checked record state lead the page;
project-linked visits preserve an ownership-checked return path and expose the
appropriate Choose or Message action.

## Flow evidence

1. **Trust-first mobile profile: healthy after correction.**
   - Before: `01-mobile-public-profile-before.png` put biography, website,
     services, and a ten-area text list ahead of the milestone section. The
     milestone began at 937 pixels in the measured 390x844 state.
   - After: `02-mobile-public-profile-after.png` presents availability,
     Workdoe-completed projects, years active, reviewed-record state, and
     milestone points first. The milestone begins at 612 pixels, 325 pixels
     earlier, with zero horizontal document overflow.
   - `07-mobile-public-profile-before-after.png` is the same-state comparison.

2. **Pending offer context: healthy.**
   - `03-mobile-client-choice-context.png` shows a project-specific Back to
     offers action and Choose contractor action before the trust summary.
   - The context appeared only after the signed-in client opened a profile from
     a project they owned and for which that contractor had a matching offer.
   - Choosing the contractor opened the private message thread through the
     existing approval route.

3. **Approved offer context: healthy.**
   - `04-mobile-client-approved-context.png` shows the same project context
     changing from Choose contractor to Message contractor after approval.
   - Back to offers returned to `/client/jobs/5#mini-bids`, with the mini-bid
     section measured 18 pixels from the viewport top.
   - The temporary QA offer, thread, and initial message were removed after the
     interaction pass.

4. **Desktop decision view: healthy.**
   - `05-desktop-client-approved-context.png` at 1280x720 keeps the project
     context, all four contractor facts, and milestone progress in one
     first-viewport scan without horizontal overflow.

5. **Coverage disclosure: healthy.**
   - `06-mobile-coverage-open.png` shows all ten current DMV service areas in a
     native disclosure below About. The collapsed state replaces the former
     narrow-column text wall without removing information.

## Runtime and privacy checks

- Flask and Cloudflare Worker comparison links carry only a numeric project ID.
- Both adapters derive the project context from server-side client ownership,
  contractor identity, and match-request records. An unrelated or missing
  project ID produces no decision context.
- Pending context exposes approval; approved context exposes only the existing
  private thread. Rejected context retains the return path without a decision
  action.
- Exact addresses, contact details, and credential identifiers are not added to
  the public profile payload.

## Accessibility checks

- Project actions use ordinary links and semantic forms with existing CSRF or
  same-origin Worker protections.
- Contractor facts remain a description list and milestones retain labelled
  progress semantics.
- Service coverage uses native `details` and `summary` without new script.
- DOM and layout checks found no horizontal overflow at 390x844 or 1280x720.

## Evidence limits

- Browser DOM checks and screenshots do not prove complete screen-reader
  support.
- Source review remains a factual public-record check, not a guarantee of
  licensing status, skill, safety, insurance, or legal eligibility.
- Production Clerk, private-media, accessibility, and Core Web Vitals gates
  remain post-deployment acceptance work.
