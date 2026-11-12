import hashlib
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from test_cloudflare_release import load_worker_entry_module

SITE = "https://workdoe.com"
WWW = "https://www.workdoe.com"
LOCAL = "http://127.0.0.1:8787"
PROXY_PATH = "/__clerk/v1/environment"
SDK_PATH = "/__clerk/npm/@clerk/clerk-js@6.40.1/dist/clerk.browser.js"
NOTICE_PATH = "/__clerk/npm/@clerk/clerk-js@6.40.1/LICENSE"


class ClerkProxyOriginTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_worker_entry_module()
        self.worker = self.module.Default()
        self.worker.env = SimpleNamespace(WORKDOE_ENV="production", CLERK_SECRET_KEY="native-fixture-only")

    async def test_unreviewed_explicit_origins_never_reach_provider(self):
        for method, origin in (
            ("GET", "https://api.workdoe.com"),
            ("HEAD", "https://outside.invalid"),
            ("OPTIONS", "null"),
            ("POST", f"{SITE}, {WWW}"),
            ("GET", "https://workdoe.com.outside.invalid"),
            ("GET", "https://workdoe.com:8443"),
            ("GET", "http://workdoe.com"),
            ("GET", LOCAL),
            ("GET", ""),
        ):
            with self.subTest(method=method, origin=origin):
                request = SimpleNamespace(
                    url=(LOCAL if origin == LOCAL else SITE) + PROXY_PATH,
                    method=method,
                    headers={"Origin": origin, "CF-Connecting-IP": "203.0.113.5"},
                    body=b"fixture",
                )
                provider = AsyncMock(return_value=self.module.Response(
                    "unexpected upstream response",
                    headers={"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"},
                ))
                with (
                    patch.object(self.module, "clerk_production_configuration_ready", return_value=True) as ready,
                    patch.object(self.module, "fetch", provider),
                ):
                    response = await self.worker.clerk_frontend_api_proxy(request)
                self.assertEqual(response.status, 403)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertNotIn("Access-Control-Allow-Origin", response.headers)
                self.assertNotIn("Access-Control-Allow-Credentials", response.headers)
                if method == "HEAD":
                    self.assertEqual(response.body, "")
                ready.assert_not_called()
                provider.assert_not_called()

    async def test_reviewed_and_originless_requests_forward_unchanged(self):
        for origin, request_base, environment in (
            (SITE, SITE, "production"),
            (WWW, SITE, "production"),
            (None, SITE, "production"),
            (LOCAL, LOCAL, "local"),
        ):
            with self.subTest(origin=origin):
                self.worker.env.WORKDOE_ENV = environment
                headers = {"CF-Connecting-IP": "203.0.113.5"}
                if origin is not None:
                    headers["Origin"] = origin
                request = SimpleNamespace(
                    url=request_base + "/__clerk/v1/client/sign_ins",
                    method="POST",
                    headers=headers,
                    body=b"fixture",
                )
                upstream = self.module.Response("fixture", status=201)
                provider = AsyncMock(return_value=upstream)
                with (
                    patch.object(self.module, "clerk_production_configuration_ready", return_value=True),
                    patch.object(self.module, "fetch", provider),
                ):
                    response = await self.worker.clerk_frontend_api_proxy(request)
                self.assertIs(response, upstream)
                provider.assert_awaited_once()
                args, options = provider.await_args
                self.assertEqual(args, ("https://frontend-api.clerk.dev/v1/client/sign_ins",))
                self.assertEqual(options["headers"].get("Origin"), origin)
                self.assertEqual(options["method"], "POST")
                self.assertEqual(options["body"], b"fixture")
                self.assertEqual(options["redirect"], "manual")

    async def test_reviewed_package_responses_preserve_verified_bytes_and_cache(self):
        body = b"reviewed package fixture"
        digest = hashlib.sha256(body).hexdigest()
        for path, method, status, media_type in (
            (SDK_PATH, "GET", 200, "application/javascript; charset=utf-8"),
            (SDK_PATH, "HEAD", 200, 'Text/JavaScript; charset="UTF-8"'),
            (NOTICE_PATH, "GET", 200, "text/plain; charset=utf-8"),
        ):
            with self.subTest(path=path, method=method, status=status):
                headers = {
                    "Cache-Control": "public, max-age=31536000, immutable", "ETag": '"synthetic"',
                    "content-type": media_type, "Content-Length": str(len(body)), "Set-Cookie": "fixture=not-forwarded",
                }
                upstream = self.module.Response(object(), status=status, headers=headers)
                request = SimpleNamespace(url=SITE + path, method=method, headers={
                    "CF-Connecting-IP": "203.0.113.5", "Range": "bytes=0-8", "If-None-Match": '"prior"',
                    "aCcEpT-EnCoDiNg": "gzip",
                })
                globals_ = self.module.verified_clerk_package.__globals__
                with (
                    patch.object(self.module, "clerk_production_configuration_ready", return_value=True),
                    patch.object(self.module, "fetch", AsyncMock(return_value=upstream)) as fetch,
                    patch.dict(globals_["CLERK_BROWSER_PINS"], {path.removeprefix("/__clerk"): (len(body), digest)}),
                    patch.dict(globals_, {"read_json_stream_bytes": AsyncMock(return_value=body)}),
                ):
                    response = await self.worker.clerk_frontend_api_proxy(request)
                    read = globals_["read_json_stream_bytes"]
                    if method == "GET":
                        read.assert_awaited_once()
                        self.assertEqual(read.await_args.kwargs["max_bytes"], len(body))
                    else:
                        read.assert_not_awaited()
                    forwarded = {key.lower(): value for key, value in fetch.await_args.kwargs["headers"].items()}
                    self.assertEqual(forwarded["accept-encoding"], "identity")
                    self.assertNotIn("range", forwarded)
                    self.assertNotIn("if-none-match", forwarded)
                self.assertEqual(response.status, 200)
                self.assertEqual(response.body, body if method == "GET" else None)
                self.assertEqual(response.headers["Content-Type"], media_type)
                self.assertEqual(response.headers["ETag"], '"synthetic"')
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertNotIn("Set-Cookie", response.headers)

    async def test_unsafe_package_responses_abort_and_do_not_reflect_upstream_content(self):
        js = {"Content-Type": "application/javascript"}
        private = "synthetic-provider-detail"
        for path, status, headers, safe_status in (
            (SDK_PATH, 200, {"Content-Type": "text/html"}, 502),
            (SDK_PATH, 200, {"Content-Type": "application/javascript; charset=utf-8, text/html"}, 502),
            (SDK_PATH, 200, {}, 502),
            (NOTICE_PATH, 200, js, 502),
            (NOTICE_PATH, 200, {"Content-Type": "text/plain; charset=latin1"}, 502),
            (SDK_PATH, 302, {"Location": "https://outside.invalid/" + private}, 502),
            (SDK_PATH, 200, {**js, "rEfReSh": "0; url=/" + private}, 502),
            (SDK_PATH, 200, {**js, "Service-Worker-Allowed": "/"}, 502),
            (SDK_PATH, 206, {**js, "Content-Range": "bytes 0-9/100"}, 502),
            (SDK_PATH, 304, {}, 502),
            (SDK_PATH, 200, {**js, "Content-Encoding": "gzip"}, 502),
            (SDK_PATH, 200, {**js, "Content-Length": "1"}, 502),
            (SDK_PATH, 429, {"Content-Type": "text/html", "Set-Cookie": f"__client={private}"}, 429),
        ):
            for method in ("GET", "HEAD"):
                with self.subTest(path=path, method=method, status=status, headers=headers):
                    upstream = self.module.Response(private, status=status, headers=headers)
                    request = SimpleNamespace(url=SITE + path, method=method, headers={"CF-Connecting-IP": "203.0.113.5"})
                    controller = Mock()
                    with (
                        patch.object(self.module, "clerk_production_configuration_ready", return_value=True),
                        patch.object(self.module, "fetch", AsyncMock(return_value=upstream)) as fetch,
                        patch.dict("sys.modules", {"js": SimpleNamespace(AbortController=SimpleNamespace(new=Mock(return_value=controller)))}),
                        patch("builtins.print") as log,
                    ):
                        response = await self.worker.clerk_frontend_api_proxy(request)
                    self.assertEqual(response.status, safe_status)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                    self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                    for header in ("Set-Cookie", "Location", "Refresh", "Service-Worker-Allowed", "Content-Range"):
                        self.assertNotIn(header, response.headers)
                    self.assertNotIn(private, response.body)
                    if method == "HEAD":
                        self.assertEqual(response.body, "")
                    controller.abort.assert_called_once_with()
                    fetch.assert_awaited_once()
                    self.assertEqual(log.call_args.args[0], '{"event": "clerk-proxy-upstream-failed", "reason": "package-response"}')
