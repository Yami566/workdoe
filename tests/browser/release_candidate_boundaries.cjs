"use strict";

const assert = require("node:assert/strict");
const {once} = require("node:events");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const {chromium} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);

const fixture = JSON.parse(fs.readFileSync(0, "utf8"));
const base = new URL(fixture.base);
assert.equal(base.protocol, "http:");
assert.equal(base.hostname, "127.0.0.1");
assert.equal(base.href, base.origin + "/");
const output = path.resolve(__dirname, "../../.test-tmp/qualified-boundaries");

async function checkPrivatePhotoOrigin(browser) {
  assert.match(fixture.hiddenLeadPhotoPath, /^\/media\/jobs\/[1-9]\d*$/);
  const photoUrl = new URL(fixture.hiddenLeadPhotoPath, base);
  photoUrl.search = "?native-photo-origin=1";
  const server = http.createServer((_request, response) => {
    response.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
    response.end(`<!doctype html><title>Private photo fixture</title>
      <img alt="Private photo fixture" src="${photoUrl}"><a href="${photoUrl}">Open photo</a>`);
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  let context;
  try {
    context = await browser.newContext({serviceWorkers: "block"});
    await context.addCookies([{
      name: "__session", value: fixture.consumerToken, url: base.origin, httpOnly: true, sameSite: "Lax",
    }]);
    const page = await context.newPage();
    page.setDefaultTimeout(9000);
    await Promise.all([
      page.waitForRequest(request => request.url() === photoUrl.href && request.resourceType() === "image"),
      page.goto(`http://127.0.0.1:${server.address().port}/`, {waitUntil: "load"}),
    ]);
    assert.equal(await page.locator("img").evaluate(img => img.complete && img.naturalWidth > 0), false,
      "A different origin rendered the private photo");
    const denied = await page.request.head(photoUrl.href, {headers: {
      "Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Dest": "image",
    }});
    assert.equal(denied.status(), 403);
    assert.equal((await denied.body()).length, 0);
    assert.equal(denied.headers()["cross-origin-resource-policy"], "same-origin");
    assert.equal(denied.headers()["x-frame-options"], "DENY");

    const [direct] = await Promise.all([
      page.waitForResponse(result => result.url() === photoUrl.href && result.request().isNavigationRequest()),
      page.getByRole("link", {name: "Open photo"}).click(),
    ]);
    assert.equal(direct.status(), 200, "Direct authenticated viewing should still work");
    await page.goto(new URL("/health", base).href);
    const [same, loaded] = await Promise.all([
      page.waitForResponse(result => result.url() === photoUrl.href && result.request().resourceType() === "image"),
      page.evaluate(src => new Promise(resolve => {
        const img = document.createElement("img");
        img.onload = () => resolve(img.naturalWidth > 0);
        img.onerror = () => resolve(false);
        img.src = src;
        document.body.append(img);
      }), photoUrl.href),
    ]);
    assert.equal(same.status(), 200);
    assert.equal(await same.headerValue("cross-origin-resource-policy"), "same-origin");
    assert.equal(loaded, true);
  } finally {
    try {
      await context?.close();
    } finally {
      await new Promise(resolve => server.close(resolve));
    }
  }
}

async function checkMissingPage(browser, width, height, scale, javaScriptEnabled) {
  const context = await browser.newContext({viewport: {width, height}, javaScriptEnabled, serviceWorkers: "block"});
  try {
    const external = [];
    await context.route("**/*", async route => {
      const url = new URL(route.request().url());
      if (url.origin !== base.origin) {
        external.push(url.origin);
        return route.abort("blockedbyclient");
      }
      if (scale !== 100 && url.pathname === "/styles.css") {
        const stylesheet = await route.fetch({maxRedirects: 0});
        assert.equal(stylesheet.status(), 200);
        return route.fulfill({response: stylesheet,
          body: `${await stylesheet.text()}\n:root {font-size: ${scale}% !important}\n`});
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(9000);
    const scripts = [];
    page.on("request", request => {
      if (request.resourceType() === "script") scripts.push(request.url());
    });
    const response = await page.goto(new URL("/workdoe-missing-page?fixture=synthetic-stale-link", base).href);
    assert.equal(response.status(), 404);
    assert.equal(await response.headerValue("referrer-policy"), "no-referrer");
    assert.equal(await response.headerValue("cache-control"), "no-store");
    assert.equal(await page.title(), "Page not found - Workdoe");
    assert.equal(await page.getByRole("main", {name: "Page not found"}).count(), 1);
    assert.equal(await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize)), 16 * scale / 100);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    const action = page.getByRole("link", {name: "Browse projects"});
    assert.equal(await action.getAttribute("href"), "/");
    await action.focus();
    assert.equal(await action.evaluate(link => document.activeElement === link && getComputedStyle(link).outlineStyle !== "none"), true);
    await page.screenshot({path: path.join(output, `404-${width}x${height}-${scale}.png`)});
    assert.deepEqual(scripts, []);
    assert.deepEqual(external, []);
    const [home] = await Promise.all([
      page.waitForResponse(result => result.url() === base.href && result.request().isNavigationRequest()),
      action.press("Enter"),
    ]);
    assert.equal(home.status(), 200);
    assert.equal(await home.request().headerValue("referer"), null);
    await page.waitForURL(base.href, {waitUntil: "load"});
    console.log(`PASS: 404 ${width}x${height}, ${scale}% text, JS ${javaScriptEnabled}, keyboard recovery`);
  } finally {
    await context.close();
  }
}

async function checkSearchPrivacy(browser, javaScriptEnabled) {
  const context = await browser.newContext({
    serviceWorkers: "block", viewport: {width: 390, height: 844}, javaScriptEnabled,
  });
  try {
    await context.route("**/*", route => (
      new URL(route.request().url()).origin === base.origin ? route.continue() : route.abort()
    ));
    const page = await context.newPage();
    page.setDefaultTimeout(9000);
    const queries = [];
    page.on("request", request => {
      const query = new URL(request.url()).searchParams.get("q");
      if (query) queries.push(query);
    });
    await page.goto(base.href, {waitUntil: "domcontentloaded"});
    if (javaScriptEnabled) {
      await page.locator("#lead-map.leaflet-container").waitFor();
      await page.getByRole("tab", {name: "Projects"}).click();
    }
    const input = page.locator("#market-search");
    const value = javaScriptEnabled ? "202\u200b555\u200b0101" : "jos\u00e9@fixture.invalid";
    await input.fill(value);
    assert.equal(await input.evaluate(element => element.validity.valid), false);
    await input.press("Enter");
    assert.equal(new URL(page.url()).searchParams.has("q"), false);
    assert.deepEqual(queries, []);
    await input.fill("Arlington");
    assert.equal(await input.evaluate(element => element.validity.valid), true);
    assert.equal(new URL(page.url()).searchParams.has("q"), false);
    assert.deepEqual(queries, []);
    const submitted = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === (javaScriptEnabled ? "/api/jobs/open" : "/") && url.searchParams.get("q") === "Arlington";
    });
    await input.press("Enter");
    assert.equal((await submitted).status(), 200);
    await page.waitForURL(url => url.searchParams.get("q") === "Arlington");
    assert.deepEqual(queries, ["Arlington"]);
    if (javaScriptEnabled) {
      const cleaning = page.getByRole("link", {name: "Cleaning", exact: true});
      await cleaning.click();
      await page.waitForURL(url => url.searchParams.get("family") === "cleaning-upkeep"
        && url.searchParams.get("q") === "Arlington");
      assert.equal(await input.inputValue(), "Arlington");
    }
    console.log("PASS: project search contact guard with JS " + javaScriptEnabled);
  } finally {
    await context.close();
  }
}

async function checkEntryLeadReturn(browser) {
  const context = await browser.newContext({serviceWorkers: "block", viewport: {width: 390, height: 844}});
  try {
    await context.addInitScript(() => { window.fetch = undefined; });
    await context.route("**/*", route => (
      new URL(route.request().url()).origin === base.origin ? route.continue() : route.abort()
    ));
    const page = await context.newPage();
    page.setDefaultTimeout(9000);
    const login = new URL("/login", base);
    login.searchParams.set("next", "/leads?family=outdoor-yard&service=pressure-washing&sort=soonest&view=sent");
    await page.goto(login.href);
    const projects = page.getByRole("tab", {name: "Projects", exact: true});
    await projects.click();
    const input = page.getByRole("searchbox", {name: "Search projects"});
    await input.fill("22201");
    await input.press("Enter");
    await page.waitForURL(url => url.pathname === "/login" && url.searchParams.get("q") === "22201");
    const mount = page.locator("[data-clerk-entry]");
    const redirect = async () => new URL(await mount.getAttribute("data-redirect-url"), base);
    const filtered = await redirect();
    assert.equal(filtered.pathname, "/leads");
    assert.deepEqual(Object.fromEntries(filtered.searchParams), {
      family: "outdoor-yard", service: "pressure-washing", q: "22201", sort: "soonest", view: "sent",
    });
    await projects.click();
    await page.getByRole("link", {name: "All work", exact: true}).click();
    await page.waitForURL(url => !url.searchParams.has("family") && url.searchParams.get("q") === "22201");
    const cleared = await redirect();
    assert.equal(cleared.pathname, "/leads");
    assert.deepEqual(Object.fromEntries(cleared.searchParams), {q: "22201", sort: "soonest", view: "sent"});
    console.log("PASS: account-entry GET search and All work preserve the contractor return route without sign-in");
  } finally {
    await context.close();
  }
}

async function checkMessageHistory(browser, width, height) {
  assert.match(fixture.threadPath, /^\/messages\/[1-9]\d*$/);
  const context = await browser.newContext({
    viewport: {width, height}, javaScriptEnabled: false, serviceWorkers: "block",
  });
  try {
    await context.addCookies([{
      name: "__session", value: fixture.consumerToken, url: base.origin, httpOnly: true, sameSite: "Lax",
    }]);
    await context.route("**/*", route => (
      new URL(route.request().url()).origin === base.origin ? route.continue() : route.abort()
    ));
    const page = await context.newPage();
    page.setDefaultTimeout(9000);
    const latestUrl = new URL(fixture.threadPath, base);
    await page.goto(latestUrl.href);
    const history = page.getByRole("navigation", {name: "Message history"});
    const older = history.getByRole("link", {name: "Older messages"});
    const list = page.getByRole("region", {name: "50 messages"});
    assert.equal(await list.locator("article").count(), 50);
    assert.equal(await list.getAttribute("tabindex"), "0");
    const reply = page.getByRole("form", {name: "New message"});
    assert.equal(await reply.count(), 1);
    if (width === 390 && height === 844) {
      const editor = await reply.getByRole("textbox", {name: "New message"}).boundingBox();
      assert.ok(editor && editor.y < height - 68, "Long titles must leave the start of the editor in view");
    }
    const linkBox = await older.boundingBox();
    assert.ok(linkBox && linkBox.x >= 0 && linkBox.x + linkBox.width <= width + 1);
    const currentOldest = await list.locator("article").first().getAttribute("id");
    await page.screenshot({path: path.join(output, `history-latest-${width}x${height}.png`)});
    const send = reply.getByRole("button", {name: "Send message"});
    await send.focus();
    assert.ok(await send.evaluate(button => {
      const box = button.getBoundingClientRect();
      const target = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
      return target && button.contains(target);
    }), "The Send button must not be clipped or covered after keyboard focus");
    await page.screenshot({path: path.join(output, `history-send-${width}x${height}.png`)});
    await older.focus();
    await page.keyboard.press("Enter");
    await page.waitForURL(url => url.searchParams.has("through"));
    assert.equal(await page.locator(`#${currentOldest}`).count(), 0);
    assert.equal(await page.getByRole("form", {name: "New message"}).count(), 0);
    assert.equal(await page.getByRole("region", {name: "50 messages"}).locator("article").count(), 50);
    const latest = history.getByRole("link", {name: "Latest messages"});
    const latestBox = await latest.boundingBox();
    assert.ok(latestBox && latestBox.x >= 0 && latestBox.x + latestBox.width <= width + 1);
    await page.screenshot({path: path.join(output, `history-older-${width}x${height}.png`)});
    await latest.focus();
    await page.keyboard.press("Enter");
    await page.waitForURL(latestUrl.href);
    assert.equal(await page.locator(`#${currentOldest}`).count(), 1);
    console.log(`PASS: keyboard and no-JavaScript message history at ${width}x${height}`);
  } finally {
    await context.close();
  }
}

async function run() {
  fs.mkdirSync(output, {recursive: true});
  const browser = await chromium.launch({
    executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE, headless: true, chromiumSandbox: true,
  });
  try {
    if (fixture.threadPath) {
      for (const [width, height] of [[390, 844], [844, 390], [820, 1180], [1280, 720]]) {
        await checkMessageHistory(browser, width, height);
      }
      return;
    }
    await checkPrivatePhotoOrigin(browser);
    await checkSearchPrivacy(browser, true);
    await checkSearchPrivacy(browser, false);
    await checkEntryLeadReturn(browser);
    for (const args of [
      [320, 420, 200, false], [390, 844, 100, true], [820, 1180, 200, true], [1280, 720, 100, true],
    ]) await checkMissingPage(browser, ...args);
  } finally {
    await browser.close();
  }
}

run().catch(error => {console.error(error); process.exitCode = 1;});
