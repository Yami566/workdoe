# Workdoe Product Requirements

Status: launch-candidate requirements baseline

Last reviewed: 2026-08-21

## Product statement

Workdoe is a local work exchange for DC, Maryland, and Virginia. It helps a
consumer describe a project and helps a contractor find, evaluate, and request
that work without exposing private contact or exact-location details before a
match is approved.

The launch experience is a marketplace, not a marketing site. A visitor should
immediately see sample or live projects in a searchable list and approximate
map, understand whether they are acting as a consumer or contractor, and enter
the relevant workflow through a same-domain email-code sign-in.

## Users and jobs to be done

### Consumer

- See that Workdoe serves the DMV area and understand the trust model.
- Create an account with an email code without leaving `workdoe.com`.
- Draft a project before account verification, then post it with title, curated
  category, coarse project setting, city/ZIP, short description, desired date,
  optional budget range, and optional private photos.
- Choose one of six numbered work families, then choose a canonical task from
  numbered family-scoped tiles. Each family presents six common tasks first
  and keeps the remaining canonical services behind a plainly labeled
  progressive-disclosure control; the native select remains the no-JavaScript
  fallback and stores the same deterministic service value.
- From the public marketplace, a selected work family must expose both valid
  next actions: browse the filtered open projects or begin a consumer project
  with that family already selected. The embedded composer opens at the task
  choice while direct links and no-JavaScript forms retain the normal six-step
  fallback.
- After a work family is selected, marketplace filters expose only that
  family's canonical tasks. Selecting a task filters both list and map by its
  stored service slug, and the posting action carries the same family and task
  into Step 3 of the project composer. Invalid or cross-family query values are
  ignored rather than producing an inconsistent selection.
- For the first researched service lanes, answer up to four optional,
  service-specific quote-readiness questions using controlled choices. The
  application stores the canonical answer codes and schema version separately
  from the narrative; it does not infer, embed, or rewrite the project.
- See a transparent `Brief n of 6` projection based only on canonical service,
  a substantive description, at least two controlled scope answers, project
  setting, desired timing, and either a budget signal or photo. It never uses
  identity, contact, exact-location, paid-placement, or contractor-fit fields
  and does not change ordering or eligibility.
- Close an owned project with a controlled outcome and optional private note;
  reopen it until either participant confirms completion, which clears the
  active close outcome while preserving its audit event.
- Reuse an owned closed project as a new six-step draft without carrying over
  the old desired date.
- Maintain a private household, small-business, property-manager, or community
  workspace and affirmatively choose whether pending-bid reminders may use
  email. New and pre-consent beta profiles default to the Workdoe inbox only;
  selecting email records consent, turning it off clears consent, and reminder
  emails link back to the same-domain preference control. Account and security
  messages are not controlled by this optional reminder setting.
- Save up to eight city/ZIP-level DMV project areas and use an owned saved area
  to prefill the location step of a new project without storing a street address.
- Save up to twelve private project templates by copying reusable service,
  scope, setting, and optional budget fields from an owned project. A template
  must not copy location, desired date, photos, bids, messages, close outcomes,
  or completion state, and it must reopen in the six-step composer for review.
- Review contractor mini bids and approve or reject them. Pending offers appear
  in received order in a shared comparison surface for price, timeline,
  availability, a current visible portfolio image when one exists,
  self-reported years/insurance, current source-checked credential signals, and
  mutually verified Workdoe project count. Each card has an explicit Choose
  contractor action, but the comparison has no recommendation, paid order,
  contact details, credential identifier, or composite score.
- See a four-bid cap and seven-day bidding deadline on every owned project;
  rejected bids continue to count toward the cap, and an expired non-full
  window may be extended seven days at a time.
- Message only contractors whose bid has been approved. Desktop thread pages
  keep up to 50 owner-visible approved-match conversations in a bounded rail so
  the participant can switch work contexts without returning to the inbox;
  phone and tablet views stay focused on one selected conversation. Every
  thread retains a canonical direct URL and server-rendered fallback.
- After closing a project, independently confirm completion for an approved
  match; the project becomes verified complete only after the contractor also
  confirms.
- After mutual completion, leave one structured review of the contractor for
  that match. Feedback covers communication, scope accuracy, timeliness, work
  outcome, whether the participants would work together again, and an optional
  capped narrative. It creates no star score, rank change, or paid advantage.
