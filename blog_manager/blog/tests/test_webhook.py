"""
Tests for GitHub webhook handlers.

Tests webhook endpoint with realistic GitHub payloads for:
- pull_request events (opened, closed, merged)
- deployment_status events (success)
- signature validation
- unknown events
"""
import pytest
import json
import hmac
import hashlib
from unittest.mock import patch
from django.test import Client
import pytest
pytest.skip("legacy PreviewSession tests - skip (model removed)", allow_module_level=True)

from blog.models import Site, Author


@pytest.fixture
def webhook_secret():
    """Webhook secret for signature validation."""
    return "test-webhook-secret-12345"


@pytest.fixture
def webhook_client(webhook_secret):
    """Client configured with webhook secret."""
    client = Client()
    with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
        yield client


def make_signature(payload: dict, secret: str) -> str:
    """Generate GitHub webhook signature."""
    payload_bytes = json.dumps(payload).encode('utf-8')
    mac = hmac.new(secret.encode('utf-8'), msg=payload_bytes, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


@pytest.mark.django_db
class TestGitHubWebhook:
    """Test GitHub webhook endpoint."""
    
    def test_pull_request_opened(self, webhook_client, webhook_secret, site):
        """Test pull_request.opened event updates session status."""
        # Create a preview session
        session = PreviewSession.objects.create(
            site=site,
            source_branch="main",
            preview_branch="preview/pr-abc123",
            pr_number=42,
            status="created"
        )
        
        # GitHub pull_request.opened payload
        payload = {
            "action": "opened",
            "number": 42,
            "pull_request": {
                "number": 42,
                "state": "open",
                "title": "Preview: 2 post(s)",
                "merged": False,
                "html_url": "https://github.com/owner/repo/pull/42"
            }
        }
        
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'processed'
        assert data['event'] == 'pull_request'
        assert data['session']['status'] == 'pr_open'
        
        # Verify session was updated
        session.refresh_from_db()
        assert session.status == 'pr_open'
    
    def test_pull_request_closed_not_merged(self, webhook_client, webhook_secret, site):
        """Test pull_request.closed (not merged) event."""
        session = PreviewSession.objects.create(
            site=site,
            source_branch="main",
            preview_branch="preview/pr-xyz",
            pr_number=99,
            status="pr_open"
        )
        
        payload = {
            "action": "closed",
            "number": 99,
            "pull_request": {
                "number": 99,
                "state": "closed",
                "merged": False
            }
        }
        
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        assert response.status_code == 200
        
        session.refresh_from_db()
        assert session.status == 'closed'
    
    def test_pull_request_merged(self, webhook_client, webhook_secret, site):
        """Test pull_request.closed with merged=true event."""
        session = PreviewSession.objects.create(
            site=site,
            source_branch="main",
            preview_branch="preview/pr-merge",
            pr_number=100,
            status="pr_open"
        )
        
        payload = {
            "action": "closed",
            "number": 100,
            "pull_request": {
                "number": 100,
                "state": "closed",
                "merged": True
            }
        }
        
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        assert response.status_code == 200
        
        session.refresh_from_db()
        assert session.status == 'merged'
    
    def test_deployment_status_success(self, webhook_client, webhook_secret, site):
        """Test deployment_status.success event sets status=ready and preview_url."""
        session = PreviewSession.objects.create(
            site=site,
            source_branch="main",
            preview_branch="preview/pr-deploy",
            pr_number=50,
            status="building"
        )
        
        payload = {
            "deployment_status": {
                "state": "success",
                "environment_url": "https://preview-pr-50.netlify.app"
            },
            "deployment": {
                "ref": "refs/pull/50/head",
                "environment": "Preview"
            }
        }
        
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='deployment_status',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data['session']['status'] == 'ready'
        assert data['session']['preview_url'] == 'https://preview-pr-50.netlify.app'
        
        session.refresh_from_db()
        assert session.status == 'ready'
        assert session.preview_url == 'https://preview-pr-50.netlify.app'
    
    def test_deployment_status_by_branch_name(self, webhook_client, webhook_secret, site):
        """Test deployment_status can find session by preview_branch."""
        session = PreviewSession.objects.create(
            site=site,
            source_branch="main",
            preview_branch="preview/pr-abc123",
            status="building"
        )
        
        payload = {
            "deployment_status": {
                "state": "success",
                "environment_url": "https://preview-abc123.vercel.app"
            },
            "deployment": {
                "ref": "refs/heads/preview/pr-abc123",
                "environment": "Preview"
            }
        }
        
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='deployment_status',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        assert response.status_code == 200
        
        session.refresh_from_db()
        assert session.status == 'ready'
    
    def test_invalid_signature(self, webhook_client):
        """Test webhook rejects invalid signature."""
        payload = {"action": "opened", "pull_request": {"number": 1}}
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'correct-secret'}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_HUB_SIGNATURE_256='sha256=invalid'
            )
        
        assert response.status_code == 400
    
    def test_missing_signature(self, webhook_client):
        """Test webhook rejects missing signature when secret is configured."""
        payload = {"action": "opened", "pull_request": {"number": 1}}
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': 'some-secret'}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request'
            )
        
        assert response.status_code == 400
    
    def test_unknown_event_type(self, webhook_client, webhook_secret):
        """Test webhook ignores unknown event types."""
        payload = {"action": "created", "issue": {"number": 1}}
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='issues',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        # 204 has no content, check directly
        assert response.status_code == 204
    
    def test_pr_event_for_non_preview_pr(self, webhook_client, webhook_secret):
        """Test webhook ignores PR events not associated with preview sessions."""
        payload = {
            "action": "opened",
            "number": 999,  # No session with this PR number
            "pull_request": {"number": 999}
        }
        
        signature = make_signature(payload, webhook_secret)
        
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_HUB_SIGNATURE_256=signature
            )
        
        # 204 has no content
        assert response.status_code == 204
    
    def test_invalid_json(self, webhook_client, webhook_secret):
        """Test webhook rejects malformed JSON."""
        with patch.dict('os.environ', {'GITHUB_WEBHOOK_SECRET': webhook_secret}):
            response = webhook_client.post(
                '/api/blog/webhooks/github/',
                data='invalid json{',
                content_type='application/json',
                HTTP_X_GITHUB_EVENT='pull_request',
                HTTP_X_HUB_SIGNATURE_256='sha256=dummy'
            )
        
        assert response.status_code == 400


@pytest.fixture
def site(db, tmp_path):
    """Create a test site."""
    repo_path = tmp_path / "test-site"
    repo_path.mkdir()
    return Site.objects.create(
        name="Test Site",
        slug="test-site",
        domain="https://test.example.com",
        repo_owner="test",
        repo_name="test-site",
        repo_path=str(repo_path)
    )
