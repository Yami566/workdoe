# Workdoe DMV Gamified Marketplace and Commercial Launch Study

Date: 2026-08-21

Status: product and implementation decision record

## Decision summary

Workdoe should launch as a transparent local work exchange, not as an opaque
lead-resale product. The most defensible first interaction is:

1. Choose one of six numbered work families.
2. Choose one of six common tasks in that family.
3. Open the longer service list only when the common choices do not fit.
4. Describe, locate, time, and review the project in the existing six-step flow.
5. Keep identity, direct contact, and exact addresses private until a consumer
   approves a contractor's mini bid.

The six work-family slugs remain stable. This keeps old jobs, D1 records,
filters, alerts, and reporting comparable while allowing labels and task order
to become clearer.

## 2026-08-23 implementation decision

Workdoe now adds a deliberately narrow progress layer for contractors:

- 100 completion points per mutually confirmed Workdoe project;
- milestone labels at 1, 3, 10, and 25 verified completions;
- separate source-checked-record and source-checked-license signals;
- no paid weight, eligibility change, search boost, bid reorder, or composite
  star score; and
- no new points table or inferred reputation data. The display is a
  deterministic projection of compartmentalized completion and credential
  records already required by the marketplace.

Consumers can filter the four received-order comparison cards by any current
source-checked record or a current source-checked trade-license record. Every
offer remains visible in the complete received-order list. The wording stays
atomic: a reviewed public record is not a guarantee of skill, safety,
insurance coverage, or legal eligibility.

The 2026-08-23 milestone follow-up makes all four fixed thresholds visible as
one compact earned/next/locked track on contractor dashboards and public
profiles. Progress is measured against the next absolute threshold, so one
verified project reads `1 of 3` toward Steady provider instead of an empty
post-milestone `0 of 2` bar. The follow-up adds no table, event, score input,
personal field, ranking weight, eligibility rule, or marketplace reorder.

The 2026-08-23 contractor-choice follow-up applies the research decision to use
portfolio evidence as a fit signal without manufacturing a recommendation. Up
to four received-order offer cards may show the newest visible, moderated
contractor photo; compact work-history and source-check signals sit beside that
identity; repeated credential rows are removed from the card presentation; and
the legal qualification note moves into a native disclosure. Photo presence
does not change received order, the four-bid cap, eligibility, or ranking.

## Research method and limits

This review uses public product pages, public help centers, public company
reports, government design-system guidance, official Cloudflare and Clerk
documentation, and explicitly licensed open-source repositories. It does not
use copied private code, leaked material, reverse-engineered competitor APIs,
or confidential product information.

Public documentation is research evidence, not automatically open-source code.
Workdoe may adapt a general interaction pattern described there, but should not
copy protected text, branding, imagery, screen composition, or implementation.

## Market comparison

