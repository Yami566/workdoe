# Workdoe Third-Party Notices

This file records the principal third-party code and data services used by the
Workdoe repository. It is not a license for Workdoe's original source code.
Machine-readable versions, source locations, licenses, and integrity values are
maintained in `DEPENDENCY_PROVENANCE.json` and checked by
`scripts/verify_dependency_provenance.py`.

## Browser-distributed code and assets

### Leaflet 1.9.4

- Purpose: interactive map rendering.
- License: BSD 2-Clause.
- Source: https://github.com/Leaflet/Leaflet/tree/v1.9.4/dist
- Retained license: `workdoe/static/vendor/leaflet/LICENSE`.
- Verification: the vendored JavaScript, CSS, and five referenced PNG assets
  are pinned by SHA-256 regression checks. The JavaScript and CSS byte hashes
  match the published `leaflet@1.9.4` npm/unpkg distribution.

### Leaflet.markercluster 1.5.3

- Purpose: clustering nearby project markers.
- License: MIT.
- Source: https://github.com/Leaflet/Leaflet.markercluster/tree/v1.5.3
- Retained license: `workdoe/static/vendor/leaflet-markercluster/LICENSE`.
- Verification: the vendored JavaScript and both CSS files are pinned by
  SHA-256 regression checks and match the published
  `leaflet.markercluster@1.5.3` npm/unpkg distribution byte for byte.

### Tabler Icons 3.46.0

- Purpose: the deer icon used in Workdoe's logo, six service-family icons,
  the task-level icons used by the guided project picker, and the dialog close
  icon.
- License: MIT.
- Source: https://github.com/tabler/tabler-icons/blob/v3.46.0/icons/outline/deer.svg
- Picker icon sources:
  https://github.com/tabler/tabler-icons/tree/v3.46.0/icons/outline
- Package: `@tabler/icons@3.46.0`, npm integrity
  `sha512-f2RYFl3fzPwj5WO82x6en0dmkjefxEfOm16D1ByM6cj/McNiwOkL4VaPUoP9VVIrXAD9WnTSVFr70px703b//A==`.
- Retained license: `workdoe/static/vendor/tabler-icons/LICENSE`.
- Verification: the deer path values, family icons, and 50-file task icon set
  are pinned by SHA-256 regression checks. The task SVG files were copied from
  the published npm package without modification. Workdoe changes only
  presentation and accessibility metadata around the upstream deer geometry.
- Workdoe's branding, colors, typography, and layout are original to this
  project; the notice covers the Tabler deer icon geometry only.

## Reproducibility evidence

The following SHA-256 values were rechecked against the pinned public package
artifacts on 2026-08-16. The test suite enforces the same values locally.

| Artifact | SHA-256 |
| --- | --- |
| Leaflet `leaflet.js` | `db49d009c841f5ca34a888c96511ae936fd9f5533e90d8b2c4d57596f4e5641a` |
| Leaflet `leaflet.css` | `a7837102824184820dfa198d1ebcd109ff6d0ff9a2672a074b9a1b4d147d04c6` |
| Markercluster `leaflet.markercluster.js` | `1e4e1d22972a3926f48598e0caf14e3fe7049835d428a344fed4f9e3665b3508` |
| Markercluster `MarkerCluster.css` | `614dea0a98ff3f4ead74f04918f6b1d1b9ba435c25b5fc23b21a394d1e3e4d87` |
| Markercluster `MarkerCluster.Default.css` | `61258232d98d64dc2a7b1e02130d67421bc5b9bda5994eef70228ff97570c170` |
| Tabler deer path geometry | `e42e5123145fcad4bf5a1b198bec2f5c10a58d05bc099d52703f496c313b79a4` |
| Tabler `trees.svg` | `9ffc31bb059b649d3995bd396f3d0f3ec59e531ffa559072a2ee6d12f5446ba0` |
| Tabler `spray.svg` | `bbd7c65c9e4f58f98bb8a7bc8ebfe38b4d12322576d224a22f9df8aca0efd6a9` |
| Tabler `truck-delivery.svg` | `6e83c8b78ef626b5326a0d27f97cb900a7ad99fc789dc64c696f7a6761dd2628` |
| Tabler `tools.svg` | `aac6ae77bd7d24d3819ed1ccc7262ca1b57444b541fc3dc90ee837bbbe6a6e7c` |
| Tabler `paint.svg` | `ab2b5b985830a0a673c0399b94420ecc7b477dc828509049d16d51eefc57672e` |
| Tabler `bolt.svg` | `f18f1b4476d1f1ba018219131fee671f2a7ac286c9eb3aa83ea72274e17f34e5` |
| Tabler `x.svg` | `c0ef7bfcae8b25bff75d060ec437054e2288af16d301e4d1ef5fb805666afc44` |
| Tabler task-icon manifest (50 files) | `b52f6c73b3afb6b19df964190046fd51748cce40d15c090054909f7007e8fcfe` |

### Clerk JavaScript SDK and UI

- Purpose: maintained same-domain authentication and account components in the production shell.
- License: MIT for the open-source JavaScript SDK and UI packages.
- Source: https://github.com/clerk/javascript
- The Clerk hosted service is a third-party SaaS dependency governed by the
  account's service agreement and privacy/data-processing terms, not by the
  SDK's MIT license.

## Local and deployment tooling

### Flask 3.1.3

- Purpose: local reference application and local prototype tests.
- License: BSD 3-Clause.
- Source: https://github.com/pallets/flask/releases/tag/3.1.3
- Flask and its complete local runtime dependency set are exactly pinned in
  `requirements.txt`: Werkzeug 3.1.8, Jinja2 3.1.6, itsdangerous 2.2.0,
  click 8.4.2, blinker 1.9.0, and MarkupSafe 3.0.3.
- These packages are installed from PyPI; they are not vendored into this
  repository and are not part of the Cloudflare production Worker bundle.
- The packages use BSD 3-Clause licenses except blinker, which uses MIT.
  Source-archive SHA-256 values and official PyPI pages are recorded in the
  dependency provenance ledger.

### Wrangler 4.123.0

- Purpose: Cloudflare Worker validation and deployment tooling.
- License: MIT OR Apache-2.0.
- Source: https://github.com/cloudflare/workers-sdk
- Wrangler is a development dependency. `node_modules` is ignored and is not
  served to Workdoe visitors. Package-specific license and integrity metadata
  is retained in `package-lock.json` and the dependency provenance ledger.

### Local security audit tools

- `pip-audit` 2.9.0, Bandit 1.8.6, `detect-secrets` 1.5.0, and Ruff 0.16.4 are
  pinned in `requirements-audit.txt` for local release verification.
- `pip-audit`, Bandit, and `detect-secrets` are distributed under the Apache
  License 2.0. Ruff is distributed under the MIT License. Their installed
  package distributions retain the full license text.
- These tools are development-only and are not included in the deployed
  Cloudflare Worker or browser assets.

## Map data and hosted services

Workdoe displays OpenStreetMap map data and tiles. OpenStreetMap attribution is
visible in the map UI. OpenStreetMap data is available under the Open Data
Commons Open Database License; the tile service is also subject to the
OpenStreetMap Foundation tile usage policy.

Cloudflare Workers, D1, R2, Email, Queues, Turnstile, DNS, and CDN are hosted
services. Their service terms are separate from the licenses of source code in
this repository.

## Workdoe first-party source

Workdoe's first-party source code, product copy, visual design, and original
assets are proprietary and are governed by the top-level `LICENSE`. The
repository and first-party product must not be described as open source.
Third-party components remain governed by the licenses and notices identified
in this file and `DEPENDENCY_PROVENANCE.json`.
