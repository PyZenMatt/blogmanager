Sync specification for repo↔DB synchronization

Goal
----
Provide a controlled, auditable synchronization mechanism between working repositories (Jekyll-style markdown repos) and the Django `Post` database. The initial implementation will be "repo-authoritative" (repos are source of truth) and support dry-runs, safe apply, and an optional safe deletion workflow.

Principles
----------
- Safe by default: destructive actions require `--confirm` and create backups.
- Dry-run first: every operator must be able to run `--dry-run` for review.
- Idempotent: repeated sync runs should not produce spurious changes.
- Auditable: each run produces a report and stores an `ExportAudit` entry with actions.
- Non-invasive: updates to metadata must avoid triggering export signals that would create loops.

High-level flow (repo -> DB)
-----------------------------
1. Discover repositories
   - Use configured `Site` records to find repo paths (`Site.repo_path` or `BLOG_REPO_BASE/<site.slug>`).
   - Skip repos that are not accessible or not valid git working copies (optionally clone if configured).

2. Enumerate post files
   - For each repo, find post files under the configured `_posts/` or configured `post_root`.
   - Normalize relative path `rel_path` and validate (no `..`, no absolute).

3. Parse file content
   - Use the same parser as exporter (front matter YAML + body) to extract fields: `title`, `slug`, `date`, `tags`, `excerpt`, and any extra front matter used by the app.
   - Compute `exported_hash` using canonical serialization of front matter + body (sha256 of bytes normalized by newline style).

4. Match to DB
   - Primary match: `exported_hash` -> Post
   - Secondary: `site` + `slug` (+ `rel_path`) -> Post
   - Tertiary: content hash or filename heuristics

5. Decide action
   - If no match: `create` candidate
   - If match but metadata/content differs: `update` candidate (include which fields changed)
   - If match and identical: `unchanged`

6. Report
   - Produce a per-repo, per-file report: created/updated/unchanged with diffs for updates.
   - Save report JSON to `reports/sync-<site>-<ts>.json` and record an `ExportAudit` entry.

7. Apply (only when `--apply` and not `--dry-run`)
   - Create and commit DB and repo backups (see Backup section).
   - Apply DB updates using `objects.filter(pk=...).update(...)` or `bulk_create`/`bulk_update`.
   - Avoid signals: use the ContextVar `_SKIP_EXPORT` or update via QuerySet to prevent re-export loops.

Deletion workflow
-----------------
- Two-step only:
  1. `--delete --dry-run` to list candidates (files removed from repo but present in DB, or explicit `--prune-orphaned` mode).
  2. `--delete --confirm --backup` creates repo branch `pre-delete-<ts>` and dumps DB rows, then removes files from repo (move to `archive/<ts>/` or remove and commit) and deletes DB rows (or marks soft-delete depending on configuration).

Backup strategy
---------------
- Repo backup: create branch `sync-backup-<ts>` and optionally push; or create a bundle `repo-<ts>.bundle` stored in `backups/`.
- DB backup: dump selected rows with `manage.py dumpdata` filtered by PKs, stored in `backups/`.
- Store manifest `backups/manifest-<ts>.json` describing actions, files and DB dump locations.

Audit & reporting
-----------------
- `ExportAudit` model fields:
  - `site` (FK), `run_id` (uuid), `action` (sync, delete, backup), `summary` (json), `user` (optional), `timestamp`.
- Reports saved as both JSON and human-readable text.

CLI surface
-----------
`python manage.py sync_repos [--sites=slug,slug] [--dry-run] [--apply] [--delete] [--confirm] [--backup] [--threads=N] [--report-path=path]`

Acceptance criteria for initial implementation
----------------------------------------------
- Can scan at least one repo and produce a dry-run report listing create/update candidates.
- Creates deterministic `exported_hash` for files and matches posts by `exported_hash` or `slug`.
- Does not modify DB or repo when `--dry-run` is used.
- Writes a JSON report and an `ExportAudit` record for the run.

Security & operational notes
----------------------------
- Never write secrets to git commits. Don't add `.env` or other secrets via sync operations.
- Ensure operator performs PAT rotation and uses least-privilege tokens if pushing backup branches.

Next steps
----------
- Implement `ExportAudit` model and migration.
- Implement `blog/sync_parser.py` to reuse exporter parsing code.
- Scaffold `management/commands/sync_repos.py` implementing dry-run scanning for a single site.