| Product | Strong pattern | Commercial model signal | Workdoe adaptation | Do not copy |
| --- | --- | --- | --- | --- |
| Thumbtack | Structured service intent, tailored result sets, messaging, instant booking for simpler jobs and estimates for complex jobs | Marketplace and professional acquisition economics | Separate quick, quotable tasks from complex estimate-led work; keep the six-family intake | Proprietary ranking, wording, visual design, or undisclosed lead allocation |
| Craigslist | Very short local posting sequence: location, type, category, text, map, photos, review | Paid postings in selected markets/categories | Preserve local-first, low-friction posting and draft review | Minimal trust controls and public contact exposure |
| Angi/HomeAdvisor | Large service taxonomy, professional profiles, lead and completed-service models | Professionals may pay for matches, ads, or completed work | Capture lead outcomes before considering fees; show provider evidence without a paid rank | Charging for unproven or ambiguous leads during the pilot |
| Taskrabbit | Task-scoped categories, availability, price-oriented selection, explicit trust and safety support | Platform service fees | Use familiar task language and availability; distinguish simple tasks from licensed or high-risk work | Fee complexity or implying guarantees Workdoe has not funded or verified |
| Nextdoor | Neighborhood radius, local business pages, recurring local presence | Business promotion and local ads | Let recurring consumers and contractors maintain stable local profiles and coarse service areas | Treating neighborhood identity as proof of competence |
| Google Local Services | Category eligibility, service areas, lead inbox, business screening, lead-quality feedback | Pay per valid lead, with budgets and credit logic | Require service/area fit, evidence gates, truthful fees, and quality reason codes before monetization | Pay-per-lead before Workdoe can adjudicate invalid or duplicate leads |
| Bark | Lead screening and quality reporting | Professional credit/lead model | Add explicit report reasons and an operator review loop | Selling the same vague request broadly without a fair opportunity rule |
| Porch | Professional preferences, lead controls, service area and budget concepts | Lead and subscription programs | Keep service capabilities, zones, availability, and lead preferences first-class | Making the consumer solely responsible for all platform quality checks |
| Homes.com | Locality, neighborhood information, agent profiles, conversational property discovery | Real-estate advertising and agent products | Use locality as context and keep profiles useful for repeat property work | Treating it as a direct contractor-marketplace blueprint |
| Uber | Upfront marketplace principles, reliability, two-sided marketplace measurement, open H3 geospatial tooling | Transaction service fee | Measure consumer time-to-match and contractor opportunity together; consider a clear success fee only after booking evidence exists | Dynamic or opaque pricing before trust and liquidity are established |

## Current SWOT

| Area | Workdoe position |
| --- | --- |
| Strengths | Structured six-step briefs, public approximate-location demand, four-offer caps, received-order fairness, role separation, source provenance, mutual completion, and no paid rank create a clearer service workflow than a general classified or social feed. |
| Weaknesses | Workdoe has no established liquidity or reputation network, requires human credential moderation, carries Flask/Worker parity cost, and still lacks production proof for email, identity, media, and operator response. |
| Opportunities | Meta's official policy leaves services such as home cleaning outside Marketplace; Uber's Trip Radar demonstrates provider-selected nearby opportunities; Nextdoor demonstrates demand for local reputation; and Thumbtack/Angi demonstrate consumer value in structured scope and comparison. Workdoe can combine those needs without selling the same lead broadly. |
| Threats | Incumbent supply, completion collusion, jurisdiction-specific licensing, moderation load, tile-provider limits, paid-acquisition pressure, and the two-sided cold start can all undermine a DMV launch before the product earns reliable repeat use. |

The competitive boundary remains intentional. Uber's driver app lets providers
select interesting Trip Radar opportunities, while Nextdoor's recommendation
volume can affect business recognition and visibility. Workdoe adopts the
provider-choice and visible-milestone ideas, but completion points never alter
lead order and consumer comparison filters never hide the full bid record.

## Category strategy

The product should present six plain-language families. Each family has six
quick tasks followed by an explicit `More ... services` control.

### 01 Yard and landscaping

Quick tasks:

- Lawn mowing
- Lawn care
- Gardening and planting
- Weed removal
- Leaf cleanup
- Hedge trimming

Additional tasks include tree service, landscape installation, fencing, deck
and patio work, snow removal, and pressure washing.

### 02 Cleaning

Quick tasks:

- House cleaning
- Deep cleaning
- Move-in or move-out cleaning
- Window cleaning
- Carpet and upholstery cleaning
- Gutter cleaning

Additional tasks include commercial and post-construction cleaning.

### 03 Moving and hauling

Quick tasks:

- Local moving
- Packing and unpacking
- Heavy lifting
- Furniture and appliance moving
- Office moving
- Junk removal

Donation pickup remains in the additional list.

### 04 Handyman and repairs

Quick tasks:

- General handyman
- Furniture assembly
- Mounting and installation
- Door and window repair
- Carpentry
- Drywall repair

Appliance work, locks/security, and the catch-all service remain additional.

### 05 Remodeling

Quick tasks:

- Kitchen remodel
- Bathroom remodel
- Basement remodel
- Interior painting
- Exterior painting
- Flooring and tile

