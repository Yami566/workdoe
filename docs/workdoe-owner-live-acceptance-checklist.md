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

- [ ] Confirm `admin@workdoe.com` is a monitored inbox with the published 1 to
  5 business-day response target for ordinary requests.
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

- [ ] Consumer: open `https://workdoe.com/create-account`, select Consumer,
  enter a non-identifying public label, request an email code, enter it, and
  confirm the consumer dashboard loads.
- [ ] Consumer: refresh a protected page and verify the existing signed-in
  session returns to the same workspace without showing a password flow.
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

- [ ] On the reviewed release commit, rerun the strict production smoke check
  and record the deployed SHA and timestamp.
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

## Decision

Keep the beta owner-supervised until every applicable item is checked and the
recorded evidence is reviewed. A passing automated test suite, security scan,
or Cloudflare smoke check does not replace these owner, legal, or operational
decisions.
