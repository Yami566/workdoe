"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const {mkdir, readFile} = require("node:fs/promises");
const {once} = require("node:events");
const http = require("node:http");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const baseline = process.argv.includes("--baseline");
const useWebkit = process.argv.includes("--webkit");
const captureBefore = process.argv.includes("--capture-before");
const previousStyles = captureBefore ? execFileSync(
  "git", ["show", "1d53b5f713abac6f9a1d2576d3eb36092f8669ad:workdoe/static/styles.css"],
  {cwd: root, windowsHide: true},
) : null;
const {
  WORKDOE_PLAYWRIGHT_MODULE, WORKDOE_CHROMIUM_EXECUTABLE,
  WORKDOE_WEBKIT_EXECUTABLE, WORKDOE_TRUST_SCREENSHOT_DIR,
} = process.env;
const executablePath = useWebkit ? WORKDOE_WEBKIT_EXECUTABLE : WORKDOE_CHROMIUM_EXECUTABLE;
assert.ok(WORKDOE_PLAYWRIGHT_MODULE && executablePath, "Use the existing pinned local browser.");
const {chromium, webkit} = require(WORKDOE_PLAYWRIGHT_MODULE);
const pages = JSON.parse(execFileSync(process.env.WORKDOE_PYTHON || "python", ["-c", [
  "import json, sys",
  "from pathlib import Path",
  "from tempfile import TemporaryDirectory",
  "from workdoe import create_app",
  "sys.path.insert(0, 'cloudflare/worker')",
  "from app_shell import privacy_page_html, safety_page_html, terms_page_html",
  "worker = {'/safety': safety_page_html(), '/privacy': privacy_page_html(), '/terms': terms_page_html()}",
  "with TemporaryDirectory() as directory:",
  "    app = create_app({'TESTING': True, 'PRODUCTION': False, 'AUTH_PROVIDER': 'local',",
  "                      'DATABASE': str(Path(directory) / 'fixture.sqlite'), 'UPLOAD_ROOT': directory,",
  "                      'TURNSTILE_SITE_KEY': '', 'TURNSTILE_SECRET_KEY': '', 'SEED_DEMO_DATA': False})",
  "    client = app.test_client()",
  "    flask = {route: client.get(route).get_data(as_text=True) for route in worker}",
  "print(json.dumps({'worker': worker, 'flask': flask}))",
].join("\n")], {cwd: root, encoding: "utf8", windowsHide: true}));

