"""
Preview utilities for per-site preview system.

This module provides functions to export posts to their respective site's Jekyll repository
in a dedicated preview directory, maintaining each site's theme and configuration:
  https://<owner>.github.io/<repo_name>/preview/<post_id>/

Key differences from production export:
- Each site uses its own repo (Site.repo_owner/repo_name)
- Path structure: preview/<post_id>/index.md
- Preview uses the same Jekyll theme as the production site
- Simplified front-matter (minimal required fields only)
"""

import logging
import os
from typing import Optional

from django.conf import settings
from django.utils import timezone

from .github_client import GitHubClient
from .exporter import (
    _extract_frontmatter_from_body,
    _validate_frontmatter_taxonomy,
    _select_date,
    _strip_leading_frontmatter,
    _normalize_yaml_indentation,
    FrontMatterValidationError,
)

logger = logging.getLogger(__name__)


def build_preview_path(site, post) -> str:
    """
    Build the preview path for a post in the site's repository.
    
    Path format: preview/<post_id>/index.md
    
    Args:
        site: Site instance
        post: Post instance
        
    Returns:
        str: Relative path in the site's repository
    """
    post_id = getattr(post, 'id', 'new')
    return f"preview/{post_id}/index.md"


def build_preview_front_matter(post, site) -> str:
    """
    Build minimal front-matter for preview export.
    
    Only includes essential fields:
    - layout: post
    - date: publication date
    - categories: [<cluster>]
    - subcluster: (if present)
    - description: (if present)
    - canonical: (if present)
    
    Merges any existing front-matter from post body, with server-controlled
    fields taking precedence.
    
    Args:
        post: Post instance
        site: Site instance
        
    Returns:
        str: YAML front-matter block with delimiters
        
    Raises:
        FrontMatterValidationError: If taxonomy validation fails
    """
    import yaml
    
    # Extract and validate front-matter from body
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    fm_body = _extract_frontmatter_from_body(body)
    
    # Validate taxonomy (cluster/subcluster)
    try:
        cluster, subcluster, audit_msgs = _validate_frontmatter_taxonomy(post, fm_body)
        
        for msg in audit_msgs:
            logger.info("[preview][frontmatter] %s", msg)
            
    except FrontMatterValidationError as e:
        logger.error(
            "[preview][validator] Front-matter validation failed for post id=%s: %s",
            getattr(post, 'id', None), str(e)
        )
        raise
    
    # Build baseline server-controlled front-matter
    data = {
        "layout": "post",
        "date": _select_date(post).strftime("%Y-%m-%d %H:%M:%S"),
        "categories": [cluster],
        "published": True,  # Force preview to always be published
    }
    
    # Add optional subcluster
    if subcluster:
        data["subcluster"] = subcluster
    
    # Add optional canonical URL
    canonical = getattr(post, "canonical_url", "") or ""
    if canonical and canonical.strip():
        data["canonical"] = canonical.strip()
    
    # Add optional description
    description = getattr(post, "description", "") or ""
    if description and description.strip():
        data["description"] = description.strip()
    
    # Merge with body front-matter if present
    if isinstance(fm_body, dict):
        merged = dict(fm_body)
        
        # Remove fields we don't want in preview
        merged.pop("slug", None)  # Path controls slug in preview
        
        # Clean empty title
        if "title" in merged and not merged.get("title"):
            merged.pop("title", None)
        
        # Clean empty optional fields
        for key in ["canonical", "description", "tags"]:
            if key in merged:
                value = merged[key]
                if (not value or 
                    (isinstance(value, (list, tuple)) and len(value) == 0) or 
                    (isinstance(value, str) and not value.strip())):
                    merged.pop(key, None)
        
        # Overlay server-authoritative fields
        merged["layout"] = data["layout"]
        merged["date"] = data["date"]
        merged["categories"] = data["categories"]
        merged["published"] = True  # Force preview to be published
        
        if "subcluster" in data:
            merged["subcluster"] = data["subcluster"]
        if "canonical" not in merged and "canonical" in data:
            merged["canonical"] = data["canonical"]
        if "description" not in merged and "description" in data:
            merged["description"] = data["description"]
            
        data = merged
    
    # Serialize to YAML
    yaml_content = yaml.dump(
        data,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False
    )
    
    return f"---\n{yaml_content}---\n"


