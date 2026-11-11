"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const {mkdir, readFile} = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");

const root = path.resolve(__dirname, "../..");
const staticRoot = path.join(root, "workdoe/static");
const oldNotices = "/vendor/clerk-notices/";
const newNotices = "/vendor/clerk-notices-v2/";
const noticeIndex = newNotices + "notices-1";
const addedNotices = ["core-js-3.47.0-license.txt", "crypto-js-4.2.0-license.txt",
  "floating-ui-react-0.27.20-license.txt", "emotion-license.txt"];
const noticeFiles = ["apache-2.0-license.txt", "base-account-2.0.1-license.txt",
  "browser-tabs-lock-1.3.0-license.txt", "coinbase-wallet-4.3.7-license.txt", "react-18.3.1-license.txt",
  "tanstack-query-core-5.102.8-license.txt", "formkit-auto-animate-0.8.4-license.txt",
  "stripe-sdk-license.txt", "zxcvbn-ts-3.0.4-license.txt", "coinbase-eip712-isc-license.txt",
  "input-otp-1.4.2-license.txt", "copy-to-clipboard-3.3.3-license.txt",
  "qrcode-react-4.2.0-license.txt", "qrcode-generator-license.txt",
  ...addedNotices];
const {WORKDOE_PLAYWRIGHT_MODULE, WORKDOE_CHROMIUM_EXECUTABLE} = process.env;
const useWebKit = process.argv.includes("--webkit");
assert.ok(WORKDOE_PLAYWRIGHT_MODULE && (useWebKit || WORKDOE_CHROMIUM_EXECUTABLE),
  "Set the existing Playwright module and, for Chromium, its executable; this check installs nothing.");
const {chromium, webkit} = require(WORKDOE_PLAYWRIGHT_MODULE);
const pages = JSON.parse(execFileSync("python", ["-c", `
import json, sys
from pathlib import Path
from tempfile import TemporaryDirectory
from workdoe import create_app
sys.path.insert(0, "cloudflare/worker")
from app_shell import terms_page_html
worker = {"/terms": terms_page_html()}
with TemporaryDirectory() as directory:
    app = create_app({"TESTING": True, "PRODUCTION": False, "AUTH_PROVIDER": "local",
                      "DATABASE": str(Path(directory) / "fixture.sqlite"), "UPLOAD_ROOT": directory,
                      "TURNSTILE_SITE_KEY": "", "TURNSTILE_SECRET_KEY": "", "SEED_DEMO_DATA": False})
    client = app.test_client()
    flask = {route: client.get(route).get_data(as_text=True) for route in worker}
print(json.dumps({"worker": worker, "flask": flask}))
`], {cwd: root, encoding: "utf8", windowsHide: true}));
const mime = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml",
  ".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8"};
const oldNoticeHits = new Map();
let noticeReleaseActivated = true;

