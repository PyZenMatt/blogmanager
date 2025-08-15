from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from writer.middleware import LoginRateLimitMiddleware


class LoginRateLimitMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = LoginRateLimitMiddleware(lambda req: HttpResponse(status=200))
        cache.clear()

    def test_rate_limit_exceeded(self):
        for _ in range(5):
            request = self.factory.post(
                "/writer/login/",
                {"username": "testuser"},
            )
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

        # 6th attempt should be blocked
        request = self.factory.post(
            "/writer/login/",
            {"username": "testuser"},
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 429)
        self.assertIn(
            b"Troppi tentativi",
            response.content,
        )

    def test_reset_on_successful_login(self):
        for _ in range(3):
            request = self.factory.post(
                "/writer/login/",
                {"username": "testuser"},
            )
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

        # Simulate successful login
        self.middleware = LoginRateLimitMiddleware(lambda req: HttpResponse(status=302))
        request = self.factory.post(
            "/writer/login/",
            {"username": "testuser"},
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)

        # Ensure counter is reset
        request = self.factory.post(
            "/writer/login/",
            {"username": "testuser"},
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_different_users_and_ips(self):
        for _ in range(5):
            request = self.factory.post("/writer/login/", {"username": "user1"})
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)

        # Another user should not be blocked
        request = self.factory.post("/writer/login/", {"username": "user2"})
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

        # Another IP should not be blocked
        request = self.factory.post(
            "/writer/login/",
            {"username": "user2"},
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.status_code, 200)
