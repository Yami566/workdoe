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
- The shared consumer and contractor navigation now carries the unread total on
  every signed-in page without carrying message text. At 390x844 the badge
  remained attached to the Messages icon inside the existing bottom navigation;
  at 1280x720 it remained inline with the desktop Messages link. Both states had
  zero horizontal overflow and exposed the exact count through the link's
  accessible name while capping only the visible badge at `99+`.
- Opening the unread thread removed the global badge in the same rendered
  response. The final automated suite passed 223 tests in 79.210 seconds.

## Contractor map-first follow-up

- The previous contractor lead board was captured at 390x844 before the change;
  metrics, family cards, and filters filled the first viewport while the map and
  project rows remained below it.
- The accepted 390x844 state opens on a full-height map with Projects, Map, and
  Details tabs plus the existing bottom task navigation. The document width
  matched the viewport with no horizontal overflow.
- The Projects panel preserves family/task filters, saved-view controls,
  contractor fit, bid state, bid capacity, photo count, brief readiness, and a
  direct row action without stacking that content above the map.
- Selecting a project changed the URL to `/leads?job_id=4`, selected Details,
  and displayed the expected project title and `View and send bid` action. The
  structured ZIP and client email were absent from the rendered workspace.
- Arrow Right moved tab focus and selection from Projects to Map. The tablist
  exposes explicit panel relationships and roving `tabindex`; project rows keep
  Arrow Up/Down/Home/End navigation.
- At 1280x720, filters/results, map, and selected details render together. At
  820x1180, the map remains full height with Search this area visible and no
  horizontal overflow.
- Before/after and accepted responsive evidence is stored in
  `docs/ux-audit/2026-08-23-current-journeys/`. The final automated suite passed
  225 tests in 83.321 seconds.

## First-viewport workflow follow-up

- Public Explore at 1280x720 keeps all six service families in one compact row
  and begins the map at 350 pixels. At 390x844, the families become one
  horizontal task rail and the map begins at 495 pixels. Both pages report zero
  horizontal document overflow.
- The mobile contractor dashboard presents the response queue before milestone
  and profile detail; its first bid begins at 602 pixels. The mobile consumer
  dashboard shows only Open projects and Pending bids summary cards before its
  status tabs; its first project begins at 553 pixels.
- The message thread is a bounded workspace at 390x844 and 1280x720. Its message
  list scrolls independently while the send form remains visible; no custom
  JavaScript or new dependency was added for this behavior.
- Before/after comparisons and accepted captures are `14` through `19` in
  `docs/ux-audit/2026-08-23-current-journeys/`. The repeated full suite passed
  225 tests in 89.840 seconds.

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
