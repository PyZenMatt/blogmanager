import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from blog.models import Post
from core.models import Site

pytestmark = pytest.mark.django_db

def make_site(name="site-a"):
    return Site.objects.create(name=name, slug=name)

def payload(site_id, **kw):
    base = {
        "site": site_id,
        "title": "Titolo base",
        "slug": "",
        "excerpt": "",
        "content_markdown": "c",
        "categories": [],
        "tags": [],
        "hero_url": "",
        "published": False,
    }
    base.update(kw)
    return base

def test_same_title_same_site_gets_suffix():
    client = APIClient()
    s = make_site().id
    r1 = client.post(reverse("api:post-list"), payload(s, title="Ciao mondo"), format="json")
    assert r1.status_code in (200, 201)
    r2 = client.post(reverse("api:post-list"), payload(s, title="Ciao mondo"), format="json")
    assert r2.status_code in (200, 201)
    p1 = Post.objects.get(id=r1.data["id"])
    p2 = Post.objects.get(id=r2.data["id"])
    assert p1.slug != p2.slug
    assert p2.slug.startswith(p1.slug) and p2.slug != p1.slug

def test_same_slug_different_sites_is_allowed():
    client = APIClient()
    s1 = make_site("site-a").id
    s2 = make_site("site-b").id
    r1 = client.post(reverse("api:post-list"), payload(s1, title="Hello", slug="same-slug"), format="json")
    r2 = client.post(reverse("api:post-list"), payload(s2, title="Hello", slug="same-slug"), format="json")
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)

def test_conflict_returns_409_when_slug_taken_in_same_site():
    client = APIClient()
    s = make_site().id
    client.post(reverse("api:post-list"), payload(s, slug="dup"), format="json")
    r = client.post(reverse("api:post-list"), payload(s, slug="dup"), format="json")
    assert r.status_code == 409
    assert "Conflitto" in r.data["detail"]