def render_preview_content(post, site) -> str:
    """
    Render full preview content (front-matter + body).
    
    Args:
        post: Post instance
        site: Site instance
        
    Returns:
        str: Complete markdown content for preview
        
    Raises:
        FrontMatterValidationError: If validation or rendering fails
    """
    # Build front-matter
    fm = build_preview_front_matter(post, site)
    
    # Get and normalize body
    body = getattr(post, "content", "") or getattr(post, "body", "") or ""
    body = _normalize_yaml_indentation(body)
    body = _strip_leading_frontmatter(body)
    
    if not body.endswith("\n"):
        body = body + "\n"
    
    # Resolve link shortcodes if enabled
    try:
        if getattr(settings, 'LINK_RESOLVER_ENABLED', True):
            from .link_resolver import LinkResolver
            
            resolved_body, errors = LinkResolver.resolve(body, site)
            if errors:
                raise FrontMatterValidationError(
                    "Link resolution errors: " + "; ".join(errors)
                )
            body = resolved_body
    except FrontMatterValidationError:
        raise
    except Exception:
        logger.exception(
            "LinkResolver failed while processing post id=%s",
            getattr(post, 'id', None)
        )
        raise
    
    return fm + "\n" + body


def build_preview_url(post, site) -> str:
    """
    Build the full preview URL for a post.
    
    Format: https://<owner>.github.io/<repo_name>/preview/<post_id>/
    
    Args:
        post: Post instance
        site: Site instance
        
    Returns:
        str: Full preview URL
    """
    repo_owner = getattr(site, 'repo_owner', '').strip()
    repo_name = getattr(site, 'repo_name', '').strip()
    post_id = getattr(post, 'id', 'new')
    
    if not repo_owner or not repo_name:
        raise ValueError(
            f"Site {getattr(site, 'slug', 'unknown')} missing repo_owner or repo_name"
        )
    
    # GitHub Pages URL format
    base_url = f"https://{repo_owner.lower()}.github.io/{repo_name}"
    return f"{base_url}/preview/{post_id}/"


