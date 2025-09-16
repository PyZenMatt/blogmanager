import pytest

from django.utils import timezone

from blog.models import Post, Site
from blog.services.publish import publish_post


@pytest.mark.django_db
def test_publish_idempotency_first_and_no_change(monkeypatch, tmp_path):
    # Setup a site and a published post. Provide required fields and a repo_path dir.
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)

    site = Site.objects.create(
        name="Test Site",
        domain="https://example.com",
        repo_owner="owner",
        repo_name="repo",
        default_branch="main",
        repo_path=str(repo_dir),
    )
    author = site.authors.create(name="A", slug="a")
    post = Post.objects.create(
        site=site,
        title="Test Post",
        slug="test-post",
        status="published",
        published_at=timezone.now(),
        content="Initial content",
        author=author,
    )

    commits = []

    def fake_upsert(*args, **kwargs):
        owner = args[0] if len(args) > 0 else kwargs.get("owner")
        repo = args[1] if len(args) > 1 else kwargs.get("repo")
        path = args[2] if len(args) > 2 else kwargs.get("path")
        branch = kwargs.get("branch") or (args[4] if len(args) > 4 else "main")
        sha = f"commit-{len(commits)+1}"
        commits.append(sha)
        return {"commit_sha": sha, "html_url": f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"}

    # Disable automatic export signals during the test to avoid local git operations
    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)
    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)

    # First publish should create a commit and set last_published_hash
    res1 = publish_post(post)
    assert res1.commit_sha is not None
    post.refresh_from_db()
    assert post.last_published_hash

    # Second publish with no changes should not call upsert (no new commits)
    res2 = publish_post(post)
    assert res2.commit_sha is None
    # ExportJob should have recorded export_error=no_changes (checked indirectly by no commit)


@pytest.mark.django_db
def test_publish_idempotency_changes_trigger_new_commit(monkeypatch, tmp_path):
    repo_dir = tmp_path / "repo2"
    repo_dir.mkdir()
    from django.conf import settings as _settings
    monkeypatch.setattr(_settings, "EXPORT_ENABLED", False)

    site = Site.objects.create(
        name="Test Site 2",
        domain="https://example2.com",
        repo_owner="owner2",
        repo_name="repo2",
        default_branch="main",
        repo_path=str(repo_dir),
    )
    author = site.authors.create(name="B", slug="b")
    post = Post.objects.create(
        site=site,
        title="Test Post 2",
        slug="test-post-2",
        status="published",
        published_at=timezone.now(),
        content="Initial content",
        author=author,
    )

    calls = []

    def fake_upsert(*args, **kwargs):
        content = kwargs.get("content") if kwargs.get("content") is not None else (args[3] if len(args) > 3 else None)
        calls.append(content)
        return {"commit_sha": "sha-1", "html_url": "https://example.com"}

    from django.conf import settings
    monkeypatch.setattr(settings, "EXPORT_ENABLED", False)
    monkeypatch.setattr("blog.github_client.GitHubClient.upsert_file", fake_upsert)

    # First publish
    publish_post(post)
    post.refresh_from_db()
    old_hash = post.last_published_hash

    # Modify content
    post.content = post.content + "\nNew line"
    post.save(update_fields=["content"])

    # Second publish should call upsert again and update hash
    res = publish_post(post)
    assert res.commit_sha is not None
    post.refresh_from_db()
    assert post.last_published_hash != old_hash
