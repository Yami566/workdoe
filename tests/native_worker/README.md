# Native Worker Journey

Run `npm run test:worker:journey` from the repository root after installing the
pinned Python/npm dependencies. This is a manual local verification command;
it does not dispatch GitHub Actions or deploy anything.

The Python driver stages a copy of the actual Worker source under `.test-tmp`,
applies every D1 migration to a fresh local-only database, seeds synthetic roles,
and starts pinned Wrangler/workerd on an available loopback port. It exercises
the real route code, Web Crypto signature verification, D1 statements, local R2
and write-rate-limiter bindings through HTTP. Node's built-in `crypto` creates an
ephemeral RSA key and signed fixture tokens; the private key is never serialized
or saved. Tokens stay in driver memory and have no authority in production.

The only replacement boundary is external provider transport:
`journey_entry.py` replaces the imported `entry.fetch` with a local Turnstile
response fixture and rejects every other external fetch. The production
Turnstile action/hostname/result validation still executes. No Clerk API, email
service, production database/media bucket, paid service or real person is used.
This test does not verify Turnstile's real widget/network/key configuration.

The fixture aliases the production `entry.Default`, capturing its fetch before
adding the local email-test route. It must not subclass that Python entrypoint:
the pinned SDK wraps the environment again and introduces a non-production
binding-lookup failure. `npm run diagnose:email-binding` isolates this from a
separate direct Python send/RPC failure; native email qualification still fails.
See `tests/email_binding_probe/README.md`. No third-party SDK is patched.

Local R2 is seeded using `--local` with the existing first-party demonstration
WebP. Local D1 metadata deliberately includes missing, hidden and incorrectly
scoped objects. No upload endpoint is enabled or bypassed; fixture objects are
inserted by the local CLI, and the real upload route must still reject intake
while the beta flag is false.

Coverage includes:

- Valid and invalid/expired/wrong-origin/pending signed sessions; role gates.
- Same-origin write marker, invalid challenge/advisory/address rejection,
  no-budget city/ZIP project creation, ownership checks and idempotent replay.
- Owner edits retaining a stored elapsed requested date, new/changed backdate
  rejection despite forged retention metadata, field errors, complete D1
  rollback and fresh form persistence without extending the bidding window.
- Approximate public lead publication without synthetic account email/subject.
- Mini bid, duplicate rejection, owner approval and private thread creation.
- Participant messages, outsider rejection, owner close and mutual completion.
- Consumer no-budget history and contractor verified completed-work history.
- Reports, admin-only message hiding, hidden-message filtering, account
  suspension/reactivation, and persisted moderation/advisory/completion records.
- Job-photo GET/HEAD role checks, exact bytes, private/no-store and generic
  filename headers, missing-object 404, scoped-key enforcement, hidden records,
  and approved-match access after closure. Contractor photos require active
  sign-in under the owner's October 30 decision; anonymous GET/HEAD, suspended
  access, hidden records and anonymous portfolio metadata are checked.

The driver strips ambient Cloudflare/Clerk/Workdoe credential variables, uses an
isolated Wrangler configuration home, disables metrics, supplies only local
resource identifiers, and issues D1 commands with `--local`. HTTP proxying and
redirect following are disabled. Its owned process tree is stopped afterwards;
cleanup checks the resolved scratch parent and retries transient Windows locks.
The unit suite checks cleanup boundaries and redirect refusal.

The fixture entry, signer and seed are outside `cloudflare/worker` and static
assets. They must never be copied into a deployable application bundle. A
production dry-run after adding this test still contains the expected 51
modules and 88 static assets, with no `journey_entry` or fixture signer.

Passing this command does not establish real Clerk email-code or second-device
acceptance, queue/email delivery, production R2 permissions or upload
sanitization, browser usability,
production rate-limit thresholds, legal approval, retention/incident operations,
or production performance. Those remain in the owner acceptance checklist.

Primary references: [D1 local development](https://developers.cloudflare.com/d1/best-practices/local-development/),
[Clerk verification](https://clerk.com/docs/guides/sessions/manual-jwt-verification),
[Node crypto](https://nodejs.org/api/crypto.html),
[Pyodide FFI](https://pyodide.org/en/stable/usage/api/python-api/ffi.html).
