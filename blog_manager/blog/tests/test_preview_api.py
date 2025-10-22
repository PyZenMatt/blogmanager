"""
Tests for PreviewSession API endpoints.

This test module references the legacy PreviewSession model which was removed
as part of the preview PR -> per-site preview migration. Skip these tests
until they are rewritten for the new preview system.
"""
import pytest

pytest.skip("legacy PreviewSession tests - skip (model removed)", allow_module_level=True)

from rest_framework.test import APIClient
from blog.models import Site


@pytest.mark.django_db
class TestPreviewSessionAPI:
    """Test PreviewSession ViewSet endpoints."""
    
    def test_list_preview_sessions(self):
        """Test GET /api/preview-sessions/ returns all sessions."""
        client = APIClient()
        response = client.get('/api/preview-sessions/')
        
        assert response.status_code == 200
        data = response.json()
        # DRF pagination wraps results
        assert 'results' in data
        assert isinstance(data['results'], list)
    
    def test_retrieve_preview_session(self, preview_session):
        """Test GET /api/preview-sessions/{uuid}/ returns session detail."""
        client = APIClient()
        response = client.get(f'/api/preview-sessions/{preview_session.uuid}/')
        
        assert response.status_code == 200
        data = response.json()
        assert data['uuid'] == str(preview_session.uuid)
        assert data['status'] == preview_session.status
        assert data['site_name'] == preview_session.site.name
    
    def test_filter_by_status(self, preview_session):
        """Test filtering by status works."""
        client = APIClient()
        
        # Filter by exact status
        response = client.get(f'/api/preview-sessions/?status={preview_session.status}')
        assert response.status_code == 200
        data = response.json()
        results = data['results']
        assert len(results) >= 1
        assert all(item['status'] == preview_session.status for item in results)
    
    def test_filter_by_site(self, preview_session):
        """Test filtering by site works."""
        client = APIClient()
        
        response = client.get(f'/api/preview-sessions/?site={preview_session.site.id}')
        assert response.status_code == 200
        data = response.json()
        results = data['results']
        assert len(results) >= 1
        assert all(item['site'] == preview_session.site.id for item in results)
    
    def test_exclude_status(self, preview_session):
        """Test ?status__ne=closed excludes closed sessions."""
        client = APIClient()
        
        # Create a closed session
        site = preview_session.site
        closed = PreviewSession.objects.create(
            site=site,
            source_branch="main",
            preview_branch="preview/test-closed",
            status="closed"
        )
        
        # Query excluding closed
        response = client.get('/api/preview-sessions/?status__ne=closed')
        assert response.status_code == 200
        data = response.json()
        results = data['results']
        
        # Should not include closed session
        uuids = [item['uuid'] for item in results]
        assert str(closed.uuid) not in uuids
        assert str(preview_session.uuid) in uuids
    
    def test_ordering_by_updated_at(self, preview_session):
        """Test default ordering is by -updated_at."""
        client = APIClient()
        
        response = client.get('/api/preview-sessions/')
        assert response.status_code == 200
        data = response.json()
        results = data['results']
        
        if len(results) > 1:
            # Check descending order
            timestamps = [item['updated_at'] for item in results]
            assert timestamps == sorted(timestamps, reverse=True)


@pytest.fixture
def preview_session(db):
    """Create a test preview session."""
    site = Site.objects.first()
    if not site:
        site = Site.objects.create(
            name="Test Site",
            domain="https://test.example.com",
            slug="test-site"
        )
    
    session = PreviewSession.objects.create(
        site=site,
        source_branch="main",
        preview_branch="preview/test-123",
        status="ready"
    )
    return session
