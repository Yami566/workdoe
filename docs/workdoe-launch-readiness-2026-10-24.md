# Workdoe Launch Readiness Review

Date: 2026-10-24

Status: **controlled beta operating; not approved for unrestricted public commercial launch**.

This record supersedes the deployment-status statements in
`workdoe-stabilization-release-status-2026-08-23.md`. That earlier document is
retained as historical implementation evidence.

## Scope and method

This review checked the live `https://workdoe.com` public surface, the current
Cloudflare Worker and Flask source adapters, dependency provenance, local
automated tests, production configuration checks, and responsive browser
layouts. It does not substitute for legal advice, an incident-response drill,
or a real two-account marketplace acceptance run.

## Evidence completed

- The strict production smoke check passed for DNS, HTTP-to-HTTPS redirects on
  pages and assets, HTTPS entry, health, public jobs API, security headers,
  static cache policy, public trust pages, social-card asset, discovery files,
  Clerk production key, invitation path, and the same-origin Clerk proxy.
- A subsequent read-only live launch-doctor check reported the local smoke,
  GitHub production environment, deploy-secret readiness, ambient Wrangler
  authentication, Cloudflare release gate, DNS delegation, apex, `www`, and
  Worker custom-domain policy as ready. The subsequent strict production smoke
  again passed. This verifies the currently deployed perimeter; it does not
  deploy the local candidate or replace the workflow and operating gates below.
- A human owner completed a production consumer email-code sign-in without
  sharing the code. A subsequent browser check confirmed the same signed-in
  consumer session reached the client dashboard. A direct protected-page
  refresh briefly entered the same-domain Clerk recovery screen, then returned
  to the consumer composer without another code. This confirms the code-receipt
  and same-device consumer-session portion of the Clerk flow, but not every
  role and marketplace journey.
- A separate production browser-tab check navigated directly to `/login` with
  the existing owner-authenticated consumer session. It briefly reported
  **Checking Workdoe access...**, then reached the consumer Projects workspace
  without a second code request. This confirms the same-browser Clerk handoff
  without extracting or entering an email code; the fresh-device and
  contractor cases remain acceptance gates.
- A signed-in Clerk dashboard review confirmed that the verified
  `workdoe.com / __clerk` Frontend API proxy is enabled; email sign-up and
  sign-in use verification codes while email links are disabled; and password
  and phone sign-up/sign-in are disabled. Access mode is Open, express legal
  consent is enabled, and its Terms and Privacy URLs point to Workdoe's public
  routes. The resulting local Clerk proof records configuration decisions only,
  without any secret values.
- The currently deployed public marketplace was inspected at 390x844, 820x1180,
  and 1280x720. Its phone map/list/detail tabs were coherent, but the 820px
  deployment still carries an older desktop-width workspace and clips the
  selected detail/action. The current local release candidate was rechecked at
  all three sizes: it changes to the compact workspace before that point, keeps
  the task controls visible, and has no observed horizontal clipping. The direct
  `/jobs/new` page remains the no-JavaScript fallback; its initial action is
  below the first viewport on a short phone.
- A fresh local browser check opened `Post project` from the map as a native
  same-page dialog, selected a work family and a service through steps 1 to 3,
  and then closed the dialog. Each selection advanced without exposing later
  steps, and close returned focus to the Post project control with the map
  workspace preserved. At 390x844, the project bottom sheet keeps Back and
  Continue visible in its safe-area-aware sticky action bar. The direct
  `/jobs/new` route remained available as the non-JavaScript fallback.
- A repeat local release-candidate check of the direct, JavaScript-enhanced
  `/jobs/new` route at 390x844 showed only step 1 at load. Selecting a work
  family moved directly to step 2, selecting a listed service moved directly
  to step 3, and focus moved to the new step heading each time. The consumer
  dashboard also exposed its active, responses, paused, and history views as
  status tabs without displaying an exact project address.
