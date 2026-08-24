# Contractor Choice Confirmation Audit

Date: 2026-08-24

## Scope

The consumer's contractor-selection path from the project comparison view and
the related contractor profile, including Flask and Cloudflare Worker behavior,
responsive dialogs, discovery rules, and the D1 data invariant.

## Finding

The interface used the singular action "Choose contractor," but the data layer
could approve more than one offer for the same project. An approved project
could also remain in public lead results and accept another offer. The action
submitted immediately, without clearly explaining that it opens messaging and
closes competing offers.

Browser QA then found a narrower parity defect: the profile confirmation opened
correctly but did not receive the offer's price, timeline, or availability from
the profile relationship query.

## Change

- Added one approved contractor per project as a database invariant in SQLite
  and D1 through a partial unique index.
- Made Flask and Worker approval conditional, rejected the remaining pending
  offers after a successful choice, and retained the private matched thread.
- Stopped matched projects from accepting new offers, appearing in public lead
  results, or entering contractor alert and repeat-invitation candidate sets.
- Added a native confirmation dialog to the project comparison and contractor
  profile paths. It states that messaging opens, other pending offers close, no
  payment is created, and the project stays open while work is underway.
- Reused the existing audited dialog controller, direct route fallbacks, design
  tokens, and server-rendered templates. No new client-side dependency was
  introduced.
- Carried price, timeline, and availability through both profile relationship
  queries and added Flask/Worker parity assertions for those terms.

## Evidence

- `00-mobile-comparison-390x844.png`: pending offer before confirmation.
- `01-mobile-confirmation-390x844.png`: project comparison confirmation.
- `02-tablet-confirmation-820x1180.png`: tablet confirmation state.
- `03-desktop-confirmation-1280x720.png`: desktop confirmation state.
- `04-mobile-before-after.png`: direct before/after comparison.
- `05-mobile-profile-confirmation-390x844.png`: corrected profile confirmation
  with the offer's price, timeline, and availability.

At 390 by 844, the profile dialog had no horizontal overflow, locked background
scroll, focused Cancel on open, and returned focus to the original Choose
contractor control on cancel. Tablet and desktop dialogs remained 560 pixels
wide by 377 pixels tall without overflow.

## Data And Privacy

The public APIs continue to return approximate coordinates only. Exact
addresses, contact details, rejected-offer content, and private thread content
were not added to discovery responses. Matching changes status and access; it
does not create a payment, ranking signal, recommendation, or credential claim.

Migration `0033_single_approved_match.sql` fails closed if historical data
contains duplicate approved offers. The operator must run this read-only audit
before the production migration:

```sql
SELECT job_id, COUNT(*) AS approved_count
FROM match_requests
WHERE status = 'approved'
GROUP BY job_id
HAVING COUNT(*) > 1;
```

All five local SQLite databases returned zero duplicate approved-project rows.
The production D1 audit and pre-deployment backup remain live release gates.

## Acceptance

All 235 tests passed in 90.321 seconds. Full Ruff passed. `pip-audit` and
`npm audit` found no known vulnerabilities; Bandit reported no medium or high
findings. The reviewed secret baseline passed across 611 non-ignored files, and
dependency provenance passed.

Cloudflare preflight returned no warnings. The D1 verifier loaded all 33
migrations, used the geographic and public-media indexes without a table scan,
and used `idx_match_requests_job` for the approved-match exclusion. Wrangler
4.125.0 packaged 48 Python modules and 86 static assets at 926.94 KiB, 170.34
KiB gzip. The command used `--dry-run`; no deployment occurred.

## Limits

The browser used seeded local client and contractor records. Production Clerk,
D1 migration backup/audit, private media, Queues, Email, Turnstile, Images,
legal approval, accessibility assistive-technology checks, and Core Web Vitals
remain separate live release gates.
