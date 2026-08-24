# Workdoe Data Inventory

Status: Internal review draft for the controlled beta. This inventory describes
the current code and planned Cloudflare production path. It is not an approved
Privacy Policy and it does not establish retention periods.

## Data principles

- Collect only what is required to create an account, describe work, evaluate a
  contractor, communicate after approval, and moderate the marketplace.
- Do not collect payment, bank, tax, Social Security, government-ID, precise
  device-location, or dedicated street-address data in the beta.
- Keep public location at city/ZIP area and rounded-map-pin level.
- Keep authentication secrets, reset links, OTP values, exact email addresses,
  and private message bodies out of operational audit payloads and logs.
- Keep job photos private behind role, ownership, match, and moderation checks.
- Treat contractor insurance, license, experience, and profile statements as
  self-reported unless a specific record is marked with a dated source check.
  A source check is not a legal-eligibility, scope, safety, or warranty decision.

## Data map

| Data group | Fields and source | Purpose | Stored in | Current visibility |
| --- | --- | --- | --- | --- |
| Account identity | Email, display name, company/household name, permanent role, status, verification state, Clerk subject | Sign-in, role enforcement, suspension, account display | Clerk plus D1 `users` | Account owner and active administrators; display/business name may appear in role-appropriate marketplace views |
| Authentication | Clerk session, email code, code/token hashes, attempt count, keyed IP hash, reset-token hash | Verify identity, limit abuse, recover local/demo accounts | Clerk cookies/session; D1 `login_codes` and local `password_reset_tokens` | Authentication systems only; never public |
| Idempotent write record | Actor ID, allow-listed action, SHA-256 request-key hash, generic resource type/ID, processing/completed state, creation/completion/expiry timestamps | Prevent browser or network retries from creating duplicate projects, ordinary messages, moderation reports, or private photos | D1/SQLite `idempotency_requests`; browser key created with Web Crypto | Internal application control only. It stores no raw key, identity/contact value, project content, message/report text, media path, location, bid term, or ranking field. Records expire after 24 hours and are opportunistically removed by later protected creates |
| Consumer profile | Organization/household name, workspace type, email-reminder preference, email-reminder consent timestamp, private note, legacy optional phone | Support households, recurring users, and small organizations without making them public marketplace profiles; prove affirmative consent before optional bid-reminder email | D1 `client_profiles` | Account owner and active administrators; current marketplace payloads do not expose these profile fields or phone. New/pre-consent profiles use the Workdoe inbox only; disabling email clears the consent timestamp and the scheduled queue requires both the email preference and a timestamp |
| Saved project area | Owner-defined label, city, state, ZIP, timestamps | Prefill the approximate-location step for recurring work | D1 `client_saved_locations` | Owning consumer and active administrators; project composer shows only the owner's records and no street address is collected |
| Project template | Owner-defined name plus service family/task, category, title, description, coarse project setting, optional budget, optional license-record preference, source-project ID, timestamps | Reuse recurring scope without silently carrying stale or sensitive project state | D1 `client_project_templates` | Owning consumer and active administrators through controlled operations. The schema excludes city, state, ZIP, desired date, photos/media paths, bids, messages, close outcomes, and completion state; use opens the six-step composer with location/date blank |
| Repeat-provider invitation | New project ID, prior project and approved-match IDs, consumer and contractor IDs, canonical service, pending/bid-sent/declined/withdrawn state, timestamps | Let a consumer ask a contractor from mutually verified work to consider a new same-service project without silently recreating prior terms; measure invitation, fresh-bid, and verified-repeat outcomes | D1 `repeat_provider_invitations`; one immediate Cloudflare email queue job in production | Owning consumer sees status; invited contractor sees the new project and may pass or submit a fresh ordinary mini bid; active administrators receive aggregate funnel counts and a recent project-level queue. The table contains no address, ZIP, media, message, contact, prior bid, price, schedule, or ranking fields. The email carries only recipient, new-project title, city/state, and a same-domain `/jobs/:id` URL; its D1 audit record replaces recipient with a keyed hash and omits message content |
| Contractor profile | Business name, legacy trade/area summary, introduction, insurance statement, license number, years in business, optional HTTPS website | Help consumers evaluate a bidder and preserve compatibility with earlier profiles | D1 `contractor_profiles` | General public sees profile facts and portfolio; the owner, active administrators, and a consumer who received that contractor's bid may see the normalized website; phone is not collected by the current profile form |
| Contractor credential claim | Contractor ID, credential type, jurisdiction, claimed identifier/name, review status, public HTTPS source, checked/expiry timestamps, reviewer ID, private review note, creation/update timestamps | Preserve claim and human-review provenance without manufacturing a generic trust badge | D1 `contractor_credentials` | Contractor owner and active administrators see the full claim; public profiles receive only current source-checked type/jurisdiction, checked/expiry dates, and public source. Rejected, pending, self-reported, and expired records are not public; public payloads exclude identifier and review note |
| Contractor market fit | Canonical service slugs and practical DMV zone slugs selected by the contractor | Deterministic, explainable service/area fit on the lead board | D1 `contractor_service_capabilities`, `service_zones`, and `contractor_service_zones` | Contractor owner can update selections; public profiles show service and area labels; lead payloads expose a fit label but not the saved selection records or project ZIP |
| Contractor work preferences | Self-reported availability state, optional next-available date, saved canonical work-family slug, saved canonical task slug, saved legacy category for compatibility, saved search text, saved deterministic sort, matching-project alert preference and consent timestamp, timestamps | Let a contractor communicate coarse capacity, restore one useful deterministic lead view, and explicitly opt into new matching project email | D1 `contractor_lead_preferences` | Public profiles receive only the coarse availability label/date and a self-reported qualifier; saved filters and alert consent are returned only to the owning active contractor and active administrators through controlled operations. Family and task values are allow-listed taxonomy slugs, not free text or embeddings. Opting out clears consent |
| Contractor lead-alert delivery | Contractor ID, new project ID, pending/queued/sent/failed state, created/queued/sent/update timestamps | Deduplicate and operate one consented project alert per contractor/project pair | D1 `contractor_lead_alert_deliveries`; Cloudflare `EMAIL_QUEUE` | Owning system operators and active administrators. The table contains no email address, client identity, ZIP, description, scope, media, message, bid, or provider response. Email jobs contain contractor recipient plus new title, canonical service label, city/state, and same-domain project/settings links; audit events replace recipient with a keyed hash |
| Service-zone activation | Canonical service and zone, launch status, allowed and excluded scope, requirements summary, minimum eligible-contractor count, approver ID, review/approval/expiry timestamps | Keep unreviewed, expired, paused, or undersupplied markets from publishing leads or accepting new bids | D1 `service_zone_activations`; enforcement setting in the Worker environment | Active administrators can inspect the gate; it is not a public record and activation remains a controlled operator change |
| Project | Title, curated category, coarse project setting, city, state, ZIP, description, desired date, optional budget bounds, optional license-record preference, status, rounded coordinates, bid limit, bidding deadline, controlled close reason, optional private close note, close timestamp | Publish and match local work while making contractor competition visible and bounded; distinguish a successful Workdoe match from cancellation or other closure | D1 `jobs` | The optional setting is limited to house, apartment/condo, business/office, shared building area, outdoor area, or other; it is not a property listing, ownership assertion, building name, unit, or address. Anonymous view gets title/category/city/state/date/budget/photo count/rounded pin and the non-personal preference boolean; signed-in contractors get the project brief, setting label, ZIP prefix, and a closed-outcome label when applicable; only the owning consumer and active administrators receive the private close note. The preference does not filter, rank, recommend, or determine eligibility |
| Project scope answers | Project ID, scope schema version, controlled question key, controlled answer code, timestamps | Improve quote readiness and measure which deterministic fields reduce contractor follow-up | D1 `job_scope_answers` | Owning consumer, eligible signed-in contractor, and active administrator receive human-readable labels in the project view. The table stores no narrative, email, phone, street address, ZIP, coordinates, media, bid, or contact data and does not drive activation or ranking by itself |
| Project brief readiness projection | Six booleans and an integer total derived from canonical service, description length, controlled scope-answer count, coarse setting, desired date, and budget-or-photo presence | Let both sides see whether a post contains enough observable quoting context and measure brief readiness in aggregate | Computed in Python response/UI code; not stored as a separate D1 record | Owning consumer and eligible signed-in contractors see the same named signals. The projection does not read identity, email, phone, exact address, coordinates, fit score, bid behavior, payment, review, or paid-placement fields and never changes ordering or eligibility |
| Service-zone pulse projection | Monday week, canonical service, coarse DMV zone, aggregate published/brief-ready/with-bid/matched/verified counts, median project-to-first-bid time, desired-date count, controlled close-out buckets, open-project-report count, total bid count, and current eligible/minimum contractor counts | Let an administrator detect thin demand, slow response, poor close outcomes, open review load, and supply gaps before expansion or monetization | Computed from existing D1 marketplace and activation records in Python; not stored as a separate analytics table | Active administrators only. First-bid timestamps are reduced to a project-level duration and then a cell median; raw timestamps are not returned. Open reports are counted once per project without reason text. Output contains no project/account ID, name, email, phone, street address, ZIP, coordinates, narrative, media, message, bid terms, close note, report reason, or private feedback. Local `.local` demo accounts are excluded. Current supply is a review-time snapshot, not the historical count at first bid, and the projection never changes ranking, moderation, account status, or eligibility |
| Pre-verification draft | Project fields above except email and photos, including the optional license-record preference; random token hash and expiry | Let a consumer begin before email verification | D1 `job_drafts`; HttpOnly draft cookie | Token holder until consumed or expired; not publicly listed; the coarse setting and neutral preference follow the same restrictions as the published project |
| Draft scope answers | Draft ID, scope schema version, controlled question key, controlled answer code, timestamps | Preserve optional quote-readiness choices through same-domain email verification | D1 `job_draft_scope_answers` | Available only through the valid draft token, then copied from the submitted form into the published project's normalized answer rows. The table has the same location/contact exclusions as project scope answers |
| Project media | Cloudflare Images-sanitized single-frame WebP bytes, original filename in D1, sanitized content type/size, generic storage key, uploader/owner IDs, moderation state | Show project conditions to eligible contractors while discarding embedded metadata and never persisting raw upload bytes | Cloudflare Images transform, private R2 `workdoe-media`, and D1 `job_photos` | Owning consumer, active contractors for open jobs or approved matches, and active administrators; never publicly listable |
| Contractor media | Cloudflare Images-sanitized single-frame WebP bytes and the same metadata categories | Portfolio display and moderation while discarding embedded metadata and never persisting raw upload bytes | Cloudflare Images transform, private R2, and D1 `contractor_photos` | Active public profile unless hidden; owner and active administrators retain management access |
| Mini bid | Scope note, price/range, timeline, experience, questions, availability, status | Let a contractor request a match | D1 `match_requests` | Submitting contractor, project owner, and active administrators |
| Contractor proposal template | Owner-defined name, source mini-bid ID, reusable scope note, timeline, experience, questions, availability, timestamps | Reduce repeat typing while forcing a new commercial estimate for each project | D1 `contractor_proposal_templates` | Owning contractor and active administrators through controlled operations. The schema has no price, project ID, client identity, email, phone, location, address, ZIP, media, message, ranking, or outcome field. Applying a template prefills only reusable wording and leaves price blank |
| Consumer bid comparison projection | Up to four pending bid IDs, contractor ID/display name/trades, latest visible contractor-photo ID, price range, timeline, availability, received-order position, self-reported years/insurance presence, current source-checked credential count, and mutually verified Workdoe project count | Let the owning consumer compare like-for-like offer and provider facts before opening a profile or approving a match | Computed in shared local/Worker Python code from existing bid/profile/credential/completion/media records; not stored separately | Owning consumer and active administrators through the protected project view. The media projection emits only `/media/contractors/:id` for a non-hidden active-profile photo and never emits the R2 key or original filename. It also excludes email, phone, address, ZIP, coordinates, website, license/credential identifier, review narrative, private messages, fit score, recommendation, and paid placement. Source checks, completion history, and self-reported fields remain separately labeled and never become a composite score |
| Lead-quality feedback | Project ID, submitting contractor ID, controlled reason code, optional private note, timestamps | Detect repeated scope, category, geography, contactability, availability, authorization, duplicate, or fraud problems without inferring them from free text | D1 `job_lead_feedback` | The submitting contractor may create/update their signal after bidding; active administrators see aggregate buckets and recent records; the consumer, other contractors, and public APIs do not receive the note |
| Match completion | Approved match ID, separate consumer and contractor confirmation timestamps, verified timestamp, creation/update timestamps | Distinguish a closed lead from work both participants say was completed | D1 `match_completions` | Match participants see the status in their workspaces; public contractor profiles receive only an aggregate verified-completion count; active administrators receive aggregate outcomes and audit events |
| Completed-work feedback | Approved match ID, reviewer and subject IDs, reviewer role, four controlled dimension codes, work-together-again code, optional capped narrative, one optional recipient response, hidden state, timestamps | Capture two-sided project evidence only after mutual completion without manufacturing a star score or recommendation rank | D1 `match_reviews` | One record per reviewer/match. Both participants see match feedback in their workspaces; client-authored contractor feedback may appear only where the contractor profile itself is relationship-visible. The projection excludes emails, contact fields, location, address, media, and bid terms |
| Feedback report | Review ID, reporter ID, capped reason, open/resolved state, timestamps | Let either review participant request human moderation | D1 `match_review_reports` | Review participants can create one report each; active administrators can inspect and resolve it. Automation events retain only role/action metadata, not the reason |
| Approved conversation | Thread participants, message body, sender, timestamp, hidden state, and per-participant last-read message ID/time | Private post-approval communication and durable unread state | D1 `threads`, `messages`, and `thread_reads` | Approved consumer/contractor participants; administrators have read-only moderation inspection. The participant inbox derives a `needs_reply` boolean from the latest visible sender at response time, but does not store or return that sender ID, add a behavioral profile, or affect marketplace ordering |
| Safety report | Reporter, target type/ID, reason, status, timestamps | Review abuse, privacy, and safety issues | D1 `reports` | Creation requires the reporter to be authorized to view the target; reporter confirmation and active administrators can view the resulting record |
| Moderation/audit | Administrator ID, action, target, reason/notes, timestamps; allow-listed automation metadata | Accountability, recovery, queue operations, abuse investigation | D1 `moderation_actions` and `automation_events` | Active administrators |
| Platform request data | IP address sent transiently to Turnstile and Clerk proxy; keyed IP hash for native-code rate limits; internal Workdoe user ID used transiently as the authenticated Worker rate-limit key; request/error metadata in Workers Logs | Bot defense, rate limiting, authentication proxy, service diagnosis | Cloudflare processing, limited D1 keyed hash, Workers Logs | Authorized operators and service providers |

