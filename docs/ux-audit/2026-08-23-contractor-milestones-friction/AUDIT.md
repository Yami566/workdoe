# Contractor Milestone Audit

Date: 2026-08-23

## Scope

This current-run audit reviewed how one mutually confirmed project appears to
the contractor on `/contractor/dashboard` and to profile viewers on
`/contractors/3`. The local Flask adapter was captured at 390x844, 820x1180,
and 1280x720. The Cloudflare Worker uses the same deterministic reputation
projection and equivalent server-rendered markup.

## Steps And Findings

1. **Contractor dashboard before - needs correction.**
   `02-mobile-milestones-before.png` shows “First finish” and 100 points, but
   the progress bar is empty because it describes progress after the first
   milestone as `0 of 2`. The four earnable milestones are not visible, and a
   long method paragraph delays the contractor's profile controls.
2. **Public profile before - needs correction.**
   `03-mobile-public-profile-before.png` repeats “1 project,” “First finish,”
   and “100 points” without showing what was earned or what comes next. A
   consumer cannot scan the complete milestone path.
3. **Public profile after - healthy.**
   `04-mobile-public-profile-after.png` and
   `05-mobile-milestone-track-after.png` show the verified completion count,
   earned First finish marker, next milestone, later thresholds, and truthful
   `1 of 3` progress. Source-checked records remain a separate trust signal.
4. **Contractor dashboard after - healthy.**
   `06-mobile-dashboard-after.png`, `07-desktop-dashboard-after.png`, and
   `08-tablet-dashboard-after.png` keep bids ahead of progress while making all
   four milestones scannable. The compact track fits each tested viewport with
   no horizontal document overflow.

`09-mobile-dashboard-before-after.png` is the same-state comparison used to
judge the mobile correction.

## Accessibility And Safety

- Milestones are an ordered list with an accessible label; the current earned
  milestone uses `aria-current="step"`.
- The progress element has a specific accessible name and now reports absolute
  progress to the next threshold.
- Earned markers reuse the pinned MIT-licensed Tabler sparkles asset. Text and
  state do not rely on color alone.
- Points remain a presentation-only projection of mutually confirmed Workdoe
  projects. They do not change lead order, bid order, service eligibility, or
  credential status and create no new stored profile or ranking data.

## Limits

Screenshots do not prove screen-reader announcements, production Worker asset
delivery, or real-user comprehension. Those remain post-deployment and pilot
acceptance checks. No production deployment was performed.