Cabinets/countertops, concrete/masonry, and roofing/siding remain additional.

### 06 Plumbing and systems

Quick tasks:

- Plumbing
- Electrical
- Heating and cooling
- Water heater
- Lighting and ceiling fans
- Generator and backup power

Insulation/weatherization and drainage/sump pump remain additional.

This order is a product hypothesis based on competitor category prominence and
the existing Workdoe taxonomy. It must be validated against DMV search terms,
completed projects, and contractor supply. Popularity should never silently
change per user during the pilot.

## Interaction findings from the current product

Evidence is stored in
`docs/ux-audit/2026-08-21-gamified-selection/` and
`docs/ux-audit/2026-08-21-gamified-work-selector/`.

### Marketplace

- The public map and live projects correctly establish that Workdoe is a
  marketplace.
- On the previous mobile layout, navigation, hero actions, and a tall map
  delayed the six-family selector until below the first viewport.
- The family selector should precede the map on the Flask public view so users
  can choose a lane before scanning pins. The map remains visible immediately
  after that compact choice band.
- Selecting a lane now presents two explicit outcomes instead of guessing the
  visitor's role: browse the filtered open projects or post within that lane.
  The posting action carries the canonical family into the same-page composer
  and starts at the six common tasks.
- The secondary public filter now follows the same hierarchy: no long task
  menu appears before a lane is chosen; after selection, the native task menu
  contains only that family's 7-12 canonical services. Exact task selection is
  enforced in SQLite/D1 and carried into Step 3 of project posting. The legacy
  category query remains accepted for old links but is no longer the primary
  consumer control.
- This deliberately uses a labeled native select only after the option set is
  short. USWDS recommends selects sparingly for roughly 7-15 choices, requires
  a visible descriptive label, and calls for implementation-level mobile,
  keyboard, zoom, and screen-reader checks. Workdoe keeps the six families as
  larger tile targets and uses the select for the narrower task choice.

### Project posting

- Step 1 already uses six stable numbered families and familiar Tabler icons.
- Step 2 previously rendered up to twelve visually equal choices. Six common
  tasks plus progressive disclosure reduces scanning without removing any
  canonical service.
- The first task-level implementation repeated the family icon on every task.
  The current implementation assigns a distinct pinned Tabler 3.46.0 icon to
  each canonical task, so lawn mowing, planting, cleanup, and trimming can be
  distinguished before the text is read.
- The native select remains available when JavaScript is unavailable. Both
  paths store the same service and family slugs.

## Gamification boundary

Workdoe should make progress legible, not turn household work or contractor
income into a game of chance.

Use:

- stable `01` through `06` family lanes and numbered common tasks;
- a six-step completion indicator with one decision per step;
- quote-readiness feedback based only on fields the consumer has completed;
- visible bid stages, response status, completion confirmation, and repeat-work
  history;
- contractor profile completeness and verified evidence, without implying
  licensure or safety checks that have not actually occurred.

Do not use:

- streaks, loot, spin mechanics, artificial countdowns, or fake scarcity;
- hidden paid rank, variable lead access, or points that can override service,
  jurisdiction, availability, or credential eligibility;
- badges that imply background checks, insurance, licensure, or guarantees
  without current evidence and an accountable review process;
- engagement metrics as a substitute for qualified bids and completed work.

This keeps the delightful part in the interaction quality: quick recognition,
clear progress, useful feedback, and a satisfying handoff into real work.

## Research-backed service coverage

The current 53 canonical services cover the core public category sets in the
Taskrabbit service directory and Google Local Services: lawn and garden work,
cleaning, moving and lifting, handyman/assembly, painting and remodeling,
plumbing, electrical, HVAC, roofing, fencing, junk removal, and window work.

The U.S. Bureau of Labor Statistics separately describes grounds-maintenance
work as mowing, edging, fertilizing, weeding, mulching, trimming, planting, and
watering. Those duties support keeping `lawn-mowing`, `lawn-care`,
`gardening-planting`, `weed-removal`, `hedge-trimming`, and `tree-service` as
distinct task buckets rather than collapsing them into one vague landscaping
category. BLS also distinguishes construction labor/helper work involving
site cleanup, materials, tools, and assistance to skilled trades. Workdoe
should therefore avoid presenting unlicensed general labor as equivalent to a
licensed trade.

