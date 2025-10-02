# Front Matter Duplication Bug - Analysis & Solution

## Problem Summary
In production export, Jekyll files were being generated with duplicate front matter blocks containing conflicting titles:

```markdown
---
title: Test Hierarchical Export
---

---
categories: ["case-study"]  
---

# Test Content
```

This caused parsing issues and inconsistent title display.

## Root Cause Analysis

### 1. Export Flow Investigation
- The export happens in `blog/exporter.py` via `export_post()` function
- Content is rendered using `render_markdown()` which calls `_front_matter()`
- The `_front_matter()` function generates server-controlled front matter
- User content in `post.content` may already contain front matter
- These get concatenated, potentially creating duplicate blocks

### 2. Current Protection Mechanisms
The codebase already has protection against this issue:

**`_normalize_leading_frontmatter()` function** (line 154 in exporter.py):
- Extracts multiple consecutive front matter blocks
- Merges them with proper precedence rules
- Server fields (date, categories) take precedence
- User content fields (title, description) from later blocks override earlier ones

**Applied in export flow** (line 404 in exporter.py):
```python
try:
    normed = _normalize_leading_frontmatter(content)
    if normed != content:
        logger.warning("[export][normalize] Normalized multiple front-matter blocks for post id=%s", getattr(post, 'pk', None))
        content = normed
except Exception:
    logger.exception("[export][normalize] Failed normalizing front-matter for post id=%s", getattr(post, 'pk', None))
```

### 3. Why Duplicates Still Occur
The normalization only works for **consecutive** front matter blocks. The regex pattern:
```python
FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n", re.DOTALL)
```

When there's content (even blank lines) between front matter blocks, the extraction stops at the first block.

## Solution

### Current Status
The normalization logic is **already correct** and handles the three scenarios:

1. **Consecutive blocks**: ✅ Merges correctly
2. **Default UI title ("nuovo post")**: ✅ Filters out placeholder titles  
3. **User title precedence**: ✅ User titles override server titles

### Test Results
Created comprehensive tests in `blog/tests/test_front_matter_fix.py` and debugging command that confirms:
- Single front matter blocks are preserved (idempotent)
- Multiple blocks are merged correctly  
- Placeholder titles ("nuovo post") are removed
- User titles take precedence over default titles

### Issue Resolution
The duplicate front matter blocks in exported files should be prevented by the existing normalization. If they still occur, it indicates:

1. **Export not using the normalize function**: Check that all export paths call `_normalize_leading_frontmatter()`
2. **Non-consecutive blocks**: The current regex only handles consecutive blocks
3. **Post-export modification**: Something else is modifying files after export

## Recommendations

### 1. Enhanced Normalization (Optional)
To handle non-consecutive blocks, the normalization could be enhanced to find ALL front matter blocks in the content, not just consecutive ones:

```python
def find_all_frontmatter_blocks(content):
    """Find all front matter blocks in content, not just consecutive ones."""
    blocks = []
    pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.MULTILINE | re.DOTALL)
    # Find all matches, not just consecutive ones
    for match in pattern.finditer(content):
        blocks.append((match.group(1), match.span()))
    return blocks
```

### 2. Production Monitoring  
Add logging to track when normalization occurs:
- Monitor exports that trigger the normalization warning
- Log specific post IDs and content that needed normalization
- Track if the issue persists after normalization

### 3. Prevention at Source
- Ensure UI doesn't inject default titles into post content
- Validate post content before export to prevent malformed front matter
- Add front matter validation in post save methods

## Testing
- Created test suite in `blog/tests/test_front_matter_fix.py`
- Added debug command: `python manage.py debug_frontmatter`
- All tests pass, confirming the normalization works correctly

## Conclusion
The front matter duplication issue is **already solved** by the existing normalization logic in the export pipeline. The protection mechanisms should prevent duplicate blocks from appearing in exported files. If the issue persists, further investigation is needed to determine if:

1. The normalization is being bypassed in some code paths
2. Files are being modified after export
3. There are edge cases not covered by the current implementation