- A fresh public-surface browser audit at `390x844`, `820x1180`, and
  `1280x720` found no observed overlap or clipping in the local release
  candidate. It also exercised map controls, the native post-project dialog,
  step advancement, and focus restoration, with no browser console warnings
  or errors. Its explicit scope and live-acceptance limits are recorded in
  `ux-audit/2026-10-24-public-surface/AUDIT.md`.
- Current candidate quality evidence: all 259 unit and integration tests passed
  after the production-auth guard, map date presentation,
  static-asset cache-manifest, short-desktop composer-action, and public
  dialog-entry corrections.
  JavaScript syntax checks and
  Ruff passed; Node and Python dependency vulnerability checks reported no
  known vulnerabilities; Bandit reported no medium or high findings; secret
  and dependency-provenance checks passed.
- A fresh release-candidate quality pass repeated the complete unit and
  integration suite, npm and Python dependency advisory checks, Bandit, Ruff,
  the reviewed secret baseline, and dependency provenance verification. The
  checks passed. The secret baseline now explicitly records the two official
  Clerk npm integrity values and one test-fixture key label as reviewed
  non-secrets; it remains fail-closed for any other finding.
- The repository has static accessibility-contract coverage for semantic
  controls, labels, focus styles, reduced motion, dialogs, and mobile layout
  rules. It does not currently include a browser automation or automated WCAG
  scanner, so those checks are not represented as automated visual or
  assistive-technology acceptance evidence.
- Cloudflare preflight passed without errors or warnings. The D1 plan check
  examined 36 migrations and confirmed the expected open-job geographic,
  public-media, and rolling-upload-window indexes without table scans.
- The current read-only launch diagnostic confirmed Cloudflare DNS delegation,
  the `workdoe.com` and `www` Worker route policy, the GitHub production
  environment, and the local encrypted Wrangler OAuth session. A separate
  authenticated Wrangler check generated sanitized evidence that all seven
  required Worker secret *names* are bound; it did not reveal or attest to any
  secret values. After recording the local non-secret Clerk proof, the final
  diagnostic reported no technical deployment blockers.
- The public jobs API currently exposes only sample leads and city/ZIP-level
  approximate coordinates. It did not return exact address or contact fields.
- A subsequent public browser and API audit found that the deployed
  demonstration detail still rendered a fixed August 2026 date as a requested
  date and its public API still exposed those fixture dates. The local candidate
  renders `Sample timing` and omits demo dates from public payloads; production
  smoke now requires both conditions and correctly fails on the deployed
  revision until the reviewed release is live. This is a public-presentation
  and public-contract release gate, not a perimeter failure.

## Corrections prepared locally

These corrections are verified locally but are **not deployed** by this review.

- The route-backed dialog controller now avoids reinjecting an already-ready
  Clerk or Turnstile library and removes each explicitly rendered Turnstile
  widget before clearing dialog content. This follows Cloudflare's documented
  explicit-render lifecycle and addresses the observed close-time Turnstile
  warning.
- The same-domain Clerk entry now mounts Clerk's documented `SignUp` component
  on an explicit create-account route and the documented `SignIn` component on
  an explicit sign-in route. Sign-in no longer relies on an implicit
  sign-in-or-up transfer; the existing 15-second bounded loading state and
  session-recovery action remain in place. Public checks confirm the deployed
  same-domain proxy resolves both Clerk UI and SDK assets, but the corrected
  component choice remains a local candidate until it is reviewed and deployed.
- The Clerk browser assets used by the entry and account shells are now pinned to
  reviewed `@clerk/ui` `1.41.2` and `@clerk/clerk-js` `6.40.1` packages. Their
  MIT licenses, npm integrity hashes, same-domain proxy delivery, and renderer
  use are enforced by the dependency-provenance verifier rather than trusting a
  moving major-version alias.
- The Flask adapter now returns `404` for direct password-login and
  password-reset requests whenever the Clerk provider is selected. The Worker
  email queue also rejects `password-reset` payloads. The legacy password code
  remains isolated to the local development adapter and test fixtures; the
  production auth boundary is Clerk email codes only.
