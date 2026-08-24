# Guided Project Posting UX Audit

Date: 2026-08-16  
Journey: signed-in consumer -> Post project -> review  
Viewports: desktop and 390 x 844 mobile

## Journey Health

Overall: Healthy for the local pilot after the guided-flow change.

The original form was functional and accessible at a basic level, but exposed all fields at once and required the consumer to translate their need into a trade category before describing the work. The updated flow begins with six recognizable work families, narrows to a canonical service, and asks one coherent group of questions at a time.

## Evidence

1. Original all-at-once form: `before-post-project.png`
2. New family picker on desktop: `after-step-1-desktop.png`
3. New final review on desktop: `after-step-6-review.png`
4. New family picker at 390 x 844: `after-step-1-mobile-viewport.png`

## Findings

1. High, resolved: Category selection required users to know Workdoe's internal trade vocabulary. Six families plus a precise service step now translate ordinary intent into canonical storage.
2. High, resolved: The old page presented title, category, timing, location, budget, description, and photos simultaneously. The new flow limits each screen to one decision group and exposes progress.
3. Medium, resolved: Consumers had no final confirmation of service, location privacy, timing, or budget. Step 6 now provides a concise review before submission.
4. Medium, resolved: The prior category field could not represent moving, house cleaning, or detailed yard work accurately. D1/SQLite now preserve a precise service slug and broad compatibility category.
5. Medium, resolved: Mobile controls remain full-width and the six choices become a single scanning column. Text fits without horizontal scrolling at 390 px.
6. Low, retained intentionally: The service list is large. It is filtered to the selected family when JavaScript is available and remains a grouped native select without JavaScript.

## Accessibility Checks

- Native radio group, fieldset, legend, select, labels, and progress element are present.
- Continue validates only the current step; server validation remains authoritative.
- Back and Continue preserve entered values.
- Invalid server responses reopen the step containing the first invalid field.
- Keyboard focus moves to the updated step heading.
- The unenhanced HTML form remains operable when JavaScript is unavailable.

## Evidence Limits

This audit used the in-app Chromium browser, DOM snapshots, screenshots, and automated tests. It does not replace a manual screen-reader session, switch-control testing, independent usability sessions with consumers/contractors, or production telemetry.
