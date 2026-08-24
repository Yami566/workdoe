# Workdoe DMV Competitive Research & Commercial Launch Study (2026-08-19)

## Purpose
This study is for the DMV pilot-to-commercial transition (Washington, DC / Maryland / Northern Virginia).

It focuses on 3 things:
1. What competitors do well that customers now expect.
2. What they do poorly or opaquely that Workdoe should avoid.
3. Which technical patterns are reusable from open-source/official documentation for trustworthy execution.

## Executive readout
For a local contractor marketplace, Workdoe should win on **clarity and trust-first flow**:

- fast lead posting with almost no friction,
- explicit job/canonical taxonomy before any matching,
- transparent state transitions (`Posted -> Open -> Matched -> Approved -> Active -> Closed`),
- privacy-first map exposure (`city/ZIP` + radius buckets),
- no hidden or non-obvious ranking as the default decision engine in pilot.

The market is not missing a marketplace; it is missing a marketplace that behaves like one operating system for local home-service work: fast, explicit, and safe.

## Competitor matrix (quick view)

- **Craigslist** – lowest friction posting and simple local category enforcement; minimal trust controls.
- **Angi / HomeAdvisor** – mature lead matching + contractor screening mindset; monetization through lead purchase and memberships.
- **Taskrabbit** – strong task scoping patterns + explicit trust/safety disclosures; fee model can feel opaque.
- **Porch** – contractor dashboard and lead preference controls; matching is largely contractor lead delivery.
- **Bark** – lead screening checks before delivery; manual review return flow.
- **Nextdoor** – neighborhood trust via local social context and radius controls.
- **Facebook Marketplace** – high-scale retrieval/ranking architecture, aggressive abuse mitigation focus, but less deterministic for work outcomes.
- **Google Local Services** – commercial lead flow with quality gates and account screening.
- **Tasking peers (Airtasker/B2B local task platforms)** – strong anti-spam and contact-handling guidance, often community-driven trust enforcement.

## Competitor deep-dive and lessons

### 1) Craigslist
**Signals:** posting flow requires location then category, zip map validation, image upload, draft review, publish, and optional phone verification; Craigslist also defines posting categories and local scopes explicitly.
- `services` and `posting create` pages emphasize local category-first UX and a local-only model.
- Moderation reasons publicly list `misleading`, `not local`, `personal info`, spam, and duplicate behavior.

**Borrow:**
- Keep low-friction draft flow.
- Preserve strict area/category selection.

**Avoid:**
- No trust-by-design before contact.
- No strong identity vetting or quality scoring in lead acceptance.

### 2) Angi / HomeAdvisor
**Signals:** connects homeowners with pros by service area and preferences, offers lead spend controls, and explicitly uses trust layers (codes of conduct, reviews, background checks) even if limited by implementation.

**Borrow:**
- Profile completeness, response expectations, trust rubric and explicit code-of-conduct style rules.

**Avoid:**
- Lead-buying without outcome transparency in pilot.
- Any policy where users pay per lead without clear acceptance/closure outcome signals.

### 3) Taskrabbit
**Signals:** publishes `Trust and Safety`, background checks for US taskers, `Taskprotect`, and support/dispute paths; also publishes fees and API for partner workflows.

**Borrow:**
- Multi-step task flow with estimate/availability/response states.
- Strong support and dispute workflows.
- Clear messaging that user data must be protected.

**Avoid:**
- Fee complexity in the first version (keep costs simple, explainable).

### 4) Porch
**Signals:** homepage and pro pages describe a “find local pro” matching flow, pro preferences, lead budget models, and “vetting by homeowner.”

**Borrow:**
- Preference controls (services, travel radius, availability) should be first-class.
- “Matched set size” model (expose limited, manageable candidate sets).

**Avoid:**
- Requiring homeowners to do all final vetting when we can do a first layer of Workdoe checks.

### 5) Bark
**Signals:** explicitly screens lead contact details, intent, quality, and service coverage before sending leads; low-quality entries can be reported and refunded.

**Borrow:**
- Pre-send filtering before exposing leads.
- “Report then review” quality loop.

**Avoid:**
- Purely static lead assignment without explainable filtering rules.

### 6) Nextdoor
**Signals:** business pages are local, neighborhood-bound, and posting is radius/manual neighborhood scoped.

**Borrow:**
- Use local reputation cues (trusted local context) in map list and dashboard.

**Avoid:**
- Not assuming social context alone equals reliability.

### 7) Facebook Marketplace
**Signals:** public engineering describes AI for retrieval and retrieval-plus-ranking, category/image/text auto-suggestions, and heavy abuse filtering.

**Borrow:**
- Two-stage architecture for recall + rerank when search matching becomes heavier.
- Auto-suggest as helper, not source of truth.

**Avoid:**
- Black-box ranking in launch stage.
- Product decisions that are only inferred from model outputs.

### 8) Google Local Services
**Signals:** strong location/availability model and lead lead-state lifecycle with lead quality/audit features and screening requirements (licenses, registrations, verification steps).

**Borrow:**
- Service-level lead outcomes (closed, no-show, lead return), not just lead views.
- Explicit account quality standards before reaching jobs.

**Avoid:**
- Launching pay-per-lead at scale before reliable post-lead data is stable.

## Backend/history research perspective (Uber + Meta)

You asked specifically about public history/open technical references:

- **Uber** openly documents its H3 geospatial index, created for marketplace analytics and city-scale locality optimization; it is Apache-licensed and mature.
- Uber’s algorithmic transparency materials describe large-scale matching/pricing systems and the governance model behind algorithmic decisioning.
- **Meta (Facebook)** publishes engineering work for moderation and Marketplace relevance: staged retrieval/rerank patterns and rule-driven abuse prevention.