- From a mutually verified completed match, invite that same contractor to a
  new project for the same canonical service. The invitation is private and
  creates no bid, approval, conversation, ranking boost, or reserved slot.
- Report inappropriate jobs, profiles, or messages. Flask and Cloudflare
  participant threads expose the same rate-limited, Turnstile-protected message
  report control without exposing the message to unrelated users.

### Contractor

- Browse project summaries and approximate locations before creating an
  account.
- Create a contractor account and profile.
- Complete a seven-item storefront-readiness checklist covering business name,
  description, services, zones, experience, HTTPS website, and portfolio work.
- Select canonical service capabilities and practical DMV service zones on the
  profile instead of relying only on free text.
- Search and filter available work by one of the six canonical work families,
  an exact family-scoped task, search text, and DMV location. Public entry
  pages and the signed-in lead board use the same family and task slugs as the
  project composer.
- Save one owner-only lead view containing the current work family, exact task,
  search text, and deterministic sort order, then restore it explicitly from
  the lead board.
- Keep projects primary in the contractor Projects panel. Family, task, search,
  sort, saved-view, and alert controls live in one native disclosure that
  summarizes the active task, sort, and alert state. The disclosure is closed
  on an unfiltered board and open when a query filter is active, preserving a
  no-JavaScript path without making alert setup a prerequisite for seeing work.
- Explicitly opt that saved view into matching-project email. A new project may
  alert the contractor only when it also matches a selected canonical service
  and DMV zone; opting out clears the consent timestamp.
- Set a self-reported available, limited, or unavailable work status with an
  optional next-available date; public profiles receive only that coarse status
  and never the contractor's saved search or private calendar.
- See deterministic fit reasons when a project's service and/or area matches
  the saved profile; matching must remain inspectable and must not expose ZIP
  data in lead-board payloads.
- Review enough detail to submit a mini bid without receiving the client's
  direct contact information or exact address.
- Publish an optional business website to the profile owner, administrators,
  and consumers evaluating that contractor's bid; unrelated visitors cannot
  retrieve it and phone is not collected on the contractor profile.
- Submit a trade-license, business-registration, or insurance-certificate
  claim with a jurisdiction and record identifier. The claim stays private to
  the contractor and administrators until an administrator checks a public
  HTTPS source; the contractor cannot assign or remove a source-checked status.
- Submit scope, estimate, timeline, experience, questions, and availability.
- Save up to six owner-only proposal templates from the contractor's own mini
  bids. A template may copy scope, timeline, experience, questions, and
  availability, but never price, client identity, location, contact, media,
  ranking, or outcome fields. Applying it to another lead leaves price blank.
- See bid slots used, slots remaining, and the close time before submitting;
  no contractor can buy priority or submit after the cap or deadline.
- Track pending, approved, and rejected bids.
- After submitting a bid, record one updateable private lead-quality reason for
  operations without turning it into a public rating or automatic penalty.
- Message a client only after approval.
- After the consumer closes the project, independently confirm completion; the
  work becomes verified complete only after the consumer also confirms.
- After mutual completion, leave one structured review of the consumer for
  that match and respond once to feedback received. Either participant can
  report the review; narratives and reports stay out of automation payloads.
- See a private invited-back queue for prior mutually verified work, then pass
  or submit a fresh mini bid under the normal service gate, deadline, and
  four-bid cap.
- Receive one transactional invitation alert for that new project through the
  production email queue. The alert links to the same-domain project page and
  contains no prior address, contact, message, price, schedule, or media data.
- Report inappropriate jobs, profiles, or messages.

### Administrator

- Review users, jobs, photos, messages, and reports.
- Hide or restore eligible content and suspend or restore users.
- Review an append-only audit history of moderation and automation actions.
- Inspect message threads without impersonating a participant or replying.
- See published, bid, approved-match, one-sided completion, and verified
  completion counts without treating a closed lead as fulfilled work.
- Review the repeat-work funnel from invitation through fresh bid and verified
  completion, plus recent project-level invitation status, without receiving
  prior-project scope or contact fields in that operational view.
- Review contractor alert opt-ins and pending, queued, sent, and failed
  delivery counts plus recent project-level delivery state. The operational
  projection excludes client identity, ZIP, description, media, and bids.
