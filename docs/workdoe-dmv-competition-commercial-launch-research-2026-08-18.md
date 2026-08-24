# Workdoe DMV Commercial Launch Research Study

Date: 2026-08-18  
Owner: Workdoe planning thread

## Focus

Create a DMV pilot that is commercially launchable and operationally safe without being feature-heavy:

- Consumer: post jobs fast and discover relevant jobs immediately.
- Contractor: apply quickly and win only relevant jobs.
- Platform: trustworthy matching, map-first visibility, and transparent state transitions.
- Security and trust: simple authentication, safe location privacy, active moderation.

## Executive takeaway

For launch, Workdoe should not emulate lead-auction behavior from incumbents.  
The MVP edge is **clarity + control**:

- explicit `Posted -> Matched -> Approved -> Completed` states,
- clear job-state transitions,
- no hidden bidding logic in pilot,
- no public exact addresses by default,
- one-site sign-in flow that does not move users between routes.

## Competition matrix (high-signal findings)

| Platform | Positioning | Useful pattern to borrow | What to avoid in pilot |
|---|---|---|---|
| Thumbtack | Home project sourcing and lead marketplace | Broad service families and clear project framing | Pay ambiguity before trust and completion signals are stable |
| Angi / HomeAdvisor | Lead routing and directory + managed channels | Review safeguards and pro screening concepts | Complex mixed monetization in early-stage trust model |
| Taskrabbit | Short-task labor market | Rich task categories and fast posting behavior | Overfitting all jobs into fixed hourly tasks |
| Craigslist | Very low barrier classifieds model | Immediate low-friction posting and local discovery | Weak trust architecture and limited abuse controls |
| Nextdoor | Local trust/social context | Location-first discovery and social shareability | Assuming community familiarity replaces verification |
| Google Local Services | Paid lead bidding model | Ad/quality mix and bid control surface | Per-lead pricing pressure too early for unknown quality |

### Why these matter for Workdoe

1. Users want speed (Craigslist-like), but they now also expect quality signals (Angi/Taskrabbit/Google-like).
2. Launch should keep monetization separate from core trust mechanics.
3. Contractor history and consumer confidence must be built from completion, not promises.

## Manual labor demand model (what jobs to support first)

From public category listings, the highest-utility first phase categories are:

- Moving and packing support
  - includes moving help, heavy lifting, furniture moving, junk pickup
- Cleaning
  - includes move-out/cleaning, one-time and periodic cleaning
- Landscaping / exterior work
  - mowing, gardening, leaf cleanup, pressure washing, yard maintenance
- Home repairs and improvements
  - minor repairs, painting, assembly, appliance-related handyman scopes
- Kitchen/bath support and remodeling-adjacent installs
  - focused on scoped and bounded jobs (not huge full-project contracting)

This aligns directly with:
- Taskrabbit category breadth (moving + cleaning + assembly + household help),
- Angi/Handy style task families with practical service clusters,
- and DMV demand for recurring household and local-service jobs.

## Gamified posting: 1–2–3–4–5–6 category flow

User asked for simpler selection and category iconing. Proposed structure:

1. **Family icon** (Move, Clean, Exterior, Repair, Remodel, Other)
2. **What do you need done?** (short chips, 3–6 options)
3. **Budget band** (optional in step 1, required for contractor triage)
4. **Map marker** (coarse city/ZIP pin)
5. **When needed** (time window + urgency)
6. **Photo + finalize**

Recommended UX:

- Display progress (“3 of 6”).
- Keep one-click fast path for repeat users.
- Keep a “simple mode” and “pro mode” for detailed posting.
- Include icon legends so category choice is visual and quick.

## Category + clustering plan (no black-box behavior)

Use authoritative taxonomy first, then optional embedding support later:

- `service_family` (coarse family): Move / Clean / Exterior / Repair / Remodel / Other
- `service_slug` (exact intent): e.g. lawn mowing, junk removal, cabinet refinish
- `geo_bucket`: coarse H3 bucket for map clustering
- `suggested_slug`: advisory AI classification score (optional, never silent)