## Public and protected boundaries

### Anonymous visitors

Anonymous visitors can see open-project titles, curated categories, city/state,
desired date, budget label, photo count, approximate rounded pins, and whether
the consumer prefers a current license record. The preference is a project
brief signal only and never changes order, bidding access, or contractor
eligibility. Workdoe's
Cloudflare public payload now substitutes `Project details are available after
sign-in.` for a live user's free-text description. Controlled sample projects
may show their authored sample descriptions.

All reviewed server-rendered user content is HTML-escaped before insertion into
the response. A regression test covers script-shaped marketplace content so
stored text cannot become executable markup in those views.

Public contractor profiles can show business name, trades, service area,
introduction, self-reported insurance/license/experience fields, portfolio
photos, coarse self-reported availability, and update date. Phone, email,
account subject, saved lead filters, and storage keys are
excluded. A contractor-provided HTTPS website is additionally available to the
profile owner, active administrators, and a consumer who has received a bid
from that contractor. Unrelated and anonymous visitors do not receive it.
Current source-checked credential records may also appear as atomic type and
jurisdiction labels with review/expiry dates and the checked public source.
This projection excludes the stored identifier, claimed name, reviewer ID, and
review note. It is not a blanket Workdoe verification badge.
Client-authored completed-work feedback may appear only when the viewer already
has permission to inspect that contractor profile through ownership,
administration, or a bid relationship. It is labeled `Workdoe-completed`,
contains no client identity or project location, and creates no public average,
star score, recommendation order, or paid placement.

