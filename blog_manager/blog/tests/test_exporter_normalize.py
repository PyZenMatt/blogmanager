import pytest
from blog.exporter import _normalize_leading_frontmatter


def test_normalize_merges_multiple_frontmatter_blocks():
    content = (
        "---\n"
        "title: nuovo post\n"
        "---\n"
        "---\n"
        "title: 'User Title'\n"
        "description: 'User desc'\n"
        "---\n"
        "# Body\n"
    )
    norm = _normalize_leading_frontmatter(content)
    # Should have only one leading --- block
    assert norm.count('---\n') >= 1
    # After normalization, only one leading block followed by body
    assert norm.startswith('---\n')
    # Title should be the user-provided one
    assert "User Title" in norm
    assert "nuovo post" not in norm


def test_normalize_idempotent():
    content = (
        "---\n"
        "title: 'User Title'\n"
        "---\n"
        "# Body\n"
    )
    n1 = _normalize_leading_frontmatter(content)
    n2 = _normalize_leading_frontmatter(n1)
    assert n1 == n2
