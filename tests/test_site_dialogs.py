from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SiteDialogNavigationTests(unittest.TestCase):
    def test_failure_fallback_bypasses_interception_but_normal_links_open_in_place(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for dialog regressions.")
        script = textwrap.dedent(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');

            function fixture(bypass, hasTurnstile = false, hasClerk = false) {
              const listeners = {};
              const requests = [];
              const responses = [];
              const timers = [];
              const navigation = [];
              let disposed = 0;
              const entry = { _workdoeClerkDispose() { disposed++; } };
              const content = {
                replaceChildren(...children) { this.children = children; },
                querySelectorAll: selector => hasClerk && selector === '[data-clerk-entry]' ? [entry] : []
              };
              const status = {};
              const title = {};
              const close = { focus() {}, addEventListener() {} };
              const focusControls = [];
              const widget = { dataset: { sitekey: 'fixture-key', action: 'job-post' } };
              const controls = {
                '[data-site-dialog-content]': content,
                '[data-site-dialog-status]': status,
                '[data-site-dialog-title]': title,
                '[data-site-dialog-close]': close
              };
              const dialog = {
                open: false, dataset: {},
                querySelector: (selector) => controls[selector],
                querySelectorAll: () => focusControls,
                hasAttribute: () => false,
                setAttribute() {},
                removeAttribute() {},
                showModal() { this.open = true; },
                addEventListener() {}
              };
              const anchor = {
                href: 'https://workdoe.com/jobs/new', target: '', dataset: {},
                closest: () => null,
                hasAttribute: (name) => bypass && name === 'data-dialog-bypass'
              };
              const document = {
                querySelector: () => dialog,
                querySelectorAll: (selector) => hasTurnstile && selector === '[data-workdoe-turnstile]' ? [widget] : [],
                createElement: tag => ({
                  tag, attributes: {}, handlers: {},
                  append(...children) { this.children = children; },
                  setAttribute(name, value) { this.attributes[name] = value; },
                  addEventListener(name, handler) { this.handlers[name] = handler; },
                  focus() { document.activeElement = this; }
                }),
                activeElement: anchor,
                body: { classList: { add() {} } },
                addEventListener(name, handler) {
                  (listeners[name] ||= []).push(handler);
                }
              };
              const window = {
                getComputedStyle: node => ({ visibility: node.visibility || 'visible' }),
                location: {
                  href: 'https://workdoe.com/client/dashboard',
                  origin: 'https://workdoe.com',
                  pathname: '/client/dashboard', search: '', hash: '',
                  assign: url => navigation.push(['assign', url])
                },
                history: {
                  pushState: (state, _, path) => navigation.push(['push', path, state.backgroundUrl]),
                  replaceState: (state, _, path) => navigation.push(['replace', path, state.backgroundUrl])
                },
                addEventListener() {},
                setTimeout(callback, delay) { timers.push({ callback, delay }); return timers.length; },
                clearTimeout() {},
                fetch(url, options) {
                  requests.push(url);
                  assert.equal(options.method, undefined); // Default GET.
                  return new Promise(resolve => responses.push(resolve));
                }
              };
              if (hasTurnstile) {
                window.turnstile = { ready: (callback) => callback(), render: () => 'owned-widget-id' };
              }
              vm.runInNewContext(source, { document, window, URL });
              const event = {
                button: 0, defaultPrevented: false,
                target: { closest: (selector) => selector === 'a[href]' ? anchor : null },
                preventDefault() { this.defaultPrevented = true; }
              };
              for (const listener of listeners.click) listener(event);
              return { event, dialog, requests, responses, timers, widget, navigation, listeners, content, status,
                document, focusControls, get disposed() { return disposed; } };
            }

            const fallback = fixture(true);
            assert.equal(fallback.event.defaultPrevented, false);
            assert.equal(fallback.dialog.open, false);
            assert.equal(fallback.requests.length, 0);
            const normal = fixture(false);
            assert.equal(normal.event.defaultPrevented, true);
            assert.equal(normal.dialog.open, true);
            assert.equal(normal.requests.length, 1);
            assert.equal(normal.requests[0], 'https://workdoe.com/jobs/new?embed=1');
            assert.equal(fixture(true, true).widget.dataset.turnstileWidgetId, 'owned-widget-id');
            assert.equal(normal.timers[0].delay, 12000);
            normal.timers[0].callback();
            const [retry, fullPage] = normal.content.children[0].children;
            assert.equal(normal.status.textContent, 'This form took too long to load.');
            assert.equal(normal.document.activeElement, retry);
            assert.equal(retry.type, 'button');
            assert.equal(fullPage.tag, 'a');
            assert.equal(fullPage.href, '/jobs/new');
            assert.ok(Object.hasOwn(fullPage.attributes, 'data-dialog-bypass'));
            retry.handlers.click();
            assert.deepEqual(normal.requests, Array(2).fill('https://workdoe.com/jobs/new?embed=1'));
            normal.responses[0]({ ok: true, redirected: true, url: 'https://workdoe.com/dashboard' });
            setImmediate(() => assert.deepEqual(normal.navigation, [['push', '/jobs/new', '/client/dashboard']]));

            const recovered = fixture(false, false, true);
            assert.equal(recovered.disposed, 1);
            recovered.listeners['workdoe:dialog-navigate'][0]({ detail: { url: '/jobs/new?service=window-cleaning' } });
            assert.equal(recovered.requests[1], 'https://workdoe.com/jobs/new?service=window-cleaning&embed=1');
            assert.equal(recovered.navigation[1][0], 'replace');
            assert.equal(recovered.navigation[1][1], '/jobs/new?service=window-cleaning');
            assert.equal(recovered.navigation[1][2], '/client/dashboard');
            recovered.listeners['workdoe:dialog-navigate'][0]({ detail: { url: '/client/dashboard?embed=1' } });
            assert.deepEqual(recovered.navigation[2], ['assign', '/client/dashboard']);

            const keyboard = fixture(false);
            function control(options = {}) {
              return Object.assign({
                tabIndex: 0, visibility: 'visible',
                closest: selector => selector === 'dialog[open]' ? keyboard.dialog : null,
                matches: () => false,
                getClientRects: () => [1],
                focus() { keyboard.document.activeElement = this; }
              }, options);
            }
            const first = control(), middle = control(), last = control();
            keyboard.focusControls.push(first, middle, last,
              control({tabIndex: -1}), control({matches: () => true}),
              control({getClientRects: () => []}), control({visibility: 'hidden'}),
              control({closest: () => ({})}));
            function press(target, options = {}) {
              keyboard.document.activeElement = target;
              const event = Object.assign({key: 'Tab', target, shiftKey: false,
                defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }}, options);
              for (const listener of keyboard.listeners.keydown) listener(event);
              return event;
            }
            assert.ok(press(last).defaultPrevented);
            assert.equal(keyboard.document.activeElement, first);
            assert.ok(press(first, {shiftKey: true}).defaultPrevented);
            assert.equal(keyboard.document.activeElement, last);
            assert.equal(press(middle).defaultPrevented, true);
            assert.equal(keyboard.document.activeElement, last);
            for (const modifier of ['ctrlKey', 'metaKey', 'altKey']) {
              const event = press(last, {[modifier]: true});
              assert.equal(event.defaultPrevented, false);
              assert.equal(keyboard.document.activeElement, last);
            }
            press(last, {defaultPrevented: true});
            assert.equal(keyboard.document.activeElement, last);
            const nested = control({closest: () => ({})});
            assert.equal(press(nested).defaultPrevented, false);
            keyboard.focusControls.length = 0;
            const radio = control({type: 'radio', name: 'role'});
            const selectedRadio = control({type: 'radio', name: 'role', checked: true});
            keyboard.focusControls.push(first, radio, selectedRadio, last);
            press(first);
            assert.equal(keyboard.document.activeElement, selectedRadio);
            press(selectedRadio);
            assert.equal(keyboard.document.activeElement, last);
            keyboard.focusControls.splice(1, 2, control({tabIndex: 2}), control({tabIndex: 1}));
            press(keyboard.focusControls[2]);
            assert.equal(keyboard.document.activeElement, keyboard.focusControls[1]);
            keyboard.dialog.open = false;
            assert.equal(press(last).defaultPrevented, false);
            """
        )
        result = subprocess.run(
            [node, "-e", script, str(ROOT / "workdoe" / "static" / "site-dialogs.js")],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
