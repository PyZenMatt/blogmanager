from typing import Optional
import os
import subprocess

from blog.github_client import GitHubClient


def delete_post_from_repo(post, *, message: str, client: Optional[GitHubClient] = None, sync_local: bool = False):
    """Minimal wrapper to delete a post file from its repo, audit the result via ExportJob, and return the client response.

    Expects `post` to have attributes: `repo_owner`, `repo_name`, `repo_path`, `repo_branch`.
    """
    client = client or GitHubClient()
    # repo_path usually stored on the Post; if missing, try last_export_path or construct via exporter
    path = getattr(post, "repo_path", None)
    if not path:
        path = getattr(post, "last_export_path", None)
    if not path:
        try:
            # try to construct using exporter.build_post_relpath if available
            from blog.exporter import build_post_relpath

            site = getattr(post, "site", None)
            if site:
                path = build_post_relpath(post, site)
        except Exception:
            path = None

    if not path:
        return {"status": "no_repo_path", "message": "Post has no repo_path and no last_export_path or computed path"}

    # owner/repo/branch may be on the Post or on the related Site
    site = getattr(post, "site", None)
    owner = getattr(post, "repo_owner", None) or (getattr(site, "repo_owner", None) if site else None)
    repo = getattr(post, "repo_name", None) or (getattr(site, "repo_name", None) if site else None)
    branch = getattr(post, "repo_branch", None) or (getattr(site, "default_branch", None) if site else "main")
    if not branch:
        branch = "main"

    # Validate required params
    if not owner or not repo:
        return {"status": "no_owner_repo", "message": "Missing repo owner or name on Post or Site"}

    try:
        # Diagnostic: log attempted delete parameters
        try:
            import logging

            logging.getLogger(__name__).debug("delete_post_from_repo: owner=%s repo=%s path=%s branch=%s", owner, repo, path, branch)
        except Exception:
            pass

        res = client.delete_file(owner, repo, path, branch=branch, message=message)
    except Exception as e:
        # Return structured error dict instead of raising so callers (admin action) can handle it
        return {"status": "error", "message": str(e)}

    # Try to record audit in ExportJob if model available (best-effort, avoid hard dependency in test)
    try:
        from blog.models import ExportJob

        ExportJob.objects.create(
            post=post,
            commit_sha=res.get("commit_sha"),
            repo_url=None,
            branch=branch,
            path=path,
            export_status=("success" if res.get("status") in ("deleted", "already_absent") else "failed"),
            action=("delete_repo_and_db" if res.get("status") == "deleted" else "delete_db_only" if res.get("status") == "already_absent" else "delete_failed"),
            message=(None if res.get("status") in ("deleted", "already_absent") else str(res.get("message") or res)),
        )
    except Exception:
        # In environments without Django ORM available (e.g., unit tests without DB), skip audit creation.
        pass

    # Optionally sync local working copy (pull updates) so local files reflect remote deletion
    local_sync_msg = None
    if sync_local:
        try:
            site = getattr(post, "site", None)
            repo_dir = getattr(site, "repo_path", None) if site else None
            if repo_dir and os.path.isdir(repo_dir):
                # perform a git pull for the branch to reflect remote changes
                try:
                    subprocess.run(["git", "fetch", "origin"], cwd=repo_dir, check=False)
                    _branch = branch or "main"
                    pull = subprocess.run(["git", "pull", "origin", str(_branch)], cwd=repo_dir, capture_output=True, text=True, check=False)
                    local_sync_msg = pull.stdout + "\n" + pull.stderr
                except Exception as e:
                    local_sync_msg = f"local sync failed: {e}"
            else:
                local_sync_msg = "no local repo_path to sync"
        except Exception as e:
            local_sync_msg = f"local sync error: {e}"

    # Include local sync info in returned dict
    if local_sync_msg:
        res = dict(res)
        res["local_sync_message"] = local_sync_msg

    # If file already absent, attempt to provide quick diagnostics: list parent dir
    try:
        if res and res.get("status") == "already_absent":
            client = client or GitHubClient()
            parent = os.path.dirname(path) or ""
            listing = []
            try:
                if parent:
                    items = client.list_files(owner, repo, path=parent, branch=branch)
                else:
                    items = client.list_files(owner, repo, path="", branch=branch)
                listing = [it.get("path") for it in items if it.get("path")]
            except Exception:
                listing = ["<listing_failed>"]

            # Try alternative candidate paths in case stored path is slightly different
            candidates = []
            # original
            candidates.append(path)
            # try last_export_path if present and different
            lep = getattr(post, 'last_export_path', None)
            if lep and lep != path:
                candidates.append(lep)
            # try with/without posts_dir prefix
            site = getattr(post, 'site', None)
            posts_dir = getattr(site, 'posts_dir', None) if site else None
            if posts_dir:
                norm_posts = posts_dir.strip('/\\')
                if not path.startswith(norm_posts + '/'):
                    candidates.append(f"{norm_posts}/{path}")
                else:
                    # also try stripping prefix
                    candidates.append(path.split('/', 1)[-1])
            # basename only
            candidates.append(os.path.basename(path))

            tried = []
            deleted_response = None
            for cand in [c for c in candidates if c]:
                if cand == path:
                    continue
                try:
                    r2 = client.delete_file(owner, repo, cand, branch=branch, message=message)
                except Exception as e:
                    tried.append({'path': cand, 'error': str(e)})
                    continue
                tried.append({'path': cand, 'status': r2.get('status'), 'commit_sha': r2.get('commit_sha')})
                if r2.get('status') == 'deleted':
                    deleted_response = r2
                    break

            res = dict(res)
            res['diagnostic_listing_parent'] = {'parent': parent, 'sample': listing[:50]}
            res['diagnostic_delete_alternatives'] = tried
            if deleted_response:
                # merge deleted response as primary success
                res = dict(deleted_response)
                res['diagnostic_delete_alternatives'] = tried
    except Exception:
        pass

    return res
