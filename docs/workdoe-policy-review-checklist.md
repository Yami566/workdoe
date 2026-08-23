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
- Project location is approximate before approval and users are warned not to
  publish exact addresses, contact details, or access codes.
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

| Decision | Current state | Evidence required before public approval |
| --- | --- | --- |
| Legal operator and data controller | Missing | Legal name, business address/jurisdiction, and approved public display format |
| Monitored contact ownership | Unverified | Named owner, monitored inbox proof, and response target for account, privacy, safety, and security requests |
| Retention and deletion schedule | Missing | Record-class schedule for accounts, projects, messages, media, reports, auth/audit records, backups, and deletion exceptions |
| Consumer data-rights workflow | Procedure drafted only | Completed export/deletion test, identity-verification rule, denial/appeal path, and request log |
| Terms acceptance | Clerk express-consent release gate implemented; live setting, policy approval, and versioned Workdoe acceptance record remain unverified/not implemented | Enable Clerk's express-consent setting for `https://workdoe.com/terms` and `https://workdoe.com/privacy`, retain operator proof, approve a version/change-notice rule, and define whether Workdoe needs its own acceptance event plus when existing users must re-accept |
| Marketplace liability/dispute language | Legal review required | Approved venue, governing law, warranty/liability, indemnity, dispute, and notice terms appropriate to the operator |
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
