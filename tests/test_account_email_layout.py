from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

import test_dashboard_access
from test_cloudflare_release import load_app_shell_module

ROOT = Path(__file__).resolve().parents[1]


class EmailFieldParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "dd" and "account-email" in attributes.get("class", "").split():
            self.fields.append(attributes)


class AccountEmailLayoutTests(unittest.TestCase):
    def test_worker_email_is_keyboard_reachable_and_escaped(self):
        module = load_app_shell_module()
        html = module.account_security_html(
            {"id": 1, "role": "client", "email": 'a<unsafe>@example.invalid'}
        )
        parser = EmailFieldParser()
        parser.feed(html)
        self.assertEqual(len(parser.fields), 1)
        self.assertEqual(parser.fields[0].get("tabindex"), "0")
        self.assertIn("a&lt;unsafe&gt;@example.invalid", html)
        self.assertNotIn("a<unsafe>", html)

    def test_flask_email_uses_the_same_reachable_field(self):
        helper = test_dashboard_access.DashboardAccessTests()
        with helper.fixture() as fixture:
            with fixture.client.session_transaction() as session:
                session["user_id"] = 1
            response = fixture.client.get("/account")
            self.assertEqual(response.status_code, 200)
            parser = EmailFieldParser()
            parser.feed(response.get_data(as_text=True))
            self.assertEqual(len(parser.fields), 1)
            self.assertEqual(parser.fields[0].get("tabindex"), "0")

    def test_email_style_is_scoped_and_keeps_full_single_line_text(self):
        styles = (ROOT / "workdoe/static/styles.css").read_text(encoding="utf-8")
        selector = r"\.account-summary \.account-email\s*\{([^}]+)\}"
        declarations = re.search(selector, styles).group(1)
        for rule in ("white-space: nowrap;", "overflow-x: auto;", "max-width: 100%;"):
            self.assertIn(rule, declarations)
        self.assertNotIn("text-overflow: ellipsis", declarations)
        self.assertNotIn("font-size", declarations)
        self.assertRegex(
            styles,
            r"\.account-summary \.profile-facts > div\s*\{[^}]*"
            r"grid-template-columns: minmax\(0, 1fr\);",
        )
