import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from blog_manager.blog.models import Post, Site, Author

pytestmark = pytest.mark.django_db

def make_site(name="site-a"):
    return Site.objects.create(name=name, domain=f"{name}.test")

def payload(site_id, author_id, **kw):
    base = {
        "site": site_id,
        "title": "Titolo base",
        "slug": "ciao-mondo",
        "body": "Contenuto di test",
        "content": "Contenuto di test",
        "author": author_id,
        "categories": [],
        "status": "draft",
    }
    base.update(kw)
    return base

def test_same_title_same_site_gets_suffix():
    client = APIClient()
    User = get_user_model()
    user = User.objects.create_user(username="testuser", password="testpass", is_staff=True, is_superuser=True)
    client.force_authenticate(user=user)
    s = make_site().id
    author = Author.objects.create(site_id=s, name="Autore", slug="autore")
    from blog_manager.blog_manager.blog.views import PostViewSet
    serializer = PostViewSet.serializer_class()
    print("Serializer fields:", serializer.get_fields().keys())
    r1 = client.post(reverse("api:post-list"), payload(s, author.id, title="Ciao mondo"), format="json")
    print(r1.data)
    assert r1.status_code in (200, 201)
    r2 = client.post(reverse("api:post-list"), payload(s, author.id, title="Ciao mondo"), format="json")
    assert r2.status_code in (200, 201)
    p1 = Post.objects.get(id=r1.data["id"])
    p2 = Post.objects.get(id=r2.data["id"])
    assert p1.slug != p2.slug
    assert p2.slug.startswith(p1.slug) and p2.slug != p1.slug

def test_same_slug_different_sites_is_allowed():
    client = APIClient()
    User = get_user_model()
    user = User.objects.create_user(username="testuser2", password="testpass", is_staff=True, is_superuser=True)
    client.force_authenticate(user=user)
    s1 = make_site("site-a").id
    s2 = make_site("site-b").id
    author1 = Author.objects.create(site_id=s1, name="Autore1", slug="autore1")
    author2 = Author.objects.create(site_id=s2, name="Autore2", slug="autore2")
    r1 = client.post(reverse("api:post-list"), payload(s1, author1.id, title="Hello", slug="same-slug"), format="json")
    r2 = client.post(reverse("api:post-list"), payload(s2, author2.id, title="Hello", slug="same-slug"), format="json")
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)

def test_conflict_returns_409_when_slug_taken_in_same_site():
    client = APIClient()
    User = get_user_model()
    user = User.objects.create_user(username="testuser3", password="testpass", is_staff=True, is_superuser=True)
    client.force_authenticate(user=user)
    s = make_site().id
    author = Author.objects.create(site_id=s, name="Autore", slug="autore")
    client.post(reverse("api:post-list"), payload(s, author.id, slug="dup"), format="json")
    r = client.post(reverse("api:post-list"), payload(s, author.id, slug="dup"), format="json")
    assert r.status_code == 409
    assert "Conflitto" in r.data["detail"]
