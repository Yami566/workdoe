# Workdoe Operations Runbook

Status: Draft for the controlled beta. The isolated local D1 export/import drill
is complete; no production recovery, rotation, deletion/export, or incident
drill is recorded as complete.

This runbook covers Workdoe's Cloudflare-hosted service and Clerk identity
provider. It is an operating procedure, not evidence that a drill occurred.
Production changes remain manual and must use the guarded release path.

## Required owners and contacts

The following decisions must be filled before unrestricted public registration
or public beta invitations are opened.

| Responsibility | Named owner | Monitored contact | Response target |
| --- | --- | --- | --- |
| Incident commander | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED |
| Cloudflare/release operator | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED |
| Clerk/auth operator | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED |
| Privacy and deletion requests | Owner-designated operator | `admin@workdoe.com` | 1-5 business days for ordinary requests |
| Safety and abuse reports | Owner-designated operator | `admin@workdoe.com` | 1-5 business days for ordinary requests; urgent path still required |
| Legal notification decision | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED | OWNER DECISION REQUIRED |

Do not publish an inbox until a person owns and monitors it. Do not put secrets,
email codes, session tokens, exact addresses, or private message bodies in an
incident ticket or chat channel.

## Operator alert routing

The Worker queues a generic alert for every new moderation report. The alert
goes to `WORKDOE_ADMIN_EMAIL` (`admin@workdoe.com` in the reviewed release),
links only to the private `/admin` console, and intentionally omits report
text, reporter identity, project details, message content, and media.

Before enabling this alert in production, configure Cloudflare Email Routing to
forward `admin@workdoe.com` to the owner-controlled `moosebay@gmail.com`
destination. Cloudflare will require the destination owner to verify that
forwarding address. Keep `admin@workdoe.com` as the public contact so the
application configuration does not contain a personal mailbox. Test one
controlled report after the verification: confirm that the alert arrives, its
link requires an administrator session, and no report content appears in the
email. This alert is a notification, not a substitute for the P0/P1 incident
response procedure or emergency services.

## Service inventory

| Service | Production identifier | Data or function |
| --- | --- | --- |
| Cloudflare Worker | `workdoe` | Python application, API, auth enforcement, scheduled and queue handlers |
| D1 | `workdoe` / binding `DB` | Users, profiles, projects, bids, messages, reports, moderation, and audit records |
| Cloudflare Images | Not attached during beta | Future reviewed upload sanitization only; requires an owner-approved opt-in |
| R2 | `workdoe-media` / binding `MEDIA` | Private storage reserved for a future media launch; public uploads are disabled |
| Queues | `workdoe-email`, `workdoe-media-review` | Transactional email and media-review work |
| Email Service | binding `EMAIL` | Email Sending is enabled for `workdoe.com`; mail is restricted to `no-reply@workdoe.com`; Cloudflare currently labels sending a Workers Paid public-beta service |
| Clerk | Workdoe production instance | Open-access email-code identity and sessions; password sign-in is disabled |
| Turnstile | Workdoe production widget | Bot checks for protected writes |
| Workers Rate Limiting | binding `WRITE_RATE_LIMITER` | Per-user authenticated write protection |
| GitHub Actions | `Workdoe Cloudflare Release` | Manual guarded release workflow |

Production sets `WORKDOE_ENFORCE_SERVICE_ACTIVATION=false` for the advisory-only
beta. The release preflight rejects accidental service-zone gating so all 53
curated services remain available, subject to their policy acknowledgements.

Public project and portfolio photo uploads are deliberately disabled for this
beta. This avoids raw-image storage and does not attach Cloudflare Images or
its paid plan to the Worker. A future photo launch requires all of the
following:

1. Approve a sanitizer/provider decision and its retention, cost, privacy, and
   abuse controls. For Cloudflare Images, enable Images Paid on the account
   that owns the `workdoe` Worker and add the `IMAGES` binding in a reviewed
   release.
2. Upload one controlled valid image and verify the R2 object is WebP, no more
   than 1600 pixels per side and below 1.5 MB, private, and readable only
   through the expected permission-checked route.
3. Submit one invalid image with a misleading extension and confirm Workdoe
   rejects it without creating an R2 object, D1 photo row, or completed
   idempotency record.
