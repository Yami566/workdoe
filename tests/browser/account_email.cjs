"use strict";

// Current renderers and styles only; no live Clerk session or provider access.
const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");

if (!process.env.WORKDOE_PLAYWRIGHT_MODULE || !process.env.WORKDOE_CHROMIUM_EXECUTABLE) {
  throw new Error("Set existing Playwright and Chromium paths; no installation is performed.");
}
const {chromium} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const baseline = process.env.WORKDOE_ACCOUNT_BASELINE_REF;
const output = path.join(root, ".test-tmp/account-email-" + (baseline ? "baseline" : "browser"));
const fixture = JSON.parse(execFileSync("python", [path.join(__dirname, "account_email_fixture.py")], {
  cwd: root, encoding: "utf8", windowsHide: true, maxBuffer: 1024 * 1024
}));
const oldStyles = baseline ? execFileSync("git", ["show", baseline + ":workdoe/static/styles.css"], {
  cwd: root, encoding: "utf8", windowsHide: true, maxBuffer: 1024 * 1024
}) : null;
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    if (url.pathname === "/privacy") {
      response.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      response.end(fixture.privacy); return;
    }
    if (fixture.pages[url.pathname]) {
      response.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      response.end(fixture.pages[url.pathname]); return;
    }
    const relative = url.pathname.replace(/^\/static\//, "/");
    if (relative === "/styles.css" && oldStyles) {
      response.writeHead(200, {"Content-Type": "text/css"}); response.end(oldStyles); return;
    }
    const file = path.resolve(staticRoot, "." + relative);
    if (!file.startsWith(staticRoot + path.sep)) throw new Error("Outside fixture");
    const bytes = await fs.readFile(file);
    response.writeHead(200, {"Content-Type": {".css": "text/css", ".svg": "image/svg+xml", ".js": "text/javascript"}[path.extname(file)] || "application/octet-stream"});
    response.end(bytes);
  } catch { response.writeHead(404); response.end(); }
});

(async () => {
  let browser;
  const cases = [], external = [];
  try {
    await fs.mkdir(output, {recursive: true});
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const base = "http://127.0.0.1:" + server.address().port;
    browser = await chromium.launch({headless: true, chromiumSandbox: true,
      executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE});
    for (const viewport of [{width: 1280, height: 720}, {width: 390, height: 844}, {width: 820, height: 1180}, {width: 320, height: 740}]) {
      for (const [location] of Object.entries(fixture.pages)) {
        for (const scale of [100, 200]) {
          const context = await browser.newContext({viewport, javaScriptEnabled: false,
            reducedMotion: "reduce", serviceWorkers: "block"});
          let page;
          try {
            await context.route("**/*", route => {
              if (new URL(route.request().url()).origin === base) return route.continue();
              external.push(route.request().url()); return route.abort("blockedbyclient");
            });
            page = await context.newPage();
            await page.goto(base + location, {waitUntil: "load"});
            await page.evaluate(value => { document.documentElement.style.fontSize = value + "%"; }, scale);
            const email = page.locator(".account-email");
            const requests = page.getByRole("link", {name: "Account data requests", exact: true});
            assert.equal(await requests.getAttribute("href"), "/privacy#privacy-choices", location);
            assert.equal(await requests.isVisible(), true, location);
            assert.ok((await requests.boundingBox()).width <= viewport.width, location);
            const role = location.includes("/client/") ? "Consumer" : "Contractor";
            assert.equal(await page.locator(".account-summary dd").last().textContent(), role, location);
            const state = await email.evaluate(node => {
              const style = getComputedStyle(node);
              return {whiteSpace: style.whiteSpace, overflow: style.overflowX,
                height: node.getBoundingClientRect().height, lineHeight: parseFloat(style.lineHeight),
                scrollable: node.scrollWidth > node.clientWidth + 1,
                rootOverflow: document.documentElement.scrollWidth > innerWidth + 1,
                text: node.textContent};
            });
            assert.equal(state.whiteSpace, "nowrap", location);
            assert.equal(state.overflow, "auto", location);
            assert.equal(state.rootOverflow, false, location);
            assert.ok(state.height <= state.lineHeight + 2, location + " must stay one line");
            await email.focus();
            assert.equal(await email.evaluate(node => document.activeElement === node), true);
            if (state.scrollable) {
              for (let count = 0; count < 12; count++) await page.keyboard.press("ArrowRight");
              let scrolled = false;
              for (let attempt = 0; attempt < 20; attempt++) {
                scrolled = await email.evaluate(node => node.scrollLeft > 0);
                if (scrolled) break;
                await new Promise(resolve => setTimeout(resolve, 50));
              }
              assert.equal(scrolled, true, location + " keyboard horizontal scrolling");
            }
            if (location === "/worker/client/normal" && scale === 100 && [390, 1280].includes(viewport.width)) {
              assert.equal(state.scrollable, false, "Normal email fits without scrolling");
              await page.screenshot({path: path.join(output, "consumer-" + viewport.width + ".png"), fullPage: true});
            }
            if (location.endsWith("/client/normal") && viewport.width === 390 && scale === 100) {
              await requests.focus();
              await page.keyboard.press("Enter");
              await page.waitForURL(base + "/privacy#privacy-choices");
              assert.equal(await page.evaluate(() => document.activeElement.id), "privacy-choices", location);
              assert.equal(await page.locator('a[href="mailto:admin@workdoe.com"]').first().isVisible(), true, location);
            }
            cases.push({viewport, location, scale, oneLine: true, noRootOverflow: true,
              keyboardReachable: true, longEmailScroll: state.scrollable, accountDataLinkVisible: true});
          } catch (error) {
            if (page) await page.screenshot({path: path.join(output, "failure.png"), fullPage: true});
            throw error;
          } finally { await context.close(); }
        }
      }
    }
    assert.deepEqual(external, []);
    await fs.writeFile(path.join(output, "result.local.json"), JSON.stringify({passed: cases.length, cases, external, providerUiNotTested: true}, null, 2));
    console.log(JSON.stringify({passed: cases.length, output, providerUiNotTested: true}));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
