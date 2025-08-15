from datetime import datetime

import pytest

from blog.exporter import render_markdown
from blog.models import Post


class DummyTag:
    def __init__(self, name):
        self.name = name


class DummyCategory:
    def __init__(self, name):
        self.name = name


@pytest.fixture
def published_post():
    return Post(
        title="Test Post",
        published_at=datetime(2025, 8, 10, 12, 0),
        description="A published post.",
        tags=[DummyTag("python"), DummyTag("django")],
        categories=[DummyCategory("tech")],
        image="/images/test.jpg",
        canonical_url="https://example.com/test-post",
        meta_title="Meta Title",
        meta_description="Meta Description",
        meta_keywords="python, django",
        og_title="OG Title",
        og_description="OG Description",
        og_image="/images/og.jpg",
        noindex=False,
        body="# Heading\nContent here.",
    )


@pytest.fixture
def draft_post():
    return Post(
        title="Draft Post",
        published_at=None,
        description="A draft post.",
        tags=[],
        categories=[],
        image=None,
        canonical_url=None,
        meta_title=None,
        meta_description=None,
        meta_keywords=None,
        og_title=None,
        og_description=None,
        og_image=None,
        noindex=True,
        body="Draft content.",
    )


def test_render_markdown_published(snapshot, published_post):
    md = render_markdown(published_post, site={})
    snapshot.assert_match(md, "published_post.md")


def test_render_markdown_draft(snapshot, draft_post):
    md = render_markdown(draft_post, site={})
    snapshot.assert_match(md, "draft_post.md")
