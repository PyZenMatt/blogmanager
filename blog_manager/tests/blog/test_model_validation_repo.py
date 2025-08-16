import pytest
from django.utils import timezone
from django.core.exceptions import ValidationError
from blog.models import Site, Post, Author

@pytest.mark.django_db
def test_published_post_requires_existing_repo(tmp_path):
    site = Site.objects.create(name="My Site", domain="https://example.com", repo_path=str(tmp_path))
    author = Author.objects.create(site=site, name="A", slug="a")
    post = Post(site=site, title="T", slug="t", author=author, content="body", status="published", is_published=True, published_at=timezone.now())
    post.clean()  # non deve alzare

    site.repo_path = str(tmp_path / "missing")
    site.save()
    post2 = Post(site=site, title="T2", slug="t2", author=author, content="body", status="published", is_published=True, published_at=timezone.now())
    with pytest.raises(ValidationError):
        post2.clean()
