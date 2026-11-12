"use strict";

// Read the real SDK contract, but block every challenge frame and submission.
const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");
if (!process.env.WORKDOE_PLAYWRIGHT_MODULE || !process.env.WORKDOE_CHROMIUM_EXECUTABLE) {
  throw new Error("Set existing Playwright and Chromium paths; no software is installed.");
}
const {chromium} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const root = path.resolve(__dirname, "../..");
const fixture = JSON.parse(execFileSync("python", ["tests/browser/turnstile_fixture.py"], {cwd: root, encoding: "utf8", windowsHide: true}));
const html = fixture.pages["/client/jobs/101/edit"].replaceAll("synthetic-key", "1x00000000000000000000AA");
const baselineRef = process.env.WORKDOE_TURNSTILE_BASELINE_REF;
const baseline = baselineRef ? execFileSync("git", ["show", baselineRef + ":workdoe/static/site-dialogs.js"], {cwd: root, encoding: "utf8", windowsHide: true}) : "";
let mode = "fixed";
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    if (url.pathname === "/client/jobs/101/edit") {
      response.writeHead(200, {"Content-Type": "text/html", "Cache-Control": "no-store"});
      response.end(html); return;
    }
    const file = path.resolve(root, "workdoe/static", "." + url.pathname);
    assert.ok(file.startsWith(path.join(root, "workdoe/static") + path.sep));
    const bytes = url.pathname === "/site-dialogs.js" && mode === "baseline" ? baseline : await fs.readFile(file);
    response.writeHead(200, {"Content-Type": url.pathname.endsWith(".js") ? "text/javascript" : "text/css", "Cache-Control": "no-store"});
    response.end(bytes);
  } catch { response.writeHead(404); response.end(); }
});

(async () => {
  let browser;
  const results = [];
  try {
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const base = "http://127.0.0.1:" + server.address().port;
    browser = await chromium.launch({headless: true, chromiumSandbox: true, executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE});
    for (mode of baselineRef ? ["baseline", "fixed"] : ["fixed"]) {
      const context = await browser.newContext({viewport: {width: 1280, height: 720}, serviceWorkers: "block"});
      const errors = [];
      let releaseSdk;
      const gate = new Promise(resolve => { releaseSdk = resolve; });
      let sdkRequests = 0, deniedFrames = 0, posts = 0;
      try {
        await context.route("**/*", async route => {
          const request = route.request(), url = new URL(request.url());
          if (request.method() !== "GET") { posts++; return route.abort(); }
          if (url.origin === base) return route.continue();
          if (url.origin === "https://challenges.cloudflare.com" && url.pathname === "/turnstile/v0/api.js") {
            sdkRequests++; await gate; return route.continue();
          }
          if (request.resourceType() === "document") deniedFrames++;
          return route.abort("blockedbyclient");
        });
        const page = await context.newPage();
        page.on("pageerror", error => errors.push(String(error).includes("Remove async/defer")));
        await page.goto(base + "/client/jobs/101/edit", {waitUntil: "domcontentloaded"});
        await page.getByRole("button", {name: "Retry verification"}).waitFor();
        releaseSdk();
        await page.waitForFunction(() => window.turnstile && typeof window.turnstile.render === "function");
        if (mode === "baseline") {
          await page.waitForTimeout(100);
          await page.getByRole("button", {name: "Retry verification"}).click();
          await page.locator("[data-turnstile-status]").filter({hasText: "Verification could not restart"}).waitFor();
          assert.ok(errors.includes(true), "Expected actual SDK async/defer rejection");
          assert.equal(await page.locator("[data-turnstile-widget-id]").count(), 0);
        } else {
          await page.locator("[data-turnstile-widget-id]").waitFor({state: "attached"});
          await page.getByRole("button", {name: "Retry verification"}).click();
          assert.equal(await page.locator("[data-turnstile-status]").textContent(), "Loading verification...");
          assert.deepEqual(errors, []);
          assert.equal(await page.locator("[data-turnstile-widget-id]").count(), 1);
        }
        assert.equal(sdkRequests, 1); assert.equal(posts, 0);
        const readiness = await page.evaluate(() => {
          try { window.turnstile.ready(() => {}); return {rejected: false}; }
          catch (error) { return {rejected: true, code: error.code, asyncDeferMessage: String(error.message).includes("Remove async/defer")}; }
        });
        assert.equal(readiness.rejected, true); assert.equal(readiness.asyncDeferMessage, true);
        results.push({mode, readiness, nativeRenderReturned: mode === "fixed", sdkRequests, deniedFrames, posts, noChallengeSolved: true});
      } finally { releaseSdk(); await context.close(); }
    }
    console.log(JSON.stringify({results, challengeFramesBlocked: true, siteverifyNeverCalled: true}, null, 2));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