def export_post_to_preview(post, site=None) -> dict:
    """
    Export a single post to its site's preview directory.
    
    This exports to the site's own Jekyll repository (Site.repo_owner/repo_name)
    in a dedicated preview/<post_id>/ directory, maintaining the site's theme.
    
    Args:
        post: Post instance to export
        site: Site instance (optional, will use post.site if not provided)
        
    Returns:
        dict with keys:
            - preview_url: Full URL to preview the post
            - preview_path: Relative path in site's repo
            - commit_sha: Git commit SHA
            - content_sha: GitHub content SHA
            
    Raises:
        ValueError: If preview is disabled or configuration is missing
        FrontMatterValidationError: If content validation fails
    """
    # Check if preview is enabled
    if not getattr(settings, 'PREVIEW_ENABLED', True):
        raise ValueError("Preview functionality is disabled (PREVIEW_ENABLED=False)")
    
    # Validate GitHub token is available
    git_token = os.getenv("GIT_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not git_token:
        raise ValueError(
            "GIT_TOKEN not configured - required for preview export"
        )
    
    # Get site
    if site is None:
        site = getattr(post, 'site', None)
    if not site:
        raise ValueError("Site is required for preview export")
    
    # Get site repository configuration
    repo_owner = getattr(site, 'repo_owner', '').strip()
    repo_name = getattr(site, 'repo_name', '').strip()
    repo_branch = getattr(site, 'default_branch', 'main').strip()
    
    if not repo_owner or not repo_name:
        raise ValueError(
            f"Site {getattr(site, 'slug', 'unknown')} missing repo_owner or repo_name - "
            "required for preview export"
        )
    
    post_id = getattr(post, 'id', None)
    site_slug = getattr(site, 'slug', 'default')
    
    logger.info(
        "[preview.export] start: post_id=%s site=%s dest_repo=%s/%s@%s",
        post_id, site_slug, repo_owner, repo_name, repo_branch
    )
    
    try:
        # Build preview content
        content = render_preview_content(post, site)
        
        # Build preview path
        preview_path = build_preview_path(site, post)
        
        logger.info(
            "[preview.export] post_id=%s preview_path='%s'",
            post_id, preview_path
        )
        
        # Export to GitHub
        gh_client = GitHubClient(token=git_token)
        commit_msg = f"preview: post {post_id} ({timezone.now().date()})"
        
        result = gh_client.upsert_file(
            owner=repo_owner,
            repo=repo_name,
            path=preview_path,
            content=content,
            branch=repo_branch,
            message=commit_msg
        )
        
        # Build preview URL
        preview_url = build_preview_url(post, site)
        
        logger.info(
            "[preview.export] success: post_id=%s commit_sha=%s preview_url=%s",
            post_id, result.get('commit_sha'), preview_url
        )
        
        return {
            'preview_url': preview_url,
            'preview_path': preview_path,
            'commit_sha': result.get('commit_sha'),
            'content_sha': result.get('content_sha'),
        }
        
    except FrontMatterValidationError as e:
        logger.error(
            "[preview.export] validation failed: post_id=%s error=%s",
            post_id, str(e)
        )
        raise
    except Exception as e:
        logger.exception(
            "[preview.export] failed: post_id=%s site=%s",
            post_id, site_slug
        )
        raise


def delete_post_from_preview(post, site=None) -> dict:
    """
    Delete a post's preview from its site's repository.
    
    Args:
        post: Post instance to delete
        site: Site instance (optional, will use post.site if not provided)
        
    Returns:
        dict with keys:
            - status: 'deleted' or 'already_absent'
            - preview_path: Relative path that was deleted
            - commit_sha: Git commit SHA (if deleted)
            
    Raises:
        ValueError: If preview is disabled or configuration is missing
    """
    # Check if preview is enabled
    if not getattr(settings, 'PREVIEW_ENABLED', True):
        raise ValueError("Preview functionality is disabled (PREVIEW_ENABLED=False)")
    
    # Validate GitHub token is available
    git_token = os.getenv("GIT_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not git_token:
        raise ValueError(
            "GIT_TOKEN not configured - required for preview deletion"
        )
    
    # Get site
    if site is None:
        site = getattr(post, 'site', None)
    if not site:
        raise ValueError("Site is required for preview deletion")
    
    # Get site repository configuration
    repo_owner = getattr(site, 'repo_owner', '').strip()
    repo_name = getattr(site, 'repo_name', '').strip()
    repo_branch = getattr(site, 'default_branch', 'main').strip()
    
    if not repo_owner or not repo_name:
        raise ValueError(
            f"Site {getattr(site, 'slug', 'unknown')} missing repo_owner or repo_name - "
            "required for preview deletion"
        )
    
    post_id = getattr(post, 'id', None)
    site_slug = getattr(site, 'slug', 'default')
    
    logger.info(
        "[preview.delete] start: post_id=%s site=%s dest_repo=%s/%s@%s",
        post_id, site_slug, repo_owner, repo_name, repo_branch
    )
    
    try:
        # Build preview path
        preview_path = build_preview_path(site, post)
        
        # Delete from GitHub
        gh_client = GitHubClient(token=git_token)
        commit_msg = f"preview: delete post {post_id}"
        
        result = gh_client.delete_file(
            owner=repo_owner,
            repo=repo_name,
            path=preview_path,
            branch=repo_branch,
            message=commit_msg
        )
        
        logger.info(
            "[preview.delete] %s: post_id=%s preview_path=%s commit_sha=%s",
            result.get('status'), post_id, preview_path, result.get('commit_sha')
        )
        
        return {
            'status': result.get('status'),
            'preview_path': preview_path,
            'commit_sha': result.get('commit_sha'),
        }
        
    except Exception as e:
        logger.exception(
            "[preview.delete] failed: post_id=%s site=%s",
            post_id, site_slug
        )
        raise