- Review close-out and contractor lead-quality buckets plus recent private
  feedback without exposing those notes to other marketplace users.
- Review completion-gated participant feedback and feedback reports, hide or
  restore a review, resolve reports, and inspect aggregate counts without
  calculating a star score or changing marketplace order.
- Review contractor credential claims against a public HTTPS source, record a
  checked date, optional expiry, and private review note, and choose only an
  allow-listed status. Every review creates moderation and automation audit
  records.

## Launch scope

Quote-readiness question sets are currently implemented for house, deep, and
move cleaning; packing/unpacking; in-home lifting; freestanding furniture
assembly; lawn mowing; gardening; landscaping; local moving; pressure washing;
window cleaning; interior painting; and kitchen remodeling. A question set in
code is not permission to launch that service-zone pair: activation still
requires the reviewed legal, safety, evidence, supply, and operator gates below.

### Included

- Public DMV project map, list, filters, and project summaries.
- Clearly labeled demonstration data when there are no live public projects.
- Consumer and contractor role separation.
- One permanent consumer or contractor role per account for the beta.
- Same-domain Clerk email-code authentication.
- Same-domain account and security management using Clerk's maintained profile
  component; optional passkeys may be enabled only after production-domain validation.
- D1 marketplace and moderation records.
- Cloudflare Images decode/re-encode before private R2 storage: accepted PNG,
  JPEG, GIF, and WebP uploads become metadata-free, single-frame WebP output
  bounded to 2400 pixels per side before permission-checked delivery.
- Deterministic six-signal project brief readiness in the composer, consumer
  workspace, contractor lead board, and both project-detail views.
- Contractor-owned storefront profiles with deterministic readiness feedback,
  moderated work photos, and relationship-scoped HTTPS business links.
- A neutral contractor credential claim ledger. Public profiles show only
  current source-checked type and jurisdiction labels plus the checked date,
  expiry, and public source; identifiers and review notes stay out of the
  public payload.
- Contractor work preferences with a coarse self-reported public availability
  projection and an owner-only saved lead view; these preferences do not alter
  lead rank, create paid placement, or expose a private calendar.
- Server-side Turnstile checks for protected write operations.
- Durable 24-hour duplicate-submit protection for project creation, ordinary
  messages, moderation reports, and private media uploads. Browser requests use
  Web Crypto keys; SQLite/D1 retain only SHA-256 hashes, generic action/resource
  references, state, and timestamps. A completed retry returns the original
  resource and an in-flight retry returns `409` with `Retry-After`.
- Mini bids, approval/rejection, private matched messaging, and reporting.
- A deterministic four-bid, seven-day fair-opportunity window enforced in the
  database write as well as the user interface.
- Two-sided completion confirmation for approved matches, with truthful
  fulfillment history and operational metrics.
- One structured completed-work review per participant after mutual
  confirmation, with one recipient response, participant reporting,
  relationship-scoped contractor-profile display, and admin moderation.
- Structured project close outcomes and bidder lead-quality signals, with only
  a Workdoe-match close eligible for completion confirmation.
- Normalized contractor service capabilities and DMV coverage zones with
  legacy-profile inference during migration.
- Jurisdiction-specific service activation records that fail closed when the
  allowed scope, required evidence, verification status, minimum eligible
  supply, or escalation owner is missing or expired.
- An initial controlled lane limited to interior cleaning, move cleaning,
  packing/unpacking, in-home heavy lifting, and freestanding furniture assembly;
  exterior work, vehicle transport, disposal, wall attachment, real-property
  alteration, and licensed trades remain inactive until their service-zone gate
  is approved.
- Repeat-project prefilling from consumer project history.
- A privacy-safe project-setting choice for house, apartment/condo, business
  space, shared building area, outdoor area, or other; no property listing,
  ownership assertion, building name, unit number, or street address is inferred.
- Private consumer workspace profiles and reusable city/ZIP-level project areas.
- Owner-only reusable project templates copied from an owned project, with
  location, date, media, bid, message, and outcome fields excluded by schema.
- Owner-only contractor proposal templates copied from the contractor's own
  mini bid, with a six-template cap and no price, client, location, contact,
  media, ranking, or outcome columns. Reuse always requires a fresh price.