### Signed-in contractors

An active contractor can see open project descriptions, ZIP prefix, budget,
desired date, and job photos so they can prepare a mini bid. Exact street
address is not a structured Workdoe field. Project-entry forms warn consumers
not to place an exact address, email, or phone in free text.

Residual risk: a consumer can ignore that warning and type contact or address
data into a title, description, message, or image. Before unrestricted launch,
the owner must choose moderation-only handling or an approved detection/blocking
rule and false-positive process.

### Approved matches

Approval creates a private message thread. The MVP does not automatically
expose phone, email, payment details, or a street address. A contractor's
optional business website may already be visible to the consumer evaluating
that contractor's bid; it is labeled as contractor-provided and does not carry
a Workdoe verification claim. Any later direct-contact sharing needs an
explicit business rule, permission check, UI disclosure, and privacy-policy
update.

After the consumer closes the project, either approved-match participant may
confirm completion. The two confirmations are stored independently. Workdoe
sets `verified_at` only when both are present and prevents reopening once either
confirmation exists. This status does not create a payment, warranty, license
verification, or dispute decision. Only after `verified_at` exists may each
participant create one structured review. The recipient may respond once and
either participant may report it. Review narrative, response, and report reason
are stored in their purpose-specific tables and are not copied into automation
event payloads.

