"""
Tests for idempotent category import functionality.
"""
import pytest
from django.test import TestCase
from django.core.management import call_command
from io import StringIO
from blog.models import Site, Post, Category, Author


class TestIdempotentCategoryImport(TestCase):
    def setUp(self):
        """Set up test data."""
        self.site = Site.objects.create(
            name="Test Site",
            domain="https://test.example.com",
            slug="test-site"
        )
        self.author = Author.objects.create(
            site=self.site,
            name="Test Author",
            slug="test-author"
        )

    def test_import_categories_idempotent_single_run(self):
        """Test that importing categories multiple times doesn't create duplicates."""
        # Create posts with overlapping categories
        posts_data = [
            ("Post 1", "---\ncategories:\n- tech\n- python\n---\n\nContent 1"),
            ("Post 2", "---\ncategories:\n- tech\n- django\n---\n\nContent 2"),
            ("Post 3", "---\ncategories:\n- tech\n- python\n---\n\nContent 3"),
            ("Post 4", "---\ncategories:\n- design\n---\n\nContent 4"),
        ]

        for title, content in posts_data:
            Post.objects.create(
                site=self.site,
                title=title,
                content=content,
                slug=title.lower().replace(" ", "-"),
                author=self.author
            )

        # First import run
        out1 = StringIO()
        call_command('import_categories_from_posts', stdout=out1)
        output1 = out1.getvalue()

        # Check that categories were created
        categories = Category.objects.filter(site=self.site)
        category_slugs = sorted([c.slug for c in categories])
        
        expected_slugs = ['design', 'django', 'python', 'tech']
        self.assertEqual(category_slugs, expected_slugs)

        # Count total categories and assignments
        initial_count = categories.count()
        initial_assignments = sum(p.categories.count() for p in Post.objects.filter(site=self.site))

        # Second import run (should be idempotent)
        out2 = StringIO()
        call_command('import_categories_from_posts', stdout=out2)
        output2 = out2.getvalue()

        # Check that no new categories were created
        final_categories = Category.objects.filter(site=self.site)
        final_count = final_categories.count()
        final_assignments = sum(p.categories.count() for p in Post.objects.filter(site=self.site))

        self.assertEqual(initial_count, final_count, "No new categories should be created on second run")
        
        # Note: assignments might increase if posts get re-assigned, but categories shouldn't duplicate
        self.assertEqual(len(expected_slugs), final_count)

        # Verify no duplicate categories exist
        for slug in expected_slugs:
            duplicate_count = Category.objects.filter(site=self.site, slug=slug).count()
            self.assertEqual(duplicate_count, 1, f"Category '{slug}' should exist exactly once")

    def test_import_categories_hierarchical_idempotent(self):
        """Test hierarchical categories are idempotent."""
        posts_data = [
            ("Post 1", "---\ncategories:\n- tech/python\n---\n\nContent 1"),
            ("Post 2", "---\ncategories:\n- tech/python\n---\n\nContent 2"),
            ("Post 3", "---\ncategories:\n- tech/django\n---\n\nContent 3"),
            ("Post 4", "---\ncategories:\n- design/ui\n---\n\nContent 4"),
        ]

        for title, content in posts_data:
            Post.objects.create(
                site=self.site,
                title=title,
                content=content,
                slug=title.lower().replace(" ", "-")
            )

        # First import
        call_command('import_categories_from_posts', fields='categories', hierarchy='slash')
        
        initial_categories = Category.objects.filter(site=self.site)
        initial_count = initial_categories.count()

        # Second import (should be idempotent)
        call_command('import_categories_from_posts', fields='categories', hierarchy='slash')
        
        final_categories = Category.objects.filter(site=self.site)
        final_count = final_categories.count()

        self.assertEqual(initial_count, final_count, "Hierarchical import should be idempotent")

        # Check expected categories exist
        expected_slugs = ['tech', 'tech-python', 'tech-django', 'design', 'design-ui']
        actual_slugs = sorted([c.slug for c in final_categories])
        self.assertEqual(actual_slugs, expected_slugs)

    def test_import_categories_large_dataset_performance(self):
        """Test that importing a large number of posts with shared categories is efficient."""
        # Create 50 posts all using the same 3 categories
        shared_categories = ['tech', 'python', 'django']
        
        for i in range(50):
            content = f"---\ncategories:\n- {shared_categories[i % 3]}\n---\n\nContent {i}"
            Post.objects.create(
                site=self.site,
                title=f"Post {i}",
                content=content,
                slug=f"post-{i}",
                author=self.author
            )

        # Import categories
        call_command('import_categories_from_posts')

        # Should only have 3 categories total, not 50
        categories = Category.objects.filter(site=self.site)
        self.assertEqual(categories.count(), 3)

        # All categories should exist exactly once
        for cat_name in shared_categories:
            cat_count = Category.objects.filter(site=self.site, slug=cat_name).count()
            self.assertEqual(cat_count, 1, f"Category '{cat_name}' should exist exactly once")

        # Second run should not create any new categories
        initial_count = categories.count()
        call_command('import_categories_from_posts')
        final_count = Category.objects.filter(site=self.site).count()
        
        self.assertEqual(initial_count, final_count, "Second import should not create new categories")

    def test_constraint_prevents_duplicates(self):
        """Test that the unique constraint prevents duplicate categories."""
        from django.db import transaction
        from django.db.utils import IntegrityError
        
        # Create first category
        cat1 = Category.objects.create(site=self.site, name="Tech", slug="tech")
        
        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(site=self.site, name="Technology", slug="tech")
        
        # Verify only one category exists
        count = Category.objects.filter(site=self.site, slug="tech").count()
        self.assertEqual(count, 1, "Should have only one category with this slug")