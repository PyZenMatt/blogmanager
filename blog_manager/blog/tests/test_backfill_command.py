import pytest
from django.core.management import call_command
from django.utils import timezone

from blog.models import Site, Post


@pytest.mark.django_db
def test_backfill_updates_hash(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    site = Site.objects.create(name="S", domain="https://x", repo_owner="o", repo_name="r", repo_path=str(repo_dir))
    author = site.authors.create(name="X", slug="x")
    post = Post.objects.create(site=site, title="P", slug="p", status="published", published_at=timezone.now(), content="abc", author=author)
    # mark as already published via last_commit_sha to make it eligible for backfill
    Post.objects.filter(pk=post.pk).update(last_commit_sha="abc123")
    post.refresh_from_db()
    assert not post.last_published_hash
    call_command("backfill_last_published_hash")
    post.refresh_from_db()
    assert post.last_published_hash