const mime = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml"};
const server = http.createServer(async (request, response) => {
  const {pathname, searchParams} = new URL(request.url, "http://127.0.0.1");
  const renderer = searchParams.get("renderer") === "flask" ? "flask" : "worker";
  if (Object.hasOwn(pages[renderer], pathname)) {
    response.writeHead(200, {"Content-Type": "text/html; charset=utf-8"}).end(pages[renderer][pathname]);
    return;
  }
  const asset = path.resolve(staticRoot, "." + pathname.replace(/^\/static\//, "/"));
  try {
    const type = mime[path.extname(asset)];
    if (!asset.startsWith(staticRoot + path.sep) || !type) throw Error("Invalid asset");
    const data = previousStyles && path.basename(asset) === "styles.css" ? previousStyles : await readFile(asset);
    response.writeHead(200, {"Content-Type": type}).end(data);
  } catch {
    response.writeHead(404).end();
  }
});

async function check(browser, base, renderer, route, width, height, scale, javaScriptEnabled) {
  const context = await browser.newContext({viewport: {width, height}, javaScriptEnabled, serviceWorkers: "block"});
  const label = [renderer, route, width + "x" + height, scale + "%", "JS", javaScriptEnabled].join(" ");
  const safetyRepro = renderer === "worker" && route === "/safety"
    && width === 320 && scale === 200 && javaScriptEnabled;
  try {
    await context.route("**/*", async request => {
      const url = new URL(request.request().url());
      if (url.origin !== base) return request.abort();
      if (scale === 100 || !url.pathname.endsWith("/styles.css")) return request.continue();
      const css = await request.fetch({maxRedirects: 0});
      return request.fulfill({response: css, body: await css.text() + "\n:root {font-size: " + scale + "% !important}\n"});
    });
    const page = await context.newPage();
    const response = await page.goto(base + route + "?renderer=" + renderer, {waitUntil: "load"});
    assert.equal(response.status(), 200, label);
    const overflow = await page.evaluate(() => {
      const {scrollWidth, clientWidth} = document.documentElement;
      return scrollWidth === clientWidth ? null : {
        scrollWidth, clientWidth,
        elements: [...document.querySelectorAll("body *")].filter(el => el.getBoundingClientRect().right > clientWidth + 1)
          .slice(0, 10).map(el => ({tag: el.tagName, class: el.className, text: el.textContent.trim().slice(0, 48)})),
      };
    });
    if (overflow && WORKDOE_TRUST_SCREENSHOT_DIR) {
      await mkdir(WORKDOE_TRUST_SCREENSHOT_DIR, {recursive: true});
      const name = ["overflow", renderer, route.slice(1), width, scale].join("-") + ".png";
      await page.screenshot({path: path.join(WORKDOE_TRUST_SCREENSHOT_DIR, name)});
    }
    assert.equal(overflow, null, label + ": " + JSON.stringify(overflow));
    // The Windows WebKit fixture does not tab to links. It still exercises
    // native Enter activation, fragment focus, and focus visibility.
    if (useWebkit) await page.getByRole("link", {name: "Skip to content", exact: true}).focus();
    else await page.keyboard.press("Tab");
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute("href")), "#main-content", label);
    await page.keyboard.press("Enter");
    const target = await page.evaluate(() => {
      const header = document.querySelector(".site-header");
      const title = document.querySelector("h1").getBoundingClientRect();
      const position = getComputedStyle(header).position;
      return {
        id: document.activeElement.id,
        top: title.top, bottom: title.bottom,
        header: position === "sticky" || position === "fixed" ? header.getBoundingClientRect().bottom : 0,
      };
    });
    assert.equal(target.id, "main-content", label);
    if (WORKDOE_TRUST_SCREENSHOT_DIR && renderer === "worker" && width === 320 && javaScriptEnabled) {
      await mkdir(WORKDOE_TRUST_SCREENSHOT_DIR, {recursive: true});
      const name = [baseline ? "before" : "after", route.slice(1), scale].join("-") + ".png";
      await page.screenshot({path: path.join(WORKDOE_TRUST_SCREENSHOT_DIR, name)});
    }
    if (baseline) {
      assert.ok(target.top < target.header - 1, label + ": expected sticky heading overlap " + JSON.stringify(target));
      return;
    }
    assert.ok(target.top >= target.header - 1 && target.bottom <= height + 1,
      label + ": heading is clipped " + JSON.stringify(target));
    if (!captureBefore && width <= 720) {
      assert.equal(await page.locator(".mobile-task-nav").evaluate(nav => getComputedStyle(nav).position),
        "static", label + ": policy navigation must not overlay the reading area");
    }
    const capture = WORKDOE_TRUST_SCREENSHOT_DIR && renderer === "worker" && scale === 100
      && javaScriptEnabled && [390, 1280].includes(width);
    if (capture) {
      await mkdir(WORKDOE_TRUST_SCREENSHOT_DIR, {recursive: true});
      await page.screenshot({path: path.join(WORKDOE_TRUST_SCREENSHOT_DIR, `${route.slice(1)}-${width}.png`)});
    }
    const links = route === "/safety" ? page.locator('a[href="#safety-contact-title"]')
      : page.getByRole("navigation", {name: "On this page", exact: true}).getByRole("link");
    const topics = await links.evaluateAll(items => items.map(link => ({
      label: link.textContent.trim(), target: link.hash.slice(1),
    })));
    const headings = await page.locator(route === "/safety" ? "#safety-contact-title" : ".legal-copy h2")
      .evaluateAll(items => items.map(heading => ({label: heading.textContent.trim(), target: heading.id})));
    assert.equal(topics.length, route === "/safety" ? 1 : 6, label);
    assert.deepEqual(topics, headings, label + ": section index does not match the document");
    if (useWebkit) await links.first().focus();
    else await page.keyboard.press("Tab");
    assert.equal(await page.evaluate(() => document.activeElement.hash), "#" + topics[0].target, label);
    const supportTargets = {"/safety": "safety-contact-title", "/privacy": "privacy-choices", "/terms": "terms-questions"};
    const visibleFocus = () => page.evaluate(() => {
      const active = document.activeElement;
      const rect = active.getBoundingClientRect();
      const header = document.querySelector(".site-header");
      const dock = document.querySelector(".mobile-task-nav");
      const visibleStart = ["sticky", "fixed"].includes(getComputedStyle(header).position)
        ? header.getBoundingClientRect().bottom : 0;
      const visibleEnd = dock && getComputedStyle(dock).position === "fixed" && getComputedStyle(dock).display !== "none"
        ? dock.getBoundingClientRect().top : innerHeight;
      return {id: active.id, hash: location.hash, href: active.getAttribute("href"),
        top: rect.top, bottom: rect.bottom, visibleStart, visibleEnd};
    });
    for (const [index, topic] of topics.entries()) {
      await links.nth(index).press("Enter");
      const focus = await visibleFocus();
      assert.equal(focus.hash, "#" + topic.target, label);
      assert.equal(focus.id, topic.target, label + ": fragment did not move focus");
      assert.ok(focus.top >= focus.visibleStart - 1 && focus.bottom <= focus.visibleEnd + 1,
        label + ": focused heading is clipped " + JSON.stringify(focus));
      if (capture && width === 390 && ["safety-contact-title", "privacy-choices", "terms-prohibited-work"].includes(topic.target)) {
        await page.screenshot({path: path.join(WORKDOE_TRUST_SCREENSHOT_DIR, `${topic.target}-390.png`)});
      }
      if (topic.target === supportTargets[route]) {
        const contactLink = page.locator("#" + topic.target).locator("..")
          .getByRole("link", {name: "admin@workdoe.com", exact: true});
        if (useWebkit) {
          await contactLink.focus();
        } else {
          await page.keyboard.press("Tab");
        }
        let contact = await visibleFocus();
        assert.equal(contact.href, "mailto:admin@workdoe.com", label);
        if (useWebkit && !captureBefore) {
          if (safetyRepro) {
            assert.ok(contact.top < contact.visibleEnd && contact.bottom > contact.visibleStart,
              label + ": the Safety contact is still fully hidden " + JSON.stringify(contact));
          }
          // Programmatic focus in this browser does not reliably scroll.
          // Verify that scrolling can reveal the link without moving focus.
          await contactLink.scrollIntoViewIfNeeded();
          contact = await visibleFocus();
          assert.equal(contact.href, "mailto:admin@workdoe.com", label);
        }
        if (WORKDOE_TRUST_SCREENSHOT_DIR && renderer === "worker" && width === 320
            && scale === 200 && javaScriptEnabled) {
          await page.screenshot({path: path.join(WORKDOE_TRUST_SCREENSHOT_DIR,
            `${route.slice(1)}-320-contact-200.png`)});
        }
        if (captureBefore) {
          assert.ok(contact.top >= contact.visibleEnd, label + ": expected contact behind dock");
          return;
        }
        assert.ok(contact.top >= contact.visibleStart - 1 && contact.bottom <= contact.visibleEnd + 1,
          label + ": support link is clipped " + JSON.stringify(contact));
      }
    }
    const footer = page.getByRole("navigation", {name: "Policies", exact: true});
    for (const policy of ["Safety", "Privacy", "Terms"]) {
      const link = footer.getByRole("link", {name: policy, exact: true});
      await link.scrollIntoViewIfNeeded();
      await link.focus();
      const focus = await visibleFocus();
      assert.ok(focus.href && focus.top < focus.visibleEnd && focus.bottom > focus.visibleStart,
        label + ": focused footer link is hidden " + JSON.stringify(focus));
    }
  } finally {
    await context.close();
  }
}