- Flask and Worker public policy pages now identify Moose Bay and Company LLC,
  a Virginia limited liability company, and accurately state the owner's stated
  `admin@workdoe.com` response target of 1 to 5 business days.
- Third-party notices now match the checked dependency provenance ledger for
  Leaflet CSS, Werkzeug, and Wrangler.
- Marketplace text now rejects common email, phone, and street-address patterns
  before project, mini-bid, message, and contractor-intro storage. This is a
  local, deterministic prevention control rather than a claim that free text
  can be made universally free of personal information. The current Flask and
  Worker mini-bid guards cover scope, price range, timeline, experience,
  questions, and availability; regression tests now exercise the otherwise
  easy-to-miss price-range and timeline fields.
- Onboarding now requests one public business name or non-identifying handle,
  never derives that label from an email local-part, and does not solicit a
  separate household or organization field. The same common-disclosure guard
  covers onboarding labels, contractor profile text, private consumer workspace
  labels/notes, and saved project-area labels. This reduces accidental contact
  and address storage but cannot prove arbitrary text or images are PII-free.
- Production-media intake now limits source files to 4 MB, stores only
  sanitized 1600-pixel WebP output below 1.5 MB, limits projects to six photos,
  contractor profiles to eight, and accounts to 12 uploads per rolling 24
  hours before costly image processing begins. It now discards user-provided
  source filenames before D1, R2 metadata, headers, or UI; a forward-only D1
  migration redacts existing filename metadata at release time. The rolling
  allowance counts successful upload audit events, so deleting a photo does not
  reset it; its D1 query has a dedicated partial index.
- The public map now supports mouse-wheel zoom, a privacy-safe current-map-area
  description that never requests browser geolocation, and a DMV-view reset
  control. On compact phones, the decorative map badge is suppressed so it
  cannot overlap those controls. The static-asset release token was regenerated
  from the reviewed asset bytes.
- On direct narrow-screen composer routes, the current step's Back/Continue
  bar now remains fixed above the mobile task navigation instead of appearing
  only after the task choices. The responsive layout reserves space for that
  action bar, while the native-dialog composer keeps its existing bottom-sheet
  controls. This addresses the observed reachable-action gap without removing
  the direct no-JavaScript route.
- On short desktop windows wider than the compact breakpoint, the same
  Back/Continue bar now becomes fixed with reserved form padding. A current
  read-only 1280x720 production capture showed the old full-page route's only
  `Continue` action below the first viewport; the candidate has a regression
  assertion for that height-specific layout rule. This correction is local
  until the reviewed release is deployed and captured.
- The public marketplace header, hero, selected-work-lane action, and anonymous
  mobile navigation now mark Post project, Create account, and Sign in as
  native-dialog actions. From the map they preserve the marketplace behind the
  interaction; their ordinary canonical links remain intact for direct visits,
  browser history, and no-JavaScript fallback. Flask and Worker rendering have
  focused parity coverage for those controls.
- Worker-rendered maps no longer hard-code a tile endpoint in either the public
  or signed-in shell. `WORKDOE_MAP_TILE_URL` and
  `WORKDOE_MAP_TILE_ATTRIBUTION` are generated and preflight-validated as an
  HTTPS Leaflet template with attribution; the browser map fails safely to the
  usable project list if either value is missing. The standard OpenStreetMap
  endpoint is retained only for the controlled beta and requires operator
  traffic monitoring and a reviewed provider decision before sustained growth.
- Public demonstration records now render `Sample timing` instead of their
  fixed demonstration date, and the public API omits the fixture date from demo
  payloads; real projects retain their requested date. This prevents an old
  sample fixture from appearing to be an overdue live project in either the UI
  or an API consumer.
- Public project cards now render valid real calendar dates as readable month
  and day labels while retaining their ISO `datetime` value for machines. The
  browser map uses the same timezone-neutral formatting after filters or map
  movement refresh the selected project.
- The live launch doctor now recognizes complete sanitized secret-name evidence
  and reports `7/7` required Worker names without demanding a local API token
  that is unnecessary for that read-only evidence path.
