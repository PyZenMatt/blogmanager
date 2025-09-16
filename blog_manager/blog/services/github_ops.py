from typing import Optional

from blog.github_client import GitHubClient


def delete_post_from_repo(post, *, message: str, client: Optional[GitHubClient] = None):
    """Minimal wrapper to delete a post file from its repo, audit the result via ExportJob, and return the client response.

    Expects `post` to have attributes: `repo_owner`, `repo_name`, `repo_path`, `repo_branch`.
    """
    client = client or GitHubClient()
    if not getattr(post, "repo_path", None):
        return {"status": "no_repo_path"}

    owner = getattr(post, "repo_owner")
    repo = getattr(post, "repo_name")
    path = getattr(post, "repo_path")
    branch = getattr(post, "repo_branch", "main")

    res = client.delete_file(owner, repo, path, branch=branch, message=message)

    # Try to record audit in ExportJob if model available (best-effort, avoid hard dependency in test)
    try:
        from blog.models import ExportJob

        ExportJob.objects.create(
            post=getattr(post, "pk", None) and post or None,
            commit_sha=res.get("commit_sha"),
            repo_url=None,
            branch=branch,
            path=path,
            export_status="success" if res.get("status") in ("deleted", "already_absent") else "failed",
            export_error=None if res.get("status") in ("deleted", "already_absent") else str(res),
        )
    except Exception:
        # In environments without Django ORM available (e.g., unit tests without DB), skip audit creation.
        pass

    return res
