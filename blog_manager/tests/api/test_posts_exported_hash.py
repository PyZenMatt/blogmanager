import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from blog.models import Post, Site

pytestmark = pytest.mark.django_db

def test_posts_list_works_when_exported_hash_field_exists(api_client: APIClient):
    site = Site.objects.create(name="Main", slug="main")
    Post.objects.create(
        site=site,
        title="Hello",
        slug="hello",
        content="...",
        is_published=True,
        published_at=timezone.now(),
        exported_hash=None,  # field present and nullable
    )
    res = api_client.get("/api/posts/")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) >= 1

def test_exported_hash_nullable_and_not_required_in_serializer(api_client: APIClient):
    site = Site.objects.create(name="Main", slug="main")
    p = Post.objects.create(
        site=site,
        title="NoHash",
        slug="nohash",
        content="...",
        is_published=True,
    )
    assert p.exported_hash is None
    res = api_client.get("/api/posts/")
    assert res.status_code == 200
