"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const {createHash} = require("node:crypto");
const {mkdir, readFile} = require("node:fs/promises");
const http = require("node:http");
const {once} = require("node:events");
const path = require("node:path");
const {chromium, webkit} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);

const root = path.resolve(__dirname, "../..");
const assets = path.join(root, "workdoe/static");
const publicSdk = process.argv.includes("--public-sdk");
const baseline = process.argv.includes("--baseline");
const useWebKit = process.argv.includes("--webkit");
const entryLayout = process.argv.includes("--entry-layout");
const entryAccessibility = process.argv.includes("--entry-accessibility");
const flaskFragments = process.argv.includes("--flask-fragments");
const browserEnv = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
  /^(SystemRoot|WINDIR|COMSPEC|PATH|PATHEXT|TEMP|TMP|USERPROFILE|APPDATA|LOCALAPPDATA|ProgramFiles|PROGRAMDATA|HOMEDRIVE|HOMEPATH)$/i.test(key)));
assert.ok(!publicSdk || process.env.WORKDOE_APPROVED_ANONYMOUS_UI_TEST === "1",
  "The public SDK check requires explicit anonymous UI-test approval.");
assert.ok(!publicSdk || !useWebKit, "The bounded public probe uses Chromium only.");
const {documents, pins, flask_documents: flaskDocuments, context_document: contextDocument} = JSON.parse(execFileSync(process.env.WORKDOE_PYTHON || "python",
  ["tests/test_clerk_entry_integrity.py"], {cwd: root, encoding: "utf8", windowsHide: true,
    env: {...process.env, PYTHONPATH: root}}));
const candidate = baseline ? execFileSync("git", ["show", "47f558f:workdoe/static/clerk-entry.js"],
  {cwd: root, encoding: "utf8", windowsHide: true}) : null;

// This loopback-only shim models the documented router hooks, not authentication.
const shim = `
  (function () {
  if (window.Clerk) return;
  window.__internal_ClerkUICtor = function FixtureUi() {};
  let navigation;
  window.Clerk = {
    isSignedIn: false, unmounts: 0,
    load(options) { navigation ||= options; return Promise.resolve(); },
    addListener() { return () => {}; },
    mountSignIn(node, props) { mount(node, 'Sign in', 'Sign up', props.signUpUrl); },
    mountSignUp(node, props) { mount(node, 'Create your account', 'Sign in', props.signInUrl); },
    unmountSignIn() { this.unmounts++; }, unmountSignUp() { this.unmounts++; }
  };
  function mount(node, title, action, destination) {
    const heading = document.createElement('h1'); heading.textContent = title;
    const label = document.createElement('label'); label.textContent = 'Email address';
    const field = document.createElement('input'); field.type = 'email'; label.append(field);
    field.className = 'cl-formFieldInput';
    const link = document.createElement('a'); link.textContent = action; link.href = destination;
    link.addEventListener('click', event => {
      event.preventDefault();
      navigation.routerPush ? navigation.routerPush(link.href, {windowNavigate: to => location.assign(to)})
        : location.assign(link.href);
    });
    node.append(heading, label, link);
  }
  })();
`;
const fixtureSri = "sha384-" + createHash("sha384").update(shim).digest("base64");
const types = {".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml",
  ".webp": "image/webp", ".png": "image/png", ".geojson": "application/geo+json"};
const output = path.join(root, ".test-tmp/clerk-dialog-routing",
  entryAccessibility ? (publicSdk ? "public" : useWebKit ? "webkit" : "chromium") + "-accessibility" +
    (flaskFragments ? "-flask" : "") :
  publicSdk ? entryLayout ? "public-layout" : baseline ? "public-baseline" : "public-candidate"
    : (useWebKit ? "webkit" : "chromium") + (entryLayout ? "-layout" : "") + (flaskFragments ? "-flask" : ""));

