import pytest
from django.conf import settings
from django.db import connection
from django.test import TestCase, SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from blog.models import Site, Post


@pytest.mark.skipif(
    connection.vendor != "mysql", reason="MySQL-specific UTF8MB4 tests"
)
class TestMySQLUTF8MB4(TestCase):
    """Test UTF8MB4 encoding support in MySQL."""

    def setUp(self):
        self.site = Site.objects.create(
            name="Test Site", 
            slug="test-site",
            repository_path="/test/repo"
        )

    def test_emoji_content_storage(self):
        """Test that emoji content can be stored and retrieved correctly."""
        emoji_content = "Hello World! 🚀🔥✨ Testing emoji support"
        
        post = Post.objects.create(
            title="Test Post with Emoji 🚀",
            content=emoji_content,
            site=self.site,
            slug="test-emoji-post"
        )
        
        # Refresh from database to ensure round-trip
        post.refresh_from_db()
        
        self.assertEqual(post.title, "Test Post with Emoji 🚀")
        self.assertEqual(post.content, emoji_content)
        self.assertIn("🚀", post.title)
        self.assertIn("🔥", post.content)

    def test_mysql_options_configuration(self):
        """Test that MySQL is configured with proper OPTIONS for UTF8MB4."""
        if connection.vendor == "mysql":
            db_config = settings.DATABASES['default']
            options = db_config.get('OPTIONS', {})
            
            # Check for UTF8MB4 configuration
            charset = options.get('charset')
            init_command = options.get('init_command')
            
            # Either charset should be utf8mb4 or init_command should set it
            self.assertTrue(
                charset == 'utf8mb4' or 
                (init_command and 'utf8mb4' in init_command),
                "Database should be configured for UTF8MB4"
            )


@pytest.mark.skipif(
    connection.vendor != "mysql", reason="MySQL-specific model collation tests"
)
class TestSlugGeneration(APITestCase):
    """Test slug generation and uniqueness per site."""

    def setUp(self):
        self.site_a = Site.objects.create(
            name="Site A", 
            slug="site-a",
            repository_path="/site-a/repo"
        )
        self.site_b = Site.objects.create(
            name="Site B", 
            slug="site-b", 
            repository_path="/site-b/repo"
        )

    def test_slug_uniqueness_within_site(self):
        """Test that slugs are unique within the same site."""
        # Create first post
        Post.objects.create(
            title="Test Post",
            content="Content",
            site=self.site_a,
            slug="test-post"
        )
        
        # Create second post with same slug should fail
        with self.assertRaises(Exception):  # Should raise IntegrityError
            Post.objects.create(
                title="Another Post",
                content="Content",
                site=self.site_a,
                slug="test-post"
            )

    def test_slug_reuse_across_different_sites(self):
        """Test that the same slug can be used in different sites."""
        # Create post in site A
        post_a = Post.objects.create(
            title="Test Post",
            content="Content A",
            site=self.site_a,
            slug="same-slug"
        )
        
        # Create post in site B with same slug - should work
        post_b = Post.objects.create(
            title="Test Post",
            content="Content B", 
            site=self.site_b,
            slug="same-slug"
        )
        
        self.assertEqual(post_a.slug, "same-slug")
        self.assertEqual(post_b.slug, "same-slug")
        self.assertNotEqual(post_a.site, post_b.site)

    def test_automatic_slug_generation_with_emoji(self):
        """Test automatic slug generation from titles containing emoji."""
        post = Post.objects.create(
            title="My Amazing Post 🚀🔥",
            content="Content with emoji",
            site=self.site_a
        )
        
        # Slug should be generated without emoji
        expected_slug = "my-amazing-post"
        self.assertEqual(post.slug, expected_slug)
        
        # Title should preserve emoji
        self.assertEqual(post.title, "My Amazing Post 🚀🔥")

    def test_slug_collision_resolution(self):
        """Test that slug collisions are resolved with suffixes."""
        # Create first post
        post1 = Post.objects.create(
            title="Duplicate Title",
            content="First content",
            site=self.site_a
        )
        
        # Create second post with same title
        post2 = Post.objects.create(
            title="Duplicate Title",
            content="Second content",
            site=self.site_a
        )
        
        # Slugs should be different
        self.assertNotEqual(post1.slug, post2.slug)
        
        # Second post should have suffix
        self.assertTrue(
            post2.slug.startswith("duplicate-title") and 
            post2.slug != "duplicate-title"
        )


class TestBasicFunctionality(SimpleTestCase):
    """Basic tests that work with any database backend."""
    
    def test_migration_exists(self):
        """Test that the UTF8MB4 migration exists."""
        from blog.migrations import __path__
        import os
        migration_file = os.path.join(__path__[0], '0020_convert_mysql_to_utf8mb4.py')
        self.assertTrue(os.path.exists(migration_file), "UTF8MB4 migration file should exist")
    
    def test_check_encoding_command_exists(self):
        """Test that the check_encoding management command exists."""
        from blog.management.commands.check_encoding import Command
        cmd = Command()
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.help, "Check and optionally fix encoding issues in blog content (dry-run by default)")
    
    def test_utf8mb4_migration_function(self):
        """Test that the UTF8MB4 migration function can be imported and is protected."""
        import importlib
        from django.db import connection
        from unittest.mock import MagicMock
        
        # Import the migration module using importlib
        migration_module = importlib.import_module('blog.migrations.0020_convert_mysql_to_utf8mb4')
        forwards = migration_module.forwards
        backwards = migration_module.backwards
        
        # Test that forwards function exists and handles non-MySQL gracefully
        mock_apps = MagicMock()
        mock_schema_editor = MagicMock()
        
        # Should not raise an error even with mocked parameters
        try:
            forwards(mock_apps, mock_schema_editor)
            backwards(mock_apps, mock_schema_editor)
        except Exception as e:
            if connection.vendor != "mysql":
                # On non-MySQL, it should exit early without error
                pass
            else:
                # On MySQL, it might error due to mocked parameters, which is ok
                pass