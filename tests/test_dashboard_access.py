from __future__ import annotations

import asyncio
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from dashboard_fixture import DashboardFixture


class DashboardAccessTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = DashboardFixture(Path(directory))
            try:
                yield fixture
            finally:
                fixture.db.close()

    def shell(self, fixture, path, actor_id=None, method="GET"):
        async def signed_in(_request):
            if actor_id is None:
                return None
            return dict(
                fixture.db.execute(
                    "SELECT * FROM users WHERE id = ?", (actor_id,)
                ).fetchone()
            )

        fixture.worker.optional_workdoe_user = signed_in
        request = SimpleNamespace(
            url="https://workdoe.com" + path,
            method=method,
            headers={},
        )
        return asyncio.run(fixture.worker.app_shell(request, urlparse(path).path))

    def test_wrong_role_dashboard_has_private_recovery_without_data_queries(self):
        for path, actor, expected_role in (
            ("/client/dashboard", 2, "consumer"),
            ("/contractor/dashboard", 1, "contractor"),
            ("/client/dashboard", 4, "consumer"),
        ):
            with self.subTest(path=path, actor=actor), self.fixture() as fixture:
                response = self.shell(fixture, path, actor)
                self.assertEqual(response.status, 403)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(
                    response.headers["Content-Type"], "text/html; charset=utf-8"
                )
                self.assertIn("Content-Security-Policy", response.headers)
                self.assertIn(
                    f'<h1 id="dashboard-access-title">Use a {expected_role} account</h1>',
                    response.body,
                )
                self.assertIn('href="/dashboard">Open my workspace</a>', response.body)
                self.assertIn('data-json-action="/api/auth/logout"', response.body)
                self.assertIn(
                    f'data-success-url-template="/login?next={path}"', response.body
                )
                self.assertIn("Sign out and switch account", response.body)
                self.assertIn('src="/worker-actions.js"', response.body)
                self.assertNotIn("fixture-", response.body)
                self.assertNotIn("Fixture yard task", response.body)
                self.assertEqual(fixture.statements, [])

    def test_wrong_role_head_is_empty_and_does_not_query_data(self):
        for path, actor in (
            ("/client/dashboard", 2),
            ("/contractor/dashboard", 1),
        ):
            with self.subTest(path=path), self.fixture() as fixture:
                response = self.shell(fixture, path, actor, "HEAD")
                self.assertEqual(response.status, 403)
                self.assertEqual(response.body, "")
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(fixture.statements, [])

    def test_anonymous_dashboard_preserves_login_destination(self):
        for path in (
            "/client/dashboard?view=history",
            "/contractor/dashboard?view=history",
            "/dashboard",
        ):
            for method in ("GET", "HEAD"):
                with self.subTest(path=path, method=method), self.fixture() as fixture:
                    response = self.shell(fixture, path, method=method)
                    self.assertEqual(response.status, 302)
                    target = urlparse(response.headers["Location"])
                    self.assertEqual(target.path, "/login")
                    self.assertEqual(parse_qs(target.query), {"next": [path]})
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                    self.assertEqual(response.body, "")
                    self.assertEqual(fixture.statements, [])

    def test_inactive_user_is_denied_before_dashboard_recovery(self):
        with self.fixture() as fixture:
            fixture.db.execute("UPDATE users SET status = 'suspended' WHERE id = 2")
            fixture.db.commit()
            response = self.shell(fixture, "/client/dashboard", 2)
            self.assertEqual(response.status, 403)
            self.assertNotIn("Open my workspace", response.body)
            self.assertEqual(fixture.statements, [])

    def test_role_aware_entry_redirects_to_current_workspace(self):
        for actor, path in (
            (1, "/client/dashboard"),
            (2, "/contractor/dashboard"),
            (4, "/admin"),
        ):
            with self.subTest(actor=actor), self.fixture() as fixture:
                response = self.shell(fixture, "/dashboard", actor)
                self.assertEqual(response.status, 302)
                self.assertEqual(response.headers["Location"], path)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(fixture.statements, [])

    def test_own_dashboard_still_renders_only_own_projects(self):
        for actor, path, sees_project in (
            (1, "/client/dashboard", True),
            (3, "/client/dashboard", False),
            (2, "/contractor/dashboard", False),
        ):
            with self.subTest(actor=actor), self.fixture() as fixture:
                response = self.shell(fixture, path, actor)
                self.assertEqual(response.status, 200)
                self.assertEqual("Fixture yard task" in response.body, sees_project)
                self.assertNotIn("Sign out and switch account", response.body)
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_missing_private_resource_is_not_replaced_with_role_recovery(self):
        for path, actor in (
            ("/client/jobs/99999", 2),
            ("/client/jobs/99999", 1),
            ("/unknown-dashboard", 1),
        ):
            with self.subTest(path=path, actor=actor), self.fixture() as fixture:
                response = self.shell(fixture, path, actor)
                self.assertEqual(response.status, 404)
                self.assertNotIn("Sign out and switch account", response.body)

    def test_flask_wrong_role_dashboard_also_denies_access(self):
        for actor, path in (
            (1, "/contractor/dashboard"),
            (2, "/client/dashboard"),
        ):
            with self.subTest(actor=actor), self.fixture() as fixture:
                with fixture.client.session_transaction() as session:
                    session["user_id"] = actor
                response = fixture.client.get(path)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn(b"Fixture yard task", response.data)
                self.assertIn(b'href="/dashboard"', response.data)
