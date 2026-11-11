"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const {mkdir, readFile} = require("node:fs/promises");
const http = require("node:http");
const {once} = require("node:events");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const {WORKDOE_PLAYWRIGHT_MODULE, WORKDOE_CHROMIUM_EXECUTABLE, WORKDOE_TILE_FREE_SCREENSHOTS} = process.env;
assert.ok(WORKDOE_PLAYWRIGHT_MODULE && WORKDOE_CHROMIUM_EXECUTABLE);
const {chromium} = require(WORKDOE_PLAYWRIGHT_MODULE);
const pages = JSON.parse(execFileSync(process.env.WORKDOE_PYTHON || "python",
  ["tests/test_tile_free_mode.py"], {cwd: root, encoding: "utf8", windowsHide: true,
    env: {...process.env, PYTHONPATH: root}}));
const types = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml",
  ".webp": "image/webp", ".png": "image/png"};

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  const key = url.pathname === "/" && url.searchParams.has("job_id")
    ? "/?job_id=" + url.searchParams.get("job_id")
    : url.pathname === "/" && url.searchParams.has("q") ? "/?q=" + url.searchParams.get("q") : url.pathname;
  if (Object.hasOwn(pages, key)) {
    const doc = pages[key];
    response.writeHead(200, {"Content-Type": "text/html; charset=utf-8", "Content-Security-Policy": doc.csp}).end(doc.html);
    return;
  }
  const asset = path.resolve(staticRoot, "." + url.pathname);
  const type = types[path.extname(asset)];
  if (!type || !asset.startsWith(staticRoot + path.sep)) {
    response.writeHead(404).end();
    return;
  }
  try {
    const data = await readFile(asset);
    response.writeHead(200, {"Content-Type": type}).end(data);
  } catch {
    response.writeHead(404).end();
  }
});

async function check(browser, base, width, height, javaScriptEnabled) {
  const context = await browser.newContext({viewport: {width, height}, javaScriptEnabled, serviceWorkers: "block"});
  const unexpected = [];
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (url.origin !== base || /\/vendor\/leaflet|\/map\.js$|\/api\/jobs\/open/.test(url.pathname)) {
      unexpected.push(url.origin + url.pathname);
      return route.abort();
    }
    return route.continue();
  });
  try {
    const page = await context.newPage();
    async function open(route) {
      await page.goto(base + route, {waitUntil: "load"});
      assert.equal(await page.locator("[data-map], #market-map-panel, #market-map-tab").count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
    }
    await open("/");
    const services = page.locator(".market-service-chooser summary");
    const cleaning = page.locator('.market-service-chooser a[href*="family=cleaning-upkeep"]');
    assert.equal(await cleaning.isVisible(), false);
    await services.press("Enter");
    assert.equal(await cleaning.isVisible(), true);
    await services.press("Enter");
    const search = page.getByRole("searchbox", {name: "Search projects"});
    await search.fill("cleaning");
    await search.press("Enter");
    await page.waitForURL(url => url.searchParams.get("q") === "cleaning");
    assert.equal(await search.inputValue(), "cleaning");
    assert.ok(await page.locator("[data-project-results] a").count());
    const result = new URL(await page.locator("[data-project-results] a").first().getAttribute("href"), base);
    assert.equal(result.searchParams.get("q"), "cleaning");
    assert.equal(result.hash, "#market-details-panel");

    await open("/");
    const headingState = await page.evaluate(() => ({
      top: document.querySelector(".market-rail-heading h2").getBoundingClientRect().top,
      headerEnd: document.querySelector(".market-header").getBoundingClientRect().bottom,
      scroll: window.scrollY,
    }));
    assert.ok(headingState.top >= headingState.headerEnd && headingState.top >= 0,
      "List heading is obscured: " + JSON.stringify(headingState));
    const firstRow = await page.locator("[data-project-results] a").first().boundingBox();
    assert.ok(firstRow && firstRow.y < height, "Project list starts below the first viewport.");
    if (WORKDOE_TILE_FREE_SCREENSHOTS && javaScriptEnabled) {
      await mkdir(WORKDOE_TILE_FREE_SCREENSHOTS, {recursive: true});
      await page.screenshot({path: path.join(WORKDOE_TILE_FREE_SCREENSHOTS, "list-" + width + ".png")});
    }
    await page.locator("[data-project-results] a[data-job-id='demo-02']").press("Enter");
    await page.waitForURL(url => url.searchParams.get("job_id") === "demo-02");
    assert.equal(new URL(page.url()).hash, "#market-details-panel");
    const details = page.locator("#market-details-panel");
    assert.equal(await details.locator("[data-project-detail-content]").getAttribute("data-job-id"), "demo-02");
    const heading = await details.getByRole("heading", {level: 2}).boundingBox();
    assert.ok(heading && heading.y >= 0 && heading.y < height, "Selected project heading is offscreen.");

    await open("/login");
    const login = await page.locator("#entry-title").boundingBox();
    assert.ok(login && login.y >= 0 && login.y < height);
    await open("/leads");
    const filters = page.locator(".lead-tools summary");
    if (await filters.getAttribute("aria-expanded") === "false" ||
        !(await page.getByRole("searchbox").isVisible())) await filters.press("Enter");
    assert.equal(await page.getByRole("searchbox").isVisible(), true);
    const lead = page.locator("[data-project-results] a").first();
    assert.equal(await lead.getAttribute("href"), "/jobs/81");
    assert.deepEqual(unexpected, []);
  } finally {
    await context.close();
  }
}

async function run() {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = await chromium.launch({executablePath: WORKDOE_CHROMIUM_EXECUTABLE, chromiumSandbox: true});
  try {
    for (const [width, height] of [[320, 568], [390, 844], [820, 1180], [1280, 720]]) {
      for (const enabled of [true, false]) await check(browser, base, width, height, enabled);
    }
    console.log("Passed eight tile-free browser cases; no map or third-party requests.");
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => server.close());
