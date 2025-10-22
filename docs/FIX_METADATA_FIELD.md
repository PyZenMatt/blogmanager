# Fix: Removed metadata field references

## Issue
```
AttributeError: 'PreviewSession' object has no attribute 'metadata'
```

## Root Cause
The code was trying to use `session.metadata` field which doesn't exist in the `PreviewSession` model.

## Model Schema
```python
class PreviewSession(models.Model):
    uuid = models.UUIDField(...)
    site = models.ForeignKey(Site, ...)
    source_branch = models.CharField(...)
    preview_branch = models.CharField(...)
    pr_number = models.IntegerField(null=True, blank=True)
    preview_url = models.CharField(max_length=255, blank=True)  # ✅ Use this
    status = models.CharField(...)
    last_error = models.TextField(...)
    created_at = models.DateTimeField(...)
    updated_at = models.DateTimeField(...)
    # ❌ NO metadata field
```

## Solution

### blog/views.py (line 340-349)
**Before:**
```python
session.metadata = session.metadata or {}
session.metadata['expected_preview_url'] = f"{preview_base_url}/{site.slug}/post/{pr_number}/"
session.save(update_fields=['pr_number', 'preview_url', 'status', 'metadata', 'updated_at'])
```

**After:**
```python
# Store expected preview URL directly in preview_url field
expected_preview_url = f"{preview_base_url}/{site.slug}/post/{pr_number}/"
session.preview_url = expected_preview_url
session.status = 'pr_open'
session.save(update_fields=['pr_number', 'preview_url', 'status', 'updated_at'])
```

### writer/views.py (line 105-108)
**Before:**
```python
post_ids = session.metadata.get('post_ids', []) if session.metadata else []
post_count = len(post_ids) if isinstance(post_ids, list) else 0
expected_url = session.metadata.get('expected_preview_url') if session.metadata else None
```

**After:**
```python
# Get post count and expected URL from existing fields
post_count = 0  # Not currently tracked in model
expected_url = session.preview_url or None
```

## Preview URL Format
The `preview_url` field now stores the expected GitHub Pages URL:
```
https://pyzenmatt.github.io/blogmanager-previews/{site.slug}/post/{PR_NUMBER}/
```

Example:
```
https://pyzenmatt.github.io/blogmanager-previews/matteoriccinet/post/42/
```

## Testing
```bash
# Verify no more metadata references
cd /home/teo/Project/blogmanager/blog_manager
grep -r "session.metadata" blog/views.py
# Should return no results

# Test preview creation
curl -X POST http://localhost:8000/api/sites/5/preview/ \
  -H "Content-Type: application/json" \
  -d '{"post_ids": [623]}' \
  | jq .
```

## Files Changed
- `blog/views.py`: Removed metadata field usage, store URL in preview_url
- `writer/views.py`: Use preview_url field instead of metadata
- `docs/PREVIEW_SESSIONS_MANAGEMENT.md`: Updated documentation

## Status
✅ Fixed - All metadata references removed
✅ Preview URL now stored in `preview_url` field
✅ No breaking changes to API response format