const server = http.createServer(async (request, response) => {
  const {pathname, searchParams} = new URL(request.url, "http://127.0.0.1");
  const renderer = searchParams.get("renderer") === "flask" ? "flask" : "worker";
  if (Object.hasOwn(pages[renderer], pathname)) {
    response.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
    response.end(pages[renderer][pathname]);
    return;
  }
  if (pathname.startsWith(oldNotices)) {
    oldNoticeHits.set(pathname, (oldNoticeHits.get(pathname) || 0) + 1);
    response.writeHead(404, {"Cache-Control": noticeReleaseActivated ? "no-store" : "public, max-age=31556952, immutable"});
    response.end();
    return;
  }
  if (!noticeReleaseActivated && addedNotices.some(file => pathname === newNotices + file)) {
    response.writeHead(404, {"Cache-Control": "no-store"}).end();
    return;
  }
  const assetPath = pathname === noticeIndex ? pathname + ".html" : pathname;
  const asset = path.resolve(staticRoot, "." + assetPath.replace(/^\/static\//, "/"));
  try {
    if (!asset.startsWith(staticRoot + path.sep)) throw new Error("Outside fixture assets");
    const bytes = await readFile(asset);
    response.writeHead(200, {"Content-Type": mime[path.extname(asset)] || "application/octet-stream"});
    response.end(bytes);
  } catch {
    response.writeHead(404).end();
  }
});

async function checkNotices(browser, base, renderer, viewport) {
  const context = await browser.newContext({viewport, javaScriptEnabled: false, serviceWorkers: "block"});
  try {
    await context.route("**/*", request => new URL(request.request().url()).origin === base
      ? request.continue() : request.abort());
    const page = await context.newPage();
    await page.goto(`${base}/terms?renderer=${renderer}`, {waitUntil: "load"});
    await page.getByRole("link", {name: "Software notices", exact: true}).press("Enter");
    await page.getByRole("heading", {name: "Sign-in software notices", exact: true}).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const links = await page.locator('main a[href$=".txt"]').evaluateAll(items => items.map(link => ({
      url: link.href, decoration: getComputedStyle(link).textDecorationLine,
    })));
    const noticeBase = base + (renderer === "flask" ? "/static" : "") + newNotices;
    assert.deepEqual(links.map(({url}) => url).sort(), noticeFiles.map(file => noticeBase + file).sort());
    for (const {url: link, decoration} of links) {
      assert.match(decoration, /\bunderline\b/);
      const response = await page.request.get(link, {maxRedirects: 0});
      assert.equal(response.status(), 200);
      assert.match(response.headers()["content-type"], /^text\/plain/);
      const bytes = await readFile(path.join(staticRoot, newNotices.slice(1), path.basename(new URL(link).pathname)));
      assert.deepEqual(await response.body(), bytes);
    }
    const evidenceDir = process.env.WORKDOE_TRUST_PAGE_SCREENSHOT_DIR;
    if (evidenceDir && renderer === "worker") {
      await mkdir(evidenceDir, {recursive: true});
      await page.screenshot({path: path.join(evidenceDir, `software-notices-${viewport.width}x${viewport.height}.png`)});
    }
  } finally {
    await context.close();
  }
}

async function checkKeyboardFooter(browser, base) {
  const context = await browser.newContext({viewport: {width: 320, height: 568}, serviceWorkers: "block"});
  try {
    const page = await context.newPage();
    await page.goto(base + "/terms");
    await page.locator('a[href="#main-content"]').press("Enter");
    const labels = [];
    for (let step = 0; step < 20 && labels.length < 4; step++) {
      await page.keyboard.press("Tab");
      const focused = await page.evaluate(() => {
        const active = document.activeElement;
        if (!active.closest(".site-footer-links")) return null;
        const link = active.getBoundingClientRect();
        const nav = document.querySelector(".mobile-task-nav").getBoundingClientRect();
        return {label: active.textContent.trim(), bottom: link.bottom, limit: nav.top};
      });
      if (!focused) continue;
      assert.ok(focused.bottom <= focused.limit + 1,
        `${focused.label} focus ends at ${focused.bottom}, beneath navigation at ${focused.limit}`);
      labels.push(focused.label);
    }
    assert.deepEqual(labels, ["Safety", "Privacy", "Terms", "Software notices"]);
  } finally {
    await context.close();
  }
}

async function checkWarmNoticeNavigation(browser, base) {
  // Playwright routing disables HTTP caching, so this loopback-only fixture uses ordinary requests.
  const context = await browser.newContext({serviceWorkers: "block"});
  const oldPaths = ["notices-1", ...noticeFiles].map(file => oldNotices + file);
  try {
    const page = await context.newPage();
    await page.goto(base + "/terms");
    noticeReleaseActivated = false;
    const statuses = paths => page.evaluate(
      async entries => Promise.all(entries.map(async item => (await fetch(item)).status)), paths);
    assert.deepEqual(await statuses(oldPaths), oldPaths.map(() => 404));
    assert.deepEqual(await statuses(addedNotices.map(file => newNotices + file)), addedNotices.map(() => 404));
    noticeReleaseActivated = true;
    assert.deepEqual(await statuses(oldPaths), oldPaths.map(() => 404));
    for (const oldPath of oldPaths) assert.equal(oldNoticeHits.get(oldPath), 1, oldPath);
    await page.getByRole("link", {name: "Software notices", exact: true}).press("Enter");
    await page.getByRole("heading", {name: "Sign-in software notices", exact: true}).waitFor();
    assert.equal(new URL(page.url()).pathname, noticeIndex);
    const links = await page.locator('main a[href$=".txt"]').evaluateAll(items => items.map(item => item.pathname));
    assert.deepEqual(links.sort(), noticeFiles.map(file => newNotices + file).sort());
    assert.deepEqual(await statuses(links), links.map(() => 200));
  } finally {
    noticeReleaseActivated = true;
    await context.close();
  }
}

async function main() {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = useWebKit ? await webkit.launch({headless: true})
      : await chromium.launch({executablePath: WORKDOE_CHROMIUM_EXECUTABLE, headless: true});
    for (const [width, height] of [[320, 568], [390, 844], [820, 1180], [1280, 720]]) {
      for (const renderer of ["worker", "flask"]) {
        await checkNotices(browser, base, renderer, {width, height});
      }
    }
    console.log("8 no-JavaScript software notice navigation and reflow cases passed.");
    if (!useWebKit) {
      await checkKeyboardFooter(browser, base);
      console.log("All four Terms footer keyboard targets clear the mobile navigation.");
      await checkWarmNoticeNavigation(browser, base);
      console.log(`Warm Chromium cache: Terms and all ${noticeFiles.length} notices load despite cached legacy misses.`);
    }
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
