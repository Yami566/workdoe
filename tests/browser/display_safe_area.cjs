"use strict";

// The actual release renderers and assets, with loopback routes and synthetic map tiles.
const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");
const {chromium, webkit} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe", "static");
const baseline = process.argv.includes("--baseline");
const projectList = process.argv.includes("--project-list");
const mapAttribution = process.argv.includes("--map-attribution");
const dialogHistory = process.argv.includes("--dialog-history");
const mapFocus = process.argv.includes("--map-focus");
const searchCooldown = process.argv.includes("--search-cooldown");
const searchFeedback = process.argv.includes("--project-search-feedback");
const tileOutage = process.argv.includes("--tile-outage");
const leadNavigation = process.argv.includes("--lead-navigation");
const mapStartup = process.argv.includes("--map-startup");
const sharedProject = process.argv.includes("--shared-project");
const zipSearch = process.argv.includes("--zip-search");
const serverMapSnapshot = process.argv.includes("--server-map-snapshot");
const forcedColorSelection = process.argv.includes("--forced-colors-selection");
const mapAreaMovement = process.argv.includes("--map-area-movement");
const mapReflow = process.argv.includes("--map-reflow");
const areaMapTools = process.argv.includes("--area-map-tools");
const accessAreaMap = process.argv.includes("--access-area-map");
const directAreaAuth = process.argv.includes("--area-map") && !accessAreaMap;
const captureBefore = process.argv.includes("--capture-before");
const areaMap = leadNavigation || mapStartup || sharedProject || zipSearch || serverMapSnapshot
  || forcedColorSelection || mapAreaMovement || mapReflow || areaMapTools || accessAreaMap
  || searchFeedback || process.argv.includes("--area-map");
const areaAsset = "/dmv-area-50fe6cd3.geojson";
const useWebkit = (areaMap || mapAttribution || dialogHistory) && process.argv.includes("--webkit");
const engineSuffix = useWebkit ? "-webkit" : "";
const output = path.join(root, ".test-tmp", searchFeedback ? `project-search-feedback-${captureBefore ? "before" : "after"}${engineSuffix}`
  : mapAreaMovement ? `map-area-movement-${captureBefore ? "before" : "after"}${engineSuffix}`
  : mapReflow ? `map-reflow-${captureBefore ? "before" : "after"}${engineSuffix}`
  : areaMapTools ? `area-map-tools-${captureBefore ? "before" : "after"}${engineSuffix}`
  : forcedColorSelection ? `map-selection-${captureBefore ? "before" : "after"}`
  : serverMapSnapshot ? `server-map-snapshot${engineSuffix}`
  : zipSearch ? `zip-search${engineSuffix}`
  : sharedProject ? `shared-project${engineSuffix}`
  : mapStartup ? `map-startup-${captureBefore ? "before" : "after"}${engineSuffix}`
  : leadNavigation ? `lead-navigation-${captureBefore ? "before" : "after"}${engineSuffix}`
  : areaMap ? `${accessAreaMap ? "access-" : ""}area-map-${useWebkit ? "webkit" : "chromium"}`
  : tileOutage ? "tile-outage" : searchCooldown ? "search-cooldown" : mapFocus ? "map-refresh-focus" : dialogHistory
  ? `map-dialog-history-${useWebkit ? "webkit" : "chromium"}`
  : mapAttribution
  ? `map-attribution-${useWebkit ? "webkit" : "chromium"}-${baseline ? "before" : "after"}`
  : projectList ? "compact-project-list" :
  baseline ? "display-safe-area-before" : "display-safe-area-after");
const priorStyle = areaMapTools && captureBefore
  ? execFileSync("git", ["show", "942a9b3:workdoe/static/styles.css"], {cwd: root})
  : forcedColorSelection && captureBefore
  ? execFileSync("git", ["show", "0158447:workdoe/static/styles.css"], {cwd: root})
  : baseline ? execFileSync(
  "git", ["show", `${mapAttribution ? "a0da73c" : "1a2960a"}:workdoe/static/styles.css`], {cwd: root},
) : null;
const priorMap = areaMapTools && captureBefore
  ? execFileSync("git", ["show", "942a9b3:workdoe/static/map.js"], {cwd: root})
  : mapAreaMovement && captureBefore
  ? execFileSync("git", ["show", "817cef8cb034bcbf9fcb480f560e139b6950053d:workdoe/static/map.js"], {cwd: root})
  : mapReflow && captureBefore
    ? execFileSync("git", ["show", "21fe91a:workdoe/static/map.js"], {cwd: root})
  : searchFeedback && captureBefore
    ? execFileSync("git", ["show", "aa1f48b:workdoe/static/map.js"], {cwd: root}) : null;
const fixture = JSON.parse(execFileSync(
  "python", [path.join(__dirname, "display_safe_area_fixture.py"), ...(areaMap ? ["--area-map"] : []),
    ...(accessAreaMap ? ["--access-area-map"] : []),
    ...(directAreaAuth ? ["--direct-area-auth"] : []),
    ...(sharedProject ? ["--shared-project"] : []),
    ...(serverMapSnapshot || mapAreaMovement || mapReflow || areaMapTools ? ["--server-map-snapshot"] : [])],
  {cwd: root, encoding: "utf8", windowsHide: true, maxBuffer: 2 * 1024 * 1024},
));
const mime = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
  ".png": "image/png", ".webp": "image/webp", ".geojson": "application/geo+json"};
const tile = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+kxt0AAAAASUVORK5CYII=", "base64");
const boundaryDeliveries = [];
let boundaryFixture;
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, "http://127.0.0.1");
    if (request.method !== "GET") throw new Error("Fixture writes are not allowed.");
    const page = fixture.pages[url.pathname + url.search] || fixture.pages[url.pathname];
    if (page) {
      response.writeHead(200, page.headers);
      response.end(page.html);
    } else if (url.pathname === "/api/jobs/open") {
      response.writeHead(200, {"Content-Type": "application/json"});
      response.end(JSON.stringify(fixture.jobs));
    } else {
      const file = path.resolve(staticRoot, "." + url.pathname);
      if (!file.startsWith(staticRoot + path.sep)) throw new Error("Outside the static fixture.");
      const isBoundary = url.pathname === areaAsset;
      const scenario = isBoundary && boundaryFixture;
      if (scenario) {
        const {cookie, referer} = request.headers;
        const denied = accessAreaMap && !cookie?.split("; ").includes("CF_Authorization=synthetic");
        const status = denied ? 302 : scenario.name === "failed" ? 503 : 200;
        boundaryDeliveries.push({status, cookie, referer});
        if (status !== 200) {
          response.writeHead(status, denied ? {Location: "https://access.invalid/login", "Cache-Control": "no-store"} : {});
          response.end();
          return;
        }
        if (scenario.name === "slow" || scenario.name === "timeout") await scenario.held;
      }
      let bytes = priorStyle && url.pathname === "/styles.css" ? priorStyle
        : priorMap && url.pathname === "/map.js" ? priorMap : await fs.readFile(file);
      if (scenario?.name === "corrupt") bytes = Buffer.concat([bytes, Buffer.from(" ")]);
      response.writeHead(200, {"Content-Type": mime[path.extname(file)] || "application/octet-stream"});
      response.end(bytes);
    }
  } catch {
    response.writeHead(404);
    response.end();
  }
});

