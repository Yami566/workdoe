"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const {chromium, webkit} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);

const base = new URL(process.env.WORKDOE_OUTAGE_PREVIEW_URL);
assert.equal(base.protocol, "http:");
assert.equal(base.hostname, "127.0.0.1");
assert.equal(base.href, base.origin + "/");
const useWebKit = process.argv.includes("--webkit");
const output = path.resolve(__dirname, "../../.test-tmp/entry-resilience", useWebKit ? "webkit" : "chromium");
const cases = [
  {name: "board", route: "/?q=synthetic-outage-search", title: "Projects temporarily unavailable",
    alternate: "Sign in", destination: "/login"},
  {name: "signup", route: "/create-account?__clerk_ticket=synthetic-outage-invitation",
    title: "Sign-in temporarily unavailable", alternate: "Browse projects", destination: "/"},
  {name: "draft", route: "/post-project?fixture=synthetic-outage-draft", retry: "/post-project",
    title: "Draft temporarily unavailable", alternate: "Browse projects", destination: "/"},
];

async function verify(browser, viewport, scale, javaScriptEnabled, spec) {
  const mobile = viewport.width < 720;
  const context = await browser.newContext({viewport, isMobile: mobile, hasTouch: mobile,
    javaScriptEnabled, reducedMotion: "reduce", serviceWorkers: "block"});
  try {
    if (spec.name === "draft") {
      await context.addCookies([{name: "workdoe_job_draft", value: "synthetic-draft-cookie",
        url: base.origin, httpOnly: true, sameSite: "Lax"}]);
    }
    const prohibited = [];
    await context.route("**/*", async route => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== base.origin || ["script", "fetch", "xhr"].includes(request.resourceType())) {
        prohibited.push(url.pathname);
        return route.abort();
      }
      if (scale !== 100 && url.pathname === "/styles.css") {
        const style = await route.fetch({maxRedirects: 0});
        assert.equal(style.status(), 200);
        return route.fulfill({response: style,
          body: (await style.text()) + `\n:root { font-size: ${scale}% !important; }\n`});
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    const url = new URL(spec.route, base).href;
    const response = await page.goto(url, {waitUntil: "load"});
    assert.equal(response.status(), 503);
    assert.equal(await page.title(), spec.title + " - Workdoe");
    assert.equal((await response.text()).includes("synthetic-outage-"), false);
    if (spec.name === "draft") {
      assert.equal(await response.headerValue("retry-after"), "5");
      assert.equal(await response.headerValue("referrer-policy"), "no-referrer");
    }
    assert.equal(await page.getByRole("main", {name: spec.title}).count(), 1);
    assert.equal(await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize)), 16 * scale / 100);
    assert.equal(await page.locator(".site-header").evaluate(header => getComputedStyle(header).position), "static");
    const capture = path.join(output, `${spec.name}-${viewport.width}-${scale}.png`);
    await page.screenshot({fullPage: true, path: capture});
    const measured = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth}));
    assert.ok(measured.width <= viewport.width + 1 && measured.scroll <= viewport.width + 1, JSON.stringify(measured));
    for (const locator of [
      page.getByRole("heading", {name: spec.title, exact: true}),
      page.getByRole("link", {name: "Try again", exact: true}),
      page.getByRole("link", {name: spec.alternate, exact: true}),
    ]) {
      const rect = await locator.boundingBox();
      assert.ok(rect && rect.x >= 0 && rect.x + rect.width <= viewport.width + 1,
        JSON.stringify({text: await locator.textContent(), rect, measured}));
    }
    const retry = page.getByRole("link", {name: "Try again", exact: true});
    await retry.focus();
    assert.ok(await retry.evaluate(link => document.activeElement === link && getComputedStyle(link).outlineStyle !== "none"));
    await page.screenshot({fullPage: true, path: capture});
    const retryUrl = spec.retry ? new URL(spec.retry, base).href : url;
    const [retried] = await Promise.all([
      page.waitForResponse(item => item.url() === retryUrl && item.request().isNavigationRequest()),
      retry.press("Enter"),
    ]);
    assert.equal(retried.status(), 503);
    assert.ok(!((await retried.request().allHeaders()).referer || "").includes("synthetic-outage-"));
    const alternate = new URL(spec.destination, base).href;
    await Promise.all([
      page.waitForURL(alternate, {waitUntil: "load"}),
      page.getByRole("link", {name: spec.alternate, exact: true}).press("Enter"),
    ]);
    assert.deepEqual(prohibited, []);
    const safety = page.getByRole("navigation", {name: "Policies"}).getByRole("link", {name: "Safety"});
    const [policy] = await Promise.all([
      page.waitForResponse(item => item.url() === new URL("/safety", base).href && item.request().isNavigationRequest()),
      safety.press("Enter"),
    ]);
    assert.equal(policy.status(), 200);
    await page.waitForURL(new URL("/safety", base).href, {waitUntil: "load"});
    process.stdout.write(`PASS: ${spec.name} ${viewport.width}x${viewport.height}, ${scale}% text, JS ${javaScriptEnabled}\n`);
  } finally {
    await context.close();
  }
}

async function main() {
  await fs.mkdir(output, {recursive: true});
  const browser = await (useWebKit ? webkit : chromium).launch(useWebKit ? {} : {
    executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE,
  });
  try {
    for (const [width, height, scale, js] of [
      [320, 420, 200, false], [390, 844, 100, true], [820, 1180, 200, true], [1280, 720, 100, true],
    ]) {
      for (const spec of cases) await verify(browser, {width, height}, scale, js, spec);
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