Deterministic recall aliases now map familiar phrases such as `grass cutting`,
`yard cleanup`, `local movers`, `TV mounting`, `kitchen renovation`, `plumber`,
and `AC repair` to canonical service slugs. D1 migration `0026` stores the same
aliases and task icon names. These aliases improve retrieval; they do not
silently reclassify a submitted project after the consumer confirms a task.

## DMV service gating

This is a product-control recommendation, not legal advice. An accountable
operator and qualified DMV counsel must approve the actual launch matrix.

| Jurisdiction | Public evidence | Workdoe control |
| --- | --- | --- |
| District of Columbia | DLCP states that business activity in the District requires the license appropriate to the activity. Its contractor page lists insurance, contract, registration, tax, criminal-history, bond, and salesperson requirements for home-improvement contracting. | Require jurisdiction-specific business and trade evidence before activating remodeling, property alteration, electrical, plumbing, HVAC, roofing, structural, or similar service-zone pairs. |
| Maryland | MHIC licenses and regulates residential alteration, remodeling, repair, and replacement. Maryland states that only MHIC-licensed contractors may contract directly with homeowners for covered home improvements. | Fail closed for covered residential home-improvement work until MHIC status and required evidence are reviewed and current. Keep project value and scope visible to the operator. |
| Virginia | DPOR contractor licenses combine a class, based on project/annual value, with a classification or specialty. Virginia law also calls for master-tradesman licensure for electrical, plumbing, and HVAC contractors. | Capture project value band, specialty, license class/number, expiration, and evidence status; eligibility must be determined before semantic ranking. |

Low-complexity pilot services still need business, insurance, safety, disposal,
vehicle, employment-classification, and local-rule review. Calling a service
"cleaning" or "moving" does not make every possible scope low risk.

### Authentication

- Sign-in and account creation already open in a same-origin modal iframe when
  launched from the marketplace.
- Embedded pages should not repeat a second page title and shortcut navigation
  beneath the dialog title.
- Embedded project posting likewise removes its duplicate page introduction;
  the dialog title and active composer step remain, with direct-access pages
  retaining their full context.
- Production should use Clerk email-code authentication on `workdoe.com`.
  Workdoe should store marketplace records in D1, not in Clerk session claims.

## Trust and safety design

### Required before a public commercial launch

- Verify service-specific DMV license, registration, insurance, and permitted
  scope requirements with qualified counsel and an accountable operator.
- Fail closed for service-zone pairs without approved evidence and sufficient
  contractor supply.
- Validate Turnstile tokens server-side and enforce route-specific rate limits.
- Preserve exact-address and contact privacy until a mini bid is approved.
- Re-encode uploads before private R2 storage and serve them only through
  permission-checked routes.
- Keep append-only moderation and automation audit records.
- Publish terms, privacy, prohibited-work, safety, incident response, refund,
  and complaint paths that match actual operations.
- Complete a production-domain Clerk, email delivery, D1 migration, R2 access,
  CSP, HTTPS, backup/export, and rollback exercise.

### Login safeguards

- Use one-time email codes as the default and keep one role per beta account.
- Apply resend cooldowns, attempt limits, generic error messages, and recent
  authentication for account security changes.
- Keep the modal on the Workdoe origin. Any Clerk-hosted network calls must be
  covered by the production CSP and configured Workdoe frontend API/proxy.
- Consider passkeys only after the production domain and recovery path are
  tested; do not make them a beta launch dependency.

## Cloudflare data and automation model

### System of record

- D1: accounts-to-profile mapping, roles, jobs, canonical taxonomy, zones,
  bids, matches, messages, outcomes, reports, moderation, and audit events.
