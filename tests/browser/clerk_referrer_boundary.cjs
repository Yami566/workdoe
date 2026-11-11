"use strict";

const assert = require("node:assert/strict");
const {execFileSync} = require("node:child_process");
const path = require("node:path");
const {chromium, webkit} = require(process.env.WORKDOE_PLAYWRIGHT_MODULE);

const root = path.resolve(__dirname, "../..");
const origin = "https://workdoe.com";
const useWebkit = process.argv.includes("--webkit");
const captureBefore = process.argv.includes("--capture-before");
const cases = JSON.parse(execFileSync("python", ["-c", `
import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch
sys.path.insert(0, "tests")
from test_tile_free_mode import request, worker_for_mode

async def collect():
    module, worker = worker_for_mode(WORKDOE_MAP_MODE="list", DB=object())
    user = {
        "id": 7, "role": "client", "status": "active", "display_name": "Fixture",
        "email": "account@fixture.invalid",
    }
    cases = {
        "board-dialog": "/?q=synthetic-workdoe-search",
        "sign-in": "/login?next=/jobs/17",
        "invitation": "/create-account?__clerk_status=sign_up&__clerk_ticket=synthetic-ticket",
        "account": "/account?fixture=synthetic-account-query",
    }
    with (
        patch.object(worker, "optional_workdoe_user", AsyncMock(return_value=user)),
        patch.object(module, "db_run", AsyncMock(return_value={"results": []})),
        patch.object(module, "unread_message_count_for_user", AsyncMock(return_value=0)),
    ):
        for name, path in cases.items():
            response = await worker.fetch(request("https://workdoe.com" + path))
            assert response.status == 200, (name, response.status)
            yield [name, path, response.headers]

async def main():
    print(json.dumps([row async for row in collect()]))

asyncio.run(main())
`], {cwd: root, encoding: "utf8", windowsHide: true}));

(async () => {
  const browser = useWebkit ? await webkit.launch({headless: true, timeout: 15000}) : await chromium.launch({
    executablePath: process.env.WORKDOE_CHROMIUM_EXECUTABLE, headless: true, chromiumSandbox: true,
  });
  try {
    for (const [name, routePath, headers] of cases) {
      const context = await browser.newContext({serviceWorkers: "block"});
      try {
        const source = origin + routePath;
        const endpoint = origin + "/__clerk/v1/client/sign_ins";
        const observed = [];
        await context.route("**/*", async route => {
          const request = route.request();
          if (request.url() === source && request.method() === "GET") {
            // Use the Worker's real headers without loading the third-party SDK.
            return route.fulfill({headers, body: "<!doctype html><title>Referrer fixture</title>"});
          }
          if (request.url() === endpoint && request.method() === "POST") {
            observed.push({
              referrer: await request.headerValue("referer"),
              origin: await request.headerValue("origin"),
              body: request.postData(),
            });
            return route.fulfill({status: 200, json: {fixture: true}});
          }
          return route.abort();
        });
        const page = await context.newPage();
        await page.goto(source);
        const response = await page.evaluate(async () => {
          const result = await fetch("/__clerk/v1/client/sign_ins", {method: "POST", body: "fixture=1"});
          return [result.status, await result.json()];
        });
        assert.deepEqual(response, [200, {fixture: true}]);
        assert.equal(observed.length, 1);
        const [post] = observed;
        assert.equal(post.origin, origin);
        assert.equal(post.body, "fixture=1");
        console.log(`${name}: ${post.referrer === origin + "/" ? "origin only" : post.referrer === source ? "full page URL" : "unexpected"}`);
        assert.equal(post.referrer, captureBefore && name !== "invitation" ? source : origin + "/");
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
