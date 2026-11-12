"use strict";

// Synthetic Turnstile/HTTP boundary only. Never solves a real challenge or calls Siteverify.
const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");
if (!process.env.WORKDOE_PLAYWRIGHT_MODULE || !process.env.WORKDOE_CHROMIUM_EXECUTABLE) {
  throw new Error("Set the already installed Playwright and Chromium paths; no installation is performed.");
}
const {chromium} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const output = path.join(root, ".test-tmp/turnstile-browser");
const fixture = JSON.parse(execFileSync("python", [path.join(__dirname, "turnstile_fixture.py")], {
  cwd: root, encoding: "utf8", windowsHide: true, maxBuffer: 2 * 1024 * 1024
}));
const sdk = `(() => {
  if (window.turnstile) return;
  const asyncLoad = Boolean(document.currentScript && (document.currentScript.async || document.currentScript.defer));
  const widgets = new Map();
  let next = 0;
  window.__verificationFixture = {widgets, completions: 0, resets: [], removes: [], readyCalls: 0};
  window.turnstile = {
    ready(callback) {
      window.__verificationFixture.readyCalls++;
      if (asyncLoad) throw Object.assign(new Error('Async SDK forbids ready()'), {code: 3857});
      callback();
    },
    render(element, options) {
      if (window.__failRenderOnce) { window.__failRenderOnce = false; throw new Error('Synthetic render failure'); }
      const id = 'synthetic-' + (++next);
      const input = document.createElement('input'); input.type = 'hidden';
      input.name = 'cf-turnstile-response'; element.appendChild(input);
      const label = document.createElement('span'); label.textContent = 'Synthetic verification control'; element.appendChild(label);
      widgets.set(id, {element, options, input}); return id;
    },
    reset(id) { const value = widgets.get(id); if (value) value.input.value = ''; window.__verificationFixture.resets.push(id); },
    remove(id) { const value = widgets.get(id); if (value) value.element.replaceChildren(); widgets.delete(id); window.__verificationFixture.removes.push(id); }
  };
  window.__completeFixture = id => { const value = widgets.get(id); const token = 'synthetic-response-' + (++window.__verificationFixture.completions);
    value.input.value = token; value.options.callback(token); };
  window.__expireFixture = id => { const value = widgets.get(id); value.input.value = ''; value.options['expired-callback'](); };
})();`;
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    const page = fixture.pages[url.pathname + url.search] || fixture.pages[url.pathname];
    if (page) { response.writeHead(200, {"Content-Type": "text/html"}); response.end(page); return; }
    if (url.pathname === "/client/jobs/101") {
      response.writeHead(200, {"Content-Type": "text/html"}); response.end("<!doctype html><h1>Synthetic saved target</h1>"); return;
    }
    const file = path.resolve(staticRoot, "." + url.pathname);
    if (!file.startsWith(staticRoot + path.sep)) throw new Error("Outside fixture");
    const bytes = await fs.readFile(file);
    response.writeHead(200, {"Content-Type": {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}[path.extname(file)] || "application/octet-stream"});
    response.end(bytes);
  } catch { response.writeHead(404); response.end(); }
});