- R2: private profile and job media after bounded decode/re-encode.
- Clerk: identity verification and sessions only.
- Turnstile plus WAF/rate limiting: complementary abuse controls.
- Queues: transactional email and single-step background delivery.
- Workflows: only for durable multi-step operations requiring retries and
  resumable state.

### Search and vectors

The commercial pilot does not need embeddings to bucket work. Canonical
service family, service slug, city/ZIP bucket, status, desired date, budget
band, and controlled scope answers are structured fields and belong in D1.

Vectorize or Cloudflare AI Search may be added later for:

- semantic recall when a contractor searches natural-language descriptions;
- typo-tolerant suggestions for the project composer;
- finding related prior project descriptions for operator analysis.

Vectors must not decide account eligibility, licensing, moderation, exact
location access, bid approval, paid placement, or the source-of-truth category.
Store the selected canonical values and model/version metadata separately from
any embedding. A deterministic filter should produce an eligible set before
semantic relevance is considered.

## Commercial model recommendation

### Pilot

- Free for consumers and contractors.
- No paid ranking, lead resale, subscription requirement, escrow, or payment
  handling.
- Measure valid posted projects, qualified supply per service-zone pair,
  response time, mini-bid rate, approval rate, mutual completion, repeat work,
  reports, and support cost.

### Earliest responsible revenue experiments

1. Optional contractor membership for operational tools that do not change
   eligibility or organic order.
2. A plainly disclosed fixed success fee only on a verified booking or
   mutually confirmed completion, after payment and refund operations exist.
3. Clearly labeled sponsorship outside the fair bid set, only after organic
   marketplace liquidity is healthy.

The Uber lesson to borrow is not surge pricing. It is that the marketplace
must state how matching and economics work, balance both sides, and preserve
choice. For Workdoe that means showing the contractor the project scope,
coarse location, timing, budget signal, bid window, and any fee before a bid is
sent. Consumers should see the bid range, assumptions, timeline, evidence, and
the final platform fee before approval.

Before any transaction fee, Workdoe still needs booking records, cancellations,
receipts, payment authorization, refunds, chargebacks, tax/accounting treatment,
support ownership, dispute evidence, and a written contractor earnings view.
Until those exist, the free lead-board pilot is the honest commercial model.

Do not start with pay-per-lead. Google and Angi can support that model because
they operate lead validation, credits/disputes, budgets, screening, and mature
supply systems. Workdoe first needs its own outcome evidence and support
capacity.

## Pilot scorecard

Evaluate by service family, jurisdiction, and week:

- eligible contractors available;
- live project count and valid-post rate;
- median time to first qualified mini bid;
- projects receiving two or more qualified bids;
- consumer approval rate;
- mutually confirmed completion rate;
- repeat invitation and repeat bid rate;
- report rate and median moderation resolution time;
- email code request-to-verification conversion;
- support contacts per posted project.

Do not optimize raw signups, map clicks, message volume, or lead views without
the corresponding quality and outcome measures.

## Launch recommendation

The UX and deterministic data model support a controlled DMV pilot. They do not
by themselves prove readiness for an unrestricted commercial launch. Public
launch remains gated by live production evidence for authentication, email,
Cloudflare bindings, domain security, service-zone compliance, moderation
staffing, backups, incident response, and real-user acceptance testing.

## Live production evidence on 2026-08-21

A read-only production smoke test confirmed:

- `https://workdoe.com/` responds over HTTPS with HTTP 200;
- apex and `www` DNS resolve through Cloudflare;
- the public jobs API responds and returned visible map leads;
- entry-page security headers and the social-share image are present;
- Clerk assets are reachable through the Workdoe same-domain proxy.

The currently deployed version is not a commercial launch candidate because:

- `/health` reports the `write_rate_limiter` binding missing;
- `/safety`, `/privacy`, and `/terms` return HTTP 404 in production even though
  the current codebase implements them;
