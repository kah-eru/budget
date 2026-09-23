from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("login-user", password="synthetic-password")

    def test_login_logout_and_session_continuity(self):
        response = self.client.post("/login/", {"username": "login-user", "password": "synthetic-password"})
        self.assertEqual(response.status_code, 302)
        second_client = Client()
        second_client.cookies = self.client.cookies
        self.assertEqual(second_client.get("/").status_code, 302)
        self.assertNotIn("/login/", second_client.get("/")["Location"])
        self.assertEqual(self.client.get("/logout/").status_code, 405)
        self.assertEqual(self.client.post("/logout/").status_code, 302)
        self.assertIn("/login/", self.client.get("/")["Location"])

    def test_five_failed_logins_block_even_a_correct_password(self):
        for _ in range(5):
            self.client.post("/login/", {"username": "login-user", "password": "incorrect"})
        response = self.client.post("/login/", {"username": "login-user", "password": "synthetic-password"})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_external_redirect_and_public_signup_is_absent(self):
        response = self.client.post("/login/", {"username": "login-user", "password": "synthetic-password", "next": "https://example.invalid"})
        self.assertEqual(response["Location"], "/")
        self.assertEqual(self.client.get("/signup/").status_code, 404)

    def test_health_readiness_and_login_are_noindex(self):
        for path in ["/health/", "/ready/", "/login/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")
            self.assertIn("no-store", response["Cache-Control"])
