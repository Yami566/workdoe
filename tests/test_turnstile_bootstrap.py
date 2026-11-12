from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from test_cloudflare_release import load_app_shell_module

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get("WORKDOE_TURNSTILE_SCRIPT", ROOT / "workdoe/static/site-dialogs.js"))


class TurnstileBootstrapTests(unittest.TestCase):
    def run_script(self, assertions):
        node = shutil.which("node")
        self.assertIsNotNone(node)
        fixture = textwrap.dedent(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            function setup(action = 'job-post', ready = true) {
              const handlers = {}, scriptHandlers = {}, options = [], resets = [];
              const notice = { textContent: '', dataset: {} };
              const status = { textContent: 'Loading verification...' };
              const retry = { disabled: false, focus() { this.focused = true; } };
              const response = { value: '' };
              const form = {
                unsaved: 'Synthetic unsaved scope',
                querySelector(selector) {
                  return {'[data-workdoe-turnstile]': widget,
                    '[data-form-status]': notice,
                    'input[name="cf-turnstile-response"]': response}[selector] || null;
                },
                querySelectorAll: selector => selector === 'input[name="cf-turnstile-response"]' ? [response] : [widget]
              };
              const field = { querySelector: selector => ({
                '[data-turnstile-status]': status, '[data-turnstile-retry]': retry,
                '[data-workdoe-turnstile]': widget
              })[selector], querySelectorAll: () => [widget] };
              const widget = { isConnected: true, dataset: { sitekey: 'synthetic-key', action },
                closest: selector => selector === 'form' ? form : field };
              retry.closest = () => field;
              const script = { src: 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit',
                addEventListener(name, callback) { scriptHandlers[name] = callback; } };
              const document = {
                querySelector: selector => selector.startsWith('script[') ? script : null,
                querySelectorAll: () => [widget],
                addEventListener(name, callback, capture) { (handlers[name] ||= []).push({callback, capture}); }
              };
              const sdk = { ready() { throw Object.assign(new Error('Async SDK forbids ready()'), {code: 3857}); },
                render(node, config) { options.push(config); return 'synthetic-widget-' + options.length; },
                reset(id) { resets.push(id); response.value = ''; } };
              const window = { location: {href: 'https://workdoe.com/client/jobs/101/edit'} };
              if (ready) window.turnstile = sdk;
              vm.runInNewContext(source, {document, window, URL});
              function submit() {
                const event = { target: form, prevented: false, stopped: false,
                  preventDefault() { this.prevented = true; },
                  stopImmediatePropagation() { this.stopped = true; } };
                for (const handler of handlers.submit || []) if (handler.capture) handler.callback(event);
                return event;
              }
              return {handlers, scriptHandlers, sdk, window, options, resets,
                form, widget, notice, status, retry, response, submit};
            }
            """
        )
        result = subprocess.run(
            [node, "-e", fixture + assertions, str(SCRIPT)],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_page_boots_without_a_dialog_shell(self):
        self.run_script(
            """
            const page = setup();
            assert.equal(page.options.length, 1);
            assert.equal(page.widget.dataset.turnstileWidgetId, 'synthetic-widget-1');
            assert.equal(page.options[0].action, 'job-post');
            assert.equal(page.options[0].sitekey, 'synthetic-key');
            page.scriptHandlers.load();
            assert.equal(page.options.length, 1, 'Do not render twice');
            """
        )

    def test_late_api_load_renders_and_disconnected_forms_are_ignored(self):
        self.run_script(
            """
            const page = setup('job-post', false);
            assert.equal(page.options.length, 0);
            page.window.turnstile = page.sdk;
            page.scriptHandlers.load();
            assert.equal(page.options.length, 1);
            const detached = setup('job-post', false);
            detached.widget.isConnected = false;
            detached.window.turnstile = detached.sdk;
            detached.scriptHandlers.load();
            assert.equal(detached.options.length, 0);
            """
        )

    def test_partially_loaded_sdk_waits_for_render_without_calling_ready(self):
        self.run_script(
            """
            const page = setup('job-post', false);
            page.window.turnstile = { ready() { throw new Error('Do not call ready on async SDK'); } };
            page.scriptHandlers.load();
            assert.equal(page.options.length, 0);
            page.window.turnstile = page.sdk;
            page.scriptHandlers.load();
            assert.equal(page.options.length, 1);
            """
        )

    def test_retry_renders_after_a_failed_start_without_sdk_ready(self):
        self.run_script(
            """
            const page = setup('job-post', false);
            const originalRender = page.sdk.render;
            page.sdk.render = () => { throw new Error('Synthetic initial render failure'); };
            page.window.turnstile = page.sdk;
            page.scriptHandlers.load();
            assert.match(page.status.textContent, /could not start/);
            assert.equal(page.widget.dataset.turnstileWidgetId, undefined);
            page.sdk.render = originalRender;
            page.handlers.click[0].callback({target: {closest: () => page.retry}});
            assert.equal(page.widget.dataset.turnstileWidgetId, 'synthetic-widget-1');
            assert.equal(page.form.unsaved, 'Synthetic unsaved scope');
            """
        )

    def test_missing_token_blocks_submit_and_preserves_scope_for_each_action(self):
        self.run_script(
            """
            for (const action of ['job-post', 'match-request', 'report']) {
              const page = setup(action);
              const blocked = page.submit();
              assert.equal(blocked.prevented, true);
              assert.equal(blocked.stopped, true);
              assert.equal(page.form.unsaved, 'Synthetic unsaved scope');
              assert.equal(page.retry.focused, true);
              assert.match(page.notice.textContent, /Complete verification/);
              page.response.value = 'synthetic-response-only';
              page.options[0].callback('synthetic-response-only');
              assert.equal(page.notice.textContent, '');
              assert.equal(page.submit().prevented, false);
            }
            """
        )

    def test_provider_errors_expiry_and_retry_stay_with_their_own_widget(self):
        self.run_script(
            """
            const page = setup();
            page.options[0]['expired-callback']();
            assert.match(page.status.textContent, /expired/);
            page.options[0]['error-callback']();
            assert.match(page.status.textContent, /could not finish/);
            page.options[0]['timeout-callback']();
            assert.match(page.status.textContent, /timed out/);
            page.scriptHandlers.error();
            assert.match(page.status.textContent, /could not load/);
            const click = {target: {closest: () => page.retry}};
            page.handlers.click[0].callback(click);
            assert.deepEqual(page.resets, ['synthetic-widget-1']);
            assert.equal(page.form.unsaved, 'Synthetic unsaved scope');
            page.notice.textContent = 'An unrelated validation error';
            page.options[0].callback('synthetic-response-only');
            assert.equal(page.notice.textContent, 'An unrelated validation error');
            """
        )

    def test_retry_clears_old_response_when_sdk_reset_fails(self):
        self.run_script(
            """
            const page = setup();
            page.response.value = 'stale-synthetic-response';
            page.sdk.reset = () => { throw new Error('Synthetic reset failure'); };
            page.notice.textContent = 'Keep the original save failure';
            page.handlers.click[0].callback({target: {closest: () => page.retry}});
            assert.equal(page.response.value, '');
            assert.match(page.status.textContent, /could not restart/);
            assert.equal(page.notice.textContent, 'Keep the original save failure');
            assert.equal(page.form.unsaved, 'Synthetic unsaved scope');
            """
        )

    def test_edit_markup_exposes_verification_and_controller_is_versioned(self):
        module = load_app_shell_module()
        html = module.job_form_html(
            {"id": 1, "role": "client"}, "synthetic-key",
            job={"id": 101, "service_slug": "lawn-mowing", "title": "Synthetic test"},
            mode="edit", media_uploads_enabled=False,
        )
        self.assertIn('data-workdoe-turnstile="true"', html)
        self.assertIn('data-turnstile-status role="status"', html)
        self.assertIn('type="button" data-turnstile-retry', html)
        self.assertIn('data-action="job-post"', html)
        self.assertIn('/site-dialogs.js?v=asset-', html)
        self.assertNotIn('v=workdoe-bid-dialog', html)
