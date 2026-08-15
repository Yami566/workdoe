# Workdoe UX Audit

## Scope

This audit covers the public marketplace entry, consumer and contractor role choice, same-domain email-code sign-in, desktop and mobile map behavior, and the visual relationship to the existing PTOWL and Nutstracker products.

## Evidence

- `01-current-entry-desktop.png`: previous text-led entry
- `02-ptowl-reference-desktop.png`: PTOWL utility-product reference
- `03-nutstracker-reference-desktop.png`: Nutstracker compact dashboard reference
- `04-current-consumer-code-request.png`: previous consumer entry state
- `05-redesigned-map-desktop.png`: redesigned three-pane marketplace
- `06-redesigned-mobile-map.png`: mobile map state
- `07-redesigned-mobile-projects.png`: mobile project list
- `08-redesigned-mobile-auth.png`: mobile role and sign-in state

The reference and redesigned desktop captures were compared together at the same viewport. Workdoe keeps their compact hierarchy and restrained controls while putting its own list, map, and project-detail workflow first.

## Product Principles

- **Coherence:** guest and signed-in contractor views share one list, map, and detail model.
- **Adaptivity:** desktop uses a three-pane workspace; mobile uses stable Projects, Map, and Details tabs.
- **Simplicity:** open projects and approximate locations appear before explanatory copy.
- **Delight:** the deer home button, crisp live-state cues, and restrained field/dispatch language add identity without distracting from the work.

No uniquely identifiable public source for a specific “SANA UX development text” was found, so these four user-provided principles were applied directly without attributing them to an unverified publication.

## Marketplace Research Guardrails

Official public engineering and safety sources were used only for general product principles:

- Uber H3 and public engineering articles informed approximate geospatial grouping and map-first discovery. H3 is Apache-2.0 licensed, but is not needed in the MVP.
- Meta's public Marketplace engineering article informed structured listings and quality/safety signals.
- Craigslist's public safety and privacy pages informed local-first transactions, privacy, and reporting.

No marketplace code, page content, images, trade dress, confidential material, or patented implementation was copied. The subtle tactical tone uses original generic words such as “field brief,” “dispatch,” and “signal”; it does not use Metal Gear names, quotes, logos, characters, or artwork.

## Implemented Experience

- Public map with 15 realistic DMV sample projects and approximate pins
- Search, category filtering, marker clustering, deep links, and selected-project details
- Consumer and contractor role choice before account onboarding
- Clerk one-time email code flow embedded on `workdoe.com`
- D1-owned role and authorization records after Clerk verifies identity
- Responsive mobile panels and keyboard-accessible map/list interaction
- HTTPS redirect behavior, HSTS, CSP, clickjacking protection, and private exact locations

## Release Checks

The release pipeline runs unit tests, Cloudflare preflight, Worker bundle validation, a local runtime smoke test, D1 migrations, deployment, and production checks for DNS, HTTPS, security headers, the public jobs API, and the same-domain Clerk asset proxy.
