from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkerFormTurnstileTests(unittest.TestCase):
    def test_review_includes_the_scope_as_text_without_interpreting_html(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for form regressions.")
        script = textwrap.dedent(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            const scope = '<b>Literal scope, not markup</b>\\nSecond line';
            const review = { textContent: '' };
            Object.defineProperty(review, 'innerHTML', {
              set() { throw new Error('Scope must never be interpreted as HTML'); }
            });
            const composer = {
              dataset: {}, elements: { description: { value: scope } },
              querySelectorAll: () => [],
              querySelector: (selector) => selector === '[data-review-description]' ? review : null,
              classList: { add() {} }, addEventListener() {}
            };
            vm.runInNewContext(source, { document: { querySelector: () => composer } });
            assert.equal(review.textContent, scope);
            """
        )
        result = subprocess.run(
            [node, "-e", script, str(ROOT / "workdoe" / "static" / "project-composer.js")],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_failed_submit_refreshes_only_its_own_widget_and_preserves_scope(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for form regressions.")
        script = textwrap.dedent(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            (async () => {
              for (const mode of ['ready', 'sdk-missing', 'reset-error', 'new-success', 'unrendered']) {
                const listeners = {}, status = {}, resets = [];
                const response = {value: 'fixture-response'};
                const verification = {textContent: 'Verification complete.'};
                const foreign = {value: 'other-form-response', textContent: 'Verification complete.'};
                const field = {querySelector: () => verification};
                const widget = {dataset: mode === 'unrendered' ? {} : {turnstileWidgetId: 'project-widget'},
                  closest: () => field};
                const button = {dataset: {}, disabled: false};
                const form = {
                  dataset: {jsonAction: '/api/jobs'}, description: 'Synthetic unsaved project scope',
                  matches: selector => selector === '[data-json-action]',
                  querySelector: selector => selector === '[data-form-status]' ? status : {value: 'fixture-request-id'},
                  querySelectorAll: selector => selector === 'input[name="cf-turnstile-response"]' ? [response]
                    : ['[data-turnstile-widget-id]', '[data-workdoe-turnstile]'].includes(selector) ? [widget] : [],
                  setAttribute() {}, removeAttribute() {}
                };
                const document = {addEventListener(name, callback) { (listeners[name] ||= []).push(callback); }};
                class FormData {
                  forEach(callback) { callback(response.value, 'cf-turnstile-response'); }
                }
                const window = mode === 'sdk-missing' ? {} : {turnstile: {reset(id) {
                  resets.push(id);
                  if (mode === 'reset-error') throw new Error('Synthetic reset failure');
                  response.value = '';
                  if (mode === 'new-success') {
                    response.value = 'fresh-synthetic-response';
                    verification.textContent = 'Verification complete.';
                  }
                }}};
                vm.runInNewContext(source, {document, window, FormData,
                  fetch: async () => ({ok: false, json: async () => ({error: 'Turnstile verification failed.'})})});
                let prevented = false;
                await listeners.submit[0]({target: form, submitter: button, preventDefault() { prevented = true; }});
                assert.equal(prevented, true);
                assert.deepEqual(resets, ['sdk-missing', 'unrendered'].includes(mode) ? [] : ['project-widget']);
                assert.equal(button.disabled, false);
                assert.equal(form.description, 'Synthetic unsaved project scope');
                assert.equal(status.textContent, 'Turnstile verification failed.');
                assert.equal(response.value, mode === 'new-success' ? 'fresh-synthetic-response' : '', mode);
                assert.match(verification.textContent, mode === 'new-success' ? /Verification complete/
                  : mode === 'reset-error' ? /could not restart/ : /Verify again before saving/, mode);
                assert.deepEqual(foreign, {value: 'other-form-response', textContent: 'Verification complete.'});
              }
            })().catch(error => { console.error(error); process.exitCode = 1; });
            """
        )
        result = subprocess.run(
            [node, "-e", script, str(ROOT / "workdoe" / "static" / "worker-actions.js")],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
