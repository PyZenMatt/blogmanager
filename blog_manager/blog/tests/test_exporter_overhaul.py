import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from datetime import datetime, timezone as tz

from blog.exporter import (
    _extract_frontmatter_from_body,
    _validate_frontmatter_taxonomy,
    FrontMatterValidationError,
    build_post_relpath,
    _handle_file_move,
    render_markdown,
    export_post
)
from blog.models import Site, Post, Author


class TestFrontMatterValidation(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site",
            slug="test-site",
            domain="example.com"
        )
        self.author = Author.objects.create(
            site=self.site,
            name="Test Author",
            slug="test-author"
        )
        self.post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="Test content",
            author=self.author
        )

    def test_extract_frontmatter_valid(self):
        """Test extracting valid front-matter."""
        body = """---
categories: [django]
subcluster: tutorials
title: Django Guide
---
This is the content."""
        
        fm = _extract_frontmatter_from_body(body)
        self.assertEqual(fm['categories'], ['django'])
        self.assertEqual(fm['subcluster'], 'tutorials')
        self.assertEqual(fm['title'], 'Django Guide')

    def test_extract_frontmatter_empty(self):
        """Test extracting from body without front-matter."""
        body = "Just content without front-matter"
        fm = _extract_frontmatter_from_body(body)
        self.assertEqual(fm, {})

    def test_validate_encoding_bom_error(self):
        """Test that BOM content raises validation error."""
        body = "\ufeff---\ncategories: [test]\n---\nContent"
        with self.assertRaises(FrontMatterValidationError) as cm:
            _extract_frontmatter_from_body(body)
        self.assertIn("BOM", str(cm.exception))

    def test_validate_encoding_crlf_error(self):
        """Test that CRLF line endings raise validation error."""
        body = "---\r\ncategories: [test]\r\n---\r\nContent"
        with self.assertRaises(FrontMatterValidationError) as cm:
            _extract_frontmatter_from_body(body)
        self.assertIn("CRLF", str(cm.exception))

    def test_validate_taxonomy_valid_cluster_only(self):
        """Test validation with valid cluster only."""
        fm_data = {'categories': ['django']}
        cluster, subcluster, audit = _validate_frontmatter_taxonomy(self.post, fm_data)
        
        self.assertEqual(cluster, 'django')
        self.assertIsNone(subcluster)
        self.assertEqual(len(audit), 1)

    def test_validate_taxonomy_valid_cluster_and_subcluster(self):
        """Test validation with valid cluster and subcluster."""
        fm_data = {
            'categories': ['django'],
            'subcluster': 'tutorials'
        }
        cluster, subcluster, audit = _validate_frontmatter_taxonomy(self.post, fm_data)
        
        self.assertEqual(cluster, 'django')
        self.assertEqual(subcluster, 'tutorials')
        self.assertEqual(len(audit), 1)

    def test_validate_taxonomy_no_frontmatter(self):
        """Test validation fails with no front-matter."""
        with self.assertRaises(FrontMatterValidationError) as cm:
            _validate_frontmatter_taxonomy(self.post, None)
        self.assertIn("No valid front-matter found", str(cm.exception))

    def test_validate_taxonomy_missing_categories(self):
        """Test validation fails with missing categories."""
        fm_data = {'title': 'Test'}
        with self.assertRaises(FrontMatterValidationError) as cm:
            _validate_frontmatter_taxonomy(self.post, fm_data)
        self.assertIn("Missing required 'categories'", str(cm.exception))

    def test_validate_taxonomy_multiple_categories(self):
        """Test validation fails with multiple categories."""
        fm_data = {'categories': ['django', 'python']}
        with self.assertRaises(FrontMatterValidationError) as cm:
            _validate_frontmatter_taxonomy(self.post, fm_data)
        self.assertIn("exactly one cluster", str(cm.exception))

    def test_validate_taxonomy_legacy_cluster_subcluster_format(self):
        """Test validation rejects legacy cluster/subcluster format."""
        fm_data = {'categories': ['django/tutorials']}
        with self.assertRaises(FrontMatterValidationError) as cm:
            _validate_frontmatter_taxonomy(self.post, fm_data)
        self.assertIn("cannot contain '/'", str(cm.exception))

    def test_validate_taxonomy_invalid_slug_format(self):
        """Test validation fails with invalid slug format."""
        fm_data = {'categories': ['Django Tutorials!']}
        with self.assertRaises(FrontMatterValidationError) as cm:
            _validate_frontmatter_taxonomy(self.post, fm_data)
        self.assertIn("must be a valid slug", str(cm.exception))

    def test_validate_taxonomy_subcluster_with_slash(self):
        """Test validation fails with subcluster containing slash."""
        fm_data = {
            'categories': ['django'],
            'subcluster': 'basic/advanced'
        }
        with self.assertRaises(FrontMatterValidationError) as cm:
            _validate_frontmatter_taxonomy(self.post, fm_data)
        self.assertIn("cannot contain '/'", str(cm.exception))


