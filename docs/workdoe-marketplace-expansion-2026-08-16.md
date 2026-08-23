# Workdoe Marketplace Expansion Brief

Date: 2026-08-16  
Scope: DMV pilot, consumer project posting, contractor discovery, Cloudflare storage, launch path

Companion research: [DMV Competition and Commercial Launch Study](workdoe-dmv-competition-commercial-launch-study-2026-08-16.md)

## Product Decision

Workdoe should begin as a trust-forward local work exchange, not a paid shared-lead marketplace. The product advantage is a cleaner scope, a privacy-preserving location, and a direct request-to-match flow. A consumer chooses a service deliberately; the platform does not guess the canonical job type from free text.

The first useful form of gamification is progress and completion, not points or public leaderboards. Six understandable work families give consumers autonomy, the step indicator gives immediate progress, and the final review builds confidence before posting.

## Six-Step Posting Flow

1. Choose a work family: six numbered choices with pinned open-source icons.
2. Pick the service: show only services in the chosen family.
3. Describe the work: short title plus the scope, condition, access, and desired outcome.
4. Set the area: city, state, and ZIP; exact street address stays out of the public post.
5. Set timing and budget: optional desired date and optional range.
6. Review: show the canonical service, scope title, approximate area, date, budget, private photo option, and final action.

The form remains a valid server-rendered HTML form when JavaScript is unavailable. JavaScript only adds the step-by-step presentation, service filtering, progress, and live review.

### Visual task-picker update, 2026-08-17

Step two now preserves the visual language of the six-family opening instead of
falling back immediately to a plain dropdown. The selected family appears as a
compact context row, and its services render as numbered radio tiles using the
same pinned Tabler family icon. Only one family is visible at a time. Changing
families clears an incompatible task before the consumer can continue.

The canonical HTML `select` remains in the form and is visible whenever
JavaScript is unavailable. With enhancement enabled, each task tile writes the
same `service_slug` and deterministic legacy `category` values used by local
SQLite and Cloudflare D1. This makes the selection more tactile without making
classification probabilistic or weakening keyboard/native-form behavior.

### Discovery-family update, 2026-08-17

The same six canonical families now lead public and contractor discovery. Home,
sign-in, account-start, and contractor lead-board screens expose a compact
`00` all-work control followed by numbered `01`-`06` icon controls above search
and map/list results. The server validates each family slug, D1/SQLite apply the
filter before building the response, and map refresh URLs preserve it.

A contractor may save the family with the existing private category/query/sort
view. Matching-project alert fanout then rechecks that family before queueing an
email. This is deterministic taxonomy reuse, not vectorization: no model chooses
the category, no embedding is stored, and the selected family does not alter
organic ordering or eligibility.

## Service Taxonomy

| Work family | Included service examples | Current broad compatibility bucket |
| --- | --- | --- |
| Outdoor & yard | mowing, lawn care, gardening, weeds, leaves, hedges, trees, landscaping, fences, decks, snow, pressure washing | Landscaping, tree service, fencing, decks, power washing |
| Cleaning & upkeep | house, deep, turnover, windows, carpet, gutters, commercial, post-construction | Window cleaning or commercial maintenance |
| Moving & hauling | local moving, packing, lifting, furniture/appliances, office moves, junk, donation pickup | Junk removal |
| Repairs & installation | handyman, furniture assembly, mounting, doors/windows, carpentry, drywall, appliances, locks/security | General handyman or drywall |
| Remodel & finish | kitchen, bath, basement, interior/exterior paint, flooring/tile, cabinets, masonry, roofing/siding | Existing finish-trade category or Other |
| Home systems | plumbing, electrical, HVAC, water heaters, lighting/fans, generators, insulation, drainage | Plumbing, electrical, HVAC, or Other |

Canonical storage uses six `service_groups`, 53 `service_types`, and 17 deterministic aliases. The legacy `category` value remains populated so existing filters, contractor profiles, and records keep working during the transition. A named `Something else` service preserves legacy catch-all records without mislabeling them as handyman work.

The pilot intentionally excludes ambiguous high-risk buckets such as hazardous-material remediation, major structural engineering, medical care, firearms, and work that requires policy or license verification not yet implemented.

## Cloudflare Data Architecture

### Source of truth

- D1 stores `service_group_slug`, `service_slug`, the legacy category, job fields, role ownership, and moderation history.
- A versioned D1 migration creates and seeds the taxonomy, backfills existing jobs/drafts, and adds an index on status/family/service.
- R2 remains the private photo store. Object access continues through permission-checked Worker routes.
- Queues remain appropriate for email and media review tasks, not canonical classification.

### Why Vectorize is not the classifier

Vector similarity is probabilistic and depends on an embedding model. That is useful for discovery, but it is the wrong source of truth for billing, moderation, contractor routing, or category reporting. A changed model must not silently move a consumer's project into another bucket.

The recommended later search architecture is:

1. D1 remains canonical.
2. Workers build a search document from title, description, service, city, and state after the D1 write succeeds.
3. D1 indexed filters handle family, service, status, and location. The family
   filter is already implemented across posting, public browsing, saved lead
   views, and contractor alert matching.
4. D1 FTS5 can support keyword search if measured query volume justifies its write/storage cost.
5. Vectorize may be added as a replaceable semantic index for queries such as "yard cleanup before winter". Every result must still be filtered by D1 metadata and authorized from D1 before display.