async function run() {
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const base = "http://127.0.0.1:" + server.address().port;
  const browser = useWebkit ? await webkit.launch({executablePath, headless: true})
    : await chromium.launch({executablePath, headless: true, chromiumSandbox: true});
  let count = 0;
  try {
    if (captureBefore) {
      assert.ok(useWebkit, "The before case targets the Windows WebKit reproduction.");
      await check(browser, base, "worker", "/safety", 320, 568, 200, true);
      console.log("Reproduced the obscured policy contact in WebKit.");
      return;
    }
    for (const renderer of baseline ? ["worker"] : ["worker", "flask"]) {
      for (const route of baseline ? ["/privacy", "/terms"] : ["/safety", "/privacy", "/terms"]) {
        for (const [width, height] of baseline ? [[320, 568]] : [
          [320, 568], [390, 844], [844, 390], [820, 1180], [1280, 720],
        ]) {
          for (const [scale, javaScriptEnabled] of baseline ? [[100, true]] : [[100, true], [200, true], [200, false]]) {
            await check(browser, base, renderer, route, width, height, scale, javaScriptEnabled);
            count++;
          }
        }
      }
    }
    console.log((baseline ? "Reproduced " : "Passed ") + count +
      " public policy " + (useWebkit ? "fragment and reflow cases in WebKit."
        : "keyboard and reflow cases in Chromium."));
  } finally {
    await browser.close();
  }
}

run().catch(error => { console.error(error); process.exitCode = 1; }).finally(() => server.close());
