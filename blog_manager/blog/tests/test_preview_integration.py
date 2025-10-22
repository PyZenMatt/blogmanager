"""
Integration tests for preview session kickoff with GitHub PR creation.

Tests the full flow: API endpoint → service layer → git operations → GitHub API.
"""
import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
import pytest
pytest.skip("legacy PreviewSession tests - skip (model removed)", allow_module_level=True)

from blog.models import Site, Post, Author, Category


@pytest.fixture
def site(db, tmp_path):
    """Create a test site with a temporary repo path."""
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


@pytest.fixture
def author(db):
    """Create a test author."""
    return Author.objects.create(
        name="Test Author",
        slug="test-author"
    )


@pytest.fixture
def post_factory(db):
    """Factory for creating test posts."""
    def _create_post(site, author, title, status, categories):
        # Create front-matter with categories
        # Extract cluster and subcluster from first category path
        if categories:
            first_cat = categories[0]
            parts = first_cat.split('/')
            cluster = parts[0]
            subcluster = parts[1] if len(parts) > 1 else None
        else:
            cluster = "uncategorized"
            subcluster = None
        
        # Build front-matter
        fm_parts = [
            "---",
            f"title: {title}",
            f"categories: [{cluster}]"
        ]
        if subcluster:
            fm_parts.append(f"subcluster: {subcluster}")
        fm_parts.extend(["---", "", f"Test content for {title}"])
        
        content = '\n'.join(fm_parts)
        
        post = Post.objects.create(
            site=site,
            author=author,
            title=title,
            slug=title.lower().replace(' ', '-'),
            status=status,
            content=content
        )
        # Add categories to post.categories relation
        for cat_path in categories:
            parts = cat_path.split('/')
            cluster_slug = parts[0]
            subcluster_slug = parts[1] if len(parts) > 1 else None
            cat, _ = Category.objects.get_or_create(
                site=site,
                cluster_slug=cluster_slug,
                subcluster_slug=subcluster_slug
            )
            post.categories.add(cat)
        return post
    
    return _create_post