4. Record the test date, operator, object/row IDs, expected authorization
   outcomes, and cleanup. Do not retain the raw test upload or expose its key.

## Service-zone review records

Workdoe retains service-zone review records as an internal planning and future
rollout control. Migration `0011_service_zone_activations.sql` seeds candidate
records; those records do not open, close, rank, or otherwise limit a service
during the advisory-only beta.

For a future gated rollout, an activation is live only when all of these
conditions hold:

1. The status is `active`, and the canonical service and zone remain enabled.
2. Allowed scope, excluded scope, and the operator requirements summary are
   present.
3. Approval and review timestamps are present and the record has not expired.
4. The live count of active contractors selecting both that service and that
   zone meets `minimum_eligible_contractors`.
5. The operator has separately approved a future gated-rollout configuration.

Before changing a candidate to active, the operator must attach a private
evidence record containing the service and zone, source links and retrieval
dates, permitted and excluded work, licensing/insurance/safety analysis,
minimum supply rationale, reviewer, approver, review date, and expiry date.
Legal interpretation and insurance adequacy require qualified human review;
neither free text nor an embedding may approve a market.

Future gated-rollout procedure:

1. Run strict readiness and record a D1 Time Travel bookmark/export.
2. Confirm the exact canonical slugs with a read-only query against
   `service_zone_activations`; confirm the admin console shows the same row.
3. Have the reviewer and release operator approve the evidence record. The
   operator then performs one scoped, reviewed D1 update for that composite
   key, supplying the final scope text, approver ID, review/approval timestamps,
   expiry, and minimum contractor count. Do not use a bulk update.
4. Re-read that exact row and its live eligible-contractor count. A row may say
   `active` while still remaining closed because the supply threshold is not
   met; that is expected.
5. Run preflight, the controlled two-role smoke test, and public job/API checks.
   Record the result without copying private user or project data.

If the future gate is explicitly enabled, setting the exact row to `paused`
stops new publication and bidding for that service-zone pair; record the reason.
During the advisory-only beta, a paused record has no marketplace effect. Use
the existing moderation and incident controls to hide unsafe content or suspend
an account, and retain approved private threads so participants are not
stranded. Use `retired` only when the market should not be reopened from the
same evidence.

The initial candidate set is interior house cleaning, deep cleaning, move
cleaning, packing/unpacking, in-home heavy lifting, and freestanding furniture
assembly in DC, Arlington County, and Alexandria. The exclusions prohibit
vehicle transport, disposal, wall attachment, exterior access, utility
connection, structural work, and alteration of real property. These are
product controls, not legal conclusions.

## Contractor Credential Review

1. Open the claim in the admin credential-review panel. Confirm the contractor,
   credential type, jurisdiction, claimed identifier, and claimed name.
2. Open an official regulator, registry, or insurer-controlled public HTTPS
   source in a separate tab. Do not use a search-result snippet, contractor
   screenshot, social profile, or user-editable directory as the checked source.
3. Compare the source record to the claim and the work/jurisdiction it actually
   covers. Workdoe does not infer project-specific legal eligibility.
4. Record the canonical public HTTPS source, expiration date when published,
   and a concise private note. Choose `Source checked` only when the displayed
   record supports that atomic claim. Use `Needs info`, `Not confirmed`, or
   `Expired` otherwise.
5. Re-open the public contractor profile and confirm that only the credential
   type, jurisdiction, checked date, optional expiry, and public source appear.
   The identifier, claimed name, and private review note must not appear in the
   public payload.
6. Confirm both a `moderation_actions` record and an
   `admin-credential-review` automation event. Never describe the result as a
   blanket Workdoe verification, endorsement, guarantee, background check, or
   proof of insurance coverage.
7. Before expiry or on a complaint, repeat the source check. Mark the record
   expired or not confirmed immediately when it is no longer current, then use
   the incident/moderation path if misrepresentation may have occurred.

Cloudflare Workers Logs and traces must remain enabled. Review errors,
uncaught exceptions, authentication failures, queue retries, and unexpected 4xx
or 5xx changes without logging sensitive request bodies.
Include HTTP `429` volume and `write-rate-limit-check-failed` events in that
review. A missing or failed `WRITE_RATE_LIMITER` binding is a production write
outage, not a reason to bypass the control.

## Severity and authority

