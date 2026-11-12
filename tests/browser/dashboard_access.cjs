"use strict";

// Loopback-only recovery UI; logout responses are synthetic, never provider calls.
const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");

if (!process.env.WORKDOE_PLAYWRIGHT_MODULE || !process.env.WORKDOE_CHROMIUM_EXECUTABLE) {
  throw new Error("Set the existing Playwright module and Chromium executable; this check installs nothing.");
}
const {chromium} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const output = path.join(root, ".test-tmp/dashboard-access-browser");
const fixture = JSON.parse(execFileSync("python", [path.join(__dirname, "dashboard_access_fixture.py")], {
  cwd: root, encoding: "utf8", windowsHide: true, maxBuffer: 1024 * 1024
}));
const mime = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2"};
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    if (fixture.pages[url.pathname]) {
      response.writeHead(403, fixture.headers); response.end(fixture.pages[url.pathname]); return;
    }
    if (url.pathname === "/login" || url.pathname === "/dashboard") {
      response.writeHead(200, {"Content-Type": "text/html"});
      response.end("<!doctype html><title>Synthetic navigation target</title><h1>Synthetic navigation target</h1>");
      return;
    }
    const file = path.resolve(staticRoot, "." + url.pathname);
    if (!file.startsWith(staticRoot + path.sep)) throw new Error("Outside fixture");
    const bytes = await fs.readFile(file);
    response.writeHead(200, {"Content-Type": mime[path.extname(file)] || "application/octet-stream"});
    response.end(bytes);
  } catch {
    response.writeHead(404); response.end();
  }
});

async function runCase(browser, base, viewport, location, scale, javaScriptEnabled) {
  const context = await browser.newContext({viewport, javaScriptEnabled, serviceWorkers: "block"});
  const requests = [], errors = [], external = [];
  let failLogout = false;
  try {
    await context.route("**/*", route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== base) { external.push(url.origin); return route.abort("blockedbyclient"); }
      if (url.pathname === "/api/auth/logout") {
        requests.push({method: request.method(), marker: request.headers()["x-workdoe-request"], body: request.postData()});
        return route.fulfill({status: failLogout ? 503 : 200, contentType: "application/json",
          body: JSON.stringify(failLogout ? {error: "Synthetic sign-out unavailable. Try again."} : {ok: true})});
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(base + location, {waitUntil: "load"});
    await page.evaluate(value => { document.documentElement.style.fontSize = value + "%"; }, scale);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    const heading = page.getByRole("heading", {level: 1});
    assert.match(await heading.innerText(), /^Use a (consumer|contractor) account$/);
    const workspace = page.getByRole("link", {name: "Open my workspace", exact: true});
    const switchButton = page.getByRole("button", {name: "Sign out and switch account", exact: true});
    await workspace.focus();
    if (javaScriptEnabled) {
      await page.keyboard.press("Tab");
      assert.equal(await switchButton.evaluate(node => document.activeElement === node), true);
      await switchButton.scrollIntoViewIfNeeded();
      assert.equal(await switchButton.evaluate(node => {
        const bounds = node.getBoundingClientRect();
        const hit = document.elementFromPoint(bounds.left + bounds.width / 2, bounds.top + bounds.height / 2);
        return node === hit || node.contains(hit);
      }), true);
    }
    assert.equal(requests.length, 0, "Opening/focusing recovery must not sign out");
    if (javaScriptEnabled && scale === 100) {
      await page.screenshot({path: path.join(output, `${location.split("/")[1]}-${viewport.width}.png`), fullPage: true});
    }
    await workspace.click();
    await page.waitForURL(base + "/dashboard");
    assert.equal(requests.length, 0, "Returning to own workspace must not sign out");
    if (javaScriptEnabled) {
      await page.goto(base + location, {waitUntil: "load"});
      failLogout = true;
      await switchButton.click();
      await page.getByRole("status").filter({hasText: "Synthetic sign-out unavailable"}).waitFor();
      assert.equal(new URL(page.url()).pathname, location);
      assert.equal(await switchButton.isEnabled(), true);
      assert.equal(requests.length, 1);
      failLogout = false;
      await switchButton.focus();
      await page.keyboard.press("Enter");
      await page.waitForURL(url => url.pathname === "/login" && url.searchParams.get("next") === location);
      assert.equal(requests.length, 2);
      for (const request of requests) {
        assert.equal(request.method, "POST");
        assert.equal(request.marker, "same-origin");
        const payload = JSON.parse(request.body);
        assert.deepEqual(Object.keys(payload), ["idempotency_key"]);
        assert.match(payload.idempotency_key, /^[a-f0-9-]{32,36}$/);
      }
    }
    assert.deepEqual(external, []); assert.deepEqual(errors, []);
    return {viewport, location, scale, javaScriptEnabled, noOverflow: true,
      ownWorkspaceLink: true, explicitLogoutAndRetry: javaScriptEnabled,
      providerSessionRevocationNotTested: true};
  } finally { await context.close(); }
}

(async () => {
  let browser;
  try {
    await fs.mkdir(output, {recursive: true});
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const base = "http://127.0.0.1:" + server.address().port;
    browser = await chromium.launch({executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE,
      headless: true, chromiumSandbox: true});
    const cases = [];
    for (const viewport of [{width: 390, height: 844}, {width: 820, height: 1180}, {width: 1280, height: 720}]) {
      for (const location of Object.keys(fixture.pages)) {
        for (const scale of [100, 200]) cases.push(await runCase(browser, base, viewport, location, scale, true));
        cases.push(await runCase(browser, base, viewport, location, 100, false));
      }
    }
    await fs.writeFile(path.join(output, "result.local.json"), JSON.stringify({passed: cases.length, cases}, null, 2));
    console.log(JSON.stringify({passed: cases.length, output}));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