- The deployed Worker entry-shell regression coverage now forbids a password
  field, password prompt, and reset link in the Clerk email-code entry flow.
- Clerk entry loading is bounded locally: after 15 seconds, or when the Clerk
  client cannot load, the former indefinite `Loading secure email sign-in...`
  placeholder is replaced with a clear retry message. A rejected session also
  exposes the `Use a new email code` recovery control. This correction is not
  deployed until the reviewed release gate is completed.
- The Clerk loading regression test now exercises both the returning-user
  sign-in mount and the new-account sign-up mount, requiring each to hide the
  loading placeholder once the documented Clerk component is ready.
- The controlled-beta configuration now explicitly keeps
  `WORKDOE_ENFORCE_SERVICE_ACTIVATION=false`. This aligns the runtime with the
  53-service advisory-only launch scope: policy acknowledgements still protect
  elevated and regulated services, while the retained service-zone records are
  evidence for a future approved gated rollout rather than an accidental beta
  discovery or bidding gate.
- The Flask production guard now rejects the local authentication provider and
  requires Clerk with same-domain email-code configuration. This makes the
  production identity boundary fail closed even if a future configuration
  change would otherwise re-enable the local password-capable fallback.
- Runtime provenance now separately records the Cloudflare-supplied Python
  Workers SDK used by the `workers` import. The release config deliberately
  disables any external SDK bundle, and provenance verification now fails if
  that bundled-runtime configuration or compatibility date drifts.
- A final read-only live launch diagnostic reports no technical deployment
  blockers. It confirms DNS delegation, apex and `www` resolution, custom
  domain policy, GitHub release readiness, the sanitized `7/7` secret-name
  evidence, and the completed Clerk configuration proof.
- On 2026-10-24, a fresh local Cloudflare preflight passed without warnings,
  including the migration chain, Worker compilation, production bindings,
  static-asset policy, auth boundary, media authorization, and release-script
  contract checks. The D1 query-plan check inspected 36 migrations and showed
  the expected open-job geography, public-media, and rolling-upload-window
  indexes with no table scans. A separate read-only live launch-doctor and
  strict production-smoke pass reported the deployed DNS, HTTPS redirects,
  entry security headers, public API, trust/discovery pages, static cache
  policy, Clerk production key, invitation entry, and same-domain Clerk proxy
  as ready. Those live checks do not deploy the local candidate or replace the
  workflow, media, legal, and operating gates below.

These are application safeguards, not a Cloudflare billing hard stop: accepted
or concurrent requests can still create billable operations. The owner must
retain Cloudflare usage alerts and review R2/Images usage before opening the
beta beyond its controlled cohort.

## External-service operating constraints

- The current map shell uses the OpenStreetMap standard tile endpoint with
  visible attribution, an ordinary browser referrer policy, and no tile
  prefetch or offline-download feature. This is appropriate for supervised
  interactive beta use, not an availability guarantee or a sustained-growth
  provider decision. The OSM tile policy requires attribution, normal caching,
  and an accurate web referrer, and permits the service to block harmful or
  heavy use. Review traffic before expanding the cohort and move to a provider
  with suitable terms before the map becomes a sustained commercial dependency:
  <https://operations.osmfoundation.org/policies/tiles/>.
- Public media uploads are disabled for this beta, and the Worker does not
  attach a Cloudflare Images binding. This avoids raw-image storage and an
  Images Paid dependency while the product is validated. Cloudflare's
  R2-upload transformation tutorial lists an Images Paid subscription as a
  prerequisite for its Worker binding; a future photo launch must be an
  owner-approved release with usage alerts and valid/invalid/oversize
  acceptance checks:
  <https://developers.cloudflare.com/images/tutorials/optimize-user-uploaded-image/>.

## Launch gates still open

