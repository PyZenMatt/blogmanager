"""Tests for the contact form honeypot functionality."""
import json
import pytest

from contact.models import ContactMessage


@pytest.mark.django_db
class TestContactHoneypot:
    """Test cases for honeypot spam filtering."""

    url = "/api/contact/submit/"

    def test_honeypot_website_field_triggers_silent_drop(self, client):
        """Test that filling the 'website' honeypot field silently drops the request."""
        data = {
            "name": "Mario",
            "email": "mario@example.com",
            "message": "Ciao!",
            "website": "http://spam.example.com",
        }
        response = client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )
        # Should return 200 OK to not signal bots
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        # Message should NOT be saved to DB
        assert ContactMessage.objects.count() == 0

    def test_honeypot_empty_website_allows_submission(self, client, settings, mailoutbox):
        """Test that empty 'website' field allows normal form submission."""
        # Configure required settings for email sending
        settings.CONTACT_RECIPIENTS = ["admin@example.com"]
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"

        data = {
            "name": "Mario",
            "email": "mario@example.com",
            "message": "Ciao!",
            "website": "",
        }
        response = client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert ContactMessage.objects.count() == 1

    def test_honeypot_missing_website_allows_submission(self, client, settings, mailoutbox):
        """Test that missing 'website' field allows normal form submission."""
        # Configure required settings for email sending
        settings.CONTACT_RECIPIENTS = ["admin@example.com"]
        settings.DEFAULT_FROM_EMAIL = "noreply@example.com"

        data = {
            "name": "Luigi",
            "email": "luigi@example.com",
            "message": "Hello world!",
        }
        response = client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert ContactMessage.objects.count() == 1
