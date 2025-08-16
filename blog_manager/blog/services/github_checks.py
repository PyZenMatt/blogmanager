from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, List, Tuple, Union

from github import Github


@dataclass
class Check:
    name: str
    ok: bool
    details: str = ""


def _get_repo(token: str, owner: str, repo: str):
    gh = Github(token)
    return gh.get_repo(f"{owner}/{repo}")


def check_repo_access(token: str, owner: str, repo: str) -> dict:
    try:
        r = _get_repo(token, owner, repo)
        name = r.full_name
        return {"name": "repo_access", "ok": True, "details": f"reachable: {name}"}
    except Exception as e:
        return {"name": "repo_access", "ok": False, "details": f"error: {e}"}


def check_permissions(token: str, owner: str, repo: str, need_pr: bool) -> dict:
    try:
        r = _get_repo(token, owner, repo)
        perms = r.permissions or {}
        push = getattr(perms, "push", False)
        pull = getattr(perms, "pull", False)
        if need_pr:
            ok = bool(pull)
            return {
                "name": "permissions",
                "ok": ok,
                "details": f"pull={pull}, push={push} (strategy=PR)",
            }
        else:
            ok = bool(push)
            return {
                "name": "permissions",
                "ok": ok,
                "details": f"push={push}, pull={pull} (strategy=direct)",
            }
    except Exception as e:
        return {"name": "permissions", "ok": False, "details": f"error: {e}"}


def check_branch(token: str, owner: str, repo: str, branch: str) -> dict:
    try:
        r = _get_repo(token, owner, repo)
        b = r.get_branch(branch)
        protected = getattr(b, "protected", False)
        return {
            "name": "branch",
            "ok": True,
            "details": f"exists: {branch}, protected={protected}",
            "protected": protected,
        }
    except Exception as e:
        return {"name": "branch", "ok": False, "details": f"error: {e}"}


def check_pages_workflow(token: str, owner: str, repo: str) -> dict:
    try:
        r = _get_repo(token, owner, repo)
        items: Union[List[Any], Any] = r.get_contents(".github/workflows")
        found = False
        names: List[str] = []
        if isinstance(items, list):
            iterable = items
        else:
            iterable = [items]
        for item in iterable:
            if getattr(item, "type", "file") == "file" and (
                str(getattr(item, "name", "")).endswith(".yml") or str(getattr(item, "name", "")).endswith(".yaml")
            ):
                names.append(str(getattr(item, "name", "")))
                # Try to detect pages keywords
                try:
                    file_obj: Any = r.get_contents(getattr(item, "path", item))
                    content_b64 = getattr(file_obj, "content", None)
                    if content_b64:
                        decoded = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
                        if (
                            "deploy-pages" in decoded
                            or "github-pages" in decoded
                            or "pages:" in decoded
                            or "actions/deploy-pages" in decoded
                        ):
                            found = True
                except Exception:
                    pass
        return {
            "name": "pages_workflow",
            "ok": found,
            "details": f".github/workflows files: {', '.join(names) or 'none'}; detected_pages={found}",
        }
    except Exception as e:
        return {"name": "pages_workflow", "ok": False, "details": f"error: {e}"}


def summarize(statuses: List[dict]) -> Tuple[bool, str]:
    ok = all(s.get("ok") for s in statuses)
    lines = [("✅" if s.get("ok") else "❌") + f" {s.get('name')}: {s.get('details', '')}" for s in statuses]
    return ok, "\n".join(lines)