async function inspectEntryKeyboard(page, surface, stage, width, direct) {
  const email = surface.getByRole("textbox", {name: "Email address", exact: true});
  const candidates = await surface.locator('a[href], button, input, select, textarea, [tabindex]').elementHandles();
  const controls = [];
  for (const node of candidates) {
    if (await node.isVisible() && await node.isEnabled() && await node.evaluate(element =>
      element.tabIndex >= 0 && !element.closest('[inert]'))) controls.push(node);
  }
  assert.ok(controls.length > 1);
  await controls[0].focus();
  const unfocused = await email.evaluate(element => {
    const style = getComputedStyle(element), ancestors = [];
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d');
    const color = value => {
      context.clearRect(0, 0, 1, 1); context.fillStyle = value; context.fillRect(0, 0, 1, 1);
      return [...context.getImageData(0, 0, 1, 1).data];
    };
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      ancestors.push(getComputedStyle(parent).backgroundColor);
    }
    return {border: style.borderTopColor, borderWidth: style.borderTopWidth, borderStyle: style.borderTopStyle,
      background: style.backgroundColor, shadow: style.boxShadow, outline: style.outline,
      opacity: style.opacity, ancestors, borderRgba: color(style.borderTopColor),
      outerRgba: ancestors.map(color).find(channels => channels[3] === 255)};
  });
  await page.screenshot({path: path.join(output, stage + "-" + width + (direct ? "-direct" : "") + ".png")});
  const active = () => page.evaluate(() => {
    const element = document.activeElement;
    return {tag: element.tagName, type: element.getAttribute('type'), id: element.id,
      inDialog: Boolean(element.closest('dialog[open]'))};
  });
  await controls[controls.length - 1].focus();
  await page.keyboard.press('Tab');
  const forward = await active();
  const forwardMatches = await controls[0].evaluate(element => element === document.activeElement);
  await controls[0].focus();
  await page.keyboard.press('Shift+Tab');
  const backward = await active();
  const backwardMatches = await controls[controls.length - 1].evaluate(element => element === document.activeElement);
  await email.focus();
  const focused = await email.evaluate(element => {
    const style = getComputedStyle(element);
    return {border: style.borderTopColor, shadow: style.boxShadow, outline: style.outline};
  });
  const luminance = channels => channels.slice(0, 3).map(channel => channel / 255)
    .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    .reduce((value, channel, index) => value + channel * [0.2126, 0.7152, 0.0722][index], 0);
  assert.equal(unfocused.opacity, '1');
  assert.equal(unfocused.borderRgba[3], 255, 'The reviewed field boundary must be opaque.');
  assert.ok(unfocused.outerRgba, 'A known opaque adjacent background is required.');
  const light = Math.max(luminance(unfocused.borderRgba), luminance(unfocused.outerRgba));
  const dark = Math.min(luminance(unfocused.borderRgba), luminance(unfocused.outerRgba));
  const contrast = (light + 0.05) / (dark + 0.05);
  assert.ok(parseFloat(unfocused.borderWidth) >= 1 && contrast >= 3,
    'The email field must retain its reviewed visible boundary.');
  if (!direct) {
    assert.ok(forward.inDialog && forwardMatches, 'Tab from the last control must wrap to the first.');
    assert.ok(backward.inDialog && backwardMatches, 'Shift+Tab from the first control must wrap to the last.');
    await controls[0].focus();
    const sequence = [];
    for (const key of ['Tab', 'Shift+Tab']) {
      for (let index = 0; index < controls.length; index++) {
        await page.keyboard.press(key);
        const current = await active();
        sequence.push({key, index, ...current});
        if (!current.inDialog) console.error(JSON.stringify({sequence, controls: await Promise.all(controls.map(
          node => node.evaluate(element => ({tag: element.tagName, type: element.getAttribute('type'),
            id: element.id, className: element.className, tabIndex: element.tabIndex}))))}));
        assert.ok(current.inDialog, 'The sampled empty-form tab sequence must stay in the modal.');
      }
    }
  }
  if (publicSdk && stage === 'signup') {
    const checkbox = surface.getByRole('checkbox');
    assert.equal(await checkbox.isChecked(), false, 'The test must not accept policies.');
    const size = await checkbox.boundingBox();
    assert.equal(size.width, 18);
    assert.equal(size.height, 18);
  }
  process.stdout.write(JSON.stringify({stage, width, direct, controls: controls.length, contrast,
    border: unfocused.border, outline: focused.outline, forward, backward, forwardMatches, backwardMatches}) + "\n");
}

function documentFor(url) {
  const key = url.pathname + (url.searchParams.get("embed") === "1" ? "?embed=1" : "");
  const doc = flaskFragments && flaskDocuments[key] ||
    entryLayout && key === "/create-account?embed=1" && contextDocument || documents[key];
  if (!doc) return null;
  return {...doc, html: Object.values(pins).reduce((html, pin) =>
    html.replaceAll(pin.script_integrity, fixtureSri), doc.html)};
}

