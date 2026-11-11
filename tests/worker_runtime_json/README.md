# Native JSON Reader Check

Local-only synthetic regression harness. It imports unchanged copies of the real
Worker modules; it is not a production entry point. Its config has no database,
email, R2, queue, asset, secret, or remote bindings. Do not deploy this config.

From the repository root, use PowerShell to prepare an ignored flat module bundle:

```powershell
New-Item -ItemType Directory -Force .test-tmp/json-reader-runtime
Copy-Item cloudflare/worker/*.py .test-tmp/json-reader-runtime/
Copy-Item tests/worker_runtime_json/probe.py .test-tmp/json-reader-runtime/
Copy-Item tests/worker_runtime_json/wrangler.jsonc .test-tmp/json-reader-runtime/
.\node_modules\.bin\wrangler.cmd dev --local --ip 127.0.0.1 --port 8891 --config .test-tmp/json-reader-runtime/wrangler.jsonc
```

Verify the port is unused before starting. In another terminal request
`http://127.0.0.1:8891/` twice. Both responses must have `passed: true`, all checks
true, and the same check count. Stop Wrangler afterward and verify port 8891 is
no longer listening. Recopy modules after source changes and compare their hashes
with `cloudflare/worker/` before recording results. Never send these inputs to
production.

The harness checks real Worker request/response wrappers, normal nested project
scope and verified email data, malformed/deep JSON, signed webhook processing,
conversion depth boundaries, and token rejection. Positive token cases use a
mock signature verifier; they do not prove RSA verification or live Clerk OTP.
Synthetic signatures and example.invalid emails are not production credentials.
This complements, rather than replaces, the full unit/integration/security suite.
