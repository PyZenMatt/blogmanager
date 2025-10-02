"""
Test for clean front matter export - only includes non-empty fields.
"""
import pytest
import yaml
from blog.exporter import _front_matter
from blog.models import Post, Site, Category


class MockPost:
    """Mock post object for testing front matter generation."""
    
    def __init__(self, **kwargs):
        self.content = kwargs.get('content', '')
        self.body = kwargs.get('body', '')
        self.title = kwargs.get('title', 'Test Post')
        self.canonical_url = kwargs.get('canonical_url', '')
        self.description = kwargs.get('description', '')
        self.published_at = kwargs.get('published_at', None)
        self.updated_at = kwargs.get('updated_at', None)
        self.created_at = kwargs.get('created_at', None)
        
        # Mock categories
        categories = kwargs.get('categories', [])
        self.categories = MockManager(categories)
    
    
class MockCategory:
    def __init__(self, slug):
        self.slug = slug


class MockManager:
    def __init__(self, items):
        self._items = items
    
    def all(self):
        return self._items


class MockSite:
    def __init__(self):
        pass


def test_clean_front_matter_excludes_empty_fields():
    """Test that empty canonical, tags, and description are not included."""
    post = MockPost(
        canonical_url="",  # empty
        description="",    # empty
        categories=[]      # empty
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the front matter
    lines = fm.strip().split('\n')
    assert lines[0] == '---'
    assert lines[-1] == '---'
    
    yaml_content = '\n'.join(lines[1:-1])
    data = yaml.safe_load(yaml_content)
    
    # Should NOT contain empty fields
    assert 'canonical' not in data
    assert 'description' not in data
    assert 'tags' not in data
    
    # Should contain required fields
    assert data['layout'] == 'post'
    assert 'date' in data
    assert data['categories'] == []


def test_clean_front_matter_includes_populated_fields():
    """Test that populated canonical and description are included."""
    post = MockPost(
        canonical_url="https://example.com/post",
        description="This is a test post description",
        categories=[MockCategory('tech'), MockCategory('python')]
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the front matter
    lines = fm.strip().split('\n')
    yaml_content = '\n'.join(lines[1:-1])
    data = yaml.safe_load(yaml_content)
    
    # Should contain populated fields
    assert data['canonical'] == 'https://example.com/post'
    assert data['description'] == 'This is a test post description'
    assert sorted(data['categories']) == ['python', 'tech']
    
    # Should NOT contain empty tags
    assert 'tags' not in data


def test_front_matter_preserves_user_fields():
    """Test that user front matter fields are preserved while cleaning empty server fields."""
    post = MockPost(
        content="""---
title: User Title
custom_field: User Value
canonical: ""
description: ""
---

# Content here
""",
        canonical_url="",  # empty server field
        description=""     # empty server field
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the front matter
    lines = fm.strip().split('\n')
    yaml_content = '\n'.join(lines[1:-1])
    data = yaml.safe_load(yaml_content)
    
    # Should preserve user fields
    assert data['title'] == 'User Title'
    assert data['custom_field'] == 'User Value'
    
    # Should NOT contain empty fields (cleaned from both server and user)
    assert 'canonical' not in data
    assert 'description' not in data
    assert 'tags' not in data


def test_front_matter_user_overrides_server():
    """Test that user fields override server fields when both are populated."""
    post = MockPost(
        content="""---
title: User Title
canonical: https://user.com/post
description: User description
---

# Content
""",
        canonical_url="https://server.com/post",  # server value
        description="Server description"          # server value
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the front matter
    lines = fm.strip().split('\n')
    yaml_content = '\n'.join(lines[1:-1])
    data = yaml.safe_load(yaml_content)
    
    # User values should win
    assert data['title'] == 'User Title'
    assert data['canonical'] == 'https://user.com/post'
    assert data['description'] == 'User description'


def test_front_matter_whitespace_only_fields_excluded():
    """Test that fields with only whitespace are treated as empty."""
    post = MockPost(
        canonical_url="   ",  # whitespace only
        description="\n\t ",  # whitespace only
    )
    site = MockSite()
    
    fm = _front_matter(post, site)
    
    # Parse the front matter
    lines = fm.strip().split('\n')
    yaml_content = '\n'.join(lines[1:-1])
    data = yaml.safe_load(yaml_content)
    
    # Should NOT contain whitespace-only fields
    assert 'canonical' not in data
    assert 'description' not in data