| Severity | Examples | Initial authority | Target |
| --- | --- | --- | --- |
| P0 | Confirmed data exposure, active credential abuse, destructive data corruption, or broad account takeover | Incident commander may disable sign-in, writes, invitations, or the Worker | OWNER DECISION REQUIRED |
| P1 | Auth outage, sustained Worker outage, missing media at scale, credible imminent-harm report | Incident commander may suspend affected users/content and pause releases | OWNER DECISION REQUIRED |
| P2 | Partial feature failure, queue backlog, isolated unauthorized-content report | Service owner may contain the affected feature or account | OWNER DECISION REQUIRED |
| P3 | Routine support, cosmetic defect, non-urgent policy question | Product/support owner | OWNER DECISION REQUIRED |

The incident commander records who declared the incident, when it began, the
systems affected, containment actions, and the reason for each production
change. A destructive D1 restore, bulk R2 delete, or identity-wide revocation
requires two-person confirmation when two authorized operators are available.

## First response

### First 15 minutes

1. Open an incident record with timestamp, reporter, symptoms, severity, and a
   redacted evidence index.
2. Confirm impact from the public health check, strict production smoke, Workers
   Logs, D1/R2 status, Clerk status, and queue state. Do not make a speculative
   data change while diagnosing.
3. Stop the spread: pause invitations or writes, suspend an affected account,
   hide reported content, revoke a suspected credential, or roll back the
   Worker as the evidence requires.
4. Preserve relevant moderation and audit identifiers. Record log query times
   before their retention window passes.
5. Assign incident commander, technical operator, and communications owner.

### First 60 minutes

1. Establish the affected users, records, media objects, routes, credentials,
   and time range.
2. Decide whether recovery is a Worker rollback, credential rotation, D1
   recovery, R2 recovery, identity action, or a combination.
3. Validate containment with negative authorization checks and a strict smoke
   test. Keep public registration/invitations paused if identity or data scope
   remains uncertain.
4. Decide whether user, regulator, insurer, platform, or law-enforcement notice
   is required. The legal owner makes that decision; this runbook does not set a
   legal deadline.
5. Record the next update time and the conditions for restoring service.

## Containment guide

| Scenario | Immediate containment | Recovery evidence |
| --- | --- | --- |
| Cloudflare or GitHub token exposed | Create a new least-privilege token, verify it, replace the stored secret, then revoke the old token | Token verification, guarded dry run, release status, strict smoke |
| Worker secret exposed | Replace the secret through Cloudflare without printing it; treat related sessions/tokens as compromised | Required-secret evidence, preflight, auth negatives, strict smoke |
| Clerk key or session compromise | Pause invitations, revoke affected sessions/users in Clerk, rotate the coherent production key set, verify domain/proxy settings | Production-key check, invitation proof, real email-code sign-in |
| Account takeover | Suspend the Workdoe account, revoke Clerk sessions, hide risky content, preserve audit identifiers | Identity ownership verified, session revocation recorded, account reactivated by owner |
| Abusive or dangerous content | Hide the content first, suspend the user when necessary, preserve report/audit records | Moderator and reason recorded; appeal/escalation decision recorded |
| Worker release failure | Stop further releases and use the Cloudflare version rollback path approved by the release operator | Health, assets, jobs API, headers, auth proxy, and strict smoke pass |
| D1 corruption or destructive write | Pause writes, record a Time Travel bookmark/export, define the last-known-good point, obtain restore approval | Counts and invariants pass; two-user flow and moderation audit verified |
| R2 deletion or inaccessible media | Pause media deletion/uploads if continuing damage is possible; identify keys from D1 metadata | Authorized sample retrieval works and unauthorized retrieval still fails |
| Email or queue outage | Pause invitation promises if email codes cannot arrive; inspect queue retries and Email Service state | Real invitation/code delivery plus queue audit event |

## Credential rotation

Never place secret values in source control, command history, screenshots,
documentation, or release evidence. Wrangler secret commands can create a new
Worker version or deploy immediately, so rotations must be treated as releases.

1. Record the credential name, reason, scope, owner, and start time without its
   value.
2. Create the replacement with the narrowest permissions and resource scope.
3. Store it through Cloudflare Worker secrets or the GitHub `production`
   environment, as applicable.
