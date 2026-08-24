# Cloudflare Static-Asset Cache Evidence

Date: 2026-08-24

Status: verified locally; production confirmation remains part of the guarded
post-deployment smoke test.

## Decision

Workdoe already configures Cloudflare Workers Static Assets with
`run_worker_first: false`, so matching assets bypass the Python Worker. The
default browser response still requires freshness revalidation on every visit.
The release now uses Cloudflare's native `workdoe/static/_headers` contract to
apply one-year immutable browser caching only to assets with a safe release
boundary:

- `/styles.css`, `/map.js`, and `/project-composer.js` are requested with the
  current release token in Flask and Worker HTML.
- `/vendor/*` is pinned by path and integrity hash in
  `DEPENDENCY_PROVENANCE.json`.
- `/deer.svg` is the provenance-checked Tabler-derived home mark.

Unversioned first-party scripts such as `/worker-actions.js` retain
Cloudflare's default revalidation policy. The policy deliberately avoids a
broad immutable wildcard.

Official basis:

- [Workers Static Assets caching](https://developers.cloudflare.com/workers/static-assets/)
- [Workers Static Assets custom headers](https://developers.cloudflare.com/workers/static-assets/headers/)

## Local Runtime Evidence

Wrangler 4.125.0 parsed six valid `_headers` rules. HEAD requests against the
local Worker returned:

| Path | Cache-Control | MIME protection |
| --- | --- | --- |
| `/styles.css?v=workdoe-message-provider-v1` | `public, max-age=31556952, immutable` | `nosniff` |
| `/map.js?v=workdoe-message-provider-v1` | `public, max-age=31556952, immutable` | `nosniff` |
| `/project-composer.js?v=workdoe-message-provider-v1` | `public, max-age=31556952, immutable` | `nosniff` |
| `/vendor/leaflet/leaflet.js` | `public, max-age=31556952, immutable` | `nosniff` |
| `/deer.svg` | `public, max-age=31556952, immutable` | `nosniff` |
| `/worker-actions.js` | `public, must-revalidate, max-age=0` | `nosniff` |

Each checked static response retained its Cloudflare asset ETag. Static HEAD
requests bypassed the Worker; `/health` continued through the Python Worker.
Wrangler also returned `404` for `/_headers`, confirming the configuration file
is consumed as deployment metadata rather than exposed as a public asset.

## Guardrails

- The generated Cloudflare manifest records the `_headers` path and exact five
  immutable route patterns.
- Preflight fails if any expected route loses the policy or if an unreviewed
  route gains the immutable policy.
- The production smoke test discovers the current stylesheet URL from the live
  homepage, requires its release token, and then requires `public`, the exact
  one-year maximum age, `immutable`, and `nosniff` on the live asset response.
- Changing a versioned first-party asset still requires rotating its HTML
  release token. Changing a vendored or Tabler-derived asset still requires
  updating and reviewing the dependency provenance hash.

## Verification

- All 236 tests passed in 81.151 seconds.
- Full Ruff passed.
- The complete security and provenance gate passed across 659 non-ignored
  files with no known Python or Node vulnerabilities, no medium/high Bandit
  finding, no unreviewed secret, and no dependency drift.
- Cloudflare preflight completed without warnings or errors.
- All 34 D1 migrations and all three expected public map/photo indexes passed
  without a table scan.
- Wrangler 4.125.0 packaged 48 Python modules and read 88 static files at
  938.51 KiB / 172.35 KiB gzip in `--dry-run` mode. No deployment occurred.

## Evidence Limits

- Local Wrangler proves policy parsing and response behavior, not production
  edge propagation or repeat-visit Core Web Vitals.
- The strict production smoke must pass after deployment. A field performance
  profile still needs real traffic or an agreed controlled production test.
