import pytest
from django.utils import timezone

from django.core.management import call_command

from blog.models import Post, Site
from blog.services.publish import publish_post


@pytest.mark.django_db
def test_publish_sets_last_published_hash(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)

    site = Site.objects.create(
        name="Test Site X",
        domain="https://example-x.com",
        repo_owner="ownerx",
        repo_name="repox",
        default_branch="main",
        repo_path=str(repo_dir),
    )
    author = site.authors.create(name="A", slug="a")
    post = Post.objects.create(
        site=site,
        title="Test Publish Hash",
        slug="test-publish-hash",
        status="published",
        published_at=timezone.now(),
        content="Initial content",
        author=author,
    )

    def fake_upsert(*args, **kwargs):
        return {"commit_sha": "sha-xyz", "html_url": "https://example.com"}

    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)
    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)

    res = publish_post(post)
    assert res.commit_sha is not None
    post.refresh_from_db()
    assert post.last_published_hash


@pytest.mark.django_db
def test_publish_idempotent_keeps_hash(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo2"
    repo_dir.mkdir()
    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)

    site = Site.objects.create(
        name="Test Site Y",
        domain="https://example-y.com",
        repo_owner="ownery",
        repo_name="repoy",
        default_branch="main",
        repo_path=str(repo_dir),
    )
    author = site.authors.create(name="B", slug="b")
    post = Post.objects.create(
        site=site,
        title="Test Publish Idempotent",
        slug="test-publish-idempotent",
        status="published",
        published_at=timezone.now(),
        content="Initial content",
        author=author,
    )

    commits = []

    def fake_upsert(*args, **kwargs):
        sha = f"sha-{len(commits)+1}"
        commits.append(sha)
        return {"commit_sha": sha, "html_url": "https://example.com"}

    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)
    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)

    res1 = publish_post(post)
    assert res1.commit_sha is not None
    post.refresh_from_db()
    old_hash = post.last_published_hash

    # Second publish with no changes
    res2 = publish_post(post)
    assert res2.commit_sha is None
    post.refresh_from_db()
    assert post.last_published_hash == old_hash


@pytest.mark.django_db
def test_backfill_dry_run_does_not_write(tmp_path):
    repo_dir = tmp_path / "repo3"
    repo_dir.mkdir()
    site = Site.objects.create(name="Sdry", domain="https://xdr", repo_owner="odr", repo_name="rdr", repo_path=str(repo_dir))
    author = site.authors.create(name="D", slug="d")
    post = Post.objects.create(site=site, title="Pdry", slug="pdry", status="published", published_at=timezone.now(), content="abc", author=author)
    # mark as already published via last_commit_sha to make it eligible for backfill
    Post.objects.filter(pk=post.pk).update(last_commit_sha="abc123")
    post.refresh_from_db()
    assert not post.last_published_hash
    call_command("backfill_last_published_hash", "--dry-run")
    post.refresh_from_db()
    assert not post.last_published_hash
