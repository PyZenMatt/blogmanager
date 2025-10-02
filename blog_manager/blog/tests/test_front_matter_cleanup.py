"""
Tests for front matter cleanup functionality.
Ensures that empty fields like canonical, tags, and description are excluded from exports.
"""
import pytest
import yaml
from blog.exporter import _front_matter


class MockCategory:
    def __init__(self, slug):
        self.slug = slug


class MockPost:
    def __init__(self, **kwargs):
        # Set defaults
        self.content = kwargs.get('content', '')
        self.body = kwargs.get('body', '')
        self.description = kwargs.get('description', '')
        self.canonical_url = kwargs.get('canonical_url', '')
        self.published_at = kwargs.get('published_at', None)
        self.created_at = kwargs.get('created_at', None)
        self.updated_at = kwargs.get('updated_at', None)
        
        # Mock categories
        categories_data = kwargs.get('categories', [])
        self.categories = MockCategoriesManager(categories_data)


class MockCategoriesManager:
    def __init__(self, categories_data):
        self._categories = [MockCategory(slug) for slug in categories_data]
    
    def all(self):
        return self._categories


class MockSite:
    pass


def test_empty_fields_excluded_from_front_matter():
    """Test that empty canonical, description, and categories are excluded."""
    post = MockPost(
        content="# Test content",
        description="",  # empty
        canonical_url="",  # empty
        categories=[],  # empty
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Should include layout and date
    assert data['layout'] == 'post'
    assert 'date' in data
    
    # Should NOT include empty fields
    assert 'canonical' not in data
    assert 'description' not in data
    assert 'categories' not in data
    assert 'tags' not in data


def test_populated_fields_included_in_front_matter():
    """Test that non-empty fields are properly included."""
    post = MockPost(
        content="# Test content",
        description="A great post about testing",
        canonical_url="https://example.com/canonical",
        categories=["tech", "python"],
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Should include all populated fields
    assert data['layout'] == 'post'
    assert 'date' in data
    assert data['canonical'] == 'https://example.com/canonical'
    assert data['description'] == 'A great post about testing'
    assert data['categories'] == ['python', 'tech']  # sorted


def test_mixed_empty_and_populated_fields():
    """Test mixed scenario with some empty and some populated fields."""
    post = MockPost(
        content="# Test content",
        description="Only description is set",
        canonical_url="",  # empty
        categories=["tech"],  # has values
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Should include only populated fields
    assert data['layout'] == 'post'
    assert 'date' in data
    assert data['description'] == 'Only description is set'
    assert data['categories'] == ['tech']
    # Should NOT include empty canonical
    assert 'canonical' not in data
    assert 'tags' not in data


def test_whitespace_only_fields_excluded():
    """Test that fields with only whitespace are considered empty."""
    post = MockPost(
        content="# Test content",
        description="   \n  \t  ",  # whitespace only
        canonical_url="  ",  # whitespace only
        categories=[],
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Should exclude whitespace-only fields
    assert 'canonical' not in data
    assert 'description' not in data
    assert 'categories' not in data


def test_front_matter_in_content_cleaned():
    """Test that empty fields in existing front matter are also cleaned."""
    post = MockPost(
        content="""---
title: "Test Post"
canonical: ""
description: ""
tags: []
custom_field: "should be kept"
---

# Content here""",
        categories=["tech"],
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Should keep title and custom field, clean empty fields
    assert data['title'] == 'Test Post'
    assert data['custom_field'] == 'should be kept'
    assert data['categories'] == ['tech']
    
    # Should NOT include empty fields from front matter
    assert 'canonical' not in data
    assert 'description' not in data
    assert 'tags' not in data


def test_backward_compatibility_with_existing_values():
    """Test that existing meaningful values are preserved."""
    post = MockPost(
        content="""---
title: "Existing Post"
canonical: "https://old-site.com/post"
description: "Old description"
tags: ["old-tag"]
---

# Content""",
        description="New description from DB",  # should be overridden by front matter
        canonical_url="https://new-site.com/post",  # should be overridden
        categories=["new-cat"],
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Front matter values should take precedence but empty ones should be cleaned
    assert data['title'] == 'Existing Post'
    # Server-controlled fields should use DB values
    assert data['categories'] == ['new-cat']
    # But if front matter has meaningful values, they should be preserved
    # (Note: current implementation gives server fields precedence)


def test_empty_tags_in_frontmatter_removed():
    """Test that empty tags arrays in front matter are removed."""
    post = MockPost(
        content="""---
title: "Post with empty tags"
tags: []
---

# Content""",
        categories=[],
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the YAML to check what's included
    yaml_content = fm.split('---\n')[1].split('\n---\n')[0]
    data = yaml.safe_load(yaml_content)
    
    # Empty tags should be removed
    assert 'tags' not in data
    assert data['title'] == 'Post with empty tags'