4. For Clerk, rotate `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`,
   `CLERK_JWT_KEY`, and `CLERK_WEBHOOK_SECRET` as one production-instance
   change.
   Reconfirm Open access mode, the Workdoe custom sign-up URL, email-code
   sign-in, disabled password sign-in, and the `workdoe.com/__clerk` proxy.
5. For Turnstile, rotate the site/secret pair and verify allowed hostnames and
   server-side action checks.
6. For `WORKDOE_SECRET_KEY`, assume existing Workdoe-signed state may become
   invalid and test session, draft, CSRF, and protected-write behavior.
7. Verify the new credential before revoking the old one. Run secret-name
   evidence, preflight, Worker dry-run, guarded release, and strict smoke.
8. Revoke the old credential, verify again, and close the rotation record.

The production command list and secret names are maintained in `README.md` and
`cloudflare/wrangler.jsonc`. Operators should use secure interactive prompts,
not command-line secret values.

## Administrator account recovery

Ordinary moderation routes must never suspend or activate an administrator.
An admin-account change is a controlled recovery operation:

1. Confirm the affected identity through Clerk and the approved operator
   contact; treat an unexplained lockout as a possible security incident.
2. Require a second authorized operator to approve the exact Workdoe user ID
   and intended status change. Never identify the account by email alone.
3. Pause releases, record current account status and relevant audit events, and
   apply only the scoped D1 user-status change through an authenticated operator
   session or reviewed D1 command.
4. If compromise is suspected, revoke Clerk sessions and rotate affected
   credentials before restoring access.
5. Verify the administrator can sign in, ordinary roles still receive 403 from
   admin routes, and the recovery action is recorded in the private incident
   log. The owner and second approver remain OWNER DECISION REQUIRED.

## D1 backup and recovery

Cloudflare D1 Time Travel supplies point-in-time recovery for production D1.
The available recovery window depends on the active plan and must be checked at
incident time. A restore overwrites the database in place, so it is not a
diagnostic command.

### Before each production release

1. Run the strict readiness and migration plan without deploying.
2. Confirm the target database is `workdoe` and record D1 database information.
3. Record a current Time Travel bookmark and release identifier in the private
   release record. The guarded GitHub deployment captures this bookmark, the
   active Worker deployment, its highest-traffic version ID, and a ready-to-use
   rollback command before applying migrations.
4. Create a D1 SQL export in restricted temporary runner storage and transfer it
   to a private backup location. Prefer an automated D1-to-R2 Workflow once the
   backup bucket, retention period, and access owner are approved.
5. Validate that the export is non-empty and contains expected schema markers.
   Do not attach the export to a public issue or build artifact.

The GitHub recovery artifact intentionally contains only the Time Travel
bookmark, Worker deployment metadata, release SHA/timestamps, checksums, and
rollback command. It does not contain a D1 export or marketplace user data. A
full export remains blocked until the private backup bucket, access owner, and
retention period are approved.

### Recovery

1. Pause writes and record the current Time Travel bookmark so the restore can
   itself be reversed if required.
2. Identify the last-known-good bookmark from audit events, release records,
   and user reports. Record the affected table counts before changing data.
3. Obtain incident-commander approval and a second confirmation for an in-place
   production restore.
4. Restore to the approved bookmark through D1 Time Travel. Do not run an
   unreviewed `d1 execute` file against production.
5. Verify schema migrations, user/job/bid/thread/message/report counts, foreign
   key relationships, and recent moderation audit rows.
6. Run negative authorization tests, strict smoke, and one controlled two-role
   workflow before reopening writes.
7. Record recovery point, operator, approver, validation output, and any data
   interval that could not be recovered.

The safe drill is an export/import into a separate non-production D1 database.
Do not use production Time Travel merely to prove that it works.

## R2 media backup and recovery

R2 durability does not undo intentional or accidental deletion. Workdoe must
not assume a deleted object can be recovered from the primary
`workdoe-media` bucket.

1. Keep the primary media bucket private and use only permission-checked Worker
   routes.
2. Treat each D1 media row and its R2 object key as one recovery unit. Back up
   the object plus a manifest containing object key, checksum, size, related
   record ID, and backup time.
3. Create a separate private backup bucket only after the retention/deletion
   policy and access owner are approved. Restrict its token to that bucket.
