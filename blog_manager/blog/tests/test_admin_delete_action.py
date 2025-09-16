import pytest
from django.urls import reverse

from blog.models import Site, Post


@pytest.mark.django_db
def test_admin_delete_db_only(client, admin_user, monkeypatch, tmp_path):
    # create site/post
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="S", domain="https://x", repo_owner="o", repo_name="r", repo_path=str(repo_dir))
    author = site.authors.create(name="A", slug="a")
    post = Post.objects.create(site=site, title="ToDelete", slug="todel", status="published", published_at="2025-01-01T00:00:00Z", content="x", author=author)

    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)
    client.force_login(admin_user)
    url = reverse("admin:blog_post_delete_confirm") + f"?pks={post.pk}"
    r = client.get(url)
    assert r.status_code == 200
    # submit form DB-only
    r2 = client.post(url, {"mode": "db"})
    # should redirect back to changelist
    assert r2.status_code in (302, 303)
    assert not Post.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_admin_delete_db_and_repo(monkeypatch, client, admin_user, tmp_path):
    # enable repo deletion via settings and mock delete_post_from_repo
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="S2", domain="https://x2", repo_owner="o2", repo_name="r2", repo_path=str(repo_dir))
    author = site.authors.create(name="B", slug="b")
    post = Post.objects.create(site=site, title="ToDelete2", slug="todel2", status="published", published_at="2025-01-02T00:00:00Z", content="y", author=author)

    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)
    monkeypatch.setattr(settings, "ALLOW_REPO_DELETE", True, raising=False)

    def fake_delete(p, message=None, client=None):
        return {"status": "deleted", "commit_sha": "deadbeef", "html_url": "https://github.com"}

    monkeypatch.setattr("blog.admin.delete_post_from_repo", fake_delete)

    client.force_login(admin_user)
    url = reverse("admin:blog_post_delete_confirm") + f"?pks={post.pk}"
    r = client.get(url)
    assert r.status_code == 200
    r2 = client.post(url, {"mode": "repo"})
    assert r2.status_code in (302, 303)
    assert not Post.objects.filter(pk=post.pk).exists()
