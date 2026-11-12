# Workdoe Owner Live Acceptance Checklist

Status: **required before representing Workdoe as an unrestricted public
commercial launch**.

This checklist is for the owner of the controlled DMV beta. It separates
technical smoke evidence from the live workflow, data-operations, and legal
decisions that automated checks cannot prove. Public photo uploads are disabled
for this beta. Use controlled test content only. Never enter a street address,
phone number, email address, legal name, or other personal details in a public
project, contractor profile, bid, or message.

## Before inviting public users

- [x] Owner decision on 2026-10-30: retained contractor photos require sign-in.
  New uploads remain disabled. See `release-evidence/2026-10-30-retained-photo-auth.md`.
- [x] Separately approved `245b004` deployed on 2026-10-30. Anonymous photo
  GET/HEAD return no-store 401; all bindings match, R2 direct publication is
  disabled and all 14 public smoke gates pass. This is scoped technical
  acceptance, not the still-open owner account/media journey.
- [x] Owner confirmed monitoring `admin@workdoe.com` with a 1 to 5 business-day
  response target for ordinary requests.
- [ ] Verify reliable inbox receipt and triage; the reported routing test
  landed in spam.
- [ ] Define an urgent safety and security escalation path that does not rely
  only on that ordinary-response inbox.
- [ ] Approve retention and deletion periods for accounts, projects, messages,
  media, reports, audit records, and backups.
- [ ] Approve the account export and deletion-request identity-verification
  process and request log.
- [ ] Obtain counsel approval for the Terms, Privacy, Safety, service-advisory,
  contractor-classification, and dispute language, including the approved
  public legal or mailing-address format for Moose Bay and Company LLC.
- [ ] Confirm public photo controls remain unavailable for this beta. A future
  media release requires an owner-approved storage/sanitization decision,
  documented cost controls, usage alerts, and a separate valid/invalid/oversize
  acceptance run. Application limits cannot impose an absolute Cloudflare
  billing ceiling.

## Owner-controlled account acceptance

Use two different owner-controlled inboxes: one consumer account and one
contractor account. Enter every email code yourself. Do not share codes in chat,
documentation, tickets, or source control.

Use **Sign in** for the existing owner test accounts. Confirm the expected role
at `/account` in each separate browser profile before testing a project. If a
known account is offered new onboarding or shows the wrong role, stop and
report it rather than creating a duplicate or changing its role. Test fresh
registration separately only with approved new test identities.

Checked items below are scoped to their cited release and observation. Later
authentication changes still require fresh OTP and cross-device acceptance.
Record the exact serving Worker/version, browser and device, last successful
step, and whether the run was staging or production. An earlier owner-run
two-account test is not acceptance of a different release.

### Current Release And Pending Save

