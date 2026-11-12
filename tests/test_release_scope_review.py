from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import review_release_scope as scope

BASE = "a" * 40
CANDIDATE = "b" * 40


def narrative(contact="mailto:admin@example.invalid", period="1 to 5 days"):
    return (
        '<h1>Policy</h1><p class="eyebrow">Beta</p><h2>Contact</h2>'
        f'<p>Email <a href="{contact}">admin</a>. Reply within {period}.</p>'
        + "".join(f"<p>Statement {index}.</p>" for index in range(5))
    )


def worker_source(body):
    return "\n".join(
        f"def {name}_page_html():\n    body = {body!r}\n    return layout(None, '/{name}', 'Policy', body)\n"
        for name in scope.POLICIES
    )


class ReleaseScopeReviewTests(unittest.TestCase):
    def test_navigation_and_markup_are_not_policy_amendments(self):
        original = scope.PolicyStatements(narrative()).statements
        changed = '<nav><p>Contents</p><a href="#contact">Contact</a></nav>' + narrative().replace(
            "<h2>", '<h2 id="contact" tabindex="-1">',
        )
        self.assertEqual(original, scope.PolicyStatements(changed).statements)
        for body in (narrative(period="30 days"), narrative(contact="https://changed.invalid")):
            self.assertNotEqual(original, scope.PolicyStatements(body).statements)

    def test_unknown_or_incomplete_policy_structure_is_not_certified(self):
        for body in ('<h1>Policy</h1>', narrative() + '<p>Unclosed', narrative().replace(
            'href="mailto:admin@example.invalid"', 'href="mailto:admin@example.invalid" href="https://changed.invalid"',
        )):
            with self.subTest(body=body[:30]), self.assertRaises(scope.ScopeReviewError):
                scope.PolicyStatements(body)
        static = '{% extends "base.html" %}{% block content %}' + narrative() + '{% endblock %}'
        self.assertEqual(scope.template_policy_body(static), narrative())
        for body in ('{{ dynamic_text }}', '{% if owner %}Accepted{% endif %}', '{% include "policy.html" %}'):
            with self.subTest(body=body), self.assertRaises(scope.ScopeReviewError):
                scope.template_policy_body('{% block content %}' + body + '{% endblock %}')

    def test_worker_policy_is_parsed_without_executing_application_code(self):
        source = worker_source(narrative())
        self.assertEqual(scope.worker_policy_body(source, "privacy"), narrative())
        for changed in (source.replace("body =", "body = make_policy() #"),
                        source.replace("'Policy', body)", "'Policy', transform(body))"),
                        source + "\ndef privacy_page_html():\n    return malicious()\n"):
            with self.subTest(changed=changed[:30]), self.assertRaises(scope.ScopeReviewError):
                scope.worker_policy_body(changed, "privacy")

    def test_json_rejects_duplicates_nonobjects_and_nonfinite_values(self):
        for raw in (b'{"vars":{},"vars":{}}', b'[]', b'{"limit":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(scope.ScopeReviewError):
                scope.read_json(lambda *_, raw=raw: raw, "config.json")

    def test_tree_rejects_unreviewed_refs_and_links_before_reading_source(self):
        with patch.object(scope, "committed_release_reader") as read, patch.object(scope, "git_read") as git:
            with self.assertRaises(scope.ScopeReviewError):
                scope.committed_tree(ROOT, "--upload-pack=unexpected")
            read.assert_not_called()
            git.assert_not_called()
            for record in (f"120000 blob {BASE}\tworkdoe/link\0", f"100644 blob {BASE}\tworkdoe/bad\nname\0"):
                git.return_value = record
                with self.assertRaises(scope.ScopeReviewError):
                    scope.committed_tree(ROOT, BASE)

    def test_scope_reports_config_and_policy_changes_without_granting_approval(self):
        import json

        paths = {"package.json", "package-lock.json", "requirements.txt", "requirements-audit.txt", "cloudflare/wrangler.jsonc",
                 "cloudflare/worker/app_shell.py", "cloudflare/d1/migrations/0001_initial.sql",
                 "LICENSE", "THIRD_PARTY_NOTICES.md", "DEPENDENCY_PROVENANCE.json",
                 *(f"workdoe/templates/{name}.html" for name in scope.POLICIES)}
        before = dict.fromkeys(paths, ("100644", BASE))
        after = {**before, "cloudflare/worker/app_shell.py": ("100644", CANDIDATE),
                 "workdoe/static/map.js": ("100644", CANDIDATE),
                 "THIRD_PARTY_NOTICES.md": ("100644", CANDIDATE),
                 ".github/python/runtime.txt": ("100644", CANDIDATE)}

        def reader(commit):
            html = narrative(period="1 to 5 days" if commit == BASE else "30 days")

            def read(path, _):
                if path == "cloudflare/worker/app_shell.py":
                    return worker_source(html).encode()
                if path.startswith("workdoe/templates/"):
                    return ('{% block content %}' + html + '{% endblock %}').encode()
                if path == "package.json":
                    return b'{"devDependencies":{"wrangler":"4.152.0"}}'
                config = {"vars": {"WORKDOE_MAP_MODE": "map" if commit == BASE else "area"}}
                config["vars"]["REMOVED" if commit == BASE else "ADDED"] = None
                if commit == BASE:
                    config["removed_setting"] = None
                return json.dumps(config).encode()

            return read

        with (
            patch.object(scope, "committed_tree", side_effect=[before, after]),
            patch.object(scope, "committed_release_reader", side_effect=lambda _, commit: reader(commit)),
        ):
            result = scope.review(ROOT, BASE, CANDIDATE)
        self.assertEqual(result["changed_path_count"], 4)
        self.assertEqual(result["configuration"]["changed_variable_names"], ["ADDED", "REMOVED", "WORKDOE_MAP_MODE"])
        self.assertEqual(result["configuration"]["other_changed_keys"], ["removed_setting"])
        self.assertTrue(result["database_migrations_unchanged"])
        self.assertEqual(result["migration_file_count"], 1)
        self.assertTrue(result["node_dependency_pins_unchanged"])
        self.assertTrue(result["python_requirements_unchanged"])
        self.assertFalse(result["python_dependency_inputs"]["unchanged"])
        self.assertIn({"path": ".github/python/runtime.txt", "status": "added"},
                      result["python_dependency_inputs"]["files"])
        self.assertEqual(result["python_requirements_legacy_scope"], "requirements.txt only")
        self.assertEqual(result["license_clearance"], "not_evaluated")
        self.assertEqual(result["provenance_changed_paths"], ["THIRD_PARTY_NOTICES.md"])
        self.assertFalse(result["deployment_authorized"])
        self.assertFalse(result["public_launch_authorized"])
        self.assertFalse(result["live_baseline_verified"])
        self.assertFalse(result["policy_statement_comparison"]["privacy"]["worker_statements_unchanged"])
        self.assertTrue(result["policy_statement_comparison"]["privacy"]["candidate_adapter_parity"])

    def test_missing_required_input_does_not_report_unchanged_dependencies(self):
        with (
            patch.object(scope, "committed_tree", return_value={"workdoe/file.py": ("100644", BASE)}),
            self.assertRaises(scope.ScopeReviewError),
        ):
            scope.review(ROOT, BASE, CANDIDATE)

    def test_python_dependency_comparison_covers_lock_additions_removals_and_hash_only_changes(self):
        before = {
            "requirements.txt": ("100644", BASE),
            "requirements-audit.txt": ("100644", BASE),
            ".github/python/ruff.txt": ("100644", BASE),
            ".github/python/old.txt": ("100644", BASE),
        }
        after = {
            "requirements.txt": ("100644", BASE),
            "requirements-audit.txt": ("100644", CANDIDATE),
            ".github/python/ruff.txt": ("100644", CANDIDATE),
            ".github/python/runtime.txt": ("100644", CANDIDATE),
            ".github/python/nested/fixture.txt": ("100644", CANDIDATE),
            "workdoe/private.txt": ("100644", CANDIDATE),
        }
        result = scope.python_dependency_inputs(before, after)
        self.assertFalse(result["unchanged"])
        self.assertEqual({item["path"]: item["status"] for item in result["files"]}, {
            "requirements.txt": "unchanged", "requirements-audit.txt": "modified",
            ".github/python/ruff.txt": "modified", ".github/python/old.txt": "removed",
            ".github/python/runtime.txt": "added",
        })
        self.assertEqual(result["package_version_changes"], "not_evaluated")
        self.assertTrue(scope.python_dependency_inputs(before, before)["unchanged"])
        missing = scope.python_dependency_inputs({}, {})
        self.assertFalse(missing["unchanged"])
        self.assertTrue(all(item["status"] == "missing" for item in missing["files"]))

    def test_license_and_notice_inputs_are_in_inventory_without_implying_clearance(self):
        self.assertIn("LICENSE", scope.SCOPE_PATHS)
        self.assertIn("THIRD_PARTY_NOTICES.md", scope.SCOPE_PATHS)
        self.assertIn("DEPENDENCY_PROVENANCE.json", scope.SCOPE_PATHS)
        self.assertIn(".github/python", scope.SCOPE_PATHS)


if __name__ == "__main__":
    unittest.main()