- production sign-in does not use a Clerk live instance;
- sanitized Cloudflare secret evidence is missing `CLERK_WEBHOOK_SECRET`;
- Clerk domain/proxy configuration proof has not been recorded;
- Cloudflare Images Paid and valid/invalid live upload behavior are not proven;
- `admin@workdoe.com` has not been proven to be a monitored operating inbox.

These are deploy/configuration and operating gates, not reasons to weaken the
product requirements. Do not deploy around them. Produce the evidence, run the
strict readiness check, deploy once, and repeat the production smoke suite.

## Follow-up decisions: taxonomy, game mechanics, and monetization

The six-lane model is broad enough for the DMV pilot and maps cleanly to the
public service directories reviewed. Taskrabbit and Thumbtack both surface
high-frequency work such as cleaning, handyman work, moving, lawn care,
mounting, appliance repair, and painting. Workdoe should keep its own wording,
interaction design, ranking, and implementation; the research is category and
workflow evidence, not a source of copied code or branded copy.

Use the six numbered lanes as progressive disclosure, not a points economy.
The useful game loop is: choose a lane, choose a task, complete a six-step
brief, receive qualified bids, confirm the work, and make repeat hiring easier.
The implemented completion points are presentation-only milestones inside that
loop; they are not currency, eligibility, pricing, or rank.
Avoid streaks, loot-like rewards, urgency counters, or payment/ranking mechanics
that pressure consumers or encourage contractors to bid indiscriminately.

Store `service_group_slug`, `service_slug`, structured scope answers, location
zone, and credential requirements as deterministic D1 fields. Recall aliases
handle everyday terms such as `grass cutting`, `gardening`, `movers`, and
`kitchen renovation`. Do not use embeddings to decide licensing, visibility,
moderation, or contractor eligibility. Cloudflare Vectorize can be evaluated
later for semantic recall only after D1 has filtered the candidate set by
status, service zone, active service, and required credentials.

Uber's public filings and marketplace materials support a reliability lesson,
not a pricing template: liquidity, completion, transparent earnings, and
repeatable operations matter more than raw lead volume. The pilot should remain
free while those outcomes are measured. A later fixed success fee is safer to
test than pay-per-lead, but only after marketplace payments, refunds,
chargebacks, contractor onboarding, tax reporting, and support operations have
owners and production evidence. Stripe Connect documents these obligations;
adding a payment button alone does not create a production payment operation.

Three additional commercial controls are required before public monetization:

1. enforce service and jurisdiction activation against DC, Maryland, and
   Virginia licensing rules rather than relying on profile claims;
2. permit feedback only from verified matches and prohibit review suppression,
   incentives conditioned on sentiment, and undisclosed generated reviews;
3. have counsel review worker-classification facts and the platform's degree of
   control before introducing prices, dispatch behavior, penalties, or required
   availability.

## Public and official sources

- Thumbtack Instant Book:
  https://press.thumbtack.com/announcements/thumbtack-launches-instant-book-to-make-hiring-pros-even-easier/
- Thumbtack Instant Results:
  https://press.thumbtack.com/announcements/thumbtack-transforms-how-customers-shop-for-local-services-with-instant-results/
- Thumbtack 2024 fact sheet:
  https://press.thumbtack.com/wp-content/uploads/2024/05/Thumbtack-2024-Fact-Sheet.pdf
- Craigslist posting flow:
  https://www.craigslist.org/about/help/posting/create
- Angi public investor metrics:
  https://ir.angi.com/static-files/ae683376-8a82-4524-bcbd-d409c35807f4
- Taskrabbit task categories:
  https://www.taskrabbit.com/services
- Taskrabbit fee explanation:
  https://support.taskrabbit.com/hc/en-us/articles/46260407116955-I-d-Like-To-Understand-The-Fees-On-My-Task-s-Invoice
- Taskrabbit trust and safety:
  https://support.taskrabbit.com/hc/en-us/articles/46260491906203-Overview-of-Trust-and-Safety
- Nextdoor local business products:
  https://business.nextdoor.com/en-us/local-1
- Nextdoor Neighborhood Faves:
  https://business.nextdoor.com/en-us/small-business/neighborhood-faves
