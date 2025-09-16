import os
from typing import Optional

from github import Github, GithubException


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        token = token or os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        self.gh = Github(token)

    def upsert_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        branch: str = "main",
        message: str = "update file",
    ) -> dict:
        """
        Create or update a file at path with content on branch. Returns dict with sha and url fields.
        """
        r = self.gh.get_repo(f"{owner}/{repo}")
        try:
            existing = r.get_contents(path, ref=branch)
            res = r.update_file(path, message, content, existing.sha, branch=branch)
        except Exception:
            res = r.create_file(path, message, content, branch=branch)
        commit = (
            res["commit"] if isinstance(res, dict) else getattr(res, "commit", None)
        )
        content_obj = (
            res["content"] if isinstance(res, dict) else getattr(res, "content", None)
        )
        return {
            "commit_sha": getattr(commit, "sha", None),
            "content_sha": getattr(content_obj, "sha", None),
            "html_url": getattr(content_obj, "html_url", None),
        }

    def delete_file(
        self,
        owner: str,
        repo: str,
        path: str,
        *,
        branch: str = "main",
        message: str = "delete file",
    ) -> dict:
        """
        Delete a file at `path` on `branch`. Treat 404 on get_contents as idempotent success.
        Returns dict with `status` ("deleted"|"already_absent"), `commit_sha` and `html_url`.
        """
        r = self.gh.get_repo(f"{owner}/{repo}")
        try:
            existing = r.get_contents(path, ref=branch)
        except GithubException as e:
            if getattr(e, "status", None) == 404:
                return {"status": "already_absent", "commit_sha": None, "html_url": None}
            raise GithubException(e.status, {"message": f"Error getting contents for {owner}/{repo}@{branch} path: {path}: {e}"})

        try:
            res = r.delete_file(path, message, existing.sha, branch=branch)
        except GithubException as e:
            raise GithubException(e.status, {"message": f"GitHub delete_file error for {owner}/{repo}@{branch} path: {path}: {e}"})

        commit = res["commit"] if isinstance(res, dict) else getattr(res, "commit", None)
        commit_sha = getattr(commit, "sha", None)
        html_url = getattr(commit, "html_url", None)
        return {"status": "deleted", "commit_sha": commit_sha, "html_url": html_url}
