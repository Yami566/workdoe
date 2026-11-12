# Workdoe Documentation

Workdoe is proprietary software using reviewed, pinned third-party dependencies.
See the [repository license](../LICENSE) and [third-party notices](../THIRD_PARTY_NOTICES.md).

## Current Launch Decision

The [public release status](workdoe-public-launch-gates.md) distinguishes
local verification from hosted acceptance. A GitHub push is not a production
deployment, policy approval, license clearance or unrestricted-launch approval.

## Application Documentation

- [Product requirements](workdoe-product-requirements.md)
- [Data inventory](workdoe-data-inventory.md)
- [Design provenance](workdoe-design-provenance.md)
- [Cloudflare migration](cloudflare-migration.md)
- [Authentication and automation](cloudflare-automation-auth.md)
- [Operations runbook](workdoe-operations-runbook.md)
- [Owner acceptance checklist](workdoe-owner-live-acceptance-checklist.md)
- [Policy approval checklist](workdoe-policy-review-checklist.md)

## Latest Release Evidence

The reviewed local candidate passed 739 Python tests, 190 strict preflight
checks, lint, security/provenance checks and both configuration dry builds.
The exported release tree is rechecked before publication. Those local
results do not establish production traffic, real-device usability or legal
approval.

New internal audit records, signed-in QA captures and provider readbacks remain
in the private local review workspace. Previously published archives are
retained as historical records, not current acceptance. References to withheld
records point to the [public status summary](workdoe-public-launch-gates.md#internal-records),
not to raw operator evidence. They are not part of the website runtime.
