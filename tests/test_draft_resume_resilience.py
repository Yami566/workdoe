from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from test_tile_free_mode import request, worker_for_mode

BASE = "https://workdoe.com"
COOKIE = "workdoe_job_draft=synthetic-draft-cookie"
CLIENT = {"id": 7, "role": "client", "status": "active", "display_name": "Fixture"}


class DraftResumeResilienceTests(IsolatedAsyncioTestCase):
    def worker(self):
        return worker_for_mode(DB=object(), WORKDOE_SECRET_KEY="s" * 32)

    async def test_draft_read_failure_offers_recovery_without_replacement_or_diagnostics(self):
        for path, user, retry_path in (
            ("/post-project", None, "/post-project"),
            ("/post-project?embed=1&fixture=synthetic-private-query", None, "/post-project"),
            ("/jobs/new", CLIENT, "/jobs/new"),
        ):
            for method in ("GET", "HEAD"):
                with self.subTest(path=path, method=method):
                    module, worker = self.worker()
                    incoming = request(BASE + path, method)
                    incoming.headers["Cookie"] = COOKIE
                    with (
                        patch.object(worker, "optional_workdoe_user", AsyncMock(return_value=user)),
                        patch.object(module, "unread_message_count_for_user", AsyncMock(return_value=0)),
                        patch.object(module, "db_run", AsyncMock(side_effect=RuntimeError("synthetic storage detail"))) as read,
                        patch.object(module, "save_job_draft_record", AsyncMock()) as save,
                    ):
                        response = await worker.fetch(incoming)
                    read.assert_awaited_once()
                    save.assert_not_awaited()
                    self.assertEqual(response.status, 503)
                    self.assertEqual(response.headers["Retry-After"], "5")
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
                    self.assertNotIn("Set-Cookie", response.headers)
                    if method == "HEAD":
                        self.assertEqual(response.body, "")
                    else:
                        self.assertIn("Draft temporarily unavailable", response.body)
                        self.assertIn(f'href="{retry_path}">Try again', response.body)
                        for marker in ("synthetic storage detail", "synthetic-private-query", COOKIE, "data-project-composer", "<script"):
                            self.assertNotIn(marker, response.body)

    async def test_untrusted_read_result_is_not_treated_as_an_absent_draft(self):
        for result, expected in (
            ({"success": False, "results": []}, 503),
            ({"success": True}, 503),
            ({"success": True, "results": {"bad": "shape"}}, 503),
            ({"success": True, "results": [{"id": 1, "scope_answers_json": "invalid"}]}, 503),
            ({"success": True, "results": [{"id": 1, "scope_answers_json": "[]"}]}, 503),
            ({"success": True, "results": []}, 200),
        ):
            with self.subTest(result=result):
                module, worker = self.worker()
                incoming = request(BASE + "/post-project")
                incoming.headers["Cookie"] = COOKIE
                with (
                    patch.object(worker, "optional_workdoe_user", AsyncMock(return_value=None)),
                    patch.object(module, "db_run", AsyncMock(return_value=result)),
                ):
                    response = await worker.fetch(incoming)
                self.assertEqual(response.status, expected)
                self.assertEqual("data-project-composer" in response.body, expected == 200)

    async def test_verified_submission_does_not_read_the_old_draft(self):
        module, worker = self.worker()
        incoming = request(BASE + "/post-project", "POST")
        incoming.headers.update({"Cookie": COOKIE, "Origin": BASE, "Sec-Fetch-Site": "same-origin"})
        form = {
            "title": "Synthetic window cleaning", "service_group_slug": "cleaning-upkeep",
            "service_slug": "window-cleaning", "category": "Window cleaning", "project_setting": "house",
            "city": "Alexandria", "state": "VA", "zip_code": "22314",
            "description": "Clean reachable ground-floor exterior glass and frames.",
            "cf-turnstile-response": "synthetic-challenge",
            "service_policy_acknowledgement": module.service_policy("window-cleaning")["version"],
        }
        with (
            patch.object(worker, "optional_workdoe_user", AsyncMock(return_value=None)),
            patch.object(module, "db_run", AsyncMock(side_effect=RuntimeError("synthetic read outage"))) as read,
            patch.object(module, "request_form_data", AsyncMock(return_value=form)),
            patch.object(module, "verify_turnstile_for_request", AsyncMock()) as verify,
            patch.object(module, "worker_write_rate_limit_response", AsyncMock(return_value=None)) as limit,
            patch.object(module, "save_job_draft_record", AsyncMock(return_value="new-synthetic-cookie")) as save,
        ):
            response = await worker.fetch(incoming)
        read.assert_not_awaited()
        self.assertEqual(verify.await_args.kwargs["action"], "job-draft")
        limit.assert_awaited_once_with(worker.env, "workdoe-guest-project-draft")
        save.assert_awaited_once()
        self.assertEqual(save.await_args.args[2]["title"], form["title"])
        self.assertEqual(response.status, 303)
        self.assertEqual(response.headers["Location"], "/create-account?intent=post-job&draft=saved")