class TestPathBuilding(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site",
            slug="test-site",
            domain="example.com",
            posts_dir="_posts"
        )
        self.author = Author.objects.create(
            site=self.site,
            name="Test Author",
            slug="test-author"
        )
        self.post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="---\ncategories: [django]\n---\nContent",
            published_at=datetime(2024, 1, 15, 12, 0, tzinfo=tz.utc),
            author=self.author
        )

    def test_build_path_cluster_only(self):
        """Test building path with cluster only."""
        fm_data = {'categories': ['django']}
        path = build_post_relpath(self.post, self.site, fm_data)
        
        expected = "_posts/django/2024-01-15-test-post.md"
        self.assertEqual(path, expected)

    def test_build_path_cluster_and_subcluster(self):
        """Test building path with cluster and subcluster."""
        fm_data = {
            'categories': ['django'],
            'subcluster': 'tutorials'
        }
        path = build_post_relpath(self.post, self.site, fm_data)
        
        expected = "_posts/django/tutorials/2024-01-15-test-post.md"
        self.assertEqual(path, expected)

    def test_build_path_custom_posts_dir(self):
        """Test building path with custom posts directory."""
        self.site.posts_dir = "content/posts"
        self.site.save()
        
        fm_data = {'categories': ['django']}
        path = build_post_relpath(self.post, self.site, fm_data)
        
        expected = "content/posts/django/2024-01-15-test-post.md"
        self.assertEqual(path, expected)

    def test_build_path_no_slug_uses_title(self):
        """Test path building falls back to slugified title when slug missing."""
        self.post.slug = ""
        self.post.title = "Complex Title with Spaces!"
        
        fm_data = {'categories': ['django']}
        path = build_post_relpath(self.post, self.site, fm_data)
        
        expected = "_posts/django/2024-01-15-complex-title-with-spaces.md"
        self.assertEqual(path, expected)


