from unittest import TestCase

from test_tile_free_mode import CONTRACTOR_ROW, worker_for_mode


class SharedProjectLinkTests(TestCase):
    def render(self, path, params, *, mode="area", rows=None):
        module, _ = worker_for_mode()
        rows = [CONTRACTOR_ROW] if rows is None else rows
        return module.build_entry_shell_html(path, params, rows, "pk_live_synthetic_fixture", "", map_mode=mode)

    def test_unavailable_link_does_not_select_a_different_project(self):
        for mode in ("area", "list"):
            for identifier in ("999", "demo-99"):
                with self.subTest(mode=mode, identifier=identifier):
                    html = self.render("/", {"job_id": [identifier]}, mode=mode)
                    self.assertIn('data-mobile-panel="details"', html)
                    self.assertIn("<h2>Project not shown</h2>", html)
                    self.assertIn('href="/">Browse all projects', html)
                    self.assertNotIn('data-project-detail-content data-job-id=', html)
                    self.assertNotIn('class="project-result is-map-active"', html)
                    self.assertNotIn("Create account to respond</a>", html)
                    self.assertEqual("data-missing-shared-project" in html, mode == "area")

    def test_visible_project_and_default_board_keep_their_normal_selection(self):
        for params in ({}, {"job_id": ["81"]}):
            with self.subTest(params=params):
                html = self.render("/", params)
                self.assertIn('data-project-detail-content data-job-id="81"', html)
                self.assertNotIn('data-mobile-panel="details"', html)
                self.assertEqual("data-missing-shared-project" in html, bool(params))

    def test_account_form_only_names_a_matching_visible_project(self):
        for params in ({"job_id": ["999"]}, {"next": ["/jobs/999"]}, {"job_id": ["demo-99"]}):
            with self.subTest(params=params):
                html = self.render("/create-account", params)
                self.assertNotIn('aria-label="Selected lead"', html)
                self.assertIn('data-selected-job-id=""', html)
        matched = self.render("/create-account", {"job_id": ["81"]})
        self.assertIn('aria-label="Selected lead"', matched)
        self.assertIn('data-selected-job-id="81"', matched)
        hidden = self.render("/login", {"job_id": ["81"]}, rows=[CONTRACTOR_ROW | {"title": "private@fixture.invalid"}])
        self.assertNotIn('aria-label="Selected lead"', hidden)
        self.assertNotIn("private@fixture.invalid", hidden)

    def test_unrecognized_sample_id_is_not_echoed(self):
        html = self.render("/", {"job_id": ["demo-unsafe@fixture.invalid"]})
        self.assertNotIn("unsafe@fixture.invalid", html)
        self.assertNotIn("data-missing-shared-project", html)