async function runCase(browser, base, viewport, surface, mode) {
  const context = await browser.newContext({viewport, serviceWorkers: "block"});
  const external = [], posts = [], errors = [];
  let blocked = mode === "blocked", release;
  const delayed = new Promise(resolve => { release = resolve; });
  try {
    if (mode === "render-error") await context.addInitScript(() => { window.__failRenderOnce = true; });
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === "https://challenges.cloudflare.com" && url.pathname === "/turnstile/v0/api.js") {
        if (blocked) return route.abort("blockedbyclient");
        if (mode === "late" || mode === "hang") await delayed;
        return route.fulfill({status: 200, contentType: "text/javascript", body: sdk});
      }
      if (url.origin !== base) { external.push(url.origin); return route.abort("blockedbyclient"); }
      if (request.method() === "POST" && url.pathname.startsWith("/api/")) {
        posts.push({path: url.pathname, payload: request.postDataJSON(), marker: request.headers()["x-workdoe-request"]});
        return route.fulfill({status: 400, contentType: "application/json", body: JSON.stringify({error: "Synthetic transport rejection; no live data was saved."})});
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(error.message));
    const location = surface === "dialog" ? "/leads" : surface === "bare" ? "/standalone-edit" : "/client/jobs/101/edit";
    const useFullPage = surface === "dialog" && mode === "blocked" && viewport.width === 390;
    await page.goto(base + location, {waitUntil: "domcontentloaded"});
    if (surface === "dialog") await page.getByRole("link", {name: "Open synthetic lead"}).click();
    if (surface === "dialog" && mode === "blocked") {
      const fullPage = page.getByRole("link", {name: "Open full page"});
      await fullPage.waitFor();
      blocked = false;
      if (useFullPage) {
        await fullPage.click();
        await page.waitForURL(base + "/jobs/101");
      } else {
        await page.getByRole("dialog").getByRole("button", {name: "Try again", exact: true}).click();
        await page.getByRole("dialog").locator("form.bid-form").waitFor();
      }
    }
    const form = page.locator(surface === "dialog" ? "form.bid-form" : 'form[data-json-action="/api/jobs/101/update"]');
    await form.waitFor();
    const scope = form.locator(surface === "dialog" ? '[name="scope_note"]' : '[name="description"]');
    const unsaved = "Synthetic unsaved scope kept through verification recovery.";
    await scope.fill(unsaved);
    if (surface === "dialog") {
      await form.locator('[name="price_range"]').fill("TEST ONLY $10-$20");
      await form.locator('[name="timeline"]').fill("Test only");
      await form.locator('[name="availability"]').fill("No booking intended");
      await form.locator('[name="experience"]').fill("Synthetic local test only; no qualifications claimed.");
    }
    const submit = form.locator('button[type="submit"]');
    await submit.click();
    assert.equal(posts.length, 0, "Missing verification must not reach the endpoint");
    assert.equal(await scope.inputValue(), unsaved);
    await form.locator('[data-form-status]').filter({hasText: "Complete verification"}).waitFor();
    if (mode === "blocked" && surface !== "dialog") {
      await form.getByRole("button", {name: "Retry verification"}).click();
      await form.locator('[data-turnstile-status]').filter({hasText: "Check your connection"}).waitFor();
      assert.equal(await form.getByRole("button", {name: "Retry verification"}).isEnabled(), true);
      assert.equal(posts.length, 0);
      blocked = false;
      await form.getByRole("button", {name: "Retry verification"}).click();
    } else if (mode === "hang") {
      await form.getByRole("button", {name: "Retry verification"}).click();
      await form.locator('[data-turnstile-status]').filter({hasText: "Check your connection"}).waitFor({timeout: 20000});
      assert.equal(await form.getByRole("button", {name: "Retry verification"}).isEnabled(), true);
      assert.equal(await scope.inputValue(), unsaved);
      assert.equal(posts.length, 0);
    } else if (mode === "render-error") {
      await form.locator('[data-turnstile-status]').filter({hasText: "could not start"}).waitFor();
      await form.getByRole("button", {name: "Retry verification"}).click();
    }
    release();
    const widget = form.locator('[data-workdoe-turnstile]');
    await page.waitForFunction(() => [...document.querySelectorAll('[data-workdoe-turnstile]')].some(node => node.dataset.turnstileWidgetId));
    const id = await widget.getAttribute("data-turnstile-widget-id");
    assert.ok(id);
    await page.evaluate(id => window.__completeFixture(id), id);
    if (mode === "expired") {
      await page.evaluate(id => window.__expireFixture(id), id);
      await submit.click();
      assert.equal(posts.length, 0);
      await form.getByRole("button", {name: "Retry verification"}).click();
      assert.equal(await page.evaluate(id => window.__verificationFixture.resets.includes(id), id), true);
      await page.evaluate(id => window.__completeFixture(id), id);
    }
    assert.equal(await scope.inputValue(), unsaved);
    await form.locator('[data-turnstile-status]').filter({hasText: "Verification complete"}).waitFor();
    await submit.click();
    await form.locator('[data-form-status]').filter({hasText: "Synthetic transport rejection"}).waitFor();
    assert.equal(posts.length, 1, surface + " " + mode + " must send exactly one request");
    assert.match(posts[0].payload["cf-turnstile-response"], /^synthetic-response-/);
    assert.equal(posts[0].marker, "same-origin");
    assert.equal(posts[0].payload[surface === "dialog" ? "scope_note" : "description"], unsaved);
    assert.equal(await scope.inputValue(), unsaved);
    assert.equal(await form.locator('input[name="cf-turnstile-response"]').inputValue(), "");
    await form.locator('[data-turnstile-status]').filter({hasText: "Verify again before saving"}).waitFor();
    await submit.click();
    assert.equal(posts.length, 1, "A consumed/reset challenge must be renewed before retry");
    if (surface === "dialog" && !useFullPage) {
      await page.keyboard.press("Escape");
      await page.waitForURL(base + "/leads");
      assert.ok(await page.evaluate(id => window.__verificationFixture.removes.includes(id), id));
      assert.equal(await page.getByRole("link", {name: "Open synthetic lead"}).evaluate(node => document.activeElement === node), true);
    }
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    assert.equal(await page.evaluate(() => window.__verificationFixture.readyCalls), 0);
    if (surface === "edit" && mode === "blocked" && [390, 1280].includes(viewport.width)) {
      await page.screenshot({path: path.join(output, "edit-recovery-" + viewport.width + ".png"), fullPage: true});
    }
    return {viewport, surface, mode, emptySubmissionBlocked: true, scopePreserved: true,
      exactOneTokenizedRequest: true, consumedRetryBlocked: true, providerNotTested: true};
  } finally { release(); await context.close(); }
}