class TestFileMove(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_handle_file_move_same_path(self):
        """Test no move when paths are the same."""
        moved, final_path = _handle_file_move(self.temp_dir, "same/path.md", "same/path.md")
        self.assertFalse(moved)
        self.assertEqual(final_path, "same/path.md")

    def test_handle_file_move_success(self):
        """Test successful file move."""
        # Create source file
        old_dir = os.path.join(self.temp_dir, "old")
        os.makedirs(old_dir, exist_ok=True)
        old_file = os.path.join(old_dir, "post.md")
        with open(old_file, 'w') as f:
            f.write("content")
        
        # Move to new location
        moved, final_path = _handle_file_move(self.temp_dir, "old/post.md", "new/category/post.md")
        
        self.assertTrue(moved)
        self.assertEqual(final_path, "new/category/post.md")
        self.assertFalse(os.path.exists(old_file))
        
        new_file = os.path.join(self.temp_dir, "new/category/post.md")
        self.assertTrue(os.path.exists(new_file))
        
        with open(new_file, 'r') as f:
            self.assertEqual(f.read(), "content")

    def test_handle_file_move_source_missing(self):
        """Test move when source file doesn't exist."""
        moved, final_path = _handle_file_move(self.temp_dir, "missing/file.md", "new/location.md")
        self.assertFalse(moved)
        self.assertEqual(final_path, "new/location.md")

    def test_handle_file_move_destination_exists(self):
        """Test move when destination already exists."""
        # Create source file
        old_dir = os.path.join(self.temp_dir, "old")
        os.makedirs(old_dir, exist_ok=True)
        old_file = os.path.join(old_dir, "post.md")
        with open(old_file, 'w') as f:
            f.write("old content")
        
        # Create destination file
        new_dir = os.path.join(self.temp_dir, "new")
        os.makedirs(new_dir, exist_ok=True)
        new_file = os.path.join(new_dir, "post.md")
        with open(new_file, 'w') as f:
            f.write("new content")
        
        # Attempt move (should resolve collision with increment policy)
        moved, final_path = _handle_file_move(self.temp_dir, "old/post.md", "new/post.md")
        
        self.assertTrue(moved)
        # Should have been moved to incremented path
        self.assertEqual(final_path, "new/post-1.md")
        
        # Check files
        self.assertFalse(os.path.exists(old_file))  # Old file should be gone
        self.assertTrue(os.path.exists(new_file))   # Original destination should still exist
        
        # Check the incremented file exists and has old content
        incremented_file = os.path.join(self.temp_dir, "new/post-1.md")
        self.assertTrue(os.path.exists(incremented_file))
        with open(incremented_file, 'r') as f:
            self.assertEqual(f.read(), "old content")


class TestRenderMarkdown(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site",
            slug="test-site",
            domain="example.com"
        )
        self.author = Author.objects.create(
            site=self.site,
            name="Test Author",
            slug="test-author"
        )

    def test_render_markdown_with_valid_frontmatter(self):
        """Test rendering markdown with valid front-matter."""
        post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="---\ncategories: [django]\nsubcluster: tutorials\n---\nPost content here",
            published_at=datetime(2024, 1, 15, 12, 0, tzinfo=tz.utc),
            author=self.author
        )
        
        result = render_markdown(post, self.site)
        
        # Should contain front-matter with normalized categories
        self.assertIn("categories:\n- django", result)
        self.assertIn("subcluster: tutorials", result)
        self.assertIn("layout: post", result)
        self.assertIn("date: '2024-01-15 12:00:00'", result)
        self.assertIn("Post content here", result)

    def test_render_markdown_invalid_frontmatter_raises_error(self):
        """Test that invalid front-matter raises FrontMatterValidationError."""
        post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="---\ncategories: [django, python]\n---\nContent",  # Multiple categories not allowed
            author=self.author
        )
        
        with self.assertRaises(FrontMatterValidationError):
            render_markdown(post, self.site)


