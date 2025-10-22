"""
Tests for preview session close and merge actions.

Tests the close/merge endpoints and service layer logic with mocked GitHub API.
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
import pytest
pytest.skip("legacy PreviewSession tests - skip (model removed)", allow_module_level=True)

from blog.models import Site
from blog.services.preview_service import close_preview_session, merge_preview_session


@pytest.fixture
def site(db):
    """Create a test site."""
    return Site.objects.create(
        name="Test Site",
        slug="test-site",
        domain="https://test.example.com",
        repo_owner="testowner",
        repo_name="test-repo"
    )


@pytest.fixture
def preview_session(site):
    """Create a preview session with PR number."""
    return PreviewSession.objects.create(
        site=site,
        source_branch='main',
        preview_branch='preview/pr-test123',
        pr_number=42,
        status='pr_open'
    )


class TestClosePreviewSession:
    """Tests for close_preview_session service function."""
    
    @patch('blog.github_client.GitHubClient')
    def test_close_preview_success(self, mock_gh_class, preview_session):
        """Test successful PR close."""
        # Setup mock
        mock_gh = MagicMock()
        mock_gh.close_pull_request.return_value = {
            'number': 42,
            'state': 'closed',
            'html_url': 'https://github.com/owner/repo/pull/42'
        }
        mock_gh_class.return_value = mock_gh
        
        # Execute
        result = close_preview_session(preview_session)
        
        # Verify
        assert result.status == 'closed'
        assert result.pr_number == 42
        mock_gh.close_pull_request.assert_called_once_with(
            owner='testowner',
            repo='test-repo',
            pr_number=42
        )
    
    def test_close_preview_no_pr_number(self, preview_session):
        """Test close fails when session has no PR number."""
        preview_session.pr_number = None
        preview_session.save()
        
        with pytest.raises(ValueError, match="no PR number"):
            close_preview_session(preview_session)
    
    def test_close_preview_already_closed(self, preview_session):
        """Test close fails when session already closed."""
        preview_session.status = 'closed'
        preview_session.save()
        
        with pytest.raises(ValueError, match="already in terminal state"):
            close_preview_session(preview_session)
    
    def test_close_preview_already_merged(self, preview_session):
        """Test close fails when session already merged."""
        preview_session.status = 'merged'
        preview_session.save()
        
        with pytest.raises(ValueError, match="already in terminal state"):
            close_preview_session(preview_session)
    
    @patch('blog.github_client.GitHubClient')
    def test_close_preview_github_api_error(self, mock_gh_class, preview_session):
        """Test close propagates GitHub API errors."""
        from github import GithubException
        
        mock_gh = MagicMock()
        mock_gh.close_pull_request.side_effect = GithubException(
            404, {'message': 'Not found'}
        )
        mock_gh_class.return_value = mock_gh
        
        with pytest.raises(Exception):
            close_preview_session(preview_session)


class TestMergePreviewSession:
    """Tests for merge_preview_session service function."""
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_preview_success(self, mock_gh_class, preview_session):
        """Test successful PR merge."""
        preview_session.status = 'ready'
        preview_session.save()
        
        # Setup mock
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.return_value = {
            'merged': True,
            'sha': 'abc123',
            'message': 'Pull Request successfully merged'
        }
        mock_gh_class.return_value = mock_gh
        
        # Execute
        result = merge_preview_session(preview_session, "Custom merge message")
        
        # Verify
        assert result.status == 'merged'
        assert result.pr_number == 42
        mock_gh.merge_pull_request.assert_called_once_with(
            owner='testowner',
            repo='test-repo',
            pr_number=42,
            commit_message="Custom merge message"
        )
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_preview_default_message(self, mock_gh_class, preview_session):
        """Test merge with default commit message."""
        preview_session.status = 'ready'
        preview_session.save()
        
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.return_value = {
            'merged': True,
            'sha': 'def456',
            'message': 'Merged'
        }
        mock_gh_class.return_value = mock_gh
        
        result = merge_preview_session(preview_session)
        
        # Verify default message includes PR number and branch
        call_args = mock_gh.merge_pull_request.call_args
        assert 'PR #42' in call_args.kwargs['commit_message']
        assert 'preview/pr-test123' in call_args.kwargs['commit_message']
    
    def test_merge_preview_no_pr_number(self, preview_session):
        """Test merge fails when session has no PR number."""
        preview_session.pr_number = None
        preview_session.save()
        
        with pytest.raises(ValueError, match="no PR number"):
            merge_preview_session(preview_session)
    
    def test_merge_preview_already_merged(self, preview_session):
        """Test merge fails when session already merged."""
        preview_session.status = 'merged'
        preview_session.save()
        
        with pytest.raises(ValueError, match="already merged"):
            merge_preview_session(preview_session)
    
    def test_merge_preview_already_closed(self, preview_session):
        """Test merge fails when PR already closed."""
        preview_session.status = 'closed'
        preview_session.save()
        
        with pytest.raises(ValueError, match="already closed"):
            merge_preview_session(preview_session)
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_preview_merge_failed(self, mock_gh_class, preview_session):
        """Test merge handles GitHub merge failure."""
        preview_session.status = 'ready'
        preview_session.save()
        
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.return_value = {
            'merged': False,
            'sha': None,
            'message': 'Merge conflict detected'
        }
        mock_gh_class.return_value = mock_gh
        
        with pytest.raises(Exception, match="PR merge failed"):
            merge_preview_session(preview_session)
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_preview_github_api_error(self, mock_gh_class, preview_session):
        """Test merge propagates GitHub API errors."""
        from github import GithubException
        
        preview_session.status = 'ready'
        preview_session.save()
        
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.side_effect = GithubException(
            422, {'message': 'Validation Failed'}
        )
        mock_gh_class.return_value = mock_gh
        
        with pytest.raises(Exception):
            merge_preview_session(preview_session)


class TestCloseEndpoint:
    """Tests for POST /api/preview-sessions/{uuid}/close/ endpoint."""
    
    @patch('blog.github_client.GitHubClient')
    def test_close_endpoint_success(self, mock_gh_class, preview_session, django_user_model):
        """Test close endpoint returns updated session."""
        mock_gh = MagicMock()
        mock_gh.close_pull_request.return_value = {
            'number': 42,
            'state': 'closed',
            'html_url': 'https://github.com/owner/repo/pull/42'
        }
        mock_gh_class.return_value = mock_gh
        
        # Authenticate as staff user
        user = django_user_model.objects.create_user(username='testuser', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/close/'
        
        response = client.post(url)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'closed'
        assert data['pr_number'] == 42
    
    @patch('blog.github_client.GitHubClient')
    def test_close_endpoint_no_pr_number(self, mock_gh_class, preview_session, django_user_model):
        """Test close endpoint returns 400 when no PR number."""
        preview_session.pr_number = None
        preview_session.save()
        
        user = django_user_model.objects.create_user(username='testuser2', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/close/'
        
        response = client.post(url)
        
        assert response.status_code == 400
        assert 'no PR number' in response.json()['detail']
    
    def test_close_endpoint_not_found(self, django_user_model):
        """Test close endpoint returns 404 for non-existent session."""
        user = django_user_model.objects.create_user(username='testuser3', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = '/api/preview-sessions/00000000-0000-0000-0000-000000000000/close/'
        
        response = client.post(url)
        
        assert response.status_code == 404
    
    @patch('blog.github_client.GitHubClient')
    def test_close_endpoint_github_error(self, mock_gh_class, preview_session, django_user_model):
        """Test close endpoint returns 500 on GitHub API error."""
        from github import GithubException
        
        mock_gh = MagicMock()
        mock_gh.close_pull_request.side_effect = GithubException(
            403, {'message': 'Forbidden'}
        )
        mock_gh_class.return_value = mock_gh
        
        user = django_user_model.objects.create_user(username='testuser4', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/close/'
        
        response = client.post(url)
        
        assert response.status_code == 500
        assert 'Failed to close PR' in response.json()['detail']


class TestMergeEndpoint:
    """Tests for POST /api/preview-sessions/{uuid}/merge/ endpoint."""
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_endpoint_success(self, mock_gh_class, preview_session, django_user_model):
        """Test merge endpoint returns updated session."""
        preview_session.status = 'ready'
        preview_session.save()
        
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.return_value = {
            'merged': True,
            'sha': 'abc123',
            'message': 'Merged'
        }
        mock_gh_class.return_value = mock_gh
        
        user = django_user_model.objects.create_user(username='mergeuser1', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/merge/'
        
        response = client.post(url, {'commit_message': 'Test merge'}, format='json')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'merged'
        assert data['pr_number'] == 42
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_endpoint_no_commit_message(self, mock_gh_class, preview_session, django_user_model):
        """Test merge endpoint works without commit message."""
        preview_session.status = 'ready'
        preview_session.save()
        
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.return_value = {
            'merged': True,
            'sha': 'def456',
            'message': 'Merged'
        }
        mock_gh_class.return_value = mock_gh
        
        user = django_user_model.objects.create_user(username='mergeuser2', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/merge/'
        
        response = client.post(url)
        
        assert response.status_code == 200
        assert response.json()['status'] == 'merged'
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_endpoint_already_merged(self, mock_gh_class, preview_session, django_user_model):
        """Test merge endpoint returns 400 when already merged."""
        preview_session.status = 'merged'
        preview_session.save()
        
        user = django_user_model.objects.create_user(username='mergeuser3', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/merge/'
        
        response = client.post(url)
        
        assert response.status_code == 400
        assert 'already merged' in response.json()['detail']
    
    def test_merge_endpoint_not_found(self, django_user_model):
        """Test merge endpoint returns 404 for non-existent session."""
        user = django_user_model.objects.create_user(username='mergeuser4', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = '/api/preview-sessions/00000000-0000-0000-0000-000000000000/merge/'
        
        response = client.post(url)
        
        assert response.status_code == 404
    
    @patch('blog.github_client.GitHubClient')
    def test_merge_endpoint_github_error(self, mock_gh_class, preview_session, django_user_model):
        """Test merge endpoint returns 500 on GitHub API error."""
        from github import GithubException
        
        preview_session.status = 'ready'
        preview_session.save()
        
        mock_gh = MagicMock()
        mock_gh.merge_pull_request.side_effect = GithubException(
            422, {'message': 'Not mergeable'}
        )
        mock_gh_class.return_value = mock_gh
        
        user = django_user_model.objects.create_user(username='mergeuser5', password='pass', is_staff=True)
        
        client = APIClient()
        client.force_authenticate(user=user)
        url = f'/api/preview-sessions/{preview_session.uuid}/merge/'
        
        response = client.post(url)
        
        assert response.status_code == 500
        assert 'Failed to merge PR' in response.json()['detail']
