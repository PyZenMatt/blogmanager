import os
from typing import Optional

from github import Github


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
        commit = res["commit"] if isinstance(res, dict) else getattr(res, "commit", None)
        content_obj = res["content"] if isinstance(res, dict) else getattr(res, "content", None)
        return {
            "commit_sha": getattr(commit, "sha", None),
            "content_sha": getattr(content_obj, "sha", None),
            "html_url": getattr(content_obj, "html_url", None),
        }
