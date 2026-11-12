"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const {createHash} = require("node:crypto");
const {mkdir, readFile} = require("node:fs/promises");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const {chromium, webkit} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const {documents, pins} = JSON.parse(execFileSync(process.env.WORKDOE_PYTHON || "python",
  ["tests/test_clerk_entry_integrity.py"], {cwd: root, encoding: "utf8", windowsHide: true,
    env: {...process.env, PYTHONPATH: root}}));
const origin = "http://127.0.0.1:19861";
const fixtures = Object.entries(pins).map(([name, pin], index) => {
  const marker = "clerkFixture" + index;
  const bytes = "window." + marker + " = true;";
  return {name, url: "/__clerk" + pin.script_path, marker, bytes,
    reviewed: pin.script_integrity, fixture: "sha384-" + createHash("sha384").update(bytes).digest("base64")};
});
const mime = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".webp": "image/webp",
  ".png": "image/png", ".geojson": "application/geo+json"};

async function verify(browser, mode, damaged, recovery = "") {
  const viewport = recovery === "stalled-body" ? {width: 320, height: 568} : {width: 390, height: 844};
  const context = await browser.newContext({viewport, serviceWorkers: "block",
    javaScriptEnabled: recovery !== "no-js"});
  const external = [];
  const fragmentRequests = [];
  let releaseStall;
  const stalledResponse = new Promise(resolve => { releaseStall = resolve; });
  let stallActive = recovery === "stalled-script";
  let tamper = damaged;
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) {
      external.push(url.origin);
      return route.abort();
    }
    if (url.pathname === "/login" && url.searchParams.get("embed") === "1") {
      fragmentRequests.push(route.request().method());
      if (recovery === "stalled-fragment" && fragmentRequests.length === 1) {
        await stalledResponse;
        return route.abort().catch(() => {});
      }
    }
    const fixture = fixtures.find(item => item.url === url.pathname);
    if (fixture) {
      if (stallActive && fixture === fixtures[0]) {
        await stalledResponse;
        return route.abort().catch(() => {});
      }
      return route.fulfill({contentType: "application/javascript",
        body: fixture.name === tamper ? "window.unreviewedClerkExecuted = true;" : fixture.bytes});
    }
    if (recovery === "blocked-boot" && url.pathname === "/clerk-entry.js") return route.abort();
    if (recovery === "stalled-map" && url.pathname === "/vendor/leaflet/leaflet.js") await stalledResponse;
    if (url.pathname === "/api/jobs/open") return route.fulfill({status: 503, json: {ok: false}});
    const doc = documents[url.pathname + url.search];
    if (doc) {
      // Replace only the verified entry digests in the fixture HTML; no Clerk code runs.
      const body = fixtures.reduce((html, item) => html.replaceAll(item.reviewed, item.fixture), doc.html);
      return route.fulfill({contentType: "text/html", headers: {"Content-Security-Policy": doc.csp}, body});
    }
    const asset = path.resolve(staticRoot, "." + url.pathname);
    const contentType = mime[path.extname(asset)];
    if (contentType && asset.startsWith(staticRoot + path.sep)) {
      try {
        return await route.fulfill({contentType, body: await readFile(asset)});
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }
    return route.fulfill({status: 404});
  });
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(7000);
    if (mode === "dialog" && recovery.startsWith("stalled-")) await page.clock.install();
    if (recovery === "stalled-body") {
      await page.addInitScript(() => {
        const fetch = window.fetch;
        let held = false;
        window.fetch = async (...args) => {
          const response = await fetch(...args);
          if (!held && new URL(args[0], location.href).pathname === "/login") {
            held = true;
            const read = response.text.bind(response);
            response.text = async () => {
              const html = await read();
              return new Promise(resolve => {
                window.releaseDialogBody = () => resolve(html.replace("Use your email code", "Stale response"));
              });
            };
          }
          return response;
        };
      });
    }
    const direct = mode !== "dialog";
    const pathname = mode === "signup" ? "/create-account" : direct ? "/login" : "/";
    const heldMap = recovery === "stalled-map"
      ? page.waitForRequest(origin + "/vendor/leaflet/leaflet.js") : null;
    await page.goto(origin + pathname, {
      waitUntil: recovery === "stalled-map" || recovery === "stalled-script" && direct ? "commit" : "load",
    });
    if (recovery === "stalled-map") {
      await heldMap;
      const trigger = page.getByRole("navigation", {name: "Primary"})
        .getByRole("link", {name: "Sign in", exact: true});
      if (!direct) await trigger.press("Enter");
      const surface = direct ? page : page.getByRole("dialog");
      await surface.locator('[data-clerk-initialized="true"]').waitFor({state: "attached"});
      assert.equal(await page.evaluate(() => Boolean(window.L)), false, "Leaflet must still be held");
      releaseStall();
      if (direct) {
        await page.getByRole("tab", {name: "Map", exact: true}).click();
      }
      await page.locator("#lead-map .leaflet-overlay-pane path").first().waitFor();
      if (!direct) {
        assert.equal(new URL(page.url()).pathname, "/login");
        assert.ok(await surface.evaluate(node => node.contains(document.activeElement)));
        await page.keyboard.press("Escape");
        await surface.waitFor({state: "hidden"});
        assert.ok(await trigger.evaluate(node => node === document.activeElement));
        assert.equal(new URL(page.url()).pathname, "/");
      }
      assert.deepEqual(external, []);
      process.stdout.write(`PASS: ${mode}, ${recovery}\n`);
      return;
    }
    if (recovery) {
      if (recovery === "stalled-body") {
        await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      }
      const trigger = page.getByRole("navigation", {name: "Primary"}).getByRole("link", {name: "Sign in", exact: true});
      const background = page.url();
      if (!direct) {
        const requested = page.waitForRequest(origin + (recovery === "stalled-script"
          ? fixtures[0].url : "/login?embed=1"));
        await trigger.click();
        await requested;
        if (recovery === "stalled-body") await page.waitForFunction(() => window.releaseDialogBody);
        await page.clock.runFor(recovery === "stalled-script" ? 16000 : 13000);
      }
      const surface = direct ? page : page.getByRole("dialog");
      const webkit = browser.browserType().name() === "webkit";
      if (direct) {
        const fallback = surface.locator("[data-clerk-load-fallback]");
        await fallback.getByRole("link", {name: "Try again", exact: true}).waitFor();
        await fallback.getByRole("link", {name: "Browse projects", exact: true}).waitFor();
        assert.equal(await surface.getByText("Loading secure email sign-in...", {exact: true}).isVisible(), false);
      } else {
        const fullPage = surface.getByRole("link", {name: "Open full page"});
        await fullPage.waitFor();
        assert.equal(await fullPage.getAttribute("href"), "/login");
        assert.equal(await surface.getAttribute("aria-busy"), null);
        const retry = surface.getByRole("button", {name: "Try again", exact: true});
        assert.ok(await retry.evaluate(node => node === document.activeElement));
        // The Windows WebKit runner does not include links in sequential focus.
        if (webkit) await fullPage.focus();
        else await page.keyboard.press("Tab");
        assert.ok(await fullPage.evaluate(node => node === document.activeElement));
        const linkBox = await fullPage.boundingBox();
        assert.ok(linkBox.x >= 0 && linkBox.y >= 0 && linkBox.x + linkBox.width <= viewport.width
          && linkBox.y + linkBox.height <= viewport.height);
        if (webkit) await retry.focus();
        else await page.keyboard.press("Shift+Tab");
        assert.ok(await retry.evaluate(node => node === document.activeElement));
      }
      // This WebKit fixture waits for fonts behind the intentionally stalled deferred script.
      if (!(webkit && direct && recovery === "stalled-script")) {
        const output = path.join(root, ".test-tmp", "clerk-entry-recovery", webkit ? "after-webkit" : "after");
        await mkdir(output, {recursive: true});
        await page.screenshot({path: path.join(output, mode + "-" + recovery + ".png"), animations: "disabled"});
      }
      if (direct && recovery === "no-js") {
        const browse = surface.locator("[data-clerk-load-fallback]").getByRole("link", {name: "Browse projects"});
        await browse.focus();
        await Promise.all([page.waitForURL(origin + "/"), browse.press("Enter")]);
      }
      if (!direct) {
        const compact = await surface.locator(".site-dialog-surface").boundingBox();
        assert.ok(compact.height < (recovery === "stalled-body" ? 410 : 300), `Recovery height: ${compact.height}px`);
        const retry = surface.getByRole("button", {name: "Try again", exact: true});
        const historyLength = await page.evaluate(() => history.length);
        const dialogUrl = page.url();
        stallActive = false;
        releaseStall();
        await page.keyboard.press("Enter");
        await surface.locator('[data-clerk-initialized="true"]').waitFor({state: "attached"});
        await surface.locator('[data-site-dialog-status]').waitFor({state: "hidden"});
        assert.equal(await surface.getAttribute("aria-busy"), null);
        assert.equal(await retry.count(), 0);
        assert.equal(page.url(), dialogUrl);
        assert.equal(await page.evaluate(() => history.length), historyLength);
        assert.deepEqual(fragmentRequests, ["GET", "GET"]);
        if (recovery === "stalled-body") {
          await page.evaluate(() => window.releaseDialogBody());
          await page.clock.runFor(50);
          assert.equal(await surface.getByText("Stale response", {exact: false}).count(), 0);
        }
        await page.keyboard.press("Escape");
        await surface.waitFor({state: "hidden"});
        assert.ok(await trigger.evaluate(link => document.activeElement === link));
        assert.equal(page.url(), background);
      }
      assert.deepEqual(external, []);
      process.stdout.write(`PASS: ${mode}, ${recovery}\n`);
      return;
    }
    const state = () => page.evaluate(markers => ({
      loaded: markers.map(marker => Boolean(window[marker])),
      unreviewed: Boolean(window.unreviewedClerkExecuted),
    }), fixtures.map(item => item.marker));

    if (mode === "direct") {
      for (const fixture of fixtures) {
        const src = page.locator(`script[src="${fixture.url}"]`);
        assert.equal(await src.getAttribute("integrity"), fixture.fixture);
      }
      assert.deepEqual(await state(), {loaded: fixtures.map(item => item.name !== damaged), unreviewed: false});
      if (damaged) {
        await page.locator("[data-clerk-load-fallback]").getByRole("link", {name: "Try again", exact: true}).waitFor();
      }
    } else {
      const trigger = page.getByRole("navigation", {name: "Primary"}).getByRole("link", {name: "Sign in", exact: true});
      await trigger.click();
      const dialog = page.getByRole("dialog");
      if (damaged) {
        const fallback = dialog.getByRole("link", {name: "Open full page"});
        await fallback.waitFor({state: "visible"});
        assert.equal(await fallback.getAttribute("href"), "/login");
        assert.equal((await state()).unreviewed, false);
        await page.keyboard.press("Escape");
        await dialog.waitFor({state: "hidden"});
        assert.equal(await trigger.evaluate(link => document.activeElement === link), true);
        tamper = null;
        await trigger.click();
      }
      await dialog.locator("[data-clerk-entry]").waitFor({state: "attached"});
      await page.waitForFunction(markers => markers.every(marker => window[marker]), fixtures.map(item => item.marker));
      assert.deepEqual(await state(), {loaded: [true, true], unreviewed: false});
      for (const fixture of fixtures) {
        const scripts = page.locator(`script[src="${origin + fixture.url}"]`);
        assert.ok(await scripts.count());
        assert.equal(await scripts.last().getAttribute("integrity"), fixture.fixture);
      }
    }
    assert.deepEqual(external, []);
    process.stdout.write(`PASS: ${mode}, ${damaged || "matching bytes"}\n`);
  } finally {
    releaseStall();
    await context.unrouteAll({behavior: "wait"});
    await context.close();
  }
}

async function main() {
  const engine = process.argv.includes("--webkit") ? webkit : chromium;
  const browser = await engine.launch(engine === webkit ? {} : {executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE});
  try {
    if (process.argv.includes("--map-independence")) {
      for (const mode of ["direct", "signup", "dialog"]) await verify(browser, mode, null, "stalled-map");
      return;
    }
    if (process.argv.includes("--recovery")) {
      await verify(browser, "direct", null, "no-js");
      await verify(browser, "direct", null, "stalled-script");
      await verify(browser, "dialog", null, "stalled-fragment");
      await verify(browser, "dialog", null, "stalled-body");
      await verify(browser, "dialog", null, "stalled-script");
      await verify(browser, "direct", null, "blocked-boot");
      return;
    }
    for (const mode of ["direct", "dialog"]) {
      for (const damaged of [null, ...fixtures.map(item => item.name)]) await verify(browser, mode, damaged);
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