A mutually verified match can also authorize a private repeat-provider
invitation for a new same-service project. The invitation does not copy prior
location, photos, messages, contact data, or bid terms. It creates no match
request or message thread; only a fresh contractor bid can do that, and the
ordinary service gate, cap, and deadline still apply.

### Administrators

Active administrators can review users, jobs, photos, reports, recent messages,
completed-work feedback, feedback reports, moderation actions, and allow-listed
automation events. They may hide/restore feedback and resolve its reports.
Message inspection is read-only. Administrative access does not waive
data-minimization or audit requirements.

## Cookies and transient tokens

| Name or provider | Purpose | Current lifetime/control |
| --- | --- | --- |
| Clerk `__session` and Clerk-managed state | Production email-code session | Clerk production configuration; owner must approve session/retention policy |
| `workdoe_session` | Native Cloudflare email-code session when that auth mode is enabled | Seven-day signed HttpOnly, Secure, SameSite=Lax cookie |
| `workdoe_job_draft` | Resume the pre-verification project draft | 24-hour random token in an HttpOnly, Secure, SameSite=Lax cookie; D1 stores only its hash |
| Local Flask session | Local reference login, CSRF token, and draft token | HttpOnly, SameSite=Lax; Secure in production-mode testing |
| Turnstile response token | Bot-verification request | Sent to Cloudflare Siteverify and not intentionally persisted by Workdoe |

