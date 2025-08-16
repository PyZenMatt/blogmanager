import pytest
from django.conf import settings
from django.db import connection
from django.test import TestCase
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