# Workdoe Account Entry Friction Audit

Date: 2026-08-23

## Overall verdict

The same-page account entry pattern is healthy. Sign in and account creation
open over the public map, retain the selected-project URL state, and return
focus to a predictable control. This pass removed the largest remaining mobile
friction: repeated account actions consumed the space needed for the map, and
the two account paths could not be switched without closing the sheet.

## Flow evidence

1. **Signed-out map entry: healthy after correction.**
   - Before: `01-signed-out-home-before.png` shows Sign in, Find work, and Post
     project repeated between the persistent header and bottom task bar.
   - After: `04-signed-out-home-after.png` keeps the header and bottom task bar,
     moves the approximate map 106 pixels earlier, and retains all four primary
     mobile destinations.
   - The six work families remain horizontally browsable and the map remains
     interactive.

2. **Sign in sheet: healthy after correction.**
   - Before: `02-sign-in-dialog-before.png` had no direct path for a new user and
     exposed an implementation-oriented `Admin/demo password` label.
   - After: `05-sign-in-dialog-after.png` uses the plain `Use a password` fallback
     label and adds `New to Workdoe? Create account` inside the sheet.
   - Switching account paths updates the canonical URL through the existing
     History API controller without navigating away from the map.

3. **Create account sheet: healthy after correction.**
   - Before: `03-create-account-dialog-before.png` used a decorative tactical
     pseudo-label and offered no direct path back to sign in.
   - After: `06-create-account-dialog-after.png` starts directly with the role
     choice and adds `Already have an account? Sign in` in the visible viewport.
   - The role labels, email, name, organization, and primary action remain
     readable without horizontal overflow at 390x844.

4. **Tablet and desktop entry: healthy.**
   - `07-tablet-home-after.png` at 820x1180 preserves the explicit three-action
     row and shows the full six-family grid above the map.
   - `08-desktop-home-after.png` at 1280x720 preserves the compact desktop
     hierarchy and keeps the map as the dominant first-screen workspace.

## Accessibility checks

- Dialogs expose names, a labelled close button, and semantic form controls.
- The in-sheet account switch is a normal link and works in both directions.
- Focus moves to the close button after a sheet switch; the existing close path
  restores focus and background URL state.
- DOM and layout checks found no horizontal overflow at 390x844, 820x1180, or
  1280x720.

## Evidence limits

- Screenshots and browser DOM checks do not prove full screen-reader support.
- Local fallback email entry was exercised visually. Production Clerk email
  delivery and invitation acceptance still require a post-deployment live test.
- Core Web Vitals and production network behavior are outside this local audit.
