import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from test_cloudflare_release import load_worker_entry_module

INVALID_IDS = (
    ("too long", "9" * 4301),
    ("outside exact range", "9007199254740992"),
    ("not ASCII", "\u0661"),
    ("not a decimal digit", "\u00b2"),
    ("zero", "0"),
    ("sign", "+1"),
    ("separator", "1_0"),
)
VALID_ID = 2147483648


class URLRecordIDTests(IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_worker_entry_module()

    def test_document_routes_do_not_accept_invalid_record_ids(self):
        for pattern, parser, checker in (
            ("/jobs/{}", "parse_app_job_id", "is_app_shell_route"),
            ("/client/jobs/{}", "parse_app_client_job_id", "is_app_shell_route"),
            ("/client/jobs/{}/edit", "parse_app_client_job_edit_id", "is_app_shell_route"),
            ("/messages/{}", "parse_app_thread_id", "is_app_shell_route"),
            ("/contractors/{}", "parse_app_contractor_id", "is_public_contractor_profile_route"),
        ):
            parse, check = getattr(self.module, parser), getattr(self.module, checker)
            self.assertTrue(check(pattern.format(VALID_ID)))
            self.assertEqual(parse(pattern.format(VALID_ID)), VALID_ID)
            for label, value in INVALID_IDS:
                with self.subTest(pattern=pattern, input=label):
                    path = pattern.format(value)
                    self.assertFalse(check(path))
                    self.assertEqual(parse(path), 0)

    def test_entry_selection_only_uses_supported_record_ids_or_sample_labels(self):
        select = self.module.selected_job_id
        exact_maximum = "9007199254740991"
        self.assertEqual(select({"job_id": [exact_maximum]}), exact_maximum)
        self.assertEqual(select({"job_id": ["demo-02"]}), "demo-02")
        self.assertEqual(select({"next": ["/jobs/9?details=1"]}), "9")
        for label, value in INVALID_IDS:
            with self.subTest(input=label):
                self.assertEqual(select({"job_id": [value]}), "")
                self.assertEqual(select({"next": ["/jobs/" + value]}), "")

    def test_api_path_parsers_reject_invalid_ids_with_route_error(self):
        for parser, pattern, expected in (
            ("parse_job_detail_id", "/api/jobs/{}", VALID_ID),
            ("parse_job_update_id", "/api/jobs/{}/update", VALID_ID),
            ("parse_job_status_path", "/api/jobs/{}/close", (VALID_ID, "close", "closed")),
            ("parse_job_quality_feedback_path", "/api/jobs/{}/quality-feedback", VALID_ID),
            ("parse_client_job_requests_path", "/api/client/jobs/{}/requests", VALID_ID),
            ("parse_match_request_job_id", "/api/jobs/{}/request", VALID_ID),
            ("parse_match_decision_path", "/api/match-requests/{}/approve", (VALID_ID, "approve", "approved")),
            ("parse_match_completion_path", "/api/match-requests/{}/complete", VALID_ID),
            ("parse_match_review_create_path", "/api/match-requests/{}/review", VALID_ID),
            ("parse_match_review_action_path", "/api/reviews/{}/response", (VALID_ID, "response")),
            ("parse_thread_id", "/api/messages/threads/{}", VALID_ID),
            ("parse_public_contractor_id", "/api/contractors/{}", VALID_ID),
            ("parse_saved_location_delete_path", "/api/client/locations/{}/delete", VALID_ID),
            ("parse_project_template_delete_path", "/api/client/templates/{}/delete", VALID_ID),
            ("parse_proposal_template_delete_path", "/api/contractor/proposal-templates/{}/delete", VALID_ID),
            ("parse_contractor_credential_remove_path", "/api/contractor/credentials/{}/remove", VALID_ID),
            ("parse_invitation_action_path", "/api/repeat-invitations/{}/decline", (VALID_ID, "decline")),
            ("media_scope_from_path", "/media/jobs/{}", ("job", VALID_ID)),
            ("media_upload_scope_from_path", "/api/media/contractors/{}/upload", ("contractor", VALID_ID)),
            (
                "parse_admin_moderation_path", "/api/admin/photos/job/{}/hide",
                {"target_type": "job_photo", "target_id": VALID_ID, "action": "hide"},
            ),
        ):
            parse = getattr(self.module, parser)
            with self.subTest(parser=parser, input="valid"):
                self.assertEqual(parse(pattern.format(VALID_ID)), expected)
            for label, value in INVALID_IDS:
                with self.subTest(parser=parser, input=label), self.assertRaisesRegex(ValueError, "route"):
                    parse(pattern.format(value))

    async def test_public_invalid_profile_ids_return_safe_404_before_lookup(self):
        worker = self.module.Default()
        worker.env = SimpleNamespace(DB=object())
        lookup = AsyncMock(side_effect=AssertionError("Invalid IDs must never be looked up."))
        previous = self.module.db_run
        self.addCleanup(setattr, self.module, "db_run", previous)
        self.module.db_run = lookup
        for prefix, methods in (("/contractors/", ("GET", "HEAD")), ("/api/contractors/", ("GET",))):
            for method in methods:
                for label, value in INVALID_IDS[:2]:
                    with self.subTest(prefix=prefix, method=method, input=label):
                        response = await worker.fetch(SimpleNamespace(
                            method=method, url=f"https://workdoe.com{prefix}{value}", headers={"Accept": "text/html"},
                        ))
                        self.assertEqual(response.status, 404)
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        if method == "HEAD":
                            self.assertEqual(response.body, "")
                        elif prefix.startswith("/api/"):
                            self.assertFalse(json.loads(response.body)["ok"])
                        else:
                            self.assertIn("Page not found", response.body)
        lookup.assert_not_called()
