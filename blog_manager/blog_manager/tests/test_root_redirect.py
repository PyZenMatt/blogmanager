from django.test import TestCase, Client
from django.urls import reverse


class RootRedirectTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_redirects_anonymous_to_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/writer/login", response["Location"])

    def test_redirects_authenticated_to_post_new(self):
        from django.contrib.auth.models import User

        user = User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/writer/new", response["Location"])