async function runEditOutcome(browser, base, viewport, outcome) {
  const context = await browser.newContext({viewport, serviceWorkers: "block"});
  const posts = [], external = [];
  const title = "TEST ONLY - Synthetic edit recovery";
  const description = "Owner-controlled beta test. No actual work is requested. Please do not bid.";
  try {
    await context.route("**/*", async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === "https://challenges.cloudflare.com" && url.pathname === "/turnstile/v0/api.js") {
        return route.fulfill({status: 200, contentType: "text/javascript", body: sdk});
      }
      if (url.origin !== base) { external.push(url.origin); return route.abort(); }
      if (request.method() === "POST" && url.pathname === "/api/jobs/101/update") {
        posts.push(request.postDataJSON());
        const invalid = posts.length === 1;
        const payload = !invalid ? {ok: true, job_id: 101, url: "/client/jobs/101"}
          : outcome === "field-error" ? {ok: false, field_errors: {desired_date: ["Choose today or a future desired date."]}}
          : {ok: false, error: "Could not confirm your changes were saved. Keep this form open and check Projects before retrying."};
        return route.fulfill({status: invalid ? outcome === "field-error" ? 400 : 503 : 200,
          contentType: "application/json", body: JSON.stringify(payload)});
      }
      return route.continue();
    });
    const page = await context.newPage();
    await page.goto(base + "/client/jobs/101/edit");
    const form = page.locator('form[data-json-action="/api/jobs/101/update"]');
    await form.locator('[name="title"]').fill(title);
    await form.locator('[name="description"]').fill(description);
    if (outcome === "field-error") await form.locator('[name="desired_date"]').fill("2000-01-01");
    const widget = form.locator('[data-workdoe-turnstile]');
    await page.waitForFunction(() => document.querySelector('[data-workdoe-turnstile]').dataset.turnstileWidgetId);
    const id = await widget.getAttribute("data-turnstile-widget-id");
    await page.evaluate(id => window.__completeFixture(id), id);
    await form.locator('button[type="submit"]').click();
    await form.locator('[data-form-status]').filter({hasText: outcome === "field-error" ? "Fix highlighted fields" : "Could not confirm"}).waitFor();
    assert.equal(new URL(page.url()).pathname, "/client/jobs/101/edit");
    assert.equal(await form.locator('[name="title"]').inputValue(), title);
    assert.equal(await form.locator('[name="description"]').inputValue(), description);
    assert.equal(await form.locator('button[type="submit"]').isEnabled(), true);
    assert.equal(await form.locator('input[name="cf-turnstile-response"]').inputValue(), "");
    await form.locator('[data-turnstile-status]').filter({hasText: "Verify again before saving"}).waitFor();
    if (outcome === "field-error") {
      assert.equal(await form.locator('[name="desired_date"]').getAttribute("aria-invalid"), "true");
      assert.equal(await form.locator('[name="desired_date"]').evaluate(node => node === document.activeElement), true);
    }
    if (viewport.width === 390) await page.screenshot({path: path.join(output, "edit-" + outcome + "-390.png"), fullPage: true});
    if (outcome === "field-error") await form.locator('[name="desired_date"]').fill("");
    await page.evaluate(id => window.__completeFixture(id), id);
    await form.locator('button[type="submit"]').click();
    await page.waitForURL(base + "/client/jobs/101");
    assert.equal(posts.length, 2);
    assert.equal(posts[1].title, title);
    assert.equal(posts[1].description, description);
    assert.notEqual(posts[0]["cf-turnstile-response"], posts[1]["cf-turnstile-response"]);
    assert.deepEqual(external, []);
    return {viewport, outcome, editPreserved: true, retrySucceeded: true, providerNotTested: true};
  } finally { await context.close(); }
}

(async () => {
  let browser;
  try {
    await fs.mkdir(output, {recursive: true});
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const base = "http://127.0.0.1:" + server.address().port;
    browser = await chromium.launch({headless: true, chromiumSandbox: true, executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE});
    const cases = [];
    for (const viewport of [{width: 390, height: 844}, {width: 820, height: 1180}, {width: 1280, height: 720}]) {
      for (const surface of ["edit", "bare", "dialog"]) {
        for (const mode of ["ready", "late", "blocked", "render-error", "expired"]) {
          cases.push(await runCase(browser, base, viewport, surface, mode));
        }
      }
    }
    cases.push(await runCase(browser, base, {width: 390, height: 844}, "bare", "hang"));
    for (const viewport of [{width: 390, height: 844}, {width: 820, height: 1180}, {width: 1280, height: 720}]) {
      for (const outcome of ["field-error", "storage-error"]) cases.push(await runEditOutcome(browser, base, viewport, outcome));
    }
    await fs.writeFile(path.join(output, "result.local.json"), JSON.stringify({passed: cases.length, cases}, null, 2));
    console.log(JSON.stringify({passed: cases.length, output, realVerificationNotTested: true}));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
