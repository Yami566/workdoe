# Local Browser Acceptance

Date: 2026-08-23

Scope: authenticated local Flask release candidate at `127.0.0.1:5017` in the
Codex in-app browser. This is local interaction evidence, not production
performance, identity-provider, or assistive-technology evidence.

## Mobile profile

- Requested viewport: 390x844. The browser reported a 375x844 document
  viewport after its own reserved chrome.
- Role/state: signed-in consumer with two deterministic DMV project records.
- Horizontal overflow: 0 pixels.
- The first viewport retained the compact app bar, all six numbered service
  families, a visible portion of the live map, and the fixed four-task bottom
  navigation.

## Verified interactions

- Opening `Post project` changed the URL from `/?job_id=5` to `/jobs/new`,
  opened one native dialog, and focused the first family input.
- Escape closed the dialog, restored `/?job_id=5`, and returned focus to the
  originating `Post project` link.
- Selecting the Washington marker updated the URL to `/?job_id=4` and marked
  the matching result row with `aria-current="true"`.
- ArrowUp from that result selected and focused project 5, updated the matching
  result row, and serialized `job_id=5` back into the URL.
- The map status region announced the selected project and result changes.
- Zoom in, zoom out, popup close, Safety, Privacy, and Terms controls measured
  at a minimum height of 44 pixels after the touch-target correction.
- The repeated visual comparison confirmed that the open popup no longer
  overlaps the zoom rail or `Search this area`; the latter is hidden only while
  a popup is open.

## Supporting automation

- `tests.test_workdoe.WorkdoeFlowTests.test_map_script_announces_results_and_active_rows`
  locks map/list state, URL serialization, keyboard navigation, and status
  announcements.
- `tests.test_workdoe.WorkdoeFlowTests.test_map_and_policy_controls_use_accessible_touch_targets`
  locks the 44-pixel map and policy-link targets.
- The full suite passed 220 tests in 80.016 seconds after these corrections.

## Contractor milestone follow-up

- Requested viewport: 390x844. The browser reported a 375-pixel document width
  with zero horizontal overflow.
- The contractor dashboard kept the compact app bar, primary work-queue
  metrics, completion milestone, profile summary, and bottom navigation in a
  coherent scan order.
- The public contractor profile was checked at 820x1180. Its milestone band
  remained inside the existing profile panel and did not change the restrained
  green/gray design system.
- The browser console reported no warnings or errors on the checked contractor
  pages.
- The final local suite passed 223 tests in 77.296 seconds. Flask/Worker parity
  tests lock the deterministic reputation projection, received-order bid
  comparison, credential-filter counts, and privacy redactions.

## Message-state follow-up

- Message listings expose a compact unread total and thread-level unread cue
  without publishing message text outside the participant-authorized view.
- Read progress is tracked per participant by immutable message ID, preserving
  deterministic ordering when multiple messages share a timestamp.
- At 390x844, all three message metrics remained in one row, participant names
  stayed on their own line, and the page had zero horizontal overflow. Opening
  one unread thread changed the aggregate unread count from 3 to 1 while the
  other thread retained its unread cue.
- At 1280x720, the three metrics and both project rows remained balanced with
  zero horizontal overflow. The checked message views produced no browser
  console warnings or errors.
- Automated local and Worker-contract coverage verifies that sending, listing,
  reading, same-second ordering, and `HEAD` request behavior preserve the
  expected unread state.

## Live gates not replaced by this check

- A real screen-reader pass with VoiceOver, NVDA, or an equivalent remains
  required; semantic DOM inspection is not assistive-technology evidence.
- The selected in-app browser does not expose page Core Web Vitals timing.
  Mobile LCP, CLS, and INP must be measured against the deployed release under
  the approved network/device profile.
- Production Clerk email-code delivery, private media, queue/email, rate-limit,
  and rollback checks remain governed by the release-status record.

Outcome: local mobile interaction acceptance passed. Unrestricted public
registration and production deployment remain blocked by the recorded live and
operator gates.
