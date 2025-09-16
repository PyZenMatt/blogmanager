import pytest
from django.utils import timezone

from blog.models import Site, Post, ExportJob


@pytest.mark.django_db
def test_delete_repo_already_absent(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="S", domain="https://x", repo_owner="o", repo_name="r", repo_path=str(repo_dir))
    author = site.authors.create(name="A", slug="a")
    post = Post.objects.create(site=site, title="ToDelete", slug="todel", status="published", published_at=timezone.now(), content="x", author=author)

    # Ensure post has repo path (normally set during publish)
    post.repo_path = "_posts/2025-09-16-todel.md"
    post.save(update_fields=["repo_path"])

    # Mock GitHubClient.delete_file to return already_absent (simulate 404)
    def fake_delete_file(*args, **kwargs):
        return {"status": "already_absent", "commit_sha": None, "html_url": None}

    monkeypatch.setattr("blog.github_client.GitHubClient.delete_file", fake_delete_file)

    # Call the service directly for this unit test
    from blog.services.github_ops import delete_post_from_repo
    res = delete_post_from_repo(post, message="test delete")
    assert res["status"] == "already_absent"
    # Audit job should be created (best-effort in service)
    jobs = ExportJob.objects.filter(post=post)
    assert jobs.exists()


@pytest.mark.django_db
def test_delete_repo_permission_denied(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="S2", domain="https://x2", repo_owner="o2", repo_name="r2", repo_path=str(repo_dir))
    author = site.authors.create(name="B", slug="b")
    post = Post.objects.create(site=site, title="ToDelete2", slug="todel2", status="published", published_at=timezone.now(), content="y", author=author)

    # set repo_path so service will attempt delete
    post.repo_path = "_posts/2025-01-02-todel2.md"
    post.save(update_fields=["repo_path"])

    def fake_delete_file(*args, **kwargs):
        raise PermissionError("403 Forbidden")

    monkeypatch.setattr("blog.github_client.GitHubClient.delete_file", fake_delete_file)
    from blog.services.github_ops import delete_post_from_repo
    with pytest.raises(PermissionError):
        delete_post_from_repo(post, message="test delete")
    # Ensure DB still has the post (service should not delete DB on repo error)
    assert Post.objects.filter(pk=post.pk).exists()


@pytest.mark.django_db
def test_meta_only_update_does_not_trigger_export(monkeypatch, tmp_path):
    # Ensure the post_save signal does not trigger export when only meta fields are updated
    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", True)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="S3", domain="https://x3", repo_owner="o3", repo_name="r3", repo_path=str(repo_dir))
    author = site.authors.create(name="C", slug="c")
    post = Post.objects.create(site=site, title="P3", slug="p3", status="published", published_at=timezone.now(), content="z", author=author)

    # Monkeypatch exporter.export_post to raise if called
    called = {"exported": False}

    def fake_export(p):
        called["exported"] = True

    monkeypatch.setattr("blog.exporter.export_post", fake_export)

    # Update only meta fields
    post.exported_hash = "x"
    post.last_export_path = post.last_export_path
    post.save(update_fields=["exported_hash"])

    assert not called["exported"]
