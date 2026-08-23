# Workdoe Contractor Profile Friction Audit

Date: 2026-08-23

## Overall verdict

Contractor profile setup now presents the three maintenance tasks before the
long service editor. Availability, profile details, and credentials have direct
anchors; a completed readiness checklist stays compact; and credential claims
appear before the 53-service form without changing data, review, or permission
contracts.

## Flow evidence

1. **Mobile profile entry: healthy after correction.**
   - Before: `01-mobile-profile-before.png` used a long explanatory heading and
     expanded all seven completed readiness items. Credential setup began at
     5,834 pixels in a 7,442-pixel document.
   - After: `02-mobile-profile-after.png` uses the shared compact dashboard
     heading, puts Preview and the three task links first, and collapses the
     completed checklist. Credential setup begins at 868 pixels.
   - `05-mobile-profile-before-after.png` provides the same-state 390x844
     comparison.

2. **Credential shortcut: healthy after correction.**
   - `03-mobile-credentials-anchor-after.png` shows the Credentials task link
     landing on the claim form with its heading fully visible below the sticky
     app bar.
   - The target uses a 72-pixel scroll margin; the measured section and heading
     positions were 72 and 115 pixels from the viewport top.

3. **Responsive desktop hierarchy: healthy.**
   - `04-desktop-profile-after.png` at 1280x720 keeps profile setup, task links,
     readiness, and availability in a scannable first viewport.
   - The credential section begins at 606 pixels and the document has no
     horizontal overflow.

4. **Runtime parity: preserved.**
   - Flask and Cloudflare Worker output the same task links, readiness
     disclosure behavior, credential-first ordering, and profile-details
     anchor.
   - Incomplete profiles keep the native readiness disclosure open; profiles
     at 100% keep it collapsed.

## Accessibility checks

- Profile tasks are ordinary anchor links with existing vendored Tabler icons.
- Readiness uses native `details` and `summary` semantics without new script.
- The anchor scroll offset prevents the sticky app bar from obscuring target
  headings.
- DOM and layout checks found no horizontal overflow at 390x844 or 1280x720;
  all three mobile task labels fit their stable grid columns.

## Evidence limits

- Browser screenshots and DOM measurements do not prove full screen-reader
  support.
- Credential source checking remains an administrator workflow and was not
  changed or represented as identity, safety, skill, or licensing assurance.
- Production Clerk, media, accessibility, and Core Web Vitals gates remain
  post-deployment acceptance work.
