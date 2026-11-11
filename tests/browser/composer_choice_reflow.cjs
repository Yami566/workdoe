"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const useWebkit = process.argv.includes("--webkit");
const keyboardEntry = process.argv.includes("--keyboard-entry");
const captureBefore = process.argv.includes("--capture-before");
const {chromium, webkit} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);
const root = path.resolve(__dirname, "../..");
const assets = path.join(root, "workdoe/static");
const output = path.join(root, ".test-tmp", keyboardEntry
  ? `composer-enter-${captureBefore ? "before" : "after"}${useWebkit ? "-webkit" : ""}`
  : "composer-choice-audit");
const origin = "https://workdoe-test.invalid";
const mime = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"};
const pages = JSON.parse(execFileSync("python", ["-c", `
import json
import sys
sys.path.insert(0, 'cloudflare/worker')
from app_shell import job_form_html, layout, public_job_draft_html
start = layout(None, '/', 'Local fixture',
               '<main><a href="/post-project" data-dialog-title="Post a project">Post project</a></main>')
print(json.dumps({
    '/': start,
    '/post-project?embed=1': public_job_draft_html(embedded=True),
    '/post-project': public_job_draft_html(),
    '/jobs/new': job_form_html({'id': 1, 'role': 'client', 'display_name': 'Fixture'}, media_uploads_enabled=False),
}))
`], {cwd: root, encoding: "utf8", windowsHide: true}));

function useFixtures(context) {
  return context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin || route.request().method() !== "GET") return route.abort();
    const html = pages[url.pathname + url.search];
    if (html) return route.fulfill({contentType: "text/html", body: html});
    const file = path.resolve(assets, "." + url.pathname);
    if (!file.startsWith(assets + path.sep) || !fs.existsSync(file)) return route.fulfill({status: 404});
    return route.fulfill({path: file, contentType: mime[path.extname(file)] || "application/octet-stream"});
  });
}

async function check(browser, width, height, scale) {
  const context = await browser.newContext({viewport: {width, height}, serviceWorkers: "block"});
  try {
    await context.addInitScript(textScale => document.addEventListener("DOMContentLoaded", () => {
      document.documentElement.style.fontSize = textScale + "%";
    }), scale);
    await useFixtures(context);
    const page = await context.newPage();
    await page.goto(origin + "/");
    await page.locator("main").getByRole("link", {name: "Post project", exact: true}).click();
    const form = page.getByRole("dialog").locator("[data-project-composer].is-enhanced");
    await form.waitFor();
    for (const [index, selection] of [[1, "service-family-cleaning-upkeep"], [2, "service-choice-house-cleaning"]]) {
      const step = form.locator(`[data-project-step="${index}"]`);
      await step.getByRole("button", {name: "Continue", exact: true}).press("Enter");
      const error = step.locator("[data-project-choice-error]");
      await error.waitFor();
      const bounds = await error.evaluate(node => {
        const message = node.getBoundingClientRect();
        const scroller = node.closest("[data-site-dialog-content]").getBoundingClientRect();
        const formBox = node.closest("form").getBoundingClientRect();
        const active = document.activeElement;
        const tile = active.closest("label")?.getBoundingClientRect();
        const footer = node.parentElement.querySelector(".project-step-actions");
        const footerTop = Math.min(footer.getBoundingClientRect().top, scroller.bottom);
        const fits = box => box.left >= formBox.left - 1 && box.right <= formBox.right + 1;
        const checks = {
          message: fits(message) && message.top >= scroller.top - 1 && message.bottom <= footerTop + 1,
          focus: active.matches("input[type=radio]") && active.getAttribute("aria-describedby") === node.id &&
            !!tile && fits(tile) && message.bottom <= tile.top && tile.bottom <= footerTop + 1,
          buttons: Array.from(footer.querySelectorAll(".button")).every(button => fits(button.getBoundingClientRect())),
          page: document.documentElement.scrollWidth <= innerWidth + 1,
        };
        return {
          ...checks,
          ...(Object.values(checks).every(Boolean) ? {} : {
            active: active.id,
            messageBox: message.toJSON(),
            tileBox: tile?.toJSON(),
            scroller: scroller.toJSON(),
            footerTop,
          }),
        };
      });
      if (width <= 390) {
        const engine = useWebkit ? "webkit" : "chromium";
        await page.screenshot({path: path.join(output, `${engine}-${width}-${scale}-0${index}.png`), animations: "disabled"});
      }
      assert.deepEqual(bounds, {message: true, focus: true, buttons: true, page: true}, `${width}px step ${index}`);
      await step.locator(`label[for="${selection}"]`).click();
    }
    await form.locator('[data-project-step="3"]').waitFor();
    console.log(`PASS ${width}x${height} at ${scale}% text`);
  } finally {
    await context.close();
  }
}

