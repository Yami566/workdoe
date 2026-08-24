# Public Map To Project Friction Audit

Date: 2026-08-24

## Scope

Anonymous public map and route-backed project dialog at `/`, `/post-project`,
and the first two composer steps. The same seeded two-project DMV state was
captured before and after at 390x844 and checked after the correction at
1280x720.

## Steps and health

1. **Open Workdoe on a phone: improved.** The map, approximate pins, six-family
   selector, Post task, Sign in task, and Create account action remain in the
   first viewport. The home heading is now one line at the fixed phone size,
   restoring additional map height without changing the desktop heading.
2. **Start a project without leaving the map: healthy.** Post opens the
   canonical `/post-project` route in the existing native dialog. Closing still
   returns to the selected map state, and the direct URL remains the
   no-JavaScript fallback.
3. **Choose a work family: improved.** The former single-column phone layout
   exposed only part of the six choices before scrolling. The accepted layout
   shows all six numbered choices in a two-column grid with the existing Tabler
   icons and 76-pixel minimum control height.
4. **Choose a common task: improved.** The former layout exposed three of six
   common tasks and repeated the selected family on every card. The accepted
   layout shows all six tasks plus the More services disclosure, states the
   family once, and retains 72-pixel minimum controls.
5. **Continue with a canonical service: healthy.** DOM inspection found six
   family radios, six common-task radios for the selected family, progress text,
   Back, Continue, and the ordinary fallback select. The chosen service still
   uses the deterministic 53-service taxonomy and existing draft contract.
6. **Review on desktop: healthy.** The project dialog retains its three-column
   task grid, selected-family context, fixed actions, and map backdrop at
   1280x720. The public desktop map remains the primary first-screen surface.
7. **Receive the corrected CSS: improved.** Flask, the Worker app shell, and the
   Worker entry shell now reference one new stylesheet version. The browser
   pass confirmed that the accepted 24-pixel phone heading and compact controls
   loaded from that version rather than a cached predecessor.

## Evidence

- `10-mobile-family-before-after.jpg`: aligned 390x844 family-step comparison.
- `11-mobile-task-before-after.jpg`: aligned 390x844 task-step comparison.
- `05-mobile-home-after.jpg`: accepted one-line heading and map-first phone view.
- `08-desktop-task-step-after.jpg`: accepted desktop task selection.
- `09-desktop-home-after.jpg`: accepted desktop public map.

## Limits

The browser pass did not submit an anonymous draft, request a real email code,
or prove production Core Web Vitals. Those behaviors are covered by existing
local integration tests or remain live release gates. The screenshots do not
prove screen-reader announcements; manual assistive-technology acceptance is
still required.
