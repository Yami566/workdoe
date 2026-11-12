from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ClerkEntryNavigationTests(unittest.TestCase):
    def test_recovery_navigation_and_detached_entry_lifecycle(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for Clerk entry regressions.")
        script = textwrap.dedent(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            const settle = async () => {
              for (let i = 0; i < 12; i++) await new Promise(setImmediate);
            };

            function fixture(options = {}) {
              const events = [], navigations = [], requests = [], mounts = [], unmounts = [];
              let connected = true, listener, unsubscribed = 0, loadOptions;
              const status = {}, loading = { setAttribute() {} };
              const scope = {
                querySelector(selector) {
                  if (selector === '[data-clerk-onboarding-message]') return status;
                  if (selector === '[data-clerk-display-name]') return { value: 'Public fixture handle' };
                  return null;
                },
                addEventListener() {}
              };
              const entry = {
                dataset: {
                  clerkMode: options.mode || 'sign-in',
                  sessionUrl: '/api/auth/session',
                  redirectUrl: options.destination || '/jobs/new?embed=1&service=window-cleaning',
                  selectedJobId: options.selectedJobId || ''
                },
                closest(selector) {
                  const panel = options.dialog ? '.market-auth-rail' : '.clerk-entry-panel';
                  if (selector.split(', ').includes(panel)) return scope;
                  return options.dialog && selector === '[data-site-dialog-content]' ? {} : null;
                },
                querySelector: () => loading
              };
              let activeEntry = entry;
              const clerk = {
                isSignedIn: options.signedIn !== false,
                session: { getToken: async () => 'synthetic-fixture-token' },
                load(settings) { loadOptions = settings; return options.load || Promise.resolve(); },
                addListener(callback) { listener = callback; return () => { unsubscribed++; }; },
                mountSignIn: (_, props) => mounts.push(props),
                mountSignUp: (_, props) => mounts.push(props),
                unmountSignIn: () => unmounts.push('sign-in'),
                unmountSignUp: () => unmounts.push('start')
              };
              const document = {
                readyState: 'complete',
                contains: () => connected,
                querySelectorAll(selector) {
                  return selector === '[data-site-dialog][open] [data-clerk-entry]'
                    ? options.dialog ? [activeEntry] : [] : [entry];
                },
                dispatchEvent: (event) => events.push(event)
              };
              const window = {
                Clerk: clerk, __internal_ClerkUICtor: function FixtureUi() {},
                location: {
                  origin: 'https://workdoe.com', pathname: '/login',
                  href: 'https://workdoe.com/login?embed=1&next=%2Fjobs%2Fnew',
                  search: '?embed=1&next=%2Fjobs%2Fnew',
                  assign: (url) => navigations.push(url),
                  replace: (url) => navigations.push({replace: url})
                },
                fetch: async (url, init) => {
                  requests.push({ url, init });
                  if (options.response) return options.response;
                  return { ok: true, json: async () => options.payload || { workdoe_user: { role: 'client' } } };
                },
                sessionStorage: { getItem() {}, setItem() {}, removeItem() {} },
                setTimeout: () => 1, clearTimeout() {}, console: { error() {} }
              };
              class CustomEvent { constructor(type, init) { this.type = type; this.detail = init.detail; } }
              vm.runInNewContext(source, { window, document, URL, URLSearchParams, Promise, CustomEvent });
              return {
                entry, events, navigations, requests, mounts, unmounts, clerk, location: window.location,
                get loadOptions() { return loadOptions; },
                adoptEntry() { activeEntry = {dataset: {state: 'ready'}}; },
                disconnect() { connected = false; },
                emit() { listener?.({ session: {}, user: {} }); },
                get unsubscribed() { return unsubscribed; }
              };
            }

            (async () => {
              const modal = fixture({ dialog: true });
              await settle();
              assert.equal(modal.navigations.length, 0, 'recovery must not replace the parent document');
              assert.equal(modal.events.length, 1);
              assert.equal(modal.events[0].type, 'workdoe:dialog-navigate');
              assert.equal(modal.events[0].detail.url, '/jobs/new?service=window-cleaning');
              assert.equal(Object.keys(modal.events[0].detail).join(','), 'url');

              const direct = fixture();
              await settle();
              assert.deepEqual(direct.navigations, ['/jobs/new?service=window-cleaning']);
              assert.equal(direct.events.length, 0);

              const external = fixture({ dialog: true, destination: 'https://untrusted.example/path' });
              await settle();
              assert.equal(external.events[0].detail.url, '/dashboard');

              const onboarding = fixture({ dialog: true, payload: { onboarding_required: true } });
              await settle();
              assert.equal(onboarding.events[0].detail.url, '/create-account');
              const existingStart = fixture({ dialog: true, mode: 'start' });
              await settle();
              assert.equal(existingStart.events[0].detail.url, '/dashboard');

              const mounted = fixture({ dialog: true, signedIn: false });
              await settle();
              assert.equal(mounted.mounts[0].forceRedirectUrl, '/login?next=%2Fjobs%2Fnew');
              const routed = [], route = mounted.loadOptions;
              assert.equal(typeof route.routerPush, 'function');
              assert.equal(typeof route.routerReplace, 'function');
              route.routerPush('/create-account?intent=find-work&job_id=17&next=%2Fjobs%2F17&embed=1',
                {windowNavigate: value => routed.push(value)});
              assert.equal(mounted.events.at(-1).detail.url,
                '/create-account?intent=find-work&job_id=17&next=%2Fjobs%2F17');
              assert.equal(routed.length, 0, 'switching forms must retain the parent document');
              mounted.entry.dataset.clerkDisposed = 'true';
              mounted.adoptEntry();
              mounted.location.pathname = '/create-account';
              mounted.location.href = 'https://workdoe.com/create-account';
              route.routerReplace('https://workdoe.com/login?next=%2Fjobs%2F17',
                {windowNavigate: value => routed.push(value)});
              assert.equal(mounted.events.at(-1).detail.url, '/login?next=%2Fjobs%2F17',
                'the shared router must find the current entry, not its disposed first mount');
              const switches = mounted.events.length;
              for (const destination of [
                '/create-account#/verify-email-address', '/dashboard', '/jobs/new',
                'https://clerk.example.invalid/handshake',
              ]) route.routerPush(destination, {windowNavigate: value => routed.push(value)});
              assert.equal(mounted.events.length, switches,
                'internal code steps and post-auth destinations must use provider navigation');
              assert.equal(routed.length, 4);
              mounted.clerk.isSignedIn = true;
              route.routerPush('/login', {windowNavigate: value => routed.push(value)});
              assert.equal(mounted.events.length, switches, 'do not intercept signed-in recovery');
              mounted.clerk.isSignedIn = false;
              for (const destination of ['javascript:alert(1)', 'data:text/html,fixture', 'https://[']) {
                route.routerPush(destination, {windowNavigate: value => routed.push(value)});
              }
              assert.equal(routed.length, 5, 'invalid and non-web destinations must not execute');
              assert.equal(mounted.events.length, switches);
              const directRouter = fixture({signedIn: false});
              await settle();
              directRouter.loadOptions.routerPush('/create-account', {windowNavigate: value => routed.push(value)});
              assert.equal(directRouter.events.length, 0, 'direct URLs must retain full-page navigation');
              directRouter.loadOptions.routerReplace('/login?next=%2Fdashboard');
              assert.deepEqual(directRouter.navigations, [{replace: '/login?next=%2Fdashboard'}]);
              route.routerPush('/dashboard');
              assert.deepEqual(mounted.navigations, ['/dashboard']);
              delete mounted.entry.dataset.clerkDisposed;
              mounted.entry._workdoeClerkDispose();
              mounted.entry._workdoeClerkDispose();
              mounted.disconnect();
              mounted.emit();
              await settle();
              assert.equal(mounted.unsubscribed, 1);
              assert.deepEqual(mounted.unmounts, ['sign-in']);
              assert.equal(mounted.requests.length, 0, 'closed entry listener must be inert');

              let finishLoad;
              const pendingLoad = fixture({ dialog: true, load: new Promise(resolve => { finishLoad = resolve; }) });
              pendingLoad.disconnect();
              finishLoad();
              await settle();
              assert.equal(pendingLoad.requests.length, 0);
              assert.equal(pendingLoad.mounts.length, 0);

              let finishResponse;
              const pendingSession = fixture({ dialog: true, response: new Promise(resolve => { finishResponse = resolve; }) });
              await settle();
              pendingSession.disconnect();
              finishResponse({ ok: true, json: async () => ({ workdoe_user: { role: 'client' } }) });
              await settle();
              assert.equal(pendingSession.events.length, 0, 'closed entry must not navigate after a delayed response');
              assert.equal(pendingSession.navigations.length, 0);
            })().catch(error => { console.error(error.stack); process.exitCode = 1; });
            """
        )
        result = subprocess.run(
            [node, "-e", script, str(ROOT / "workdoe" / "static" / "clerk-entry.js")],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