- Google Local Services categories and controls:
  https://support.google.com/localservices/answer/6224841?hl=en
- Google Local Services lead charging:
  https://support.google.com/localservices/answer/7195435?hl=en
- Google Local Services requirements:
  https://support.google.com/localservices/answer/6245891?hl=en
- Google Local Services screening and verification:
  https://support.google.com/localservices/answer/12174778?hl=en
- Google Local Services job types and service areas:
  https://support.google.com/localservices/answer/12491364?hl=en
- Bark lead screening:
  https://help.bark.com/hc/en-us/articles/26980550854940-How-Bark-screens-your-leads
- Porch professional network:
  https://pro.porch.com/how-it-works/porch-pro-network
- Homes.com agent discovery:
  https://www.homes.com/support/2022/07/18/how-do-i-find-an-agent/
- Uber Marketplace principles:
  https://www.uber.com/us/en/marketplace/principles/
- Uber Driver app and Trip Radar:
  https://www.uber.com/us/en/drive/driver-app/
- Uber service-fee explanation:
  https://www.uber.com/us/en/marketplace/pricing/service-fee/
- Uber 2025 annual report filed with the SEC:
  https://www.sec.gov/Archives/edgar/data/1543151/000155278126000148/e26089_uber-ars.pdf
- Stripe Connect pricing and marketplace features:
  https://stripe.com/connect/pricing
  https://stripe.com/connect/features
- FTC Consumer Reviews and Testimonials Rule Q&A:
  https://www.ftc.gov/business-guidance/resources/consumer-reviews-testimonials-rule-questions-answers
- U.S. Department of Labor independent-contractor rule announcement:
  https://www.dol.gov/newsroom/releases/whd/whd20240109-1
- O*NET licensing and database downloads:
  https://www.onetcenter.org/license_agreements.html
  https://www.onetcenter.org/database.html
- U.S. BLS grounds-maintenance duties:
  https://www.bls.gov/ooh/building-and-grounds-cleaning/grounds-maintenance-workers.htm
- U.S. BLS construction laborers and helpers:
  https://www.bls.gov/ooh/construction-and-extraction/construction-laborers-and-helpers.htm
- DC business licensing:
  https://dlcp.dc.gov/service/business-licensing-division
- DC contractor and construction services:
  https://dlcp.dc.gov/node/1618551
- Maryland Home Improvement Commission:
  https://www.labor.maryland.gov/license/mhic/
- Virginia Board for Contractors:
  https://www.dpor.virginia.gov/Boards/Contractors/
- Virginia contractor definitions and value thresholds:
  https://law.lis.virginia.gov/vacodefull/title54.1/chapter11/article1/
- Uber H3 source, Apache-2.0:
  https://github.com/uber/h3
- USWDS step indicator:
  https://designsystem.digital.gov/components/step-indicator/
- USWDS select guidance and accessibility tests:
  https://designsystem.digital.gov/components/select/
  https://designsystem.digital.gov/components/select/accessibility-tests/
- GOV.UK question-page pattern:
  https://design-system.service.gov.uk/patterns/question-pages/
- OWASP Authentication Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- Clerk email and SMS one-time-password flows:
  https://clerk.com/docs/guides/development/custom-flows/authentication/email-sms-otp
- Clerk JavaScript source, MIT:
  https://github.com/clerk/javascript
- Cloudflare platform storage choices:
  https://developers.cloudflare.com/learning-paths/workers/devplat/intro-to-devplat/
- Cloudflare Workers best practices:
  https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
- Cloudflare AI Search and Vectorize comparison:
  https://developers.cloudflare.com/ai-search/concepts/how-ai-search-works/
- Cloudflare Vectorize metadata filtering:
  https://developers.cloudflare.com/vectorize/reference/metadata-filtering/
- Cloudflare R2 Workers API:
  https://developers.cloudflare.com/r2/get-started/workers-api/
- Cloudflare malicious-bot controls:
  https://developers.cloudflare.com/use-cases/solutions/stop-malicious-bots/