class TestExportPost(TestCase):
    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site",
            slug="test-site",
            domain="example.com"
        )
        self.author = Author.objects.create(
            site=self.site,
            name="Test Author",
            slug="test-author"
        )
        self.temp_dir = tempfile.mkdtemp()
        self.site.repo_path = self.temp_dir
        self.site.save()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('blog.exporter._git')
    def test_export_post_invalid_frontmatter_blocks_export(self, mock_git):
        """Test that invalid front-matter blocks export."""
        post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="---\ncategories: [django, python]\n---\nContent",  # Invalid: multiple categories
            author=self.author
        )
        
        # Should return early due to validation error
        export_post(post)
        
        # Git should not be called since export was blocked
        mock_git.assert_not_called()

    @patch('blog.exporter._git')
    @patch('blog.exporter._is_tracked')
    @patch('blog.exporter._working_tree_clean')
    @patch('blog.exporter._is_ahead')
    def test_export_post_valid_frontmatter_succeeds(self, mock_ahead, mock_clean, mock_tracked, mock_git):
        """Test successful export with valid front-matter."""
        post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="---\ncategories: [django]\nsubcluster: tutorials\n---\nPost content",
            published_at=datetime(2024, 1, 15, 12, 0, tzinfo=tz.utc),
            author=self.author
        )
        
        # Mock git operations to return proper values
        def mock_git_side_effect(*args, **kwargs):
            command = args[1] if len(args) > 1 else ""
            if command == "remote":
                result = Mock()
                result.stdout = "origin\tgit@github.com:user/repo.git"
                return result
            elif command == "rev-parse":
                result = Mock()
                result.stdout = "abcd1234567890"
                return result
            else:
                return Mock()
        
        mock_tracked.return_value = False  # File not tracked, needs add
        mock_clean.return_value = True
        mock_ahead.return_value = False
        mock_git.side_effect = mock_git_side_effect
        
        # Mock the push URL building to avoid token requirements
        with patch('blog.exporter._build_push_url', return_value="https://token@github.com/user/repo.git"):
            export_post(post)
        
        # Verify file was created
        expected_path = os.path.join(self.temp_dir, "_posts/django/tutorials/2024-01-15-test-post.md")
        self.assertTrue(os.path.exists(expected_path))
        
        # Verify content
        with open(expected_path, 'r') as f:
            content = f.read()
            self.assertIn("categories:\n- django", content)
            self.assertIn("subcluster: tutorials", content)
            self.assertIn("Post content", content)

    def test_export_post_path_change_triggers_move(self):
        """Test that changing front-matter triggers file move."""
        # Create post with initial front-matter
        post = Post.objects.create(
            site=self.site,
            title="Test Post",
            slug="test-post",
            content="---\ncategories: [django]\n---\nContent",
            published_at=datetime(2024, 1, 15, 12, 0, tzinfo=tz.utc),
            last_export_path="_posts/old-category/2024-01-15-test-post.md",
            author=self.author
        )
        
        # Create the old file
        old_path = os.path.join(self.temp_dir, "_posts/old-category/2024-01-15-test-post.md")
        os.makedirs(os.path.dirname(old_path), exist_ok=True)
        with open(old_path, 'w') as f:
            f.write("old content")
        
        # Update content to change cluster
        post.content = "---\ncategories: [python]\n---\nNew content"
        post.save()
        
        # Mock git operations to return proper values
        def mock_git_side_effect(*args, **kwargs):
            command = args[1] if len(args) > 1 else ""
            if command == "remote":
                result = Mock()
                result.stdout = "origin\tgit@github.com:user/repo.git"
                return result
            elif command == "rev-parse":
                result = Mock()
                result.stdout = "abcd1234567890"
                return result
            else:
                return Mock()
        
        with patch('blog.exporter._git', side_effect=mock_git_side_effect), \
             patch('blog.exporter._is_tracked', return_value=True), \
             patch('blog.exporter._working_tree_clean', return_value=True), \
             patch('blog.exporter._is_ahead', return_value=False), \
             patch('blog.exporter._build_push_url', return_value="https://token@github.com/user/repo.git"):
            
            export_post(post)
        
        # Old file should be gone
        self.assertFalse(os.path.exists(old_path))
        
        # New file should exist
        new_path = os.path.join(self.temp_dir, "_posts/python/2024-01-15-test-post.md")
        self.assertTrue(os.path.exists(new_path))
        
        # Post metadata should be updated
        post.refresh_from_db()
        self.assertEqual(post.last_export_path, "_posts/python/2024-01-15-test-post.md")