async function checkKeyboardEntry(browser, name, width, height, modal) {
  const context = await browser.newContext({viewport: {width, height}, serviceWorkers: "block"});
  try {
    await useFixtures(context);
    const page = await context.newPage();
    await page.goto(origin + (modal ? "/" : "/jobs/new"));
    if (modal) {
      await page.locator("main").getByRole("link", {name: "Post project", exact: true}).click();
    }
    const form = page.locator("[data-project-composer].is-enhanced");
    await form.waitFor();
    await form.evaluate(node => {
      node.dataset.fixtureSubmissions = "0";
      node.addEventListener("submit", event => {
        event.preventDefault();
        event.stopImmediatePropagation();
        node.dataset.fixtureSubmissions = String(Number(node.dataset.fixtureSubmissions) + 1);
      }, true);
    });
    const activeStep = form.locator("[data-project-step]:not([hidden])");
    const step = async number => activeStep.and(form.locator(`[data-project-step="${number}"]`)).waitFor();
    const sample = () => form.evaluate(node => {
      const selected = node.querySelector("[data-project-step]:not([hidden])");
      const footer = selected.querySelector(".project-step-actions");
      const active = document.activeElement;
      const bounds = active.getBoundingClientRect();
      const center = document.elementFromPoint(bounds.left + bounds.width / 2, bounds.top + bounds.height / 2);
      const isVisible = active.id === "job-description" && bounds.top >= 0
        && bounds.bottom <= window.innerHeight + 1 && center === active
        && (getComputedStyle(footer).position === "static" || bounds.bottom <= footer.getBoundingClientRect().top + 1);
      return {
        step: Number(selected.dataset.projectStep), submissions: Number(node.dataset.fixtureSubmissions),
        active: active.id, descriptionVisible: isVisible,
      };
    });
    await form.locator('label[for="service-family-cleaning-upkeep"]').click();
    await step(2);
    await form.locator('label[for="service-choice-house-cleaning"]').click();
    await step(3);
    const title = form.locator("#job-title");
    const description = form.locator("#job-description");
    await title.fill("Synthetic cleaning project");
    await title.press("Enter");
    const initial = await sample();
    await page.screenshot({path: path.join(output, name + "-first-enter.png"), animations: "disabled"});
    for (let number = initial.step; number > 3; number -= 1) {
      await activeStep.locator("[data-project-back]").click();
      await step(number - 1);
    }
    await description.fill("Synthetic scope for cleaning an empty room and wiping the interior windows.");
    await description.press("End");
    await description.press("Enter");
    assert.ok((await description.inputValue()).endsWith("\n"), "Enter inserts a newline in Description");
    async function reachReview() {
      await step(3);
      await activeStep.locator("[data-project-next]").click();
      await step(4);
      await form.locator("#job-zip-code").fill("20001");
      await activeStep.locator("[data-project-next]").click();
      await step(5);
      await activeStep.locator("[data-project-next]").click();
      await step(6);
    }
    await reachReview();
    await activeStep.getByRole("button", {name: "Edit project details", exact: true}).click();
    await step(3);
    await title.fill("Synthetic cleaning project updated");
    await title.press("Enter");
    const edited = await sample();
    await page.screenshot({path: path.join(output, name + "-edit-enter.png"), animations: "disabled"});
    await reachReview();
    await activeStep.getByRole("button", {name: "Edit project area", exact: true}).click();
    await step(4);
    await form.locator("#job-city").press("Enter");
    const area = await sample();
    await activeStep.locator("[data-project-next]").click();
    await step(5);
    await form.locator("#job-budget-min").fill("100");
    await form.locator("#job-budget-min").press("Enter");
    const budget = await sample();
    await activeStep.locator("[data-project-next]").click();
    await step(6);
    await activeStep.locator('button[type="submit"]').press("Enter");
    const final = await sample();
    console.log(JSON.stringify({name, initial, edited, area, budget, final}));
    if (!captureBefore) {
      const expected = {step: 3, submissions: 0, active: "job-description", descriptionVisible: true};
      assert.deepEqual(initial, expected, name + " first title entry");
      assert.deepEqual(edited, expected, name + " edited title entry");
      assert.deepEqual([area.step, area.submissions], [4, 0], name + " area entry");
      assert.deepEqual([budget.step, budget.submissions], [5, 0], name + " budget entry");
      assert.equal(final.step, 6);
      assert.equal(final.submissions, 1, name + " explicit confirmation");
    }
  } finally {
    await context.close();
  }
}

async function checkNoScriptSubmission(browser) {
  const context = await browser.newContext({viewport: {width: 390, height: 844}, javaScriptEnabled: false});
  try {
    await useFixtures(context);
    const page = await context.newPage();
    await page.goto(origin + "/post-project");
    const form = page.locator("[data-project-composer]");
    assert.equal(await form.locator("[data-project-step]:visible").count(), 6);
    assert.equal(await form.locator('button[type="submit"]').isEnabled(), true);
    console.log("PASS: direct no-script composer keeps its native submit control");
  } finally {
    await context.close();
  }
}

(async () => {
  fs.mkdirSync(output, {recursive: true});
  const browser = useWebkit ? await webkit.launch({headless: true}) : await chromium.launch({
    headless: true, executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE, chromiumSandbox: true,
  });
  try {
    if (keyboardEntry) {
      for (const dimensions of [["phone-dialog", 390, 844, true], ["short-dialog", 390, 420, true],
        ["landscape-form", 844, 390, false],
        ["tablet-form", 820, 1180, false], ["desktop-form", 1280, 720, false]]) {
        await checkKeyboardEntry(browser, ...dimensions);
      }
      await checkNoScriptSubmission(browser);
    } else {
      for (const dimensions of [[320, 568, 200], [390, 844, 100], [820, 1180, 100], [1280, 720, 100]]) {
        await check(browser, ...dimensions);
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