1. **Data-minimization decision:** Email-code authentication necessarily
   processes an email address. Clerk is the primary identity provider, and the
   current D1 user mirror retains the verified email for account lookup and
   transactional operations. Do not market the beta as non-PII. Either accept
   and document that narrow PII boundary or fund a separate, forward-only
   pseudonymous-account migration with replacement operational-email flows.
2. **Legal and policy approval:** Record an approved public legal/mailing
   address and display format; obtain counsel approval for the Terms, Privacy,
   Safety, service-policy, contractor-classification, and dispute language.
3. **Data operations:** Approve a retention/deletion schedule for accounts,
   projects, messages, media, reports, audit records, and backups; perform an
   export/deletion request test; define identity verification and request logs.
4. **Incident coverage:** Document urgent safety/security escalation. A single
   monitored inbox with a 1 to 5 business-day target is appropriate for ordinary
   requests, not for time-sensitive incident response.
5. **Live marketplace acceptance:** Complete a contractor email-code test and
   one controlled two-account journey: post a city/ZIP-only project, submit
   and approve a mini bid, exchange a message, complete the project, then
   verify visibility, audit, and deletion behavior. The owner should enter all
   one-time codes and use test content only.
6. **Future media acceptance:** Before any future photo launch, exercise the
   approved sanitizer/storage path with valid, invalid, and oversize inputs;
   verify private authorization, quota/rate-limit behavior, and cleanup under
   the approved retention policy.
7. **Release acceptance:** After the preceding gates are approved, deploy the
   locally prepared dialog/policy/provenance, responsive-workspace, map-control,
   tile-provider configuration, and demonstration-timing corrections through
   the normal reviewed release process, record the deployed SHA, and rerun the
   production smoke, responsive browser, and browser-console checks. Capture
   the direct composer at 1280x720 as well as the map workspace viewports.
8. **Browser accessibility acceptance:** At the deployed release, record
   keyboard-only, reduced-motion, and screen-reader-label checks plus visual
   captures at 390x844, 820x1180, and 1280x720. The current source-level
   accessibility contract tests are useful regression coverage, but do not
   replace a browser/assistive-technology acceptance run.
## Licensing and provenance

## 2026-10-25 verification addendum

This follow-up did not deploy, push, commit, authenticate as a user, or create
marketplace data. The current local release candidate passed all 259 unit and
integration tests in 90.7 seconds. Cloudflare preflight completed with no
errors or warnings. The complete security command reported no known Node or
Python dependency vulnerabilities, no Bandit medium or high findings, a
passing secret gate across 702 non-ignored files, and passing dependency
provenance verification.

The read-only strict production smoke check still fails only for the two
demonstration-timing safeguards: the deployed public API returns fixed
`desired_date` values for `demo-01`, `demo-02`, and `demo-03`, and the deployed
sample detail does not display `Sample timing`. DNS, HTTPS redirects, health,
security headers, asset caching, public trust and discovery pages, social
preview, production Clerk key, invitation entry, and same-domain Clerk proxy
remain ready. This confirms the local correction is not yet the deployed
revision; it does not weaken or replace any open owner-controlled launch gate.

Workdoe's first-party source and assets remain proprietary. The checked
third-party dependencies are pinned with licenses, official sources, and
integrity hashes in `DEPENDENCY_PROVENANCE.json`; retained notices are in
`THIRD_PARTY_NOTICES.md`. No PTOwl or NuTs source was copied into Workdoe.
Cloudflare, Clerk, and OpenStreetMap are operational providers whose current
terms and configuration requirements remain separate from open-source
dependency licensing.

## Decision

The deployed production site is operating for a controlled owner-supervised
beta, but its currently live public marketplace predates the local responsive
and map polish fixes. Its strengthened production smoke currently fails the
demonstration-timing detail and public-API checks, so the deployed public UI
and public contract are not ready to represent as the reviewed candidate. The
local candidate has no remaining automated technical failure, but it cannot be
called ready until the reviewed release is deployed and the smoke check passes.
It is also not ready to be represented as an unrestricted commercial launch
because the legal, data-operations, incident-response, live two-role workflow,
media-acceptance, and reviewed-release gates above remain open.
