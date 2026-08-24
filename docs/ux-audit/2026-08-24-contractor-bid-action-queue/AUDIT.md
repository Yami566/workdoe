# Contractor Bid Action Queue Audit

Date: 2026-08-24

## Scope

This current-run audit reviewed the signed-in contractor dashboard at
`/contractor/dashboard` in the local Flask adapter and the equivalent
Cloudflare Worker shell. The accepted state uses the existing Workdoe visual
system, status vocabulary, four server-rendered filters, and private bid data.

## Finding

The prior mobile state in
`../2026-08-24-current-workflow-followup/02-contractor-dashboard-mobile.png`
put the newest pending and rejected bids ahead of approved work. Every row had
nearly equal visual weight, and contractors had to open each project to recall
their submitted estimate and timing.

## Change

- The private All lane now groups approved bids first, pending bids second, and
  rejected history last. Each group remains newest-submitted first.
- Filtered Pending, Approved, and Rejected lanes retain newest-submitted order.
- Every row now shows the already-stored bid status, estimate, and timeline.
- Approved rows still open the approved private message thread. Pending and
  rejected rows still open the contractor's project/bid record.
- Status-colored left borders improve scanning without replacing text labels or
  using color as the only signal.
- Each task-specific link references its bid terms with `aria-describedby`.
- No new script, dependency, table, event, score, rank input, notification, or
  public field was introduced.

## Evidence

- `03-mobile-dashboard-refined.png`: accepted 390x844 all-bids queue.
- `04-tablet-dashboard-after.png`: accepted tablet queue and milestone context.
- `05-desktop-dashboard-after.png`: accepted 1280x720 queue and milestone edge.

At 390x844, the first bid begins at 279 pixels and the third active bid ends at
768 pixels, above the fixed task bar. The document and body widths both measure
375 pixels. The rendered status sequence is Approved, Approved, Pending,
Rejected. All four `aria-describedby` references resolve to unique visible bid
term elements. At 820x1180 and 1280x720, document width matches body width and
the same four-row order is preserved without clipping or horizontal overflow.

## Product And Privacy Boundary

This is action prioritization inside one contractor's private dashboard, not
marketplace ranking. It does not change which leads contractors see, the
received order consumers use to compare offers, completion points, credential
filters, or the four-bid cap. The cards reuse the contractor's submitted
estimate and timeline and expose no client identity, contact information, or
exact address.

## Verification

- Full Ruff: passed.
- Unit and integration suite: 238 tests passed in 83.129 seconds.
- Dependency, Bandit, secret, and provenance gates: passed across 676
  non-ignored files.
- Cloudflare preflight: passed without warnings.
- D1 verification: all 34 migrations loaded; all three expected public
  map/photo indexes were used; no table scan was found.
- Wrangler 4.125.0 dry run: 49 Python modules and 88 static assets packaged at
  941.19 KiB / 172.97 KiB gzip without deploying.

## Limits

The screenshots and browser checks do not prove production D1 latency, Clerk
authentication, live queue/email delivery, Cloudflare Images sanitization, or
real-user comprehension. No GitHub push or Cloudflare deployment was performed
for this batch.
