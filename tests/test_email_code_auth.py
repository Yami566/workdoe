from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = ROOT / "cloudflare" / "worker"
AUTH_PATH = WORKER_ROOT / "email_code_auth.py"
ENTRY_SHELL_PATH = WORKER_ROOT / "entry_shell.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EmailCodeAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth = load_module("email_code_auth_test", AUTH_PATH)

    def setUp(self):
        self.secret = "test-secret-that-is-longer-than-thirty-two-characters"

    def test_code_hashing_is_deterministic_and_secret_bound(self):
        expected = self.auth.hash_code("123456", self.secret)
        self.assertEqual(expected, self.auth.hash_code("123456", self.secret))
        self.assertNotEqual(expected, self.auth.hash_code("654321", self.secret))
        self.assertTrue(self.auth.tokens_match(expected, expected))

    def test_challenge_and_session_tokens_round_trip(self):
        challenge = self.auth.challenge_token(42, " Person@Example.COM ", self.secret, now=100)
        challenge_payload = self.auth.verified_token(
            challenge,
            self.secret,
            "challenge",
            now=101,
        )
        self.assertEqual(challenge_payload["code_id"], 42)
        self.assertEqual(challenge_payload["email"], "person@example.com")

        session = self.auth.session_token(17, self.secret, now=100)
        session_payload = self.auth.session_from_cookie(
            f"theme=light; workdoe_session={session}",
            self.secret,
            now=101,
        )
        self.assertEqual(session_payload["user_id"], 17)

    def test_signed_tokens_reject_tampering_and_expiration(self):
        token = self.auth.challenge_token(42, "person@example.com", self.secret, now=100)
        with self.assertRaisesRegex(self.auth.EmailCodeAuthError, "invalid"):
            self.auth.verified_token(token[:-1] + "x", self.secret, "challenge", now=101)
        with self.assertRaisesRegex(self.auth.EmailCodeAuthError, "expired"):
            self.auth.verified_token(
                token,
                self.secret,
                "challenge",
                now=100 + self.auth.CHALLENGE_TTL_SECONDS + 1,
            )

    def test_session_cookie_uses_browser_security_flags(self):
        cookie = self.auth.session_cookie("signed-token")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Path=/", cookie)
        self.assertIn("Max-Age=604800", cookie)

    def test_safe_next_path_accepts_local_paths_only(self):
        self.assertEqual(self.auth.safe_next_path("/jobs/3?view=map"), "/jobs/3?view=map")
        for unsafe in ("https://example.com", "//example.com", "/\\example.com"):
            self.assertEqual(self.auth.safe_next_path(unsafe), "/dashboard")

    def test_native_entry_shell_stays_on_workdoe(self):
        sys.path.insert(0, str(WORKER_ROOT))
        try:
            shell = load_module("entry_shell_native_test", ENTRY_SHELL_PATH)
        finally:
            sys.path.pop(0)
        html = shell.build_entry_shell_html(
            "/login",
            {"next": "/jobs/3"},
            [],
            clerk_publishable_key="",
            clerk_frontend_api_url="",
            auth_provider=self.auth.AUTH_PROVIDER,
            turnstile_site_key="turnstile-site-key",
        )
        self.assertIn('data-request-url="/api/auth/code/request"', html)
        self.assertIn('data-verify-url="/api/auth/code/verify"', html)
        self.assertIn('data-sitekey="turnstile-site-key"', html)
        self.assertIn('/static/email-code-entry.js', html)
        self.assertNotIn('data-clerk-entry', html)
        self.assertNotIn('frontend-api.clerk.dev', html)


if __name__ == "__main__":
    unittest.main()