class TestChecklistScenarios(TestCase):
    """Test the 4 specific scenarios from the operational checklist."""
    
    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site",
            slug="test-site",
            domain="example.com"
        )
        self.author = Author.objects.create(
            site=self.site,
            name="Test Author",
            slug="test-author"
        )
        self.temp_dir = tempfile.mkdtemp()
        self.site.repo_path = self.temp_dir
        self.site.save()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scenario_1_solo_cluster(self):
        """Test Case 1: Solo cluster → file nella cartella del cluster."""
        post = Post.objects.create(
            site=self.site,
            title="Django Tutorial",
            slug="django-tutorial",
            content="---\ncategories: [django]\n---\nDjango content here",
            published_at=datetime(2024, 1, 15, 12, 0, tzinfo=tz.utc),
            author=self.author
        )
        
        # Test path building
        body = post.content
        fm_data = _extract_frontmatter_from_body(body)
        expected_path = build_post_relpath(post, self.site, fm_data)
        
        # Expected: _posts/django/2024-01-15-django-tutorial.md
        self.assertEqual(expected_path, "_posts/django/2024-01-15-django-tutorial.md")
        
        # Test actual export (dry-run)
        simulation = export_post(post, dry_run=True)
        self.assertIn("CREATE: _posts/django/2024-01-15-django-tutorial.md", simulation['actions'])
        self.assertTrue(simulation['would_succeed'])

    def test_scenario_2_cluster_plus_subcluster(self):
        """Test Case 2: Cluster+subcluster → file nella cartella del subcluster."""
        post = Post.objects.create(
            site=self.site,
            title="Advanced Django",
            slug="advanced-django",
            content="---\ncategories: [django]\nsubcluster: tutorials\n---\nAdvanced Django content",
            published_at=datetime(2024, 1, 16, 12, 0, tzinfo=tz.utc),
            author=self.author
        )
        
        # Test path building
        body = post.content
        fm_data = _extract_frontmatter_from_body(body)
        expected_path = build_post_relpath(post, self.site, fm_data)
        
        # Expected: _posts/django/tutorials/2024-01-16-advanced-django.md
        self.assertEqual(expected_path, "_posts/django/tutorials/2024-01-16-advanced-django.md")
        
        # Test actual export (dry-run)
        simulation = export_post(post, dry_run=True)
        self.assertIn("CREATE: _posts/django/tutorials/2024-01-16-advanced-django.md", simulation['actions'])
        self.assertTrue(simulation['would_succeed'])

    def test_scenario_3_cambio_subcluster(self):
        """Test Case 3: Cambio subcluster → file spostato e vecchio rimosso."""
        post = Post.objects.create(
            site=self.site,
            title="Django Basics",
            slug="django-basics",
            content="---\ncategories: [django]\nsubcluster: basics\n---\nBasic Django content",
            published_at=datetime(2024, 1, 17, 12, 0, tzinfo=tz.utc),
            last_export_path="_posts/django/basics/2024-01-17-django-basics.md",
            author=self.author
        )
        
        # Create the old file
        old_path = os.path.join(self.temp_dir, "_posts/django/basics/2024-01-17-django-basics.md")
        os.makedirs(os.path.dirname(old_path), exist_ok=True)
        with open(old_path, 'w') as f:
            f.write("old content")
        
        # Change subcluster
        post.content = "---\ncategories: [django]\nsubcluster: advanced\n---\nAdvanced Django content"
        post.save()
        
        # Test dry-run first
        simulation = export_post(post, dry_run=True)
        expected_move = "MOVE: _posts/django/basics/2024-01-17-django-basics.md -> _posts/django/advanced/2024-01-17-django-basics.md"
        self.assertIn(expected_move, simulation['actions'])
        self.assertTrue(simulation['would_succeed'])

    def test_scenario_4_collisione_filename(self):
        """Test Case 4: Collisione filename → comportamento conforme alla policy."""
        # Create existing file
        existing_path = os.path.join(self.temp_dir, "_posts/django/2024-01-18-tutorial.md")
        os.makedirs(os.path.dirname(existing_path), exist_ok=True)
        with open(existing_path, 'w') as f:
            f.write("existing content")
        
        # Create new post with same slug and date
        post = Post.objects.create(
            site=self.site,
            title="Tutorial",
            slug="tutorial",
            content="---\ncategories: [django]\n---\nNew tutorial content",
            published_at=datetime(2024, 1, 18, 12, 0, tzinfo=tz.utc),
            author=self.author
        )
        
        # Test with increment policy (default)
        simulation = export_post(post, dry_run=True, collision_policy="increment")
        # Should warn about collision and suggest increment
        collision_warnings = [w for w in simulation['warnings'] if 'COLLISION' in w]
        self.assertTrue(len(collision_warnings) > 0)
        self.assertIn("tutorial-1.md", str(collision_warnings))
        
        # Test with fail policy
        simulation_fail = export_post(post, dry_run=True, collision_policy="fail")
        # Should warn that fail policy would block
        fail_warnings = [w for w in simulation_fail['warnings'] if 'would block' in w]
        self.assertTrue(len(fail_warnings) > 0)
        self.assertFalse(simulation_fail['would_succeed'])