- Private repeat-provider invitations created only from an active contractor's
  mutually verified approved match. Invitations keep the same service and
  store no prior address, media, message, contact, or bid terms.
- Cloudflare Queues/Cron for supported email, reminder, media-review, and
  moderation jobs.
- Responsive desktop and mobile entry flows.
- Six-step consumer posting with family icons, numbered service tiles, and a
  server-rendered native-select fallback.

### Explicitly excluded from the first public beta

- Payments, escrow, subscriptions, lead credits, contracts, insurance coverage
  verification, background checks, public star ratings, review-driven ranking,
  and dispute adjudication.
- Exact-address publishing on the public or contractor lead board.
- Automated contractor licensing decisions, legal-eligibility decisions, or
  guarantees. A source-checked record is a dated human lookup, not an
  endorsement of skill, safety, coverage, or legal eligibility.
- Expansion outside DC, Maryland, and Virginia.
- Automatic rebooking, recurring schedules, contractor reservation, automatic
  bid or approval, and any paid advantage in an invited project.

## Trust, safety, and privacy requirements

- Public and unmatched-contractor views receive approximate coordinates and
  limited location text only.
- Direct phone/email fields and raw R2 object keys never appear in public APIs.
  Optional contractor websites appear only to the owner, active administrators,
  or a consumer with a bid relationship and are labeled as self-reported.
- Each protected route re-verifies identity, active status, role, ownership,
  and match state rather than trusting browser state.
- Job and profile photos are uploaded only through allow-listed MIME/extension
  combinations, a 12 MB limit, scoped object keys, and D1 ownership metadata.
- Suspended users cannot continue protected marketplace actions.
- All moderation actions create audit records.
- The first release is a controlled beta. Clerk Restricted sign-up mode limits
  account creation to invited users; invitation tickets return to
  `https://workdoe.com/create-account` and role selection remains on Workdoe.
- Production pages must publish Privacy, Terms, and Safety information before
  unrestricted public account creation.
- The owner must define data retention, account deletion, law-enforcement
  handling, underage-use rules, contractor representation, and incident
  response before general release.

## Experience requirements

- The deer logo links to the homepage.
- The first viewport prioritizes open projects, map/list navigation, and sign
  in rather than testimonials or technical explanation.
- Public home, sign-in, account-start, and contractor lead-board views place a
  compact `00` all-work control plus numbered `01`-`06` family icon controls
  above the existing search and map/list results. Selecting a family is a real
  URL filter, preserves relevant search and sort values, and can be cleared
  without JavaScript.
- Authentication remains inside the Workdoe page and uses a one-time email
  code; no hosted-login redirect is part of the intended flow.
- A filtered contractor lead URL retains its validated family, exact task,
  search, and sort intent through the same-domain sign-in journey.
- A first-time user entering from that contractor URL starts with the contractor
  role selected and returns to the same validated lead view after verification.
- Signed-in users can open `/account` to manage Clerk identity and security
  settings without leaving Workdoe; marketplace role and profile fields remain
  Workdoe-owned and are not changed by the Clerk component.
- `Post project` is a first-class public action at `/post-project`. A valid
  24-hour server-side draft survives account verification and prefills the
  protected project form; photos are accepted only after verification.
- Mobile users can switch among Projects, Map, and Details/Account without
  horizontal scrolling or obscured controls.
- Demo projects are visibly identified and must never be represented as live
  customer demand.
- Copy must remain practical and concise. Technical architecture belongs in
  repository documentation, not public product pages.

## Service and operational requirements

- `https://workdoe.com` is canonical and HTTP redirects to HTTPS.
- Production deploys are guarded and manual; routine pushes do not deploy.
- D1 migrations run before Worker release and production smoke checks run after
  release.
- Required secrets are stored outside source control.
- Authentication codes, reset links, full email queue bodies, and recipient
  addresses are excluded from operational audit payloads.
- Worker logs and traces remain enabled with a documented review process.
- The operator maintains working admin, security, privacy, and support contact
  channels.
- D1 and R2 backup/restore procedures are documented and restore-tested.
- An incident-response runbook identifies owner, severity levels,
  containment, notification, and recovery steps.
- The operating procedure is maintained in
  `docs/workdoe-operations-runbook.md`; documentation alone does not satisfy the
  restore-test or incident-drill acceptance criteria.
