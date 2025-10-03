import pytest

from blog.serializers import PostWriteSerializer


def test_post_write_serializer_rejects_categories_key():
    # Minimal payload with a body and title; including categories should cause validation error
    payload = {
        "title": "Test post",
        "body": "---\n---\nContent",
        "site": 1,
        "categories": [1, 2, 3],
    }

    serializer = PostWriteSerializer(data=payload)
    assert not serializer.is_valid()
    assert 'categories' in serializer.errors
