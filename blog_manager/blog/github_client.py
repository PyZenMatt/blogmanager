import os
from typing import Optional

from github import Github, GithubException


def _friendly_error(e: GithubException, context: str) -> GithubException:
    status = getattr(e, "status", None)
    # Map common statuses to clearer messages
    if status in (401, 403):
        msg = "Token mancante o permessi insufficienti"
    elif status == 429:
        msg = "Rate limit raggiunto: riprova più tardi"
    else:
        msg = str(e)
    return GithubException(status, {"message": f"{context}: {msg}"})


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GIT_TOKEN")
        if not token:
            # Allow unauthenticated access for public repos; caller should handle permission errors.
            import warnings

            warnings.warn("GITHUB_TOKEN/GIT_TOKEN not set: using unauthenticated GitHub client (rate limits stricter).", RuntimeWarning)
            self.gh = Github()
        else:
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
            try:
                existing = r.get_contents(path, ref=branch)
                res = r.update_file(path, message, content, existing.sha, branch=branch)
            except GithubException as e:
                # If not found, create; for auth/rate-limit propagate friendly error
                if getattr(e, "status", None) == 404:
                    res = r.create_file(path, message, content, branch=branch)
                else:
                    raise _friendly_error(e, f"Error accessing contents for {owner}/{repo}@{branch} {path}")
        except GithubException:
            # re-raise as-is for caller to handle
            raise
        except Exception:
            # Fallback create if library returns unexpected exception
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
            # Map common errors to friendly message
            raise _friendly_error(e, f"Error getting contents for {owner}/{repo}@{branch} path: {path}")

        try:
            res = r.delete_file(path, message, existing.sha, branch=branch)
        except GithubException as e:
            raise _friendly_error(e, f"GitHub delete_file error for {owner}/{repo}@{branch} path: {path}")

        commit = res["commit"] if isinstance(res, dict) else getattr(res, "commit", None)
        commit_sha = getattr(commit, "sha", None)
        html_url = getattr(commit, "html_url", None)
        return {"status": "deleted", "commit_sha": commit_sha, "html_url": html_url}

    def get_file(self, owner: str, repo: str, path: str, branch: str = "main") -> dict:
        """Return the file content and metadata from repo. Raises GithubException for errors other than 404.

        Returns: {"content": str, "encoding": str, "sha": str}
        If file not found raises the original GithubException with status 404.
        """
        r = self.gh.get_repo(f"{owner}/{repo}")
        try:
            c = r.get_contents(path, ref=branch)
        except GithubException as e:
            # Propagate friendly errors for auth/rate-limit etc.
            raise _friendly_error(e, f"Error getting file {owner}/{repo}@{branch} path: {path}")
        # content is base64-encoded if using PyGithub ContentFile; expose raw content
        raw = None
        try:
            raw = c.decoded_content.decode("utf-8") if hasattr(c, "decoded_content") else getattr(c, "content", None)
        except Exception:
            raw = getattr(c, "content", None)
        return {"content": raw, "encoding": getattr(c, "encoding", None), "sha": getattr(c, "sha", None)}

    def list_files(self, owner: str, repo: str, path: str = "", branch: str = "main") -> list:
        """
        List repository files under `path` at `branch` recursively.
        Returns a list of dicts: {"path": str, "type": "file"|"dir", "sha": str}
        """
        r = self.gh.get_repo(f"{owner}/{repo}")
        try:
            contents = r.get_contents(path or "", ref=branch)
        except GithubException as e:
            raise _friendly_error(e, f"Error listing contents for {owner}/{repo}@{branch} path: {path}")

        results_map = {}

        def _walk(items):
            for it in items:
                t = getattr(it, "type", None) or ("dir" if hasattr(it, "type") and it.type == "dir" else "file")
                p = getattr(it, "path", None)
                s = getattr(it, "sha", None)
                if p and p not in results_map:
                    results_map[p] = {"path": p, "type": t, "sha": s}
                if t == "dir":
                    try:
                        children = r.get_contents(p, ref=branch)
                        if not isinstance(children, list):
                            children = [children]
                        _walk(children)
                    except GithubException as e:
                        # propagate friendly error
                        raise _friendly_error(e, f"Error listing dir {p} in {owner}/{repo}@{branch}")

        # `contents` may be a single ContentFile or a list
        if not isinstance(contents, list):
            contents = [contents]
        _walk(contents)
        return list(results_map.values())