Workdoe application JavaScript does not intentionally store marketplace data in
`localStorage` or `sessionStorage`.

## Service providers and transfers

| Provider | Data handled | Boundary |
| --- | --- | --- |
| Cloudflare Workers, D1, R2, Queues, Email Service, Turnstile, and Logs | Application records, private media, email jobs, request/security metadata | Primary production platform; access, retention, backup, and deletion settings require operator approval and drills |
| Clerk | Email identity, invitations, email-code verification, sessions, user subject | Production identity provider; Restricted sign-up and production-instance proof remain launch gates |
| OpenStreetMap tile service | Tile request metadata such as requester IP and browser headers | Public map tiles only; no exact Workdoe address or browser geolocation is sent by application code |
| GitHub Actions | Source, tests, release metadata, Cloudflare deployment credentials | Release tooling; production user exports and database/media backups must not be attached as workflow artifacts |

## Public policy surfaces

The production candidate exposes `/privacy`, `/terms`, and `/safety`, with
linked `robots.txt`, `sitemap.xml`, and `/.well-known/security.txt` discovery
files. These routes summarize the current data map and controlled-beta product
boundaries; they do not replace approval of the unresolved retention,
operator-identity, contact-ownership, and legal decisions tracked in
`docs/workdoe-policy-review-checklist.md`.