async function verify(browser, base, width, height, failSwitch = false, direct = false) {
  const context = await browser.newContext({viewport: {width, height}, serviceWorkers: "block"});
  const prohibited = [], documentsRequested = [], verifiedScripts = [], scriptReads = [], scriptErrors = [];
  let tileRequests = 0, failNext = failSwitch;
  await context.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url());
    if (!["GET", "HEAD"].includes(request.method())) {
      prohibited.push(request.method()); return route.abort();
    }
    if (url.origin !== base) {
      if (publicSdk && url.origin === "https://tile.openstreetmap.org" &&
          request.resourceType() === "image" && ++tileRequests <= 32) return route.continue();
      if (!publicSdk) prohibited.push("external request: " + url.origin);
      return route.abort();
    }
    if (request.isNavigationRequest()) documentsRequested.push(url.pathname);
    if (url.pathname === "/clerk-entry.js") {
      return route.fulfill({contentType: "text/javascript", body: candidate || await readFile(path.join(assets, "clerk-entry.js"))});
    }
    if (publicSdk && entryLayout && url.pathname === "/styles.css") {
      return route.fulfill({contentType: "text/css", body: await readFile(path.join(assets, "styles.css"))});
    }
    if (publicSdk && entryAccessibility && url.pathname === "/site-dialogs.js") {
      return route.fulfill({contentType: "text/javascript", body: await readFile(path.join(assets, "site-dialogs.js"))});
    }
    if (publicSdk) {
      if (url.pathname.startsWith("/api/") && url.pathname !== "/api/jobs/open") return route.abort();
      return route.continue();
    }
    if (Object.values(pins).some(pin => url.pathname === "/__clerk" + pin.script_path)) {
      return route.fulfill({contentType: "text/javascript", body: shim});
    }
    if (failNext && url.pathname === "/create-account" && url.searchParams.get("embed") === "1") {
      failNext = false;
      return route.fulfill({status: 503, contentType: "text/html", body: "Unavailable"});
    }
    const doc = documentFor(url);
    if (doc) return route.fulfill({contentType: "text/html", headers: {"Content-Security-Policy": doc.csp}, body: doc.html});
    if (url.pathname === "/api/jobs/open") return route.fulfill({status: 503, json: {ok: false}});
    const assetPath = url.pathname.startsWith("/static/") ? url.pathname.slice(7) : url.pathname;
    const asset = path.resolve(assets, "." + assetPath), type = types[path.extname(asset)];
    if (type && asset.startsWith(assets + path.sep)) {
      try { return await route.fulfill({contentType: type, body: await readFile(asset)}); }
      catch (error) { if (error.code !== "ENOENT") throw error; }
    }
    return route.fulfill({status: 404});
  });
  try {
    const page = await context.newPage();
    page.setDefaultTimeout(publicSdk ? 20000 : 8000);
    if (publicSdk) page.on("response", response => {
      const pathname = new URL(response.url()).pathname;
      const pin = Object.values(pins).find(item => pathname === "/__clerk" + item.script_path);
      if (!pin) return;
      scriptReads.push((async () => {
        assert.equal(response.status(), 200);
        const bytes = await response.body();
        assert.ok(bytes.length > 0 && bytes.length < 8 * 1024 * 1024);
        assert.equal("sha384-" + createHash("sha384").update(bytes).digest("base64"), pin.script_integrity);
        verifiedScripts.push(pin.script_path);
      })().catch(error => { scriptErrors.push(error.message); }));
    });
    await page.goto(base + (direct ? "/login" : "/"), {waitUntil: "domcontentloaded"});
    if (!direct) await page.locator("#lead-map .leaflet-marker-icon, #lead-map .leaflet-overlay-pane path").first().waitFor();
    if (entryLayout && !publicSdk && !direct) {
      await page.waitForLoadState("networkidle");
      if (width <= 820) await page.getByRole("tab", {name: "Projects", exact: true}).click();
      const first = page.locator("[data-project-results] a").first();
      const box = await first.boundingBox();
      const panel = await page.locator("#market-projects-panel").boundingBox();
      const footer = await page.locator(".market-policy-footer").boundingBox();
      const families = await page.locator(".service-family-filter-link").evaluateAll(links => links.map(link => {
        const box = link.getBoundingClientRect();
        const label = link.querySelector("strong").getBoundingClientRect();
        return {height: box.height, labelFits: label.left >= box.left && label.right <= box.right
          && label.top >= box.top && label.bottom <= box.bottom};
      }));
      assert.equal(families.length, 7);
      assert.ok(families.every(family => family.height >= 44 && family.labelFits));
      await page.screenshot({path: path.join(output, "projects-" + width + ".png")});
      process.stdout.write(JSON.stringify({viewport: width, firstResult: box, panelBottom: panel.y + panel.height,
        footerTop: footer.y}) + "\n");
      assert.ok(box.y >= panel.y && box.y + box.height <= Math.min(footer.y, panel.y + panel.height),
        "A complete project result must fit above the footer without scrolling.");
    }
    const initialUrl = page.url();
    await page.evaluate(() => { window.workdoeRoutingDocument = "synthetic-review-marker"; });
    if (!publicSdk) await page.evaluate(() => {
      window.workdoeSelectionEvents = [];
      for (const type of ['focusin', 'pointermove']) document.addEventListener(type, event => {
        const row = event.target.closest && event.target.closest('.project-result');
        if (row) window.workdoeSelectionEvents.push({type, id: row.dataset.jobId,
          x: event.clientX, y: event.clientY, dx: event.movementX, dy: event.movementY,
          modal: Boolean(document.querySelector('dialog[open]')), phase: window.workdoeRoutingPhase});
      });
    });
    const initialHistory = await page.evaluate(() => history.length);
    const trigger = page.getByRole("navigation", {name: "Primary", exact: true})
      .getByRole("link", {name: "Sign in", exact: true});
    if (!direct) await trigger.click();
    const surface = direct ? page : page.getByRole("dialog");
    const entry = surface.locator("[data-clerk-entry]");
    await entry.getByRole("textbox", {name: "Email address", exact: true}).waitFor();
    assert.equal(await page.evaluate(() => window.Clerk.isSignedIn), false);
    assert.equal(await entry.getByRole("textbox").first().inputValue(), "");
    if (entryLayout) {
      const heading = surface.locator(".market-auth-heading > h2, .clerk-entry-panel > div:first-child > h1");
      await page.screenshot({path: path.join(output, "signin-" + width + (direct ? "-direct" : "") + ".png")});
      assert.equal(await heading.isVisible(), direct, "Only dialog fragments should omit the redundant heading.");
      assert.equal(await entry.getByRole("heading").isVisible(), true, "Provider instructions must remain visible.");
      if (!direct && !flaskFragments) assert.equal(await surface.getByRole("complementary", {name: "Sign in", exact: true}).count(), 1);
    }
    if (entryAccessibility) await inspectEntryKeyboard(page, surface, 'signin', width, direct);
    const beforeSwitch = documentsRequested.length;
    await entry.getByRole("link", {name: "Sign up", exact: true}).click();
    if (direct) {
      await page.waitForURL(url => url.pathname === "/create-account");
      await page.locator("[data-clerk-entry]").getByRole("textbox", {name: "Email address", exact: true}).waitFor();
      assert.equal(await page.locator("dialog[open]").count(), 0);
      assert.equal(await page.evaluate(() => window.workdoeRoutingDocument), undefined);
    } else {
      if (failSwitch) {
        await surface.getByRole("button", {name: "Try again", exact: true}).click();
      }
      await surface.locator('[data-clerk-mode="start"]').getByRole("textbox", {name: "Email address", exact: true}).waitFor();
      if (entryLayout) {
        const ownHeading = surface.locator(".market-auth-heading > h2, .clerk-entry-panel > div:first-child > h2");
        assert.equal(await ownHeading.isVisible(), false);
        assert.equal(await surface.getByRole("group", {name: "What brings you here?", exact: true}).isVisible(), true);
        if (!publicSdk && !flaskFragments) {
          assert.equal(await surface.locator(".selected-lead-pill").count(), 2);
          for (const note of await surface.locator(".selected-lead-pill").all()) assert.equal(await note.isVisible(), true);
        }
        if (publicSdk) assert.equal(await surface.getByRole("checkbox").isChecked(), false);
      }
      assert.equal(await page.evaluate(() => window.workdoeRoutingDocument), "synthetic-review-marker");
      assert.equal(documentsRequested.length, beforeSwitch, "switch must not replace the document");
      assert.equal(await page.evaluate(() => history.length), initialHistory + 1);
      assert.equal(new URL(page.url()).pathname, "/create-account");
      assert.ok(await surface.evaluate(dialog => dialog.contains(document.activeElement)));
      await page.screenshot({path: path.join(output, "signup-" + width + (failSwitch ? "-retry" : "") + ".png")});
      if (entryAccessibility) await inspectEntryKeyboard(page, surface, 'signup', width, direct);
      await surface.locator("[data-clerk-entry]").getByRole("link", {name: "Sign in", exact: true}).click();
      await surface.locator('[data-clerk-mode="signin"]').getByRole("textbox", {name: "Email address", exact: true}).waitFor();
      assert.equal(documentsRequested.length, beforeSwitch);
      assert.equal(await page.evaluate(() => history.length), initialHistory + 1);
      await page.keyboard.press("Escape");
      await surface.waitFor({state: "hidden"});
      try {
        await page.waitForURL(initialUrl);
      } catch (error) {
        const safe = value => {
          const url = new URL(value);
          return {path: url.pathname, selected: url.searchParams.get("job_id"),
            filters: ["family", "service", "q", "sort"].map(key => [key, url.searchParams.get(key)])};
        };
        console.error(JSON.stringify({expected: safe(initialUrl), observed: safe(page.url())}));
        await page.screenshot({path: path.join(output, "close-failure-" + width + ".png")});
        throw error;
      }
      assert.ok(await trigger.evaluate(link => link === document.activeElement));
      await trigger.click();
      await surface.locator("[data-clerk-entry]").getByRole("textbox", {name: "Email address", exact: true}).waitFor();
      await page.evaluate(() => { window.workdoeRoutingPhase = 'back'; });
      await page.goBack();
      await surface.waitFor({state: "hidden"});
      if (page.url() !== initialUrl) {
        console.error(JSON.stringify(await page.evaluate(() => ({selectionEvents: window.workdoeSelectionEvents,
          selected: new URL(location.href).searchParams.get('job_id'), active: document.activeElement.tagName}))));
        await page.screenshot({path: path.join(output, 'back-failure-' + width + '.png')});
      }
      assert.equal(page.url(), initialUrl);
      assert.equal(await page.evaluate(() => window.workdoeRoutingDocument), "synthetic-review-marker");
      if (entryAccessibility) await page.screenshot({path: path.join(output, 'closed-' + width + '.png')});
      if (entryLayout && !publicSdk) {
        const preview = page.locator('.project-result[data-job-id="demo-03"]');
        await preview.scrollIntoViewIfNeeded();
        await preview.dispatchEvent("mouseenter");
        await preview.dispatchEvent("pointermove", {pointerType: "touch"});
        assert.equal(page.url(), initialUrl, "layout entry and touch scrolling must not select a different project");
        await page.mouse.move(0, 0);
        await preview.hover();
        await page.waitForURL(url => url.searchParams.get("job_id") === "demo-03");
        await page.locator('.project-result[data-job-id="demo-02"]').focus();
        await page.waitForURL(url => url.searchParams.get("job_id") === "demo-02");
      }
    }
    await Promise.all(scriptReads);
    assert.deepEqual(scriptErrors, []);
    if (publicSdk) {
      assert.equal(await page.evaluate(() => window.Clerk.version), "6.40.1");
      assert.equal(new Set(verifiedScripts).size, 2, "both actual provider entry scripts must match reviewed pins");
    }
    assert.deepEqual(prohibited, [], "this check must not submit any data or contact external fixture services");
    process.stdout.write(`PASS: ${publicSdk ? "actual anonymous SDK + local script overlay" : "synthetic router"}, ` +
      `${width}x${height}, ${direct ? "direct fallback" : failSwitch ? "dialog retry" : "dialog switch/close/back"}` +
      `${entryLayout ? ", layout" : ""}${flaskFragments ? ", Flask auth fragments" : ""}\n`);
  } finally {
    await Promise.allSettled(scriptReads);
    await context.close();
  }
}

async function main() {
  await mkdir(output, {recursive: true});
  const server = publicSdk ? null : http.createServer((_, response) => response.writeHead(404).end());
  if (server) { server.listen(0, "127.0.0.1"); await once(server, "listening"); }
  const base = publicSdk ? "https://workdoe.com" : "http://127.0.0.1:" + server.address().port;
  let browser;
  try {
    browser = await (useWebKit ? webkit : chromium).launch({env: browserEnv,
      ...(!useWebKit ? {executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE} : {})});
    for (const [width, height] of publicSdk ? [[390, 844]] : [[390, 844], [820, 1180], [1280, 720]]) {
      await verify(browser, base, width, height);
      if (!publicSdk) await verify(browser, base, width, height, true);
    }
    if (!publicSdk) await verify(browser, base, 390, 844, false, true);
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
