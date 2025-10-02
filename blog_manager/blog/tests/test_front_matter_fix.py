"""
Test for the front matter duplication fix.

This test demonstrates the issue described in the bug report where 
production exports create duplicate front matter blocks with conflicting titles.
"""
import pytest
import re
import yaml
from blog.exporter import _normalize_leading_frontmatter, FRONTMATTER_RE


def test_duplicate_front_matter_issue():
    """Test the specific issue: two front matter blocks with conflicting titles."""
    # This is the problematic content that gets exported in production
    problematic_content = """---
title: nuovo post
---
---
title: 'Test Hierarchical Export'
categories: ["case-study"]
---

# Test

Test gerarchico.
"""
    
    # This should normalize to a single front matter block
    normalized = _normalize_leading_frontmatter(problematic_content)
    
    # Count front matter blocks - should be exactly 1
    front_matter_blocks = FRONTMATTER_RE.findall(normalized)
    assert len(front_matter_blocks) == 1, f"Expected 1 front matter block, got {len(front_matter_blocks)}"
    
    # Parse the front matter and check title
    fm_data = yaml.safe_load(front_matter_blocks[0])
    
    # Title should be the user's title, not the default "nuovo post"
    assert fm_data.get("title") == "Test Hierarchical Export"
    assert "nuovo post" not in str(fm_data)
    
    # Should preserve user categories
    assert fm_data.get("categories") == ["case-study"]


def test_single_front_matter_is_preserved():
    """Test that content with single front matter block remains unchanged."""
    good_content = """---
title: 'User Title'
categories: ["tech"]
---

# Content
"""
    
    normalized = _normalize_leading_frontmatter(good_content)
    
    # Should be identical (idempotent)
    assert normalized == good_content


def test_empty_or_placeholder_title_removed():
    """Test that empty or placeholder titles are removed."""
    content_with_placeholder = """---
title: nuovo post
---
---
categories: ["tech"]
---

# Content
"""
    
    normalized = _normalize_leading_frontmatter(content_with_placeholder)
    front_matter_blocks = FRONTMATTER_RE.findall(normalized)
    fm_data = yaml.safe_load(front_matter_blocks[0])
    
    # Placeholder title should be removed
    assert "title" not in fm_data or not fm_data.get("title")
    assert fm_data.get("categories") == ["tech"]


def test_user_title_overrides_db_title():
    """Test that user-provided title in front matter takes precedence."""
    content = """---
title: DB Title
layout: post
---
---
title: User Provided Title
description: User description
---

# Content
"""
    
    normalized = _normalize_leading_frontmatter(content)
    front_matter_blocks = FRONTMATTER_RE.findall(normalized)
    fm_data = yaml.safe_load(front_matter_blocks[0])
    
    # User title should win
    assert fm_data.get("title") == "User Provided Title"
    assert fm_data.get("description") == "User description"
    assert fm_data.get("layout") == "post"  # Server field preserved


def improved_normalize_leading_frontmatter(content: str) -> str:
    """
    Improved version of _normalize_leading_frontmatter that handles the 
    duplicate front matter issue correctly.
    """
    if not content:
        return content
    
    parts = []
    rest = content
    
    # Extract all consecutive front-matter blocks at start
    while True:
        m = FRONTMATTER_RE.match(rest)
        if not m:
            break
        parts.append(m.group(1))
        rest = rest[m.end():]

    if not parts:
        return content

    # Merge parts with proper precedence rules
    merged = {}
    server_authoritative = {"layout", "date", "categories", "tags", "canonical", "description"}
    
    for i, part in enumerate(parts):
        try:
            data = yaml.safe_load(part) or {}
            if isinstance(data, dict):
                for key, value in data.items():
                    if key == "title":
                        # Handle title with special logic
                        if value and str(value).strip() and str(value).strip() != "nuovo post":
                            # Valid user title - keep it (later ones override earlier)
                            merged[key] = value
                        # Skip empty titles or default placeholders
                    elif key in server_authoritative:
                        # Server authoritative: first occurrence wins
                        if key not in merged:
                            merged[key] = value
                    else:
                        # User custom fields: later blocks override earlier
                        merged[key] = value
        except Exception:
            continue

    # Clean up empty or placeholder titles
    if "title" in merged:
        title_val = str(merged.get("title", "")).strip()
        if not title_val or title_val == "nuovo post":
            merged.pop("title", None)

    # Generate normalized content
    fm_text = yaml.dump(merged, default_flow_style=False, allow_unicode=True, sort_keys=False)
    normalized = f"---\n{fm_text}---\n{rest.lstrip() or ''}"
    return normalized


def test_improved_normalizer():
    """Test the improved normalizer function."""
    problematic_content = """---
title: nuovo post
---
---
title: 'User Title'
description: 'User desc'
---

# Body
"""
    
    normalized = improved_normalize_leading_frontmatter(problematic_content)
    
    # Should have only one front matter block
    front_matter_blocks = FRONTMATTER_RE.findall(normalized)
    assert len(front_matter_blocks) == 1
    
    # Parse and verify
    fm_data = yaml.safe_load(front_matter_blocks[0])
    assert fm_data.get("title") == "User Title"
    assert fm_data.get("description") == "User desc"
    assert "nuovo post" not in normalized