Implementation rule: AI suggestions are advisory and always user-editable.

For map safety, use coarse geospatial grouping (for example H3 index or equivalent) so jobs are visible without exact addresses before approval.

## Login + safety (the first commercial reliability stack)

Requirements:

- one login surface that opens inside current page (modal or panel),
- email one-time passcode as primary method,
- optional secondary credential path after trust baseline,
- strict route-level checks for protected operations,
- OTP abuse and bot throttling.

Clerk is suitable for a quick and safer rollout path because it supports hosted sign-in workflows and can be kept in-app.  
Cloudflare-native alternatives remain possible if you want fewer external auth dependencies.

## Open-source and compliance posture

Use external code only from audited public sources and official docs.

Strong, appropriate options:

- Map: Leaflet + OpenStreetMap tiles (map stack already proven and lightweight).
- Geospatial clustering: H3 for deterministic tile-like grouping.
- Optional clustering utility: Supercluster for point clustering.
- Database/infra: Cloudflare D1, R2, Workers runtime limits awareness.

Open source is not “unlicensed” code; it is licensed code:
- include license notices,
- preserve notices in releases,
- avoid copying competitor workflows/text.

## P0 launch gates (required before commercial open launch)

1. One-site sign-in (no cross-route auth hops), with OTP first-class flow.
2. Explicit job state machine visible to both users.
3. Public map pins are privacy-safe by default (no full address).
4. Report + moderation queue with rollback actions.
5. Contractor review status and consumer completion indicators.
6. Audit logs for profile edits, job edits, status transitions, and report actions.

## P1 launch gates (post-pilot stabilization)

1. Contractor profile verification labels by source (ID/phone/email/business docs).
2. Repeat-job history for both roles.
3. Abuse analytics (suspicious account and message behavior).
4. SLA dashboards: response times, completion conversion, no-show rate.

## P2 monetization gates (only after stable quality)

1. Introduce paid contractor visibility only after baseline trust metrics are stable.
2. Add clear per-unit pricing before any paid traffic product.
3. Add billing and refund policy linked to job lifecycle outcomes.

## DMV rollout strategy

Lane priority:

1. Exterior / cleaning cluster  
2. Moving and packing cluster  
3. Basic repairs + assembly cluster  
4. Light remodeling support (kitchen/bath support items)  

Target for each lane:

- completion-to-approval ratio,
- median time-to-first-response,
- no-show rate,
- report rate per 100 jobs,
- first-job-to-repeat job ratio.

## Current status against goal

**Not fully launch-ready for unrestricted monetized commercial release yet.**

Research and planning are complete enough to move into controlled pilot execution, but risk remains around:
- production OTP reliability,
- moderation load and rollback workflows,
- consistent privacy enforcement on all public job views.

## Open sources used

