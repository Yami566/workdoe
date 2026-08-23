# Workdoe Documentation Index

Last reviewed: 2026-08-23

This index identifies the current product and release documents. Dated studies,
screenshots, and earlier audits remain useful evidence, but they do not override
the current requirements, policy gates, or release status.

## Current authority

- `workdoe-stabilization-release-status-2026-08-23.md`: current implementation,
  verification, and remaining production gates.
- `workdoe-product-requirements.md`: product scope, roles, user journeys,
  launch criteria, and owner decisions.
- `workdoe-data-inventory.md`: data classes, storage, visibility, providers,
  and unresolved retention decisions.
- `workdoe-security-impact-assessment.md`: security boundaries, implemented
  controls, residual risks, and required live verification.
- `workdoe-policy-review-checklist.md`: public-policy content and owner/legal
  approval gates.
- `workdoe-operations-runbook.md`: incident, moderation, recovery, credential,
  and data-request operating procedures.
- `cloudflare-migration.md` and `cloudflare-automation-auth.md`: production
  architecture, Cloudflare automation, Clerk, and controlled release workflow.
- `workdoe-design-provenance.md`: first-party design and reference-use record.
- Repository root `LICENSE`, `THIRD_PARTY_NOTICES.md`, and
  `DEPENDENCY_PROVENANCE.json`: proprietary status and dependency provenance.

## Current design evidence

- `ux-audit/2026-08-23-task-navigation/`: accepted desktop, tablet, and mobile
  navigation/dashboard captures plus the editable Figma reference board.
- `ux-audit/2026-08-22-service-policy/`: advisory acknowledgement evidence.
- `ux-audit/2026-08-22-stabilization/`: map, dialog, and stabilization evidence.

Screenshots are point-in-time evidence. A capture is not proof that the current
code still matches it unless the current release-status record cites a repeated
browser check.

## Research and historical records

- The dated DMV competition, commercial-launch, marketplace-expansion, and
  gamified-marketplace studies are research inputs. The latest product decision
  record is `workdoe-dmv-gamified-marketplace-commercial-launch-study-2026-08-21.md`.
- `workdoe-launch-completion-matrix-2026-08-21.md` is superseded by the current
  stabilization release-status record.
- `launch-readiness-2026-08-16/` and `live-acceptance-review-2026-08-16/` are
  historical audits. Findings may have been closed or reclassified later.
- Earlier `ux-audit/` folders and top-level smoke screenshots are historical
  visual evidence, not the current target specification.
- `workdoe-launch-handoff*.local.md` files are generated operator snapshots and
  are not source-of-truth documentation.

When documents conflict, use the current authority list above, then confirm the
behavior in source, tests, and current release evidence.
