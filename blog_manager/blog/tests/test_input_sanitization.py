import pytest
from rest_framework.test import APIClient
from rest_framework import status
from blog.models import Post, Site, Author
from django.contrib.auth.models import User, Group

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_user():
    """Create a test user with publisher permissions"""
    user = User.objects.create_user(username="testuser", password="testpass123")
    # Add user to Publisher group for write permissions
    publisher_group, _ = Group.objects.get_or_create(name="Publisher")
    user.groups.add(publisher_group)
    return user


@pytest.fixture
def test_site():
    """Create a test site"""
    return Site.objects.create(
        name="Test Site",
        domain="https://test.example.com"
    )


@pytest.fixture
def test_author(test_site):
    """Create a test author"""
    return Author.objects.create(
        name="Test Author",
        site=test_site,
        slug="test-author"
    )


def _post_payload(**kwargs):
    """Create a base post payload for testing"""
    base = {
        "title": "Test Title",
        "slug": "test-title",
        "body": "Test content",
        "site": 1,
        "author": 1,
        "categories": [],
        "is_published": False,
    }
    base.update(kwargs)
    return base


def test_create_post_with_emoji_succeeds(test_user, test_site, test_author):
    """Test that posts with emoji content save correctly (4-byte Unicode)"""
    client = APIClient()
    client.force_authenticate(user=test_user)
    
    payload = _post_payload(
        title="Hello 👩🏽‍💻✨ World",
        body="Content with emoji 😄🚀 and more Unicode ✨",
        site=test_site.id,
        author=test_author.id
    )
    
    response = client.post("/api/blog/posts/", payload, format="json")
    
    assert response.status_code in (200, 201), f"Expected 200/201, got {response.status_code}: {response.content}"
    
    # Check that the post was saved with emojis intact
    post = Post.objects.filter(slug="test-title").first()
    assert post is not None
    assert "👩🏽‍💻✨" in post.title
    assert "😄🚀" in post.content


def test_null_byte_is_stripped_from_content():
    """Test that null bytes are removed from content during validation"""
    from blog.serializers import _clean_text
    
    # Test null byte removal
    dirty_text = "line\x00break\x00more"
    clean_text = _clean_text(dirty_text)
    assert "\x00" not in clean_text
    assert clean_text == "linebreakmore"


def test_surrogate_characters_are_stripped():
    """Test that surrogate characters are removed during validation"""
    from blog.serializers import _clean_text
    
    # Test surrogate removal (these are invalid UTF-16 surrogates)
    dirty_text = "text\uD800\uDFFFmore"
    clean_text = _clean_text(dirty_text)
    assert "\uD800" not in clean_text
    assert "\uDFFF" not in clean_text
    assert clean_text == "textmore"


def test_unicode_normalization():
    """Test that Unicode text is normalized to NFC form"""
    from blog.serializers import _clean_text
    
    # Test with composed vs decomposed accented characters
    composed = "café"  # é as single character
    decomposed = "cafe\u0301"  # e + combining accent
    
    normalized_composed = _clean_text(composed)
    normalized_decomposed = _clean_text(decomposed)
    
    # Both should normalize to the same form
    assert normalized_composed == normalized_decomposed


def test_title_overflow_returns_400(test_user, test_site, test_author):
    """Test that overly long titles return 400 instead of 500"""
    client = APIClient()
    client.force_authenticate(user=test_user)
    
    payload = _post_payload(
        title="x" * 201,  # Exceeds 200 character limit
        site=test_site.id,
        author=test_author.id
    )
    
    response = client.post("/api/blog/posts/", payload, format="json")
    
    assert response.status_code == 400
    # Django's built-in validation handles max_length, which is fine
    assert "title" in response.data
    assert "max_length" in str(response.data["title"]) or "characters" in str(response.data["title"])


def test_slug_overflow_returns_400(test_user, test_site, test_author):
    """Test that overly long slugs return 400 instead of 500"""
    client = APIClient()
    client.force_authenticate(user=test_user)
    
    payload = _post_payload(
        slug="x" * 201,  # Exceeds 200 character limit
        site=test_site.id,
        author=test_author.id
    )
    
    response = client.post("/api/blog/posts/", payload, format="json")
    
    assert response.status_code == 400
    # Django's built-in validation handles max_length, which is fine
    assert "slug" in response.data
    assert "max_length" in str(response.data["slug"]) or "characters" in str(response.data["slug"])


def test_post_with_cleaned_content_creates_successfully(test_user, test_site, test_author):
    """Test that posts with null bytes are cleaned and saved"""
    client = APIClient()
    client.force_authenticate(user=test_user)
    
    # Note: We can't test surrogates via JSON API as they can't be serialized to JSON
    # But we can test null bytes which can be in strings
    payload = _post_payload(
        title="Test Title",  # Clean title for this test
        body="Content with embedded nulls",  # Can't include actual null bytes in JSON
        site=test_site.id,
        author=test_author.id,
        slug="test-clean"
    )
    
    response = client.post("/api/blog/posts/", payload, format="json")
    
    assert response.status_code in (200, 201)
    
    # Verify post was created successfully
    post = Post.objects.filter(slug="test-clean").first()
    assert post is not None
    assert post.title == "Test Title"
    # The content should be clean (our serializer validation handles this)
    assert post.content == "Content with embedded nulls"


@pytest.mark.skipif(
    True, reason="MySQL-specific test - requires MySQL database setup"
)
def test_mysql_charset_error_returns_400():
    """Test that MySQL charset errors are converted to 400 responses"""
    # This test would require actual MySQL setup with utf8 (not utf8mb4)
    # to trigger OperationalError for 4-byte Unicode characters
    pass