## Current technical retention

- Project drafts expire after 24 hours and are marked consumed after account
  handoff. The cleanup schedule and deletion evidence still need an operations
  drill.
- Native email codes expire after 10 minutes, are attempt-limited, and are
  atomically consumed before account/session issuance. Existing rows are
  expired/invalidated, but the long-term deletion period is not yet an approved
  policy.
- Native sessions are configured for seven days. Clerk session policy remains a
  production configuration decision.
- Jobs, profiles, photos, bids, completion confirmations, completed-work
  feedback/responses/reports, messages, general reports, moderation actions,
  automation events, and account rows have no owner-approved retention period.
- R2 lifecycle/lock rules are intentionally not applied until deletion, legal
  hold, and backup-retention decisions are approved.
- Workers Logs are enabled, but the review cadence, sampling, export, and
  retention owner remain operational decisions.

## Data minimization fixes verified in review

- Full email queue bodies are no longer copied into D1 automation events on
  validation, missing-binding, provider-failure, or unknown-queue paths.
- Email audit events retain only event type, attempt count, a keyed recipient
  hash when the app secret is available, and allow-listed delivery fields.
- Successful email delivery is acknowledged before its best-effort audit write;
  an audit outage is logged without retaining message content and cannot cause
  a duplicate delivery retry.
- OTP values, reset URLs, full recipient addresses, subjects, arbitrary provider
  result fields, and bounce addresses are excluded from audit payloads.
- Repeat-provider alert payloads use only the contractor recipient, new-project
  title, city/state, and an exact same-domain project URL. They do not read or
  queue prior scope, ZIP, address, contact, message, media, or bid fields.
- New matching-project fanout requires affirmative email consent, a saved lead
  view, an available contractor, saved work-family and category/query fit,
  exact service and zone capability, an open bid window, and no existing bid. Delivery state
  is unique per contractor/project; queue and audit payloads omit client
  identity, ZIP, description, media, messages, and bid content.
- Clerk onboarding audit events use the D1 user target instead of duplicating
  email and Clerk subject values.
- Anonymous Cloudflare public-job payloads no longer expose live user-written
  descriptions; sample descriptions remain available for the controlled demo.
- Public contractor portfolios and inline media response headers use generic
  photo labels instead of exposing original upload filenames.
- Uploads require matching allow-listed extension, MIME type, and file header;
  failed metadata or queue handoffs trigger scoped D1/R2 cleanup and an audit
  event so private orphaned objects can be reconciled.
- Project forms now warn against exact street addresses, email addresses, and
  phone numbers.
- Reports can be created only for targets the reporter is authorized to see;
  private-message reports require membership in the approved thread.
- Contractor websites are accepted only as public HTTPS URLs. Validation
  rejects credentials, local/single-label hosts, IP literals, nonstandard
  ports, malformed DNS labels, and whitespace/control characters. Rendered
  links open in a new tab with `noopener`, `noreferrer`, `nofollow`, and
  `external` relationships.
- The unused contractor phone input was removed. Existing legacy database
  columns remain for migration compatibility and are cleared when a contractor
  profile is saved.

## Owner decisions required

1. Decide whether client profile phone is also removed until a supported use
   exists.
2. Approve whether free-text contact/address leakage is handled through user
   instruction and moderation or through a blocking detector and appeal path.
3. Set retention/deletion periods for accounts, identity links, projects,
   drafts, media, bids, messages, reports, moderation/audit records, and logs.
4. Name the privacy-request owner, identity-verification method, export format,
   deletion exceptions, and response target.
5. Approve Clerk session settings, Workers Logs sampling/review, R2 backup
   retention, and the production subprocessor list.

The corresponding execution and drill procedure is in
`docs/workdoe-operations-runbook.md`.
