# Local Email Binding Reproduction

Run `npm run diagnose:email-binding` from the repository root with the existing
pinned development dependencies. This manual diagnostic never deploys and is
not a replacement for `npm run test:worker:email` or real delivery acceptance.

The driver starts three separate loopback-only Workers, in sequence:

1. An original JavaScript control using the documented structured send API.
2. A Python entrypoint directly inheriting `WorkerEntrypoint`, with no Workdoe
   application imports.
3. A Python subclass of that entrypoint, to isolate inherited SDK wrapping.

Every generated configuration has `remote: false`, fixed `.invalid` sender and
recipient restrictions, `workers_dev: false`, and no account, route, D1, R2,
Queue, asset or secret binding. The driver strips provider and Wrangler
credential variables, uses an isolated configuration home and local persistence,
refuses redirects/proxies, bounds the response, and reaps its own process tree.
Never enable remote bindings or use real recipients in these fixtures.

An ignored `.test-tmp/email-binding-probe.local.json` records package versions,
UTC time, source hashes and each outcome. Python stack frames include basenames,
not machine paths. Always check its timestamp: failure during process startup
can leave an older report. Exit status is zero only if all three cases accept;
`real_delivery_verified` is always false, including an all-green simulation.

On Windows, sandbox restrictions may prevent local subprocess/loopback access.
That startup failure is not an Email API result. Run under the approved local
test permissions; do not weaken the fixture's resource boundaries.

## Observed On 2026-10-30

Pinned Wrangler `4.152.0`, workerd `1.20261019.1`, Miniflare
`5.20261019.2-beta`, compatibility date `2026-08-23`, bundled Python SDK:

| Case | HTTP / Stage | Result |
| --- | --- | --- |
| JavaScript | 200 / send-accepted | Local simulator accepted. |
| Direct Python | 500 / send | `TypeError: Result should have type "object" not "function"`; `_workers.py:1017`. |
| Inherited Python | 500 / binding-lookup | `AttributeError: 'function' object has no attribute 'name'`; `_workers.py:309`. |

These are separate failures, not proof of a production provider defect. The
reproduction remains failing. No SDK bypass, monkeypatch, dependency upgrade,
new production runtime or provider credential is supplied as a workaround.

The marketplace fixture now aliases the production `entry.Default` and wraps
only its first-party fetch method rather than introducing another SDK subclass.
Ordinary requests still invoke the captured production fetch. The corrected
email qualification reaches the real queue handler and observes retry instead
of the required successful acknowledgement; it still exits 1.

The release evidence and public-source references are in
`docs/release-evidence/2026-10-30-email-binding-reproduction.md`. No upstream
issue has been posted, and these proprietary repository files have not been
published or licensed for external redistribution.
