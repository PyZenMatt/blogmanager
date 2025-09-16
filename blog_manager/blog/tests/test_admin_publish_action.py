import pytest
from django.utils import timezone

from blog.models import Site, Post, ExportJob


@pytest.mark.django_db
def test_admin_publish_new_post(monkeypatch, tmp_path, client):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="ASite", domain="https://a", repo_owner="o", repo_name="r", repo_path=str(repo_dir))
    author = site.authors.create(name="AA", slug="aa")
    post = Post.objects.create(site=site, title="APost", slug="apost", status="draft", content="x", author=author)

    def fake_upsert(*args, **kwargs):
        return {"commit_sha": "sha-admin-1", "html_url": "https://github.com"}

    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)

    # Create a fake request with message storage for admin
    from django.test import RequestFactory
    from django.contrib.messages.storage.fallback import FallbackStorage
    req = RequestFactory().post("/")
    req.user = None
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    from blog.admin import PostAdmin
    pa = PostAdmin(Post, None)
    pa.publish_posts(req, Post.objects.filter(pk=post.pk))

    post.refresh_from_db()
    assert post.last_published_hash
    assert ExportJob.objects.filter(post=post, export_status="success").exists()


@pytest.mark.django_db
def test_admin_publish_idempotent(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo2"
    repo_dir.mkdir()
    site = Site.objects.create(name="BSite", domain="https://b", repo_owner="o2", repo_name="r2", repo_path=str(repo_dir))
    author = site.authors.create(name="BB", slug="bb")
    post = Post.objects.create(site=site, title="BPost", slug="bpost", status="published", published_at=timezone.now(), content="x", author=author)

    commits = []

    def fake_upsert(*args, **kwargs):
        sha = f"sha-{len(commits)+1}"
        commits.append(sha)
        return {"commit_sha": sha, "html_url": "https://github.com"}

    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)
    # First publish
    from django.test import RequestFactory
    from django.contrib.messages.storage.fallback import FallbackStorage
    req = RequestFactory().post("/")
    req.user = None
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    from blog.admin import PostAdmin
    pa = PostAdmin(Post, None)
    pa.publish_posts(req, Post.objects.filter(pk=post.pk))
    post.refresh_from_db()
    old_hash = post.last_published_hash

    # Second publish should be idempotent (no new commit)
    pa.publish_posts(req, Post.objects.filter(pk=post.pk))
    post.refresh_from_db()
    assert post.last_published_hash == old_hash
    # ExportJob with no_changes should exist
    assert ExportJob.objects.filter(post=post, action="publish", message="no_changes").exists()


@pytest.mark.django_db
def test_admin_publish_error(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo3"
    repo_dir.mkdir()
    site = Site.objects.create(name="CSite", domain="https://c", repo_owner="o3", repo_name="r3", repo_path=str(repo_dir))
    author = site.authors.create(name="CC", slug="cc")
    post = Post.objects.create(site=site, title="CPost", slug="cpost", status="draft", content="x", author=author)

    def fake_upsert(*args, **kwargs):
        raise PermissionError("403 Forbidden")

    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)
    from django.test import RequestFactory
    from django.contrib.messages.storage.fallback import FallbackStorage
    req = RequestFactory().post("/")
    req.user = None
    setattr(req, 'session', {})
    setattr(req, '_messages', FallbackStorage(req))

    from blog.admin import PostAdmin
    pa = PostAdmin(Post, None)
    pa.publish_posts(req, Post.objects.filter(pk=post.pk))

    # ExportJob failed should be created
    assert ExportJob.objects.filter(post=post, export_status="failed").exists()