async function checkMapAreaMovement(browser, base) {
  const results = [];
  for (const [name, viewport, resized, pathname] of [
    ["desktop-home", {width: 1280, height: 720}, {width: 1160, height: 760}, "/"],
    ["phone-saved-area", {width: 390, height: 844}, {width: 844, height: 390}, fixture.bounded_url],
    ["phone-projects-first", {width: 390, height: 844}, {width: 844, height: 390}, fixture.bounded_family_url],
  ]) {
    const context = await browser.newContext({viewport, serviceWorkers: "block", reducedMotion: "reduce"});
    try {
      const requests = [];
      await context.route("**/*", route => {
        const target = new URL(route.request().url());
        assert.equal(target.origin, base);
        if (target.pathname !== "/api/jobs/open") return route.continue();
        requests.push(target);
        return route.fulfill({json: fixture.jobs});
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.clock.install();
      await page.goto(base + pathname);
      const map = page.locator("#lead-map");
      const action = page.locator("[data-search-map-area]");
      const mapTab = page.getByRole("tab", {name: "Map", exact: true});
      const projects = page.getByRole("tab", {name: "Projects", exact: true});
      if (name === "phone-projects-first") {
        assert.equal(await projects.getAttribute("aria-selected"), "true");
        assert.equal(await map.isVisible(), false);
        await mapTab.click();
      }
      await page.locator('#lead-map[aria-busy="false"] .leaflet-overlay-pane path').first().waitFor({state: "attached"});
      await page.clock.runFor(500);
      const afterLoad = await action.isVisible();
      const drawsInFrame = () => map.evaluate(node => {
        const frame = node.getBoundingClientRect();
        const overlaps = item => {
          const box = item.getBoundingClientRect();
          return box.width > 0 && box.height > 0 &&
            box.left < frame.right && box.right > frame.left &&
            box.top < frame.bottom && box.bottom > frame.top;
        };
        return [".leaflet-overlay-pane svg", ".leaflet-overlay-pane path", ".leaflet-marker-icon"]
          .every(selector => [...node.querySelectorAll(selector)].some(overlaps));
      });
      const initialGeometry = await drawsInFrame();
      await page.screenshot({path: path.join(output, `01-${name}.png`), animations: "disabled"});
      if (await projects.isVisible()) {
        await projects.click();
        await mapTab.click();
        await page.clock.runFor(500);
      }
      await page.setViewportSize(resized);
      await page.clock.runFor(500);
      const afterLayout = await action.isVisible();
      const result = {name, afterLoad, afterLayout, initialGeometry, startupRequests: requests.length};
      results.push(result);
      assert.equal(requests.length, 0);
      if (captureBefore) continue;
      assert.equal(afterLoad, false, `${name}: startup fit or resize offered an area search`);
      assert.equal(afterLayout, false, `${name}: layout alone offered an area search`);
      assert.ok(initialGeometry, `${name}: startup did not draw boundaries and pins in frame`);
      assert.ok(await drawsInFrame(), `${name}: layout change lost boundaries or pins`);
      if (name === "desktop-home") {
        const frame = await map.boundingBox();
        const x = frame.x + frame.width * 0.45;
        const y = frame.y + frame.height * 0.43;
        await page.mouse.move(x, y);
        await page.mouse.down();
        await page.mouse.move(x + 86, y + 22, {steps: 5});
        await page.mouse.up();
      } else {
        await map.getByRole("button", {name: "Zoom in", exact: true}).press("Enter");
      }
      await page.clock.runFor(500);
      assert.ok(await action.isVisible(), `${name}: a real pan or zoom did not offer an area search`);
      assert.equal(requests.length, 0, "Movement alone must not issue a query.");
      await action.press("Enter");
      await action.waitFor({state: "hidden"});
      assert.equal(requests.length, 1);
      for (const key of ["north", "south", "east", "west"]) assert.ok(requests[0].searchParams.has(key));
      assert.ok(await map.evaluate(node => node === document.activeElement));
      await page.getByRole("button", {name: "DMV view", exact: true}).click();
      await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
      await page.clock.runFor(500);
      assert.equal(requests.length, 2);
      assert.equal(requests[1].searchParams.has("north"), false);
      assert.equal(await action.isVisible(), false, "The explicit reset must not leave a pending area action.");
      if (name === "desktop-home") {
        const frame = await map.boundingBox();
        await page.mouse.move(frame.x + frame.width * 0.45, frame.y + frame.height * 0.43);
        await page.mouse.wheel(0, -220);
        await page.clock.runFor(500);
        assert.ok(await action.isVisible(), "Mouse-wheel zoom must also offer a search.");
        assert.equal(requests.length, 2, "Mouse-wheel zoom must not send a query.");
        for (let step = 0; step < 12; step++) {
          await map.press("ArrowRight");
          await page.clock.runFor(500);
        }
        assert.ok(await map.locator(".leaflet-overlay-pane path").count(), "Keyboard panning lost the DMV geography.");
        await action.press("Enter");
        await action.waitFor({state: "hidden"});
        const bounds = requests[2].searchParams;
        assert.ok(Number(bounds.get("west")) < -76.2 && Number(bounds.get("east")) > -78
          && Number(bounds.get("south")) < 39.5 && Number(bounds.get("north")) > 38,
          "Area search must still overlap the pilot after keyboard panning.");
        const zoomOut = map.getByRole("button", {name: "Zoom out", exact: true});
        for (let step = 0; step < 12 && await zoomOut.getAttribute("aria-disabled") !== "true"; step++) {
          await zoomOut.press("Enter");
          await page.clock.runFor(500);
        }
        await page.screenshot({path: path.join(output, "02-desktop-overview.png"), animations: "disabled"});
        assert.ok(await drawsInFrame(), "Zooming out lost the DMV geography or pins.");
        await action.press("Enter");
        await action.waitFor({state: "hidden"});
        const overview = requests[3].searchParams;
        assert.ok(Number(overview.get("east")) - Number(overview.get("west")) < 8,
          "The area-map overview must not zoom out to the whole world.");
      }
    } finally {
      await context.close();
    }
  }
  if (captureBefore) assert.ok(results.some(result => result.afterLoad || result.afterLayout));
  console.log(JSON.stringify({before: captureBefore, results}));
}

async function checkMapReflow(browser, base) {
  const evidence = [];
  for (const [name, pathname] of [["all", "/"], ["saved", fixture.bounded_url]]) {
    const context = await browser.newContext({
      viewport: {width: 1180, height: 820}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    try {
      const requests = [];
      await context.route("**/*", route => {
        const target = new URL(route.request().url());
        assert.equal(target.origin, base);
        if (target.pathname === "/api/jobs/open") requests.push(target.pathname);
        return route.continue();
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.goto(base + pathname);
      const map = page.locator("#lead-map");
      const action = page.locator("[data-search-map-area]");
      await page.locator('#lead-map[aria-busy="false"] .leaflet-overlay-pane path').first().waitFor({state: "attached"});
      const settleMapFrame = () => page.waitForFunction(() => {
        const node = document.querySelector("#lead-map");
        const layer = node.querySelector(".leaflet-overlay-pane svg");
        // Leaflet's SVG renderer pads its measured frame by 10% on all sides.
        return Math.abs(Number(layer.getAttribute("width")) - node.clientWidth * 1.2) < 3 &&
          Math.abs(Number(layer.getAttribute("height")) - node.clientHeight * 1.2) < 3;
      });
      await settleMapFrame();
      const initialUrl = page.url();
      const locations = () => map.evaluate(node => {
        const frame = node.getBoundingClientRect();
        return [...node.querySelectorAll(".leaflet-marker-icon")].reduce((count, pin) => {
          const rect = pin.getBoundingClientRect();
          const inside = rect.width > 0 && rect.height > 0 && rect.left >= frame.left && rect.right <= frame.right &&
            rect.top >= frame.top && rect.bottom <= frame.bottom;
          return inside ? count + Number(pin.querySelector(".cluster-count")?.textContent || 1) : count;
        }, 0);
      });
      const initial = await locations();
      assert.ok(initial > 3, "Fixture needs a broad set of initially framed locations.");
      for (const [width, height] of [[844, 390], [390, 844], [320, 568], [820, 1180]]) {
        await page.setViewportSize({width, height});
        // Let the application's 150 ms resize debounce and Leaflet's redraw finish.
        await page.waitForTimeout(350);
        await settleMapFrame();
        await page.screenshot({path: path.join(output, `${name}-${width}x${height}.png`), animations: "disabled"});
        const result = {name, width, height, initial, inside: await locations(), offeredSearch: await action.isVisible()};
        evidence.push(result);
        assert.equal(page.url(), initialUrl);
        assert.deepEqual(requests, []);
        if (!captureBefore) {
          assert.equal(result.inside, initial, `Map reflow lost locations at ${width}x${height}`);
          assert.equal(result.offeredSearch, false, "Reflow must not imply user movement.");
        }
      }
      if (!captureBefore) {
        const mapArea = page.getByRole("button", {name: "Map area", exact: true});
        const zoomIn = map.getByRole("button", {name: "Zoom in", exact: true});
        await zoomIn.press("Enter");
        await zoomIn.press("Enter");
        await map.press("ArrowRight");
        await map.locator(".leaflet-pan-anim").waitFor({state: "detached"});
        await action.waitFor({state: "visible"});
        await mapArea.click();
        const center = await map.locator("#lead-map-status").textContent();
        await page.setViewportSize({width: 390, height: 844});
        await page.waitForTimeout(350);
        await settleMapFrame();
        await mapArea.click();
        assert.equal(await map.locator("#lead-map-status").textContent(), center, "Reflow changed the visitor's map center.");
        assert.ok(await action.isVisible());
        assert.deepEqual(requests, []);
        assert.equal(page.url(), initialUrl);
      }
    } finally {
      await context.close();
    }
  }
  console.log(JSON.stringify({before: captureBefore, evidence}));
  if (captureBefore) assert.ok(evidence.some(result => result.inside < result.initial || result.offeredSearch));
}

async function checkAreaMapTools(browser, base) {
  const cases = [
    ["narrow", 320, 568, 100, "/"],
    ["text", 320, 568, 200, "/"],
    ["landscape", 844, 390, 100, "/"],
    ["contractor", 390, 844, 100, "/leads"],
  ];
  for (const [name, width, height, textSize, pathname] of captureBefore ? cases.slice(0, 1) : cases) {
    const context = await browser.newContext({
      viewport: {width: 1180, height: 820}, hasTouch: true, serviceWorkers: "block", reducedMotion: "reduce",
    });
    try {
      const requests = [];
      await context.route("**/*", route => {
        const url = new URL(route.request().url());
        assert.equal(url.origin, base);
        if (url.pathname === "/api/jobs/open") {
          requests.push(url);
          if (name === "text" && requests.length === 1) return route.fulfill({status: 503, json: {ok: false}});
        }
        return route.continue();
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.goto(base + pathname);
      const map = page.locator("#lead-map");
      await page.locator('#lead-map[aria-busy="false"] .leaflet-overlay-pane path').first().waitFor({state: "attached"});
      if (textSize !== 100) {
        await page.evaluate(size => { document.documentElement.style.fontSize = size + "%"; }, textSize);
      }
      await page.setViewportSize({width, height});
      await page.waitForTimeout(350);
      const area = page.getByRole("button", {name: "Map area", exact: true});
      const reset = page.getByRole("button", {name: "DMV view", exact: true});
      const action = page.locator("[data-search-map-area]");
      await area.waitFor();
      await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
      const geometry = await page.evaluate(() => {
        const map = document.querySelector("#lead-map").getBoundingClientRect();
        const tools = document.querySelector(".map-view-controls");
        const buttons = [...tools.querySelectorAll("button:not([hidden])")];
        const visiblePins = [...document.querySelectorAll("#lead-map .leaflet-marker-icon")].flatMap(pin => {
          const rect = pin.getBoundingClientRect();
          const x = rect.x + rect.width / 2;
          const y = rect.y + rect.height / (pin.querySelector(".cluster-count") ? 2 : 3);
          if (x < map.left || x > map.right || y < map.top || y > map.bottom ||
              x < 0 || x >= innerWidth || y < 0 || y >= innerHeight) return [];
          return [{name: pin.getAttribute("aria-label") || pin.title || "Cluster",
            blockedBy: document.elementFromPoint(x, y)?.closest("button")?.textContent.trim() || ""}];
        });
        return {dockOutside: tools.getBoundingClientRect().bottom <= map.top + 1,
          textFits: buttons.every(button => button.offsetWidth >= 44 && button.offsetHeight >= 44 &&
            button.scrollWidth <= button.clientWidth + 1 && button.scrollHeight <= button.clientHeight + 1), visiblePins};
      });
      if (captureBefore) {
        assert.equal(geometry.dockOutside, false);
        assert.ok(geometry.visiblePins.some(pin => pin.blockedBy), "Expected a marker under the old controls.");
        console.log(JSON.stringify(geometry));
        continue;
      }
      assert.ok(geometry.dockOutside && geometry.textFits, name + ": dock and labels must fit outside the map");
      assert.ok(geometry.visiblePins.length && geometry.visiblePins.every(pin => !pin.blockedBy),
        name + ": Workdoe controls must not cover marker hit targets");
      assert.ok(await page.getByRole("group", {name: "Map controls"}).isVisible());
      await area.focus();
      await area.press("Enter");
      assert.match(await map.locator("#lead-map-status").textContent(), /Current map area is approximately/);
      assert.ok(await area.evaluate(button => button === document.activeElement));
      if (pathname === "/") {
        await action.waitFor({state: "hidden"});
        const layout = () => map.evaluate(node => [
          node.clientWidth, node.clientHeight, node.closest(".market-map-stage").querySelector(".map-stage-toolbar").offsetHeight,
        ]);
        const frame = await layout();
        await map.getByRole("button", {name: "Zoom in", exact: true}).press("Enter");
        await action.waitFor();
        assert.deepEqual(await layout(), frame, "The search action must not resize the canvas.");
        assert.deepEqual(requests, []);
        await action.press("Enter");
        if (name === "text") {
          await page.getByText("Previous results", {exact: true}).waitFor();
          await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
          assert.ok(await action.evaluate(button => button === document.activeElement));
          assert.deepEqual(await layout(), frame, "A search failure must not resize the canvas.");
          await action.press("Enter");
        }
        await action.waitFor({state: "hidden"});
        assert.ok(await map.evaluate(node => node === document.activeElement));
        assert.equal(requests.length, name === "text" ? 2 : 1);
        assert.ok(requests[0].searchParams.has("north"));
      }
      if (name === "narrow") {
        await reset.tap();
        await action.waitFor({state: "hidden"});
        await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
        assert.match(await map.locator("#lead-map-status").textContent(), /DMV map view restored/);
        const pin = map.locator("img.leaflet-marker-icon").first();
        await pin.tap();
        await page.locator('[data-market-workspace][data-mobile-panel="details"]').waitFor();
        assert.equal(await page.getByRole("tab", {name: "Details", exact: true}).getAttribute("aria-selected"), "true");
      }
      console.log(`PASS: ${name} dock, marker targets, keyboard area and search (${useWebkit ? "WebKit" : "Chromium"})`);
    } finally {
      await context.close();
    }
  }
}

async function checkForcedColorSelection(browser, base) {
  const results = [];
  for (const scheme of ["light", "dark"]) {
    const context = await browser.newContext({
      viewport: {width: 390, height: 844}, colorScheme: scheme, forcedColors: "active",
      serviceWorkers: "block", reducedMotion: "reduce",
    });
    try {
      await context.route("**/*", route => {
        assert.equal(new URL(route.request().url()).origin, base);
        return route.continue();
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.goto(base + "/");
      const map = page.getByRole("tab", {name: "Map", exact: true});
      const projects = page.getByRole("tab", {name: "Projects", exact: true});
      assert.equal(await page.evaluate(() => matchMedia("(forced-colors: active)").matches), true);
      assert.equal(await map.getAttribute("aria-selected"), "true");
      await map.press("ArrowLeft");
      assert.equal(await projects.getAttribute("aria-selected"), "true");
      assert.equal(await map.getAttribute("aria-selected"), "false");
      assert.equal(await projects.evaluate(node => node === document.activeElement), true);
      const search = page.getByRole("searchbox", {name: "Search projects"});
      await search.focus();
      const selectedFamily = page.locator('.service-family-filter-link[aria-current="page"] .service-family-filter-copy strong');
      const selectedRow = page.locator('.project-result[aria-current="true"] .project-result-heading strong');
      const inactiveFamily = page.locator('.service-family-filter-link:not([aria-current]) .service-family-filter-copy strong').first();
      const inactiveRow = page.locator('.project-result:not([aria-current]) .project-result-heading strong').first();
      const decoration = locator => locator.evaluate(node => getComputedStyle(node).textDecorationLine);
      const selected = await Promise.all([projects, selectedFamily, selectedRow].map(decoration));
      const unselected = await Promise.all([map, inactiveFamily, inactiveRow].map(decoration));
      const background = locator => locator.evaluate(node => getComputedStyle(node).backgroundColor);
      const outline = await search.evaluate(node => getComputedStyle(node).outlineStyle);
      assert.notEqual(outline, "none");
      await page.screenshot({path: path.join(output, `01-projects-${scheme}.png`), animations: "disabled"});
      results.push({scheme, selected, unselected, focused: "search", tabBackgrounds: [
        await background(projects), await background(map),
      ]});
      if (captureBefore) {
        assert.deepEqual(selected, ["none", "none", "none"], "The baseline reproduces the missing non-color cues.");
      } else {
        assert.deepEqual(selected, ["underline", "underline", "underline"]);
        assert.deepEqual(unselected, ["none", "none", "none"]);
        await projects.press("ArrowRight");
        assert.equal(await map.getAttribute("aria-selected"), "true");
        assert.equal(await map.evaluate(node => node === document.activeElement), true);
        assert.equal(await decoration(map), "underline");
        assert.equal(await decoration(projects), "none");
        await page.waitForFunction(() => {
          const mapElement = document.querySelector('#lead-map[aria-busy="false"]');
          const boundary = mapElement?.querySelector(".leaflet-overlay-pane svg");
          const marker = mapElement?.querySelector(".leaflet-marker-icon");
          return boundary?.getBoundingClientRect().width > 0 && marker?.getBoundingClientRect().width > 0;
        });
        await page.getByRole("button", {name: "Zoom in", exact: true}).focus();
        await page.screenshot({path: path.join(output, `02-map-${scheme}.png`), animations: "disabled"});
        await projects.click();
        const sample = page.locator('a[data-job-id="demo-01"]');
        await sample.press("Enter");
        await page.getByRole("heading", {name: "Power wash brick rowhouse exterior", exact: true}).waitFor();
        await projects.click();
        assert.equal(await sample.getAttribute("aria-current"), "true");
        assert.equal(await decoration(sample.locator(".project-result-heading strong")), "underline");
        assert.equal(await decoration(page.locator('a[data-job-id="7001"] .project-result-heading strong')), "none");
      }
    } finally {
      await context.close();
    }
  }
  console.log(JSON.stringify({before: captureBefore, results}));
}

async function checkServerMapSnapshot(browser, base) {
  for (const [name, width, script, pathname] of [
    ["home-desktop", 1280, true, "/"],
    ["bounded-phone", 390, true, fixture.bounded_url],
    ["bounded-no-script", 390, false, fixture.bounded_url],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height: 844}, javaScriptEnabled: script, serviceWorkers: "block", reducedMotion: "reduce",
    });
    try {
      const requests = [];
      await context.route("**/*", route => {
        const target = new URL(route.request().url());
        assert.equal(target.origin, base);
        if (target.pathname !== "/api/jobs/open") return route.continue();
        requests.push(target);
        return route.fulfill({json: {...fixture.zip_jobs, truncated: false}});
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.goto(base + pathname);
      if (script) {
        await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
        await page.locator("#lead-map .leaflet-overlay-pane path").first().waitFor({state: "attached"});
        if (width < 900) await page.getByRole("tab", {name: "Projects", exact: true}).click();
      }
      assert.equal(requests.length, 0, "A server-rendered snapshot must not trigger a second lookup.");
      const items = page.locator("[data-project-results] a[data-job-id]");
      const expected = pathname === "/" ? fixture.jobs.jobs.map(job => String(job.id)) : fixture.bounded_ids;
      assert.deepEqual(await items.evaluateAll(nodes => nodes.map(node => node.dataset.jobId)), expected);
      const truncation = page.locator("[data-project-truncation]");
      assert.equal(await truncation.isVisible(), pathname === "/");
      if (pathname !== "/") {
        const north = script ? new URL(page.url()).searchParams.get("north")
          : await page.locator('input[type="hidden"][name="north"]').inputValue();
        assert.equal(Number(north), 39.5);
      }
      if (!script) {
        await Promise.all([
          page.waitForURL(url => url.searchParams.get("sort") === "newest"),
          page.getByRole("button", {name: "Filter", exact: true}).click(),
        ]);
        await items.first().waitFor();
        assert.deepEqual(await items.evaluateAll(nodes => nodes.map(node => node.dataset.jobId)), expected);
        for (const key of ["north", "south", "east", "west"]) assert.ok(new URL(page.url()).searchParams.has(key));
        assert.equal(requests.length, 0);
      }
      if (name === "home-desktop") {
        const input = page.locator('input[name="q"]');
        await input.fill("22201");
        await input.press("Enter");
        await page.locator('[data-project-results] a[data-job-id="7001"]').waitFor();
        await truncation.waitFor({state: "hidden"});
        assert.equal(requests.length, 1);
        assert.equal(requests[0].searchParams.get("q"), "22201");
        await page.getByRole("button", {name: "Zoom in", exact: true}).click();
        const searchArea = page.getByRole("button", {name: "Search this area", exact: true});
        await searchArea.click();
        await searchArea.waitFor({state: "hidden"});
        assert.equal(requests.length, 2);
        for (const key of ["north", "south", "east", "west"]) assert.ok(requests[1].searchParams.has(key));
      }
      console.log(`PASS: ${name}, zero startup lookups (${useWebkit ? "WebKit" : "Chromium"})`);
    } finally {
      await context.close();
    }
  }
}

async function checkZipSearch(browser, base) {
  for (const [name, script, url] of [
    ["submitted-zip", true, "/"], ["stale-zip", true, "/"], ["direct-zip", true, "/?q=22201"],
    ["direct-no-script", false, "/?q=22201"],
  ]) {
    const context = await browser.newContext({
      viewport: {width: 390, height: 844}, javaScriptEnabled: script, serviceWorkers: "block",
    });
    try {
      const requested = [];
      let releaseStale;
      const staleGate = new Promise(resolve => { releaseStale = resolve; });
      await context.route("**/*", async route => {
        const target = new URL(route.request().url());
        assert.equal(target.origin, base);
        if (target.pathname !== "/api/jobs/open") return route.continue();
        const query = target.searchParams.get("q") || "";
        requested.push(query);
        if (query === "22199") {
          await staleGate;
          return route.fulfill({json: {...fixture.zip_jobs, jobs: [
            {...fixture.zip_jobs.jobs[0], id: 7998, title: "Stale ZIP response"},
          ]}});
        }
        return route.fulfill({json: query ? fixture.zip_jobs : fixture.jobs});
      });
      const page = await context.newPage();
      page.setDefaultTimeout(6500);
      const apiDone = script
        ? page.waitForResponse(result => new URL(result.url()).pathname === "/api/jobs/open")
        : null;
      await page.goto(base + url);
      if (script) {
        await (await apiDone).finished();
        await page.getByRole("tab", {name: "Projects", exact: true}).click();
        const filter = page.locator('input[name="q"]');
        if (name === "stale-zip") {
          const matchOldQuery = event => new URL(event.url()).searchParams.get("q") === "22199";
          const sent = page.waitForRequest(matchOldQuery);
          const done = page.waitForResponse(matchOldQuery);
          await filter.fill("22199");
          await filter.press("Enter");
          await sent;
          await filter.fill("");
          releaseStale();
          await (await done).finished();
        } else if (url === "/") {
          await filter.fill("22201");
          const response = page.waitForResponse(result => new URL(result.url()).searchParams.get("q") === "22201");
          await filter.press("Enter");
          await (await response).finished();
        }
        await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
        assert.equal(requested.at(-1), name === "stale-zip" ? "22199" : "22201");
      }
      const results = page.locator("[data-project-results]");
      await results.locator('a[data-job-id="7001"]').waitFor();
      if (name === "stale-zip") {
        assert.equal(await results.locator('a[data-job-id="7998"]').count(), 0);
        assert.equal(new URL(page.url()).searchParams.get("q"), null);
        console.log(`PASS: ${name} (${useWebkit ? "WebKit" : "Chromium"})`);
        continue;
      }
      assert.equal(await results.locator("a[data-job-id]").count(), 1);
      assert.doesNotMatch(await results.innerText(), /22201/);
      assert.equal(new URL(page.url()).searchParams.get("q"), "22201");
      assert.equal(fixture.zip_jobs.jobs[0].zip_code, undefined);
      const cleaning = page.getByRole("link", {name: "Cleaning", exact: true});
      const familyUrl = async () => new URL(await cleaning.getAttribute("href"), base);
      assert.equal((await familyUrl()).searchParams.get("q"), "22201", "Family navigation must carry the applied query.");
      if (name === "submitted-zip") {
        const sorted = page.waitForResponse(response => new URL(response.url()).searchParams.get("sort") === "city");
        await page.getByRole("combobox", {name: "Sort", exact: true}).selectOption("city");
        await (await sorted).finished();
        await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
        await page.getByRole("searchbox", {name: "Search projects"}).fill("unsubmitted draft");
        const link = (await familyUrl()).searchParams;
        assert.equal(link.get("q"), "22201");
        assert.equal(link.get("sort"), "city");
        assert.equal(link.get("family"), "cleaning-upkeep");
      }
      console.log(`PASS: ${name} (${useWebkit ? "WebKit" : "Chromium"})`);
    } finally {
      await context.close();
    }
  }
}

async function checkSharedProject(browser, base) {
  for (const [name, width, requested, refresh, javaScriptEnabled] of [
    ["missing-desktop", 1280, "7999", "normal", true],
    ["missing-phone", 390, "7999", "normal", true],
    ["missing-no-script", 390, "7999", "normal", false],
    ["present", 1280, "7001", "normal", true],
    ["removed-during-refresh", 1280, "7001", "removed", true],
    ["found-during-refresh", 1280, "7999", "found", true],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height: 844}, javaScriptEnabled, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const external = [];
    try {
      await context.route("**/*", route => {
        const url = new URL(route.request().url());
        if (url.origin !== base) {
          external.push(url.origin);
          return route.abort();
        }
        if (url.pathname !== "/api/jobs/open" || refresh === "normal") return route.continue();
        const projects = fixture.jobs.jobs.filter(job => String(job.id) !== "7001");
        if (refresh === "found") {
          const fixtureProject = fixture.jobs.jobs.find(job => String(job.id) === "7001");
          projects.unshift({...fixtureProject, id: 7999, title: "Synthetic project restored"});
        }
        return route.fulfill({json: {...fixture.jobs, jobs: projects, result_count: projects.length}});
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      const url = base + "/?job_id=" + requested;
      const fetched = javaScriptEnabled ? page.waitForResponse(result => new URL(result.url()).pathname === "/api/jobs/open") : null;
      await page.goto(url);
      if (fetched) await (await fetched).finished();
      const details = page.locator("#market-details-panel");
      const missing = refresh === "removed" || requested === "7999" && refresh !== "found";
      if (missing) {
        await details.getByRole("heading", {name: "Project not shown"}).waitFor();
        assert.equal(await details.getByRole("link", {name: "Browse all projects"}).getAttribute("href"), "/");
        assert.equal(await details.getByRole("link", {name: /respond|bid/i}).count(), 0);
      } else {
        await details.locator(`[data-project-detail-content][data-job-id="${requested}"]`).waitFor();
      }
      assert.equal(new URL(page.url()).searchParams.get("job_id"), requested);
      if (width > 900 && javaScriptEnabled) {
        await page.waitForFunction(() => {
          const map = document.querySelector("#lead-map");
          const boundary = map?.querySelector(".leaflet-overlay-pane svg");
          const markers = Array.from(map?.querySelectorAll(".leaflet-marker-icon") || []);
          const frame = map?.getBoundingClientRect();
          return boundary && boundary.getBoundingClientRect().width > 0 && markers.some(marker => {
            const pin = marker.getBoundingClientRect();
            return pin.width > 0 && pin.right > frame.left && pin.left < frame.right
              && pin.bottom > frame.top && pin.top < frame.bottom;
          });
        }, undefined, {timeout: 6000});
      }
      if (name.startsWith("missing")) {
        await details.scrollIntoViewIfNeeded();
        await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
      }
      if (name === "missing-phone") {
        await page.getByRole("tab", {name: "Projects", exact: true}).click();
        const replacement = page.locator('a[data-job-id="7001"]');
        await replacement.focus();
        assert.equal(new URL(page.url()).searchParams.get("job_id"), requested);
        await replacement.press("Enter");
        await details.locator('[data-project-detail-content][data-job-id="7001"]').waitFor();
        assert.equal(new URL(page.url()).searchParams.get("job_id"), "7001");
      }
      assert.deepEqual(external, []);
      console.log(`PASS: shared project ${name} (${useWebkit ? "WebKit" : "Chromium"})`);
    } finally {
      await context.close();
    }
  }
}

async function checkMapStartup(browser, base) {
  const findings = [];
  for (const [name, width, height, routePath] of [
    ["public", 390, 844, "/"], ["contractor", 390, 844, "/leads"], ["narrow", 320, 568, "/leads"],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const external = [];
    let release;
    let areaRequests = 0;
    const held = new Promise(resolve => { release = resolve; });
    try {
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin !== base) {
          external.push(url.origin);
          return route.abort();
        }
        if (url.pathname === "/map.js") await held;
        if (url.pathname === areaAsset) areaRequests++;
        return route.continue();
      });
      const page = await context.newPage();
      const scriptRequested = page.waitForRequest(request => new URL(request.url()).pathname === "/map.js");
      await page.goto(base + routePath, {waitUntil: "commit"});
      await scriptRequested;
      const item = page.locator("[data-project-results] a[data-job-id]").nth(8);
      try {
        await item.waitFor({timeout: 4000});
      } catch (error) {
        if (!captureBefore || error.name !== "TimeoutError") throw error;
        findings.push({name, blockedMarkup: (await page.locator("body").count()) === 0});
        release();
        await page.waitForLoadState("load");
        await page.locator("#lead-map .leaflet-overlay-pane path").first().waitFor();
        await page.screenshot({path: path.join(output, name + "-initialized.png"), animations: "disabled"});
        assert.deepEqual(external, []);
        continue;
      }
      const jobId = await item.getAttribute("data-job-id");
      const row = page.locator(`[data-project-results] a[data-job-id="${jobId}"]`);
      await row.evaluate(element => element.scrollIntoView({block: "center"}));
      await page.waitForFunction(() => document.querySelector("#market-projects-panel").getBoundingClientRect().top < 0);
      assert.equal(await page.evaluate(() => document.activeElement === document.body), true);
      const before = await row.boundingBox();
      assert.ok(before.y >= 0 && before.y + before.height <= height);
      // With a deferred script held, WebKit waits for document fonts before taking a screenshot.
      if (!useWebkit) {
        await page.screenshot({path: path.join(output, name + "-reading.png"), animations: "disabled"});
      }
      const jobs = routePath === "/" ? page.waitForResponse(
        response => new URL(response.url()).pathname === "/api/jobs/open",
      ) : null;
      release();
      await page.waitForLoadState("load");
      if (jobs) await (await jobs).finished();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const selected = await page.locator("[data-market-workspace]").getAttribute("data-mobile-panel");
      if (captureBefore && selected === "map") {
        await page.locator("#lead-map .leaflet-overlay-pane path").first().waitFor();
      }
      const after = await row.boundingBox();
      const areaBeforeMapChoice = areaRequests;
      await page.screenshot({path: path.join(output, name + "-initialized.png"), animations: "disabled"});
      findings.push({
        name, selected, beforeY: Math.round(before.y), afterY: after && Math.round(after.y),
        areaBeforeMapChoice,
      });
      if (!captureBefore) {
        assert.equal(selected, "filters", "Finishing map startup must not replace a scrolled project list.");
        assert.ok(after && Math.abs(after.y - before.y) <= 24, "Keep the same project close to its reading position.");
        assert.equal(areaBeforeMapChoice, 0, "Do not fetch the area asset while the map is hidden.");
        await page.getByRole("tab", {name: "Map", exact: true}).click();
        await page.locator("#lead-map .leaflet-overlay-pane path").first().waitFor();
        assert.equal(areaRequests, 1, "The user can still open the map.");
      }
      assert.deepEqual(external, []);
    } finally {
      release();
      await context.close();
    }
  }
  await fs.writeFile(path.join(output, "findings.json"), JSON.stringify(findings, null, 2));
  console.log(JSON.stringify(findings));
}

async function checkLeadNavigation(browser, base) {
  const findings = [];
  for (const [name, width, javaScriptEnabled, missingLeaflet] of [
    ["no-script", 390, false, false],
    ["leaflet-missing", 390, true, true],
    ["keyboard", 390, true, false],
    ["narrow", 320, true, false],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height: 844}, javaScriptEnabled, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const unexpected = [];
    try {
      await context.route("**/*", route => {
        const url = new URL(route.request().url());
        if (url.origin !== base) {
          unexpected.push(url.origin);
          return route.abort();
        }
        if (missingLeaflet && url.pathname === "/vendor/leaflet/leaflet.js") return route.abort();
        return route.continue();
      });
      const page = await context.newPage();
      await page.goto(base + "/leads", {waitUntil: "load"});
      const tabs = page.getByRole("tablist", {name: "Marketplace view"});
      const row = page.locator('[data-project-results] a[data-job-id="7001"]');
      const filename = suffix => path.join(output, name + suffix + ".png");
      if (!javaScriptEnabled || missingLeaflet) {
        await page.screenshot({path: filename("")});
        const listVisible = await row.isVisible();
        const tabsVisible = await tabs.isVisible();
        findings.push({name, listVisible, tabsVisible});
        if (!captureBefore) {
          assert.equal(listVisible, true, name + ": projects must remain visible");
          assert.equal(tabsVisible, false, name + ": nonfunctional tabs must be hidden");
          assert.equal(await row.getAttribute("href"), "/jobs/7001");
          await row.focus();
          assert.equal(await row.evaluate(node => node === document.activeElement), true);
        }
      } else {
        await page.locator("#lead-map .leaflet-overlay-pane path").first().waitFor();
        const mapTab = tabs.getByRole("tab", {name: "Map", exact: true});
        const projects = tabs.getByRole("tab", {name: "Projects", exact: true});
        const details = tabs.getByRole("tab", {name: "Details", exact: true});
        await mapTab.focus();
        await mapTab.press("Home");
        assert.equal(await projects.evaluate(node => node === document.activeElement), true);
        const projectsPanel = page.getByRole("tabpanel", {name: "Projects", exact: true});
        const linked = await projectsPanel.count() === 1;
        await row.focus();
        await row.press("Enter");
        const focusRestored = await details.evaluate(node => node === document.activeElement);
        await page.screenshot({path: filename("-detail")});
        findings.push({name, linked, focusRestored});
        if (!captureBefore) {
          assert.equal(linked, true, name + ": active tab must name its panel");
          assert.equal(focusRestored, true, name + ": selecting a row must leave visible focus");
          assert.equal(await details.getAttribute("aria-selected"), "true");
          const panel = page.getByRole("tabpanel", {name: "Details", exact: true});
          await panel.getByRole("heading", {name: "Synthetic unpinned project"}).waitFor();
          await details.press("Tab");
          assert.equal(await panel.evaluate(node => node === document.activeElement), true);
          await page.setViewportSize({width: 1280, height: 720});
          await page.getByRole("complementary", {name: "Selected project"}).waitFor();
          assert.equal(await tabs.isVisible(), false);
        }
      }
      assert.deepEqual(unexpected, []);
    } finally {
      await context.close();
    }
  }
  await fs.writeFile(path.join(output, "findings.json"), JSON.stringify(findings, null, 2));
  console.log(JSON.stringify(findings));
}

async function checkAreaMap(browser, base) {
  let windowsWebkitCookie = false;
  const cases = accessAreaMap ? [
    ["staging-home", 390, 844, "/"],
    ["staging-sign-in", 820, 1180, "/login"],
    ["staging-leads", 1280, 720, "/leads"],
    ["staging-expired", 390, 844, "/"],
  ] : [
    ["narrow", 320, 568, "/"], ["phone", 390, 844, "/"], ["tablet", 820, 1180, "/"],
    ["large-text", 320, 568, "/"],
    ["desktop", 1280, 720, "/leads"], ["slow", 390, 844, "/"],
    ["failed", 390, 844, "/"], ["corrupt", 1280, 720, "/leads"], ["timeout", 320, 568, "/"],
    ["sign-in", 390, 844, "/login"], ["create-account", 820, 1180, "/create-account"],
  ];
  for (const [name, width, height, routePath] of cases) {
    const deliveryStart = boundaryDeliveries.length;
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
      proxy: {server: base, bypass: "127.0.0.1"},
    });
    const unexpected = [];
    let release;
    const held = new Promise(resolve => { release = resolve; });
    boundaryFixture = {name, held};
    try {
      const expired = name === "staging-expired";
      await context.addCookies([accessAreaMap ? {
        name: "CF_Authorization", value: expired ? "expired-fixture" : "synthetic",
        url: base, httpOnly: true,
      } : {name: "fixture", value: "non-sensitive", url: base}]);
      // The loopback proxy does not forward traffic. Avoid interception rewriting headers.
      context.on("request", request => {
        const url = new URL(request.url());
        if (url.origin !== base) unexpected.push(url.origin);
      });
      const page = await context.newPage();
      await page.addInitScript(asset => {
        window.deviceLocationCalls = 0;
        for (const method of ["getCurrentPosition", "watchPosition"]) {
          navigator.geolocation[method] = () => { window.deviceLocationCalls++; };
        }
        const nativeFetch = window.fetch;
        window.fetch = function (input, init) {
          if (input === asset) window.boundaryCredentials = new Request(input, init).credentials;
          return nativeFetch.call(this, input, init);
        };
      }, areaAsset);
      const map = page.locator("#lead-map");
      const dock = page.locator(".map-view-dock");
      const mapTab = page.getByRole("tab", {name: "Map", exact: true});
      const projectsTab = page.getByRole("tab", {name: "Projects", exact: true});
      if (name === "timeout") await page.clock.install();
      const boundaryStarted = name === "timeout" ? page.waitForRequest(base + areaAsset) : null;
      const jobs = name === "slow" ? page.waitForResponse(response =>
        new URL(response.url()).pathname === "/api/jobs/open" && response.ok()) : null;
      await page.goto(base + routePath, {waitUntil: "domcontentloaded"});
      if (name === "large-text") await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      if (!await map.isVisible()) await mapTab.click();
      if (jobs) {
        await (await jobs).finished();
        await page.locator("#lead-map[aria-busy=true] .map-fallback").waitFor();
        await dock.waitFor({state: "hidden"});
        await projectsTab.click();
        await page.locator("[data-project-results]").waitFor();
        await mapTab.click();
        release();
      }
      if (boundaryStarted) {
        await boundaryStarted;
        await page.clock.runFor(14000);
        await page.locator("#lead-map[aria-busy=true] .map-fallback").waitFor();
        await page.clock.runFor(2000);
      }
      if (expired || name === "failed" || name === "corrupt" || name === "timeout") {
        const browse = map.getByRole("button", {name: "Browse projects"});
        await dock.waitFor({state: "hidden"});
        await browse.click();
        await page.locator("[data-project-results]:focus").waitFor();
        assert.equal(await map.locator(".leaflet-overlay-pane path").count(), 0);
      } else {
        const layer = map.locator(".leaflet-overlay-pane svg path");
        await layer.first().waitFor();
        assert.equal(await layer.count(), 50, name + ": all reviewed boundaries registered");
        assert.equal(await map.locator(".leaflet-overlay-pane path.leaflet-interactive").count(), 0);
        await map.locator(".leaflet-control-attribution").getByText("U.S. Census Bureau", {exact: false}).waitFor();
        await page.locator("#lead-map[aria-busy=false]").waitFor();
        if (routePath !== "/leads") {
          const source = page.locator("[data-map-source-counts]");
          const listOnly = page.locator("[data-map-list-only-count]");
          assert.equal(await source.innerText(), "0 live / 15 sample");
          assert.equal(await listOnly.innerText(), "; 1 list only");
          for (const counts of [source, listOnly]) {
            assert.ok(await counts.evaluate(node => {
              const bounds = node.getBoundingClientRect();
              return bounds.width > 0 && bounds.height > 0 && bounds.left >= 0 && bounds.right <= innerWidth + 1
                && document.documentElement.scrollWidth <= innerWidth + 1;
            }), name + ": map counts must reflow without clipping or horizontal page scrolling");
          }
        }
        if (name === "sign-in" || name === "create-account") {
          await page.locator('[data-market-workspace][data-entry-mode="account"]').waitFor();
          await map.locator(".leaflet-marker-icon").first().waitFor();
          await dock.getByRole("button", {name: "Map area", exact: true}).press("Enter");
          assert.match(await map.locator("#lead-map-status").textContent(),
            /Current map area is approximately .* Workdoe does not access your device location\./);
        }
        if (["narrow", "phone", "large-text", "tablet", "desktop"].includes(name)) {
          if (name !== "narrow" && name !== "large-text") await map.locator(".area-map-label:visible").first().waitFor();
          await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
        }
        const zoom = map.locator(".leaflet-control-zoom-in");
        await zoom.focus();
        if (name === "large-text") {
          await page.waitForFunction(() => {
            const focused = document.activeElement;
            const box = focused.getBoundingClientRect();
            const footer = document.querySelector(".market-policy-footer");
            const bottom = footer ? Math.min(innerHeight, footer.getBoundingClientRect().top) : innerHeight;
            return focused.matches(".leaflet-control-zoom-in") && box.top >= 0 && box.bottom <= bottom;
          }, null, {timeout: 2500});
        }
        const before = await layer.first().getAttribute("d");
        await zoom.press("Enter");
        await page.waitForFunction(value => {
          const first = document.querySelector("#lead-map .leaflet-overlay-pane path");
          return first && first.getAttribute("d") !== value;
        }, before);
        if (await projectsTab.isVisible()) await projectsTab.click();
        await page.locator("[data-project-results] a[data-job-id]").first().waitFor();
        if (name === "phone") {
          await page.locator('[data-project-results] a[data-job-id="7001"]').click();
          await page.getByText("(no map pin)", {exact: true}).waitFor();
          assert.equal(await map.locator('.leaflet-marker-icon[title^="Synthetic unpinned project"]').count(), 0);
        }
      }
      assert.equal(await page.evaluate(() => window.boundaryCredentials), accessAreaMap ? "same-origin" : "omit");
      assert.equal(await page.evaluate(() => window.deviceLocationCalls), 0, name + ": no device location access");
      const deliveries = boundaryDeliveries.slice(deliveryStart);
      // Windows WebKit 2311 also sends this cookie for a plain loopback fetch with credentials: omit.
      const engineCookie = !accessAreaMap && useWebkit && process.platform === "win32"
        && deliveries[0]?.cookie === "fixture=non-sensitive";
      windowsWebkitCookie ||= engineCookie;
      assert.deepEqual(deliveries, [{
        status: expired ? 302 : name === "failed" ? 503 : 200,
        cookie: accessAreaMap ? `CF_Authorization=${expired ? "expired-fixture" : "synthetic"}`
          : engineCookie ? "fixture=non-sensitive" : undefined,
        referer: undefined,
      }], name + ": one boundary request with the expected headers and status");
      assert.deepEqual(unexpected, []);
      console.log(`PASS: ${name} area map (${useWebkit ? "WebKit" : "Chromium"})`);
    } finally {
      boundaryFixture = null;
      release();
      await context.close();
    }
  }
  if (windowsWebkitCookie) console.log("LIMITATION: Windows WebKit sent a same-origin synthetic cookie despite credentials: omit.");
}

async function checkTileOutage(browser, base) {
  for (const [name, width, height, routePath] of [
    ["cold", 390, 844, "/"], ["timeout", 320, 568, "/"], ["late", 1280, 720, "/leads"],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    let tileRequests = 0;
    let fail = name !== "late";
    let release;
    const held = new Promise(resolve => { release = resolve; });
    let finishSearch;
    const searchHeld = new Promise(resolve => { finishSearch = resolve; });
    const unexpected = [];
    try {
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin === "https://tile.openstreetmap.org" && /^\/\d+\/\d+\/\d+\.png$/.test(url.pathname)) {
          tileRequests++;
          if (!fail) return route.fulfill({contentType: "image/png", body: tile});
          if (name !== "cold") await held;
          return route.fulfill({status: 403, body: "Synthetic tile outage"}).catch(() => {});
        }
        if (url.origin === base) {
          if (name === "cold" && url.pathname === "/api/jobs/open") await searchHeld;
          return route.continue();
        }
        unexpected.push(url.origin);
        return route.abort();
      });
      const page = await context.newPage();
      page.setDefaultTimeout(6000);
      const pageErrors = [];
      page.on("pageerror", error => pageErrors.push(error.message));
      if (name === "timeout") await page.clock.install({time: new Date("2026-11-09T12:00:00Z")});
      await page.goto(base + routePath + "?job_id=7001", {waitUntil: "domcontentloaded"});
      if (name === "late") {
        await page.locator(".leaflet-tile-loaded").first().waitFor({state: "visible"});
        const initialRequests = tileRequests;
        fail = true;
        const zoom = page.getByRole("button", {name: "Zoom in", exact: true});
        await zoom.press("Enter");
        assert.equal(await zoom.evaluate(node => node === document.activeElement), true);
        await page.waitForFunction(() => document.querySelector(".leaflet-tile:not(.leaflet-tile-loaded)"));
        assert.ok(tileRequests > initialRequests);
        release();
      }
      const browse = page.locator("#lead-map").getByRole("button", {name: "Browse projects", exact: true});
      if (name === "timeout") {
        await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
        await page.clock.runFor(14000);
        assert.equal(await browse.isVisible(), false, "A slow request must get the full deadline.");
        await page.clock.runFor(2000);
        assert.equal(await browse.isVisible(), true, "Recovery must not wait for any tile response.");
        release();
      }
      if (name === "cold") {
        await page.waitForLoadState("load");
        await page.screenshot({path: path.join(output, "cold.png")});
        finishSearch();
        await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
      }
      await browse.waitFor({state: "visible"});
      const rect = await browse.boundingBox();
      assert.ok(rect && rect.x >= 0 && rect.x + rect.width <= width + 1
        && rect.y >= 0 && rect.y + rect.height <= height + 1, "Recovery action stays within the viewport.");
      const map = page.locator("#lead-map");
      assert.equal(await map.getAttribute("aria-label"), "Project map unavailable");
      assert.equal(await page.getByRole("button", {name: "Zoom in", exact: true}).isVisible(), false);
      assert.match(await page.locator("[data-map-result-count]").innerText(), /projects? available$/);
      assert.match(await page.locator("#lead-map-status").textContent(), /map couldn.t load/i);
      assert.equal(await browse.evaluate(node => node === document.activeElement), name === "late");
      assert.ok(tileRequests > 0, "The synthetic provider must have been exercised.");
      const requestsAtFailure = tileRequests;
      await browse.press("Enter");
      assert.equal(await page.locator("[data-project-results]").evaluate(node => node === document.activeElement), true);
      const row = page.locator('[data-project-results] a[data-job-id="7001"]');
      await row.press("Enter");
      assert.match(await page.locator("[data-project-detail-content]").innerText(), /Synthetic unpinned project/);
      assert.equal(new URL(page.url()).searchParams.get("job_id"), "7001");
      assert.equal(tileRequests, requestsAtFailure, "List recovery must not restart tile requests.");
      assert.deepEqual(unexpected, []);
      assert.deepEqual(pageErrors, []);
      console.log("PASS: synthetic " + name + " tile outage keeps projects and keyboard navigation available");
    } finally {
      release();
      finishSearch();
      await context.close();
    }
  }
}

async function checkSearchCooldown(browser, base) {
  const results = [];
  const startedAt = Date.parse("2026-11-09T12:00:00Z");
  for (const [width, height, scenario, retryAfter, waitMs] of [
    [390, 844, "seconds", "120", 120000],
    [1280, 720, "date", new Date(startedAt + 8000).toUTCString(), 8000],
    [320, 568, "fallback", "malformed", 10000],
    [844, 390, "missing", null, 10000],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    let requests = 0;
    try {
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin === "https://tile.openstreetmap.org") {
          return route.fulfill({contentType: "image/png", body: tile});
        }
        if (url.origin !== base) return route.abort();
        if (url.pathname !== "/api/jobs/open") return route.continue();
        requests += 1;
        if (requests === 2) {
          return route.fulfill({
            status: 429, headers: {
              ...(retryAfter === null ? {} : {"Retry-After": retryAfter}),
              Date: new Date(startedAt).toUTCString(),
            },
            contentType: "text/html", body: "<html>Unreviewed edge error content</html>",
          });
        }
        return route.fulfill({json: fixture.jobs});
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.clock.install({time: new Date(startedAt)});
      await page.goto(base + "/?job_id=7001");
      const idle = page.locator('#lead-map[aria-busy="false"]');
      await idle.waitFor({state: "attached"});
      if (scenario === "fallback") {
        await page.evaluate(async () => {
          document.documentElement.style.fontSize = "200%";
          await document.fonts.ready;
        });
        await page.clock.runFor(100);
      }
      const mapTab = page.getByRole("tab", {name: "Map", exact: true});
      const projects = page.getByRole("tab", {name: "Projects", exact: true});
      const filter = page.locator("[data-market-filters] button[type=submit]");
      const row = page.locator('[data-project-results] a[data-job-id="7001"]');
      const area = page.locator("[data-search-map-area]");
      const initial = scenario === "seconds" ? area : filter;
      if (scenario === "seconds") {
        if (await mapTab.isVisible()) await mapTab.press("Enter");
        await page.locator(".leaflet-control-zoom-in").press("Enter");
      } else if (await projects.isVisible()) {
        await projects.press("Enter");
      }
      const limited = page.waitForResponse(r => r.status() === 429);
      await initial.press("Enter");
      await limited;
      await idle.waitFor({state: "attached"});
      await page.clock.runFor(100);
      await page.screenshot({path: path.join(output, scenario + ".png"), animations: "disabled"});
      assert.equal(await initial.evaluate(el => document.activeElement === el), true);
      assert.equal(await initial.getAttribute("aria-disabled"), "true", `${scenario}: search remained enabled during 429`);
      assert.equal(await page.locator("[data-map-source-counts]").textContent(), "Previous results");
      if (await projects.isVisible() && await projects.getAttribute("aria-selected") !== "true") {
        await projects.press("Enter");
      }
      await row.waitFor({state: "visible"});
      const notice = page.locator("[data-market-search-notice]");
      assert.match(await notice.textContent(), /Too many searches.*previous results/i);
      assert.doesNotMatch(await notice.textContent(), /Unreviewed edge/);
      assert.equal(await filter.textContent(), "Wait");
      if (scenario === "fallback") {
        const visible = await filter.evaluate(el => {
          const rail = el.closest("[data-market-panel]");
          const edges = rail.getBoundingClientRect();
          const box = el.getBoundingClientRect();
          return document.activeElement === el && box.top >= edges.top && box.bottom <= Math.min(innerHeight, edges.bottom) + 1;
        });
        assert.ok(visible, "At doubled text the focused button must show the paused state in view.");
      }
      await filter.press("Enter");
      await page.getByRole("combobox", {name: "Sort", exact: true}).selectOption("city");
      await page.clock.fastForward(waitMs - 2000);
      assert.equal(await filter.getAttribute("aria-disabled"), "true", `${scenario}: Retry-After ended early`);
      assert.equal(requests, 2, `${scenario}: a blocked action sent another request`);
      await page.clock.fastForward(3000);
      assert.equal(await filter.getAttribute("aria-disabled"), null);
      assert.equal(await filter.textContent(), "Retry");
      assert.match(await notice.textContent(), /ready to retry/i);
      assert.equal(requests, 2, `${scenario}: expiry sent an automatic request`);
      const recovered = page.waitForResponse(r => new URL(r.url()).pathname === "/api/jobs/open");
      await filter.press("Enter");
      assert.equal((await recovered).status(), 200);
      await idle.waitFor({state: "attached"});
      assert.equal(await notice.textContent(), "");
      assert.equal(await notice.evaluate(el => el.classList.contains("sr-only")), true);
      assert.equal(await row.isVisible(), true);
      assert.equal(await filter.evaluate(el => document.activeElement === el), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      results.push({scenario, waitMs, requests});
    } finally {
      await context.close();
    }
  }
  console.log(JSON.stringify({searchCooldown: results, output}));
}

async function checkProjectSearchFeedback(browser, base) {
  const cases = captureBefore ? [[390, 844, "failed"]] :
    [[390, 844, "failed"], [320, 568, "timeout"], [1280, 720, "invalid"], [390, 844, "elsewhere"]];
  for (const [width, height, scenario] of cases) {
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const stalled = Promise.withResolvers();
    const unexpected = [];
    let requests = 0;
    try {
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin !== base) {
          unexpected.push(url.origin);
          return route.abort();
        }
        if (url.pathname !== "/api/jobs/open") return route.continue();
        requests += 1;
        if (requests === 1) return route.fulfill({json: fixture.jobs});
        if (requests === 2 && scenario === "failed") {
          return route.fulfill({status: 503, json: {error: "Unreviewed provider error"}});
        }
        if (requests === 2 && scenario === "invalid") return route.fulfill({json: {jobs: [null]}});
        if (requests === 2) {
          await stalled.promise;
          if (scenario === "elsewhere") return route.fulfill({status: 503, json: {}});
          return route.fulfill({json: {jobs: [], count: 0}}).catch(() => {});
        }
        return route.fulfill({json: fixture.zip_jobs});
      });
      const page = await context.newPage();
      if (scenario === "timeout") await page.clock.install();
      await page.goto(base);
      const map = page.locator('#lead-map[aria-busy="false"]');
      await map.waitFor({state: "attached"});
      const projectsTab = page.getByRole("tab", {name: "Projects", exact: true});
      if (await projectsTab.isVisible()) await projectsTab.press("Enter");
      const filter = page.locator("[data-market-filters] button[type=submit]");
      const sort = page.getByRole("combobox", {name: "Sort", exact: true});
      const buttonInView = (inset = 0) => filter.evaluate((el, inset) => {
        const rail = el.closest("[data-market-panel]").getBoundingClientRect();
        const rect = el.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        return rect.top >= Math.max(rail.top, 0) + inset &&
          rect.bottom <= Math.min(rail.bottom, innerHeight) + 1 - inset && el.contains(hit);
      }, inset);
      const rows = page.locator("[data-project-results] a[data-job-id]");
      const ids = () => rows.evaluateAll(nodes => nodes.map(node => node.dataset.jobId));
      const appliedIds = await ids();
      const appliedUrl = page.url();
      const input = page.getByRole("searchbox", {name: "Search projects", exact: true});
      assert.ok(appliedIds.length > 1);
      await input.fill("22201");
      if (scenario === "failed") {
        await page.screenshot({path: path.join(output, "zip-draft.png"), animations: "disabled"});
      }
      assert.equal(requests, 1, "Typing must not request a search.");
      if (captureBefore) {
        assert.equal(await rows.count(), 0, "The baseline discarded the displayed listing slice while typing.");
        assert.equal(new URL(page.url()).searchParams.get("q"), "22201");
      } else {
        assert.deepEqual(await ids(), appliedIds, "Typing must preserve the last confirmed listings.");
        assert.equal(page.url(), appliedUrl, "A draft search must not enter the shareable URL.");
      }
      if (scenario === "timeout") await filter.scrollIntoViewIfNeeded();
      const requestStarted = page.waitForRequest(request => new URL(request.url()).pathname === "/api/jobs/open");
      await filter.press("Enter");
      assert.equal(new URL((await requestStarted).url()).searchParams.get("q"), "22201");
      if (scenario === "elsewhere") {
        await page.keyboard.press("Shift+Tab");
        assert.equal(await sort.evaluate(el => el === document.activeElement), true);
        stalled.resolve();
      }
      if (scenario === "timeout") {
        assert.ok(await buttonInView(), "Filter must be in view before the resize.");
        await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
        await page.setViewportSize({width, height: 360});
        await page.clock.runFor(100);
        await page.screenshot({path: path.join(output, "timeout-pending.png"), animations: "disabled"});
        const timedOut = page.waitForEvent("requestfailed", {
          predicate: request => new URL(request.url()).pathname === "/api/jobs/open",
        });
        await page.clock.fastForward(13000);
        assert.ok((await timedOut).failure());
      }
      await map.waitFor({state: "attached"});
      const notice = page.locator(".market-search-notice").filter({hasText: /search.*previous results/i});
      await page.screenshot({path: path.join(output, scenario + ".png"), animations: "disabled"});
      if (captureBefore) {
        assert.ok(await notice.isVisible(), "The baseline already had a warning about previous results.");
        assert.equal(await rows.count(), 0, "The baseline warns about results it has hidden.");
        console.log("Observed: the failed ZIP search says previous results are shown, but the list is empty.");
        continue;
      }
      assert.ok(await notice.isVisible(), scenario + ": previous results were not labeled");
      const status = page.locator("[data-project-results-status]");
      assert.match(await status.textContent(), /search.*previous results/i);
      assert.match(await page.locator("main").ariaSnapshot(), /status:.*previous results/i);
      assert.doesNotMatch(await page.locator("main").innerText(), /Unreviewed provider error/);
      assert.deepEqual(await ids(), appliedIds);
      assert.equal(page.url(), appliedUrl, "A failed search must not replace the URL for previous results.");
      const expectedFocus = scenario === "elsewhere" ? sort : filter;
      assert.equal(await expectedFocus.evaluate(el => el === document.activeElement), true);
      assert.equal(await filter.getAttribute("aria-disabled"), null);
      assert.equal(await filter.textContent(), "Retry");
      if (scenario === "invalid") {
        await rows.nth(1).press("Enter");
        assert.equal(new URL(page.url()).searchParams.get("q"), null, "Project selection must not publish the malformed search.");
      }
      if (scenario === "timeout") {
        assert.ok(await buttonInView(6), "Retry and its focus outline must be in view after reflow at doubled text.");
      }
      const recovered = page.waitForResponse(response => new URL(response.url()).pathname === "/api/jobs/open");
      await filter.press("Enter");
      assert.equal((await recovered).status(), 200);
      await map.waitFor({state: "attached"});
      stalled.resolve();
      assert.equal(await rows.count(), 1);
      assert.equal(new URL(page.url()).searchParams.get("q"), "22201");
      assert.match(await status.textContent(), /^1 project shown/);
      assert.equal(await notice.count(), 0);
      assert.equal(await filter.evaluate(el => el === document.activeElement), true);
      assert.equal(await filter.textContent(), "Filter");
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      assert.deepEqual(unexpected, []);
      await page.screenshot({path: path.join(output, scenario + "-recovered.png"), animations: "disabled"});
      console.log(`PASS: ${width}px ${scenario} search reports stale results and permits keyboard retry`);
    } finally {
      stalled.resolve();
      await context.close();
    }
  }
}

async function checkMapFocus(browser, base) {
  const failures = [];
  const results = [];
  for (const [width, height, scenario] of [
    [1280, 720, "retained"], [390, 844, "retained"], [390, 844, "removed"],
    [820, 1180, "area-success"], [390, 844, "area-error"], [1280, 720, "elsewhere"],
    [844, 390, "moved-again"],
  ]) {
    const name = `${width}x${height}-${scenario}`;
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const release = Promise.withResolvers();
    let boundedRequests = 0;
    try {
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin === "https://tile.openstreetmap.org") {
          return route.fulfill({contentType: "image/png", body: tile});
        }
        if (url.origin !== base) return route.abort();
        if (url.pathname !== "/api/jobs/open" || !url.searchParams.has("north")) return route.continue();
        boundedRequests += 1;
        await release.promise;
        if (scenario === "area-error") {
          return route.fulfill({status: 503, json: {error: "Could not refresh projects."}});
        }
        const jobs = scenario === "removed" ? {jobs: [], map_jobs: [], result_count: 0} : fixture.jobs;
        return route.fulfill({json: jobs});
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      await page.goto(base + "/?job_id=7001");
      const map = page.locator("#lead-map");
      await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
      const mapTab = page.getByRole("tab", {name: "Map", exact: true});
      if (await mapTab.isVisible()) await mapTab.press("Enter");
      const zoomIn = map.locator(".leaflet-control-zoom-in");
      await zoomIn.press("Enter");
      const area = page.locator("[data-search-map-area]");
      await area.press("Enter");
      await page.locator('#lead-map[aria-busy="true"]').waitFor({state: "attached"});
      const stayedOnArea = await area.evaluate(el => document.activeElement === el);
      const areaMarkedBusy = await area.getAttribute("aria-disabled");
      const row = page.locator('[data-project-results] a[data-job-id="7001"]');
      const search = page.getByRole("searchbox", {name: "Search projects", exact: true});
      const elsewhere = page.getByRole("navigation", {name: "Primary", exact: true})
        .getByRole("link", {name: "Sign in", exact: true});
      let expected;
      if (scenario === "retained" || scenario === "removed") {
        const projects = page.getByRole("tab", {name: "Projects", exact: true});
        if (await projects.isVisible()) await projects.press("Enter");
        await row.focus();
        expected = scenario === "retained" ? row : search;
      } else if (scenario === "elsewhere") {
        await elsewhere.focus();
        expected = elsewhere;
      } else if (scenario === "moved-again") {
        await zoomIn.press("Enter");
        expected = zoomIn;
      } else {
        // A second Enter on a pending action should not issue another search.
        if (stayedOnArea) await page.keyboard.press("Enter");
        expected = scenario === "area-success" ? map : area;
      }
      release.resolve();
      await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
      await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
      const focused = await expected.evaluate(el => document.activeElement === el);
      const observed = await page.evaluate(() => document.activeElement?.tagName);
      results.push({name, focused, observed, stayedOnArea, areaMarkedBusy, boundedRequests});
      if (!focused) failures.push(`${name}: focus landed on ${observed}`);
      if (scenario.startsWith("area-") && (!stayedOnArea || areaMarkedBusy !== "true" || boundedRequests !== 1)) {
        failures.push(`${name}: pending search was not focusable, disabled and single-submit`);
      }
      if (scenario === "area-error") {
        const retry = page.getByRole("button", {name: "Retry area search", exact: true});
        assert.ok(await retry.isVisible() && await retry.isEnabled(), `${name}: failed search could not be retried`);
        const response = page.waitForResponse(r => new URL(r.url()).pathname === "/api/jobs/open");
        await page.keyboard.press("Enter");
        assert.equal((await response).status(), 503);
      }
      if (scenario === "area-success") {
        assert.equal(await area.isVisible(), false);
        assert.ok(await map.evaluate(el => el.matches(":focus-visible") && getComputedStyle(el).outlineWidth === "3px"));
      }
      if (scenario === "moved-again") {
        assert.ok(await area.isVisible() && await area.isEnabled(), "A second movement must remain searchable.");
      }
      if (scenario === "retained" && focused) {
        await page.keyboard.press("ArrowDown");
        assert.notEqual(await page.locator(":focus").getAttribute("data-job-id"), "7001");
        assert.ok(await page.locator('[data-project-results] a[data-job-id]:focus').count());
      }
    } finally {
      release.resolve();
      await context.close();
    }
  }
  console.log(JSON.stringify({mapFocus: results, failures, output}));
  assert.deepEqual(failures, []);
}

async function checkDialogHistory(browser, base) {
  const results = [];
  const bounds = ["north", "south", "east", "west"];
  for (const [width, height, action] of [
    [1280, 720, "header"], [820, 1180, "header"], [390, 844, "header"], [844, 390, "header"],
    [1280, 720, "project"], [390, 844, "project"], [1280, 720, "removed"],
  ]) {
    const name = `${width}x${height}-${action}`;
    const projectAction = action !== "header";
    const context = await browser.newContext({
      viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const held = Promise.withResolvers();
    const release = Promise.withResolvers();
    const errors = [];
    try {
      await context.route("**/*", async route => {
        const url = new URL(route.request().url());
        if (url.origin === base) {
          if (url.pathname !== "/api/jobs/open" || !url.searchParams.has("north")) return route.continue();
          const viewport = Object.fromEntries(bounds.map(key => [key, Number(url.searchParams.get(key))]));
          held.resolve(viewport);
          await release.promise;
          const jobs = action === "removed" ? {jobs: [], map_jobs: [], result_count: 0} : fixture.jobs;
          return route.fulfill({json: {...jobs, viewport}});
        }
        if (url.origin === "https://tile.openstreetmap.org") {
          return route.fulfill({contentType: "image/png", body: tile});
        }
        errors.push(url.origin);
        return route.abort();
      });
      const page = await context.newPage();
      page.setDefaultTimeout(8000);
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(base + "/?job_id=7001");
      const map = page.locator("#lead-map");
      await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
      const projectsTab = page.getByRole("tab", {name: "Projects", exact: true});
      if (await projectsTab.isVisible()) await projectsTab.press("Enter");
      await page.getByRole("searchbox", {name: "Search projects", exact: true}).fill("window");
      const mapTab = page.getByRole("tab", {name: "Map", exact: true});
      if (await mapTab.isVisible()) await mapTab.press("Enter");
      await map.locator(".leaflet-control-zoom-in").click();
      await page.getByRole("button", {name: "Search this area", exact: true}).click();
      await page.locator('#lead-map[aria-busy="true"]').waitFor();
      const detailsTab = page.getByRole("tab", {name: "Details", exact: true});
      if (projectAction && await detailsTab.isVisible()) await detailsTab.press("Enter");
      const trigger = projectAction
        ? page.locator('[data-project-detail-content][data-job-id="7001"]').getByRole("link")
        : page.getByRole("navigation", {name: "Primary", exact: true}).getByRole("link", {name: "Sign in", exact: true});
      const viewport = await held.promise;
      await trigger.press("Enter");
      const dialog = page.getByRole("dialog");
      const close = dialog.getByRole("button", {name: "Close dialog", exact: true});
      await dialog.locator("[data-dialog-fragment]").waitFor();
      if (!projectAction) {
        const requests = dialog.getByRole("link", {name: "Account data requests", exact: true});
        assert.equal(await requests.getAttribute("href"), "/privacy#privacy-choices");
        assert.equal(await requests.isVisible(), true, `${name}: data request link is not visible in the sign-in dialog`);
      }
      const dialogUrl = page.url();
      assert.equal(new URL(dialogUrl).pathname, projectAction ? "/create-account" : "/login");
      release.resolve();
      await page.locator('#lead-map[aria-busy="false"]').waitFor({state: "attached"});
      await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
      assert.equal(page.url(), dialogUrl, `${name}: map results rewrote the open dialog URL`);
      assert.equal(await page.evaluate(() => history.state.workdoeDialog), true);
      await close.press(width < 1000 ? "Enter" : "Escape");
      await dialog.waitFor({state: "hidden"});
      const restored = new URL(page.url());
      assert.equal(restored.pathname, "/");
      assert.equal(restored.searchParams.get("q"), "window");
      assert.equal(restored.searchParams.get("job_id"), action === "removed" ? null : "7001");
      for (const key of bounds) assert.equal(Number(restored.searchParams.get(key)), viewport[key]);
      const focusTarget = action === "removed"
        ? page.getByRole("heading", {name: "No projects match", exact: true}) : trigger;
      assert.equal(await focusTarget.evaluate(el => document.activeElement === el), true, `${name}: lost return focus`);
      await page.goForward();
      await dialog.locator("[data-dialog-fragment]").waitFor();
      assert.equal(page.url(), dialogUrl);
      await page.goBack();
      await dialog.waitFor({state: "hidden"});
      assert.equal(page.url(), restored.href);
      assert.deepEqual(errors, []);
      results.push(name);
    } finally {
      release.resolve();
      await context.close();
    }
  }
  console.log(JSON.stringify({dialogHistory: results, output}));
}

async function checkProjectList(browser, base) {
  const results = [];
  for (const [width, height, textSize, javaScriptEnabled] of [
    [390, 844, 100, true], [820, 1180, 100, true], [1280, 720, 100, true],
    [320, 568, 200, true], [390, 844, 100, false],
  ]) {
    const context = await browser.newContext({
      viewport: {width, height}, javaScriptEnabled, serviceWorkers: "block", reducedMotion: "reduce",
    });
    const errors = [];
    try {
      await context.route("**/*", route => {
        const url = new URL(route.request().url());
        if (url.origin === base) return route.continue();
        if (url.origin === "https://tile.openstreetmap.org") {
          return route.fulfill({status: 200, contentType: "image/png", body: tile});
        }
        errors.push(url.origin);
        return route.abort();
      });
      const page = await context.newPage();
      page.on("pageerror", error => errors.push(error.message));
      await page.goto(base + "/");
      if (textSize !== 100) {
        await page.evaluate(size => { document.documentElement.style.fontSize = size + "%"; }, textSize);
      }
      const projects = page.getByRole("tab", {name: "Projects", exact: true});
      if (await projects.isVisible()) await projects.press("Enter");
      const rail = page.locator(".market-filter-rail");
      const row = rail.locator("[data-project-results] a[data-job-id]").first();
      await row.waitFor({state: "visible"});
      const bounds = await row.evaluate(el => {
        const row = el.getBoundingClientRect();
        const panel = el.closest(".market-filter-rail").getBoundingClientRect();
        return {top: Math.round(row.top), bottom: Math.round(row.bottom),
          edge: Math.floor(Math.min(innerHeight, panel.bottom))};
      });
      const name = `${width}x${height}-${textSize}-${javaScriptEnabled ? "interactive" : "no-script"}`;
      await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
      if (javaScriptEnabled && textSize === 100) {
        assert.ok(bounds.top >= 0 && bounds.bottom <= bounds.edge + 1,
          `${name}: first project is clipped (${JSON.stringify(bounds)})`);
      }
      assert.equal(await rail.locator(".service-family-filter-link").count(), 7);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
      const headerFits = await page.locator(".market-header").evaluate(header => {
        const logo = header.querySelector(".brand").getBoundingClientRect();
        const links = Array.from(header.querySelectorAll(".market-nav a"), a => a.getBoundingClientRect());
        return links.filter(link => link.width > 0).every(link => link.left >= logo.right - 1
          && link.right <= innerWidth + 1);
      });
      assert.ok(headerFits, `${name}: the home mark and task controls must not overlap`);
      if (textSize === 200) {
        assert.equal(await rail.locator(".service-family-filter-link").evaluateAll(links =>
          links.every(link => link.scrollWidth <= link.clientWidth + 1)), true);
        await row.scrollIntoViewIfNeeded();
        assert.ok(await row.evaluate(el => el.getBoundingClientRect().bottom
          <= el.closest(".market-filter-rail").getBoundingClientRect().bottom + 1));
      }
      const sort = rail.getByRole("combobox", {name: "Sort", exact: true});
      const filter = rail.getByRole("button", {name: "Filter", exact: true});
      assert.ok(await sort.isVisible() && await filter.isVisible());
      assert.ok(await rail.getByRole("link", {name: "Clear filters", exact: true}).isVisible());
      if (!javaScriptEnabled) {
        await rail.getByRole("searchbox", {name: "Search projects", exact: true}).fill("window");
        await sort.selectOption("city");
        await filter.click();
        await page.waitForURL(url => url.searchParams.get("q") === "window" && url.searchParams.get("sort") === "city");
      } else if (width === 390) {
        await rail.getByRole("searchbox", {name: "Search projects", exact: true}).fill("window");
        const search = page.waitForResponse(response => {
          const url = new URL(response.url());
          return url.pathname === "/api/jobs/open" && url.searchParams.get("q") === "window";
        });
        await filter.click();
        assert.ok((await search).ok());
      }
      assert.deepEqual(errors, []);
      results.push({name, ...bounds});
    } finally {
      await context.close();
    }
  }
  console.log(JSON.stringify({projectList: results}));
}

async function checkMapAttribution(browser, base) {
  const darkTile = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><path fill="#192731" d="M0 0h256v256H0z"/><path stroke="#324450" d="M0 64h256M0 192h256M64 0v256M192 0v256"/></svg>';
  const results = [];
  for (const pathname of ["/", "/leads"]) {
    for (const [width, height, textSize] of [[320, 420, 200], [390, 844, 100], [820, 1180, 200], [1280, 720, 100]]) {
      const context = await browser.newContext({
        viewport: {width, height}, serviceWorkers: "block", reducedMotion: "reduce",
      });
      const name = `${pathname === "/" ? "public" : "contractor"}-${width}x${height}-${textSize}`;
      const errors = [];
      try {
        await context.route("**/*", route => {
          const url = new URL(route.request().url());
          if (url.origin === base) return route.continue();
          if (url.origin === "https://tile.openstreetmap.org" && /^\/\d+\/\d+\/\d+\.png$/.test(url.pathname)) {
            return route.fulfill({status: 200, contentType: "image/svg+xml", body: darkTile});
          }
          errors.push(url.origin);
          return route.abort();
        });
        const page = await context.newPage();
        page.on("pageerror", error => errors.push(error.message));
        await page.goto(base + pathname);
        if (textSize !== 100) {
          await page.evaluate(size => { document.documentElement.style.fontSize = size + "%"; }, textSize);
        }
        const mapTab = page.getByRole("tab", {name: "Map", exact: true});
        if (await mapTab.isVisible()) await mapTab.click();
        const credit = page.locator("#lead-map .leaflet-control-attribution");
        const leaflet = credit.getByRole("link", {name: "Leaflet", exact: true});
        const provider = credit.getByRole("link", {name: "OpenStreetMap", exact: true});
        await page.locator("#lead-map img.leaflet-tile-loaded").first().waitFor({state: "visible"});
        if (useWebkit) {
          await provider.focus();
        } else {
          await leaflet.focus();
          await page.keyboard.press("Tab");
        }
        await credit.scrollIntoViewIfNeeded();
        const observation = await credit.evaluate(node => {
          const rgb = value => value.match(/[\d.]+/g).map(Number);
          const luminance = channels => channels.slice(0, 3).map(n => n / 255)
            .map(n => n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4)
            .reduce((sum, n, index) => sum + n * [0.2126, 0.7152, 0.0722][index], 0);
          const style = getComputedStyle(node);
          const background = rgb(style.backgroundColor);
          const alpha = background[3] ?? 1;
          const contrast = (fg, tile) => {
            const a = luminance(rgb(fg));
            const b = luminance(background.slice(0, 3).map(n => n * alpha + tile * (1 - alpha)));
            return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
          };
          const box = node.getBoundingClientRect(), mapNode = node.closest("#lead-map");
          const map = mapNode.getBoundingClientRect();
          const stage = mapNode.closest(".market-map-stage");
          const toolbar = stage.querySelector(".map-stage-toolbar").getBoundingClientRect();
          const zoom = mapNode.querySelector(".leaflet-control-zoom").getBoundingClientRect();
          const commands = mapNode.querySelector(".map-view-controls").getBoundingClientRect();
          const navFits = [...document.querySelectorAll(".mobile-task-nav a > span:last-child")].every(label => {
            if (!label.getClientRects().length) return true;
            const link = label.closest("a").getBoundingClientRect();
            return label.scrollWidth <= link.width + 1
              && label.getBoundingClientRect().height <= parseFloat(getComputedStyle(label).lineHeight) + 1;
          });
          const links = [...node.querySelectorAll("a")].map(link => {
            const css = getComputedStyle(link);
            return {
              href: link.href, focused: document.activeElement === link,
              contrast: Math.min(contrast(css.color, 0), contrast(css.color, 255)),
              underline: css.textDecorationLine.includes("underline"),
              outlined: css.outlineStyle === "solid" && parseFloat(css.outlineWidth) >= 2,
              visible: [...link.getClientRects()].every(rect =>
                rect.left >= 0 && rect.top >= 0 && rect.right <= innerWidth + 1 && rect.bottom <= innerHeight + 1
                && link.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2))),
            };
          });
          return {
            alpha, fontSize: parseFloat(style.fontSize), textContrast: Math.min(contrast(style.color, 0), contrast(style.color, 255)),
            fits: box.left >= map.left - 1 && box.right <= map.right + 1 && box.top >= map.top && box.bottom <= map.bottom + 1
              && document.documentElement.scrollWidth <= innerWidth + 1,
            toolbarFits: toolbar.bottom <= map.top + 1 && stage.scrollWidth <= stage.clientWidth + 1,
            commandsClearZoom: commands.left >= zoom.right || commands.top >= zoom.bottom,
            navFits,
            links,
          };
        });
        await page.screenshot({path: path.join(output, name + ".png"), animations: "disabled"});
        const osm = observation.links.find(link => link.href === "https://www.openstreetmap.org/copyright");
        const passes = observation.alpha === 1 && observation.fits && observation.toolbarFits
          && observation.commandsClearZoom && observation.navFits && observation.fontSize >= 12 * textSize / 100
          && observation.textContrast >= 4.5 && observation.links.length === 2
          && observation.links.every(link => link.contrast >= 4.5 && link.underline)
          && Boolean(osm?.focused && osm.outlined && osm.visible);
        assert.deepEqual(errors, [], name);
        results.push({name, passes, ...observation});
      } finally {
        await context.close();
      }
    }
  }
  await fs.writeFile(path.join(output, "results.json"), JSON.stringify(results, null, 2) + "\n");
  const failed = results.filter(row => !row.passes);
  console.log(JSON.stringify({states: results.length, failed: failed.map(row => row.name), output, externalRequests: 0}));
  assert.deepEqual(baseline ? results.filter(row => row.passes) : failed, []);
}

async function checkViewport(browser, base, profile, viewport, insets) {
  const context = await browser.newContext({
    viewport, isMobile: true, hasTouch: true, serviceWorkers: "block", reducedMotion: "reduce",
  });
  const unexpected = [], records = [];
  try {
    await context.route("**/*", route => {
      const url = new URL(route.request().url());
      if (url.origin === base) return route.continue();
      if (url.origin === "https://tile.openstreetmap.org" && /^\/\d+\/\d+\/\d+\.png$/.test(url.pathname)) {
        return route.fulfill({status: 200, contentType: "image/png", body: tile});
      }
      unexpected.push(url.origin);
      return route.abort();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(7000);
    const cdp = await context.newCDPSession(page);
    await cdp.send("Emulation.setSafeAreaInsetsOverride", {insets});
    const fits = ({x, y, width, height}) => x >= insets.left - 1 && y >= insets.top - 1 &&
      x + width <= viewport.width - insets.right + 1 && y + height <= viewport.height - insets.bottom + 1;

    async function capture(stage, targets) {
      const outside = [];
      for (const [label, locator] of Object.entries(targets)) {
        await locator.waitFor();
        if (!fits(await locator.boundingBox())) outside.push(label);
      }
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      await page.screenshot({path: path.join(output, `${profile}-${stage}.png`), animations: "disabled"});
      if (outside.includes("attribution")) {
        await targets.attribution.evaluate(node => node.scrollIntoView({block: "center"}));
        if (fits(await targets.attribution.boundingBox())) outside.splice(outside.indexOf("attribution"), 1);
        await page.screenshot({path: path.join(output, `${profile}-${stage}-attribution.png`), animations: "disabled"});
      }
      records.push({profile, stage, outside, overflow});
    }

    for (const location of ["/", "/leads"]) {
      await page.goto(base + location);
      const observedInsets = await page.evaluate(() => {
        const probe = document.createElement("div");
        probe.style.padding = "env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)";
        document.body.append(probe);
        const style = getComputedStyle(probe);
        const values = Object.fromEntries(["top", "right", "bottom", "left"].map(edge => [edge, parseFloat(style.getPropertyValue("padding-" + edge))]));
        probe.remove();
        return values;
      });
      assert.deepEqual(observedInsets, insets);
      const skip = page.getByRole("link", {name: "Skip to content", exact: true});
      if (!baseline) {
        assert.equal(await skip.evaluate(node => getComputedStyle(node).opacity), "0");
        await skip.focus();
        await page.waitForFunction(() => {
          const active = document.activeElement;
          return active.matches(".skip-link") && getComputedStyle(active).opacity === "1";
        });
        assert.ok(fits(await skip.boundingBox()), "Focused skip link is clear of the cutout.");
        await skip.blur();
      }
      const mapTab = page.getByRole("tab", {name: "Map", exact: true});
      if (await mapTab.isVisible()) await mapTab.click();
      const mapped = page.locator("[data-map-result-count]");
      await page.waitForFunction(expected =>
        document.querySelector("[data-map-result-count]")?.textContent.includes(expected),
      fixture.jobs.mapped_count + " projects mapped");
      assert.equal(await mapped.innerText(), fixture.jobs.mapped_count + " projects mapped");
      const projects = page.getByRole("tab", {name: "Projects", exact: true});
      if (await projects.isVisible()) await projects.click();
      const unpinned = page.locator('a[data-job-id="7001"]').first();
      await unpinned.click();
      await page.locator(".project-detail-location").getByText("(no map pin)", {exact: true}).waitFor();
      assert.equal(await page.locator('.leaflet-marker-icon[title^="Synthetic unpinned project"]').count(), 0);
      if (await mapTab.isVisible()) await mapTab.click();
      await capture(location === "/" ? "public-map" : "contractor-map", {
        home: page.getByRole("link", {name: "Workdoe home", exact: true}),
        zoom: page.locator(".leaflet-control-zoom-in"),
        attribution: page.locator(".leaflet-control-attribution"),
      });
    }
    await page.goto(base + "/");
    if (!baseline && profile === "phone-portrait") {
      const map = page.getByRole("tab", {name: "Map", exact: true});
      await map.click();
      await page.setViewportSize({width: 844, height: 390});
      await cdp.send("Emulation.setSafeAreaInsetsOverride", {insets: {top: 0, left: 47, right: 47, bottom: 21}});
      await page.waitForFunction(() => {
        const zoom = document.querySelector(".leaflet-control-zoom-in");
        return zoom?.getBoundingClientRect().left >= 47;
      });
      assert.equal(await map.getAttribute("aria-selected"), "true");
      await page.locator(".leaflet-control-zoom-in").click();
      await page.setViewportSize(viewport);
      await cdp.send("Emulation.setSafeAreaInsetsOverride", {insets});
      await page.waitForFunction(() => {
        const home = document.querySelector(".market-header .brand");
        return home?.getBoundingClientRect().top >= 47;
      });
      assert.equal(await map.getAttribute("aria-selected"), "true");
    }
    for (const title of ["Sign in", "Post project"]) {
      const trigger = page.locator(".market-header").getByRole("link", {name: title, exact: true});
      await trigger.click();
      const dialog = page.locator("[data-site-dialog][open]");
      const close = dialog.getByRole("button", {name: "Close dialog"});
      const surface = dialog.locator(".site-dialog-surface");
      if (title === "Sign in") {
        await dialog.locator("[data-clerk-entry]").waitFor({state: "attached"});
        await capture("signin", {surface, close});
      } else {
        const composer = dialog.locator("[data-project-composer].is-enhanced");
        const next = composer.locator('[data-project-step="1"] [data-project-next]');
        await capture("post", {surface, close, next});
        await composer.locator('input[name="service_group_slug"]').first().focus();
        await page.keyboard.press("Space");
        await next.click();
        assert.ok(await composer.locator('[data-project-step="2"]').isVisible(), "Continue advances one step.");
      }
      await close.click();
      await page.waitForURL(url => url.origin === base && url.pathname === "/");
      assert.ok(await trigger.evaluate(node => document.activeElement === node), "Close returns focus to the trigger.");
    }
    assert.deepEqual(unexpected, []);
    return records;
  } finally {
    await context.close();
  }
}

(async () => {
  let browser;
  try {
    await fs.mkdir(output, {recursive: true});
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    const base = "http://127.0.0.1:" + server.address().port;
    browser = useWebkit ? await webkit.launch({
      executablePath: process.env.WORKDOE_WEBKIT_EXECUTABLE || undefined,
      timeout: 15000,
    }) : await chromium.launch({
      chromiumSandbox: true, executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE,
    });
    if (mapStartup) {
      await checkMapStartup(browser, base);
      return;
    }
    if (leadNavigation) {
      await checkLeadNavigation(browser, base);
      return;
    }
    if (sharedProject) {
      await checkSharedProject(browser, base);
      return;
    }
    if (zipSearch) {
      await checkZipSearch(browser, base);
      return;
    }
    if (serverMapSnapshot) {
      await checkServerMapSnapshot(browser, base);
      return;
    }
    if (forcedColorSelection) {
      await checkForcedColorSelection(browser, base);
      return;
    }
    if (mapAreaMovement) {
      await checkMapAreaMovement(browser, base);
      return;
    }
    if (mapReflow) {
      await checkMapReflow(browser, base);
      return;
    }
    if (areaMapTools) {
      await checkAreaMapTools(browser, base);
      return;
    }
    if (searchFeedback) {
      await checkProjectSearchFeedback(browser, base);
      return;
    }
    if (areaMap) {
      await checkAreaMap(browser, base);
      return;
    }
    if (tileOutage) {
      await checkTileOutage(browser, base);
      return;
    }
    if (searchCooldown) {
      await checkSearchCooldown(browser, base);
      return;
    }
    if (mapFocus) {
      await checkMapFocus(browser, base);
      return;
    }
    if (dialogHistory) {
      await checkDialogHistory(browser, base);
      return;
    }
    if (mapAttribution) {
      await checkMapAttribution(browser, base);
      return;
    }
    if (projectList) {
      await checkProjectList(browser, base);
      return;
    }
    const results = [];
    for (const [profile, viewport, insets] of [
      ["phone-landscape", {width: 844, height: 390}, {top: 0, left: 47, right: 47, bottom: 21}],
      ["phone-portrait", {width: 390, height: 844}, {top: 47, left: 0, right: 0, bottom: 34}],
      ["tablet", {width: 1180, height: 820}, {top: 24, left: 0, right: 0, bottom: 20}],
    ]) results.push(...await checkViewport(browser, base, profile, viewport, insets));
    const failures = results.filter(record => record.outside.length || record.overflow);
    await fs.writeFile(path.join(output, "results.json"), JSON.stringify({baseline, results}, null, 2) + "\n");
    console.log(JSON.stringify({states: results.length, failures, rotationChecked: !baseline, output, externalRequests: 0}));
    if (!baseline) assert.deepEqual(failures, []);
  } finally {
    if (browser) await browser.close();
    if (server.listening) await new Promise(resolve => server.close(resolve));
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
