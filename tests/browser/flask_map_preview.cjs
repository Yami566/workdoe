"use strict";

// Exercise the real Flask adapters on two disposable, loopback previews.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const {chromium} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const output = path.resolve(__dirname, "../../.test-tmp/flask-map-parity");
const asset = "/static/dmv-area-50fe6cd3.geojson";

function origin(value) {
  const url = new URL(value);
  assert.equal(url.hostname, "127.0.0.1");
  assert.equal(url.protocol, "http:");
  assert.equal(url.href, url.origin + "/");
  return url.origin;
}

async function check(browser, base, mode, viewport) {
  const context = await browser.newContext({
    viewport, javaScriptEnabled: mode === "area", serviceWorkers: "block", reducedMotion: "reduce",
  });
  const external = [];
  const assetRequests = [];
  const mapRequests = [];
  try {
    await context.addCookies([{name: "fixture", value: "non-sensitive", url: base}]);
    await context.route("**/*", async route => {
      const url = new URL(route.request().url());
      if (url.origin !== base) {
        external.push(url.origin);
        return route.abort();
      }
      if (url.pathname === asset) assetRequests.push(await route.request().allHeaders());
      if (url.pathname.includes("/leaflet/") || url.pathname === "/static/map.js") mapRequests.push(url.pathname);
      return route.continue();
    });
    const page = await context.newPage();
    const home = await page.goto(base + "/");
    assert.equal(home.status(), 200);
    assert.ok(!home.headers()["content-security-policy"].includes("tile.openstreetmap.org"));
    if (mode === "area") {
      await page.locator("#lead-map .leaflet-overlay-pane svg path").first().waitFor();
      assert.equal(await page.locator("#lead-map .leaflet-overlay-pane svg path").count(), 50);
      await page.locator("#lead-map .leaflet-marker-icon").first().waitFor();
      await page.getByText("Source: U.S. Census Bureau", {exact: false}).waitFor();
      const dock = page.getByRole("group", {name: "Map controls"});
      await dock.waitFor();
      const controls = await dock.boundingBox();
      const canvas = await page.locator("#lead-map").boundingBox();
      assert.ok(controls.y + controls.height <= canvas.y + 1, "Flask map controls must not cover its pins.");
      await page.waitForFunction(() => {
        const map = document.querySelector("#lead-map").getBoundingClientRect();
        return [...document.querySelectorAll("#lead-map .leaflet-marker-icon")].some(pin => {
          const rect = pin.getBoundingClientRect();
          return rect.left >= map.left && rect.right <= map.right && rect.top >= map.top && rect.bottom <= map.bottom;
        });
      });
      assert.equal(assetRequests.length, 1);
      assert.equal(assetRequests[0].cookie, undefined);
      assert.equal(assetRequests[0].referer, undefined);
      await page.screenshot({path: path.join(output, `area-${viewport.width}.png`)});
      const zoom = page.locator(".leaflet-control-zoom-in");
      const boundary = page.locator("#lead-map .leaflet-overlay-pane svg path").first();
      const before = await boundary.getAttribute("d");
      await zoom.focus();
      assert.equal(await zoom.evaluate(node => node === document.activeElement), true);
      await zoom.press("Enter");
      await page.waitForFunction(previous => {
        const current = document.querySelector("#lead-map .leaflet-overlay-pane svg path");
        return current && current.getAttribute("d") !== previous;
      }, before);
      await page.goto(base + "/login?embed=1");
      assert.equal(await page.locator("#lead-map, script[src*='/leaflet/']").count(), 0);
      assert.equal(assetRequests.length, 1);
    } else {
      assert.equal(await page.locator("#lead-map, [data-mobile-panel-target='map']").count(), 0);
      const filter = page.getByRole("search", {name: "Filter open jobs"});
      await filter.getByRole("searchbox").fill("Washington");
      await filter.getByRole("button", {name: "Filter", exact: true}).click();
      await page.waitForURL(url => url.searchParams.get("q") === "Washington");
      const rows = page.locator("#home-open-job-results");
      await rows.getByText("Power wash townhouse front steps", {exact: true}).waitFor();
      assert.equal(await rows.getByText("Replace damaged fence panel", {exact: true}).count(), 0);
      await rows.scrollIntoViewIfNeeded();
      await page.screenshot({path: path.join(output, `list-${viewport.width}.png`)});
      assert.deepEqual(mapRequests, []);
      assert.deepEqual(assetRequests, []);
    }
    assert.deepEqual(external, []);
    console.log(`PASS: Flask ${mode} at ${viewport.width}x${viewport.height}`);
  } finally {
    await context.close();
  }
}

(async () => {
  const areaBase = origin(process.argv[2]);
  const listBase = origin(process.argv[3]);
  assert.notEqual(areaBase, listBase);
  await fs.mkdir(output, {recursive: true});
  const browser = await chromium.launch({
    chromiumSandbox: true, executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE,
  });
  try {
    for (const viewport of [{width: 390, height: 844}, {width: 820, height: 1180}]) {
      await check(browser, areaBase, "area", viewport);
      await check(browser, listBase, "list", viewport);
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
