from django.core.management.base import BaseCommand
from django.utils import timezone
from blog.models import Site, Post
from django.db import models
from blog import sync_parser
from blog.github_client import GitHubClient
from github import GithubException
from blog.signals import _SKIP_EXPORT
import json
import os
import logging
from blog.utils import create_categories_from_frontmatter
import re
import subprocess
import shutil
from django.core.management import call_command
from blog.models import ExportAudit

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scan configured repos and sync posts into DB (repo->DB). By default runs as dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--sites", help="Comma-separated site slugs to limit scan", default=None)
        parser.add_argument("--dry-run", action="store_true", help="Do not modify DB or repo")
        parser.add_argument("--apply", action="store_true", help="Apply changes to the DB (no deletes)")
        parser.add_argument("--report-path", help="Where to write JSON report", default="reports")
        parser.add_argument("--backup", action="store_true", help="Create backups before applying changes (branch + db dump)")
        parser.add_argument("--delete-pks", help="Comma-separated Post PKs to delete (use with --confirm).", default=None)
        parser.add_argument("--delete-mode", choices=["db-only", "repo-and-db"], default="db-only", help="When deleting posts, also remove file from repo")
        parser.add_argument("--confirm", action="store_true", help="Confirm destructive operations (must be used with --delete-pks)")

    def handle(self, *args, **options):
        slugs = options.get("sites")
        dry = options.get("dry_run")
        apply_changes = options.get("apply")
        report_path = options.get("report_path") or "reports"

        if apply_changes and dry:
            self.stdout.write(self.style.ERROR("Cannot use --apply together with --dry-run"))
            return

        qs = Site.objects.all()
        if slugs:
            wanted = [s.strip() for s in slugs.split(",") if s.strip()]
            qs = qs.filter(slug__in=wanted)

        os.makedirs(report_path, exist_ok=True)
        run_id = timezone.now().strftime("%Y%m%d%H%M%S")
        report = {"run_id": run_id, "sites": {}}
        mode_text = "dry-run" if dry else ("apply" if apply_changes else "dry-run")

        # Prepare a logfile. If caller sets SYNC_LOG_PATH env var we'll use it (allow admin UI to tail it)
        logs_dir = os.path.join(report_path, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        env_log_path = os.getenv("SYNC_LOG_PATH")
        if env_log_path:
            log_path = env_log_path
        else:
            log_path = os.path.join(logs_dir, f"sync-{run_id}.log")

        # Dual writer so all self.stdout.write(...) also goes into the logfile
        class _DualStdout:
            def __init__(self, primary, fh):
                self.primary = primary
                self.fh = fh

            def write(self, s):
                try:
                    prefix = timezone.now().isoformat() + " "
                except Exception:
                    prefix = ""
                # ensure s is a str
                try:
                    s_text = str(s)
                except Exception:
                    s_text = ""
                out_line = f"{prefix}{s_text}"
                try:
                    if self.primary:
                        self.primary.write(out_line)
                except Exception:
                    pass
                try:
                    if self.fh:
                        self.fh.write(out_line + ("\n" if not out_line.endswith("\n") else ""))
                        self.fh.flush()
                except Exception:
                    pass

            def flush(self):
                try:
                    if self.primary:
                        self.primary.flush()
                except Exception:
                    pass
                try:
                    if self.fh:
                        self.fh.flush()
                except Exception:
                    pass

        # open log file and wrap stdout
        file_handler = None
        root_handler = None
        orig_stdout = None
        try:
            fh = open(log_path, "a", encoding="utf-8")
        except Exception:
            fh = None
        if fh:
            # attach a file handler to module logger so logger.exception/.. go into the same file
            try:
                file_handler = logging.FileHandler(log_path, encoding="utf-8")
                file_handler.setLevel(logging.DEBUG)
                fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
                file_handler.setFormatter(fmt)
                logger.addHandler(file_handler)
                # also attach to root logger to be broader
                root = logging.getLogger()
                root.addHandler(file_handler)
                root_handler = file_handler
            except Exception:
                file_handler = None
                root_handler = None
            orig_stdout = self.stdout
            self.stdout = _DualStdout(orig_stdout, fh)

        self.stdout.write(self.style.NOTICE(f"Starting sync run {run_id} mode={mode_text}; log={log_path}"))

        # Ensure we restore stdout/handlers and close file at the end of the command
        cleanup_required = bool(fh)

        for site in qs:
            self.stdout.write(self.style.NOTICE(f"Processing site {site.slug} (mode={mode_text})"))
            posts_dir = (site.posts_dir or "_posts").strip()
            site_report = {"created": [], "updated": [], "unchanged": []}
            processed_paths = set()

            use_github = bool(site.repo_owner and site.repo_name)
            gh_client = None
            gh_files = None
            if use_github:
                try:
                    gh_client = GitHubClient()
                    gh_files = gh_client.list_files(site.repo_owner, site.repo_name, path=posts_dir, branch=(site.default_branch or "main"))
                except Exception as e:
                    logger.exception("GitHub listing failed for site %s: %s", site.slug, e)
                    gh_client = None
                    gh_files = None

            if use_github and gh_files is None:
                # fallback to local working copy but warn
                self.stdout.write(self.style.WARNING(f"Site {site.slug}: GitHub access failed, falling back to local working copy"))

            if gh_files is not None:
                # iterate over files reported by GitHub under posts_dir
                # Deduplicate by path in case GitHub recursion returned duplicates
                seen_paths = set()
                md_files = []
                from pathlib import PurePosixPath

                for f in gh_files:
                    raw_path = (f.get("path") or "")
                    if not raw_path.lower().endswith(".md"):
                        continue
                    # normalize as posix path and compute relpath relative to posts_dir when possible
                    p = PurePosixPath(raw_path)
                    # normalize posts_dir for comparison
                    pd = PurePosixPath(posts_dir) if posts_dir else None
                    canon = None
                    try:
                        if pd and pd != PurePosixPath("") and pd in p.parents:
                            # path contains posts_dir somewhere: compute path relative to posts_dir
                            # e.g. _posts/2025-... -> 2025-.../file.md
                            # find the subpath starting at posts_dir
                            parts = p.parts
                            # find index where posts_dir (possibly with same name) starts
                            for i in range(len(parts)):
                                if parts[i] == pd.name:
                                    canon = PurePosixPath(*parts[i+1:]).as_posix()
                                    break
                        if canon is None:
                            # fallback: use relative path from repo root (strip leading /)
                            canon = p.as_posix().lstrip("/")
                    except Exception:
                        canon = p.name
                    if canon in seen_paths:
                        continue
                    seen_paths.add(canon)
                    # store canonical rel_path on meta for downstream use
                    f["_canon_rel_path"] = canon
                    md_files.append(f)

                self.stdout.write(self.style.NOTICE(f"Site {site.slug}: found {len(md_files)} markdown files on GitHub; beginning processing"))
                # First pass: fetch and parse all files to build a plan and run audit checks before any write
                plan_items = []
                site_warnings = []
                from blog.utils import slug_from_filename

                for fmeta in md_files:
                    full_path = fmeta.get("path") or ""
                    # Compute rel_path relative to posts_dir, prefer canonical rel path set during dedupe
                    if fmeta.get("_canon_rel_path"):
                        rel_path = fmeta.get("_canon_rel_path")
                    else:
                        if posts_dir and full_path.startswith(posts_dir + "/"):
                            rel_path = full_path[len(posts_dir) + 1 :]
                        elif posts_dir and full_path == posts_dir:
                            rel_path = os.path.basename(full_path)
                        else:
                            # fallback: use basename
                            rel_path = os.path.basename(full_path) or full_path

                    if rel_path in processed_paths:
                        continue

                    if not gh_client:
                        logger.warning("No GitHub client available for site %s despite files present", site.slug)
                        continue

                    try:
                        gf = gh_client.get_file(site.repo_owner, site.repo_name, full_path, branch=(site.default_branch or "main"))
                        content = gf.get("content") or ""
                        commit_sha = gf.get("sha")
                    except Exception as e:
                        logger.exception("Failed to fetch %s from GitHub for site %s: %s", full_path, site.slug, e)
                        continue

                    fm, body = sync_parser.split_front_matter(content)
                    fallback_body = None
                    if isinstance(fm, dict):
                        fallback_body = fm.get("description") or fm.get("excerpt") or fm.get("summary")
                    if not (body and body.strip()):
                        body = (fallback_body or "").strip()
                    if not (body and body.strip()):
                        title_fallback = (fm.get("title") or os.path.splitext(os.path.basename(rel_path))[0].split("-", 1)[-1])
                        body = f"# {title_fallback}\n\n(Imported without body)"

                    h = sync_parser.compute_exported_hash(fm, body)
                    # Slug: prefer front-matter; otherwise use anchored filename fallback
                    if isinstance(fm, dict) and fm.get("slug"):
                        slug = fm.get("slug")
                        slug_source = 'front_matter'
                    else:
                        slug = slug_from_filename(os.path.basename(rel_path))
                        slug_source = 'filename'

                    # Audit candidate slug for suspicious patterns
                    s_normal = (slug or '').lower()
                    reasons = []
                    if re.match(r'^\d{2}-\d{2}-', s_normal):
                        reasons.append('starts-with-partial-date')
                    if len(s_normal) > 75:
                        reasons.append('too-long')
                    if re.search(r'[^a-z0-9-]', s_normal):
                        reasons.append('invalid-chars')
                    if reasons:
                        site_warnings.append({"path": rel_path, "slug": slug, "reasons": reasons})

                    plan_items.append({
                        'rel_path': rel_path,
                        'full_path': full_path,
                        'content': content,
                        'commit_sha': commit_sha,
                        'fm': fm,
                        'body': body,
                        'hash': h,
                        'slug': slug,
                        'slug_source': slug_source,
                    })

                # If applying changes, abort if audit found warnings for this site
                if apply_changes and site_warnings:
                    self.stdout.write(self.style.ERROR(f"Aborting apply for site {site.slug}: slug audit found {len(site_warnings)} issues."))
                    for w in site_warnings:
                        self.stdout.write(self.style.ERROR(f"  {w['path']}: slug={w['slug']} reasons={w['reasons']}"))
                    # Skip applying for this site
                    report['sites'][site.slug] = site_report
                    # mark processed to avoid partial changes
                    continue

                # Second pass: perform the same operations as before but using prepared plan_items
                for item in plan_items:
                    rel_path = item['rel_path']
                    full_path = item['full_path']
                    content = item['content']
                    commit_sha = item['commit_sha']
                    fm = item['fm']
                    body = item['body']
                    h = item['hash']
                    slug = item['slug']
                    # Match order: repo_path exact -> exported_hash -> slug
                    post = Post.objects.filter(site=site, repo_path=rel_path).first()
                    if not post:
                        post = Post.objects.filter(site=site, exported_hash=h).first()
                    if not post:
                        post = Post.objects.filter(site=site, slug=slug).first()

                    if not post:
                        if rel_path in processed_paths:
                            continue
                        title = (fm.get("title") if isinstance(fm, dict) else None) or slug
                        author_name = fm.get("author") if isinstance(fm, dict) else None
                        existing = Post.objects.filter(site=site, repo_path=rel_path).first()
                        if not existing:
                            existing = Post.objects.filter(site=site, title__iexact=title).first()
                        if existing:
                            db_hash = existing.exported_hash or ""
                            processed_paths.add(rel_path)
                            if db_hash != h:
                                site_report["updated"].append({"path": rel_path, "hash": h, "post_id": existing.pk})
                                if apply_changes:
                                    Post.objects.filter(pk=existing.pk).update(content=body, exported_hash=h, last_exported_at=timezone.now(), repo_path=rel_path, repo_filename=(full_path or os.path.join(posts_dir or '', rel_path)))
                            else:
                                site_report["unchanged"].append({"path": rel_path, "hash": h, "post_id": existing.pk})
                            continue

                        processed_paths.add(rel_path)
                        site_report["created"].append({"path": rel_path, "hash": h, "slug": slug})
                        self.stdout.write(self.style.SUCCESS(f"  Created planned: {rel_path}"))
                        if apply_changes:
                            from blog.models import Author
                            p = Post(site=site, title=title, slug=slug, content=content or body, exported_hash=h, repo_path=rel_path, repo_filename=(full_path or os.path.join(posts_dir or '', rel_path)))
                            assigned = False
                            if author_name:
                                a = Author.objects.filter(name=author_name).first() or Author.objects.filter(slug=author_name).first()
                                if a:
                                    p.author = a
                                    assigned = True
                            if not assigned:
                                a = Author.objects.filter(site=site).first()
                                if a:
                                    p.author = a
                                    assigned = True
                            if not assigned:
                                slug_def = 'imported'
                                a, created = Author.objects.get_or_create(site=site, slug=slug_def, defaults={'name': 'Imported'})
                                p.author = a
                            status = (fm.get("status") if isinstance(fm, dict) else None) or "published"
                            published_at = (fm.get("date") if isinstance(fm, dict) else None) or (fm.get("published_at") if isinstance(fm, dict) else None)
                            if status:
                                p.status = status
                                if status == "published":
                                    try:
                                        from django.utils.dateparse import parse_datetime

                                        dt = parse_datetime(published_at) if published_at else None
                                        if dt:
                                            p.published_at = dt
                                        else:
                                            p.published_at = timezone.now()
                                    except Exception:
                                        p.published_at = timezone.now()
                            try:
                                if commit_sha:
                                    p.last_commit_sha = commit_sha
                                p.last_export_path = full_path or rel_path
                            except Exception:
                                pass
                            token = _SKIP_EXPORT.set(True)
                            try:
                                p.save()
                            finally:
                                _SKIP_EXPORT.reset(token)
                            try:
                                create_categories_from_frontmatter(p, fields=["categories", "cluster"], hierarchy="slash")
                            except Exception:
                                logger.exception("Failed to create categories from front-matter for post %s", getattr(p, 'pk', None))
                            self.stdout.write(self.style.SUCCESS(f"  Created: {rel_path} (id={p.pk})"))
                    else:
                        db_hash = post.exported_hash or ""
                        # Standardized mismatch logging: if the repo-derived slug differs from DB slug, log a clear message
                        try:
                            repo_slug_candidate = slug_from_filename(os.path.basename(rel_path)) if 'slug_from_filename' in globals() else None
                            if repo_slug_candidate and repo_slug_candidate != (post.slug or ''):
                                suggestion = 'rename+redirect' if post.slug_locked else 'align-front-matter-or-rename'
                                msg = {
                                    'type': 'slug_mismatch',
                                    'post_id': post.pk,
                                    'site': site.slug,
                                    'repo_filename': rel_path,
                                    'slug_db': post.slug,
                                    'slug_repo': repo_slug_candidate,
                                    'suggestion': suggestion,
                                }
                                self.stdout.write(self.style.WARNING(json.dumps(msg, ensure_ascii=False)))
                        except Exception:
                            pass
                        if db_hash != h:
                            site_report["updated"].append({"path": rel_path, "hash": h, "post_id": post.pk})
                            self.stdout.write(self.style.WARNING(f"  Update planned: {rel_path} -> post {post.pk}"))
                            if apply_changes:
                                try:
                                    # Update content with full original content (including front-matter)
                                        Post.objects.filter(pk=post.pk).update(
                                        content=content or (body or ""),
                                        exported_hash=h,
                                        last_exported_at=timezone.now(),
                                        repo_path=rel_path,
                                        repo_filename=rel_path,
                                        last_commit_sha=commit_sha or post.last_commit_sha,
                                        last_export_path=full_path or post.last_export_path,
                                    )
                                except Exception:
                                    logger.exception("Failed to update post %s with full metadata, falling back to minimal update", post.pk)
                                    # attempt a minimal update if the full one fails
                                    try:
                                        Post.objects.filter(pk=post.pk).update(
                                            content=content or (body or ""),
                                            exported_hash=h,
                                            last_exported_at=timezone.now(),
                                            repo_path=rel_path,
                                        )
                                    except Exception:
                                        logger.exception("Fallback update also failed for post %s", post.pk)
                                # After performing update(), refresh and create/assign categories from front-matter
                                try:
                                    post.refresh_from_db()
                                    create_categories_from_frontmatter(post, fields=["categories", "cluster"], hierarchy="slash")
                                except Exception:
                                    logger.exception("Failed to create categories from front-matter for updated post %s", getattr(post, 'pk', None))
                        else:
                            site_report["unchanged"].append({"path": rel_path, "hash": h, "post_id": post.pk})
                            # If content is identical but repo_path is missing or different, allow apply to associate it
                            try:
                                self.stdout.write(self.style.NOTICE(f"  Unchanged: {rel_path} (post {post.pk})"))
                                if apply_changes:
                                    # If post has no repo_path or differs from current rel_path, set it so mapping is recovered
                                    if (not post.repo_path) or (post.repo_path != rel_path):
                                        Post.objects.filter(pk=post.pk).update(repo_path=rel_path, last_export_path=(full_path or post.last_export_path), last_commit_sha=(commit_sha or post.last_commit_sha))
                                        self.stdout.write(self.style.SUCCESS(f"  Associated repo path: {rel_path} -> post {post.pk}"))
                                        try:
                                            post.refresh_from_db()
                                            create_categories_from_frontmatter(post, fields=["categories", "cluster"], hierarchy="slash")
                                        except Exception:
                                            logger.exception("Failed to create categories from front-matter when associating repo_path for post %s", getattr(post, 'pk', None))
                            except Exception:
                                logger.exception("Failed to associate repo_path for post %s", post.pk)
                        # mark processed to avoid reporting duplicates if the same path appears multiple times
                        processed_paths.add(rel_path)

                # Deduplicate report entries (preserve order)
                def _dedupe_list(items):
                    seen = set()
                    out = []
                    for it in items:
                        key = (it.get("path"), it.get("post_id"), it.get("hash"), it.get("slug"))
                        if key in seen:
                            continue
                        seen.add(key)
                        out.append(it)
                    return out

                site_report["created"] = _dedupe_list(site_report["created"])
                site_report["updated"] = _dedupe_list(site_report["updated"])
                site_report["unchanged"] = _dedupe_list(site_report["unchanged"])

                # Diagnostic counts to help understand mapping
                try:
                    unique_github_files = len(seen_paths) if 'seen_paths' in locals() else 0
                    db_repo_paths = Post.objects.filter(site=site).exclude(repo_path__isnull=True).count()
                except Exception:
                    unique_github_files = 0
                    db_repo_paths = 0

                site_report_meta = site_report.get("_meta", {})
                site_report_meta["unique_github_files"] = unique_github_files
                site_report_meta["db_repo_paths"] = db_repo_paths
                site_report["_meta"] = site_report_meta

                report["sites"][site.slug] = site_report
                self.stdout.write(self.style.SUCCESS(f"Site {site.slug}: created={len(site_report['created'])} updated={len(site_report['updated'])} unchanged={len(site_report['unchanged'])} (from GitHub). github_files={unique_github_files} db_repo_paths={db_repo_paths}"))
                continue

            # fallback: local working copy scanning
            repo = (site.repo_path or "").strip()
            if not repo or not os.path.isdir(repo):
                self.stdout.write(self.style.WARNING(f"Skipping site {site.slug}: repo missing {repo}"))
                continue
            total_local = 0
            for rel_path, abs_path in sync_parser.iter_post_files(repo, posts_dir=posts_dir):
                total_local += 1
            # Inform about local files count and mode
            self.stdout.write(self.style.NOTICE(f"Site {site.slug}: found {total_local} local markdown files; beginning processing (mode={mode_text})"))
            for rel_path, abs_path in sync_parser.iter_post_files(repo, posts_dir=posts_dir):
                try:
                    self.stdout.write(self.style.SQL_FIELD(f"  Processing: {rel_path}"))
                    with open(abs_path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                except Exception:
                    logger.exception("Cannot read %s", abs_path)
                    continue
                fm, body = sync_parser.split_front_matter(content)
                h = sync_parser.compute_exported_hash(fm, body)
                # Match order: repo_path exact -> exported_hash (fallback) -> slug
                slug = fm.get("slug") or os.path.splitext(os.path.basename(rel_path))[0].split("-", 1)[-1]
                post = Post.objects.filter(site=site, repo_path=rel_path).first()
                if not post:
                    post = Post.objects.filter(site=site, exported_hash=h).first()
                if not post:
                    post = Post.objects.filter(site=site, slug=slug).first()

                if not post:
                    # avoid processing same file twice in this run
                    if rel_path in processed_paths:
                        continue
                    title = fm.get("title") or slug
                    author_name = fm.get("author")
                    # Try extra matches: existing post with same title or same repo_path
                    # Prefer exact repo_path match, fallback to title match only if no repo_path found
                    existing = Post.objects.filter(site=site, repo_path=rel_path).first()
                    if not existing:
                        existing = Post.objects.filter(site=site, title__iexact=title).first()
                    if existing:
                        # Treat as update if hash differs, otherwise unchanged
                        db_hash = existing.exported_hash or ""
                        if db_hash != h:
                            site_report["updated"].append({"path": rel_path, "hash": h, "post_id": existing.pk})
                            if apply_changes:
                                Post.objects.filter(pk=existing.pk).update(content=body or "", exported_hash=h, last_exported_at=timezone.now(), repo_path=rel_path)
                        else:
                            site_report["unchanged"].append({"path": rel_path, "hash": h, "post_id": existing.pk})
                        processed_paths.add(rel_path)
                        continue

                    site_report["created"].append({"path": rel_path, "hash": h, "slug": slug})
                    # mark path processed to avoid duplicates within same run
                    processed_paths.add(rel_path)
                    self.stdout.write(self.style.SUCCESS(f"  Created planned: {rel_path}"))
                    if apply_changes:
                        # create Post with optional front-matter enrichment
                        author_name = fm.get("author")
                        # Default to published when importing from repo (repo content is typically published)
                        status = fm.get("status") or "published"
                        published_at = fm.get("date") or fm.get("published_at")
                        # Create Post and record repo path immediately
                        p = Post(site=site, title=title, slug=slug, content=body or "", exported_hash=h, repo_path=rel_path)
                        # Assign author if present, otherwise try to pick a site default or create a fallback
                        from blog.models import Author
                        assigned = False
                        if author_name:
                            a = Author.objects.filter(name=author_name).first() or Author.objects.filter(slug=author_name).first()
                            if a:
                                p.author = a
                                assigned = True
                        if not assigned:
                            # try to use any existing author for the site
                            a = Author.objects.filter(site=site).first()
                            if a:
                                p.author = a
                                assigned = True
                        if not assigned:
                            # create a fallback author 'imported' under the site
                            slug_def = 'imported'
                            a, created = Author.objects.get_or_create(site=site, slug=slug_def, defaults={'name': 'Imported'})
                            p.author = a
                        # Apply status and published_at: if published, prefer front-matter date else now
                        if status:
                            p.status = status
                            if status == "published":
                                try:
                                    from django.utils.dateparse import parse_datetime

                                    dt = parse_datetime(published_at) if published_at else None
                                    if dt:
                                        p.published_at = dt
                                    else:
                                        p.published_at = timezone.now()
                                except Exception:
                                    p.published_at = timezone.now()
                        # Avoid triggering post_save export/publish hooks while importing
                        token = _SKIP_EXPORT.set(True)
                        try:
                            p.save()
                        finally:
                            _SKIP_EXPORT.reset(token)
                        self.stdout.write(self.style.SUCCESS(f"  Created: {rel_path} (id={p.pk})"))
                else:
                    # compute if content differs
                    db_hash = post.exported_hash or ""
                    if db_hash != h:
                        site_report["updated"].append({"path": rel_path, "hash": h, "post_id": post.pk})
                        self.stdout.write(self.style.WARNING(f"  Update planned: {rel_path} -> post {post.pk}"))
                        if apply_changes:
                            # update metadata and content safely using update()
                            Post.objects.filter(pk=post.pk).update(content=body or "", exported_hash=h, last_exported_at=timezone.now(), repo_path=rel_path)
                        else:
                            site_report["unchanged"].append({"path": rel_path, "hash": h, "post_id": post.pk})
                            try:
                                self.stdout.write(self.style.NOTICE(f"  Unchanged: {rel_path} (post {post.pk})"))
                                if apply_changes:
                                    if (not post.repo_path) or (post.repo_path != rel_path):
                                        Post.objects.filter(pk=post.pk).update(repo_path=rel_path, last_export_path=rel_path)
                                        self.stdout.write(self.style.SUCCESS(f"  Associated repo path: {rel_path} -> post {post.pk}"))
                            except Exception:
                                logger.exception("Failed to associate repo_path for post %s", post.pk)

            report["sites"][site.slug] = site_report
            # simple output summary per site
            self.stdout.write(self.style.SUCCESS(f"Site {site.slug}: created={len(site_report['created'])} updated={len(site_report['updated'])} unchanged={len(site_report['unchanged'])}"))

        out_file = os.path.join(report_path, f"sync-report-{run_id}.json")
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

        self.stdout.write(self.style.SUCCESS(f"Report written to {out_file}"))

        # Record audit of the sync run
        try:
            # create one audit per run; include whole report and associate with sites where possible
            for slug, site_report in report.get('sites', {}).items():
                try:
                    s = Site.objects.get(slug=slug)
                except Exception:
                    s = None
                ExportAudit.objects.create(run_id=run_id, action=("sync:apply" if apply_changes else "sync:dry-run"), site=s, summary={slug: site_report})
        except Exception:
            logger.exception("Unable to write ExportAudit record")

        # Deletion flow: remove posts specified by --delete-pks
        delete_pks = options.get("delete_pks")
        delete_mode = options.get("delete_mode") or "db-only"
        confirm = options.get("confirm")
        do_backup = options.get("backup")

        if delete_pks:
            if not confirm:
                self.stdout.write(self.style.ERROR("Deletion requested but --confirm not provided. Aborting."))
                return
            # prepare backups dir
            backups_dir = os.path.join("backups", run_id)
            os.makedirs(backups_dir, exist_ok=True)
            pks = [int(x) for x in delete_pks.split(",") if x.strip()]
            # dump selected rows
            dumpfile = os.path.join(backups_dir, f"posts-{run_id}.json")
            try:
                call_command("dumpdata", "blog.Post", "--pks", ",".join(str(x) for x in pks), "--output", dumpfile)
                self.stdout.write(self.style.SUCCESS(f"Dumped posts to {dumpfile}"))
            except Exception:
                logger.exception("Failed to dump posts")

            # For each post, optionally archive file in repo then delete DB row
            for pk in pks:
                try:
                    post = Post.objects.get(pk=pk)
                except Post.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Post {pk} does not exist, skipping"))
                    continue
                site = post.site
                repo = (site.repo_path or "").strip()
                repo_file = post.repo_path or post.last_export_path or None
                if repo_file and repo and os.path.isdir(repo):
                    full_path = os.path.join(repo, repo_file)
                else:
                    full_path = None

                if delete_mode == "repo-and-db" and full_path and os.path.exists(full_path):
                    # archive file inside repo
                    archive_dir = os.path.join(repo, "archive", run_id)
                    os.makedirs(archive_dir, exist_ok=True)
                    dest = os.path.join(archive_dir, os.path.basename(full_path))
                    try:
                        shutil.move(full_path, dest)
                        # commit the change
                        try:
                            subprocess.run(["git", "add", "--all"], cwd=repo, check=False)
                            subprocess.run(["git", "commit", "-m", f"chore(blog): archive deleted post {post.slug} ({run_id})"], cwd=repo, check=False)
                        except Exception:
                            logger.exception("Git operations failed for archiving %s", full_path)
                        self.stdout.write(self.style.SUCCESS(f"Archived {full_path} -> {dest}"))
                    except Exception:
                        logger.exception("Failed to archive %s", full_path)

                # finally delete from DB
                try:
                    post.delete()
                    self.stdout.write(self.style.SUCCESS(f"Deleted Post {pk} from DB"))
                except Exception:
                    logger.exception("Failed to delete Post %s", pk)

            # record audit for deletion
            try:
                ExportAudit.objects.create(run_id=run_id, action=f"delete:{delete_mode}", site=None, summary={"pks": pks})
            except Exception:
                logger.exception("Unable to write ExportAudit record for delete")

        # cleanup logfile and logging handlers
        try:
            if fh:
                try:
                    # restore original stdout wrapper
                    if 'orig_stdout' in locals():
                        self.stdout = orig_stdout
                except Exception:
                    pass
                try:
                    fh.close()
                except Exception:
                    pass
                try:
                    root = logging.getLogger()
                    if root_handler:
                        root.removeHandler(root_handler)
                    if file_handler:
                        logger.removeHandler(file_handler)
                except Exception:
                    pass
        except Exception:
            pass
