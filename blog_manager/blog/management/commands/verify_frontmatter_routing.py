from django.core.management.base import BaseCommand
from django.conf import settings
import os
import re
import yaml
import logging
from blog.models import Site, Post
from blog.exporter import (
    _extract_frontmatter_from_body, 
    _validate_frontmatter_taxonomy,
    FrontMatterValidationError,
    build_post_relpath,
    _handle_file_move
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Verify front-matter and file paths are consistent, optionally fix with --apply'

    def add_arguments(self, parser):
        parser.add_argument(
            '--site',
            type=str,
            help='Site slug to check (if not provided, checks all sites)'
        )
        parser.add_argument(
            '--repo-base',
            type=str,
            default=getattr(settings, 'BLOG_REPO_BASE', ''),
            help='Base directory for exported repos'
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply fixes (default is dry-run)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose logging'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate export operations without making changes'
        )
        parser.add_argument(
            '--collision-policy',
            choices=['fail', 'increment'],
            default='increment',
            help='Collision handling policy (default: increment)'
        )

    def handle(self, *args, **options):
        if options['verbose']:
            logging.basicConfig(level=logging.DEBUG)
        
        site_slug = options['site']
        repo_base = options['repo_base']
        apply_fixes = options['apply']
        dry_run = options['dry_run']
        collision_policy = options['collision_policy']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🧪 DRY-RUN MODE: No changes will be made'))
        
        if not repo_base:
            self.stdout.write(self.style.ERROR('BLOG_REPO_BASE not configured'))
            return
        
        # Get sites to check
        sites = Site.objects.all()
        if site_slug:
            sites = sites.filter(slug=site_slug)
            if not sites.exists():
                self.stdout.write(self.style.ERROR(f'Site "{site_slug}" not found'))
                return
        
        total_issues = 0
        total_fixes = 0
        
        for site in sites:
            issues, fixes = self._check_site(site, repo_base, apply_fixes)
            total_issues += issues
            total_fixes += fixes
        
        if apply_fixes:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Completed: {total_fixes} fixes applied, {total_issues - total_fixes} issues remain')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'🔍 Dry-run: {total_issues} issues found (use --apply to fix)')
            )
    
    def _check_site(self, site, repo_base, apply_fixes):
        """Check a single site for front-matter/path consistency."""
        site_slug = site.slug
        repo_dir = os.path.join(repo_base, site_slug)
        
        if not os.path.isdir(repo_dir):
            self.stdout.write(f'⚠️  Site {site_slug}: repo directory not found at {repo_dir}')
            return 0, 0
        
        self.stdout.write(f'\n📁 Checking site: {site_slug}')
        
        issues_found = 0
        fixes_applied = 0
        
        # Check all posts for this site
        posts = Post.objects.filter(site=site)
        
        for post in posts:
            try:
                issues, fixes = self._check_post(post, site, repo_dir, apply_fixes)
                issues_found += issues
                fixes_applied += fixes
            except Exception as e:
                self.stdout.write(f'❌ Error checking post {post.pk}: {e}')
                issues_found += 1
        
        # Scan repository for orphaned files
        orphan_issues, orphan_fixes = self._check_orphaned_files(site, repo_dir, apply_fixes)
        issues_found += orphan_issues
        fixes_applied += orphan_fixes
        
        return issues_found, fixes_applied
    
    def _check_post(self, post, site, repo_dir, apply_fixes):
        """Check a single post for front-matter/path consistency."""
        issues = 0
        fixes = 0
        
        post_id = post.pk
        body = getattr(post, 'content', '') or getattr(post, 'body', '') or ''
        
        if not body.strip():
            self.stdout.write(f'⚠️  Post {post_id}: empty content')
            return 1, 0
        
        try:
            # Extract and validate front-matter
            fm_data = _extract_frontmatter_from_body(body)
            cluster, subcluster, audit_msgs = _validate_frontmatter_taxonomy(post, fm_data)
            
            # Calculate expected path
            expected_path = build_post_relpath(post, site, fm_data)
            
            # Get current path
            current_path = getattr(post, 'last_export_path', None)
            
            if not current_path:
                self.stdout.write(f'⚠️  Post {post_id}: no last_export_path recorded')
                issues += 1
                if apply_fixes:
                    # This will be fixed on next export
                    pass
            elif current_path != expected_path:
                self.stdout.write(f'🔄 Post {post_id}: path mismatch')
                self.stdout.write(f'     Current:  {current_path}')
                self.stdout.write(f'     Expected: {expected_path}')
                issues += 1
                
                if apply_fixes:
                    try:
                        moved = _handle_file_move(repo_dir, current_path, expected_path)
                        if moved:
                            # Update post metadata
                            post.last_export_path = expected_path
                            post.save(update_fields=['last_export_path'])
                            self.stdout.write(f'✅ Post {post_id}: moved and updated metadata')
                            fixes += 1
                        else:
                            self.stdout.write(f'ℹ️  Post {post_id}: no file to move')
                    except Exception as e:
                        self.stdout.write(f'❌ Post {post_id}: move failed: {e}')
            else:
                # Path is correct, check if file exists
                file_path = os.path.join(repo_dir, current_path)
                if not os.path.exists(file_path):
                    self.stdout.write(f'⚠️  Post {post_id}: file missing at {current_path}')
                    issues += 1
                    # File missing will be recreated on next export
        
        except FrontMatterValidationError as e:
            self.stdout.write(f'❌ Post {post_id}: front-matter validation failed: {e}')
            issues += 1
            # Cannot auto-fix validation errors
        
        except Exception as e:
            self.stdout.write(f'❌ Post {post_id}: unexpected error: {e}')
            issues += 1
        
        return issues, fixes
    
    def _check_orphaned_files(self, site, repo_dir, apply_fixes):
        """Check for files in repo that don't correspond to posts."""
        issues = 0
        fixes = 0
        
        posts_dir = os.path.join(repo_dir, '_posts')
        if not os.path.exists(posts_dir):
            return 0, 0
        
        # Get all markdown files in _posts
        md_files = []
        for root, dirs, files in os.walk(posts_dir):
            for file in files:
                if file.endswith('.md'):
                    rel_path = os.path.relpath(os.path.join(root, file), repo_dir)
                    md_files.append(rel_path)
        
        # Get all expected paths from posts
        expected_paths = set()
        for post in Post.objects.filter(site=site):
            path = getattr(post, 'last_export_path', None)
            if path:
                expected_paths.add(path)
        
        # Find orphaned files
        orphaned = [f for f in md_files if f not in expected_paths]
        
        if orphaned:
            self.stdout.write(f'\n🗑️  Found {len(orphaned)} orphaned files:')
            for orphan in orphaned:
                self.stdout.write(f'     {orphan}')
                issues += 1
                
                if apply_fixes:
                    # Move to _archive directory
                    archive_dir = os.path.join(repo_dir, '_archive')
                    os.makedirs(archive_dir, exist_ok=True)
                    
                    src = os.path.join(repo_dir, orphan)
                    dst = os.path.join(archive_dir, os.path.basename(orphan))
                    
                    # Handle name collisions
                    counter = 1
                    while os.path.exists(dst):
                        name, ext = os.path.splitext(os.path.basename(orphan))
                        dst = os.path.join(archive_dir, f'{name}-{counter}{ext}')
                        counter += 1
                    
                    try:
                        os.rename(src, dst)
                        self.stdout.write(f'✅ Archived: {orphan} -> _archive/{os.path.basename(dst)}')
                        fixes += 1
                    except Exception as e:
                        self.stdout.write(f'❌ Failed to archive {orphan}: {e}')
        
        return issues, fixes