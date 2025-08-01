import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from blog.models import Site, Category, Author, Post
from django.utils import timezone

pytestmark = pytest.mark.django_db

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def sample_data():
    site = Site.objects.create(name="MessyMind", domain="https://messymind.it")
    cat = Category.objects.create(site=site, name="Tech", slug="tech")
    author = Author.objects.create(site=site, name="Mario Rossi", bio="Bio", slug="mario-rossi")
    post = Post.objects.create(
        site=site,
        title="Test Post",
        slug="test-post",
        author=author,
        content="Contenuto di test",
        published_at=timezone.now(),
        is_published=True
    )
    post.categories.add(cat)
    return {
        "site": site,
        "category": cat,
        "author": author,
        "post": post
    }

def test_sites_list(api_client, sample_data):
    url = reverse('site-list')
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data[0]['domain'] == "https://messymind.it"

def test_posts_list_filter_by_site(api_client, sample_data):
    url = reverse('post-list')
    resp = api_client.get(url, {'site': 'https://messymind.it'})
    assert resp.status_code == 200
    assert resp.data['results'][0]['title'] == "Test Post"

def test_post_detail(api_client, sample_data):
    url = reverse('post-detail', kwargs={'slug': 'test-post'})
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert resp.data['slug'] == "test-post"

def test_categories_list(api_client, sample_data):
    url = reverse('category-list')
    resp = api_client.get(url, {'site': sample_data['site'].id})
    assert resp.status_code == 200
    assert resp.data[0]['name'] == "Tech"

def test_authors_list(api_client, sample_data):
    url = reverse('author-list')
    resp = api_client.get(url, {'site': sample_data['site'].id})
    assert resp.status_code == 200
    assert resp.data[0]['name'] == "Mario Rossi"
