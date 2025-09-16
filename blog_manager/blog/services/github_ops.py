from typing import Optional

from blog.github_client import GitHubClient


def delete_post_from_repo(post, *, message: str, client: Optional[GitHubClient] = None):
    """Minimal wrapper to delete a post file from its repo, audit the result via ExportJob, and return the client response.

    Expects `post` to have attributes: `repo_owner`, `repo_name`, `repo_path`, `repo_branch`.
    """
    client = client or GitHubClient()
    # repo_path usually stored on the Post; if missing, try site.repo_path
    path = getattr(post, "repo_path", None)
    if not path:
        site = getattr(post, "site", None)
        path = getattr(site, "posts_dir", None)
    if not path:
        return {"status": "no_repo_path"}

    # owner/repo/branch may be on the Post or on the related Site
    site = getattr(post, "site", None)
    owner = getattr(post, "repo_owner", None) or (getattr(site, "repo_owner", None) if site else None)
    repo = getattr(post, "repo_name", None) or (getattr(site, "repo_name", None) if site else None)
    branch = getattr(post, "repo_branch", None) or (getattr(site, "default_branch", None) if site else "main")

    res = client.delete_file(owner, repo, path, branch=branch, message=message)

    # Try to record audit in ExportJob if model available (best-effort, avoid hard dependency in test)
    try:
        from blog.models import ExportJob

        ExportJob.objects.create(
            post=post,
            commit_sha=res.get("commit_sha"),
            repo_url=None,
            branch=branch,
            path=path,
            export_status="success" if res.get("status") in ("deleted", "already_absent") else "failed",
            action=("delete_repo_and_db" if res.get("status") == "deleted" else "delete_db_only"),
            message=(None if res.get("status") in ("deleted", "already_absent") else str(res)),
        )
    except Exception:
        # In environments without Django ORM available (e.g., unit tests without DB), skip audit creation.
        pass

    return res
