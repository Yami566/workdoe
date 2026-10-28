# Workdoe Beta Retention And Incident Decision Proposal

Status: **proposal only; not approved, effective, or a public policy**.

Prepared for Moose Bay and Company LLC's controlled Workdoe beta on
2026-10-27. This document turns the currently open retention and urgent
incident questions into a decision-ready operating proposal. It is not legal
advice and does not establish a regulatory deadline, authorize deletion, or
replace counsel's review of the public Privacy Policy, Terms of Use, and
Safety page.

## Why This Exists

Workdoe is deliberately designed to minimize marketplace data: no structured
street address, phone, payment card, browser geolocation, or public contact
detail is collected during the beta. Accounts still have email identity
through Clerk, and Workdoe stores marketplace records, reports, and audit
metadata. A written schedule is needed before unrestricted public sign-up.

This proposal follows three practical principles:

1. Keep only what is needed to operate the beta, answer a legitimate request,
   or preserve a documented security or legal exception.
2. Remove access immediately when an account is suspended or a deletion
   request is verified; do not wait for a background deletion job to make
   content private.
3. Preserve evidence during a credible security incident or legal hold, then
   delete it through a recorded, reviewed operation once the exception ends.

The Federal Trade Commission recommends collecting and retaining only what a
business needs and planning how to secure operations and preserve evidence
during an incident. See [Protecting Personal Information: A Guide for
Business](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business)
and [Data Breach Response: A Guide for
Business](https://www.ftc.gov/business-guidance/resources/data-breach-response-guide-business).
Virginia's Attorney General describes access, correction, deletion, and copy
requests under the Virginia Consumer Data Protection Act, subject to its scope
and exceptions. Counsel must determine whether and how those rules apply to
Workdoe. See [the Attorney General's VCDPA
summary](https://www.oag.state.va.us/consumer-protection/files/tips-and-info/Virginia-Consumer-Data-Protection-Act-Summary-2-2-23.pdf).

## Proposed Retention Schedule

The periods below are recommended operational defaults, not legal conclusions.
They begin only after written owner and counsel approval, an implementation
plan, a deletion drill, and a public-policy update where needed.

| Record class | Proposed period | Proposed action | Exception |
| --- | --- | --- | --- |
| Unverified project draft | 24 hours from creation | Delete draft and normalized scope answers | Active investigation or legal hold |
| Expired native development email-code records | 24 hours after expiry or use | Delete code row; retain no code value | Active security investigation |
| Idempotency and transient automation metadata | 30 days after completion | Delete hashed request key and generic event metadata | Active incident, fraud review, or legal hold |
| Closed or deleted account profile | 30 days after a verified deletion request completes | Delete or irreversibly de-identify profile fields and identity link where permissible | Open project, thread, safety report, fraud review, payment/legal obligation, or legal hold |
| Closed project, bids, approved-match thread, and completion feedback | 180 days after project closure or verified account deletion, whichever is later | Delete or irreversibly de-identify the marketplace record set as one scoped operation | Open safety report, dispute preservation, fraud review, or legal hold |
| Safety reports, moderation actions, and security audit records | 365 days after resolution | Delete the minimum record needed for audit history | Credible threat, repeat-abuse review, legal hold, or counsel-directed preservation |
| Legacy, demonstration, or future private media | 7 days after the related project/report is deleted or resolved | Delete R2 object and its metadata together, then verify no authorized media route remains | Legal hold or active abuse investigation |
| Worker logs and platform telemetry | Platform-configured minimum necessary window | Restrict access; review for incident evidence; do not export routinely | Active incident or legal hold |

The product currently enforces only the 24-hour draft expiry, short-lived
native development code expiry, and immediate discovery/access removal when an
account is suspended. New public media uploads are disabled. Do not represent
the proposed durations above as current behavior until the deletion jobs,
operator procedure, and evidence are implemented and verified.

## Request Handling Proposal

1. Route ordinary access, correction, deletion, and safety requests to
   `admin@workdoe.com`; the owner targets a response within 1 to 5 business
   days.
2. Before disclosing, exporting, or deleting data, verify the requester using
   an owner-approved method. The recommended minimum is a fresh Workdoe/Clerk
   email-code session for the affected account plus confirmation through that
   account's verified primary email. Email appearance alone is not sufficient.
3. Log only the request ID, received date, verified account ID, request type,
   decision, exception category, and completion date. Do not copy email codes,
   project narratives, addresses, messages, or media into the request log.
4. For a denial or delay, give the requester a plain-language reason and a way
   to seek review from the operator. Counsel must approve the final wording and
   any timetable.
5. For an approved deletion, immediately make the account inactive and remove
   its unmatched marketplace content from discovery. Perform the scoped record
   deletion after the approved grace period and record only the resulting IDs,
   timestamps, and exception basis.

## Urgent Incident Proposal

The ordinary inbox is not an incident-response channel. Before unrestricted
registration, the owner must name an incident commander, a backup, and an
out-of-band urgent contact method that is monitored outside the 1-to-5-business
day support target. The published site should continue to direct immediate
danger to emergency services, not to Workdoe.

For a suspected exposure, account takeover, destructive write, or credible
imminent-harm report:

1. Contain access first: pause relevant writes or invitations, hide content,
   suspend the affected account, or roll back a Worker release as evidence
   requires.
2. Preserve redacted evidence and identify the likely scope. Do not delete
   forensic evidence or paste sensitive content into chat, tickets, or email.
3. Assign technical, communications, and legal owners. Counsel determines any
   notice obligations and timing.
4. Verify containment with authorization checks and the strict production
   smoke test before restoring service.
5. Record the decision, evidence index, actions, next update time, and
   closure review in the private incident record.

Cloudflare D1 Time Travel availability depends on the account plan and storage
backend. Current Cloudflare documentation describes a seven-day recovery window
on Workers Free and thirty days on Workers Paid; a restore overwrites the
database in place. Confirm the actual database plan and record a recovery
bookmark before destructive recovery or retention work. See [D1 Time Travel
and backups](https://developers.cloudflare.com/d1/reference/time-travel/) and
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/).

## Approval Checklist

Before making this effective, Moose Bay and Company LLC should record all of
the following outside source control:

- Counsel's approval or revisions to the public policy and service-safety
  language.
- The named incident commander, backup, and urgent contact method.
- The approved requester identity-verification method and request-log owner.
- The approved record-class periods, exceptions, and legal-hold owner.
- The Cloudflare D1 plan/storage-backend recovery window and backup decision.
- A completed controlled deletion/export drill and incident containment drill.
- The date, approver, version, and required re-acceptance/change-notice rule.

Until every item is recorded, this remains a controlled-beta operating
proposal. It must not be presented to users as a guaranteed deletion schedule
or a substitute for legal advice.
