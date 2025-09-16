import pytest
from django.utils import timezone

from blog.models import Site, Post, ExportJob


@pytest.mark.django_db
def test_refresh_ok(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="RSite", domain="https://r", repo_owner="ro", repo_name="rr", repo_path=str(repo_dir))
    author = site.authors.create(name="RA", slug="ra")
    post = Post.objects.create(site=site, title="RPost", slug="rpost", status="published", published_at=timezone.now(), content="same-content", author=author)

    def fake_get_file(*args, **kwargs):
        return {"content": "same-content", "sha": "sha-1"}

    monkeypatch.setattr("blog.github_client.GitHubClient.get_file", fake_get_file)
    from django.test import RequestFactory
    from django.contrib.messages.storage.fallback import FallbackStorage
    req = RequestFactory().post("/")
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    from blog.admin import PostAdmin
    pa = PostAdmin(Post, None)
    pa.refresh_posts(req, Post.objects.filter(pk=post.pk))

    assert ExportJob.objects.filter(post=post, action="refresh", message="ok").exists()


@pytest.mark.django_db
def test_refresh_absent(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo2"
    repo_dir.mkdir()
    site = Site.objects.create(name="RSite2", domain="https://r2", repo_owner="ro2", repo_name="rr2", repo_path=str(repo_dir))
    author = site.authors.create(name="RB", slug="rb")
    post = Post.objects.create(site=site, title="RPost2", slug="rpost2", status="published", published_at=timezone.now(), content="same-content", author=author)

    def fake_get_file(*args, **kwargs):
        raise Exception("Not Found")

    monkeypatch.setattr("blog.github_client.GitHubClient.get_file", fake_get_file)
    from django.test import RequestFactory
    from django.contrib.messages.storage.fallback import FallbackStorage
    req = RequestFactory().post("/")
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    from blog.admin import PostAdmin
    pa = PostAdmin(Post, None)
    pa.refresh_posts(req, Post.objects.filter(pk=post.pk))

    assert ExportJob.objects.filter(post=post, action="refresh", message="drift_absent").exists()


@pytest.mark.django_db
def test_refresh_content_drift(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo3"
    repo_dir.mkdir()
    site = Site.objects.create(name="RSite3", domain="https://r3", repo_owner="ro3", repo_name="rr3", repo_path=str(repo_dir))
    author = site.authors.create(name="RC", slug="rc")
    post = Post.objects.create(site=site, title="RPost3", slug="rpost3", status="published", published_at=timezone.now(), content="local-content", author=author)

    def fake_get_file(*args, **kwargs):
        return {"content": "remote-content", "sha": "sha-remote"}

    monkeypatch.setattr("blog.github_client.GitHubClient.get_file", fake_get_file)
    from django.test import RequestFactory
    from django.contrib.messages.storage.fallback import FallbackStorage
    req = RequestFactory().post("/")
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    from blog.admin import PostAdmin
    pa = PostAdmin(Post, None)
    pa.refresh_posts(req, Post.objects.filter(pk=post.pk))

    assert ExportJob.objects.filter(post=post, action="refresh", message="drift_content").exists()