For Workdoe, the implication is practical: use proven patterns, but keep the core logic transparent and auditable.

## What to implement for Workdoe now (commercial launch path)

### Keep as required core
1. **Deterministic taxonomy first**
   - `service_family + service_slug + geo_bucket + status + budget_band + urgency` must be mandatory for all matching and search.
2. **Map-first discovery, not contact-first**
   - keep approximate location visible (city/ZIP + radius), exact address only after match approval.
3. **State machine in dashboard**
   - every actor sees explicit job lifecycle, timestamps, and who took each action.
4. **Moderation-by-design**
   - auto-filters for duplicates, invalid contact details, low-quality jobs, banned language, suspicious post behavior.
5. **Review and outcomes capture**
   - track closure reasons for every post (`won`, `cancelled`, `spam`, `unresponsive`, `out of scope`).

### Add in phase 2 once pilot is stable
1. **Vector/embedding support** as additive relevance layer for browsing only.
2. **Vectorized profiles/jobs** for search “did-you-mean” and category completion assistance.
3. **Quality scoring model** for contractor ranking only inside the top-N candidate set.

### Launch metrics (pilot-ready)
- 48%+ of new consumer posts saved as valid `Draft -> Posted` within first session.
- Median contractor response time < 3 minutes.
- 5%+ of posted jobs move from `Posted` to `Approved` within 24h after first 2 weeks.
- `< 4%` report-to-post ratio for suspicious quality.
- `< 8%` complaints on contact/address leakage (exact address policy).

## Decision support for DMV market structure

Use the current 6-family taxonomy and prioritize:
1. Exterior + Yard
2. Cleaning + Turnover
3. Moving + Haul
4. Repairs + Installation
5. Remodel + Finish
6. Home Systems

Launch sequencing: start with categories where contractors can respond quickly with photos and clear outcomes (cleaning, moving, yard) then add complex remodeling and systems only after moderation is proven.

## Open-source and licensing posture

- We are aligned to use only explicit public documentation and source code under licenses we can track (`Apache-2.0` for H3, etc.).
- Do not copy proprietary internals from any competitor API/algorithm.
- If we draw inspiration from open research, keep it as pattern-level guidance and keep Workdoe’s matching logic fully documented in our own codebase and policy language.

## What to remove from pilot scope (important)
- No opaque global ranking.
- No hidden lead-pricing before trust metrics.
- No unbounded message opening between consumer and contractor before approval state.

## Recommended next steps for you
1. Lock the next release as **“Trust & Matching v1.0”** with deterministic matching only.
2. Add a **Lead Quality Gate** and **reason-code outcomes** to `admin` + `job detail`.
3. Add a **small competitive playbook page** in docs that maps each behavior to source-platform precedent and Workdoe adaptation.
4. Keep competitor benchmarking ongoing in this doc as we test the pilot with live DMV users.

---

## Source references

- Craigslist posting and posting removal reasons:
  - [posting create](https://www.craigslist.org/about/help/posting/create)
  - [removal reasons](https://www.craigslist.org/about/help/reasons)
  - [reference API and categories](https://www.craigslist.org/about/reference)

- Angi / HomeAdvisor public behavior and trust:
  - [Angi FAQ](https://www.angi.com/faq/what-angi)
  - [HomeAdvisor contractor workflow](https://www.homeadvisor.com/pro/how-it-works/)

- Taskrabbit support + API:
  - [trust and safety](https://support.taskrabbit.com/hc/en-us/articles/46260491906203-Overview-of-Trust-and-Safety)
  - [fee policy](https://support.taskrabbit.com/hc/en-us/articles/46260407116955-I-d-Like-To-Understand-The-Fees-On-My-Task-s-Invoice)
  - [developer API overview](https://developer.taskrabbit.com/docs/overview-taskrabbit-home-services-api)

- Bark / Porch / Nextdoor / Airtasker support behavior:
  - [Bark lead screening](https://help.bark.com/hc/en-us/articles/26980550854940-How-Bark-screens-your-leads)
  - [Porch pro network](https://pro.porch.com/how-it-works/porch-pro-network)
  - [Porch pro control flows](https://pro.porch.com/pro)
  - [Nextdoor business page](https://business.nextdoor.com/en-us/getting-started/business-page)
  - [Nextdoor business post flow](https://business.nextdoor.com/en-us/getting-started/business-post)
  - [Airtasker spam guidance](https://support.airtasker.com/hc/en-us/articles/23276292518169-How-do-I-protect-myself-against-spam-tasks)

- Facebook / Meta technical patterns:
  - [Meta: Marketplace AI](https://engineering.fb.com/2018/10/02/ml-applications/under-the-hood-facebook-marketplace-powered-by-artificial-intelligence/)
  - [Meta spam rule language approach](https://engineering.fb.com/2013/01/24/web/fighting-spam-with-pure-functions/)

- Google Local Services and search/ads model:
  - [Local Services help center](https://support.google.com/localservices/answer/6224841?hl=en-G)

- Open-source technical references used for architecture inspiration:
  - [Uber H3 repository](https://github.com/uber/h3)
  - [H3 docs](https://h3geo.org/docs/)
  - [Cadence workflow](https://raw.githubusercontent.com/cadence-workflow/cadence/master/README.md)
  - [Uber algorithmic governance (report)](https://tb-static.uber.com/prod/uber-static/uber-sites/_pdf/ai-on-uber/US-Algorithmic-Transparency-2026.pdf)
  - [Uber H3 article](https://www.uber.com/us/en/blog/h3/)
