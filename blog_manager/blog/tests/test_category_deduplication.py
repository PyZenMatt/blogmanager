import pytest
from django.test import TestCase, override_settings
from blog.models import Category, Post, Site, Author
from blog.utils import create_categories_from_frontmatter
from unittest.mock import patch


class CategoryDeduplicationTest(TestCase):
    def setUp(self):
        """Set up test data"""
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

    @patch('blog.signals.ensure_categories_from_post')
    @override_settings(EXPORT_ENABLED=False)
    def test_category_deduplication_basic(self, mock_signal):
        """Test that creating the same category multiple times doesn't create duplicates"""
        
        # Create first post with django category
        with patch('django.db.models.signals.post_save.send'):
            post1 = Post.objects.create(
                site=self.site,
                title="First Django Post",
                slug="first-django-post",
                content="""---
categories: [django]
---
# First Django Post
Content here.""",
                author=self.author
            )
        
        # Create categories from front matter
        cats1 = create_categories_from_frontmatter(post1)
        
        # Check we have exactly one django category
        django_cats = Category.objects.filter(site=self.site, cluster_slug='django')
        self.assertEqual(django_cats.count(), 1)
        self.assertEqual(len(cats1), 1)
        self.assertEqual(cats1[0].cluster_slug, 'django')
        self.assertIsNone(cats1[0].subcluster_slug)
        
        # Create second post with the same django category
        with patch('django.db.models.signals.post_save.send'):
            post2 = Post.objects.create(
                site=self.site,
                title="Second Django Post", 
                slug="second-django-post",
                content="""---
categories: [django]
---
# Second Django Post
More content.""",
                author=self.author
            )
        
        # Create categories from front matter again
        cats2 = create_categories_from_frontmatter(post2)
        
        # Should still have exactly one django category
        django_cats = Category.objects.filter(site=self.site, cluster_slug='django')
        self.assertEqual(django_cats.count(), 1)
        self.assertEqual(len(cats2), 1)
        self.assertEqual(cats2[0].id, cats1[0].id)  # Same category object
        
        # Both posts should reference the same category
        self.assertEqual(post1.categories.count(), 1)
        self.assertEqual(post2.categories.count(), 1) 
        self.assertEqual(post1.categories.first().id, post2.categories.first().id)

    @patch('blog.signals.ensure_categories_from_post')
    @override_settings(EXPORT_ENABLED=False)
    def test_hierarchical_categories(self, mock_signal):
        """Test cluster/subcluster category creation"""
        
        # Create the post without triggers
        with patch('django.db.models.signals.post_save.send'):
            post = Post.objects.create(
                site=self.site,
                title="Django Forms Post",
                slug="django-forms-post", 
                content="""---
categories: [django/forms]
---
# Django Forms
About forms.""",
                author=self.author
            )
        
        cats = create_categories_from_frontmatter(post)
        
        # Should create both cluster and cluster/subcluster categories
        django_cats = Category.objects.filter(site=self.site, cluster_slug='django')
        self.assertEqual(django_cats.count(), 2)
        
        # Check cluster category
        cluster_cat = django_cats.filter(subcluster_slug__isnull=True).first()
        self.assertIsNotNone(cluster_cat)
        self.assertEqual(cluster_cat.cluster_slug, 'django')
        self.assertIsNone(cluster_cat.subcluster_slug)
        
        # Check subcluster category  
        subcluster_cat = django_cats.filter(subcluster_slug='forms').first()
        self.assertIsNotNone(subcluster_cat)
        self.assertEqual(subcluster_cat.cluster_slug, 'django')
        self.assertEqual(subcluster_cat.subcluster_slug, 'forms')
        
        # Post should have both categories
        self.assertEqual(post.categories.count(), 2)

    @patch('blog.signals.ensure_categories_from_post')
    @override_settings(EXPORT_ENABLED=False)  # Disable export signals
    def test_idempotent_category_creation(self, mock_signal):
        """Test that running category creation multiple times is idempotent"""
        
        # Create the post without triggers
        with patch('django.db.models.signals.post_save.send'):
            post = Post.objects.create(
                site=self.site,
                title="Multiple Categories Post",
                slug="multiple-categories-post",
                content="""---
categories: [django, python, django/forms]
---
# Multiple Categories
Content with multiple categories.""",
                author=self.author
            )
        
        # Run category creation multiple times
        cats1 = create_categories_from_frontmatter(post)
        initial_count = Category.objects.filter(site=self.site).count()
        
        # Debug: print all categories
        print(f"\nDEBUG: Categories after first run ({initial_count} total):")
        for cat in Category.objects.filter(site=self.site):
            cluster = getattr(cat, 'cluster_slug', 'NO_CLUSTER')
            subcluster = getattr(cat, 'subcluster_slug', None)
            print(f"  - ID {cat.id}: {cluster}/{subcluster or 'None'} (name: {cat.name})")
        
        cats2 = create_categories_from_frontmatter(post) 
        cats3 = create_categories_from_frontmatter(post)
        
        # Should still have the same number of categories
        final_count = Category.objects.filter(site=self.site).count()
        print(f"\nDEBUG: Categories after additional runs ({final_count} total):")
        for cat in Category.objects.filter(site=self.site):
            cluster = getattr(cat, 'cluster_slug', 'NO_CLUSTER')
            subcluster = getattr(cat, 'subcluster_slug', None)
            print(f"  - ID {cat.id}: {cluster}/{subcluster or 'None'} (name: {cat.name})")
        
        self.assertEqual(initial_count, final_count)
        
        # Should have: django (cluster), python (cluster), django/forms (subcluster)
        self.assertEqual(final_count, 3)
        
        # Verify the categories
        django_cluster = Category.objects.get(site=self.site, cluster_slug='django', subcluster_slug__isnull=True)
        python_cluster = Category.objects.get(site=self.site, cluster_slug='python', subcluster_slug__isnull=True) 
        django_forms = Category.objects.get(site=self.site, cluster_slug='django', subcluster_slug='forms')
        
        self.assertEqual(django_cluster.name, 'django')
        self.assertEqual(python_cluster.name, 'python')
        self.assertEqual(django_forms.name, 'django/forms')

    @patch('blog.signals.ensure_categories_from_post')
    @override_settings(EXPORT_ENABLED=False)
    def test_unique_constraint_enforcement(self, mock_signal):
        """Test that the unique constraint prevents duplicates at DB level"""
        
        # Create a category with subcluster (non-null values)
        cat1 = Category.objects.create(
            site=self.site,
            name='django-forms',
            slug='django-forms',
            cluster_slug='django',
            subcluster_slug='forms'  # Non-null
        )
        
        # Try to create a duplicate with same cluster+subcluster - should raise integrity error
        with self.assertRaises(Exception):  # IntegrityError or similar
            Category.objects.create(
                site=self.site,
                name='django-forms-duplicate',
                slug='django-forms-duplicate', 
                cluster_slug='django',  # Same cluster_slug
                subcluster_slug='forms'  # Same subcluster_slug (non-null)
            )

    @patch('blog.signals.ensure_categories_from_post')
    @override_settings(EXPORT_ENABLED=False)
    def test_sync_simulation_no_duplicates(self, mock_signal):
        """Simulate multiple sync runs to ensure no duplicates are created"""
        
        # Simulate processing the same post multiple times (like during repeated syncs)
        post_content = """---
categories: [burnout-e-lavoro, burnout-e-lavoro/ritmi-gentili]
---
# Burnout e Lavoro
Post about burnout."""
        
        for i in range(5):  # Simulate 5 sync runs
            with patch('django.db.models.signals.post_save.send'):
                post = Post.objects.create(
                    site=self.site,
                    title=f"Burnout Post {i+1}",
                    slug=f"burnout-post-{i+1}",
                    content=post_content,
                    author=self.author
                )
            create_categories_from_frontmatter(post)
        
        # Should have exactly 2 categories despite 5 posts
        burnout_cats = Category.objects.filter(site=self.site, cluster_slug='burnout-e-lavoro')
        self.assertEqual(burnout_cats.count(), 2)
        
        # Check the categories
        cluster_cat = burnout_cats.filter(subcluster_slug__isnull=True).first()
        subcluster_cat = burnout_cats.filter(subcluster_slug='ritmi-gentili').first()
        
        self.assertIsNotNone(cluster_cat)
        self.assertIsNotNone(subcluster_cat)
        self.assertEqual(cluster_cat.name, 'burnout-e-lavoro')
        self.assertEqual(subcluster_cat.name, 'burnout-e-lavoro/ritmi-gentili')
        
        # All 5 posts should reference the same 2 categories
        for i in range(5):
            post = Post.objects.get(slug=f"burnout-post-{i+1}")
            self.assertEqual(post.categories.count(), 2)
            self.assertIn(cluster_cat, post.categories.all())
            self.assertIn(subcluster_cat, post.categories.all())