- [Taskrabbit services list](https://www.taskrabbit.com/services)
- [Taskrabbit category scope and task types](https://support.taskrabbit.com/hc/en-ca/articles/46260534390555-What-Types-of-Tasks-Can-I-Do-as-a-Tasker)
- [Taskrabbit fee model](https://support.taskrabbit.com/hc/en-us/articles/46260407116955-I-d-Like-To-Understand-The-Fees-On-My-Task-s-Invoice)
- [Angi FAQ](https://www.angi.com/faq.htm)
- [Angi request workflow and fees](https://www.angi.com/landing/faq)
- [HomeAdvisor how it works](https://www.homeadvisor.com/spa/how-it-works)
- [Angi instant connect process](https://pro.homeadvisor.com/articles/videos/instant-connect)
- [Handy/Angi service categories list](https://orders.angi.com/services)
- [Nextdoor business directory categories](https://us.nextdoor.com/directories/)
- [Craigslist services section](https://www.craigslist.org/about/help/services)
- [Craigslist posting type list](https://www.craigslist.org/about/help/posting/features/type)
- [Craigslist fees](https://www.craigslist.org/about/help/posting_fees)
- [Craigslist reference categories/types](https://www.craigslist.org/about/reference)
- [Uber marketplace principles](https://www.uber.com/us/en/marketplace/principles/)
- [Uber algorithm transparency report](https://tb-static.uber.com/prod/uber-static/uber-sites/_pdf/ai-on-uber/US-Algorithmic-Transparency-2026.pdf)
- [Google Local Services bidding model](https://support.google.com/localservices/answer/10125017?hl=en)
- [Leaflet docs](https://leafletjs.com/)
- [Leaflet license](https://raw.githubusercontent.com/Leaflet/Leaflet/main/LICENSE)
- [Supercluster license](https://raw.githubusercontent.com/mapbox/supercluster/main/LICENSE)
- [H3 overview](https://h3geo.org/docs/)
- [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Cloudflare D1](https://developers.cloudflare.com/d1/)
- [Cloudflare Vectorize](https://developers.cloudflare.com/vectorize/)
- [Clerk authentication workflow](https://clerk.com/docs/guides/how-clerk-works/overview)
- [Cloudflare Email Routing](https://developers.cloudflare.com/email-routing/)
- [OpenStreetMap privacy](https://www.openstreetmap.org/about/privacy)

## Backend and architecture sources review (open and official)

To keep this commercial launch study aligned to auditability, here are sources that are clearly public and suitable as reference for implementation direction:

- **Marketplace matching and balancing:** Uber publicly documents that matching is a city-scale optimization problem with batched/collective matching rather than nearest-only assignment, and that location and ETA models are key inputs.
  - [Uber matching overview](https://www.uber.com/us/en/marketplace/matching/)
  - [Uber algorithm transparency report](https://tb-static.uber.com/prod/uber-static/uber-sites/_pdf/ai-on-uber/Algorithmic_Transparency_7.pdf)
  - [Uber reinforcement-learning matching blog](https://www.uber.com/au/en/blog/reinforcement-learning-for-modeling-marketplace-balance/)
- **Open geospatial and retrieval tooling used in modern marketplaces:** Uber’s own geospatial project H3 is Apache-licensed and documented.
  - [H3 docs](https://h3geo.org/docs/)
  - [H3 GitHub repository](https://github.com/uber/h3)
  - [FAISS similarity search (Meta)](https://github.com/facebookresearch/faiss/wiki)
  - [Duckling date/time parser (Meta)](https://github.com/facebook/duckling)
- **Taskrabbit API and partner architecture:** Taskrabbit exposes public API documentation for service availability and pricing estimates, and confirms OAuth2 + endpoint-based integration.
  - [Taskrabbit project estimate API guide](https://developer.taskrabbit.com/docs/project-estimate)
  - [Taskrabbit estimate endpoint reference](https://developer.taskrabbit.com/reference/projectestimate)
  - [Taskrabbit trust-and-safety overview](https://support.taskrabbit.com/hc/en-gb/articles/46260491906203-Overview-of-Trust-and-Safety)
- **Craigslist posting flow and verification:** Public help content confirms low-friction posting, required location/category selection, and email/phone verification before publish.
  - [Craigslist posting flow](https://www.craigslist.org/about/help/posting/create)
  - [Craigslist posting verification](https://www.craigslist.org/about/help/posting/verify)
  - [Craigslist posting fees](https://www.craigslist.org/about/help/posting_fees)
- **Facebook Marketplace product intelligence patterns:** Meta’s engineering article shows AI multimodal indexing/ranking, auto category suggestions, and similarity search for discovery, but not private backend schemas.
  - [Facebook Marketplace is powered by AI](https://engineering.fb.com/2018/10/02/ml-applications/under-the-hood-facebook-marketplace-powered-by-artificial-intelligence/)
- **Local discovery/community channels:** Nextdoor’s official business-page flow and posting controls illustrate neighborhood radius/audience mechanics useful for contractor visibility decisions.
  - [Nextdoor business page setup](https://business.nextdoor.com/en-us/getting-started/business-page)

### What is not directly open-sourced (important)

For this launch plan, the following must be treated as non-copyable unless public APIs or official source are explicitly provided:

- Angi/HomeAdvisor internal lead scoring and routing internals.
- Thumbtack backend models and ranking pipelines.
- Facebook/Instagram commercial matching internals outside published AI overviews.
- Google/Meta local lead adjudication and fraud models.

This is not a blocker for the DMV launch, but it means Workdoe should avoid trying to imitate those black-box systems. We should build explicit, auditable product logic first, then add advanced optimization only when we can measure business impact.

## Competition-to-launch implications for Workdoe

### What to adopt quickly

1. **Speed + low friction at first touch**
   - Keep the current six-step post flow and map/list first experience.
   - Use Craigslist-like immediate draft creation and publish timing to reduce abandonment.
2. **Clear market-fit matching gate**
   - Keep deterministic taxonomy (family + service slug) as the first routing layer.
   - Do not rely on hidden text embeddings as a source of truth before consent and completion.
3. **Visibility controls before trust**
   - Preserve coarse map pins, no public street address, no direct contact until approved.
   - Expose only allowed profile fields until a match reaches approved and active status.
4. **Bid quality over volume**
   - Keep one-to-few contractor response behavior now, with explicit bid deadline and one clear approval path.
   - Match Taskrabbit’s bounded-worker model and Airtasker-like bid review, not broad lead dumping.
5. **Rate and availability logic**
   - Use explicit optional budget band + timeline as signals.
   - Use these in sorting and alerts before more complex optimization.

### What to phase in later

1. **Pre-qualification and service guarantees**
   - Introduce license checks, references, and service completion proof only after we can prove moderation throughput.
2. **Monetization**
   - No per-lead pay during pilot.
   - Introduce premium contractor features only after measurable completion quality and repeat conversion.
3. **Advanced ranking**
   - Add semantic ranking (vector search / embedding) only as an optional ranking layer, never as the canonical filter.
4. **Algorithmic balancing**
   - Hold off on RL-style balancing until demand/supply data is sufficient and quality outcomes are protected by robust rollback and audit.

### Open-source and legal posture (DMV commercial)

- Continue to treat every open-source dependency as vendored by license and notice, with pinned versions and explicit provenance tracking.
- Do **not** claim the app is open source unless a top-level license is selected.
- For any third-party competitor behavior we emulate, mirror only *flows and product principles*, not proprietary copy.

### New commercial readiness checks before DMV commercial launch

1. Prove a real contractor acceptance flow end-to-end with two test production accounts: post -> mini-bid -> approval -> private messaging -> completion note.
2. Verify all public job views mask exact addresses by default and include location radius policy in two explicit copy states.
3. Validate OTP flow under rate limits and abuse attempts with clear cooldown and replay protection.
4. Confirm moderation and reporting actions are reversible, logged, and visible in admin controls.
5. Set category-specific launch thresholds per family (requests/week, bids/job, response time, no-show rate).
6. Build a small launch benchmark sheet:
   - target 0 days to post in 75th percentile,
   - target 3 minutes to first visible bid from a known contractor,
   - target <15% incomplete matches in first week,
   - target first-pass job privacy compliance 100%.

## Suggested launch roadmap for this study cycle

### Phase A (now, same-site MVP + docs)
- Keep one-side onboarding (consumer + contractor profiles with role lock).
- Keep 6-step composer, map/list lead board, role-aware dashboards.
- Complete policy pages and evidence artifacts.

### Phase B (2–4 weeks)
- Add reliability instrumentation for every lead state transition.
- Tighten contractor profile verification workflows (admin-reviewed fields and expiry).
- Add map and moderation guardrails for category-specific abuse.

### Phase C (4–8 weeks)
- Enable controlled invite-only billing for optional premium contractor signals (alerts, response templates).
- Expand category depth only where completion-to-approval rate sustains.
- Begin post-pilot pricing tests with explicit opt-in cohorts.

### Phase D (8+ weeks)
- Open commercial marketing in DMV once the above metrics are stable.
- Add optional paid distribution only after quality and conversion baselines hold for three full weeks.
