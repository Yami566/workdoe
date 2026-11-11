# Workdoe Public Policy Review Checklist

Status: Production-candidate copy exists locally. Owner and legal approval are
not recorded. Do not treat route availability as policy approval.

The candidate public surfaces are `/privacy`, `/terms`, `/safety`,
`/robots.txt`, `/sitemap.xml`, and `/.well-known/security.txt`. Flask and the
Cloudflare Worker implement the same material statements and every page links
to the policy set from the footer.

## Statements currently represented

- Accounts are limited to adults age 18 or older.
- Consumer and contractor roles remain separate and fixed per account.
- Workdoe is a matching marketplace, not the employer, contractor, insurer,
  payment processor, emergency service, or project guarantor.
- The controlled beta has no payment, escrow, warranty, background-check,
  license-verification, rating, or dispute-adjudication product.
- Project location is approximate before approval. Marketplace, public-profile,
  onboarding-label, private-workspace, and saved-area text reject common email,
  phone, and street-address patterns, while the UI warns that no automated
  check can identify every disclosure.
- Contractor qualifications and project statements are self-reported unless
  Workdoe explicitly labels a fact as verified.
- Illegal, emergency, hazardous-material, medical/personal-care, firearms,
  unlicensed gas/utility, insurance-claim, illegal-dumping, and unsafe minor
  work is prohibited.
- Workdoe does not sell personal information or use it for third-party
  behavioral advertising.
- Access, correction, deletion, safety, and account requests currently point
  to `admin@workdoe.com`.

## Approval gates

An additional live copy/product consistency finding is recorded in
`release-evidence/2026-10-28-public-policy-product-parity.md`: the Terms exclude
all ratings and license verification, while the implemented scope includes
limited structured completed-work feedback and dated source checks. The
non-effective clarification draft needs owner/counsel approval, a version and
change-notice/re-consent decision before either runtime Terms is amended.

| Decision | Current state | Evidence required before public approval |
| --- | --- | --- |
| Legal operator and data controller | Owner identified Moose Bay and Company LLC as the Virginia operator; a public street or mailing address and approved legal display format are still unrecorded | Confirm the public address/display format and obtain legal approval of the operator statement |
| Monitored contact ownership | Owner confirms they monitor `admin@workdoe.com` and target a 1-5 business-day response. One owner-reported routing test arrived in spam; timely normal receipt and urgent coverage are not established. | Verify reliable receipt and triage from a separate mailbox, define urgent/security coverage, and record the owner operating procedure. |
| Retention and deletion schedule | Decision proposal drafted; not approved or effective. [Local account scope rehearsal](workdoe-public-launch-gates.md#internal-records) establishes cascade and restore risks only. | Owner/counsel approval of the record-class periods, exceptions, legal-hold owner, public notice, implementation plan, and hosted deletion drill. See `docs/workdoe-beta-retention-incident-decision-proposal.md`. |
| Consumer data-rights workflow | Owner selected one request for Workdoe data and sign-in. The procedure is still a draft and [Clerk self-deletion remains enabled](workdoe-public-launch-gates.md#internal-records). | Approved and accessible request intake, identity verification including lost sign-in, denial/appeal path, request log, coordinated provider settings, and a hosted export/deletion and recovery drill. |
| Terms acceptance | Clerk production express consent is enabled and evidenced for `https://workdoe.com/terms` and `https://workdoe.com/privacy`; policy approval and a versioned Workdoe acceptance record remain unverified/not implemented | Retain operator proof, approve a version/change-notice rule, and define whether Workdoe needs its own acceptance event plus when existing users must re-accept |
| Marketplace liability/dispute language | Legal review required | Approved venue, governing law, warranty/liability, indemnity, dispute, and notice terms appropriate to the operator |
| Product-policy parity for feedback and reviewed records | Live Terms contain overbroad or ambiguous exclusions relative to implemented structured feedback and source-checked records | Approve accurate feature limits, feedback visibility/moderation wording, verification disclaimers, policy version/effective date, and user notice/re-consent treatment; then update and test both renderers |
| Contractor classification and licensing | Legal review required | Approved independent-business wording and service/zone-specific qualification rules |
| Underage-use rule | Candidate says 18+ | Owner/legal approval and enforcement/escalation procedure |
| Prohibited work | Candidate list exists | Operations/legal approval plus service-taxonomy enforcement review |
| Source-code posture | Proprietary owner direction recorded | Keep the top-level `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `DEPENDENCY_PROVENANCE.json` aligned; do not market first-party Workdoe source as open source |

## Research basis

This checklist uses public official guidance as design input, not as a legal
determination that any specific law applies to Workdoe.

- The FTC recommends knowing what personal information a business holds,
  collecting and retaining only what it needs, restricting access, disposing
  of unneeded data, and planning for incidents:
  <https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business>
- Maryland's Attorney General explains access, correction, deletion,
  nondiscrimination, and use/disclosure rights under the Maryland Online Data
  Privacy Act, which took effect October 1, 2025:
  <https://oag.maryland.gov/resources-info/Pages/data-privacy.aspx>
- Virginia's Attorney General publishes the Consumer Data Protection Act among
  the Commonwealth's consumer-protection laws:
  <https://www.oag.state.va.us/consumer-protection/index.php/laws-cases>
- Clerk's maintained sign-up component can require express consent to an
  application's Terms and Privacy documents when Legal Compliance is enabled:
  <https://clerk.com/docs/guides/secure/legal-compliance>. Workdoe uses this
  platform control instead of a custom consent widget; the release proof does
  not substitute for policy approval or a re-consent decision.

Counsel should determine applicability, thresholds, exceptions, and final
language before unrestricted registration.
