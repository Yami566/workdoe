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
            const settle = async () => { for (let step = 0; step < 4; step += 1) await new Promise(setImmediate); };

            function fixture(clerk) {
              const status = { textContent: 'Loading secure email sign-in...' };
              const loading = { textContent: 'Loading secure email sign-in...' };
              const node = {
                dataset: {},
                querySelector: (selector) => selector === '.clerk-entry-loading' ? loading : null,
                closest: () => scope
              };
              const scope = {
                querySelector: (selector) => selector === '[data-clerk-onboarding-message]' ? status : null,
                addEventListener() {}
              };
              const timers = [];
              const window = {
                Clerk: clerk,
                __internal_ClerkUICtor: function FixtureUi() {},
                console: { error() {} },
                location: { pathname: '/login', search: '', assign() {} },
                sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
                setTimeout: (callback) => { timers.push(callback); return timers.length; },
                clearTimeout() {}
              };
              const document = { readyState: 'complete', querySelectorAll: () => [node] };
              vm.runInNewContext(source, { window, document, Promise, URLSearchParams });
              return { node, status, loading, timers };
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
