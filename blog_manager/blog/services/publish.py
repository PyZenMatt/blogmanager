from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from blog.exporter import build_post_relpath, compute_canonical_url, render_markdown
from blog.github_client import GitHubClient
from blog.models import ExportJob, Post


@dataclass
class PublishResult:
    path: str
    commit_sha: str
    canonical_url: Optional[str]


def _validate_site(post: Post):
    site = post.site
    missing = []
    if not site.repo_owner:
        missing.append("repo_owner")
    if not site.repo_name:
        missing.append("repo_name")
    if not site.default_branch:
        missing.append("default_branch")
    if missing:
        raise ValueError(f"Missing site repo config: {', '.join(missing)}")
    return site


def publish_post(
    post: Post | int, *, token: Optional[str] = None, message: Optional[str] = None
) -> PublishResult:
    if isinstance(post, int):
        post = (
            Post.objects.select_related("site")
            .prefetch_related("categories", "tags")
            .get(pk=post)
        )
    if post.status != "published" or not post.published_at:
        raise ValueError("Post must be published and have published_at set")

    site = _validate_site(post)

    # Render markdown
    content = render_markdown(post, site)
    rel_path = build_post_relpath(post, site)
    branch = site.default_branch or "main"
    commit_msg = message or f"publish/update: {post.title} (post #{post.id})"

    # Commit to GitHub
    gh = GitHubClient(token)
    result = gh.upsert_file(
        site.repo_owner,
        site.repo_name,
        rel_path,
        content,
        branch=branch,
        message=commit_msg,
    )

    # Compute canonical URL if missing
    canonical = compute_canonical_url(post, site)

    # Audit + ExportJob
    ExportJob.objects.create(
        post=post,
        commit_sha=result.get("commit_sha"),
        repo_url=f"https://github.com/{site.repo_owner}/{site.repo_name}",
        branch=branch,
        path=rel_path,
        export_status="success",
    )

    post.last_commit_sha = result.get("commit_sha")
    post.repo_path = rel_path
    post.exported_at = timezone.now()
    if canonical and not post.canonical_url:
        post.canonical_url = canonical
    post.export_status = "success"
    post.last_export_path = rel_path
    post.save(
        update_fields=[
            "last_commit_sha",
            "repo_path",
            "exported_at",
            "canonical_url",
            "export_status",
            "last_export_path",
            "updated_at",
        ]
    )

    return PublishResult(
        path=rel_path,
        commit_sha=result.get("commit_sha"),
        canonical_url=post.canonical_url,
    )