4. Apply lifecycle rules and bucket locks only after privacy deletion and legal
   hold rules are settled. A lock that prevents deletion can conflict with an
   approved deletion request.
5. To recover, restore a sampled object to a non-public test key, verify its
   checksum and permission behavior, then copy it to the approved production
   key. Record every recovered key.
6. Never empty or delete an R2 bucket as a troubleshooting step. R2 object
   deletion is irreversible without a separate copy.
7. Review `media-upload-failed` events for `metadata_cleanup` or
   `object_cleanup` values beginning with `failed:`. Reconcile only the exact
   scoped key and row recorded by the event; never bulk-delete by prefix.

## User data export and deletion

No deletion request should be completed until Workdoe's identity, retention,
legal-hold, and moderation-record policies are approved. For a controlled test,
use a synthetic account and synthetic content.

1. Verify the requester's identity through the production Clerk account and a
   second operator check. Suspend sign-in if compromise is suspected.
2. Search by Workdoe user ID and Clerk subject, not email alone. Inventory the
   user row, role profile, projects, bids, threads, messages, reports, media
   metadata/R2 keys, automation events, and moderation actions.
3. Produce a restricted JSON export with a media manifest. Include private media
   only through an authenticated, expiring delivery path approved by the
   privacy owner.
4. Check for OWNER DECISION REQUIRED retention or legal-hold rules before any
   deletion. Record any records withheld and the policy basis.
5. Revoke sessions and block further writes. Delete authorized R2 objects and
   verify each key no longer resolves.
6. Perform the approved D1 deletion/anonymization transaction. Verify each
   dependent table explicitly; do not rely only on cascade behavior.
7. Delete or anonymize the Clerk identity according to the approved identity
   policy, then verify sign-in fails closed.
8. Preserve only the minimum approved deletion/audit receipt without retaining
   the deleted content. Record requester, scope, operator, approver, date, and
   verification result.

## Moderation escalation

1. Triage reports by credible imminent harm, suspected illegal content,
   harassment/fraud, privacy exposure, and ordinary marketplace disputes.
2. For imminent danger, display and use the approved emergency guidance;
   Workdoe must not represent itself as an emergency service.
3. Hide reported content while reviewing when continued visibility creates
   harm. Suspend the account when continued access creates material risk.
4. Preserve report, content ID, user ID, moderator, reason, timestamps, and
   action in the existing moderation/audit records. Avoid copying private
   message bodies into external tickets.
5. Escalate privacy, legal, child-safety, credible-threat, and law-enforcement
   matters to the named owner. Contacts and response targets remain OWNER
   DECISION REQUIRED.
6. Record restoration, continued removal, user notice, and appeal outcome. Admin
   message inspection remains read-only.

## Weekly marketplace quality review

During the controlled DMV pilot, review the prior seven days by service and
zone:

1. Open the admin `Service-zone pulse` and compare published projects,
   projects with bids, median time to first bid, approved matches,
   `workdoe-match` close outcomes, cancelled/no-fit outcomes, open project
   reports, one-sided completion signals, and verified completions. Keep every
   active service-zone cell visible even when it has no projects. Do not
   substitute a desired date for a scheduled appointment, an open report for a
   formal dispute, or a closed-project count for fulfilled work.
2. Review close-reason distributions for sudden changes in `plans-changed`,
   `no-qualified-bid`, `scope-changed`, and `duplicate`.
3. Review lead-quality reason distributions and sample the underlying project,
   bid, and private note. One signal is not proof and must not automatically
   penalize a consumer.
4. Compare the share of published projects reaching five or six transparent
   brief-readiness signals with bid and match outcomes by service and zone.
   Treat this as intake evidence, not a consumer score, and never use it for
   automatic moderation or marketplace ordering.
5. Route `suspicious` and `authorization-concern` signals to the existing
   moderation process when the project context supports review. Do not copy
   private notes into external tickets unless required by the approved incident
   procedure.
6. Record any taxonomy or intake change as an operator decision with before and
   after metrics. Do not train or enable a classifier from pilot notes without
   a separate privacy, bias, retention, and evaluation review.
7. Treat `Current supply` as the review-time count of active contractors whose
   saved capability and zone match the cell. It is not proof of how many were
   eligible before the first bid. A historical supply snapshot requires a
   separate schema, retention purpose, and privacy review before it can support
   causal or monetization claims.