- The current personal-data map and unresolved retention decisions are
  maintained in `docs/workdoe-data-inventory.md`.
- The controlled beta remains a request-to-match marketplace. Workdoe does not
  set contractor prices, assign a contractor, direct how work is performed,
  process project payments, or promise workmanship until qualified counsel has
  reviewed the resulting worker-classification, employment-service,
  principal/agent, tax-reporting, insurance, and consumer-contract duties.
- Product changes that add managed scheduling, fixed pricing, assignment,
  payment, guarantees, claims decisions, or performance control trigger a new
  legal and security review before release.

## Launch acceptance criteria

- Public HTTPS, security headers, health endpoint, static assets, map/list, and
  open-jobs API pass production smoke tests.
- Non-secret release evidence confirms Clerk Restricted sign-up mode, the
  Workdoe custom sign-up URL, email-code sign-in, and disabled password sign-in.
- A real test consumer can receive an email code, create a job with a photo,
  review a bid, approve it, and exchange messages.
- A separate real test contractor can receive an email code, create a profile,
  find that job, submit a bid, and access only authorized photos/messages.
- A contractor can save reusable wording from their own bid, apply it to a
  different project with the price field empty, and cannot inspect or remove
  another contractor's template.
- Negative authorization tests prove role, ownership, and unauthenticated
  requests fail closed.
- An admin can resolve a report and the audit record is visible.
- Both production test participants can independently confirm a closed approved
  match whose close outcome is `workdoe-match`, and only the second
  confirmation creates a verified completion.
- After that verified completion, each participant can submit no more than one
  structured review; the recipient can respond once; a participant can report
  it; and an administrator can hide/restore the review and resolve its report
  with audit evidence. No address or participant contact field appears in the
  contractor-profile projection.
- A consumer can close and reopen with audited outcome state; a bidder can
  submit/update lead feedback; an administrator can review aggregate buckets
  without automation logs retaining private notes.
- Dependency vulnerability scans, secret scan, license inventory, unit tests,
  Cloudflare preflight, and deployment dry run are clean.
- Mobile and desktop public flows receive a visual, keyboard, screen-reader,
  contrast, and zoom/reflow pass.
- Privacy Policy, Terms, Safety, security contact, retention/deletion policy,
  and contractor disclaimers are approved and linked from public pages.
- Every live service-zone pair has an approved allowed/excluded scope, evidence
  path, at least three eligible contractors plus an operational backup, tested
  intake questions, and a monitored safety escalation owner.
- Qualified-match, time-to-first-eligible-bid, approved-match, verified-
  completion, and safety metrics are reviewed by service, zone, and week rather
  than only as a regional aggregate.
- The admin console presents a rolling 12-week service-zone pulse with
  transparent project, brief-readiness, bid, match, verified-completion, and
  current-supply denominators plus median time to first accepted Workdoe bid,
  controlled cancelled/no-fit outcomes, and open project-report counts. Active
  launch cells remain visible when they have zero projects, local demo accounts
  are excluded, and the pulse cannot change ranking, moderation, account status,
  or service eligibility. The response metric is not described as scheduled
  work, historical eligible-supply proof, or payment fulfillment.
- Counsel-approved launch documentation describes Workdoe's actual marketplace
  controls and the applicable DC, Maryland, Virginia, federal worker-status,
  employment-service, tax-reporting, and consumer-contract obligations. Product
  behavior, public copy, and Terms use the same role description.

## Owner decisions still required

- What legal person/entity operates Workdoe and what contact details should
  appear in Privacy and Terms?
- What minimum age, geographic eligibility, prohibited jobs, and contractor
  qualification language should apply?
- Which inboxes are monitored for administration, privacy, security, and user
  support, and what response targets apply?
- What retention and deletion periods apply to accounts, jobs, media,
  messages, moderation records, and logs?
- Which qualified counsel will review Workdoe's marketplace role and define the
  mandatory review trigger before payment, managed fulfillment, guarantees, or
  other additional control is introduced?

## Resolved owner decisions

- Workdoe's first-party source code, product copy, visual design, and original
  assets are proprietary. The top-level `LICENSE`, third-party notices, and
  machine-readable dependency provenance ledger record this posture.