The reviewed production source is now `f4b9488`, Worker version
`d2e4928c-8620-4d09-b553-beb1b5374f81`. Its
[deployment evidence](workdoe-public-launch-gates.md#internal-records)
records mandatory public smoke and independent 100-percent traffic readback.
It changes project-edit transactions and verification retry only, not auth.
The owner was asked to retry labeling project 1 from a fresh consumer tab
while keeping the original unsaved form open. That signed-in test is pending;
do not mark it passed from automated public smoke.

A separate [local date correction](workdoe-public-launch-gates.md#internal-records)
addresses editing other details after an unchanged requested date has elapsed.
It is not in the serving release and is not a confirmed cause of this failure.
Record any visible date-related error without changing the requested date just
to bypass it, and do not submit duplicate projects or bids while investigating.

### Prior Auth Acceptance: a195fe6

The prior reviewed production source was `a195fe6`, Worker version
`1caee132-9ee4-4dca-a666-30f8535213d2`. The
[deployment receipt](workdoe-public-launch-gates.md#internal-records)
records the scope and source of each result below. These checks do not
cover fresh registration or approve the draft policies.

- [x] Existing consumer: fresh email-code sign-in in a requested private
  window, dashboard refresh, and sign-out with the protected dashboard
  requiring sign-in again. Owner reported all three passed on November 11.
- [ ] Existing consumer: resume an existing unsent draft. This was optional
  in the prompt but was not included in the owner's result; do not assume
  there was a draft or that recovery passed.
- [x] Existing contractor: fresh email-code sign-in, confirm Contractor at
  `/account`, refresh the dashboard, and verify access is denied after
  sign-out. Owner reported the role and all three steps passed on November 11.
- [ ] Existing test project: save the TEST ONLY label and test-only description
  on project 1. The owner confirmed it is their test but saving failed.
  Obtain the visible error and resolve this acceptance failure before another
  bid, reopening, or duplicate test post. Keep the unsaved form open.
- [ ] Record browser/device details and complete physical cross-device
  acceptance. The consumer result did not identify the browser or device.

### Registration And Wider Acceptance

- [ ] Consumer: open `https://workdoe.com/create-account`, select Consumer,
  enter a non-identifying public label, request an email code, enter it, and
  confirm the consumer dashboard loads.
- [x] Consumer: refresh a protected page and verify the existing signed-in
  session returns to the same workspace without showing a password flow.
  Observed on `b93f80e` on 2026-10-28; see
  [the live dialog evidence](workdoe-public-launch-gates.md#internal-records).
  Existing-session recovery through Sign in was also observed on `4315e09`
  on 2026-10-30; see the
  [entry audit](workdoe-public-launch-gates.md#internal-records). This does not check
  either fresh-email-code item or second-device acceptance below.
  Recovery and unsent modal opening/closing were repeated after the approved
  `b09231f` deployment; see the
  [live focus record](workdoe-public-launch-gates.md#internal-records).
- [ ] Consumer: in a second browser profile or device, sign in to the same
  existing account with a newly requested email code. Confirm the existing
  Workdoe account and Consumer role reopen without a duplicate profile or a
  second onboarding flow. A session is intentionally browser-specific; a new
  device must use a fresh email code.
- [ ] Contractor: use a separate browser profile or device, open
  `https://workdoe.com/create-account?intent=find-work`, select Contractor,
  complete email-code sign-in, and confirm the lead board loads.
- [ ] Contractor: verify the profile only requests business-advertisement
  information and makes no street-address or contact-detail field public.
- [ ] On the reviewed hosted release, use **Account data requests** from
  Account & security and from signed-out Sign in. Confirm it goes to the
  existing Privacy contact section, including when the provider UI is
  unavailable. Do not send email or submit a deletion during this UI check.
- [ ] Verify the email-code-only requirement for existing accounts, not just
  the instance's advertised methods. [Clerk documents that disabling Password
  does not affect existing passwords](https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options#password).
  Review the per-account [password-enabled flag](https://clerk.com/docs/reference/backend/types/backend-user)
  for the approved cohort and record only the aggregate outcome. Do not
  collect, test, remove, or share any real passwords in this review.

## Controlled two-role marketplace journey

Perform this only after both account sign-ins work. This creates live test data;
use a clearly labeled, non-emergency project and remove or close it according to
the approved retention policy afterwards.

- [ ] Consumer posts one city/ZIP-only project. Confirm no exact address is
  requested or shown on the public map, job detail, or public jobs API.
- [ ] Confirm project and contractor-profile photo controls state that photos
  are unavailable during this beta. Do not use external image hosts or add
  private project material to a workaround URL.
- [ ] Contractor finds the project through the list and map, submits one mini
  bid without contact details, and confirms a duplicate bid is prevented.
- [ ] Consumer approves that bid; contractor and consumer exchange one
  test-only message; both mark the work complete.
- [ ] Consumer and contractor histories show project/work labels without an
  exact address.
- [ ] Use the report and moderation paths with test content; confirm an admin
  can review the action and audit record without exposing the content publicly.

## Release and public-view checks

- [x] Exact reviewed `7a7bd0e` deployed on 2026-10-30; all 14 strict production
  smoke checks pass. See `release-evidence/2026-10-30-reviewed-7a7bd0e-deployment.md`.
  Repeated successfully for the separately approved privacy release `245b004`;
  see `release-evidence/2026-10-30-retained-photo-auth.md`.
  Repeated successfully for separately approved discovery release `9ece619`;
  see `release-evidence/2026-10-30-reviewed-9ece619-deployment.md`. Its scoped
  public browser checks are not full owner workflow or accessibility acceptance.
  Repeated successfully for separately approved focus/history release `4315e09`;
  see `release-evidence/2026-10-30-reviewed-4315e09-deployment.md`. All 316
  isolated tests, native marketplace/security/build checks and all 14 public
  smoke gates pass; live family/search focus was checked. No fresh account,
  consent, posting, messaging or completion journey was performed in this release.
- [ ] Confirm the public map and API label every demonstration record as sample
  content and do not expose its fixed fixture date as a live requested date.
- [ ] Check `http://workdoe.com` and `http://www.workdoe.com` redirect to HTTPS,
  and that `https://workdoe.com` and `https://www.workdoe.com` resolve as
  intended.
- [ ] Inspect the logged-out public surface at 390x844, 820x1180, and 1280x720.
  Confirm no clipped controls, misleading live-project claims, or accidental
  personal data appear.
- [ ] Complete keyboard-only checks for map controls, native dialogs, sign-in,
  the six-step project composer, and bottom navigation. Check reduced-motion
  behavior and screen-reader labels before expanding the cohort.

## Street-Free DMV Map Acceptance

The owner selected the [same-origin DMV area map](workdoe-public-launch-gates.md#internal-records)
for the pilot. Run these checks against the exact separately approved hosted
candidate. This selection does not change the currently serving map.

- [ ] Release operator: verify area mode on the hosted candidate, including
  the versioned county file's bytes, headers and source credit. Check anonymous
  browse, direct sign-in and contractor leads. Confirm no request goes to an
  external tile provider when opening, panning or zooming the map. The
  list-only fallback is not evidence that the map passed.
- [ ] Release operator: on hosted iPhone/iPad Safari, verify the public
  boundary request has no referrer and check cookie presence without recording
  cookie values. Windows WebKit sent a same-origin fixture cookie despite the
  omission option; do not assume the physical browser behaves the same.
- [ ] On iPhone and iPad Safari, open the Map tab in portrait and landscape.
  Expect county boundaries, place labels and approximate pins, not streets or
  directions. Open a project from the map, return to Projects, then return to
  the map. Confirm the same selection is visible and controls stay reachable
  with Safari zoom and VoiceOver.
- [ ] At the narrowest Safari zoom setting used in the review, confirm
  **Map area**, **DMV view**, and **Search this area** stay outside the pins.
  Tap a pin near the toolbar and confirm it opens its project, not a map
  command. Use VoiceOver or an external keyboard to activate an area search:
  it should not shift the map canvas when it appears, and successful search
  should return focus to the map when the action disappears.
- [ ] On the public board, pan or zoom and choose **Search this area**.
  Check that the matching projects with pins appear in both views. Refresh
  the filtered view, then choose **DMV view** to clear the area constraint.
  Pan toward the edge and zoom out; the map should stay in the DMV overview.
  Rotating or switching tabs alone should not prompt a new area search.
- [ ] Release operator: in an isolated browser, block only the boundary file.
  Verify the map reports the failure and project search and opening a result
  still work in the list. Do not disable production assets or settings.
- [ ] Release operator: intercept one project search in an isolated browser
  and return a synthetic failure. Before submitting the ZIP, confirm the
  listings and share URL stay unchanged. On Projects, verify the previous results
  warning and Retry are visible, focus stays on the action, and the results
  status is exposed when the Map panel is hidden. Restore the response and
  verify retry clears the warning and updates the results and URL. Check with
  VoiceOver during the device review without changing the live API.
- [ ] Submit a ZIP and change Sort, then follow a work family. Confirm the
  new family keeps the confirmed ZIP and sort but clears the prior task.
  From a filtered contractor lead sign-in link, verify a GET fallback and
  All work keep the same-domain leads destination and clear the old family.
  Do not send a code for this navigation-only check.

Record only the serving version, device and OS, step, and outcome. Do not
include session URLs, request captures, or private project details.

## Decision

Keep the beta owner-supervised until every applicable item is checked and the
recorded evidence is reviewed. A passing automated test suite, security scan,
or Cloudflare smoke check does not replace these owner, legal, or operational
decisions.