@pytest.mark.django_db
class TestPreviewKickoffIntegration:
    """Test the complete preview kickoff workflow."""
    
    def test_preview_kickoff_success(self, site, post_factory, author):
        """Test successful preview kickoff creates session and PR."""
        # Setup
        post1 = post_factory(
            site=site,
            author=author,
            title="Test Post 1",
            status="published",
            categories=["tech/python"]
        )
        post2 = post_factory(
            site=site,
            author=author,
            title="Test Post 2",
            status="published",
            categories=["tech/django"]
        )
        
        client = APIClient()
        # DRF router action URL pattern: /api/sites/{id}/preview/
        url = f'/api/sites/{site.pk}/preview/'
        
        # Mock git operations and GitHub API
        with patch('blog.services.preview_service.subprocess.run') as mock_subprocess, \
             patch('blog.views.GitHubClient') as mock_gh_class:
            
            # Mock git commands to succeed
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout=b'abc123commit',
                stderr=b''
            )
            
            # Mock GitHub client
            mock_gh = MagicMock()
            mock_gh.create_pull_request.return_value = {
                'number': 42,
                'html_url': 'https://github.com/owner/repo/pull/42'
            }
            mock_gh_class.return_value = mock_gh
            
            # Make request
            response = client.post(url, {
                'post_ids': [post1.pk, post2.pk],
                'source_branch': 'main'
            }, format='json')
        
        # Assertions
        assert response.status_code == 201
        data = response.json()
        
        assert 'uuid' in data
        assert data['pr_number'] == 42
        assert data['preview_url'] == 'https://github.com/owner/repo/pull/42'
        assert data['status'] == 'pr_open'
        assert 'preview_branch' in data
        
        # Verify session was created and updated
        session = PreviewSession.objects.get(uuid=data['uuid'])
        assert session.pr_number == 42
        assert session.status == 'pr_open'
        assert session.preview_url == 'https://github.com/owner/repo/pull/42'
        
        # Verify GitHub client was called correctly
        mock_gh.create_pull_request.assert_called_once()
        call_kwargs = mock_gh.create_pull_request.call_args[1]
        assert call_kwargs['head'].startswith('preview/pr-')
        assert call_kwargs['base'] == 'main'
    
    def test_preview_kickoff_validation_error(self, site, author):
        """Test preview kickoff fails when post validation fails."""
        # Create post with invalid front-matter (multiple clusters)
        content = """---
title: Invalid Post
categories: [tech, life]
---

Test content
"""
        post = Post.objects.create(
            site=site,
            author=author,
            title="Invalid Post",
            slug="invalid-post",
            status="published",
            content=content
        )
        
        # Add matching categories to DB (even though FM is invalid)
        for cluster in ['tech', 'life']:
            cat, _ = Category.objects.get_or_create(
                site=site,
                cluster_slug=cluster
            )
            post.categories.add(cat)
        
        client = APIClient()
        url = f'/api/sites/{site.pk}/preview/'
        
        response = client.post(url, {
            'post_ids': [post.pk],
            'source_branch': 'main'
        }, format='json')
        
        # Should return error
        assert response.status_code == 500
        assert 'detail' in response.json()
        
        # Verify session was created but status is 'error'
        sessions = PreviewSession.objects.filter(site=site)
        assert sessions.count() == 1
        session = sessions.first()
        assert session.status == 'error'
        assert 'multiple clusters' in session.last_error.lower()
    
    def test_preview_kickoff_github_error(self, site, post_factory, author):
        """Test preview kickoff handles GitHub API errors gracefully."""
        post = post_factory(
            site=site,
            author=author,
            title="Test Post",
            status="published",
            categories=["tech/python"]
        )
        
        client = APIClient()
        url = f'/api/sites/{site.pk}/preview/'
        
        with patch('blog.services.preview_service.subprocess.run') as mock_subprocess, \
             patch('blog.views.GitHubClient') as mock_gh_class:
            
            # Git operations succeed
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout=b'abc123commit',
                stderr=b''
            )
            
            # GitHub API fails
            mock_gh = MagicMock()
            from github import GithubException
            mock_gh.create_pull_request.side_effect = GithubException(
                403,
                {"message": "Forbidden"}
            )
            mock_gh_class.return_value = mock_gh
            
            response = client.post(url, {
                'post_ids': [post.pk],
                'source_branch': 'main'
            }, format='json')
        
        # Should return error
        assert response.status_code == 500
        data = response.json()
        assert 'detail' in data
        assert 'failed' in data['detail'].lower()
        
        # Session should be in error state
        sessions = PreviewSession.objects.filter(site=site)
        assert sessions.count() == 1
        session = sessions.first()
        assert session.status == 'error'
        assert session.last_error is not None
    
    def test_preview_kickoff_git_push_error(self, site, post_factory, author):
        """Test preview kickoff handles git push errors."""
        post = post_factory(
            site=site,
            author=author,
            title="Test Post",
            status="published",
            categories=["tech/python"]
        )
        
        client = APIClient()
        url = f'/api/sites/{site.pk}/preview/'
        
        with patch('blog.services.preview_service.subprocess.run') as mock_subprocess:
            # Make git push fail
            def subprocess_side_effect(cmd, **kwargs):
                if 'push' in cmd:
                    from subprocess import CalledProcessError
                    raise CalledProcessError(1, cmd, stderr=b'Permission denied')
                return MagicMock(returncode=0, stdout=b'abc123', stderr=b'')
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            response = client.post(url, {
                'post_ids': [post.pk],
                'source_branch': 'main'
            }, format='json')
        
        # Should return error
        assert response.status_code == 500
        data = response.json()
        assert 'detail' in data
        
        # Session should be in error state
        sessions = PreviewSession.objects.filter(site=site)
        assert sessions.count() == 1
        session = sessions.first()
        assert session.status == 'error'
        assert 'push' in session.last_error.lower()
    
    def test_preview_kickoff_defaults_to_all_published(self, site, post_factory, author):
        """Test preview kickoff defaults to all published posts when post_ids not provided."""
        post1 = post_factory(
            site=site,
            author=author,
            title="Published 1",
            status="published",
            categories=["tech/python"]
        )
        post2 = post_factory(
            site=site,
            author=author,
            title="Published 2",
            status="published",
            categories=["tech/django"]
        )
        # Draft post should not be included
        post_factory(
            site=site,
            author=author,
            title="Draft",
            status="draft",
            categories=["tech/other"]
        )
        
        client = APIClient()
        url = f'/api/sites/{site.pk}/preview/'
        
        with patch('blog.services.preview_service.subprocess.run') as mock_subprocess, \
             patch('blog.views.GitHubClient') as mock_gh_class:
            
            mock_subprocess.return_value = MagicMock(
                returncode=0,
                stdout=b'abc123commit',
                stderr=b''
            )
            
            mock_gh = MagicMock()
            mock_gh.create_pull_request.return_value = {
                'number': 99,
                'html_url': 'https://github.com/owner/repo/pull/99'
            }
            mock_gh_class.return_value = mock_gh
            
            # Don't provide post_ids - should default to all published
            response = client.post(url, {
                'source_branch': 'main'
            }, format='json')
        
        assert response.status_code == 201
        data = response.json()
        assert data['pr_number'] == 99
        
        # Verify session was created
        session = PreviewSession.objects.get(uuid=data['uuid'])
        assert session.status == 'pr_open'
    
    def test_preview_kickoff_requires_authentication(self, site, post_factory, author):
        """Test preview kickoff endpoint validation with empty post list."""
        # Don't provide any posts - should fail validation
        client = APIClient()
        url = f'/api/sites/{site.pk}/preview/'
        
        # Create at least one post so we can test with empty post_ids
        post_factory(
            site=site,
            author=author,
            title="Test Post",
            status="published",
            categories=["tech/python"]
        )
        
        response = client.post(url, {
            'post_ids': [],  # Explicitly empty list
            'source_branch': 'main'
        }, format='json')
        
        # Should return error for empty post list
        assert response.status_code == 500
        assert 'detail' in response.json()
        assert 'no posts' in response.json()['detail'].lower()