Cloudflare documents D1 migrations and recommends applying schema changes through migrations rather than on request. Its indexing guidance also recommends measuring frequently queried columns and notes FTS5 as an option for arbitrary text search. Vectorize accepts vectors generated and managed by the application and supports metadata filtering; that confirms it is a retrieval layer, not the authoritative taxonomy.

## Marketplace Research

TaskRabbit, Angi, HomeAdvisor, and Nextdoor all expose recognizable household-service categories. Their common clusters support Workdoe's six-family model: cleaning, outdoor/yard, moving/hauling, handyman/installation, remodeling/finish work, and building systems.

Craigslist demonstrates the value of a short posting sequence and simple one-time economics, but its broad categories provide little scope quality. Workdoe should keep its directness while adding structured service selection, approximate location, private photos, and match approval.

Public contractor discussions about Thumbtack repeatedly describe shared paid leads, vague scopes, non-response, and lead costs as pain points. These are anecdotal reports, not population-level evidence, but they support a conservative launch: do not charge multiple contractors for the same unverified vague lead.

## Monetization Sequence

### Pilot

- Free for consumers and contractors.
- Measure completed profiles, ready-to-bid projects, response rate, match approval, time to first qualified bid, and project closure.

### First paid layer

- Contractor workspace subscription for saved service areas, faster alerts, calendar tools, and business analytics. The beta now includes up to six price-free proposal templates as a free utility so Workdoe can measure genuine reuse before deciding whether a larger template library or team controls belong in a paid plan.
- Optional one-time promoted placement that is clearly labeled and never changes organic match eligibility.

### Later, only after trust metrics are healthy

- Small success fee for an accepted match or completed platform-supported booking.
- Consumer tools for recurring property managers and small businesses.

Avoid selling the same unverified lead repeatedly. Uber's public marketplace material is useful for transparent upfront opportunity information, reducing idle time, and marketplace balance; its dynamic pricing and dispatch complexity should not be copied into this pilot.

## Contractor And Consumer Profiles

The contractor profile now supports a business name, canonical services and DMV zones, an HTTPS-only business website, description, insurance/license notes, years in business, portfolio uploads, and a deterministic seven-step readiness meter. The website is visible only to the contractor, active administrators, and consumers evaluating that contractor's bid; the unused phone input was removed. Next iterations may add an optional logo/cover photo, response reliability, and carefully defined verification status without creating a public popularity contest.

Consumer profiles now support a private household or organization name, workspace type, email-reminder preference, recurring project-area labels, one-click location prefilling, repeat posting, owner-only reusable project templates, and private project history. A single account keeps its permanent consumer or contractor role; consumers cannot fulfill projects. Contractors now have a separate six-item proposal-template library that reuses wording but deliberately never carries a prior price into a new lead.

## Safer Sign-In

- Keep the same-domain email-code flow for the pilot.
- Accept each code once, expire it quickly, and rate-limit failures.
- Offer Clerk passkey enrollment after a successful login as the safer low-friction upgrade.
- Require stronger authentication for administrators and sensitive account changes.
- Do not describe manually entered email OTP as phishing-resistant; NIST distinguishes passkeys from manually entered OTPs on that property.

## Commercial Launch Gaps

The guided composer and taxonomy improve product readiness, but they do not close the previously documented launch blockers:

- Production Clerk is still recorded as a development instance and webhook-secret proof remains incomplete.
- Privacy, Terms, Safety, prohibited-work, minimum-age, retention/deletion, and operator-contact decisions need owner/legal approval and live routes.
- A live two-user OTP -> job -> bid -> approval -> message -> moderation acceptance run is still required.
- Recovery, credential rotation, data deletion, incident response, keyboard/screen-reader testing, and an independent security assessment remain open.
- Workdoe's original source still has no selected top-level license. Third-party notices are present, but the repository must not be marketed as open source until the owner selects a license.

## Primary Sources

- Cloudflare D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- Cloudflare D1 indexing: https://developers.cloudflare.com/d1/best-practices/use-indexes/
- Cloudflare Vectorize/AI Search roles: https://developers.cloudflare.com/ai-search/concepts/how-ai-search-works/
- GOV.UK question pages: https://design-system.service.gov.uk/patterns/question-pages/
- GOV.UK radio buttons: https://design-system.service.gov.uk/components/radios/
- WCAG 2.2 understanding guidance: https://www.w3.org/WAI/WCAG22/Understanding/
- TaskRabbit service directory: https://www.taskrabbit.com/services
- Angi category directory: https://www.angi.com/companylist/
- Angi model FAQ: https://www.angi.com/faqs
- HomeAdvisor category selection: https://www.homeadvisor.com/servlet/CategoryServlet
- Nextdoor local business: https://business.nextdoor.com/en-us/local-1
- Craigslist posting fees: https://www.craigslist.org/about/Help/posting_fees
- Uber marketplace matching: https://www.uber.com/us/en/marketplace/matching/
- Uber service fee explanation: https://www.uber.com/us/en/marketplace/pricing/service-fee/
- Clerk email-code strategies: https://clerk.com/docs/guides/configure/auth-strategies/sign-up-sign-in-options
- Clerk passkeys: https://clerk.com/docs/guides/development/custom-flows/authentication/passkeys
- NIST authenticator guidance: https://pages.nist.gov/800-63-4/sp800-63b/authenticators/
