from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClerkEntryLoadingTests(unittest.TestCase):
    def test_missing_or_stalled_clerk_never_leaves_the_loading_message(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for Clerk entry regressions.")
        script = textwrap.dedent(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            const settle = async () => {
              for (let step = 0; step < 12; step += 1) await new Promise(setImmediate);
              await new Promise((resolve) => setTimeout(resolve, 0));
            };

            function fixture(clerk, sessionResponse) {
              const status = { textContent: 'Loading secure email sign-in...' };
              const loading = {
                textContent: 'Loading secure email sign-in...',
                hidden: false,
                attributes: {},
                setAttribute(name, value) { this.attributes[name] = value; }
              };
              const node = {
                dataset: { sessionUrl: '/api/auth/session' },
                querySelector: (selector) => selector === '.clerk-entry-loading' ? loading : null,
                closest: () => scope
              };
              const retry = { disabled: false, addEventListener(type, callback) { this.callback = callback; } };
              const recovery = {
                dataset: {},
                hidden: true,
                attributes: {},
                querySelector: (selector) => selector === '[data-clerk-session-retry]' ? retry : null,
                setAttribute(name, value) { this.attributes[name] = value; },
                removeAttribute(name) { delete this.attributes[name]; }
              };
              const scope = {
                querySelector: (selector) => {
                  if (selector === '[data-clerk-onboarding-message]') return status;
                  if (selector === '[data-clerk-session-recovery]') return recovery;
                  return null;
                },
                addEventListener() {}
              };
              const timers = [];
              const window = {
                Clerk: clerk,
                __internal_ClerkUICtor: function FixtureUi() {},
                console: { error() {} },
                location: { pathname: '/login', search: '', assign() {} },
                fetch: async () => sessionResponse || { ok: true, status: 200, json: async () => ({ workdoe_user: { role: 'client' } }) },
                sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
                setTimeout: (callback) => { timers.push(callback); return timers.length; },
                clearTimeout() {}
              };
              const document = { readyState: 'complete', querySelectorAll: () => [node] };
              vm.runInNewContext(source, { window, document, Promise, URLSearchParams });
              return { node, status, loading, recovery, retry, timers };
            }

            (async () => {
              const unavailable = fixture(undefined);
              await settle();
              assert.equal(unavailable.node.dataset.state, 'unavailable');
              assert.match(unavailable.loading.textContent, /could not load/);
              assert.equal(unavailable.status.textContent, unavailable.loading.textContent);

              const stalled = fixture({
                isSignedIn: false,
                load: () => new Promise(() => {}),
                mountSignIn() {}
              });
              await settle();
              assert.equal(stalled.timers.length, 1);
              stalled.timers[0]();
              await settle();
              assert.equal(stalled.node.dataset.state, 'failed');
              assert.match(stalled.loading.textContent, /taking longer than expected/);
              assert.equal(stalled.status.textContent, stalled.loading.textContent);

              const mounted = fixture({
                isSignedIn: false,
                load: () => Promise.resolve(),
                mountSignIn() {}
              });
              await settle();
              assert.equal(mounted.node.dataset.state, 'ready');
              assert.equal(mounted.loading.hidden, true);
              assert.equal(mounted.loading.attributes['aria-hidden'], 'true');

              const rejected = fixture(
                { isSignedIn: true, load: () => Promise.resolve(), mountSignIn() {} },
                { ok: false, status: 401, json: async () => ({ error: 'Session token not verified.' }) }
              );
              await settle();
              assert.equal(rejected.node.dataset.state, 'session-rejected');
              assert.equal(rejected.recovery.hidden, false);
              assert.match(rejected.status.textContent, /Use a new email code/);
            })().catch((error) => { console.error(error.stack); process.exitCode = 1; });
            """
        )
        result = subprocess.run(
            [node, "-e", script, str(ROOT / "workdoe" / "static" / "clerk-entry.js")],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
