import json
from django.test import TestCase, Client
from .models import ContactMessage


class ContactMessageModelTest(TestCase):
    def test_create_message(self):
        msg = ContactMessage.objects.create(name="Test User", email="test@example.com", message="Hello!")
        self.assertEqual(msg.name, "Test User")
        self.assertEqual(msg.email, "test@example.com")
        self.assertEqual(msg.message, "Hello!")


class ContactSubmitAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/contact/submit/"

    def test_successful_post(self):
        data = {"name": "Mario", "email": "mario@example.com", "message": "Ciao!"}
        response = self.client.post(self.url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["success"], True)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_invalid_email(self):
        data = {"name": "Mario", "email": "not-an-email", "message": "Ciao!"}
        response = self.client.post(self.url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    def test_honeypot(self):
        data = {"name": "Mario", "email": "mario@example.com", "message": "Ciao!", "honeypot": "spam"}
        response = self.client.post(self.url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
