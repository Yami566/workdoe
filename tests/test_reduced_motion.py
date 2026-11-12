from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReducedMotionTests(unittest.TestCase):
    def run_script(self, script: str, filename: str) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for browser-controller regressions.")
        result = subprocess.run(
            [node, "-e", textwrap.dedent(script), str(ROOT / "workdoe/static" / filename)],
            capture_output=True, text=True, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_map_selection_and_reset_respect_reduced_motion_without_losing_selection(self):
        self.run_script(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            for (const reduced of [true, false, null]) {
              for (const useCluster of [true, false]) {
                const calls = { views: [], fits: [], pans: [], popups: 0, resized: false };
                const rowEvents = {}, resetEvents = {}, tileEvents = {};
                const row = {
                  dataset: {}, setAttribute() {}, removeAttribute() {},
                  classList: { toggle() {} }, matches: () => true,
                  getAttribute: () => 'fixture-1',
                  addEventListener: (name, fn) => { rowEvents[name] = fn; }
                };
                const mapElement = {
                  clientWidth: 620, clientHeight: 520,
                  getAttribute: name => ({
                    'data-tile-url': 'https://tiles.invalid/{z}/{x}/{y}.png',
                    'data-tile-attribution': 'Fixture attribution'
                  }[name] || ''),
                  classList: { add() {}, remove() {} }
                };
                const reset = { addEventListener: (name, fn) => { resetEvents[name] = fn; } };
                const seed = { textContent: JSON.stringify([
                  {id: 'fixture-1', title: 'Mow grass', lat: 38.9, lng: -77.0},
                  {id: 'fixture-2', title: 'Clean windows', lat: 39.0, lng: -77.1}
                ]) };
                const map = {
                  on() {},
                  invalidateSize() { calls.resized = true; },
                  setView(center, zoom, options) { calls.views.push(options); return this; },
                  fitBounds(bounds, options) {
                    assert.ok(calls.resized, 'measure the visible frame before fitting');
                    calls.fits.push(options);
                  },
                  panTo(center, options) { calls.pans.push(options); }
                };
                const layer = { addTo() {}, clearLayers() {}, addLayer() {} };
                const L = {
                  map(element, options) { calls.mapOptions = options; return map; },
                  layerGroup: () => layer,
                  tileLayer: () => ({
                    on(name, handler) { tileEvents[name] = handler; },
                    addTo() {}
                  }),
                  marker: () => ({
                    bindPopup() {}, on() {}, getLatLng: () => [38.9, -77],
                    openPopup() { calls.popups += 1; }
                  })
                };
                if (useCluster) {
                  L.markerClusterGroup = options => { calls.clusterOptions = options; return layer; };
                }
                const document = {
                  getElementById: id => id === 'lead-map' ? mapElement : id === 'map-jobs-data' ? seed : null,
                  querySelector: selector => selector === '[data-reset-map-view]' ? reset : null,
                  querySelectorAll: selector => selector.includes('[data-job-id]') ? [row] : [],
                  addEventListener: (name, fn) => { if (name === 'DOMContentLoaded') fn(); }
                };
                const window = {
                  L, location: { href: 'https://workdoe.invalid/' },
                  addEventListener() {}, setTimeout() {}
                };
                if (reduced !== null) {
                  window.matchMedia = query => ({matches: query.includes('reduced-motion') && reduced});
                }
                vm.runInNewContext(source, { document, window, URL });
                assert.deepEqual(Object.keys(tileEvents).sort(), ['load', 'loading', 'tileerror']);
                rowEvents.click({button: 0});
                resetEvents.click();
                const animate = reduced !== true;
                for (const key of ['zoomAnimation', 'fadeAnimation', 'markerZoomAnimation', 'inertia']) {
                  assert.equal(calls.mapOptions[key], animate, key);
                }
                if (useCluster) assert.equal(calls.clusterOptions.animate, animate);
                assert.equal(calls.pans.length, 1);
                assert.equal(calls.pans[0].animate, animate, 'project selection motion');
                assert.equal(calls.popups, 1, 'selection must still open its project');
                assert.equal(calls.fits.length, 1);
                const moveAnimation = reduced === true ? false : undefined;
                assert.equal(calls.views[0].animate, moveAnimation, 'initial view motion');
                assert.equal(calls.fits[0].animate, moveAnimation, 'initial bounds motion');
                assert.equal(calls.views.at(-1).animate, moveAnimation, 'DMV reset motion');
              }
            }
            """,
            "map.js",
        )

    def test_validation_focus_and_error_labels_survive_reduced_motion(self):
        self.run_script(
            """
            const assert = require('node:assert/strict');
            const fs = require('node:fs');
            const vm = require('node:vm');
            const source = fs.readFileSync(process.argv[1], 'utf8');
            (async () => {
              for (const reduced of [true, false, null]) {
                const listeners = {}, status = {}, calls = {}, attrs = {};
                const container = { appendChild(error) { calls.error = error; } };
                const control = {
                  name: 'title', type: 'text', dataset: {},
                  matches: selector => selector === 'input, select, textarea',
                  closest: selector => selector === 'label' ? container : null,
                  getAttribute: name => attrs[name] || null,
                  setAttribute: (name, value) => { attrs[name] = value; },
                  focus: options => { calls.focus = options; },
                  scrollIntoView: options => { calls.scroll = options; }
                };
                const button = { dataset: {}, disabled: false };
                const form = {
                  dataset: {jsonAction: '/api/jobs'},
                  matches: selector => selector === '[data-json-action]',
                  querySelector: selector => selector === '[data-form-status]' ? status : {value: 'fixture-id'},
                  querySelectorAll: selector => selector === 'input, select, textarea' ? [control] : [],
                  setAttribute() {}, removeAttribute() {}
                };
                const window = {};
                if (reduced !== null) window.matchMedia = () => ({matches: reduced});
                const document = {
                  addEventListener(name, fn) { (listeners[name] ||= []).push(fn); },
                  createElement: () => ({dataset: {}})
                };
                class FormData { forEach(fn) { fn('', 'title'); } }
                vm.runInNewContext(source, {
                  document, window, FormData,
                  fetch: async () => ({ok: false, json: async () => ({field_errors: {title: ['Add a title.']}})})
                });
                await listeners.submit[0]({target: form, submitter: button, preventDefault() {}});
                assert.equal(calls.scroll.behavior, reduced === true ? 'instant' : 'smooth');
                assert.equal(calls.scroll.block, 'center');
                assert.equal(calls.focus.preventScroll, true);
                assert.equal(attrs['aria-invalid'], 'true');
                assert.equal(attrs['aria-describedby'], 'worker-error-title');
                assert.equal(calls.error.textContent, 'Add a title.');
                assert.equal(status.textContent, 'Fix highlighted fields.');
                assert.equal(button.disabled, false);
              }
            })().catch(error => {console.error(error); process.exitCode = 1;});
            """,
            "worker-actions.js",
        )
