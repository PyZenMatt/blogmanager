import pytest
from django.contrib.auth.models import Group, User
from django.urls import reverse
from rest_framework.test import APIClient

from blog.models import Author, Post, Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def create_user_with_group(username, group_name):
    user = User.objects.create_user(username=username, password="pass")
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


def test_author_cannot_publish(api_client):
    site = Site.objects.create(name="TestSite", domain="https://testsite.com")
    author_obj = Author.objects.create(site=site, name="Author", bio="", slug="author")
    post = Post.objects.create(
        site=site,
        title="Draft",
        slug="draft",
        author=author_obj,
        content="Test",
        is_published=False,
    description="Test Description",
    keywords="test",
    )
    author = create_user_with_group("author1", "Author")
    api_client.force_authenticate(user=author)
    url = reverse("post-detail", kwargs={"slug": post.slug})
    resp = api_client.patch(url, {"is_published": True}, format="json")
    assert resp.status_code == 403
    assert "permission" in str(resp.data).lower()


def test_publisher_can_publish(api_client):
    site = Site.objects.create(name="TestSite", domain="https://testsite.com")
    author_obj = Author.objects.create(site=site, name="Author", bio="", slug="author")
    post = Post.objects.create(
        site=site,
        title="Draft",
        slug="draft2",
        author=author_obj,
        content="Test",
        is_published=False,
    description="Test Description",
    keywords="test",
    )
    publisher = create_user_with_group("publisher1", "Publisher")
    print(
        "Publisher user groups:", list(publisher.groups.values_list("name", flat=True))
    )
    api_client.force_authenticate(user=publisher)
    url = reverse("post-detail", kwargs={"pk": post.pk})
    from django.utils import timezone

    resp = api_client.patch(
        url,
        {
            "is_published": True,
            "published_at": timezone.now().isoformat(),
            "status": "published",
        },
        format="json",
    )
    print("PATCH response status:", resp.status_code)
    print("PATCH response data:", resp.data)
    assert resp.status_code in [200, 202]
    post.refresh_from_db()
    assert post.is_published is True
