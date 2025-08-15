import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone
from blog.models import Site, Post

pytestmark = pytest.mark.django_db

def _mk(site, status="published", slug="hello", content="body"):
    return Post.objects.create(
        site=site, title="Hello", slug=slug,
        content=content,
        status=status, is_published=(status=="published"),
        published_at=timezone.now() if status=="published" else None,
    )

@patch("blog_manager.blog.exporter._git_add_commit_push", return_value=True)
@patch("blog_manager.blog.exporter._safe_write", return_value=True)
def test_first_export_commits(write, gcommit):
    from blog_manager.blog.exporter import render_markdown
    s = Site.objects.create(name="s", slug="s")
    p = _mk(s)
    changed, h, path = render_markdown(p, s)
    assert changed is True
    assert gcommit.called

@patch("blog_manager.blog.exporter._git_add_commit_push")
@patch("blog_manager.blog.exporter._safe_write")
def test_second_export_no_change_no_commit(write, gcommit):
    from blog_manager.blog.exporter import render_markdown
    s = Site.objects.create(name="s", slug="s")
    p = _mk(s)
    # primo export → set exported_hash
    changed1, h1, path1 = render_markdown(p, s)
    p.exported_hash = h1
    # secondo export identico → nessun commit
    changed2, h2, path2 = render_markdown(p, s)
    assert changed2 is False
    assert not gcommit.called