## Drill record

No row may be marked complete without a date, operator, approver, evidence path,
and an observed result. Drill evidence must be redacted and kept outside public
artifacts when it contains account or infrastructure details.

### Controlled beta marketplace acceptance

Before changing the beta's operating status, run this journey with two
owner-controlled test accounts and synthetic content only. The owner enters each
email code personally. Do not put email addresses, codes, session identifiers,
exact addresses, or private-message bodies in the evidence record.

1. Sign in as a consumer with the one-time email code. Confirm the session
   reaches the consumer workspace and that a refresh retains the authenticated
   session without exposing the code in the URL or page source.
2. Post one project using a service-family and service selection, a city and ZIP
   only, and neutral test scope text. Confirm the form rejects an email address,
   phone number, or street address in its free-text fields. Upload one valid
   synthetic image.
3. Sign in as the contractor test account with its own email code. Confirm the
   map/list shows only an approximate location, the service filters return the
   project, and the contractor can open the authorized photo without learning a
   street address, contact detail, raw storage key, or source filename.
4. Submit a synthetic mini bid. From the consumer account, review and approve
   it; confirm that a private message thread opens only for those two matched
   accounts. Send a neutral test message and confirm the text guard rejects
   contact or street details.
5. Mark the test project complete, then confirm each account's history shows
   the appropriate project/work result without an exact address. Confirm a
   third, unmatched account cannot retrieve the project photo or message.
6. Record pass/fail for every assertion, a redacted timestamp, application
   release SHA, and the operator/approver in private operating evidence. A
   failure leaves the drill pending; it is not fixed by editing this document.

Run the media-specific valid, invalid, oversize, quota, rate-limit, and cleanup
checks separately under the media drill. Run an export/deletion test only after
the retention, legal-hold, and identity-verification rules are approved.

| Drill | Environment | Date | Operator/approver | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| D1 export and import into separate test D1 | Isolated local D1 | 2026-08-16 | Codex / N/A for local isolation | `docs/launch-readiness-2026-08-16/D1_LOCAL_RECOVERY_DRILL.md` | Pass locally; production recovery remains unproved |
| D1 recovery tabletop using bookmarks | Tabletop | Not run | Not assigned | None | Pending |
| R2 manifest, sampled backup, and restore | Non-production | Not run | Not assigned | None | Pending |
| Clerk production credential rotation | Production-safe rotation | Not run | Not assigned | None | Pending |
| Cloudflare/GitHub token rotation | Production-safe rotation | Not run | Not assigned | None | Pending |
| Two-account marketplace journey and authorization boundary | Production | Not run | Owner / Not assigned | Private redacted acceptance record | Pending |
| Valid, invalid, oversize, quota, rate-limit, and cleanup media checks | Production | Not run | Owner / Not assigned | Private redacted media acceptance record | Pending |
| Synthetic account export and deletion | Production or production-equivalent | Not run | Not assigned | None | Pending |
| Abuse report, hide, suspend, resolve, and appeal | Production-equivalent | Not run | Not assigned | None | Pending |
| Worker rollback and strict smoke | Production or production-equivalent | Not run | Not assigned | None | Pending |
| P0 incident tabletop and notification decision | Tabletop | Not run | Not assigned | None | Pending |

An unrestricted launch is blocked until owners and contacts are named, policy
placeholders are resolved, the drills above pass, and evidence is reviewed.

## Primary references

- [D1 Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/)
- [D1 import and export](https://developers.cloudflare.com/d1/best-practices/import-export-data/)
- [D1 backup to R2 Workflow example](https://developers.cloudflare.com/workflows/examples/backup-d1/)
- [Workers rollbacks](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/)
- [R2 durability](https://developers.cloudflare.com/r2/reference/durability/)
- [R2 object lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
- [R2 bucket locks](https://developers.cloudflare.com/r2/buckets/bucket-locks/)
- [R2 bucket deletion](https://developers.cloudflare.com/r2/buckets/delete-buckets/)
- [Workers Logs](https://developers.cloudflare.com/workers/observability/logs/workers-logs/)
- [Workers secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Cloudflare API tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Clerk access settings](https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options)
- [Clerk application invitations](https://clerk.com/docs/guides/development/custom-flows/authentication/application-invitations)
