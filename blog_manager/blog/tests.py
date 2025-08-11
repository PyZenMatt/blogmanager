import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from blog.models import Author, Category, Post, Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def sample_data():
    site = Site.objects.create(name="MessyMind", domain="https://messymind.it")
    cat = Category.objects.create(site=site, name="Tech", slug="tech")
    author = Author.objects.create(
        site=site, name="Mario Rossi", bio="Bio", slug="mario-rossi"
    )
    post = Post.objects.create(
        site=site,
        title="Test Post",
        slug="test-post",
        author=author,
        content="Contenuto di test",
        published_at=timezone.now(),
        is_published=True,
    )
    post.categories.add(cat)
    return {"site": site, "category": cat, "author": author, "post": post}


def test_sites_list(api_client, sample_data):
    url = reverse("site-list")
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data[0]["domain"] == "https://messymind.it"


def test_posts_list_filter_by_site(api_client, sample_data):
    url = reverse("post-list")
    resp = api_client.get(url, {"site": "https://messymind.it"})
    assert resp.status_code == 200
    assert resp.data["results"][0]["title"] == "Test Post"


def test_post_detail(api_client, sample_data):
    url = reverse("post-detail", kwargs={"slug": "test-post"})
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data["slug"] == "test-post"


def test_categories_and_authors_list(api_client, sample_data):
    url = reverse("category-list")
    resp = api_client.get(url, {"site": sample_data["site"].id})
    assert resp.status_code == 200
    assert resp.data[0]["name"] == "Tech"

    url = reverse("author-list")
    resp = api_client.get(url, {"site": sample_data["site"].id})
    assert resp.status_code == 200
    assert resp.data[0]["name"] == "Mario Rossi"


def test_post_status_transitions():
    User = get_user_model()
    site = Site.objects.create(name="TestSite", domain="https://testsite.com")
    author = Author.objects.create(site=site, name="Author", bio="", slug="author")
    post = Post.objects.create(
        site=site,
        title="Workflow",
        slug="workflow",
        author=author,
        content="Test",
        is_published=False,
    )

    # Draft to Review
    reviewer = User.objects.create(username="reviewer", is_staff=True)
    post.status = "review"
    post.reviewed_by = reviewer
    post.review_notes = "Looks good"
    post.save()
    assert post.status == "review"
    assert post.reviewed_by == reviewer
    assert post.review_notes == "Looks good"

    # Review to Published (requires published_at and is_published)
    post.status = "published"
    post.is_published = True
    post.published_at = timezone.now()
    post.save()
    assert post.status == "published"
    assert post.is_published is True
    assert post.published_at is not None


def test_post_publish_requires_published_at():
    site = Site.objects.create(name="TestSite2", domain="https://testsite2.com")
    author = Author.objects.create(site=site, name="Author2", bio="", slug="author2")
    post = Post.objects.create(
        site=site,
        title="NoPubDate",
        slug="nopubdate",
        author=author,
        content="Test",
        is_published=True,
    )
    post.status = "published"
    post.published_at = None
    with pytest.raises(ValidationError):
        post.save()


def test_post_review_requires_reviewer():
    site = Site.objects.create(name="TestSite3", domain="https://testsite3.com")
    author = Author.objects.create(site=site, name="Author3", bio="", slug="author3")
    post = Post.objects.create(
        site=site,
        title="NoReviewer",
        slug="noreviewer",
        author=author,
        content="Test",
        is_published=False,
    )
    post.status = "review"
    post.reviewed_by = None
    with pytest.raises(ValidationError):
        post.save()


def test_author_cannot_publish(api_client, sample_data):
    User = get_user_model()
    author_user = User.objects.create_user(username="author1", password="pass")
    author_user.groups.create(name="Author")
    api_client.force_authenticate(user=author_user)

    post = sample_data["post"]
    url = reverse("post-detail", kwargs={"slug": post.slug})
    resp = api_client.patch(url, {"is_published": True}, format="json")
    assert resp.status_code == 403
    assert "permission" in str(resp.data.get("detail", "")).lower()


def test_publisher_can_publish(api_client, sample_data):
    User = get_user_model()
    publisher_user = User.objects.create_user(username="publisher1", password="pass")
    publisher_user.groups.create(name="Publisher")
    api_client.force_authenticate(user=publisher_user)

    post = sample_data["post"]
    url = reverse("post-detail", kwargs={"slug": post.slug})
    resp = api_client.patch(url, {"is_published": True}, format="json")
    assert resp.status_code in [200, 202]
    assert resp.data["is_published"] is True
