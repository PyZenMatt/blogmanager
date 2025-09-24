import pytest
from django.core.exceptions import ValidationError
from blog.models import Post, Site, Author


@pytest.mark.django_db
def test_slug_immutable_when_locked():
    site = Site.objects.create(name="Test Site", domain="https://example.com", slug="test-site")
    author = Author.objects.create(name="A", slug="a", site=site)
    p = Post.objects.create(site=site, title="Hello", slug="hello", author=author, status="published", is_published=True)
    # Post is published so slug_locked should be True after save
    p.refresh_from_db()
    assert p.slug_locked is True

    # Attempt to change slug and save -> ValidationError
    p.slug = "hello-renamed"
    with pytest.raises(ValidationError):
        p.full_clean()
